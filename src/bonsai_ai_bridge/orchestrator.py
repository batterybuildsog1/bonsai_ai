from __future__ import annotations

import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from bonsai_ai.analysis_exports import JsonAnalysisExportBackend
from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    ArtifactFormat,
    ArtifactKind,
    ArtifactRole,
    DesignBrief,
    LoadCase,
    PipelineArtifact,
    SourceDocument,
)
from bonsai_ai.execution import IfcPhysicalModelBackend
from bonsai_ai.freecad_runner import run_freecad_handoff
from bonsai_ai.pipeline import DesignPipeline
from bonsai_ai.planner_backends import CorePhysicalPlannerBackend
from bonsai_ai.pynite_backend import PyNiteSolverBackend
from bonsai_ai.results_bundle import JsonResultsBundleBackend

DEFAULT_ENGINEERING_SCOPES = [
    "global_frame",
    "roof_load_path",
    "facade_support",
    "substructure",
    "opening_support",
]


@dataclass
class ArtifactRecord:
    id: str
    path: str
    kind: str
    format: str
    role: str
    label: str
    is_primary: bool
    source_stage: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobRecord:
    id: str
    status: str
    stage: str
    output_dir: str
    created_at: str
    updated_at: str
    progress_pct: int = 0
    stage_message: str | None = None
    manifest_path: str | None = None
    summary: str | None = None
    artifacts: List[ArtifactRecord] = field(default_factory=list)
    error: str | None = None


class DesignOrchestrator:
    def __init__(self) -> None:
        self.jobs: Dict[str, JobRecord] = {}
        self.artifacts: Dict[str, ArtifactRecord] = {}

    def run_design_job(
        self,
        *,
        provider: str,
        model: str | None,
        prompt: str,
        docs_text: str | None = None,
        scene_context: Dict[str, Any] | None = None,
        analysis_domains: List[str] | None = None,
        design_codes: List[str] | None = None,
        solver: str = "calculix",
        api_key: str | None = None,
        reasoning_effort: str | None = "high",
        service_tier: str | None = "priority",
        run_freecad: bool = False,
        freecad_executable: str | None = None,
    ) -> JobRecord:
        job_id = uuid.uuid4().hex
        output_dir = Path(tempfile.mkdtemp(prefix="bonsai_ai_job_"))
        now = _utc_now()
        job = JobRecord(
            id=job_id,
            status="queued",
            stage="planning",
            output_dir=str(output_dir),
            created_at=now,
            updated_at=now,
            progress_pct=0,
            stage_message="Queued for planning.",
        )
        self.jobs[job_id] = job

        try:
            self._set_job_stage(job, status="running", stage="planning", progress_pct=10, stage_message="Generating a physical model plan.")
            brief = DesignBrief(
                prompt=prompt,
                scene_context=scene_context,
                documents=self._documents_from_text(output_dir, docs_text),
                analysis_domains=[AnalysisDomain(domain) for domain in (analysis_domains or [])],
            )
            analysis_request = None
            if brief.analysis_domains:
                analysis_request = AnalysisRequest(
                    solver=solver,
                    design_codes=design_codes or [],
                    load_cases=[
                        LoadCase(
                            name=f"{domain.value}_default",
                            domain=domain,
                            code_basis=(design_codes[0] if design_codes else "unspecified"),
                        )
                            for domain in brief.analysis_domains
                    ],
                    export_options={
                        "freecad_handoff": True,
                        "engineering_scopes": list(DEFAULT_ENGINEERING_SCOPES),
                    },
                )

            solver_backend = PyNiteSolverBackend() if analysis_request and solver == "pynite" else None
            pipeline = DesignPipeline(
                planner=CorePhysicalPlannerBackend(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    reasoning_effort=reasoning_effort,
                    service_tier=service_tier,
                ),
                physical_backend=IfcPhysicalModelBackend(),
                analysis_exporter=JsonAnalysisExportBackend(),
                solver=solver_backend,
                results_backend=JsonResultsBundleBackend(),
            )
            self._set_job_stage(job, status="running", stage="materializing_ifc", progress_pct=35, stage_message="Materializing the IFC package.")
            package = pipeline.run(brief=brief, output_dir=output_dir, analysis_request=analysis_request)
            if analysis_request:
                self._set_job_stage(
                    job,
                    status="running",
                    stage="exporting_analysis",
                    progress_pct=70,
                    stage_message="Packaging the analytical handoff and results bundle.",
                )
            if run_freecad:
                self._set_job_stage(
                    job,
                    status="running",
                    stage="running_freecad",
                    progress_pct=82,
                    stage_message="Running the FreeCAD handoff macro.",
                )
                package.analysis_artifacts.extend(run_freecad_handoff(output_dir, freecad_bin=freecad_executable))
                if package.results_artifacts:
                    package.results_artifacts = list(JsonResultsBundleBackend().build(package, output_dir))
                DesignPipeline.write_manifest(package, output_dir / "design_package.json")
            self._set_job_stage(job, status="running", stage="packaging_results", progress_pct=90, stage_message="Registering bridge artifacts.")
            job.manifest_path = str(output_dir / "design_package.json")
            job.summary = package.physical_model.summary if package.physical_model else None
            job.artifacts = self._register_artifacts(job_id, package, output_dir / "design_package.json")
            self._set_job_stage(job, status="completed", stage="ready", progress_pct=100, stage_message="Artifacts are ready for Blender import.")
            return job
        except Exception as exc:
            self._set_job_stage(job, status="failed", stage="failed", progress_pct=100, stage_message="Design job failed.")
            job.error = str(exc)
            return job

    def get_job(self, job_id: str) -> JobRecord:
        return self.jobs[job_id]

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        return self.artifacts[artifact_id]

    def _register_artifacts(self, job_id: str, package, manifest_path: Path) -> List[ArtifactRecord]:
        artifact_records: List[ArtifactRecord] = []
        built_artifacts = list(package.physical_artifacts) + list(package.analysis_artifacts) + list(package.results_artifacts) + list(package.review_artifacts) + [
            PipelineArtifact(
                kind=ArtifactKind.DESIGN_PACKAGE,
                format=ArtifactFormat.JSON,
                path=str(manifest_path),
                metadata={"role": ArtifactRole.MANIFEST.value, "label": "Design Package Manifest"},
            )
        ]
        for artifact in built_artifacts:
            artifact_id = f"{job_id}_{uuid.uuid4().hex[:8]}"
            role = str(artifact.metadata.get("role") or _artifact_role(artifact.kind).value)
            label = str(artifact.metadata.get("label") or _artifact_label(artifact.kind))
            created_at = _utc_now()
            base_metadata = {
                "filename": Path(artifact.path).name,
                "analysis_domains": [domain.value for domain in package.brief.analysis_domains],
                "design_codes": list(package.analysis_request.design_codes) if package.analysis_request else [],
                "solver": package.analysis_request.solver if package.analysis_request else None,
                "summary": package.physical_model.summary if package.physical_model else None,
            }
            base_metadata.update(getattr(artifact, "metadata", {}) or {})
            record = ArtifactRecord(
                id=artifact_id,
                path=artifact.path,
                kind=artifact.kind.value,
                format=artifact.format.value,
                role=role,
                label=label,
                is_primary=bool(base_metadata.get("is_primary") or artifact.kind in {ArtifactKind.PHYSICAL_IFC, ArtifactKind.RESULTS_BUNDLE}),
                source_stage=_artifact_stage(artifact.kind),
                created_at=created_at,
                metadata=base_metadata,
            )
            self.artifacts[artifact_id] = record
            artifact_records.append(record)
        return artifact_records

    @staticmethod
    def _set_job_stage(job: JobRecord, *, status: str, stage: str, progress_pct: int, stage_message: str) -> None:
        job.status = status
        job.stage = stage
        job.progress_pct = progress_pct
        job.stage_message = stage_message
        job.updated_at = _utc_now()

    @staticmethod
    def _documents_from_text(output_dir: Path, docs_text: str | None) -> List[SourceDocument]:
        if not docs_text:
            return []
        doc_path = output_dir / "reference_docs.txt"
        doc_path.write_text(docs_text)
        return [SourceDocument(name=doc_path.name, path=str(doc_path), role="reference_text")]

def _artifact_role(kind: ArtifactKind) -> ArtifactRole:
    mapping = {
        ArtifactKind.DESIGN_PACKAGE: ArtifactRole.MANIFEST,
        ArtifactKind.BIM_PLAN: ArtifactRole.BIM_PLAN,
        ArtifactKind.SEMANTIC_MODEL: ArtifactRole.SEMANTIC_MODEL,
        ArtifactKind.PHYSICAL_IFC: ArtifactRole.PRIMARY_IFC,
        ArtifactKind.ANALYTICAL_MODEL: ArtifactRole.ANALYSIS_MODEL,
        ArtifactKind.ENGINEERING_MODEL: ArtifactRole.ENGINEERING_MODEL,
        ArtifactKind.SOLVER_INPUT: ArtifactRole.SOLVER_INPUT,
        ArtifactKind.SOLVER_RESULT: ArtifactRole.SOLVER_RESULT,
        ArtifactKind.RESULTS_BUNDLE: ArtifactRole.RESULTS_BUNDLE,
        ArtifactKind.ENGINEERING_REPORT: ArtifactRole.ENGINEERING_REPORT,
        ArtifactKind.REVIEW_RENDER: ArtifactRole.REVIEW_RENDER,
    }
    return mapping.get(kind, ArtifactRole.MANIFEST)


def _artifact_label(kind: ArtifactKind) -> str:
    return {
        ArtifactKind.DESIGN_PACKAGE: "Design Package Manifest",
        ArtifactKind.BIM_PLAN: "Physical Model Plan",
        ArtifactKind.SEMANTIC_MODEL: "Semantic Building Model",
        ArtifactKind.PHYSICAL_IFC: "Primary IFC",
        ArtifactKind.ANALYTICAL_MODEL: "Analytical Model",
        ArtifactKind.ENGINEERING_MODEL: "Engineering Model",
        ArtifactKind.SOLVER_INPUT: "Solver Request",
        ArtifactKind.SOLVER_RESULT: "Solver Result",
        ArtifactKind.RESULTS_BUNDLE: "Results Bundle",
        ArtifactKind.ENGINEERING_REPORT: "Engineering Report",
        ArtifactKind.REVIEW_RENDER: "Review Render",
    }.get(kind, kind.value.replace("_", " ").title())


def _artifact_stage(kind: ArtifactKind) -> str:
    if kind in {ArtifactKind.PHYSICAL_IFC, ArtifactKind.BIM_PLAN, ArtifactKind.SEMANTIC_MODEL}:
        return "materializing_ifc"
    if kind in {ArtifactKind.ANALYTICAL_MODEL, ArtifactKind.ENGINEERING_MODEL, ArtifactKind.SOLVER_INPUT, ArtifactKind.SOLVER_RESULT}:
        return "exporting_analysis"
    return "packaging_results"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
