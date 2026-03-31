# Results Bundle

## Purpose
Aggregates all pipeline artifacts into a normalized results bundle with entrypoints, summaries, and diagnostics for downstream consumption (Blender addon, review tools).

## How It Works

### results_bundle.py (293 lines)
**`JsonResultsBundleBackend`** implements `ResultsBundleBackend` protocol:
- `build(package, output_dir)`:
  1. Calls `_build_bundle()` to create a `ResultsBundle` dataclass.
  2. Writes it as `results_bundle.json`.
  3. Returns a single `PipelineArtifact`.

- `_build_bundle(package, output_dir)` constructs:
  - **entrypoints** dict mapping 15 named entrypoints to relative file paths:
    - `physical_ifc`, `physical_plan`, `semantic_model`, `structural_source_model`, `analytical_model`
    - `engineering_model_global_frame`, `engineering_model_roof_load_path`, `engineering_model_facade_support`, `engineering_model_substructure`, `engineering_model_opening_support`
    - `solver_request`, `solver_result`, `freecad_handoff`, `freecad_model`
  - **artifacts** list of `NormalizedArtifactRef` for all physical + analysis + review artifacts.
  - **physical_summary**: summary text, assumptions, created elements, element counts by IFC class, storeys, planner metadata.
  - **analysis_summary**: status, domains, load cases, solver, governing cases, unity checks, warnings.
  - **diagnostics**: execution messages, missing artifacts, engineering scope status.
  - **blender_payload**: role keys for Blender addon import.

- Entrypoint resolution uses a priority system: preferred role -> preferred format -> first match.
- `_entrypoint_by_role_and_scope()` finds engineering model artifacts by role + scope metadata.
- `_element_counts()` tallies IFC classes from execution items.
- `_missing_artifacts()` checks for expected artifacts and reports which are absent.

**Helper functions:**
- `_relative_path()` converts absolute paths to relative for portability.
- `_role_for_kind()` maps ArtifactKind to default ArtifactRole.
- `_label_for_kind()` maps ArtifactKind to human-readable labels.

## Current State
Fully implemented. The bundle serves as the single entry point for consuming pipeline results.

## Known Issues
- The bundle uses `asdict()` for serialization, which deep-copies all nested dataclasses including large metadata dicts.
- `_storeys()` has a fallback path that reads storeys from the plan's `ensure_storey` actions when execution items don't have storey metadata, but this fallback doesn't capture the elevation, only the name.
- The `blender_payload` section is minimal (just role keys and status). It could be enriched with more Blender-specific import hints.
- No validation that the referenced artifact files actually exist on disk at bundle creation time.

## Last Reviewed
2026-03-31
