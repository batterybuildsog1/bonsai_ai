from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List

from .contracts import (
    AnalysisSummary,
    ArtifactFormat,
    ArtifactKind,
    ArtifactRole,
    DesignPackage,
    NormalizedArtifactRef,
    PhysicalSummary,
    PipelineArtifact,
    ResultsBundle,
)
from .pipeline import ResultsBundleBackend


class JsonResultsBundleBackend(ResultsBundleBackend):
    def build(self, package: DesignPackage, output_dir: Path) -> List[PipelineArtifact]:
        bundle = self._build_bundle(package, output_dir)
        path = output_dir / "results_bundle.json"
        path.write_text(json.dumps(asdict(bundle), indent=2))
        return [
            PipelineArtifact(
                kind=ArtifactKind.RESULTS_BUNDLE,
                format=ArtifactFormat.JSON,
                path=str(path),
                metadata={"role": ArtifactRole.RESULTS_BUNDLE.value, "label": "Results Bundle", "is_primary": True},
            )
        ]

    def _build_bundle(self, package: DesignPackage, output_dir: Path) -> ResultsBundle:
        all_artifacts = list(package.physical_artifacts) + list(package.analysis_artifacts) + list(package.review_artifacts)
        artifact_refs = [self._artifact_ref(artifact, output_dir) for artifact in all_artifacts]
        execution_report = (package.physical_model.metadata.get("execution_report") if package.physical_model else {}) or {}
        execution_items = execution_report.get("items") or []
        result_status = "not_requested"
        if package.analysis_request:
            result_status = "exported"
        if package.analysis_result:
            result_status = package.analysis_result.status

        return ResultsBundle(
            schema_version="1.0",
            entrypoints={
                "physical_ifc": self._entrypoint(package.physical_artifacts, ArtifactKind.PHYSICAL_IFC, output_dir),
                "physical_plan": self._entrypoint(package.physical_artifacts, ArtifactKind.BIM_PLAN, output_dir),
                "structural_source_model": self._entrypoint(
                    all_artifacts,
                    ArtifactKind.STRUCTURAL_SOURCE_MODEL,
                    output_dir,
                    preferred_role=ArtifactRole.STRUCTURAL_SOURCE_MODEL,
                ),
                "analytical_model": self._entrypoint(
                    all_artifacts,
                    ArtifactKind.ANALYTICAL_MODEL,
                    output_dir,
                    preferred_role=ArtifactRole.ANALYSIS_MODEL,
                ),
                "engineering_model_global_frame": self._entrypoint_by_role_and_scope(
                    all_artifacts,
                    ArtifactRole.ENGINEERING_MODEL,
                    "global_frame",
                    output_dir,
                ),
                "engineering_model_roof_load_path": self._entrypoint_by_role_and_scope(
                    all_artifacts,
                    ArtifactRole.ENGINEERING_MODEL,
                    "roof_load_path",
                    output_dir,
                ),
                "engineering_model_facade_support": self._entrypoint_by_role_and_scope(
                    all_artifacts,
                    ArtifactRole.ENGINEERING_MODEL,
                    "facade_support",
                    output_dir,
                ),
                "engineering_model_substructure": self._entrypoint_by_role_and_scope(
                    all_artifacts,
                    ArtifactRole.ENGINEERING_MODEL,
                    "substructure",
                    output_dir,
                ),
                "engineering_model_opening_support": self._entrypoint_by_role_and_scope(
                    all_artifacts,
                    ArtifactRole.ENGINEERING_MODEL,
                    "opening_support",
                    output_dir,
                ),
                "solver_request": self._entrypoint(
                    all_artifacts,
                    ArtifactKind.SOLVER_INPUT,
                    output_dir,
                    preferred_format=ArtifactFormat.JSON,
                ),
                "solver_result": self._entrypoint(all_artifacts, ArtifactKind.SOLVER_RESULT, output_dir),
                "freecad_handoff": self._entrypoint_by_role(all_artifacts, ArtifactRole.FREECAD_HANDOFF, output_dir),
                "freecad_model": self._entrypoint_by_role(all_artifacts, ArtifactRole.FREECAD_MODEL, output_dir),
            },
            artifacts=artifact_refs,
            physical_summary=PhysicalSummary(
                summary=package.physical_model.summary if package.physical_model else "",
                assumptions=list(package.physical_model.assumptions) if package.physical_model else [],
                created=list(execution_report.get("created") or []),
                element_counts=self._element_counts(execution_items),
                storeys=self._storeys(execution_items, package),
                planner_metadata=dict(package.physical_model.metadata) if package.physical_model else {},
            ),
            analysis_summary=AnalysisSummary(
                status=result_status,
                domains=[domain.value for domain in package.brief.analysis_domains],
                load_cases=[case.name for case in package.analysis_request.load_cases] if package.analysis_request else [],
                load_combinations=[combo.name for combo in package.analysis_request.load_combinations] if package.analysis_request else [],
                solver=package.analysis_request.solver if package.analysis_request else None,
                design_codes=list(package.analysis_request.design_codes) if package.analysis_request else [],
                governing_cases=list(package.analysis_result.governing_cases) if package.analysis_result else [],
                unity_checks=dict(package.analysis_result.unity_checks) if package.analysis_result else {},
                warnings=list(package.analysis_result.warnings) if package.analysis_result else [],
            ),
            diagnostics={
                "execution_messages": list(execution_report.get("messages") or []),
                "missing_artifacts": self._missing_artifacts(package),
                "requested_engineering_scopes": list((package.engineering_model_summary or {}).get("requested_scopes") or []),
                "emitted_engineering_scopes": list((package.engineering_model_summary or {}).get("emitted_scopes") or []),
                "invalid_engineering_scopes": list((package.engineering_model_summary or {}).get("invalid_scopes") or []),
                "engineering_scope_diagnostics": dict((package.engineering_model_summary or {}).get("scope_diagnostics") or {}),
                "engineering_warnings": list((package.engineering_model_summary or {}).get("warnings") or []),
                "has_analysis_request": bool(package.analysis_request),
            },
            blender_payload={
                "primary_ifc_role": ArtifactRole.PRIMARY_IFC.value,
                "results_roles": [ArtifactRole.SOLVER_RESULT.value, ArtifactRole.RESULTS_BUNDLE.value],
                "plan_role": ArtifactRole.BIM_PLAN.value,
                "status": result_status,
            },
        )

    @staticmethod
    def _artifact_ref(artifact: PipelineArtifact, output_dir: Path) -> NormalizedArtifactRef:
        role = artifact.metadata.get("role") or _role_for_kind(artifact.kind).value
        label = artifact.metadata.get("label") or _label_for_kind(artifact.kind)
        is_primary = bool(artifact.metadata.get("is_primary") or artifact.kind in {ArtifactKind.PHYSICAL_IFC, ArtifactKind.RESULTS_BUNDLE})
        return NormalizedArtifactRef(
            kind=artifact.kind,
            format=artifact.format,
            path=_relative_path(artifact.path, output_dir),
            role=ArtifactRole(role),
            label=label,
            is_primary=is_primary,
            metadata=dict(artifact.metadata),
        )

    @staticmethod
    def _entrypoint(
        artifacts: Iterable[PipelineArtifact],
        kind: ArtifactKind,
        output_dir: Path,
        *,
        preferred_role: ArtifactRole | None = None,
        preferred_format: ArtifactFormat | None = None,
    ) -> str | None:
        candidates = [candidate for candidate in artifacts if candidate.kind == kind]
        artifact = None
        if preferred_role is not None:
            artifact = next((candidate for candidate in candidates if candidate.metadata.get("role") == preferred_role.value), None)
        if artifact is None and preferred_format is not None:
            artifact = next((candidate for candidate in candidates if candidate.format == preferred_format), None)
        if artifact is None:
            artifact = next(iter(candidates), None)
        if artifact is None:
            return None
        return _relative_path(artifact.path, output_dir)

    @staticmethod
    def _entrypoint_by_role(artifacts: Iterable[PipelineArtifact], role: ArtifactRole, output_dir: Path) -> str | None:
        artifact = next((candidate for candidate in artifacts if candidate.metadata.get("role") == role.value), None)
        if artifact is None:
            return None
        return _relative_path(artifact.path, output_dir)

    @staticmethod
    def _entrypoint_by_role_and_scope(
        artifacts: Iterable[PipelineArtifact],
        role: ArtifactRole,
        scope: str,
        output_dir: Path,
    ) -> str | None:
        artifact = next(
            (
                candidate
                for candidate in artifacts
                if candidate.metadata.get("role") == role.value and str(candidate.metadata.get("scope") or "") == scope
            ),
            None,
        )
        if artifact is None:
            return None
        return _relative_path(artifact.path, output_dir)

    @staticmethod
    def _element_counts(execution_items: List[Dict[str, object]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in execution_items:
            ifc_class = str(item.get("ifc_class") or "unknown")
            counts[ifc_class] = counts.get(ifc_class, 0) + 1
        return counts

    @staticmethod
    def _storeys(execution_items: List[Dict[str, object]], package: DesignPackage) -> List[str]:
        storeys: List[str] = []
        for item in execution_items:
            metadata = item.get("metadata") or {}
            storey_name = metadata.get("storey_name")
            if storey_name and storey_name not in storeys:
                storeys.append(str(storey_name))
        if storeys:
            return storeys
        if package.physical_model:
            for action in package.physical_model.plan.get("actions", []):
                if action["type"] == "ensure_storey" and action["name"] not in storeys:
                    storeys.append(action["name"])
        return storeys

    @staticmethod
    def _missing_artifacts(package: DesignPackage) -> List[str]:
        missing = []
        if not any(artifact.kind == ArtifactKind.PHYSICAL_IFC for artifact in package.physical_artifacts):
            missing.append("physical_ifc")
        if package.analysis_request and not any(
            artifact.kind == ArtifactKind.ANALYTICAL_MODEL for artifact in package.analysis_artifacts
        ):
            missing.append("analytical_model")
        requested_scopes = list((package.engineering_model_summary or {}).get("requested_scopes") or [])
        emitted_scopes = set((package.engineering_model_summary or {}).get("emitted_scopes") or [])
        invalid_scopes = set((package.engineering_model_summary or {}).get("invalid_scopes") or [])
        for scope in requested_scopes:
            if scope in invalid_scopes:
                missing.append(f"engineering_model_invalid:{scope}")
            elif scope not in emitted_scopes:
                missing.append(f"engineering_model:{scope}")
        return missing


def _relative_path(path: str, output_dir: Path) -> str:
    target = Path(path)
    return str(target.relative_to(output_dir)) if target.is_absolute() else str(target)


def _role_for_kind(kind: ArtifactKind) -> ArtifactRole:
    mapping = {
        ArtifactKind.DESIGN_PACKAGE: ArtifactRole.MANIFEST,
        ArtifactKind.BIM_PLAN: ArtifactRole.BIM_PLAN,
        ArtifactKind.PHYSICAL_IFC: ArtifactRole.PRIMARY_IFC,
        ArtifactKind.STRUCTURAL_SOURCE_MODEL: ArtifactRole.STRUCTURAL_SOURCE_MODEL,
        ArtifactKind.ANALYTICAL_MODEL: ArtifactRole.ANALYSIS_MODEL,
        ArtifactKind.ENGINEERING_MODEL: ArtifactRole.ENGINEERING_MODEL,
        ArtifactKind.SOLVER_INPUT: ArtifactRole.SOLVER_INPUT,
        ArtifactKind.SOLVER_RESULT: ArtifactRole.SOLVER_RESULT,
        ArtifactKind.RESULTS_BUNDLE: ArtifactRole.RESULTS_BUNDLE,
        ArtifactKind.ENGINEERING_REPORT: ArtifactRole.ENGINEERING_REPORT,
        ArtifactKind.REVIEW_RENDER: ArtifactRole.REVIEW_RENDER,
    }
    return mapping.get(kind, ArtifactRole.MANIFEST)


def _label_for_kind(kind: ArtifactKind) -> str:
    mapping = {
        ArtifactKind.DESIGN_PACKAGE: "Design Package Manifest",
        ArtifactKind.BIM_PLAN: "Physical Model Plan",
        ArtifactKind.PHYSICAL_IFC: "Primary IFC",
        ArtifactKind.STRUCTURAL_SOURCE_MODEL: "Structural Source Model",
        ArtifactKind.ANALYTICAL_MODEL: "Analytical Model",
        ArtifactKind.ENGINEERING_MODEL: "Engineering Model",
        ArtifactKind.SOLVER_INPUT: "Solver Request",
        ArtifactKind.SOLVER_RESULT: "Solver Result",
        ArtifactKind.RESULTS_BUNDLE: "Results Bundle",
        ArtifactKind.ENGINEERING_REPORT: "Engineering Report",
        ArtifactKind.REVIEW_RENDER: "Review Render",
    }
    return mapping.get(kind, kind.value.replace("_", " ").title())
