# Option C Deep Cutover Tracker

Last updated: 2026-03-30

## Goal

Build the deep Option C architecture around one editable semantic building model that can drive:

- authored physical BIM / IFC
- structural source and solver preparation
- styled Blender review hierarchy
- AI edit/rebuild commands

## Current Status

### Completed

- canonical action/schema contract cleanup in `bonsai_ai_core`
- semantic edit verbs aligned across schema, planner shims, and compiler
- persistent Blender review presentation, nested tree organization, role isolate, selection inspect, and section box tools
- semantic model generation from authored plans
- first solver-to-authoring round-trip for sized sections back into the plan
- semantic model artifacts now emitted in physical/export flows

### In Progress

- semantic building/assembly model as the actual shared source of truth, not just a derived artifact
- exposing semantic model artifacts consistently across package/export/results flows
- doc-level tracking of the deep cutover and file ownership

### Next

1. make the semantic model richer for assembly ownership and branch-level rebuilds
2. move structural source, review tree, and future IFC rebuilds to consume the same assembly graph
3. round-trip solved steel and footing results back into authored geometry more completely
4. add selection-aware AI editing against semantic IDs/branches inside Blender
5. add QA checks for unsized members, orphan branches, and missing semantics

## Milestones

### M1. Contract Unification

Status: done

Files:

- `bonsai_ai_core/action_catalog.py`
- `bonsai_ai_core/schema.py`
- `src/bonsai_ai/tool_specs.py`
- `src/bonsai_ai/planner.py`
- `src/bonsai_ai/__init__.py`

### M2. Semantic Edit Pipeline

Status: done

Files:

- `bonsai_ai_core/compiler.py`
- `bonsai_ai_core/semantic_model.py`
- `tests/test_compiler.py`
- `tests/test_schema.py`
- `tests/test_semantic_model.py`

### M3. Review Hierarchy And Presentation

Status: done

Files:

- `bonsai_ai_blender/presentation.py`
- `bonsai_ai_blender/ui.py`
- `bonsai_ai_blender/client.py`
- `scripts/blender_import_ifc_to_blend.py`
- `scripts/blender_render_architectural_concept.py`

### M4. Semantic Model As Shared Artifact

Status: in progress

Done:

- semantic model is generated from authored plans
- planner backends attach semantic model to `PhysicalModelSpec`
- physical execution persists semantic model JSON
- analysis export emits `semantic_model.json`

Open:

- structural source still derives directly from primitive actions instead of semantic assemblies
- Blender presentation still builds its hierarchy from IFC metadata rather than the semantic model artifact
- IFC rebuild still executes compiled primitives rather than semantic assemblies

Files:

- `bonsai_ai_core/semantic_model.py`
- `src/bonsai_ai/planner_backends.py`
- `src/bonsai_ai/execution.py`
- `src/bonsai_ai/analysis_exports.py`
- `src/bonsai_ai/results_bundle.py`
- `src/bonsai_ai_bridge/orchestrator.py`

### M5. Solver Round-Trip

Status: in progress

Done:

- selected section sizes can write back into the authored plan

Open:

- writeback is still dimension/section metadata only
- no profiled W/HSS geometry rebuild yet
- no footing geometry regeneration from solved reactions yet

Files:

- `src/bonsai_ai/plan_roundtrip.py`
- `src/bonsai_ai/grouped_sizing.py`
- `src/bonsai_ai/catalog_resolver.py`
- `src/bonsai_ai/section_library.py`

### M6. Selection-Aware AI Editing

Status: partially done

Done:

- isolate selected branch
- inspect selected semantic metadata
- section box cutaway

Open:

- no direct “edit selected branch” prompt flow yet
- no branch diff/rebuild UI

Files:

- `bonsai_ai_blender/presentation.py`
- `bonsai_ai_blender/ui.py`

## Risks

- There are still multiple “truths” in the system: compiled plan, semantic model, IFC metadata, structural source model, and Blender review tree.
- Steel sizing round-trip currently updates rectangular approximations, not true catalog-profile geometry.
- Footing engineering is still starter-level and not yet a full solved-to-geometry feedback loop.
- Some legacy bridge/direct paths still coexist; they need continued consolidation to avoid feature drift.

## Recommended Implementation Order

1. enrich the semantic model into a real assembly graph with explicit parent/child ownership and branch metadata
2. build structural source from semantic assemblies instead of direct primitive heuristics
3. teach IFC/review rebuild paths to consume semantic assemblies
4. deepen round-trip into profiled steel and footing regeneration
5. wire Blender selection directly into semantic edit commands

## Verification Baseline

Recent passing checks after the current cutover work:

- `PYTHONPATH=src:. python3 -m unittest tests.test_tool_specs tests.test_schema tests.test_compiler tests.test_execution tests.test_ifc_author tests.test_structural_source tests.test_analysis_exports tests.test_footing_selector tests.test_pynite_backend tests.test_plan_roundtrip`
- `PYTHONPYCACHEPREFIX=/tmp/bonsai_ai_pyc python3 -m py_compile bonsai_ai_core/action_catalog.py bonsai_ai_core/schema.py bonsai_ai_core/compiler.py src/bonsai_ai/plan_roundtrip.py src/bonsai_ai/grouped_sizing.py bonsai_ai_blender/ui.py bonsai_ai_blender/presentation.py`
