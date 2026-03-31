# Pattern: Provider Dispatch

## Summary
Three AI providers (OpenAI, Anthropic, Google) are abstracted behind a common interface using raw HTTP calls with provider-specific payload formatting.

## Implementation

### Core dispatch (bonsai_ai_core/providers.py)
The canonical implementation uses a class hierarchy:
1. `ProviderRequest` dataclass carries: provider name, prompts, model, api_key, reasoning_effort, service_tier.
2. `BaseProvider` base class holds the request, resolved API key, model, and schema.
3. Three concrete providers override `generate_plan()`:
   - **`OpenAIProvider`**: POST to `api.openai.com/v1/responses`, JSON schema response format, Authorization header. Retry logic: (a) retry without priority service_tier, (b) retry without JSON schema constraint.
   - **`AnthropicProvider`**: POST to `api.anthropic.com/v1/messages`, forced tool_use for `emit_bonsai_action_plan`, x-api-key header.
   - **`GoogleProvider`**: POST to `generativelanguage.googleapis.com/v1beta`, responseSchema in generationConfig, API key in URL query.
4. `get_provider(req)` dispatches by provider name string.

### API key resolution
`_resolve_api_key(provider, explicit_key)` checks:
1. Explicit key parameter.
2. Environment variables from `ENV_KEYS[provider]` (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`).

### Response extraction
All providers return raw API responses. `_extract_json_from_text()` handles:
1. Stripping markdown code fences.
2. Extracting the first `{...}` block if direct parse fails.

### Provider name mapping
The system uses "google" internally but "gemini" externally:
- `bonsai_ai_core`: uses "google" everywhere.
- `src/bonsai_ai/planner.py`: maps "gemini" -> "google" via `_provider_name()`.
- `DEFAULT_MODELS` in planner.py is re-keyed: `{"gemini": CORE_DEFAULT_MODELS["google"]}`.

### Tool specs formatting (src/bonsai_ai/tool_specs.py)
A parallel, legacy formatting layer exists for the older `cli.py` path:
- `as_openai_tools()`: `{"type": "function", "function": {..., "strict": True}}`
- `as_anthropic_tools()`: `{"name", "description", "input_schema"}`
- `as_gemini_tools()`: `{"name", "description", "parameters"}`
These are not used by the newer pipeline path.

## Key design decisions
- **No SDKs**: All providers use `urllib.request` directly. This keeps the dependency footprint at zero but means the code handles rate limiting, retries, and response parsing manually.
- **Schema-driven generation**: OpenAI and Google use JSON Schema for structured output. Anthropic uses forced tool_use. All produce the same plan schema.
- **Graceful degradation**: OpenAI provider has 3 retry levels (priority -> standard tier, schema -> no-schema, combined).

## Last Reviewed
2026-03-31
