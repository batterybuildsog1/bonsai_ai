# Bridge Server

## Purpose
FastAPI REST server that exposes the full design pipeline as HTTP endpoints, enabling the Blender addon and other clients to submit design jobs, poll status, and download artifacts.

## How It Works

### bonsai_ai_bridge/ package

**server.py** (205 lines):
- FastAPI app with 6 endpoints:
  - `GET /health` -> `HealthResponse(status, default_models)`
  - `POST /v1/plan` -> `BuildingPlan` (simple plan generation)
  - `POST /v1/jobs/design` -> `JobResponse` (full pipeline job)
  - `GET /v1/jobs/{job_id}` -> `JobResponse` (job status/results)
  - `GET /v1/artifacts/{artifact_id}/meta` -> `ArtifactResponse`
  - `GET /v1/artifacts/{artifact_id}` -> `FileResponse` (binary download)
- Pydantic models: `PlanRequest`, `DesignJobRequest` (with all pipeline options), `ArtifactResponse`, `JobResponse`.
- `DesignJobRequest` includes: provider, model, prompt, docs_text, scene_context, analysis_domains, design_codes, solver, reasoning_effort, service_tier, run_freecad, freecad_executable.
- Uses a singleton `DesignOrchestrator` instance.

**orchestrator.py** (~300+ lines):
- `DesignOrchestrator` class manages jobs and artifacts in memory.
- `run_design_job(...)`:
  1. Creates a `JobRecord` with UUID and temp directory.
  2. Builds a `DesignBrief` and optional `AnalysisRequest`.
  3. Constructs a `DesignPipeline` with `CorePhysicalPlannerBackend`, `IfcPhysicalModelBackend`, `JsonAnalysisExportBackend`, optional `PyNiteSolverBackend`, `JsonResultsBundleBackend`.
  4. Runs the pipeline with stage updates (planning -> materializing_ifc -> analysis -> finalizing).
  5. Optionally runs FreeCAD handoff.
  6. Converts `PipelineArtifact` instances to `ArtifactRecord` instances with UUIDs.
  7. Updates job status to "completed" or "failed".
- `get_job(job_id)` and `get_artifact(artifact_id)` for retrieval.
- `ArtifactRecord` and `JobRecord` dataclasses track all job state.
- `_documents_from_text()` saves docs_text to a temp file if provided.
- `DEFAULT_ENGINEERING_SCOPES` matches the CLI defaults.

**planner.py** (bridge, 75 lines):
- `generate_plan(provider_name, model, prompt, scene_context)` -- thin async wrapper around `bonsai_ai_core.build_plan()` + `compile_plan()`. Returns a `BuildingPlan` Pydantic model.

**providers.py** (bridge, ~130 lines):
- Re-exports `DEFAULT_MODELS`, `ProviderError` from `bonsai_ai_core`.
- May contain additional bridge-specific provider configuration.

**schemas.py** (bridge, ~170 lines):
- Pydantic models for the API: `BuildingPlan`, action models, etc.

## Current State
Fully implemented. The server provides a complete REST API for the design pipeline.

## Known Issues
- Jobs are stored in memory (`self.jobs` dict) with no persistence. Server restart loses all job data.
- `run_design_job()` is synchronous and blocks the FastAPI event loop. Long-running jobs (especially with PyNite analysis + FreeCAD) will block other requests.
- Artifact files are stored in temporary directories (`tempfile.mkdtemp`). No cleanup mechanism exists -- artifacts accumulate until manual cleanup or system restart.
- No authentication or rate limiting on any endpoint.
- The `/v1/plan` endpoint uses a separate `generate_plan()` function that returns compiled actions, while `/v1/jobs/design` runs the full pipeline. The two paths may produce different results for the same prompt.

## Last Reviewed
2026-03-31
