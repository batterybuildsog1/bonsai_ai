# Entry Points

## Purpose
Two CLI entry points that drive the system: `cli.py` for simple prompt-to-IFC, and `design_pipeline_cli.py` for the full design+analysis pipeline.

## How It Works

### cli.py (91 lines)
- `build_parser()` defines argparse with `--provider`, `--model`, `--api-key-env`, `--output`, `--prompt`, `--dry-run`.
- `main()` creates an `IfcAuthor(args.output)`, then loops up to 12 rounds:
  1. Calls `create_plan()` from `planner.py` with the user prompt, scene summary, and progress summary.
  2. Detects repeat rounds via `round_signature` (tuple of call name + sorted JSON args) stored in `seen_rounds`.
  3. Applies each `PlannedToolCall` via `author.apply_tool_call(call.name, call.arguments)`.
  4. On `AuthoringError`, records the failure in `failed_calls` and appends a replan hint to `progress_lines`. If the same call fails twice, raises.
  5. On `--dry-run`, skips execution and prints the planned calls as JSON.
- After all rounds, calls `author.save()` and prints results + `debug_dump()`.

### design_pipeline_cli.py (124 lines)
- `build_parser()` adds richer args: `--analysis-domain` (repeatable, from `AnalysisDomain` enum), `--solver`, `--freecad-handoff`, `--run-freecad`, `--design-code`, `--reasoning-effort`, `--service-tier`.
- `main()` builds a `DesignBrief` and optional `AnalysisRequest`, then constructs a `DesignPipeline` with:
  - `CorePhysicalPlannerBackend` (planner)
  - `IfcPhysicalModelBackend` (physical backend)
  - `JsonAnalysisExportBackend` (analysis exporter)
  - `PyNiteSolverBackend` (if solver == "pynite")
  - `JsonResultsBundleBackend` (results)
- Calls `pipeline.run(brief, output_dir, analysis_request)` to get a `DesignPackage`.
- Optionally runs `run_freecad_handoff()` if `--run-freecad` and the handoff JSON exists.
- `DEFAULT_ENGINEERING_SCOPES` = `["global_frame", "roof_load_path", "facade_support", "substructure", "opening_support"]`.

## Current State
Both CLIs are fully implemented and functional. `cli.py` is the simpler, original entrypoint. `design_pipeline_cli.py` is the full pipeline that includes structural analysis, catalog selection, sizing, FreeCAD handoff, and results bundling.

## Known Issues
- `cli.py` hardcodes `max_rounds = 12` with no CLI flag to override.
- `cli.py` uses the older `create_plan()` path from `planner.py` while `design_pipeline_cli.py` uses `CorePhysicalPlannerBackend` which goes through `bonsai_ai_core.build_plan` + `compile_plan` -- two different code paths for the same conceptual operation.
- `design_pipeline_cli.py` always creates a `PyNiteSolverBackend` only when `--solver pynite` is set, but the default is `"calculix"` which has no backend implementation, meaning analysis without `--solver pynite` will skip the solver stage silently.

## Last Reviewed
2026-03-31
