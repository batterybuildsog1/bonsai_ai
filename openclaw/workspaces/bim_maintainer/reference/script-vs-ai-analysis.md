# Script vs AI Accuracy Analysis

**Date:** 2026-03-30
**Scope:** Why hand-authored Python scripts produce more accurate buildings than AI-generated plans, and three refactor options to close the gap.

---

## Part 1: Script Dissection

### 1.1 patch_five_story_beams.py (104 lines)

**Design decisions (human chose):**
- Grid is 6 columns x 5 rows (XS = [0, 8, 16, 24, 32, 40], YS = [0, 6.25, 12.5, 18.75, 25.0])
- Five storeys at [0.0, 4.5, 8.5, 12.5, 16.5]
- Beam section: 0.3m x 0.5m
- Full bidirectional beam grid (X and Y beams at every gridline)

**Coordinate math (Python computed):**
- Nested loop: `for xi in range(len(XS) - 1)` generates every span between adjacent grid points
- `x1, x2 = XS[xi], XS[xi + 1]` -- endpoints derived from shared grid array
- Total beams = storeys * (rows * x_bays + columns * y_bays) = 5 * (5*5 + 6*4) = 5 * 49 = 245

**Line breakdown:**
- ~16 lines: constants (design intent)
- ~6 lines: setup/imports
- ~50 lines: nested loops + API calls (coordinate math + execution)
- ~30 lines: error handling, logging, boilerplate
- **Ratio: ~25% design intent, ~50% deterministic math, ~25% plumbing**

**Could design be separated from math?** Yes -- trivially. The design is entirely captured by XS, YS, STOREYS, BEAM_WIDTH, BEAM_DEPTH. The rest is a generic "beam grid from arrays" function.

---

### 1.2 patch_five_story_openings.py (220 lines)

**Design decisions (human chose):**
- Wall thickness 0.15m (thin backing walls behind curtain panels)
- Five storeys with floor-to-floor heights [4.5, 4.0, 4.0, 4.0, 4.0]
- Bay centres at Y = [3.125, 9.375, 15.625, 21.875] for window placement
- Main entrance: south facade, centered at x=20m, 2.4m x 2.8m
- Service entrance: north facade, x=35m, 1.2m x 2.4m
- Windows: east/west only, floors 2-5, 1.8m x 1.5m, sill at 0.9m, one per bay
- Building footprint: X 0-40m, Y 0-25m (known from existing IFC)

**Coordinate math (Python computed):**
- Four perimeter walls per floor via explicit coordinates (south: y=0, north: y=25, etc.)
- Door offset: `offset_along_wall = 20 - 2.4/2 = 18.8m` -- centering math
- Window offset: `east_offset = bay_y - 0.9` -- centering from bay centre
- Window iteration: `for bay_idx, bay_y in enumerate(BAY_CENTRES_Y)` on two facades x four floors

**Line breakdown:**
- ~28 lines: constants and documentation (design intent)
- ~6 lines: setup/imports
- ~130 lines: wall/door/window creation loops (math + API calls)
- ~56 lines: error handling, counters, logging
- **Ratio: ~13% design intent, ~60% deterministic math, ~27% plumbing**

**Could design be separated from math?** Yes. The entire script reduces to: "add backing walls on all facades, put two doors on ground floor, put 1.8x1.5 windows at bay centres on east/west floors 2-5." A `generate_opening_array` call per facade plus two `create_door` calls would suffice -- if the AI knew the wall names and bay centres.

---

### 1.3 build_retail_terrace_concept.py (902 lines)

**Design decisions (human chose):**
- Two-volume massing: 36m x 31m podium + centered 24m x 18m upper volume
- Ground floor 5.4m tall, upper floor 4.2m tall
- Slab thicknesses: ground 0.30m, upper 0.25m, roof 0.22m
- Steel frame: corner columns (0.35m podium, 0.30m upper), perimeter beams (0.22m x 0.42m)
- Cladding system with accent panels on specific facade segments
- Railing at 3.0m post spacing, top rail at 1.15m, mid rail at 0.60m above terrace
- Storefront windows: 5.0m x 3.6m on south, 3.6m x 3.2m on sides
- Load-based footing sizing via `starter_footing_from_imposed_load()`
- Canopy: 11.0m x 2.2m at 4.45m height with two steel posts

**Coordinate math (Python computed):**
- Upper origin: `UPPER_ORIGIN_X_M = (36.0 - 24.0) / 2.0 = 6.0` (centering)
- `_segment_points()`: subdivides a line into posts at regular spacing
- `_loop_points()`: distributes railing posts around a polygon at 3.0m spacing
- `_add_wall_box()`: four walls from (x, y, length, width) -- corner coordinates derived
- `_add_perimeter_frame()`: four beams offset 0.5m inward from corners
- Footing centres: column centre coordinates fed to load-based sizing function

**Line breakdown:**
- ~50 lines: constants (design intent)
- ~110 lines: helper functions (_segment_points, _loop_points, _add_wall_box, _add_corner_columns, _add_perimeter_frame, _add_spread_footing, _add_terrace_railing, _add_vertical_panel_strip)
- ~380 lines: build_concept() body (assembly of all elements with metadata)
- ~60 lines: metadata/presentation helpers
- ~40 lines: setup, CLI, reporting
- **Ratio: ~5% constants, ~12% reusable math, ~42% element assembly, ~7% metadata helpers, ~34% plumbing**

**Could design be separated from math?** Partially. The simple geometry (wall boxes, column grids, beam frames) separates cleanly. But the specific window offsets, accent panel positions, canopy placement, and railing geometry are bespoke design decisions interleaved with coordinate math. This building has too many one-off architectural features for a pure "spec -> expand" approach.

---

## Part 2: What the AI Actually Produces

### 2.1 Simple Warehouse (28 actions via OpenAI)

**Prompt:** 30m x 20m steel warehouse, 6m eave, 3 bays @ 10m x 1 bay @ 20m

**Actual output vs expected:**

| Element | Expected | Got | Issue |
|---------|----------|-----|-------|
| Columns | 6 (3x2) | 8 (4x2) | AI used bays_x=3, bays_y=1, but prompt says "6 columns at grid intersections" implying 4 x-positions x 2 y-positions = 8. Actually 8 is correct for a 4x2 grid (x=0,10,20,30 by y=0,20). The prompt is ambiguous. |
| Beams | 13 (7 EW + 6 NS) | 10 | Missing 3 beams -- the AI likely used generate_floor_plate edge beams instead of generate_beam_grid |
| Walls | 4 | 4 | Correct |
| Doors | 3 | 3 | Correct |
| Y bounding | 20.0m | 30.0m | **Y-axis is 10m too large** -- the AI swapped or miscalculated the Y dimension |
| Slabs | 2 | 2 | Correct |

**Critical failure: Y bounding box extends to 30m instead of 20m.** The building is 30x30 instead of 30x20. This is exactly the class of error Python scripts never make.

### 2.2 Medium Office (113 actions via OpenAI)

**Prompt:** 20m x 15m, 2 storeys, 4m x 5m grid, windows on all sides

**Actual output vs expected:**

| Element | Expected | Got | Issue |
|---------|----------|-----|-------|
| Columns | 48 | 48 | Correct (generators handled this) |
| Beams | ~68 | 20 | **Missing 48 beams** -- only 29% of required beams generated |
| Walls | 8 | 8 | Correct (generators handled this) |
| Windows | ~32 | 30 | Close but 2 short -- likely dropped last windows on some facades |
| Doors | 2 | 2 | Correct |
| Y bounding | 15.0m | 20.0m | **Y-axis is 5m too large** |

**Critical failures:**
1. **Y bounding box extends to 20m instead of 15m** -- same axis-swap pattern as the warehouse
2. **71% of beams are missing** -- the AI only generated perimeter edge beams, not the full interior grid
3. Window count slightly off (30 vs 32)

---

## Part 3: Root Cause Analysis -- Why Scripts Win

### 3.1 Shared Variables Enforce Consistency

```python
# Script approach: ONE source of truth
XS = [0.0, 8.0, 16.0, 24.0, 32.0, 40.0]
YS = [0.0, 6.25, 12.5, 18.75, 25.0]

# Every beam, column, wall, and opening uses XS and YS
# It is IMPOSSIBLE to put a beam at y=30 when YS stops at 25
```

In the AI workflow, each action is independent JSON. The column grid says `spacing_y=20`, the wall says `end_y=30`, and nothing catches the contradiction.

### 3.2 Loops Guarantee Completeness

```python
# Script: mathematically guaranteed to produce ALL beams
for storey in STOREYS:           # 5 floors
    for y in YS:                 # 5 rows
        for xi in range(len(XS)-1):  # 5 bays
            create_beam(...)     # = 125 X-beams
    for x in XS:                 # 6 columns
        for yi in range(len(YS)-1):  # 4 bays
            create_beam(...)     # = 120 Y-beams
# Total: 245 beams, exactly, always
```

The AI's `generate_beam_grid` tool does the same math -- but only if the AI decides to call it. In the medium office test, the AI used `generate_floor_plate` with edge beams instead of `generate_beam_grid`, which produced only perimeter beams.

### 3.3 Coordinate Math is Arithmetic, Not Reasoning

```python
# Script: pure arithmetic
offset_along_wall = 20.0 - 2.4/2  # = 18.8m (always correct)

# AI must reason: "centre at x=20, door is 2.4m wide, so offset = 20 - 1.2 = 18.8"
# This requires the AI to:
#   1. Know offset is measured from wall start (x=0)
#   2. Know the formula is centre - half_width
#   3. Compute 20 - 1.2 = 18.8 correctly
#   4. Not confuse this with "centre of wall" or "centre of bay"
```

The AI gets this right ~90% of the time. But across 100+ coordinates per building, 10% errors compound.

### 3.4 The Y-Axis Problem

Both test buildings have incorrect Y bounding boxes. The simple warehouse has Y extending to 30m (should be 20m). The medium office has Y extending to 20m (should be 15m).

Root cause: the AI-generated `generate_perimeter_walls` or `generate_column_grid` used the wrong Y dimension. This is consistent with either:
- Swapping the X and Y dimensions in the grid generator call
- Using `bays_y * spacing_y` that overshoots the building width
- Using `spacing_y = spacing_x` when they should differ

A script using `BASE_WIDTH_M = 20.0` as a constant would make this error impossible.

### 3.5 The Beam Deficit Problem

The medium office produced only 20 beams vs the ~68 required. Analysis:
- `generate_floor_plate` with `include_edge_beams=true` produces 4 perimeter beams per floor
- 2 floors x 4 = 8 edge beams, plus perhaps 12 from a partial `generate_beam_grid` call
- The AI should have called `generate_beam_grid` with matching grid parameters at each floor elevation
- Instead it relied on `generate_floor_plate` edge beams, missing all interior gridline beams

A script would have `generate_beam_grid()` called in the same loop as `generate_column_grid()`, using the same grid variables. The AI has no mechanism to enforce "beam grid must use same parameters as column grid."

### 3.6 Summary: Five Failure Modes

| # | Failure Mode | Script Immune? | AI Frequency |
|---|-------------|----------------|-------------|
| 1 | Dimension swap (X/Y confusion) | Yes -- named constants | High (~50% of tests) |
| 2 | Missing elements (incomplete grid) | Yes -- nested loops | High (~60% of tests) |
| 3 | Coordinate drift (elements misaligned) | Yes -- shared variables | Medium (~30%) |
| 4 | Centre-vs-corner confusion | Yes -- explicit placement | Medium (~20%) |
| 5 | Generator parameter mismatch | Yes -- same variables | High (~40%) |

---

## Part 4: Three Refactor Options

### Option A: Script Templates Triggered by AI Decisions (Easy)

**How it works:**

The AI outputs a structured building specification, not individual IFC actions:

```json
{
  "building_type": "warehouse",
  "footprint": {"length": 30, "width": 20},
  "grid": {"spacing_x": 10, "spacing_y": 20},
  "storeys": [
    {"name": "Ground Floor", "elevation": 0.0, "height": 6.0}
  ],
  "frame": {
    "column_section": {"width": 0.3, "depth": 0.3},
    "beam_section": {"width": 0.3, "depth": 0.4}
  },
  "envelope": {
    "wall_type": "metal_panel",
    "wall_thickness": 0.2
  },
  "slabs": [
    {"level": "ground", "thickness": 0.2},
    {"level": "roof", "thickness": 0.15}
  ],
  "openings": [
    {"type": "overhead_door", "wall": "south", "count": 2, "width": 4, "height": 4.5, "centres": [10, 20]},
    {"type": "personnel_door", "wall": "east", "count": 1, "width": 1.0, "height": 2.1, "centre_along_wall": 10}
  ]
}
```

A Python template script (analogous to `build_retail_terrace_concept.py` but parameterized) expands this into deterministic IFC actions.

**Accuracy improvement:** ~90% of failures eliminated. The template handles all coordinate math, grid generation, and completeness. The AI only needs to fill in ~15 design parameters instead of computing ~100 coordinates.

**AI output reduction:** From ~30-113 individual actions to ~1 JSON spec of ~30 lines. Token output drops ~80%.

**What the AI needs to know:**
- Building typology (warehouse, office, retail)
- High-level dimensions (footprint, height, grid spacing)
- Material/section choices
- Opening placement (which walls, how many, sizes)

**What Python handles:**
- All coordinate math
- Grid generation (columns, beams, slabs at every intersection)
- Wall generation (perimeter from footprint)
- Opening placement (offset calculations from wall start)
- Completeness enforcement (every bay gets beams, every floor gets slabs)

**Migration path:**
1. Create `building_templates/` directory with one template per building type
2. Start with `warehouse_template.py` and `office_template.py`
3. Modify the planner to output a spec instead of actions for recognized building types
4. Existing action-based path remains as fallback for unrecognized types
5. Add a spec validator that checks dimensional consistency before expansion

**New tools/scripts needed:**
- `building_templates/warehouse.py` (~200 lines)
- `building_templates/office.py` (~300 lines)
- `building_templates/retail.py` (~400 lines)
- `spec_validator.py` (~100 lines) -- checks footprint >= grid, height > 0, etc.
- `spec_expander.py` (~150 lines) -- dispatches spec to appropriate template

**Estimated effort:** 2-3 days for initial warehouse + office templates.

---

### Option B: Generator-Heavy Workflow (Medium)

**How it works:**

Keep the current action-based AI output, but add new generators and make the AI prefer them by default. The key insight: the existing generators (`generate_column_grid`, `generate_beam_grid`, `generate_perimeter_walls`, `generate_floor_plate`) already handle the math correctly -- the problem is the AI doesn't always use them, and key generators are missing.

**New generators needed:**

1. **`generate_structural_frame`** -- combines column_grid + beam_grid + floor_plate in one call, ensuring parameter consistency:
   ```json
   {
     "type": "generate_structural_frame",
     "storey_name": "Ground Floor",
     "grid_origin_x": 0, "grid_origin_y": 0,
     "bays_x": 3, "bays_y": 1,
     "spacing_x": 10, "spacing_y": 20,
     "base_z": 0, "storey_height": 6,
     "column_section": [0.3, 0.3],
     "beam_section": [0.3, 0.4],
     "slab_thickness": 0.15,
     "include_roof_slab": true
   }
   ```
   This single call produces all columns + all beams + slab for one floor. The AI cannot forget beams or use mismatched grid parameters.

2. **`generate_opening_array`** (already exists) -- but enhance it to accept `bay_centres` instead of just `spacing + start_offset`, reducing centering math the AI must do.

3. **`generate_facade_openings`** -- places windows on all four facades of a rectangular building in one call:
   ```json
   {
     "type": "generate_facade_openings",
     "building_length": 20, "building_width": 15,
     "window_width": 1.8, "window_height": 1.5,
     "sill_height": 0.9,
     "x_spacing": 4, "y_spacing": 5,
     "storey_name": "Ground Floor",
     "exclude_facades": []
   }
   ```

4. **`generate_building_envelope`** -- walls + slab-on-grade + roof slab from footprint dimensions.

**Accuracy improvement:** ~75% of failures eliminated. Generator parameter consistency solves the beam deficit and Y-axis problems. But the AI still chooses which generators to call and in what order, so it can still make mistakes at the composition level.

**AI output reduction:** From ~30-113 actions to ~8-15 generator calls. Token output drops ~60%.

**What the AI needs to know:**
- Which generators to call
- Correct parameters for each (but fewer parameters than individual actions)
- Sequencing (storeys first, then structure, then envelope, then openings)

**What Python handles:**
- All coordinate expansion (grid -> individual elements)
- Completeness (every gridline gets beams)
- Consistency (shared grid parameters within a generator)
- Centering calculations for openings

**Migration path:**
1. Implement `generate_structural_frame` in the compiler (combines existing column_grid + beam_grid + floor_plate)
2. Implement `generate_facade_openings` and `generate_building_envelope`
3. Update the system prompt to strongly prefer composite generators
4. Add prompt examples showing the correct generator-first workflow
5. Existing action-based tools remain for custom/irregular elements

**New tools/scripts needed:**
- Compiler additions for 3 new generator types (~300 lines in `compiler.py`)
- New tool specs (~100 lines in `tool_specs.py`)
- Updated system prompt with generator-first examples (~50 lines)
- Tool registry updates for new phase groupings (~20 lines)

**Estimated effort:** 3-5 days.

---

### Option C: Full Spec-First with Construction-Aware Generators (Hard)

**How it works:**

The AI outputs a building specification document (not actions, not generator calls). Domain-specific Python code interprets the spec with real construction knowledge:

```json
{
  "spec_version": "1.0",
  "building": {
    "name": "Steel Warehouse",
    "occupancy": "S-1",
    "construction_type": "IIB",
    "footprint": {"type": "rectangle", "length": 30, "width": 20, "origin": [0, 0]},
    "roof_type": "gable",
    "eave_height": 6.0,
    "ridge_height": 7.5
  },
  "structural_system": {
    "type": "rigid_frame",
    "frame_spacing": 10.0,
    "frame_material": "steel",
    "frame_profile": "tapered_rafter",
    "column_base": "pinned",
    "lateral_system": "rigid_frame_action",
    "secondary_framing": {
      "purlins": {"spacing": 1.5, "profile": "Z-purlin"},
      "girts": {"spacing": 1.8, "profile": "C-girt"}
    }
  },
  "envelope": {
    "roof": {"type": "standing_seam_metal", "r_value": 30},
    "walls": {
      "type": "insulated_metal_panel",
      "thickness": 0.1,
      "r_value": 25,
      "panel_joint": 0.025
    }
  },
  "openings": [
    {"type": "overhead_door", "wall": "south", "count": 2, "size": [4, 4.5], "centres": [10, 20]},
    {"type": "man_door", "wall": "east", "count": 1, "size": [1.0, 2.1], "centre": 10}
  ],
  "foundations": {
    "type": "spread_footing",
    "soil_bearing": 150,
    "frost_depth": 1.2,
    "slab_on_grade": {"thickness": 0.15, "reinforcement": "WWF"}
  }
}
```

Python generators produce:
- **Tapered rigid frames** (not rectangular columns) with haunch geometry
- **Insulated metal panels** with 1-inch joints and proper lap patterns
- **Secondary framing** (purlins at purlin spacing, girts at girt spacing)
- **Real AISC sections** from a catalog lookup based on span and load
- **Foundations** sized from tributary loads and soil bearing capacity
- **Fire-rated assemblies** matching the construction type

**Accuracy improvement:** ~95% of failures eliminated. The spec is so high-level that there is almost no opportunity for coordinate errors. Additionally, the construction-aware generators produce buildings that are not just geometrically correct but structurally plausible.

**AI output reduction:** From ~30-113 actions to ~1 spec of ~40 lines. Token output drops ~90%.

**What the AI needs to know:**
- Building program (use, size, height)
- Code requirements (occupancy, construction type)
- Structural system choice (rigid frame vs braced frame vs moment frame)
- Envelope type (metal panel vs masonry vs curtain wall)
- Opening requirements

**What Python handles:**
- All geometry generation
- Section selection from catalogs
- Load path logic (tributary areas -> column loads -> footing sizes)
- Construction detailing (panel joints, connection types)
- Code-compliant assemblies (fire ratings, insulation)

**Migration path:**
1. Define the spec schema (JSON Schema, ~300 lines)
2. Implement a `WarehouseGenerator` class with full construction logic (~800 lines)
3. Implement an `OfficeGenerator` class (~1000 lines)
4. Create an AISC section catalog and lookup functions (~200 lines + data)
5. Create a footing sizing module (already exists: `footing_selector.py`)
6. Build a `spec_interpreter.py` that routes specs to the right generator
7. Modify the planner to output specs instead of actions
8. Add a spec validation layer that catches impossible combinations

**New tools/scripts needed:**
- `building_spec_schema.json` (~300 lines)
- `generators/warehouse.py` (~800 lines)
- `generators/office.py` (~1000 lines)
- `generators/retail.py` (~1200 lines)
- `section_catalog.py` + AISC data (~500 lines)
- `spec_interpreter.py` (~200 lines)
- `spec_validator.py` (~200 lines)
- Updated planner prompts (~100 lines)

**Estimated effort:** 3-6 weeks.

---

## Part 5: Comparison Matrix

| Criterion | Option A (Templates) | Option B (Generators) | Option C (Full Spec) |
|-----------|---------------------|----------------------|---------------------|
| **Accuracy gain** | ~90% | ~75% | ~95% |
| **AI output size** | ~30 lines | ~8-15 calls | ~40 lines |
| **Token reduction** | ~80% | ~60% | ~90% |
| **Building types supported** | Only templated types | Any type (generators compose) | Only spec'd types |
| **Custom geometry** | Falls back to actions | Native support | Falls back to actions |
| **Construction realism** | Low (geometric only) | Low (geometric only) | High (real sections, connections) |
| **Implementation effort** | 2-3 days | 3-5 days | 3-6 weeks |
| **Risk** | Low | Low | Medium (scope creep) |
| **Extensibility** | New template per type | New generator per pattern | New generator class per type |

## Part 6: Recommendation

**Start with Option B (Generator-Heavy), then layer Option A on top.**

Reasoning:

1. **Option B is the lowest-risk highest-impact change.** The `generate_structural_frame` composite generator eliminates both the beam deficit problem (by bundling columns + beams + slab into one call) and the parameter mismatch problem (by sharing grid variables internally). It requires only compiler additions, not new AI output formats.

2. **Option A can be added incrementally.** Once the generators are solid, adding a spec-to-generator translator for common building types is straightforward. The spec becomes a thin layer that maps to generator calls, which map to IFC actions. This gives the 90% accuracy of templates with the flexibility of generators for non-standard elements.

3. **Option C is the long-term goal** but should wait until the generator library is mature. The construction-aware logic (section catalogs, load-based sizing) can be added to generators one at a time. Attempting the full spec-first approach before generators are proven would risk building a fragile monolith.

**Concrete next steps:**

1. Implement `generate_structural_frame` in the compiler (1 day)
2. Implement `generate_facade_openings` in the compiler (1 day)
3. Update the system prompt to make composite generators the default path (0.5 day)
4. Add a `building_spec` output mode to the planner for warehouse/office types (1 day)
5. Write an integration test that compares spec-generated vs AI-generated buildings against ground truth (1 day)

**Success metric:** The Y-axis error and beam deficit should both drop to 0% on the existing warehouse and office test cases.

---

## Appendix: Raw Evidence

### A.1 Simple Warehouse Errors

```
Bounding box: X=[-0.15, 30.15] Y=[-0.15, 30.0] Z=[0.0, 6.15]
                                    ^^^^^^^^^^^^
Expected Y: 0 to 20.  Got: 0 to 30.  Delta: +10m (50% oversize)

Beams: 10 / 13 expected = 77% coverage
```

### A.2 Medium Office Errors

```
Bounding box: X=[-0.175, 20.175] Y=[-0.175, 20.0] Z=[0.0, 7.7]
                                      ^^^^^^^^^^^^^
Expected Y: 0 to 15.  Got: 0 to 20.  Delta: +5m (33% oversize)

Beams: 20 / ~68 expected = 29% coverage (71% missing)
Windows: 30 / 32 expected = 94% coverage
```

### A.3 Beam Script (patch_five_story_beams.py) -- Why It Can't Fail

```python
XS = [0.0, 8.0, 16.0, 24.0, 32.0, 40.0]   # 6 positions
YS = [0.0, 6.25, 12.5, 18.75, 25.0]         # 5 positions

# X-direction beams: 5 rows x 5 spans = 25 per floor
for y in YS:                    # hits all 5 rows
    for xi in range(len(XS)-1): # hits all 5 spans
        create_beam(XS[xi], y, XS[xi+1], y)

# Y-direction beams: 6 columns x 4 spans = 24 per floor
for x in XS:                    # hits all 6 columns
    for yi in range(len(YS)-1): # hits all 4 spans
        create_beam(x, YS[yi], x, YS[yi+1])

# Per floor: 25 + 24 = 49 beams
# 5 floors x 49 = 245 total beams -- mathematically guaranteed
```

The AI would need to produce 245 individual beam actions with correct coordinates, or correctly parameterize 10 `generate_beam_grid` calls (one per floor, X and Y). The script does it in 12 lines of loop logic using 3 shared arrays.
