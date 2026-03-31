from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _find_view3d_context():
    window = bpy.context.window
    if window is None:
        return None
    area = next((area for area in window.screen.areas if area.type == "VIEW_3D"), None)
    if area is None:
        return None
    region = next((region for region in area.regions if region.type == "WINDOW"), None)
    if region is None:
        return None
    return {"window": window, "screen": window.screen, "area": area, "region": region}


ARGS = None


def _write(payload):
    output_path = Path(ARGS.output_json).resolve()
    output_path.write_text(json.dumps(payload, indent=2))
    bpy.ops.wm.quit_blender()
    return None


def _run():
    addon = bpy.context.preferences.addons.get("bonsai_ai_blender")
    payload = {"addon_enabled": addon is not None}
    if addon is None:
        return _write(payload)

    context_data = _find_view3d_context()
    if context_data is None:
        payload["error"] = "No VIEW_3D context available."
        return _write(payload)

    prompt = Path(ARGS.prompt_file).read_text()
    with bpy.context.temp_override(**context_data):
        try:
            result = bpy.ops.bonsai_ai.quick_prompt(
                "EXEC_DEFAULT",
                prompt_input=prompt,
                docs_input="",
                doc_path="",
                append_docs=False,
                build_now=True,
            )
            settings = bpy.context.scene.bonsai_ai_settings
            payload["operator_result"] = list(result)
            payload["status"] = settings.status
            log_name = settings.log_text_name
            log_raw = bpy.data.texts[log_name].as_string() if log_name in bpy.data.texts else ""
            payload["log_raw"] = log_raw
            try:
                payload["log_json"] = json.loads(log_raw) if log_raw else None
            except json.JSONDecodeError:
                payload["log_json_error"] = "log was not valid JSON"
        except Exception as exc:
            payload["error"] = str(exc)
    return _write(payload)


def main() -> None:
    global ARGS
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output-json", required=True)
    ARGS = parser.parse_args(_script_argv())
    bpy.app.timers.register(_run, first_interval=2.0)


main()
