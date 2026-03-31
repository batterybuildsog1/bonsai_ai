# Core Library

## Purpose
Pure-Python planning core that handles prompt-to-plan generation, plan validation, compilation (semantic actions to buildable primitives), and semantic model construction. Provider-agnostic and dependency-free (stdlib HTTP only).

## How It Works

### bonsai_ai_core/ package

**__init__.py**: Exports `build_plan`, `compile_plan`, `build_semantic_model`, `semantic_model_to_plan`, `validate_plan`, `pretty_plan`, `DEFAULT_MODELS`, `PROVIDERS`.

**defaults.py** (16 lines):
- `PROVIDERS = ("openai", "anthropic", "google")`
- `DEFAULT_MODELS`: openai -> gpt-5.4, anthropic -> claude-opus-4-6, google -> gemini-2.5-flash-lite
- `ENV_KEYS`: maps each provider to env var names.

**errors.py** (11 lines): `BonsaiAIError`, `ProviderError`, `ValidationError`.

**http.py** (34 lines): `post_json()` using `urllib.request`, raises `ProviderError` for HTTP errors and JSON parse failures.

**providers.py** (240 lines):
- `ProviderRequest` dataclass: provider, system_prompt, user_prompt, model, api_key, reasoning_effort, service_tier.
- `BaseProvider` base class with `generate_plan()` abstract method.
- **`OpenAIProvider`**: Uses `/v1/responses` endpoint with `json_schema` response format. Has retry logic: first retries without `service_tier` if priority fails, then retries without JSON schema constraint if schema is rejected. Parses response from `output_text` or nested `output[].content[].text`.
- **`AnthropicProvider`**: Uses `/v1/messages` with tool_use forced to `emit_bonsai_action_plan`. Extracts plan from `tool_use` content block or falls back to text extraction.
- **`GoogleProvider`**: Uses `generativelanguage.googleapis.com/v1beta` with `responseSchema` in `generationConfig`. API key in URL query param.
- `_extract_json_from_text()` strips markdown code fences and attempts brace-delimited extraction.
- `get_provider(req)` dispatches to the correct provider class.

**planner.py** (85 lines):
- `SYSTEM_PROMPT` (~40 lines): defines Bonsai AI's role, supported action types (18 total including semantic and edit actions), and rules for generation.
- `build_plan(prompt, provider, model, api_key, reasoning_effort, service_tier)`:
  1. Validates non-empty prompt.
  2. Loops up to 3 attempts with self-repair:
     - Calls `get_provider(req).generate_plan()`.
     - Validates via `validate_plan()`.
     - On `ValidationError`, appends the error to the prompt for the next attempt.
  3. Raises the last error if all attempts fail.

**schema.py** (~100+ lines):
- `plan_schema()` returns JSON Schema for the plan: version, units ("meters"), summary, assumptions, actions (array of typed objects with `COMMON_ACTION_PROPERTIES`).
- `validate_plan()` checks required fields, units, and validates each action.
- `validate_action()` checks type against `SUPPORTED_ACTIONS`, validates name, optional objects (semantics/presentation/foundation/patch), edit action requirements (target fields, patch object).
- `_coerce_numeric_fields()` converts string numbers to floats for robustness.

**action_catalog.py** (~200+ lines):
- `BUILDABLE_ACTIONS` (10), `SEMANTIC_ACTIONS` (3: stair_run, stair_landing, connection_plate), `EDIT_ACTIONS` (5: update/delete/move/replace_section/rebuild_branch).
- `COMMON_ACTION_PROPERTIES`: 60+ properties covering all action types, semantics, presentation, and foundation metadata.
- `SEMANTICS_OBJECT`, `PRESENTATION_OBJECT`, `FOUNDATION_OBJECT`: shared JSON Schema objects.

**compiler.py** (~150+ lines):
- `compile_plan(plan)`:
  1. Deep-copies and validates the plan.
  2. Builds a semantic model via `build_semantic_model()`.
  3. Converts back to plan via `semantic_model_to_plan()`.
  4. Compiles each action: stair_run -> series of create_rect_slab treads, stair_landing -> create_rect_slab, connection_plate -> create_panel (horizontal), edit actions applied in-place.
  5. Validates the compiled plan (no semantic/edit actions allowed).

**semantic_model.py** (~150+ lines):
- `build_semantic_model(plan)`: normalizes elements with stable IDs, builds assembly tree from branch_path/parent_id/assembly_id.
- `semantic_model_to_plan(model)`: extracts actions from elements.
- Handles edit actions (`_apply_edit_action`): delete removes from state, move applies dx/dy/dz offsets, update applies patch objects.
- Assembly tree construction: uses branch paths (group_path) to create hierarchical nodes, links elements to assemblies.

## Current State
Fully implemented and the most architecturally clean package in the codebase. Zero external dependencies (stdlib HTTP only). Supports all 18 action types including semantic editing.

## Known Issues
- OpenAI provider uses `/v1/responses` endpoint (not `/v1/chat/completions`), which is the newer Responses API. The fallback retry logic is complex with 3 levels of retries.
- The 3-attempt self-repair loop in `build_plan()` appends validation errors to the prompt, which increases token usage on each retry.
- `SYSTEM_PROMPT` references action types like `create_stair_run` and edit actions that the planner itself doesn't route to `IfcAuthor` -- they depend on the compiler step.
- `semantic_model.py` has duplicate `metadata` key in the return dict of `build_semantic_model()` (lines 43-53 and 68-76) -- the second one overwrites the first.
- No streaming support for any provider.

## Last Reviewed
2026-03-31
