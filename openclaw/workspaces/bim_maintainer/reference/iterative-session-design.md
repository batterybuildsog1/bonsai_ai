# Iterative Session Design for BIM Model Generation

**Date:** 2026-03-31
**Status:** Research complete, design ready for implementation

---

## 1. Problem Statement

The current phased planner (`phased_planner.py`) fires independent `openclaw agent` subprocess calls for each phase. Each call starts a fresh context: the agent sees only its workspace files (AGENTS.md, SOUL.md, TOOLS.md, etc.) plus the prompt. There is no conversation memory between phases. This causes:

- **Spatial misalignment**: The column grid phase places columns at origin (0,0), but the slab phase independently guesses a center-based origin at (20, 12.5), because it has no memory of what the structure phase decided.
- **Missing envelope/openings**: The openings phase does not know which walls exist because it only sees a scene summary string, not the full conversation context of design decisions.
- **No error correction between phases**: If phase N produces a mistake, phase N+1 cannot reference why or how to compensate.

The iterative session approach solves this by maintaining a single conversation thread with the agent across all phases.

---

## 2. Research Findings

### 2.1 Session Persistence (Confirmed Working)

OpenClaw sessions are fully persistent. Key findings from live testing:

**Session storage:**
- Sessions are stored as JSONL files at `~/.openclaw/agents/<agent_id>/sessions/<session_uuid>.jsonl`
- The JSONL contains every message (user and assistant), thinking blocks, model changes, and tool calls
- A session index lives at `~/.openclaw/agents/<agent_id>/sessions/sessions.json`

**Session-id behavior:**
- `--session-id <custom-id>` maps to the agent's default session key (`agent:bim_operator:main`)
- The custom session-id is stored in the session index but the JSONL file uses a UUID filename
- Subsequent calls with the same `--session-id` resume the same conversation thread
- The full conversation history is replayed to the model on each turn

**Context window:**
- bim_operator is configured with `contextTokens: 200000` (200K)
- System prompt (workspace files + skills + tools) consumes ~31K chars (~15K tokens)
- Current bim_operator session is at ~153K tokens (from prior work)
- Cache read behavior confirmed: turn 2 showed `cacheRead: 152960` tokens, meaning only the new message tokens were charged as input

**Session lifetime:**
- No automatic expiration observed
- Sessions persist until explicitly cleaned via `openclaw sessions cleanup --enforce`
- The compaction system (`mode: "safeguard"`) will flush memories to disk when context approaches the limit, with a `reserveTokensFloor: 20000`

### 2.2 Live Test Results

**Turn 1** (12.8s, 153K total tokens):
```
Message: "Generate storeys for a 5-story building..."
Response: {"actions":[{"type":"ensure_storey","name":"Ground Floor","elevation":0.0}, ...]}
```
- Agent returned clean JSON with 5 ensure_storey actions
- All elevations correct: 0.0, 4.5, 8.5, 12.5, 16.5

**Turn 2** (7.6s, 153K total tokens, 152K cache read):
```
Message: "Storeys are created. Now add a column grid at origin (0,0)..."
Response: {"actions":[{"type":"generate_column_grid","name":"Ground Floor Column Grid",...}]}
```
- Agent remembered the storey names from turn 1 (used "Ground Floor" without being told)
- Used generate_column_grid parametric generator correctly
- Cache hit confirmed: only 374 new input tokens charged

**Key insight**: The agent retains full context between turns. Turn 2's response referenced storey names established in turn 1 without re-prompting them.

### 2.3 Cost Analysis

With cached sessions, the per-turn cost structure is:

| Component | Tokens | Notes |
|-----------|--------|-------|
| System prompt | ~15K | Cached after first call |
| Conversation history | ~1-5K per turn | Cached from previous turns |
| New message | ~100-500 | Only fresh input tokens |
| Response | ~100-500 | Output tokens per phase |

For a 6-phase building (storeys, structure per floor, envelope, openings), estimated total: ~160K tokens with ~95% cache hits after turn 1. This is comparable to the current phased planner's total but with the critical benefit of conversational memory.

---

## 3. Architecture

### 3.1 Current Architecture (phased_planner.py)

```
user prompt
  |
  v
_plan_phases() ---[openclaw agent]---> phase list (JSON)
  |
  v
for each phase:
    _build_execution_prompt() ---> focused prompt (~1000 chars)
    _call_openclaw()          ---[openclaw agent, NEW session]---> actions JSON
    _extract_json()           ---> parsed actions
    compile_core_plan()       ---> compiled primitives
    author.apply_tool_call()  ---> IFC mutations
    author.scene_summary()    ---> scene summary for next phase
```

Problems:
- Each `_call_openclaw()` is a **new conversation** with no memory of prior phases
- Scene summary is a compressed text string, not the full context of decisions
- No way for the agent to correct mistakes from previous phases

### 3.2 Proposed Architecture (iterative_planner.py)

```
user prompt
  |
  v
session_id = f"build-{project}-{timestamp}"
author = IfcAuthor(output_path)
  |
  v
Turn 0: Planning decomposition (same session)
  _call_openclaw(session_id, decomposition_prompt) ---> phase list
  |
  v
for each phase:
    scene = author.scene_summary()
    result_report = format_execution_report(last_phase_results)
    prompt = f"{result_report}\n\nScene: {scene}\n\nNow generate {phase.name}..."
    |
    _call_openclaw(session_id, prompt) ---> actions JSON
    _extract_json()   ---> parsed actions
    _normalize_actions()
    compile_core_plan()
    |
    for each action:
        author.apply_tool_call()  ---> IFC mutations (track success/failure)
    |
    scene = author.scene_summary()  # refresh for next turn
  |
  v
Optional: Turn N+1: Verification / correction turn
  _call_openclaw(session_id, f"Build complete. Final scene:\n{scene}\nAny issues?")
  |
  v
author.save()
```

Key differences:
1. **Single session-id** across all turns -- the agent accumulates context
2. **Execution reports** fed back as user messages -- the agent knows what succeeded/failed
3. **Scene summary** injected into each turn -- the agent sees concrete model state
4. **Correction turns** possible -- if something looks wrong, ask the agent to fix it

### 3.3 Turn Protocol

Each orchestrator turn follows this protocol:

```
ORCHESTRATOR -> AGENT:
  "[Phase result] {N} actions applied, {M} errors.
   Errors: [list if any]

   Scene: {scene_summary}

   Now generate the {PHASE_NAME} phase.
   Constraints: only use {allowed_types}.
   Return JSON: {format}"

AGENT -> ORCHESTRATOR:
  {"version": "1", "units": "meters", "summary": "...",
   "assumptions": [...], "actions": [...]}
```

The orchestrator:
1. Parses the JSON response
2. Compiles and executes each action against the IfcAuthor
3. Collects successes and failures
4. Builds the next prompt with the execution report
5. Loops

---

## 4. Orchestrator Script Design

### 4.1 Module: `iterative_planner.py`

```python
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
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ifc_author import AuthoringError, IfcAuthor
from .planner import PlannerError

# Phase ordering and action type constraints
# (reuse from phased_planner.py)
PHASE_ORDER = ["storeys", "structure", "mezzanines", "foundations", "envelope", "openings"]

PHASE_ACTION_TYPES = {
    "storeys": ["ensure_storey"],
    "structure": [
        "generate_column_grid", "create_column", "create_beam",
        "generate_floor_plate", "create_rectangular_slab",
    ],
    "mezzanines": ["create_rectangular_slab", "create_column", "create_beam"],
    "envelope": [
        "create_wall", "generate_perimeter_walls",
        "create_curtain_wall", "generate_facade_grid", "create_panel",
    ],
    "openings": ["create_door", "create_window"],
    "foundations": ["create_footing"],
}


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


class IterativeBuilder:
    """Orchestrates multi-turn BIM generation through an OpenClaw session."""

    def __init__(
        self,
        output_path: str,
        session_id: Optional[str] = None,
        agent_id: str = "bim_operator",
        timeout_per_turn: int = 120,
    ):
        self.output_path = output_path
        self.session_id = session_id or f"build-{uuid.uuid4().hex[:8]}"
        self.agent_id = agent_id
        self.timeout = timeout_per_turn
        self.author = IfcAuthor(output_path)
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
        ):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        raise PlannerError("Cannot find 'openclaw' binary.")

    def _call_agent(self, message: str) -> str:
        """Send a message to the agent within the persistent session."""
        cmd = [
            self.openclaw_bin,
            "agent",
            "--agent", self.agent_id,
            "--session-id", self.session_id,
            "--message", message,
            "--json",
            "--timeout", str(self.timeout),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 30,
            )
        except subprocess.TimeoutExpired as exc:
            raise PlannerError(
                f"Agent timed out after {self.timeout}s"
            ) from exc

        output = result.stdout.strip()
        if not output:
            stderr = result.stderr.strip()
            raise PlannerError(
                f"Agent returned no output. Exit: {result.returncode}. "
                f"Stderr: {stderr[:500]}"
            )
        return output

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from agent response (handles OpenClaw envelope)."""
        stripped = text.strip()

        # Unwrap OpenClaw JSON envelope
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
                elif "actions" in envelope or "phases" in envelope:
                    return envelope
        except json.JSONDecodeError:
            pass

        # Direct parse
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # Markdown fence
        fence = re.search(r"```(?:json)?\s*\n(.*?)```", stripped, re.DOTALL)
        if fence:
            try:
                return json.loads(fence.group(1).strip())
            except json.JSONDecodeError:
                pass

        # First balanced braces
        brace = re.search(r"\{", stripped)
        if brace:
            start = brace.start()
            depth = 0
            for i in range(start, len(stripped)):
                if stripped[i] == "{":
                    depth += 1
                elif stripped[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(stripped[start:i + 1])
                        except json.JSONDecodeError:
                            break

        raise PlannerError(
            f"Failed to extract JSON. Raw: {stripped[:500]}"
        )

    # ------------------------------------------------------------------
    # Turn builders
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
    ) -> str:
        scene = self.author.scene_summary() or "Empty IFC model"
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
        parts.append(f"Current scene: {scene}")
        parts.append("")

        # Phase instruction
        parts.append(
            f"Now generate the {phase_name.upper()} phase: {description}"
        )
        parts.append(
            f"Only use these action types: {', '.join(allowed)}."
        )

        # Generators reminder
        parts.append(
            "Use generate_column_grid for regular column grids, "
            "generate_floor_plate for rectangular slabs with edge beams, "
            "generate_perimeter_walls for walls around a footprint. "
            "Keep total actions under 30."
        )

        # Openings constraint
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
    ) -> Tuple[int, int, List[str]]:
        """Compile and apply actions, return (applied, failed, errors)."""
        from .phased_planner import _normalize_actions

        # Import the core compiler
        try:
            from bonsai_ai_core import compile_plan as compile_core_plan
        except ModuleNotFoundError:
            import sys
            ROOT = Path(__file__).resolve().parents[2]
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from bonsai_ai_core import compile_plan as compile_core_plan

        from .planner import _to_tool_call

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

        # Apply to IFC
        tool_calls = [
            _to_tool_call(action, idx)
            for idx, action in enumerate(compiled["actions"], start=1)
        ]

        applied = 0
        failed = 0
        errors = []
        for call in tool_calls:
            try:
                self.author.apply_tool_call(call.name, call.arguments)
                applied += 1
            except AuthoringError as exc:
                failed += 1
                errors.append(f"{call.name}({call.arguments.get('name', '?')}): {exc}")

        return applied, failed, errors

    # ------------------------------------------------------------------
    # Main build loop
    # ------------------------------------------------------------------

    def build(self, user_prompt: str, dry_run: bool = False) -> BuildResult:
        """Execute the full iterative build."""
        t0 = time.time()
        total_actions = 0
        total_errors = 0

        # Turn 0: Planning decomposition
        print(f"[iterative] Session: {self.session_id}")
        print("[iterative] Turn 0: Decomposing building into phases...")

        plan_output = self._call_agent(self._planning_prompt(user_prompt))
        plan_data = self._extract_json(plan_output)
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

            # Build prompt with prior turn's results
            prompt = self._execution_prompt(phase, completed_summary)

            # Call agent (within persistent session)
            output = self._call_agent(prompt)
            data = self._extract_json(output)
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

            # Execute actions
            applied, failed, errors = self._execute_actions(
                actions, phase_name
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
                retry_prompt = (
                    f"The {phase_name} phase failed:\n"
                    + "\n".join(f"  - {e}" for e in errors[:5])
                    + f"\n\nCurrent scene: {self.author.scene_summary()}\n"
                    f"Please try again with corrected actions. "
                    f"Return ONLY JSON."
                )
                retry_output = self._call_agent(retry_prompt)
                retry_data = self._extract_json(retry_output)
                retry_actions = retry_data.get("actions", [])
                if retry_actions:
                    r_applied, r_failed, r_errors = self._execute_actions(
                        retry_actions, phase_name
                    )
                    total_actions += r_applied
                    total_errors += r_failed
                    completed_summary = (
                        f"Phase {phase_name} retry: "
                        f"{r_applied} applied, {r_failed} failed"
                    )

        # Save IFC
        self.author.save()
        elapsed = time.time() - t0

        print(
            f"\n[iterative] Build complete: {total_actions} actions "
            f"across {len(phases)} phases in {elapsed:.1f}s"
        )
        if total_errors:
            print(f"[iterative] {total_errors} total errors")
        print(self.author.debug_dump())

        return BuildResult(
            session_id=self.session_id,
            turns=self.turn_results,
            total_actions=total_actions,
            total_errors=total_errors,
            elapsed_seconds=round(elapsed, 1),
            output_path=self.output_path,
        )


# ------------------------------------------------------------------
# Public API (matches phased_planner interface)
# ------------------------------------------------------------------

def create_iterative_plan_via_openclaw(
    user_prompt: str,
    output_path: str,
    dry_run: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Entry point for the iterative session-based planner."""
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
```

### 4.2 CLI Integration

Add `--iterative` flag to `cli.py`:

```python
parser.add_argument(
    "--iterative",
    action="store_true",
    help="Use iterative session-based planner (maintains conversation context across phases).",
)
```

In `main()`:

```python
if use_openclaw and getattr(args, "iterative", False):
    from .iterative_planner import create_iterative_plan_via_openclaw
    summary = create_iterative_plan_via_openclaw(
        user_prompt=args.prompt,
        output_path=args.output,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(json.dumps(summary, indent=2))
    return 0
```

### 4.3 Session ID Strategy

For reproducibility and debugging, session IDs follow this pattern:

```
build-{project_name}-{timestamp}
```

Example: `build-retail-terrace-20260331-1050`

This allows:
- Easy identification in `openclaw sessions --agent bim_operator`
- Session reuse for incremental builds (pass same session-id to continue)
- Cleanup via `openclaw sessions cleanup`

---

## 5. Comparison: Phased vs Iterative

| Aspect | Phased (current) | Iterative (proposed) |
|--------|------------------|---------------------|
| Context between phases | None (scene summary string only) | Full conversation history |
| Spatial consistency | Prone to misalignment (60% of quality issues) | Agent references its own prior decisions |
| Error recovery | 1 blind retry per phase | Error report fed back; agent can reason about the failure |
| Token usage | ~150K per phase x N phases (mostly cached system prompt) | ~153K session + ~500 per turn (95%+ cache hits) |
| Latency per phase | 10-30s (cold prompt) | 7-12s (warm cache) |
| Session cost | N independent sessions | 1 session, N turns |
| Prompt size per turn | ~1000 chars (full context re-injected each time) | ~300-500 chars (only new context) |
| Visual verification | Not possible | Possible: screenshot between turns |

### 5.1 Cost Comparison

**Phased planner (6 phases, current)**:
- Turn 1: 153K input tokens (cold)
- Turns 2-6: 153K input each (system prompt cached, but new conversation each time)
- Total input: ~765K tokens (most cached, but 5x session overhead)

**Iterative planner (6 phases, proposed)**:
- Turn 1: 153K input tokens (cold)
- Turns 2-6: ~500 new tokens each + 153K cached
- Total input: ~155K tokens (single session, almost entirely cached)
- Net savings: ~80% fewer non-cached input tokens

---

## 6. Visual Verification Between Turns

### 6.1 Headless Blender Rendering

Between turns, the orchestrator can render a screenshot via headless Blender:

```python
def render_screenshot(ifc_path: str, output_png: str) -> str:
    """Render IFC model via headless Blender + BlenderBIM."""
    script = f'''
import bpy
import blenderbim.tool as tool
bpy.ops.bim.load_project(filepath="{ifc_path}")
bpy.ops.view3d.camera_to_view()
bpy.context.scene.render.filepath = "{output_png}"
bpy.ops.render.render(write_still=True)
'''
    subprocess.run(
        ["blender", "--background", "--python-expr", script],
        capture_output=True, timeout=60,
    )
    return output_png
```

### 6.2 Sending Screenshot to Agent

The bim_operator agent has vision capability (imageModel: gpt-5.4). The orchestrator can include the rendered screenshot in the next turn:

```python
# After rendering, the agent could read the image via its read tool
prompt = (
    f"Phase {phase_name} complete. {applied} actions applied.\n"
    f"I've saved a render to: {screenshot_path}\n"
    f"Read it and verify the model looks correct before continuing."
)
```

However, since `openclaw agent --message` only accepts text, the image would need to be read by the agent using its `read` tool (which supports images) or via the `image` tool. This is a natural fit since the agent already has these capabilities.

### 6.3 Practical Approach

For the initial implementation, skip visual verification and rely on scene summary validation. Add visual verification as a follow-up enhancement once the core loop is proven.

---

## 7. Implementation Plan

### Phase 1: Core Orchestrator (This Sprint)

1. Create `src/bonsai_ai/iterative_planner.py` based on the design above
2. Add `--iterative` flag to `cli.py`
3. Reuse `_normalize_actions()` and `_extract_json()` from `phased_planner.py` (extract to shared module)
4. Test with the 5-story mezzanine building that exposed the spatial misalignment bug

### Phase 2: Session Management

1. Implement session-id naming strategy with project name + timestamp
2. Add `--resume-session <session-id>` flag for incremental builds
3. Add session cleanup integration (clean up build sessions older than 24h)

### Phase 3: Visual Verification

1. Add headless Blender render between phases
2. Pass screenshot path to agent for visual inspection
3. Agent can flag issues ("columns appear to be outside the slab footprint")
4. Orchestrator can trigger a correction turn based on agent feedback

### Phase 4: Advanced Features

1. **Incremental builds**: Resume a session to add/modify elements
2. **Interactive mode**: Human reviews each phase before continuing
3. **Multi-model**: Use fast model (gemini-flash) for simple phases, strong model (gpt-5.4) for complex ones
4. **Parallel phases**: Structure phases for different floors can run in parallel sessions

---

## 8. Risk Assessment

### Session Context Overflow

With a 200K token context window and ~15K for system prompt, we have ~185K for conversation history. At ~500 tokens per turn, that is ~370 turns before overflow. A typical building has 5-8 phases, so this is not a practical concern. If it becomes one, the compaction system will flush to memory files.

### Session Collision

If `--session-id` reuses an existing session, the agent will see prior conversation history. This could be beneficial (incremental builds) or harmful (stale context). Mitigation: default to unique session IDs for new builds; only reuse when explicitly requested.

### Agent Verbose Responses

The agent might include commentary alongside JSON. The `_extract_json()` function already handles this with multiple fallback strategies (envelope unwrap, fence extraction, brace matching). The iterative approach also allows the orchestrator to remind the agent: "Return ONLY JSON."

### Agent Tool Use During Turns

The agent may decide to use tools (read, exec, web_search) during a BIM generation turn, consuming time and tokens. Mitigation: the prompt explicitly says "Return ONLY JSON" which the agent respects well (confirmed in live testing).

---

## 9. Test Validation

### Verified Behaviors (Live Test 2026-03-31)

- [x] `--session-id` creates a persistent session
- [x] Subsequent turns with same session-id resume the conversation
- [x] Agent retains context from prior turns (storey names referenced in turn 2)
- [x] Cache hits confirmed (152K/153K tokens cached on turn 2)
- [x] JSON-only responses confirmed (no commentary when instructed)
- [x] Response time improves on cached turns (12.8s -> 7.6s)

### To Validate During Implementation

- [ ] 6-phase full building build (storeys -> structure -> mezzanines -> envelope -> openings -> foundations)
- [ ] Spatial consistency: slabs align with column grid origins
- [ ] Error recovery: agent corrects mistakes when error report is fed back
- [ ] Session reuse: resuming a build session to add elements to an existing model
- [ ] Comparison: same building via phased vs iterative, measure quality delta
