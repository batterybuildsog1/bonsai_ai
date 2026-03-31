# Execution

## Purpose
Translates compiled action plans into IFC files by dispatching actions to `IfcAuthor`, and defines the protocol-based pipeline architecture.

## How It Works

### execution.py (478 lines)
**`HeadlessIfcExecutor`** -- the core execution engine:
- Constructor: `default_storey_name="Level 0"`, `overwrite_existing=True`.
- `execute_plan(plan, output_path)`:
  1. Optionally deletes existing file.
  2. Creates an `IfcAuthor` instance.
  3. Iterates over `plan["actions"]`, calling `_apply_action()` for each.
  4. Saves the IFC, returns an `ExecutionReport`.
- `_apply_action(author, action)` dispatches by `action["type"]`:
  - `ensure_storey`, `create_rect_slab`, `create_wall`, `create_column`, `create_beam`, `create_panel`, `create_window`, `create_door`, `create_curtain_wall`, `create_footing`.
  - Each handler normalizes field names (e.g., `z` vs `base_z`, `x1/y1/x2/y2` vs start/end), calls `_ensure_storey()` for auto-creation, and passes `**_metadata_fields(action)` for semantic/presentation/foundation metadata.
  - Beam handling has special logic for both endpoint-based (`x1/y1/x2/y2`) and rotation-based (`rotation_deg` + `height` as span) input formats.
  - Curtain wall handling supports both endpoint-based and origin+width formats.
- `_metadata_fields()` extracts metadata by excluding reserved geometry fields, then merges `semantics`, `presentation`, and `foundation` groups including legacy field aliases.
- `_reserved_fields()` returns 34 field names to exclude from metadata passthrough.
- `_semantic_group()`, `_presentation_group()`, `_foundation_fields()` each merge nested objects with legacy flat fields.

**`IfcPhysicalModelBackend`** -- implements `PhysicalModelBackend` protocol:
- `materialize(package, output_dir)`:
  1. Writes the compiled plan JSON, authored plan JSON, and semantic model JSON.
  2. Calls `executor.execute_plan()` to create the IFC.
  3. Stores execution report in `package.physical_model.metadata`.
  4. Returns artifacts list (BIM_PLAN, PHYSICAL_IFC, and optional authored plan and semantic model).

**Data classes:**
- `ExecutionItem(action_type, element_name, ifc_class, global_id, metadata)`
- `ExecutionReport(output_path, created, messages, debug_dump, items)`

### pipeline.py (80 lines)
Defines the **protocol interfaces** and **pipeline orchestrator**:
- `PlannerBackend` protocol: `build_physical_model(brief) -> PhysicalModelSpec`
- `PhysicalModelBackend` protocol: `materialize(package, output_dir) -> List[PipelineArtifact]`
- `AnalysisExportBackend` protocol: `export(package, output_dir) -> List[PipelineArtifact]`
- `ResultsBundleBackend` protocol: `build(package, output_dir) -> List[PipelineArtifact]`
- `SolverBackend` protocol: `analyze(request, package, output_dir) -> AnalysisResult`

**`DesignPipeline`** dataclass orchestrates the full flow:
1. `planner.build_physical_model(brief)` -> sets `package.physical_model`
2. `physical_backend.materialize(package, target_dir)` -> sets `package.physical_artifacts`
3. `analysis_exporter.export(package, target_dir)` -> sets `package.analysis_artifacts`
4. `solver.analyze(request, package, target_dir)` -> sets `package.analysis_result`
5. `results_backend.build(package, target_dir)` -> sets `package.results_artifacts`
6. `write_manifest(package, target_dir / "design_package.json")` -- serializes to JSON.

## Current State
Fully implemented. The protocol-based design allows clean substitution of backends.

## Known Issues
- `HeadlessIfcExecutor._apply_action()` raises `ValueError` for unsupported action types rather than `AuthoringError`, breaking the error recovery pattern used in `cli.py`.
- The beam handler uses `height` as span length when in rotation-based format, which is a confusing overload of the `height` field name.
- `_reserved_fields()` is a static set that must be manually kept in sync with new action fields.
- `DesignPipeline.run()` has no error handling around individual stages -- a failure in analysis export will prevent results bundling.

## Last Reviewed
2026-03-31
