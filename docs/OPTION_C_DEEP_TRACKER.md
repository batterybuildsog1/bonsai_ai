# Option C Deep Tracker

## Goal

Complete the deep cutover so Bonsai can generate a new building from AI, keep a clean nested semantic hierarchy, drive engineering and solver workflows from the same source-of-truth structure, and round-trip reviewed/sized results back into a styled, explorable model.

## Scope

In scope:

- canonical action/schema/planner contract
- semantic edit verbs and branch rebuild
- semantic building/assembly model
- clean nested hierarchy for review and engineering
- styled review model with glass, steel, concrete, and studio lighting
- selection, branch isolate, and section/cutaway review tools
- solver-to-authored-plan round-trip for structural sizing
- clearer footing metadata and basis reporting

Out of scope for this track:

- native railing rewrite
- street/car/context placement layer
- long-term preservation of legacy test-only paths

## Status

Completed:

- Canonical planner/schema/action contract centered in `bonsai_ai_core`
- Legacy planner/tool surfaces reduced to shims
- Semantic edit verbs wired through validation and compilation
- Persistent styled Blender review model with nested review hierarchy
- Role isolate, selected-branch isolate, selection inspect, and section box tools in Blender
- Starter footing metadata and execution support
- First solver-to-authored-plan round-trip for sized member sections

In progress:

- Semantic building/assembly model as a first-class source-of-truth artifact
- Pipeline tracking/docs so progress stays tied to the deep plan

Next:

1. Expand the semantic model from element list to nested assembly tree and publish it as a pipeline artifact.
2. Start consuming semantic-model assembly data in structural/engineering stages instead of re-deriving as much from names.
3. Regenerate physical/review output from sized plan data so visible steel dimensions track chosen sections more closely.
4. Deepen footing engineering checks and authored footing reporting.
5. Add selection-aware AI edit loops in Blender using semantic IDs and branch paths.

## Milestones

### M1. Contract Cutover

Status: done

Key files:

- [bonsai_ai_core/action_catalog.py](/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_core/action_catalog.py)
- [bonsai_ai_core/schema.py](/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_core/schema.py)
- [bonsai_ai_core/compiler.py](/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_core/compiler.py)
- [src/bonsai_ai/tool_specs.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/tool_specs.py)
- [src/bonsai_ai/planner.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/planner.py)

Outcome:

- one canonical action language
- semantic edit actions supported in the core contract
- old surfaces kept only as compatibility wrappers

### M2. Review Model

Status: done

Key files:

- [bonsai_ai_blender/presentation.py](/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_blender/presentation.py)
- [bonsai_ai_blender/ui.py](/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_blender/ui.py)
- [bonsai_ai_blender/client.py](/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_blender/client.py)
- [scripts/blender_import_ifc_to_blend.py](/Users/alanknudson/Applications/Bonsai_ai/scripts/blender_import_ifc_to_blend.py)

Outcome:

- persistent styled blend output
- nested review collections
- studio lighting
- glass/steel/concrete styling
- selection inspection and section tools

### M3. Semantic Source Of Truth

Status: in progress

Key files:

- [bonsai_ai_core/semantic_model.py](/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_core/semantic_model.py)
- [src/bonsai_ai/planner_backends.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/planner_backends.py)
- [src/bonsai_ai/execution.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/execution.py)

Current state:

- semantic model already exists for normalized elements and edit application
- nested assemblies and roots now exist in the semantic model artifact
- semantic model is emitted as a first-class pipeline artifact
- structural source has started consuming semantic-model records when explicit semantic IDs are present

Exit criteria:

- semantic model contains nested assembly nodes
- semantic model is emitted as an artifact in the pipeline
- downstream stages can reference it without rebuilding hierarchy from names alone

### M4. Engineering Alignment

Status: in progress

Key files:

- [src/bonsai_ai/structural_source.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/structural_source.py)
- [src/bonsai_ai/analysis_exports.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/analysis_exports.py)
- [src/bonsai_ai/grouped_sizing.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/grouped_sizing.py)
- [src/bonsai_ai/plan_roundtrip.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/plan_roundtrip.py)

Current state:

- structural source already understands semantic IDs/roles better than earlier architecture notes implied
- grouped sizing now writes resolved section IDs and dimensions back to the compiled plan, authored plan, and semantic model
- structural source elements now carry semantic branch and assembly lineage metadata from the semantic model
- footing basis metadata now round-trips back into authored footing actions as part of the same sizing/engineering handoff
- grouped sizing now emits a regenerated sized plan package and a sized IFC for review

Exit criteria:

- engineering stages consume semantic assembly relationships directly
- sized member selections regenerate the physical/review model more faithfully

### M5. Footings And Foundations

Status: partial

Key files:

- [src/bonsai_ai/ifc_author.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/ifc_author.py)
- [src/bonsai_ai/execution.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/execution.py)
- [src/bonsai_ai/footing_selector.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/footing_selector.py)

Current state:

- footing geometry and metadata exist
- rebar weights/strength metadata can be carried through
- detailed footing engineering checks are still limited

Exit criteria:

- governing load basis is explicit
- rebar/concrete assumptions are surfaced clearly
- next-stage footing checks extend beyond starter sizing

## Current Risks

- The semantic model exists, but downstream consumers still partly reconstruct hierarchy independently.
- Steel is still visually approximate even when section choices are known.
- The architecture doc predates some implemented progress and must not be treated as a literal snapshot of the current codebase.

## Validation Habit

Use these after each milestone slice:

- `PYTHONPATH=src:. python3 -m unittest tests.test_tool_specs tests.test_schema tests.test_compiler tests.test_execution tests.test_ifc_author tests.test_structural_source tests.test_analysis_exports tests.test_footing_selector tests.test_pynite_backend tests.test_plan_roundtrip tests.test_semantic_model`
- `PYTHONPYCACHEPREFIX=/tmp/bonsai_ai_pyc python3 -m py_compile bonsai_ai_core/*.py src/bonsai_ai/*.py bonsai_ai_blender/*.py`
