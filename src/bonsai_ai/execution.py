from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol

from .contracts import ArtifactFormat, ArtifactKind, ArtifactRole, DesignPackage, PipelineArtifact
from .ifc_author import ExecutionResult, IfcAuthor
from .pipeline import PhysicalModelBackend


@dataclass
class ExecutionItem:
    action_type: str
    element_name: str
    ifc_class: str | None
    global_id: str | None
    metadata: Dict[str, Any]


@dataclass
class ExecutionReport:
    output_path: str
    created: List[str]
    messages: List[str]
    debug_dump: str
    items: List[ExecutionItem]


class PlanExecutor(Protocol):
    def execute_plan(self, plan: Dict[str, Any], output_path: str | Path) -> ExecutionReport:
        raise NotImplementedError


class HeadlessIfcExecutor:
    def __init__(self, default_storey_name: str = "Level 0", overwrite_existing: bool = True):
        self.default_storey_name = default_storey_name
        self.overwrite_existing = overwrite_existing

    def execute_plan(self, plan: Dict[str, Any], output_path: str | Path) -> ExecutionReport:
        output_path = Path(output_path)
        if self.overwrite_existing and output_path.exists():
            output_path.unlink()
        author = IfcAuthor(str(output_path))
        results: List[ExecutionResult] = []
        for action in plan.get("actions", []):
            results.append(self._apply_action(author, action))
        author.save()
        items = [
            ExecutionItem(
                action_type=result.tool_name,
                element_name=result.element_name,
                ifc_class=result.ifc_class,
                global_id=result.global_id,
                metadata=dict(result.metadata),
            )
            for result in results
        ]
        return ExecutionReport(
            output_path=str(output_path),
            created=[result.element_name for result in results],
            messages=[result.message for result in results],
            debug_dump=author.debug_dump(),
            items=items,
        )

    def _apply_action(self, author: IfcAuthor, action: Dict[str, Any]) -> ExecutionResult:
        action_type = action["type"]
        name = action["name"]
        if action_type == "ensure_storey":
            return author.ensure_storey(name, float(action["elevation"]))
        if action_type == "create_rect_slab":
            storey_name = self._storey_name(action, self.default_storey_name)
            base_z = float(action.get("z", action.get("base_z", 0.0)))
            self._ensure_storey(author, storey_name, base_z)
            return author.create_rectangular_slab(
                name=name,
                storey_name=storey_name,
                x=float(action["x"]),
                y=float(action["y"]),
                z=base_z,
                length=float(action.get("length", action["width"])),
                width=float(action.get("depth", action["width"])),
                thickness=float(action["thickness"]),
                rotation_deg=float(action.get("rotation_deg") or 0.0),
                **self._metadata_fields(action),
            )
        if action_type == "create_wall":
            storey_name = self._storey_name(action, self.default_storey_name)
            self._ensure_storey(author, storey_name, float(action["base_z"]))
            return author.create_wall(
                name=name,
                storey_name=storey_name,
                start_x=float(action["x1"]),
                start_y=float(action["y1"]),
                end_x=float(action["x2"]),
                end_y=float(action["y2"]),
                base_z=float(action["base_z"]),
                height=float(action["height"]),
                thickness=float(action["thickness"]),
                **self._metadata_fields(action),
            )
        if action_type == "create_column":
            storey_name = self._storey_name(action, self.default_storey_name)
            self._ensure_storey(author, storey_name, float(action["base_z"]))
            return author.create_column(
                name=name,
                storey_name=storey_name,
                x=float(action["x"]),
                y=float(action["y"]),
                base_z=float(action["base_z"]),
                width=float(action["width"]),
                depth=float(action["depth"]),
                height=float(action["height"]),
                rotation_deg=float(action.get("rotation_deg") or 0.0),
                **self._metadata_fields(action),
            )
        if action_type == "create_beam":
            storey_name = self._storey_name(action, self.default_storey_name)
            self._ensure_storey(author, storey_name, float(action["base_z"]))
            if all(field in action for field in ("x1", "y1", "x2", "y2")):
                start_x = float(action["x1"])
                start_y = float(action["y1"])
                end_x = float(action["x2"])
                end_y = float(action["y2"])
                end_z = float(action.get("end_z", action.get("z2", action.get("base_z"))))
            else:
                rotation = math.radians(float(action.get("rotation_deg") or 0.0))
                span = float(action["height"])
                start_x = float(action["x"])
                start_y = float(action["y"])
                end_x = start_x + (math.cos(rotation) * span)
                end_y = start_y + (math.sin(rotation) * span)
                end_z = float(action.get("end_z", action.get("z2", action.get("base_z"))))
            return author.create_beam(
                name=name,
                storey_name=storey_name,
                start_x=start_x,
                start_y=start_y,
                end_x=end_x,
                end_y=end_y,
                base_z=float(action["base_z"]),
                width=float(action["width"]),
                depth=float(action["depth"]),
                end_z=end_z,
                **self._metadata_fields(action),
            )
        if action_type == "create_panel":
            storey_name = self._storey_name(action, self.default_storey_name)
            self._ensure_storey(author, storey_name, float(action["base_z"]))
            return author.create_panel(
                name=name,
                storey_name=storey_name,
                x=float(action["x"]),
                y=float(action["y"]),
                base_z=float(action["base_z"]),
                width=float(action["width"]),
                height=float(action["height"]) if "height" in action else None,
                depth=float(action["depth"]) if "depth" in action else None,
                thickness=float(action["thickness"]),
                orientation=str(action.get("orientation") or "vertical"),
                rotation_deg=float(action.get("rotation_deg") or 0.0),
                **self._metadata_fields(action),
            )
        if action_type == "create_window":
            storey_name = self._storey_name(action, self.default_storey_name)
            self._ensure_storey(author, storey_name, float(action.get("base_z") or 0.0))
            return author.create_window(
                name=name,
                storey_name=storey_name,
                wall_name=str(action["wall_name"]),
                offset_along_wall=float(action["offset_along_wall"]),
                sill_height=float(action["sill_height"]),
                width=float(action["width"]),
                height=float(action["height"]),
                thickness=float(action["thickness"]),
                **self._metadata_fields(action),
            )
        if action_type == "create_door":
            storey_name = self._storey_name(action, self.default_storey_name)
            self._ensure_storey(author, storey_name, float(action.get("base_z") or 0.0))
            return author.create_door(
                name=name,
                storey_name=storey_name,
                wall_name=str(action["wall_name"]),
                offset_along_wall=float(action["offset_along_wall"]),
                width=float(action["width"]),
                height=float(action["height"]),
                thickness=float(action["thickness"]),
                **self._metadata_fields(action),
            )
        if action_type == "create_curtain_wall":
            storey_name = self._storey_name(action, self.default_storey_name)
            self._ensure_storey(author, storey_name, float(action["base_z"]))
            if all(field in action for field in ("x1", "y1", "x2", "y2")):
                dx = float(action["x2"]) - float(action["x1"])
                dy = float(action["y2"]) - float(action["y1"])
                width = math.hypot(dx, dy)
                rotation = math.degrees(math.atan2(dy, dx))
                origin_x = float(action["x1"])
                origin_y = float(action["y1"])
                height = float(action["top_z"]) - float(action["base_z"])
            else:
                width = float(action["width"])
                rotation = float(action.get("rotation_degrees", action.get("rotation_deg", 0.0)))
                origin_x = float(action["x"])
                origin_y = float(action["y"])
                height = float(action["height"])
            return author.create_curtain_wall(
                name=name,
                storey_name=storey_name,
                x=origin_x,
                y=origin_y,
                base_z=float(action["base_z"]),
                width=width,
                height=height,
                rotation_degrees=rotation,
                panel_width=float(action["panel_width"]),
                panel_height=float(action["panel_height"]),
                panel_thickness=float(action.get("panel_thickness", action["thickness"])),
                **self._metadata_fields(action),
            )
        if action_type == "create_footing":
            storey_name = self._storey_name(action, self.default_storey_name)
            self._ensure_storey(author, storey_name, float(action["base_z"]))
            foundation = self._foundation_fields(action)
            return author.create_footing(
                name=name,
                storey_name=storey_name,
                x=float(action["x"]),
                y=float(action["y"]),
                base_z=float(action["base_z"]),
                length=float(action.get("length", action["width"])),
                width=float(action.get("width", action.get("depth", action.get("length")))),
                thickness=float(action["thickness"]),
                rotation_deg=float(action.get("rotation_deg") or 0.0),
                **self._metadata_fields(action, foundation=foundation),
            )
        raise ValueError(f"Unsupported action type for headless IFC execution: {action_type}")

    def _ensure_storey(self, author: IfcAuthor, storey_name: str, elevation: float) -> None:
        author.ensure_storey(storey_name, elevation)

    @staticmethod
    def _storey_name(action: Dict[str, Any], fallback: str) -> str:
        return str(action.get("storey_name") or action.get("storey") or fallback)

    @classmethod
    def _metadata_fields(cls, action: Dict[str, Any], *, foundation: Dict[str, Any] | None = None) -> Dict[str, Any]:
        metadata = {
            key: value
            for key, value in action.items()
            if key not in cls._reserved_fields() and value is not None
        }
        semantics = cls._semantic_group(action)
        presentation = cls._presentation_group(action)
        foundation_payload = foundation or cls._foundation_fields(action)
        legacy_semantics = action.get("semantic_metadata")

        if semantics:
            metadata["semantics"] = semantics
            metadata.update({key: value for key, value in semantics.items() if key not in metadata})
        if isinstance(legacy_semantics, dict):
            metadata["semantic_metadata"] = dict(legacy_semantics)
        if presentation:
            metadata["presentation"] = presentation
            metadata.update({key: value for key, value in presentation.items() if key not in metadata})
        if foundation_payload:
            metadata["foundation"] = foundation_payload
            metadata.update({key: value for key, value in foundation_payload.items() if key not in metadata})
        return metadata

    @staticmethod
    def _reserved_fields() -> set[str]:
        return {
            "type",
            "name",
            "storey",
            "storey_name",
            "notes",
            "x",
            "y",
            "z",
            "x1",
            "y1",
            "x2",
            "y2",
            "width",
            "depth",
            "length",
            "height",
            "thickness",
            "center_x",
            "center_y",
            "tread_depth",
            "riser_height",
            "step_count",
            "direction_deg",
            "elevation",
            "orientation",
            "rotation_deg",
            "rotation_degrees",
            "panel_width",
            "panel_height",
            "panel_gap",
            "panel_thickness",
            "base_z",
            "top_z",
            "end_z",
            "wall_name",
            "offset_along_wall",
            "sill_height",
            "semantics",
            "presentation",
            "foundation",
            "semantic_metadata",
        }

    @staticmethod
    def _semantic_group(action: Dict[str, Any]) -> Dict[str, Any]:
        merged = {}
        legacy = action.get("semantic_metadata")
        if isinstance(legacy, dict):
            merged.update({key: value for key, value in legacy.items() if value is not None})
        current = action.get("semantics")
        if isinstance(current, dict):
            merged.update({key: value for key, value in current.items() if value is not None})
        for field in (
            "element_id",
            "parent_id",
            "assembly_id",
            "role",
            "subrole",
            "system_name",
            "group_name",
            "group_path",
            "parent_name",
            "collection_key",
            "selector_tags",
            "is_exposed",
            "view_mode",
        ):
            value = action.get(field)
            if value is not None:
                merged[field] = value
        return merged

    @staticmethod
    def _presentation_group(action: Dict[str, Any]) -> Dict[str, Any]:
        merged = {}
        current = action.get("presentation")
        if isinstance(current, dict):
            merged.update({key: value for key, value in current.items() if value is not None})
        for field in (
            "presentation_style",
            "style_preset",
            "material_key",
            "material_preset",
            "glass_material_key",
            "frame_material_key",
            "window_type",
            "frame_style",
            "glazing_style",
            "transparency",
            "mullion_pattern",
            "is_storefront",
        ):
            value = action.get(field)
            if value is not None:
                merged[field] = value
        if "material_key" not in merged and merged.get("material_preset") is not None:
            merged["material_key"] = merged["material_preset"]
        if "presentation_style" not in merged and merged.get("style_preset") is not None:
            merged["presentation_style"] = merged["style_preset"]
        return merged

    @staticmethod
    def _foundation_fields(action: Dict[str, Any]) -> Dict[str, Any]:
        merged = {}
        current = action.get("foundation")
        if isinstance(current, dict):
            merged.update({key: value for key, value in current.items() if value is not None})

        aliases = {
            "foundation_type": "foundation_type",
            "bearing_elevation": "bearing_elevation",
            "support_for": "support_for",
            "soil_assumption": "soil_assumption",
            "structural_role": "structural_role",
            "load_combo": "load_combo",
            "imposed_load_kN": "imposed_load_kN",
            "imposed_load_kn": "imposed_load_kN",
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
        }
        for source, target in aliases.items():
            value = action.get(source)
            if value is not None and target not in merged:
                merged[target] = value
        return merged


class IfcPhysicalModelBackend(PhysicalModelBackend):
    def __init__(self, executor: PlanExecutor | None = None, filename: str = "physical_model.ifc"):
        self.executor = executor or HeadlessIfcExecutor()
        self.filename = filename

    def materialize(self, package: DesignPackage, output_dir: Path) -> List[PipelineArtifact]:
        if not package.physical_model:
            raise ValueError("physical_model must be present before materialization")

        output_path = output_dir / self.filename
        plan_path = output_dir / "physical_model_plan.json"
        plan_path.write_text(json.dumps(package.physical_model.plan, indent=2))
        authored_plan_path = output_dir / "physical_model_authored_plan.json"
        semantic_model_path = output_dir / "physical_model_semantic_model.json"
        if package.physical_model.authored_plan:
            authored_plan_path.write_text(json.dumps(package.physical_model.authored_plan, indent=2))
        if package.physical_model.semantic_model:
            semantic_model_path.write_text(json.dumps(package.physical_model.semantic_model, indent=2))
        report = self.executor.execute_plan(package.physical_model.plan, output_path)
        package.physical_model.metadata["execution_report"] = {
            "created": report.created,
            "messages": report.messages,
            "debug_dump": report.debug_dump,
            "items": [asdict(item) for item in report.items],
        }
        if package.physical_model.authored_plan:
            package.physical_model.metadata["authored_plan_path"] = str(authored_plan_path)
        if package.physical_model.semantic_model:
            package.physical_model.metadata["semantic_model_path"] = str(semantic_model_path)
        artifacts = [
            PipelineArtifact(
                kind=ArtifactKind.BIM_PLAN,
                format=ArtifactFormat.JSON,
                path=str(plan_path),
                metadata={"role": ArtifactRole.BIM_PLAN.value, "label": "Compiled Physical Plan", "is_primary": True},
            ),
            PipelineArtifact(
                kind=ArtifactKind.PHYSICAL_IFC,
                format=ArtifactFormat.IFC,
                path=report.output_path,
                metadata={"created": report.created, "role": ArtifactRole.PRIMARY_IFC.value, "label": "Primary IFC", "is_primary": True},
            ),
        ]
        if package.physical_model.authored_plan:
            artifacts.append(
                PipelineArtifact(
                    kind=ArtifactKind.BIM_PLAN,
                    format=ArtifactFormat.JSON,
                    path=str(authored_plan_path),
                    metadata={"role": ArtifactRole.BIM_PLAN.value, "label": "Authored Physical Plan", "is_primary": False},
                )
            )
        if package.physical_model.semantic_model:
            artifacts.append(
                PipelineArtifact(
                    kind=ArtifactKind.SEMANTIC_MODEL,
                    format=ArtifactFormat.JSON,
                    path=str(semantic_model_path),
                    metadata={"role": ArtifactRole.SEMANTIC_MODEL.value, "label": "Semantic Building Model", "is_primary": False},
                )
            )
        return artifacts
