"""Plan-then-execute architecture for building generation via OpenClaw.

Splits building generation into two stages:
  Phase 1 (plan):   Decompose the building into subsystem phases (~600 char prompt)
  Phase 2 (execute): For each phase, generate focused BIM actions (~800-1400 char prompt)

Each OpenClaw subprocess call uses a small, focused prompt. The scene summary is
refreshed between phases so the model sees what previous phases built.
"""

from __future__ import annotations

import json
import re
import subprocess
import shutil
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from bonsai_ai_core import compile_plan as compile_core_plan
except ModuleNotFoundError:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from bonsai_ai_core import compile_plan as compile_core_plan

from .ifc_author import AuthoringError, IfcAuthor
from .planner import PlannerError, PlanResult, PlannedToolCall, _to_tool_call

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PHASE_TIMEOUT = 180  # seconds per phase — single phase should be fast
_PLAN_TIMEOUT = 120   # seconds for the high-level decomposition

# Action types allowed per phase category.  Used to build the constraint
# instruction in each per-phase prompt.
_PHASE_ACTION_TYPES: Dict[str, List[str]] = {
    "storeys": [
        "ensure_storey",
    ],
    "structure": [
        "generate_column_grid",
        "create_column",
        "create_beam",
        "generate_floor_plate",
        "create_rectangular_slab",
    ],
    "mezzanines": [
        "create_rectangular_slab",
        "create_column",
        "create_beam",
    ],
    "envelope": [
        "create_wall",
        "generate_perimeter_walls",
        "create_curtain_wall",
        "generate_facade_grid",
        "create_panel",
    ],
    "openings": [
        "create_door",
        "create_window",
    ],
    "foundations": [
        "create_footing",
    ],
}

# Canonical phase ordering — if the LLM returns phases outside this order
# we sort them to ensure dependencies are respected (storeys first, etc.)
_PHASE_ORDER = [
    "storeys",
    "structure",
    "mezzanines",
    "foundations",
    "envelope",
    "openings",
]


# ---------------------------------------------------------------------------
# OpenClaw binary helper (shared with openclaw_planner.py)
# ---------------------------------------------------------------------------

def _find_openclaw() -> Optional[str]:
    """Locate the openclaw binary."""
    found = shutil.which("openclaw")
    if found:
        return found
    for candidate in (
        "/opt/homebrew/bin/openclaw",
        "/usr/local/bin/openclaw",
        os.path.expanduser("~/.local/bin/openclaw"),
        os.path.expanduser("~/bin/openclaw"),
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


# ---------------------------------------------------------------------------
# JSON extraction (reused from openclaw_planner.py)
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from agent response text.

    Handles OpenClaw's JSON envelope: the actual content may be inside
    result.payloads[0].text or result.text when --json is used.
    """
    stripped = text.strip()

    # Strategy 0: unwrap OpenClaw JSON envelope if present
    try:
        envelope = json.loads(stripped)
        if isinstance(envelope, dict):
            # Try result.payloads[0].text (openclaw --json output)
            payloads = (envelope.get("result") or {}).get("payloads", [])
            if payloads and isinstance(payloads[0], dict) and "text" in payloads[0]:
                inner = payloads[0]["text"]
                try:
                    return json.loads(inner)
                except json.JSONDecodeError:
                    # Inner text may not be valid JSON, try other strategies below
                    stripped = inner.strip()
            # Try result.text
            elif isinstance((envelope.get("result") or {}).get("text"), str):
                inner = envelope["result"]["text"]
                try:
                    return json.loads(inner)
                except json.JSONDecodeError:
                    stripped = inner.strip()
            # If it already has the keys we want, return as-is
            elif "phases" in envelope or "actions" in envelope:
                return envelope
    except json.JSONDecodeError:
        pass

    # Strategy 1: direct parse
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Strategy 2: markdown code fence
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", stripped, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: first balanced { ... } block
    brace_match = re.search(r"\{", stripped)
    if brace_match:
        start = brace_match.start()
        depth = 0
        for i in range(start, len(stripped)):
            if stripped[i] == "{":
                depth += 1
            elif stripped[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(stripped[start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise PlannerError(
        f"Failed to extract JSON from agent response. "
        f"Raw output (first 500 chars): {stripped[:500]}"
    )


# ---------------------------------------------------------------------------
# OpenClaw subprocess call
# ---------------------------------------------------------------------------

def _call_openclaw(message: str, timeout: int, openclaw_bin: str) -> str:
    """Run openclaw agent and return stdout."""
    cmd = [
        openclaw_bin,
        "agent",
        "--agent", "bim_operator",
        "--message", message,
        "--json",
        "--timeout", str(timeout),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
    except subprocess.TimeoutExpired as exc:
        raise PlannerError(
            f"OpenClaw agent timed out after {timeout}s."
        ) from exc
    except FileNotFoundError as exc:
        raise PlannerError(
            f"Failed to execute openclaw at '{openclaw_bin}': {exc}"
        ) from exc

    output = result.stdout.strip()
    if not output:
        # OpenClaw sometimes puts the response in stderr when the gateway
        # falls back to embedded mode. Check for JSON payloads in stderr.
        stderr = result.stderr.strip()
        if stderr:
            # Look for JSON payload in stderr (after diagnostic lines)
            for line in stderr.split("\n"):
                line = line.strip()
                if line.startswith("{") and ("payloads" in line or "actions" in line or "phases" in line):
                    output = line
                    break
            # Also try: find the last JSON block in stderr
            if not output:
                import re as _re
                json_blocks = _re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', stderr)
                for block in reversed(json_blocks):
                    if "payloads" in block or "actions" in block or "phases" in block or "text" in block:
                        output = block
                        break
        if not output:
            raise PlannerError(
                f"OpenClaw agent returned no output. "
                f"Exit code: {result.returncode}. "
                f"Stderr: {stderr[:500] if stderr else '(empty)'}"
            )
    return output


# ---------------------------------------------------------------------------
# Phase 1: High-level planning — decompose into phases
# ---------------------------------------------------------------------------

def _build_planning_prompt(user_prompt: str) -> str:
    """Build the ~600-char prompt for Phase 1 (decomposition)."""
    return (
        "Decompose this building request into construction phases.\n"
        'Respond with JSON: {"phases": [{"name": "...", "description": "...", '
        '"element_types": [...], "estimated_count": N}, ...]}\n'
        "\n"
        "Phase names must be from: storeys, structure, mezzanines, envelope, openings, foundations.\n"
        "Order: storeys first, then structure, then envelope/openings.\n"
        "Keep descriptions concise (one line each).\n"
        "\n"
        f"Building: {user_prompt.strip()}\n"
        "\n"
        "Respond with ONLY the JSON. No markdown, no commentary."
    )


def _plan_phases(user_prompt: str, openclaw_bin: str) -> List[Dict[str, Any]]:
    """Phase 1: Decompose building into ordered phases."""
    message = _build_planning_prompt(user_prompt)
    output = _call_openclaw(message, _PLAN_TIMEOUT, openclaw_bin)
    data = _extract_json(output)

    phases = data.get("phases", [])
    if not phases:
        raise PlannerError(
            "Planning phase returned no phases. "
            f"Raw response: {output[:500]}"
        )

    # Validate and normalize phase names
    for phase in phases:
        name = str(phase.get("name", "")).lower().strip()
        phase["name"] = name
        if "element_types" not in phase:
            phase["element_types"] = []
        if "estimated_count" not in phase:
            phase["estimated_count"] = 0
        if "description" not in phase:
            phase["description"] = name

    # Sort phases to canonical ordering (storeys before structure, etc.)
    def _sort_key(phase: Dict[str, Any]) -> int:
        name = phase["name"]
        try:
            return _PHASE_ORDER.index(name)
        except ValueError:
            return len(_PHASE_ORDER)  # unknown phases go last

    phases.sort(key=_sort_key)
    return phases


# ---------------------------------------------------------------------------
# Phase 2: Per-phase execution prompts
# ---------------------------------------------------------------------------

def _allowed_types_for_phase(phase_name: str, element_types: List[str]) -> List[str]:
    """Determine which action types this phase should use."""
    # Prefer the canonical set if available, otherwise use what the LLM suggested
    canonical = _PHASE_ACTION_TYPES.get(phase_name)
    if canonical:
        return canonical

    # Fall back to what the LLM listed, filtered to known types
    from .tool_specs import tool_names
    known = set(tool_names())
    # Also accept compiled action types that the compiler knows
    known.update({
        "ensure_storey", "create_rect_slab", "create_rectangular_slab",
        "generate_column_grid", "generate_perimeter_walls",
        "generate_floor_plate", "generate_facade_grid",
    })
    return [t for t in element_types if t in known] or list(known)


def _build_execution_prompt(
    phase: Dict[str, Any],
    user_prompt: str,
    scene_summary: str,
    completed_phases: List[str],
) -> str:
    """Build a focused ~800-1400 char prompt for one execution phase."""
    phase_name = phase["name"].upper()
    description = phase.get("description", "")
    allowed = _allowed_types_for_phase(phase["name"], phase.get("element_types", []))

    parts = [
        f"Generate BIM actions for the {phase_name} phase of this building.",
    ]

    # Scene context — what already exists
    if scene_summary.strip() and scene_summary.strip() != "Empty IFC model":
        parts.append(f"Scene has: {scene_summary.strip()}")
    else:
        parts.append("Starting from empty scene.")

    # What previous phases completed
    if completed_phases:
        parts.append(f"Completed phases: {', '.join(completed_phases)}.")

    # Building context (abbreviated)
    parts.append(f"\nBuilding: {user_prompt.strip()}")
    parts.append(f"Phase focus: {description}")

    # Output format
    parts.append(
        '\nRespond with JSON: {"version":"1", "units":"meters", '
        '"summary":"...", "assumptions":[], "actions":[...]}'
    )
    parts.append(
        "Each action: {\"type\":\"<action_type>\", \"name\":\"<name>\", ...params}"
    )

    # Constraint: only use allowed types
    parts.append(
        f"\nOnly use these action types: {', '.join(allowed)}."
    )

    # Strongly encourage parametric generators to reduce action count
    parts.append(
        "IMPORTANT: Use generate_column_grid for regular column grids (1 action instead of 30+). "
        "Use generate_floor_plate for rectangular slabs with edge beams (1 action instead of 5). "
        "Use generate_perimeter_walls for walls around a footprint (1 action instead of 4). "
        "Keep total actions under 30 by using generators wherever possible."
    )
    parts.append(
        "Other phases handle other element types. Do not duplicate existing elements."
    )
    parts.append("\nRespond with ONLY the JSON. No markdown, no commentary.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Phase execution — call agent, parse, compile, apply
# ---------------------------------------------------------------------------

# Action type aliases the LLM may produce
_TYPE_ALIASES = {
    "create_rectangular_slab": "create_rect_slab",
    "create_slab": "create_rect_slab",
    "create_column_grid": "generate_column_grid",
    "create_perimeter_walls": "generate_perimeter_walls",
    "create_floor_plate": "generate_floor_plate",
    "create_facade_grid": "generate_facade_grid",
    "ensure_project": "ensure_storey",  # if project, let storey handle it
}

# Field aliases the LLM may use
_FIELD_ALIASES = {
    "storey": "storey_name",
    "start_x": "x1",
    "start_y": "y1",
    "end_x": "x2",
    "end_y": "y2",
}


def _normalize_actions(actions: List[Dict[str, Any]]) -> None:
    """Normalize action types and field names in-place so the compiler accepts them.

    Fixes common LLM mistakes:
    - create_rectangular_slab -> create_rect_slab
    - beam with x/y instead of x1/y1/x2/y2
    - storey instead of storey_name
    """
    for action in actions:
        # Normalize type
        atype = action.get("type", "")
        if atype in _TYPE_ALIASES:
            action["type"] = _TYPE_ALIASES[atype]

        # Normalize field names
        for old_key, new_key in _FIELD_ALIASES.items():
            if old_key in action and new_key not in action:
                action[new_key] = action.pop(old_key)

        # Special case: beams with x/y need conversion to x1/y1/x2/y2
        if action.get("type") == "create_beam":
            if "x" in action and "x1" not in action:
                # Single-point beam → can't fix, but set x1=x, y1=y
                # The planner should have provided start/end points
                pass
            if "start_x" in action and "x1" not in action:
                action["x1"] = action.pop("start_x")
            if "start_y" in action and "y1" not in action:
                action["y1"] = action.pop("start_y")
            if "end_x" in action and "x2" not in action:
                action["x2"] = action.pop("end_x")
            if "end_y" in action and "y2" not in action:
                action["y2"] = action.pop("end_y")


@dataclass
class _PhaseResult:
    """Result of executing a single phase."""
    phase_name: str
    action_count: int
    elapsed_seconds: float
    errors: List[str]


def _execute_phase(
    phase: Dict[str, Any],
    user_prompt: str,
    scene_summary: str,
    completed_phases: List[str],
    openclaw_bin: str,
    author: IfcAuthor,
) -> _PhaseResult:
    """Execute a single phase: prompt -> parse -> compile -> apply to IFC."""
    t0 = time.time()
    phase_name = phase["name"]
    errors: List[str] = []

    # Build and send the focused prompt
    message = _build_execution_prompt(
        phase, user_prompt, scene_summary, completed_phases,
    )
    output = _call_openclaw(message, _PHASE_TIMEOUT, openclaw_bin)

    # Parse JSON response
    authored_plan = _extract_json(output)

    # Ensure plan has required top-level keys for the compiler
    if "version" not in authored_plan:
        authored_plan["version"] = "1"
    if "units" not in authored_plan:
        authored_plan["units"] = "meters"
    if "summary" not in authored_plan:
        authored_plan["summary"] = f"{phase_name} phase"
    if "assumptions" not in authored_plan:
        authored_plan["assumptions"] = []
    if "actions" not in authored_plan:
        authored_plan["actions"] = []

    # Normalize action types and field names before compilation
    _normalize_actions(authored_plan["actions"])

    if not authored_plan["actions"]:
        elapsed = time.time() - t0
        return _PhaseResult(
            phase_name=phase_name,
            action_count=0,
            elapsed_seconds=elapsed,
            errors=["Phase returned no actions"],
        )

    # Compile authored actions into primitives
    try:
        compiled_plan = compile_core_plan(authored_plan)
    except Exception as exc:
        elapsed = time.time() - t0
        return _PhaseResult(
            phase_name=phase_name,
            action_count=0,
            elapsed_seconds=elapsed,
            errors=[f"Compilation failed: {exc}"],
        )

    # Convert to PlannedToolCall objects
    tool_calls = [
        _to_tool_call(action, index)
        for index, action in enumerate(compiled_plan["actions"], start=1)
    ]

    # Apply each tool call to the IFC model
    applied = 0
    for call in tool_calls:
        try:
            result = author.apply_tool_call(call.name, call.arguments)
            applied += 1
        except AuthoringError as exc:
            errors.append(f"{call.name}({call.arguments.get('name', '?')}): {exc}")

    elapsed = time.time() - t0
    return _PhaseResult(
        phase_name=phase_name,
        action_count=applied,
        elapsed_seconds=elapsed,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plan_building(
    user_prompt: str,
    output_path: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Multi-phase building generation via OpenClaw agent.

    Phase 1: Decompose the building request into subsystem phases.
    Phase 2: Execute each phase with a focused prompt.

    Returns a summary dict with phase details and total action count.
    """
    openclaw_bin = _find_openclaw()
    if not openclaw_bin:
        raise PlannerError(
            "Cannot find 'openclaw' binary. "
            "Install OpenClaw or ensure it is on your PATH."
        )

    # -----------------------------------------------------------------------
    # Phase 1: Decompose into phases
    # -----------------------------------------------------------------------
    print("[phased] Phase 1: Decomposing building into phases...")
    t0 = time.time()
    phases = _plan_phases(user_prompt, openclaw_bin)
    plan_elapsed = time.time() - t0

    print(
        f"[phased] Plan complete in {plan_elapsed:.1f}s — "
        f"{len(phases)} phases: {', '.join(p['name'] for p in phases)}"
    )

    for i, phase in enumerate(phases, 1):
        est = phase.get("estimated_count", "?")
        print(f"  {i}. {phase['name']}: {phase['description']} (~{est} actions)")

    if dry_run:
        return {
            "phases": [
                {
                    "name": p["name"],
                    "description": p["description"],
                    "element_types": p.get("element_types", []),
                    "estimated_count": p.get("estimated_count", 0),
                }
                for p in phases
            ],
            "total_phases": len(phases),
            "dry_run": True,
        }

    # -----------------------------------------------------------------------
    # Phase 2: Execute each phase
    # -----------------------------------------------------------------------
    author = IfcAuthor(output_path)
    completed_phases: List[str] = []
    phase_results: List[Dict[str, Any]] = []
    total_actions = 0
    total_errors = 0

    for i, phase in enumerate(phases, 1):
        phase_name = phase["name"]
        est = phase.get("estimated_count", "?")
        print(f"\n[phased] Phase {i}/{len(phases)}: {phase_name} (~{est} actions)...")

        # Get fresh scene summary so the model sees what previous phases built
        scene_summary = author.scene_summary()

        # Execute with retry on failure
        result = _execute_phase(
            phase=phase,
            user_prompt=user_prompt,
            scene_summary=scene_summary,
            completed_phases=completed_phases,
            openclaw_bin=openclaw_bin,
            author=author,
        )

        # If the phase failed completely, retry once with a simplified prompt
        if result.action_count == 0 and result.errors:
            print(
                f"[phased]   Phase {phase_name} failed ({len(result.errors)} errors), "
                "retrying..."
            )
            scene_summary = author.scene_summary()
            result = _execute_phase(
                phase=phase,
                user_prompt=user_prompt,
                scene_summary=scene_summary,
                completed_phases=completed_phases,
                openclaw_bin=openclaw_bin,
                author=author,
            )

        completed_phases.append(phase_name)
        total_actions += result.action_count
        total_errors += len(result.errors)

        status = "done" if not result.errors else f"done with {len(result.errors)} errors"
        print(
            f"[phased]   Phase {i}/{len(phases)}: {phase_name} "
            f"({result.action_count} actions)... {status} in {result.elapsed_seconds:.1f}s"
        )

        if result.errors:
            for err in result.errors[:5]:
                print(f"[phased]     ERROR: {err}")
            if len(result.errors) > 5:
                print(f"[phased]     ... and {len(result.errors) - 5} more errors")

        phase_results.append({
            "name": phase_name,
            "actions": result.action_count,
            "errors": len(result.errors),
            "elapsed_seconds": round(result.elapsed_seconds, 1),
        })

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    author.save()
    total_elapsed = time.time() - t0

    print(f"\n[phased] Complete: {total_actions} actions across {len(phases)} phases "
          f"in {total_elapsed:.1f}s")
    if total_errors:
        print(f"[phased] {total_errors} total errors")
    print(author.debug_dump())

    return {
        "phases": phase_results,
        "total_phases": len(phases),
        "total_actions": total_actions,
        "total_errors": total_errors,
        "elapsed_seconds": round(total_elapsed, 1),
        "output_path": output_path,
    }


# ---------------------------------------------------------------------------
# PlanResult facade — for compatibility with the existing CLI loop
# ---------------------------------------------------------------------------

def create_phased_plan_via_openclaw(
    user_prompt: str,
    output_path: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Entry point for the phased planner.

    Unlike ``create_plan_via_openclaw()`` which returns a PlanResult for the
    CLI loop to execute, this function handles the full plan-then-execute
    pipeline internally (because each phase needs its own prompt and the
    scene state refreshes between phases).

    Returns a summary dict. The IFC file is written to ``output_path``.
    """
    return plan_building(
        user_prompt=user_prompt,
        output_path=output_path,
        dry_run=dry_run,
    )
