"""Iterative session-based building generation via OpenClaw agent.

Unlike the phased_planner.py which fires independent subprocess calls,
this module maintains a single conversation session across all phases.
The agent accumulates context from previous turns, enabling it to:
- Reference decisions from earlier phases (e.g., storey names, grid origins)
- Correct spatial misalignments between phases
- Adapt to execution failures reported by the orchestrator
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
from .phased_planner import _normalize_actions, _extract_json

# ---------------------------------------------------------------------------
# Phase ordering and action type constraints
# ---------------------------------------------------------------------------

PHASE_ORDER = [
    "storeys",
    "structure",
    "mezzanines",
    "foundations",
    "envelope",
    "openings",
]

PHASE_ACTION_TYPES: Dict[str, List[str]] = {
    "storeys": ["ensure_storey"],
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

# Timeouts
_PLAN_TIMEOUT = 120     # 2 minutes for decomposition turn
_PHASE_TIMEOUT = 180    # 3 minutes per execution phase turn


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
    """Orchestrates multi-turn BIM generation through an OpenClaw session."""

    def __init__(
        self,
        output_path: str,
        session_id: Optional[str] = None,
        agent_id: str = "bim_operator",
        timeout_per_turn: int = _PHASE_TIMEOUT,
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
            # Check stderr for JSON payloads (OpenClaw embedded mode fallback)
            stderr = result.stderr.strip()
            if stderr:
                for line in stderr.split("\n"):
                    line = line.strip()
                    if line.startswith("{") and any(
                        kw in line for kw in ("payloads", "actions", "phases", "text")
                    ):
                        output = line
                        break
                if not output:
                    json_blocks = re.findall(
                        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', stderr
                    )
                    for block in reversed(json_blocks):
                        if any(kw in block for kw in ("payloads", "actions", "phases", "text")):
                            output = block
                            break
            if not output:
                raise PlannerError(
                    f"Agent returned no output. Exit: {result.returncode}. "
                    f"Stderr: {(stderr or '(empty)')[:500]}"
                )
        return output

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _planning_prompt(self, user_prompt: str) -> str:
        return (
            "I need you to help me build this as an IFC model, step by step.\n"
            "First, decompose this building into construction phases.\n"
            'Respond with JSON: {"phases": [{"name": "...", "description": "...", '
            '"estimated_count": N}, ...]}\n'
            "\n"
            "Phase names must be from: storeys, structure, mezzanines, "
            "envelope, openings, foundations.\n"
            "Order: storeys first, then structure, then envelope, then openings.\n"
            "\n"
            f"Building: {user_prompt.strip()}\n"
            "\n"
            "Respond with ONLY the JSON. No markdown, no commentary."
        )

    def _execution_prompt(
        self,
        phase: Dict[str, Any],
        completed_summary: str,
        scene_summary: str,
    ) -> str:
        phase_name = phase["name"]
        description = phase.get("description", phase_name)
        allowed = PHASE_ACTION_TYPES.get(
            phase_name,
            list(PHASE_ACTION_TYPES.get("structure", [])),
        )

        parts = []

        # Report what happened in previous turn
        if completed_summary:
            parts.append(completed_summary)
            parts.append("")

        # Current scene state
        parts.append(f"Current scene: {scene_summary}")
        parts.append("")

        # Phase instruction
        parts.append(
            f"Now generate the {phase_name.upper()} phase: {description}"
        )
        parts.append(
            f"Only use these action types: {', '.join(allowed)}."
        )

        # Generator guidance
        parts.append(
            "Use generate_column_grid for regular column grids, "
            "generate_floor_plate for rectangular slabs with edge beams, "
            "generate_perimeter_walls for walls around a footprint. "
            "Keep total actions under 30."
        )

        # Phase-specific constraints
        if phase_name == "openings":
            parts.append(
                "IMPORTANT: Windows/doors can only be hosted in walls created "
                "by create_wall (IfcWall), NOT curtain walls. Only reference "
                "wall names from the scene summary above."
            )

        parts.append("")
        parts.append(
            'Return JSON: {"version":"1", "units":"meters", '
            '"summary":"...", "assumptions":[], "actions":[...]}'
        )
        parts.append("Respond with ONLY the JSON.")

        return "\n".join(parts)

    def _format_turn_report(self, result: TurnResult) -> str:
        """Format a turn result as a status report for the agent."""
        lines = [
            f"Phase {result.phase_name} complete: "
            f"{result.actions_applied} actions applied"
        ]
        if result.actions_failed > 0:
            lines[0] += f", {result.actions_failed} failed"
            for err in result.errors[:5]:
                lines.append(f"  Error: {err}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Execution engine
    # ------------------------------------------------------------------

    def _execute_actions(
        self,
        actions: List[Dict[str, Any]],
        phase_name: str,
        author: IfcAuthor,
    ) -> Tuple[int, int, List[str]]:
        """Compile and apply actions, return (applied, failed, errors)."""
        # Normalize LLM quirks
        _normalize_actions(actions)

        # Build a plan dict for the compiler
        plan = {
            "version": "1",
            "units": "meters",
            "summary": f"{phase_name} phase",
            "assumptions": [],
            "actions": actions,
        }

        # Compile
        try:
            compiled = compile_core_plan(plan)
        except Exception as exc:
            return 0, len(actions), [f"Compilation failed: {exc}"]

        # Convert to PlannedToolCall objects and apply to IFC
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
        """Execute the full iterative build."""
        t0 = time.time()
        total_actions = 0
        total_errors = 0

        # Ensure output directory exists
        output_dir = Path(self.output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create the IfcAuthor (will create new file or load existing)
        author = IfcAuthor(self.output_path)

        # Turn 0: Planning decomposition
        print(f"[iterative] Session: {self.session_id}")
        print("[iterative] Turn 0: Decomposing building into phases...")

        plan_output = self._call_agent(
            self._planning_prompt(user_prompt),
            timeout=_PLAN_TIMEOUT,
        )
        plan_data = _extract_json(plan_output)
        phases = plan_data.get("phases", [])

        if not phases:
            raise PlannerError("Planning turn returned no phases.")

        # Sort to canonical order
        def sort_key(p):
            name = p.get("name", "").lower().strip()
            try:
                return PHASE_ORDER.index(name)
            except ValueError:
                return len(PHASE_ORDER)

        phases.sort(key=sort_key)

        print(
            f"[iterative] Plan: {len(phases)} phases: "
            f"{', '.join(p['name'] for p in phases)}"
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

        # Execute each phase as a conversation turn
        completed_summary = ""

        for i, phase in enumerate(phases, 1):
            phase_name = phase["name"]
            print(
                f"\n[iterative] Turn {i}/{len(phases)}: {phase_name}..."
            )
            turn_t0 = time.time()

            # Get current scene state
            scene_summary = author.scene_summary() or "Empty IFC model"

            # Build prompt with prior turn's results
            prompt = self._execution_prompt(
                phase, completed_summary, scene_summary
            )

            # Call agent (within persistent session)
            output = self._call_agent(prompt)
            data = _extract_json(output)
            actions = data.get("actions", [])

            if not actions:
                result = TurnResult(
                    phase_name=phase_name,
                    actions_applied=0,
                    actions_failed=0,
                    errors=["No actions returned"],
                    elapsed_seconds=time.time() - turn_t0,
                    raw_response=output[:1000],
                )
                self.turn_results.append(result)
                completed_summary = self._format_turn_report(result)
                print(f"[iterative]   {phase_name}: no actions returned")
                continue

            # Execute actions against IFC
            applied, failed, errors = self._execute_actions(
                actions, phase_name, author
            )

            result = TurnResult(
                phase_name=phase_name,
                actions_applied=applied,
                actions_failed=failed,
                errors=errors,
                elapsed_seconds=time.time() - turn_t0,
            )
            self.turn_results.append(result)
            total_actions += applied
            total_errors += failed

            completed_summary = self._format_turn_report(result)

            status = "done" if not errors else f"done ({len(errors)} errors)"
            print(
                f"[iterative]   {phase_name}: {applied} actions, "
                f"{status}, {result.elapsed_seconds:.1f}s"
            )
            for err in errors[:3]:
                print(f"[iterative]     ERROR: {err}")

            # Retry once if the phase failed completely
            if applied == 0 and errors:
                print(f"[iterative]   Retrying {phase_name}...")
                retry_scene = author.scene_summary() or "Empty IFC model"
                retry_prompt = (
                    f"The {phase_name} phase failed:\n"
                    + "\n".join(f"  - {e}" for e in errors[:5])
                    + f"\n\nCurrent scene: {retry_scene}\n"
                    f"Please try again with corrected actions. "
                    f"Return ONLY JSON."
                )
                retry_output = self._call_agent(retry_prompt)
                retry_data = _extract_json(retry_output)
                retry_actions = retry_data.get("actions", [])
                if retry_actions:
                    r_applied, r_failed, r_errors = self._execute_actions(
                        retry_actions, phase_name, author
                    )
                    total_actions += r_applied
                    total_errors += r_failed
                    completed_summary = (
                        f"Phase {phase_name} retry: "
                        f"{r_applied} applied, {r_failed} failed"
                    )
                    if r_errors:
                        for err in r_errors[:3]:
                            print(f"[iterative]     RETRY ERROR: {err}")
                    else:
                        print(
                            f"[iterative]   {phase_name} retry: "
                            f"{r_applied} actions applied"
                        )

        # Save IFC
        author.save()
        elapsed = time.time() - t0

        print(
            f"\n[iterative] Build complete: {total_actions} actions "
            f"across {len(phases)} phases in {elapsed:.1f}s"
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

    Maintains a single OpenClaw session across all phases so the agent
    accumulates context from previous turns.

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
        "total_phases": len(result.turns),
        "total_actions": result.total_actions,
        "total_errors": result.total_errors,
        "elapsed_seconds": result.elapsed_seconds,
        "output_path": result.output_path,
    }
