from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .contracts import ArtifactFormat, ArtifactKind, ArtifactRole, PipelineArtifact


_FREECAD_CANDIDATES = (
    "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
    "/Applications/FreeCAD.app/Contents/Resources/bin/freecad",
    "/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd",
    "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD",
    str(Path.home() / "Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd"),
    str(Path.home() / "Applications/FreeCAD.app/Contents/MacOS/FreeCAD"),
)


def find_freecad_binary(preferred: str | None = None) -> str | None:
    if preferred:
        preferred_path = Path(preferred).expanduser()
        if preferred_path.is_absolute():
            return str(preferred_path) if preferred_path.exists() and preferred_path.is_file() else None
        resolved = shutil.which(preferred)
        return resolved if resolved else None

    candidates: List[str] = []
    for candidate in (
        os.environ.get("FREECAD_BIN"),
        shutil.which("FreeCADCmd"),
        shutil.which("FreeCAD"),
        *_FREECAD_CANDIDATES,
    ):
        if not candidate:
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file():
            return str(path)
    return None


def detect_freecad_executable(explicit: str | None = None, *, candidates: Iterable[str] = ()) -> str | None:
    if candidates:
        for candidate in (explicit, *candidates):
            if not candidate:
                continue
            path = Path(candidate).expanduser()
            if path.is_absolute() and path.exists() and path.is_file():
                return str(path)
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None
    return find_freecad_binary(explicit)


def run_freecad_handoff(
    output_dir: str | Path,
    *,
    executable: str | None = None,
    freecad_bin: str | None = None,
    timeout_seconds: int = 240,
) -> List[PipelineArtifact]:
    target_dir = Path(output_dir)
    handoff_path = target_dir / "freecad_handoff.json"
    macro_path = target_dir / "freecad_handoff.py"
    output_document_path = target_dir / "freecad_handoff.FCStd"
    result_path = target_dir / "freecad_run_report.json"

    if not handoff_path.exists() or not macro_path.exists():
        raise ValueError("FreeCAD handoff artifacts are missing. Expected freecad_handoff.json and freecad_handoff.py.")

    executable = find_freecad_binary(executable or freecad_bin)
    if executable is None:
        report = {
            "status": "skipped_missing_freecad",
            "handoff_path": handoff_path.name,
            "macro_path": macro_path.name,
            "output_document": output_document_path.name,
            "message": "FreeCAD is not installed or could not be found.",
        }
        result_path.write_text(json.dumps(report, indent=2))
        return [_report_artifact(result_path, report["status"])]

    run_result = _execute_freecad(
        executable=executable,
        macro_path=macro_path,
        handoff_path=handoff_path,
        output_document_path=output_document_path,
        result_path=result_path,
        timeout_seconds=timeout_seconds,
    )
    artifacts = [_report_artifact(result_path, str(run_result["status"]))]
    if output_document_path.exists():
        artifacts.append(
            PipelineArtifact(
                kind=ArtifactKind.ENGINEERING_MODEL,
                format=ArtifactFormat.FCSTD,
                path=str(output_document_path),
                metadata={
                    "role": ArtifactRole.FREECAD_MODEL.value,
                    "label": "FreeCAD Model",
                    "consumer": "freecad",
                    "status": run_result["status"],
                },
            )
        )
    return artifacts


def _report_artifact(result_path: Path, status: str) -> PipelineArtifact:
    return PipelineArtifact(
        kind=ArtifactKind.ENGINEERING_REPORT,
        format=ArtifactFormat.JSON,
        path=str(result_path),
        metadata={
            "role": ArtifactRole.ENGINEERING_REPORT.value,
            "label": "FreeCAD Run Report",
            "consumer": "freecad",
            "status": status,
        },
    )


def _execute_freecad(
    *,
    executable: str,
    macro_path: Path,
    handoff_path: Path,
    output_document_path: Path,
    result_path: Path,
    timeout_seconds: int,
) -> Dict[str, Any]:
    env = dict(os.environ)
    env["BONSAI_FREECAD_HANDOFF"] = str(handoff_path)
    env["BONSAI_FREECAD_OUTPUT"] = str(output_document_path)
    env["BONSAI_FREECAD_RESULT"] = str(result_path)

    attempts: List[Dict[str, Any]] = []
    for command in _command_variants(executable, macro_path):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                env=env,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            report = {
                "status": "failed_timeout",
                "executable": executable,
                "command": command,
                "handoff_path": handoff_path.name,
                "macro_path": macro_path.name,
                "output_document": output_document_path.name,
                "timeout_seconds": timeout_seconds,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }
            result_path.write_text(json.dumps(report, indent=2))
            return report

        attempts.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if completed.returncode == 0 and output_document_path.exists():
            report = {
                "status": "completed",
                "executable": executable,
                "command": command,
                "handoff_path": handoff_path.name,
                "macro_path": macro_path.name,
                "output_document": output_document_path.name,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "attempts": attempts,
            }
            result_path.write_text(json.dumps(report, indent=2))
            return report

    final_attempt = attempts[-1] if attempts else {}
    report = {
        "status": "failed",
        "executable": executable,
        "handoff_path": handoff_path.name,
        "macro_path": macro_path.name,
        "output_document": output_document_path.name,
        "attempts": attempts,
        "stdout": final_attempt.get("stdout", ""),
        "stderr": final_attempt.get("stderr", ""),
    }
    result_path.write_text(json.dumps(report, indent=2))
    return report


def _command_variants(executable: str, macro_path: Path) -> Iterable[List[str]]:
    executable_name = Path(executable).name.lower()
    if executable_name == "freecadcmd":
        return ([executable, str(macro_path)],)
    return (
        [executable, "-c", str(macro_path)],
        [executable, str(macro_path)],
    )
