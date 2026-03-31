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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--ifc-out")
    args = parser.parse_args(_script_argv())

    plan = Path(args.plan_json).read_text()
    json_out = Path(args.json_out).resolve()
    ifc_out = Path(args.ifc_out).resolve() if args.ifc_out else None

    def _write(payload: dict) -> None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, indent=2))
        bpy.ops.wm.quit_blender()

    def _run():
        payload: dict[str, object] = {"addon_enabled": bpy.context.preferences.addons.get("bonsai_ai_blender") is not None}
        context_data = _find_view3d_context()
        if context_data is None:
            payload["error"] = "No VIEW_3D context available."
            _write(payload)
            return None

        with bpy.context.temp_override(**context_data):
            try:
                settings = bpy.context.scene.bonsai_ai_settings
                settings.artifact_download_dir = str(Path("/tmp") / "bonsai_ai_semantic_apply")
                plan_block = bpy.data.texts.get(settings.plan_text_name) or bpy.data.texts.new(settings.plan_text_name)
                plan_block.clear()
                plan_block.write(plan)
                result = bpy.ops.bonsai_ai.apply_plan("EXEC_DEFAULT")
                payload["operator_result"] = list(result)
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
        _write(payload)
        return None

    bpy.app.timers.register(_run, first_interval=2.0)


if __name__ == "__main__":
    main()
