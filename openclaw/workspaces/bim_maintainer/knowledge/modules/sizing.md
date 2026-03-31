# Grouped Sizing

## Purpose
Iteratively sizes structural members by running FEA analysis, evaluating unity checks, and advancing to larger sections for groups that exceed capacity.

## How It Works

### grouped_sizing.py (317 lines)
**`GroupedSectionSizer`** class:
- Constructor: `solver_backend` (default `PyNiteSolverBackend()`), `max_iterations=8`.
- **`size(package, output_dir)`** -- main entry point:
  1. Calls `_initial_group_state()` to build a dict of `{group_id: {candidates: [...], index: 0}}` from each element's `catalog_selection.candidate_sections`.
  2. Loops up to `max_iterations`:
     a. Deep-copies the source model.
     b. Creates `current_overrides` mapping each group to its current candidate section.
     c. Calls `resolve_catalog_sections()` with overrides.
     d. Builds an analytical model via `StructuralAnalysisReducer`.
     e. Runs the solver to get results.
     f. Computes `_group_demand_summary()` and `_evaluate_groups()`.
     g. Calls `_advance_failing_groups()` -- increments the candidate index for groups with unity > 1.0.
     h. If nothing advanced, breaks (converged).
  3. Runs a final analysis with the converged sections.
  4. Writes: `sizing_summary.json`, `selected_section_costs.json`, `plan_roundtrip_summary.json`, `analytical_model.json`.
  5. Calls `apply_sized_sections_to_plan()` from `plan_roundtrip.py` to update the physical plan with resolved section dimensions.
  6. Returns `(final_result, sizing_summary, artifacts)`.

- **`_group_demand_summary()`** aggregates solver demands by sizing group, tracking max absolute values for axial, moment, shear, and deflection.
- **`_evaluate_groups()`** computes unity checks per group:
  - Axial ratio = axial_demand / (phi * Fy * A)
  - Moment major ratio = moment / (phi * Fy * Sx)
  - Moment minor ratio
  - Deflection ratio = max_deflection / deflection_limit
  - Unity = max of all ratios
- **`_advance_failing_groups()`** increments candidate index for groups with unity > 1.0. Returns `True` if any group changed.

**Helper functions:**
- `_initial_group_state()` extracts group state from source model elements.
- `_section_capacity()` computes phi*Fy*A and phi*Fy*S for a section.
- `_deflection_limit_m()` applies L/360 for floor beams, L/240 for roof/facade beams, 0 for columns.
- `_selected_section_costs()` tallies total weight and length by section.

### plan_roundtrip.py (77 lines)
- **`apply_sized_sections_to_plan(plan, source_model)`** maps resolved sections back to plan actions:
  1. Builds an index of actions by name and semantic element_id.
  2. For each source element with a section_id, finds the matching action and updates `width`/`depth` (for beams/columns) or `thickness` (for panels/slabs/footings).
  3. Returns a summary of applied changes.

## Current State
Fully implemented. The iterative sizing loop is simple but effective -- it monotonically increases section sizes until all groups pass or candidates are exhausted.

## Known Issues
- The sizing only goes in one direction (up). If the initial section is oversized, it stays oversized. No mechanism to try smaller sections.
- Capacity calculation uses phi=0.9 (LRFD) and the elastic section modulus, not the plastic section modulus. This is conservative but not aligned with AISC Chapter F for compact sections.
- No interaction equation is used (e.g., AISC H1-1 for combined axial + bending). The unity check uses `max()` of individual ratios, which underestimates demand for combined loading.
- Cold-formed sections (C, Z purlins) have no section records, so they are never sized.
- `_deflection_limit_m()` returns 0 for columns, meaning columns are never checked for deflection.

## Last Reviewed
2026-03-31
