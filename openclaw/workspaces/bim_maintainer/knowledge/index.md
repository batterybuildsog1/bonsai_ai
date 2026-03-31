# Codebase Knowledge Index

## Application: Bonsai AI

Root: `/Users/alanknudson/Applications/Bonsai_ai/`

## Module Map

### Core Pipeline (src/bonsai_ai/)

```
User Prompt
    │
    ▼
cli.py / design_pipeline_cli.py    ← entry points
    │
    ▼
planner.py                          ← sends prompt + tools to AI provider
    │                                  returns PlannedToolCall[]
    ▼
tool_specs.py                       ← defines available tools + schemas
    │                                  formats per-provider (OpenAI/Anthropic/Gemini)
    ▼
ifc_author.py                       ← applies tool calls to IfcOpenShell
    │                                  creates native IFC geometry
    ▼
.ifc file                           ← output
```

### Analysis Pipeline (optional, via design_pipeline_cli.py)

```
.ifc file
    │
    ▼
structural_source.py                ← extracts structural elements from IFC
    │
    ▼
catalog_selector.py                 ← maps roles to catalog families
    │
    ▼
catalog_resolver.py                 ← resolves to specific sections (W12x26 etc)
    │
    ▼
grouped_sizing.py                   ← iterative member sizing
    │
    ▼
analysis_exports.py                 ← generates analytical models
    │
    ▼
pynite_backend.py                   ← runs FEA (gravity, seismic, wind)
    │
    ▼
results bundle                      ← JSON artifacts in out/<project>/
```

### Blender Addon (bonsai_ai_blender/)

```
ui.py                               ← Blender panels, operators, properties
    │
    ▼
runtime.py                          ← loads vendored bonsai_ai_core
    │
    ▼
bonsai_ai_core/                     ← planner, schema, providers (vendored copy)
    │
    ▼
integration.py                      ← scene context, IFC import
```

## Module Status

### Core pipeline (priority — understand these first)

| Module | Knowledge File | Last Reviewed |
|--------|---------------|---------------|
| cli.py + design_pipeline_cli.py | knowledge/modules/entry-points.md | 2026-03-31 |
| planner.py + planner_backends.py | knowledge/modules/planner.md | 2026-03-31 |
| ifc_author.py | knowledge/modules/ifc-author.md | 2026-03-31 |
| tool_specs.py | knowledge/modules/tool-specs.md | 2026-03-31 |
| execution.py + pipeline.py | knowledge/modules/execution.md | 2026-03-31 |
| contracts.py | knowledge/modules/contracts.md | 2026-03-31 |

### Catalog and sizing

| Module | Knowledge File | Last Reviewed |
|--------|---------------|---------------|
| catalog_selector.py + catalog_resolver.py | knowledge/modules/catalog-system.md | 2026-03-31 |
| section_library.py + system_catalog.py | knowledge/modules/section-library.md | 2026-03-31 |
| grouped_sizing.py | knowledge/modules/sizing.md | 2026-03-31 |
| system_layout.py | knowledge/modules/system-layout.md | 2026-03-31 |

### Structural analysis

| Module | Knowledge File | Last Reviewed |
|--------|---------------|---------------|
| structural_source.py | knowledge/modules/structural-source.md | 2026-03-31 |
| analysis_exports.py + load_path.py | knowledge/modules/analysis-pipeline.md | 2026-03-31 |
| pynite_backend.py + pynite_results.py | knowledge/modules/pynite.md | 2026-03-31 |
| footing_selector.py | knowledge/modules/footings.md | 2026-03-31 |
| freecad_handoff.py + freecad_runner.py | knowledge/modules/freecad.md | 2026-03-31 |
| results_bundle.py | knowledge/modules/results.md | 2026-03-31 |

### Blender and bridge

| Module | Knowledge File | Last Reviewed |
|--------|---------------|---------------|
| bonsai_ai_blender/ (ui, integration, client, runtime) | knowledge/modules/blender-addon.md | 2026-03-31 |
| bonsai_ai_core/ (planner, schema, providers, compiler) | knowledge/modules/core-library.md | 2026-03-31 |
| bonsai_ai_bridge/ (server, orchestrator, providers) | knowledge/modules/bridge-server.md | 2026-03-31 |

## Patterns

| Pattern | Knowledge File | Last Reviewed |
|---------|---------------|---------------|
| Provider dispatch (3 AI providers abstracted) | knowledge/patterns/provider-dispatch.md | 2026-03-31 |
| Tool call flow (prompt -> plan -> compile -> IFC) | knowledge/patterns/tool-call-flow.md | 2026-03-31 |
| Error recovery (retry, replan, fallback) | knowledge/patterns/error-recovery.md | 2026-03-31 |

## Relationships

- `tool_specs.py` defines what `planner.py` can ask for and what `ifc_author.py` can execute
- `catalog_selector.py` and `catalog_resolver.py` depend on `contracts.py` data classes
- `bonsai_ai_blender/` vendors a copy of `bonsai_ai_core/` -- changes to core need addon rebuild
- `design_pipeline_cli.py` orchestrates the full pipeline but each stage is independently testable

## Known Gaps

- No `update_element_section` tool (elements are write-only after creation)
- No mechanism to swap component specs on existing IFC elements
- Blender addon vendors source -- easy to get out of sync
- No streaming support in planner (full response only)
