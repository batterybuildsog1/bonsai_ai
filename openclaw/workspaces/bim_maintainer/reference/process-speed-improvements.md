# Bonsai AI Process Speed Improvements

## Research Date: 2026-03-30

## Current Pipeline Timing Model

```
User prompt
  |
  v
[AI Planner] -----> 5-30s per round (network + inference)
  |                  x up to 12 rounds = 60-360s worst case
  v
[IfcOpenShell] ----> <1s per element (CPU-bound Python/C++)
  |                  ~100-1000 elements = 1-10s total
  v
[save .ifc] ------> <1s (file write)
  |
  v
[Optional: structural pipeline] --> 10-60s (catalog + FEA + sizing)
  |
  v
[Viewer] ----------> 1-5s (Blender load or web parse)
```

**Dominant bottleneck: AI planner rounds.** Each round is a full network call (5-30s). With replanning, the planner can consume 90%+ of total wall-clock time. IFC generation itself is fast.

---

## 1. Faster AI Planning

### 1A. Prompt Caching (OpenAI + Anthropic)

**What it is:** Both OpenAI and Anthropic automatically cache prompt prefixes. When requests share the same prefix (system prompt, tool definitions, schema), the cached KV state is reused, skipping re-computation of those tokens.

**How it applies to Bonsai AI:**
- The system prompt in `bonsai_ai_core/planner.py` (~44 lines of rules) is identical across all rounds.
- The plan schema (`plan_schema()`) is identical across all rounds.
- Tool definitions for Anthropic's forced tool_use are identical across all rounds.
- In multi-round planning, the only changing content is the user prompt (with scene summary and progress notes appended at the end).

**Current state:** OpenAI prompt caching is automatic -- no API changes needed. It activates when the prefix exceeds 1,024 tokens. Anthropic requires `cache_control` breakpoints in the request but offers explicit control over what gets cached.

**Performance impact:**
- OpenAI: up to 80% latency reduction and 50% cost reduction on cached prefix tokens.
- Anthropic: up to 85% latency reduction and 90% cost reduction on cached tokens. Cache reads cost 0.1x base price.

**Implementation:**
- OpenAI: Already happening automatically if the system prompt + schema prefix exceeds 1,024 tokens. Verify by checking `usage.prompt_tokens_details.cached_tokens` in responses. **Difficulty: trivial** (just confirm it works).
- Anthropic: Add `cache_control: {"type": "ephemeral"}` to the system prompt and tool definition blocks in `providers.py`. **Difficulty: easy** (a few lines of code in `AnthropicProvider.generate_plan()`).

**Estimated speedup:** 2-5x on rounds 2+ (the prefix is already cached from round 1). First round sees no benefit.

**Risks:** Cache entries expire (5 min default for Anthropic, OpenAI is automatic). Long pauses between rounds could miss the cache. No quality tradeoff.

### 1B. Predicted Outputs (OpenAI)

**What it is:** You provide a "prediction" of what the model will generate, and OpenAI uses speculative decoding to validate predicted tokens in parallel, yielding 3-5x faster responses for predictable output.

**How it applies:** Many building plans follow predictable patterns. A grid of 20 columns will produce very similar JSON for each column, varying only in coordinates.

**Critical limitation:** Predicted Outputs **cannot be used with tool calls, structured outputs, or JSON mode.** Since Bonsai AI uses structured output (`json_schema` format) for plan generation, this feature is **not compatible** with the current architecture.

**Verdict: Not feasible** with the current structured-output approach. Would require switching to raw text output and doing JSON parsing/validation ourselves, which reintroduces hallucination risk.

### 1C. OpenAI Batch API

**What it is:** Submit up to thousands of requests as a JSONL batch. Processing completes within 24 hours at 50% cost.

**How it applies:** Not useful for interactive planning (24-hour turnaround). Could be useful for offline batch generation of building templates or training data.

**Verdict: Not applicable** to the interactive workflow. Useful only for offline template generation (see Section 4).

### 1D. Parallel Tool Calls (OpenAI)

**What it is:** OpenAI models can emit multiple tool calls in a single response. When `parallel_tool_calls` is enabled, the model may return several function calls simultaneously.

**How it applies:** The current architecture already receives multiple tool calls per round (the plan contains many actions). The bottleneck is not tool execution parallelism -- it is the number of *planning rounds*.

**Note:** Reasoning models (o-series) do not reliably support parallel tool calls. gpt-4.1 family supports them well.

**Verdict: Already partially leveraged.** The plan returns all actions for a round in one response. The key optimization is reducing the number of rounds, not parallelizing within a round.

---

## 2. IFC Generation Speed

### 2A. IfcOpenShell Performance Profile

**Current architecture:** `ifc_author.py` (49KB, ~1,110 lines) creates IFC entities one at a time using `ifcopenshell.api.root.create_entity()` and related API calls. Each element involves:
1. Creating the entity
2. Creating geometry (extrusion, swept solid, or mapped item)
3. Assigning to spatial container (storey)
4. Attaching property sets (Pset_BonsaiAI metadata)
5. Setting placement matrix

**Measured performance:** For the techridge model (1,119 structural elements), the full pipeline completes in seconds, not minutes. IFC generation is **not the bottleneck**.

**Where IfcOpenShell is slow:**
- *Parsing* large existing files (450MB file = 1m40s to open) -- relevant if loading a large existing model for incremental edits.
- *Geometry processing/meshing* -- only relevant for visualization, not authoring.
- Multi-threaded geometry iteration has memory issues (60GB+ for large files).

**Verdict:** IFC generation speed is **not a priority optimization**. The authoring path (creating new elements) is fast. Focus optimization effort on the AI planner instead.

### 2B. Bypass IfcOpenShell for Direct IFC-SPF Writing

**What it is:** IFC files are STEP Physical Files (ISO 10303-21), which are essentially structured text. You could write IFC-SPF directly as strings instead of going through the IfcOpenShell API.

**Feasibility:** Technically possible for simple geometry (extruded area solids, rectangular profiles). The IFC schema is well-documented.

**Risks:**
- Extremely error-prone. IFC entity relationships are complex (placements, representations, spatial containment, property sets).
- No schema validation. Malformed files would silently corrupt.
- Would bypass IfcOpenShell's C++ geometry kernel entirely.
- Maintenance nightmare when IFC schema evolves.

**Verdict: Not recommended.** The marginal speed gain (saving <1s on a 10s authoring step) does not justify the engineering risk. IfcOpenShell's API is the right abstraction layer.

### 2C. IfcOpenShell Optimizer for Output Files

**What it is:** IfcOpenShell includes an optimizer that deduplicates shared entity instances in IFC files, reducing file size and processing time for downstream consumers.

**How it applies:** After generating a building with many repeated elements (identical column profiles, identical wall thicknesses), running the optimizer before save could reduce file size significantly.

**Implementation:** `ifcopenshell.api.project.optimize_file(model)` before `model.write()`. **Difficulty: trivial** (one line in `IfcAuthor.save()`).

**Estimated impact:** 20-60% file size reduction for repetitive models. Faster downstream loading.

---

## 3. Incremental Model Updates

### 3A. Current Problem

Changing one wall currently requires:
1. Replanning the entire model (or at least re-running the planner with the edit request)
2. The planner sees the full scene summary and must decide what changed
3. Up to 12 rounds of re-planning
4. All elements are re-evaluated even if only one changed

### 3B. IfcOpenShell Native IFC / Incremental Editing

**Industry status:** IfcOpenShell Issue #1222 tracks the migration of BlenderBIM to incremental editing. The goal is to hold the IFC dataset in memory and apply atomic changes rather than import/export cycles. This work is ongoing but represents the direction the ecosystem is heading.

IFC5 (future spec) aims to decouple from file formats and support incremental updates natively. Not available yet.

**What we can do now:**

The `ifc_author.py` already has `update_element`, `delete_element`, `move_element`, `replace_section`, and `rebuild_branch` action types defined in the tool specs. The key optimization is making the **planner** smarter about using these edit actions instead of replanning from scratch.

### 3C. Targeted Edit Planning

**Approach:** When the user requests a change to an existing model:
1. Parse the edit request and identify the target element(s)
2. Send only the relevant context (target element properties + immediate neighbors) to the planner
3. Constrain the planner to emit only edit actions (`update_element`, `move_element`, `delete_element`, `replace_section`)
4. Apply the edit actions directly without full replanning

**Implementation:**
- Add an "edit mode" system prompt that constrains the planner to edit actions only
- Extract a focused context window around the target element(s)
- Reduce the scene summary to only the relevant spatial neighborhood
- This should complete in 1 round instead of 12

**Estimated speedup:** 5-12x for edit operations (1 round instead of up to 12, with a smaller prompt).

**Difficulty: medium.** Requires a new planner mode and context extraction logic. The edit action types already exist in the schema.

**Quality risk:** The planner might miss cascading changes (moving a wall might require moving its windows). Mitigation: include a "dependency check" step that identifies affected elements.

---

## 4. Template / Pattern Caching

### 4A. Agentic Plan Caching (Research-backed)

**Academic backing:** "Agentic Plan Caching" (APC, arxiv 2506.14852) demonstrates extracting reusable plan templates from completed agent executions. On average: 50% cost reduction and 27% latency reduction while maintaining quality.

**How it applies to Bonsai AI:**

Common building patterns repeat constantly:
- Grid of columns (N x M at spacing S)
- Perimeter walls (4 walls forming a rectangle)
- Floor plates (slab per storey)
- Stair cores (stair run + landing per storey)
- Window arrays (N windows equally spaced along a wall)

**Implementation approach:**

1. **Template extraction:** After each successful plan generation, extract the plan structure as a template with parameterized coordinates:
   ```json
   {
     "pattern": "column_grid",
     "params": {"rows": 4, "cols": 6, "spacing_x": 6.0, "spacing_y": 9.0},
     "template_actions": [...]
   }
   ```

2. **Template matching:** Before calling the AI planner, check if the user's prompt matches a cached template using keyword extraction + embedding similarity.

3. **Template instantiation:** If a match is found, instantiate the template with the specific parameters, bypassing the AI planner entirely.

4. **Hybrid approach:** Use templates for the predictable parts (column grids, floor plates) and the AI planner only for the creative/custom parts.

**Estimated speedup:** 10-100x for template-matched requests (no AI call needed). 2-5x for hybrid requests (fewer planner rounds).

**Difficulty: medium-high.** Requires building a template library, a matching system, and a parameterization engine. Could start simple (exact pattern matching on common requests) and grow more sophisticated.

**Quality risk:** Templates might not capture edge cases. Mitigation: always validate the instantiated plan against the schema before execution.

### 4B. Pre-compiled Plan Library

**Simpler version of 4A:** Instead of runtime extraction, manually author a library of common building plans as pre-compiled action sequences:

```python
TEMPLATES = {
    "simple_office": {
        "params": ["length", "width", "stories", "story_height"],
        "generator": generate_simple_office_plan,
    },
    "warehouse": {
        "params": ["length", "width", "height", "bay_spacing"],
        "generator": generate_warehouse_plan,
    },
}
```

**Estimated speedup:** Near-instant for matched templates (<100ms vs 5-30s).

**Difficulty: low-medium.** Can start with 3-5 common building types and expand.

---

## 5. Parallel AI Calls

### 5A. Decompose Building into Independent Subsystems

**Concept:** A building can be decomposed into subsystems that are largely independent:
- Structure (columns, beams, slabs)
- Envelope (walls, curtain walls, windows, doors)
- Vertical circulation (stairs, elevators)
- Foundations (footings)

These can be planned in parallel by separate AI calls.

**Architecture:**

```
User prompt
  |
  v
[Decomposer] --> identifies subsystems (1 AI call, 3-5s)
  |
  +----> [Structure Planner] -----> columns, beams, slabs (1 call)
  +----> [Envelope Planner] ------> walls, windows, doors (1 call)
  +----> [Circulation Planner] ---> stairs, elevators (1 call)
  +----> [Foundation Planner] ----> footings (1 call)
  |
  v
[Merge] --> combine all plans, resolve conflicts
```

**Estimated speedup:** 3-4x (4 parallel calls instead of 4 sequential rounds). Combined with prompt caching, could see 5-8x.

**Difficulty: high.** Requires:
- A decomposition step that correctly partitions the building
- Conflict resolution when subsystems overlap (wall-to-column connections)
- Coordinate system consistency across parallel planners

**Quality risk:** Subsystems are not truly independent. Walls attach to columns. Beams span between columns. Stairs need to align with floor plates. The merge step is complex and error-prone.

**Mitigation:** Run structure first (it defines the grid), then run envelope + circulation in parallel using the structural grid as a constraint.

### 5B. Python asyncio for Concurrent API Calls

**Current state:** `bonsai_ai_core/http.py` uses synchronous `urllib` for HTTP requests. The bridge server (`server.py`) is blocking on the FastAPI event loop.

**Implementation:** Replace `post_json()` with an async version using `aiohttp` or `httpx`. Use `asyncio.gather()` to make parallel API calls.

**Difficulty: medium.** Requires refactoring the HTTP layer and making the planner async. The `IfcAuthor` remains synchronous (IfcOpenShell is not thread-safe), but API calls can be parallelized.

**Estimated impact:** Only useful if combined with 5A (parallel planning). No benefit for sequential rounds.

---

## 6. Streaming IFC Generation

### 6A. Stream Tool Calls, Execute Incrementally

**Concept:** Instead of waiting for the full plan to arrive, stream the AI response and execute tool calls as they arrive.

**How it works with OpenAI Responses API:**
1. Set `stream=True` in the API request
2. Listen for `response.function_call_arguments.delta` events
3. As each tool call's arguments are fully assembled, execute it immediately
4. The viewer sees elements appear one at a time as the plan streams in

**Implementation:**
- Modify `providers.py` to support streaming responses
- Add an event-based execution pipeline: `on_tool_call_complete -> execute -> update_viewer`
- For the web viewer: use WebSocket to push new IFC elements as they are created

**Estimated speedup:** Perceived latency drops to time-to-first-element (1-3s) instead of time-to-complete-plan (5-30s). Total wall clock unchanged, but user sees progress immediately.

**Difficulty: medium.** Streaming parsing is well-documented for OpenAI. The challenge is the incremental viewer update.

**Quality risk:** None for the IFC output. The viewer might show intermediate states that look incomplete.

### 6B. Progressive Web Viewer

**Technologies available:**
- **web-ifc** (ThatOpen): WASM-based IFC parser for browser. Can load and display IFC files client-side.
- **ifc-lite**: Rust + WASM core with WebGPU rendering. First triangles on screen in ~200ms. Streaming pipeline architecture. Up to 5x faster geometry processing.
- **xeokit**: Purpose-built BIM viewer. Loads hundreds of thousands of objects in seconds.

**Implementation:** Instead of writing the full IFC file and then loading it in a viewer, push geometry fragments to the viewer over WebSocket as elements are created.

**Difficulty: medium-high.** Requires a streaming geometry protocol between the Python backend and the web viewer.

---

## 7. Pre-warmed Model State

### 7A. Keep IfcOpenShell Model in Memory Between Rounds

**Current behavior:** The `IfcAuthor` class in `cli.py` already holds the model in memory across rounds:
```python
author = IfcAuthor(args.output)  # loaded once
for _ in range(max_rounds):
    plan = create_plan(...)
    for call in plan.tool_calls:
        author.apply_tool_call(call.name, call.arguments)  # operates on in-memory model
author.save()  # writes once at the end
```

**Verdict: Already implemented.** The model is created or loaded once and held in memory throughout the planning loop. Elements accumulate in the in-memory model. `model.write()` is called once at the end.

### 7B. Persist Model Across Sessions (Bridge Server)

**Current state:** The bridge server (`server.py`) creates a new `IfcAuthor` per design job. If the user makes a follow-up request, the model is re-loaded from disk.

**Optimization:** Keep the `IfcAuthor` instance alive in the server process. Use an LRU cache of recent models keyed by file path.

```python
from functools import lru_cache

@lru_cache(maxsize=8)
def get_author(path: str) -> IfcAuthor:
    return IfcAuthor(path)
```

**Estimated speedup:** Eliminates file re-parsing on follow-up edits. For small models (<10MB), this saves <1s. For large models (100MB+), this could save 5-10s.

**Difficulty: low.** Requires cache invalidation when the file is modified externally.

**Risk:** Memory usage grows with cached models. IfcOpenShell models for large buildings can consume hundreds of MB.

---

## 8. Smart Replanning

### 8A. Current Replanning Problem

The `cli.py` planning loop runs up to 12 rounds:
- Each round calls the AI planner with the full prompt + scene summary + progress notes
- The planner sees what was completed and decides what to do next
- If a tool call fails, the error is appended to progress notes for the next round
- Duplicate round detection prevents infinite loops

This is wasteful when:
- Most elements succeed but 1-2 fail. The next round re-evaluates everything.
- The planner generates the same pattern of elements across multiple rounds (e.g., floor-by-floor).

### 8B. Targeted Failure Retry

**Approach:** Instead of re-running the full planner when a tool call fails:
1. Collect all failed calls from the current round
2. Send only the failed calls + their error messages to the planner
3. Ask for corrective actions for just those elements
4. Apply the corrections without replanning the entire model

**Implementation:**
```python
failed_in_round = []
for call in plan.tool_calls:
    try:
        result = author.apply_tool_call(call.name, call.arguments)
    except AuthoringError as exc:
        failed_in_round.append((call, str(exc)))

if failed_in_round:
    repair_plan = create_repair_plan(failed_in_round, author.scene_summary())
    # Only replans the failed elements
```

**Estimated speedup:** Reduces round count from 12 to 2-3 in typical cases. Each repair round is faster because the prompt is smaller (only failed elements, not the full building description).

**Difficulty: low-medium.** Requires a "repair mode" system prompt and a focused context builder.

### 8C. Single-Shot Planning with Validation

**Approach:** Instead of multi-round planning, generate the entire plan in one shot and validate it before execution:
1. Send the full building description to the planner
2. Receive a complete plan (all storeys, all elements)
3. Validate the plan against geometric constraints (no overlapping elements, valid coordinates)
4. Execute the validated plan in one pass
5. If validation fails, send specific validation errors for targeted repair

**Implementation:** This is essentially what `build_core_plan()` does now (single plan generation), but adding a validation step before execution.

**Estimated speedup:** Reduces to 1-2 rounds total. Combined with prompt caching, each round is faster.

**Difficulty: medium.** Requires building a geometric validation layer. The schema already validates structure; this adds spatial validation.

### 8D. Durable Execution / Checkpoint-Resume

**Approach (from Prefect/Pydantic AI research):** When a multi-step workflow fails, checkpoint the completed steps and resume from the point of failure.

**Implementation:**
- After each successful tool call, checkpoint the model state
- On failure, roll back only the failed operation
- Resume planning from the last successful checkpoint

**Estimated speedup:** Eliminates wasted re-execution of successful steps. Combined with targeted retry (8B), this minimizes total work.

**Difficulty: medium.** IfcOpenShell does not have native undo/rollback. Would need to track created entity IDs and remove them on failure.

---

## Priority Ranking

Sorted by (impact / difficulty):

| # | Optimization | Speedup | Difficulty | Priority |
|---|---|---|---|---|
| 1 | **Prompt caching (Anthropic explicit)** | 2-5x on rounds 2+ | Trivial | **Do first** |
| 2 | **Prompt caching (OpenAI verify)** | 2-5x on rounds 2+ | Trivial | **Do first** |
| 3 | **Targeted failure retry (8B)** | 3-5x fewer rounds | Low-medium | **Do second** |
| 4 | **Pre-compiled plan library (4B)** | 100x for matched | Low-medium | **Do third** |
| 5 | **Targeted edit planning (3C)** | 5-12x for edits | Medium | **Do fourth** |
| 6 | **Streaming tool execution (6A)** | Perceived 5-10x | Medium | **Do fifth** |
| 7 | **Bridge server model cache (7B)** | 1-10s per session | Low | **Quick win** |
| 8 | **IfcOpenShell optimizer (2C)** | File size, not speed | Trivial | **Quick win** |
| 9 | **Agentic plan caching (4A)** | 2-5x for similar | Medium-high | **Later** |
| 10 | **Parallel subsystem planning (5A)** | 3-4x | High | **Later** |
| 11 | **Progressive web viewer (6B)** | Perceived speedup | Medium-high | **Later** |
| 12 | **Single-shot with validation (8C)** | 5-10x | Medium | **Later** |

---

## Recommended Implementation Order

### Phase 1: Quick Wins (1-2 days)
1. Verify OpenAI prompt caching is active (check `cached_tokens` in response)
2. Add Anthropic cache breakpoints to system prompt and tool definitions
3. Add `ifcopenshell.api.project.optimize_file()` call before save
4. Add LRU cache for IfcAuthor instances in bridge server

### Phase 2: Smart Replanning (3-5 days)
5. Implement targeted failure retry (separate failed calls, repair prompt)
6. Add "edit mode" system prompt that constrains to edit actions
7. Reduce scene summary to focused context window for edit operations

### Phase 3: Template System (1-2 weeks)
8. Build pre-compiled plan generators for 5 common building types
9. Add template matching to the planner dispatch
10. Implement hybrid planning (templates for structure, AI for custom parts)

### Phase 4: Streaming Pipeline (2-3 weeks)
11. Add streaming support to OpenAI provider
12. Implement incremental tool call execution
13. Add WebSocket push to web viewer for progressive rendering

### Phase 5: Advanced (1-2 months)
14. Parallel subsystem planning with merge
15. Agentic plan caching with template extraction
16. Geometric validation layer for single-shot planning

---

## Sources

### AI Planning and Caching
- [OpenAI Prompt Caching Guide](https://developers.openai.com/api/docs/guides/prompt-caching)
- [OpenAI Prompt Caching 201](https://developers.openai.com/cookbook/examples/prompt_caching_201)
- [Anthropic Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Anthropic Prompt Caching Announcement](https://www.anthropic.com/news/prompt-caching)
- [OpenAI Predicted Outputs](https://developers.openai.com/api/docs/guides/predicted-outputs)
- [OpenAI Latency Optimization Guide](https://developers.openai.com/api/docs/guides/latency-optimization)
- [OpenAI Batch API](https://developers.openai.com/api/docs/guides/batch)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI Streaming Responses](https://developers.openai.com/api/docs/guides/streaming-responses)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

### Agentic Plan Caching Research
- [Agentic Plan Caching: Test-Time Memory for Fast and Cost-Efficient LLM Agents (arxiv 2506.14852)](https://arxiv.org/abs/2506.14852)
- [A Plan Reuse Mechanism for LLM-Driven Agents (arxiv 2512.21309)](https://arxiv.org/html/2512.21309v1)

### Parallel Agent Architecture
- [Parallel Agent Processing (Kore.ai)](https://www.kore.ai/ai-insights/parallel-agent-processing)
- [Scale a Multi-Agent System by Parallel Execution](https://medium.com/@manojjahgirdar/scale-a-multi-agent-system-effectively-by-parallel-execution-of-agents-acc79a126a0b)
- [AI Agent Orchestration Patterns (Microsoft)](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [The Landscape of Emerging AI Agent Architectures (arxiv 2404.11584)](https://arxiv.org/html/2404.11584v1)

### Smart Replanning
- [Build AI Agents That Resume from Failure with Pydantic AI (Prefect)](https://www.prefect.io/blog/prefect-pydantic-integration)
- [Plan and Execute: Turning Agent Plans into Action](https://mbrenndoerfer.com/writing/plan-and-execute-ai-agents)
- [AI Agent Error Handling Best Practices (Fast.io)](https://fast.io/resources/ai-agent-error-handling/)

### IfcOpenShell Performance
- [IfcOpenShell Performance: Slow File Opening (Issue #5026)](https://github.com/IfcOpenShell/IfcOpenShell/issues/5026)
- [IfcOpenShell High Memory Usage (Issue #6905)](https://github.com/IfcOpenShell/IfcOpenShell/issues/6905)
- [IfcOpenShell Optimizer Tutorial](https://academy.ifcopenshell.org/posts/ifcopenshell-optimizer-tutorial/)
- [IfcOpenShell Geometry Processing Docs](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html)

### IFC Incremental Updates
- [BlenderBIM Incremental Editing (Issue #1222)](https://github.com/IfcOpenShell/IfcOpenShell/issues/1222)
- [Native IFC Discussion (Issue #2240)](https://github.com/IfcOpenShell/IfcOpenShell/issues/2240)

### Web Viewers and Streaming
- [web-ifc: WASM IFC Parser (ThatOpen)](https://github.com/ThatOpen/engine_web-ifc)
- [ifc-lite: Rust/WASM + WebGPU IFC Viewer](https://github.com/louistrue/ifc-lite)
- [xeokit BIM Viewer SDK](https://xeokit.io/)
- [Open IFC Viewer](https://openifcviewer.com/)
