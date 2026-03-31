# Direct Planner vs Phased Planner: Quality Comparison

**Date**: 2026-03-30
**Builds compared**:
- `retail_terrace_concept` -- direct planner (legacy iterative loop)
- `five_story_mezzanine` -- phased planner (`create_phased_plan_via_openclaw`)

---

## 1. Output Quality Summary

| Metric | retail_terrace (direct) | five_story_mezzanine (phased) |
|---|---|---|
| Storeys | 4 | 5 |
| Columns | 52 | 174 |
| Beams | 92 | 40 |
| Slabs | 4 | 9 |
| Walls | 8 | **0** |
| Curtain Walls | 0 | 4 |
| Plates | 7 | 330 |
| Doors | 4 | **0** |
| Windows | 17 | **0** |
| Footings | 6 | 0 |
| Total errors | 0 (clean build) | Multiple across attempts |
| Build time | N/A (scripted) | ~92s (final successful run) |

**Verdict**: The phased planner produces structurally complete models (storeys, columns, slabs, curtain walls all work) but **systematically fails on openings (windows and doors)** and has intermittent compilation failures on mezzanines and beams.

---

## 2. Architecture Differences

### Direct Planner Path (`planner.py` + `cli.py`)

```
User prompt
  -> build_core_plan()          # calls provider API with structured tool schema
  -> compile_core_plan()        # compiler normalizes + expands generators
  -> _to_tool_call()            # maps compiled fields to ifc_author parameters
  -> author.apply_tool_call()   # writes IFC
  -> [up to 12 repair rounds with scene context]
```

Key properties:
- **Provider API handles structured output**: The AI provider (OpenAI, Anthropic, Gemini) receives the full JSON schema via `build_core_plan()` and returns structured tool calls. Field names are enforced by the schema.
- **12-round iterative repair loop**: Failures get targeted repair prompts with scene context. Structural failures trigger full replans.
- **Single coherent context**: The model sees the entire building request plus all progress in every round.

### Phased Planner Path (`phased_planner.py`)

```
User prompt
  -> _plan_phases() via openclaw  # Phase 1: decompose into ~5 phases
  -> for each phase:
       _build_execution_prompt()  # focused ~800-1400 char prompt
       _call_openclaw()           # subprocess call to openclaw agent
       _extract_json()            # parse free-text JSON from response
       _normalize_actions()       # fix field names, type aliases
       compile_core_plan()        # same compiler as direct path
       _to_tool_call()            # same field mapping as direct path
       author.apply_tool_call()   # same IFC authoring
```

Key properties:
- **Free-text JSON generation**: The openclaw agent generates JSON as plain text, not via structured output API.
- **Single retry per phase**: If a phase fails completely, it retries once -- no targeted repair.
- **Phase isolation**: Each phase sees only what previous phases built, not the full building context.

---

## 3. The Field Name Translation Chain (Critical Path Analysis)

Both planners ultimately share the same final two steps:

```
compile_core_plan() output  -->  _to_tool_call()  -->  ifc_author methods
```

### What the compiler produces vs what ifc_author expects

| Element | Compiler output fields | `_to_tool_call()` mapping | ifc_author expects |
|---|---|---|---|
| **Wall** | `x1, y1, x2, y2` | `start_x=x1, start_y=y1, end_x=x2, end_y=y2` | `start_x, start_y, end_x, end_y` |
| **Beam** | `x1, y1, x2, y2` | `start_x=x1, start_y=y1, end_x=x2, end_y=y2` | `start_x, start_y, end_x, end_y` |
| **Curtain wall** | `x1, y1, x2, y2` | Converts to `x, y, width, rotation_degrees` | `x, y, width, height, rotation_degrees` |
| **Slab** | `x, y, z, width, depth` | `length=width, width=depth` | `length, width` (confusing but correct) |
| **Column** | `x, y, base_z, width, depth, height` | Passthrough | `x, y, base_z, width, depth, height` |
| **Storey** | `name, elevation` | Passthrough | `name, elevation` |
| **Window** | `wall_name, offset_along_wall, sill_height, width, height, thickness` | Passthrough | Same |
| **Door** | `wall_name, offset_along_wall, width, height, thickness` | Passthrough | Same |

**Finding**: The `_to_tool_call()` function correctly translates the compiler's `x1/y1/x2/y2` to ifc_author's `start_x/start_y/end_x/end_y` for walls and beams. This mapping works identically for both planners because both route through the same `_to_tool_call()` function.

### Where the phased planner adds its own normalization

Before reaching `compile_core_plan()`, the phased planner runs `_normalize_actions()` which:

1. **Type aliases** (`_TYPE_ALIASES`):
   - `create_rectangular_slab` -> `create_rect_slab`
   - `create_slab` -> `create_rect_slab`
   - `create_column_grid` -> `generate_column_grid`
   - etc.

2. **Field aliases** (`_FIELD_ALIASES`):
   - `storey` -> `storey_name`

3. **Beam-specific field aliases** (`_BEAM_FIELD_ALIASES`):
   - `start_x` -> `x1`, `start_y` -> `y1`, `end_x` -> `x2`, `end_y` -> `y2`

4. **Numeric coercion**: Strips unit suffixes like "0.5m" -> 0.5

**Finding**: This normalization is correct and well-designed. But it has a **gap**: if the LLM produces `create_rectangular_slab` without being caught by `_TYPE_ALIASES`, the compiler rejects it (see build_log_phased4.txt line 21: `Action 0 has unsupported type 'create_rectangular_slab'`). Wait -- that IS in `_TYPE_ALIASES`. This means the alias mapping may have been missing in an earlier version, or the normalization wasn't running. The final code does include it.

---

## 4. Root Cause of Quality Issues

### Issue 1: Openings phase produces 0 windows and 0 doors (CRITICAL)

**Cause**: The building has no `IfcWall` elements. The envelope phase generates curtain walls (`IfcCurtainWall`) and panels (`IfcPlate`) instead of `IfcWall`. Windows and doors require a host `IfcWall` -- they cannot be hosted in curtain walls.

**Why this happens with the phased planner but not the direct planner**:
- The **direct planner** builds walls AND curtain walls in the same plan, and the iterative repair loop can see that windows need walls and adjust.
- The **phased planner** has separate envelope and openings phases. The envelope phase instruction says to use `create_wall, generate_perimeter_walls, create_curtain_wall, generate_facade_grid, create_panel`. The LLM picks curtain walls for all facades because it is a commercial building. When the openings phase runs, there are no `IfcWall` entities to host windows.
- The phased planner DOES have a mitigation (line 377-386) that tells the openings phase not to place windows on curtain walls. But instead of creating walls first, it just skips the openings entirely.

**Evidence** from build_log_phased4.txt:
```
ERROR: create_window(Level 2 West Window 01): Wall not found: West Metal Facade
ERROR: create_door(Main South Entrance): Wall not found: South Ground Floor Glass Facade
```

From build_log_final.txt (the successful run): openings phase produced 0 actions. The model saw no walls in the scene and correctly skipped all openings -- but the result is a building with no windows or doors.

### Issue 2: Mezzanine compilation failures (MODERATE)

**Cause**: The LLM sometimes omits the `depth` field for `create_rect_slab` actions, or provides it as `null`. The `_normalize_actions()` function tries to handle this (lines 499-504: if `depth` is missing but `length` is set, use `length` as `depth`), but if both are missing or the LLM provides neither, the compiler rejects it.

**Evidence** from build_log_fix.txt:
```
ERROR: Compilation failed: Action 0 field 'depth' must be numeric.
```

From build_log_fix2.txt:
```
DEBUG: mezzanines action[0] field 'depth' = None (type NoneType)
```

**Why this doesn't happen with the direct planner**: The direct planner uses the provider's structured output API, which enforces the schema. The LLM cannot omit required fields when the provider validates the JSON schema.

### Issue 3: Beam field mismatch (MODERATE)

From build_log_phased4.txt:
```
ERROR: Compilation failed: Action 2 create_beam must provide either endpoint fields
x1/y1/x2/y2/base_z/width/depth or origin fields x/y/base_z/width/depth/height.
```

**Cause**: The LLM generated a beam with `start_x/start_y` fields, but the `_BEAM_FIELD_ALIASES` normalization in `_normalize_actions()` should handle this. This error likely occurred in an earlier version before `_BEAM_FIELD_ALIASES` was added, or the normalization wasn't applied (e.g., if `_normalize_actions()` ran after an exception path that skipped it).

### Issue 4: Facade `start_x` non-numeric (MINOR)

From build_log_fix.txt:
```
ERROR: Compilation failed: Action 0 field 'start_x' must be numeric.
```

**Cause**: The LLM produced `start_x` as a string or null for a `generate_facade_grid` action. The `_normalize_actions()` coercion handles string-to-number conversion but cannot fix null values.

---

## 5. Specific Answers to Hypotheses

### Q: Does the core compiler expect `x1/y1/x2/y2` for beams while ifc_author expects `start_x/start_y/end_x/end_y`?

**Yes, exactly.** The compiler schema validates beams with `x1/y1/x2/y2/base_z/width/depth`. The `_to_tool_call()` function in `planner.py` (line 139-153) maps:
```python
"start_x": action["x1"],
"start_y": action["y1"],
"end_x": action["x2"],
"end_y": action["y2"],
```

This works correctly for both planners because both route through `_to_tool_call()`.

However, the phased planner's `_normalize_actions()` also normalizes in the REVERSE direction for beams (line 487-490):
```python
_BEAM_FIELD_ALIASES = {
    "start_x": "x1",   # compiler expects x1
    "start_y": "y1",
    "end_x": "x2",
    "end_y": "y2",
}
```

This is correct: LLM writes `start_x` -> normalized to `x1` -> compiler validates `x1` -> `_to_tool_call()` maps back to `start_x` for ifc_author.

### Q: Does the core compiler expect `storey` while ifc_author expects `storey_name`?

**Both are handled.** The compiler uses `storey` internally. The `_to_tool_call()` function (line 105) does:
```python
storey_name = action.get("storey_name") or action.get("storey")
```
And then passes `storey_name` to ifc_author. The phased planner's `_FIELD_ALIASES` normalizes `storey` -> `storey_name` before compilation, which also works because the compiler's `_coerce_numeric_fields` (schema.py line 274) handles `storey_name` -> `storey` for windows/doors.

### Q: Does the compilation step change coordinate values?

**Only for generators.** Simple primitives (create_wall, create_beam, create_column, create_rect_slab) pass through unchanged. But generators compute coordinates:
- `generate_column_grid` calculates grid positions from `grid_origin_x/y`, `spacing_x/y`, `bays_x/y`
- `generate_floor_plate` calculates beam endpoints from slab corners
- `generate_facade_grid` passes through to a single curtain wall
- `generate_perimeter_walls` converts corners array to individual wall segments

These coordinate transformations are deterministic and the same for both planners.

### Q: Are there field transformations that could produce wrong positions?

**No erroneous transformations found.** The `_to_tool_call()` mapping is faithful. The slab field mapping is the most confusing:
```python
"length": action.get("length", action["width"]),
"width": action.get("depth", action["width"]),
```
The compiler calls them `width` and `depth`, but ifc_author calls them `length` and `width`. The mapping is semantically: compiler.width -> ifc_author.length (X extent), compiler.depth -> ifc_author.width (Y extent).

---

## 6. The Real Problem: Architecture, Not Field Mapping

The field mapping between compiler and ifc_author is **correct and consistent** across both planners. The phased planner's quality issues are NOT caused by field name mismatches. They stem from three architectural issues:

### 6a. Free-text JSON vs Structured Output

The direct planner uses provider structured output APIs (OpenAI tool calling, Anthropic tool_use, etc.) which enforce the JSON schema. Fields cannot be omitted or null when the schema says `required`. The phased planner generates free-text JSON via openclaw, so the LLM can:
- Omit required fields (depth=null for slabs)
- Use wrong field names (before normalization catches them)
- Produce non-numeric values for numeric fields

**Impact**: Intermittent compilation failures (mezzanines, beams, facades).

### 6b. Phase Isolation Prevents Cross-Concern Reasoning

The most damaging issue. The prompt asks for "punched windows on east and west facades." The LLM needs to reason:
1. Windows require IfcWall host elements
2. Therefore the envelope phase must create walls (not curtain walls) on the east and west facades
3. Only then can the openings phase host windows in those walls

With the direct planner, the model sees the entire request and can reason across element types. With the phased planner, the envelope phase only knows it should create "facades" and picks curtain walls because they are the natural choice for commercial cladding. By the time the openings phase runs, it is too late.

**Impact**: Complete loss of windows and doors in the final model.

### 6c. Insufficient Error Recovery

The direct planner has up to 12 rounds of iterative repair with targeted prompts. The phased planner retries each phase once, without targeted repair. When a phase fails, the phased planner:
1. Retries with the same prompt (often produces the same error)
2. Moves on, leaving the phase incomplete
3. Downstream phases inherit the incomplete state

**Impact**: Cascading failures -- failed structure phase means no beams, failed envelope means no walls for openings.

---

## 7. Recommendations

### Short-term fixes (address the wall/window problem)

1. **Envelope phase prompt awareness**: When the building request mentions windows or doors on a facade, the envelope phase prompt must instruct the LLM to use `create_wall` (not `create_curtain_wall`) for that facade. Add a pre-analysis step that detects window/door mentions and annotates which facades need walls.

2. **Hybrid facade strategy**: Allow the envelope phase to create walls for facades that need openings, and curtain walls for facades that don't. The phase prompt should explicitly say: "Use create_wall for facades where windows or doors are needed. Use create_curtain_wall only for fully glazed facades without punched openings."

### Medium-term fixes (address compilation reliability)

3. **Add retry with error feedback**: When compilation fails, send the error message back to openclaw as a repair prompt (like the direct planner's targeted repair). Currently the phased planner retries with the identical prompt.

4. **Validate before compile**: Run a lightweight field-presence check on each action before passing to `compile_core_plan()`. Fill in missing required fields with sensible defaults or reject the action with a clear error that can guide the retry prompt.

5. **Use structured output when available**: If openclaw supports a `--schema` flag or JSON mode, use it to constrain the LLM output format.

### Long-term fix (address the architecture gap)

6. **Cross-phase dependency analysis**: Before executing phases, analyze the building request to identify cross-phase dependencies (e.g., "windows need walls, therefore envelope must create walls on windowed facades"). Inject these constraints into each phase's prompt.

7. **Consider a hybrid approach**: Use the phased planner for decomposition and token efficiency, but run the openings phase through the direct planner's iterative loop with full scene context and targeted repair.

---

## 8. Files Referenced

| File | Role |
|---|---|
| `/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/cli.py` | CLI entry point, direct planner's 12-round loop |
| `/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/planner.py` | Direct planner: `build_core_plan` + `compile_core_plan` + `_to_tool_call` |
| `/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/phased_planner.py` | Phased planner: phase decomposition, normalization, execution |
| `/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_core/compiler.py` | Core compiler: generator expansion, action compilation |
| `/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_core/schema.py` | Schema validation and numeric coercion |
| `/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_core/semantic_model.py` | Semantic model normalization |
| `/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/ifc_author.py` | IFC authoring: actual element creation |
| `/Users/alanknudson/Applications/Bonsai_ai/out/retail_terrace_concept/` | Direct planner output (reference quality) |
| `/Users/alanknudson/Applications/Bonsai_ai/out/five_story_mezzanine/` | Phased planner output + build logs |
