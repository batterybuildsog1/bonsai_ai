from __future__ import annotations

import argparse
import json
import shutil
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


def _write(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    bpy.ops.wm.quit_blender()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--ifc-out")
    args = parser.parse_args(_script_argv())

    prompt = Path(args.prompt_file).read_text()
    json_out = Path(args.json_out).resolve()
    ifc_out = Path(args.ifc_out).resolve() if args.ifc_out else None

    def run():
        payload: dict[str, object] = {"addon_enabled": bpy.context.preferences.addons.get("bonsai_ai_blender") is not None}
        context_data = _find_view3d_context()
        if context_data is None:
            payload["error"] = "No VIEW_3D context available."
            _write(json_out, payload)
            return None

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
                payload["operator_result"] = list(result)
                settings = bpy.context.scene.bonsai_ai_settings
                payload["status"] = settings.status
                log_name = settings.log_text_name
                log_text = bpy.data.texts[log_name].as_string() if log_name in bpy.data.texts else ""
                payload["log"] = log_text
                try:
                    log_json = json.loads(log_text) if log_text else {}
                except json.JSONDecodeError:
                    log_json = {}
                payload["log_json"] = log_json
                output_ifc = log_json.get("output_ifc")
                payload["output_ifc"] = output_ifc
                if output_ifc and ifc_out:
                    ifc_out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(output_ifc, ifc_out)
                    payload["copied_ifc"] = str(ifc_out)
            except Exception as exc:
                payload["error"] = str(exc)
        _write(json_out, payload)
        return None

    bpy.app.timers.register(run, first_interval=2.0)


if __name__ == "__main__":
    main()
