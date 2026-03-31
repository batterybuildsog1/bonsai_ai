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

# ---------------------------------------------------------------------------
# Locate the openclaw binary
# ---------------------------------------------------------------------------

_OPENCLAW_TIMEOUT = 120  # seconds


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

def _tool_spec_summary() -> str:
    """Compact plain-text description of available BIM tools for the prompt."""
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
    """Construct the prompt message sent to the OpenClaw agent.

    The message embeds the BIM planner system prompt, the plan JSON schema,
    and a summary of available tools so the agent returns a well-formed plan.
    """
    schema_json = json.dumps(plan_schema(), indent=2)
    parts = [
        SYSTEM_PROMPT.strip(),
        "",
        "## Response format",
        "",
        "You MUST respond with ONLY a single JSON object matching this schema:",
        "```json",
        schema_json,
        "```",
        "",
        "Each action in the 'actions' array must have at least 'type' and 'name'.",
        "",
        "## Available action types and their fields",
        "",
        _tool_spec_summary(),
    ]

    if scene_summary.strip():
        parts.extend(["", "## Current scene", "", scene_summary.strip()])

    if progress_summary.strip():
        parts.extend(["", "## Completed work so far", "", progress_summary.strip()])

    parts.extend([
        "",
        "## User request",
        "",
        user_prompt.strip(),
        "",
        "Respond with ONLY the JSON plan. No markdown fences, no commentary.",
    ])

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Parse the agent response
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Dict:
    """Extract a JSON object from the agent's response text.

    Tries several strategies:
    1. Direct JSON parse of the full text
    2. Extract from markdown code fences
    3. Find the first { ... } block
    """
    stripped = text.strip()

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
