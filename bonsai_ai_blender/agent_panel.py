"""Agent chat panel for the Bonsai AI Blender addon.

Provides a conversational interface to the bim_operator OpenClaw agent
directly inside Blender's 3D View sidebar. Communication happens via
subprocess -- the panel spawns ``openclaw agent`` and polls its output
with ``bpy.app.timers``.

Phase 2 adds:
- Streaming display: stdout lines are shown incrementally as they arrive
- Tool call visibility: stderr tool-execution lines are displayed in real-time
- Phase indicator: agent_phase tracks thinking / tool / responding / idle

Phase 3 adds:
- Plan approval UI: tool calls rendered as a readable plan with formatted args
- Optional approval gate: require_approval toggle pauses execution for user OK
- Approve / Reject operators for pending plans
- Human-readable tool argument formatting (dimensions, names, storeys)

Phase 4 adds:
- Element linking from chat: agent response text is scanned for Blender object
  names and clickable select buttons are drawn next to matches
- Plan messages also get select buttons for elements that already exist in the
  scene (e.g., host walls referenced by door/window tool calls)
- The select operator now zooms the viewport to the selected element

Phase 5 adds:
- Floating Cmd+K / Ctrl+K quick prompt dialog (like VS Code command palette)
- Uses invoke_props_dialog for a native Blender floating input
- Sends message to agent and auto-opens sidebar to show the response
- Replaces the old sidebar toggle keymap with the quick prompt operator
"""

from __future__ import annotations

import json
import math
import os
import queue
import re
import shutil
import subprocess
import textwrap
import threading
import time
from typing import List

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    IntProperty,
    StringProperty,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIMER_INTERVAL = 0.25  # seconds between polls
_MAX_DISPLAY_MESSAGES = 80  # limit drawn messages to keep UI responsive
_WRAP_CHARS = 55  # characters per line for text wrapping in sidebar
_OPENCLAW_TIMEOUT = 300  # seconds before we consider the agent hung
_MAX_ELEMENT_LINKS = 5  # Phase 4: max clickable element links per message

# Regex patterns for detecting tool calls in stderr output
_TOOL_RE = re.compile(
    r"\[tool\]\s+(\S+)\s*(.*)", re.IGNORECASE
)
# Broader pattern: lines like "Running tool: memory_search ..." or
# "Executing read /path/to/file"
_TOOL_ALT_RE = re.compile(
    r"(?:running|executing|calling|tool)\s*:?\s+(\S+)\s*(.*)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Module-level transient state (not serialized)
# ---------------------------------------------------------------------------

_process: subprocess.Popen | None = None
_process_start_time: float = 0.0
_stdout_queue: queue.Queue = queue.Queue()
_stderr_queue: queue.Queue = queue.Queue()
_reader_thread: threading.Thread | None = None
_stderr_thread: threading.Thread | None = None
_timer_registered: bool = False
_accumulated_stdout: list[str] = []

# Phase 2 streaming state
_streaming_msg_index: int = -1  # index into state.messages for the live placeholder
_seen_tool_calls: list[str] = []  # tool call IDs/summaries we already displayed
_accumulated_stderr: list[str] = []  # raw stderr lines for final fallback

# Phase 3 plan approval state
_pending_tool_calls: list[dict] = []  # raw tool_call dicts awaiting approval
_pending_reply: str = ""  # agent reply text held until plan is approved/rejected

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_openclaw() -> str | None:
    """Locate the openclaw binary, handling Blender's limited PATH."""
    found = shutil.which("openclaw")
    if found:
        return found
    # Common install locations on macOS / Linux
    for candidate in (
        "/opt/homebrew/bin/openclaw",
        "/usr/local/bin/openclaw",
        os.path.expanduser("~/.local/bin/openclaw"),
        os.path.expanduser("~/bin/openclaw"),
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _wrap_text(text: str, width: int = _WRAP_CHARS) -> List[str]:
    """Split text into lines that fit the sidebar panel width."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        stripped = paragraph.strip()
        if stripped:
            lines.extend(textwrap.wrap(stripped, width=width))
        else:
            lines.append("")
    return lines or [""]


def _ifc_context_for_object(obj) -> str | None:
    """Return concise IFC semantic context for a Blender object, or None.

    Uses Bonsai's ``tool.Ifc`` to resolve the IFC entity and reads key
    properties from ``Pset_BonsaiAI``.  All imports are lazy so the function
    degrades gracefully when IfcOpenShell or Bonsai are not available.
    """
    try:
        import bonsai.tool as tool  # noqa: delayed import
        import ifcopenshell.util.element
    except Exception:
        return None

    ifc_file = tool.Ifc.get()
    if ifc_file is None:
        return None
    element = tool.Ifc.get_entity(obj)
    if element is None:
        return None

    ifc_class = element.is_a()
    lines: list[str] = [f"{obj.name} ({ifc_class})"]

    # Storey / spatial container
    try:
        container = ifcopenshell.util.element.get_container(element)
        if container and getattr(container, "Name", None):
            lines.append(f"  Storey: {container.Name}")
    except Exception:
        pass

    # Pset_BonsaiAI metadata (dimensions, material, role)
    try:
        psets = ifcopenshell.util.element.get_psets(
            element, psets_only=True, should_inherit=False,
        )
        ai_props = psets.get("Pset_BonsaiAI", {})
    except Exception:
        ai_props = {}

    # Dimensions -- pick whichever keys exist
    dim_parts: list[str] = []
    for key, unit in (
        ("Length", "m long"),
        ("Width", "m wide"),
        ("Height", "m high"),
        ("Thickness", "m thick"),
    ):
        val = ai_props.get(key)
        if val is not None:
            try:
                dim_parts.append(f"{float(val):.2g} {unit}")
            except (TypeError, ValueError):
                pass
    if dim_parts:
        lines.append(f"  Dims: {', '.join(dim_parts)}")

    # Material / section
    mat = ai_props.get("MaterialRef")
    if mat:
        lines.append(f"  Material: {mat}")

    # Semantic role (may be top-level or inside a JSON 'semantics' dict)
    role = ai_props.get("Role")
    semantics_raw = ai_props.get("semantics")
    if isinstance(semantics_raw, str):
        try:
            semantics_raw = json.loads(semantics_raw)
        except Exception:
            semantics_raw = None
    if isinstance(semantics_raw, dict):
        role = role or semantics_raw.get("role")
        sys_name = semantics_raw.get("system_name")
        if sys_name:
            lines.append(f"  System: {sys_name}")
    if role:
        lines.append(f"  Role: {role}")

    return "\n".join(lines)


def _viewport_context_string() -> str:
    """Gather current viewport selection context for the agent.

    When Bonsai / IfcOpenShell are available the context is enriched with
    IFC class, storey, dimensions, material, and semantic role for each
    selected object.  Falls back to plain name + location otherwise.
    """
    parts: list[str] = []

    # Active IFC path
    ifc_path = bpy.context.scene.get("bonsai_ai_last_ifc_path")
    if isinstance(ifc_path, str) and ifc_path:
        parts.append(f"Active IFC: {ifc_path}")

    # Selected objects -- try IFC-enriched, fall back to plain names
    selected = bpy.context.selected_objects
    if selected:
        enriched: list[str] = []
        for obj in selected[:10]:
            ifc_ctx = _ifc_context_for_object(obj)
            if ifc_ctx:
                enriched.append(ifc_ctx)
            else:
                enriched.append(obj.name)
        label = "Selected" if len(enriched) == 1 else "Selected objects"
        # Single selection: inline.  Multiple: one per line.
        if len(enriched) == 1:
            parts.append(f"{label}: {enriched[0]}")
        else:
            parts.append(f"{label}:")
            for entry in enriched:
                # indent sub-lines of multi-line entries
                for i, line in enumerate(entry.split("\n")):
                    parts.append(f"  {line}" if i == 0 else f"  {line}")
        if len(selected) > 10:
            parts.append(f"  ... and {len(selected) - 10} more")

    # Active object detail (location is always useful)
    active = bpy.context.active_object
    if active:
        parts.append(f"Active object: {active.name}")
        loc = active.location
        parts.append(f"  Location: ({loc.x:.2f}, {loc.y:.2f}, {loc.z:.2f})")

    if not parts:
        return ""
    return "[Viewport context]\n" + "\n".join(parts)


def _build_agent_message(user_text: str) -> str:
    """Combine user text with viewport context for the agent."""
    ctx = _viewport_context_string()
    if ctx:
        return f"{user_text}\n\n{ctx}"
    return user_text


def _reader_worker(pipe, q: queue.Queue) -> None:
    """Background thread that reads a pipe line-by-line into a queue."""
    try:
        for line in iter(pipe.readline, b""):
            q.put(line.decode("utf-8", errors="replace"))
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def _add_message(state, role: str, content: str, tool_name: str = "") -> None:
    """Append a message to the agent state collection."""
    msg = state.messages.add()
    msg.role = role
    msg.content = content
    msg.tool_name = tool_name
    msg.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    # Auto-scroll to newest
    state.message_index = len(state.messages) - 1


# ---------------------------------------------------------------------------
# Phase 2: Streaming display helpers
# ---------------------------------------------------------------------------


def _ensure_streaming_placeholder(state) -> int:
    """Create or return the index of the streaming placeholder message.

    The placeholder is an "agent" message that gets its ``content`` updated
    every timer tick while stdout accumulates.  When the process completes
    the placeholder is either replaced with the final parsed response or
    removed if nothing useful was streamed.
    """
    global _streaming_msg_index
    if _streaming_msg_index >= 0 and _streaming_msg_index < len(state.messages):
        return _streaming_msg_index
    # Create the placeholder
    msg = state.messages.add()
    msg.role = "streaming"
    msg.content = "..."
    msg.tool_name = ""
    msg.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    _streaming_msg_index = len(state.messages) - 1
    state.message_index = _streaming_msg_index
    return _streaming_msg_index


def _update_streaming_content(state, text: str) -> None:
    """Update the streaming placeholder message with *text*."""
    global _streaming_msg_index
    idx = _ensure_streaming_placeholder(state)
    if idx < len(state.messages):
        state.messages[idx].content = text


def _remove_streaming_placeholder(state) -> None:
    """Remove the streaming placeholder if it exists."""
    global _streaming_msg_index
    if _streaming_msg_index >= 0 and _streaming_msg_index < len(state.messages):
        state.messages.remove(_streaming_msg_index)
    _streaming_msg_index = -1


def _parse_stderr_for_tools(line: str) -> tuple[str, str] | None:
    """Try to extract a tool name and arguments from a stderr line.

    Returns ``(tool_name, args_summary)`` or ``None`` if the line doesn't
    look like a tool call.
    """
    stripped = line.strip()
    if not stripped:
        return None

    m = _TOOL_RE.match(stripped)
    if m:
        return m.group(1), m.group(2).strip()

    m = _TOOL_ALT_RE.match(stripped)
    if m:
        return m.group(1), m.group(2).strip()

    return None


def _detect_phase_from_stderr(line: str) -> str | None:
    """Infer the agent phase from a stderr status line.

    Returns a phase string or ``None`` if no phase can be inferred.
    """
    low = line.lower().strip()
    if not low:
        return None
    if any(kw in low for kw in ("thinking", "reasoning", "planning")):
        return "thinking"
    if any(kw in low for kw in ("[tool]", "running tool", "executing", "calling tool")):
        return "tool"
    if any(kw in low for kw in ("responding", "generating", "writing response")):
        return "responding"
    return None


def _extract_streaming_text(accumulated: list[str]) -> str:
    """Build a display string from accumulated stdout lines.

    The final output is expected to be JSON, but partial lines may contain
    readable fragments.  This function tries to extract anything useful for
    display while the process is still running.
    """
    raw = "".join(accumulated)
    if not raw.strip():
        return ""

    # Quick check: if it looks like a partial JSON object, try to extract
    # text fields we can display early.
    text_parts: list[str] = []

    # Try to find "thinking" / "reasoning" content in partial JSON
    for key in ("thinking", "reasoning"):
        pattern = rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"'
        m = re.search(pattern, raw)
        if m:
            text_parts.append(m.group(1).replace("\\n", "\n").replace('\\"', '"'))

    # Try to find "reply" / "response" / "content" text
    for key in ("reply", "response", "content"):
        pattern = rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"'
        m = re.search(pattern, raw)
        if m:
            val = m.group(1).replace("\\n", "\n").replace('\\"', '"')
            if val and val not in text_parts:
                text_parts.append(val)

    if text_parts:
        return "\n".join(text_parts)

    # If nothing was extracted from JSON patterns, and the raw text is
    # short enough, show it directly (might be plain-text output mode)
    stripped = raw.strip()
    # If it looks like JSON, don't show raw braces -- just show a waiting msg
    if stripped.startswith("{") or stripped.startswith("["):
        return ""
    return stripped


# ---------------------------------------------------------------------------
# Phase 3: Plan formatting helpers
# ---------------------------------------------------------------------------


def _wall_length(args: dict) -> float | None:
    """Compute wall length from start/end coordinates, if available."""
    try:
        dx = float(args["end_x"]) - float(args["start_x"])
        dy = float(args["end_y"]) - float(args["start_y"])
        return math.sqrt(dx * dx + dy * dy)
    except (KeyError, TypeError, ValueError):
        return None


def _format_tool_call(name: str, args: dict) -> str:
    """Produce a human-readable one-liner for a tool call.

    Examples:
        create_wall: "South Wall" on Level 0 -- 20.0m long, 4.0m high, 0.2m thick
        create_rectangular_slab: "Ground Slab" on Level 0 -- 10.0m x 8.0m, 0.15m thick
        create_door: "Main Entry" in "North Wall" -- 1.2m x 2.4m
        ensure_storey: "Level 1" at 3.5m
    """
    elem_name = args.get("name", "")
    storey = args.get("storey_name", "")

    # Start with the tool name
    parts: list[str] = [name + ":"]

    # Element name
    if elem_name:
        parts.append(f'"{elem_name}"')

    # --- Tool-specific formatting ---

    if name == "ensure_project":
        proj = args.get("project_name", "")
        site = args.get("site_name", "")
        bldg = args.get("building_name", "")
        detail_parts = []
        if proj:
            detail_parts.append(f'project "{proj}"')
        if site:
            detail_parts.append(f'site "{site}"')
        if bldg:
            detail_parts.append(f'building "{bldg}"')
        if detail_parts:
            parts.append("-- " + ", ".join(detail_parts))
        return " ".join(parts)

    if name == "ensure_storey":
        elev = args.get("elevation")
        if elev is not None:
            parts.append(f"at {float(elev):.1f}m")
        return " ".join(parts)

    # Storey context
    if storey:
        parts.append(f"on {storey}")

    if name == "create_wall":
        length = _wall_length(args)
        height = args.get("height")
        thickness = args.get("thickness")
        dims = []
        if length is not None:
            dims.append(f"{length:.1f}m long")
        if height is not None:
            dims.append(f"{float(height):.1f}m high")
        if thickness is not None:
            dims.append(f"{float(thickness):.1f}m thick")
        if dims:
            parts.append("-- " + ", ".join(dims))

    elif name == "create_rectangular_slab":
        length = args.get("length")
        width = args.get("width")
        thickness = args.get("thickness")
        dims = []
        if length is not None and width is not None:
            dims.append(f"{float(length):.1f}m x {float(width):.1f}m")
        if thickness is not None:
            dims.append(f"{float(thickness):.1f}m thick")
        if dims:
            parts.append("-- " + ", ".join(dims))

    elif name in ("create_door", "create_window"):
        wall = args.get("wall_name", "")
        w = args.get("width")
        h = args.get("height")
        if wall:
            parts.append(f'in "{wall}"')
        dims = []
        if w is not None and h is not None:
            dims.append(f"{float(w):.1f}m x {float(h):.1f}m")
        if dims:
            parts.append("-- " + ", ".join(dims))
        if name == "create_window":
            sill = args.get("sill_height")
            if sill is not None:
                parts.append(f"sill {float(sill):.1f}m")

    elif name == "create_column":
        w = args.get("width")
        d = args.get("depth")
        h = args.get("height")
        dims = []
        if w is not None and d is not None:
            dims.append(f"{float(w):.1f}m x {float(d):.1f}m")
        if h is not None:
            dims.append(f"{float(h):.1f}m high")
        if dims:
            parts.append("-- " + ", ".join(dims))

    elif name == "create_beam":
        w = args.get("width")
        d = args.get("depth")
        dims = []
        if w is not None and d is not None:
            dims.append(f"{float(w):.1f}m x {float(d):.1f}m section")
        if dims:
            parts.append("-- " + ", ".join(dims))

    elif name == "create_panel":
        w = args.get("width")
        h = args.get("height")
        t = args.get("thickness")
        orient = args.get("orientation", "")
        dims = []
        if w is not None:
            dims.append(f"{float(w):.1f}m wide")
        if h is not None:
            dims.append(f"{float(h):.1f}m high")
        if t is not None:
            dims.append(f"{float(t):.1f}m thick")
        if orient:
            dims.append(orient)
        if dims:
            parts.append("-- " + ", ".join(dims))

    elif name == "create_footing":
        length = args.get("length")
        w = args.get("width")
        t = args.get("thickness")
        dims = []
        if length is not None and w is not None:
            dims.append(f"{float(length):.1f}m x {float(w):.1f}m")
        if t is not None:
            dims.append(f"{float(t):.1f}m thick")
        if dims:
            parts.append("-- " + ", ".join(dims))

    elif name == "create_curtain_wall":
        w = args.get("width")
        h = args.get("height")
        pw = args.get("panel_width")
        ph = args.get("panel_height")
        dims = []
        if w is not None and h is not None:
            dims.append(f"{float(w):.1f}m x {float(h):.1f}m")
        if pw is not None and ph is not None:
            dims.append(f"panels {float(pw):.1f}m x {float(ph):.1f}m")
        if dims:
            parts.append("-- " + ", ".join(dims))

    else:
        # Unknown tool -- show a compact JSON summary of args
        # Filter out metadata keys to keep it readable
        display_args = {
            k: v for k, v in args.items()
            if k not in ("semantics", "presentation", "foundation", "name", "storey_name")
        }
        if display_args:
            brief = json.dumps(display_args, separators=(",", ":"))
            if len(brief) > 60:
                brief = brief[:57] + "..."
            parts.append(f"-- {brief}")

    return " ".join(parts)


def _build_plan_summary(tool_calls: list[dict]) -> str:
    """Build a multi-line plan summary from a list of tool call dicts.

    Each tool call dict should have 'name' and 'args' keys.
    Returns a string like:
        Proposed Plan (3 actions):
        1. create_wall: "South Wall" on Level 0 -- 20.0m long, 4.0m high
        2. create_wall: "East Wall" on Level 0 -- 15.0m long, 4.0m high
        3. create_door: "Main Entry" in "North Wall" -- 1.2m x 2.4m
    """
    count = len(tool_calls)
    header = f"Proposed Plan ({count} action{'s' if count != 1 else ''}):"
    lines = [header]
    for i, tc in enumerate(tool_calls, 1):
        name = tc.get("name", "unknown")
        args = tc.get("args", {})
        formatted = _format_tool_call(name, args)
        lines.append(f"  {i}. {formatted}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 4: Element linking helpers
# ---------------------------------------------------------------------------


def _find_element_names_in_text(text: str) -> list[str]:
    """Scan *text* for substrings that match Blender object names in the scene.

    Returns a deduplicated list of matched object names, limited to
    ``_MAX_ELEMENT_LINKS`` entries.  Only objects currently in
    ``bpy.data.objects`` are considered.

    Matching strategy:
    - Check every object name in the scene against the text
    - Require the name to appear as a "word-like" boundary (not part of a
      longer identifier) by checking that the surrounding characters are not
      alphanumeric/underscore.  This avoids false positives where a short
      name accidentally matches inside a longer word.
    - Sort candidate matches by length descending so longer, more specific
      names are preferred (and checked first for overlap avoidance).
    - Skip very short names (< 3 chars) to reduce noise from objects named
      things like "X" or "UV".
    """
    if not text:
        return []

    try:
        all_objects = bpy.data.objects
    except Exception:
        return []

    if not all_objects:
        return []

    # Build candidates: (name, length) sorted longest first
    candidates = sorted(
        ((obj.name, len(obj.name)) for obj in all_objects if len(obj.name) >= 3),
        key=lambda t: t[1],
        reverse=True,
    )

    found: list[str] = []
    found_spans: list[tuple[int, int]] = []  # track matched ranges to avoid overlaps

    for name, _length in candidates:
        if len(found) >= _MAX_ELEMENT_LINKS:
            break

        # Find all occurrences of this name in the text
        start = 0
        while start < len(text):
            idx = text.find(name, start)
            if idx == -1:
                break

            end_idx = idx + len(name)

            # Boundary check: character before and after should not be
            # alphanumeric or underscore (word-boundary-like)
            before_ok = (idx == 0) or not (text[idx - 1].isalnum() or text[idx - 1] == "_")
            after_ok = (end_idx == len(text)) or not (
                text[end_idx].isalnum() or text[end_idx] == "_"
            )

            if before_ok and after_ok:
                # Check this span doesn't overlap with an already-matched span
                overlaps = False
                for fs, fe in found_spans:
                    if not (end_idx <= fs or idx >= fe):
                        overlaps = True
                        break

                if not overlaps and name not in found:
                    found.append(name)
                    found_spans.append((idx, end_idx))
                    break  # one match per name is enough

            start = idx + 1

    return found


def _draw_element_links(layout, text: str) -> None:
    """Draw clickable select buttons for element names found in *text*.

    Called after rendering message content.  Adds a compact row of small
    buttons, each invoking ``BONSAI_AI_OT_agent_select_element``.
    """
    names = _find_element_names_in_text(text)
    if not names:
        return

    link_col = layout.column(align=True)
    for name in names:
        row = link_col.row(align=True)
        row.scale_y = 0.85  # slightly smaller than normal for subtlety
        op = row.operator(
            "bonsai_ai.agent_select_element",
            text=f"Select \"{name}\"",
            icon="RESTRICT_SELECT_OFF",
        )
        op.object_name = name


def _draw_plan_line_element_links(layout, action_line: str) -> None:
    """Draw select buttons for existing objects referenced in a plan action line.

    Extracts quoted strings from the line and checks if they correspond to
    existing scene objects.  This is useful for host references like
    ``in "North Wall"`` where the wall already exists.
    """
    quoted = re.findall(r'"([^"]+)"', action_line)
    if not quoted:
        return

    try:
        all_objects = bpy.data.objects
    except Exception:
        return

    for name in quoted:
        if all_objects.get(name) is not None:
            row = layout.row(align=True)
            row.scale_y = 0.75  # compact to avoid bloating the plan
            # Indent to align with action content
            row.separator(factor=2.0)
            op = row.operator(
                "bonsai_ai.agent_select_element",
                text=f"Select \"{name}\"",
                icon="RESTRICT_SELECT_OFF",
            )
            op.object_name = name


def _normalize_tool_calls(raw_list: list) -> list[dict]:
    """Normalize a list of tool call dicts into [{name, args}, ...]."""
    result: list[dict] = []
    for tc in raw_list:
        if not isinstance(tc, dict):
            continue
        name = tc.get("name") or tc.get("tool") or "unknown"
        args = tc.get("arguments") or tc.get("args") or tc.get("input") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = {}
        result.append({"name": name, "args": args})
    return result


def _parse_agent_response(raw_json: str, state) -> None:
    """Parse the JSON output from ``openclaw agent --json`` and populate chat.

    Phase 3: when tool_calls are present they are rendered as a formatted plan.
    If ``require_approval`` is enabled, execution pauses for user confirmation.
    """
    global _pending_tool_calls, _pending_reply

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        # Not valid JSON -- treat entire output as plain text response
        _add_message(state, "agent", raw_json.strip() or "(empty response)")
        return

    # The agent JSON may have various shapes. Handle the common ones.
    # Typical shape: {"result": {...}, "thinking": "...", "tool_calls": [...]}

    # Show thinking if present
    thinking = data.get("thinking") or data.get("reasoning") or ""
    if thinking:
        _add_message(state, "thinking", thinking.strip())

    # Extract reply text
    reply = data.get("reply") or data.get("response") or data.get("content") or ""
    if not reply:
        result_val = data.get("result")
        if isinstance(result_val, dict):
            reply = result_val.get("text", "") or result_val.get("content", "")
        elif isinstance(result_val, str):
            reply = result_val
    if isinstance(reply, dict):
        reply = json.dumps(reply, indent=2)
    reply = str(reply).strip()

    # --- Phase 3: Tool calls as a formatted plan ---
    raw_tool_calls = data.get("tool_calls") or data.get("tools") or []
    normalized = _normalize_tool_calls(raw_tool_calls) if isinstance(raw_tool_calls, list) else []

    if normalized:
        # Build a human-readable plan summary
        plan_text = _build_plan_summary(normalized)
        _add_message(state, "plan", plan_text)

        if state.require_approval:
            # Approval mode: hold execution, store pending state
            _pending_tool_calls = normalized
            _pending_reply = reply
            state.approval_pending = True
            state.agent_phase = "approval"
            state.status = "Awaiting approval..."
            # Don't show the reply yet -- it will be shown after approve/reject
            return
        else:
            # No approval needed: show plan (already added above) and continue
            pass

    # Show main response text
    if reply:
        _add_message(state, "agent", reply)

    # If nothing was extracted, dump the raw JSON summary
    if not thinking and not normalized and not reply:
        summary = json.dumps(data, indent=2)
        if len(summary) > 500:
            summary = summary[:500] + "\n... (truncated)"
        _add_message(state, "agent", summary)


def _tag_redraw() -> None:
    """Request a redraw of all 3D View sidebars so the panel updates."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == "UI":
                        region.tag_redraw()


# ---------------------------------------------------------------------------
# Timer callback
# ---------------------------------------------------------------------------


def _poll_agent_process() -> float | None:
    """Timer callback: drain queues, display streaming content, check finish.

    Phase 2 enhancements:
    - Parses stderr for tool-call signals and displays them immediately
    - Extracts partial content from stdout and updates a streaming placeholder
    - Tracks agent_phase transitions (thinking -> tool -> responding -> done)
    """
    global _process, _timer_registered, _accumulated_stdout
    global _streaming_msg_index, _seen_tool_calls, _accumulated_stderr

    state = _get_agent_state()
    if state is None:
        _timer_registered = False
        return None

    # ------------------------------------------------------------------
    # 1. Drain stdout queue
    # ------------------------------------------------------------------
    new_stdout = False
    while True:
        try:
            line = _stdout_queue.get_nowait()
            _accumulated_stdout.append(line)
            new_stdout = True
        except queue.Empty:
            break

    # ------------------------------------------------------------------
    # 2. Drain stderr queue -- detect tool calls and phase changes
    # ------------------------------------------------------------------
    stderr_lines: list[str] = []
    while True:
        try:
            line = _stderr_queue.get_nowait()
            stripped = line.strip()
            if stripped:
                stderr_lines.append(stripped)
                _accumulated_stderr.append(stripped)
        except queue.Empty:
            break

    for line in stderr_lines:
        # Try to detect a tool call
        tool_info = _parse_stderr_for_tools(line)
        if tool_info is not None:
            tool_name, tool_args = tool_info
            # Build a dedup key so we don't repeat the same tool message
            dedup_key = f"{tool_name}:{tool_args}"
            if dedup_key not in _seen_tool_calls:
                _seen_tool_calls.append(dedup_key)
                # Format: wrench emoji + tool name + brief args
                if tool_args:
                    # Truncate very long argument strings
                    display_args = tool_args if len(tool_args) <= 80 else tool_args[:77] + "..."
                    summary = f"\U0001f527 {tool_name}: {display_args}"
                else:
                    summary = f"\U0001f527 {tool_name}"
                _add_message(state, "tool", summary, tool_name=tool_name)
                state.agent_phase = "tool"
                state.status = f"Tool: {tool_name}"
            continue

        # Try to detect a phase change
        phase = _detect_phase_from_stderr(line)
        if phase is not None:
            state.agent_phase = phase
            if phase == "thinking":
                state.status = "Thinking..."
            elif phase == "responding":
                state.status = "Responding..."
        else:
            # Generic stderr status update (keep the existing V1 behaviour)
            state.status = line[:120]

    # ------------------------------------------------------------------
    # 3. Update streaming placeholder with partial stdout content
    # ------------------------------------------------------------------
    if new_stdout and _accumulated_stdout:
        preview = _extract_streaming_text(_accumulated_stdout)
        if preview:
            _update_streaming_content(state, preview)
            # If we're getting text output, we're probably in the responding phase
            if state.agent_phase not in ("tool", "responding"):
                state.agent_phase = "responding"
                state.status = "Responding..."

    if _process is None:
        _timer_registered = False
        return None

    # ------------------------------------------------------------------
    # 4. Enforce timeout
    # ------------------------------------------------------------------
    if _process_start_time and (time.time() - _process_start_time) > _OPENCLAW_TIMEOUT + 30:
        try:
            _process.terminate()
            _process.wait(timeout=2)
        except Exception:
            try:
                _process.kill()
            except Exception:
                pass
        _remove_streaming_placeholder(state)
        _add_message(state, "error", f"Agent timed out after {_OPENCLAW_TIMEOUT}s.")
        state.agent_phase = "error"
        state.status = "Timed out"
        state.is_running = False
        _process = None
        _timer_registered = False
        _cleanup_streaming_state()
        _tag_redraw()
        return None

    # ------------------------------------------------------------------
    # 5. Check if process finished
    # ------------------------------------------------------------------
    retcode = _process.poll()
    if retcode is not None:
        # Process finished -- give reader threads a moment to flush
        if _reader_thread and _reader_thread.is_alive():
            _reader_thread.join(timeout=1.0)
        if _stderr_thread and _stderr_thread.is_alive():
            _stderr_thread.join(timeout=1.0)

        # Drain any remaining stdout
        while True:
            try:
                line = _stdout_queue.get_nowait()
                _accumulated_stdout.append(line)
            except queue.Empty:
                break

        # Drain any remaining stderr (for error reporting)
        while True:
            try:
                line = _stderr_queue.get_nowait()
                stripped = line.strip()
                if stripped:
                    _accumulated_stderr.append(stripped)
                    # Last-chance tool detection on remaining stderr
                    tool_info = _parse_stderr_for_tools(stripped)
                    if tool_info is not None:
                        tool_name, tool_args = tool_info
                        dedup_key = f"{tool_name}:{tool_args}"
                        if dedup_key not in _seen_tool_calls:
                            _seen_tool_calls.append(dedup_key)
                            if tool_args:
                                display_args = tool_args if len(tool_args) <= 80 else tool_args[:77] + "..."
                                summary = f"\U0001f527 {tool_name}: {display_args}"
                            else:
                                summary = f"\U0001f527 {tool_name}"
                            _add_message(state, "tool", summary, tool_name=tool_name)
            except queue.Empty:
                break

        full_output = "".join(_accumulated_stdout).strip()
        _accumulated_stdout.clear()

        # Remove the streaming placeholder -- it will be replaced by the
        # final parsed response (or an error message).
        _remove_streaming_placeholder(state)

        if retcode == 0 and full_output:
            _parse_agent_response(full_output, state)
            state.agent_phase = "done"
            state.status = "Done."
        elif retcode != 0:
            error_text = full_output or f"Process exited with code {retcode}"
            # Append accumulated stderr for context
            if _accumulated_stderr:
                error_text += "\n" + "\n".join(_accumulated_stderr[-10:])
            _add_message(state, "error", error_text.strip())
            state.agent_phase = "error"
            state.status = f"Error (exit code {retcode})."
        else:
            _add_message(state, "error", "Agent returned empty response.")
            state.agent_phase = "error"
            state.status = "Error: empty response."

        state.is_running = False
        _process = None
        _timer_registered = False
        _cleanup_streaming_state()
        _tag_redraw()
        return None  # Unregister timer

    # ------------------------------------------------------------------
    # 6. Still running -- ensure phase is set and schedule next tick
    # ------------------------------------------------------------------
    if state.agent_phase == "idle":
        state.agent_phase = "thinking"
        state.status = "Thinking..."
    _tag_redraw()
    return _TIMER_INTERVAL


def _cleanup_streaming_state() -> None:
    """Reset all Phase 2 streaming state between runs."""
    global _streaming_msg_index, _seen_tool_calls, _accumulated_stderr
    _streaming_msg_index = -1
    _seen_tool_calls.clear()
    _accumulated_stderr.clear()


def _cleanup_approval_state(state) -> None:
    """Reset Phase 3 approval state."""
    global _pending_tool_calls, _pending_reply
    _pending_tool_calls.clear()
    _pending_reply = ""
    state.approval_pending = False


def _get_agent_state():
    """Safely get the agent state from the current scene."""
    try:
        return bpy.context.scene.bonsai_agent_state
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


class BONSAI_AI_OT_agent_send(bpy.types.Operator):
    """Send a message to the bim_operator agent"""

    bl_idname = "bonsai_ai.agent_send"
    bl_label = "Send to Agent"
    bl_description = "Send the current message to the bim_operator OpenClaw agent"

    def execute(self, context):
        global _process, _reader_thread, _stderr_thread, _timer_registered
        global _accumulated_stdout

        state = context.scene.bonsai_agent_state
        user_text = state.input_text.strip()

        if not user_text:
            self.report({"WARNING"}, "Message is empty.")
            return {"CANCELLED"}

        if state.is_running:
            self.report({"WARNING"}, "Agent is already running. Stop it first or wait.")
            return {"CANCELLED"}

        # Find openclaw binary
        openclaw_bin = _find_openclaw()
        if not openclaw_bin:
            self.report(
                {"ERROR"},
                "Cannot find 'openclaw' in PATH. Install OpenClaw or set the path.",
            )
            return {"CANCELLED"}

        # Record user message
        _add_message(state, "user", user_text)
        state.input_text = ""

        # Build agent command
        full_message = _build_agent_message(user_text)
        cmd = [
            openclaw_bin,
            "agent",
            "--agent", "bim_operator",
            "--message", full_message,
            "--json",
            "--timeout", str(_OPENCLAW_TIMEOUT),
        ]

        # Spawn subprocess
        try:
            env = os.environ.copy()
            # Ensure common paths are in PATH for macOS Blender
            path_dirs = env.get("PATH", "")
            for extra in ("/opt/homebrew/bin", "/usr/local/bin", os.path.expanduser("~/.local/bin")):
                if extra not in path_dirs:
                    path_dirs = extra + ":" + path_dirs
            env["PATH"] = path_dirs

            _process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=os.path.expanduser("~"),
            )
            global _process_start_time
            _process_start_time = time.time()
        except Exception as exc:
            _add_message(state, "error", f"Failed to start agent: {exc}")
            state.agent_phase = "error"
            state.status = f"Error: {exc}"
            return {"CANCELLED"}

        # Clear accumulated stdout and Phase 2 streaming state
        _accumulated_stdout.clear()
        _cleanup_streaming_state()

        # Drain old queues
        while not _stdout_queue.empty():
            try:
                _stdout_queue.get_nowait()
            except queue.Empty:
                break
        while not _stderr_queue.empty():
            try:
                _stderr_queue.get_nowait()
            except queue.Empty:
                break

        # Start reader threads
        _reader_thread = threading.Thread(
            target=_reader_worker,
            args=(_process.stdout, _stdout_queue),
            daemon=True,
        )
        _reader_thread.start()

        _stderr_thread = threading.Thread(
            target=_reader_worker,
            args=(_process.stderr, _stderr_queue),
            daemon=True,
        )
        _stderr_thread.start()

        # Update state
        state.is_running = True
        state.agent_phase = "thinking"
        state.status = "Thinking..."

        # Register timer
        if not _timer_registered:
            bpy.app.timers.register(_poll_agent_process, first_interval=_TIMER_INTERVAL)
            _timer_registered = True

        _tag_redraw()
        return {"FINISHED"}


class BONSAI_AI_OT_agent_stop(bpy.types.Operator):
    """Stop the running agent process"""

    bl_idname = "bonsai_ai.agent_stop"
    bl_label = "Stop Agent"
    bl_description = "Terminate the running agent subprocess"

    def execute(self, context):
        global _process

        state = context.scene.bonsai_agent_state

        if _process is not None:
            try:
                _process.terminate()
                _process.wait(timeout=5)
            except Exception:
                try:
                    _process.kill()
                except Exception:
                    pass
            _process = None

        _remove_streaming_placeholder(state)
        _cleanup_streaming_state()
        _cleanup_approval_state(state)
        state.is_running = False
        state.agent_phase = "idle"
        state.status = "Cancelled."
        _add_message(state, "status", "Agent stopped by user.")
        _tag_redraw()
        return {"FINISHED"}


class BONSAI_AI_OT_agent_clear(bpy.types.Operator):
    """Clear the agent chat history"""

    bl_idname = "bonsai_ai.agent_clear"
    bl_label = "Clear Chat"
    bl_description = "Remove all messages from the agent chat history"

    def execute(self, context):
        state = context.scene.bonsai_agent_state

        if state.is_running:
            self.report({"WARNING"}, "Agent is running. Stop it before clearing.")
            return {"CANCELLED"}

        state.messages.clear()
        state.message_index = 0
        state.status = "Idle"
        state.agent_phase = "idle"
        _cleanup_approval_state(state)
        _tag_redraw()
        return {"FINISHED"}


class BONSAI_AI_OT_agent_select_element(bpy.types.Operator):
    """Select an object in the viewport by name and zoom to it"""

    bl_idname = "bonsai_ai.agent_select_element"
    bl_label = "Select Element"
    bl_description = "Select the named object in the 3D viewport and zoom to it"

    object_name: StringProperty()

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if obj is None:
            self.report({"WARNING"}, f"Object '{self.object_name}' not found.")
            return {"CANCELLED"}

        # Deselect all, then select and make active
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Zoom the 3D viewport to the selected object
        # We need a 3D View context for view_selected, so find one
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == "WINDOW":
                        with context.temp_override(
                            area=area, region=region
                        ):
                            bpy.ops.view3d.view_selected()
                        break
                break

        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Phase 3: Plan approval operators
# ---------------------------------------------------------------------------


class BONSAI_AI_OT_agent_approve(bpy.types.Operator):
    """Approve the pending plan and proceed with execution"""

    bl_idname = "bonsai_ai.agent_approve"
    bl_label = "Approve Plan"
    bl_description = "Approve the proposed plan and allow execution to proceed"

    def execute(self, context):
        global _pending_tool_calls, _pending_reply

        state = context.scene.bonsai_agent_state

        if not state.approval_pending:
            self.report({"WARNING"}, "No plan is pending approval.")
            return {"CANCELLED"}

        # Mark approved
        state.approval_pending = False
        _add_message(state, "status", "Plan approved.")

        # Show the held reply if any
        if _pending_reply:
            _add_message(state, "agent", _pending_reply)

        # Clear pending state
        _pending_tool_calls.clear()
        _pending_reply = ""

        state.agent_phase = "done"
        state.status = "Done (approved)."
        _tag_redraw()
        return {"FINISHED"}


class BONSAI_AI_OT_agent_reject(bpy.types.Operator):
    """Reject the pending plan and cancel execution"""

    bl_idname = "bonsai_ai.agent_reject"
    bl_label = "Reject Plan"
    bl_description = "Reject the proposed plan and discard it"

    def execute(self, context):
        global _pending_tool_calls, _pending_reply

        state = context.scene.bonsai_agent_state

        if not state.approval_pending:
            self.report({"WARNING"}, "No plan is pending approval.")
            return {"CANCELLED"}

        # Mark rejected
        state.approval_pending = False
        _add_message(state, "status", "Plan rejected by user.")

        # Clear pending state
        _pending_tool_calls.clear()
        _pending_reply = ""

        state.agent_phase = "idle"
        state.status = "Plan rejected."
        _tag_redraw()
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Phase 5: Floating quick prompt operator
# ---------------------------------------------------------------------------


class BONSAI_AI_OT_agent_quick_prompt(bpy.types.Operator):
    """Open a floating prompt dialog to quickly send a message to the agent"""

    bl_idname = "bonsai_ai.agent_quick_prompt"
    bl_label = "Ask Bonsai Agent"
    bl_description = (
        "Open a quick prompt dialog to send a message to the Bonsai AI agent "
        "(Cmd+K / Ctrl+K)"
    )
    bl_options = {"REGISTER", "INTERNAL"}

    prompt_text: StringProperty(
        name="",
        description="Type your message to the agent",
        default="",
    )

    def invoke(self, context, event):
        # Pre-fill with viewport context hint if nothing is selected,
        # otherwise leave blank for the user to type freely.
        self.prompt_text = ""
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Message:", icon="LIGHT_SUN")
        layout.prop(self, "prompt_text", text="", icon="NONE")

    def execute(self, context):
        user_text = self.prompt_text.strip()
        if not user_text:
            self.report({"INFO"}, "Empty message -- nothing sent.")
            return {"CANCELLED"}

        # Ensure the sidebar is open so the user can see the response
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.show_region_ui = True
                break

        # Put the text into the agent state and invoke the send operator,
        # exactly as if the user typed in the sidebar and clicked Send.
        state = context.scene.bonsai_agent_state
        state.input_text = user_text
        bpy.ops.bonsai_ai.agent_send()

        return {"FINISHED"}


# ---------------------------------------------------------------------------
# PropertyGroups
# ---------------------------------------------------------------------------


class BonsaiAgentMessage(bpy.types.PropertyGroup):
    """A single message in the agent chat history."""

    role: StringProperty(
        name="Role",
        description="Message role: user, agent, tool, plan, thinking, streaming, status, error",
        default="user",
    )
    content: StringProperty(
        name="Content",
        description="Text content of the message",
        default="",
    )
    tool_name: StringProperty(
        name="Tool Name",
        description="For tool messages, the name of the tool that was called",
        default="",
    )
    timestamp: StringProperty(
        name="Timestamp",
        description="ISO timestamp of the message",
        default="",
    )


class BonsaiAgentState(bpy.types.PropertyGroup):
    """Runtime state for the agent chat panel."""

    messages: CollectionProperty(type=BonsaiAgentMessage)
    message_index: IntProperty(name="Message Index", default=0)
    input_text: StringProperty(
        name="Message",
        description="Type your message to the agent",
        default="",
    )
    status: StringProperty(name="Status", default="Idle")
    agent_phase: StringProperty(
        name="Phase",
        description="Current agent lifecycle phase",
        default="idle",
    )
    show_thinking: BoolProperty(
        name="Show Thinking",
        description="Display the agent's reasoning steps",
        default=False,
    )
    is_running: BoolProperty(
        name="Is Running",
        description="Whether an agent subprocess is currently active",
        default=False,
    )
    # Phase 3: Plan approval
    require_approval: BoolProperty(
        name="Require Approval",
        description=(
            "When enabled, the agent pauses for approval before executing "
            "IFC model changes. Use this for sensitive projects"
        ),
        default=False,
    )
    approval_pending: BoolProperty(
        name="Approval Pending",
        description="A plan is awaiting user approval or rejection",
        default=False,
    )


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

# Icons per role
_ROLE_ICONS = {
    "user": "USER",
    "agent": "LIGHT_SUN",
    "tool": "TOOL_SETTINGS",
    "plan": "PRESET",            # Phase 3: proposed plan summary
    "thinking": "LIGHT_HEMI",
    "streaming": "TRACKING",     # Phase 2: live placeholder while response streams in
    "status": "INFO",
    "error": "ERROR",
}

# Phase icons for the status bar
_PHASE_ICONS = {
    "idle": "RADIOBUT_OFF",
    "thinking": "SORTTIME",
    "tool": "TOOL_SETTINGS",     # Phase 2: currently executing a tool
    "responding": "TRACKING",    # Phase 2: generating the response
    "approval": "PAUSE",         # Phase 3: awaiting user approval
    "acting": "PLAY",
    "done": "CHECKMARK",
    "error": "ERROR",
}


class BONSAI_AI_PT_agent(bpy.types.Panel):
    """Agent chat panel in the Bonsai AI sidebar tab."""

    bl_label = "Agent"
    bl_idname = "BONSAI_AI_PT_agent"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai AI"
    bl_order = 0  # Appear above the existing panel

    def draw(self, context):
        layout = self.layout
        state = context.scene.bonsai_agent_state

        # ---- Status bar ----
        phase_icon = _PHASE_ICONS.get(state.agent_phase, "QUESTION")
        status_row = layout.row(align=True)
        status_row.label(text=state.status, icon=phase_icon)

        # ---- Controls row ----
        ctrl_row = layout.row(align=True)
        ctrl_row.prop(state, "show_thinking", toggle=True, icon="HIDE_OFF")
        ctrl_row.prop(
            state, "require_approval", toggle=True,
            text="Approval", icon="LOCKED" if state.require_approval else "UNLOCKED",
        )
        ctrl_row.operator("bonsai_ai.agent_clear", text="Clear", icon="TRASH")

        layout.separator()

        # ---- Chat history ----
        messages = state.messages
        total = len(messages)
        start = max(0, total - _MAX_DISPLAY_MESSAGES)

        if total == 0:
            box = layout.box()
            box.label(text="No messages yet.", icon="INFO")
            col = box.column(align=True)
            col.label(text="Type a message below and click Send")
            col.label(text="to talk to the bim_operator agent.")
        else:
            for i in range(start, total):
                msg = messages[i]

                # Skip thinking messages if toggle is off
                if msg.role == "thinking" and not state.show_thinking:
                    continue

                icon = _ROLE_ICONS.get(msg.role, "DOT")

                # --- Phase 3: Plan message rendering ---
                if msg.role == "plan":
                    _draw_plan_message(layout, msg)
                    continue

                # Draw message block
                msg_box = layout.box()
                header = msg_box.row(align=True)

                # Role label
                if msg.role == "streaming":
                    # Phase 2: streaming placeholder shows as "Agent" with
                    # an animated-looking indicator
                    header.label(text="Agent ...", icon=icon)
                elif msg.role == "tool" and msg.tool_name:
                    role_label = f"Tool: {msg.tool_name}"
                    header.label(text=role_label, icon=icon)
                else:
                    role_label = msg.role.capitalize()
                    header.label(text=role_label, icon=icon)

                # For tool messages with a tool_name that might match an object,
                # add a select button
                if msg.role == "tool" and msg.tool_name:
                    # Try to extract an object name from the content
                    # Heuristic: look for quoted strings
                    _maybe_draw_select_button(header, msg.content)

                # Timestamp (small, right-aligned) -- skip for streaming placeholder
                if msg.timestamp and msg.role != "streaming":
                    ts_short = msg.timestamp[11:16] if len(msg.timestamp) > 16 else msg.timestamp
                    header.label(text=ts_short)

                # Content lines
                content_col = msg_box.column(align=True)
                if msg.role == "thinking":
                    content_col.enabled = False  # Dim the thinking text
                elif msg.role == "streaming":
                    content_col.enabled = True  # Keep streaming text visible

                wrapped = _wrap_text(msg.content)
                for line in wrapped:
                    if line:
                        content_col.label(text=line)
                    else:
                        content_col.separator(factor=0.5)

                # Phase 4: Element links for agent response messages
                if msg.role == "agent":
                    _draw_element_links(msg_box, msg.content)

        # ---- Phase 3: Approve / Reject buttons when pending ----
        if state.approval_pending:
            layout.separator()
            approval_box = layout.box()
            approval_box.label(text="Plan awaiting approval", icon="PAUSE")
            btn_row = approval_box.row(align=True)
            btn_row.scale_y = 1.4
            btn_row.operator(
                "bonsai_ai.agent_approve",
                text="Approve",
                icon="CHECKMARK",
            )
            btn_row.operator(
                "bonsai_ai.agent_reject",
                text="Reject",
                icon="CANCEL",
            )

        layout.separator()

        # ---- Input row ----
        input_row = layout.row(align=True)
        input_row.prop(state, "input_text", text="")

        if state.is_running:
            input_row.operator("bonsai_ai.agent_stop", text="", icon="CANCEL")
        else:
            input_row.operator("bonsai_ai.agent_send", text="", icon="PLAY")


def _draw_plan_message(layout, msg) -> None:
    """Draw a plan message with distinct visual styling.

    The plan content is a multi-line summary produced by ``_build_plan_summary``.
    The first line is the header, subsequent lines are numbered actions.

    Phase 4: Adds select buttons for elements referenced in the plan that
    already exist in the scene (e.g., host walls for doors/windows).
    """
    plan_box = layout.box()

    # Header row
    header = plan_box.row(align=True)
    header.label(text="Plan", icon="PRESET")
    if msg.timestamp:
        ts_short = msg.timestamp[11:16] if len(msg.timestamp) > 16 else msg.timestamp
        header.label(text=ts_short)

    content_col = plan_box.column(align=True)

    lines = msg.content.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            content_col.separator(factor=0.3)
            continue

        # The header line (e.g., "Proposed Plan (3 actions):")
        if stripped.startswith("Proposed Plan"):
            content_col.label(text=stripped, icon="NONE")
            continue

        # Numbered action lines -- wrap them for sidebar width
        # They start with a number like "1. create_wall: ..."
        wrapped = _wrap_text(stripped, width=_WRAP_CHARS - 2)
        for i, wl in enumerate(wrapped):
            if wl:
                # First line gets the wrench icon, continuation lines are indented
                if i == 0:
                    row = content_col.row(align=True)
                    row.label(text=wl, icon="TOOL_SETTINGS")
                else:
                    row = content_col.row(align=True)
                    row.label(text="    " + wl)

        # Phase 4: Add select buttons for existing objects referenced in
        # this action line (e.g., host walls like 'in "North Wall"')
        _draw_plan_line_element_links(content_col, stripped)


def _maybe_draw_select_button(layout_row, content: str) -> None:
    """If the tool call content contains a quoted name, add a select button."""
    # Simple heuristic: find first quoted string
    match = re.search(r'"([^"]+)"', content)
    if match:
        name = match.group(1)
        # Only show button if there's a matching Blender object
        if bpy.data.objects.get(name):
            op = layout_row.operator(
                "bonsai_ai.agent_select_element",
                text="",
                icon="RESTRICT_SELECT_OFF",
            )
            op.object_name = name


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_CLASSES = (
    BonsaiAgentMessage,
    BonsaiAgentState,
    BONSAI_AI_OT_agent_send,
    BONSAI_AI_OT_agent_stop,
    BONSAI_AI_OT_agent_clear,
    BONSAI_AI_OT_agent_select_element,
    BONSAI_AI_OT_agent_approve,      # Phase 3
    BONSAI_AI_OT_agent_reject,       # Phase 3
    BONSAI_AI_OT_agent_quick_prompt, # Phase 5
    BONSAI_AI_PT_agent,
)

_agent_keymaps: list = []


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bonsai_agent_state = bpy.props.PointerProperty(
        type=BonsaiAgentState
    )

    # Keyboard shortcut: Cmd+K / Ctrl+K to open the floating quick prompt
    # (Phase 5: replaces the old sidebar toggle with a command-palette-style
    # dialog that sends directly to the agent)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        # Cmd+K (macOS) -- floating quick prompt
        kmi = km.keymap_items.new(
            "bonsai_ai.agent_quick_prompt",
            "K",
            "PRESS",
            oskey=True,
        )
        _agent_keymaps.append((km, kmi))

        # Ctrl+K (Linux/Windows) -- floating quick prompt
        kmi = km.keymap_items.new(
            "bonsai_ai.agent_quick_prompt",
            "K",
            "PRESS",
            ctrl=True,
        )
        _agent_keymaps.append((km, kmi))


def unregister() -> None:
    # Unregister keymaps
    for km, kmi in _agent_keymaps:
        km.keymap_items.remove(kmi)
    _agent_keymaps.clear()

    # Kill any running process
    global _process
    if _process is not None:
        try:
            _process.terminate()
            _process.wait(timeout=2)
        except Exception:
            try:
                _process.kill()
            except Exception:
                pass
        _process = None

    # Unregister timer if active
    global _timer_registered
    if _timer_registered:
        try:
            bpy.app.timers.unregister(_poll_agent_process)
        except Exception:
            pass
        _timer_registered = False

    # Clean up Phase 2 streaming state
    _cleanup_streaming_state()

    # Clean up Phase 3 approval state (module-level only)
    global _pending_tool_calls, _pending_reply
    _pending_tool_calls.clear()
    _pending_reply = ""

    # Remove property
    try:
        del bpy.types.Scene.bonsai_agent_state
    except Exception:
        pass

    # Unregister classes
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
