"""Planner backend that routes through OpenClaw instead of direct API calls.

Uses the ``openclaw agent`` subprocess to make model calls via the user's
OpenClaw subscription (OAuth auth) rather than per-token API keys.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    from bonsai_ai_core import compile_plan as compile_core_plan
    from bonsai_ai_core.planner import SYSTEM_PROMPT
    from bonsai_ai_core.schema import plan_schema
except ModuleNotFoundError:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from bonsai_ai_core import compile_plan as compile_core_plan
    from bonsai_ai_core.planner import SYSTEM_PROMPT
    from bonsai_ai_core.schema import plan_schema

from .planner import PlannerError, PlanResult, PlannedToolCall, _to_tool_call
from .tool_specs import TOOL_SPECS
from .tool_registry import get_tool_summary_for_phase, get_tool_summary_for_phases

# ---------------------------------------------------------------------------
# Locate the openclaw binary
# ---------------------------------------------------------------------------

_OPENCLAW_TIMEOUT = 1200  # 20 minutes — quality over speed, let models work iteratively


def _find_openclaw() -> Optional[str]:
    """Locate the openclaw binary, checking PATH and common install locations."""
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
# Build the message that the OpenClaw agent receives
# ---------------------------------------------------------------------------

def _tool_spec_summary(phase: Optional[str] = None) -> str:
    """Compact plain-text description of available BIM tools for the prompt.

    If *phase* is given, returns only tools relevant to that building phase
    via the tool registry (~85% token reduction). Otherwise returns all tools.
    """
    if phase is not None:
        return get_tool_summary_for_phase(phase)
    lines: List[str] = []
    for spec in TOOL_SPECS:
        required = spec.schema.get("required", [])
        lines.append(f"- {spec.name}: {spec.description}")
        lines.append(f"  Required fields: {', '.join(required)}")
    return "\n".join(lines)


def _build_message(
    user_prompt: str,
    scene_summary: str,
    progress_summary: str = "",
) -> str:
    """Construct a lean prompt for the OpenClaw bim_operator agent.

    Option A (lean): Trust the agent's own AGENTS.md charter for BIM domain
    knowledge and tool awareness. Send only the building request, scene state,
    and a compact output format hint. This keeps the message under ~1500 chars
    so OpenClaw + agent context doesn't overwhelm the model.
    """
    parts = [
        "Generate a BIM plan as JSON for this building. Respond with ONLY a JSON object:",
        '{"version":"1", "units":"meters", "summary":"...", "assumptions":[...], "actions":[...]}',
        "",
        "Each action: {\"type\":\"<action_type>\", \"name\":\"<element_name>\", ...dimensions/coords...}",
        "Use generate_column_grid, generate_perimeter_walls, generate_floor_plate for repetitive patterns.",
        "Use create_wall, create_beam, create_column, create_slab, create_curtain_wall, create_door, create_window for individual elements.",
        "All dimensions in meters. Build storeys first, then structure, then envelope, then openings.",
    ]

    if scene_summary.strip():
        parts.extend(["", "Current scene: " + scene_summary.strip()])
    else:
        parts.extend(["", "Starting from empty scene."])

    if progress_summary.strip():
        parts.extend(["", "Completed so far:", progress_summary.strip()])

    parts.extend([
        "",
        "Building request:",
        user_prompt.strip(),
        "",
        "Respond with ONLY the JSON. No markdown, no commentary.",
    ])

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Parse the agent response
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Dict:
    """Extract a JSON object from the agent's response text.

    Handles OpenClaw's JSON envelope (result.payloads[0].text) and
    tries several fallback strategies.
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
                try:
                    return json.loads(envelope["result"]["text"])
                except json.JSONDecodeError:
                    stripped = envelope["result"]["text"].strip()
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
        f"Failed to extract JSON from OpenClaw agent response. "
        f"Raw output (first 500 chars): {stripped[:500]}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_plan_via_openclaw(
    user_prompt: str,
    scene_summary: str,
    progress_summary: str = "",
) -> PlanResult:
    """Create a BIM plan by routing through the OpenClaw agent subprocess.

    This replaces direct API calls with the user's OpenClaw subscription.
    The agent handles model selection and authentication via OAuth.

    Returns the same ``PlanResult`` as ``planner.create_plan()``.
    """
    openclaw_bin = _find_openclaw()
    if not openclaw_bin:
        raise PlannerError(
            "Cannot find 'openclaw' binary. "
            "Install OpenClaw or ensure it is on your PATH. "
            "Checked: PATH, /opt/homebrew/bin, /usr/local/bin, ~/.local/bin"
        )

    message = _build_message(user_prompt, scene_summary, progress_summary)

    cmd = [
        openclaw_bin,
        "agent",
        "--agent", "bim_operator",
        "--message", message,
        "--json",
        "--timeout", str(_OPENCLAW_TIMEOUT),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_OPENCLAW_TIMEOUT + 10,  # grace period beyond agent timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise PlannerError(
            f"OpenClaw agent timed out after {_OPENCLAW_TIMEOUT}s. "
            "Try simplifying the prompt or increasing the timeout."
        ) from exc
    except FileNotFoundError as exc:
        raise PlannerError(
            f"Failed to execute openclaw at '{openclaw_bin}': {exc}"
        ) from exc

    output = result.stdout.strip()
    if not output:
        stderr = result.stderr.strip()
        raise PlannerError(
            f"OpenClaw agent returned no output. "
            f"Exit code: {result.returncode}. "
            f"Stderr: {stderr[:500] if stderr else '(empty)'}"
        )

    # Parse the JSON plan from the agent response
    authored_plan = _extract_json(output)

    # Compile the authored plan into buildable primitive actions
    try:
        compiled_plan = compile_core_plan(authored_plan)
    except Exception as exc:
        raise PlannerError(
            f"OpenClaw agent returned a plan that failed compilation: {exc}"
        ) from exc

    # Convert compiled actions into PlannedToolCall objects
    tool_calls = [
        _to_tool_call(action, index)
        for index, action in enumerate(compiled_plan["actions"], start=1)
    ]

    return PlanResult(
        provider="openclaw",
        model="openclaw-agent",
        tool_calls=tool_calls,
        raw_text="COMPLETE" if not tool_calls else "",
    )
