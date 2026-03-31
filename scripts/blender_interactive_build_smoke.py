from __future__ import annotations

import json
from pathlib import Path

import bpy


OUTPUT_PATH = Path("/tmp/bonsai_ai_interactive_build_smoke.json")
PROMPT = """Create a simple one-storey room in meters.
- ensure storey Level 0 at elevation 0
- create one 6m x 8m slab at z=0
- create four perimeter walls with base_z 0, height 3, thickness 0.2
Return valid numeric coordinates for every wall.
"""


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


def _write(payload):
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))
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

    with bpy.context.temp_override(**context_data):
        try:
            result = bpy.ops.bonsai_ai.quick_prompt(
                "EXEC_DEFAULT",
                prompt_input=PROMPT,
                docs_input="",
                doc_path="",
                append_docs=False,
                build_now=True,
            )
            payload["operator_result"] = list(result)
            payload["status"] = bpy.context.scene.bonsai_ai_settings.status
            log_name = bpy.context.scene.bonsai_ai_settings.log_text_name
            payload["log_excerpt"] = bpy.data.texts[log_name].as_string()[:1000] if log_name in bpy.data.texts else ""
        except Exception as exc:
            payload["error"] = str(exc)
    return _write(payload)


bpy.app.timers.register(_run, first_interval=2.0)
