from __future__ import annotations

import argparse
import json
from typing import Sequence

from .ifc_author import AuthoringError, IfcAuthor
from .planner import DEFAULT_MODELS, DEFAULT_ENV_VARS, create_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt-driven IFC authoring for Bonsai.")
    parser.add_argument("--provider", choices=sorted(DEFAULT_MODELS), default="openai")
    parser.add_argument("--model", help="Override the default model for the selected provider.")
    parser.add_argument("--api-key-env", help="Environment variable that holds the API key.")
    parser.add_argument("--output", required=True, help="Path to the IFC file to create or update.")
    parser.add_argument("--prompt", required=True, help="Natural-language building request.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned tool calls without writing IFC.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    author = IfcAuthor(args.output)
    all_calls = []
    all_results = []
    progress_lines = []
    seen_rounds = set()
    failed_calls = set()
    max_rounds = 12

    for _ in range(max_rounds):
        plan = create_plan(
            provider=args.provider,
            model=args.model,
            api_key_env=args.api_key_env or DEFAULT_ENV_VARS[args.provider],
            user_prompt=args.prompt,
            scene_summary=author.scene_summary(),
            progress_summary="\n".join(progress_lines),
        )
        if not plan.tool_calls:
            break

        round_signature = tuple((call.name, json.dumps(call.arguments, sort_keys=True)) for call in plan.tool_calls)
        if round_signature in seen_rounds:
            raise RuntimeError("Planner repeated a previous round of tool calls before completing the request.")
        seen_rounds.add(round_signature)

        all_calls.extend(plan.tool_calls)
        if args.dry_run:
            progress_lines.extend(
                f"{call.name}: {json.dumps(call.arguments, sort_keys=True)}" for call in plan.tool_calls
            )
            continue

        for call in plan.tool_calls:
            try:
                result = author.apply_tool_call(call.name, call.arguments)
                all_results.append(result)
                progress_lines.append(f"{result.tool_name}: {result.message}")
            except AuthoringError as exc:
                failed_signature = (call.name, json.dumps(call.arguments, sort_keys=True))
                if failed_signature in failed_calls:
                    raise RuntimeError(f"Planner repeated a failing tool call: {call.name} -> {exc}") from exc
                failed_calls.add(failed_signature)
                progress_lines.append(
                    f"FAILED {call.name}: {exc}. Replan from the updated scene summary and avoid this mistake."
                )

    else:
        raise RuntimeError("Planner exceeded the maximum number of rounds.")

    if args.dry_run:
        print(
            json.dumps(
                [{"id": call.id, "name": call.name, "arguments": call.arguments} for call in all_calls],
                indent=2,
            )
        )
        return 0

    author.save()
    for result in all_results:
        print(f"{result.tool_name}: {result.message}")
    print(author.debug_dump())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
