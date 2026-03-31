# Planner Prompt Refactor Options

## Problem Statement

The OpenClaw planner bridge (`src/bonsai_ai/openclaw_planner.py`) times out because it packs everything into a single `--message` string passed to `openclaw agent`. The bim_operator agent then layers its own context on top (AGENTS.md, SOUL.md, memory files, project context), creating an enormous input that overwhelms the model or exceeds time limits.

### Measured message sizes (typical 2-storey building prompt)

| Component | Chars |
|-----------|-------|
| SYSTEM_PROMPT (bonsai_ai_core/planner.py) | ~3,900 |
| Tool spec summary (_tool_spec_summary) | ~2,900 |
| Response format instructions | ~300 |
| User prompt + scene summary | ~400 |
| **Total bridge message** | **~7,500** |
| bim_operator AGENTS.md (loaded by OpenClaw) | ~7,100 |
| bim_operator SOUL.md (loaded by OpenClaw) | ~1,200 |
| Memory files + project context (varies) | ~2,000-8,000 |
| **Estimated total model input** | **~18,000-24,000+** |

### Why the direct planner works fine

The direct planner (`src/bonsai_ai/planner.py` + `bonsai_ai_core/providers.py`) separates concerns cleanly:

- **System prompt** goes in the `system` parameter (Anthropic) or system instruction (OpenAI/Gemini)
- **Schema** goes in the `tools` parameter (Anthropic forced tool use) or `responseSchema` (Gemini) or `json_schema` (OpenAI structured output)
- **User message** contains ONLY the building request + scene summary

The model sees the schema as structured metadata, not prose to parse. The user message is short and focused.

### Why the OpenClaw bridge fails

The bridge has no way to set system prompt or tools separately -- `openclaw agent --message` accepts one string. So everything gets concatenated:

1. Full SYSTEM_PROMPT (3,900 chars of BIM rules) duplicates what's already in bim_operator's AGENTS.md
2. Full tool spec summary (2,900 chars) -- the operator's AGENTS.md already lists the primitives
3. Detailed response format instructions
4. Scene + progress summaries
5. User request

Then OpenClaw's agent runtime adds AGENTS.md, SOUL.md, memory, and project files on top. The model gets two competing sets of BIM instructions, one embedded in the message and one in the agent's charter.

---

## Option A: Minimal Message (Small Fix)

**Approach:** Strip the bridge message down to only what the bim_operator doesn't already know. Trust the agent's own charter files (AGENTS.md, SOUL.md) to provide BIM domain knowledge. The message becomes a pure task request.

### Changes

**File: `src/bonsai_ai/openclaw_planner.py`**

Replace `_build_message()` with a minimal version:

```python
def _build_message(
    user_prompt: str,
    scene_summary: str,
    progress_summary: str = "",
) -> str:
    parts = [
        "Generate a BIM action plan as a JSON object.",
        "",
        "Format: {\"version\": \"1\", \"units\": \"meters\", \"summary\": \"...\", \"assumptions\": [...], \"actions\": [...]}",
        "Each action: {\"type\": \"<action_type>\", \"name\": \"<descriptive_name>\", ...params}",
        "",
        "Respond with ONLY the JSON plan. No markdown fences, no commentary.",
    ]

    if scene_summary.strip():
        parts.extend(["", "## Current scene", "", scene_summary.strip()])

    if progress_summary.strip():
        parts.extend(["", "## Completed so far", "", progress_summary.strip()])

    parts.extend(["", "## Request", "", user_prompt.strip()])

    return "\n".join(parts)
```

Delete `_tool_spec_summary()` entirely (or keep it for debugging).

**No other files change.**

### Message size

| Component | Before | After |
|-----------|--------|-------|
| Bridge message | ~7,500 | ~600-800 |
| Agent charter context | ~10,000-16,000 | ~10,000-16,000 |
| **Estimated total** | **~18,000-24,000** | **~11,000-17,000** |

**Reduction: ~7,000 chars (~35-40% of total input)**

### Risk to output quality

**Medium risk.** The bim_operator's AGENTS.md lists the supported primitives and their names, but it does NOT include:

- Required fields per action type (the operator AGENTS.md just says "create_wall -- straight wall between two XY points")
- Parametric generator details (bays_x, spacing_x, etc.)
- Metadata objects (semantics, presentation, foundation) guidance
- The specific rules about coordinate systems, ordering, etc.

The model will know WHAT tools exist but may produce plans with missing fields or wrong parameter names. The compilation step (`compile_core_plan`) will catch some errors, but others may produce silent coordinate mistakes.

**Mitigation:** Update `openclaw/AGENTS.md` to include a condensed version of the required fields for each action type. This keeps the knowledge in one place (the agent's charter) rather than duplicated in the bridge. Add a one-line note in the bridge message: "Refer to your supported primitives documentation for required fields per action type."

### Implementation effort

**2-4 hours.** Change `_build_message()`, test with a few building prompts, iterate on what the operator's AGENTS.md needs to include. May need to update AGENTS.md with field-level detail if output quality drops.

---

## Option B: Shared Prompt Architecture (Medium Refactor)

**Approach:** Extract the prompt content into a layered system with three tiers: (1) core rules that both paths share, (2) schema/tool specification that goes in the structured parameter for direct or in the agent charter for OpenClaw, and (3) the user message which is always just the request + scene. Both the direct planner and the OpenClaw bridge consume the same prompt layers but assemble them differently.

### Changes

**New file: `bonsai_ai_core/prompt_layers.py`**

```python
# Layer 1: Core BIM rules (always needed, either in system prompt or agent charter)
BIM_RULES = """..."""  # The current SYSTEM_PROMPT content, cleaned up

# Layer 2: Compact tool reference (field-level, not full JSON schema)
TOOL_REFERENCE = """..."""  # One-line per tool with required params

# Layer 3: Response format (varies by path)
RESPONSE_FORMAT_STRUCTURED = "..."  # For direct path (schema-enforced)
RESPONSE_FORMAT_FREEFORM = "..."    # For OpenClaw path (JSON in text)

def build_system_prompt(include_tools: bool = True) -> str:
    """Direct planner system prompt. Tools go in the schema parameter."""
    ...

def build_task_message(user_prompt, scene_summary, progress_summary) -> str:
    """The user message, shared by both paths."""
    ...

def build_openclaw_message(user_prompt, scene_summary, progress_summary) -> str:
    """Minimal message for OpenClaw. Assumes agent charter has BIM rules."""
    ...
```

**File: `bonsai_ai_core/planner.py`**

Replace inline `SYSTEM_PROMPT` with import from `prompt_layers.py`. Keep backward compat by re-exporting `SYSTEM_PROMPT = build_system_prompt()`.

**File: `src/bonsai_ai/openclaw_planner.py`**

Replace `_build_message()` with call to `build_openclaw_message()`. Remove `_tool_spec_summary()`.

**File: `src/bonsai_ai/planner.py`**

Use `build_task_message()` for the user prompt instead of inline `_scene_prompt()`.

**File: `openclaw/AGENTS.md`**

Add a new section "## Action Field Reference" that is generated from or kept in sync with `TOOL_REFERENCE`. This becomes the canonical field-level documentation the operator agent uses.

### Message size

| Component | Before | After |
|-----------|--------|-------|
| Bridge message | ~7,500 | ~600-800 |
| Agent charter (with field ref) | ~10,000-16,000 | ~12,000-18,000 |
| **Estimated total** | **~18,000-24,000** | **~13,000-19,000** |

**Reduction: ~5,000 chars, plus elimination of duplication**

The total reduction is less dramatic than Option A because we move the tool reference into the agent charter. But the key win is architectural: there is now ONE source of truth for prompt content, and both paths consume it.

### Risk to output quality

**Low risk.** The direct planner path is unchanged in behavior (system prompt + schema enforcement). The OpenClaw path gets cleaner because:

- BIM rules live in the agent charter where they belong
- The tool reference is field-level accurate (not just names)
- The message is focused on the task
- No conflicting instructions between message and charter

### Implementation effort

**2-3 days.**

- Day 1: Create `prompt_layers.py`, migrate SYSTEM_PROMPT, write tool reference
- Day 2: Rewire both planners, update AGENTS.md, run comparison tests
- Day 3: Edge cases, multi-round planning, edit actions, documentation

---

## Option C: Native OpenClaw Agent Integration (Large Refactor)

**Approach:** Stop treating OpenClaw as a subprocess that receives a single message. Instead, make the BIM planner a first-class OpenClaw agent with persistent sessions, native tool definitions, and multi-step planning.

### Architecture

```
Current:
  Bonsai CLI → openclaw_planner.py → subprocess("openclaw agent --message <blob>") → bim_operator → one-shot response

Proposed:
  Bonsai CLI → openclaw_planner.py → session-based agent calls:
    Step 1: "Plan the structure for this building" → structural actions
    Step 2: "Now plan the envelope" → envelope actions
    Step 3: "Now plan openings" → opening actions
    Each step validated before proceeding to next
```

### Key Design Decisions

**1. Persistent session instead of one-shot subprocess**

Use `openclaw agent --session-id <building-session>` to maintain conversation state. The agent remembers what it already planned in earlier steps. This means:

- Step 1 output (structure) becomes context for Step 2 (envelope)
- No need to re-send the full building description each round
- Failed steps can be retried without re-planning everything
- The session can span multiple CLI invocations (iterative design)

**2. OpenClaw native tool registration (if/when supported)**

If OpenClaw adds tool/function support to its agent protocol, register BIM tools natively:

```python
# Hypothetical -- depends on OpenClaw agent tool protocol
cmd = [
    openclaw_bin, "agent",
    "--agent", "bim_planner",
    "--session-id", session_id,
    "--tools", tools_json_path,  # native tool definitions
    "--message", user_prompt,    # JUST the request
]
```

This mirrors exactly what the direct Anthropic provider does with `tool_choice: { type: "tool" }`. The model is forced to respond via structured tool calls, not free-text JSON.

Until OpenClaw supports this, the bridge can simulate it by asking for structured JSON and validating/retrying.

**3. Multi-step planning pipeline**

Break the monolithic "plan entire building" into phases:

```
Phase 1: Foundation & Structure
  → ensure_project, ensure_storey, generate_column_grid, generate_floor_plate, create_footing
  → Validate: all storeys exist, columns land on grid, slabs are supported

Phase 2: Envelope
  → generate_perimeter_walls, generate_facade_grid, create_curtain_wall
  → Validate: walls close the perimeter, facades attach to structure

Phase 3: Openings & Interior
  → create_door, create_window, create_wall (interior partitions)
  → Validate: doors/windows reference existing walls by exact name

Phase 4: Metadata & Semantics
  → update_element (add semantics, presentation, foundation metadata)
  → Validate: group_paths are consistent, material_keys exist
```

Each phase produces a partial plan that is compiled and validated before the next phase starts. The model gets feedback about what it built, reducing hallucination in later phases.

### Changes

**New file: `src/bonsai_ai/openclaw_session.py`**

Session management for multi-step OpenClaw planning:

```python
class OpenClawPlanSession:
    def __init__(self, building_prompt: str, session_id: str = None):
        self.session_id = session_id or f"bim-{uuid4().hex[:8]}"
        self.building_prompt = building_prompt
        self.completed_phases: list[str] = []
        self.accumulated_actions: list[dict] = []

    def run_phase(self, phase_name: str, phase_prompt: str) -> list[dict]:
        """Run one planning phase via OpenClaw agent subprocess."""
        ...

    def run_full_plan(self) -> PlanResult:
        """Run all phases sequentially, accumulate actions."""
        ...
```

**New file: `src/bonsai_ai/plan_phases.py`**

Phase definitions and per-phase prompt builders:

```python
PHASES = [
    Phase("structure", "Plan the structural system: ...", allowed_types=[...]),
    Phase("envelope", "Plan the building envelope: ...", allowed_types=[...]),
    Phase("openings", "Plan doors and windows: ...", allowed_types=[...]),
]
```

**New agent: `openclaw/agents/bim_planner/`**

A dedicated OpenClaw agent workspace (separate from bim_operator) that is purpose-built for planning:

- AGENTS.md contains ONLY the BIM rules and tool reference (no operator workflow, no project memory, no maintainer spawning)
- No SOUL.md (it's a function, not a persona)
- Minimal charter = minimal context overhead

This separates the "plan a building" function from the "operate the BIM tool" persona. The bim_operator can spawn the bim_planner when it needs a plan, or the CLI can call it directly.

**File: `src/bonsai_ai/openclaw_planner.py`**

Rewrite to use `OpenClawPlanSession` and multi-step pipeline. Keep the existing `create_plan_via_openclaw()` signature as a facade that runs the full pipeline.

**File: `openclaw/AGENTS.md` (bim_operator)**

Remove inline primitive documentation. Replace with: "For building plans, spawn the bim_planner agent or use the planning CLI." The operator becomes a workflow coordinator, not a planner.

### Message size per step

| Component | Per-phase message |
|-----------|------------------|
| Phase prompt | ~200-400 |
| Previous phase summary | ~200-500 |
| Scene state | ~200-500 |
| **Total per-step message** | **~600-1,400** |
| bim_planner charter (minimal) | ~3,000-4,000 |
| **Total model input per step** | **~3,600-5,400** |

**Reduction: 70-80% per model call compared to current single-shot**

And each call is simpler, so the model produces better output per call. Total token cost across all phases may be similar or slightly higher, but quality and reliability improve significantly.

### Risk to output quality

**Low risk to quality, medium risk to integration.** Multi-step planning with validation between phases should IMPROVE quality because:

- Each phase is a smaller, more focused task
- Validation catches errors before they compound
- The model can reference what it already built (via session state)
- Phase-specific allowed_types prevent the model from jumping ahead

Integration risks:

- Persistent sessions depend on OpenClaw session semantics being stable
- Multi-step adds latency (3-4 subprocess calls instead of 1)
- Phase boundaries need design work (what if a building doesn't fit the phase model?)
- Needs a fallback to single-shot for simple prompts ("add a wall at x=5")

### Implementation effort

**2-3 weeks.**

- Week 1: Session management, phase definitions, bim_planner agent workspace, basic multi-step flow
- Week 2: Per-phase validation, error recovery, retry logic, fallback to single-shot for simple prompts
- Week 3: Testing across building types, edge cases (edits, partial rebuilds, multi-storey), performance tuning, documentation

---

## Comparison Summary

| | Option A: Minimal | Option B: Shared Layers | Option C: Native Agent |
|---|---|---|---|
| **Message reduction** | ~7,000 chars (35-40%) | ~5,000 chars + no duplication | ~70-80% per call |
| **Quality risk** | Medium (missing field specs) | Low | Low (likely improves) |
| **Architecture improvement** | None (band-aid) | Good (single source of truth) | Major (right abstraction) |
| **Effort** | 2-4 hours | 2-3 days | 2-3 weeks |
| **Files changed** | 1 | 4-5 + AGENTS.md | 6-8 + new agent workspace |
| **Breaks existing tests** | No | Unlikely (backward compat) | Yes (new test surface) |
| **Unlocks future work** | No | Shared prompt for new surfaces | Multi-step, iterative design |

## Recommendation

**Ship Option A now, build toward Option B this week.**

Option A unblocks the OpenClaw bridge immediately. The quality risk is manageable -- if plans come back with missing fields, the compilation step will error clearly, and we can add field hints to the operator's AGENTS.md incrementally.

Option B is the right medium-term architecture. It eliminates the duplication that caused this problem and makes prompt content maintainable. It also sets up the layering that Option C would need.

Option C is the right long-term direction, but it depends on OpenClaw features (tool registration, stable sessions) that may not be ready. Add it to the improvement backlog with a dependency note on OpenClaw capabilities.
