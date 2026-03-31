from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


PROMPT = """Create a simple single-storey office shell in meters.
- 8m x 12m slab at z=0
- perimeter walls 3m high and 0.2m thick
- one interior partition wall centered along the short dimension
Use supported BIM primitives only and give every action a stable name.
"""


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _ensure_text_block(name: str, content: str) -> None:
    text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    text.clear()
    text.write(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(_script_argv())

    if bpy.context.preferences.addons.get("bonsai_ai_blender") is None:
        bpy.ops.preferences.addon_enable(module="bonsai_ai_blender")

    addon = bpy.context.preferences.addons.get("bonsai_ai_blender")
    if addon is None:
        raise RuntimeError("bonsai_ai_blender is not enabled in Blender preferences.")
    prefs = addon.preferences

    scene = bpy.context.scene
    settings = scene.bonsai_ai_settings
    settings.provider = prefs.provider
    settings.model = prefs.model
    settings.auto_create_project = prefs.auto_create_project
    settings.include_docs_context = False

    _ensure_text_block(settings.prompt_text_name, PROMPT)
    _ensure_text_block(settings.docs_text_name, "")

    result = bpy.ops.bonsai_ai.plan(execute_build=True)
    if "FINISHED" not in result:
        raise RuntimeError(f"bonsai_ai.plan failed: {result}")

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_result = bpy.ops.bim.save_project(filepath=str(output_path))
    if "FINISHED" not in export_result:
        raise RuntimeError(f"IFC export failed: {export_result}")

    print(
        json.dumps(
            {
                "provider": prefs.provider,
                "model": prefs.model,
                "status": settings.status,
                "output_ifc": str(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
