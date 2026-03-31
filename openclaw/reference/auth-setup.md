# OpenClaw Auth Setup: API Key vs Subscription

## Current Auth State

### Global Config (`~/.openclaw/openclaw.json`)
- **Default model**: `openai/gpt-5.4` (uses `openai` provider = API key billing)
- **Global auth profile**: `openai:default` with mode `api_key`
- The `lastGood` entry in each agent's auth-profiles.json points to `openai:default`

### Per-Agent Auth Profiles

All agents (bim_operator, bim_maintainer, main, etc.) share identical auth-profiles.json with two profiles:

| Profile ID             | Type    | Provider       | Billing Model          | Status      |
|------------------------|---------|----------------|------------------------|-------------|
| `openai:default`       | api_key | openai         | Per-token (pay-as-go)  | Active, `lastGood` |
| `openai-codex:default` | oauth   | openai-codex   | ChatGPT Plus subscription | Valid, expires ~10 days |

**Problem**: The `lastGood` pointer is set to `openai:default` (API key), so all requests route through the paid API even though a valid OAuth subscription token exists.

### OAuth Token Details
- **bim_operator / bim_maintainer**: Linked to `alan@techridge.com` ChatGPT Plus account
- **main agent**: Linked to `alan@sunhomes.io` ChatGPT Team account
- Both tokens have valid refresh tokens and expire in ~10 days (auto-refreshable)
- Weekly usage meter shows capacity remaining

---

## How to Switch to Subscription Mode

### Option A: Change the Default Model (Recommended)

Switch from `openai/gpt-5.4` to `openai-codex/gpt-5.4`. The `openai-codex/` prefix routes through the ChatGPT subscription OAuth instead of the API key.

```bash
# Set globally for all agents
openclaw models set openai-codex/gpt-5.4

# Or per-agent
openclaw models set openai-codex/gpt-5.4 --agent bim_operator
openclaw models set openai-codex/gpt-5.4 --agent bim_maintainer
```

Available subscription models:
```
openai-codex/gpt-5.1
openai-codex/gpt-5.1-codex-max
openai-codex/gpt-5.1-codex-mini
openai-codex/gpt-5.2
openai-codex/gpt-5.2-codex
openai-codex/gpt-5.3-codex
openai-codex/gpt-5.3-codex-spark
openai-codex/gpt-5.4
openai-codex/gpt-5.4-mini
```

### Option B: Change Auth Profile Order

If you want to keep using `openai/gpt-5.4` but route it through the subscription:

```bash
# Lock bim_operator to use the OAuth profile for openai requests
openclaw models auth order set openai-codex:default --agent bim_operator --provider openai

# Same for bim_maintainer
openclaw models auth order set openai-codex:default --agent bim_maintainer --provider openai
```

> Note: Option A is more reliable since the openai-codex provider is specifically designed for subscription routing.

### Option C: Edit Config Directly

In `~/.openclaw/openclaw.json`, change:

```json
"model": {
  "primary": "openai/gpt-5.4"
}
```

to:

```json
"model": {
  "primary": "openai-codex/gpt-5.4"
}
```

Then restart the gateway: `openclaw gateway --force`

---

## Verification

After switching, verify with:

```bash
# Check that the model now shows openai-codex prefix
openclaw models status
openclaw models status --agent bim_operator
openclaw models status --agent bim_maintainer

# Look for this in the output:
#   Default: openai-codex/gpt-5.4
#   openai-codex effective=profiles:... | oauth=1

# Quick test
openclaw agent --agent bim_operator --message "Say hello" 2>&1
```

The `models status` output should show the OAuth token being used (not the API key).

---

## Cost Implications

### Current: API Key Mode (`openai/gpt-5.4`)
- Billed per token via OpenAI API platform
- GPT-5.4 pricing: ~$2.50/1M input tokens, ~$10/1M output tokens (approximate)
- No usage caps, but costs scale with usage
- Every agent turn, tool call, and retry costs money

### After Switch: Subscription Mode (`openai-codex/gpt-5.4`)
- Included in existing ChatGPT Plus ($20/mo) or Team ($25/user/mo) subscription
- Subject to rate limits (5h rolling window, weekly cap shown in `models status`)
- Weekly usage resets on a rolling basis
- **No additional per-token cost** beyond the subscription fee
- If rate-limited, falls back to API key if configured as fallback

### Recommendation
For the bim agents which run periodic tasks and research, the subscription mode is significantly cheaper. The rate limits (5h rolling, weekly cap) are generous enough for typical agent workloads. Set the API key model as a fallback for burst scenarios:

```bash
# Set subscription as default, API key as fallback
openclaw models set openai-codex/gpt-5.4
openclaw models fallbacks set openai/gpt-5.4
```

---

## Refreshing Expired OAuth Tokens

If the OAuth token expires (check with `openclaw models status`):

```bash
# Re-login via browser OAuth flow
openclaw models auth login --provider openai-codex

# Or for a specific agent
openclaw models auth login --provider openai-codex --agent bim_operator
```

This opens a browser window to authenticate with your ChatGPT account. The refresh token auto-renews the access token, so manual refresh is rarely needed unless the refresh token itself expires.

---

## Summary of Changes Needed

1. Run: `openclaw models set openai-codex/gpt-5.4`
2. Optionally set API key as fallback: `openclaw models fallbacks set openai/gpt-5.4`
3. Verify: `openclaw models status`
4. Restart gateway if running: `openclaw gateway --force`
