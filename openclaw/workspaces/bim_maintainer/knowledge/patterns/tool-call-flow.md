# Pattern: Tool Call Flow

## Summary
The full lifecycle from user prompt to IFC file follows a multi-stage pipeline: prompt -> plan -> compile -> semantic model -> execute -> structural analysis -> IFC output.

## The Two Paths

### Path 1: Legacy CLI (cli.py)
```
User Prompt
    |
    v
planner.py: create_plan()
    |-- bonsai_ai_core.build_plan()      [LLM call]
    |-- bonsai_ai_core.compile_plan()    [semantic -> buildable]
    |-- _to_tool_call()                   [compiled action -> PlannedToolCall]
    v
PlannedToolCall[] (name + arguments)
    |
    v
ifc_author.py: apply_tool_call()
    |-- ensure_storey(), create_wall(), etc.
    v
IFC file (via IfcOpenShell)
```
This path loops up to 12 rounds, feeding back scene_summary + progress_summary for replanning.

### Path 2: Design Pipeline (design_pipeline_cli.py)
```
User Prompt + DesignBrief
    |
    v
CorePhysicalPlannerBackend.build_physical_model()
    |-- bonsai_ai_core.build_plan()       [LLM call]
    |-- bonsai_ai_core.build_semantic_model()
    |-- bonsai_ai_core.compile_plan()
    v
PhysicalModelSpec (plan + semantic_model + metadata)
    |
    v
IfcPhysicalModelBackend.materialize()
    |-- HeadlessIfcExecutor.execute_plan()
    |   |-- For each action: IfcAuthor.create_*()
    v
IFC file + plan JSON + semantic model JSON
    |
    v
JsonAnalysisExportBackend.export()
    |-- StructuralSourceModelBuilder.build()
    |-- build_system_layout()
    |-- build_load_path_model()
    |-- apply_catalog_selection()
    |-- resolve_catalog_sections()
    |-- StructuralAnalysisReducer.reduce()
    |-- StructuralEngineeringModelEmitter.emit() [per scope]
    |-- FreeCADHandoffExporter.export()
    v
8+ JSON artifacts
    |
    v
PyNiteSolverBackend.analyze() [optional]
    |-- Build FEModel3D geometry, supports, loads
    |-- analyze_linear()
    v
solver_result.json
    |
    v
GroupedSectionSizer.size() [optional, iterative]
    |-- Loop: resolve sections -> analyze -> evaluate -> advance
    v
Sized sections + updated plan
    |
    v
JsonResultsBundleBackend.build()
    v
results_bundle.json (master entry point)
```

## Action type lifecycle

1. **Authored actions** (18 types): What the LLM produces. Includes semantic types (stair_run, connection_plate) and edit types (update, delete, move, replace_section, rebuild_branch).
2. **Compiled actions** (10 types): After `compile_plan()` removes semantic/edit actions. Only buildable primitives remain.
3. **Tool calls**: Compiled actions mapped to IfcAuthor method signatures with normalized field names.
4. **IFC elements**: Native IfcOpenShell entities with Pset_BonsaiAI metadata.
5. **Structural source elements**: Extracted from compiled plan with role/family/system/zone classification.
6. **Analytical elements**: Filtered by analysis profile, with section properties from catalog resolution.

## Data flow through contracts

```
DesignBrief
    -> PhysicalModelSpec (plan + semantic_model)
    -> DesignPackage.physical_artifacts (IFC + plan JSONs)
    -> StructuralSourceModel (elements with roles/families)
    -> AnalyticalModel (elements + loads + supports)
    -> EngineeringModel[] (scoped subsets)
    -> AnalysisResult (demands + unity checks)
    -> ResultsBundle (entrypoints to all artifacts)
```

## Last Reviewed
2026-03-31
