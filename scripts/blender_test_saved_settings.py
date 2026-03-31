from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bonsai_ai_blender.integration import BonsaiAIExecutor
from bonsai_ai_blender.runtime import load_core


PROMPT = """Create a simple single-storey office shell in meters.
- 8m x 12m slab at z=0
- perimeter walls 3m high and 0.2m thick
- one interior partition wall centered along the short dimension
Use supported BIM primitives only and give every action a stable name.
"""


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _api_key_from_preferences(prefs) -> str:
    provider = getattr(prefs, "provider", "openai")
    if provider == "openai":
        return getattr(prefs, "openai_api_key", "").strip()
    if provider == "anthropic":
        return getattr(prefs, "anthropic_api_key", "").strip()
    return getattr(prefs, "google_api_key", "").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(_script_argv())

    addon = bpy.context.preferences.addons.get("bonsai_ai_blender")
    if addon is None:
        raise RuntimeError("bonsai_ai_blender is not enabled in Blender preferences.")
    prefs = addon.preferences
    api_key = _api_key_from_preferences(prefs)
    if not api_key:
        raise RuntimeError(f"No saved API key found for provider '{prefs.provider}'.")

    ai_core = load_core()
    plan = ai_core.build_plan(
        prompt=PROMPT,
        provider=prefs.provider,
        model=prefs.model.strip() or None,
        api_key=api_key,
        reasoning_effort=prefs.openai_reasoning_effort if prefs.provider == "openai" else None,
        service_tier=prefs.openai_service_tier if prefs.provider == "openai" else None,
    )
    result = BonsaiAIExecutor(auto_create_project=prefs.auto_create_project).execute_plan(plan)
    if not result["created"]:
        raise RuntimeError("No BIM objects were created by the smoke test.")

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
                "summary": plan.get("summary"),
                "actions": len(plan.get("actions", [])),
                "created": result["created"],
                "output_ifc": str(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
