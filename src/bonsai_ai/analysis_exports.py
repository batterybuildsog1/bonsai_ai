from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
from typing import Any, Dict, List

from .contracts import (
    AnalysisDomain,
    AnalysisProfile,
    AnalyticalModel,
    EngineeringModelScope,
    ArtifactFormat,
    ArtifactKind,
    ArtifactRole,
    DesignPackage,
    LoadAction,
    LoadCase,
    LoadCombination,
    MaterialSpec,
    PipelineArtifact,
    SectionSpec,
    StructuralElement,
    SupportSpec,
)
from .catalog_selector import apply_catalog_selection
from .catalog_resolver import resolve_catalog_sections
from .freecad_handoff import FreeCADHandoffBuilder
from .load_path import build_load_path_model
from .pipeline import AnalysisExportBackend
from .structural_source import StructuralAnalysisReducer, StructuralEngineeringModelEmitter, StructuralSourceModelBuilder
from .system_catalog import starter_core_shell_catalog
from .system_layout import build_system_layout


class AnalyticalModelBuilder:
    def build(self, package: DesignPackage) -> AnalyticalModel:
        if not package.analysis_request:
            raise ValueError("analysis_request must be present before analytical export")
        if not package.physical_model:
            raise ValueError("physical_model must be present before analytical export")
        package.structural_source_model = StructuralSourceModelBuilder().build(package)
        package.load_path_model = build_load_path_model(package.structural_source_model, package.system_layout)
        reducer = StructuralAnalysisReducer()
        export_options = dict(package.analysis_request.export_options or {})
        profile = self._profile_from_options(export_options)
        return reducer.reduce(
            package.structural_source_model,
            profile,
            package.analysis_request,
            summary=package.physical_model.summary,
            assumptions=list(package.physical_model.assumptions),
            analysis_domains=list(package.brief.analysis_domains),
            source_plan_version=str(package.physical_model.plan.get("version")),
            load_path_model=package.load_path_model,
        )

    @staticmethod
    def _profile_from_options(export_options: Dict[str, Any]) -> AnalysisProfile:
        profile_name = str(export_options.get("analysis_profile") or "").strip()
        if profile_name:
            try:
                return AnalysisProfile(profile_name)
            except ValueError:
                pass
        mode = str(export_options.get("analysis_model_mode") or "full")
        if mode == "frame_only":
            return AnalysisProfile.GLOBAL_FAST
        return AnalysisProfile.GLOBAL_FULL

    def _default_supports(self, elements: List[StructuralElement]) -> List[SupportSpec]:
        column_elements = [element for element in elements if element.kind == "column"]
        if not column_elements:
            return []
        min_base_z = min(float(element.geometry["origin"][2]) for element in column_elements)
        supports: List[SupportSpec] = []
        for element in column_elements:
            origin_z = float(element.geometry["origin"][2])
            if abs(origin_z - min_base_z) > 1e-6:
                continue
            supports.append(
                SupportSpec(
                    id=f"{element.id}_fixed_base",
                    target_id=element.id,
                    target_kind=element.kind,
                    restraints={
                        "dx": True,
                        "dy": True,
                        "dz": True,
                        "rx": True,
                        "ry": True,
                        "rz": True,
                    },
                    metadata={"strategy": "auto_lowest_column_support"},
                )
            )
        return supports

    @staticmethod
    def _keep_frame_only_element(element: StructuralElement) -> bool:
        if element.kind == "beam":
            role = str(element.metadata.get("member_role") or "")
            return role in {
                "brace",
                "drag_collector",
                "roof_primary_frame",
                "roof_collector",
                "perimeter_spandrel",
                "panel_joint_support",
                "roof_edge_support",
                "floor_beam",
                "floor_girder",
            }
        if element.kind == "column":
            source_name = str(element.metadata.get("source_name") or "")
            return "Facade Post" not in source_name and " Jamb" not in source_name
        return False

    def _elements_from_action(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> List[StructuralElement]:
        action_type = action["type"]
        if action_type == "create_wall":
            return [self._wall_element(action, materials, sections)]
        if action_type == "create_rect_slab":
            return [self._slab_element(action, materials, sections)]
        if action_type == "create_column":
            return [self._column_element(action, materials, sections)]
        if action_type == "create_beam":
            return [self._beam_element(action, materials, sections)]
        if action_type == "create_panel":
            return [self._panel_element(action, materials, sections)]
        if action_type == "create_footing":
            return [self._footing_element(action, materials, sections)]
        if action_type == "create_curtain_wall":
            return self._curtain_wall_panels(action, materials, sections)
        return []

    def _wall_element(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> StructuralElement:
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
        return StructuralElement(
            id=self._element_id(action["name"]),
            kind="wall",
            section_id=section_id,
            storey=action.get("storey"),
            geometry={
                "start": [float(action["x1"]), float(action["y1"]), float(action["base_z"])],
                "end": [float(action["x2"]), float(action["y2"]), float(action["base_z"])],
                "height": float(action["height"]),
                "thickness": thickness,
            },
            orientation={"rotation_deg": math.degrees(math.atan2(dy, dx))},
            metadata={"source_action": "create_wall", "source_name": action["name"]},
        )

    def _slab_element(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> StructuralElement:
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
        name_lower = str(action["name"]).lower()
        element_kind = "foundation" if "footing" in name_lower or "foundation" in name_lower else "panel"
        return StructuralElement(
            id=self._element_id(action["name"]),
            kind=element_kind,
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

    def _column_element(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> StructuralElement:
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
        return StructuralElement(
            id=self._element_id(action["name"]),
            kind="column",
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

    def _footing_element(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> StructuralElement:
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
        return StructuralElement(
            id=self._element_id(action["name"]),
            kind="foundation",
            section_id=section_id,
            storey=action.get("storey_name") or action.get("storey"),
            geometry={
                "origin": [float(action["x"]), float(action["y"]), float(action["base_z"])],
                "length": float(action["length"]),
                "width": float(action["width"]),
                "thickness": thickness,
            },
            metadata={
                "source_action": "create_footing",
                "source_name": action["name"],
                "support_for": foundation.get("support_for"),
                "imposed_load_kN": foundation.get("imposed_load_kN") or foundation.get("imposed_load_kn"),
                "service_reaction_kN": foundation.get("service_reaction_kN") or foundation.get("service_reaction_kn"),
                "rebar_weight_kg": foundation.get("rebar_weight_kg"),
            },
        )

    def _beam_element(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> StructuralElement:
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
        return StructuralElement(
            id=self._element_id(action["name"]),
            kind="beam",
            section_id=section_id,
            storey=action.get("storey"),
            geometry={
                "start": [start_x, start_y, float(action["base_z"])],
                "end": [end_x, end_y, float(action.get("end_z", action.get("z2", action["base_z"])) )],
                "width": width,
                "depth": depth,
            },
            orientation={"rotation_deg": math.degrees(math.atan2(dy, dx))},
            metadata={
                "source_action": "create_beam",
                "source_name": action["name"],
                "member_role": action.get("member_role"),
            },
        )

    def _panel_element(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> StructuralElement:
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
        orientation = str(action.get("orientation") or "vertical")
        geometry = {
            "origin": [float(action["x"]), float(action["y"]), float(action["base_z"])],
            "width": float(action["width"]),
            "thickness": thickness,
        }
        kind = "panel"
        if orientation == "horizontal":
            geometry["depth"] = float(action["depth"])
            kind = "plate"
        else:
            geometry["height"] = float(action["height"])
        return StructuralElement(
            id=self._element_id(action["name"]),
            kind=kind,
            section_id=section_id,
            storey=action.get("storey"),
            geometry=geometry,
            orientation={"rotation_deg": float(action.get("rotation_deg") or 0.0)},
            metadata={
                "source_action": "create_panel",
                "source_name": action["name"],
                "orientation": orientation,
            },
        )

    def _curtain_wall_panels(
        self,
        action: Dict[str, Any],
        materials: Dict[str, MaterialSpec],
        sections: Dict[str, SectionSpec],
    ) -> List[StructuralElement]:
        thickness = float(action["thickness"])
        section_id = f"panel_{thickness:.4f}"
        self._ensure_material(
            materials,
            MaterialSpec(
                id="glass_default",
                family="glass",
                model="elastic_isotropic",
                properties={"density_kg_m3": 2500, "elastic_modulus_pa": 70_000_000_000, "poisson_ratio": 0.22},
            ),
        )
        self._ensure_section(
            sections,
            SectionSpec(id=section_id, kind="plate", material_id="glass_default", dimensions={"thickness": thickness}),
        )
        dx = float(action["x2"]) - float(action["x1"])
        dy = float(action["y2"]) - float(action["y1"])
        width = math.hypot(dx, dy)
        height = float(action["top_z"]) - float(action["base_z"])
        panel_width = float(action["panel_width"])
        panel_height = float(action["panel_height"])
        columns = max(1, math.ceil(width / panel_width))
        rows = max(1, math.ceil(height / panel_height))
        elements: List[StructuralElement] = []
        for row in range(rows):
            for column in range(columns):
                current_width = min(panel_width, width - (column * panel_width))
                current_height = min(panel_height, height - (row * panel_height))
                if current_width <= 0 or current_height <= 0:
                    continue
                elements.append(
                    StructuralElement(
                        id=f"{self._element_id(action['name'])}_panel_{row + 1}_{column + 1}",
                        kind="panel",
                        section_id=section_id,
                        storey=action.get("storey"),
                        geometry={
                            "origin": [
                                float(action["x1"]),
                                float(action["y1"]),
                                float(action["base_z"]) + (row * panel_height),
                            ],
                            "width": current_width,
                            "height": current_height,
                            "thickness": thickness,
                        },
                        orientation={"rotation_deg": math.degrees(math.atan2(dy, dx))},
                        metadata={
                            "source_action": "create_curtain_wall",
                            "source_name": action["name"],
                            "panel_row": row + 1,
                            "panel_column": column + 1,
                        },
                    )
                )
        return elements

    def _normalize_load_case(self, load_case: LoadCase, elements: List[StructuralElement]) -> LoadCase:
        if load_case.actions:
            return load_case
        return LoadCase(
            name=load_case.name,
            domain=load_case.domain,
            code_basis=load_case.code_basis,
            category=load_case.category,
            design_situation=load_case.design_situation,
            parameters=dict(load_case.parameters),
            actions=self._default_actions(load_case, elements),
        )

    def _default_actions(self, load_case: LoadCase, elements: List[StructuralElement]) -> List[LoadAction]:
        if load_case.domain == AnalysisDomain.GRAVITY:
            return [LoadAction(target_id="all", kind="self_weight", magnitude=1.0, metadata={"source": "default_gravity"})]
        if load_case.domain == AnalysisDomain.WIND:
            pressure = float(load_case.parameters.get("pressure_kpa", 0.75))
            surface_actions = [
                LoadAction(
                    target_id=element.id,
                    kind="pressure",
                    direction=str(load_case.parameters.get("direction") or "global_x"),
                    magnitude=pressure,
                    metadata={"source": "default_wind"},
                )
                for element in elements
                if element.kind in {"wall", "panel"}
            ]
            if surface_actions:
                return surface_actions
            collector_roles = {"drag_collector", "roof_collector", "perimeter_spandrel", "panel_joint_support", "roof_edge_support"}
            tributary_height_m = float(load_case.parameters.get("tributary_height_m", 3.8))
            return [
                LoadAction(
                    target_id=element.id,
                    kind="point_load",
                    direction=str(load_case.parameters.get("direction") or "global_x"),
                    magnitude=self._collector_point_load_magnitude(element, pressure, tributary_height_m),
                    metadata={"source": "default_wind_frame_only"},
                )
                for element in elements
                if element.kind == "beam" and str(element.metadata.get("member_role") or "") in collector_roles
            ]
        if load_case.domain == AnalysisDomain.SEISMIC:
            return [
                LoadAction(
                    target_id="all",
                    kind="acceleration",
                    direction=str(load_case.parameters.get("direction") or "global_x"),
                    magnitude=float(load_case.parameters.get("acceleration_g", 0.2)),
                    metadata={"source": "default_seismic"},
                )
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
    def _collector_point_load_magnitude(element: StructuralElement, pressure_kpa: float, tributary_height_m: float) -> float:
        start = [float(value) for value in element.geometry.get("start", [0.0, 0.0, 0.0])]
        end = [float(value) for value in element.geometry.get("end", start)]
        span_m = math.dist(start, end)
        total_force_n = pressure_kpa * 1000.0 * max(span_m, 0.1) * max(tributary_height_m, 0.1)
        return total_force_n / 2.0


class JsonAnalysisExportBackend(AnalysisExportBackend):
    """Write a solver-agnostic analytical model plus a small solver request manifest."""

    def __init__(self, *, include_freecad_handoff: bool = True) -> None:
        self.include_freecad_handoff = include_freecad_handoff

    def export(self, package: DesignPackage, output_dir: Path) -> List[PipelineArtifact]:
        if not package.analysis_request:
            raise ValueError("analysis_request must be present before analytical export")
        if package.physical_model and not package.physical_model.semantic_model:
            try:
                from bonsai_ai_core.semantic_model import build_semantic_model

                source_plan = package.physical_model.authored_plan or {
                    "version": str(package.physical_model.plan.get("version") or "1.0"),
                    "units": str(package.physical_model.plan.get("units") or "meters"),
                    "summary": package.physical_model.summary,
                    "assumptions": list(package.physical_model.assumptions),
                    "actions": list(package.physical_model.plan.get("actions") or []),
                }
                if source_plan:
                    package.physical_model.semantic_model = build_semantic_model(source_plan)
            except Exception:
                pass

        builder = AnalyticalModelBuilder()
        package.analytical_model = builder.build(package)
        semantic_model_path = output_dir / "semantic_model.json"
        structural_source_path = output_dir / "structural_source_model.json"
        system_layout_path = output_dir / "system_layout.json"
        load_path_path = output_dir / "load_path_model.json"
        catalog_selection_path = output_dir / "catalog_selection_summary.json"
        analytical_path = output_dir / "analytical_model.json"
        solver_input_path = output_dir / "solver_request.json"
        export_options = dict(package.analysis_request.export_options or {})
        primary_profile = builder._profile_from_options(export_options)
        system_catalog = (
            (package.physical_model.metadata.get("system_catalog_data") if package.physical_model else None)
            or starter_core_shell_catalog()
        )
        if package.structural_source_model:
            package.catalog_selection_summary = apply_catalog_selection(package.structural_source_model, system_catalog)
            package.system_layout = build_system_layout(package.structural_source_model)
            package.load_path_model = build_load_path_model(package.structural_source_model, package.system_layout)
            resolution_summary = resolve_catalog_sections(package.structural_source_model, system_catalog)
            package.catalog_selection_summary["resolution_summary"] = resolution_summary
        artifacts = [
            PipelineArtifact(
                kind=ArtifactKind.SEMANTIC_MODEL,
                format=ArtifactFormat.JSON,
                path=str(semantic_model_path),
                metadata={
                    "role": ArtifactRole.SEMANTIC_MODEL.value,
                    "label": "Semantic Building Model",
                    "is_primary": bool(package.physical_model and package.physical_model.semantic_model),
                },
            ),
            PipelineArtifact(
                kind=ArtifactKind.STRUCTURAL_SOURCE_MODEL,
                format=ArtifactFormat.JSON,
                path=str(structural_source_path),
                metadata={
                    "role": ArtifactRole.STRUCTURAL_SOURCE_MODEL.value,
                    "label": "Structural Source Model",
                    "is_primary": True,
                },
            ),
            PipelineArtifact(
                kind=ArtifactKind.ENGINEERING_REPORT,
                format=ArtifactFormat.JSON,
                path=str(system_layout_path),
                metadata={"role": ArtifactRole.ENGINEERING_REPORT.value, "label": "System Layout", "report_kind": "system_layout", "is_primary": False},
            ),
            PipelineArtifact(
                kind=ArtifactKind.ENGINEERING_REPORT,
                format=ArtifactFormat.JSON,
                path=str(load_path_path),
                metadata={"role": ArtifactRole.ENGINEERING_REPORT.value, "label": "Load Path Model", "report_kind": "load_path_model", "is_primary": False},
            ),
            PipelineArtifact(
                kind=ArtifactKind.ENGINEERING_REPORT,
                format=ArtifactFormat.JSON,
                path=str(catalog_selection_path),
                metadata={"role": ArtifactRole.ENGINEERING_REPORT.value, "label": "Catalog Selection Summary", "report_kind": "catalog_selection_summary", "is_primary": False},
            ),
            PipelineArtifact(
                kind=ArtifactKind.ANALYTICAL_MODEL,
                format=ArtifactFormat.JSON,
                path=str(analytical_path),
                metadata={"role": ArtifactRole.ANALYSIS_MODEL.value, "label": "Analytical Model", "is_primary": True},
            ),
            PipelineArtifact(
                kind=ArtifactKind.SOLVER_INPUT,
                format=ArtifactFormat.JSON,
                path=str(solver_input_path),
                metadata={
                    "role": ArtifactRole.SOLVER_INPUT.value,
                    "solver": package.analysis_request.solver,
                    "label": "Solver Request",
                    "is_primary": True,
                },
            ),
        ]
        solver_request = {
            "solver": package.analysis_request.solver,
            "design_codes": package.analysis_request.design_codes,
            "load_cases": [load_case.name for load_case in package.analytical_model.load_cases],
            "load_combinations": [combo.name for combo in package.analytical_model.load_combinations],
            "export_options": package.analysis_request.export_options,
            "metadata": package.analysis_request.metadata,
            "analysis_profile": primary_profile.value,
            "structural_source_model": structural_source_path.name,
            "analytical_model": analytical_path.name,
        }

        engineering_scope_names = [name for name in export_options.get("engineering_scopes", []) if str(name).strip()]
        valid_engineering_scopes, invalid_engineering_scopes = self._parse_engineering_scopes(engineering_scope_names)
        if invalid_engineering_scopes:
            allowed = ", ".join(scope.value for scope in EngineeringModelScope)
            invalid = ", ".join(invalid_engineering_scopes)
            raise ValueError(f"Unsupported engineering scopes: {invalid}. Allowed values: {allowed}")
        package.engineering_models = {}
        package.engineering_model_summary = {
            "requested_scopes": [str(name) for name in engineering_scope_names],
            "emitted_scopes": [],
            "invalid_scopes": invalid_engineering_scopes,
            "scope_diagnostics": {},
            "warnings": [],
        }
        if package.structural_source_model and valid_engineering_scopes:
            emitter = StructuralEngineeringModelEmitter()
            engineering_models_manifest: Dict[str, str] = {}
            for scope in valid_engineering_scopes:
                model = emitter.emit(
                    package.structural_source_model,
                    scope,
                    summary=package.physical_model.summary if package.physical_model else "",
                    assumptions=list(package.physical_model.assumptions) if package.physical_model else [],
                    source_plan_version=str(package.physical_model.plan.get("version")) if package.physical_model else None,
                )
                package.engineering_models[scope.value] = model
                package.engineering_model_summary["emitted_scopes"].append(scope.value)
                package.engineering_model_summary["scope_diagnostics"][scope.value] = {
                    "element_count": len(model.elements),
                    "support_count": len(model.supports),
                    "support_expectation": model.metadata.get("support_expectation"),
                    "standalone_ready": bool(model.metadata.get("standalone_ready")),
                    "warnings": list(model.metadata.get("warnings") or []),
                    "role_counts": dict(model.metadata.get("role_counts") or {}),
                    "group_counts": dict(model.metadata.get("group_counts") or {}),
                    "family_counts": dict(model.metadata.get("family_counts") or {}),
                    "parent_count": int(model.metadata.get("parent_count") or 0),
                }
                engineering_path = output_dir / f"engineering_model.{scope.value}.json"
                engineering_path.write_text(json.dumps(asdict(model), indent=2))
                engineering_models_manifest[scope.value] = engineering_path.name
                artifacts.append(
                    PipelineArtifact(
                        kind=ArtifactKind.ENGINEERING_MODEL,
                        format=ArtifactFormat.JSON,
                        path=str(engineering_path),
                        metadata={
                            "role": ArtifactRole.ENGINEERING_MODEL.value,
                            "label": f"Engineering Model ({scope.value})",
                            "scope": scope.value,
                            "is_primary": scope == EngineeringModelScope.GLOBAL_FRAME,
                        },
                    )
                )
            if engineering_models_manifest:
                solver_request["engineering_models"] = engineering_models_manifest
        if package.engineering_model_summary["scope_diagnostics"]:
            engineering_summary_path = output_dir / "engineering_model_summary.json"
            engineering_summary_path.write_text(json.dumps(package.engineering_model_summary, indent=2))
            artifacts.append(
                PipelineArtifact(
                    kind=ArtifactKind.ENGINEERING_REPORT,
                    format=ArtifactFormat.JSON,
                    path=str(engineering_summary_path),
                    metadata={
                        "role": ArtifactRole.ENGINEERING_REPORT.value,
                        "label": "Engineering Model Summary",
                        "report_kind": "engineering_model_summary",
                        "is_primary": False,
                    },
                )
            )

        if package.physical_model and package.physical_model.semantic_model:
            semantic_model_path.write_text(json.dumps(package.physical_model.semantic_model, indent=2))
        else:
            semantic_model_path.write_text(json.dumps({}, indent=2))
        if package.structural_source_model:
            structural_source_path.write_text(json.dumps(asdict(package.structural_source_model), indent=2))
        system_layout_path.write_text(json.dumps(package.system_layout or {}, indent=2))
        load_path_path.write_text(json.dumps(package.load_path_model or {}, indent=2))
        catalog_selection_path.write_text(json.dumps(package.catalog_selection_summary or {}, indent=2))
        analytical_path.write_text(json.dumps(asdict(package.analytical_model), indent=2))
        solver_input_path.write_text(json.dumps(solver_request, indent=2))

        profile_names = [name for name in export_options.get("analysis_profiles", []) if str(name).strip()]
        profile_summary = {
            "primary_profile": primary_profile.value,
            "profiles": {
                primary_profile.value: self._profile_summary(package.analytical_model),
            },
        }
        if package.structural_source_model and profile_names:
            reducer = StructuralAnalysisReducer()
            for profile_name in profile_names:
                profile = AnalysisProfile(str(profile_name))
                if profile == primary_profile:
                    continue
                reduced_model = reducer.reduce(
                    package.structural_source_model,
                    profile,
                    package.analysis_request,
                    summary=package.physical_model.summary if package.physical_model else "",
                    assumptions=list(package.physical_model.assumptions) if package.physical_model else [],
                    analysis_domains=list(package.brief.analysis_domains),
                    source_plan_version=str(package.physical_model.plan.get("version")) if package.physical_model else None,
                )
                profile_path = output_dir / f"analytical_model.{profile.value}.json"
                profile_path.write_text(json.dumps(asdict(reduced_model), indent=2))
                profile_summary["profiles"][profile.value] = self._profile_summary(reduced_model)
                artifacts.append(
                    PipelineArtifact(
                        kind=ArtifactKind.ANALYTICAL_MODEL,
                        format=ArtifactFormat.JSON,
                        path=str(profile_path),
                        metadata={
                            "role": ArtifactRole.ANALYSIS_MODEL.value,
                            "label": f"Analytical Model ({profile.value})",
                            "profile": profile.value,
                            "is_primary": False,
                        },
                    )
                )
        profile_summary_path = output_dir / "analysis_profile_summary.json"
        profile_summary_path.write_text(json.dumps(profile_summary, indent=2))
        artifacts.append(
            PipelineArtifact(
                kind=ArtifactKind.ENGINEERING_REPORT,
                format=ArtifactFormat.JSON,
                path=str(profile_summary_path),
                metadata={
                    "role": ArtifactRole.ENGINEERING_REPORT.value,
                    "label": "Analysis Profile Summary",
                    "is_primary": False,
                },
            )
        )
        if not self.include_freecad_handoff:
            return artifacts

        freecad_handoff_path = output_dir / "freecad_handoff.json"
        freecad_macro_path = output_dir / "freecad_handoff.py"
        handoff_builder = FreeCADHandoffBuilder()
        freecad_handoff = handoff_builder.build(package)
        freecad_handoff["source_files"] = {
            "analytical_model": analytical_path.name,
            "solver_request": solver_input_path.name,
        }
        solver_request["handoff_artifacts"] = {
            "freecad_handoff": freecad_handoff_path.name,
            "freecad_macro": freecad_macro_path.name,
        }
        solver_input_path.write_text(json.dumps(solver_request, indent=2))
        handoff_builder.write_json(freecad_handoff_path, freecad_handoff)
        handoff_builder.write_macro(freecad_macro_path, handoff_filename=freecad_handoff_path.name)
        artifacts.extend(
            [
                PipelineArtifact(
                    kind=ArtifactKind.ANALYTICAL_MODEL,
                    format=ArtifactFormat.JSON,
                    path=str(freecad_handoff_path),
                    metadata={
                        "role": ArtifactRole.FREECAD_HANDOFF.value,
                        "label": "FreeCAD Handoff JSON",
                        "handoff_target": "freecad",
                        "is_primary": False,
                    },
                ),
                PipelineArtifact(
                    kind=ArtifactKind.SOLVER_INPUT,
                    format=ArtifactFormat.PY,
                    path=str(freecad_macro_path),
                    metadata={
                        "role": ArtifactRole.SOLVER_INPUT.value,
                        "label": "FreeCAD Handoff Script",
                        "handoff_target": "freecad",
                        "is_primary": False,
                    },
                ),
            ]
        )
        return artifacts

    @staticmethod
    def _profile_summary(model: AnalyticalModel) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        role_counts: Dict[str, int] = {}
        for element in model.elements:
            counts[element.kind] = counts.get(element.kind, 0) + 1
            role = str(element.metadata.get("analysis_role") or "unclassified")
            role_counts[role] = role_counts.get(role, 0) + 1
        return {
            "element_counts": counts,
            "role_counts": role_counts,
            "support_count": len(model.supports),
            "load_case_count": len(model.load_cases),
            "load_combination_count": len(model.load_combinations),
        }

    @staticmethod
    def _parse_engineering_scopes(scope_names: List[str]) -> tuple[List[EngineeringModelScope], List[str]]:
        valid: List[EngineeringModelScope] = []
        invalid: List[str] = []
        seen: set[str] = set()
        for scope_name in scope_names:
            normalized = str(scope_name).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            try:
                valid.append(EngineeringModelScope(normalized))
            except ValueError:
                invalid.append(normalized)
        return valid, invalid
