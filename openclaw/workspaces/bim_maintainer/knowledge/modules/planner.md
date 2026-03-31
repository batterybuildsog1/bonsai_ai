# Planner

## Purpose
Translates natural language prompts into structured tool calls by delegating to `bonsai_ai_core` for plan generation and compilation, then mapping compiled actions to legacy tool-call format.

## How It Works

### planner.py (213 lines)
- **Data classes:** `PlannedToolCall(id, name, arguments)`, `PlanResult(provider, model, tool_calls, raw_text)`.
- **`create_plan()`** is the main entry point:
  1. Validates provider name (openai/anthropic/gemini), maps "gemini" to "google" for core.
  2. Resolves API key from explicit value or env var.
  3. Composes a scene prompt combining user prompt + scene summary + progress summary.
  4. Calls `build_core_plan()` from `bonsai_ai_core` to get an authored plan.
  5. Calls `compile_core_plan()` to compile semantic actions into buildable primitives.
  6. Maps each compiled action to a `PlannedToolCall` via `_to_tool_call()`.
- **`_to_tool_call()`** translates action types using `_TOOL_NAME_MAP` (e.g., `create_rect_slab` -> `create_rectangular_slab`). Contains specialized argument extraction for slabs, walls, beams, curtain walls (computing width/rotation from x1/y1/x2/y2). Falls back to passing all non-`type`/`storey` fields as arguments.
- **`_TOOL_NAME_MAP`** maps 10 action types to tool names. Notably maps `create_rect_slab` -> `create_rectangular_slab`.
- **`DEFAULT_MODELS`** and **`DEFAULT_ENV_VARS`** are imported from `bonsai_ai_core.defaults` and re-keyed (core uses "google", planner uses "gemini").

### planner_backends.py (71 lines)
- **`CorePhysicalPlannerBackend`** implements the `PlannerBackend` protocol.
- Constructor takes `provider`, `model`, `api_key`, `reasoning_effort`, `service_tier`.
- `build_physical_model(brief)`:
  1. Lazy-imports `bonsai_ai_core`.
  2. Composes a prompt from the `DesignBrief` (prompt + constraints + documents + scene context).
  3. Calls `core.build_plan()` then `core.build_semantic_model()` then `core.compile_plan()`.
  4. Returns a `PhysicalModelSpec` with summary, assumptions, plan, authored_plan, semantic_model, and metadata (counts of authored/semantic/compiled elements).
- This backend is used by `design_pipeline_cli.py` and the bridge server.

## Current State
Fully implemented. The two-layer design (planner.py for cli.py, planner_backends.py for the pipeline) works but creates parallel code paths.

## Known Issues
- `_to_tool_call()` has a hardcoded `_TOOL_NAME_MAP` that must be updated whenever `bonsai_ai_core` adds action types. There is no validation that the map covers all possible compiled action types.
- The `create_plan()` function in `planner.py` sets `raw_text="COMPLETE"` when tool_calls is empty, which is misleading since no text was actually received.
- `planner_backends.py` uses `_load_core()` as a `@staticmethod` that does a bare `import bonsai_ai_core`, creating a hard runtime dependency that isn't declared at module level.

## Last Reviewed
2026-03-31
