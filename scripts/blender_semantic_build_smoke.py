from __future__ import annotations

import json
from pathlib import Path

import bpy


OUTPUT_JSON = Path("/tmp/bonsai_ai_semantic_build_smoke.json")
ARTIFACT_DIR = Path.home() / "Downloads" / "bonsai_ai_bridge" / "semantic_build_smoke"

SEMANTIC_PLAN = {
    "version": "1.0",
    "units": "meters",
    "summary": "Semantic stair and steel detail smoke test.",
    "assumptions": ["This is an offline semantic-plan build smoke test."],
    "actions": [
        {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
        {
            "type": "create_column",
            "name": "Column A",
            "storey": "Level 0",
            "x": 0.0,
            "y": 0.0,
            "base_z": 0.0,
            "width": 0.3,
            "depth": 0.3,
            "height": 4.0,
        },
        {
            "type": "create_beam",
            "name": "Beam A",
            "storey": "Level 0",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 6.0,
            "y2": 0.0,
            "base_z": 3.6,
            "width": 0.25,
            "depth": 0.4,
        },
        {
            "type": "create_stair_run",
            "name": "East Stair",
            "storey": "Level 0",
            "x": 8.0,
            "y": 0.0,
            "base_z": 0.0,
            "width": 1.2,
            "tread_depth": 0.28,
            "riser_height": 0.175,
            "step_count": 6,
            "thickness": 0.08,
            "direction_deg": 90.0,
        },
        {
            "type": "create_stair_landing",
            "name": "East Stair Landing",
            "storey": "Level 0",
            "x": 8.0,
            "y": 1.68,
            "base_z": 1.05,
            "width": 1.2,
            "depth": 1.2,
            "thickness": 0.08,
            "direction_deg": 90.0,
        },
        {
            "type": "create_connection_plate",
            "name": "Beam Plate",
            "storey": "Level 0",
            "center_x": 0.0,
            "center_y": 0.0,
            "base_z": 3.9,
            "width": 0.35,
            "depth": 0.35,
            "thickness": 0.02,
        },
    ],
}


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
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2))
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
            settings = bpy.context.scene.bonsai_ai_settings
            settings.artifact_download_dir = str(ARTIFACT_DIR)
            plan_text = bpy.data.texts.get(settings.plan_text_name) or bpy.data.texts.new(settings.plan_text_name)
            plan_text.clear()
            plan_text.write(json.dumps(SEMANTIC_PLAN, indent=2))

            result = bpy.ops.bonsai_ai.apply_plan("EXEC_DEFAULT")
            payload["operator_result"] = list(result)
            payload["status"] = settings.status
            log_name = settings.log_text_name
            payload["log_excerpt"] = bpy.data.texts[log_name].as_string()[:3000] if log_name in bpy.data.texts else ""
            payload["output_ifc"] = str(ARTIFACT_DIR / "bonsai_ai_live.ifc")
        except Exception as exc:
            payload["error"] = str(exc)
    return _write(payload)


bpy.app.timers.register(_run, first_interval=2.0)
