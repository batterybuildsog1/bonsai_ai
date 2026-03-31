from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bonsai_ai.ifc_author import AuthoringError, IfcAuthor
from bonsai_ai.planner import create_plan


PROMPT = """Create a small one-storey office shell in meters.
- 8m x 12m slab at z=0 on Level 0
- perimeter walls 3m high and 0.2m thick
- one interior partition wall running east-west through the middle
When complete, stop.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    api_key = sys.stdin.read().strip()
    if not api_key:
        raise RuntimeError("Expected API key on stdin.")

    author = IfcAuthor(args.output)
    progress_lines: list[str] = []
    all_results = []
    for _ in range(12):
        plan = create_plan(
            provider=args.provider,
            model=args.model,
            api_key=api_key,
            user_prompt=PROMPT,
            scene_summary=author.scene_summary(),
            progress_summary="\n".join(progress_lines),
        )
        if not plan.tool_calls:
            break
        for call in plan.tool_calls:
            try:
                result = author.apply_tool_call(call.name, call.arguments)
                all_results.append(result)
                progress_lines.append(f"{result.tool_name}: {result.message}")
            except AuthoringError as exc:
                progress_lines.append(f"FAILED {call.name}: {exc}")
    else:
        raise RuntimeError("Planner exceeded the maximum number of rounds.")

    author.save()
    print(
        json.dumps(
            {
                "output_ifc": str(Path(args.output).resolve()),
                "created": [result.element_name for result in all_results],
                "debug_dump": json.loads(author.debug_dump()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
