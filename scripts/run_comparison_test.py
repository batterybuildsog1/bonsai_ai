"""Run a building prompt through the direct planner and produce comparison artifacts.

Usage:
    python3 scripts/run_comparison_test.py \
        --provider openai --model gpt-5.4 \
        --output out/test_gpt54/ \
        --prompt "Design a 5-story commercial building ..."

    python3 scripts/run_comparison_test.py \
        --provider anthropic --model claude-opus-4-6 \
        --output out/test_opus/ \
        --prompt "..."

Auth: Uses OPENAI_API_KEY / ANTHROPIC_API_KEY env vars. If not set,
attempts to extract from OpenClaw's auth-profiles.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bonsai_ai.ifc_author import AuthoringError, IfcAuthor
from bonsai_ai.planner import (
    DEFAULT_ENV_VARS,
    DEFAULT_MODELS,
    PlannerError,
    PlannedToolCall,
    create_plan,
)

# ───────────────────────── Default test prompt ────────────────────────────

DEFAULT_PROMPT = """\
Design a 5-story commercial building:
- 40m x 25m footprint, 8m structural grid (5 bays x 3 bays)
- Ground floor 4.5m (retail), upper floors 4.0m each
- Steel columns (0.3x0.3m) at all grid intersections
- Steel beams (0.3x0.5m) spanning between columns at each level
- Concrete slabs (0.2m) at each level, origin at (0,0)
- East/west/north: concrete walls (0.2m) with punched windows (1.8x1.5m, sill 0.9m)
- South ground: glass curtain wall (1.5x4.0m panels)
- South upper: concrete wall with windows
- Mezzanines at floors 3-4: east/west sides, 10m deep
- Main entrance: south facade double door (2.4x2.8m)
- Service door: north facade (1.2x2.4m)
"""

# ───────────────────── API key resolution ─────────────────────────────────

OPENCLAW_AUTH_PATHS = [
    Path.home() / ".openclaw/agents/bim_operator/agent/auth-profiles.json",
    Path.home() / ".openclaw/agents/main/agent/auth-profiles.json",
]


def _extract_openclaw_key(provider: str) -> str | None:
    """Try to read the API key from OpenClaw's auth-profiles.json."""
    profile_key = f"{provider}:default"
    for path in OPENCLAW_AUTH_PATHS:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            profiles = data.get("profiles", {})
            profile = profiles.get(profile_key, {})
            key = profile.get("key")
            if key:
                print(f"[auth] Loaded {provider} key from {path}")
                return key
        except Exception:
            continue
    return None


def resolve_api_key(provider: str) -> str:
    """Resolve the API key from env vars or OpenClaw auth-profiles."""
    env_var = DEFAULT_ENV_VARS.get(provider)
    if env_var:
        value = os.environ.get(env_var)
        if value:
            print(f"[auth] Using {provider} key from ${env_var}")
            return value

    key = _extract_openclaw_key(provider)
    if key:
        return key

    raise RuntimeError(
        f"No API key found for provider '{provider}'. "
        f"Set ${env_var} or add an openai:default profile to "
        f"~/.openclaw/agents/bim_operator/agent/auth-profiles.json"
    )


# ───────────────────── Plan + Execute loop ────────────────────────────────

MAX_ROUNDS = 12


def run_building_test(
    provider: str,
    model: str,
    api_key: str,
    prompt: str,
    output_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Run the direct planner loop and save all artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    ifc_path = output_dir / "building.ifc"
    plan_path = output_dir / "plan.json"
    log_path = output_dir / "build_log.txt"

    author = IfcAuthor(str(ifc_path))
    all_calls: list[dict] = []
    all_results = []
    progress_lines: list[str] = []
    log_lines: list[str] = []
    seen_rounds: set = set()
    failed_calls: set = set()
    element_types: Counter = Counter()
    error_count = 0

    start_time = time.time()
    log_lines.append(f"Provider: {provider}")
    log_lines.append(f"Model: {model}")
    log_lines.append(f"Prompt: {prompt[:200]}...")
    log_lines.append(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append("")

    for round_num in range(MAX_ROUNDS):
        log_lines.append(f"--- Round {round_num + 1} ---")
        round_start = time.time()

        try:
            plan = create_plan(
                provider=provider,
                model=model,
                api_key=api_key,
                user_prompt=prompt,
                scene_summary=author.scene_summary(),
                progress_summary="\n".join(progress_lines),
            )
        except PlannerError as exc:
            log_lines.append(f"PLANNER ERROR: {exc}")
            error_count += 1
            break

        round_elapsed = time.time() - round_start
        log_lines.append(f"Planning took {round_elapsed:.1f}s, got {len(plan.tool_calls)} tool calls")

        if not plan.tool_calls:
            log_lines.append("No tool calls returned - planner considers work complete.")
            break

        # Duplicate round detection
        round_signature = tuple(
            (call.name, json.dumps(call.arguments, sort_keys=True))
            for call in plan.tool_calls
        )
        if round_signature in seen_rounds:
            log_lines.append("ERROR: Planner repeated a previous round, aborting.")
            error_count += 1
            break
        seen_rounds.add(round_signature)

        # Record planned calls
        for call in plan.tool_calls:
            all_calls.append({
                "round": round_num + 1,
                "id": call.id,
                "name": call.name,
                "arguments": call.arguments,
            })

        if dry_run:
            for call in plan.tool_calls:
                msg = f"[dry-run] {call.name}: {json.dumps(call.arguments, sort_keys=True)}"
                progress_lines.append(msg)
                log_lines.append(msg)
            continue

        # Execute
        for call in plan.tool_calls:
            try:
                result = author.apply_tool_call(call.name, call.arguments)
                all_results.append(result)
                progress_lines.append(f"{result.tool_name}: {result.message}")
                log_lines.append(f"  OK {result.tool_name}: {result.message}")
                if result.ifc_class:
                    element_types[result.ifc_class] += 1
            except AuthoringError as exc:
                error_msg = str(exc)
                error_count += 1
                failed_sig = (call.name, json.dumps(call.arguments, sort_keys=True))
                if failed_sig in failed_calls:
                    log_lines.append(f"  REPEATED FAILURE {call.name}: {exc}")
                    break
                failed_calls.add(failed_sig)
                progress_lines.append(
                    f"FAILED {call.name}: {exc}. "
                    "Replan from the updated scene summary and avoid this mistake."
                )
                log_lines.append(f"  FAIL {call.name}: {exc}")
    else:
        log_lines.append("WARNING: Reached maximum rounds without completion.")

    elapsed = time.time() - start_time

    # Save IFC
    if not dry_run:
        author.save()

    # Save plan.json
    plan_data = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "tool_calls": all_calls,
        "total_actions": len(all_calls),
        "errors": error_count,
        "elapsed_seconds": round(elapsed, 1),
        "element_types": dict(element_types),
    }
    plan_path.write_text(json.dumps(plan_data, indent=2))

    # Save build log
    log_lines.append("")
    log_lines.append(f"Elapsed: {elapsed:.1f}s")
    log_lines.append(f"Total tool calls: {len(all_calls)}")
    log_lines.append(f"Errors: {error_count}")
    log_lines.append(f"Element types: {dict(element_types)}")
    if not dry_run:
        log_lines.append(f"IFC file: {ifc_path.resolve()}")
        try:
            log_lines.append("")
            log_lines.append("Debug dump:")
            log_lines.append(author.debug_dump())
        except Exception:
            pass
    log_path.write_text("\n".join(log_lines))

    # Summary
    summary = {
        "provider": provider,
        "model": model,
        "output_dir": str(output_dir.resolve()),
        "ifc_file": str(ifc_path.resolve()),
        "total_actions": len(all_calls),
        "errors": error_count,
        "elapsed_seconds": round(elapsed, 1),
        "element_types": dict(element_types),
    }
    return summary


# ───────────────────── CLI ────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a building prompt through the direct planner for model comparison testing."
    )
    parser.add_argument(
        "--provider",
        choices=sorted(DEFAULT_MODELS),
        default="openai",
        help="LLM provider (default: openai).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (default: provider default from defaults.py).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for artifacts (plan.json, build_log.txt, building.ifc).",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Building prompt. Defaults to the 5-story commercial building test prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only, do not execute tool calls or write IFC.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    provider = args.provider
    model = args.model or DEFAULT_MODELS[provider]
    prompt = args.prompt or DEFAULT_PROMPT
    output_dir = Path(args.output)
    dry_run = args.dry_run

    print(f"=== Comparison Test: {provider}/{model} ===")
    print(f"Output: {output_dir.resolve()}")
    print()

    api_key = resolve_api_key(provider)

    summary = run_building_test(
        provider=provider,
        model=model,
        api_key=api_key,
        prompt=prompt,
        output_dir=output_dir,
        dry_run=dry_run,
    )

    print()
    print("=== Results ===")
    print(f"Provider:       {summary['provider']}")
    print(f"Model:          {summary['model']}")
    print(f"Total actions:  {summary['total_actions']}")
    print(f"Errors:         {summary['errors']}")
    print(f"Elapsed:        {summary['elapsed_seconds']}s")
    print(f"Element types:  {summary['element_types']}")
    print(f"Output dir:     {summary['output_dir']}")
    if not dry_run:
        print(f"IFC file:       {summary['ifc_file']}")
    print()

    return 1 if summary["errors"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
