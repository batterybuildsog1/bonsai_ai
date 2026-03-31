"""CLI for testing the planning layer outside Blender."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .planner import build_plan


def _load_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    raise SystemExit("Provide --prompt or --prompt-file.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a Bonsai AI action plan.")
    parser.add_argument("--provider", required=True, choices=("openai", "anthropic", "google"))
    parser.add_argument("--model")
    parser.add_argument("--api-key")
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    args = parser.parse_args(argv)

    plan = build_plan(
        prompt=_load_prompt(args),
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
    )
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
