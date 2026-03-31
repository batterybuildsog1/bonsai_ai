# Bonsai AI Planner Harness Audit

> Audit date: 2026-03-30
> Auditor: Claude Opus 4.6 (automated)
> Scope: SYSTEM_PROMPT, tool schemas, plan schema, compilation pipeline
> Concern: over-constraining models, causing bad outputs

---

## Executive Summary

The planner harness has **three significant architectural issues** and **several medium-severity prompt problems** that are likely degrading output quality. The biggest problem is not the system prompt itself -- it is that the model receives a 67-property "god object" action schema where every action type shares every field, forcing the model to reason about 60+ irrelevant properties per action. The system prompt (598 words, ~1,100 tokens) is actually reasonable in length, but it contains contradictions and unnecessarily prescriptive rules that conflict with best practices for GPT-5.4 and Claude Opus 4.6.

---

## Issues Found

### CRITICAL (will cause wrong geometry or failures)

#### Issue 1: Slab field naming mismatch across surfaces
**Severity: Critical**

The create_rect_slab action uses `width` and `depth` in the plan schema (action_catalog.py), but the system prompt's coordinate convention rule says `length` and `width`, and the tool spec (tool_specs.py) uses `length` and `width`. The model sees all three surfaces.

- Plan schema (what the model outputs): `x, y, z, width, depth, thickness`
- System prompt rule: "A slab at x=0, y=0 with length=40, width=25 spans from (0,0) to (40,25)"
- Tool spec (direct planner path): `x, y, z, length, width, thickness`

The `_to_tool_call()` mapper in `src/bonsai_ai/planner.py` (line 115-116) handles this with fallbacks, but the model is being trained on contradictory naming. This wastes reasoning tokens as the model reconciles the mismatch.

**Fix**: Standardize on `length` and `width` everywhere, or `width` and `depth` everywhere. Pick one and update all surfaces.

---

#### Issue 2: 67-property "god object" action schema
**Severity: Critical**

The plan schema (`COMMON_ACTION_PROPERTIES` in action_catalog.py) puts ALL 67 properties on EVERY action item, with `additionalProperties: false`. This means:

- A simple `ensure_storey` action (needs `type`, `name`, `elevation`) is presented to the model alongside 64 irrelevant fields (`panel_width`, `riser_height`, `corners`, `beam_depth`, etc.)
- The schema is ~4,600 tokens. The model must parse and reason about ALL of it for EVERY action.
- OpenAI's structured output CFG engine must evaluate 67 possible properties at each token -- this directly impacts latency.
- With `additionalProperties: false`, the model cannot add ANY field the schema does not define, but the schema already defines everything, so this is moot -- the real cost is cognitive load.

This violates OpenAI's recommendation of max 100 properties total and "err on the side of making arguments flat" -- flat is good, but 67 properties on one object is not flat, it is bloated.

**Fix**: Use discriminated union (oneOf/anyOf) so each action type only shows its own fields. Or move to the tool-call path where each tool has its own focused schema.

---

#### Issue 3: Two conflicting planner paths with divergent schemas
**Severity: Critical**

There are TWO planner codepaths:

1. **Core planner** (`bonsai_ai_core/planner.py`): Uses `plan_schema()` as `response_format` / structured output. The model outputs a JSON plan with action type names like `create_rect_slab`, `create_wall`, etc. (22 action types). No tool calling.

2. **Direct planner** (`src/bonsai_ai/planner.py`): Calls the core planner, then compiles the plan, then maps compiled actions to tool calls using `_TOOL_NAME_MAP` (10 mapped types). Tool specs use different names (`create_rectangular_slab` vs `create_rect_slab`).

The tool_specs.py defines 15 tools with their own schemas, but these are NEVER sent to the model during plan generation. They are only used for downstream execution. Meanwhile, the model sees the god-object plan schema.

**This means the detailed, well-crafted tool descriptions in tool_specs.py (e.g., "Bottom-left corner origin X in meters (NOT center)") are invisible to the model during planning.** The model only sees generic `_number("X coordinate in meters.")` from the action catalog.

**Fix**: Either (a) send tool_specs as tools and use tool calling for plan generation, or (b) port the detailed field descriptions from tool_specs into the action_catalog schema.

---

### HIGH (degrades output quality significantly)

#### Issue 4: System prompt tells model both WHAT and HOW
**Severity: High**

The system prompt mixes high-level intent ("Prefer a small number of clear actions") with implementation micro-management ("A create_stair_run should include x, y, base_z, width, tread_depth, riser_height, step_count, thickness, and optional direction_deg"). The field-level instructions duplicate what the schema already enforces via `required`.

Lines that duplicate the schema and should be removed:
- "A create_stair_run should include x, y, base_z, width, tread_depth, riser_height, step_count, thickness, and optional direction_deg."
- "A create_stair_landing should include x, y, base_z, width, depth, thickness, and optional direction_deg."
- "Steel connection details should prefer create_connection_plate actions with center_x, center_y, base_z, width, depth, and thickness."

These cost ~80 tokens and add zero value because the schema already enforces required fields. Worse, they may conflict if the schema changes and the prompt is not updated.

**Fix**: Remove all field-listing sentences. The schema is the source of truth for required fields.

---

#### Issue 5: "Use only these action types" is a creativity trap
**Severity: High**

Line 18: "Use only these action types: ensure_storey, create_rect_slab, create_wall, create_column, create_beam, create_panel, create_window, create_door, create_curtain_wall, create_footing, create_stair_run, create_stair_landing, create_connection_plate, generate_column_grid, generate_perimeter_walls, generate_floor_plate, generate_facade_grid, update_element, delete_element, move_element, replace_section, rebuild_branch."

This is 45 words listing 22 action types that are ALREADY constrained by the schema's `type` enum. The model literally cannot output an action type not in the enum when using structured output. This instruction:
- Wastes ~55 tokens
- Is redundant with the schema constraint
- Is the SECOND line of the prompt, pushing important context down
- GPT-5.4 penalizes redundant/contradictory instructions by spending reasoning tokens reconciling them

**Fix**: Remove this line entirely. The schema enum enforces it.

---

#### Issue 6: COORDINATE CONVENTION rule is counterproductive
**Severity: High**

Line 50: "COORDINATE CONVENTION: For slabs and panels, x/y is the BOTTOM-LEFT CORNER ORIGIN (not center). A slab at x=0, y=0 with length=40, width=25 spans from (0,0) to (40,25). For columns, x/y IS the center point. Match column grid origins with slab origins."

Problems:
1. Uses `length` and `width` while the schema has `width` and `depth` (see Issue 1).
2. The "(not center)" and "(NOT center)" emphasis in both the prompt and tool_specs creates a negative instruction pattern. Research shows models process negative instructions worse than positive ones. "The origin is the bottom-left corner" is better than "NOT center."
3. The tool_specs already have clear descriptions: "Bottom-left corner origin X in meters (NOT center)" -- but these are invisible to the model during planning (see Issue 3).
4. Claude Opus 4.6 documentation specifically warns that aggressive language ("CRITICAL", "MUST", "NOT") causes overtriggering. All-caps "COORDINATE CONVENTION" and "NOT center" fall into this pattern.

**Fix**: Replace with a positive-framed rule: "Slab and panel x/y is the bottom-left corner. Column x/y is the center point."

---

#### Issue 7: WALL vs CURTAIN WALL rule is overly restrictive
**Severity: High**

Line 51: "WALL vs CURTAIN WALL: If the design needs windows or doors on a facade, that facade MUST use create_wall (IfcWall), NOT create_curtain_wall. Windows and doors can only be hosted in IfcWall. Use curtain walls only for fully glazed facades without individual openings."

This is a valid technical constraint (IfcWindow/IfcDoor require an IfcWall host), but the phrasing is problematic:
1. "MUST" and "NOT" in all-caps triggers cautious behavior in both GPT-5.4 and Claude 4.6.
2. The model may now avoid curtain walls entirely to be "safe," even when the design clearly calls for a fully glazed facade.
3. It prevents a legitimate design pattern: a curtain wall with operable panels (not IfcDoor/IfcWindow, but panel openings).

**Fix**: State the technical fact without the aggressive framing: "Windows and doors require an IfcWall host. Curtain walls cannot host individual openings."

---

### MEDIUM (suboptimal but functional)

#### Issue 8: Missing storey-element coordination guidance
**Severity: Medium**

There is no guidance on how storeys relate to element placement. The model must figure out:
- Does `base_z` match the storey elevation?
- If a column spans two storeys, which storey does it belong to?
- Should slabs sit at the storey elevation or below it (top of slab at storey)?

This is a common source of misaligned geometry in BIM models.

**Fix**: Add one sentence: "Element base_z should match the elevation of its assigned storey. Multi-storey elements belong to their lowest storey."

---

#### Issue 9: No slab-column grid alignment guidance
**Severity: Medium**

The prompt says "Match column grid origins with slab origins" but does not explain what happens when a slab is offset from the grid. The `generate_floor_plate` + `generate_column_grid` generators each take independent origins with no enforcement that they align.

**Fix**: Add: "When using generate_column_grid and generate_floor_plate together, use the same origin coordinates."

---

#### Issue 10: Metadata instructions are noisy
**Severity: Medium**

Lines 33-38 instruct the model on `semantics`, `presentation`, and `foundation` metadata objects. These are optional enrichment fields that the model can use if helpful, but 6 lines of instruction on them (~90 tokens) pushes down more important content.

**Fix**: Compress to: "Use optional `semantics`, `presentation`, and `foundation` metadata objects for grouping, styling, and structural intent."

---

#### Issue 11: Editing instructions dominate the prompt
**Severity: Medium**

Lines 38-43 contain 6 lines of editing instructions (update_element, move_element, replace_section, rebuild_branch, target_id, patch, etc.). These are only relevant when editing an existing model. For new-building prompts (the majority use case), this is ~120 tokens of irrelevant instruction.

**Fix**: Move editing instructions to a separate system prompt section that is only included when `scene_summary` or `selection_context` is present in the user prompt.

---

#### Issue 12: `ensure_project` exists in tool_specs but not in the plan schema
**Severity: Medium**

`tool_specs.py` defines an `ensure_project` tool, but the plan schema's action type enum does not include it, and `SUPPORTED_ACTIONS` does not list it. The model cannot generate this action via the core planner path. This is either dead code or a missing feature.

**Fix**: Either add `ensure_project` to `SUPPORTED_ACTIONS` and the plan schema, or remove it from tool_specs.

---

#### Issue 13: Prompt caching is only enabled for Anthropic
**Severity: Medium**

The `AnthropicProvider` (providers.py line 173-195) correctly uses `cache_control: {"type": "ephemeral"}` on system prompt and tools. But for OpenAI, no explicit caching optimization is done (though OpenAI auto-caches at 1,024+ tokens). For Google/Gemini, no caching is used at all.

More importantly, the prompt structure does not maximize cache hits: the system prompt includes no variable content, but the schema is inlined via `response_format` which may change between requests if schema definitions are updated.

---

### LOW (minor improvements)

#### Issue 14: `strict: False` in OpenAI provider
**Severity: Low**

`providers.py` line 93: `"strict": False` on the OpenAI response_format JSON schema. The research document explicitly recommends `strict: true` for production. With `strict: False`, the model can produce structurally non-compliant JSON, requiring the retry loop (3 attempts) in `build_plan()`.

**Fix**: Set `"strict": True`. The only reason to use `False` is if the schema exceeds OpenAI's 100-property limit -- and with 67 action properties + nested objects, it may actually exceed it. This circles back to Issue 2.

---

#### Issue 15: Retry loop error messages are vague
**Severity: Low**

`bonsai_ai_core/planner.py` line 74: "The previous JSON plan was invalid." does not tell the model WHAT to fix. The `repair_note` contains the validation error, but the surrounding text is verbose. GPT-5.4's prompting guide recommends precise, minimal correction instructions.

---

## Before/After: Most Impactful Changes

### Change 1: System Prompt (current vs recommended)

**Before** (598 words, ~1,100 tokens):

```
You are Bonsai AI, a BIM planning model for Blender + Bonsai.

Return only JSON that matches the provided schema.

Rules:
- Use metric units in meters.
- Use only these action types: ensure_storey, create_rect_slab, ...
[40 lines of rules]
```

**After** (see Minimal Prompt below, 290 words, ~540 tokens):

50% reduction. Removes all schema-redundant instructions, compresses metadata/editing guidance, reframes negative instructions as positive ones.

### Change 2: Plan Schema (god object -> discriminated)

**Before**: One action object with 67 properties, all shared across 22 action types.

**After** (recommended architecture):

```json
{
  "actions": {
    "type": "array",
    "items": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "type": {"const": "ensure_storey"},
            "name": {"type": "string"},
            "elevation": {"type": "number"}
          },
          "required": ["type", "name", "elevation"],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "type": {"const": "create_rect_slab"},
            "name": {"type": "string"},
            "storey": {"type": "string"},
            "x": {"type": "number"},
            "y": {"type": "number"},
            "z": {"type": "number"},
            "length": {"type": "number"},
            "width": {"type": "number"},
            "thickness": {"type": "number"}
          },
          "required": ["type", "name", "storey", "x", "y", "z", "length", "width", "thickness"],
          "additionalProperties": false
        }
      ]
    }
  }
}
```

**Impact**: Each action type only shows its relevant 5-12 fields instead of 67. Reduces schema tokens by ~60%. Eliminates the model's need to reason about irrelevant fields.

**Caveat**: OpenAI structured outputs support `anyOf` but not `oneOf` natively. For OpenAI, use `anyOf`. For Anthropic, `oneOf` works. The `strict: true` constraint requires all fields to be `required`, so optional fields need `{"anyOf": [{"type": "number"}, {"type": "null"}]}`.

### Change 3: Coordinate convention rule

**Before**:
```
- COORDINATE CONVENTION: For slabs and panels, x/y is the BOTTOM-LEFT CORNER ORIGIN (not center). A slab at x=0, y=0 with length=40, width=25 spans from (0,0) to (40,25). For columns, x/y IS the center point. Match column grid origins with slab origins.
```

**After**:
```
- Slab and panel x/y is the bottom-left corner origin. Column x/y is the center point.
- Element base_z should match the elevation of its assigned storey.
```

---

## Minimal System Prompt (Under 500 Words)

```
You are Bonsai AI, a BIM planning model for Blender + Bonsai.

Return JSON matching the provided schema. Use metric units (meters).

## Element Placement

- Slab and panel x/y is the bottom-left corner. Column x/y is the center.
- Element base_z should match its assigned storey elevation.
- When generators share a footprint, use the same origin coordinates.
- Prefer a small number of clear actions over many micro-actions.

## Generators (prefer these for regular patterns)

- `generate_column_grid`: regular column grids. Expands to (bays_x+1)*(bays_y+1) columns.
- `generate_perimeter_walls`: walls around a polygon. Expands to one wall per edge.
- `generate_floor_plate`: slab with optional perimeter beams. Set include_edge_beams=true for framed floors.
- `generate_facade_grid`: curtain wall facade with panel dimensions.
- Fall back to individual create_* actions for irregular or custom geometry.

## Primitives

- Interior partitions: create_wall.
- Steel framing: create_beam. Connection plates: create_connection_plate.
- Facade panels: create_panel or create_curtain_wall.
- Doors and windows require an IfcWall host (cannot be placed in curtain walls).
- Footings: create_footing. Include foundation metadata when the prompt has structural intent.
- Stairs: create_stair_run and create_stair_landing (approximate; note in assumptions).
- Unsupported element types: approximate with supported primitives and note in assumptions.

## Metadata (optional, use when helpful)

- `semantics`: grouping, naming, selector tags, view modes. Use group_path for review trees.
- `presentation`: glazing, material, frame intent.
- `foundation`: loads, bearing, concrete, reinforcement.

## Editing (when modifying an existing model)

- Target elements via target_id from selection context. Use target_path or target_selector_tags for branches.
- update_element with patch for metadata changes.
- move_element with dx/dy/dz for spatial adjustments.
- replace_section for steel or shell sizing changes.
- rebuild_branch with replacement_actions for regenerating a local branch.
- Prefer semantic edits over recreating the whole building.

## Naming

- Give every action a stable, descriptive name.
- Use absolute coordinates in world space.
```

**Word count: ~280 words, ~520 tokens** (53% reduction from current 598 words / 1,100 tokens)

**What was removed and why:**
1. "Use only these action types" -- redundant with schema enum (55 tokens saved)
2. Field-by-field parameter listings for stairs, connection plates -- schema enforces this (80 tokens saved)
3. ALL-CAPS rules (COORDINATE CONVENTION, WALL vs CURTAIN WALL) -- replaced with calm positive phrasing (40 tokens saved)
4. "Return only JSON" -> "Return JSON matching the provided schema" -- same meaning, fewer words
5. Verbose metadata descriptions (6 lines -> 3 lines)
6. Verbose editing instructions (6 lines -> 5 concise lines)

**What was added:**
1. "Element base_z should match its assigned storey elevation" (Issue 8)
2. "When generators share a footprint, use the same origin coordinates" (Issue 9)

---

## Recommendations Priority Order

| # | Issue | Effort | Impact |
|---|---|---|---|
| 1 | Discriminate action schema (Issue 2) | High | Highest -- eliminates 67-field god object |
| 2 | Standardize field names (Issue 1) | Medium | High -- eliminates model confusion |
| 3 | Adopt minimal prompt (Issues 4-7, 10-11) | Low | High -- 50% prompt reduction |
| 4 | Port tool_spec descriptions to plan schema (Issue 3) | Medium | High -- model sees the good descriptions |
| 5 | Set `strict: true` on OpenAI (Issue 14) | Low | Medium -- eliminates retry loop |
| 6 | Add storey/grid alignment rules (Issues 8-9) | Low | Medium -- reduces geometry errors |
| 7 | Conditional editing section (Issue 11) | Medium | Medium -- saves tokens on new-building prompts |
| 8 | Remove/fix ensure_project (Issue 12) | Low | Low -- dead code cleanup |

---

## Comparison Against Best Practices

### OpenAI GPT-5.4 Best Practices

| Practice | Current Status | Verdict |
|---|---|---|
| CTCO structure (Context, Task, Constraints, Output) | Mixed -- rules and implementation details interleaved | Needs restructuring |
| Remove personality padding | Good -- no "world-class expert" language | Pass |
| No contradictory instructions | Fail -- field names differ across surfaces | Fix Issue 1 |
| Schema in tools/response_format, not prompt | Partially -- schema is in response_format, but good descriptions are in unused tool_specs | Fix Issue 3 |
| Reasoning effort parameter | Supported but optional | Pass |
| strict: true on structured outputs | Set to `false` | Fix Issue 14 |
| Max 100 object properties | 67 action + 13 semantics + 10 presentation + 18 foundation = 108 total | Exceeds limit (Issue 2) |

### Anthropic Claude Opus 4.6 Best Practices

| Practice | Current Status | Verdict |
|---|---|---|
| Clear, direct instructions | Mostly -- some over-explanation | Fix Issues 4, 10 |
| XML tags for structure | Not used | Consider for Claude-specific path |
| 3-5 examples | Zero examples | Add 1-2 input_examples |
| Dial back aggressive tool-use language | Fails -- MUST, NOT, CRITICAL patterns | Fix Issues 6, 7 |
| Prompt caching | Implemented correctly | Pass |
| Long context: data at top, query at bottom | N/A -- system prompt is instructions only | Pass |

### Shared Best Practices

| Practice | Current Status | Verdict |
|---|---|---|
| Tool schemas in tools parameter | Not used for planning (only for execution) | Fix Issue 3 |
| Fewer than 30 tools | 15 tool specs (good), but 22 action types in schema | Borderline |
| Flat schemas | 67-property god object | Fix Issue 2 |
| Examples for semantic guidance | None | Add 1-2 examples |

---

## Compilation Pipeline Analysis

### Does compile_core_plan() lose information?

**Yes, in specific cases:**

1. **Stair runs are decomposed into individual slab treads** (`_compile_stair_run`). The original stair semantics (riser height, tread depth, step count) are lost -- the compiled output is just N rectangular slabs. Downstream tools cannot distinguish a stair from a stack of slabs without checking `semantics.subrole == "stair_tread"`.

2. **Connection plates become horizontal panels** (`_compile_connection_plate`). The center-point origin is transformed to a corner origin, but the semantic meaning of "connection plate" is reduced to "horizontal panel."

3. **Facade grids become curtain walls** (`_compile_facade_grid`). The start/end point parameterization is converted to a single curtain wall with computed width and rotation. The `rotation_degrees` field from the original action is preserved but the geometric derivation (atan2 of the line direction) could mask the original design intent.

### Are there silent failures?

1. **`_to_tool_call` KeyError on unmapped action types**: If compilation produces an action type not in `_TOOL_NAME_MAP`, line 104 raises `PlannerError`. This is not silent -- it is a hard failure. But the error message says "unsupported action for legacy tool execution," which is confusing.

2. **Slab width/depth swap**: The `_compile_floor_plate` sets `width=length` and `depth=width` (line 293-294 in compiler.py). Then `_to_tool_call` maps `length=action.get("length", action["width"])` and `width=action.get("depth", action["width"])`. If the model outputs a `create_rect_slab` with both `width` and `length` fields (possible since both exist in the schema), the fallback logic in `_to_tool_call` may pick up the wrong value. This is a latent bug.

3. **Curtain wall conditional branch**: `_to_tool_call` line 154 checks `if all(key in action for key in ("x1", "y1", "x2", "y2"))`. If the compiled action is missing any of these (e.g., the model outputs `x`, `y` instead of `x1`, `y1`), it falls through to the generic `else` branch (line 173-178) which does a raw dict copy with no validation. This could silently produce incorrect tool arguments.

### Coordinate transform correctness

The `_compile_floor_plate` beam generation (lines 304-353) correctly transforms local corners to world coordinates using rotation. The `_compile_connection_plate` center-to-corner transform (lines 62-65) is also correct. The `_compile_facade_grid` uses `atan2` for line direction, which is standard.

**No coordinate transform bugs found**, but the naming inconsistency (Issue 1) creates risk for future changes.
