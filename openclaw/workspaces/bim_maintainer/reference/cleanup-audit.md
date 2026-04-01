# Codebase Cleanup Audit

**Date:** 2026-03-30
**Scope:** Dead code, unused files, .gitignore gaps, reference doc cruft

---

## 1. Dead Code: `tool_registry.py`

**Status:** DEAD -- safe to delete

`tool_registry.py` and `tool_specs.py` were built for the phased planner
(`openclaw_planner.py`) which has been deleted. The only import of
`tool_registry` from production code is its own docstring example (line 9 of
`tool_registry.py` itself). No module in `src/bonsai_ai/` imports it. The
iterative planner (`iterative_planner.py`), planner (`planner.py`), and CLI
(`cli.py`) all bypass it entirely.

`tool_specs.py` IS still imported by `tool_registry.py` only. However,
`tool_specs.py` also imports from `bonsai_ai_core.action_catalog`, so it has a
live dependency chain. Check whether anything else uses `tool_specs.py` directly
-- only `test_tool_specs.py` in tests.

| File | Action | Effort |
|------|--------|--------|
| `src/bonsai_ai/tool_registry.py` | Delete | Trivial |
| `src/bonsai_ai/tool_specs.py` | Delete (only consumer was tool_registry + 1 test) | Trivial |
| `tests/test_tool_registry.py` | Delete | Trivial |
| `tests/test_tool_specs.py` | Delete | Trivial |

---

## 2. Dead Code: Mojo Modules

**Status:** DEAD WEIGHT -- committed to git, not referenced by any production code

The `mojo_modules/` directory contains 7 tracked files (+ compiled `.so` which
is gitignored). Grep of `src/` and `tests/` for `mojo_modules`, `bonsai_fea`,
and `bonsai_tessellate` returns zero hits. These modules were built during a
performance exploration session (2026-03-30) but the architecture decision
(documented in `path-a-python-optimize.md`, `path-b-mojo-rust-hybrid.md`) was to
stay Python-first and drop Mojo.

The benchmarks showed Mojo was SLOWER than NumPy for medium-to-large problems
due to per-element interop overhead (0.24x-0.53x of NumPy speed). A vectorized
NumPy approach was implemented instead.

| File | Action | Effort |
|------|--------|--------|
| `mojo_modules/bonsai_fea.mojo` | Delete from git | Trivial |
| `mojo_modules/bonsai_tessellate.mojo` | Delete from git | Trivial |
| `mojo_modules/bonsai_fea_fast.py` | Delete from git | Trivial |
| `mojo_modules/benchmark_fea.py` | Delete from git | Trivial |
| `mojo_modules/benchmark_tessellate.py` | Delete from git | Trivial |
| `mojo_modules/test_fea.py` | Delete from git | Trivial |
| `mojo_modules/test_tessellate.py` | Delete from git | Trivial |

**Alternative:** If you want to preserve the research for reference, move
the directory out of git and into an archive or keep only the benchmark
results in a reference doc. The `.mojo` source files and Python wrappers
have no consumers.

---

## 3. Committed Build Cache: `.vite/deps/`

**Status:** SHOULD NOT BE IN GIT -- 24 files tracked

The `.vite/deps/` directory contains Vite dependency pre-bundle cache files
(`.js`, `.js.map`, `_metadata.json`, `package.json`). These are generated
artifacts that should never be committed. They are 100% reproducible by
running `npm install && npm run dev` in the viewer directory.

| Item | Action | Effort |
|------|--------|--------|
| `.vite/` in `.gitignore` | Add `.vite/` line | Trivial |
| Remove from git tracking | `git rm -r --cached .vite/` | Trivial |

---

## 4. Test File Audit

### Tests that import from live modules -- KEEP

All test imports resolve successfully. Specifically:

- `test_generators.py` imports `bonsai_ai_core.compiler` -- OK, module exists
- `test_schema.py` imports `bonsai_ai_core.schema` -- OK, module exists
- `test_schemas.py` imports `bonsai_ai_bridge.schemas` -- OK, module exists

### Tests for dead modules -- DELETE

- `test_tool_registry.py` -- imports from `bonsai_ai.tool_registry` which is dead code (see finding 1)
- `test_tool_specs.py` -- imports from `bonsai_ai.tool_specs` which is dead code (see finding 1)

### Potential duplication: `test_schema.py` vs `test_schemas.py`

These are NOT duplicates. They test different things:
- `test_schema.py` tests `bonsai_ai_core.schema.validate_plan` (the core plan validation, dict-based)
- `test_schemas.py` tests `bonsai_ai_bridge.schemas` (the bridge Pydantic models: `BuildingPlan`, `parse_plan_text`, `validate_plan`)

Both should be kept.

| File | Action | Effort |
|------|--------|--------|
| `tests/test_tool_registry.py` | Delete | Trivial |
| `tests/test_tool_specs.py` | Delete | Trivial |

---

## 5. `.gitignore` Completeness

**Current gaps:**

| Pattern | Why it should be added |
|---------|----------------------|
| `.vite/` | Vite dep cache is committed (24 files). See finding 3. |
| `out/tests/` | Test output artifacts exist on disk but are not gitignored. Currently `out/` is already in .gitignore, so `out/tests/` IS covered. No action needed. |

The existing `.gitignore` already covers:
- `out/` (covers `out/tests/`)
- `mojo_modules/*.so` and `mojo_modules/__pycache__/`
- `dist/`, `build/`, `.venv*/`, `node_modules/`, etc.

| Item | Action | Effort |
|------|--------|--------|
| Add `.vite/` to `.gitignore` | One line | Trivial |

---

## 6. `blender_addon.py` in `src/bonsai_ai/`

**Status:** LEGACY DEAD CODE -- not imported by anything

`src/bonsai_ai/blender_addon.py` is a standalone Blender panel implementation
that imports from `bonsai_ai.ifc_author` and `bonsai_ai.planner`. It is NOT
imported by any other module in the codebase. The maintained Blender UI now
lives in the separate `bonsai_ai_blender/` package (confirmed by the comment in
`__init__.py`: "The maintained Blender UI now lives in the `bonsai_ai_blender`
package").

The `scripts/package_addon.py` script packages the `bonsai_ai_blender/`
directory, not this file.

| File | Action | Effort |
|------|--------|--------|
| `src/bonsai_ai/blender_addon.py` | Delete | Trivial |

---

## 7. Reference Doc Redundancy

The `reference/` directory contains 30 documents totaling ~600KB. Several
document groups cover overlapping territory from different angles or time points.

### Group A: Performance & Compute (5 docs, heavy overlap)

| Document | Size | Content |
|----------|------|---------|
| `performance-benchmarks.md` | 3KB | Raw benchmark numbers (Mojo vs NumPy vs vectorized) |
| `mojo-fea-optimization.md` | 8KB | Mojo FEA research -- conclusion: Mojo is slower, use vectorized NumPy |
| `compute-scaling-analysis.md` | 26KB | How bottlenecks shift as models grow |
| `pipeline-performance-analysis.md` | 17KB | Deep pipeline stage timing analysis |
| `process-speed-improvements.md` | 17KB | Process speed improvement recommendations |

`performance-benchmarks.md` is a strict subset of `mojo-fea-optimization.md`
(same tables, less context). `pipeline-performance-analysis.md` and
`process-speed-improvements.md` overlap significantly -- both analyze the same
pipeline stages and propose similar optimizations.

**Recommendation:** Consolidate into 2 docs: one for FEA/compute benchmarks and
one for pipeline performance. Delete `performance-benchmarks.md` (subsumed).

| Action | Effort |
|--------|--------|
| Delete `performance-benchmarks.md` | Trivial |
| Merge `process-speed-improvements.md` into `pipeline-performance-analysis.md` | Easy |

### Group B: Architecture Decision (3 docs about Mojo/Rust, now decided)

| Document | Size | Content |
|----------|------|---------|
| `path-a-python-optimize.md` | 30KB | Stay Python -- RECOMMENDED |
| `path-b-mojo-rust-hybrid.md` | 19KB | Mojo+Rust hybrid -- REJECTED |
| `path-c-rust-migration.md` | 19KB | Full Rust migration -- REJECTED |

The decision has been made (Python-first). The rejected paths are historical
artifacts. They are well-written evaluations but no longer actionable.

**Recommendation:** Keep `path-a-python-optimize.md` (the chosen path). Archive
or delete paths B and C. If you want to preserve the reasoning, consolidate
the rejection rationale into a paragraph in path-a.

| Action | Effort |
|--------|--------|
| Delete `path-b-mojo-rust-hybrid.md` | Trivial |
| Delete `path-c-rust-migration.md` | Trivial |

### Group C: Planner Architecture (5 docs, heavy overlap)

| Document | Content |
|----------|---------|
| `planner-refactor-options.md` | Refactor options for openclaw_planner.py (now deleted) |
| `openclaw-integration-options.md` | How to use OpenClaw auth without overhead |
| `harness-audit.md` | 67-property god-object diagnosis |
| `simple-tool-interface.md` | Redesign tool schema to fix god-object |
| `simplification-research.md` | Extended research on tool simplification |

`planner-refactor-options.md` references `openclaw_planner.py` which no longer
exists. Its content is partially superseded by the iterative planner
implementation. `simple-tool-interface.md` and `simplification-research.md`
cover the same topic at different depths -- the research doc subsumes the
design doc.

**Recommendation:**
| Action | Effort |
|--------|--------|
| Delete `planner-refactor-options.md` (references deleted code) | Trivial |
| Merge `simple-tool-interface.md` into `simplification-research.md` | Easy |

### Group D: Quality Diagnosis (3 docs, partial overlap)

| Document | Content |
|----------|---------|
| `building-quality-diagnosis.md` | Five-story mezzanine quality analysis |
| `quality-audit-comparison.md` | Iterative build comparison (2 builds) |
| `direct-vs-phased-comparison.md` | Direct vs phased planner quality |

These overlap in diagnosing the same spatial misalignment issues (slab offset,
column grid gaps). However, each analyzes different builds, so they have
distinct value. Keep all three but add cross-references.

| Action | Effort |
|--------|--------|
| Add cross-references between the 3 docs | Trivial |

### Group E: Design Proposals (superseded)

| Document | Status |
|----------|--------|
| `agent-as-operator.md` | Proposal from before iterative planner was built. Partially implemented. |
| `iterative-session-design.md` | Design doc for the iterative session -- now implemented. |
| `feedback-loop-design.md` | Predict-execute-compare loop -- not yet implemented. |

`iterative-session-design.md` is now a historical design doc (the feature was
built). It can be kept for context but should be marked as IMPLEMENTED.

| Action | Effort |
|--------|--------|
| Mark `iterative-session-design.md` header as IMPLEMENTED | Trivial |
| Mark `agent-as-operator.md` header as PARTIALLY IMPLEMENTED | Trivial |

---

## 8. Orphaned Imports Check

All four key modules import successfully:
- `bonsai_ai.cli`: OK
- `bonsai_ai.planner`: OK
- `bonsai_ai.iterative_planner`: OK
- `bonsai_ai.ifc_author`: OK

No orphaned imports detected in the main execution paths.

---

## Summary: Prioritized Action List

### Immediate (trivial, no risk)

1. Add `.vite/` to `.gitignore` and run `git rm -r --cached .vite/`
2. Delete `src/bonsai_ai/tool_registry.py`
3. Delete `src/bonsai_ai/tool_specs.py`
4. Delete `tests/test_tool_registry.py`
5. Delete `tests/test_tool_specs.py`
6. Delete `src/bonsai_ai/blender_addon.py`
7. Delete `reference/performance-benchmarks.md` (subsumed by mojo-fea-optimization.md)
8. Delete `reference/planner-refactor-options.md` (references deleted openclaw_planner.py)

### Soon (trivial-easy, low risk)

9. Remove `mojo_modules/` from git (`git rm -r mojo_modules/` + add to .gitignore)
10. Delete `reference/path-b-mojo-rust-hybrid.md` and `reference/path-c-rust-migration.md`
11. Merge `reference/simple-tool-interface.md` into `reference/simplification-research.md`
12. Merge `reference/process-speed-improvements.md` into `reference/pipeline-performance-analysis.md`
13. Mark `reference/iterative-session-design.md` and `reference/agent-as-operator.md` with implementation status

### Optional (cleanup, no urgency)

14. Add cross-references between the 3 quality diagnosis docs
15. Archive the Mojo benchmark data (keep the conclusions, remove the source files)
