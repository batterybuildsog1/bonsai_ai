from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

from bonsai_ai_blender.integration import BonsaiAIExecutor


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(_script_argv())

    bpy.ops.preferences.addon_enable(module="bonsai_ai_blender")

    plan_path = Path(args.plan).resolve()
    output_path = Path(args.output).resolve()
    plan = json.loads(plan_path.read_text())

    result = BonsaiAIExecutor(auto_create_project=True).execute_plan(plan)
    _require(result["created"], "No BIM objects were created")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_result = bpy.ops.bim.save_project(filepath=str(output_path))
    _require("FINISHED" in export_result, f"IFC export failed: {export_result}")

    print(
        json.dumps(
            {
                "summary": plan.get("summary"),
                "assumptions": plan.get("assumptions", []),
                "created": result["created"],
                "output_ifc": str(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
