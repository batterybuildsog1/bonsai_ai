from __future__ import annotations

import importlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .contracts import (
    AnalysisResult,
    AnalyticalModel,
    ArtifactFormat,
    ArtifactKind,
    DesignPackage,
    LoadAction,
    PipelineArtifact,
    SectionSpec,
    StructuralElement,
    SupportSpec,
)
from .pipeline import SolverBackend


def load_pynite_module() -> Any:
    try:
        return importlib.import_module("Pynite")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in tests/runtime
        raise RuntimeError(
            "PyNite is not installed. Install the 'PyNiteFEA' package to use the PyNite solver backend."
        ) from exc


def load_pynite() -> Any:
    return load_pynite_module()


@dataclass
class _BuildContext:
    model: Any
    analytical_model: AnalyticalModel
    materials: Dict[str, Dict[str, float]]
    sections: Dict[str, SectionSpec]
    warnings: List[str] = field(default_factory=list)
    nodes_by_coord: Dict[Tuple[float, float, float], str] = field(default_factory=dict)
    node_names: List[str] = field(default_factory=list)
    element_nodes: Dict[str, List[str]] = field(default_factory=dict)
    member_sections: Dict[str, str] = field(default_factory=dict)
    member_materials: Dict[str, str] = field(default_factory=dict)
    support_nodes: List[str] = field(default_factory=list)
    support_node_targets: Dict[str, str] = field(default_factory=dict)

    def ensure_node(self, preferred_name: str, x: float, y: float, z: float) -> str:
        key = (round(float(x), 6), round(float(y), 6), round(float(z), 6))
        existing = self.nodes_by_coord.get(key)
        if existing:
            return existing
        self.model.add_node(preferred_name, float(x), float(y), float(z))
        self.nodes_by_coord[key] = preferred_name
        self.node_names.append(preferred_name)
        return preferred_name


class PyNiteSolverBackend(SolverBackend):
    def __init__(self, *, pynite_module: Any | None = None) -> None:
        self._pynite_module = pynite_module

    def analyze(self, request, package: DesignPackage, output_dir: Path) -> AnalysisResult:
        if not package.analytical_model:
            raise ValueError("analytical_model must be present before PyNite analysis")

        pynite_module = self._pynite_module or load_pynite_module()
        model = pynite_module.FEModel3D()
        context = _BuildContext(
            model=model,
            analytical_model=package.analytical_model,
            materials=self._material_map(package.analytical_model),
            sections={section.id: section for section in package.analytical_model.sections},
        )

        self._add_materials(context)
        self._build_geometry(context)
        self._apply_supports(context, package.analytical_model.supports)
        self._apply_loads(context)
        self._apply_load_combinations(context)
        self._run_solver(model)

        summary = self._build_summary(context)
        payload = {
            "solver": "pynite",
            "status": "completed",
            "load_combinations": [combo.name for combo in package.analytical_model.load_combinations],
            "summary": summary,
            "warnings": list(context.warnings),
        }
        result_path = output_dir / "solver_result.json"
        result_path.write_text(json.dumps(payload, indent=2))

        return AnalysisResult(
            solver="pynite",
            status="completed",
            governing_cases=[combo.name for combo in package.analytical_model.load_combinations],
            warnings=list(context.warnings),
            artifacts=[
                PipelineArtifact(
                    kind=ArtifactKind.SOLVER_RESULT,
                    format=ArtifactFormat.PYNITE_JSON,
                    path=str(result_path),
                    metadata={"role": "solver_result", "label": "PyNite Results", "engine": "pynite"},
                )
            ],
            summary=summary,
            metadata={"supports_inferred": not bool(package.analytical_model.supports)},
        )

    @staticmethod
    def _material_map(analytical_model: AnalyticalModel) -> Dict[str, Dict[str, float]]:
        result: Dict[str, Dict[str, float]] = {}
        for material in analytical_model.materials:
            elastic_modulus = float(material.properties.get("elastic_modulus_pa", 20_000_000_000.0))
            poisson_ratio = float(material.properties.get("poisson_ratio", 0.3))
            density = float(material.properties.get("density_kg_m3", 0.0))
            result[material.id] = {
                "E": elastic_modulus,
                "G": elastic_modulus / (2.0 * (1.0 + poisson_ratio)),
                "nu": poisson_ratio,
                "rho": density,
            }
        return result

    def _add_materials(self, context: _BuildContext) -> None:
        for material_id, props in context.materials.items():
            context.model.add_material(material_id, props["E"], props["G"], props["nu"], props["rho"])

    def _build_geometry(self, context: _BuildContext) -> None:
        for element in context.analytical_model.elements:
            if element.kind == "column":
                self._add_column(context, element)
            elif element.kind == "beam":
                self._add_beam(context, element)
            elif element.kind in {"wall", "panel", "foundation"}:
                self._add_surface(context, element)
            else:
                context.warnings.append(f"Unsupported PyNite element kind '{element.kind}' for {element.id}.")

    def _add_column(self, context: _BuildContext, element: StructuralElement) -> None:
        geometry = element.geometry
        origin = [float(value) for value in geometry["origin"]]
        top = [origin[0], origin[1], origin[2] + float(geometry["height"])]
        start_node = context.ensure_node(f"{element.id}_i", *origin)
        end_node = context.ensure_node(f"{element.id}_j", *top)

        section = context.sections.get(element.section_id or "")
        if section is None:
            context.warnings.append(f"Missing section for column {element.id}.")
            return

        material_name = section.material_id
        width = float(section.dimensions.get("width", geometry.get("width", 0.3)))
        depth = float(section.dimensions.get("depth", geometry.get("depth", 0.3)))
        properties = self._section_properties(section)
        area = properties["area"]
        iy = properties["iy"]
        iz = properties["iz"]
        torsion = properties["j"]
        section_name = f"{element.id}_section"
        context.model.add_section(section_name, area, iy, iz, torsion)
        context.model.add_member(element.id, start_node, end_node, material_name, section_name)
        context.element_nodes[element.id] = [start_node, end_node]
        context.member_sections[element.id] = section.id
        context.member_materials[element.id] = material_name

    def _add_beam(self, context: _BuildContext, element: StructuralElement) -> None:
        geometry = element.geometry
        start = [float(value) for value in geometry["start"]]
        end = [float(value) for value in geometry["end"]]
        start_node = context.ensure_node(f"{element.id}_i", *start)
        end_node = context.ensure_node(f"{element.id}_j", *end)

        section = context.sections.get(element.section_id or "")
        if section is None:
            context.warnings.append(f"Missing section for beam {element.id}.")
            return

        material_name = section.material_id
        width = float(section.dimensions.get("width", geometry.get("width", 0.3)))
        depth = float(section.dimensions.get("depth", geometry.get("depth", 0.5)))
        properties = self._section_properties(section)
        area = properties["area"]
        iy = properties["iy"]
        iz = properties["iz"]
        torsion = properties["j"]
        section_name = f"{element.id}_section"
        context.model.add_section(section_name, area, iy, iz, torsion)
        context.model.add_member(element.id, start_node, end_node, material_name, section_name)
        context.element_nodes[element.id] = [start_node, end_node]
        context.member_sections[element.id] = section.id
        context.member_materials[element.id] = material_name

    def _add_surface(self, context: _BuildContext, element: StructuralElement) -> None:
        node_names, thickness = self._surface_geometry(context, element)
        if len(node_names) != 4:
            context.warnings.append(f"Unsupported surface geometry for {element.id}.")
            return
        material_name = self._material_for_element(context, element)
        context.model.add_quad(element.id, node_names[0], node_names[1], node_names[2], node_names[3], thickness, material_name)
        context.element_nodes[element.id] = node_names

    def _surface_geometry(self, context: _BuildContext, element: StructuralElement) -> Tuple[List[str], float]:
        geometry = element.geometry
        if element.kind == "wall" and {"start", "end", "height", "thickness"}.issubset(geometry):
            start = [float(value) for value in geometry["start"]]
            end = [float(value) for value in geometry["end"]]
            height = float(geometry["height"])
            return (
                [
                    context.ensure_node(f"{element.id}_i", *start),
                    context.ensure_node(f"{element.id}_j", *end),
                    context.ensure_node(f"{element.id}_m", end[0], end[1], end[2] + height),
                    context.ensure_node(f"{element.id}_n", start[0], start[1], start[2] + height),
                ],
                float(geometry["thickness"]),
            )

        if {"origin", "length", "width", "thickness"}.issubset(geometry):
            origin = [float(value) for value in geometry["origin"]]
            length = float(geometry["length"])
            width = float(geometry["width"])
            z_value = float(origin[2])
            return (
                [
                    context.ensure_node(f"{element.id}_i", origin[0], origin[1], z_value),
                    context.ensure_node(f"{element.id}_j", origin[0] + length, origin[1], z_value),
                    context.ensure_node(f"{element.id}_m", origin[0] + length, origin[1] + width, z_value),
                    context.ensure_node(f"{element.id}_n", origin[0], origin[1] + width, z_value),
                ],
                float(geometry["thickness"]),
            )

        if {"origin", "width", "height", "thickness"}.issubset(geometry):
            origin = [float(value) for value in geometry["origin"]]
            width = float(geometry["width"])
            height = float(geometry["height"])
            return (
                [
                    context.ensure_node(f"{element.id}_i", origin[0], origin[1], origin[2]),
                    context.ensure_node(f"{element.id}_j", origin[0] + width, origin[1], origin[2]),
                    context.ensure_node(f"{element.id}_m", origin[0] + width, origin[1], origin[2] + height),
                    context.ensure_node(f"{element.id}_n", origin[0], origin[1], origin[2] + height),
                ],
                float(geometry["thickness"]),
            )

        return ([], float(geometry.get("thickness", 0.2)))

    def _apply_supports(self, context: _BuildContext, supports: Iterable[SupportSpec]) -> None:
        support_list = list(supports)
        if support_list:
            for support in support_list:
                for node_name in self._support_target_nodes(context, support):
                    self._define_support(context, node_name, support)
            return

        if not context.nodes_by_coord:
            return

        min_z = min(coords[2] for coords in context.nodes_by_coord)
        for coords, node_name in context.nodes_by_coord.items():
            if math.isclose(coords[2], min_z, abs_tol=1e-6):
                context.model.def_support(
                    node_name,
                    support_DX=True,
                    support_DY=True,
                    support_DZ=True,
                    support_RX=True,
                    support_RY=True,
                    support_RZ=True,
                )
                context.support_nodes.append(node_name)
        context.warnings.append("No supports were defined in the analytical model. Fixed supports were inferred at the lowest nodes.")

    def _define_support(self, context: _BuildContext, node_name: str, support: SupportSpec) -> None:
        restraints = {key.lower(): bool(value) for key, value in support.restraints.items()}
        context.model.def_support(
            node_name,
            support_DX=restraints.get("dx", True),
            support_DY=restraints.get("dy", True),
            support_DZ=restraints.get("dz", True),
            support_RX=restraints.get("rx", True),
            support_RY=restraints.get("ry", True),
            support_RZ=restraints.get("rz", True),
        )
        if node_name not in context.support_nodes:
            context.support_nodes.append(node_name)
        context.support_node_targets[node_name] = support.target_id

    def _support_target_nodes(self, context: _BuildContext, support: SupportSpec) -> List[str]:
        node_names = list(context.element_nodes.get(support.target_id, []))
        if len(node_names) <= 1:
            return node_names
        nodes = [(node_name, self._node_lookup(context, node_name)) for node_name in node_names]
        z_values = [float(node.Z) for _, node in nodes if node is not None]
        if not z_values:
            return node_names[:1]
        min_z = min(z_values)
        return [node_name for node_name, node in nodes if node is not None and math.isclose(float(node.Z), min_z, abs_tol=1e-6)]

    def _apply_loads(self, context: _BuildContext) -> None:
        for load_case in context.analytical_model.load_cases:
            for action in load_case.actions:
                if action.kind == "self_weight":
                    self._apply_self_weight(context, action, load_case.name)
                elif action.kind == "pressure":
                    self._apply_pressure(context, action, load_case.name)
                elif action.kind == "point_load":
                    self._apply_point_load(context, action, load_case.name)
                else:
                    context.warnings.append(f"Unsupported PyNite load kind '{action.kind}' in case {load_case.name}.")

    def _apply_self_weight(self, context: _BuildContext, action: LoadAction, case_name: str) -> None:
        element_ids = context.element_nodes.keys() if action.target_id == "all" else [action.target_id]
        for element_id in element_ids:
            node_names = context.element_nodes.get(element_id, [])
            if len(node_names) != 2:
                continue
            section_id = context.member_sections.get(element_id)
            material_name = context.member_materials.get(element_id)
            section = context.sections.get(section_id or "")
            material = context.materials.get(material_name or "")
            if not section or not material:
                context.warnings.append(f"PyNite self-weight could not be applied to member {element_id}.")
                continue
            properties = self._section_properties(section)
            weight_per_length = float(properties.get("weight_n_per_m") or 0.0)
            if weight_per_length <= 0.0:
                width = float(section.dimensions.get("width", 0.0))
                depth = float(section.dimensions.get("depth", 0.0))
                weight_per_length = width * depth * material["rho"] * 9.81
            weight_per_length *= float(action.magnitude or 1.0)
            context.model.add_member_dist_load(element_id, "FZ", -weight_per_length, -weight_per_length, case=case_name)

    def _apply_pressure(self, context: _BuildContext, action: LoadAction, case_name: str) -> None:
        target_ids = context.element_nodes.keys() if action.target_id == "all" else [action.target_id]
        for element_id in target_ids:
            node_names = context.element_nodes.get(element_id, [])
            if len(node_names) != 4:
                continue
            context.model.add_quad_surface_pressure(element_id, float(action.magnitude), case_name)

    def _apply_point_load(self, context: _BuildContext, action: LoadAction, case_name: str) -> None:
        direction = self._node_direction(action.direction)
        target_nodes = context.element_nodes.get(action.target_id, [])
        if not target_nodes and action.target_id in context.node_names:
            target_nodes = [action.target_id]
        for node_name in target_nodes:
            context.model.add_node_load(node_name, direction, float(action.magnitude), case_name)

    def _apply_load_combinations(self, context: _BuildContext) -> None:
        combos = context.analytical_model.load_combinations or [
            type("Combo", (), {"name": load_case.name, "case_factors": {load_case.name: 1.0}})
            for load_case in context.analytical_model.load_cases
        ]
        if not context.analytical_model.load_combinations:
            context.analytical_model.load_combinations = list(combos)
        for combo in combos:
            context.model.add_load_combo(combo.name, combo.case_factors)

    @staticmethod
    def _run_solver(model: Any) -> None:
        try:
            model.analyze_linear(log=False)
        except TypeError:
            model.analyze_linear()

    def _build_summary(self, context: _BuildContext) -> Dict[str, Any]:
        combo_names = [combo.name for combo in context.analytical_model.load_combinations]
        model_counts = {
            "nodes": len(context.node_names),
            "members": len(context.member_sections),
            "quads": sum(1 for nodes in context.element_nodes.values() if len(nodes) == 4),
        }
        support_reactions = {combo_name: self._support_reactions_for_combo(context, combo_name) for combo_name in combo_names}
        support_target_reactions = {combo_name: self._support_target_reactions_for_combo(context, combo_name) for combo_name in combo_names}
        member_demands = self._member_demands(context, combo_names)
        max_displacement = 0.0
        for combo_name in combo_names:
            for node_name in context.node_names:
                node = self._node_lookup(context, node_name)
                if node is None:
                    continue
                max_displacement = max(
                    max_displacement,
                    abs(float(getattr(node, "DX", {}).get(combo_name, 0.0))),
                    abs(float(getattr(node, "DY", {}).get(combo_name, 0.0))),
                    abs(float(getattr(node, "DZ", {}).get(combo_name, 0.0))),
                )
        return {
            "model_counts": model_counts,
            "max_displacement": max_displacement,
            "max_displacement_mm": max_displacement * 1000.0,
            "support_reactions": support_reactions,
            "support_target_reactions": support_target_reactions,
            "member_demands": member_demands,
        }

    def _member_demands(self, context: _BuildContext, combo_names: List[str]) -> Dict[str, Dict[str, Any]]:
        members = getattr(context.model, "members", None)
        if not isinstance(members, dict):
            return {}
        demands: Dict[str, Dict[str, Any]] = {}
        element_by_id = {element.id: element for element in context.analytical_model.elements}
        for member_name, member in members.items():
            element = element_by_id.get(member_name)
            if element is None:
                continue
            section = context.sections.get(context.member_sections.get(member_name, ""))
            geometry = dict(element.geometry)
            start = [float(value) for value in geometry.get("start", geometry.get("origin", [0.0, 0.0, 0.0]))]
            end = geometry.get("end")
            if end is None:
                height = float(geometry.get("height", 0.0))
                end = [start[0], start[1], start[2] + height]
            end = [float(value) for value in end]
            combo_demands: Dict[str, Dict[str, float]] = {}
            max_abs = {"axial_n": 0.0, "moment_y_nm": 0.0, "moment_z_nm": 0.0, "shear_y_n": 0.0, "shear_z_n": 0.0, "deflection_y_m": 0.0, "deflection_z_m": 0.0}
            for combo_name in combo_names:
                demand = self._member_demand_for_combo(member, combo_name)
                combo_demands[combo_name] = demand
                for key, value in demand.items():
                    max_abs[key] = max(max_abs[key], abs(float(value)))
            demands[member_name] = {
                "element_kind": element.kind,
                "section_id": context.member_sections.get(member_name),
                "material_id": context.member_materials.get(member_name),
                "sizing_group_id": str(element.metadata.get("catalog_selection", {}).get("sizing_group_id") or ""),
                "length_m": math.dist(start, end),
                "combo_demands": combo_demands,
                "max_abs": max_abs,
                "section_properties": dict((section.metadata or {}).get("section_properties") or {}) if section else {},
            }
        return demands

    def _support_reactions_for_combo(self, context: _BuildContext, combo_name: str) -> Dict[str, float]:
        totals = {"fx": 0.0, "fy": 0.0, "fz": 0.0, "mx": 0.0, "my": 0.0, "mz": 0.0}
        for node_name in context.support_nodes:
            node = self._node_lookup(context, node_name)
            if node is None:
                continue
            totals["fx"] += float(getattr(node, "RxnFX", {}).get(combo_name, 0.0))
            totals["fy"] += float(getattr(node, "RxnFY", {}).get(combo_name, 0.0))
            totals["fz"] += float(getattr(node, "RxnFZ", {}).get(combo_name, 0.0))
            totals["mx"] += float(getattr(node, "RxnMX", {}).get(combo_name, 0.0))
            totals["my"] += float(getattr(node, "RxnMY", {}).get(combo_name, 0.0))
            totals["mz"] += float(getattr(node, "RxnMZ", {}).get(combo_name, 0.0))
        return totals

    def _support_target_reactions_for_combo(self, context: _BuildContext, combo_name: str) -> Dict[str, Dict[str, float]]:
        totals: Dict[str, Dict[str, float]] = {}
        for node_name in context.support_nodes:
            target_id = context.support_node_targets.get(node_name, node_name)
            node = self._node_lookup(context, node_name)
            if node is None:
                continue
            entry = totals.setdefault(target_id, {"fx": 0.0, "fy": 0.0, "fz": 0.0, "mx": 0.0, "my": 0.0, "mz": 0.0})
            entry["fx"] += float(getattr(node, "RxnFX", {}).get(combo_name, 0.0))
            entry["fy"] += float(getattr(node, "RxnFY", {}).get(combo_name, 0.0))
            entry["fz"] += float(getattr(node, "RxnFZ", {}).get(combo_name, 0.0))
            entry["mx"] += float(getattr(node, "RxnMX", {}).get(combo_name, 0.0))
            entry["my"] += float(getattr(node, "RxnMY", {}).get(combo_name, 0.0))
            entry["mz"] += float(getattr(node, "RxnMZ", {}).get(combo_name, 0.0))
        return totals

    @staticmethod
    def _node_lookup(context: _BuildContext, node_name: str) -> Any | None:
        nodes = getattr(context.model, "nodes", None)
        if isinstance(nodes, dict):
            return nodes.get(node_name)
        return None

    def _material_for_element(self, context: _BuildContext, element: StructuralElement) -> str:
        section = context.sections.get(element.section_id or "")
        if section is None:
            return next(iter(context.materials.keys()), "default_material")
        return section.material_id

    @staticmethod
    def _section_properties(section: SectionSpec) -> Dict[str, float]:
        """Map Bonsai section properties to PyNite axis convention.

        Axis convention mapping:
          Bonsai ix_m4 (strong/major axis) -> PyNite Iz (Z = major/strong axis)
          Bonsai iy_m4 (weak/minor axis)   -> PyNite Iy (Y = minor/weak axis)

        PyNite convention (from Section.py):
          Iy = second moment of area about the Y (minor) axis
          Iz = second moment of area about the Z (major) axis
        """
        explicit = dict((section.metadata or {}).get("section_properties") or {})
        if explicit:
            return {
                "area": float(explicit.get("area_m2", 0.0)),
                # Bonsai iy_m4 (weak/minor) -> PyNite Iy (Y = minor/weak axis)
                "iy": float(explicit.get("iy_m4", explicit.get("iz_m4", 0.0))),
                # Bonsai ix_m4 (strong/major) -> PyNite Iz (Z = major/strong axis)
                "iz": float(explicit.get("ix_m4", explicit.get("iy_m4", 0.0))),
                "j": float(explicit.get("j_m4", 0.0)),
                "weight_n_per_m": float(explicit.get("weight_n_per_m", 0.0)),
            }
        width = float(section.dimensions.get("width", 0.3))
        depth = float(section.dimensions.get("depth", 0.3))
        return {
            "area": width * depth,
            # width * depth^3 / 12 = strong axis (larger for depth > width) -> PyNite Iz (major)
            "iz": width * depth**3 / 12.0,
            # depth * width^3 / 12 = weak axis (smaller for depth > width) -> PyNite Iy (minor)
            "iy": depth * width**3 / 12.0,
            "j": width * depth * (width**2 + depth**2) / 12.0,
            "weight_n_per_m": 0.0,
        }

    @staticmethod
    def _member_demand_for_combo(member: Any, combo_name: str) -> Dict[str, float]:
        defaults = {
            "axial_n": 0.0,
            "moment_y_nm": 0.0,
            "moment_z_nm": 0.0,
            "shear_y_n": 0.0,
            "shear_z_n": 0.0,
            "deflection_y_m": 0.0,
            "deflection_z_m": 0.0,
        }
        if not hasattr(member, "max_axial"):
            return defaults
        return {
            "axial_n": max(abs(float(member.max_axial(combo_name))), abs(float(member.min_axial(combo_name)))),
            "moment_y_nm": max(abs(float(member.max_moment("My", combo_name))), abs(float(member.min_moment("My", combo_name)))),
            "moment_z_nm": max(abs(float(member.max_moment("Mz", combo_name))), abs(float(member.min_moment("Mz", combo_name)))),
            "shear_y_n": max(abs(float(member.max_shear("Fy", combo_name))), abs(float(member.min_shear("Fy", combo_name)))),
            "shear_z_n": max(abs(float(member.max_shear("Fz", combo_name))), abs(float(member.min_shear("Fz", combo_name)))),
            "deflection_y_m": max(abs(float(member.max_deflection("dy", combo_name))), abs(float(member.min_deflection("dy", combo_name)))),
            "deflection_z_m": max(abs(float(member.max_deflection("dz", combo_name))), abs(float(member.min_deflection("dz", combo_name)))),
        }

    @staticmethod
    def _node_direction(direction: str | None) -> str:
        mapping = {
            None: "FZ",
            "global_x": "FX",
            "global_y": "FY",
            "global_z": "FZ",
            "x": "FX",
            "y": "FY",
            "z": "FZ",
        }
        return mapping.get(direction, "FZ")
