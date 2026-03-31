# Prompt Engineering & Tool Use Research (2025-2026)

> Research compiled March 2026 for optimizing the BIM Planner prompt (system prompt + JSON schema + tool specs + user request) that is timing out due to size and complexity.
>
> Target models: **GPT-5.4** (OpenAI) and **Claude Opus 4.6** (Anthropic)

---

## Table of Contents

1. [OpenAI Prompt Engineering Best Practices](#1-openai-prompt-engineering-best-practices)
2. [Anthropic Prompt Engineering Best Practices](#2-anthropic-prompt-engineering-best-practices)
3. [Tool Use Design Patterns](#3-tool-use-design-patterns)
4. [Structured Output Strategies](#4-structured-output-strategies)
5. [Multi-Step vs Single-Step Planning](#5-multi-step-vs-single-step-planning)
6. [Prompt Compression Techniques](#6-prompt-compression-techniques)
7. [Actionable Recommendations for BIM Planner](#7-actionable-recommendations-for-bim-planner)

---

## 1. OpenAI Prompt Engineering Best Practices

### 1.1 GPT-5 / GPT-5.4 Prompt Structure

GPT-5 generation models represent a significant shift in how prompts should be structured. Key findings from OpenAI's official GPT-5 prompting guide:

**Instruction precision is critical.** GPT-5 follows instructions more precisely than prior models. This means poorly-constructed prompts containing contradictory or vague instructions are *more damaging* to GPT-5 than to GPT-4o because the model spends reasoning tokens reconciling conflicts instead of doing useful work. Every word in the system prompt matters more now.

**Recommended structure (CTCO pattern):**
- **Context**: What the model needs to know
- **Task**: What you want it to do
- **Constraints**: Boundaries and rules
- **Output**: Expected format and structure

**Specific GPT-5 changes:**
- Remove "personality padding" ("Take a deep breath", "You are a world-class expert") -- GPT-5.x treats this as noise.
- The model reads top to bottom; put the most important information first.
- Try zero-shot before reaching for few-shot. GPT-5 is capable enough that adding examples is sometimes unnecessary and just adds token cost.
- Pin production apps to specific model snapshots (e.g., `gpt-5-2025-08-07`).
- Use the `reasoning_effort` parameter to control how much the model reasons. Set explicit tool call budgets (e.g., "maximum of 2 tool calls") to reduce unnecessary context gathering.
- Use the `verbosity` parameter (new in GPT-5) to control final answer length separately from reasoning effort.

**Max recommended system prompt length:** No explicit hard limit is documented, but prompt caching activates automatically at 1,024+ tokens. The practical guidance is: keep system prompts concise and contradiction-free. Longer prompts are fine if they are well-structured and cached, but every additional instruction the model must reconcile costs reasoning tokens.

### 1.2 System Prompt Structure for Tool Use

From OpenAI's o3/o4-mini function calling guide and GPT-5 documentation:

- **Structure prompts for caching**: Place static content first (system instructions, few-shot examples, tool definitions) and variable content last (user messages, query-specific data). This maximizes prompt cache hit rates.
- **Front-load key rules in tool descriptions**: Function descriptions should lead with the most important usage criteria and avoid distracting details.
- **Disambiguate tool instructions maximally**: If multiple tools have overlapping purposes or vague descriptions, models may call the wrong one or hesitate to call any at all. Explicitly define tool usage boundaries in the developer prompt.
- **Discard irrelevant past tool calls/outputs**: When context gets too long, summarize and discard old tool call results. This prevents lazy model behavior from context overload.

### 1.3 Does Sending the Full JSON Schema Help or Hurt?

**For structured output**: Sending the full schema via `response_format: { type: "json_schema" }` is now the recommended approach. GPT-5.x uses a Context-Free Grammar (CFG) engine to mask invalid tokens before generation -- it literally cannot produce a non-conforming response. This is far superior to asking for JSON in the prompt.

**For tool definitions**: Always send tool schemas via the `tools` parameter, not in the system prompt text. The model is trained to understand these schemas natively. Use `strict: true` on all function definitions.

**Schema size limits**: Max 100 object properties total, max 5 levels of nesting. Keep schemas as flat as possible.

Sources:
- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [GPT-5 Prompting Guide (Cookbook)](https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide)
- [o3/o4-mini Function Calling Guide](https://developers.openai.com/cookbook/examples/o-series/o3o4-mini_prompting_guide)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-5.2 Prompting Guide (Atlabs)](https://www.atlabs.ai/blog/gpt-5.2-prompting-guide-the-2026-playbook-for-developers-agents)

---

## 2. Anthropic Prompt Engineering Best Practices

### 2.1 Claude Opus 4.6 Prompt Structure

From Anthropic's official prompting best practices documentation:

**Be clear and direct.** Think of Claude as a brilliant but new employee who lacks context on your norms. The more precisely you explain what you want, the better the result. Golden rule: show your prompt to a colleague with minimal context -- if they would be confused, Claude will be too.

**Use XML tags for structure.** XML tags help Claude parse complex prompts unambiguously, especially when mixing instructions, context, examples, and variable inputs. Use consistent, descriptive tag names (e.g., `<instructions>`, `<context>`, `<input>`) and nest tags for hierarchical content.

**Provide 3-5 examples for best results.** Wrap examples in `<example>` tags so Claude distinguishes them from instructions. Examples are one of the most reliable ways to steer Claude's output format, tone, and structure.

**Long context prompting (critical for BIM planner):**
- Put longform data (documents, schemas) at the **top** of the prompt, above your query and instructions.
- Queries at the end can improve response quality by up to 30% in tests, especially with complex, multi-document inputs.
- Structure documents with XML tags: `<document index="1"><source>...</source><document_content>...</document_content></document>`.
- Ask Claude to quote relevant parts before carrying out its task (grounding in quotes).

**Claude 4.6 specific considerations:**
- Claude Opus 4.6 is more responsive to the system prompt than previous models. If prompts were designed to reduce undertriggering on tools, they may now overtrigger. Dial back aggressive language like "CRITICAL: You MUST use this tool when..." to "Use this tool when...".
- Claude 4.6 does significantly more upfront exploration than previous models. If this causes excessive latency, add: "Choose an approach and commit to it. Avoid revisiting decisions unless you encounter new information that directly contradicts your reasoning."
- Use the `effort` parameter to control thinking depth. Lower effort settings reduce latency significantly.
- Prefilled responses on the last assistant turn are deprecated. Use structured outputs or explicit instructions instead.

### 2.2 How Claude Handles Long vs Short System Prompts

**Long system prompts work well if structured properly.** Claude's 200K context window can handle massive inputs, but:
- Large, complex system prompts may trigger more adaptive thinking than needed, inflating thinking tokens and slowing responses.
- Counter with: "Extended thinking adds latency and should only be used when it will meaningfully improve answer quality -- typically for problems that require multi-step reasoning. When in doubt, respond directly."
- Use the `effort` parameter: `"low"` for high-volume or latency-sensitive workloads, `"medium"` for most applications, `"high"` for complex reasoning.

**Prompt caching is the key enabler for large prompts.** With caching, a 100K-token prompt drops from 11.5s to 2.4s latency (up to 85% reduction). Cache reads cost only 10% of standard input price.

### 2.3 Prompt Caching Details (Anthropic)

**Cache hierarchy**: `tools` -> `system` -> `messages`. Changes at any level invalidate that level and all subsequent levels.

**Minimum cacheable tokens by model:**

| Model | Minimum Tokens |
|---|---|
| Claude Opus 4.6, 4.5 | 4,096 |
| Claude Sonnet 4.6 | 2,048 |

**How to enable:**
```json
{
  "cache_control": {"type": "ephemeral"},
  "system": "Your system prompt...",
  "messages": [...]
}
```

Or use explicit breakpoints on individual content blocks (up to 4 per request) for fine-grained control.

**TTL options:**
- 5-minute (default): write cost is 1.25x base input price, reads are 0.1x
- 1-hour: write cost is 2x base input price, reads are 0.1x

**Critical for BIM planner**: Cache tool definitions by placing `cache_control` on the last tool in the `tools` array. Cache system prompt separately. Changes to tool definitions invalidate the entire cache.

**Best structure for multi-turn caching:**
1. Tool definitions (rarely change) -- cache breakpoint 1
2. System instructions (stable) -- cache breakpoint 2
3. Reference documents/schemas -- cache breakpoint 3
4. Conversation history -- cache breakpoint 4

Sources:
- [Anthropic Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Claude Prompt Engineering (PromptBuilder)](https://promptbuilder.cc/blog/claude-prompt-engineering-best-practices-2026)

---

## 3. Tool Use Design Patterns

### 3.1 How Many Tools Is Too Many?

**OpenAI (GPT-5.x):**
- Fewer than ~100 tools and fewer than ~20 arguments per tool is considered "in-distribution" (trained for). But even within these bounds, more tools increase ambiguity and reasoning latency.
- A common failure mode is an "overgrown tool set that introduces ambiguity about which tool should be invoked."
- GPT-5.4 supports `tool_search` for deferred tool loading -- tools are discovered on demand rather than loaded all at once.

**Anthropic (Claude):**
- Tool selection accuracy degrades significantly once you exceed **30-50 available tools**.
- A typical 5-server MCP setup (GitHub, Slack, Sentry, Grafana, Splunk) can consume ~55K tokens in tool definitions before the conversation starts. Adding Jira alone adds ~17K tokens.
- Claude's tool search tool reduces this by **85%** in token usage, loading only 3-5 tools per request.
- With tool search, Opus 4 accuracy improved from 49% to 74% on MCP evaluations.

**Recommendation for BIM planner (15+ tools):** This is in the zone where both providers recommend optimization. Use deferred loading / tool search on both platforms.

### 3.2 Tool Schemas: In System Prompt or Tools Parameter?

**Both OpenAI and Anthropic agree**: Tool schemas belong in the `tools` parameter, NOT in the system prompt.

**OpenAI**: "Our o3/o4-mini models are trained to understand and use [tool] schemas natively." The API constructs an internal system prompt from tool definitions automatically.

**Anthropic**: When you call the API with the `tools` parameter, the API constructs a special system prompt from tool definitions. Putting tools in both places wastes tokens.

**If your BIM planner embeds tool schemas inside the system prompt text, move them to the `tools` parameter.** This alone could significantly reduce prompt size and improve accuracy.

### 3.3 Handling Complex Nested Schemas

**OpenAI:**
- Max 100 object properties total, max 5 levels of nesting.
- "Err on the side of making the arguments flat" rather than deeply nested.
- Flat structures are easier for models to reason about, reducing parsing errors and omitted fields.
- Use enums to constrain inputs to known valid values.
- Use `minItems`, `maxItems`, `minLength`, `maxLength` to set boundaries.

**Anthropic:**
- Consolidate related operations into fewer tools. Rather than `create_pr`, `review_pr`, `merge_pr`, group them into a single tool with an `action` parameter.
- Use meaningful namespacing: `github_list_prs`, `slack_send_message`.
- Provide extremely detailed descriptions (at least 3-4 sentences per tool, more for complex tools).
- Use `input_examples` for complex tools with nested objects. Each example costs ~20-50 tokens (simple) to ~100-200 tokens (complex).
- Design tool responses to return only high-signal information.

### 3.4 Deferred Loading / Tool Search (CRITICAL for BIM Planner)

Both OpenAI and Anthropic now offer deferred tool loading, which is the single most impactful optimization for systems with many tools.

**Anthropic's Tool Search:**
```json
{
  "tools": [
    {"type": "tool_search_tool_regex_20251119", "name": "tool_search_tool_regex"},
    {
      "name": "bim_place_wall",
      "description": "Place a wall element in the BIM model...",
      "input_schema": {...},
      "defer_loading": true
    }
  ]
}
```
- Keep 3-5 most frequently used tools as non-deferred.
- Deferred tools do NOT consume context until Claude needs them.
- Deferred tools are appended inline, preserving prompt caching.
- Max 10,000 tools in catalog, returns 3-5 per search.
- Works with Sonnet 4.0+ and Opus 4.0+ only.

**OpenAI's Tool Search (GPT-5.4+):**
```json
{
  "tools": [
    {"type": "tool_search", "name": "tool_search"},
    {
      "type": "function",
      "function": {"name": "bim_place_wall", ...},
      "defer_loading": true
    }
  ]
}
```
- Discovered tools are injected at the end of the context window, preserving cache.
- Available on GPT-5.4 and later (not GPT-5.4 nano).

Sources:
- [Anthropic Tool Search Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [Anthropic Define Tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Anthropic Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [OpenAI Tool Search](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [o3/o4-mini Function Calling Guide](https://developers.openai.com/cookbook/examples/o-series/o3o4-mini_prompting_guide)

---

## 4. Structured Output Strategies

### 4.1 OpenAI: Use `response_format` with JSON Schema (Not Prompt-Based JSON)

**Structured Outputs with `response_format: { type: "json_schema" }` is now the production standard.** It uses constrained decoding (CFG engine) to guarantee 100% schema compliance. The model literally cannot produce invalid JSON.

**Two approaches:**
1. **Function calling** (tool use): Use when connecting to external systems. Set `strict: true` on all function definitions.
2. **Response format** (`json_schema`): Use when you want the model's direct output in JSON (data extraction, structured reports).

**For the BIM planner**: If you need the model to output a plan as structured JSON, use `response_format` with your plan schema. If you need the model to invoke BIM operations, use function calling with `strict: true`.

**Key constraints:**
- Schema max: 100 object properties, 5 nesting levels
- All fields must be required (use Union types with null for optional fields)
- `additionalProperties: false` must be set on all objects
- Always check `message.refusal` before parsing (refusal is a new failure mode)

**JSON Mode (`type: "json_object"`) is now considered legacy.** Always prefer JSON Schema mode.

### 4.2 Anthropic: Structured Outputs (GA since late 2025)

Anthropic offers two complementary features:

1. **JSON outputs** (`output_config.format`): Control Claude's response format.
```json
{
  "output_config": {
    "format": {
      "type": "json_schema",
      "schema": {
        "type": "object",
        "properties": {...},
        "required": [...],
        "additionalProperties": false
      }
    }
  }
}
```

2. **Strict tool use** (`strict: true`): Guarantee schema validation on tool inputs.

**Performance note:** Expect 100-300ms overhead on the first request with a new schema while Claude compiles the grammar. After that, it is cached for 24 hours.

**For the BIM planner**: Use strict tool use (`strict: true`) on all tool definitions for guaranteed schema compliance. Use JSON outputs mode if you need the model's direct response in a structured format.

### 4.3 Which Approach Produces More Reliable Output?

| Approach | Structural Validity | Semantic Quality | Notes |
|---|---|---|---|
| Prompt-based ("return JSON") | 80-95% | Good | Fails on complex schemas |
| OpenAI JSON Mode | 100% syntactically valid | Good | No schema enforcement |
| OpenAI JSON Schema | 100% schema-compliant | Good | Production standard |
| Anthropic Strict Tool Use | 100% schema-compliant | Good | Use for tool inputs |
| Anthropic JSON Outputs | 100% schema-compliant | Good | Use for direct responses |

**Both OpenAI and Anthropic constrained decoding produce 100% structural compliance.** However, structural validity does not guarantee semantic accuracy -- the values in the fields still depend on prompt quality.

**Recommendation**: Always use constrained decoding (strict schemas) instead of prompt-based JSON. This eliminates an entire class of parsing failures and retries.

Sources:
- [OpenAI Structured Outputs Guide](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [OpenAI Structured Outputs Practical Guide (Team 400)](https://team400.ai/blog/2026-03-openai-structured-outputs-practical-guide)
- [Anthropic Structured Outputs (Towards Data Science)](https://towardsdatascience.com/hands-on-with-anthropics-new-structured-output-capabilities/)

---

## 5. Multi-Step vs Single-Step Planning

### 5.1 The Two Paradigms

**Single-step (ReAct):** Thought -> Action -> Observation -> Repeat. The model looks at current state, decides one action, executes it, observes the result, and repeats. Good for straightforward or highly uncertain tasks.

**Multi-step (Plan-and-Execute):** The model generates a complete multi-step plan first, then an executor handles each step. Advantages:
- Forces the model to "think through" all steps upfront (proven prompting technique for better outcomes).
- Keeps the agent aligned with original intent across many steps.
- Can use a lighter-weight model for execution steps.
- Each sub-task can run without an additional expensive LLM call.

**Tradeoffs of Plan-and-Execute:**
- Higher latency (plan step + execution steps).
- Multiple LLM calls raise compute costs.
- Plans may need revision if early steps produce unexpected results.

### 5.2 Hybrid Approach: Pre-Act (2025)

**Pre-Act** (from recent research) combines both: the model generates a multi-step plan with detailed reasoning for each step, then executes sequentially, incorporating past observations and refining the plan. This outperforms both pure ReAct and pure Plan-and-Execute on most benchmarks.

### 5.3 How Commercial AI Coding Tools Handle This

**Claude Code**: Thinks before it writes -- shows its reasoning process analyzing the codebase, forming a plan, then executing. Uses the full 200K context window for architectural understanding. Maintains state across extended sessions with exceptional state tracking.

**Cursor (Agent Mode)**: Uses Composer with 20x scaled reinforcement learning for multi-file editing. Supports up to 8 parallel agents. Focuses on "structured, scoped prompts yield the most reliable results" from their GPT-5 integration work.

**Windsurf (Plan Mode / Cascade)**: Analyzes the full task scope and creates a structured plan before writing code. Maintains persistent session context and understands downstream dependency effects.

### 5.4 Recommendation for BIM Planner

**Use a two-phase approach:**

1. **Phase 1 (Plan)**: Ask the model to generate a structured plan (using structured output / JSON schema). This plan includes all BIM operations needed, their order, and dependencies. Use a smaller/faster model or lower effort setting.

2. **Phase 2 (Execute)**: Feed the plan back and have the model (or a simpler executor) issue tool calls one at a time, validating each step.

**Why not all-in-one**: Asking for ALL actions in one massive response with a massive prompt is likely what is causing the timeout. The model must reason about the entire schema, all tools, and generate a complete response in a single forward pass. Breaking it into plan-then-execute reduces the cognitive load per call.

Sources:
- [LangChain Plan-and-Execute Agents](https://blog.langchain.com/planning-agents/)
- [Pre-Act: Multi-Step Planning (arXiv)](https://arxiv.org/html/2505.09970v2)
- [Plan-and-Act (arXiv)](https://arxiv.org/html/2503.09572v3)
- [Cursor vs Windsurf vs Claude Code 2026 Comparison](https://dev.to/pockit_tools/cursor-vs-windsurf-vs-claude-code-in-2026-the-honest-comparison-after-using-all-three-3gof)

---

## 6. Prompt Compression Techniques

### 6.1 Can You Reduce Prompt Size Without Losing Quality?

**Yes. For most use cases, 60-70% compression with >90% quality retention is achievable.**

### 6.2 Technique: Structured Formatting

Express verbose instructions in compact, semi-structured formats (JSON, bullet points, tables). This typically reduces token count while improving model interpretation. Reduces ambiguity.

**Before (verbose):**
```
When the user asks you to place a wall, you should use the place_wall tool.
The wall needs to have a start point and an end point. The start point should
be specified as x and y coordinates. The end point should also be specified as
x and y coordinates. The wall also needs a height, which should be in meters.
You can optionally specify the wall type, which can be "interior", "exterior",
or "partition".
```

**After (structured):**
```xml
<tool_usage name="place_wall">
  Required: start_point(x,y), end_point(x,y), height(meters)
  Optional: wall_type(interior|exterior|partition)
  When: user requests wall placement
</tool_usage>
```

### 6.3 Technique: Schema Summarization / Examples Instead of Full Schemas

**Finding: Full schemas via the `tools` parameter or `response_format` are better than examples for structural compliance.** The constrained decoding engines in both GPT-5.x and Claude 4.x guarantee 100% schema compliance, which examples cannot do.

**However**, for *semantic guidance* (helping the model understand WHAT values to put in the fields), examples are superior. The recommended hybrid approach:

1. Put the schema in the `tools` parameter or `response_format` (for structural guarantee).
2. Add 1-3 `input_examples` (Anthropic) or few-shot examples in the system prompt (OpenAI) for semantic guidance.
3. Each example costs ~20-200 tokens but dramatically improves output quality for complex inputs.

### 6.4 Technique: Remove Redundant Information

Things to cut from BIM planner prompt:
- **Personality/role padding**: "You are an expert BIM architect with 20 years of experience..." -> "You are a BIM planning assistant."
- **Redundant schema descriptions**: If schemas are in the `tools` parameter, do NOT also describe them in the system prompt.
- **Over-specified obvious behaviors**: If the model naturally does something right, don't waste tokens instructing it.
- **Verbose error handling instructions**: GPT-5 and Claude 4.6 handle errors well by default.

### 6.5 Technique: Reference-Based Prompting

Instead of including the full specification in every request, store it externally and give the model a condensed reference:

```
Follow the BIM operation schema as defined in the tools parameter.
Key rules:
- All coordinates are in meters, origin at bottom-left
- Wall heights default to 2.7m if not specified
- Operations execute in array order
```

This replaces pages of detailed specification with a few key rules, relying on the schema definitions in the tools parameter for structural details.

### 6.6 Technique: Algorithmic Compression (LLMLingua)

Microsoft Research's LLMLingua library uses a small language model to identify and remove unimportant tokens. This is a code-level solution that can compress prompts at the token level. Useful for compressing large context documents, less applicable to system prompts (which should be hand-optimized).

### 6.7 Prompt Caching as "Compression"

Prompt caching doesn't reduce the prompt size, but it eliminates the latency and cost penalty of large prompts:

| Provider | Min Tokens | Latency Reduction | Cost Reduction |
|---|---|---|---|
| OpenAI | 1,024 | Up to 80% | Up to 90% on cached tokens |
| Anthropic (Opus 4.6) | 4,096 | Up to 85% | 90% on cached reads |

**For the BIM planner**: If the system prompt + tool definitions + schemas are mostly static, caching should eliminate the timeout issue for repeat requests. The first request may still be slow.

Sources:
- [Prompt Compression Guide (MasterPrompting)](https://masterprompting.net/blog/prompt-compression-guide)
- [LLMLingua (Microsoft Research)](https://medium.com/@sahin.samia/prompt-compression-in-large-language-models-llms-making-every-token-count-078a2d1c7e03)
- [OpenAI Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

---

## 7. Actionable Recommendations for BIM Planner

### Priority 1: Move Tool Schemas to the `tools` Parameter (Immediate Win)

If the BIM planner currently embeds JSON schemas in the system prompt text, move them to the `tools` parameter with `strict: true`. This:
- Reduces system prompt size (schemas are no longer duplicated)
- Improves tool selection accuracy (models are trained on the tools parameter)
- Enables constrained decoding (guaranteed schema compliance)
- Enables prompt caching on tool definitions separately from the system prompt

### Priority 2: Enable Deferred Tool Loading (Biggest Impact)

With 15+ tool types, the BIM planner is in the zone where tool definition bloat causes significant problems. Enable tool search / deferred loading:

**For Anthropic:**
- Add `tool_search_tool_regex_20251119` or `tool_search_tool_bm25_20251119` to the tools list.
- Set `defer_loading: true` on all but the 3-5 most frequently used tools.
- Expected result: ~85% reduction in tool definition tokens.

**For OpenAI (GPT-5.4):**
- Add `tool_search` to the tools list.
- Set `defer_loading: true` on rarely-used tools.
- Discovered tools are injected at end of context, preserving cache.

### Priority 3: Enable Prompt Caching (Latency Fix)

**For Anthropic:**
```json
{
  "cache_control": {"type": "ephemeral"},
  "tools": [...tools with cache_control on last tool...],
  "system": [{
    "type": "text",
    "text": "...",
    "cache_control": {"type": "ephemeral"}
  }],
  "messages": [...]
}
```

**For OpenAI:** Automatic for prompts over 1,024 tokens. Structure prompts with static content first and dynamic content last. Use `prompt_cache_key` for consistent routing.

### Priority 4: Use Structured Outputs Instead of Prompt-Based JSON

Replace any "please return JSON in this format..." instructions with:
- OpenAI: `response_format: { type: "json_schema", json_schema: {...} }`
- Anthropic: `output_config: { format: { type: "json_schema", schema: {...} } }`

This guarantees structural compliance and removes the need for lengthy format instructions in the prompt.

### Priority 5: Adopt Plan-Then-Execute Architecture

Instead of one massive prompt that asks for all BIM operations at once:

1. **Plan call** (fast, lower effort):
   - Send: condensed system prompt + user request + planning schema
   - Receive: structured plan (list of operations, order, dependencies)
   - Use `effort: "medium"` (Claude) or `reasoning_effort: "medium"` (OpenAI)

2. **Execute loop** (per-operation):
   - For each planned operation, invoke the specific tool
   - Validate each result before proceeding
   - Can use a cheaper/faster model for execution

This approach:
- Reduces per-call prompt size dramatically
- Prevents timeout on the planning step
- Allows validation between steps
- Is the pattern used by Cursor, Claude Code, and Windsurf

### Priority 6: Compress the System Prompt

Apply these compression techniques to the system prompt:
1. Remove personality/role padding and verbose instructions
2. Use XML tags (Claude) or structured sections (OpenAI) for clear hierarchy
3. Replace verbose rule descriptions with concise bullet points
4. Remove any tool/schema descriptions that duplicate the `tools` parameter
5. Add 1-2 focused `input_examples` instead of verbose format instructions
6. Target 60-70% reduction from current size

### Priority 7: Flatten and Simplify Schemas

For both providers:
- Flatten deeply nested objects where possible (max 5 levels on OpenAI)
- Use enums instead of string descriptions for constrained values
- Remove optional fields that are rarely used (move them to advanced/deferred tools)
- Set explicit bounds: `minItems`, `maxItems`, `minLength`, `maxLength`
- Consolidate related operations: instead of separate tools for wall/door/window placement, consider a single `place_element` tool with an `element_type` parameter

### Summary: Expected Impact

| Optimization | Token Reduction | Latency Impact | Implementation Effort |
|---|---|---|---|
| Move schemas to `tools` param | 20-40% | Moderate improvement | Low |
| Deferred tool loading | ~85% of tool tokens | Major improvement | Medium |
| Prompt caching | 0% (size stays same) | Up to 85% latency reduction | Low |
| Structured outputs | 5-10% (removes format instructions) | Slight improvement | Low |
| Plan-then-execute architecture | 50-70% per call | Major improvement | High |
| System prompt compression | 30-50% of system prompt | Moderate improvement | Medium |
| Schema flattening | 10-20% of tool definitions | Minor improvement | Medium |

**Combined, these optimizations could reduce the effective prompt from its current size to 15-25% of the original, with latency improvements of 70-90% on cached requests.**
