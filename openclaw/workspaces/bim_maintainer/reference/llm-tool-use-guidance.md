# LLM Tool Use Guidance for Complex Multi-Step Tasks

> Date: 2026-03-30
> Author: Claude Opus 4.6 (web research synthesis)
> Status: Reference document
> Purpose: Inform BIM system architecture decisions with latest vendor guidance and research

---

## Executive Summary

Both OpenAI and Anthropic have converged on a clear pattern for complex multi-step tasks: **let the model generate code (or a structured spec) rather than making hundreds of individual tool calls**. This directly validates our spec-first architecture for building generation. The research also shows that iterative feedback loops outperform one-shot generation, and that tool count beyond ~15-20 degrades selection accuracy unless tools are sharply distinct.

---

## Part 1: Vendor Guidance on Tool Use Architecture

### 1.1 OpenAI's Position (as of March 2026)

**Source: [A Practical Guide to Building Agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) (April 2025, still canonical)**

Key recommendations:

- **Start narrow.** Add tools only when they remove a real manual loop. Do not wire in every system from the start. Start with one or two that clearly add value, then expand.
- **Tool count is about clarity, not number.** The issue is not solely the number of tools but their similarity or overlap. Some implementations successfully manage more than 15 well-defined, distinct tools while others struggle with fewer than 10 overlapping tools.
- **Soft limit: ~20 tools per turn.** OpenAI recommends aiming for fewer than 20 functions available at the start of any turn. Use tool search (deferred loading) to manage larger tool surfaces.
- **Hard boundary: ~100 tools.** Any setup with fewer than ~100 tools and fewer than ~20 arguments per tool is considered "in-distribution" and should perform within expected reliability bounds. Beyond that, ambiguity and confusion increase.
- **Use o-series for planning, GPT-series for execution.** Most AI workflows should combine both -- o-series for agentic planning and decision-making, GPT-series for task execution.
- **Structured outputs for data, function calling for actions.** Use `response_format` (structured output) when you need the model's response to follow a specific JSON schema. Use function calling when you need the model to invoke external tools or APIs. For building specs, **structured output is the right pattern** -- you want a JSON schema, not a function call.

**Source: [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/)**

- Two orchestration modes: LLM-directed (model chooses tools) vs code-directed (your code manages flow).
- **Code-directed orchestration** uses structured outputs to generate well-formed data that code inspects, then chains agents by transforming output of one into input of the next.
- The SDK automatically handles the agent loop: calling tools over multiple turns, handoffs between agents, and guardrails on inputs/outputs.

**Source: [Code Interpreter](https://developers.openai.com/api/docs/guides/tools-code-interpreter)**

- The Code Interpreter pattern: model writes Python code, executes it in a sandbox, sees results, and iterates until it works.
- A model can write code that fails to run and keep rewriting and running that code until it succeeds -- self-healing iteration.
- This is the closest parallel to our "AI writes a build script" idea (see Part 3.4).

### 1.2 Anthropic's Position (as of March 2026)

**Source: [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)**

The most successful implementations use simple, composable patterns, not complex frameworks:

1. **Augmented LLM** -- the foundational building block. An LLM enhanced with retrieval, tools, and memory.
2. **Prompt chaining** -- decompose a task into sequential steps, each LLM call processing the output of the previous one. Add programmatic checks on intermediate steps.
3. **Routing** -- classify input and direct to specialized handlers.
4. **Parallelization** -- break into independent subtasks run simultaneously (sectioning) or run the same task multiple times for diverse outputs (voting).
5. **Evaluator-optimizer** -- generator produces output, evaluator provides critical feedback, iterate.

Key architectural distinction: **Workflows** are systems where LLMs and tools are orchestrated through predefined code paths. **Agents** are systems where LLMs dynamically direct their own processes and tool usage. Anthropic recommends workflows for well-defined tasks and agents only when flexibility is essential.

**Source: [Programmatic Tool Calling (PTC)](https://www.anthropic.com/engineering/advanced-tool-use) -- GA as of February 2026**

This is Anthropic's most important recent advancement for our use case:

- **Instead of one tool call per round trip**, Claude writes a Python script that orchestrates the entire workflow. The script runs in a sandboxed environment, pausing when it needs results from your tools.
- **Massive efficiency gains**: In one test case, token usage dropped from 150,000 to 2,000. Eliminates 19+ inference passes when orchestrating 20+ tool calls.
- **Better accuracy**: By writing explicit orchestration logic in code, Claude makes fewer errors than when juggling multiple tool results in natural language.
- **When to use PTC**: When the workflow is genuinely programmatic -- iteration, conditional branching, data aggregation, retry logic, or composition that would otherwise require many sequential model invocations.
- **When NOT to use PTC**: When your agent orchestrates a small number of well-defined API calls in a fixed order.

**Direct implication for BIM**: PTC is essentially what our spec-first system does. The model produces code/spec, deterministic code expands it. Anthropic has validated this pattern as superior to per-action tool calling.

**Source: [Claude Computer Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)**

Computer Use runs a continuous screenshot-analyze-act loop:
1. Take a screenshot
2. Analyze (identify UI elements, read text, understand state)
3. Decide next action (click, type, scroll)
4. Execute action, take another screenshot, verify it worked
5. Continue until done

This is the **per-action model** -- one action per turn, with visual feedback between each action. It works for GUI interaction where the state space is unpredictable. But for building generation where the output is fully determined by input parameters, this approach is wasteful. Computer Use is evidence that per-action tool calling works when you NEED state feedback between actions, but should be avoided when deterministic expansion is possible.

### 1.3 Multi-Agent Research System (Anthropic)

**Source: [How We Built Our Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)**

- Lead agent decomposes queries into subtasks and describes them to subagents.
- Each subagent needs: an objective, an output format, guidance on tools/sources, and clear task boundaries.
- 57% of organizations now deploy multi-step agent workflows (2026 industry data).

---

## Part 2: Research on Scripts vs Specs vs Tool Calls

### 2.1 The Self-Spec Paper (2025-2026)

**Source: [Self-Spec: Model-Authored Specifications for Reliable LLM Code Generation](https://openreview.net/forum?id=6pr7BUGkLp)**

First systematic study of letting an LLM design its own spec language:
- Simple, model-agnostic approach: (i) design a compact spec schema, (ii) instantiate it from the problem description, (iii) resolve ambiguities via Q&A loop, (iv) generate code only from the confirmed spec.
- **Results on HumanEval (pass@1)**: GPT-4o 87% -> 92% (+5), Claude 3.7 92% -> 94% (+2).
- The spec acts as an intermediate representation that reduces ambiguity before code generation.

**Implication**: This validates our two-phase approach (spec -> code). The spec is a forcing function that makes the AI commit to design decisions before computing coordinates.

### 2.2 Specification-Driven Code Generation (SANER 2026)

**Source: [Understanding Specification-Driven Code Generation with LLMs](https://arxiv.org/html/2601.03878)**

- Introducing a specification intermediate makes assumptions explicit, reduces drift, and materially improves outcomes compared to direct NL prompting.
- The **spec-test-implement** ordering is effective: write the spec, generate tests from the spec, then generate code that passes the tests.
- The CURRANTE tool uses a three-stage workflow: Specification -> Tests -> Function.

**Implication**: For BIM, this maps to: BuildingSpec (JSON) -> Validation checks -> IFC generation. Our architecture already follows this pattern.

### 2.3 Spec-Driven Development in Practice (Thoughtworks 2025)

**Source: [Spec-Driven Development](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)**

Spec-driven development is emerging as one of 2025's key new AI-assisted engineering practices, with growing adoption heading into 2026.

### 2.4 Code Generation vs Structured Data: Which is Better?

The research points to a nuanced answer:

**Structured specs are better for:**
- Making design intent explicit and reviewable
- Ensuring reproducibility (same spec = same output)
- Validation (a schema can be checked before execution)
- Separation of concerns (AI handles design, code handles math)

**Code generation is better for:**
- Tasks requiring iteration, conditionals, and error handling
- Complex orchestration with many steps
- Self-healing workflows (write code, run it, fix errors, repeat)
- Cases where the "spec" is implicitly embedded in the logic

**For BIM building generation specifically**: Structured specs win. The AI's job is to make ~16-25 design decisions (footprint, grid spacing, story heights, structural sections). Deterministic Python handles the ~8,000 tokens of coordinate math. Asking the AI to generate the Python script would conflate design decisions with coordinate computation, making errors harder to detect and the output harder to validate.

---

## Part 3: Answers to Key Architecture Questions

### 3.1 Scripts vs Specs vs Tool Calls

**Answer: Specs, validated by research.**

| Approach | Pros | Cons | For BIM? |
|----------|------|------|----------|
| **Per-action tool calls** | Feedback after each action; flexible | Hundreds of round trips; token-expensive; error propagation | No. 522 elements = 522+ round trips. |
| **AI-generated Python script** | LLMs are good at code; self-contained | Conflates design + math; hard to validate; no schema checking | Maybe for patches, not for full buildings. |
| **Structured spec (JSON)** | Schema-validated; reviewable; deterministic expansion; small token count | Less flexible; generators must be pre-built | Yes. 200-400 tokens vs 8,000. |

The Self-Spec research (Section 2.1) shows that specs improve code generation quality. Our architecture goes further: the spec IS the AI output, and the code is pre-written (generators). This is the most reliable pattern.

**Hybrid approach**: For small repairs/patches, AI-generated Python scripts (like our existing patch scripts) remain effective. The script approach works when the task is bounded and the AI can see the results. For full building generation, specs are superior.

### 3.2 Single Big Output vs Iterative Small Outputs

**Answer: Iterative, with caveats.**

Research findings:
- Running multiple smaller inference passes can match or surpass a single large-model inference, given the same compute budget.
- Models do not use their context uniformly; performance degrades as input length grows ("context rot").
- The evaluator-optimizer pattern (Anthropic) explicitly recommends iterative refinement.
- But: each iteration adds latency. For a building spec of ~200-400 tokens, a single output is practical.

**Recommended approach for BIM**:
1. **Phase 1**: Single-shot spec generation (~200-400 tokens). This is small enough that quality degradation from length is not a concern.
2. **Phase 2**: Validation feedback loop. Run the spec through validators, report issues back to the model, let it fix them.
3. **Phase 3**: Visual feedback. Render the model, show it to the user (or an evaluator agent), iterate on design.

This gives us the speed of single-shot generation with the quality of iterative refinement.

### 3.3 Tool Count: How Many Is Too Many?

**Answer: Our 15+ tools are in the danger zone. Consolidate to ~8-10 sharp tools.**

Evidence:
- OpenAI: "Fewer than ~20 functions per turn" is the soft recommendation, but "the issue isn't solely the number but their similarity or overlap."
- OpenAI: Up to ~100 tools is "in-distribution" but performance depends on clarity and distinctness.
- Anthropic: Use tool search (deferred loading) for large tool surfaces. Only expose relevant tools per turn.
- Berkeley Function Calling Leaderboard: Selection accuracy degrades with similar-sounding tools.

**Practical recommendations**:
1. **Audit for overlap**: If `create_wall` and `create_curtain_wall` and `create_partition_wall` are separate tools, consolidate into `create_wall(type="curtain")`.
2. **Use tool search / deferred loading**: Don't expose all 15+ tools every turn. Load structural tools for structural tasks, MEP tools for MEP tasks.
3. **Consider the spec-first bypass**: If the AI generates a spec instead of calling tools, you need exactly ONE tool: `generate_building(spec)`. The tool count problem disappears entirely.

### 3.4 The Code Interpreter Pattern for BIM

**Answer: Viable for patches, not recommended for full generation.**

The Code Interpreter pattern (OpenAI) and Programmatic Tool Calling (Anthropic PTC) both follow the same idea: the AI writes Python code that calls tools, executes it, sees results, iterates.

For BIM, this would mean:
- AI writes a Python script that calls `ifcauthor.create_column(...)`, `ifcauthor.create_beam(...)`, etc.
- Script executes against the IFC API
- AI sees the resulting model (or errors), fixes the script, re-runs

**Why this partially works**: Our existing patch scripts (patch_five_story_beams.py, patch_five_story_openings.py) already follow this pattern. They contain ~25% design intent and ~50% deterministic math. They work well for bounded tasks.

**Why specs are still better for full buildings**: A 5-story building requires ~522 elements. A Python script generating all of them would be ~300+ lines of code. This exceeds the "sweet spot" for LLM code generation reliability. A spec is 30-50 lines of JSON. The generators are pre-validated Python that have been tested. Errors in the spec are caught by schema validation BEFORE any IFC operations.

**Hybrid recommendation**: Use the Code Interpreter / PTC pattern for:
- Ad-hoc repairs and patches (bounded scope)
- Custom elements that don't fit the spec schema
- One-off modifications to existing models

Use the spec pattern for:
- Full building generation
- Major renovations / redesigns
- Anything that benefits from reproducibility

### 3.5 Feedback Loops in Tool Use

**Answer: Essential. Both vendors agree.**

**OpenAI's approach**:
- Multi-turn tool use: model calls tool, sees result, decides next action.
- Code Interpreter: write code, execute, see errors, fix, re-execute.
- Agents SDK: automatic agent loop handles tools over multiple turns.

**Anthropic's approach**:
- Evaluator-optimizer pattern: generator produces output, evaluator provides critical feedback, iterate.
- Reasoning continuity: thinking blocks capture step-by-step reasoning; tool results include original thinking so Claude continues from where it left off.
- Critical best practice: "Grade what the agent produced, not the path it took." Checking specific tool call sequences is too rigid.

**For BIM building design, the recommended feedback loop**:

```
User request
    |
    v
[AI generates BuildingSpec JSON]
    |
    v
[Schema validation] -- errors? --> [AI fixes spec] --> loop
    |
    v
[Deterministic generators produce IFC]
    |
    v
[Structural validation] -- issues? --> [AI revises spec] --> loop
    |
    v
[Visual render / clash detection]
    |
    v
[User review] -- changes? --> [AI modifies spec] --> loop
    |
    v
Final model
```

Each loop iteration is cheap: the AI only revises the 200-400 token spec, not the 8,000-token IFC output. Validators provide structured feedback that the AI can act on. The model never needs to track coordinate state -- it only reasons about design decisions.

---

## Part 4: Synthesis -- What This Means for Our BIM Architecture

### 4.1 The Spec-First Architecture Is Validated

Both OpenAI and Anthropic, plus academic research (Self-Spec, SANER 2026 studies), converge on the same conclusion: **structured specifications outperform direct generation for complex, multi-step tasks**. Our spec-first design (see spec-first-design.md) aligns with industry best practice.

### 4.2 Anthropic's PTC Is Our Architecture

Anthropic's Programmatic Tool Calling (PTC) pattern is architecturally identical to what we're building:
- Instead of per-action tool calls, the model produces a structured orchestration plan
- Deterministic code expands it
- The model only sees summaries/results, not every intermediate state
- Token usage drops dramatically (150K -> 2K in Anthropic's example; our equivalent is 8,000 -> 400)

### 4.3 Recommended Architecture Stack

```
Layer 1: AI Design Agent
  - Input: User request + building program + site constraints
  - Output: BuildingSpec JSON (200-400 tokens)
  - Pattern: Structured output (OpenAI response_format / Anthropic tool_use)
  - Tools needed: 1 (generate_building) or 0 (pure structured output)

Layer 2: Validation Pipeline
  - Schema validation (JSON Schema)
  - Structural rules (spans, loads, code compliance)
  - Spatial validation (no overlaps, proper connections)
  - Pattern: Deterministic code, no AI needed

Layer 3: IFC Generation
  - Deterministic Python generators expand spec -> IFC
  - Pattern: Pure code, no AI needed

Layer 4: Feedback Loop
  - Render + validate results
  - Feed structured feedback to AI
  - AI revises spec (not IFC, not coordinates)
  - Pattern: Evaluator-optimizer (Anthropic) / multi-turn (OpenAI)

Layer 5: Patch Agent (for modifications)
  - Input: Existing IFC + modification request
  - Output: Python patch script or spec delta
  - Pattern: Code Interpreter (OpenAI) / PTC (Anthropic)
  - Tools needed: IfcAuthor API tools (5-8 well-defined tools)
```

### 4.4 Tool Count Recommendation

Reduce from 15+ to a tiered system:

**Tier 1 -- Always available (3-4 tools)**:
- `generate_building(spec)` -- full building from spec
- `modify_building(spec_delta)` -- modify existing building
- `validate_model(checks)` -- run validation suite
- `render_model(view)` -- produce visual preview

**Tier 2 -- Loaded on demand via tool search (5-8 tools)**:
- Individual IFC element tools for patches and custom work
- Structural analysis tools
- MEP-specific tools

This keeps the per-turn tool count under 5 for the common case (full building generation) and under 12 for the complex case (detailed patch work).

---

## Sources

- [OpenAI: A Practical Guide to Building Agents (PDF)](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
- [OpenAI: Function Calling Documentation](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI: Structured Model Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI: Code Interpreter](https://developers.openai.com/api/docs/guides/tools-code-interpreter)
- [OpenAI: Agents SDK - Agent Orchestration](https://openai.github.io/openai-agents-python/multi_agent/)
- [OpenAI: o3/o4-mini Function Calling Guide](https://developers.openai.com/cookbook/examples/o-series/o3o4-mini_prompting_guide)
- [OpenAI: Reasoning Best Practices](https://developers.openai.com/api/docs/guides/reasoning-best-practices)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [Anthropic: Introducing Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Anthropic: Programmatic Tool Calling Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
- [Anthropic: How We Built Our Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Anthropic: Claude Computer Use Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- [Anthropic: Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Self-Spec: Model-Authored Specifications for Reliable LLM Code Generation (OpenReview)](https://openreview.net/forum?id=6pr7BUGkLp)
- [Understanding Specification-Driven Code Generation with LLMs (SANER 2026)](https://arxiv.org/html/2601.03878)
- [Spec-Driven Development (Thoughtworks)](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)
- [Concise Thoughts: Impact of Output Length on LLM Reasoning and Cost](https://arxiv.org/pdf/2407.19825)
- [Context Rot: How Increasing Input Tokens Impacts LLM Performance (Chroma Research)](https://research.trychroma.com/context-rot)
- [Berkeley Function Calling Leaderboard V4](https://gorilla.cs.berkeley.edu/leaderboard.html)
- [Vellum: When to Use Function Calling, Structured Outputs, or JSON Mode](https://vellum.ai/blog/when-should-i-use-function-calling-structured-outputs-or-json-mode)
- [Addy Osmani: My LLM Coding Workflow Going Into 2026](https://addyo.substack.com/p/my-llm-coding-workflow-going-into)
