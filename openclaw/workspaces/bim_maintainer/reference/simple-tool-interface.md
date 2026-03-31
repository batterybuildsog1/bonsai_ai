# Simplified Tool Interface for the BIM Agent

> Date: 2026-03-30
> Author: Claude Opus 4.6 (automated architecture research)
> Status: Design options for discussion
> Depends on: harness-audit.md (the 67-property god-object diagnosis)

---

## The Problem in One Sentence

The BIM agent currently generates a monolithic JSON plan conforming to a 67-property god-object schema with 22 action types, but what it actually needs is a handful of composable tools it can call one at a time.

## What the Current System Actually Does

Tracing the full path from agent intent to IFC output:

```
Agent has an idea ("put a column grid here")
  |
  v
Agent must produce a complete JSON plan conforming to plan_schema()
  - 67 properties on every action item (COMMON_ACTION_PROPERTIES)
  - 22 action types sharing the same flat property bag
  - Nested metadata objects: semantics (13 props), presentation (10 props), foundation (18 props)
  - Total: 108+ properties across the schema surface
  |
  v
compile_plan() expands semantic actions to primitives
  - generate_column_grid -> N create_column actions
  - generate_perimeter_walls -> N create_wall actions
  - generate_floor_plate -> 1 slab + 4 beams
  - create_stair_run -> N slab treads
  |
  v
HeadlessIfcExecutor._apply_action() dispatches each primitive
  - Calls IfcAuthor methods (create_wall, create_column, etc.)
  - Each method is 50-100 lines of ifcopenshell API calls
  |
  v
IfcAuthor.save() writes the IFC file
```

The critical insight: **the agent never sees the tool_specs.py descriptions** that explain how each tool works. It only sees the god-object schema where every field appears on every action. The well-crafted per-tool documentation ("Bottom-left corner origin X in meters (NOT center)") is invisible during planning.

---

## Option A: Simple CLI Tools

### The Interface

Replace the JSON plan with individual bash commands. Each command does one thing.

```bash
# ---- Storey management ----
bim storey "Ground Floor" --elevation 0
bim storey "Level 1" --elevation 4.5

# ---- Structure ----
bim column-grid "Main Grid GF" \
  --storey "Ground Floor" \
  --origin 0,0 \
  --bays 5,3 \
  --spacing 8,8 \
  --column-size 0.3,0.3 \
  --height 4.5

bim slab "Ground Floor Slab" \
  --storey "Ground Floor" \
  --corner 0,0 \
  --size 40,24 \
  --thickness 0.2 \
  --elevation 0

# ---- Envelope ----
bim perimeter-walls "GF Walls" \
  --storey "Ground Floor" \
  --corners 0,0 40,0 40,24 0,24 \
  --height 4.5 \
  --thickness 0.2

bim window "East Win 01" \
  --storey "Ground Floor" \
  --wall "GF Walls-Seg-02" \
  --offset 4.0 \
  --sill 0.9 \
  --size 1.8,1.5

# ---- Inspection ----
bim info                    # element counts, storey list, scene summary
bim check                   # spatial validation, orphan detection
bim elements --storey "Ground Floor" --type column  # list specific elements

# ---- Editing ----
bim move "East Win 01" --dx 0.5
bim delete "East Win 01"
bim update "GF Walls-Seg-02" --height 5.0
```

### Implementation

The `bim` command is a Python CLI that wraps `IfcAuthor` directly, bypassing the plan schema, compiler, and tool_specs entirely.

```python
#!/usr/bin/env python3
"""bim - Simple CLI for BIM model authoring.

Each subcommand creates or modifies IFC elements in a model file.
All commands read/write the same model file (default: out/model.ifc).
All commands return JSON to stdout.

Usage:
    bim storey "Ground Floor" --elevation 0
    bim column-grid "Grid A" --storey "Ground Floor" --origin 0,0 --bays 5,3 ...
    bim info
"""

import argparse, json, sys
from ifc_author import IfcAuthor

def cmd_storey(author, args):
    result = author.ensure_storey(args.name, args.elevation)
    return {"created": result.element_name, "elevation": args.elevation}

def cmd_slab(author, args):
    x, y = args.corner
    length, width = args.size
    result = author.create_rectangular_slab(
        name=args.name,
        storey_name=args.storey,
        x=x, y=y, z=args.elevation,
        length=length, width=width,
        thickness=args.thickness,
    )
    return {"created": result.element_name}

def cmd_column_grid(author, args):
    # Expand to individual columns, return count
    ...

def cmd_info(author, args):
    return json.loads(author.debug_dump())

# ... one function per subcommand
```

Each subcommand:
- Takes only the arguments relevant to that operation (3-8 flags, not 67)
- Returns JSON to stdout (element name, global_id, success/failure)
- Saves the model file after each operation (or batches with `--dry-run`)
- Supports `--help` with full documentation
- Operates on a single model file (`--model out/model.ifc`, defaulting to environment variable or convention)

### How the Agent Uses It

The agent has bash tool access. It runs commands sequentially, reading each result before deciding the next step.

```
Agent thinks: "I need a 5x3 column grid on the ground floor"
Agent runs:   bim storey "Ground Floor" --elevation 0
Agent reads:  {"created": "Ground Floor", "elevation": 0}
Agent runs:   bim column-grid "Main Grid" --storey "Ground Floor" --origin 0,0 --bays 5,3 --spacing 8,8 --column-size 0.3,0.3 --height 4.5
Agent reads:  {"created": 24, "elements": ["Main Grid-Col-A1", ...]}
Agent runs:   bim info
Agent reads:  {"columns": 24, "storeys": 1, ...}
Agent thinks: "Grid looks right. Now I need the slab."
```

This is exactly how Claude Code, GitHub Copilot CLI, and other AI-driven developer tools work: the agent calls simple commands and reads their output.

### Error Recovery

```
Agent runs:   bim window "Win 01" --wall "NonexistentWall" --offset 4 --sill 0.9 --size 1.8,1.5
Agent reads:  {"error": "Wall 'NonexistentWall' not found. Available walls: GF Walls-Seg-01, GF Walls-Seg-02, ..."}
Agent thinks: "Wrong wall name. Let me check what walls exist."
Agent runs:   bim elements --type wall
Agent reads:  [{"name": "GF Walls-Seg-01", ...}, {"name": "GF Walls-Seg-02", ...}]
Agent runs:   bim window "Win 01" --wall "GF Walls-Seg-02" --offset 4 --sill 0.9 --size 1.8,1.5
Agent reads:  {"created": "Win 01", "host_wall": "GF Walls-Seg-02"}
```

Errors are immediate, specific, and actionable. The agent can inspect the model state and retry. No retry loop with vague "The previous JSON plan was invalid" messages.

### Evaluation

| Criterion | Assessment |
|-----------|------------|
| Simplicity for the agent | Excellent. Each command has 3-8 flags. Help text is self-documenting. |
| Capability loss | None for creation. Bulk operations (30 columns) expand internally like they do now. Metadata (semantics, presentation, foundation) can be added via `--metadata '{"role": "structure"}'` JSON flag or individual flags like `--role structure`. |
| Interaction with existing pipeline | Bypasses plan schema and compiler entirely. Goes directly to IfcAuthor. The compile step is absorbed into the column-grid/perimeter-walls/floor-plate subcommands. |
| Self-describing (no system prompt needed) | Yes. `bim --help`, `bim storey --help`, etc. The agent can discover usage from help output alone. |
| Error recovery | Immediate per-command. Agent sees the error, inspects state, retries. |
| Mistake recovery | `bim delete`, `bim move`, `bim update` let the agent fix mistakes surgically. Or `bim reset` to start over. |

---

## Option B: Natural Language Interpreter

### The Interface

The agent describes what it wants; a deterministic interpreter converts to actions.

```
Agent: "Create a building storey called Ground Floor at elevation 0"
Interpreter: ensure_storey("Ground Floor", 0.0) -> OK

Agent: "Add a 5x3 column grid starting at origin (0,0) with 8m spacing in both directions, 0.3m square columns, 4.5m tall, on Ground Floor"
Interpreter: Parsed -> generate_column_grid(origin=(0,0), bays=(5,3), spacing=(8,8), size=(0.3,0.3), height=4.5, storey="Ground Floor")
             This will create 24 columns. Execute? [preview shown]
Agent: "Execute"
Interpreter: Created 24 columns. Model now has 24 columns, 1 storey.

Agent: "Add a 40x24m slab at origin for the ground floor, 200mm thick"
Interpreter: Parsed -> create_rectangular_slab(corner=(0,0), size=(40,24), thickness=0.2, storey="Ground Floor")
             Execute?
Agent: "Execute"
```

### Implementation

This requires a secondary LLM call (or a structured NLU parser) to convert natural language to tool calls. In effect, this is **the current system** with a different prompt surface.

```python
# This is essentially what the planner already does:
# LLM input: natural language
# LLM output: structured JSON actions
# The "interpreter" is just the LLM with structured output
```

### Evaluation

| Criterion | Assessment |
|-----------|------------|
| Simplicity for the agent | Moderate. The agent still needs to describe geometry precisely. "8m spacing" is unambiguous, but "put columns around the perimeter" is not. |
| Capability loss | Depends entirely on interpreter quality. Ambiguous inputs produce wrong geometry. |
| Interaction with existing pipeline | This IS the existing pipeline with a different prompt. Does not solve the god-object problem. |
| Self-describing | No. The agent must learn what the interpreter understands through trial and error. |
| Error recovery | Worse than Option A. If the interpreter misunderstands "8m spacing," the agent may not detect the error until visual inspection. |
| Mistake recovery | Same as current system -- generate a new plan or edit plan. |

**Verdict: Option B does not solve the fundamental problem.** It adds a translation layer that introduces ambiguity. The agent already knows what it wants (specific dimensions, coordinates, element types). Forcing it to describe these in natural language and then parse them back to structured calls is a round-trip through ambiguity.

---

## Option C: Hybrid -- CLI Tools + Batch JSON for Bulk Operations

### The Interface

Simple CLI tools for individual operations and queries (same as Option A). An optional batch mode for when the agent wants to create many elements at once.

```bash
# Individual commands (same as Option A)
bim storey "Ground Floor" --elevation 0
bim slab "GF Slab" --storey "Ground Floor" --corner 0,0 --size 40,24 --thickness 0.2 --elevation 0

# Batch mode: agent writes a simple JSON array, not a full plan
bim batch <<'EOF'
[
  {"cmd": "storey", "name": "Ground Floor", "elevation": 0},
  {"cmd": "storey", "name": "Level 1", "elevation": 4.5},
  {"cmd": "column-grid", "name": "Main Grid GF", "storey": "Ground Floor",
   "origin": [0, 0], "bays": [5, 3], "spacing": [8, 8],
   "column_size": [0.3, 0.3], "height": 4.5},
  {"cmd": "slab", "name": "GF Slab", "storey": "Ground Floor",
   "corner": [0, 0], "size": [40, 24], "thickness": 0.2, "elevation": 0}
]
EOF
# Returns: [{"ok": true, "created": "Ground Floor"}, {"ok": true, "created": 24}, ...]

# Inspection (same as Option A)
bim info
bim check
```

### Why Batch Mode Matters

An agent calling bash tools typically makes one tool call per turn. Building a 3-story office building requires ~15-30 operations. Without batch mode, that is 15-30 round trips. With batch mode, the agent can group related operations:

```bash
# Round trip 1: Create all storeys
bim batch <<'EOF'
[
  {"cmd": "storey", "name": "Ground Floor", "elevation": 0},
  {"cmd": "storey", "name": "Level 1", "elevation": 4.5},
  {"cmd": "storey", "name": "Level 2", "elevation": 9.0}
]
EOF

# Round trip 2: Create structure for all floors
bim batch <<'EOF'
[
  {"cmd": "column-grid", "name": "Grid GF", "storey": "Ground Floor", ...},
  {"cmd": "slab", "name": "Slab GF", "storey": "Ground Floor", ...},
  {"cmd": "column-grid", "name": "Grid L1", "storey": "Level 1", ...},
  {"cmd": "slab", "name": "Slab L1", "storey": "Level 1", ...}
]
EOF

# Round trip 3: Check, then add envelope
bim info
```

The batch JSON is much simpler than the current plan schema:
- Each item has only the fields for its specific command (3-8, not 67)
- No `version`, `units`, `summary`, `assumptions` wrapper
- No shared property bag -- each command type has its own shape
- Errors are reported per-item, so the agent knows exactly which one failed

### Evaluation

| Criterion | Assessment |
|-----------|------------|
| Simplicity for the agent | Excellent. Individual commands for exploration, batch for efficiency. |
| Capability loss | None. Batch JSON can carry metadata too. |
| Interaction with existing pipeline | Bypasses plan schema. Batch mode re-implements the compile step internally per command. |
| Self-describing | Yes. `bim --help` plus `bim batch --help` with schema examples. |
| Error recovery | Per-item errors in batch. Individual commands for surgical fixes. |
| Mistake recovery | Same as Option A. |

---

## Detailed Comparison

### Complexity the Agent Must Handle

| Concern | Current System | Option A (CLI) | Option C (Hybrid) |
|---------|---------------|----------------|-------------------|
| Properties per action | 67 (shared flat bag) | 3-8 (per command) | 3-8 (per command) |
| Action types to learn | 22 (in one enum) | ~12 subcommands | ~12 subcommands |
| Schema tokens sent to model | ~4,600 | 0 (help text on demand) | 0 (help text on demand) |
| System prompt required | Yes (~1,100 tokens) | No (tools are self-describing) | No (tools are self-describing) |
| Wrapper overhead | version, units, summary, assumptions | None | None for individual; minimal for batch |
| Field name confusion | width/depth vs length/width | Single canonical name per flag | Single canonical name per flag |
| Metadata (semantics etc.) | Always present, 41 nested properties | Opt-in via --metadata or flags | Same |

### Token Economics

Current system per building:
- System prompt: ~1,100 tokens
- Plan schema (response_format): ~4,600 tokens
- Agent output (full JSON plan): ~2,000-8,000 tokens

Option A per building (15-30 commands):
- No system prompt tokens for schema
- Each command: ~20-50 tokens of bash
- Each response: ~50-100 tokens of JSON
- Total agent I/O: ~1,500-4,500 tokens
- Help text (if agent checks): ~200 tokens per subcommand, loaded on demand

Option C per building (3-5 batch calls + individual):
- Batch JSON: ~200-500 tokens per batch
- Total agent I/O: ~1,000-3,000 tokens

### Capabilities Matrix

| Capability | Current | Option A | Option C |
|------------|---------|----------|----------|
| Create storeys | Yes | Yes | Yes |
| Create slabs | Yes | Yes | Yes |
| Create walls | Yes | Yes | Yes |
| Create columns | Yes | Yes | Yes |
| Create beams | Yes | Yes | Yes |
| Create panels | Yes | Yes | Yes |
| Create windows/doors | Yes | Yes | Yes |
| Create curtain walls | Yes | Yes | Yes |
| Create footings | Yes | Yes | Yes |
| Column grids | Yes (generator) | Yes (subcommand) | Yes |
| Perimeter walls | Yes (generator) | Yes (subcommand) | Yes |
| Floor plates with beams | Yes (generator) | Yes (subcommand) | Yes |
| Facade grids | Yes (generator) | Yes (subcommand) | Yes |
| Stair runs | Yes (compiled to slab treads) | Yes (subcommand) | Yes |
| Edit elements | Yes (5 edit action types) | Yes (move/delete/update) | Yes |
| Inspect model | Requires separate query_scene.py | Built-in (bim info) | Built-in |
| Spatial validation | Requires separate script | Built-in (bim check) | Built-in |
| Incremental authoring | No (full plan each time) | Yes (each command appends) | Yes |
| Undo last operation | No | Possible (bim undo) | Possible |

The only capability the current system has that Option A/C does not have by default is the `summary` and `assumptions` metadata on the plan envelope. These are easily added as a separate `bim annotate --summary "..." --assumptions "..."` command if needed.

---

## How Commercial BIM Tools Handle Scripting

### Revit API (Autodesk)

Revit's API is imperative, not declarative. Scripts create elements one at a time inside a transaction:

```csharp
using (Transaction tx = new Transaction(doc, "Create Column")) {
    tx.Start();
    FamilyInstance column = doc.Create.NewFamilyInstance(
        new XYZ(0, 0, 0),           // location
        columnType,                   // family type
        level,                        // host level
        StructuralType.Column         // structural usage
    );
    tx.Commit();
}
```

Key features:
- One call per element (like Option A)
- Transactions group related changes (like Option C batch)
- Immediate validation on commit
- Full query API to inspect the model
- No JSON schemas -- method signatures with typed parameters

### Dynamo (Autodesk visual scripting)

Dynamo nodes are individual operations with typed inputs. A "Column Grid" node takes origin, spacing, counts. A "Floor" node takes a boundary curve and a type. Nodes are wired together visually, but each node is effectively a single tool call.

### Grasshopper (McNeel/Rhino)

Same pattern as Dynamo: small composable nodes. A typical Grasshopper definition for a column grid has:
- A "Grid" node (origin, spacing, counts)
- A "Column" node (point, height, section)
- Connected by wires (data flow)

Each node has 3-6 inputs, not 67.

### IFC.js / IfcOpenShell Python

Direct API calls. Create elements one at a time. No schema.

```python
wall = ifcopenshell.api.root.create_entity(model, ifc_class="IfcWall")
```

### BlenderBIM / Bonsai

Uses `ifcopenshell.api` calls directly. The Bonsai add-on for Blender exposes individual operators (one per element type) in the UI, each with its own property panel showing only relevant fields.

### Common Pattern

Every commercial BIM scripting interface uses **imperative, per-element calls** with **type-specific parameters**. None of them use a flat god-object schema. The current Bonsai AI approach is unique in its use of a monolithic plan schema -- and not in a good way.

---

## The DSL Question

Could we use a domain-specific language instead of JSON or bash?

### Possible DSL

```
project "AI Office Building"
  site "Main Campus"

storey "Ground Floor" at 0m
storey "Level 1" at 4.5m

on "Ground Floor":
  column-grid "Main Grid"
    origin 0, 0
    bays 5 x 3
    spacing 8m x 8m
    columns 300mm x 300mm, height 4.5m

  slab "Floor Slab"
    corner 0, 0
    size 40m x 24m
    thickness 200mm

  perimeter-walls
    corners (0,0) (40,0) (40,24) (0,24)
    height 4.5m
    thickness 200mm
```

### Evaluation

A DSL is elegant but adds a parsing layer the agent must learn. The agent would need either:
1. Examples of the DSL in its system prompt (which we are trying to eliminate)
2. A grammar specification (which is a schema by another name)

**The bash CLI approach gives us a "DSL" for free** -- the command names and flag names ARE the domain vocabulary, and the agent already knows how to use bash. Every LLM has deep training data on CLI tools and `--help` output. No LLM has training data on a custom BIM DSL.

---

## What AI Code Generation Systems Do

### Claude Code (this tool)

Uses bash commands, file reads, file edits. Each tool does one thing. The agent calls tools sequentially, reading results between calls. No JSON plan. No schema. The agent discovers tool capabilities from documentation and help text.

### GitHub Copilot (editor mode)

Generates code directly in the editor. No intermediate schema. The output IS the code. If we applied this pattern, the agent would directly write Python that calls `IfcAuthor` methods.

### Cursor / Aider

Same as Copilot -- direct code generation with file edits.

### The Pattern

Modern AI code tools give the agent **direct access to the execution surface**. They do not interpose a schema between the agent and the output. The schema is the API itself (method signatures, type annotations, docstrings).

---

## Recommendation: Option A with Batch Extension (Option C)

### Why

1. **Option A is the simplest possible interface** that can build a complete building. Each command has 3-8 parameters. The agent can learn all commands from `bim --help`.

2. **Batch mode (Option C extension) solves the round-trip problem** without reintroducing the god-object schema. The batch JSON is per-command typed, not a flat shared bag.

3. **This matches every commercial BIM scripting tool.** Revit API, Dynamo, Grasshopper, IfcOpenShell -- all use per-element imperative calls. The current monolithic plan schema is an aberration.

4. **The agent already has bash access.** The bim_operator agent has the `coding` tool profile with bash execution. No new tool infrastructure needed.

5. **Zero system prompt needed.** The agent runs `bim --help`, reads the output, and knows what to do. This eliminates the 1,100-token system prompt and the 4,600-token schema.

6. **Incremental authoring enables iteration.** The agent can build, inspect, fix, and extend. The current system requires regenerating the entire plan to fix one column.

### What Gets Removed

| Component | Current Role | After |
|-----------|-------------|-------|
| `COMMON_ACTION_PROPERTIES` (67 props) | God-object plan schema | Eliminated. Each CLI subcommand has its own argparse definition. |
| `plan_schema()` | OpenAI structured output format | Eliminated. No structured output needed -- agent produces bash commands. |
| `tool_specs.py` (15 tools) | Tool schemas for downstream execution | Absorbed into CLI subcommand implementations. |
| `compiler.py` | Expands semantic actions to primitives | Absorbed into CLI subcommands (column-grid, perimeter-walls, etc.) |
| `_TOOL_NAME_MAP` | Maps plan actions to tool names | Eliminated. Direct dispatch via argparse subcommands. |
| `_coerce_numeric_fields()` | Fixes LLM field naming mistakes | Eliminated. CLI flags enforce canonical names. |
| System prompt (1,100 tokens) | Instructs model on schema rules | Eliminated. `bim --help` is the instruction. |

### What Stays

| Component | Current Role | After |
|-----------|-------------|-------|
| `IfcAuthor` | IFC element creation | Unchanged. CLI subcommands call IfcAuthor methods directly. |
| `HeadlessIfcExecutor` | Batch execution | Simplified. Only needed for `bim batch` mode, and can be streamlined since each batch item is already a resolved command. |
| `query_scene.py` | Model inspection | Absorbed into `bim info` and `bim check`. |

### Implementation Sketch

The entire CLI is approximately 400-500 lines of Python. The argparse definitions serve as both the parameter schema and the help documentation. Here is the structure:

```
scripts/bim.py                    # Main CLI entrypoint
  |-- cmd_storey(author, args)    # 10 lines
  |-- cmd_slab(author, args)      # 15 lines
  |-- cmd_wall(author, args)      # 15 lines
  |-- cmd_column(author, args)    # 15 lines
  |-- cmd_beam(author, args)      # 15 lines
  |-- cmd_panel(author, args)     # 15 lines
  |-- cmd_window(author, args)    # 15 lines
  |-- cmd_door(author, args)      # 15 lines
  |-- cmd_curtain_wall(author, args)  # 15 lines
  |-- cmd_footing(author, args)   # 15 lines
  |-- cmd_column_grid(author, args)   # 25 lines (expands to columns)
  |-- cmd_perimeter_walls(author, args)  # 20 lines
  |-- cmd_floor_plate(author, args)   # 25 lines (slab + optional beams)
  |-- cmd_facade_grid(author, args)   # 20 lines
  |-- cmd_stair_run(author, args)     # 25 lines
  |-- cmd_move(author, args)      # 15 lines
  |-- cmd_delete(author, args)    # 10 lines
  |-- cmd_update(author, args)    # 15 lines
  |-- cmd_info(author, args)      # 10 lines
  |-- cmd_check(author, args)     # 20 lines
  |-- cmd_elements(author, args)  # 15 lines
  |-- cmd_batch(author, args)     # 30 lines
```

### Migration Path

The CLI does not require removing the existing plan-based system. Both can coexist:

1. **Phase 1**: Build `scripts/bim.py` as a new interface alongside the existing pipeline.
2. **Phase 2**: Update the bim_operator agent to use `bim` commands instead of generating JSON plans.
3. **Phase 3**: When the CLI is proven, deprecate the plan schema path. `execute_plan.py` can be reimplemented as a thin wrapper that converts plans to `bim batch` calls.
4. **Phase 4**: Remove `COMMON_ACTION_PROPERTIES`, `plan_schema()`, `_coerce_numeric_fields()`, and the system prompt.

### What the Agent Session Looks Like

```
User: "Design a 2-story office building, 40m x 24m, 4.5m floor heights"

Agent: I will build this incrementally, starting with the structural frame.

[Agent runs: bim storey "Ground Floor" --elevation 0]
[Agent runs: bim storey "Level 1" --elevation 4.5]
[Agent runs: bim storey "Roof" --elevation 9.0]

[Agent runs: bim column-grid "Grid GF" --storey "Ground Floor" --origin 0,0 --bays 5,3 --spacing 8,8 --column-size 0.3,0.3 --height 4.5]
  -> {"created": 24, "elements": ["Grid GF-Col-A1", ...]}

[Agent runs: bim column-grid "Grid L1" --storey "Level 1" --origin 0,0 --bays 5,3 --spacing 8,8 --column-size 0.3,0.3 --height 4.5]
  -> {"created": 24}

[Agent runs: bim floor-plate "GF Slab" --storey "Ground Floor" --corner 0,0 --size 40,24 --thickness 0.2 --elevation 0 --edge-beams --beam-size 0.3,0.5]
  -> {"created": 5, "slab": "GF Slab-Slab", "beams": 4}

[Agent runs: bim floor-plate "L1 Slab" --storey "Level 1" --corner 0,0 --size 40,24 --thickness 0.2 --elevation 4.5 --edge-beams --beam-size 0.3,0.5]

[Agent runs: bim info]
  -> {"storeys": 3, "columns": 48, "slabs": 2, "beams": 8}

Agent: Structure is in place. Adding envelope.

[Agent runs: bim perimeter-walls "GF Walls" --storey "Ground Floor" --corners 0,0 40,0 40,24 0,24 --height 4.5 --thickness 0.2]
  -> {"created": 4, "walls": ["GF Walls-Seg-01", "GF Walls-Seg-02", "GF Walls-Seg-03", "GF Walls-Seg-04"]}

[Agent runs: bim window "East Win 01" --storey "Ground Floor" --wall "GF Walls-Seg-02" --offset 4 --sill 0.9 --size 1.8,1.5]
[Agent runs: bim window "East Win 02" --storey "Ground Floor" --wall "GF Walls-Seg-02" --offset 10 --sill 0.9 --size 1.8,1.5]

[Agent runs: bim check]
  -> {"orphan_elements": 0, "validation_passed": true}

Agent: Building complete. The model has 3 storeys, 48 columns, 2 slabs with edge beams, 4 perimeter walls, and 2 windows. The IFC file is at out/model.ifc.
```

The agent works exactly like a human architect using a scripting console: create elements, inspect the model, make corrections, move on. No monolithic plan. No god-object schema. No system prompt. Just simple tools that do one thing well.

---

## Open Questions

1. **Model file locking.** If the agent runs multiple commands in parallel (e.g., in a batch), the IFC file needs to handle concurrent writes. Solution: `bim batch` opens the file once, executes all commands, saves once.

2. **Undo/rollback.** Should `bim` support undo? The simplest approach: snapshot the IFC file before each operation. More sophisticated: IFC transaction log.

3. **Metadata pass-through.** The current system carries rich metadata (semantics, presentation, foundation). The CLI should support this via `--metadata '{"semantics": {...}}'` or dedicated flags like `--role structure --subrole grid_column`.

4. **Integration with existing blender addon.** The Bonsai blender addon (`bonsai_ai_blender/runtime.py`) currently expects plans. It would need to either: (a) accept CLI commands via a socket, or (b) continue using the plan interface internally while the agent-facing interface is the CLI.

5. **Performance.** Opening and saving the IFC file per command adds overhead. For individual commands this is negligible. For 50+ sequential commands, batch mode or a persistent server mode (`bim serve` with HTTP endpoints) would be better.
