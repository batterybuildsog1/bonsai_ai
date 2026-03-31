"""Thin-client helpers for importing external design artifacts into Blender."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from urllib import parse, request

try:
    import bpy  # type: ignore
except Exception:
    bpy = None


def _replace_text(name: str, content: str) -> None:
    if bpy is None:
        return
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    text.clear()
    text.write(content)


def load_json_artifact(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def submit_design_job(bridge_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = bridge_url.rstrip("/") + "/v1/jobs/design"
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def get_job(bridge_url: str, job_id: str) -> Dict[str, Any]:
    endpoint = bridge_url.rstrip("/") + f"/v1/jobs/{parse.quote(job_id)}"
    with request.urlopen(endpoint, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def download_artifact(bridge_url: str, artifact_id: str, destination: str | Path) -> str:
    endpoint = bridge_url.rstrip("/") + f"/v1/artifacts/{parse.quote(artifact_id)}"
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    with request.urlopen(endpoint, timeout=120) as response:
        target.write_bytes(response.read())
    return str(target)


def list_artifacts(job: Dict[str, Any], *, role: str | None = None, kind: str | None = None, is_primary: bool | None = None) -> List[Dict[str, Any]]:
    artifacts = list(job.get("artifacts") or [])
    if role is not None:
        artifacts = [artifact for artifact in artifacts if artifact.get("role") == role]
    if kind is not None:
        artifacts = [artifact for artifact in artifacts if artifact.get("kind") == kind]
    if is_primary is not None:
        artifacts = [artifact for artifact in artifacts if bool(artifact.get("is_primary")) is is_primary]
    return artifacts


def download_job_artifact(bridge_url: str, job: Dict[str, Any], *, role: str, destination_dir: str | Path) -> str:
    artifact = _preferred_artifact(job, role)
    if artifact is None:
        raise ValueError(f"No artifact with role '{role}' is available for this job.")
    filename = str((artifact.get("metadata") or {}).get("filename") or f"{artifact['id']}.{artifact['format']}")
    target = Path(destination_dir) / str(job["id"]) / filename
    return download_artifact(bridge_url, artifact["id"], target)


def import_job_artifact(
    bridge_url: str,
    job: Dict[str, Any],
    settings,
    role: str,
    destination_dir: str | Path,
) -> str:
    preferred_role = role
    artifact = _preferred_artifact(job, role)
    if artifact is None and role == "results":
        for candidate in ("solver_result", "results_bundle"):
            artifact = _preferred_artifact(job, candidate)
            if artifact is not None:
                preferred_role = candidate
                break
    if artifact is None:
        raise ValueError(f"No importable artifact was found for '{role}'.")

    downloaded = download_job_artifact(bridge_url, job, role=preferred_role, destination_dir=destination_dir)
    if preferred_role == "primary_ifc":
        return _import_ifc_artifact(downloaded)
    if artifact.get("format") == "pdf":
        return f"Downloaded '{artifact.get('label')}' to {downloaded}."
    return import_design_artifact(downloaded, settings)


def import_design_artifact(path: str | Path, settings) -> str:
    payload = load_json_artifact(path)
    target = Path(path)

    if {"schema_version", "entrypoints", "physical_summary", "analysis_summary"}.issubset(payload.keys()):
        _replace_text(settings.log_text_name, json.dumps(payload, indent=2))
        _replace_text(settings.results_text_name, json.dumps(payload["analysis_summary"], indent=2))
        plan_ref = payload.get("entrypoints", {}).get("physical_plan")
        if plan_ref:
            plan_path = (target.parent / plan_ref).resolve()
            if plan_path.exists():
                _replace_text(settings.plan_text_name, json.dumps(load_json_artifact(plan_path), indent=2))
        return f"Imported results bundle '{target.name}'."

    if "physical_model" in payload:
        _replace_text(settings.log_text_name, json.dumps(payload, indent=2))
        physical_model = payload.get("physical_model") or {}
        if physical_model.get("plan"):
            _replace_text(settings.plan_text_name, json.dumps(physical_model["plan"], indent=2))
        return f"Imported design package '{target.name}'."

    if {"version", "actions"}.issubset(payload.keys()):
        _replace_text(settings.plan_text_name, json.dumps(payload, indent=2))
        return f"Imported plan artifact '{target.name}'."

    _replace_text(settings.log_text_name, json.dumps(payload, indent=2))
    return f"Imported JSON artifact '{target.name}' into the log."


def _preferred_artifact(job: Dict[str, Any], role: str) -> Dict[str, Any] | None:
    artifacts = list_artifacts(job, role=role)
    if artifacts:
        return artifacts[0]
    if role == "primary_ifc":
        artifacts = list_artifacts(job, kind="physical_ifc", is_primary=True) or list_artifacts(job, kind="physical_ifc")
        return artifacts[0] if artifacts else None
    return None


def _import_ifc_artifact(path: str | Path) -> str:
    try:
        import bpy  # type: ignore
        from .presentation import bake_presentation
    except Exception:
        return f"Downloaded primary IFC to {path}."

    bim_ops = getattr(bpy.ops, "bim", None)
    if bim_ops:
        for operator_name in ("load_project", "load_ifc", "open_project"):
            operator = getattr(bim_ops, operator_name, None)
            if operator is None:
                continue
            try:
                operator(filepath=str(path))
                report = bake_presentation(path)
                return (
                    f"Imported primary IFC from {path}. "
                    f"Styled {report.get('styled_objects', 0)} objects across "
                    f"{report.get('view_collection_count', 0)} review collections."
                )
            except TypeError:
                try:
                    operator("INVOKE_DEFAULT", filepath=str(path))
                    report = bake_presentation(path)
                    return (
                        f"Imported primary IFC from {path}. "
                        f"Styled {report.get('styled_objects', 0)} objects across "
                        f"{report.get('view_collection_count', 0)} review collections."
                    )
                except Exception:
                    continue
            except Exception:
                continue
    return f"Downloaded primary IFC to {path}. Open it in Bonsai if automatic import is unavailable."
