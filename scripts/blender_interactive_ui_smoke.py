from __future__ import annotations

import json
from pathlib import Path

import bpy


OUTPUT_PATH = Path("/tmp/bonsai_ai_interactive_ui_smoke.json")


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


def _collect_keymap_state():
    key_state = []
    wm = bpy.context.window_manager
    keyconfigs = getattr(wm, "keyconfigs", None)
    addon = getattr(keyconfigs, "addon", None)
    if addon is None:
        return key_state
    for km in addon.keymaps:
        if km.name != "3D View":
            continue
        for item in km.keymap_items:
            if item.idname not in {"bonsai_ai.quick_prompt", "bonsai_ai.open_settings"}:
                continue
            key_state.append(
                {
                    "idname": item.idname,
                    "type": item.type,
                    "value": item.value,
                    "ctrl": bool(item.ctrl),
                    "oskey": bool(item.oskey),
                    "shift": bool(item.shift),
                }
            )
    return key_state


def _write(payload):
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))
    bpy.ops.wm.quit_blender()
    return None


def _invoke_test():
    if bpy.context.preferences.addons.get("bonsai_ai_blender") is None:
        bpy.ops.preferences.addon_enable(module="bonsai_ai_blender")

    context_data = _find_view3d_context()
    payload = {
        "addon_enabled": bpy.context.preferences.addons.get("bonsai_ai_blender") is not None,
        "keymaps": _collect_keymap_state(),
    }
    if context_data is None:
        payload["error"] = "No VIEW_3D context available."
        return _write(payload)

    with bpy.context.temp_override(**context_data):
        try:
            result = bpy.ops.bonsai_ai.quick_prompt("INVOKE_DEFAULT")
            payload["invoke_result"] = list(result)
        except Exception as exc:
            payload["invoke_error"] = str(exc)
            return _write(payload)

    def finalize():
        payload["operators"] = [op.bl_idname for op in bpy.context.window_manager.operators]
        payload["quick_prompt_running"] = any(op.bl_idname == "BONSAI_AI_OT_quick_prompt" for op in bpy.context.window_manager.operators)
        return _write(payload)

    bpy.app.timers.register(finalize, first_interval=1.0)
    return None


bpy.app.timers.register(_invoke_test, first_interval=5.0)
