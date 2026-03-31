# Codebase State

## Last Updated

2026-03-31 (full review)

## Architecture Summary

Bonsai AI is a Python-based BIM authoring system that generates native IFC4 files from natural language prompts, with optional structural analysis, catalog-based member sizing, and FreeCAD handoff.

Three execution paths:
1. **CLI** (`src/bonsai_ai/cli.py`) -- direct prompt-to-IFC with iterative replanning (up to 12 rounds)
2. **Design Pipeline CLI** (`src/bonsai_ai/design_pipeline_cli.py`) -- full pipeline: plan -> IFC -> structural source -> catalog selection -> analysis -> sizing -> FreeCAD -> results bundle
3. **Bridge Server** (`src/bonsai_ai_bridge/server.py`) -- FastAPI REST interface exposing the full pipeline as HTTP endpoints
4. **Blender Addon** (`bonsai_ai_blender/`) -- interactive UI in Blender 4.4+ with bridge server integration

Three AI providers, all using raw HTTP (no SDK):
- OpenAI gpt-5.4 (primary) via Responses API (`/v1/responses`)
- Anthropic claude-opus-4-6 via Messages API with forced tool_use
- Google gemini-2.5-flash-lite via Generative Language API

Core planning library (`bonsai_ai_core/`) supports 18 action types:
- 10 buildable: ensure_storey, create_rect_slab, create_wall, create_column, create_beam, create_panel, create_window, create_door, create_curtain_wall, create_footing
- 3 semantic: create_stair_run, create_stair_landing, create_connection_plate
- 5 edit: update_element, delete_element, move_element, replace_section, rebuild_branch

## Module Sizes (measured)

| Module | Size | Lines | Complexity |
|--------|------|-------|------------|
| structural_source.py | 54KB | ~1177 | High -- 3 classes, role/family/zone classification |
| ifc_author.py | 49KB | ~1110 | High -- core geometry engine, 11 element types |
| analysis_exports.py | 40KB | ~800+ | High -- full analysis export orchestration |
| ui.py (blender) | 43KB | - | Medium -- Blender UI/operators |
| presentation.py (blender) | 30KB | - | Medium -- Blender styling |
| pynite_backend.py | 27KB | ~542 | High -- FEA solver integration |
| grouped_sizing.py | 17KB | ~317 | Medium -- iterative member sizing |
| freecad_handoff.py | 16KB | ~399 | Medium -- FreeCAD payload + macro generation |
| semantic_model.py (core) | 16KB | - | Medium -- assembly tree construction |
| schema.py (core) | 16KB | - | Medium -- plan validation |
| results_bundle.py | 14KB | ~293 | Medium -- artifact aggregation |
| integration.py (blender) | 13KB | ~350+ | Medium -- Blender/Bonsai execution |
| compiler.py (core) | 12KB | - | Medium -- semantic action compilation |
| tool_specs.py | 13KB | ~307 | Low -- declarative tool definitions |
| contracts.py | 10KB | ~322 | Low -- data model definitions |
| section_library.py | 10KB | ~297 | Low -- AISC section properties |
| system_catalog.py | 9KB | ~205 | Low -- starter catalog data |
| planner.py (src) | 8KB | ~213 | Low -- provider dispatch |
| providers.py (core) | 9KB | ~240 | Medium -- 3 provider implementations |
| system_layout.py | 7KB | ~187 | Low -- zone/system hierarchy |
| freecad_runner.py | 8KB | ~218 | Low -- subprocess execution |
| load_path.py | 7KB | ~160 | Low -- facade/diaphragm load paths |
| footing_selector.py | 7KB | ~159 | Low -- footing sizing |
| client.py (blender) | 7KB | ~177 | Low -- bridge server client |
| design_pipeline_cli.py | 5KB | ~124 | Low -- pipeline CLI |
| catalog_selector.py | 5KB | ~113 | Low -- role-to-family mapping |
| planner.py (core) | 5KB | ~85 | Low -- plan generation with self-repair |
| cli.py | 3KB | ~91 | Low -- simple CLI |
| catalog_resolver.py | 3KB | ~71 | Low -- section resolution |
| plan_roundtrip.py | 3KB | ~77 | Low -- sizing roundtrip |
| pipeline.py | 3KB | ~80 | Low -- protocol definitions |
| planner_backends.py | 3KB | ~71 | Low -- pipeline planner backend |

## Key Findings (2026-03-31 review)

1. **Two parallel planning paths**: `cli.py` uses `planner.py` (tool-call loop), `design_pipeline_cli.py` uses `planner_backends.py` (single-pass through bonsai_ai_core). The two paths share `bonsai_ai_core` but diverge in how they dispatch compiled actions.

2. **Cold-formed sections unresolved**: C and Z purlin/girt families are defined in the system catalog but have no `CatalogSectionRecord` entries, meaning they cannot be resolved to actual section properties.

3. **PyNite axis swap**: `_section_properties()` maps `ix_m4` to `iy` and `iy_m4` to `iz`, which may swap major/minor axis conventions.

4. **Duplicate semantic model metadata key**: `build_semantic_model()` in `bonsai_ai_core/semantic_model.py` has duplicate `metadata` key in the return dict.

5. **Bridge server blocking**: `run_design_job()` is synchronous, blocking the FastAPI event loop.

6. **integration.py incomplete**: Blender's `BonsaiAIExecutor` only implements 5 of 11 action types.

## Test Coverage

20 test modules in `tests/`. Key ones:
- test_execution.py -- IFC authoring integration
- test_ifc_author.py -- low-level IFC operations
- test_providers.py -- provider API integration
- test_pynite_backend.py -- structural analysis
- test_schema.py -- plan validation
