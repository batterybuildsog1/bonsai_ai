# Structural Source

## Purpose
Extracts structural semantics from compiled physical plans, classifying elements by role, family, system, and zone to build a rich structural source model. Also provides analysis reduction and engineering model emission.

## How It Works

### structural_source.py (~1177 lines, ~54KB)
Three major classes in one file.

**`StructuralSourceModelBuilder`**:
- `build(package)` iterates over `package.physical_model.plan["actions"]`, calling `_elements_from_action()` for each. Produces a `StructuralSourceModel` with materials, sections, elements, and auto-generated supports.
- Element extraction methods (`_wall_source`, `_slab_source`, `_column_source`, `_beam_source`, `_panel_source`, `_footing_source`, `_curtain_wall_sources`):
  - Each creates a `StructuralSourceElement` with full semantic metadata.
  - Uses `_semantic_*()` helpers to extract from the `semantics` dict on each action.
  - Assigns `role` using classifiers: `_classify_column_role()` (facade_post, opening_jamb, primary_column, gravity_column), `_classify_beam_role()` (14 roles including brace, collector, floor_beam, etc.).
  - Assigns `structural_family` via `_family_for_column_role()` / `_family_for_beam_role()` (primary_frame, facade_support, opening_support, secondary_frame, panel_system, substructure, diaphragm).
  - Computes `parent_id` using spatial/naming heuristics: `_parent_for_column()` uses grid coordinates, `_parent_for_beam()` uses storey and naming patterns (brace bay, collector line, etc.).
  - Calls `_identity_for_zone()` to derive `system_id`, `assembly_id`, `layout_zone_id`, `layout_zone_kind`, and `interface_type`.
- `_default_supports()` finds the lowest primary columns and adds fixed-base supports.
- Naming/classification uses extensive string matching on element names (e.g., "Basement Retaining" -> retaining role, facade directions from name).

**`StructuralAnalysisReducer`**:
- `reduce(source_model, profile, request, ...)` filters source elements by analysis profile and converts to `StructuralElement` via `_to_analytical_element()`.
- Profile filtering: `GLOBAL_FAST` keeps only primary_frame/brace/collector; `GLOBAL_FULL` keeps everything; `FACADE_SUPPORT` and `SUBSTRUCTURE` keep role-specific subsets.
- `_normalize_load_case()` generates default load actions when none are provided:
  - GRAVITY: self-weight + superimposed loads from load path diaphragm zones.
  - WIND: surface pressure on facades or point loads on collectors, with load-path-aware zone targeting.
  - FOOTING: surface traction on foundation elements.
  - Fallback: self-weight only.

**`StructuralEngineeringModelEmitter`**:
- `emit(source_model, scope)` creates scoped `EngineeringModel` subsets:
  - GLOBAL_FRAME: primary_frame, brace, collector, diaphragm
  - ROOF_LOAD_PATH: roof-specific roles + columns
  - FACADE_SUPPORT: facade_post, spandrel, opening support, envelope
  - SUBSTRUCTURE: retaining, foundation, columns
  - OPENING_SUPPORT: opening headers/sills/jambs + facade context
- Adds warnings when supports are missing or derived from parent.
- Computes rich metadata with role/group/family/parent/system/zone counts.

## Current State
Fully implemented and the most complex module in the codebase. The semantic classification system is sophisticated, mapping over 16 structural roles across 7 families with zone/system hierarchy.

## Known Issues
- Heavy reliance on string matching in element names for classification (e.g., `_facade_from_name()` searches for cardinal directions). Names from non-English prompts or unconventional naming would break classification.
- `_assembly_id_for_role()` returns `parent_id` for every role branch, making assembly_id effectively the same as parent_id in all cases -- the branching logic is dead code.
- `StructuralAnalysisReducer` references `StructuralSourceModelBuilder._analysis_group()` as a static method, creating tight coupling between the two classes.
- Wind load generation has cascading fallback logic (load-path zones -> fallback zone targets -> fallback beam targets) that is hard to reason about.
- The file is ~54KB and mixes three distinct responsibilities; splitting into separate files would improve maintainability.

## Last Reviewed
2026-03-31
