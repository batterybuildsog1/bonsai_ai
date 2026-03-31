from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.util.element
import numpy as np


AI_PSET = "Pset_BonsaiAI"


@dataclass
class ExecutionResult:
    tool_name: str
    element_name: str
    message: str
    ifc_class: Optional[str] = None
    global_id: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)


class AuthoringError(RuntimeError):
    pass


class IfcAuthor:
    def __init__(self, path: str):
        self.path = path
        self.model = ifcopenshell.open(path) if os.path.exists(path) else ifcopenshell.api.project.create_file(version="IFC4")
        # Perf: cache hierarchy check and body context to avoid repeated entity scans
        self._hierarchy_ready = False
        self._cached_body_context = None
        self._ensure_contexts()

    def _ensure_contexts(self) -> None:
        if not self.model.by_type("IfcProject"):
            return
        if not self.body_context:
            model3d = self._find_model_context()
            if model3d is None:
                model3d = ifcopenshell.api.context.add_context(self.model, context_type="Model")
            ifcopenshell.api.context.add_context(
                self.model,
                context_type="Model",
                context_identifier="Body",
                target_view="MODEL_VIEW",
                parent=model3d,
            )
            # Perf: invalidate body_context cache after creating new context
            self._cached_body_context = None

    @property
    def body_context(self):
        # Perf: cache body_context to avoid repeated linear scans of IFC entities
        if self._cached_body_context is not None:
            return self._cached_body_context
        for context in self.model.by_type("IfcGeometricRepresentationSubContext"):
            if (
                getattr(context, "ContextType", None) == "Model"
                and getattr(context, "ContextIdentifier", None) == "Body"
                and getattr(context, "TargetView", None) == "MODEL_VIEW"
            ):
                self._cached_body_context = context
                return context
        return None

    def _find_model_context(self):
        for context in self.model.by_type("IfcGeometricRepresentationContext"):
            if getattr(context, "ContextType", None) == "Model":
                return context
        return None

    @staticmethod
    def _unit_vector(vector: np.ndarray) -> np.ndarray:
        length = float(np.linalg.norm(vector))
        if length <= 1e-9:
            raise AuthoringError("Cannot normalize a zero-length vector")
        return vector / length

    def _member_transform(self, start: np.ndarray, end: np.ndarray) -> tuple[np.ndarray, float]:
        direction = self._unit_vector(end - start)
        reference = np.array([0.0, 0.0, 1.0])
        if abs(float(np.dot(direction, reference))) > 0.999:
            reference = np.array([0.0, 1.0, 0.0])
        local_x = self._unit_vector(np.cross(reference, direction))
        local_y = self._unit_vector(np.cross(direction, local_x))
        matrix = np.eye(4)
        matrix[0:3, 0] = local_x
        matrix[0:3, 1] = local_y
        matrix[0:3, 2] = direction
        matrix[0:3, 3] = start
        length = float(np.linalg.norm(end - start))
        return matrix, length

    def _ensure_project_hierarchy(
        self,
        project_name: str = "AI Project",
        site_name: str = "Default Site",
        building_name: str = "Main Building",
    ) -> None:
        # Perf: skip repeated linear scan if hierarchy was already confirmed
        if self._hierarchy_ready:
            return
        if self.model.by_type("IfcProject"):
            self._ensure_contexts()
            self._hierarchy_ready = True
            return
        project = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcProject", name=project_name)
        length_unit = ifcopenshell.api.unit.add_si_unit(self.model, unit_type="LENGTHUNIT")
        area_unit = ifcopenshell.api.unit.add_si_unit(self.model, unit_type="AREAUNIT")
        volume_unit = ifcopenshell.api.unit.add_si_unit(self.model, unit_type="VOLUMEUNIT")
        ifcopenshell.api.unit.assign_unit(self.model, units=[length_unit, area_unit, volume_unit])
        model3d = ifcopenshell.api.context.add_context(self.model, context_type="Model")
        ifcopenshell.api.context.add_context(
            self.model,
            context_type="Model",
            context_identifier="Body",
            target_view="MODEL_VIEW",
            parent=model3d,
        )
        site = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcSite", name=site_name)
        building = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcBuilding", name=building_name)
        ifcopenshell.api.aggregate.assign_object(self.model, products=[site], relating_object=project)
        ifcopenshell.api.aggregate.assign_object(self.model, products=[building], relating_object=site)
        self._hierarchy_ready = True

    def _find_by_name(self, ifc_class: str, name: str):
        for entity in self.model.by_type(ifc_class):
            if getattr(entity, "Name", None) == name:
                return entity
        return None

    def _metadata(self, product) -> Dict[str, object]:
        raw = ifcopenshell.util.element.get_psets(product, psets_only=True, should_inherit=False).get(AI_PSET, {})
        parsed: Dict[str, object] = {}
        for key, value in raw.items():
            if isinstance(value, str) and value[:1] in {"{", "["}:
                try:
                    parsed[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    pass
            parsed[key] = value
        return parsed

    def _write_metadata(self, product, properties: Dict[str, object]) -> None:
        properties = self._normalize_metadata(properties)
        pset = None
        for definition in getattr(product, "IsDefinedBy", []) or []:
            rel_def = getattr(definition, "RelatingPropertyDefinition", None)
            if rel_def and rel_def.is_a("IfcPropertySet") and rel_def.Name == AI_PSET:
                pset = rel_def
                break
        if pset is None:
            pset = ifcopenshell.api.pset.add_pset(self.model, product=product, name=AI_PSET)
        ifcopenshell.api.pset.edit_pset(self.model, pset=pset, properties=self._normalize_metadata(properties))

    @staticmethod
    def _normalize_metadata(properties: Dict[str, object]) -> Dict[str, object]:
        normalized: Dict[str, object] = {}
        for key, value in properties.items():
            if value is None:
                continue
            if isinstance(value, np.generic):
                normalized[key] = value.item()
            elif isinstance(value, (dict, list, tuple, set)):
                normalized[key] = json.dumps(value, sort_keys=True)
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _merged_metadata(base: Dict[str, object], extra: Dict[str, object]) -> Dict[str, object]:
        merged = dict(base)
        merged.update({key: value for key, value in extra.items() if value is not None})
        return merged

    @staticmethod
    def _dict_payload(payload: Dict[str, object], key: str) -> Dict[str, object]:
        value = payload.get(key)
        return dict(value) if isinstance(value, dict) else {}

    @classmethod
    def _presentation_metadata(cls, payload: Dict[str, object]) -> Dict[str, object]:
        presentation = cls._dict_payload(payload, "presentation")
        legacy_pairs = {
            "presentation_style": "presentation_style",
            "material_key": "material_key",
            "glass_material_key": "glass_material_key",
            "frame_material_key": "frame_material_key",
            "window_type": "window_type",
            "frame_style": "frame_style",
            "glazing_style": "glazing_style",
            "transparency": "transparency",
            "mullion_pattern": "mullion_pattern",
            "is_storefront": "is_storefront",
        }
        for legacy_key, canonical_key in legacy_pairs.items():
            if canonical_key not in presentation and payload.get(legacy_key) is not None:
                presentation[canonical_key] = payload[legacy_key]
        return presentation

    @classmethod
    def _foundation_metadata(cls, payload: Dict[str, object]) -> Dict[str, object]:
        foundation = cls._dict_payload(payload, "foundation")
        legacy_pairs = {
            "foundation_type": "foundation_type",
            "bearing_elevation": "bearing_elevation",
            "support_for": "support_for",
            "soil_assumption": "soil_assumption",
            "structural_role": "structural_role",
            "load_combo": "load_combo",
            "imposed_load_kn": "imposed_load_kn",
            "imposed_load_kN": "imposed_load_kn",
            "service_reaction_kN": "service_reaction_kN",
            "service_reaction_kn": "service_reaction_kN",
            "allowable_bearing_kpa": "allowable_bearing_kpa",
            "concrete_strength_mpa": "concrete_strength_mpa",
            "rebar_yield_strength_mpa": "rebar_yield_strength_mpa",
            "rebar_grade": "rebar_grade",
            "rebar_weight_kg": "rebar_weight_kg",
            "total_rebar_weight_kg": "rebar_weight_kg",
            "rebar_bar_diameter_mm": "rebar_bar_diameter_mm",
            "rebar_spacing_mm": "rebar_spacing_mm",
            "rebar_layer_count": "rebar_layer_count",
            "rebar_schedule": "rebar_schedule",
            "basis_notes": "basis_notes",
            "basis_note": "basis_notes",
        }
        for legacy_key, canonical_key in legacy_pairs.items():
            if canonical_key not in foundation and payload.get(legacy_key) is not None:
                foundation[canonical_key] = payload[legacy_key]
        return foundation

    @classmethod
    def _material_ref(cls, payload: Dict[str, object], default: str) -> str:
        presentation = cls._presentation_metadata(payload)
        return str(presentation.get("material_key") or payload.get("material_key") or default)

    @classmethod
    def _glass_material_ref(cls, payload: Dict[str, object], default: str = "glass_default") -> str:
        presentation = cls._presentation_metadata(payload)
        return str(
            presentation.get("glass_material_key")
            or presentation.get("material_key")
            or payload.get("glass_material_key")
            or payload.get("material_key")
            or default
        )

    @staticmethod
    def _result(tool_name: str, product, element_name: str, message: str, metadata: Optional[Dict[str, object]] = None) -> ExecutionResult:
        return ExecutionResult(
            tool_name=tool_name,
            element_name=element_name,
            message=message,
            ifc_class=product.is_a() if product is not None else None,
            global_id=getattr(product, "GlobalId", None) if product is not None else None,
            metadata=metadata or {},
        )

    def ensure_project(self, project_name: str, site_name: str, building_name: str) -> ExecutionResult:
        self._ensure_project_hierarchy(project_name, site_name, building_name)
        project = self.model.by_type("IfcProject")[0] if self.model.by_type("IfcProject") else None
        return self._result("ensure_project", project, project_name, "Project hierarchy ready")

    def ensure_storey(self, name: str, elevation: float) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._find_by_name("IfcBuildingStorey", name)
        if storey is None:
            building = self.model.by_type("IfcBuilding")[0]
            storey = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcBuildingStorey", name=name)
            ifcopenshell.api.aggregate.assign_object(self.model, products=[storey], relating_object=building)
        storey.Elevation = float(elevation)
        matrix = np.eye(4)
        matrix[:, 3][0:3] = (0.0, 0.0, float(elevation))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=storey, matrix=matrix, is_si=True)
        self._write_metadata(storey, {"ElevationMeters": float(elevation), "StructuralKind": "storey"})
        return self._result(
            "ensure_storey",
            storey,
            name,
            f"Storey ready at {elevation}m",
            metadata={"storey_name": name, "elevation": float(elevation)},
        )

    def _require_storey(self, storey_name: str):
        storey = self._find_by_name("IfcBuildingStorey", storey_name)
        if storey is None:
            raise AuthoringError(f"Storey not found: {storey_name}")
        return storey

    def create_rectangular_slab(
        self,
        name: str,
        storey_name: str,
        x: float,
        y: float,
        z: float,
        length: float,
        width: float,
        thickness: float,
        rotation_deg: float = 0.0,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        slab = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcSlab", name=name)
        matrix = np.eye(4)
        angle = math.radians(float(rotation_deg))
        matrix[0, 0] = math.cos(angle)
        matrix[0, 1] = -math.sin(angle)
        matrix[1, 0] = math.sin(angle)
        matrix[1, 1] = math.cos(angle)
        matrix[:, 3][0:3] = (float(x), float(y), float(z))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=slab, matrix=matrix, is_si=True)
        rep = ifcopenshell.api.geometry.add_slab_representation(
            self.model,
            context=body,
            depth=float(thickness),
            polyline=[(0.0, 0.0), (float(length), 0.0), (float(length), float(width)), (0.0, float(width)), (0.0, 0.0)],
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=slab, representation=rep)
        ifcopenshell.api.spatial.assign_container(self.model, products=[slab], relating_structure=storey)
        element_metadata = self._merged_metadata(
            {
                "OriginX": float(x),
                "OriginY": float(y),
                "OriginZ": float(z),
                "Length": float(length),
                "Width": float(width),
                "Thickness": float(thickness),
                "RotationDegrees": float(rotation_deg),
                "StructuralKind": "slab",
                "MaterialRef": self._material_ref(semantic_metadata, "concrete_default"),
                "SectionRef": f"slab_{float(thickness):.4f}",
            },
            semantic_metadata,
        )
        self._write_metadata(slab, element_metadata)
        return self._result(
            "create_rectangular_slab",
            slab,
            name,
            f"Created slab {length}m x {width}m",
            metadata=self._merged_metadata(
                {
                "storey_name": storey_name,
                "length": float(length),
                "width": float(width),
                "thickness": float(thickness),
                "rotation_deg": float(rotation_deg),
                "material_ref": self._material_ref(semantic_metadata, "concrete_default"),
                "section_ref": f"slab_{float(thickness):.4f}",
                },
                semantic_metadata,
            ),
        )

    def create_wall(
        self,
        name: str,
        storey_name: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        base_z: float,
        height: float,
        thickness: float,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        dx = float(end_x) - float(start_x)
        dy = float(end_y) - float(start_y)
        length = math.hypot(dx, dy)
        if length <= 0:
            raise AuthoringError(f"Wall {name} has zero length")
        angle = math.atan2(dy, dx)
        wall = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcWall", name=name)
        matrix = np.eye(4)
        matrix[0, 0] = math.cos(angle)
        matrix[0, 1] = -math.sin(angle)
        matrix[1, 0] = math.sin(angle)
        matrix[1, 1] = math.cos(angle)
        matrix[:, 3][0:3] = (float(start_x), float(start_y), float(base_z))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=wall, matrix=matrix, is_si=True)
        rep = ifcopenshell.api.geometry.add_wall_representation(
            self.model,
            context=body,
            length=length,
            height=float(height),
            thickness=float(thickness),
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=wall, representation=rep)
        ifcopenshell.api.spatial.assign_container(self.model, products=[wall], relating_structure=storey)
        element_metadata = self._merged_metadata(
            {
                "StartX": float(start_x),
                "StartY": float(start_y),
                "EndX": float(end_x),
                "EndY": float(end_y),
                "BaseZ": float(base_z),
                "Height": float(height),
                "Thickness": float(thickness),
                "StructuralKind": "wall",
                "MaterialRef": self._material_ref(semantic_metadata, "concrete_default"),
                "SectionRef": f"wall_{float(thickness):.4f}",
            },
            semantic_metadata,
        )
        self._write_metadata(wall, element_metadata)
        return self._result(
            "create_wall",
            wall,
            name,
            f"Created wall {length:.2f}m long",
            metadata=self._merged_metadata(
                {
                "storey_name": storey_name,
                "length": float(length),
                "height": float(height),
                "thickness": float(thickness),
                "material_ref": self._material_ref(semantic_metadata, "concrete_default"),
                "section_ref": f"wall_{float(thickness):.4f}",
                },
                semantic_metadata,
            ),
        )

    def create_column(
        self,
        name: str,
        storey_name: str,
        x: float,
        y: float,
        base_z: float,
        width: float,
        depth: float,
        height: float,
        rotation_deg: float = 0.0,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        angle = math.radians(float(rotation_deg))
        column = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcColumn", name=name)
        matrix = np.eye(4)
        matrix[0, 0] = math.cos(angle)
        matrix[0, 1] = -math.sin(angle)
        matrix[1, 0] = math.sin(angle)
        matrix[1, 1] = math.cos(angle)
        matrix[:, 3][0:3] = (float(x), float(y), float(base_z))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=column, matrix=matrix, is_si=True)
        profile = self.model.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            XDim=float(width),
            YDim=float(depth),
        )
        rep = ifcopenshell.api.geometry.add_profile_representation(
            self.model,
            context=body,
            profile=profile,
            depth=float(height),
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=column, representation=rep)
        ifcopenshell.api.spatial.assign_container(self.model, products=[column], relating_structure=storey)
        element_metadata = self._merged_metadata(
            {
                "OriginX": float(x),
                "OriginY": float(y),
                "BaseZ": float(base_z),
                "Width": float(width),
                "Depth": float(depth),
                "Height": float(height),
                "RotationDegrees": float(rotation_deg),
                "StructuralKind": "column",
                "MaterialRef": self._material_ref(semantic_metadata, "steel_default"),
                "SectionRef": f"column_{float(width):.4f}x{float(depth):.4f}",
            },
            semantic_metadata,
        )
        self._write_metadata(column, element_metadata)
        return self._result(
            "create_column",
            column,
            name,
            f"Created column {width:.2f}m x {depth:.2f}m",
            metadata=self._merged_metadata(
                {
                "storey_name": storey_name,
                "width": float(width),
                "depth": float(depth),
                "height": float(height),
                "rotation_deg": float(rotation_deg),
                "material_ref": self._material_ref(semantic_metadata, "steel_default"),
                "section_ref": f"column_{float(width):.4f}x{float(depth):.4f}",
                },
                semantic_metadata,
            ),
        )

    def create_beam(
        self,
        name: str,
        storey_name: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        base_z: float,
        width: float,
        depth: float,
        end_z: float | None = None,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        start = np.array([float(start_x), float(start_y), float(base_z)])
        end = np.array([float(end_x), float(end_y), float(base_z if end_z is None else end_z)])
        if np.linalg.norm(end - start) <= 0:
            raise AuthoringError(f"Beam {name} has zero length")
        matrix, length = self._member_transform(start, end)
        beam = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcBeam", name=name)
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=beam, matrix=matrix, is_si=True)
        profile = self.model.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            XDim=float(width),
            YDim=float(depth),
        )
        rep = ifcopenshell.api.geometry.add_profile_representation(
            self.model,
            context=body,
            profile=profile,
            depth=length,
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=beam, representation=rep)
        ifcopenshell.api.spatial.assign_container(self.model, products=[beam], relating_structure=storey)
        element_metadata = self._merged_metadata(
            {
                "StartX": float(start_x),
                "StartY": float(start_y),
                "EndX": float(end_x),
                "EndY": float(end_y),
                "BaseZ": float(base_z),
                "EndZ": float(base_z if end_z is None else end_z),
                "Width": float(width),
                "Depth": float(depth),
                "Length": float(length),
                "StructuralKind": "beam",
                "MaterialRef": self._material_ref(semantic_metadata, "steel_default"),
                "SectionRef": f"beam_{float(width):.4f}x{float(depth):.4f}",
            },
            semantic_metadata,
        )
        self._write_metadata(beam, element_metadata)
        return self._result(
            "create_beam",
            beam,
            name,
            f"Created beam {length:.2f}m long",
            metadata=self._merged_metadata(
                {
                "storey_name": storey_name,
                "length": float(length),
                "width": float(width),
                "depth": float(depth),
                "end_z": float(base_z if end_z is None else end_z),
                "material_ref": self._material_ref(semantic_metadata, "steel_default"),
                "section_ref": f"beam_{float(width):.4f}x{float(depth):.4f}",
                },
                semantic_metadata,
            ),
        )

    def create_panel(
        self,
        name: str,
        storey_name: str,
        x: float,
        y: float,
        base_z: float,
        width: float,
        height: float | None,
        depth: float | None,
        thickness: float,
        orientation: str = "vertical",
        rotation_deg: float = 0.0,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        angle = math.radians(float(rotation_deg))
        material_ref = self._material_ref(
            semantic_metadata,
            "steel_default" if orientation == "horizontal" else "concrete_default",
        )
        panel = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcPlate", name=name)
        matrix = np.eye(4)
        matrix[0, 0] = math.cos(angle)
        matrix[0, 1] = -math.sin(angle)
        matrix[1, 0] = math.sin(angle)
        matrix[1, 1] = math.cos(angle)
        matrix[:, 3][0:3] = (float(x), float(y), float(base_z))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=panel, matrix=matrix, is_si=True)
        if orientation == "horizontal":
            if depth is None:
                raise AuthoringError(f"Horizontal panel {name} requires a depth.")
            rep = ifcopenshell.api.geometry.add_slab_representation(
                self.model,
                context=body,
                depth=float(thickness),
                polyline=[
                    (0.0, 0.0),
                    (float(width), 0.0),
                    (float(width), float(depth)),
                    (0.0, float(depth)),
                    (0.0, 0.0),
                ],
            )
        else:
            if height is None:
                raise AuthoringError(f"Vertical panel {name} requires a height.")
            rep = ifcopenshell.api.geometry.add_wall_representation(
                self.model,
                context=body,
                length=float(width),
                height=float(height),
                thickness=float(thickness),
            )
        ifcopenshell.api.geometry.assign_representation(self.model, product=panel, representation=rep)
        ifcopenshell.api.spatial.assign_container(self.model, products=[panel], relating_structure=storey)
        element_metadata = self._merged_metadata(
            {
                "OriginX": float(x),
                "OriginY": float(y),
                "BaseZ": float(base_z),
                "Width": float(width),
                "Depth": float(depth) if depth is not None else None,
                "Height": float(height) if height is not None else None,
                "Thickness": float(thickness),
                "Orientation": orientation,
                "RotationDegrees": float(rotation_deg),
                "StructuralKind": "panel",
                "MaterialRef": material_ref,
                "SectionRef": f"panel_{float(thickness):.4f}",
            },
            semantic_metadata,
        )
        self._write_metadata(panel, element_metadata)
        return self._result(
            "create_panel",
            panel,
            name,
            f"Created panel {width:.2f}m x {(depth if orientation == 'horizontal' else height):.2f}m",
            metadata=self._merged_metadata(
                {
                "storey_name": storey_name,
                "width": float(width),
                "height": float(height) if height is not None else None,
                "depth": float(depth) if depth is not None else None,
                "thickness": float(thickness),
                "orientation": orientation,
                "rotation_deg": float(rotation_deg),
                "material_ref": material_ref,
                "section_ref": f"panel_{float(thickness):.4f}",
                },
                semantic_metadata,
            ),
        )

    def _wall_frame(self, wall_name: str) -> Dict[str, float]:
        wall = self._find_by_name("IfcWall", wall_name)
        if wall is None:
            raise AuthoringError(f"Wall not found: {wall_name}")
        meta = self._metadata(wall)
        if not meta:
            raise AuthoringError(f"Wall {wall_name} is missing Bonsai AI metadata")
        return {
            "start_x": float(meta["StartX"]),
            "start_y": float(meta["StartY"]),
            "end_x": float(meta["EndX"]),
            "end_y": float(meta["EndY"]),
            "base_z": float(meta["BaseZ"]),
            "height": float(meta["Height"]),
            "thickness": float(meta["Thickness"]),
            "wall": wall,
        }

    def _opening_transform(self, wall_name: str, offset_along_wall: float, y_shift: float, z_shift: float) -> np.ndarray:
        frame = self._wall_frame(wall_name)
        dx = frame["end_x"] - frame["start_x"]
        dy = frame["end_y"] - frame["start_y"]
        angle = math.atan2(dy, dx)
        matrix = np.eye(4)
        matrix[0, 0] = math.cos(angle)
        matrix[0, 1] = -math.sin(angle)
        matrix[1, 0] = math.sin(angle)
        matrix[1, 1] = math.cos(angle)
        world_x = frame["start_x"] + math.cos(angle) * float(offset_along_wall) - math.sin(angle) * float(y_shift)
        world_y = frame["start_y"] + math.sin(angle) * float(offset_along_wall) + math.cos(angle) * float(y_shift)
        matrix[:, 3][0:3] = (world_x, world_y, frame["base_z"] + float(z_shift))
        return matrix

    def create_door(
        self,
        name: str,
        storey_name: str,
        wall_name: str,
        offset_along_wall: float,
        width: float,
        height: float,
        thickness: float,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        frame = self._wall_frame(wall_name)
        opening = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcOpeningElement", name=f"{name} Opening")
        opening_rep = ifcopenshell.api.geometry.add_wall_representation(
            self.model,
            context=body,
            length=float(width),
            height=float(height),
            thickness=float(frame["thickness"]) + 0.2,
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=opening, representation=opening_rep)
        opening_matrix = self._opening_transform(wall_name, float(offset_along_wall), -0.1, 0.0)
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=opening, matrix=opening_matrix, is_si=True)
        ifcopenshell.api.feature.add_feature(self.model, feature=opening, element=frame["wall"])

        door = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcDoor", name=name)
        door_rep = ifcopenshell.api.geometry.add_door_representation(
            self.model,
            context=body,
            overall_height=float(height),
            overall_width=float(width),
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=door, representation=door_rep)
        door_matrix = self._opening_transform(wall_name, float(offset_along_wall), 0.05, 0.0)
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=door, matrix=door_matrix, is_si=True)
        ifcopenshell.api.feature.add_filling(self.model, opening=opening, element=door)
        ifcopenshell.api.spatial.assign_container(self.model, products=[door], relating_structure=storey)
        element_metadata = self._merged_metadata(
            {
                "HostWall": wall_name,
                "OffsetAlongWall": float(offset_along_wall),
                "Width": float(width),
                "Height": float(height),
                "Thickness": float(thickness),
            },
            semantic_metadata,
        )
        self._write_metadata(door, element_metadata)
        return self._result(
            "create_door",
            door,
            name,
            f"Created door in {wall_name}",
            metadata=self._merged_metadata({"host_wall": wall_name}, semantic_metadata),
        )

    def create_window(
        self,
        name: str,
        storey_name: str,
        wall_name: str,
        offset_along_wall: float,
        sill_height: float,
        width: float,
        height: float,
        thickness: float,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        frame = self._wall_frame(wall_name)
        opening = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcOpeningElement", name=f"{name} Opening")
        opening_rep = ifcopenshell.api.geometry.add_wall_representation(
            self.model,
            context=body,
            length=float(width),
            height=float(height),
            thickness=float(frame["thickness"]) + 0.2,
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=opening, representation=opening_rep)
        opening_matrix = self._opening_transform(wall_name, float(offset_along_wall), -0.1, float(sill_height))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=opening, matrix=opening_matrix, is_si=True)
        ifcopenshell.api.feature.add_feature(self.model, feature=opening, element=frame["wall"])

        window = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcWindow", name=name)
        window_rep = ifcopenshell.api.geometry.add_window_representation(
            self.model,
            context=body,
            overall_height=float(height),
            overall_width=float(width),
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=window, representation=window_rep)
        window_matrix = self._opening_transform(wall_name, float(offset_along_wall), 0.05, float(sill_height))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=window, matrix=window_matrix, is_si=True)
        ifcopenshell.api.feature.add_filling(self.model, opening=opening, element=window)
        ifcopenshell.api.spatial.assign_container(self.model, products=[window], relating_structure=storey)
        element_metadata = self._merged_metadata(
            {
                "HostWall": wall_name,
                "OffsetAlongWall": float(offset_along_wall),
                "SillHeight": float(sill_height),
                "Width": float(width),
                "Height": float(height),
                "Thickness": float(thickness),
            },
            semantic_metadata,
        )
        self._write_metadata(window, element_metadata)
        return self._result(
            "create_window",
            window,
            name,
            f"Created window in {wall_name}",
            metadata=self._merged_metadata({"host_wall": wall_name}, semantic_metadata),
        )

    def create_curtain_wall(
        self,
        name: str,
        storey_name: str,
        x: float,
        y: float,
        base_z: float,
        width: float,
        height: float,
        rotation_degrees: float,
        panel_width: float,
        panel_height: float,
        panel_thickness: float,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        curtain_wall = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcCurtainWall", name=name)
        ifcopenshell.api.spatial.assign_container(self.model, products=[curtain_wall], relating_structure=storey)
        angle = math.radians(float(rotation_degrees))
        base_matrix = np.eye(4)
        base_matrix[0, 0] = math.cos(angle)
        base_matrix[0, 1] = -math.sin(angle)
        base_matrix[1, 0] = math.sin(angle)
        base_matrix[1, 1] = math.cos(angle)
        base_matrix[:, 3][0:3] = (float(x), float(y), float(base_z))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=curtain_wall, matrix=base_matrix, is_si=True)
        element_metadata = self._merged_metadata(
            {
                "OriginX": float(x),
                "OriginY": float(y),
                "BaseZ": float(base_z),
                "Width": float(width),
                "Height": float(height),
                "RotationDegrees": float(rotation_degrees),
                "PanelWidth": float(panel_width),
                "PanelHeight": float(panel_height),
                "PanelThickness": float(panel_thickness),
                "StructuralKind": "curtain_wall",
                "MaterialRef": self._glass_material_ref(semantic_metadata),
                "SectionRef": f"panel_{float(panel_thickness):.4f}",
            },
            semantic_metadata,
        )
        self._write_metadata(curtain_wall, element_metadata)

        columns = max(1, math.ceil(float(width) / float(panel_width)))
        rows = max(1, math.ceil(float(height) / float(panel_height)))
        panels = []
        for row in range(rows):
            for column in range(columns):
                current_width = min(float(panel_width), float(width) - (column * float(panel_width)))
                current_height = min(float(panel_height), float(height) - (row * float(panel_height)))
                if current_width <= 0 or current_height <= 0:
                    continue
                panel = ifcopenshell.api.root.create_entity(
                    self.model,
                    ifc_class="IfcPlate",
                    name=f"{name} Panel {row + 1}-{column + 1}",
                )
                panel_rep = ifcopenshell.api.geometry.add_wall_representation(
                    self.model,
                    context=body,
                    length=current_width,
                    height=current_height,
                    thickness=float(panel_thickness),
                )
                ifcopenshell.api.geometry.assign_representation(self.model, product=panel, representation=panel_rep)
                local_matrix = np.array(base_matrix, copy=True)
                tx = math.cos(angle) * (column * float(panel_width)) - math.sin(angle) * 0.0
                ty = math.sin(angle) * (column * float(panel_width)) + math.cos(angle) * 0.0
                local_matrix[:, 3][0:3] = (float(x) + tx, float(y) + ty, float(base_z) + (row * float(panel_height)))
                ifcopenshell.api.geometry.edit_object_placement(self.model, product=panel, matrix=local_matrix, is_si=True)
                ifcopenshell.api.spatial.assign_container(self.model, products=[panel], relating_structure=storey)
                self._write_metadata(
                    panel,
                    self._merged_metadata(
                        {
                        "StructuralKind": "panel",
                        "MaterialRef": self._glass_material_ref(semantic_metadata),
                        "SectionRef": f"panel_{float(panel_thickness):.4f}",
                        "ParentAssembly": name,
                        "PanelWidth": float(current_width),
                        "PanelHeight": float(current_height),
                        "PanelThickness": float(panel_thickness),
                        },
                        semantic_metadata,
                    ),
                )
                panels.append(panel)
        if panels:
            ifcopenshell.api.aggregate.assign_object(self.model, products=panels, relating_object=curtain_wall)
        return self._result(
            "create_curtain_wall",
            curtain_wall,
            name,
            f"Created curtain wall with {len(panels)} panels",
            metadata=self._merged_metadata(
                {
                "storey_name": storey_name,
                "width": float(width),
                "height": float(height),
                "panel_count": len(panels),
                "panel_width": float(panel_width),
                "panel_height": float(panel_height),
                "panel_thickness": float(panel_thickness),
                "material_ref": self._glass_material_ref(semantic_metadata),
                "section_ref": f"panel_{float(panel_thickness):.4f}",
                },
                semantic_metadata,
            ),
        )

    def create_footing(
        self,
        name: str,
        storey_name: str,
        x: float,
        y: float,
        base_z: float,
        length: float,
        width: float,
        thickness: float,
        rotation_deg: float = 0.0,
        **semantic_metadata: object,
    ) -> ExecutionResult:
        self._ensure_project_hierarchy()
        storey = self._require_storey(storey_name)
        body = self.body_context
        footing = ifcopenshell.api.root.create_entity(self.model, ifc_class="IfcFooting", name=name)
        matrix = np.eye(4)
        angle = math.radians(float(rotation_deg))
        matrix[0, 0] = math.cos(angle)
        matrix[0, 1] = -math.sin(angle)
        matrix[1, 0] = math.sin(angle)
        matrix[1, 1] = math.cos(angle)
        matrix[:, 3][0:3] = (float(x), float(y), float(base_z))
        ifcopenshell.api.geometry.edit_object_placement(self.model, product=footing, matrix=matrix, is_si=True)
        rep = ifcopenshell.api.geometry.add_slab_representation(
            self.model,
            context=body,
            depth=float(thickness),
            polyline=[(0.0, 0.0), (float(length), 0.0), (float(length), float(width)), (0.0, float(width)), (0.0, 0.0)],
        )
        ifcopenshell.api.geometry.assign_representation(self.model, product=footing, representation=rep)
        ifcopenshell.api.spatial.assign_container(self.model, products=[footing], relating_structure=storey)
        legacy_semantics = (
            dict(semantic_metadata.get("semantic_metadata"))
            if isinstance(semantic_metadata.get("semantic_metadata"), dict)
            else {}
        )
        normalized_metadata = dict(semantic_metadata)
        normalized_metadata.update({key: value for key, value in legacy_semantics.items() if value is not None})
        normalized_metadata["foundation"] = self._foundation_metadata(normalized_metadata)
        foundation_payload = self._foundation_metadata(normalized_metadata)
        result_metadata = self._merged_metadata(
            {
            "OriginX": float(x),
            "OriginY": float(y),
            "BaseZ": float(base_z),
            "Length": float(length),
            "Width": float(width),
            "Thickness": float(thickness),
            "RotationDegrees": float(rotation_deg),
            "StructuralKind": "foundation",
            "MaterialRef": self._material_ref(normalized_metadata, "concrete_default"),
            "SectionRef": f"footing_{float(thickness):.4f}",
            "FoundationType": foundation_payload.get("foundation_type") or "spread_footing",
            "BearingElevation": foundation_payload.get("bearing_elevation"),
            "SupportFor": foundation_payload.get("support_for"),
            "SoilAssumption": foundation_payload.get("soil_assumption"),
            "StructuralRole": foundation_payload.get("structural_role"),
            "LoadCombo": foundation_payload.get("load_combo"),
            "ImposedLoadKN": foundation_payload.get("imposed_load_kn"),
            "ServiceReactionKN": foundation_payload.get("service_reaction_kN"),
            "AllowableBearingKPa": foundation_payload.get("allowable_bearing_kpa"),
            "ConcreteStrengthMPa": foundation_payload.get("concrete_strength_mpa"),
            "RebarYieldStrengthMPa": foundation_payload.get("rebar_yield_strength_mpa"),
            "RebarGrade": foundation_payload.get("rebar_grade"),
            "RebarWeightKg": foundation_payload.get("rebar_weight_kg"),
            "TotalRebarWeightKg": foundation_payload.get("rebar_weight_kg"),
            "RebarBarDiameterMM": foundation_payload.get("rebar_bar_diameter_mm"),
            "RebarSpacingMM": foundation_payload.get("rebar_spacing_mm"),
            "RebarLayerCount": foundation_payload.get("rebar_layer_count"),
            "RebarSchedule": foundation_payload.get("rebar_schedule"),
            "BasisNotes": foundation_payload.get("basis_notes"),
            },
            normalized_metadata,
        )
        self._write_metadata(footing, result_metadata)
        return self._result(
            "create_footing",
            footing,
            name,
            f"Created footing {length:.2f}m x {width:.2f}m",
            metadata={key: value for key, value in result_metadata.items() if value is not None},
        )

    def apply_tool_call(self, tool_name: str, arguments: Dict[str, object]) -> ExecutionResult:
        handlers = {
            "ensure_project": self.ensure_project,
            "ensure_storey": self.ensure_storey,
            "create_rectangular_slab": self.create_rectangular_slab,
            "create_wall": self.create_wall,
            "create_column": self.create_column,
            "create_beam": self.create_beam,
            "create_panel": self.create_panel,
            "create_door": self.create_door,
            "create_window": self.create_window,
            "create_curtain_wall": self.create_curtain_wall,
            "create_footing": self.create_footing,
        }
        if tool_name not in handlers:
            raise AuthoringError(f"Unsupported tool: {tool_name}")
        return handlers[tool_name](**arguments)

    def apply_plan(self, tool_calls: Iterable) -> List[ExecutionResult]:
        results = []
        for call in tool_calls:
            results.append(self.apply_tool_call(call.name, call.arguments))
        return results

    def save(self) -> None:
        self.model.write(self.path)

    def scene_summary(self) -> str:
        lines = []
        project_names = [p.Name for p in self.model.by_type("IfcProject") if getattr(p, "Name", None)]
        if project_names:
            lines.append(f"Project: {project_names[0]}")
        storeys = [s.Name for s in self.model.by_type("IfcBuildingStorey") if getattr(s, "Name", None)]
        if storeys:
            lines.append(f"Storeys: {', '.join(storeys[:20])}")
        for ifc_class in ["IfcWall", "IfcSlab", "IfcDoor", "IfcWindow", "IfcCurtainWall"]:
            names = [e.Name for e in self.model.by_type(ifc_class) if getattr(e, "Name", None)]
            if names:
                lines.append(f"{ifc_class}: {', '.join(names[:20])}")
        footing_names = [e.Name for e in self.model.by_type("IfcFooting") if getattr(e, "Name", None)]
        if footing_names:
            lines.append(f"IfcFooting: {', '.join(footing_names[:20])}")
        semantic_samples = []
        for ifc_class in ["IfcWall", "IfcColumn", "IfcBeam", "IfcWindow", "IfcFooting"]:
            for element in self.model.by_type(ifc_class):
                name = getattr(element, "Name", None)
                if not name:
                    continue
                metadata = self._metadata(element)
                semantics = metadata.get("semantics") if isinstance(metadata.get("semantics"), dict) else {}
                role = semantics.get("role") or metadata.get("Role")
                group_path = semantics.get("group_path") or metadata.get("GroupPath")
                if role or group_path:
                    semantic_samples.append(f"{name} [{role or 'untyped'}]")
                if len(semantic_samples) >= 12:
                    break
            if len(semantic_samples) >= 12:
                break
        if semantic_samples:
            lines.append(f"Semantic samples: {', '.join(semantic_samples)}")
        bbox = self._compute_bounding_box()
        if bbox:
            xmin, xmax, ymin, ymax, zmin, zmax = bbox
            lines.append(f"Bounding box: X=[{xmin}, {xmax}] Y=[{ymin}, {ymax}] Z=[{zmin}, {zmax}]")
        return "\n".join(lines) if lines else "Empty IFC model"

    def _compute_bounding_box(self):
        """Compute an approximate axis-aligned bounding box from element metadata."""
        xs: List[float] = []
        ys: List[float] = []
        zs: List[float] = []
        spatial_classes = ["IfcSlab", "IfcWall", "IfcColumn", "IfcBeam", "IfcPlate", "IfcFooting", "IfcCurtainWall"]
        for ifc_class in spatial_classes:
            for element in self.model.by_type(ifc_class):
                meta = self._metadata(element)
                kind = meta.get("StructuralKind", "")
                if kind == "slab":
                    ox, oy, oz = float(meta.get("OriginX", 0)), float(meta.get("OriginY", 0)), float(meta.get("OriginZ", 0))
                    length = float(meta.get("Length", 0))
                    width = float(meta.get("Width", 0))
                    thickness = float(meta.get("Thickness", 0))
                    xs.extend([ox, ox + length])
                    ys.extend([oy, oy + width])
                    zs.extend([oz, oz + thickness])
                elif kind == "wall":
                    sx, sy = float(meta.get("StartX", 0)), float(meta.get("StartY", 0))
                    ex, ey = float(meta.get("EndX", 0)), float(meta.get("EndY", 0))
                    bz = float(meta.get("BaseZ", 0))
                    h = float(meta.get("Height", 0))
                    xs.extend([sx, ex])
                    ys.extend([sy, ey])
                    zs.extend([bz, bz + h])
                elif kind == "column":
                    cx, cy = float(meta.get("OriginX", 0)), float(meta.get("OriginY", 0))
                    bz = float(meta.get("BaseZ", 0))
                    h = float(meta.get("Height", 0))
                    w = float(meta.get("Width", 0))
                    d = float(meta.get("Depth", 0))
                    xs.extend([cx - w / 2, cx + w / 2])
                    ys.extend([cy - d / 2, cy + d / 2])
                    zs.extend([bz, bz + h])
                elif kind == "beam":
                    sx, sy = float(meta.get("StartX", 0)), float(meta.get("StartY", 0))
                    ex, ey = float(meta.get("EndX", 0)), float(meta.get("EndY", 0))
                    bz = float(meta.get("BaseZ", 0))
                    xs.extend([sx, ex])
                    ys.extend([sy, ey])
                    zs.append(bz)
                elif kind == "footing":
                    ox, oy = float(meta.get("OriginX", 0)), float(meta.get("OriginY", 0))
                    bz = float(meta.get("BaseZ", 0))
                    length = float(meta.get("Length", 0))
                    width = float(meta.get("Width", 0))
                    thickness = float(meta.get("Thickness", 0))
                    xs.extend([ox, ox + length])
                    ys.extend([oy, oy + width])
                    zs.extend([bz, bz + thickness])
                else:
                    # Fallback: use placement origin if available
                    ox = meta.get("OriginX")
                    oy = meta.get("OriginY")
                    oz = meta.get("OriginZ") or meta.get("BaseZ")
                    if ox is not None:
                        xs.append(float(ox))
                    if oy is not None:
                        ys.append(float(oy))
                    if oz is not None:
                        zs.append(float(oz))
        if not xs or not ys or not zs:
            return None
        return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

    def debug_dump(self) -> str:
        return json.dumps(
            {
                "projects": len(self.model.by_type("IfcProject")),
                "storeys": len(self.model.by_type("IfcBuildingStorey")),
                "walls": len(self.model.by_type("IfcWall")),
                "slabs": len(self.model.by_type("IfcSlab")),
                "doors": len(self.model.by_type("IfcDoor")),
                "windows": len(self.model.by_type("IfcWindow")),
                "columns": len(self.model.by_type("IfcColumn")),
                "beams": len(self.model.by_type("IfcBeam")),
                "curtain_walls": len(self.model.by_type("IfcCurtainWall")),
                "plates": len(self.model.by_type("IfcPlate")),
                "footings": len(self.model.by_type("IfcFooting")),
            },
            indent=2,
        )
