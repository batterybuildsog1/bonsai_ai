# Tool Interface Simplification Research

> Date: 2026-03-30
> Author: Claude Opus 4.6 (automated research)
> Status: Planning only -- no code changes
> Inputs: Test harness results, harness-audit.md, simple-tool-interface.md, codebase analysis, commercial tool research

---

## Test Results Baseline

| Scenario | GPT-5.4 | Claude Opus 4.6 |
|---|---|---|
| Simple warehouse | 28 actions, 0 errors, 75s | 29 actions, 19 errors, 131s |
| Medium office | 113 actions, 0 errors, 84s | 113 actions, 0 errors, 137s |
| Hard 5-story | Failed (timeout) | Failed (JSON parsing) |
| Patched 5-story (manual) | 174 cols, 285 beams, 9 slabs, 20 walls, 2 doors, 32 windows | -- |

The hard 5-story building requires ~522 elements. At the current schema size, the model must reason about 67 properties per action for hundreds of actions. Both models fail at this scale.

---

## Question 1: Can We Reduce the Schema from 67 Properties to What Actually Matters?

### Current State: The God Object

Every action in `COMMON_ACTION_PROPERTIES` (action_catalog.py) shares all 67 properties:

```
type, name, target_id, target_name, target_path, target_selector_tags,
storey, storey_name, wall_name, notes, section_id, patch,
x, y, z, dx, dy, dz, x1, y1, x2, y2,
width, depth, length, height, thickness,
center_x, center_y, tread_depth, riser_height, step_count,
direction_deg, elevation, orientation, rotation_deg, rotation_degrees,
panel_width, panel_height, panel_gap, panel_thickness,
base_z, top_z, end_z, offset_along_wall, sill_height,
replacement_actions,
grid_origin_x, grid_origin_y, bays_x, bays_y, spacing_x, spacing_y,
column_width, column_depth, column_height,
corners, include_edge_beams, beam_width, beam_depth,
start_x, start_y, end_x, end_y,
semantics (13 sub-properties), presentation (10 sub-properties), foundation (18 sub-properties)
```

### Discriminated Union: Properties Per Action Type

Here is what each action type actually needs:

| Action Type | Required Fields | Optional Fields | Total |
|---|---|---|---|
| ensure_storey | type, name, elevation | semantics | 4 |
| create_rect_slab | type, name, storey, x, y, z, width, depth, thickness | rotation_deg, semantics, presentation | 12 |
| create_wall | type, name, storey, x1, y1, x2, y2, base_z, height, thickness | semantics, presentation | 12 |
| create_column | type, name, storey, x, y, base_z, width, depth, height | rotation_deg, semantics, presentation | 12 |
| create_beam | type, name, storey, x1, y1, x2, y2, base_z, width, depth | end_z, semantics, presentation | 13 |
| create_panel | type, name, storey, x, y, base_z, width, thickness, orientation | height, depth, rotation_deg, semantics, presentation | 14 |
| create_window | type, name, storey, wall_name, offset_along_wall, sill_height, width, height, thickness | semantics, presentation | 12 |
| create_door | type, name, storey, wall_name, offset_along_wall, width, height, thickness | semantics, presentation | 11 |
| create_curtain_wall | type, name, storey, x1, y1, x2, y2, base_z, top_z, panel_width, panel_height, thickness | rotation_degrees, semantics, presentation | 15 |
| create_footing | type, name, storey, x, y, base_z, length, width, thickness | rotation_deg, semantics, foundation | 12 |
| create_stair_run | type, name, storey, x, y, base_z, width, tread_depth, riser_height, step_count, thickness | direction_deg, semantics | 13 |
| create_stair_landing | type, name, storey, x, y, base_z, width, depth, thickness | direction_deg, semantics | 12 |
| create_connection_plate | type, name, storey, center_x, center_y, base_z, width, depth, thickness | rotation_deg, semantics | 11 |
| generate_column_grid | type, name, storey, grid_origin_x, grid_origin_y, base_z, bays_x, bays_y, spacing_x, spacing_y, column_width, column_depth, column_height | rotation_deg, semantics | 15 |
| generate_perimeter_walls | type, name, storey, corners, base_z, height, thickness | semantics | 8 |
| generate_floor_plate | type, name, storey, x, y, z, length, width, thickness | include_edge_beams, beam_width, beam_depth, rotation_deg, semantics | 14 |
| generate_facade_grid | type, name, storey, start_x, start_y, end_x, end_y, base_z, height, panel_width, panel_height, panel_thickness | rotation_degrees, semantics, presentation | 15 |
| update_element | type, name, target_id/target_name/target_path/target_selector_tags, patch | semantics | 6-8 |
| delete_element | type, name, target_id/target_name/target_path/target_selector_tags | -- | 4-6 |
| move_element | type, name, target_id/target_name/target_path/target_selector_tags | dx, dy, dz | 5-7 |
| replace_section | type, name, target_id/target_name/target_path/target_selector_tags | section_id, width, depth, thickness, patch | 6-10 |
| rebuild_branch | type, name, target_id/target_name/target_path/target_selector_tags, replacement_actions | storey | 6-8 |

**Average fields per action: ~11. Current: 67. Reduction: 84%.**

### Token Count Difference

**Current god-object schema** (measured from action_catalog.py):
- 67 top-level properties with descriptions: ~2,800 tokens
- semantics object (13 properties): ~500 tokens
- presentation object (10 properties): ~400 tokens
- foundation object (18 properties): ~700 tokens
- Plan wrapper (version, units, summary, assumptions): ~200 tokens
- **Total schema: ~4,600 tokens**

**Discriminated union schema** (oneOf with 22 variants):
- Each variant: ~80-150 tokens (type const + 5-12 typed properties with descriptions)
- 22 variants: ~2,200 tokens
- Shared metadata objects (included only on variants that use them): ~400 tokens
- Plan wrapper: ~200 tokens
- **Total schema: ~2,800 tokens**

**Savings: ~1,800 tokens (39% reduction in schema size).**

But the real win is not token count -- it is **CFG evaluation complexity**. OpenAI's structured output engine evaluates all possible properties at each generated token. With 67 properties, the engine must evaluate 67 choices at every object-property boundary. With discriminated unions, once the `type` field is emitted, only 5-12 properties are valid. This directly reduces generation latency.

### Estimated Latency Impact

OpenAI's CFG engine constrains token generation at each step. The constraint evaluation cost scales with the number of valid alternatives. Reducing from 67 to ~11 average valid properties per action should reduce per-token latency by roughly 40-60% for the action generation portion of the output.

For a 5-story building generating ~50 actions at ~15 tokens per action:
- Current: ~750 action tokens, each evaluated against 67 properties
- Discriminated: ~750 action tokens, each evaluated against ~11 properties
- Estimated time savings: 15-30 seconds on a 75-second generation (20-40%)

### OpenAI Compatibility Caveat

OpenAI structured outputs support `anyOf` but not `oneOf`. The discriminated union must use `anyOf` with a `type` field that has a `const` value for each variant. OpenAI also requires `strict: true` schemas to have ALL properties in `required`, meaning optional fields must use `{"anyOf": [{"type": "number"}, {"type": "null"}]}` rather than simply being absent from `required`.

---

## Question 2: Can We Reduce the Number of Action Types?

### Current: 22 Action Types

10 buildable primitives + 7 semantic/generator actions + 5 edit actions.

### Proposed Consolidations

#### Merge 1: `create_wall` + `create_panel` --> `create_wall` (for opaque surfaces)

Both create rectangular extrusions. The difference:
- `create_wall` uses start/end points (x1,y1 -> x2,y2) and is an IfcWall
- `create_panel` uses origin (x,y) + width/height and is an IfcPlate

**Verdict: Keep separate.** They map to different IFC classes (IfcWall vs IfcPlate), which matters for downstream engineering and openings. A wall can host windows and doors; a panel cannot. Merging would lose this distinction.

#### Merge 2: `create_column` --> absorbed into `generate_column_grid`

Individual columns are rarely needed. In the test results:
- Simple warehouse: all columns came from `generate_column_grid`
- Medium office: all columns came from `generate_column_grid`
- 5-story: all 174 columns came from `generate_column_grid`

**Verdict: Keep `create_column` but demote it.** The system prompt already says "prefer generators." For 95% of cases, `generate_column_grid` is sufficient. Individual `create_column` is needed only for mezzanine supports, transfer columns, or irregular layouts. Moving it to an "advanced" tier would reduce the action types the model considers in the common case.

#### Merge 3: `create_door` + `create_window` --> `create_opening`

Both are hosted in walls, both have offset_along_wall + width + height + thickness. The only difference is `sill_height` (windows sit above the floor; doors sit at floor level).

**Verdict: Viable merge.** A unified `create_opening` with an `opening_type: "door" | "window"` discriminator and optional `sill_height` (defaults to 0 for doors) reduces two types to one. Token savings: ~100 tokens from eliminating one schema variant. Conceptual simplification: the model thinks about "openings in walls" instead of two separate concepts.

#### Merge 4: `create_stair_run` + `create_stair_landing` --> `create_stair`

These always appear together. A stair is a run + landing + run + landing pattern.

**Verdict: Viable merge, but complex.** A single `create_stair` with parameters for total rise, run direction, landing positions would compress the interface. However, the current implementation decomposes stair_run into individual slab treads, which is a lossy transformation. A proper stair generator that takes start_elevation, end_elevation, width, and direction and computes the geometry deterministically would be better. This is more of a new generator than a simple merge.

#### Merge 5: `create_connection_plate` --> absorbed into `create_panel`

Connection plates compile to horizontal panels anyway (compiler.py line 59-82). The center-to-corner transform is a convenience that could be a flag.

**Verdict: Viable merge.** Add `origin_mode: "center" | "corner"` to `create_panel`. Removes one action type with zero capability loss.

### Recommended Reduced Set: 17 Action Types (down from 22)

| Tier | Action Types | Count |
|---|---|---|
| **Core generators** | generate_column_grid, generate_perimeter_walls, generate_floor_plate, generate_facade_grid | 4 |
| **Core primitives** | ensure_storey, create_rect_slab, create_wall, create_beam, create_column | 5 |
| **Envelope** | create_opening (merged door+window), create_curtain_wall, create_panel (absorbs connection_plate) | 3 |
| **Specialty** | create_footing, create_stair (merged run+landing) | 2 |
| **Edit** | update_element, delete_element, move_element | 3 |

Removed entirely:
- `replace_section` (fold into `update_element` with a patch on width/depth/section_id)
- `rebuild_branch` (complex and rarely generated correctly by models; fold into delete + recreate)
- `create_door` (merged into create_opening)
- `create_window` (merged into create_opening)
- `create_connection_plate` (merged into create_panel with origin_mode)

**Net: 22 --> 17 action types. ~23% reduction.**

The bigger win is not the count reduction but the **tiering**. If the model is told "use generators first, then primitives, then specialty types," it will reach for the 4 generators before considering the 13 other types. For a typical building, 4 generators + ensure_storey covers 80% of the elements.

---

## Question 3: Can We Use Parametric Generators More Aggressively?

### What Generators Currently Compress

| Generator | Input Actions | Output Elements | Compression Ratio |
|---|---|---|---|
| generate_column_grid (5x3, 5 floors) | 5 | 120 columns | 24:1 |
| generate_perimeter_walls (rectangular, 5 floors) | 5 | 20 walls | 4:1 |
| generate_floor_plate (5 floors + roof) | 6 | 6 slabs + 24 beams | 5:1 |
| generate_facade_grid (4 facades) | 4 | 4 curtain walls | 1:1 (but with panel subdivision) |

For the patched 5-story building (174 cols, 285 beams, 9 slabs, 20 walls, 2 doors, 32 windows):
- **With individual primitives**: ~522 actions
- **With current generators**: ~50-70 actions (storeys + grids + floor plates + walls + openings)
- **Theoretical minimum with aggressive generators**: ~25-35 actions

### Missing Generators That Would Help

#### 1. `generate_beam_grid` (NEW)

The 5-story building has 285 beams. Currently, `generate_floor_plate` only creates 4 perimeter beams per floor. All interior beams (at every column-to-column gridline) must be individual `create_beam` actions.

A `generate_beam_grid` that takes the same grid parameters as `generate_column_grid` and places beams along every gridline would compress ~57 beams/floor into 1 action.

**Input**: grid_origin, bays_x, bays_y, spacing_x, spacing_y, base_z, beam_width, beam_depth
**Output**: (bays_x * (bays_y + 1)) + (bays_y * (bays_x + 1)) beams per floor
**For 5x3 grid**: (5*4) + (3*6) = 38 beams per invocation
**Compression**: 38:1 per floor, 190:1 for 5 floors

This single addition would reduce the 5-story building from ~70 actions to ~35 actions.

#### 2. `generate_opening_array` (NEW)

32 windows on a 5-story building follow a regular pattern: N windows per wall segment, evenly spaced or at fixed intervals. Currently each is an individual `create_window` action.

A `generate_opening_array` that takes a wall name, count, spacing, and opening dimensions would compress entire facade window patterns into single actions.

**Input**: wall_name, count, start_offset, spacing, width, height, sill_height, opening_type
**Output**: N windows or doors
**Compression**: 8:1 per wall (typical), 32:1 for all facade windows

#### 3. `generate_full_floor` (NEW -- mega-generator)

Combines column_grid + floor_plate + beam_grid for one storey in a single action. This is what the model conceptually wants to do: "add a structural floor at this elevation."

**Input**: storey_name, origin, bays_x, bays_y, spacing_x, spacing_y, column_size, column_height, slab_thickness, beam_size
**Output**: All columns + slab + all beams for one floor
**Compression**: ~50:1 for a typical floor

### Generator-Primary Interface: Action Count Estimates

| Building Element | Current Actions | With New Generators | Savings |
|---|---|---|---|
| 5 storeys | 5 ensure_storey | 5 ensure_storey | 0 |
| 174 columns | 5 generate_column_grid | 5 generate_column_grid | 0 (already compressed) |
| 285 beams | ~285 create_beam OR ~5 generate_floor_plate + ~280 create_beam | 5 generate_beam_grid | ~280 actions saved |
| 9 slabs | 5-6 generate_floor_plate + 3-4 create_rect_slab | 5-6 generate_floor_plate + 3-4 create_rect_slab | 0 |
| 20 walls | 5 generate_perimeter_walls | 5 generate_perimeter_walls | 0 |
| 2 doors | 2 create_door | 2 create_opening | 0 |
| 32 windows | 32 create_window | 4-8 generate_opening_array | ~24 actions saved |
| **Total** | **~340 actions** | **~35-40 actions** | **~300 actions (88% reduction)** |

With generate_full_floor as the mega-generator:

| Building Element | Actions |
|---|---|
| 5 ensure_storey | 5 |
| 5 generate_full_floor (cols + slab + beams per floor) | 5 |
| 1 generate_full_floor (roof slab only, no columns) | 1 |
| 5 generate_perimeter_walls | 5 |
| 4-8 generate_opening_array | 6 |
| 3-4 create_rect_slab (mezzanine) | 4 |
| **Total** | **~26 actions** |

**26 actions vs. ~340. Both models can generate 26 actions without timeout.**

### Risk Assessment

More aggressive generators trade flexibility for compression. Risks:
- **Irregular grids**: generate_full_floor assumes rectangular regular grids. L-shaped buildings, setbacks, or mixed bay sizes need individual primitives.
- **Mixed floor types**: Some floors have different beam depths, column sizes, or slab thicknesses. The generator assumes uniform parameters.
- **Partial floors**: Mezzanines, double-height spaces, and atriums break the "one generator per floor" pattern.

Mitigation: Keep individual primitives as fallbacks. The prompt says "use generators for regular patterns, fall back to primitives for exceptions." The mezzanine in the 5-story building (3-4 extra slabs) would still be individual create_rect_slab actions.

---

## Question 4: Can We Split the Problem Differently?

### Current Approach: AI Generates All Placement Math

The model currently computes every coordinate, every dimension, every bay count. For a 5-story building, this means:
- Calculate 5 storey elevations
- Calculate column grid positions (bays * spacing = footprint check)
- Calculate slab dimensions to match footprint
- Calculate beam endpoints at every gridline intersection
- Calculate wall positions matching building perimeter
- Calculate window offsets along each wall
- All while maintaining JSON syntax correctness across hundreds of actions

This is asking a language model to do what a spreadsheet does better.

### Proposed Approach: Spec-First, Then Deterministic Expansion

Split into two phases:

**Phase 1: AI generates a SPEC** (design decisions only, ~10-15 fields)

```json
{
  "building_type": "commercial_office",
  "stories": 5,
  "footprint": {"length": 40, "width": 25},
  "grid": {"bay_x": 8, "bay_y": 8.33},
  "heights": {"ground": 4.5, "typical": 4.0},
  "structure": {
    "column_size": [0.4, 0.4],
    "beam_size": [0.3, 0.5],
    "slab_thickness": 0.2
  },
  "envelope": {
    "north": {"type": "wall", "thickness": 0.25},
    "south": {"type": "curtain_wall", "panel": [1.5, 1.2, 0.02]},
    "east": {"type": "wall", "thickness": 0.25, "windows": {"count_per_bay": 1, "width": 1.8, "height": 1.5, "sill": 0.9}},
    "west": {"type": "wall", "thickness": 0.25, "windows": {"count_per_bay": 1, "width": 1.8, "height": 1.5, "sill": 0.9}}
  },
  "entries": [
    {"wall": "south", "type": "door", "width": 2.0, "height": 2.4, "offset": 19}
  ],
  "mezzanine": {
    "storey": 2,
    "footprint": {"x": 0, "y": 0, "length": 20, "width": 12.5},
    "height": 2.0
  }
}
```

**Phase 2: Deterministic code generates the building** (no AI needed)

A Python function reads the spec and computes ALL coordinates, ALL element placements, ALL beam gridlines. The logic is straightforward:

```python
def expand_spec(spec):
    actions = []

    # Storeys
    elevation = 0
    for i in range(spec["stories"]):
        h = spec["heights"]["ground"] if i == 0 else spec["heights"]["typical"]
        actions.append(ensure_storey(f"Level {i+1}", elevation))
        elevation += h
    actions.append(ensure_storey("Roof", elevation))

    # Structure per floor
    for i in range(spec["stories"]):
        actions.append(generate_column_grid(...))
        actions.append(generate_floor_plate(...))
        actions.append(generate_beam_grid(...))  # ALL gridline beams

    # Roof slab
    actions.append(generate_floor_plate("Roof Slab", ...))

    # Envelope per floor
    for i in range(spec["stories"]):
        for face in ["north", "south", "east", "west"]:
            envelope = spec["envelope"][face]
            if envelope["type"] == "wall":
                actions.append(generate_perimeter_wall_segment(...))
                if "windows" in envelope:
                    actions.append(generate_opening_array(...))
            elif envelope["type"] == "curtain_wall":
                actions.append(generate_facade_grid(...))

    # Entries
    for entry in spec["entries"]:
        actions.append(create_opening(...))

    return actions
```

### What the AI Does vs. What Code Does

| Concern | Current (AI does everything) | Spec-first (AI decides, code places) |
|---|---|---|
| "How many stories?" | AI decides | AI decides |
| "What bay spacing?" | AI decides | AI decides |
| "What facade type per face?" | AI decides | AI decides |
| "What window rhythm?" | AI decides | AI decides |
| "Where is column A3?" | AI computes: x=16, y=16.66 | Code computes from grid spec |
| "Where is beam B2-C2?" | AI computes: x1=8, y1=8.33, x2=16, y2=8.33 | Code computes from grid spec |
| "Where is window 14?" | AI computes: wall="East-Seg-02", offset=12.5 | Code computes from window pattern |
| "What is the roof slab z?" | AI computes: 4.5 + 4*4.0 = 20.5 | Code computes from heights |

**The AI makes ~15 design decisions. The code does ~500 coordinate calculations.** This is the correct division of labor. Language models are good at design intent. Code is good at arithmetic.

### Token Economics of Spec-First

| Component | Current | Spec-First |
|---|---|---|
| Schema tokens (sent to model) | ~4,600 (67-property god object) | ~800 (spec schema with ~30 properties) |
| System prompt tokens | ~520 (minimal prompt) | ~300 (simpler instructions about design choices) |
| Model output tokens | ~2,000-8,000 (full action list) | ~200-500 (spec JSON) |
| **Total model I/O** | **~7,000-13,000 tokens** | **~1,300-1,600 tokens** |

**5-10x reduction in model output tokens. Generation time drops from 60-120s to 5-15s.**

### Risk: Loss of Flexibility

The spec-first approach assumes regular rectangular buildings. It cannot express:
- L-shaped footprints (though this could be a polygon footprint spec)
- Mixed structural systems (steel frame on lower floors, wood frame on upper)
- Irregular window patterns (specific windows at specific locations)
- Atriums and double-height spaces (partially addressable via floor exclusion zones)
- Complex mezzanine arrangements

However, the test results show that both GPT-5.4 and Claude already fail at complex buildings. A spec-first approach that reliably produces correct regular buildings is better than an action-list approach that fails on complex buildings.

### Hybrid: Spec + Override Actions

The spec handles the 90% regular case. Individual actions handle the 10% exceptions:

```json
{
  "spec": { ... regular building parameters ... },
  "overrides": [
    {"action": "delete_element", "target": "Level 3 Col-B2"},
    {"action": "create_rect_slab", "name": "Atrium Opening", ...},
    {"action": "create_opening", "name": "Custom Entrance", ...}
  ]
}
```

The expansion code generates the regular building from the spec, then applies override actions to handle special cases. The AI outputs a spec (fast, reliable) plus a handful of surgical overrides (small, focused).

---

## Question 5: How Do Commercial Tools Handle This?

### Hypar.io

**Interface**: Parametric functions that receive a spec and return a model. Each function (written in C# or Python) is a "generator" that takes typed inputs (footprint polygon, floor count, bay spacing) and produces BIM elements. Functions are composed in a visual workflow.

**Key insight**: Hypar does NOT ask the AI to compute coordinates. Hypar functions are deterministic: given inputs, they always produce the same output. The AI (or user) sets the inputs. The function does the math.

**Input level**: Building-level parameters (site polygon, program requirements, height limits). Not element-level placement.

**Relevance to us**: Hypar's generators ARE our `generate_column_grid`, `generate_floor_plate`, etc. -- but Hypar makes generators the ONLY interface. There is no "place this individual column at (12.5, 8.33)." If you want a column grid, you define the grid parameters and the generator places all columns.

### TestFit.io

**Interface**: Building typology + parameters. The user selects a typology (apartment building, office, industrial) and sets parameters: unit mix, parking ratios, building height, setbacks. TestFit's solver generates building layouts that satisfy all constraints.

**Key insight**: The solver is constraint-based, not action-based. The user says "I need 80% 1BR and 20% 2BR units with 1.5 parking stalls per unit" and the solver figures out the floor plan, unit placement, and garage layout.

**Input level**: Program-level (unit counts, area requirements, zoning constraints). Even higher abstraction than Hypar.

**Relevance to us**: TestFit's input is closer to our proposed "spec" than to our current action list. The user describes WHAT they want; the system figures out HOW to build it.

### Finch3D

**Interface**: Graph rules + constraints + AI generation. Users define space relationships (bedroom adjacent to bathroom, living room has exterior wall access), minimum areas, and daylight requirements. The AI generates floor plans that satisfy all rules.

**Key insight**: Finch separates design rules (reusable constraints) from generation (AI-driven layout). Rules are the "spec." Generation is deterministic given the rules and the unit boundary polygon.

**Input level**: Space-program level (room types, adjacencies, area requirements). The lowest abstraction of the three -- Finch deals with individual rooms -- but still far above element-level placement.

**Relevance to us**: Finch proves that AI-driven spatial layout works when the AI operates at the room/space level, not the element level. The AI decides "living room goes here"; the system creates the walls, floor, and openings.

### Common Pattern Across All Three

| Tool | What the AI/user specifies | What the system computes |
|---|---|---|
| Hypar | Building parameters, program | Element geometry, placement, IFC |
| TestFit | Unit mix, parking, zoning | Floor plans, unit placement, structure |
| Finch3D | Room program, adjacencies | Floor plan layout, wall positions |
| **Our current system** | **Every element, every coordinate** | **Nothing (the AI does everything)** |

**The common pattern: the AI makes high-level design decisions; deterministic code handles geometric placement.** Our system is the outlier by asking the AI to do both.

---

## Question 6: What Is the Minimum Viable Prompt for a Good Building?

### Proposed Minimum Spec

```
Building: 5-story commercial office
Footprint: 40m x 25m
Grid: 8m x 8m (adjusts to fit)
Heights: 4.5m ground, 4.0m upper
Structure: 400x400mm columns, 300x500mm beams, 200mm slabs
Facades: concrete walls E/W/N, glass curtain wall S ground, walls upper
Windows: 1.8m x 1.5m, 0.9m sill, 1 per bay on E/W
Entries: 1 double door south-center ground floor
```

### What the System Must Figure Out Deterministically

From just this spec, the system can compute:

1. **Storeys**: 5 + roof = 6 ensure_storey actions. Elevations: 0, 4.5, 8.5, 12.5, 16.5, 20.5.

2. **Column grid**: 40/8 = 5 bays X. 25/8 = 3.125 bays Y -- round to 3 bays, last bay = 9m (or adjust: 4 bays at 6.25m). The system resolves this with a rule: "last bay absorbs remainder if within 25% of typical bay."
   - Columns per floor: (5+1) * (4+1) = 30
   - Total: 30 * 5 = 150 columns

3. **Beams**: At every column gridline, both directions, every floor.
   - X-direction beams per floor: 5 bays * (4+1) rows = 25
   - Y-direction beams per floor: 4 bays * (5+1) cols = 24
   - Per floor: 49 beams. Total: 49 * 5 = 245 beams + roof = 294 beams

4. **Slabs**: 1 per floor + 1 roof = 6 slabs at 40m x 25m x 0.2m.

5. **Walls**: Perimeter walls on floors where spec says "wall":
   - North/East/West walls on all 5 floors
   - South wall on floors 2-5 (ground floor is curtain wall)
   - 4 walls per floor * 5 floors - 1 south ground = 19 walls

6. **Curtain wall**: South facade, ground floor, 40m wide x 4.5m tall.

7. **Windows**: East and west walls, 1 per bay.
   - East wall: 5 bays * 5 floors = 25 windows (minus ground floor if it is special)
   - West wall: same = 25 windows
   - Total: ~50 windows

8. **Door**: 1 double door at south-center = 1 door.

**Total elements: ~150 cols + 294 beams + 6 slabs + 19 walls + 1 curtain wall + 50 windows + 1 door = ~521 elements.**

**Total AI output: ~100-200 tokens for the spec. Total deterministic computation: ~0.5 seconds.**

Compare to current: the AI must output ~3,000-8,000 tokens of JSON action lists AND get every coordinate right. One wrong number in 8,000 tokens = broken building.

### What the AI Actually Needs to Decide

The spec above contains exactly **16 design decisions**:

1. Building type (commercial office)
2. Story count (5)
3. Footprint length (40m)
4. Footprint width (25m)
5. Grid bay X (8m)
6. Grid bay Y (8m)
7. Ground floor height (4.5m)
8. Typical floor height (4.0m)
9. Column size (400x400mm)
10. Beam size (300x500mm)
11. Slab thickness (200mm)
12. North facade type (concrete wall)
13. South facade type (glass curtain wall ground, walls upper)
14. East/West facade type (concrete wall with windows)
15. Window dimensions and pattern (1.8x1.5, sill 0.9, 1/bay)
16. Entry location and size (south center, double door)

These 16 decisions are what a model like GPT-5.4 or Claude is actually good at: interpreting a user's intent ("5-story commercial office") and making reasonable design choices. The model is NOT good at computing 294 beam endpoints -- that is what code is for.

---

## Synthesis: Recommended Simplification Strategy

### Three layers, from quickest win to biggest transformation:

### Layer 1: Fix the Schema (1-2 days, no architecture change)

1. **Discriminated union schema**: Replace `COMMON_ACTION_PROPERTIES` god object with oneOf/anyOf variants. Each action type shows only its own fields.
   - Effort: Rewrite `action_catalog.py` and `schema.py`
   - Impact: ~39% schema token reduction, ~40-60% faster structured output generation
   - Risk: Low. The validation logic in `schema.py` already validates per-type.

2. **Adopt minimal system prompt**: The one from harness-audit.md (280 words, ~520 tokens instead of 598 words, ~1,100 tokens).
   - Effort: Replace SYSTEM_PROMPT in `planner.py`
   - Impact: ~50% prompt token reduction
   - Risk: Low. Removes only redundant/contradictory instructions.

3. **Standardize field names**: `length`/`width` everywhere, not `width`/`depth` in some places.
   - Effort: Update action_catalog.py, tool_specs.py, compiler.py
   - Impact: Eliminates model confusion and the `_coerce_numeric_fields` hacks
   - Risk: Medium. Requires updating all test fixtures.

### Layer 2: Add Missing Generators (3-5 days, minor architecture change)

4. **`generate_beam_grid`**: Creates all beams along column gridlines for one floor.
   - Compression: ~40 beams per floor into 1 action
   - Impact on 5-story: reduces from ~340 to ~50 actions

5. **`generate_opening_array`**: Creates evenly-spaced windows or doors along a wall.
   - Compression: ~8 windows per wall into 1 action
   - Impact on 5-story: reduces from ~50 to ~35 actions

6. **Merge door+window into create_opening**: Single action type with `opening_type` discriminator.
   - Simplification: 22 action types --> 21

### Layer 3: Spec-First Architecture (1-2 weeks, significant architecture change)

7. **Building spec schema**: A ~30-property JSON describing the building at the design-decision level (footprint, grid, heights, facade types, window patterns).

8. **Deterministic expander**: Python code that reads a spec and generates all actions, computing all coordinates. No AI needed for placement math.

9. **Override mechanism**: The AI outputs a spec + optional override actions for irregular elements.

10. **Impact**: Model output drops from ~3,000-8,000 tokens to ~200-500 tokens. Generation time drops from 60-120s to 5-15s. The hard 5-story building that currently times out would complete in under 20 seconds.

### Expected Impact on Test Scenarios

| Scenario | Current Best | After Layer 1 | After Layer 2 | After Layer 3 |
|---|---|---|---|---|
| Simple warehouse | 28 actions, 75s | 28 actions, ~50s | ~15 actions, ~30s | ~100 token spec, ~5s |
| Medium office | 113 actions, 84s | 113 actions, ~55s | ~30 actions, ~25s | ~200 token spec, ~8s |
| Hard 5-story | FAIL (timeout) | ~340 actions, ~90s (might work) | ~35 actions, ~30s | ~300 token spec, ~10s |

### What Each Layer Requires

| Layer | Files Changed | Lines of Code | Architecture Change | Backward Compatible |
|---|---|---|---|---|
| 1: Schema fix | action_catalog.py, schema.py, planner.py | ~200 lines rewritten | None | Yes (same pipeline) |
| 2: New generators | compiler.py, action_catalog.py, schema.py | ~150 lines added | Minor (new action types) | Yes (additive) |
| 3: Spec-first | New files: spec_schema.py, spec_expander.py | ~400 lines new | Significant (new entry point) | Yes (parallel path) |

---

## Key Findings

1. **The 67-property god object is the single biggest performance problem.** Discriminated unions would reduce schema tokens by 39% and speed up structured output generation by 40-60%. This is the highest-impact, lowest-risk change.

2. **Beams are the action count bottleneck.** A 5-story building needs ~285 beams but only ~30 columns (via grid generator). A `generate_beam_grid` would compress beams the same way `generate_column_grid` compresses columns, cutting total action count by 80%.

3. **The AI is doing the wrong job.** Language models make good design decisions but bad calculators. The spec-first approach gives the AI the job it is good at (design intent) and gives code the job it is good at (coordinate math). Every commercial tool (Hypar, TestFit, Finch3D) works this way.

4. **The 5-story building is not actually hard.** It is a regular rectangular building with a regular grid. The ONLY reason it fails is that the action list is too long for the model to generate correctly in one pass. With a 300-token spec and deterministic expansion, it would take 10 seconds.

5. **Consolidating action types (22 --> 17) helps conceptually but is not the biggest win.** The biggest wins come from (a) discriminated schemas and (b) generators that compress hundreds of actions into single invocations.

6. **Layer 3 (spec-first) is the end state, but Layers 1-2 can ship independently and immediately.** The layers are cumulative, not sequential. Each one improves the system regardless of whether the next is built.

---

Sources:
- [Hypar Documentation](https://docs.hypar.io/)
- [Hypar: text-to-BIM and beyond - AEC Magazine](https://aecmag.com/features/hypar-text-to-bim-and-beyond/)
- [GitHub - hypar-io/Elements](https://github.com/hypar-io/Elements)
- [TestFit: Real Estate Feasibility Platform](https://www.testfit.io)
- [TestFit Building Typologies](https://support.testfit.io/knowledge/getting-started/building-typologies)
- [TestFit 5.6 Generative Parameters](https://www.testfit.io/blog/testfit-5-6-more-flexible-data-centers-generative-parameters)
- [Finch3D - Optimizing Architecture](https://www.finch3d.com/)
- [Finch3D: Drawing a Floor Plan with AI Co-Pilot](https://docs.finch3d.com/courses/drawing-and-generating-floor-plans-in-finch/drawing-a-floor-plan-with-ai-co-pilot)
- [Finch3D: Enterprise Generate Unit Plan](https://docs.finch3d.com/docs/projects-and-variants/unit-editor/enterprise-generate-unit-plan)
- [Integrating Generative and Parametric Design with BIM (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2666496825000512)
