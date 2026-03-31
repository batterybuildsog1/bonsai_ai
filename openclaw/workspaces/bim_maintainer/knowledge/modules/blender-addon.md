# Blender Addon

## Purpose
Provides an interactive Blender UI for generating IFC buildings from prompts, importing design artifacts, and applying presentation styles.

## How It Works

### bonsai_ai_blender/ package

**__init__.py** (13 lines): Registers as a Blender addon (bl_info: version 0.2.0, Blender 4.4+). Delegates to `ui.py` for register/unregister.

**runtime.py** (26 lines):
- `load_core()` imports `bonsai_ai_core` from vendored copy or system install.
- `load_headless_executor()` imports `HeadlessIfcExecutor` from vendored or system install.

**client.py** (177 lines) -- Bridge server thin client:
- `submit_design_job(bridge_url, payload)` POSTs to `/v1/jobs/design`.
- `get_job(bridge_url, job_id)` GETs `/v1/jobs/{job_id}`.
- `download_artifact(bridge_url, artifact_id, destination)` downloads binary artifacts.
- `list_artifacts(job, role, kind, is_primary)` filters the job's artifact list.
- `import_design_artifact(path, settings)` handles multiple artifact types:
  - Results bundle: imports into Blender text blocks (log, results, plan).
  - Design package: extracts plan and imports.
  - Raw plan: imports as plan text.
  - Unknown JSON: imports into log text.
- `import_job_artifact()` orchestrates download + import with role-based fallback (e.g., "results" falls back to "solver_result" then "results_bundle").
- `_import_ifc_artifact()` calls Blender's `bpy.ops.bim.load_project()` and then `bake_presentation()` from `presentation.py`.

**integration.py** (~350+ lines) -- `BonsaiAIExecutor` class:
- Works inside Blender using Bonsai's core APIs (`bonsai.core.geometry`, `bonsai.core.root`, `bonsai.tool`).
- `execute_plan(plan)` dispatches actions: `ensure_storey`, `create_rect_slab`, `create_wall`, `create_column`, `create_curtain_wall`.
- Each method creates Blender objects, assigns IFC class via `core_root.assign_class()`, creates IFC representations, and calls `switch_representation()`.
- `create_curtain_wall()` manually creates a grid of panels using tangent/normal vector math.
- `_ensure_storey()` reuses existing storeys or creates new ones via `bpy.ops.bim`.

**ui.py** (~43KB) -- main UI module (not fully read but referenced):
- Defines Blender panels, operators, and properties for the Bonsai AI sidebar.
- Includes plan editing, job submission, artifact import, and review view operators.

**presentation.py** (~30KB) -- styling module (not fully read but referenced):
- `bake_presentation()` applies material presets and view collections to imported IFC elements.

### src/bonsai_ai/blender_addon.py (144 lines) -- legacy/simple Blender addon:
- Standalone Blender addon alternative using `bpy` directly.
- `BonsaiAIProperties` property group with provider, model, api_key_env, output_path, prompt.
- `BONSAI_AI_OT_generate` operator: creates `IfcAuthor`, loops up to 12 rounds calling `create_plan()` from `planner.py` (the legacy path), with the same repeat/failure detection as `cli.py`.
- `BONSAI_AI_PT_panel`: simple sidebar panel with provider/model/key/path/prompt fields.

## Current State
The addon package (`bonsai_ai_blender/`) is the primary Blender integration, with rich UI, bridge server support, and presentation styling. The standalone `blender_addon.py` in `src/bonsai_ai/` is a simpler, self-contained alternative using the legacy planner path.

## Known Issues
- `bonsai_ai_blender/` vendors `bonsai_ai_core` in a `vendor/` subdirectory. Changes to `bonsai_ai_core` require rebuilding/recopying the vendor directory.
- `integration.py` only implements 4 of the 11 action types (ensure_storey, create_rect_slab, create_wall, create_column, create_curtain_wall). Missing: create_beam, create_panel, create_door, create_window, create_footing.
- `blender_addon.py` (`src/`) duplicates the cli.py replanning loop with identical logic.
- `client.py` uses `urllib.request` for HTTP (no async), which blocks Blender's main thread during artifact downloads.

## Last Reviewed
2026-03-31
