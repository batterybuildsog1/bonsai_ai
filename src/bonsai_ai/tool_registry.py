"""Deferred / selective tool loading for the Bonsai AI planner.

Instead of sending all 15+ tool schemas with every LLM request, this module
lets callers select only the 3-5 tools relevant to the current building phase.
This reduces tool-definition token usage by ~85%.

Usage::

    from bonsai_ai.tool_registry import get_tools_for_phase, as_openai_tools_for_phase

    # Get only structure-phase tools
    specs = get_tools_for_phase("structure")

    # Get OpenAI-formatted tools for the envelope phase
    tools = as_openai_tools_for_phase("envelope")

    # Compact text summary for prompt injection
    summary = get_tool_summary_for_phase("structure")
"""

from __future__ import annotations

from typing import Dict, List

from .tool_specs import TOOL_SPECS, ToolSpec

JsonDict = Dict[str, object]

# ---------------------------------------------------------------------------
# Phase -> tool name mapping
# ---------------------------------------------------------------------------
# Each phase lists the tool names relevant to that building stage.
# Tools that don't yet have ToolSpec entries (e.g. stair and editing tools)
# are included for forward-compatibility — they are silently skipped when
# resolving to ToolSpec objects.

TOOL_CATEGORIES: Dict[str, List[str]] = {
    "setup": ["ensure_project", "ensure_storey"],
    "structure": [
        "generate_column_grid",
        "create_column",
        "create_beam",
        "generate_floor_plate",
        "create_rectangular_slab",
    ],
    "envelope": [
        "create_wall",
        "generate_perimeter_walls",
        "create_curtain_wall",
        "generate_facade_grid",
        "create_panel",
    ],
    "openings": ["create_door", "create_window"],
    "foundations": ["create_footing"],
    "stairs": ["create_stair_run", "create_stair_landing"],
    "editing": [
        "update_element",
        "delete_element",
        "move_element",
        "replace_section",
        "rebuild_branch",
    ],
}

# Pre-build a name -> ToolSpec lookup for fast resolution.
_SPEC_BY_NAME: Dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}


def available_phases() -> List[str]:
    """Return the list of known phase names."""
    return list(TOOL_CATEGORIES.keys())


# ---------------------------------------------------------------------------
# Core lookup helpers
# ---------------------------------------------------------------------------

def get_tools_for_phase(phase_name: str) -> List[ToolSpec]:
    """Return only the ToolSpec objects relevant to *phase_name*.

    Raises ``KeyError`` if the phase name is not recognized.
    Tools listed in the category but not yet defined in TOOL_SPECS are
    silently skipped (forward-compatibility for stair/editing tools).
    """
    tool_names = TOOL_CATEGORIES.get(phase_name)
    if tool_names is None:
        raise KeyError(
            f"Unknown phase '{phase_name}'. "
            f"Available phases: {', '.join(TOOL_CATEGORIES)}"
        )
    return [_SPEC_BY_NAME[name] for name in tool_names if name in _SPEC_BY_NAME]


def get_tools_for_phases(phase_names: List[str]) -> List[ToolSpec]:
    """Return ToolSpec objects for multiple phases, deduplicated and ordered.

    The returned list preserves the order in which tools first appear across
    the requested phases (first phase listed wins for ordering).

    Raises ``KeyError`` if any phase name is not recognized.
    """
    seen: set[str] = set()
    result: List[ToolSpec] = []
    for phase in phase_names:
        for spec in get_tools_for_phase(phase):
            if spec.name not in seen:
                seen.add(spec.name)
                result.append(spec)
    return result


# ---------------------------------------------------------------------------
# Compact summaries (for prompt injection)
# ---------------------------------------------------------------------------

def get_tool_summary_for_phase(phase_name: str) -> str:
    """Return a compact plain-text summary of tools available for *phase_name*.

    The summary is designed to be injected into an LLM prompt alongside a
    phase-specific instruction set.  It stays under ~500 characters for
    typical phases.
    """
    specs = get_tools_for_phase(phase_name)
    if not specs:
        return f"[{phase_name}] No tools available yet."
    lines: List[str] = [f"[{phase_name}] tools:"]
    for spec in specs:
        required = spec.schema.get("required", [])
        lines.append(f"- {spec.name}({', '.join(required)})")
    return "\n".join(lines)


def get_tool_summary_for_phases(phase_names: List[str]) -> str:
    """Return a compact summary covering multiple phases."""
    specs = get_tools_for_phases(phase_names)
    if not specs:
        return "No tools available for the requested phases."
    lines: List[str] = ["Available tools:"]
    for spec in specs:
        required = spec.schema.get("required", [])
        lines.append(f"- {spec.name}({', '.join(required)})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Provider-formatted tool lists (phase-filtered)
# ---------------------------------------------------------------------------

def as_openai_tools_for_phase(phase_name: str) -> List[JsonDict]:
    """OpenAI-formatted tool definitions for a specific phase."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "strict": True,
                "parameters": spec.schema,
            },
        }
        for spec in get_tools_for_phase(phase_name)
    ]


def as_anthropic_tools_for_phase(phase_name: str) -> List[JsonDict]:
    """Anthropic-formatted tool definitions for a specific phase."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.schema,
        }
        for spec in get_tools_for_phase(phase_name)
    ]


def as_openai_tools_for_phases(phase_names: List[str]) -> List[JsonDict]:
    """OpenAI-formatted tool definitions for multiple phases (deduped)."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "strict": True,
                "parameters": spec.schema,
            },
        }
        for spec in get_tools_for_phases(phase_names)
    ]


def as_anthropic_tools_for_phases(phase_names: List[str]) -> List[JsonDict]:
    """Anthropic-formatted tool definitions for multiple phases (deduped)."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.schema,
        }
        for spec in get_tools_for_phases(phase_names)
    ]
