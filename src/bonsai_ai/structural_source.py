from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from .contracts import (
    AnalysisDomain,
    AnalysisProfile,
    AnalyticalModel,
    DesignPackage,
    EngineeringModel,
    EngineeringModelScope,
    LoadAction,
    LoadCase,
    LoadCombination,
    MaterialSpec,
    SectionSpec,
    StructuralElement,
    StructuralSourceElement,
    StructuralSourceModel,
    SupportSpec,
)


class StructuralSourceModelBuilder:
    def build(self, package: DesignPackage) -> StructuralSourceModel:
        if not package.physical_model:
            raise ValueError("physical_model must be present before structural source build")

        materials: Dict[str, MaterialSpec] = {}
        sections: Dict[str, SectionSpec] = {}
        elements: List[StructuralSourceElement] = []

        for action in package.physical_model.plan.get("actions", []):
            elements.extend(self._elements_from_action(action, materials, sections))

        supports = self._default_supports(elements)
        family_counts: Dict[str, int] = {}
        parent_counts: Dict[str, int] = {}
        system_counts: Dict[str, int] = {}
        zone_kind_counts: Dict[str, int] = {}
        for element in elements:
            family_counts[element.structural_family] = family_counts.get(element.structural_family, 0) + 1
            if element.parent_id:
                parent_counts[element.parent_id] = parent_counts.get(element.parent_id, 0) + 1
            if element.system_id:
                system_counts[element.system_id] = system_counts.get(element.system_id, 0) + 1
            if element.layout_zone_kind:
                zone_kind_counts[element.layout_zone_kind] = zone_kind_counts.get(element.layout_zone_kind, 0) + 1
        return StructuralSourceModel(
            units=str(package.physical_model.plan.get("units") or "meters"),
            materials=list(materials.values()),
            sections=list(sections.values()),
            elements=elements,
            supports=supports,
            metadata={
                "summary": package.physical_model.summary,
                "assumptions": list(package.physical_model.assumptions),
                "source_plan_version": package.physical_model.plan.get("version"),
                "family_counts": family_counts,
                "parent_counts": parent_counts,
                "system_counts": system_counts,
                "zone_kind_counts": zone_kind_counts,
            },
        )

    def _default_supports(self, elements: List[StructuralSourceElement]) -> List[SupportSpec]:
        primary_columns = [
            e
            for e in elements
            if e.kind == "column" and self._analysis_group(e.role) == "primary_frame"
        ]
        if not primary_columns:
            return []
        min_base_z = min(float(element.geometry["origin"][2]) for element in primary_columns)
        supports: List[SupportSpec] = []
        for element in primary_columns:
            origin_z = float(element.geometry["origin"][2])
            if abs(origin_z - min_base_z) > 1e-6:
                continue
            supports.append(
                SupportSpec(
                    id=f"{element.id}_fixed_base",
                    target_id=element.id,
                    target_kind=element.kind,
                    restraints={"dx": True, "dy": True, "dz": True, "rx": True, "ry": True, "rz": True},
                    metadata={"strategy": "auto_lowest_primary_column_support"},
                )
            )
        return supports

    def _elements_from_action(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> List[StructuralSourceElement]:
        action_type = action["type"]
        if action_type == "create_wall":
            return [self._wall_source(action, materials, sections)]
        if action_type == "create_rect_slab":
            return [self._slab_source(action, materials, sections)]
        if action_type == "create_column":
            return [self._column_source(action, materials, sections)]
        if action_type == "create_beam":
            return [self._beam_source(action, materials, sections)]
        if action_type == "create_panel":
            return [self._panel_source(action, materials, sections)]
        if action_type == "create_footing":
            return [self._footing_source(action, materials, sections)]
        if action_type == "create_curtain_wall":
            return self._curtain_wall_sources(action, materials, sections)
        return []

    @staticmethod
    def _semantic_meta(action: Dict[str, Any]) -> Dict[str, Any]:
        semantics = action.get("semantics")
        if isinstance(semantics, dict):
            return semantics
        return {}

    @classmethod
    def _semantic_id(cls, action: Dict[str, Any]) -> str:
        semantics = cls._semantic_meta(action)
        return str(semantics.get("element_id") or cls._element_id(str(action["name"])))

    @classmethod
    def _semantic_parent_id(cls, action: Dict[str, Any], fallback: str | None) -> str | None:
        semantics = cls._semantic_meta(action)
        return str(semantics.get("parent_id") or fallback) if (semantics.get("parent_id") or fallback) else None

    @classmethod
    def _semantic_assembly_id(cls, action: Dict[str, Any], fallback: str | None) -> str | None:
        semantics = cls._semantic_meta(action)
        return str(semantics.get("assembly_id") or fallback) if (semantics.get("assembly_id") or fallback) else None

    @classmethod
    def _semantic_system_id(cls, action: Dict[str, Any], structural_family: str, fallback: str) -> str:
        semantics = cls._semantic_meta(action)
        system_name = str(semantics.get("system_name") or "").strip()
        if system_name:
            return f"system:{cls._slug(system_name)}"
        return fallback

    @classmethod
    def _semantic_role_or(cls, action: Dict[str, Any], fallback: str) -> str:
        semantics = cls._semantic_meta(action)
        return str(semantics.get("role") or fallback)

    @classmethod
    def _semantic_interface_type(cls, action: Dict[str, Any], role: str, zone_kind: str | None) -> str:
        semantics = cls._semantic_meta(action)
        view_mode = str(semantics.get("view_mode") or "").strip().lower()
        if view_mode == "structure":
            return "structure_review"
        return cls._interface_type_for_role(role, zone_kind)

    def _wall_source(
        self, action: Dict[str, Any], materials: Dict[str, MaterialSpec], sections: Dict[str, SectionSpec]
    ) -> StructuralSourceElement:
        thickness = float(action["thickness"])
        section_id = f"wall_{thickness:.4f}"
        self._ensure_material(
            materials,
            MaterialSpec(
                id="concrete_default",
                family="concrete",
                model="elastic_isotropic",
                properties={"density_kg_m3": 2400, "elastic_modulus_pa": 27_000_000_000, "poisson_ratio": 0.2},
            ),
        )
        self._ensure_section(
            sections,
            SectionSpec(id=section_id, kind="shell", material_id="concrete_default", dimensions={"thickness": thickness}),
        )
        dx = float(action["x2"]) - float(action["x1"])
        dy = float(action["y2"]) - float(action["y1"])
        source_name = str(action["name"])
        default_role = "retaining" if source_name.startswith("Basement Retaining") else "envelope"
        role = self._semantic_role_or(action, default_role)
        structural_family = "substructure" if role == "retaining" else "panel_system"
        parent_id = self._semantic_parent_id(action, self._parent_for_wall(source_name, role))
        identity = self._identity_for_zone(role, structural_family, parent_id)
        return StructuralSourceElement(
            id=self._semantic_id(action),
            kind="wall",
            role=role,
            structural_family=structural_family,
            parent_id=parent_id,
            system_id=self._semantic_system_id(action, structural_family, str(identity["system_id"])),
            assembly_id=self._semantic_assembly_id(action, identity["assembly_id"]),
            layout_zone_id=identity["layout_zone_id"],
            layout_zone_kind=identity["layout_zone_kind"],
            interface_type=self._semantic_interface_type(action, role, identity["layout_zone_kind"]),
            section_id=section_id,
            storey=action.get("storey"),
            geometry={
                "start": [float(action["x1"]), float(action["y1"]), float(action["base_z"])],
                "end": [float(action["x2"]), float(action["y2"]), float(action["base_z"])],
                "height": float(action["height"]),
                "thickness": thickness,
            },
            orientation={"rotation_deg": math.degrees(math.atan2(dy, dx))},
            metadata={"source_action": "create_wall", "source_name": source_name},
        )

    def _slab_source(
        self, action: Dict[str, Any], materials: Dict[str, MaterialSpec], sections: Dict[str, SectionSpec]
    ) -> StructuralSourceElement:
        thickness = float(action["thickness"])
        section_id = f"slab_{thickness:.4f}"
        self._ensure_material(
            materials,
            MaterialSpec(
                id="concrete_default",
                family="concrete",
                model="elastic_isotropic",
                properties={"density_kg_m3": 2400, "elastic_modulus_pa": 27_000_000_000, "poisson_ratio": 0.2},
            ),
        )
        self._ensure_section(
            sections,
            SectionSpec(id=section_id, kind="plate", material_id="concrete_default", dimensions={"thickness": thickness}),
        )
        source_name = str(action["name"]).lower()
        if "basement slab" in source_name or "footing" in source_name or "foundation" in source_name:
            default_role = "foundation"
        else:
            default_role = "diaphragm"
        role = self._semantic_role_or(action, default_role)
        structural_family = "substructure" if role == "foundation" else "diaphragm"
        fallback_parent_id = "foundation:basement" if role == "foundation" else self._diaphragm_parent_id(str(action.get("storey") or action["name"]))
        parent_id = self._semantic_parent_id(action, fallback_parent_id)
        identity = self._identity_for_zone(role, structural_family, parent_id)
        return StructuralSourceElement(
            id=self._semantic_id(action),
            kind="panel",
            role=role,
            structural_family=structural_family,
            parent_id=parent_id,
            system_id=self._semantic_system_id(action, structural_family, str(identity["system_id"])),
            assembly_id=self._semantic_assembly_id(action, identity["assembly_id"]),
            layout_zone_id=identity["layout_zone_id"],
            layout_zone_kind=identity["layout_zone_kind"],
            interface_type=self._semantic_interface_type(action, role, identity["layout_zone_kind"]),
            section_id=section_id,
            storey=action.get("storey"),
            geometry={
                "origin": [float(action["x"]), float(action["y"]), float(action["z"])],
                "length": float(action["width"]),
                "width": float(action["depth"]),
                "thickness": thickness,
            },
            metadata={"source_action": "create_rect_slab", "source_name": action["name"], "subkind": "slab"},
        )

    def _column_source(
        self, action: Dict[str, Any], materials: Dict[str, MaterialSpec], sections: Dict[str, SectionSpec]
    ) -> StructuralSourceElement:
        width = float(action["width"])
        depth = float(action["depth"])
        section_id = f"column_{width:.4f}x{depth:.4f}"
        self._ensure_material(
            materials,
            MaterialSpec(
                id="steel_default",
                family="steel",
                model="elastic_isotropic",
                properties={"density_kg_m3": 7850, "elastic_modulus_pa": 200_000_000_000, "poisson_ratio": 0.3},
            ),
        )
        self._ensure_section(
            sections,
            SectionSpec(id=section_id, kind="rect_profile", material_id="steel_default", dimensions={"width": width, "depth": depth}),
        )
        default_role = self._classify_column_role(str(action["name"]))
        role = self._semantic_role_or(action, default_role)
        structural_family = self._family_for_column_role(role)
        parent_id = self._semantic_parent_id(action, self._parent_for_column(str(action["name"]), role, float(action["x"]), float(action["y"])))
        identity = self._identity_for_zone(role, structural_family, parent_id)
        return StructuralSourceElement(
            id=self._semantic_id(action),
            kind="column",
            role=role,
            structural_family=structural_family,
            parent_id=parent_id,
            system_id=self._semantic_system_id(action, structural_family, str(identity["system_id"])),
            assembly_id=self._semantic_assembly_id(action, identity["assembly_id"]),
            layout_zone_id=identity["layout_zone_id"],
            layout_zone_kind=identity["layout_zone_kind"],
            interface_type=self._semantic_interface_type(action, role, identity["layout_zone_kind"]),
            section_id=section_id,
            storey=action.get("storey"),
            geometry={
                "origin": [float(action["x"]), float(action["y"]), float(action["base_z"])],
                "height": float(action["height"]),
                "width": width,
                "depth": depth,
            },
            orientation={"rotation_deg": float(action.get("rotation_deg") or 0.0)},
            metadata={"source_action": "create_column", "source_name": action["name"]},
        )

    def _footing_source(
        self, action: Dict[str, Any], materials: Dict[str, MaterialSpec], sections: Dict[str, SectionSpec]
    ) -> StructuralSourceElement:
        thickness = float(action["thickness"])
        section_id = f"footing_{thickness:.4f}"
        self._ensure_material(
            materials,
            MaterialSpec(
                id="concrete_default",
                family="concrete",
                model="elastic_isotropic",
                properties={"density_kg_m3": 2400, "elastic_modulus_pa": 27_000_000_000, "poisson_ratio": 0.2},
            ),
        )
        self._ensure_section(
            sections,
            SectionSpec(id=section_id, kind="plate", material_id="concrete_default", dimensions={"thickness": thickness}),
        )
        foundation = dict(action.get("foundation") or {})
        storey_name = action.get("storey_name") or action.get("storey")
        source_name = str(action["name"])
        role = self._semantic_role_or(action, "foundation")
        structural_family = "substructure"
        parent_id = self._semantic_parent_id(action, f"foundation:{str(storey_name or 'subgrade').lower().replace(' ', '_')}")
        identity = self._identity_for_zone(role, structural_family, parent_id)
        return StructuralSourceElement(
            id=self._semantic_id(action),
            kind="foundation",
            role=role,
            structural_family=structural_family,
            parent_id=parent_id,
            system_id=self._semantic_system_id(action, structural_family, str(identity["system_id"])),
            assembly_id=self._semantic_assembly_id(action, identity["assembly_id"]),
            layout_zone_id=identity["layout_zone_id"],
            layout_zone_kind=identity["layout_zone_kind"],
            interface_type=self._semantic_interface_type(action, role, identity["layout_zone_kind"]),
            section_id=section_id,
            storey=storey_name,
            geometry={
                "origin": [float(action["x"]), float(action["y"]), float(action["base_z"])],
                "length": float(action["length"]),
                "width": float(action["width"]),
                "thickness": thickness,
            },
            metadata={
                "source_action": "create_footing",
                "source_name": source_name,
                "support_for": foundation.get("support_for"),
                "load_combo": foundation.get("load_combo"),
                "imposed_load_kN": foundation.get("imposed_load_kN") or foundation.get("imposed_load_kn"),
                "service_reaction_kN": foundation.get("service_reaction_kN") or foundation.get("service_reaction_kn"),
                "rebar_weight_kg": foundation.get("rebar_weight_kg"),
                "rebar_schedule": foundation.get("rebar_schedule"),
            },
        )

    def _beam_source(
        self, action: Dict[str, Any], materials: Dict[str, MaterialSpec], sections: Dict[str, SectionSpec]
    ) -> StructuralSourceElement:
        width = float(action["width"])
        depth = float(action["depth"])
        section_id = f"beam_{width:.4f}x{depth:.4f}"
        self._ensure_material(
            materials,
            MaterialSpec(
                id="steel_default",
                family="steel",
                model="elastic_isotropic",
                properties={"density_kg_m3": 7850, "elastic_modulus_pa": 200_000_000_000, "poisson_ratio": 0.3},
            ),
        )
        self._ensure_section(
            sections,
            SectionSpec(id=section_id, kind="rect_profile", material_id="steel_default", dimensions={"width": width, "depth": depth}),
        )
        start_x = float(action["x1"])
        start_y = float(action["y1"])
        end_x = float(action["x2"])
        end_y = float(action["y2"])
        dx = end_x - start_x
        dy = end_y - start_y
        member_role = str(action.get("member_role") or "")
        default_role = self._classify_beam_role(member_role)
        role = self._semantic_role_or(action, default_role)
        structural_family = self._family_for_beam_role(role)
        parent_id = self._semantic_parent_id(action, self._parent_for_beam(str(action["name"]), role, str(action.get("storey") or "")))
        identity = self._identity_for_zone(role, structural_family, parent_id)
        return StructuralSourceElement(
            id=self._semantic_id(action),
            kind="beam",
            role=role,
            structural_family=structural_family,
            parent_id=parent_id,
            system_id=self._semantic_system_id(action, structural_family, str(identity["system_id"])),
            assembly_id=self._semantic_assembly_id(action, identity["assembly_id"]),
            layout_zone_id=identity["layout_zone_id"],
            layout_zone_kind=identity["layout_zone_kind"],
            interface_type=self._semantic_interface_type(action, role, identity["layout_zone_kind"]),
            section_id=section_id,
            storey=action.get("storey"),
            geometry={
                "start": [start_x, start_y, float(action["base_z"])],
                "end": [end_x, end_y, float(action.get("end_z", action.get("z2", action["base_z"])))],
                "width": width,
                "depth": depth,
            },
            orientation={"rotation_deg": math.degrees(math.atan2(dy, dx))},
            metadata={
                "source_action": "create_beam",
                "source_name": action["name"],
                "member_role": member_role,
            },
        )

    def _panel_source(
        self, action: Dict[str, Any], materials: Dict[str, MaterialSpec], sections: Dict[str, SectionSpec]
    ) -> StructuralSourceElement:
        thickness = float(action["thickness"])
        section_id = f"panel_{thickness:.4f}"
        self._ensure_material(
            materials,
            MaterialSpec(
                id="steel_plate_default",
                family="steel",
                model="elastic_isotropic",
                properties={"density_kg_m3": 7850, "elastic_modulus_pa": 200_000_000_000, "poisson_ratio": 0.3},
            ),
        )
        self._ensure_section(
            sections,
            SectionSpec(id=section_id, kind="plate", material_id="steel_plate_default", dimensions={"thickness": thickness}),
        )
        role = self._semantic_role_or(action, "envelope")
        parent_id = self._semantic_parent_id(action, self._facade_parent_id(str(action["name"])))
        structural_family = "panel_system" if role in {"envelope", "cladding"} else "secondary_frame"
        identity = self._identity_for_zone(role, structural_family, parent_id)
        return StructuralSourceElement(
            id=self._semantic_id(action),
            kind="panel",
            role=role,
            structural_family=structural_family,
            parent_id=parent_id,
            system_id=self._semantic_system_id(action, structural_family, str(identity["system_id"])),
            assembly_id=self._semantic_assembly_id(action, identity["assembly_id"]),
            layout_zone_id=identity["layout_zone_id"],
            layout_zone_kind=identity["layout_zone_kind"],
            interface_type=self._semantic_interface_type(action, role, identity["layout_zone_kind"]),
            section_id=section_id,
            storey=action.get("storey"),
            geometry={
                "origin": [float(action["x"]), float(action["y"]), float(action["base_z"])],
                "width": float(action["width"]),
                "height": float(action["height"]),
                "thickness": thickness,
            },
            metadata={"source_action": "create_panel", "source_name": action["name"]},
        )

    def _curtain_wall_sources(
        self, action: Dict[str, Any], materials: Dict[str, MaterialSpec], sections: Dict[str, SectionSpec]
    ) -> List[StructuralSourceElement]:
        thickness = float(action["thickness"])
        section_id = f"panel_{thickness:.4f}"
        self._ensure_material(
            materials,
            MaterialSpec(
                id="steel_plate_default",
                family="steel",
                model="elastic_isotropic",
                properties={"density_kg_m3": 7850, "elastic_modulus_pa": 200_000_000_000, "poisson_ratio": 0.3},
            ),
        )
        self._ensure_section(
            sections,
            SectionSpec(id=section_id, kind="plate", material_id="steel_plate_default", dimensions={"thickness": thickness}),
        )
        rows = int(action["rows"])
        columns = int(action["columns"])
        panel_width = float(action["width"]) / columns
        panel_height = float(action["height"]) / rows
        dx = float(action["x2"]) - float(action["x1"])
        dy = float(action["y2"]) - float(action["y1"])
        role = self._semantic_role_or(action, "envelope")
        parent_id = self._semantic_parent_id(action, f"curtain_wall:{self._semantic_id(action)}")
        structural_family = "panel_system"
        identity = self._identity_for_zone(role, structural_family, parent_id)
        elements: List[StructuralSourceElement] = []
        for row in range(rows):
            for column in range(columns):
                child_action = {
                    "name": f"{action['name']} Panel {row + 1:02d}-{column + 1:02d}",
                    "semantics": {
                        **dict(self._semantic_meta(action)),
                        "element_id": f"{self._semantic_id(action)}__panel_{row + 1}_{column + 1}",
                        "parent_id": parent_id,
                        "assembly_id": self._semantic_assembly_id(action, identity["assembly_id"]),
                    },
                }
                elements.append(
                    StructuralSourceElement(
                        id=self._semantic_id(child_action),
                        kind="panel",
                        role=role,
                        structural_family=structural_family,
                        parent_id=parent_id,
                        system_id=self._semantic_system_id(action, structural_family, str(identity["system_id"])),
                        assembly_id=self._semantic_assembly_id(child_action, identity["assembly_id"]),
                        layout_zone_id=identity["layout_zone_id"],
                        layout_zone_kind=identity["layout_zone_kind"],
                        interface_type=self._semantic_interface_type(action, role, identity["layout_zone_kind"]),
                        section_id=section_id,
                        storey=action.get("storey"),
                        geometry={
                            "origin": [
                                float(action["x1"]),
                                float(action["y1"]),
                                float(action["base_z"]) + (row * panel_height),
                            ],
                            "width": panel_width,
                            "height": panel_height,
                            "thickness": thickness,
                        },
                        orientation={"rotation_deg": math.degrees(math.atan2(dy, dx))},
                        metadata={"source_action": "create_curtain_wall", "source_name": action["name"]},
                    )
                )
        return elements

    @staticmethod
    def _ensure_material(materials: Dict[str, MaterialSpec], material: MaterialSpec) -> None:
        materials.setdefault(material.id, material)

    @staticmethod
    def _ensure_section(sections: Dict[str, SectionSpec], section: SectionSpec) -> None:
        sections.setdefault(section.id, section)

    @staticmethod
    def _element_id(name: str) -> str:
        safe = "".join(char.lower() if char.isalnum() else "_" for char in name)
        while "__" in safe:
            safe = safe.replace("__", "_")
        return safe.strip("_") or "element"

    @staticmethod
    def _classify_column_role(name: str) -> str:
        lowered = name.lower()
        if " facade post " in f" {lowered} " or "facade post" in lowered:
            return "facade_post"
        if " jamb" in lowered:
            return "opening_jamb"
        if "corner_frame_column" in lowered or "sidewall_frame_column" in lowered or "endwall_column" in lowered:
            return "primary_column"
        if "interior_gravity_column" in lowered:
            return "gravity_column"
        return "primary_column"

    @staticmethod
    def _classify_beam_role(member_role: str) -> str:
        role_map = {
            "brace": "brace",
            "roof_brace": "brace",
            "drag_collector": "drag_collector",
            "roof_collector": "roof_collector",
            "roof_primary_frame": "roof_primary_frame",
            "floor_beam": "floor_beam",
            "floor_girder": "floor_girder",
            "perimeter_spandrel": "perimeter_spandrel",
            "panel_joint_support": "panel_joint_support",
            "roof_edge_support": "roof_edge_support",
            "window_header": "opening_header",
            "window_sill": "opening_sill",
            "door_header": "opening_header",
        }
        return role_map.get(member_role, "secondary_beam")

    @staticmethod
    def _family_for_column_role(role: str) -> str:
        mapping = {
            "primary_column": "primary_frame",
            "gravity_column": "primary_frame",
            "facade_post": "facade_support",
            "opening_jamb": "opening_support",
        }
        return mapping.get(role, "secondary_frame")

    @staticmethod
    def _family_for_beam_role(role: str) -> str:
        mapping = {
            "brace": "primary_frame",
            "drag_collector": "primary_frame",
            "roof_collector": "primary_frame",
            "roof_primary_frame": "primary_frame",
            "floor_beam": "primary_frame",
            "floor_girder": "primary_frame",
            "perimeter_spandrel": "facade_support",
            "panel_joint_support": "facade_support",
            "roof_edge_support": "facade_support",
            "opening_header": "opening_support",
            "opening_sill": "opening_support",
            "secondary_beam": "secondary_frame",
        }
        return mapping.get(role, "secondary_frame")

    @classmethod
    def _parent_for_wall(cls, source_name: str, role: str) -> str:
        if role == "retaining":
            return "substructure:retaining_loop"
        return cls._facade_parent_id(source_name)

    @classmethod
    def _parent_for_column(cls, source_name: str, role: str, x: float, y: float) -> str:
        grid_key = f"x{int(round(x)):03d}_y{int(round(y)):03d}"
        if role == "opening_jamb":
            return cls._opening_parent_id(source_name)
        if role == "facade_post":
            facade = cls._facade_from_name(source_name) or "perimeter"
            return f"facade_support:{facade}"
        if role == "gravity_column":
            return f"frame_line:gravity:{grid_key}"
        return f"frame_line:primary:{grid_key}"

    @classmethod
    def _parent_for_beam(cls, source_name: str, role: str, storey: str) -> str:
        storey_key = cls._slug(storey or "unassigned")
        lowered = source_name.lower()
        if role in {"opening_header", "opening_sill"}:
            return cls._opening_parent_id(source_name)
        if role == "brace":
            if "brace bay" in lowered:
                return f"brace_bay:{cls._brace_bay_key(source_name)}"
            return f"brace_system:{storey_key}"
        if role in {"drag_collector", "roof_collector"}:
            if "collector bay" in lowered:
                return f"collector_line:{cls._brace_bay_key(source_name)}"
            return f"collector_line:{storey_key}"
        if role == "roof_primary_frame":
            return f"roof_frame:{storey_key}"
        if role in {"floor_beam", "floor_girder"}:
            return f"floor_framing:{storey_key}"
        if role in {"perimeter_spandrel", "panel_joint_support", "roof_edge_support"}:
            facade = cls._facade_from_name(source_name) or "perimeter"
            return f"facade_support:{facade}"
        return f"member_group:{storey_key}"

    @classmethod
    def _facade_parent_id(cls, source_name: str) -> str:
        facade = cls._facade_from_name(source_name) or "unknown"
        tier = "generic"
        lowered = source_name.lower()
        if "main tier" in lowered:
            tier = "main_tier"
        elif "top tier" in lowered:
            tier = "top_tier"
        return f"facade:{facade}:{tier}"

    @staticmethod
    def _facade_from_name(source_name: str) -> str | None:
        lowered = source_name.lower()
        for facade in ("south", "north", "east", "west"):
            if facade in lowered:
                return facade
        return None

    @classmethod
    def _opening_parent_id(cls, source_name: str) -> str:
        lowered = source_name.lower()
        cleaned = re.sub(r"\s+(left|right)\s+jamb$", "", lowered)
        cleaned = re.sub(r"\s+(header|sill)$", "", cleaned)
        return f"opening:{cls._slug(cleaned)}"

    @classmethod
    def _brace_bay_key(cls, source_name: str) -> str:
        lowered = source_name.lower()
        cleaned = re.sub(r"\s+[ab]$", "", lowered)
        return cls._slug(cleaned)

    @classmethod
    def _diaphragm_parent_id(cls, storey_name: str) -> str:
        return f"diaphragm:{cls._slug(storey_name)}"

    @classmethod
    def _identity_for_zone(cls, role: str, structural_family: str, parent_id: str | None) -> Dict[str, str | None]:
        zone_id = parent_id
        zone_kind = cls._zone_kind_for_parent(parent_id)
        return {
            "system_id": cls._system_id_for_family(structural_family),
            "assembly_id": cls._assembly_id_for_role(role, parent_id),
            "layout_zone_id": zone_id,
            "layout_zone_kind": zone_kind,
            "interface_type": cls._interface_type_for_role(role, zone_kind),
        }

    @staticmethod
    def _system_id_for_family(structural_family: str) -> str:
        mapping = {
            "primary_frame": "primary_frame_system",
            "facade_support": "facade_support_system",
            "opening_support": "opening_support_system",
            "panel_system": "panel_system",
            "substructure": "substructure_system",
            "diaphragm": "diaphragm_system",
            "secondary_frame": "secondary_frame_system",
        }
        return mapping.get(structural_family, f"{structural_family}_system")

    @staticmethod
    def _assembly_id_for_role(role: str, parent_id: str | None) -> str | None:
        if not parent_id:
            return None
        if role in {"opening_header", "opening_sill", "opening_jamb"}:
            return parent_id
        if role in {"perimeter_spandrel", "panel_joint_support", "roof_edge_support", "facade_post"}:
            return parent_id
        if role in {"primary_column", "gravity_column", "roof_primary_frame", "floor_beam", "floor_girder"}:
            return parent_id
        if role in {"brace", "drag_collector", "roof_collector"}:
            return parent_id
        if role in {"retaining", "foundation"}:
            return parent_id
        if role in {"envelope", "diaphragm"}:
            return parent_id
        return parent_id

    @staticmethod
    def _zone_kind_for_parent(parent_id: str | None) -> str | None:
        if not parent_id:
            return None
        for prefix, kind in (
            ("frame_line:", "frame_line"),
            ("brace_bay:", "brace_bay"),
            ("brace_system:", "brace_bay"),
            ("collector_line:", "collector_line"),
            ("roof_frame:", "roof_frame"),
            ("floor_framing:", "floor_framing_zone"),
            ("facade:", "facade_zone"),
            ("facade_support:", "facade_support_zone"),
            ("opening:", "opening_zone"),
            ("diaphragm:", "diaphragm_zone"),
            ("substructure:", "substructure_zone"),
            ("foundation:", "foundation_zone"),
            ("curtain_wall:", "curtain_wall_zone"),
            ("member_group:", "member_group"),
        ):
            if parent_id.startswith(prefix):
                return kind
        return "unknown_zone"

    @staticmethod
    def _interface_type_for_role(role: str, zone_kind: str | None) -> str:
        mapping = {
            "primary_column": "primary_support",
            "gravity_column": "gravity_support",
            "facade_post": "panel_support",
            "opening_jamb": "opening_transfer",
            "brace": "lateral_bracing",
            "drag_collector": "collector_transfer",
            "roof_collector": "collector_transfer",
            "roof_primary_frame": "primary_framing",
            "floor_beam": "gravity_framing",
            "floor_girder": "gravity_framing",
            "perimeter_spandrel": "panel_support",
            "panel_joint_support": "panel_support",
            "roof_edge_support": "panel_support",
            "opening_header": "opening_transfer",
            "opening_sill": "opening_transfer",
            "retaining": "soil_retention",
            "foundation": "foundation_bearing",
            "diaphragm": "diaphragm_transfer",
            "envelope": "enclosure_surface",
        }
        if role in mapping:
            return mapping[role]
        if zone_kind in {"facade_zone", "curtain_wall_zone"}:
            return "enclosure_surface"
        return "generic_interface"

    @staticmethod
    def _slug(value: str) -> str:
        safe = "".join(char.lower() if char.isalnum() else "_" for char in value)
        while "__" in safe:
            safe = safe.replace("__", "_")
        return safe.strip("_") or "unclassified"

    @staticmethod
    def _analysis_group(role: str) -> str:
        if role in {"primary_column", "gravity_column", "roof_primary_frame", "floor_beam", "floor_girder"}:
            return "primary_frame"
        if role in {"brace"}:
            return "brace"
        if role in {"drag_collector", "roof_collector"}:
            return "collector"
        if role in {"perimeter_spandrel", "panel_joint_support", "roof_edge_support", "facade_post"}:
            return "facade_support"
        if role in {"opening_header", "opening_sill", "opening_jamb"}:
            return "opening_frame"
        if role in {"retaining"}:
            return "retaining"
        if role in {"foundation"}:
            return "foundation"
        if role in {"diaphragm"}:
            return "diaphragm"
        if role in {"envelope"}:
            return "envelope"
        return "secondary_frame"


class StructuralAnalysisReducer:
    def reduce(
        self,
        source_model: StructuralSourceModel,
        profile: AnalysisProfile,
        request,
        *,
        summary: str = "",
        assumptions: List[str] | None = None,
        analysis_domains: List[AnalysisDomain] | None = None,
        source_plan_version: str | None = None,
        load_path_model: Dict[str, Any] | None = None,
    ) -> AnalyticalModel:
        assumptions = assumptions or []
        analysis_domains = analysis_domains or []
        elements = [self._to_analytical_element(element) for element in source_model.elements if self._include_element(element, profile)]
        supports = [support for support in source_model.supports if support.target_id in {element.id for element in elements}]
        load_cases = [self._normalize_load_case(load_case, elements, profile, load_path_model or {}) for load_case in request.load_cases]
        load_combinations = request.load_combinations or [
            LoadCombination(
                name=f"{load_case.name} 1.0",
                case_factors={load_case.name: 1.0},
                category=load_case.category,
                code_basis=load_case.code_basis,
            )
            for load_case in load_cases
        ]
        return AnalyticalModel(
            units=source_model.units,
            materials=list(source_model.materials),
            sections=list(source_model.sections),
            elements=elements,
            supports=supports,
            load_cases=load_cases,
            load_combinations=load_combinations,
            metadata={
                "summary": summary,
                "assumptions": list(assumptions),
                "analysis_domains": [domain.value for domain in analysis_domains],
                "source_plan_version": source_plan_version,
                "analysis_profile": profile.value,
                "support_strategy": "explicit_fixed_supports_on_lowest_primary_column_supports",
                "load_path_model": dict(load_path_model or {}),
            },
        )

    def _include_element(self, element: StructuralSourceElement, profile: AnalysisProfile) -> bool:
        role = StructuralSourceModelBuilder._analysis_group(element.role)
        if profile == AnalysisProfile.GLOBAL_FAST:
            return role in {"primary_frame", "brace", "collector"}
        if profile == AnalysisProfile.GLOBAL_FULL:
            return True
        if profile == AnalysisProfile.FACADE_SUPPORT:
            return role in {"facade_support", "opening_frame", "collector", "primary_frame", "envelope"}
        if profile == AnalysisProfile.SUBSTRUCTURE:
            return role in {"retaining", "foundation", "primary_frame"}
        return True

    @staticmethod
    def _to_analytical_element(element: StructuralSourceElement) -> StructuralElement:
        kind = element.kind
        analysis_group = StructuralSourceModelBuilder._analysis_group(element.role)
        if analysis_group == "diaphragm":
            kind = "panel"
        if analysis_group == "foundation":
            kind = "foundation"
        return StructuralElement(
            id=element.id,
            kind=kind,
            geometry=dict(element.geometry),
            section_id=element.section_id,
            storey=element.storey,
            orientation=dict(element.orientation),
            metadata=dict(element.metadata)
            | {
                "analysis_role": element.role,
                "analysis_group": analysis_group,
                "structural_family": element.structural_family,
                "parent_id": element.parent_id,
                "system_id": element.system_id,
                "assembly_id": element.assembly_id,
                "layout_zone_id": element.layout_zone_id,
                "layout_zone_kind": element.layout_zone_kind,
                "interface_type": element.interface_type,
            },
        )

    def _normalize_load_case(self, load_case: LoadCase, elements: List[StructuralElement], profile: AnalysisProfile, load_path_model: Dict[str, Any]) -> LoadCase:
        if load_case.actions:
            return load_case
        return LoadCase(
            name=load_case.name,
            domain=load_case.domain,
            code_basis=load_case.code_basis,
            category=load_case.category,
            design_situation=load_case.design_situation,
            parameters=dict(load_case.parameters),
            actions=self._default_actions(load_case, elements, profile, load_path_model),
        )

    def _default_actions(
        self,
        load_case: LoadCase,
        elements: List[StructuralElement],
        profile: AnalysisProfile,
        load_path_model: Dict[str, Any],
    ) -> List[LoadAction]:
        if load_case.domain == AnalysisDomain.GRAVITY:
            actions = [LoadAction(target_id="all", kind="self_weight", magnitude=1.0, metadata={"source": "default_gravity"})]
            superimposed_floor_kpa = float(load_case.parameters.get("superimposed_floor_kpa", 2.5))
            roof_superimposed_kpa = float(load_case.parameters.get("superimposed_roof_kpa", 1.0))
            diaphragm_targets = {element.id: element for element in elements if str(element.metadata.get("analysis_group") or "") == "diaphragm"}
            for zone in load_path_model.get("diaphragm_zones", []):
                zone_storeys = [str(storey or "") for storey in zone.get("storeys", [])]
                is_roof = any("roof" in storey.lower() for storey in zone_storeys)
                pressure = roof_superimposed_kpa if is_roof else superimposed_floor_kpa
                for element_id in zone.get("diaphragm_element_ids", []):
                    if element_id not in diaphragm_targets:
                        continue
                    actions.append(
                        LoadAction(
                            target_id=element_id,
                            kind="pressure",
                            magnitude=pressure,
                            metadata={"source": "load_path_superimposed_gravity", "zone_id": zone.get("zone_id"), "is_roof": is_roof},
                        )
                    )
            return actions
        if load_case.domain == AnalysisDomain.WIND:
            pressure = float(load_case.parameters.get("pressure_kpa", 0.75))
            direction = str(load_case.parameters.get("direction") or "global_x")
            exposed_facades = self._wind_exposed_facades(direction)
            facade_zones = [zone for zone in load_path_model.get("facade_zones", []) if zone.get("facade") in exposed_facades]
            if profile in {AnalysisProfile.GLOBAL_FULL, AnalysisProfile.FACADE_SUPPORT}:
                surface_actions = []
                for zone in facade_zones:
                    for element_id in zone.get("envelope_element_ids", []):
                        if any(element.id == element_id and element.kind in {"wall", "panel"} for element in elements):
                            surface_actions.append(
                                LoadAction(
                                    target_id=element_id,
                                    kind="pressure",
                                    direction=direction,
                                    magnitude=pressure,
                                    metadata={"source": "load_path_wind_surface", "zone_id": zone.get("zone_id"), "facade": zone.get("facade")},
                                )
                            )
                if surface_actions:
                    return surface_actions
                fallback_surface_actions = [
                    LoadAction(
                        target_id=element.id,
                        kind="pressure",
                        direction=direction,
                        magnitude=pressure,
                        metadata={"source": "default_wind_surface"},
                    )
                    for element in elements
                    if element.kind in {"wall", "panel"}
                ]
                if fallback_surface_actions:
                    return fallback_surface_actions
            fast_actions: List[LoadAction] = []
            valid_ids = {element.id for element in elements if element.kind == "beam"}
            fallback_zone_targets = [
                element.id
                for element in elements
                if element.kind == "beam"
                and str(element.metadata.get("analysis_group") or "") in {"collector", "primary_frame", "brace"}
            ]
            for zone in facade_zones:
                target_ids = [element_id for element_id in zone.get("support_element_ids", []) if element_id in valid_ids]
                if not target_ids:
                    target_ids = list(fallback_zone_targets)
                if not target_ids:
                    continue
                zone_force_n = pressure * 1000.0 * max(float(zone.get("area_m2") or 0.0), 0.1)
                point_load_n = zone_force_n / max(len(target_ids), 1) / 2.0
                for target_id in target_ids:
                    fast_actions.append(
                        LoadAction(
                            target_id=target_id,
                            kind="point_load",
                            direction=direction,
                            magnitude=point_load_n,
                            metadata={"source": "load_path_wind_collector", "zone_id": zone.get("zone_id"), "facade": zone.get("facade")},
                        )
                    )
            if fast_actions:
                return fast_actions
            tributary_height_m = float(load_case.parameters.get("tributary_height_m", 3.8))
            fallback_targets = [
                element
                for element in elements
                if str(element.metadata.get("analysis_group") or "") in {"collector", "facade_support"}
                and element.kind == "beam"
            ]
            if not fallback_targets:
                fallback_targets = [
                    element
                    for element in elements
                    if str(element.metadata.get("analysis_group") or "") in {"primary_frame", "secondary_frame", "brace"}
                    and element.kind == "beam"
                ]
            if fallback_targets:
                return [
                    LoadAction(
                        target_id=element.id,
                        kind="point_load",
                        direction=direction,
                        magnitude=self._collector_point_load_magnitude(element, pressure, tributary_height_m),
                        metadata={"source": "default_wind_collector"},
                    )
                    for element in fallback_targets
                ]
        if load_case.domain == AnalysisDomain.FOOTING:
            return [
                LoadAction(
                    target_id=element.id,
                    kind="surface_traction",
                    direction="global_z",
                    magnitude=float(load_case.parameters.get("bearing_pressure_kpa", 150.0)),
                    metadata={"source": "default_footing"},
                )
                for element in elements
                if element.kind == "foundation"
            ]
        return [LoadAction(target_id="all", kind="self_weight", magnitude=1.0, metadata={"source": "default_structural"})]

    @staticmethod
    def _wind_exposed_facades(direction: str) -> set[str]:
        mapping = {
            "global_x": {"east", "west", "unknown"},
            "x": {"east", "west", "unknown"},
            "global_y": {"north", "south", "unknown"},
            "y": {"north", "south", "unknown"},
        }
        return mapping.get(direction, {"north", "south", "east", "west", "unknown"})

    @staticmethod
    def _collector_point_load_magnitude(element: StructuralElement, pressure_kpa: float, tributary_height_m: float) -> float:
        start = [float(value) for value in element.geometry.get("start", [0.0, 0.0, 0.0])]
        end = [float(value) for value in element.geometry.get("end", start)]
        span_m = math.dist(start, end)
        total_force_n = pressure_kpa * 1000.0 * max(span_m, 0.1) * max(tributary_height_m, 0.1)
        return total_force_n / 2.0


class StructuralEngineeringModelEmitter:
    SUPPORT_EXPECTATIONS = {
        EngineeringModelScope.GLOBAL_FRAME: "required",
        EngineeringModelScope.ROOF_LOAD_PATH: "required",
        EngineeringModelScope.FACADE_SUPPORT: "required",
        EngineeringModelScope.SUBSTRUCTURE: "required",
        EngineeringModelScope.OPENING_SUPPORT: "derived_from_parent",
    }

    def emit(
        self,
        source_model: StructuralSourceModel,
        scope: EngineeringModelScope,
        *,
        summary: str = "",
        assumptions: List[str] | None = None,
        source_plan_version: str | None = None,
    ) -> EngineeringModel:
        assumptions = assumptions or []
        elements = [
            StructuralAnalysisReducer._to_analytical_element(element)
            for element in source_model.elements
            if self._include_element(element, scope)
        ]
        element_ids = {element.id for element in elements}
        supports = [support for support in source_model.supports if support.target_id in element_ids]
        role_counts: Dict[str, int] = {}
        group_counts: Dict[str, int] = {}
        family_counts: Dict[str, int] = {}
        parent_counts: Dict[str, int] = {}
        system_counts: Dict[str, int] = {}
        zone_kind_counts: Dict[str, int] = {}
        for element in elements:
            role = str(element.metadata.get("analysis_role") or "unclassified")
            group = str(element.metadata.get("analysis_group") or "unclassified")
            family = str(element.metadata.get("structural_family") or "generic")
            parent_id = str(element.metadata.get("parent_id") or "")
            system_id = str(element.metadata.get("system_id") or "")
            zone_kind = str(element.metadata.get("layout_zone_kind") or "")
            role_counts[role] = role_counts.get(role, 0) + 1
            group_counts[group] = group_counts.get(group, 0) + 1
            family_counts[family] = family_counts.get(family, 0) + 1
            if parent_id:
                parent_counts[parent_id] = parent_counts.get(parent_id, 0) + 1
            if system_id:
                system_counts[system_id] = system_counts.get(system_id, 0) + 1
            if zone_kind:
                zone_kind_counts[zone_kind] = zone_kind_counts.get(zone_kind, 0) + 1
        support_expectation = self.SUPPORT_EXPECTATIONS.get(scope, "optional")
        warnings: List[str] = []
        standalone_ready = True
        if support_expectation == "required" and not supports:
            standalone_ready = False
            warnings.append(f"{scope.value} has no explicit supports; add boundary conditions before standalone analysis.")
        elif support_expectation == "derived_from_parent":
            standalone_ready = False
            warnings.append(f"{scope.value} relies on boundary conditions from a parent engineering model.")
        return EngineeringModel(
            units=source_model.units,
            scope=scope.value,
            materials=list(source_model.materials),
            sections=list(source_model.sections),
            elements=elements,
            supports=supports,
            metadata={
                "summary": summary,
                "assumptions": list(assumptions),
                "source_plan_version": source_plan_version,
                "engineering_scope": scope.value,
                "role_counts": role_counts,
                "group_counts": group_counts,
                "family_counts": family_counts,
                "parent_count": len(parent_counts),
                "parent_counts": parent_counts,
                "system_counts": system_counts,
                "zone_kind_counts": zone_kind_counts,
                "support_strategy": "explicit_fixed_supports_on_lowest_primary_column_supports",
                "support_expectation": support_expectation,
                "support_count": len(supports),
                "standalone_ready": standalone_ready,
                "warnings": warnings,
            },
        )

    def _include_element(self, element: StructuralSourceElement, scope: EngineeringModelScope) -> bool:
        role = element.role
        group = StructuralSourceModelBuilder._analysis_group(role)
        if scope == EngineeringModelScope.GLOBAL_FRAME:
            return group in {"primary_frame", "brace", "collector", "diaphragm"}
        if scope == EngineeringModelScope.ROOF_LOAD_PATH:
            return role in {
                "roof_primary_frame",
                "roof_collector",
                "drag_collector",
                "brace",
                "panel_joint_support",
                "roof_edge_support",
                "primary_column",
                "gravity_column",
                "diaphragm",
            }
        if scope == EngineeringModelScope.FACADE_SUPPORT:
            return role in {
                "facade_post",
                "perimeter_spandrel",
                "panel_joint_support",
                "roof_edge_support",
                "opening_header",
                "opening_sill",
                "opening_jamb",
                "envelope",
                "primary_column",
            }
        if scope == EngineeringModelScope.SUBSTRUCTURE:
            return role in {"retaining", "foundation", "primary_column", "gravity_column"}
        if scope == EngineeringModelScope.OPENING_SUPPORT:
            return role in {"opening_header", "opening_sill", "opening_jamb", "facade_post", "perimeter_spandrel", "envelope"}
        return True
