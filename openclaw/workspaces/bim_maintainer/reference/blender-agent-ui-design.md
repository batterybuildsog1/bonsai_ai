# Blender Agent UI Design -- Bonsai AI

## Overview

This document specifies the design for an agent chat panel within the Bonsai AI
Blender addon. The panel provides a conversational interface to the
`bim_operator` OpenClaw agent, allowing users to type natural-language prompts
and see agent responses, tool calls, and status updates directly inside Blender's
3D View sidebar.

---

## 1. Architecture

### Integration with the existing addon

The agent panel is a **new file** (`agent_panel.py`) that registers its own
classes alongside the existing `ui.py` classes. It does not modify or replace
any existing panels -- the original `BONSAI_AI_PT_panel` remains as-is for
bridge jobs, legacy planning, review controls, and provider settings.

```
bonsai_ai_blender/
  __init__.py          -- imports register/unregister from ui.py (unchanged)
  ui.py                -- existing panel; updated only to import + register agent_panel
  agent_panel.py       -- NEW: agent chat panel, operators, properties, timer
  integration.py       -- unchanged
  client.py            -- unchanged
  runtime.py           -- unchanged
  presentation.py      -- unchanged
```

### Dependency chain

```
__init__.py
  -> ui.py register()
       -> agent_panel.register()   (called at the end of ui.register)
       -> agent_panel.unregister() (called at the start of ui.unregister)
```

### No new Python dependencies

The agent panel uses only stdlib modules (`subprocess`, `threading`, `queue`,
`json`, `textwrap`, `shutil`) and `bpy`. It does not import any third-party
packages.

---

## 2. UI Layout

### Where it lives

The agent panel lives in the **same sidebar tab** (`Bonsai AI`) as the existing
panel. It registers as `BONSAI_AI_PT_agent` and appears **above** the existing
panel (controlled by `bl_order`).

### Panel structure (top to bottom)

```
+-------------------------------------------+
| Bonsai AI Agent                       [-] |
+-------------------------------------------+
| Status: Idle                              |
+-------------------------------------------+
| [Show Thinking]  [Clear Chat]             |
+-------------------------------------------+
|                                           |
| -- Chat History (UIList) --               |
|                                           |
| You:                                      |
|   Create a 10m x 8m slab at ground       |
|   level with 4m exterior walls            |
|                                           |
| Agent:                                    |
|   I'll create the slab and walls.         |
|   Planning 5 actions...                   |
|                                           |
| [tool] create_rect_slab "Ground Slab"     |
| [tool] create_wall "North Wall"           |
| [tool] create_wall "South Wall"           |
| [tool] create_wall "East Wall"            |
| [tool] create_wall "West Wall"            |
|                                           |
| Agent:                                    |
|   Done. Created 5 elements on the         |
|   ground storey.                          |
|                                           |
+-------------------------------------------+
| [________________________] [Send] [Stop]  |
+-------------------------------------------+
```

### ASCII mockup -- collapsed thinking

When "Show Thinking" is off, `[thinking]` lines are hidden. When on, they
appear as dimmed labels between the agent's response lines.

### ASCII mockup -- plan approval mode (Phase 3, implemented)

```
+-------------------------------------------+
| Plan                              14:32   |
+-------------------------------------------+
| Proposed Plan (5 actions):                |
|   1. create_rectangular_slab:             |
|      "Ground Slab" on Level 0             |
|      -- 10.0m x 8.0m, 0.15m thick        |
|   2. create_wall: "North Wall"            |
|      on Level 0 -- 10.0m long,            |
|      4.0m high, 0.2m thick               |
|   3. create_wall: "South Wall" ...        |
|   4. create_wall: "East Wall" ...         |
|   5. create_wall: "West Wall" ...         |
+-------------------------------------------+
| Plan awaiting approval                    |
| [  Approve  ]  [  Reject  ]              |
+-------------------------------------------+
```

Plan approval mode is controlled by the "Approval" toggle in the controls row.
When OFF (default), plans are displayed but executed immediately. When ON,
execution pauses and the user must click Approve or Reject.

Design rationale: agents should be able to kick off work without gating. The
approval gate is specifically for editing existing user projects, not for agents
building their own work. So it is available but not blocking by default.

---

## 3. Communication Pattern

### Subprocess approach

The agent panel spawns `openclaw agent` as a subprocess:

```
openclaw agent --agent bim_operator --message "<user prompt>" --json --timeout 300
```

This is the simplest integration:
- No need for a running bridge server
- No WebSocket complexity
- The `openclaw` CLI is already installed and in PATH
- `--json` returns structured output that can be parsed

### Passing viewport context

Before spawning the subprocess, the panel gathers:
- Currently selected objects and their IFC element metadata
- Active IFC file path (from `bonsai_ai_last_ifc_path` scene property)
- Current storey/spatial context

This context is prepended to the user's message so the agent knows what the
user is looking at.

### Process lifecycle

```
User clicks Send
  -> Operator validates input
  -> Stores message in chat history CollectionProperty
  -> Spawns subprocess via subprocess.Popen (stdout=PIPE, stderr=PIPE)
  -> Stores Popen handle in module-level variable
  -> Registers bpy.app.timers callback (0.25s interval)
  -> Sets status to "Thinking..."

Timer fires every 0.25s
  -> Checks if subprocess has finished (poll())
  -> If not finished: reads any available stdout lines from a reader thread
  -> Updates status with latest line (streaming status)
  -> If finished: reads all remaining output
  -> Parses JSON response
  -> Appends agent response to chat history
  -> Sets status to "Done" / "Error"
  -> Unregisters timer
  -> Tags UI region for redraw
```

### Thread-safe stdout reading

Since Blender's Python is not thread-safe, we use a background thread that
reads subprocess stdout line-by-line into a `queue.Queue`. The timer callback
drains the queue on the main thread. This avoids blocking Blender's UI.

```python
def _reader_thread(pipe, queue):
    for line in iter(pipe.readline, b''):
        queue.put(line.decode('utf-8', errors='replace'))
    pipe.close()
```

---

## 4. Streaming Status

### Status levels

| Status      | UI display                                    |
|-------------|-----------------------------------------------|
| idle        | "Idle" (dimmed)                               |
| thinking    | "Thinking..." with spinner icon               |
| acting      | "Executing: create_wall 'North Wall'"         |
| done        | "Done. Created 5 elements."                   |
| error       | "Error: <message>" (alert icon)               |
| cancelled   | "Cancelled by user."                          |

### How streaming works in V1

In V1, we don't parse streaming tokens. Instead:
1. While the subprocess runs, status shows "Thinking..."
2. Any stdout lines that look like status updates are shown in real-time
3. When the process completes, the full JSON response is parsed
4. Tool calls are extracted and displayed as separate chat entries

### Phase 2 streaming (implemented)

Phase 2 implements line-by-line subprocess streaming rather than SSE.
The timer callback extracts partial content from stdout using regex
patterns for known JSON keys (`"thinking"`, `"reply"`, etc.) and displays
it in a "streaming" placeholder message that updates each tick. Tool calls
are detected from stderr in real-time.

### Future: SSE streaming

The OpenClaw gateway supports Server-Sent Events. A future version could use
`urllib.request` to poll an SSE endpoint, or use a thread with `http.client`
to consume the stream. This would enable token-by-token display.

---

## 5. State Management

### PropertyGroups

```python
class BonsaiAgentMessage(bpy.types.PropertyGroup):
    role: StringProperty()      # "user", "agent", "tool", "thinking", "status", "error"
    content: StringProperty()   # The text content
    tool_name: StringProperty() # For role="tool": the tool function name
    timestamp: StringProperty() # ISO timestamp

class BonsaiAgentState(bpy.types.PropertyGroup):
    messages: CollectionProperty(type=BonsaiAgentMessage)
    message_index: IntProperty()
    input_text: StringProperty()
    status: StringProperty(default="Idle")
    agent_phase: StringProperty(default="idle")  # idle/thinking/acting/done/error
    show_thinking: BoolProperty(default=False)
    is_running: BoolProperty(default=False)
```

### Module-level state (not serialized)

```python
_process: subprocess.Popen | None = None
_stdout_queue: queue.Queue | None = None
_reader_thread: threading.Thread | None = None
```

These are intentionally not stored in Blender properties because they are
transient runtime handles.

### Chat history persistence

Messages are stored in `bpy.types.Scene.bonsai_agent_state.messages`
(a CollectionProperty). This means:
- History survives panel redraws and area changes
- History is lost on file close (CollectionProperty is not saved to .blend
  unless it's on an ID type, and even then custom PropertyGroups have limits)
- For true persistence, we could serialize to a `bpy.data.texts` block, but
  that's a V2 concern

---

## 6. Chat Display Strategy

### UIList vs. direct labels

**Decision: use direct labels in a box, not UIList.**

Rationale:
- UIList requires a fixed-height item draw and is designed for homogeneous
  lists (vertex groups, materials). Chat messages vary wildly in length.
- UIList scrolls, but the scroll behavior is per-item, not per-pixel.
- For chat, we want the panel to scroll naturally with the sidebar scroll.
- Multiple `layout.label()` calls with manual text wrapping are simpler and
  give us full control over styling (icons, indentation, dimming).

### Text wrapping

Blender's `layout.label()` does not wrap text. We implement a helper:

```python
def _wrap_text(text, width_chars=60):
    """Split text into lines that fit the sidebar panel width."""
    import textwrap
    lines = []
    for paragraph in text.split('\n'):
        if paragraph.strip():
            lines.extend(textwrap.wrap(paragraph, width=width_chars))
        else:
            lines.append('')
    return lines
```

The `width_chars` is estimated at ~60 for a standard sidebar width. A more
precise calculation uses `context.region.width` and an empirical
characters-per-pixel ratio (~7px per character at default DPI).

### Role-based formatting

| Role     | Icon            | Style              |
|----------|-----------------|--------------------|
| user     | USER            | Bold-ish label     |
| agent    | LIGHT_SUN       | Normal label       |
| tool     | TOOL_SETTINGS   | Indented, monospace-ish |
| plan     | PRESET          | Box with numbered actions, wrench icons (Phase 3) |
| thinking | LIGHT_HEMI      | Dimmed, only if show_thinking |
| streaming| TRACKING        | Live placeholder while response streams (Phase 2) |
| error    | ERROR           | Red alert label    |
| status   | INFO            | Italic-ish label   |

Blender doesn't support bold/italic in labels, but we use icons and
indentation (via `row.separator()` or nested `col.box()`) to create
visual hierarchy.

---

## 7. Implementation Plan

### Phase 1 (this PR) -- Minimum Viable Agent Panel

1. Create `agent_panel.py` with:
   - `BonsaiAgentMessage` PropertyGroup
   - `BonsaiAgentState` PropertyGroup
   - `BONSAI_AI_PT_agent` Panel (draws chat history + input)
   - `BONSAI_AI_OT_agent_send` Operator (spawns subprocess)
   - `BONSAI_AI_OT_agent_stop` Operator (kills subprocess)
   - `BONSAI_AI_OT_agent_clear` Operator (clears chat history)
   - Timer callback for polling subprocess
   - Text wrapping helper
   - Viewport context gatherer

2. Modify `ui.py`:
   - Import `agent_panel`
   - Call `agent_panel.register()` in `register()`
   - Call `agent_panel.unregister()` in `unregister()`
   - Add Cmd+K / Ctrl+K keymap for focusing agent input

### Phase 2 (implemented) -- Streaming + Tool Visibility

Implemented as subprocess line-by-line streaming (not SSE). Changes to
`agent_panel.py`:

1. **Streaming placeholder message**: When the agent process is running,
   a "streaming" role message is created and updated every 250ms tick with
   partial content extracted from accumulated stdout. When the process
   finishes, the placeholder is removed and replaced with the final parsed
   response from `_parse_agent_response()`. Falls back cleanly to Phase 1
   behaviour if no partial content is detected (e.g. single-JSON-blob mode).

2. **Real-time tool call display from stderr**: New helpers
   `_parse_stderr_for_tools()` and `_detect_phase_from_stderr()` scan each
   stderr line for patterns like `[tool] memory_search ...` or
   `Running tool: read /path`. Detected tool calls are immediately added
   as "tool" messages with a wrench emoji prefix. Deduplication prevents
   the same tool+args from appearing twice.

3. **Phase indicator**: `agent_phase` now cycles through four active states:
   - `"thinking"` -- agent is reasoning (detected from stderr keywords)
   - `"tool"` -- agent is executing a tool call (detected from stderr)
   - `"responding"` -- agent is generating text output (detected from stdout
     content or stderr keywords)
   - `"idle"` / `"done"` / `"error"` -- terminal states (unchanged)

   New entries in `_PHASE_ICONS`: `"tool"` (TOOL_SETTINGS) and
   `"responding"` (TRACKING).

4. **New role `"streaming"`**: Added to `_ROLE_ICONS` and handled in the
   `draw()` method. The streaming message shows as "Agent ..." with the
   TRACKING icon and no timestamp. It is removed when the process completes.

5. **Cleanup**: `_cleanup_streaming_state()` resets all Phase 2 transient
   state (`_streaming_msg_index`, `_seen_tool_calls`, `_accumulated_stderr`)
   and is called from the send operator, stop operator, and unregister.

6. **Backward-compatible**: The `--json` flag is kept. If openclaw outputs
   a single JSON blob with no streaming signals, the timer simply waits
   for completion and parses the result exactly as Phase 1 did.

### Phase 3 (implemented) -- Plan Approval

Implemented in `agent_panel.py`. Tool calls from the agent JSON response are
now rendered as a human-readable plan instead of raw JSON.

1. **`_format_tool_call(name, args)`**: Converts raw tool call arguments into
   readable one-liners. Knows about all BIM tools from `tool_specs.py`:
   - `create_wall`: computes length from start/end coordinates, shows height
     and thickness in meters
   - `create_rectangular_slab`: shows length x width and thickness
   - `create_door` / `create_window`: shows host wall name and dimensions
   - `create_column`, `create_beam`, `create_panel`, `create_footing`,
     `create_curtain_wall`: shows relevant dimensions
   - `ensure_project`, `ensure_storey`: shows project/site/building or elevation
   - Unknown tools: compact JSON summary with metadata keys stripped

2. **`_build_plan_summary(tool_calls)`**: Produces a numbered plan like:
   ```
   Proposed Plan (3 actions):
     1. create_wall: "South Wall" on Level 0 -- 20.0m long, 4.0m high, 0.2m thick
     2. create_wall: "East Wall" on Level 0 -- 15.0m long, 4.0m high, 0.2m thick
     3. create_door: "Main Entry" in "North Wall" -- 1.2m x 2.4m
   ```

3. **New message role `"plan"`**: Added to `_ROLE_ICONS` (PRESET icon).
   Rendered via `_draw_plan_message()` with distinct box styling: header row
   with "Plan" label, numbered action lines with wrench icons, text wrapping
   for sidebar width.

4. **Approval toggle**: `require_approval` BoolProperty on `BonsaiAgentState`.
   Shown in the controls row as a lock/unlock toggle labeled "Approval".
   - When OFF (default): plan is displayed but execution continues immediately
   - When ON: plan is displayed, `approval_pending` is set, agent phase
     becomes `"approval"`, and execution pauses

5. **Approve / Reject operators**:
   - `BONSAI_AI_OT_agent_approve`: clears pending state, shows held reply,
     sets phase to "done"
   - `BONSAI_AI_OT_agent_reject`: clears pending state, adds "rejected"
     status message, returns to idle

6. **Approval buttons**: When `approval_pending` is True, a prominent box
   with "Approve" (checkmark) and "Reject" (cancel) buttons appears below
   the chat history, above the input row. Buttons are scaled 1.4x for
   visibility.

7. **Cleanup**: `_cleanup_approval_state()` resets `_pending_tool_calls`,
   `_pending_reply`, and `approval_pending`. Called from stop, clear, and
   the approve/reject operators.

8. **Design philosophy**: The approval gate is available but NOT blocking by
   default. Agents can kick off work freely. The gate is for sensitive
   projects where the user explicitly enables "Require Approval".

### Phase 4 (implemented) -- Element Linking

When the agent mentions IFC elements by name in its responses, users can click
to select and zoom to those elements in the 3D viewport.

1. **`_find_element_names_in_text(text)`**: Scans message text for substrings
   that match `bpy.data.objects` names. Uses word-boundary-like matching to
   avoid false positives, sorts candidates longest-first for specificity, and
   skips names shorter than 3 characters. Returns up to 5 unique matches.

2. **`_draw_element_links(layout, text)`**: Called after rendering agent message
   content. For each detected element name, draws a compact select button row
   (`scale_y=0.85`) with the `RESTRICT_SELECT_OFF` icon. Buttons invoke
   `BONSAI_AI_OT_agent_select_element` with the matched object name.

3. **`_draw_plan_line_element_links(layout, line)`**: Called per plan action
   line inside `_draw_plan_message()`. Extracts quoted strings from the line
   and adds select buttons for any that correspond to existing scene objects.
   This is useful for host references (e.g., `in "North Wall"` when the wall
   already exists).

4. **Select operator zoom**: `BONSAI_AI_OT_agent_select_element` now zooms
   the viewport to the selected object via `bpy.ops.view3d.view_selected()`,
   using `context.temp_override` to target the correct 3D View area.

5. **Integration points**:
   - Agent messages (`role == "agent"`): `_draw_element_links()` is called
     on the message box after content labels
   - Plan messages (`role == "plan"`): each action line gets
     `_draw_plan_line_element_links()` after its wrapped text
   - Tool messages (`role == "tool"`): existing `_maybe_draw_select_button()`
     (from Phase 1) still handles header-row select buttons

6. **Design philosophy**: Element links are subtle -- slightly smaller than
   normal buttons, placed below message content rather than inline. Limited
   to 5 per message to avoid UI clutter. Only objects that actually exist
   in `bpy.data.objects` are shown; names that appear in text but have no
   corresponding scene object are silently skipped.

### Phase 5 (implemented) -- Floating Cmd+K Quick Prompt

Cmd+K (macOS) / Ctrl+K (Linux/Windows) now opens a floating prompt dialog
instead of toggling the sidebar. This is a command-palette-style input for
quickly sending a message to the agent without opening the full sidebar.

1. **`BONSAI_AI_OT_agent_quick_prompt` operator**: Uses Blender's native
   `invoke_props_dialog(self, width=420)` to display a centered floating
   dialog titled "Ask Bonsai Agent". Contains a single `StringProperty` text
   field where the user types their message. OK / Enter sends; Escape cancels.

2. **Send flow**: On execute, the operator sets `state.input_text` to the
   prompt text and calls `bpy.ops.bonsai_ai.agent_send()` -- reusing the
   exact same send pipeline from Phase 1. No duplication of subprocess logic.

3. **Auto-open sidebar**: After sending, the operator ensures the sidebar is
   visible (`area.spaces.active.show_region_ui = True`) so the user can
   see the streamed response, tool calls, and plan approval UI.

4. **Keymap update**: The Cmd+K / Ctrl+K keymaps now invoke
   `bonsai_ai.agent_quick_prompt` instead of `wm.context_toggle`. The old
   sidebar toggle is no longer bound to a shortcut but remains accessible
   via Blender's standard N-key sidebar toggle or the panel header.

5. **Backward-compatible**: All Phase 1-4 functionality is unchanged. The
   quick prompt simply provides another entry point into the same send flow.

### Phase 6 (implemented) -- Selection-Aware Agent Queries

When the user selects IFC elements in the 3D viewport, the agent now receives
rich semantic context instead of bare object names. This lets the agent reason
about element types, dimensions, materials, and spatial relationships without
needing to run extra tool calls.

1. **`_ifc_context_for_object(obj)`**: New helper that resolves a Blender
   object to its IFC entity via `bonsai.tool.Ifc.get_entity()` and extracts
   concise metadata:
   - IFC class (e.g., `IfcWall`, `IfcSlab`, `IfcColumn`)
   - Spatial container / storey name via `ifcopenshell.util.element.get_container()`
   - Key dimensions from `Pset_BonsaiAI`: `Length`, `Width`, `Height`,
     `Thickness` -- formatted with human-readable units
   - Material reference (`MaterialRef`)
   - Semantic role (from `Role` key or nested `semantics.role`)
   - System name (from `semantics.system_name`)
   Returns `None` for non-IFC objects, allowing graceful fallback.

2. **Enhanced `_viewport_context_string()`**: Now calls
   `_ifc_context_for_object()` for each selected object (up to 10).  If IFC
   data is available, the output looks like:
   ```
   [Viewport context]
   Active IFC: /path/to/model.ifc
   Selected: Wall-South-001 (IfcWall)
     Storey: Level 0
     Dims: 20 m long, 4 m high, 0.2 m thick
     Material: concrete_default
     Role: envelope
   Active object: Wall-South-001
     Location: (0.00, 0.00, 0.00)
   ```
   For non-IFC objects the output falls back to plain names (Phase 1 behavior).

3. **Lazy imports**: `bonsai.tool` and `ifcopenshell.util.element` are imported
   inside `_ifc_context_for_object()` within a `try/except`. If either module
   is unavailable (IfcOpenShell not installed, Bonsai not active), the helper
   returns `None` and the function falls back silently.

4. **Context budget**: The enriched context is kept concise (~5-8 lines per
   selected element) to avoid bloating the agent prompt. Only the most useful
   properties are extracted; full property set dumps are avoided.

5. **Backward-compatible**: No changes to `_build_agent_message()` or any
   other function. The enriched context is purely additive -- it replaces plain
   object names with richer descriptions when available.

---

## 8. Known Limitations

### Blender UI constraints

1. **No rich text** -- all display uses `layout.label()` which is plain text
   only. No markdown, no code highlighting, no hyperlinks.

2. **No scrollable sub-regions in panels** -- the entire sidebar scrolls, but
   we cannot create a scrollable area within a panel. Long chat histories
   will make the panel very tall. Mitigation: limit displayed messages to the
   last N (e.g., 50) and provide a "Show More" button.

3. **No inline text input** -- `layout.prop()` with a StringProperty creates
   a text field, but it's a single line. Multi-line input requires the Text
   Editor. Mitigation: single-line input is fine for V1; for longer prompts,
   users can use the existing Quick Prompt dialog.

4. **No async in draw()** -- the draw method must be synchronous and fast.
   All async work happens via timers and threads.

5. **Fixed-width estimation** -- text wrapping uses an estimated character
   width. At non-default DPI or with wide sidebars, wrapping may be imperfect.

### Agent limitations

1. **No session continuity** -- each `openclaw agent` invocation is a single
   turn. Multi-turn context requires passing conversation history in the
   message, which is limited by token budget. Future: use `--session-id` to
   maintain a session.

2. **Plan approval is opt-in** -- the approval gate must be explicitly enabled
   via the "Approval" toggle. When off (default), the agent runs to completion.
   If it makes mistakes, the user must undo and retry. (Phase 3 implemented
   the approval mechanism; future work could add plan editing.)

3. **Subprocess startup cost** -- spawning `openclaw agent` has overhead
   (~1-2s). This is acceptable for V1 but could be improved with a persistent
   gateway connection.

### Platform notes

- `openclaw` must be in PATH. On macOS, Blender may not inherit the shell
  PATH. Mitigation: use `shutil.which('openclaw')` and fall back to
  common install locations (`/opt/homebrew/bin/openclaw`,
  `/usr/local/bin/openclaw`).

- Subprocess output encoding assumes UTF-8. This should be fine on all
  modern systems.

---

## 9. File Inventory

| File | Action | Description |
|------|--------|-------------|
| `bonsai_ai_blender/agent_panel.py` | CREATE | Agent chat panel, operators, state, timer |
| `bonsai_ai_blender/ui.py` | MODIFY | Import + register agent_panel; add Cmd+K keymap |
| `bonsai_ai_blender/__init__.py` | NO CHANGE | Already imports from ui.py |
