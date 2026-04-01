# Deep Tradeoff Analysis: Options A, B, and C

**Date:** 2026-03-30
**Purpose:** Brutally honest assessment of downsides for each architecture option, stress-tested against real-world building complexity.

---

## Option B: Composite Generators (generate_structural_frame)

### The Pitch

Bundle columns + beams + slab into a single `generate_structural_frame` call. The AI calls ~8-15 generators instead of ~100+ primitives. Parameter consistency is enforced within each generator because the grid variables are shared internally.

### Downside 1: Non-standard frames are still hard

The `generate_structural_frame` call assumes a regular rectangular grid: uniform bay spacing in X, uniform in Y, same column section everywhere, same beam depth everywhere, one slab thickness.

Real buildings routinely violate every one of these assumptions:

- **Columns at different heights**: A ground-floor retail space at 5m with upper floors at 3.5m means column heights vary per floor. The generator handles this (one call per floor). But what about a double-height lobby that spans two floors? The generator produces columns on every floor. Now the AI must delete the intermediate columns and extend the ground-floor columns -- which means it is back to reasoning about individual elements.

- **Mixed bay sizes**: A building where the perimeter bays are 6m (for offices) but the central bay is 12m (for an open trading floor) cannot be expressed as `spacing_x = N`. The generator either takes a single spacing or an array of spacings. If it takes an array, the AI must specify `[6, 6, 12, 6, 6]` -- which is already close to the coordinate-level reasoning we are trying to avoid.

- **Irregular grids**: A column grid that is not rectilinear -- columns placed to follow a curved facade, or a grid that rotates 15 degrees in one wing -- cannot be expressed as bays_x/bays_y/spacing parameters at all. The generator is simply inapplicable.

### Downside 2: Bundling reduces flexibility, not complexity

`generate_structural_frame` produces columns + beams + slab. But the user might want:

- **Beams but no slab** (open steel frame for a canopy or parking structure).
- **Slab but no beams** (flat plate concrete construction where the slab spans directly to columns).
- **Different beam depths per direction** (deeper beams in the long span, shallower in the short span). The composite generator takes one beam section.
- **Different beam depths per floor** (transfer beams at the podium level, standard beams above).
- **Beams only in one direction** (one-way spanning joist floor).

Every one of these requires either (a) separate parameters that bloat the generator call, or (b) a post-generation edit step where the AI deletes/modifies elements. Option (a) turns the generator into a god-function with 20+ parameters -- recreating the very complexity it was meant to eliminate. Option (b) means the AI is still reasoning about individual elements for the irregular cases.

### Downside 3: Iterative modification is destructive

User says: "Make the ground floor columns 450mm instead of 300mm."

With individual `create_column` calls, the AI could target specific columns. With `generate_structural_frame`, the entire frame for that floor was produced by one call. The AI has two choices:

1. **Re-call the generator** with updated column_section. But the generator does not know which floor it previously generated. The AI must know to call it again for floor 1 only, with the new section, and somehow the system must delete or replace the old columns. This requires either (a) a "regenerate floor N" concept that does not exist, or (b) the AI issuing delete commands for all old ground-floor columns before regenerating.

2. **Issue individual update_element commands** for each column, changing width/depth. But the AI must know how many columns exist on the ground floor and their names. This is the same spatial reasoning problem we are trying to avoid.

Neither path is clean. The generator's "all or nothing" nature makes surgical edits harder, not easier.

### Downside 4: This is still AI-directed orchestration

The generators reduce action count from ~113 to ~15, but the AI still decides:
- Which generators to call
- In what order
- With what parameters
- Which floors get which treatment

The test results show the AI already fails at *choosing* which generators to use (it used `generate_floor_plate` edge beams instead of `generate_beam_grid` for the medium office). Adding more generators gives the AI more choices to get wrong. The beam deficit was not caused by a missing generator -- `generate_beam_grid` was available. The AI simply did not call it.

More generators do not fix a decision-making problem. They may even worsen it by expanding the action space the AI must navigate.

### Downside 5: Generator parameter mismatch is not fully solved

The pitch says `generate_structural_frame` eliminates parameter mismatch by sharing grid variables internally. True -- within a single call. But the AI still must ensure that `generate_structural_frame` on floor 2 uses the same grid as floor 1. If the AI calls the generator 5 times (once per floor), it must pass `bays_x=5, spacing_x=8` identically each time. The Y-axis swap error from the test results would still occur if the AI passes `spacing_y=20` on one floor and `spacing_y=15` on another.

The root cause is that the AI has no persistent variable binding across calls. Each generator call is an independent JSON object. Consistency across calls depends entirely on the AI's working memory.

### Honest Assessment

Option B is an incremental improvement that reduces the blast radius of AI errors (fewer calls = fewer opportunities to mess up) but does not address the fundamental problem: the AI is still an unreliable orchestrator of coordinate-dependent operations. It makes simple rectangular buildings somewhat safer. It does nothing for complex buildings.

---

## Option A: Spec Templates

### The Pitch

Predefined template scripts for common building types (warehouse, office, retail). The AI fills in ~15 parameters; Python does all coordinate math. ~90% accuracy improvement.

### Downside 1: Coverage is inherently limited

Templates must be authored by hand. Each template is hundreds of lines of Python:
- `warehouse_template.py` (~200 lines)
- `office_template.py` (~300 lines)
- `retail_template.py` (~400 lines)

What building types have no template?

- **Educational** (classrooms with corridors, labs with fume hoods, gymnasiums)
- **Healthcare** (patient rooms, nurses' stations, operating theaters -- wildly irregular layouts)
- **Hospitality** (hotel room repetition + unique lobby/ballroom/kitchen)
- **Religious** (vaulted ceilings, naves, transepts)
- **Industrial/manufacturing** (crane bays, specialized clearances)
- **Residential multifamily** (unit repetition with varied unit types)
- **Data centers** (raised floors, massive mechanical systems)
- **Performing arts** (sloped seating, fly towers, acoustic shells)

Each new type is a multi-day development effort. At what point do you have 20 templates and the maintenance burden exceeds the benefit?

### Downside 2: L-shapes, irregular footprints, setbacks

The templates assume rectangular footprints with optional parameters. Common real-world footprints that break this assumption:

- **L-shaped**: Two rectangles joined at a corner. A template could handle this with two footprint specs, but the structural grid must span the joint. Where do columns go at the intersection? Do beams span across or terminate?
- **Courtyard/U-shape**: The template must handle an interior perimeter in addition to the exterior perimeter. Walls face inward. Windows face the courtyard.
- **Stepped massing**: The building is wider at the base than the top (podium + tower). Each floor has a different footprint. The template needs per-floor footprint overrides.
- **Irregular polygon**: A triangular site, a wedge-shaped building on a curved street. Templates are fundamentally rectangular; polygons require a different approach entirely.
- **Curved facades**: A building with a curved south wall. The template generates straight walls. A curve requires segmented wall approximation or an entirely different wall generation strategy.

Templates either handle these cases (and become enormously complex) or do not handle them (and the user falls through to the action-based path, which is the path that already fails).

### Downside 3: Rigidity kills creative design

An architect says: "I want a 4-story office building where the ground floor is entirely open -- no interior columns -- supported by transfer beams, and the upper floors have a standard 8m grid."

The office template does not have a `transfer_beam` option. The architect is stuck. They cannot express their vision within the template's parameter space. The template becomes a straitjacket.

This is not hypothetical. Every real building has at least one "special" condition that deviates from the template. Architecture is fundamentally about the exceptions. A system that only handles the rule -- never the exception -- will be abandoned by architects who find it too limiting.

### Downside 4: Template proliferation and maintenance

Consider the parameter space for just an "office building" template:
- Rectangular vs L-shaped vs U-shaped footprint
- 1-50 stories
- Concrete frame vs steel frame vs composite
- Flat roof vs pitched roof vs green roof
- Curtain wall vs punched windows vs mixed
- With or without basement parking
- With or without retail podium
- Core location: central vs side vs dual
- Corridor layout: single-loaded vs double-loaded vs open plan

Even with generous defaulting, the combinatorial explosion means the template is either (a) too simple to handle real buildings, or (b) so parameterized that filling it out is as complex as writing a spec. Option (b) converges to Option C.

### Downside 5: The AI still needs construction knowledge

The template takes `beam_section: [0.3, 0.5]` as a parameter. Where does the AI get this number? It must know that a 300mm x 500mm beam is appropriate for an 8m span in a 5-story building. This is structural engineering knowledge. If the AI picks a 200mm x 200mm beam, the template will faithfully produce a building with undersized beams.

The template guarantees geometric correctness (no coordinate errors) but not engineering correctness (appropriate member sizes). The AI is still making engineering decisions with no guardrails.

### Honest Assessment

Option A solves the coordinate math problem for the narrow set of buildings that fit predefined templates. It is the fastest to implement and the easiest to validate. But it is fundamentally limited to "simple rectangular buildings of known types" -- which is exactly the class of buildings that the AI already handles tolerably well. The buildings the AI fails on (complex, irregular, multi-system) are precisely the buildings templates cannot cover.

---

## Option C: Spec-First with Construction Generators

### The Pitch

The AI outputs a ~200-token building specification. Deterministic Python generators with embedded construction knowledge expand it into 558 perfectly-coordinated elements in 5 seconds. 95% accuracy improvement. Zero coordinate errors.

### Downside 1: The spec format assumes regularity

The spec schema has been designed around regular rectangular buildings. It handles the easy case beautifully. Now consider the hard cases:

**Curved facade**: The spec has `facades.south.type = "curtain_wall"`. This generates a flat curtain wall along the south edge. A curved facade requires either (a) polyline vertices for the wall path, which the spec does not support, or (b) segmented approximation as an override, which requires the AI to compute segment endpoints -- exactly the coordinate math the spec was meant to eliminate.

**Stepped setback**: The building steps back 5m at floor 4. The spec has a single `footprint` field that applies to all floors. Per-floor footprint overrides are not in the schema. This could be added (`stories[3].footprint = {length: 35, width: 25}`), but now the grid resolution becomes floor-dependent, beams at the setback edge need special treatment (they terminate at the setback line, not at the next gridline), and the column grid has holes. The generator complexity explodes.

**Mixed structural systems**: Steel frame for the office floors, concrete core walls for lateral resistance, post-tensioned slabs for the parking levels. The spec has one `structure.frame_type` field. Per-floor structural system overrides would require the generator to switch between fundamentally different construction logic (steel column-beam vs concrete wall-slab) at a floor boundary. This is not a parameter change; it is a different generator entirely.

**Additions to existing buildings**: The spec assumes a greenfield building. An addition to an existing structure requires knowing where the existing building ends and the new one begins, how to tie into existing foundations, where to cut openings in existing walls. The spec has no concept of "existing conditions."

### Downside 2: Spec format lock-in

Once the AI is trained (or prompted) to output specs in a specific format, and once users have saved specs, the format becomes an API contract. Changing the spec schema breaks:
- All saved specs
- All AI prompts that reference the schema
- All validation logic
- All generator code that reads the spec

Schema evolution is manageable (versioning, migration scripts), but it imposes a governance burden. Every new building feature must be expressed within the existing schema or requires a schema version bump. This creates a tension between "keep the spec simple" and "handle more building types."

In practice, the spec will grow. The current schema has 25 top-level fields. Add per-floor footprints, per-floor structural systems, curved walls, inclined slabs, irregular grids, and it becomes 40+ fields. At some point, the spec is no longer a "200-token design intent document" -- it is a full building description language, and the AI must learn a DSL instead of just describing a building.

### Downside 3: Generator complexity and correctness

Each generator embeds construction knowledge:
- `_generate_beam_grid()` knows that beams go at gridline intersections and their base_z is at the top of columns
- `_generate_foundations()` knows how to compute tributary areas and size footings
- `_auto_select_column()` uses a simplified capacity check: `Pu <= 0.5 * Fy * Ag`

Who verifies this knowledge is correct?

The simplified column capacity check in the spec-first design uses `0.5 * Fy * Ag`, which is a gross simplification of AISC Chapter E column design (which involves slenderness ratios, effective length factors, critical stress calculations, and local buckling checks). For a short stocky column, `0.5 * Fy * Ag` may be conservative. For a slender column, it could be wildly unconservative. A 6-story building with 4m floor heights has columns with slenderness ratios around 40-60 -- right in the zone where the simplified check diverges significantly from the real capacity.

This is not academic nitpicking. If the system produces member sizes that a structural engineer would reject, the spec-first approach has traded geometric accuracy for engineering inaccuracy. The user sees a building that "looks right" but has members that are too small (or wastefully too large).

Maintaining engineering correctness across all generators requires ongoing review by someone who understands both the construction domain and the code. This is a rare skill set. As generators multiply (one per building type, one per structural system, one per foundation type), the maintenance burden grows linearly with coverage.

### Downside 4: The "558 elements in 5 seconds" claim assumes the easy case

The 5-story office example is a perfectly regular rectangular building with a uniform grid, four flat facades, repetitive windows, and a single structural system. This is the simplest possible multi-story building. The impressive numbers are accurate but misleading -- they describe peak performance on the easiest class of input.

For a complex building (L-shaped, stepped, mixed-use, with an atrium and a feature stair), the spec either:
1. Cannot express the building (user is stuck)
2. Uses the `overrides` escape hatch extensively (user is back to writing individual actions)
3. Requires schema extensions that have not been built yet

The override mechanism is the system's admission that the spec cannot handle everything. But overrides are individual actions -- the same actions that fail at scale in the current system. If 20% of the building requires overrides, the user is writing 100+ override actions for a 500-element building. The spec saved them from writing the other 400, which is still a win, but the user's pain point has not been eliminated -- it has been reduced.

### Downside 5: Creative constraint

The spec format implicitly defines the design space. If the spec has `facades.*.type = "wall" | "curtain_wall" | "panel_array"`, then those are the only three facade types the system can produce. A designer who wants:
- A perforated metal screen facade
- A double-skin curtain wall
- Timber cladding with horizontal boards
- A green wall / living facade
- Operable louvers

...cannot express any of these. The `overrides` array can create arbitrary elements, but the designer must describe them as low-level geometric primitives, which defeats the purpose of the high-level spec.

The spec format is a design vocabulary. A limited vocabulary produces limited designs. Expanding the vocabulary (more facade types, more structural systems, more opening patterns) grows the schema and the generator code in lockstep. There is no way to add new design options without writing new generator code.

### Honest Assessment

Option C is the architecturally cleanest solution and the correct end-state for simple-to-moderate buildings. The division of labor (AI decides, code computes) is exactly right. But it has a hard ceiling: buildings that do not fit the spec grammar require an escape hatch that recreates many of the problems the spec was meant to solve. The system is excellent for 60-70% of real-world buildings (regular, rectangular, standard construction) and inadequate for the other 30-40%.

---

## The Hybrid Question: Spec + Tool-Use Together

### How it would work

1. **Phase 1: Spec generates the regular structure.** The AI outputs a building spec covering footprint, grid, floors, walls, windows, foundations. The generator produces ~500 elements in 5 seconds. This covers the grid, the slabs, the standard facades, the repetitive windows.

2. **Phase 2: Tool-use handles the exceptions.** The AI then uses individual actions (or composite generators) to add:
   - The atrium void (delete slabs and beams in a zone, add guardrails)
   - The feature stair (custom geometry, not a standard switchback)
   - The skylight (custom roof opening with glazing)
   - The corner entrance (delete wall segments, add revolving door assembly)
   - The double-height lobby (delete intermediate floor slab and columns in a zone)
   - Per-floor facade variations that exceed what the spec can express

### How the AI knows when to switch

The AI does not "switch" modes. The workflow is sequential:

1. AI reads the user prompt and generates a spec covering the regular portions.
2. Generator expands the spec into a base model.
3. AI reviews the base model (element list, bounding box) and identifies what is missing or wrong relative to the user's intent.
4. AI generates targeted override actions for the exceptions.

The decision boundary is implicit in the spec schema: if the spec can express it, it goes in the spec. If not, it goes in the overrides.

### Problems with the hybrid approach

**Problem 1: The AI must understand both systems.** The AI needs to know the spec schema (to fill it out correctly) AND the action schema (to write overrides). This is a larger cognitive load than either system alone. The system prompt must explain both, increasing token cost.

**Problem 2: Override actions reference generated elements.** To delete slabs in the atrium zone, the AI must know the generated element names. But the names are assigned by the generator (e.g., "Level 3 Floor Slab"). The AI must predict what the generator will name things. If the naming convention changes, all overrides break.

Mitigation: The generator returns a manifest of created elements. The AI reviews the manifest before writing overrides. This adds a round-trip (generate -> review manifest -> write overrides) that increases latency and token cost.

**Problem 3: Overrides are fragile.** An override that says `delete_element(target_name="Level 3 Col-B4")` assumes the column grid has a column at grid position B4. If the user later changes the grid spacing (updating the spec), the column names change and the override breaks silently.

This is the classic problem of imperative patches applied to declarative specs. The spec is a description of what the building should be; overrides are a description of how to modify what was generated. When the spec changes, overrides may become nonsensical.

**Problem 4: Regeneration invalidates overrides.** The spec-first design recommends full regeneration for spec changes. But regeneration destroys all override-created elements. The overrides must be re-applied after every regeneration. If the spec changed in a way that makes an override invalid (e.g., the atrium zone now falls outside the building footprint), the override fails silently or produces garbage.

### Despite these problems, hybrid is the right answer

The problems are real but solvable:
- Manifest-based override targeting (overrides reference semantic locations, not element names)
- Override validation after regeneration (check that target elements still exist)
- Semantic override language ("delete all slabs in the zone x=12..24, y=8..16" instead of naming specific slabs)

The hybrid approach matches how architects actually work: start with a standard building, then customize. No architect designs a building from individual bricks. They start with a concept (the spec) and then make exceptions (the overrides). The hybrid approach mirrors this workflow.

---

## The Complicated Building Test

### The Prompt

> "Design a 6-story mixed-use building. L-shaped footprint. Ground floor retail with 6m ceiling, double-height lobby on the corner. Floors 2-3 are office with open floor plans. Floors 4-6 are residential with unit partitions. The east wing steps back 5m at floor 4 to create a terrace. South facade is full glass curtain wall. North and west are insulated concrete panels. There's a courtyard between the two wings."

### Decomposition into requirements

1. L-shaped footprint (two rectangular wings)
2. 6 stories with mixed program (retail, office, residential)
3. Double-height lobby at the corner (two-floor void)
4. Setback at floor 4 on the east wing (footprint changes mid-building)
5. Different facade treatment per face (curtain wall south, panels north/west)
6. Courtyard between wings (interior facades face the courtyard)
7. Unit partitions on residential floors (interior walls)

### Can Option C's spec format express this?

**Partially.** Here is what works and what does not:

**Works:**
- Mixed program per floor: `stories[0].program = "retail"`, etc.
- South curtain wall: `facades.south.type = "curtain_wall"`
- North/west panels: `facades.north.type = "panel_array"`
- 6m ground floor: `stories[0].height = 6.0`

**Does not work:**
- **L-shaped footprint**: The spec supports polygon footprints via `footprint.vertices`, so the L-shape itself is expressible. But the column grid uses a bounding-box approach with point-in-polygon culling. This works geometrically but produces an inefficient grid (columns are placed on a full rectangular grid, then culled). More importantly, beams at the inner corner of the L need special treatment -- they terminate at the re-entrant corner, not at the next gridline. The generator does not handle this.

- **Double-height lobby**: The spec has no concept of "void zones." The generator places a slab on every floor. To create a double-height lobby, the AI must delete the slab and columns on floor 2 in the corner zone -- this requires overrides. The override must target a specific rectangular region, which means the AI must compute the corner coordinates of the lobby zone.

- **Setback at floor 4**: The spec has a single footprint for all floors. Per-floor footprint overrides are not supported. The AI must delete columns, beams, and slabs that fall outside the reduced footprint on floors 4-6, and create a terrace slab at the setback line. This is ~20 override actions.

- **Courtyard interior facades**: The spec's `facades` section has four cardinal faces. An L-shaped building with a courtyard has at least 8 facade segments (4 exterior + 4 facing the courtyard). The spec cannot express interior facades at all.

- **Residential unit partitions**: The spec has no interior wall concept. Residential unit partitions are entirely override-driven.

**Verdict:** The spec covers maybe 60% of this building (the regular grid, the floor plates, the exterior walls, the basic massing). The remaining 40% -- the lobby void, the setback, the courtyard facades, the partitions -- requires ~50-80 override actions. The spec still saves significant effort (without it, the entire building is ~600+ individual actions), but the "200-token spec" promise is misleading for this building. The real output is a 200-token spec plus a 500-token override list.

### Can Option B's generators handle this?

**Somewhat.** The generators would be called as follows:

- `generate_structural_frame` for the east wing, floors 1-3 (regular grid)
- `generate_structural_frame` for the west wing, floors 1-6 (regular grid)
- `generate_structural_frame` for the east wing, floors 4-6 (reduced footprint, setback)
- `generate_perimeter_walls` for each wing, each floor
- `generate_facade_openings` for each facade type
- Individual `create_wall` for courtyard-facing facades
- Individual `create_wall` for residential partitions
- Individual `delete_element` for the lobby void

This is approximately 30-40 generator calls plus 30-40 individual actions. The AI must reason about the L-shape decomposition into two rectangular wings, compute the setback footprint, decide which floors get which generator call, and handle all the edge conditions. This is exactly the kind of spatial reasoning the AI fails at.

The generators help with the regular portions but do not help with the irregular portions, which are the hard part.

### Would the original tool-use approach do better?

**No, it would do worse.** The original approach requires ~600+ individual actions, each with explicit coordinates. The AI would need to:
- Place ~180 columns with correct coordinates across an L-shaped grid
- Place ~350 beams connecting the correct column pairs
- Create 8+ facade segments with correct start/end points
- Handle the setback by omitting elements above floor 3 in the east wing
- Create the lobby void by omitting slabs and columns in the correct zone
- Place ~40+ windows along non-trivial facade segments

This is exactly the scale at which both GPT-5.4 and Claude fail. The 5-story rectangular building (522 elements) already times out. An L-shaped 6-story building with setbacks would require ~700+ actions. It would not complete.

### What would a script look like?

A hand-authored script for this building would be approximately 400-600 lines:

```python
# Constants (design intent: ~50 lines)
WEST_WING = {"x": 0, "y": 0, "length": 30, "width": 20}
EAST_WING = {"x": 30, "y": 0, "length": 20, "width": 30}
SETBACK_FLOOR = 3  # 0-indexed: floors 4-6 step back
SETBACK_DEPTH = 5  # east wing loses 5m on the east side
LOBBY_ZONE = {"x": 25, "y": 0, "length": 10, "width": 15}  # corner
STORIES = [
    {"name": "Ground Retail", "height": 6.0, "program": "retail"},
    {"name": "Level 2", "height": 4.0, "program": "office"},
    {"name": "Level 3", "height": 4.0, "program": "office"},
    {"name": "Level 4", "height": 3.5, "program": "residential"},
    {"name": "Level 5", "height": 3.5, "program": "residential"},
    {"name": "Level 6", "height": 3.5, "program": "residential"},
]
GRID_SPACING = 8.0

# Grid computation (~30 lines)
west_xs = compute_gridlines(WEST_WING["x"], WEST_WING["length"], GRID_SPACING)
west_ys = compute_gridlines(WEST_WING["y"], WEST_WING["width"], GRID_SPACING)
east_xs = compute_gridlines(EAST_WING["x"], EAST_WING["length"], GRID_SPACING)
east_ys = compute_gridlines(EAST_WING["y"], EAST_WING["width"], GRID_SPACING)

# Per-floor element generation (~200 lines)
for i, story in enumerate(STORIES):
    elevation = sum(s["height"] for s in STORIES[:i])

    # West wing: full footprint all floors
    generate_columns(west_xs, west_ys, elevation, story["height"])
    generate_beams(west_xs, west_ys, elevation + story["height"])
    generate_slab(WEST_WING, elevation, thickness=0.2)

    # East wing: full footprint floors 0-2, reduced floors 3-5
    if i < SETBACK_FLOOR:
        east_footprint = EAST_WING
    else:
        east_footprint = {
            "x": EAST_WING["x"],
            "y": EAST_WING["y"],
            "length": EAST_WING["length"] - SETBACK_DEPTH,
            "width": EAST_WING["width"],
        }
    eff_east_xs = [x for x in east_xs if x <= east_footprint["x"] + east_footprint["length"]]
    generate_columns(eff_east_xs, east_ys, elevation, story["height"])
    generate_beams(eff_east_xs, east_ys, elevation + story["height"])
    generate_slab(east_footprint, elevation, thickness=0.2)

    # Skip lobby zone slab and columns on floor 2
    if i == 1:  # Level 2
        delete_elements_in_zone(LOBBY_ZONE, elevation)

# Facades (~100 lines)
for i, story in enumerate(STORIES):
    elevation = sum(s["height"] for s in STORIES[:i])
    # South facade: curtain wall
    create_curtain_wall("south", WEST_WING["x"], 0,
                        EAST_WING["x"] + effective_east_length(i), 0,
                        elevation, story["height"])
    # North facade: panels (two segments for L-shape)
    create_panel_array("north_west", WEST_WING, elevation, story["height"])
    create_panel_array("north_east", EAST_WING, elevation, story["height"])
    # West facade: panels
    create_panel_array("west", WEST_WING, elevation, story["height"])
    # Courtyard facades: walls
    create_courtyard_walls(WEST_WING, EAST_WING, elevation, story["height"])

# Terrace slab at setback (~20 lines)
terrace_elevation = sum(s["height"] for s in STORIES[:SETBACK_FLOOR])
create_terrace_slab(EAST_WING, SETBACK_DEPTH, terrace_elevation)
create_railing(terrace_perimeter(EAST_WING, SETBACK_DEPTH), terrace_elevation)

# Residential partitions (~60 lines)
for i in range(SETBACK_FLOOR, len(STORIES)):
    elevation = sum(s["height"] for s in STORIES[:i])
    create_unit_partitions(WEST_WING, elevation, STORIES[i]["height"], unit_width=6.0)
    create_unit_partitions(effective_east(i), elevation, STORIES[i]["height"], unit_width=6.0)
```

This script is explicit about every design decision. The grid computation, the setback logic, the lobby void, the per-floor footprint variation -- all of it is expressed in clear Python with named constants. There is no ambiguity, no AI reasoning required, and the coordinate math is guaranteed correct.

The question is: can any of the three options produce this building as reliably as this script? The honest answer is no. But Option C with a hybrid override mechanism comes closest.

---

## Synthesis: Where Each Option Belongs

### The Building Complexity Spectrum

| Complexity | Example | Best Option |
|---|---|---|
| Trivial | Rectangular warehouse, 1 story | Any option works. Option C is overkill. |
| Simple | Rectangular office, 3-5 stories, standard facades | Option C excels. Option B adequate. Option A works if template exists. |
| Moderate | Mixed-use podium + tower, rectangular, varied facades | Option C with minor overrides. Option B struggles with mixed facades. |
| Complex | L-shaped, setbacks, double-height spaces, courtyard | Option C + heavy overrides, or a hand-authored script. |
| Bespoke | Curved facades, irregular geometry, feature architecture | Hand-authored script. No option handles this well. |

### The uncomfortable truth

All three options optimize for the same segment of the market: regular rectangular buildings. This is the segment where the AI already performs tolerably well (the simple warehouse and medium office both produced functional buildings despite errors). The segment where the AI fails badly -- complex, irregular buildings -- is also the segment where all three options fail.

The reason is structural: all three options assume that a building can be described by a small number of parameters applied uniformly. Complex buildings violate this assumption. An L-shaped building with a setback and a courtyard is not "a rectangular building with exceptions." It is a fundamentally different design problem that requires spatial reasoning about zone boundaries, facade segments, and structural discontinuities.

### Recommendation

**Build Option C (spec-first) with the hybrid override mechanism, but do not pretend it solves the hard cases.**

1. **Spec-first for the 70% case**: Regular rectangular buildings get the full benefit: 200-token spec, 5-second generation, zero coordinate errors. This is a massive improvement over the current system.

2. **Override mechanism for the 20% case**: Moderate complexity (mixed facades, partial voids, simple setbacks) is handled by spec + 10-30 override actions. The override actions are simpler because they operate on a base model that already has the right grid, the right slabs, and the right walls. The AI is making targeted modifications, not building from scratch.

3. **Script path for the 10% case**: Truly complex buildings (L-shapes with courtyards, curved facades, bespoke architecture) get a hand-authored or AI-assisted script. The spec-first system should not try to handle these. Instead, invest in making script authoring easier: good libraries, good examples, good documentation.

4. **Do not skip Option B's generators**. Even within the spec-first system, the generators are the implementation mechanism. The `BuildingGenerator` class internally uses the same logic as `generate_structural_frame`, `generate_beam_grid`, etc. Building these generators first (Option B) creates the foundation for Option C. And the generators remain available for the override/script paths.

### What to build, in order

1. **Week 1**: `generate_beam_grid` and `generate_structural_frame` generators (Option B). These immediately fix the beam deficit and parameter mismatch problems. The existing action-based workflow gets better.

2. **Week 2-3**: Spec schema and `BuildingGenerator` class (Option C Phase 1). Rectangular buildings only. Test against the 5-story benchmark. Target: 558 elements, zero coordinate errors.

3. **Week 3-4**: Envelope and openings generators (Option C Phase 2). Add facades, windows, doors. Test against the full 5-story benchmark with all elements.

4. **Week 4-5**: Hybrid override mechanism. Test against the L-shaped building prompt. Measure how many overrides are needed. Iterate on the spec schema to reduce override count.

5. **Ongoing**: Expand spec coverage incrementally. Each new building test reveals gaps in the spec schema. Fill the gaps with new spec fields or new generators. Accept that some buildings will always need scripts.

### The metric that matters

The right success metric is not "accuracy on simple buildings" (all options achieve 90%+). It is **"what percentage of real user prompts can the system handle without falling back to the action-based path?"**

If that percentage is 70% at launch and grows to 85% over 3 months, the system is working. If it stalls at 50%, the spec schema is too rigid and needs rethinking. Track this metric relentlessly.
