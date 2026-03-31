# Pattern: Error Recovery

## Summary
Error recovery operates at three levels: LLM plan generation (retry + self-repair), IFC authoring (replan on failure), and provider API calls (tier/schema fallback).

## Level 1: Provider API Retry (bonsai_ai_core/providers.py)

**OpenAI** has the most sophisticated retry:
1. First call with `service_tier: "priority"` and JSON schema format.
2. If `service_tier` error detected -> retry without priority.
3. If `invalid_json_schema` error -> retry with schema in system prompt text instead of structured format.
4. If both fail -> retry without priority AND without schema.
Detection: `_should_retry_without_priority()` checks for "service_tier" or "priority" in error text. `_should_retry_without_schema()` checks for "invalid_json_schema" or "invalid schema for response_format".

**Anthropic** and **Google** have no retry logic -- single attempt, fail on error.

## Level 2: Plan Validation Self-Repair (bonsai_ai_core/planner.py)

`build_plan()` loops up to 3 attempts:
1. Generate plan via provider.
2. Validate via `validate_plan()`.
3. On `ValidationError`:
   - Append the validation error message to the prompt.
   - Tell the model: "The previous JSON plan was invalid. Return a corrected plan."
   - Retry with the augmented prompt.
This handles malformed JSON, missing fields, wrong types, and invalid action types.

`validate_plan()` coerces string numbers to floats (`_coerce_numeric_fields()`) before validation, handling a common LLM mistake of returning "3.0" instead of 3.0.

## Level 3: IFC Authoring Replan (src/bonsai_ai/cli.py)

The CLI loop handles authoring failures:
1. Apply each `PlannedToolCall` via `author.apply_tool_call()`.
2. On `AuthoringError`:
   - Record the failed call signature (name + arguments) in `failed_calls`.
   - Append a failure message to `progress_lines`: "FAILED {tool}: {error}. Replan from the updated scene summary and avoid this mistake."
   - Continue to the next round, where the planner sees the failure context.
3. If the same call fails twice (signature in `failed_calls`), raise immediately.
4. If the planner emits the exact same set of calls as a previous round (`seen_rounds`), raise to prevent infinite loops.
5. Maximum 12 rounds before raising.

Common recoverable errors:
- "Storey not found" -> planner adds ensure_storey in next round.
- "Wall not found" (for door/window hosting) -> planner creates the wall first.
- "Zero-length wall/beam" -> planner adjusts coordinates.

## Level 4: Pipeline Stage Independence (pipeline.py)

The `DesignPipeline.run()` method has implicit error isolation:
- Each stage checks for required inputs (e.g., `if not package.physical_model: raise ValueError`).
- Optional stages (solver, results bundle) only run if their backend is configured.
- However, there is no try/except around individual stages -- a failure in analysis export prevents results bundling.

## Level 5: Grouped Sizing Convergence (grouped_sizing.py)

The iterative sizing loop has its own convergence safety:
- Maximum 8 iterations.
- `_advance_failing_groups()` only advances groups with unity > 1.0.
- Monotonic progression: candidates only move forward (larger sections), never backward.
- If no groups advanced, the loop terminates (converged or stuck).
- If candidates are exhausted for a failing group, it stays at the largest available section.

## Known gaps
- No retry on `ProviderError` for network failures (timeout, DNS, connection reset).
- The bridge server orchestrator catches exceptions and sets job status to "failed" but doesn't retry.
- Blender addon blocks the main thread during API calls with no timeout UI feedback.
- PyNite solver failures (singular stiffness matrix, etc.) are not caught -- they propagate as unhandled exceptions.

## Last Reviewed
2026-03-31
