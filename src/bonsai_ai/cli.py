from __future__ import annotations

import argparse
import json
from typing import Dict, List, Sequence, Tuple

from .ifc_author import AuthoringError, IfcAuthor
from .planner import DEFAULT_MODELS, DEFAULT_ENV_VARS, PlannerError, PlannedToolCall, create_plan
from .openclaw_planner import create_plan_via_openclaw
from .phased_planner import create_phased_plan_via_openclaw


# ---------------------------------------------------------------------------
# Failure classification for smart replanning
# ---------------------------------------------------------------------------

# Keywords in error messages that indicate a structural / hierarchy problem.
# These failures cannot be repaired in isolation -- they require a full replan
# so the planner can reconsider the project structure.
_STRUCTURAL_FAILURE_KEYWORDS = (
    "storey",
    "project",
    "hierarchy",
    "IfcProject",
    "IfcBuildingStorey",
    "IfcBuilding",
    "IfcSite",
    "no site",
    "no building",
)


def _is_structural_failure(error_message: str) -> bool:
    """Return True if the error indicates a structural/hierarchy problem
    that cannot be repaired by a targeted fix and needs a full replan."""
    lower = error_message.lower()
    return any(kw.lower() in lower for kw in _STRUCTURAL_FAILURE_KEYWORDS)


def _build_repair_prompt(
    succeeded: List[Tuple[PlannedToolCall, str]],
    failed: List[Tuple[PlannedToolCall, str]],
    scene_summary: str,
) -> str:
    """Build a targeted repair prompt that asks the planner to fix ONLY the
    failed tool calls without re-creating elements that already exist."""
    parts: List[str] = []

    # Describe what failed and why
    parts.append("The following tool calls failed and need repair:")
    for call, error in failed:
        parts.append(
            f"  - {call.name}({json.dumps(call.arguments, sort_keys=True)}): {error}"
        )

    # Describe what already succeeded (so the planner does not duplicate)
    if succeeded:
        parts.append("")
        parts.append("The following tool calls succeeded -- do NOT recreate these elements:")
        for call, msg in succeeded:
            parts.append(f"  - {call.name}: {msg}")

    # Current scene state
    parts.append("")
    parts.append(f"The scene already contains:\n{scene_summary}")

    # Clear instruction
    parts.append("")
    parts.append(
        "Fix ONLY the failures listed above. Use corrected coordinates, "
        "dimensions, or names as needed. Do not recreate existing elements."
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt-driven IFC authoring for Bonsai.")
    parser.add_argument("--provider", choices=sorted(DEFAULT_MODELS), default="openai")
    parser.add_argument("--model", help="Override the default model for the selected provider.")
    parser.add_argument("--api-key-env", help="Environment variable that holds the API key.")
    parser.add_argument("--output", required=True, help="Path to the IFC file to create or update.")
    parser.add_argument("--prompt", required=True, help="Natural-language building request.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned tool calls without writing IFC.")
    parser.add_argument(
        "--via-openclaw",
        action="store_true",
        help="Route model calls through OpenClaw agent (uses subscription auth instead of API keys).",
    )
    parser.add_argument(
        "--single-phase",
        action="store_true",
        help="Use single-shot planner instead of phased plan-then-execute (only with --via-openclaw).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    use_openclaw = getattr(args, "via_openclaw", False)
    use_single_phase = getattr(args, "single_phase", False)

    # -----------------------------------------------------------------------
    # Phased planner path — default when --via-openclaw is set.
    # The phased planner handles its own plan-then-execute loop internally
    # because it refreshes the scene summary between phases.
    # -----------------------------------------------------------------------
    if use_openclaw and not use_single_phase:
        try:
            summary = create_phased_plan_via_openclaw(
                user_prompt=args.prompt,
                output_path=args.output,
                dry_run=args.dry_run,
            )
        except PlannerError as exc:
            # If a direct-API provider is also configured, fall back to it
            if getattr(args, "provider", None):
                print(f"[phased] Phased planner failed: {exc}")
                print("[phased] Falling back to single-phase direct API...")
                # Fall through to the legacy loop below
            else:
                raise
        else:
            if args.dry_run:
                print(json.dumps(summary, indent=2))
            return 0

    # -----------------------------------------------------------------------
    # Legacy single-phase loop (direct API or --single-phase --via-openclaw)
    # -----------------------------------------------------------------------
    author = IfcAuthor(args.output)
    all_calls: List[PlannedToolCall] = []
    all_results = []
    progress_lines: List[str] = []
    seen_rounds: set = set()
    failed_calls: set = set()
    max_rounds = 12

    # Helper: call the right planner backend based on --via-openclaw flag.
    def _do_plan(user_prompt: str, scene_summary: str, progress_summary: str):
        if use_openclaw:
            try:
                return create_plan_via_openclaw(
                    user_prompt=user_prompt,
                    scene_summary=scene_summary,
                    progress_summary=progress_summary,
                )
            except PlannerError:
                # If --provider is also set, fall back to direct API
                if getattr(args, "provider", None):
                    print("[openclaw] OpenClaw failed, falling back to direct API...")
                    return create_plan(
                        provider=args.provider,
                        model=args.model,
                        api_key_env=args.api_key_env or DEFAULT_ENV_VARS[args.provider],
                        user_prompt=user_prompt,
                        scene_summary=scene_summary,
                        progress_summary=progress_summary,
                    )
                raise
        return create_plan(
            provider=args.provider,
            model=args.model,
            api_key_env=args.api_key_env or DEFAULT_ENV_VARS[args.provider],
            user_prompt=user_prompt,
            scene_summary=scene_summary,
            progress_summary=progress_summary,
        )

    # Track per-element repair attempts.  Key = (tool_name, element_name_or_sig).
    # If an element fails targeted repair twice, we escalate to full replan.
    repair_attempt_counts: Dict[str, int] = {}

    # After executing a round, this may be set to a targeted repair prompt
    # that should be used *instead of* the full user prompt on the next
    # iteration.  It is consumed (reset to None) once used.
    pending_repair_prompt: str | None = None

    # True once at least one failure has occurred (used to decide whether to
    # annotate progress_lines with REPLAN markers).
    any_failure_seen = False

    for round_num in range(max_rounds):
        # ------------------------------------------------------------------
        # Plan: either a targeted repair or a full (re)plan
        # ------------------------------------------------------------------
        if pending_repair_prompt is not None:
            # REPAIR round -- send a focused prompt
            repair_prompt = pending_repair_prompt
            pending_repair_prompt = None  # consume it

            progress_lines.append(f"REPAIR: attempting targeted repair (round {round_num + 1})")

            plan = _do_plan(
                user_prompt=repair_prompt,
                scene_summary=author.scene_summary(),
                progress_summary="\n".join(progress_lines),
            )
        else:
            # FULL (re)plan -- the normal path
            if round_num > 0 and any_failure_seen:
                # Log that we are doing a full replan (only after failures --
                # in the zero-failure case the progress_lines stay identical
                # to the original behaviour).
                progress_lines.append(f"REPLAN: full round {round_num + 1}")

            plan = _do_plan(
                user_prompt=args.prompt,
                scene_summary=author.scene_summary(),
                progress_summary="\n".join(progress_lines),
            )

        if not plan.tool_calls:
            break

        round_signature = tuple(
            (call.name, json.dumps(call.arguments, sort_keys=True))
            for call in plan.tool_calls
        )
        if round_signature in seen_rounds:
            raise RuntimeError(
                "Planner repeated a previous round of tool calls before completing the request."
            )
        seen_rounds.add(round_signature)

        all_calls.extend(plan.tool_calls)
        if args.dry_run:
            progress_lines.extend(
                f"{call.name}: {json.dumps(call.arguments, sort_keys=True)}"
                for call in plan.tool_calls
            )
            continue

        # ------------------------------------------------------------------
        # Execute the tool calls, tracking successes and failures
        # ------------------------------------------------------------------
        succeeded: List[Tuple[PlannedToolCall, str]] = []
        failed_this_round: List[Tuple[PlannedToolCall, str]] = []
        has_structural_failure = False

        for call in plan.tool_calls:
            try:
                result = author.apply_tool_call(call.name, call.arguments)
                all_results.append(result)
                progress_lines.append(f"{result.tool_name}: {result.message}")
                succeeded.append((call, result.message))
            except AuthoringError as exc:
                error_msg = str(exc)
                failed_signature = (call.name, json.dumps(call.arguments, sort_keys=True))
                if failed_signature in failed_calls:
                    raise RuntimeError(
                        f"Planner repeated a failing tool call: {call.name} -> {exc}"
                    ) from exc
                failed_calls.add(failed_signature)

                if _is_structural_failure(error_msg):
                    has_structural_failure = True

                failed_this_round.append((call, error_msg))
                progress_lines.append(
                    f"FAILED {call.name}: {exc}. "
                    "Replan from the updated scene summary and avoid this mistake."
                )

        # ------------------------------------------------------------------
        # Smart replanning decision
        # ------------------------------------------------------------------
        if failed_this_round:
            any_failure_seen = True
            # Decide: targeted repair or full replan?
            #
            # Escalate to full replan when:
            #   1. Any failure is structural (hierarchy problem)
            #   2. ALL calls in the round failed (nothing to anchor the repair)
            #   3. Any element has already been repaired twice (stuck in a loop)
            should_full_replan = has_structural_failure or not succeeded

            if not should_full_replan:
                # Check per-element repair attempt limits
                for call, _error in failed_this_round:
                    element_key = call.arguments.get("name", json.dumps(call.arguments, sort_keys=True))
                    repair_key = f"{call.name}:{element_key}"
                    count = repair_attempt_counts.get(repair_key, 0)
                    if count >= 2:
                        # This element has failed repair twice -- escalate
                        should_full_replan = True
                        progress_lines.append(
                            f"REPAIR ESCALATION: {repair_key} failed repair {count} time(s), "
                            "escalating to full replan"
                        )
                        break
                    repair_attempt_counts[repair_key] = count + 1

            if should_full_replan:
                # Fall through to next iteration which will do a full replan
                # (pending_repair_prompt is already None)
                if has_structural_failure:
                    progress_lines.append(
                        "REPLAN REASON: structural/hierarchy failure detected, "
                        "skipping targeted repair"
                    )
                elif not succeeded:
                    progress_lines.append(
                        "REPLAN REASON: all tool calls in the round failed, "
                        "skipping targeted repair"
                    )
            else:
                # Set up a targeted repair for the next iteration
                pending_repair_prompt = _build_repair_prompt(
                    succeeded=succeeded,
                    failed=failed_this_round,
                    scene_summary=author.scene_summary(),
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
