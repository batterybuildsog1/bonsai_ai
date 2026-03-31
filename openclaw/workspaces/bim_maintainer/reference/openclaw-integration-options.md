# OpenClaw Integration Options for Bonsai AI Planner

**Date:** 2026-03-30
**Problem:** The direct planner (`planner.py`) produces good buildings but requires an OpenAI API key (out of quota). The OpenClaw agent bridge (`openclaw_planner.py`) uses subscription auth but the agent framework adds ~16KB of context overhead (AGENTS.md, SOUL.md, TOOLS.md, MEMORY.md, memory search, session history) that bloats prompts, causes timeouts, and degrades output quality.

**Goal:** Use OpenClaw's subscription auth (openai-codex OAuth) without the agent context overhead.

---

## Architecture Summary

**What works (direct planner):**
- `bonsai_ai_core/planner.py` builds a `ProviderRequest` with `SYSTEM_PROMPT` (~2.5KB) and the user prompt
- `bonsai_ai_core/providers.py` `OpenAIProvider` sends the request to `https://api.openai.com/v1/responses` with `Authorization: Bearer <api_key>`
- Uses structured output (`json_schema` response format) for reliable JSON plans
- Has a 3-attempt validation/repair loop
- Total prompt: system prompt + user prompt + JSON schema = clean and focused

**What struggles (OpenClaw bridge):**
- Spawns `openclaw agent --agent bim_operator --message <prompt> --json`
- The gateway loads the bim_operator agent, which injects AGENTS.md (9.4KB), SOUL.md (1.6KB), TOOLS.md (3.8KB), MEMORY.md, memory search results, and session history
- Prompt balloons from ~4KB to ~20KB+ before the model even sees the building request
- No structured output -- the agent outputs freeform text that must be parsed for JSON
- Single attempt (no validation/repair loop at the agent level)

**Key discovery:** The `openai-codex:default` auth profile in `~/.openclaw/agents/bim_operator/agent/auth-profiles.json` contains an OAuth JWT with audience `https://api.openai.com/v1`, a refresh token, and expiry timestamp. This token is issued by `https://auth.openai.com` and is accepted as a Bearer token by OpenAI's API directly.

---

## Option A: Enable the Gateway's OpenAI-Compatible HTTP API (Recommended)

### How it works

OpenClaw's gateway can expose an OpenAI-compatible HTTP API at `POST /v1/chat/completions` and `POST /v1/responses` on the same port as the gateway (18789). These endpoints act as a transparent proxy: they accept standard OpenAI API payloads, authenticate using the gateway token, route to the configured model provider (openai-codex OAuth), and return standard OpenAI response format. No agent framework is loaded.

The `x-openclaw-model` header selects the backend model. The gateway handles OAuth token refresh automatically.

### What to configure

Add to `openclaw.json` under `gateway`:

```json
{
  "gateway": {
    "http": {
      "endpoints": {
        "chatCompletions": { "enabled": true },
        "responses": { "enabled": true }
      }
    }
  }
}
```

Then restart the gateway: `openclaw gateway restart`

### Code changes

**Option A1 -- Minimal change in `providers.py`:** Add an `OpenClawProxyProvider` that points `OpenAIProvider` at the gateway instead of `api.openai.com`:

```python
class OpenClawProxyProvider(OpenAIProvider):
    """Route through the local OpenClaw gateway for subscription auth."""
    provider_name = "openai"
    endpoint = "http://127.0.0.1:18789/v1/responses"

    def __init__(self, req: ProviderRequest):
        # Skip API key resolution -- gateway handles auth
        self.req = req
        self.api_key = None  # not used
        self.model = req.model or DEFAULT_MODELS["openai"]
        self.schema = plan_schema()
        # Gateway token for auth
        self._gateway_token = os.getenv(
            "OPENCLAW_GATEWAY_TOKEN",
            "f9bc185f6781f1b743e815d6767572b3df25a32426b64b15"
        )

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._gateway_token}",
            "Content-Type": "application/json",
            "x-openclaw-model": f"openai-codex/{self.model}",
        }
```

**Option A2 -- Even simpler, change in `planner.py` only:** Set the existing `OpenAIProvider` endpoint and API key to proxy through the gateway. This requires only environment variables:

```bash
export BONSAI_OPENCLAW_PROXY=1
export OPENCLAW_GATEWAY_TOKEN=f9bc185f6781f1b743e815d6767572b3df25a32426b64b15
```

And a ~15-line wrapper in `planner.py` that, when `BONSAI_OPENCLAW_PROXY` is set, overrides the provider endpoint to `http://127.0.0.1:18789/v1/responses` and passes the gateway token as the Bearer credential, with `x-openclaw-model: openai-codex/gpt-5.4` in headers.

### Impact on output quality

**Same as direct planner.** The exact same `SYSTEM_PROMPT`, JSON schema, and validation/repair loop execute. The only difference is the HTTP endpoint -- the gateway proxies to the same OpenAI model with zero additional context. Structured output (`json_schema` response format) is preserved.

### Complexity

**Low.** Gateway config change (3 lines of JSON) + one new provider class or env-var wrapper (~30 lines). No changes to prompt engineering, schema, or validation. The gateway already exists and runs on port 18789.

### Auth mechanism

Subscription auth (openai-codex OAuth). Gateway handles token refresh automatically. No API keys needed.

---

## Option B: Extract the OAuth Token Directly from auth-profiles.json

### How it works

Read the `openai-codex:default` profile from `~/.openclaw/agents/bim_operator/agent/auth-profiles.json`, extract the `access` JWT, and use it as a Bearer token in direct calls to `https://api.openai.com/v1/responses`. The JWT audience is `https://api.openai.com/v1`, so OpenAI's API accepts it directly. When the token expires, read the `refresh` token, call `https://auth.openai.com/oauth/token` with a PKCE exchange to get a new access token, and write it back.

### Code changes

New module `bonsai_ai_core/openclaw_auth.py` (~60-80 lines):

```python
import json, time
from pathlib import Path
from urllib import request

AUTH_PROFILES = Path.home() / ".openclaw/agents/bim_operator/agent/auth-profiles.json"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"

def get_codex_token() -> str:
    profiles = json.loads(AUTH_PROFILES.read_text())
    codex = profiles["profiles"]["openai-codex:default"]
    if codex["expires"] / 1000 > time.time() + 300:  # 5min buffer
        return codex["access"]
    # Refresh the token
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": codex["refresh"],
    }).encode()
    req = request.Request(TOKEN_URL, data=data, method="POST")
    resp = json.loads(request.urlopen(req).read())
    codex["access"] = resp["access_token"]
    codex["refresh"] = resp.get("refresh_token", codex["refresh"])
    codex["expires"] = int(time.time() + resp["expires_in"]) * 1000
    AUTH_PROFILES.write_text(json.dumps(profiles, indent=2))
    return codex["access"]
```

Then in `providers.py`, modify `_resolve_api_key` to fall back to `get_codex_token()` when no API key is set and the provider is `openai`.

### Impact on output quality

**Same as direct planner.** Identical prompt, schema, structured output, and validation loop. The only change is the auth credential source.

### Complexity

**Medium.** The token extraction is straightforward, but the refresh flow has edge cases:
- File locking (OpenClaw may refresh concurrently)
- The client_id is extracted from the JWT and may change across OpenClaw versions
- The refresh endpoint may require additional PKCE parameters
- Token write-back must not corrupt OpenClaw's own token management
- Requires monitoring OpenClaw updates for auth format changes

### Auth mechanism

Subscription auth (openai-codex OAuth), extracted directly. No API keys. Refresh handled in-process.

### Risks

- **Token conflicts:** Bonsai and OpenClaw refreshing the token simultaneously can cause race conditions. The loser's refresh token becomes invalid.
- **Brittleness:** The auth-profiles.json format, client_id, and refresh endpoint are internal to OpenClaw and undocumented. Breaking changes in OpenClaw updates would silently break Bonsai.
- **Token leakage surface:** Embedding token-reading logic in Bonsai creates a second place where credentials are handled.

---

## Option C: Headless OpenClaw Agent with Zero Charter

### How it works

Register a new OpenClaw agent (e.g., `bim_headless`) with no AGENTS.md, no SOUL.md, no MEMORY.md, no memory search, and no session persistence. This creates a "bare metal" agent that is effectively just a model proxy with auth. Route the subprocess call through this agent instead of `bim_operator`.

### Configuration

Create a minimal agent workspace:

```bash
mkdir -p ~/Applications/Bonsai_ai/openclaw/workspaces/bim_headless
# No AGENTS.md, no SOUL.md, no MEMORY.md -- empty workspace
```

Add to `openclaw.json` agents list:

```json
{
  "id": "bim_headless",
  "name": "BIM Headless",
  "workspace": "/Users/alanknudson/Applications/Bonsai_ai/openclaw/workspaces/bim_headless",
  "model": "openai-codex/gpt-5.4",
  "memorySearch": { "enabled": false },
  "tools": { "profile": "none", "allow": [] },
  "params": { "cacheRetention": "none" }
}
```

### Code changes

In `openclaw_planner.py`, change the agent id:

```python
cmd = [
    openclaw_bin,
    "agent",
    "--agent", "bim_headless",  # was: "bim_operator"
    "--message", message,
    "--json",
    "--timeout", str(_OPENCLAW_TIMEOUT),
]
```

Also modify the message in `_build_message()` to include the full `SYSTEM_PROMPT` from `bonsai_ai_core.planner`, since the agent no longer has domain knowledge from charter files.

### Impact on output quality

**Better than current bridge, but still worse than direct planner.**
- Eliminates ~16KB of agent charter overhead
- Still lacks structured output (no `json_schema` response format) -- the model must output valid JSON from natural language instructions alone
- Still subprocess-based (startup overhead, no retry loop)
- Still single-turn (no validation/repair loop unless added to the message)
- The OpenClaw agent framework may still inject some minimal system prompt (identity, timestamp, tool preamble) even with an empty workspace

### Complexity

**Low-Medium.** New agent config + empty workspace + one-line change to agent id. But the quality gap from missing structured output remains, and debugging requires understanding what OpenClaw injects even for "empty" agents.

### Auth mechanism

Subscription auth (openai-codex OAuth) via the OpenClaw gateway. No API keys.

---

## Option D: Gateway Chat Completions with Full Prompt Parity (Recommended Implementation)

### How it works

This is the concrete implementation of Option A, designed for production. Use the gateway's `/v1/responses` endpoint (matching what `OpenAIProvider` already targets) with the `x-openclaw-model` header to route through `openai-codex/gpt-5.4`. The existing `providers.py` and `planner.py` code runs unmodified except for the endpoint URL and auth header.

### Code changes

**File: `bonsai_ai_core/providers.py`** -- Add a new provider class (~25 lines):

```python
class OpenClawGatewayProvider(OpenAIProvider):
    """OpenAI Responses API via local OpenClaw gateway (subscription auth)."""
    provider_name = "openclaw-gateway"
    endpoint = "http://127.0.0.1:18789/v1/responses"

    def __init__(self, req: ProviderRequest):
        self.req = req
        self.model = req.model or "gpt-5.4"
        self.schema = plan_schema()
        self._gateway_token = os.getenv("OPENCLAW_GATEWAY_TOKEN", "")

    def generate_plan(self) -> Dict[str, Any]:
        payload = self._build_payload()
        headers = {
            "Authorization": f"Bearer {self._gateway_token}",
            "Content-Type": "application/json",
            "x-openclaw-model": f"openai-codex/{self.model}",
        }
        response = post_json(self.endpoint, payload, headers)
        return self._extract_plan(response)
```

The `_build_payload()` method reuses the parent class logic for building the OpenAI Responses API payload with `json_schema` structured output.

**File: `bonsai_ai_core/defaults.py`** -- Add the provider:

```python
PROVIDERS = ("openai", "anthropic", "google", "openclaw-gateway")
DEFAULT_MODELS["openclaw-gateway"] = "gpt-5.4"
ENV_KEYS["openclaw-gateway"] = ("OPENCLAW_GATEWAY_TOKEN",)
```

**File: `planner.py`** -- Add the provider mapping:

```python
DEFAULT_MODELS["openclaw-gateway"] = CORE_DEFAULT_MODELS.get("openclaw-gateway", "gpt-5.4")
```

**File: `openclaw.json`** -- Enable the endpoint:

```json
{
  "gateway": {
    "http": {
      "endpoints": {
        "responses": { "enabled": true }
      }
    }
  }
}
```

**Usage from Blender UI or CLI:**

```python
result = create_plan(
    provider="openclaw-gateway",
    user_prompt="Design a 3-story office building...",
    scene_summary="Empty scene",
    api_key=os.getenv("OPENCLAW_GATEWAY_TOKEN"),
)
```

### Impact on output quality

**Identical to direct planner.** This is not an approximation -- it is the same code path:
- Same `SYSTEM_PROMPT` (2.5KB BIM domain knowledge)
- Same `json_schema` structured output with `strict: false`
- Same 3-attempt validation/repair loop in `build_plan()`
- Same `compile_core_plan()` post-processing
- Same model (`gpt-5.4`)
- Zero agent context overhead (no AGENTS.md, SOUL.md, memory, session history)

The only difference from the original `OpenAIProvider` path is the HTTP destination (localhost:18789 instead of api.openai.com) and the auth mechanism (gateway token + x-openclaw-model header instead of API key).

### Complexity

**Low.**
- 3 lines of JSON config (enable endpoint)
- 1 gateway restart
- ~25-line provider class (mostly inheriting from `OpenAIProvider`)
- ~3 lines in defaults.py
- ~1 line in planner.py
- No subprocess spawning, no JSON parsing heuristics, no token management

### Auth mechanism

Subscription auth (openai-codex OAuth) via gateway proxy. The gateway reads `auth-profiles.json`, manages token refresh, and handles all OAuth complexity. Bonsai only needs the gateway token (a static local secret).

---

## Comparison Matrix

| Criterion | A/D: Gateway Proxy | B: Token Extraction | C: Headless Agent |
|---|---|---|---|
| Output quality | Same as direct | Same as direct | Worse (no structured output) |
| Structured output | Yes (json_schema) | Yes (json_schema) | No |
| Validation/repair loop | Yes (3 attempts) | Yes (3 attempts) | No |
| Auth | Subscription (gateway-managed) | Subscription (self-managed) | Subscription (agent-managed) |
| Token refresh | Automatic (gateway) | Manual (must implement) | Automatic (gateway) |
| Code changes | ~30 lines | ~80 lines | ~5 lines |
| Config changes | 3 lines JSON + restart | None | ~10 lines JSON |
| Subprocess overhead | None | None | Yes (openclaw agent) |
| Latency vs. direct | +1-2ms (localhost hop) | Same | +500ms-2s (subprocess) |
| Fragility | Low (documented API) | High (internal format) | Medium (agent framework) |
| Maintenance burden | Minimal | Watch for auth format changes | Watch for agent framework changes |

---

## Recommendation

**Option D (Gateway Proxy with full prompt parity)** is the clear winner:

1. **Zero quality degradation** -- identical prompts, structured output, and validation
2. **Minimal code changes** -- inherits from existing `OpenAIProvider`
3. **No token management** -- the gateway handles all OAuth complexity
4. **No subprocess overhead** -- direct HTTP call, same as the current provider
5. **Documented API** -- OpenClaw's `/v1/responses` endpoint is a public interface
6. **Future-proof** -- if OpenClaw changes auth internals, the gateway API stays stable

The implementation path is:
1. Add `gateway.http.endpoints.responses.enabled: true` to `openclaw.json`
2. Run `openclaw gateway restart`
3. Add `OpenClawGatewayProvider` to `bonsai_ai_core/providers.py`
4. Register it in `defaults.py` and the provider map in `providers.py`
5. Test: `create_plan(provider="openclaw-gateway", ...)`

Option B (token extraction) is a viable fallback if the gateway HTTP API has unforeseen limitations with the Responses format, but it carries significant maintenance risk from depending on internal OpenClaw file formats.

Option C (headless agent) should be avoided -- it still runs through the subprocess/agent framework, loses structured output, and provides no quality guarantee.
