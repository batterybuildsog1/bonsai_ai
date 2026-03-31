# Quality Audit: Iterative Build Comparison

## Date: 2026-03-31

## Builds Compared
- Build 1: `out/five_story_iterative/` (219 actions, 8 errors, 292s)
- Build 2: `out/test_openai_sub/` (215 actions, 0 errors, 226s)
- Both: openai-codex/gpt-5.4, iterative planner, subscription auth

## Critical Issues (Both Builds)

### 1. Slab Length/Width Ambiguity (SCHEMA)
AI assigns Length=25, Width=40. Harness maps Length→profile-X, Width→profile-Y.
Result: slabs cover X=0..25, Y=0..40 instead of X=0..40, Y=0..25.
**Fix:** Rename to x_extent/y_extent or document Length=X-axis explicitly.

### 2. Column Grid Doesn't Fit Building Width (MODEL)
3 bays × 8m = 24m but building is 25m. 1m unsupported gap at north wall.
**Fix:** Add system prompt rule: "grid must span the full building footprint."

### 3. Insufficient Beam Framing (MODEL)
4 beams/floor instead of ~20+. Most grid lines have no beam.
**Fix:** Add system prompt rule: "place beams at every column-to-column grid line."

### 4. Storey.Elevation = NULL (HARNESS)
ensure_storey doesn't set the IFC Elevation attribute.
**Fix:** Code change in ifc_author.py.

### 5. No Self-Verification (ARCHITECTURE)
Agent generates JSON but never checks spatial coherence.
**Fix:** Add bounding box + grid alignment checks to scene_summary.

## Build-Specific Issues

### Build 1 Only
- Mezzanine east slab overflows building by 15m (L/W swap)
- Envelope phase failed first try (non-numeric field)
- No north wall windows
- 8 errors not fully reported

### Build 2 Only
- Curtain wall panels overflow storey by 3.5m (2 rows of 4m panels in 4.5m storey)
- Curtain wall 0.5m wider than building (27 × 1.5m = 40.5m)
- Only service door, no main entrance
- Mezzanine edge columns are full-height (debatable)

## Fix Priority

1. Rename slab fields to x_extent/y_extent (SCHEMA) — eliminates 90deg rotation
2. Add spatial validation to scene_summary (HARNESS) — catches misalignment
3. Add grid-span and beam-framing rules to system prompt (MODEL guidance)
4. Set Storey.Elevation in ensure_storey (HARNESS)
5. Add visual verification capability (ARCHITECTURE)
