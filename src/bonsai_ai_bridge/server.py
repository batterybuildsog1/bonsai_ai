from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from bonsai_ai_bridge.planner import generate_plan
from bonsai_ai_bridge.orchestrator import DesignOrchestrator
from bonsai_ai_bridge.providers import DEFAULT_MODELS, ProviderError
from bonsai_ai_bridge.schemas import BuildingPlan


app = FastAPI(title="Bonsai AI Bridge", version="0.1.0")
orchestrator = DesignOrchestrator()


class PlanRequest(BaseModel):
    provider: str = Field(default="openai")
    model: Optional[str] = Field(default=None)
    prompt: str
    scene_context: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str
    default_models: dict[str, str]


class DesignJobRequest(BaseModel):
    provider: str = Field(default="openai")
    model: Optional[str] = Field(default=None)
    prompt: str
    docs_text: Optional[str] = None
    scene_context: Optional[dict] = None
    analysis_domains: List[str] = Field(default_factory=list)
    design_codes: List[str] = Field(default_factory=list)
    solver: str = Field(default="calculix")
    reasoning_effort: Optional[str] = Field(default="high")
    service_tier: Optional[str] = Field(default="priority")
    run_freecad: bool = Field(default=False)
    freecad_executable: Optional[str] = Field(default=None)


class ArtifactResponse(BaseModel):
    id: str
    kind: str
    format: str
    role: str
    label: str
    is_primary: bool
    source_stage: str
    created_at: str
    metadata: dict = Field(default_factory=dict)


class JobResponse(BaseModel):
    id: str
    status: str
    stage: str
    created_at: str
    updated_at: str
    progress_pct: int
    stage_message: Optional[str] = None
    summary: Optional[str] = None
    manifest_path: Optional[str] = None
    output_dir: str
    error: Optional[str] = None
    artifacts: List[ArtifactResponse] = Field(default_factory=list)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", default_models=DEFAULT_MODELS)


@app.post("/v1/plan", response_model=BuildingPlan)
async def plan(request: PlanRequest) -> BuildingPlan:
    try:
        return await generate_plan(
            provider_name=request.provider,
            model=request.model,
            prompt=request.prompt,
            scene_context=request.scene_context,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/jobs/design", response_model=JobResponse)
async def create_design_job(request: DesignJobRequest) -> JobResponse:
    try:
        job = orchestrator.run_design_job(
            provider=request.provider,
            model=request.model,
            prompt=request.prompt,
            docs_text=request.docs_text,
            scene_context=request.scene_context,
            analysis_domains=request.analysis_domains,
            design_codes=request.design_codes,
            solver=request.solver,
            reasoning_effort=request.reasoning_effort,
            service_tier=request.service_tier,
            run_freecad=request.run_freecad,
            freecad_executable=request.freecad_executable,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return JobResponse(
        id=job.id,
        status=job.status,
        stage=job.stage,
        created_at=job.created_at,
        updated_at=job.updated_at,
        progress_pct=job.progress_pct,
        stage_message=job.stage_message,
        summary=job.summary,
        manifest_path=job.manifest_path,
        output_dir=job.output_dir,
        error=job.error,
        artifacts=[
            ArtifactResponse(
                id=a.id,
                kind=a.kind,
                format=a.format,
                role=a.role,
                label=a.label,
                is_primary=a.is_primary,
                source_stage=a.source_stage,
                created_at=a.created_at,
                metadata=a.metadata,
            )
            for a in job.artifacts
        ],
    )


@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
async def get_design_job(job_id: str) -> JobResponse:
    try:
        job = orchestrator.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    return JobResponse(
        id=job.id,
        status=job.status,
        stage=job.stage,
        created_at=job.created_at,
        updated_at=job.updated_at,
        progress_pct=job.progress_pct,
        stage_message=job.stage_message,
        summary=job.summary,
        manifest_path=job.manifest_path,
        output_dir=job.output_dir,
        error=job.error,
        artifacts=[
            ArtifactResponse(
                id=a.id,
                kind=a.kind,
                format=a.format,
                role=a.role,
                label=a.label,
                is_primary=a.is_primary,
                source_stage=a.source_stage,
                created_at=a.created_at,
                metadata=a.metadata,
            )
            for a in job.artifacts
        ],
    )


@app.get("/v1/artifacts/{artifact_id}/meta", response_model=ArtifactResponse)
async def get_artifact_meta(artifact_id: str) -> ArtifactResponse:
    try:
        artifact = orchestrator.get_artifact(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    return ArtifactResponse(
        id=artifact.id,
        kind=artifact.kind,
        format=artifact.format,
        role=artifact.role,
        label=artifact.label,
        is_primary=artifact.is_primary,
        source_stage=artifact.source_stage,
        created_at=artifact.created_at,
        metadata=artifact.metadata,
    )


@app.get("/v1/artifacts/{artifact_id}")
async def download_artifact(artifact_id: str):
    try:
        artifact = orchestrator.get_artifact(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    return FileResponse(artifact.path)
