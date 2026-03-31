# Improvement Backlog

Items added as observed. Priority based on frequency and impact.

## Format

```
- [ ] <description> (category: bug|feature|performance|quality|test) -- added YYYY-MM-DD
  Context: <how this was noticed>
```

## Bugs (from 2026-03-31 knowledge crawl)

- [ ] PyNite axis swap: `_section_properties()` maps `ix_m4` to `iy` and `iy_m4` to `iz` (bug) -- added 2026-03-31
  Context: pynite_backend.py review. May produce wrong results for asymmetric sections.

- [ ] Duplicate metadata key in `build_semantic_model()` return dict (bug) -- added 2026-03-31
  Context: bonsai_ai_core/semantic_model.py review. Dict has two `metadata` keys; second silently overwrites first.

- [ ] Cold-formed C/Z purlin/girt families defined in system_catalog but have no `CatalogSectionRecord` entries (bug) -- added 2026-03-31
  Context: section_library.py + system_catalog.py review. These families cannot be resolved to actual section properties.

## Performance

- [ ] Bridge server `run_design_job()` is synchronous, blocks FastAPI event loop (performance) -- added 2026-03-31
  Context: bonsai_ai_bridge/orchestrator.py review. Should be async or run in executor.

## Feature Gaps

- [ ] No `update_element_section` tool -- elements are write-only after creation (feature) -- added 2026-03-31
  Context: ifc_author.py review. Cannot swap component specs on existing IFC elements. Operator needs this for component selection workflow.

- [ ] Blender integration.py only implements 5 of 11 action types (feature) -- added 2026-03-31
  Context: bonsai_ai_blender/integration.py review. Missing: create_beam, create_panel, create_footing, create_curtain_wall, create_door, create_window.

## Quality

- [ ] Vendored addon copy out of sync with source (quality) -- added 2026-03-31
  Context: semantic_model.py modified but dist/staging copy is stale. Need to run scripts/package_addon.py.
