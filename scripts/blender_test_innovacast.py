from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import bpy

from bonsai_ai_blender.integration import BonsaiAIExecutor
from bonsai_ai_blender.runtime import load_core


PROMPT = """Create a single precast insulated cladding wall section based on the attached InnovaCast engineering reports.

Model intent:
- one vertical wall panel assembly only
- use a conservative engineering representation of the tested panel, not unsupported hidden internals
- create a panel that is 4 feet wide and 16.58 feet tall
- overall thickness 7.5 inches
- represent the two concrete wythes as 2.25 inch outer layers and note the 3 inch foam core in assumptions
- base elevation 0
- place the panel along the X axis starting at world origin
- use supported BIM primitives only

Engineering characteristics to preserve in the plan assumptions and summary:
- tested as an InnovaCast precast insulated cladding panel
- 24 inch hanger spacing
- minimum 4000 psi concrete
- top fastener spacing 24 inches
- designed vertical support interval 16.58 feet max
- use the Cedar City Utah report values as the governing basis

If internal reinforcement, ties, or anchors cannot be modeled with the available action schema, state that explicitly in assumptions while still creating the closest supported BIM representation.
"""

DOCS = """Source summary for InnovaCast cladding panel test

- Subject panel: 7.5 in total thickness consisting of 2.25 in concrete / 3 in foam core / 2.25 in concrete.
- Design basis location: Cedar City, Utah.
- Max vertical support span between girts: 16.58 ft governing.
- Typical panel width in axial tests: 4 ft.
- Steel hanger connectors: typically at 24 in intervals.
- Concrete strength basis: minimum 4000 psi.
- Fastener basis: 3/8 in x 3 in Tapcon+ anchor, recommended top spacing 24 in.
- Reinforcement basis: WWR plain wire, #4 wire (W4.0), 6 in spacing from report capacity sheets.
- The tested behavior depends on partial composite action and should not be extrapolated casually.
"""


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _build_prompt() -> str:
    return (
        f"{PROMPT}\n\n"
        "Reference document context:\n"
        f"{DOCS}\n\n"
        "Use the reference document to extract dimensions, engineering constraints, and design assumptions. "
        "If an engineering characteristic cannot be represented in geometry, keep it in assumptions."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    args = parser.parse_args(_script_argv())

    api_key = os.getenv(args.api_key_env)
    _require(bool(api_key), f"{args.api_key_env} is not set")

    ai_core = load_core()
    plan = ai_core.build_plan(
        prompt=_build_prompt(),
        provider=args.provider,
        model=args.model,
        api_key=api_key,
        reasoning_effort="high",
        service_tier="priority",
    )

    result = BonsaiAIExecutor(auto_create_project=True).execute_plan(plan)
    _require(result["created"], "No BIM objects were created")

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_result = bpy.ops.bim.save_project(filepath=str(output_path))
    _require("FINISHED" in export_result, f"IFC export failed: {export_result}")

    print(
        json.dumps(
            {
                "plan_summary": plan.get("summary"),
                "assumptions": plan.get("assumptions", []),
                "actions": plan.get("actions", []),
                "created": result["created"],
                "output_ifc": str(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
