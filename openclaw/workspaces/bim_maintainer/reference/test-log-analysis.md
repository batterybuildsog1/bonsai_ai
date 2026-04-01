# Test Log Analysis: Model Tool Usage Patterns

Generated: 2026-03-30
Tests analyzed: simple_openai, simple_anthropic, medium_openai, medium_anthropic, hard_openai (failed), hard_anthropic (failed)
Planner mode: All tests used the **iterative planner** via OpenClaw agent sessions

---

## 1. Test Results Summary

| Test | Model | Actions | Errors | Turns | Time | Elements | Storeys |
|------|-------|---------|--------|-------|------|----------|---------|
| Simple warehouse | GPT-5.4 | 28 | 0 | 1 | 75s | 27 | 1/1 |
| Simple warehouse | Claude Opus 4.6 | 29 | 19 | 2 (+retry) | 131s | 27 | 1/1 |
| Medium office | GPT-5.4 | 113 | 0 | 1 | 137s | 111 | 2/2 |
| Medium office | Claude Opus 4.6 | 113 | 0 | 1 | 84s | 111 | 2/2 |
| Hard 5-story | GPT-5.4 | 0 | 1 | 0 | 0s | 0 | 0/5 |
| Hard 5-story | Claude Opus 4.6 | 0 | 1 | 0 | 0s | 0 | 0/5 |

---

## 2. Action Types and Generator Usage

### Simple Warehouse (both models)

Both models produced structurally identical IFC files with the same element names and positions:

- **1 `ensure_storey`** - Ground Floor at z=0
- **1 `generate_column_grid`** - 3 bays x 1 bay (8 columns total)
- **10 `create_beam`** - 6 along X (3 per row at y=0 and y=20) + 4 along Y
- **2 `create_rect_slab`** - Slab on grade + roof deck
- **1 `generate_perimeter_walls`** - 4 wall segments from corner polygon
- **3 `create_door`** - 2 overhead doors on south + 1 personnel door on east

Total compiled elements: 1 storey + 8 columns + 10 beams + 2 slabs + 4 walls + 3 doors = 28 elements.

Generators used effectively: `generate_column_grid` (instead of 8 individual columns) and `generate_perimeter_walls` (instead of 4 individual walls).

### Medium Office (both models)

Both models produced **byte-for-byte identical** IFC output (same 147 product names, same positions):

- **2 `ensure_storey`** - Ground Floor (z=0), Level 2 (z=4.0)
- **2 `generate_column_grid`** - 5 bays x 3 bays per floor = 24 columns each = 48 total
- **2 `generate_floor_plate`** with `include_edge_beams=true` - 2 slabs + 8 edge beams
- **1 `create_rect_slab`** - Ground floor slab at z=0
- **12 `create_beam`** - Interior beams (6 per level x 2 levels)
- **2 `generate_perimeter_walls`** - 4 walls per floor x 2 = 8 walls
- **30 `create_window`** - Windows on all sides, correctly excluding door positions
- **2 `create_door`** - Main entrance + rear exit

Total compiled elements: 2 storeys + 48 columns + 20 beams + 3 slabs + 8 walls + 30 windows + 2 doors = 113 compiled actions, 111 IFC elements.

---

## 3. Claude's 19 Errors on Simple Test

### What happened

The iterative planner uses OpenClaw agent sessions. The flow for Claude's simple test:

1. **Turn 1**: Claude generated a JSON plan with 19 actions. **All 19 failed** during compilation (`_execute_actions` returned `applied=0, failed=19`).
2. **Turn 1 retry**: The error feedback was sent back to Claude. Claude corrected and generated a new plan. **28 actions applied successfully.**
3. **Turn 2**: Claude sent 1 additional action. Total: 29 applied, 19 errors.

### Root cause (inferred)

No `build_log.txt` exists because the iterative planner does not write one (only the direct planner does). However, the error pattern -- all 19 actions failing in a batch -- indicates a **compilation failure** rather than individual authoring errors:

- `_execute_actions` compiles all actions together via `compile_core_plan(plan)`. If compilation raises an exception, it returns `(0, len(actions), ["Compilation failed: ..."])`.
- 19 actions failing with 0 applied means the entire compilation failed.

Most likely causes:
1. **Action type names not matching**: Claude may have used `create_slab` instead of `create_rect_slab`, or `create_column_grid` instead of `generate_column_grid`. The `_normalize_actions` function handles some aliases but not all possible variations.
2. **Field name mismatches**: Claude may have used `storey` instead of `storey_name`, or different coordinate field names.
3. **Schema structure differences**: The iterative planner tells the agent to respond with `{version, units, summary, assumptions, actions}` but Claude may have used a different JSON structure (e.g., wrapping in another object, using `kind` instead of `type`).

The fact that the retry succeeded after error feedback confirms this was a **format/schema mismatch** that Claude corrected once it saw the specific validation error.

### Why GPT-5.4 did not have this problem

GPT-5.4 generated valid actions on the first attempt (1 turn, 0 errors). This suggests GPT-5.4 more closely followed the JSON schema specification in the initial prompt, or its default structured output behavior aligned better with the expected format.

---

## 4. Why Both Models Produce Identical Medium Results (113 actions)

The IFC files are **structurally identical** between GPT-5.4 and Claude Opus 4.6 for both tests:
- Same element names (e.g., "Ground Floor Column Grid-Col-A1")
- Same positions (coordinates match exactly)
- Same element counts

This is because:
1. **The plan schema is highly constrained**. The system prompt specifies exactly which generators to use and the prompt provides exact coordinates.
2. **Generators are deterministic**. `generate_column_grid` with 5 bays x 3 bays always produces 24 columns at the same positions.
3. **The prompt is fully specified**. Window positions (x=2,6,10,14,18), door locations (x=10), column grid dimensions -- everything is given explicitly. There is very little room for model interpretation.

The 113 action count breaks down as: 2 storeys + 2 column grids + 2 floor plates + 1 slab + 12 individual beams + 2 perimeter wall generators + 30 windows + 2 doors = 53 authored actions. After generator compilation: 2 + 48 + (2 slabs + 8 beams) + 1 + 12 + 8 + 30 + 2 = 113 compiled actions.

---

## 5. Hard Test Failures

Both hard tests (5-story commercial building) failed with `errors=1, total_actions=0, notes="no IFC"`. The output directories exist but are empty.

Since no IFC, plan.json, or scene_analysis.json were written, the failure occurred **before any planning**. Looking at the test matrix runner code:

```python
except Exception as exc:
    print(f"    FAILED: {exc}")
    summary = { "total_actions": 0, "errors": 1, ... }
```

The top-level exception handler caught the error. Possible causes:
1. **OpenClaw agent timeout** (`_SESSION_TIMEOUT = 900s`) -- unlikely since elapsed=0
2. **OpenClaw binary not found** or session creation failed
3. **API error** during the initial planning call (model refused, rate limit, etc.)
4. **JSON extraction failure** from agent response -- the 5-story prompt may have produced a response the `_extract_json` function could not parse

Since `elapsed_seconds=0`, the failure was immediate, not a timeout. Most likely: the `IterativeBuilder` constructor or initial `_call_agent` call threw an exception.

**No hard test JSON structure is available to inspect** because the failure prevented any output file creation.

---

## 6. Slab Dimension Swap Bug

### Discovery

The IFC files show a systematic slab dimension swap:

| Slab | Expected L x W | IFC L x W | Status |
|------|----------------|-----------|--------|
| Simple: Slab on Grade | 30 x 20 | 20 x 30 | SWAPPED |
| Simple: Roof Deck | 30 x 20 | 20 x 30 | SWAPPED |
| Medium: Ground Floor Slab | 20 x 15 | 15 x 20 | SWAPPED |
| Medium: Level 2 Floor Plate | 20 x 15 | 20 x 15 | CORRECT |
| Medium: Roof Floor Plate | 20 x 15 | 20 x 15 | CORRECT |

### Root cause

The bug is in `iterative_planner.py` line 194:

```python
if action.get('type') in ('create_rect_slab', 'create_rectangular_slab'):
    if (not action.get('depth')) and action.get('length'):
        action['depth'] = action.pop('length')
```

This maps `length` to `depth` instead of maintaining axis alignment. The flow:

1. Model outputs: `{length: 30, width: 20}` (length=X-axis, width=Y-axis)
2. `_normalize_actions`: `depth = length = 30`, removes `length`. Now: `{width: 20, depth: 30}`
3. Core compiler `_coerce_numeric_fields`: sees `width=20` and `depth=30`, no coercion needed
4. `_to_tool_call`: `length = action.get('length', action['width']) = 20`, `width = action.get('depth', action['width']) = 30`
5. IFC author: creates slab with `length=20` (X-axis) and `width=30` (Y-axis)
6. **Result**: Slab is 20m along X and 30m along Y instead of 30m x 20m. The slab extends 10m beyond the building footprint in Y.

The `generate_floor_plate` path does NOT have this bug because it goes through `_compile_floor_plate` in the compiler, which correctly maps `length` to `width` (X-axis) and `width` to `depth` (Y-axis) in the compiled slab.

### Impact

The slab geometry is rotated 90 degrees when created via `create_rect_slab` through the iterative planner. The slab extends beyond the building footprint defined by columns and walls. This affects the scene_summary bounding box (reports Y=[-0.15, 30.0] instead of Y=[-0.15, 20.15] for the simple warehouse).

### Fix

```python
# In iterative_planner.py _normalize_actions:
# CURRENT (buggy):
if (not action.get('depth')) and action.get('length'):
    action['depth'] = action.pop('length')

# SHOULD BE:
if action.get('length') and not action.get('width'):
    action['width'] = action.pop('length')
elif action.get('length') and action.get('width') and not action.get('depth'):
    action['depth'] = action.get('width')
    action['width'] = action.pop('length')
```

Or simply remove this normalization and let the core compiler's `_coerce_numeric_fields` handle it (it already does this correctly).

---

## 7. Generator Effectiveness

Generators are used **effectively** by both models:

| Generator | Simple | Medium | Replaces |
|-----------|--------|--------|----------|
| `generate_column_grid` | 1 call -> 8 cols | 2 calls -> 48 cols | 8/48 individual `create_column` |
| `generate_perimeter_walls` | 1 call -> 4 walls | 2 calls -> 8 walls | 4/8 individual `create_wall` |
| `generate_floor_plate` | 0 | 2 calls -> 2 slabs + 8 beams | 2 `create_rect_slab` + 8 `create_beam` |
| `generate_facade_grid` | 0 | 0 | Not applicable for these prompts |

For the simple test, models used generators for columns (1 action -> 8 elements) and walls (1 action -> 4 elements), but used individual `create_beam` calls for all 10 beams. This is appropriate because the beams are not on a regular grid suitable for a generator.

For the medium test, `generate_floor_plate` with `include_edge_beams=true` efficiently created floor slabs + perimeter beams in one call. Interior beams were correctly specified individually since they don't follow a pattern that any generator covers.

No model fell back to individual primitives where generators were appropriate.

---

## 8. Planner Rounds Per Test

| Test | Model | Planning Rounds | Retry Rounds | Total Agent Calls |
|------|-------|----------------|--------------|-------------------|
| Simple | GPT-5.4 | 1 | 0 | 1 |
| Simple | Claude Opus 4.6 | 2 | 1 | 3 |
| Medium | GPT-5.4 | 1 | 0 | 1 |
| Medium | Claude Opus 4.6 | 1 | 0 | 1 |
| Hard | Both | 0 | 0 | Failed before planning |

GPT-5.4 always completed in a single round. Claude needed error recovery on the simple test but completed the medium test in a single round (suggesting Claude learned from training rather than from this specific session).

---

## 9. What Makes the Tool Interface Hard for Models

### Problem 1: Dual naming conventions (HIGHEST IMPACT)

The system has **three different naming systems** for the same concepts:

| Concept | Core schema | Tool spec | Bridge schema | IFC author |
|---------|-------------|-----------|---------------|------------|
| Slab X-extent | `width` | `length` | `width` | `length` |
| Slab Y-extent | `depth` | `width` | `depth` | `width` |
| Storey reference | `storey` | `storey_name` | `storey` | `storey_name` |
| Action type | `create_rect_slab` | `create_rectangular_slab` | `create_slab` | `create_rectangular_slab` |

The `length/width` confusion is the most damaging:
- The **tool spec** tells models: `length = "Slab extent along the X axis"`, `width = "Slab extent along the Y axis"`
- The **core compiler** uses: `width = X-axis`, `depth = Y-axis`
- The **IFC author** uses: `length = X-axis`, `width = Y-axis`
- The **iterative planner normalization** incorrectly maps `length -> depth`

Models output `{length: X, width: Y}` following the tool spec, but the normalization layer corrupts this.

### Problem 2: Inconsistent coordinate semantics

- **Slabs**: `x/y` is the **bottom-left corner** (origin)
- **Columns**: `x/y` is the **center**
- **Walls**: defined by `start_x/start_y -> end_x/end_y` (endpoints)
- **Beams**: defined by `start_x/start_y -> end_x/end_y` (endpoints) or `x/y` (legacy)
- **Doors/Windows**: defined by `wall_name + offset_along_wall` (hosted)

The system prompt says this clearly, but it's still a source of potential errors because there are 4 different placement paradigms.

### Problem 3: Build order dependencies

Doors and windows **require** a host wall to exist first. The system prompt says "Build storeys first, then structure, then envelope, then openings." But:
- If a model interleaves door creation with wall creation, the door's `wall_name` reference may fail
- The wall name must match **exactly** (e.g., "Warehouse Perimeter Walls-Seg-01" not "South Wall")
- Generator-produced wall names include auto-generated suffixes (-Seg-01, -Seg-02) that the model must predict

### Problem 4: Generator parameter vs primitive parameter overlap

When using `generate_column_grid`, the parameters are `column_width/column_depth/column_height` with `bays_x/bays_y/spacing_x/spacing_y`. But for individual `create_column`, they are just `width/depth/height` with `x/y`. This is reasonable but adds cognitive load.

### Problem 5: Schema complexity for metadata

Each action can optionally include `semantics`, `presentation`, and `foundation` objects with 15+, 5+, and 20+ optional fields respectively. While these are all optional, their presence in the schema adds noise. Models generally ignore these (which is fine for basic geometry), but the schema size may affect structured output performance.

### Problem 6: Multiple normalization layers

Actions pass through up to 4 normalization/coercion steps:
1. `iterative_planner._normalize_actions` (type aliases, field aliases, numeric coercion)
2. `schema._coerce_numeric_fields` (field renaming for length/width/depth)
3. `compiler._compile_action` (generator expansion)
4. `planner._to_tool_call` (another round of field mapping)

Each layer has slightly different rules. A field name that passes layer 1 might fail at layer 3. This makes debugging difficult and creates subtle bugs like the slab dimension swap.

---

## 10. Key Findings and Recommendations

### What works well
- Both models use generators effectively (not falling back to primitives)
- Both models follow the prompt's coordinate specifications accurately
- Both models handle multi-storey buildings correctly (column grids, floor plates, walls per floor)
- Window placement correctly accounts for door positions
- The iterative retry mechanism successfully recovered from Claude's first-attempt errors

### What needs fixing
1. **Slab dimension swap bug** in `iterative_planner._normalize_actions` (length -> depth instead of maintaining axis alignment)
2. **Missing error logging** in iterative planner (no build_log.txt, making debugging impossible)
3. **Hard test failure** produces no diagnostic output at all
4. **Naming inconsistency** across the four schema surfaces (core, tool spec, bridge, IFC author)

### What would improve model success rate
1. Unify `length/width/depth` naming across all layers to a single convention
2. Add the iterative planner's normalization as a build_log.txt with full error details
3. For the hard test, catch and log the specific exception before it propagates
4. Reduce the schema to only the fields the model actually uses (most metadata is ignored)
5. Auto-generate wall names in a predictable pattern documented in the prompt
