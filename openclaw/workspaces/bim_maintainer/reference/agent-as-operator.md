# Agent-as-Operator: bim_operator Drives the BIM Pipeline

**Date:** 2026-03-30
**Author:** Claude Opus 4.6 (automated architecture design)
**Status:** Proposal

---

## Problem Statement

The bim_operator agent understands BIM. It knows the primitives, the build order, the coordinate conventions, the storey hierarchy. But today it is a *prompt advisor* -- it crafts prompts for humans to paste into the planner CLI. It cannot build anything itself.

Meanwhile, the planner pipeline (`cli.py` + `phased_planner.py`) runs autonomously but is *dumb* -- it does not understand BIM context, cannot visually verify results, and cannot iterate on design intent. It just calls the LLM and executes whatever comes back.

The key insight: **the bim_operator already has the domain knowledge. Give it the execution tools and let it drive the pipeline directly.**

---

## Current Architecture

```
Human
  |
  v
bim_operator (OpenClaw agent)          <-- knows BIM, has memory, can see images
  |                                         but can only: read, memory_search,
  |                                         memory_get, sessions_spawn
  v
"Here's a prompt to use..."            <-- text output, no execution
  |
  v
Human runs:
  python3 -m bonsai_ai.cli \
    --provider openai \
    --prompt "..." \
    --output model.ifc               <-- actual execution happens here
  |
  v
planner.py -> tool_calls -> ifc_author.py -> model.ifc
```

The human is the bridge between knowledge and execution. That bridge is slow, error-prone, and breaks iteration.

---

## Proposed Architecture

```
Human: "Design a 3-story retail building"
  |
  v
bim_operator (OpenClaw agent)
  |
  |-- Phase 1: PLAN
  |     Decomposes the building into phases.
  |     Generates JSON plan for each phase.
  |     Uses domain knowledge from projects/, site/, components/.
  |
  |-- Phase 2: EXECUTE  (via `bash` tool)
  |     Calls: python3 execute_plan.py --plan plan.json --output model.ifc
  |     Gets back: success/failure, element counts, scene summary
  |
  |-- Phase 3: VERIFY  (via `read` tool)
  |     Reads the scene summary from the output
  |     Optionally reads a rendered screenshot
  |     Compares against design intent
  |
  |-- Phase 4: ITERATE
  |     "Column grid looks good. Proceeding to envelope."
  |     "Slab on Level 2 is offset by 0.15m. Fixing coordinates."
  |     Generates a repair plan and re-executes.
  |
  v
Final model.ifc + design log
```

---

## The Tools the Agent Needs

### What it already has (default OpenClaw tools)

| Tool | Use in this architecture |
|------|--------------------------|
| `read` | Read project docs, site constraints, component specs, inspiration images, IFC scene summaries, rendered screenshots |
| `memory_search` | Recall prior session patterns, prompt strategies, project context |
| `memory_get` | Load specific memory entries |
| `sessions_spawn` | Delegate to bim_maintainer when a code fix is needed |
| `bash` / `exec` | Execute shell commands (key enabler -- see below) |

### What it needs (new capabilities via bash/exec)

The bim_operator already has access to `bash` via OpenClaw's default `coding` tool profile (configured in `openclaw.json`: `"tools": { "profile": "coding" }`). The `coding` profile includes the `bash` execution tool. This means the agent can already run shell commands.

What is missing is a **purpose-built execution script** that wraps the compile + execute + summarize pipeline into a single callable interface.

---

## Implementation: The Execute Script

### `scripts/execute_plan.py`

A standalone Python script that takes a JSON plan, compiles it, executes it via IfcAuthor, and returns a structured result. The bim_operator calls this via `bash`.

```python
#!/usr/bin/env python3
"""Execute a BIM plan JSON and produce an IFC file.

Usage:
    python3 execute_plan.py --plan plan.json --output model.ifc [--append]
    python3 execute_plan.py --plan-stdin --output model.ifc
    echo '{"actions":[...]}' | python3 execute_plan.py --plan-stdin --output model.ifc

Output (JSON to stdout):
    {
        "success": true,
        "output_path": "/path/to/model.ifc",
        "elements_created": 47,
        "scene_summary": "Project: ...\nStoreys: ...",
        "debug_dump": {"walls": 12, "slabs": 5, ...},
        "errors": []
    }
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from bonsai_ai_core import compile_plan
from bonsai_ai.ifc_author import AuthoringError, IfcAuthor
from bonsai_ai.execution import HeadlessIfcExecutor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", help="Path to plan JSON file")
    parser.add_argument("--plan-stdin", action="store_true",
                        help="Read plan JSON from stdin")
    parser.add_argument("--output", required=True,
                        help="Output IFC path")
    parser.add_argument("--append", action="store_true",
                        help="Append to existing IFC instead of overwriting")
    parser.add_argument("--skip-compile", action="store_true",
                        help="Plan is already compiled (skip compile_plan)")
    args = parser.parse_args()

    # Read the plan
    if args.plan_stdin:
        raw = sys.stdin.read()
    elif args.plan:
        raw = Path(args.plan).read_text()
    else:
        print(json.dumps({"success": False, "errors": ["No plan provided"]}))
        return 1

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False,
                          "errors": [f"Invalid JSON: {e}"]}))
        return 1

    # Compile if needed (semantic -> primitive)
    errors = []
    if not args.skip_compile:
        try:
            plan = compile_plan(plan)
        except Exception as e:
            print(json.dumps({"success": False,
                              "errors": [f"Compilation failed: {e}"]}))
            return 1

    # Execute
    executor = HeadlessIfcExecutor(overwrite_existing=not args.append)
    try:
        report = executor.execute_plan(plan, args.output)
    except Exception as e:
        print(json.dumps({"success": False,
                          "errors": [f"Execution failed: {e}"]}))
        return 1

    # Scene summary from the saved file
    author = IfcAuthor(args.output)
    summary = author.scene_summary()
    debug = author.debug_dump()

    result = {
        "success": True,
        "output_path": str(Path(args.output).resolve()),
        "elements_created": len(report.created),
        "scene_summary": summary,
        "debug_dump": json.loads(debug),
        "created": report.created[:50],  # cap for readability
        "errors": errors,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Why a standalone script?

1. **No import path issues.** The script adds `src/` and project root to `sys.path` itself. The agent just runs `python3 /path/to/execute_plan.py`.
2. **Clean JSON contract.** The agent reads structured JSON output, not log spew.
3. **Composable.** Can be called from bash, from the chat-proxy, from cron, from tests.
4. **No new dependencies.** Uses existing `compile_plan`, `HeadlessIfcExecutor`, `IfcAuthor`.

---

## How the Agent Uses It

### Example session flow

The bim_operator receives: *"Design a 3-story retail building with a double-height ground floor and mezzanine"*

#### Step 1: Plan (agent generates JSON)

The agent reads project context, site constraints, and component specs. It then generates a plan JSON using its BIM knowledge:

```json
{
  "version": "1",
  "units": "meters",
  "summary": "3-storey retail with double-height GF and mezzanine",
  "assumptions": ["4.5m ground floor clear height", "3.6m upper floors"],
  "actions": [
    {"type": "ensure_storey", "name": "Ground Floor", "elevation": 0.0},
    {"type": "ensure_storey", "name": "Mezzanine", "elevation": 4.5},
    {"type": "ensure_storey", "name": "Level 1", "elevation": 9.0},
    {"type": "ensure_storey", "name": "Level 2", "elevation": 12.6}
  ]
}
```

The agent writes this to a temp file or pipes it via stdin.

#### Step 2: Execute (agent calls bash)

```bash
cd /Users/alanknudson/Applications/Bonsai_ai && \
PYTHONPATH=src:. python3 scripts/execute_plan.py \
  --plan-stdin --output out/retail/storeys.ifc <<'EOF'
{"version":"1","units":"meters","summary":"...","assumptions":[],"actions":[...]}
EOF
```

The agent reads the JSON response:

```json
{
  "success": true,
  "output_path": "/Users/.../out/retail/storeys.ifc",
  "elements_created": 4,
  "scene_summary": "Project: AI Project\nStoreys: Ground Floor, Mezzanine, Level 1, Level 2",
  "debug_dump": {"storeys": 4, "walls": 0, "slabs": 0, ...}
}
```

#### Step 3: Verify

The agent reads the scene summary and validates:
- 4 storeys created (correct)
- Elevations match design intent (0.0, 4.5, 9.0, 12.6)
- No errors

#### Step 4: Iterate -- next phase

The agent generates the structure phase:

```json
{
  "version": "1",
  "units": "meters",
  "summary": "Column grid and floor plates for retail building",
  "assumptions": [],
  "actions": [
    {
      "type": "generate_column_grid",
      "name": "GF-Grid",
      "storey": "Ground Floor",
      "grid_origin_x": 0.0,
      "grid_origin_y": 0.0,
      "base_z": 0.0,
      "bays_x": 4,
      "bays_y": 3,
      "spacing_x": 7.2,
      "spacing_y": 7.2,
      "column_width": 0.4,
      "column_depth": 0.4,
      "column_height": 4.5
    },
    {
      "type": "generate_floor_plate",
      "name": "Mezzanine-Slab",
      "storey": "Mezzanine",
      "x": 0.0,
      "y": 0.0,
      "z": 4.5,
      "length": 28.8,
      "width": 21.6,
      "thickness": 0.2,
      "include_edge_beams": true,
      "beam_width": 0.3,
      "beam_depth": 0.5
    }
  ]
}
```

Execute with `--append` to add to the existing IFC:

```bash
python3 scripts/execute_plan.py \
  --plan-stdin --output out/retail/storeys.ifc --append <<'EOF'
...
EOF
```

Read result. Verify column count (5x4=20 columns). Verify slab dimensions. Proceed to envelope.

#### Step 5: Handle failures

If execution returns errors:

```json
{
  "success": false,
  "errors": ["Storey not found: Mezzanine Level"]
}
```

The agent recognizes the storey name mismatch (it used "Mezzanine Level" instead of "Mezzanine"), corrects the plan, and re-executes. No human intervention needed.

---

## Implementation Plan

### Phase 1: The execute script (build this first)

**File:** `scripts/execute_plan.py`
**Effort:** ~2 hours
**Dependencies:** None (uses existing modules)
**Test:** `echo '{"version":"1",...}' | python3 scripts/execute_plan.py --plan-stdin --output /tmp/test.ifc`

Deliverables:
1. The script itself (code above, refined)
2. A unit test that exercises compile + execute + JSON output
3. Validation that `--append` mode works (build incrementally)

### Phase 2: Update the operator's AGENTS.md and TOOLS.md

**Files:**
- `openclaw/AGENTS.md` -- add "Execution" section describing the bash-based pipeline
- `openclaw/TOOLS.md` -- document the execute_plan.py interface

New section in AGENTS.md:

```markdown
## Direct Execution

You can build IFC models directly using the execute_plan.py script.

### Generating a plan
Generate a BIM plan as a JSON object following the standard format.
Use your knowledge of the primitives, build order, and project context.

### Executing a plan
```bash
cd /Users/alanknudson/Applications/Bonsai_ai && \
PYTHONPATH=src:. python3 scripts/execute_plan.py \
  --plan-stdin --output out/<project>/model.ifc <<'PLAN'
<your JSON plan here>
PLAN
```

### Incremental building
Use --append to add to an existing model:
```bash
python3 scripts/execute_plan.py \
  --plan-stdin --output out/<project>/model.ifc --append
```

### Reading the result
The script outputs JSON with: success, elements_created, scene_summary,
debug_dump, errors. Use this to verify and iterate.
```

**Effort:** ~30 minutes

### Phase 3: Verify the agent can actually use bash

The bim_operator's config in `openclaw.json` does NOT explicitly set a `tools` block -- it inherits the global defaults:

```json
"tools": {
    "profile": "coding",
    ...
}
```

The `coding` profile includes the `bash` execution tool. However, we need to verify:

1. Does the `bim_operator` agent inherit the global tools profile?
2. Can it run `bash` commands with sufficient permissions?
3. Is there a timeout that would kill long-running builds?

**Test:**
```bash
openclaw agent --agent bim_operator \
  --message "Run this command and tell me the output: python3 --version" \
  --thinking low
```

If bash is not available, add an explicit tools config to the bim_operator agent:

```json
{
    "id": "bim_operator",
    ...
    "tools": {
        "profile": "coding",
        "allow": [
            "memory_search",
            "memory_get",
            "read",
            "sessions_spawn",
            "bash",
            "write"
        ]
    }
}
```

**Effort:** ~15 minutes to test, ~5 minutes to fix if needed

### Phase 4: Add a scene query script

**File:** `scripts/query_scene.py`

A companion script that reads an existing IFC file and returns structured information:

```bash
python3 scripts/query_scene.py --model out/retail/model.ifc
```

Output:
```json
{
    "scene_summary": "Project: AI Project\nStoreys: ...",
    "element_counts": {"walls": 12, "slabs": 5, "columns": 20, ...},
    "storeys": [
        {"name": "Ground Floor", "elevation": 0.0, "element_count": 15},
        {"name": "Level 1", "elevation": 4.5, "element_count": 12}
    ],
    "validation": {
        "orphan_elements": 0,
        "elements_without_storey": [],
        "storey_elevation_gaps": []
    }
}
```

This gives the agent a way to inspect the model state at any point without re-executing anything.

**Effort:** ~1.5 hours

### Phase 5: Visual verification (optional, high impact)

The agent can already read images via the `read` tool (it is vision-capable via GPT-5.4 and Claude Opus 4.6). If we can render the IFC to a screenshot, the agent can visually verify the building.

**Options for rendering:**

| Method | Pros | Cons |
|--------|------|------|
| IfcOpenShell + OCC viewer | Already a dependency, headless possible | Complex setup, slow |
| Blender CLI render | High quality, the native tool | Requires Blender installed, ~10s per render |
| xeokit-sdk (Node.js) | Fast, web-native | New dependency |
| Three.js + Puppeteer | Could reuse viewer code | Heavyweight for CLI use |

**Recommended:** Blender CLI render via a simple script:

```bash
blender --background --python scripts/render_ifc.py -- \
  --input out/retail/model.ifc \
  --output out/retail/preview.png \
  --camera-preset isometric
```

The agent then reads the PNG via `read` and can describe what it sees:
- "The column grid is visible on the ground floor. I count 20 columns in a 5x4 grid."
- "The south facade has no windows yet. Proceeding to openings phase."
- "The mezzanine slab appears to be floating -- it may not be connected to the column grid."

**Effort:** ~4 hours (Blender render script + camera presets)

---

## How This Connects to the Chat Proxy

The viewer's `chat-proxy.js` currently spawns the bim_operator for `/ask` requests and the bim_maintainer for `/research` requests. Adding a `/build` endpoint would let the viewer trigger a full build session:

### New endpoint: `POST /build`

```javascript
// POST /build — trigger iterative build via bim_operator
async function handleBuild(req, res) {
    const { prompt, project, maxPhases } = JSON.parse(await readBody(req));

    // The operator does the full plan-execute-verify loop
    const message = [
        `Build this project: ${prompt}`,
        `Output to: out/${project}/model.ifc`,
        `Use scripts/execute_plan.py for execution.`,
        `Build incrementally: storeys, then structure, then envelope, then openings.`,
        `After each phase, verify the scene summary before proceeding.`,
        maxPhases ? `Maximum ${maxPhases} phases.` : "",
    ].filter(Boolean).join("\n");

    const proc = spawn("openclaw", [
        "agent", "--agent", "bim_operator",
        "--message", message,
        "--thinking", "medium",
        "--timeout", "600",
    ], { cwd: WORKSPACE, timeout: 600000 });

    // Stream progress via SSE or return when complete
    // ...
}
```

This turns the viewer's chat panel into a "build" button that triggers the full autonomous pipeline.

---

## Answering the Design Questions

### Can OpenClaw agents call external scripts/tools?

**Yes.** The global tools config uses `"profile": "coding"` which includes the `bash` execution tool. Agents can run arbitrary shell commands, including Python scripts. The bim_operator inherits this unless overridden.

Verified by examining `openclaw.json`:
```json
"tools": {
    "profile": "coding",
    ...
}
```

And confirmed by the `coding-agent` skill (at `/opt/homebrew/lib/node_modules/openclaw/skills/coding-agent/SKILL.md`) which documents how agents use `bash` with optional `pty`, `workdir`, `background`, and `timeout` parameters.

### What is the skill system? How do you register custom tools?

OpenClaw has two extension mechanisms:

1. **Skills** (`SKILL.md` files): Markdown files with YAML frontmatter that define instructions for when/how to use a capability. They are loaded into the agent's context when triggered. Skills are either bundled with OpenClaw or installed from ClawHub. Custom skills go in the workspace's `skills/` directory.

2. **Tools** (agent config): Tools are configured per-agent or globally via `openclaw.json`. The `tools.profile` setting (`minimal`, `coding`, etc.) controls which built-in tools are available. The `tools.allow` array can whitelist specific tools.

For our use case, we do NOT need a custom tool or skill. The `bash` tool from the `coding` profile is sufficient. The execute_plan.py script provides the interface contract.

However, if we wanted a more polished experience, we could create a **custom skill**:

**File:** `openclaw/skills/bim-execute/SKILL.md`
```yaml
---
name: bim-execute
description: "Execute a BIM plan JSON to produce an IFC file. Use when the operator has a complete plan and wants to build it."
metadata:
  openclaw:
    emoji: "🏗️"
    requires:
      allBins: ["python3"]
---

# BIM Execute

Execute a BIM plan via the Bonsai AI pipeline.

## Usage

```bash
cd /Users/alanknudson/Applications/Bonsai_ai && \
PYTHONPATH=src:. python3 scripts/execute_plan.py \
  --plan-stdin --output <output_path> [--append] <<'PLAN'
<plan JSON>
PLAN
```

## Plan format
Standard Bonsai AI plan JSON with version, units, summary, assumptions, actions.

## Result
JSON object with: success, output_path, elements_created, scene_summary, debug_dump, errors.
```

### Can the agent see screenshots (vision) to verify the building?

**Yes.** The bim_operator uses `openai-codex/gpt-5.4` which is vision-capable. The agent can read PNG/JPG files using the `read` tool. This is already documented in `TOOLS.md`:

> **Image files (vision-capable):**
> - Rendered views: any `.jpg`, `.png` in the project tree

The bottleneck is *producing* the screenshot, not reading it. We need a render script that converts IFC to PNG. Blender CLI is the most practical option since it is already the native tool for the Bonsai workflow.

### How does session continuity work across multiple subprocess calls?

OpenClaw agents maintain session state via two mechanisms:

1. **Session ID persistence:** `openclaw agent --session-id <id>` continues an existing session. All messages in the same session share context. The chat-proxy currently does NOT use session IDs (each `/ask` is a fresh session).

2. **Memory system:** The agent reads `memory/YYYY-MM-DD.md` and project-specific files at session start. Memory persists across sessions.

For the iterative build loop, there are two approaches:

**Approach A: Single long session (recommended)**
Run one `openclaw agent` call with a comprehensive prompt. The agent plans, executes (via bash), verifies (via read), and iterates -- all within a single session. The agent's internal reasoning maintains context across phases.

**Approach B: Multi-turn session**
Use `--session-id` to continue the same session across multiple calls:
```bash
# Turn 1: Plan
openclaw agent --agent bim_operator --session-id build-retail-001 \
  --message "Design a 3-story retail building. Start with storeys."

# Turn 2: Verify and continue
openclaw agent --agent bim_operator --session-id build-retail-001 \
  --message "Storeys created. Scene summary: [paste]. Now design structure."
```

Approach A is simpler and faster (no subprocess overhead per phase). The agent has all the tools it needs in a single session.

### What is the simplest way to give the agent a "build this plan" capability?

**In order of simplicity:**

1. **Simplest (works today, ~2 hours):**
   Create `scripts/execute_plan.py`. Tell the agent about it in AGENTS.md. The agent uses `bash` to call it. No OpenClaw config changes needed.

2. **Better (adds scene inspection, ~4 hours):**
   Add `scripts/query_scene.py` for non-destructive model inspection. The agent can check the model state without re-executing.

3. **Best (adds visual verification, ~8 hours):**
   Add `scripts/render_ifc.py` for Blender CLI rendering. The agent can see screenshots of the model and visually verify the design.

---

## Comparison with Current Approaches

| Approach | Who drives? | Can iterate? | Can verify? | Has BIM knowledge? | Structured output? |
|----------|-------------|--------------|-------------|---------------------|---------------------|
| **Current CLI** (`cli.py`) | Script (fixed loop) | Yes (12 rounds) | No (scene summary only) | No (LLM prompt only) | Yes (json_schema) |
| **Phased planner** (`phased_planner.py`) | Script (fixed phases) | Limited (per phase) | No | No | Partial |
| **Chat proxy** (`chat-proxy.js`) | Human (via viewer) | Manual only | Human judges | Agent advises | No |
| **Agent-as-operator** (this proposal) | Agent (autonomous) | Yes (intelligent) | Yes (summary + vision) | Yes (full context) | Agent generates JSON |

The agent-as-operator approach is the only one that combines domain knowledge, execution capability, verification, and intelligent iteration in a single loop.

---

## Risks and Mitigations

### Risk: Agent generates invalid plan JSON
**Mitigation:** The `compile_plan()` step validates the plan schema. If compilation fails, the agent gets a clear error message and can fix the JSON.

### Risk: Runaway execution (infinite loop of retries)
**Mitigation:** The agent has a natural turn limit from OpenClaw (configurable timeout, default 600s). Additionally, the execute_plan.py script is stateless -- each call either succeeds or fails cleanly. The AGENTS.md instructions should include a "maximum 6 phases per build" guideline.

### Risk: Agent overwrites IFC files without asking
**Mitigation:** Already covered by the red line in AGENTS.md: "Don't overwrite IFC files without confirming with the human." For autonomous builds, the agent should use a new output path (e.g., `out/<project>/draft_001.ifc`) and only overwrite the canonical model after human approval.

### Risk: Agent lacks structured output for plan generation
**Mitigation:** The agent generates free-form JSON (not schema-constrained like the planner's structured output). However, compile_plan() validates the schema, so malformed plans fail fast with actionable errors. In practice, GPT-5.4 and Claude Opus 4.6 produce valid BIM plan JSON reliably when given the plan format specification in AGENTS.md.

### Risk: Long build sessions hit OpenClaw timeout
**Mitigation:** Configure the bim_operator agent with a higher timeout for build sessions. The `openclaw agent --timeout 600` flag (10 minutes) should be sufficient for most builds. For very large buildings, Approach B (multi-turn sessions) can break the work across calls.

---

## Decision: Start with Option 1 (Simplest)

Build `scripts/execute_plan.py` and update AGENTS.md/TOOLS.md. This requires:
- 1 new file (the execute script)
- 2 file edits (AGENTS.md, TOOLS.md)
- 0 OpenClaw config changes
- 0 new dependencies

The agent can start building IFC models autonomously immediately. Visual verification (Phase 5) can be added later as a high-impact enhancement.

---

## Appendix A: Tool Profile Verification

The bim_operator agent's tools depend on the inheritance chain:

1. Global defaults: `"tools": { "profile": "coding" }` -- includes bash, read, write, exec
2. Agent-level overrides: bim_operator has NO explicit `tools` block
3. Therefore: bim_operator inherits the global `coding` profile

The `coding` profile (standard OpenClaw) includes:
- `bash` -- execute shell commands (this is the key tool)
- `read` -- read files (already documented in TOOLS.md)
- `write` -- write files (needed to save plan JSON)
- `exec` / `process` -- background process management
- `memory_search` / `memory_get` -- memory system
- `sessions_spawn` -- sub-agent delegation
- `web_fetch` -- web content retrieval

All tools needed for the agent-as-operator architecture are already available.

## Appendix B: execute_plan.py Interface Contract

**Input:**
- `--plan <path>` or `--plan-stdin`: BIM plan JSON (semantic or compiled)
- `--output <path>`: IFC output file path
- `--append`: Add to existing IFC (do not overwrite)
- `--skip-compile`: Plan is already in primitive form

**Output (JSON to stdout):**
```json
{
    "success": true | false,
    "output_path": "/absolute/path/to/model.ifc",
    "elements_created": 47,
    "scene_summary": "Project: ...\nStoreys: ...\nIfcWall: ...",
    "debug_dump": {
        "projects": 1,
        "storeys": 4,
        "walls": 12,
        "slabs": 5,
        "columns": 20,
        "beams": 16,
        "doors": 4,
        "windows": 8,
        "curtain_walls": 2,
        "plates": 24,
        "footings": 0
    },
    "created": ["Ground Floor", "Level 1", "GF-Grid-Col-A1", ...],
    "errors": []
}
```

**Exit codes:**
- 0: success (JSON output on stdout)
- 1: failure (JSON error on stdout)

## Appendix C: Sequence Diagram

```
bim_operator                execute_plan.py              IfcAuthor
    |                            |                          |
    |-- generate plan JSON       |                          |
    |                            |                          |
    |-- bash: python3            |                          |
    |   execute_plan.py          |                          |
    |   --plan-stdin             |                          |
    |   --output model.ifc       |                          |
    |                            |                          |
    |                     read plan JSON                    |
    |                     compile_plan()                    |
    |                            |                          |
    |                            |-- execute_plan()         |
    |                            |                          |
    |                            |   for each action:       |
    |                            |     apply_action() ----->|
    |                            |     <-- ExecutionResult  |
    |                            |                          |
    |                            |-- author.save()          |
    |                            |-- author.scene_summary() |
    |                            |-- author.debug_dump()    |
    |                            |                          |
    |<-- JSON result             |                          |
    |                            |                          |
    |-- read result JSON         |                          |
    |-- verify against intent    |                          |
    |                            |                          |
    |-- if errors: fix plan,     |                          |
    |   re-execute               |                          |
    |-- if ok: next phase        |                          |
    |   or report complete       |                          |
```
