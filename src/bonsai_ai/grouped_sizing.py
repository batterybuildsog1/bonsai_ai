from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Dict, List

from .analysis_exports import AnalyticalModelBuilder
from .catalog_resolver import resolve_catalog_sections
from .contracts import AnalysisResult, ArtifactFormat, ArtifactKind, ArtifactRole, DesignPackage, PipelineArtifact
from .execution import HeadlessIfcExecutor
from .pipeline import SolverBackend
from .plan_roundtrip import apply_sized_sections_to_physical_model
from .pynite_backend import PyNiteSolverBackend
from .structural_source import StructuralAnalysisReducer


class GroupedSectionSizer:
    def __init__(self, *, solver_backend: SolverBackend | None = None, max_iterations: int = 8) -> None:
        self.solver_backend = solver_backend or PyNiteSolverBackend()
        self.max_iterations = max_iterations

    def size(self, package: DesignPackage, output_dir: Path) -> tuple[AnalysisResult, Dict[str, Any], List[PipelineArtifact]]:
        if not package.structural_source_model:
            raise ValueError("structural_source_model must be present before grouped sizing")
        if not package.analysis_request:
            raise ValueError("analysis_request must be present before grouped sizing")
        if not package.physical_model:
            raise ValueError("physical_model must be present before grouped sizing")

        group_state = _initial_group_state(package.structural_source_model)
        iteration_history: List[Dict[str, Any]] = []
        last_result: AnalysisResult | None = None
        last_group_summary: Dict[str, Any] = {}
        sizing_catalog = package.physical_model.metadata.get("system_catalog_data") or {}

        for iteration_index in range(self.max_iterations):
            trial_source = deepcopy(package.structural_source_model)
            current_overrides = {group_id: state["candidates"][state["index"]] for group_id, state in group_state.items()}
            resolution_summary = resolve_catalog_sections(
                trial_source,
                sizing_catalog,
                group_overrides=current_overrides,
            )
            analytical_model = self._build_analytical_model(package, trial_source)
            trial_package = deepcopy(package)
            trial_package.structural_source_model = trial_source
            trial_package.analytical_model = analytical_model
            iteration_dir = output_dir / ".sizing_iterations" / f"iter_{iteration_index + 1:02d}"
            iteration_dir.mkdir(parents=True, exist_ok=True)
            result = self.solver_backend.analyze(package.analysis_request, trial_package, iteration_dir)
            group_summary = self._group_demand_summary(analytical_model, result.summary.get("member_demands", {}))
            evaluation = self._evaluate_groups(trial_source, analytical_model, group_summary)
            iteration_history.append(
                {
                    "iteration": iteration_index + 1,
                    "group_sections": current_overrides,
                    "resolution_summary": resolution_summary,
                    "evaluations": evaluation,
                }
            )
            last_result = result
            last_group_summary = group_summary
            package.structural_source_model = trial_source
            package.analytical_model = analytical_model
            if not self._advance_failing_groups(group_state, evaluation):
                break

        if last_result is None:
            raise RuntimeError("Grouped sizing did not produce a solver result")

        final_result = self.solver_backend.analyze(package.analysis_request, package, output_dir)
        final_group_summary = self._group_demand_summary(package.analytical_model, final_result.summary.get("member_demands", {}))
        final_evaluation = self._evaluate_groups(package.structural_source_model, package.analytical_model, final_group_summary)
        unity_checks = {
            group_id: float(data["unity"])
            for group_id, data in final_evaluation.items()
            if data.get("status") == "evaluated"
        }
        final_result.unity_checks = unity_checks
        final_result.summary["group_demands"] = final_group_summary
        final_result.summary["group_unity_checks"] = final_evaluation
        (output_dir / "analytical_model.json").write_text(json.dumps(asdict(package.analytical_model), indent=2))
        solver_result_path = next((Path(artifact.path) for artifact in final_result.artifacts if str(artifact.path).endswith("solver_result.json")), None)
        if solver_result_path is not None:
            solver_result_path.write_text(
                json.dumps(
                    {
                        "solver": final_result.solver,
                        "status": final_result.status,
                        "load_combinations": final_result.governing_cases,
                        "summary": final_result.summary,
                        "warnings": final_result.warnings,
                        "unity_checks": final_result.unity_checks,
                    },
                    indent=2,
                )
            )

        sizing_summary = {
            "iterations": iteration_history,
            "final_sections": {group_id: state["candidates"][state["index"]] for group_id, state in group_state.items()},
            "final_group_demands": final_group_summary,
            "final_group_unity_checks": final_evaluation,
            "largest_group_unity": max((value["unity"] for value in final_evaluation.values() if value.get("status") == "evaluated"), default=0.0),
        }
        roundtrip_summary = apply_sized_sections_to_physical_model(package.physical_model, package.structural_source_model)
        sizing_summary["plan_roundtrip"] = roundtrip_summary
        summary_path = output_dir / "sizing_summary.json"
        summary_path.write_text(json.dumps(sizing_summary, indent=2))

        section_costs = _selected_section_costs(package.analytical_model, final_group_summary)
        costs_path = output_dir / "selected_section_costs.json"
        costs_path.write_text(json.dumps(section_costs, indent=2))
        roundtrip_path = output_dir / "plan_roundtrip_summary.json"
        roundtrip_path.write_text(json.dumps(roundtrip_summary, indent=2))
        roundtrip_artifacts = _write_roundtripped_physical_outputs(package, output_dir)
        artifacts = [
            PipelineArtifact(
                kind=ArtifactKind.ENGINEERING_REPORT,
                format=ArtifactFormat.JSON,
                path=str(summary_path),
                metadata={"role": ArtifactRole.ENGINEERING_REPORT.value, "label": "Sizing Summary", "report_kind": "sizing_summary", "is_primary": False},
            ),
            PipelineArtifact(
                kind=ArtifactKind.ENGINEERING_REPORT,
                format=ArtifactFormat.JSON,
                path=str(costs_path),
                metadata={"role": ArtifactRole.ENGINEERING_REPORT.value, "label": "Selected Section Costs", "report_kind": "selected_section_costs", "is_primary": False},
            ),
            PipelineArtifact(
                kind=ArtifactKind.ENGINEERING_REPORT,
                format=ArtifactFormat.JSON,
                path=str(roundtrip_path),
                metadata={"role": ArtifactRole.ENGINEERING_REPORT.value, "label": "Plan Roundtrip Summary", "report_kind": "plan_roundtrip_summary", "is_primary": False},
            ),
        ]
        artifacts.extend(roundtrip_artifacts)
        return final_result, sizing_summary, artifacts

    def _build_analytical_model(self, package: DesignPackage, source_model) -> Any:
        export_options = dict(package.analysis_request.export_options or {})
        profile = AnalyticalModelBuilder()._profile_from_options(export_options)
        return StructuralAnalysisReducer().reduce(
            source_model,
            profile,
            package.analysis_request,
            summary=package.physical_model.summary,
            assumptions=list(package.physical_model.assumptions),
            analysis_domains=list(package.brief.analysis_domains),
            source_plan_version=str(package.physical_model.plan.get("version")),
            load_path_model=dict(package.load_path_model or {}),
        )

    def _group_demand_summary(self, analytical_model, member_demands: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        sections = {section.id: section for section in analytical_model.sections}
        groups: Dict[str, Dict[str, Any]] = {}
        for element in analytical_model.elements:
            if element.kind not in {"beam", "column"}:
                continue
            group_id = str(element.metadata.get("catalog_selection", {}).get("sizing_group_id") or "")
            if not group_id:
                continue
            demand = dict(member_demands.get(element.id) or {})
            if not demand:
                continue
            entry = groups.setdefault(
                group_id,
                {
                    "element_ids": [],
                    "section_id": element.section_id,
                    "length_m_total": 0.0,
                    "max_member_length_m": 0.0,
                    "max_abs": {"axial_n": 0.0, "moment_y_nm": 0.0, "moment_z_nm": 0.0, "shear_y_n": 0.0, "shear_z_n": 0.0, "deflection_y_m": 0.0, "deflection_z_m": 0.0},
                    "section_properties": dict((sections.get(element.section_id or "").metadata or {}).get("section_properties") or {}) if sections.get(element.section_id or "") else {},
                    "material_id": sections.get(element.section_id or "").material_id if sections.get(element.section_id or "") else None,
                    "role": str(element.metadata.get("analysis_role") or ""),
                },
            )
            entry["element_ids"].append(element.id)
            member_length = float(demand.get("length_m") or 0.0)
            entry["length_m_total"] += member_length
            entry["max_member_length_m"] = max(float(entry["max_member_length_m"] or 0.0), member_length)
            for key, value in (demand.get("max_abs") or {}).items():
                entry["max_abs"][key] = max(float(entry["max_abs"].get(key) or 0.0), abs(float(value)))
        return groups

    def _evaluate_groups(self, source_model, analytical_model, group_demands: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        section_lookup = {section.id: section for section in analytical_model.sections}
        material_lookup = {material.id: material for material in analytical_model.materials}
        group_elements: Dict[str, List[Any]] = {}
        for element in source_model.elements:
            group_id = str(element.metadata.get("catalog_selection", {}).get("sizing_group_id") or "")
            if group_id:
                group_elements.setdefault(group_id, []).append(element)

        evaluation: Dict[str, Dict[str, Any]] = {}
        for group_id, elements in group_elements.items():
            demand = group_demands.get(group_id)
            first_element = elements[0]
            selection = dict(first_element.metadata.get("catalog_selection") or {})
            section_name = str(selection.get("resolved_section_name") or selection.get("preferred_section_id") or "")
            section = section_lookup.get(first_element.section_id or "")
            material = material_lookup.get(section.material_id) if section else None
            if not demand or not section or not material:
                evaluation[group_id] = {
                    "status": "insufficient_data",
                    "section_name": section_name,
                    "unity": 0.0,
                }
                continue
            capacity = _section_capacity(section, material.properties)
            moment_y = float(demand["max_abs"].get("moment_y_nm") or 0.0)
            moment_z = float(demand["max_abs"].get("moment_z_nm") or 0.0)
            axial = float(demand["max_abs"].get("axial_n") or 0.0)
            ratios = {
                "axial": axial / max(capacity["axial_n"], 1.0),
                "moment_major": moment_y / max(capacity["moment_major_nm"], 1.0),
                "moment_minor": moment_z / max(capacity["moment_minor_nm"], 1.0),
            }
            deflection_limit = _deflection_limit_m(str(demand.get("role") or ""), float(demand.get("max_member_length_m") or 0.0))
            deflection_ratio = 0.0
            if deflection_limit > 0.0:
                governing_deflection = max(float(demand["max_abs"].get("deflection_y_m") or 0.0), float(demand["max_abs"].get("deflection_z_m") or 0.0))
                deflection_ratio = governing_deflection / deflection_limit
            ratios["deflection"] = deflection_ratio
            unity = max(ratios.values())
            evaluation[group_id] = {
                "status": "evaluated",
                "section_name": section_name,
                "catalog_family_id": selection.get("preferred_family_id"),
                "unity": unity,
                "ratios": ratios,
                "element_count": len(elements),
                "candidate_section_ids": list(selection.get("candidate_sections") or []),
                "deflection_limit_m": deflection_limit,
            }
        return evaluation

    @staticmethod
    def _advance_failing_groups(group_state: Dict[str, Dict[str, Any]], evaluation: Dict[str, Dict[str, Any]]) -> bool:
        changed = False
        for group_id, data in evaluation.items():
            if data.get("status") != "evaluated":
                continue
            if float(data.get("unity") or 0.0) <= 1.0:
                continue
            state = group_state.get(group_id)
            if not state:
                continue
            if state["index"] + 1 >= len(state["candidates"]):
                continue
            state["index"] += 1
            changed = True
        return changed


def _initial_group_state(source_model) -> Dict[str, Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for element in source_model.elements:
        selection = dict(element.metadata.get("catalog_selection") or {})
        group_id = str(selection.get("sizing_group_id") or "")
        candidates = list(selection.get("candidate_sections") or [])
        if not group_id or not candidates:
            continue
        groups.setdefault(group_id, {"candidates": candidates, "index": 0})
    return groups


def _section_capacity(section, material_properties: Dict[str, Any]) -> Dict[str, float]:
    props = dict((section.metadata or {}).get("section_properties") or {})
    fy = float(material_properties.get("fy_pa", 345_000_000.0))
    phi = 0.9
    area = float(props.get("area_m2") or 0.0)
    s_major = float(props.get("section_modulus_major_m3") or 0.0)
    s_minor = float(props.get("section_modulus_minor_m3") or 0.0)
    return {
        "axial_n": phi * fy * area,
        "moment_major_nm": phi * fy * s_major,
        "moment_minor_nm": phi * fy * s_minor,
    }


def _deflection_limit_m(role: str, length_m: float) -> float:
    if length_m <= 0.0:
        return 0.0
    role = role or ""
    if role in {"floor_beam", "floor_girder"}:
        return length_m / 360.0
    if role in {"roof_primary_frame", "roof_collector", "drag_collector", "perimeter_spandrel", "panel_joint_support", "roof_edge_support", "opening_header", "opening_sill"}:
        return length_m / 240.0
    return 0.0


def _selected_section_costs(analytical_model, group_demands: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    section_lookup = {section.id: section for section in analytical_model.sections}
    section_counts: Counter[str] = Counter()
    total_weight_n = 0.0
    total_length_m = 0.0
    for group_id, data in group_demands.items():
        section_id = str(data.get("section_id") or "")
        if not section_id:
            continue
        section = section_lookup.get(section_id)
        if not section:
            continue
        props = dict((section.metadata or {}).get("section_properties") or {})
        section_name = str((section.metadata or {}).get("catalog_section_name") or section.id)
        section_counts[section_name] += len(data.get("element_ids") or [])
        total_length_m += float(data.get("length_m_total") or 0.0)
        total_weight_n += float(props.get("weight_n_per_m") or 0.0) * float(data.get("length_m_total") or 0.0)
    return {
        "selected_section_counts": dict(section_counts),
        "total_structural_length_m": round(total_length_m, 3),
        "total_weight_n": round(total_weight_n, 3),
        "total_weight_kips": round(total_weight_n / 4448.2216152605, 3),
    }


def _write_roundtripped_physical_outputs(package: DesignPackage, output_dir: Path) -> List[PipelineArtifact]:
    if not package.physical_model:
        return []

    artifacts: List[PipelineArtifact] = []

    sized_plan_path = output_dir / "physical_model_sized_plan.json"
    sized_plan_path.write_text(json.dumps(package.physical_model.plan, indent=2))
    artifacts.append(
        PipelineArtifact(
            kind=ArtifactKind.BIM_PLAN,
            format=ArtifactFormat.JSON,
            path=str(sized_plan_path),
            metadata={"role": ArtifactRole.BIM_PLAN.value, "label": "Sized Physical Plan", "is_primary": False},
        )
    )

    if package.physical_model.authored_plan:
        sized_authored_path = output_dir / "physical_model_sized_authored_plan.json"
        sized_authored_path.write_text(json.dumps(package.physical_model.authored_plan, indent=2))
        artifacts.append(
            PipelineArtifact(
                kind=ArtifactKind.BIM_PLAN,
                format=ArtifactFormat.JSON,
                path=str(sized_authored_path),
                metadata={"role": ArtifactRole.BIM_PLAN.value, "label": "Sized Authored Physical Plan", "is_primary": False},
            )
        )

    if package.physical_model.semantic_model:
        sized_semantic_path = output_dir / "physical_model_sized_semantic_model.json"
        sized_semantic_path.write_text(json.dumps(package.physical_model.semantic_model, indent=2))
        artifacts.append(
            PipelineArtifact(
                kind=ArtifactKind.SEMANTIC_MODEL,
                format=ArtifactFormat.JSON,
                path=str(sized_semantic_path),
                metadata={"role": ArtifactRole.SEMANTIC_MODEL.value, "label": "Sized Semantic Building Model", "is_primary": False},
            )
        )

    sized_ifc_path = output_dir / "physical_model_sized.ifc"
    report = HeadlessIfcExecutor(default_storey_name="Level 0", overwrite_existing=True).execute_plan(package.physical_model.plan, sized_ifc_path)
    artifacts.append(
        PipelineArtifact(
            kind=ArtifactKind.PHYSICAL_IFC,
            format=ArtifactFormat.IFC,
            path=str(sized_ifc_path),
            metadata={
                "role": ArtifactRole.ENGINEERING_REPORT.value,
                "label": "Sized Physical IFC",
                "report_kind": "sized_physical_ifc",
                "is_primary": False,
                "created": list(report.created),
            },
        )
    )

    return artifacts
