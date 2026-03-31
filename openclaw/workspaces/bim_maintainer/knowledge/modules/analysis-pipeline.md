# Analysis Pipeline

## Purpose
Orchestrates the full analysis export: builds structural source models, applies catalog selection, generates analytical models, emits engineering models, and produces FreeCAD handoff artifacts.

## How It Works

### analysis_exports.py (~800+ lines, ~40KB)

**`AnalyticalModelBuilder`** class:
- `build(package)`:
  1. Calls `StructuralSourceModelBuilder().build(package)` to create the structural source model.
  2. Calls `build_load_path_model()` to create load path zones.
  3. Calls `StructuralAnalysisReducer().reduce()` with the appropriate profile.
  4. Returns an `AnalyticalModel`.
- `_profile_from_options()` maps export options to `AnalysisProfile` enum.
- Also contains legacy `_elements_from_action()` methods that duplicate functionality from `StructuralSourceModelBuilder` -- these create `StructuralElement` objects directly (without the richer `StructuralSourceElement` semantics).

**`JsonAnalysisExportBackend`** implements `AnalysisExportBackend` protocol:
- `export(package, output_dir)`:
  1. Optionally builds semantic model from `bonsai_ai_core.semantic_model` if missing.
  2. Builds the analytical model via `AnalyticalModelBuilder`.
  3. Applies catalog selection (`apply_catalog_selection()`) and resolution (`resolve_catalog_sections()`).
  4. Builds system layout (`build_system_layout()`).
  5. Builds load path model.
  6. Emits engineering models for each requested scope via `StructuralEngineeringModelEmitter`.
  7. Writes 8+ JSON files: semantic_model, structural_source_model, system_layout, load_path_model, catalog_selection_summary, analytical_model, solver_request, analysis_profile_summary.
  8. Optionally emits FreeCAD handoff via `FreeCADHandoffExporter`.
  9. Returns a list of `PipelineArtifact` references.

### load_path.py (160 lines)
- **`build_load_path_model(source_model, system_layout)`** creates facade and diaphragm zone load paths:
  - `_facade_zone_load_paths()`: groups facade-zone elements, finds envelope elements and their support elements (panel_support, collector_transfer, primary_framing), computes surface areas.
  - `_diaphragm_zone_load_paths()`: groups diaphragm-zone elements, finds supporting primary frame members by storey.
  - Returns a dict with `facade_zones`, `diaphragm_zones`, and `systems` (primary_frame, substructure summaries).
- Helper functions: `_vertical_surface_area()`, `_horizontal_surface_area()`, `_element_height()`, `_element_width()`, `_supports_facade()`.

## Current State
Fully implemented. The analysis export is the most artifact-heavy stage, producing 8+ JSON files plus engineering models per scope.

## Known Issues
- `AnalyticalModelBuilder` contains legacy `_elements_from_action()` methods that duplicate `StructuralSourceModelBuilder` but produce `StructuralElement` instead of `StructuralSourceElement`. These appear to be dead code since `build()` delegates to `StructuralSourceModelBuilder`, but they are still present and maintained.
- `_parse_engineering_scopes()` is called in `export()` but not defined in the visible code -- likely a method that validates scope names.
- `load_path.py` passes `elements` as an iterable to `_diaphragm_zone_load_paths()` without converting to a list first, meaning it would be consumed by the first iteration. However, `build_load_path_model()` converts to `list(source_model.elements)` at the top, so this works because the list is passed, not a generator.
- FreeCAD handoff is included in the analysis export backend even though it is logically a separate concern.

## Last Reviewed
2026-03-31
