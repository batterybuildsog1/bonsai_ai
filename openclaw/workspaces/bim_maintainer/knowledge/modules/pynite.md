# PyNite Backend

## Purpose
Runs finite element analysis using the PyNite FEA library, translating the analytical model into a PyNite FEModel3D and extracting results.

## How It Works

### pynite_backend.py (542 lines)
**`PyNiteSolverBackend`** implements `SolverBackend` protocol:
- `analyze(request, package, output_dir)`:
  1. Lazy-loads PyNite module via `importlib.import_module("Pynite")`.
  2. Creates `FEModel3D()` and a `_BuildContext` to track state.
  3. Calls pipeline: `_add_materials()` -> `_build_geometry()` -> `_apply_supports()` -> `_apply_loads()` -> `_apply_load_combinations()` -> `_run_solver()`.
  4. Builds summary and writes `solver_result.json`.
  5. Returns `AnalysisResult`.

**`_BuildContext`** dataclass tracks:
- `nodes_by_coord` (deduplication by rounded coordinates), `node_names`, `element_nodes`, `member_sections`, `member_materials`, `support_nodes`, `support_node_targets`.
- `ensure_node(name, x, y, z)` creates or finds an existing node at the given coordinates (rounded to 6 decimals).

**Geometry building:**
- `_add_column()`: creates 2 nodes (base + top), adds rectangular section properties, adds PyNite member.
- `_add_beam()`: creates 2 nodes (start + end), same section treatment.
- `_add_surface()`: creates 4-node quads for walls (start/end + height), slabs/panels (origin + length + width), and vertical panels (origin + width + height). Uses `add_quad()`.
- Section properties from `_section_properties()`: uses explicit `section_properties` from metadata if available (from catalog resolution), otherwise falls back to rectangular approximation (width * depth).

**Support application:**
- If explicit supports exist, applies them to the lowest node(s) of each target element.
- If no supports, infers fixed supports at all nodes at the minimum Z coordinate with a warning.

**Load application:**
- `_apply_self_weight()`: distributed FZ load on members using `weight_n_per_m` or computed from area * density * g.
- `_apply_pressure()`: `add_quad_surface_pressure()` on 4-node elements.
- `_apply_point_load()`: `add_node_load()` on element nodes, direction mapped via `_node_direction()` (global_x->FX, etc.).
- Load combinations created from `analytical_model.load_combinations` or auto-generated 1.0 factor combos.

**Results extraction:**
- `_build_summary()` computes: model counts, max displacement, support reactions per combo, support target reactions per combo, member demands per combo.
- `_member_demands()` extracts max absolute axial, moment (My, Mz), shear (Fy, Fz), and deflection (dy, dz) for each member across all combos.

### pynite_results.py (86 lines)
Standalone utility for summarizing PyNite results:
- `summarize_results(model, combo_names, warnings)` returns model counts, max displacement (with node/combo/components), and support reactions.
- Uses attribute probing (`_lookup_combo_value`) with fallback attribute names (e.g., `RxnFX` / `RXN_FX`).

## Current State
Fully implemented. The backend handles members (beams/columns) and quads (walls/slabs/panels/foundations) with gravity, wind, and footing loads.

### Fast Solver (factor-once-solve-many)
`_run_solver()` now defaults to a Cholesky factor-once-solve-many approach (`_run_solver_fast`):
- Uses PyNite for model setup (materials, geometry, supports, loads, load combos)
- Replaces PyNite's per-combo `spsolve` with a single `scipy.linalg.cho_factor` + per-combo `cho_solve`
- Uses PyNite's own `Analysis._prepare_model`, `_partition_D`, `_partition`, `_store_displacements`, and `_calc_reactions` for full compatibility
- Produces bit-identical results to PyNite's native solver (validated to 1e-10 displacement / 1e-5 reaction tolerance)
- Falls back to PyNite's `analyze_linear()` if the fast path fails (e.g. singular matrix, mock model)
- Controlled by `BONSAI_FEA_SOLVER` environment variable: `"fast"` (default) or `"pynite"` (original)

## Known Issues
- Seismic loads (`AnalysisDomain.SEISMIC`) are defined in the schema but `_apply_loads()` has no handler for the `"acceleration"` load kind -- seismic loads would fall through to the warning.
- Section properties use `ix_m4` for Iy and `iy_m4` for Iz (lines 492-493), which appears to swap the major/minor axis conventions. This could produce incorrect results for asymmetric sections.
- Surface elements (quads) don't contribute to member demands, so walls and slabs are present in the model but their internal forces are not reported.
- `_member_demand_for_combo()` returns zeros if the member doesn't have `max_axial` attribute, silently hiding solver failures.
- The fast solver converts K11 to dense for Cholesky, which uses O(n^2) memory. For very large models (>10k DOFs), a sparse Cholesky (e.g. `scikit-sparse.cholmod`) would be preferable.

## Last Reviewed
2026-03-30
