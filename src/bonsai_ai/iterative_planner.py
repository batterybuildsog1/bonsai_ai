"""Iterative session-based building generation via OpenClaw agent.

Maintains a single conversation session so the agent accumulates context
from previous turns, enabling it to reference earlier decisions, correct
spatial misalignments, and adapt to execution failures.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from bonsai_ai_core import compile_plan as compile_core_plan
except ModuleNotFoundError:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from bonsai_ai_core import compile_plan as compile_core_plan

from .ifc_author import AuthoringError, IfcAuthor
from .planner import PlannerError, PlannedToolCall, _to_tool_call

# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

_SESSION_TIMEOUT = 900  # 15 minutes per turn — quality over speed


# ---------------------------------------------------------------------------
# JSON extraction
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
            payloads = (envelope.get("result") or {}).get("payloads", [])
            if payloads and isinstance(payloads[0], dict) and "text" in payloads[0]:
                inner = payloads[0]["text"]
                try:
                    return json.loads(inner)
                except json.JSONDecodeError:
                    stripped = inner.strip()
            elif isinstance((envelope.get("result") or {}).get("text"), str):
                inner = envelope["result"]["text"]
                try:
                    return json.loads(inner)
                except json.JSONDecodeError:
                    stripped = inner.strip()
            elif "actions" in envelope or "version" in envelope:
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
# Action normalization
# ---------------------------------------------------------------------------

_TYPE_ALIASES = {
    "create_rectangular_slab": "create_rect_slab",
    "create_slab": "create_rect_slab",
    "create_column_grid": "generate_column_grid",
    "create_beam_grid": "generate_beam_grid",
    "create_perimeter_walls": "generate_perimeter_walls",
    "create_floor_plate": "generate_floor_plate",
    "create_facade_grid": "generate_facade_grid",
    "create_opening_array": "generate_opening_array",
    "ensure_project": "ensure_storey",
}

_FIELD_ALIASES = {
    "storey": "storey_name",
}

_BEAM_FIELD_ALIASES = {
    "start_x": "x1",
    "start_y": "y1",
    "end_x": "x2",
    "end_y": "y2",
}

_NUMERIC_FIELDS = frozenset({
    "depth", "width", "height", "thickness", "length",
    "x", "y", "z", "x1", "y1", "x2", "y2",
    "dx", "dy", "dz",
    "base_z", "top_z", "end_z", "elevation",
    "start_x", "start_y", "end_x", "end_y",
    "offset_along_wall", "sill_height",
    "spacing_x", "spacing_y",
    "grid_origin_x", "grid_origin_y",
    "column_width", "column_depth", "column_height",
    "beam_width", "beam_depth",
    "center_x", "center_y",
    "tread_depth", "riser_height", "step_count",
    "rotation_deg", "rotation_degrees", "direction_deg",
    "bays_x", "bays_y",
    "panel_width", "panel_height", "panel_gap", "panel_thickness",
    "count", "spacing", "start_offset",
})


def _coerce_numeric(value: object) -> object:
    """Try to coerce a value to a number."""
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        for suffix in ("mm", "m", "cm", "in", "ft", "'", '"'):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
                break
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            pass
    return value


def _normalize_actions(actions: List[Dict[str, Any]]) -> None:
    """Normalize action types and field names in-place so the compiler accepts them."""
    for action in actions:
        atype = action.get("type", "")
        if atype in _TYPE_ALIASES:
            action["type"] = _TYPE_ALIASES[atype]

        for old_key, new_key in _FIELD_ALIASES.items():
            if old_key in action and new_key not in action:
                action[new_key] = action.pop(old_key)

        if action.get("type") == "create_beam":
            for old_key, new_key in _BEAM_FIELD_ALIASES.items():
                if old_key in action and new_key not in action:
                    action[new_key] = action.pop(old_key)

        for field_name in _NUMERIC_FIELDS:
            if field_name in action:
                action[field_name] = _coerce_numeric(action[field_name])

        # NOTE: Slab dimension coercion (length/width -> width/depth) is
        # handled by _coerce_numeric_fields in the schema layer.  Do NOT
        # remap slab dimensions here -- the previous code mapped
        # length -> depth which rotated slabs 90 degrees.


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Result of a single orchestrator turn."""
    phase_name: str
    actions_applied: int
    actions_failed: int
    errors: List[str]
    elapsed_seconds: float
    raw_response: str = ""


@dataclass
class BuildResult:
    """Result of the full iterative build."""
    session_id: str
    turns: List[TurnResult]
    total_actions: int
    total_errors: int
    elapsed_seconds: float
    output_path: str


# ---------------------------------------------------------------------------
# IterativeBuilder
# ---------------------------------------------------------------------------

class IterativeBuilder:
    """Orchestrates multi-turn BIM generation through an OpenClaw session.

    The session loop is simple:
    1. Send the building prompt to the agent.
    2. Agent generates actions (JSON plan).
    3. Orchestrator compiles and applies actions to IFC.
    4. Orchestrator reports results + scene summary back.
    5. Agent decides what to do next.
    6. Repeat until the agent returns no more actions.
    """

    def __init__(
        self,
        output_path: str,
        session_id: Optional[str] = None,
        agent_id: str = "bim_operator",
        timeout_per_turn: int = _SESSION_TIMEOUT,
    ):
        self.output_path = str(Path(output_path).resolve())
        self.session_id = session_id or f"build-{uuid.uuid4().hex[:8]}"
        self.agent_id = agent_id
        self.timeout = timeout_per_turn
        self.openclaw_bin = self._find_openclaw()
        self.turn_results: List[TurnResult] = []

    @staticmethod
    def _find_openclaw() -> str:
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
        raise PlannerError("Cannot find 'openclaw' binary.")

    # ------------------------------------------------------------------
    # Agent communication
    # ------------------------------------------------------------------

    def _call_agent(self, message: str, timeout: Optional[int] = None) -> str:
        """Send a message to the agent within the persistent session."""
        t = timeout or self.timeout
        cmd = [
            self.openclaw_bin,
            "agent",
            "--agent", self.agent_id,
            "--session-id", self.session_id,
            "--message", message,
            "--json",
            "--timeout", str(t),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=t + 30,
            )
        except subprocess.TimeoutExpired as exc:
            raise PlannerError(
                f"Agent timed out after {t}s"
            ) from exc

        output = result.stdout.strip()
        if not output:
            stderr = result.stderr.strip()
            if stderr:
                for line in stderr.split("\n"):
                    line = line.strip()
                    if line.startswith("{") and any(
                        kw in line for kw in ("payloads", "actions", "text")
                    ):
                        output = line
                        break
                if not output:
                    json_blocks = re.findall(
                        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', stderr
                    )
                    for block in reversed(json_blocks):
                        if any(kw in block for kw in ("payloads", "actions", "text")):
                            output = block
                            break
            if not output:
                raise PlannerError(
                    f"Agent returned no output. Exit: {result.returncode}. "
                    f"Stderr: {(stderr or '(empty)')[:500]}"
                )
        return output

    # ------------------------------------------------------------------
    # Execution engine
    # ------------------------------------------------------------------

    def _execute_actions(
        self,
        actions: List[Dict[str, Any]],
        turn_label: str,
        author: IfcAuthor,
    ) -> Tuple[int, int, List[str]]:
        """Compile and apply actions, return (applied, failed, errors)."""
        _normalize_actions(actions)

        plan = {
            "version": "1",
            "units": "meters",
            "summary": turn_label,
            "assumptions": [],
            "actions": actions,
        }

        try:
            compiled = compile_core_plan(plan)
        except Exception as exc:
            return 0, len(actions), [f"Compilation failed: {exc}"]

        tool_calls = [
            _to_tool_call(action, idx)
            for idx, action in enumerate(compiled["actions"], start=1)
        ]

        applied = 0
        failed = 0
        errors = []
        for call in tool_calls:
            try:
                author.apply_tool_call(call.name, call.arguments)
                applied += 1
            except AuthoringError as exc:
                failed += 1
                errors.append(
                    f"{call.name}({call.arguments.get('name', '?')}): {exc}"
                )

        return applied, failed, errors

    # ------------------------------------------------------------------
    # Main build loop
    # ------------------------------------------------------------------

    def build(self, user_prompt: str, dry_run: bool = False) -> BuildResult:
        """Execute the full iterative build.

        1. Send the building prompt to the agent.
        2. Agent responds with actions.
        3. Apply actions to IFC, report results back.
        4. Repeat until agent returns no actions or max turns reached.
        """
        t0 = time.time()
        total_actions = 0
        total_errors = 0
        max_turns = 10

        output_dir = Path(self.output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        author = IfcAuthor(self.output_path)

        print(f"[iterative] Session: {self.session_id}")
        print(f"[iterative] Sending building request...")

        # Initial prompt — just the building request + output format hint
        initial_message = (
            f"Build this as an IFC model:\n\n{user_prompt.strip()}\n\n"
            "Generate BIM actions as JSON. Respond with:\n"
            '{"version":"1", "units":"meters", "summary":"...", '
            '"assumptions":[], "actions":[...]}\n\n'
            "Use generate_column_grid, generate_beam_grid, generate_floor_plate, "
            "generate_perimeter_walls, generate_opening_array for repetitive patterns. "
            "Build storeys first, then structure, then envelope, "
            "then openings.\n\n"
            "Respond with ONLY JSON."
        )

        if dry_run:
            elapsed = time.time() - t0
            return BuildResult(
                session_id=self.session_id,
                turns=[],
                total_actions=0,
                total_errors=0,
                elapsed_seconds=round(elapsed, 1),
                output_path=self.output_path,
            )

        message = initial_message
        for turn_num in range(1, max_turns + 1):
            print(f"\n[iterative] Turn {turn_num}...")
            turn_t0 = time.time()

            output = self._call_agent(message)
            data = _extract_json(output)
            actions = data.get("actions", [])

            if not actions:
                print(f"[iterative]   No actions returned -- build complete.")
                break

            applied, failed, errors = self._execute_actions(
                actions, f"turn-{turn_num}", author
            )

            result = TurnResult(
                phase_name=f"turn-{turn_num}",
                actions_applied=applied,
                actions_failed=failed,
                errors=errors,
                elapsed_seconds=time.time() - turn_t0,
            )
            self.turn_results.append(result)
            total_actions += applied
            total_errors += failed

            status = "done" if not errors else f"done ({len(errors)} errors)"
            print(
                f"[iterative]   Turn {turn_num}: {applied} actions, "
                f"{status}, {result.elapsed_seconds:.1f}s"
            )
            for err in errors[:3]:
                print(f"[iterative]     ERROR: {err}")

            # Build follow-up message with results + current scene
            scene_summary = author.scene_summary() or "Empty IFC model"
            parts = [
                f"Turn {turn_num} result: {applied} actions applied, {failed} failed.",
            ]
            if errors:
                parts.append("Errors:")
                for err in errors[:5]:
                    parts.append(f"  - {err}")
            parts.append(f"\nCurrent scene: {scene_summary}")
            parts.append(
                "\nIf the building is complete, respond with "
                '{"actions":[]}. Otherwise, send the next batch of actions.'
            )
            message = "\n".join(parts)

            # Retry once if the turn failed completely
            if applied == 0 and errors:
                print(f"[iterative]   Retrying...")
                retry_output = self._call_agent(message)
                retry_data = _extract_json(retry_output)
                retry_actions = retry_data.get("actions", [])
                if retry_actions:
                    r_applied, r_failed, r_errors = self._execute_actions(
                        retry_actions, f"turn-{turn_num}-retry", author
                    )
                    total_actions += r_applied
                    total_errors += r_failed
                    if r_errors:
                        for err in r_errors[:3]:
                            print(f"[iterative]     RETRY ERROR: {err}")
                    else:
                        print(
                            f"[iterative]   Retry: {r_applied} actions applied"
                        )
        else:
            print(f"[iterative] Reached max turns ({max_turns}).")

        # Save IFC
        author.save()
        elapsed = time.time() - t0

        print(
            f"\n[iterative] Build complete: {total_actions} actions "
            f"in {elapsed:.1f}s"
        )
        if total_errors:
            print(f"[iterative] {total_errors} total errors")
        print(author.debug_dump())

        return BuildResult(
            session_id=self.session_id,
            turns=self.turn_results,
            total_actions=total_actions,
            total_errors=total_errors,
            elapsed_seconds=round(elapsed, 1),
            output_path=self.output_path,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_iterative_plan_via_openclaw(
    user_prompt: str,
    output_path: str,
    dry_run: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Entry point for the iterative session-based planner.

    Maintains a single OpenClaw session so the agent accumulates context
    from previous turns.

    Returns a summary dict. The IFC file is written to ``output_path``.
    """
    builder = IterativeBuilder(
        output_path=output_path,
        session_id=session_id,
    )
    result = builder.build(user_prompt, dry_run=dry_run)
    return {
        "session_id": result.session_id,
        "turns": [
            {
                "name": t.phase_name,
                "actions": t.actions_applied,
                "errors": t.actions_failed,
                "elapsed_seconds": round(t.elapsed_seconds, 1),
            }
            for t in result.turns
        ],
        "total_turns": len(result.turns),
        "total_actions": result.total_actions,
        "total_errors": result.total_errors,
        "elapsed_seconds": result.elapsed_seconds,
        "output_path": result.output_path,
    }
