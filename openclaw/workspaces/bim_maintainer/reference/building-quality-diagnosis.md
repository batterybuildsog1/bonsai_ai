# Five-Story Mezzanine Building Quality Diagnosis

**Date:** 2026-03-30
**File examined:** `out/five_story_mezzanine/five_story_mezzanine.ifc`
**Planner:** Phased planner (`phased_planner.py`)
**Comparison baseline:** `out/retail_terrace_concept/retail_terrace_concept.ifc` (hand-coded, not AI-generated)

---

## Executive Summary

The building is **partially coherent but has critical spatial misalignment**: columns and curtain walls form a correct 40m x 25m footprint, but all floor slabs and their edge beams are offset by (20m, 12.5m) -- exactly half the footprint dimensions. This is a **model issue** (the AI generated incorrect coordinates), not a harness/compiler bug. The phased planner's architecture is not the root cause, but its lack of spatial validation between phases allowed the error to propagate unchecked.

**Verdict: 60% model issue, 40% API design issue.**

---

## Build Log Summary

From `out/five_story_mezzanine/build_log_final.txt`:

| Phase | Actions | Time | Notes |
|-------|---------|------|-------|
| storeys | 5 | 6.4s | 5 storeys created correctly |
| structure | 195 | 28.2s | Column grids + floor plates + beams |
| mezzanines | 28 | 31.4s | Mezzanine slabs + support columns |
| envelope | 4 | 10.5s | 4 curtain walls |
| openings | 0 | 8.3s | No walls -> no openings possible |

**Total: 232 actions, 92.3s, 0 reported errors.**

No compilation errors. No authoring errors. The system believes the build succeeded perfectly, which is itself a problem -- there is no spatial validation.

---

## Element Inventory

| IFC Type | Count | Assessment |
|----------|-------|------------|
| IfcBuildingStorey | 5 | Correct elevations: 0, 4.5, 8.5, 12.5, 16.5m |
| IfcColumn | 174 | Correct grid at (0,0)-(40,25) |
| IfcBeam | 40 | Edge beams MISALIGNED; interior beams OK |
| IfcSlab | 9 | ALL 9 slabs MISPLACED |
| IfcCurtainWall | 4 | Correct positions and full-height spans |
| IfcPlate | 330 | Curtain wall panels, positioned correctly |
| IfcWall | 0 | Missing -- no opaque walls generated |
| IfcDoor | 0 | Cannot exist without IfcWall hosts |
| IfcWindow | 0 | Cannot exist without IfcWall hosts |

---

## Detailed Findings

### 1. Storey Elevations -- CORRECT

Storeys have proper Z placements:
- Level 1: Z = 0.0m
- Level 2: Z = 4.5m
- Level 3: Z = 8.5m
- Level 4: Z = 12.5m
- Level 5: Z = 16.5m

Column heights are appropriate: 4.5m (L1), 4.0m (L2-L5). Total building height = 20.5m.
Elements are properly parented to their storeys with correct local Z = 0 coordinates, inheriting the storey Z offset through the IFC placement hierarchy.

### 2. Column Grid -- CORRECT

174 columns on a regular 6x5 grid (6 bays x 4 bays + 1):
- **X positions:** 0, 8, 16, 24, 32, 40m (6 positions, 8m spacing)
- **Y positions:** 0, 6.25, 12.5, 18.75, 25.0m (5 positions, 6.25m spacing) plus additional at 10, 15m for mezzanine support
- **Distribution:** 30 columns per typical floor, 42 on L3/L4 (extra mezzanine columns)

The grid is coherent and well-structured. The AI used `generate_column_grid` correctly with `grid_origin_x=0, grid_origin_y=0`.

### 3. Main Floor Slabs -- MISPLACED (Critical Bug)

All 5 main floor slabs have:
- **Placement origin:** (20.0, 12.5, 0.0) relative to their storey
- **Profile:** polyline (0,0) to (40, 25) -- a 40m x 25m rectangle
- **Actual world coverage:** (20, 12.5) to (60, 37.5)
- **Expected coverage:** (0, 0) to (40, 25)

**Root cause:** The AI generated `x=20.0, y=12.5` for the `generate_floor_plate` action, interpreting x,y as the **center** of the footprint (40/2 = 20, 25/2 = 12.5). However, the API treats x,y as the **bottom-left corner origin**. The slab profile is drawn as a polyline starting at (0,0) in local space, so the placement origin IS the corner, not the center.

The AI correctly computed `x=0, y=0` for `generate_column_grid.grid_origin_x/y` but incorrectly used center coordinates for `generate_floor_plate.x/y`. This inconsistency suggests the AI was uncertain about the coordinate convention and guessed differently for different action types.

### 4. Edge Beams -- MISPLACED (follows slabs)

The `_compile_floor_plate()` function generates 4 edge beams using world corners computed from the slab's (x, y) origin:
```
South beam: (20, 12.5) to (60, 12.5)  -- should be (0, 0) to (40, 0)
East beam:  (60, 12.5) to (60, 37.5)  -- should be (40, 0) to (40, 25)
North beam: (60, 37.5) to (20, 37.5)  -- should be (40, 25) to (0, 25)
West beam:  (20, 37.5) to (20, 12.5)  -- should be (0, 25) to (0, 0)
```

The beams are correctly computed relative to the slab origin -- the compiler is not at fault. The beams are wrong because the slab origin was wrong.

**Interior beams** (created separately by the AI as individual `create_beam` actions) are at correct positions: (0, 6.25) to (40, 6.25) etc. This further confirms the AI knows the correct building extents but used wrong coords for floor plates specifically.

### 5. Mezzanine Slabs -- MISPLACED AND MALFORMED

4 mezzanine slabs (west and east on Levels 3 and 4):
- **West Mezzanine:** placed at (20.0, 5.0) with profile 10m x 40m
  - World coverage: X=(20,30), Y=(5,45) -- extends 20m beyond building edge
- **East Mezzanine:** placed at (20.0, 20.0) with profile 10m x 40m
  - World coverage: X=(20,30), Y=(20,60) -- extends 35m beyond building edge

**Problems:**
1. Origin coordinates appear to be center-ish values, not corner values
2. Width and depth appear swapped: a 10m-wide mezzanine should span 10m in Y (building width direction), not 40m
3. The profile has length=10 along X and width=40 along Y, but the building is only 25m in Y
4. Mezzanine columns at Y=10 (west) and Y=15 (east) do not align with slab edges

### 6. Curtain Walls -- CORRECT

4 curtain walls properly positioned:
- **North Metal Facade:** Y=25, facing along X, 120 panels, Z=0 to 20.5m
- **South Glass Facade:** Y=0, facing along X, 54 panels, Z=0 to 4.5m (ground floor only)
- **West Metal Facade:** X=0, facing along Y, 78 panels, Z=0 to 20.5m
- **East Metal Facade:** X=40, facing along Y, 78 panels, Z=0 to 20.5m

The facade grid compilation (generate_facade_grid -> create_curtain_wall) works correctly. The AI used start/end coordinates properly for line-defined facades.

### 7. Missing Walls, Doors, and Windows

- **0 IfcWall elements**: The envelope phase only created curtain walls, no opaque walls
- **0 doors, 0 windows**: The openings phase detected no IfcWall to host openings and correctly returned 0 actions
- The phased planner's openings phase constraint is correct: "windows and doors can only be hosted in walls created by create_wall (IfcWall), NOT in curtain walls"
- But the envelope phase should have created some opaque walls for the upper floors to host windows

---

## Root Cause Analysis

### Primary Issue: AI Coordinate Confusion (Model Issue)

The AI model (running through OpenClaw) consistently misinterpreted `x, y` parameters for `generate_floor_plate` and `create_rect_slab` actions as **center coordinates** when the API treats them as **origin (bottom-left corner) coordinates**.

Evidence:
- `generate_column_grid`: AI correctly used `grid_origin_x=0, grid_origin_y=0` (parameter name includes "origin")
- `generate_facade_grid`: AI correctly used `start_x/start_y` and `end_x/end_y` (parameter names are explicit)
- `generate_floor_plate`: AI incorrectly used `x=20, y=12.5` (exactly half the footprint -- center coordinates)
- `create_rect_slab` (mezzanines): AI incorrectly used center-like coordinates

The parameter name `x` / `y` with description "X coordinate in meters" / "Y coordinate in meters" is ambiguous. The column grid uses `grid_origin_x` (explicit), while the floor plate uses bare `x` (ambiguous). The AI guessed correctly when the name contained "origin" or "start/end" but guessed wrong when it was bare `x/y`.

### Secondary Issue: No Spatial Validation (Harness Issue)

The phased planner has no spatial coherence checks:
1. No check that slab extents match column grid extents
2. No check that beams connect to columns
3. No check that mezzanine slabs fit within the building footprint
4. No check that element counts are reasonable
5. `scene_summary()` only reports element names and counts, not positions

The `scene_summary()` passed between phases lists:
```
Storeys: Level 1, Level 2, Level 3, Level 4, Level 5
IfcSlab: Level 1 Main Floor Plate-Slab, Level 2 Main Floor Plate-Slab, ...
```

It does NOT include any coordinate information. So when the mezzanines phase runs, it cannot see where the structure phase placed elements and cannot verify alignment.

### Tertiary Issue: No Opaque Walls (Model Issue)

The AI chose to wrap the entire building in curtain walls, leaving no IfcWall surfaces for the openings phase to insert doors and windows. This is a plausible but incomplete design choice -- a real 5-story building would typically have opaque walls on at least some upper-floor facades.

### Non-Issue: Phased Architecture

The phased approach itself is sound:
- Storeys were created first with correct elevations
- Structure phase saw the storeys and created columns at correct Z
- Elements are properly contained in their storeys
- The IFC placement hierarchy (storey-relative coordinates) works correctly
- The compiler correctly expands parametric generators into primitives

The phasing did not cause the coordinate error -- the AI would have made the same center-vs-origin mistake in a single-pass plan.

---

## Comparison with retail_terrace_concept

| Aspect | retail_terrace_concept | five_story_mezzanine |
|--------|----------------------|---------------------|
| Built by | Hand-coded Python script | AI via phased planner |
| Slab origin x,y | (0, 0) -- correct corner | (20, 12.5) -- wrong, center |
| Column-slab alignment | Aligned | Misaligned by 20m, 12.5m |
| Walls | 8 IfcWall | 0 IfcWall |
| Doors/windows | 4 doors, 17 windows | 0 doors, 0 windows |
| Beam positions | Correct absolute coords | Edge beams wrong, interior correct |

The retail_terrace_concept was built programmatically (not AI-generated), so it doesn't suffer from coordinate interpretation errors.

---

## Recommended Fixes

### Fix 1: Clarify Parameter Names (API Design -- High Priority)

Rename ambiguous `x, y` parameters in `generate_floor_plate` to match the explicit naming used elsewhere:

```python
# In tool_specs.py and action_catalog.py, change:
"x": _number("Floor plate origin X in meters.")
"y": _number("Floor plate origin Y in meters.")

# To:
"origin_x": _number("Floor plate bottom-left corner X in meters (NOT center).")
"origin_y": _number("Floor plate bottom-left corner Y in meters (NOT center).")
```

Or alternatively, add a system-level instruction to all prompts:
> "All x,y coordinates are bottom-left corner origins, NOT centers."

### Fix 2: Add Spatial Validation Post-Phase (Harness -- High Priority)

After each phase, validate spatial coherence:

```python
def _validate_spatial_coherence(author: IfcAuthor) -> List[str]:
    warnings = []
    columns = author.model.by_type("IfcColumn")
    slabs = author.model.by_type("IfcSlab")

    if columns and slabs:
        col_xs = [get_absolute_x(c) for c in columns]
        col_ys = [get_absolute_y(c) for c in columns]
        col_bbox = (min(col_xs), min(col_ys), max(col_xs), max(col_ys))

        for slab in slabs:
            slab_bbox = get_slab_world_bbox(slab)
            if not bboxes_overlap(col_bbox, slab_bbox):
                warnings.append(f"Slab {slab.Name} does not overlap column grid")

    return warnings
```

### Fix 3: Enrich scene_summary() with Coordinates (Harness -- Medium Priority)

Add bounding box or key coordinate info to the scene summary passed between phases:

```python
# In scene_summary(), add:
col_positions = [(get_x(c), get_y(c)) for c in columns[:50]]
if col_positions:
    xs = [p[0] for p in col_positions]
    ys = [p[1] for p in col_positions]
    lines.append(f"Column grid bbox: X=[{min(xs):.1f}, {max(xs):.1f}], Y=[{min(ys):.1f}, {max(ys):.1f}]")
```

### Fix 4: Add Coordinate Convention to Execution Prompts (Prompt -- Medium Priority)

In `_build_execution_prompt()`, add:

```python
parts.append(
    "COORDINATE CONVENTION: All x,y coordinates are the bottom-left corner "
    "(minimum X, minimum Y), NOT the center. For a 40x25 slab at building "
    "origin, use x=0, y=0 (not x=20, y=12.5)."
)
```

### Fix 5: Require Opaque Walls for Openings (Prompt -- Low Priority)

Modify the envelope phase prompt to explicitly request both curtain walls and opaque walls where doors/windows are needed:

```python
if "openings" in [p["name"] for p in phases]:
    parts.append(
        "If the building needs doors or windows, at least some facade "
        "segments must be create_wall (IfcWall), not curtain walls."
    )
```

---

## Impact Assessment

| Issue | Severity | Visual Impact | Structural Impact |
|-------|----------|---------------|-------------------|
| Slab offset by (20, 12.5) | Critical | Slabs float outside building | Slabs not supported by columns |
| Edge beams offset | Critical | Beams in empty space | Not connected to structure |
| Mezzanine malformed | Critical | Extends 20m+ beyond building | Physically impossible |
| No opaque walls | Moderate | All-glass building | No door/window hosts |
| No doors/windows | Moderate | Inaccessible building | Missing program elements |

The building as generated would look like a column grid wrapped in glass curtain walls, with all floor slabs and edge beams floating 20m to the east and 12.5m to the north of the structure. The mezzanines extend dramatically beyond the building envelope. It would appear as two disconnected structures rather than one coherent building.
