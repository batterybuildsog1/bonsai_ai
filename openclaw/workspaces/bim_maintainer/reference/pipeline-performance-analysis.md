# Bonsai AI Pipeline -- Deep Performance Analysis

Generated: 2026-03-30

## Pipeline Architecture Overview

The `DesignPipeline.run()` method in `pipeline.py` executes five serial stages:

```
1. Planner       -> build_physical_model(brief)
2. Physical      -> materialize(package, output_dir)       [IFC authoring]
3. Analysis      -> export(package, output_dir)            [structural + analytical model]
4. Solver        -> analyze(request, package, output_dir)  [FEA via PyNite]
5. Results       -> build(package, output_dir)             [JSON bundle]
```

When the grouped sizing loop (`grouped_sizing.py`) is active, stages 3-4 repeat
up to **8 iterations** inside a `deepcopy`-heavy loop, then re-execute the IFC
author a final time for roundtrip output.

---

## Stage-by-Stage Bottleneck Analysis

### 1. Planner (`planner.py` / `bonsai_ai_core`)

**What it does:** Sends user prompt + scene summary to an LLM provider (OpenAI,
Anthropic, or Google), receives a building plan, then compiles it into a list of
tool calls via `build_core_plan()` -> `compile_core_plan()`.

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **Network I/O** (LLM API round-trip) |
| Estimated time | 3-15 s per round (depends on prompt size, provider, model) |
| Parallelizable? | No -- each round depends on the previous scene summary |
| Cacheable? | Yes -- identical prompts with identical scene state produce identical plans |
| GIL impact | None (blocked on network, not CPU) |

**Bottleneck detail:**
- `cli.py` runs up to **12 rounds** serially. Each round calls `create_plan()`,
  which makes a synchronous HTTP request. At 5 s/round, 12 rounds = **60 s**.
- The `_scene_prompt()` helper concatenates strings with `.strip()` on every
  invocation -- negligible cost.
- `_to_tool_call()` does a dict-per-action construction with
  `json.dumps(call.arguments, sort_keys=True)` for round-dedup signatures.
  This is cheap but creates throwaway JSON strings each round.

**Acceleration opportunities:**
1. **Streaming / early-exit:** If the LLM plan returns `COMPLETE`, we could
   detect it earlier rather than waiting for the full response body.
2. **Plan caching:** Hash `(provider, model, user_prompt, scene_summary,
   progress_summary)` and cache the compiled plan to disk. Replay-heavy
   development workflows would skip the LLM entirely.
3. **Batched tool application:** Within a single round, `cli.py` applies tool
   calls serially (line 56). Many IFC operations (slabs, columns, walls) are
   independent -- they could be applied in parallel via `ThreadPoolExecutor`.
4. **Reduce round count:** Provide a more detailed system prompt or use a
   larger context window so the planner can emit more actions per round,
   reducing the number of round-trips from 12 to 2-3.

---

### 2. IFC Authoring (`ifc_author.py` / `execution.py`)

**What it does:** Opens or creates an IFC4 file via IfcOpenShell, iterates over
plan actions, and for each action: creates an IFC entity, computes a 4x4
transform matrix, creates geometry representations, assigns spatial containment,
and writes property sets.

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **CPU** (IfcOpenShell entity creation, numpy matrix ops) |
| Estimated time | 0.5-3 s for a typical building (50-200 elements) |
| Parallelizable? | Partially -- element creation is independent, but the IFC model object is not thread-safe |
| Cacheable? | The whole IFC file can be cached by plan hash |
| GIL impact | Moderate -- numpy releases GIL for linalg, but IfcOpenShell is C++ with GIL held |

**Bottleneck detail:**

- **Redundant `_ensure_project_hierarchy()` calls:** Every single element
  creation method (`create_wall`, `create_column`, `create_beam`, etc.) calls
  `_ensure_project_hierarchy()` which does `self.model.by_type("IfcProject")`
  on every invocation. For 200 elements, that is 200 linear scans of the model
  entity list. This is the single most obvious CPU waste in the IFC stage.

- **Redundant `body_context` property lookups:** The `body_context` property
  iterates `self.model.by_type("IfcGeometricRepresentationSubContext")` on
  every access. Each element creation reads it once, so 200 elements = 200
  linear scans.

- **`_write_metadata` creates a new pset or scans existing psets for every
  element.** Each call does `getattr(product, "IsDefinedBy", [])` which walks
  the STEP entity graph.

- **`_normalize_metadata` calls `json.dumps()` for every dict/list value in
  the metadata.** For a typical element with 5-10 complex metadata fields, this
  creates small JSON strings that get embedded as IFC IfcPropertySingleValue
  strings.

- **Duplicate `np.eye(4)` allocation:** Every element creates a fresh 4x4
  identity matrix. Cost is trivial per-call but adds up across hundreds of
  elements.

- **`HeadlessIfcExecutor.execute_plan()` iterates actions serially** (line 48-49
  in execution.py), creating one IfcAuthor instance per plan execution. The
  `_apply_action` dispatcher re-parses action types via string comparison
  chains.

- **The IFC model is written TWICE in grouped sizing:** Once in the initial
  `IfcPhysicalModelBackend.materialize()` call and once more in
  `_write_roundtripped_physical_outputs()` at the end of sizing (line 364 of
  grouped_sizing.py). Each call to `HeadlessIfcExecutor.execute_plan()` creates
  a brand new `IfcAuthor`, re-parses the entire plan, and re-generates all
  geometry.

**Acceleration opportunities:**
1. **Cache `body_context` and project hierarchy check.** Store them as instance
   variables after first resolution. One-line fix, saves ~200 entity scans.
2. **Batch `_write_metadata` calls.** Accumulate all property sets and write
   them in a single pass at the end rather than per-element.
3. **Skip the second IFC write in grouped sizing** if the plan hasn't actually
   changed (check a plan-content hash).
4. **Use `model.by_type()` once and index by name** instead of
   `_find_by_name()` doing a linear scan each time.
5. **Pre-allocate a numpy matrix pool** or use a factory function that returns
   pre-rotated matrices.

---

### 3. Structural Source Extraction (`structural_source.py`)

**What it does:** Walks the compiled plan actions, creates `StructuralSourceElement`
objects with role classification, semantic enrichment from the semantic model,
and zone/system/assembly identity resolution.

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **CPU** (pure Python dict/string manipulation) |
| Estimated time | 50-200 ms for a typical plan |
| Parallelizable? | Yes -- each action is independent |
| Cacheable? | Yes -- deterministic from plan + semantic model |
| GIL impact | Full GIL contention (pure Python) |

**Bottleneck detail:**

- **`_semantic_meta()` is called multiple times per element.** Within a single
  `_beam_source()` call, the code calls: `_semantic_role_or()`,
  `_semantic_parent_id()`, `_semantic_assembly_id()`, `_semantic_system_id()`,
  `_semantic_interface_type()`, and `_semantic_metadata_fields()`. Each of
  these internally calls `_semantic_meta()` which calls `_semantic_record()`
  which does a dict lookup + defensive `isinstance` checks. For one element,
  `_semantic_meta()` is called **6+ times** with identical results.

- **String formatting overhead:** `_element_id()` (line 532 of
  analysis_exports.py) does character-by-character iteration and repeated
  `str.replace("__", "_")` in a while loop. This is O(n^2) in the worst case.

- **Duplicate material/section creation:** `_ensure_material()` and
  `_ensure_section()` are called for every element, each doing a
  `dict.setdefault()`. The MaterialSpec and SectionSpec objects are
  re-constructed on every call even when they already exist.

**Acceleration opportunities:**
1. **Memoize `_semantic_meta()` per action name.** One `@lru_cache` or a local
   variable would eliminate 5x redundant dict lookups per element.
2. **Pre-build the material/section catalog** before iterating elements.
   Construct each MaterialSpec once and just reference it.
3. **Replace the `_element_id()` while loop** with a single regex substitution:
   `re.sub(r'_+', '_', safe).strip('_')`.

---

### 4. Catalog Selection (`catalog_selector.py`)

**What it does:** Maps each structural element's `role` to a preferred catalog
family and section, using a static `ROLE_TO_SELECTION` lookup table.

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **CPU** (pure Python, trivial) |
| Estimated time | < 10 ms |
| Parallelizable? | Yes but unnecessary at this scale |
| Cacheable? | Yes |
| GIL impact | Negligible |

**Bottleneck detail:** Minimal. This is a single-pass loop over elements with
dict lookups. No significant overhead.

---

### 5. Catalog Resolution (`catalog_resolver.py`)

**What it does:** For each element that was successfully selected, resolves the
preferred section ID to a full `SectionSpec` with physical properties (area,
moment of inertia, weight per meter, etc.).

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **CPU** (dict lookups + section_library calls) |
| Estimated time | 10-50 ms |
| Parallelizable? | Yes but unnecessary at this scale |
| Cacheable? | Yes -- the section library is static |
| GIL impact | Low |

**Bottleneck detail:**
- `resolve_catalog_section()` is called per-element, each doing a library
  lookup. If the section library involves file I/O (reading CSV/JSON), this
  could be slower than expected.
- The function mutates `source_model.sections` and `source_model.materials`
  in-place, which is fine for single-threaded execution but blocks parallelism.

---

### 6. Analysis Model Generation (`analysis_exports.py`)

**What it does:** Builds the analytical model by:
1. Constructing the semantic model (if missing) via `bonsai_ai_core`
2. Building the `StructuralSourceModel`
3. Applying catalog selection and resolution
4. Running the `StructuralAnalysisReducer`
5. Emitting engineering models for each scope (up to 5)
6. Writing 10+ JSON files to disk
7. Building the FreeCAD handoff

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **CPU + Disk I/O** |
| Estimated time | 200 ms - 1 s |
| Parallelizable? | The 5 engineering scope emissions are independent |
| Cacheable? | Yes -- deterministic from physical model |
| GIL impact | Moderate (pure Python computation + JSON serialization) |

**Bottleneck detail:**

- **CRITICAL REDUNDANCY: The structural source model is built TWICE.**
  `AnalyticalModelBuilder.build()` (line 43) calls
  `StructuralSourceModelBuilder().build(package)` which walks the entire plan
  and creates all elements. Then in `JsonAnalysisExportBackend.export()` (line
  573), `builder.build(package)` is called, which internally calls
  `StructuralSourceModelBuilder().build(package)` AGAIN. The same plan is
  parsed twice, creating duplicate element objects.

- **CRITICAL REDUNDANCY: Catalog selection + resolution runs TWICE.**
  Inside `AnalyticalModelBuilder.build()`, the reducer path calls
  `build_load_path_model()` which depends on the source model. Then
  `export()` (lines 588-591) calls `apply_catalog_selection()`,
  `build_system_layout()`, `build_load_path_model()`, and
  `resolve_catalog_sections()` AGAIN on the same source model.

- **JSON serialization of large models:** `asdict(package.analytical_model)`
  (line 744) recursively converts all dataclass fields to dicts. For a model
  with 200+ elements, each with nested metadata dicts, this creates thousands
  of intermediate dict objects. Then `json.dumps(..., indent=2)` formats it.
  The same model is serialized multiple times (once here, once in the solver,
  once in the results bundle).

- **Engineering model emission is serial:** The loop at line 679-715 emits up
  to 5 engineering model scopes one at a time. Each calls `emitter.emit()`
  which filters and transforms the source model. These are independent and
  could run in parallel.

- **`_profile_summary()` iterates all elements** (line 849) for each profile.
  With multiple profiles, this is redundant work.

**Acceleration opportunities:**
1. **Build structural source model ONCE and reuse.** Store on `package` after
   first construction.
2. **Run catalog selection/resolution ONCE.** Currently runs inside
   `AnalyticalModelBuilder.build()` and again in `export()`.
3. **Parallelize engineering scope emission** with `ThreadPoolExecutor` or
   `multiprocessing.Pool`.
4. **Use `orjson` instead of `json`** for serialization. `orjson` is typically
   5-10x faster for large dicts and produces bytes directly, avoiding the
   string intermediate.
5. **Write JSON files asynchronously** using `aiofiles` or background threads
   -- there are 10+ file writes that could overlap with computation.

---

### 7. Grouped Member Sizing (`grouped_sizing.py`)

**What it does:** Iteratively sizes structural members by:
1. Deep-copying the entire source model
2. Resolving catalog sections with group overrides
3. Rebuilding the analytical model
4. Running the PyNite solver
5. Evaluating demand/capacity unity checks
6. If any group fails (unity > 1.0), advance to next candidate section
7. Repeat up to 8 iterations

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **CPU** (FEA solver dominates), **Disk I/O** (JSON writes per iteration) |
| Estimated time | 5-60 s (depends on model size and iteration count) |
| Parallelizable? | Iterations are sequential, but independent groups could be solved in parallel |
| Cacheable? | Intermediate results per (group_state, iteration) tuple |
| GIL impact | High -- PyNite solver and deepcopy are pure Python |

**Bottleneck detail:**

- **`deepcopy(package.structural_source_model)` on every iteration** (line 41).
  For a model with 200 elements, each with nested metadata dicts, deepcopy
  traverses thousands of objects. This is O(n) in model size and creates
  enormous garbage collection pressure.

- **`deepcopy(package)` on line 49** -- copies the ENTIRE design package
  including all artifacts, physical model, etc. just to create a
  `trial_package` for the solver. This is the most expensive deepcopy in the
  pipeline.

- **Analytical model is rebuilt from scratch every iteration** (line 47,
  `_build_analytical_model`). Each rebuild re-runs the StructuralAnalysisReducer,
  which re-processes all elements even though only the section assignments
  changed.

- **PyNite solver runs N+1 times:** N iterations in the loop, plus a final
  `self.solver_backend.analyze()` call on line 74 outside the loop. The final
  run often duplicates the last iteration's result if no groups advanced.

- **JSON file writes inside the iteration loop:** Each iteration writes to
  `.sizing_iterations/iter_XX/solver_result.json`. File I/O inside a tight
  loop adds latency.

- **The final `_write_roundtripped_physical_outputs()` re-executes the IFC
  author** (line 364), re-creating the entire IFC file from scratch. This is
  a full duplicate of the materialization stage.

- **Unity check evaluation is O(n*m)** where n = groups and m = elements,
  because `_evaluate_groups` builds `group_elements` by scanning ALL source
  model elements.

**Acceleration opportunities:**
1. **Replace `deepcopy` with copy-on-write or partial updates.** Only the
   section assignments change between iterations -- clone only the
   element.section_id and element.metadata fields, not the entire model.
2. **Incremental analytical model update.** Instead of rebuilding from scratch,
   update only the section properties that changed.
3. **Skip the final solver run** if no groups advanced in the last iteration
   (the result is identical to the last iteration).
4. **Pre-index group_elements once** rather than rebuilding the index in
   `_evaluate_groups` every iteration.
5. **Parallelize independent sizing groups.** Groups that don't share nodes
   could be analyzed independently.
6. **Buffer iteration artifacts in memory** and write to disk only at the end.

---

### 8. PyNite FEA Solver (`pynite_backend.py`)

**What it does:** Translates the analytical model into a PyNite FEModel3D,
adds materials, geometry (members + quad surfaces), supports, loads, and
load combinations, then runs `model.analyze_linear()`.

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **CPU** (matrix factorization in PyNite, pure Python) |
| Estimated time | 0.5-10 s per solve (depends on DOF count) |
| Parallelizable? | Load combinations are independent |
| Cacheable? | Yes -- identical model produces identical results |
| GIL impact | **SEVERE** -- PyNite is pure Python with numpy. GIL is held during Python loops; released only during numpy BLAS calls |

**Bottleneck detail:**

- **Model construction is O(n) with high constant factors.** Each element
  requires: `context.ensure_node()` (coordinate dict lookup), `add_section()`,
  `add_member()`. The `ensure_node` method rounds coordinates to 6 decimal
  places and does a tuple key lookup in `nodes_by_coord` -- efficient.

- **`_section_properties()` (line 487-505) is called for every element** to
  extract area, Iy, Iz, J. Each call does `dict.get()` chains with fallback
  calculations. The same section is looked up repeatedly for elements sharing
  a section.

- **Self-weight load application iterates ALL members** (line 321) when
  `target_id == "all"`, doing per-member section and material lookups.

- **`_build_summary()` iterates all nodes for all combinations** (line 386-394)
  to find max displacement. For N nodes and C combos, this is O(N*C) with
  Python-level getattr calls.

- **`_member_demands()` does per-member, per-combo extraction** (line 406-441).
  Each member call does 7 `max(abs(...))` computations via PyNite's
  internal envelope methods, which themselves iterate internal arrays.

- **No result caching.** If the solver is called with an identical model
  (e.g., final iteration == last iteration), it re-runs the full analysis.

**Acceleration opportunities:**
1. **Cache `_section_properties()` by section_id.** Many elements share
   sections. A dict lookup would eliminate redundant computation.
2. **Use sparse matrix solver.** PyNite's `analyze_linear()` uses scipy
   sparse, which is reasonable. However, for very large models, consider
   direct C-level solvers (MUMPS, CHOLMOD).
3. **Parallelize load combination analysis.** Each combo is independent.
   PyNite solves all combos sequentially.
4. **Skip redundant final solve** in grouped sizing.
5. **Pre-build section properties map** once before geometry construction.
6. **Vectorize `_build_summary()` and `_member_demands()`** using numpy
   arrays instead of Python loops over nodes.

---

### 9. Results Bundle (`results_bundle.py`)

**What it does:** Collects all pipeline artifacts, computes relative paths,
builds a summary JSON with entrypoints, element counts, and diagnostics.

| Dimension | Assessment |
|-----------|-----------|
| Bound by | **CPU** (Python object traversal) + **Disk I/O** (one JSON write) |
| Estimated time | < 50 ms |
| Parallelizable? | N/A |
| Cacheable? | No -- depends on all previous stages |
| GIL impact | Negligible |

**Bottleneck detail:**
- `_build_bundle()` calls `asdict(bundle)` (line 26) which recursively
  converts the entire ResultsBundle dataclass tree. For large bundles with
  many artifacts, this creates many intermediate dicts.
- `_entrypoint()` and `_entrypoint_by_role_and_scope()` iterate the artifact
  list multiple times (once per entrypoint type). With ~15 entrypoint lookups
  and ~30 artifacts, this is ~450 comparisons -- trivial.
- The `json.dumps(asdict(bundle), indent=2)` serialization is the main cost.

**Acceleration opportunities:**
1. Use `orjson` for JSON serialization.
2. Build a single artifact index dict up front instead of iterating per
   entrypoint.

---

### 10. Plan Execution (`execution.py`)

**What it does:** Bridges the compiled plan (dict of actions) to the
`IfcAuthor` by dispatching each action type to the corresponding author
method.

| Dimension | Assessment |
|-----------|-----------|
| Bound by | Same as IFC Authoring (CPU / IfcOpenShell) |
| Estimated time | 0.5-3 s |
| Parallelizable? | Same limitations as IFC Authoring |
| Cacheable? | Yes |
| GIL impact | Same as IFC Authoring |

**Bottleneck detail:**
- `_apply_action()` is a long if-elif chain (13 branches). A dict dispatch
  table would be marginally faster but the real cost is in the IfcAuthor
  methods themselves.
- `_metadata_fields()` builds a filtered dict from every action, calling
  `_semantic_group()`, `_presentation_group()`, and `_foundation_fields()`.
  Each iterates specific field lists with `action.get()`. For 200 elements,
  this is ~600 dict scans.
- `_reserved_fields()` returns a new set on every call. Should be a class
  constant.

**Acceleration opportunities:**
1. Make `_reserved_fields()` a class-level `frozenset` constant.
2. Use a dispatch dict instead of if-elif chain.
3. Pre-filter semantic/presentation/foundation fields once per plan.

---

## Cross-Cutting Bottleneck Summary

### 1. Redundant Computation (HIGHEST IMPACT)

| What gets recomputed | Where | How many times |
|---------------------|-------|---------------|
| StructuralSourceModel from plan | `AnalyticalModelBuilder.build()` + `export()` | 2x |
| Catalog selection + resolution | `export()` inner path + `grouped_sizing` loop | 2-10x |
| Analytical model construction | `export()` + each sizing iteration | 2-10x |
| IFC file authoring | `materialize()` + `_write_roundtripped_physical_outputs()` | 2x |
| `_ensure_project_hierarchy()` | Every element creation | 200x per IFC write |
| `body_context` property | Every element creation | 200x per IFC write |
| `_semantic_meta()` per element | Each source element builder | 6x per element |
| PyNite solver | Final iteration + final solve | 2x (often identical) |

**Estimated savings from eliminating redundant computation: 30-50% of total
pipeline time.**

### 2. Serial Bottlenecks That Could Be Parallelized

| Serial work | Parallelism opportunity | Expected speedup |
|------------|------------------------|-----------------|
| 12 planner rounds | Cannot parallelize (sequential dependency) | None |
| IFC element creation (200 elements) | Thread pool with per-element IfcAuthor (requires thread-safe IFC model) | 2-4x |
| 5 engineering scope emissions | ThreadPoolExecutor (pure Python, independent) | 3-5x |
| Sizing iteration solver runs | Cannot parallelize iterations; can parallelize per-combo within solver | 2x |
| 10+ JSON file writes | asyncio / thread pool | Minor (I/O is fast) |

### 3. Memory / GC Pressure

| Source | Impact |
|--------|--------|
| `deepcopy(package)` in grouped sizing | Creates a full clone of every object in the package. For a large model, this could be 10-50 MB of transient objects per iteration. |
| `deepcopy(source_model)` in grouped sizing | Creates element + metadata clones. 200 elements * 8 iterations = 1600 element objects created and discarded. |
| `asdict()` on dataclasses | Recursively converts nested dataclasses. Each call creates a fresh dict tree. Called 3+ times for the same model. |
| `json.dumps(..., indent=2)` | Creates large formatted strings. The analytical model JSON can be 500KB+. Written multiple times. |

### 4. Disk I/O

The pipeline writes **15-25 JSON files** during a typical run:
- `physical_model_plan.json`
- `physical_model_authored_plan.json`
- `physical_model_semantic_model.json`
- `semantic_model.json`
- `structural_source_model.json`
- `system_layout.json`
- `load_path_model.json`
- `catalog_selection_summary.json`
- `analytical_model.json`
- `solver_request.json`
- 5x `engineering_model.{scope}.json`
- `engineering_model_summary.json`
- `analysis_profile_summary.json`
- `freecad_handoff.json`
- `freecad_handoff.py`
- `solver_result.json`
- `results_bundle.json`
- `design_package.json`
- Plus per-iteration files during sizing

Each file involves `json.dumps(indent=2)` + `path.write_text()`. The total
I/O is likely 2-10 MB. On SSD, this is < 100 ms total, but on network
filesystems it could be significant.

### 5. Python-Specific Overhead

| Issue | Location | Impact |
|-------|----------|--------|
| GIL contention | PyNite solver, IfcOpenShell, deepcopy | Blocks true multicore parallelism |
| String formatting in loops | `_element_id()`, `f"column_{width:.4f}x{depth:.4f}"` | Minor per-call, accumulates over 200+ elements |
| `isinstance()` checks | `_normalize_metadata`, `_semantic_meta` | Python isinstance is fast but called thousands of times |
| `dict.get()` chains | Every metadata extraction path | 5-10 chained .get() calls per element per stage |
| `float()` wrapping | Every geometry parameter | Defensive float() on values that are already floats |

---

## Prioritized Optimization Recommendations

### Tier 1: Quick Wins (< 1 hour each, no architecture change)

1. **Cache `body_context` and `_ensure_project_hierarchy` result** in
   `IfcAuthor.__init__()`. Saves ~400 entity scans per IFC write.
   - File: `ifc_author.py`, lines 46-69
   - Fix: Add `self._body_context = None` / `self._hierarchy_ready = False`

2. **Make `_reserved_fields()` a class constant** in `execution.py`.
   - File: `execution.py`, line 276
   - Fix: `_RESERVED_FIELDS = frozenset({...})`

3. **Cache `_section_properties()` by section_id** in `pynite_backend.py`.
   - File: `pynite_backend.py`, line 487
   - Fix: Add a `_section_cache: Dict[str, Dict]` to `_BuildContext`

4. **Memoize `_semantic_meta()` per action** in `structural_source.py`.
   - File: `structural_source.py`
   - Fix: Compute once per element, pass as parameter to sub-methods

5. **Replace `_element_id()` while loop** with `re.sub(r'_+', '_', safe)`.
   - File: `analysis_exports.py`, line 532-536

### Tier 2: Moderate Effort (2-4 hours each)

6. **Eliminate double StructuralSourceModel build.** Have `export()` check if
   `package.structural_source_model` is already populated before rebuilding.
   - Files: `analysis_exports.py` lines 43-44 and 572-573

7. **Eliminate double catalog selection/resolution.** Run catalog operations
   once in `export()` and store results on the package.
   - File: `analysis_exports.py` lines 587-592

8. **Skip final PyNite solver run when no groups advanced** in
   `grouped_sizing.py`.
   - File: `grouped_sizing.py`, line 74
   - Fix: Track whether `_advance_failing_groups` returned True on last iteration

9. **Replace `deepcopy(package)` with a lightweight trial wrapper** that shares
   immutable data and only copies mutable fields.
   - File: `grouped_sizing.py`, line 49

10. **Skip second IFC write in grouped sizing** when plan hasn't changed.
    - File: `grouped_sizing.py`, line 364

### Tier 3: Significant Effort (1-2 days each)

11. **Switch JSON serialization to `orjson`** throughout the pipeline.
    - All files that call `json.dumps()`
    - Expected 5-10x faster serialization

12. **Parallelize engineering scope emission** with `concurrent.futures`.
    - File: `analysis_exports.py`, lines 679-715

13. **Incremental analytical model update** in sizing iterations.
    - File: `grouped_sizing.py`, `_build_analytical_model()`
    - Only update section properties, not rebuild the entire model

14. **Batch IFC property set writes** -- accumulate metadata and write all
    psets in a single pass before `author.save()`.
    - File: `ifc_author.py`

### Tier 4: Architectural Changes (multi-day)

15. **Async pipeline orchestration** -- use `asyncio` for the pipeline stages
    that are I/O-bound (planner, file writes) and `multiprocessing` for
    CPU-bound stages (solver).

16. **Persistent model cache** -- hash-based caching of intermediate artifacts
    (structural source model, analytical model, solver results) to skip
    redundant computation across pipeline runs.

17. **Replace PyNite with a C-level FEA solver** (e.g., direct scipy sparse
    solve, or a binding to MUMPS/CHOLMOD) for 10-100x speedup on large models.

18. **IfcOpenShell batch API** -- investigate whether IfcOpenShell supports
    bulk entity creation to avoid per-element API overhead.

---

## Estimated Time Budget (typical 200-element building)

| Stage | Current (est.) | After Tier 1-2 (est.) |
|-------|---------------|----------------------|
| Planner (3 rounds) | 15 s | 15 s (network-bound) |
| IFC Authoring | 2 s | 1 s |
| Structural Source | 0.2 s | 0.1 s |
| Catalog Selection + Resolution | 0.1 s | 0.05 s |
| Analysis Export (incl. eng models) | 1 s | 0.4 s |
| Grouped Sizing (4 iterations) | 20 s | 8 s |
| PyNite Solver (per run) | 3 s | 3 s (CPU-bound) |
| Results Bundle | 0.05 s | 0.03 s |
| JSON File I/O (20 files) | 0.1 s | 0.1 s |
| **Total** | **~41 s** | **~28 s (32% faster)** |

With Tier 3-4 optimizations (orjson, parallel scopes, C solver), the pipeline
could reach **~10-15 s** for the same workload, a **60-70% reduction**.

---

## Files Referenced

| File | Key concern |
|------|------------|
| `src/bonsai_ai/pipeline.py` | Serial stage orchestration |
| `src/bonsai_ai/cli.py` | 12-round serial planner loop |
| `src/bonsai_ai/planner.py` | Network-bound LLM calls |
| `src/bonsai_ai/ifc_author.py` | Redundant hierarchy/context lookups per element |
| `src/bonsai_ai/execution.py` | Serial action dispatch, mutable set creation |
| `src/bonsai_ai/structural_source.py` | 6x redundant `_semantic_meta()` per element |
| `src/bonsai_ai/catalog_selector.py` | Clean, minimal overhead |
| `src/bonsai_ai/catalog_resolver.py` | Clean, runs twice unnecessarily |
| `src/bonsai_ai/analysis_exports.py` | Double source model build, double catalog ops, serial eng scope emission |
| `src/bonsai_ai/grouped_sizing.py` | deepcopy overhead, N+1 solver runs, duplicate IFC write |
| `src/bonsai_ai/pynite_backend.py` | Uncached section properties, Python-loop summary extraction |
| `src/bonsai_ai/results_bundle.py` | Multiple artifact list iterations, asdict overhead |
