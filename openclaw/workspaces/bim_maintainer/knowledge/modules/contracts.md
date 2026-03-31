# Contracts

## Purpose
Central data model: all shared dataclasses, enums, and type definitions used across the pipeline stages.

## How It Works

### contracts.py (322 lines)
**Enums (7):**
- `AnalysisDomain`: WIND, SEISMIC, GRAVITY, FOOTING, STRUCTURAL_STEEL
- `AnalysisProfile`: GLOBAL_FAST, GLOBAL_FULL, FACADE_SUPPORT, SUBSTRUCTURE
- `EngineeringModelScope`: GLOBAL_FRAME, ROOF_LOAD_PATH, FACADE_SUPPORT, SUBSTRUCTURE, OPENING_SUPPORT
- `ArtifactKind`: 13 values (DESIGN_BRIEF through ENGINEERING_REPORT)
- `ArtifactFormat`: 12 values (JSON, PY, FCSTD, IFC, IFCZIP, PDF, PNG, GLB, CALCULIX_INP, CODE_ASTER, PYNITE_JSON, UNKNOWN)
- `ArtifactRole`: 14 values for artifact classification

**Core data classes:**
- `SourceDocument(name, path, role, metadata)` -- reference document input
- `LoadAction(target_id, kind, direction, magnitude, distribution, metadata)` -- individual load action
- `LoadCase(name, domain, code_basis, category, design_situation, parameters, actions)` -- named load case
- `LoadCombination(name, case_factors, category, code_basis)` -- load combination with factors
- `MaterialSpec(id, family, model, properties)` -- material definition
- `SectionSpec(id, kind, material_id, dimensions, metadata)` -- cross-section definition
- `SupportSpec(id, target_id, target_kind, restraints, spring_stiffness, metadata)` -- boundary condition
- `StructuralElement(id, kind, geometry, section_id, storey, orientation, metadata)` -- analytical element
- `StructuralSourceElement` -- extends StructuralElement with `role`, `structural_family`, `parent_id`, `system_id`, `assembly_id`, `layout_zone_id`, `layout_zone_kind`, `interface_type`
- `StructuralSourceModel(units, materials, sections, elements, supports, metadata)` -- full source model
- `AnalyticalModel` -- extends StructuralSourceModel with `load_cases` and `load_combinations`
- `EngineeringModel` -- scoped subset with `scope` field

**Pipeline data classes:**
- `DesignBrief(prompt, documents, scene_context, constraints, analysis_domains, load_cases, metadata)` -- input
- `PhysicalModelSpec(summary, assumptions, plan, authored_plan, semantic_model, metadata)` -- planner output
- `PipelineArtifact(kind, format, path, metadata)` -- file artifact reference
- `AnalysisRequest(solver, design_codes, load_cases, load_combinations, export_options, metadata)` -- analysis config
- `AnalysisResult(solver, status, governing_cases, unity_checks, warnings, artifacts, summary, metadata)` -- solver output

**Bundle data classes:**
- `NormalizedArtifactRef(kind, format, path, role, label, is_primary, metadata)` -- enriched artifact reference
- `PhysicalSummary(summary, assumptions, created, element_counts, storeys, planner_metadata)` -- physical stage summary
- `AnalysisSummary(status, domains, load_cases, load_combinations, solver, design_codes, governing_cases, unity_checks, warnings)` -- analysis stage summary
- `ResultsBundle(schema_version, entrypoints, artifacts, physical_summary, analysis_summary, diagnostics, blender_payload)` -- final bundle
- `DesignPackage` -- the master container with all stages, plus `to_manifest()` for JSON serialization

## Current State
Comprehensive and well-structured. All data classes use `@dataclass` with `field(default_factory=dict/list)` for mutable defaults.

## Known Issues
- `DesignPackage.to_manifest()` calls `asdict(self)` which deep-copies the entire object graph including large nested structures -- could be slow for big models.
- `StructuralSourceElement` has 13 fields, many optional, making it verbose to construct. Could benefit from a builder pattern.
- Some enum values are unused in practice (e.g., `ArtifactFormat.CALCULIX_INP`, `ArtifactFormat.CODE_ASTER`).

## Last Reviewed
2026-03-31
