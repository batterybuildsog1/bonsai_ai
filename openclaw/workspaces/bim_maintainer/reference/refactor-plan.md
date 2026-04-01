# Refactor Plan: From Abstract Rectangles to Real Buildings

> Date: 2026-03-30
> Author: Claude Opus 4.6 (architecture analysis)
> Status: Three options for discussion
> Context: The system generates IFC geometry (columns, slabs, walls) but the output feels like abstract rectangular volumes, not real buildings with real components. The full pipeline (plan -> IFC -> structural model -> catalog selection -> section sizing -> FEA -> results) exists but is disconnected from the generation phase.

---

## Where We Are Now

The system has two distinct halves that barely talk to each other:

**Generation half** (cli.py, the planner):
- GPT-5.4 or Claude generates a JSON plan with actions like `create_column`, `create_rect_slab`
- The plan uses a 67-property god-object schema (harness-audit Issue 2)
- Actions are compiled and executed against IfcAuthor to produce an IFC file
- Output: geometry with placeholder dimensions (0.3m x 0.3m columns, 0.2m slabs)
- The planner has NO knowledge of what steel sections exist, what loads govern, or what any of it costs

**Engineering half** (design_pipeline_cli.py, the full pipeline):
- Takes the IFC, extracts a structural source model (structural_source.py)
- Maps elements to catalog families via role-based lookup (catalog_selector.py)
- Resolves to real AISC sections like W12x26, HSS6x6x3/8 (catalog_resolver.py + section_library.py)
- Runs iterative grouped sizing with PyNite FEA (grouped_sizing.py)
- Produces sized IFC, unity checks, cost summaries

**The problem**: These two halves run sequentially with no feedback. The planner generates abstract geometry. The engineering pipeline tries to make it work structurally. If the geometry is nonsensical (bay spacing too wide for the lightest beam, column heights impossible for HSS sections), the engineering pipeline either fails silently or selects the heaviest available section and reports unity > 1.0.

**The retail_terrace_concept was good because**: it used the direct planner (cli.py) with GPT-5.4's native tool calling, ran the full pipeline end to end, and the geometry happened to be reasonable for the catalog. The model got lucky with proportions, and the pipeline cleaned it up. That is not a repeatable process.

---

## Option 1: Shallow Refactor (1-2 weeks)

### Goal
Get back to retail_terrace_concept quality consistently. Make the pipeline end-to-end default, fix the known schema bugs, stop over-engineering the planner.

### What Changes

**1. Make the full pipeline the default, not the plan-only path**

Currently, `cli.py` runs ONLY the plan step. The engineering pipeline (`design_pipeline_cli.py`) is a separate entry point. Most agent sessions use `cli.py` and never run structural analysis.

Change: Wire `cli.py`'s output directly into the engineering pipeline stages. After the plan executes and produces an IFC file, automatically run:
- Structural source extraction (structural_source.py)
- Catalog selection (catalog_selector.py)
- Catalog resolution (catalog_resolver.py)
- Grouped sizing with FEA (grouped_sizing.py)
- Write the sized IFC back out

This means every run produces a building with real W-shapes and HSS sections, not placeholder 0.3m x 0.3m rectangles.

Files to modify:
- `src/bonsai_ai/cli.py` -- after `author.save()`, call the pipeline stages
- `src/bonsai_ai/design_pipeline_cli.py` -- extract the pipeline stages into importable functions (some of this is already in `pipeline.py`)

**2. Fix the known schema issues from the audit**

Apply the three critical fixes from harness-audit.md:
- Standardize slab field names (`length`/`width` everywhere, not `width`/`depth` in some places)
- Adopt the minimal system prompt (280 words instead of 598)
- Remove the 67-property god-object and replace with discriminated action types

Files to modify:
- `src/bonsai_ai_core/action_catalog.py` -- discriminated schema
- `src/bonsai_ai_core/system_prompt.py` or wherever the prompt lives -- minimal prompt
- `src/bonsai_ai/planner.py` -- fix the `_to_tool_call()` field mapping

**3. Add engineering guardrails to the system prompt**

The planner currently has zero awareness of structural feasibility. Add three sentences to the system prompt that encode basic engineering reality:
- "Column spacing should not exceed 12m for steel framed buildings."
- "Floor-to-floor heights are typically 3.5m-5.0m for commercial buildings."
- "Slab spans are limited by the available beam sections. Keep bay dimensions between 6m and 10m."

This does not make the agent an engineer. It prevents the agent from generating 30m clear spans that no W-shape in the catalog can handle.

File to modify:
- System prompt file (wherever the minimal prompt lands)

**4. Revert to direct planner as default**

The phased planner and iterative planner add complexity without improving output quality. The direct planner (GPT-5.4 with native tool calling) produced the best results.

File to modify:
- `src/bonsai_ai/cli.py` -- make the direct plan path the default, move `--via-openclaw` and `--iterative` to opt-in flags

### What the Agent Experience Looks Like

```
User: "Design a 2-story retail building, 40m x 24m"

Agent: [runs cli.py with the prompt]
  -> Planner generates a plan (storeys, columns, slabs, walls, beams)
  -> Plan executes against IfcAuthor -> produces initial IFC
  -> Structural source extraction maps columns to primary_column role, beams to floor_beam role
  -> Catalog selector maps: primary_column -> primary_columns_w (W10x33 through W18x86)
  -> Catalog resolver picks initial sections (W10x33 for columns, W12x26 for beams)
  -> Grouped sizing runs PyNite FEA, finds W10x33 has unity > 1.0 for the given loads
  -> Sizing advances to W12x40, then W12x53, stops when unity <= 1.0
  -> Sized IFC written with W12x53 columns, W18x35 beams
  -> Agent reports: "Building designed. Columns: W12x53, beams: W18x35, max unity: 0.87"

Output files:
  - model.ifc (sized geometry)
  - sizing_summary.json (iteration history, unity checks)
  - selected_section_costs.json (total steel weight)
```

### Output Quality

- **Geometry**: Same as current (rectangular columns, flat slabs, planar walls). No improvement to the visual quality of the IFC.
- **Structural**: Significant improvement. Every steel member has a real AISC section. Unity checks confirm adequacy. Cost data is real.
- **Consistency**: High. The pipeline enforces feasibility. If the planner generates impossible geometry, the sizing loop will flag it (unity > 1.0 on the heaviest section).

### What We Keep vs Discard

| Keep | Discard |
|------|---------|
| IfcAuthor and all IFC creation logic | Phased planner as default (keep as opt-in) |
| Full engineering pipeline (structural_source through grouped_sizing) | Iterative planner as default (keep as opt-in) |
| System catalog (system_catalog.py) | 67-property god-object schema |
| Section library (section_library.py) | Redundant system prompt rules |
| Viewer and agent infrastructure | Nothing else -- all infrastructure stays |
| Direct planner with tool calling | |

### Risk

| Risk | Severity | Mitigation |
|------|----------|------------|
| Schema changes break existing saved plans | Medium | Version the schema; add migration for old plans |
| Engineering pipeline fails on unusual geometry | Medium | Add graceful degradation: if sizing fails, output the unsized IFC with a warning |
| Planner still generates structurally nonsensical geometry despite guardrails | Medium | The sizing loop will catch it and report high unity ratios. The user sees the problem. |
| Two-week timeline is aggressive for schema + prompt + pipeline wiring | Low | The code for each piece exists. This is integration, not new development. |

### What the User Sees and Does

The user's experience barely changes. They describe a building. They get an IFC file. The difference:
- The IFC file has real section names on elements (W12x53 instead of "Column")
- A sizing summary appears showing structural adequacy
- A cost summary shows total steel weight in kips
- If anything fails structurally, the user sees which members are overstressed

---

## Option 2: Medium Refactor (1-2 months)

### Goal
Make the agent understand real construction. The agent does not just place rectangles and hope the pipeline makes them work -- it selects real components from catalogs during generation, checks its own work, and iterates.

### What Changes

**1. PEMB-specific primitives**

The current action types are generic BIM primitives (column, beam, slab, wall). Pre-engineered metal buildings have specific component types that do not map cleanly to these:

| PEMB Component | Current Approximation | Problem |
|---|---|---|
| Rigid frame (rafter + column, moment-connected) | Separate column + beam | Loses the rigid frame behavior. FEA treats them as independent members. |
| Tapered column / tapered rafter | Uniform rectangular column / beam | Cannot represent a column that is 12" deep at the base and 24" at the knee. |
| Purlin (Z or C section, spans between frames) | Not represented | Purlins carry roof loads to the frames. Without them, the load path is incomplete. |
| Girt (Z or C section on walls) | Not represented | Girts carry wall loads to the columns. Without them, facade design is guesswork. |
| Insulated metal panel (wall or roof) | create_panel | Loses the R-value, gauge, profile, and attachment method. |
| Endwall frame (braced frame with flush columns) | Column grid | Endwall columns are typically lighter than interior frames. Different structural behavior. |
| Bracing (rod, cable, or HSS) | Not represented cleanly | The catalog has brace_hss and brace_rod but no action type drives their creation. |
| Base plate / anchor bolt assembly | create_connection_plate | Loses the anchor bolt pattern, base plate thickness, concrete embedment. |

New action types to add:
- `create_rigid_frame` -- takes clear span, eave height, roof slope, optional haunch depth. Generates the frame geometry (two columns + rafter) as a single structural unit.
- `create_purlin_layout` -- takes frame spacing, roof slope, purlin spacing, Z/C selection. Generates purlins between frames.
- `create_girt_layout` -- takes column height, girt spacing, C section. Generates girts on wall panels.
- `create_endwall_frame` -- takes width, height, column spacing. Generates the endwall framing.
- `create_bracing_bay` -- takes frame height, bay width, brace type (rod/HSS). Generates X-bracing or V-bracing in a bay.
- `create_metal_panel` -- takes panel dimensions, profile type, R-value. Generates wall or roof panels.

Files to create/modify:
- New: `src/bonsai_ai/pemb_primitives.py` -- PEMB-specific action compilation
- New: `src/bonsai_ai/pemb_catalog.py` -- PEMB system catalog (frame sizes, purlin tables, panel specifications)
- Modify: `src/bonsai_ai_core/action_catalog.py` -- add PEMB action types
- Modify: `src/bonsai_ai/structural_source.py` -- extract structural models from PEMB frames (rigid frame -> moment-connected column+rafter)
- Modify: `src/bonsai_ai/catalog_selector.py` -- add PEMB-specific role mappings

**2. Catalog-integrated generation**

Move catalog awareness from post-processing into the generation phase. The planner should know what sections are available before it generates geometry.

Implementation:
- Include a catalog summary in the system prompt or as a reference document. The summary from `system_catalog.py`'s `starter_catalog_summary()` is compact -- catalog_id, family counts, defaults. Extend it to include the actual section lists per family.
- When the agent creates a rigid frame, it references the available frame depths. When it creates a purlin layout, it knows the purlin sections available.
- The agent's plan includes a `preferred_section` field on each structural action. The engineering pipeline respects this preference (instead of always starting from the lightest section).

Files to modify:
- System prompt or reference document injection -- include catalog data
- `src/bonsai_ai/catalog_selector.py` -- respect agent-specified preferred sections
- `src/bonsai_ai/grouped_sizing.py` -- start sizing from the agent's preferred section instead of index 0

**3. Per-project spec sheet integration**

The agent reads project-specific documents (the `--doc` flag on design_pipeline_cli.py already supports this). Extend this to the planner path:
- Agent receives the project spec sheet (e.g., "Butler MBS Frame Selection Guide")
- Agent extracts relevant constraints (max clear span, available frame depths, panel R-values)
- Agent uses these constraints during generation

Files to modify:
- `src/bonsai_ai/cli.py` -- add `--doc` flag, pass documents to the planner
- Planner system prompt -- instructions for reading and applying spec sheet constraints

**4. Structural verification feedback loop**

After generation, the agent runs structural analysis and checks the results. If members are overstressed, the agent modifies the design (not just the section size -- the geometry itself).

```
Agent generates: 60ft clear span rigid frame with W12x26 rafters
Pipeline reports: rafter unity = 3.4 (severely overstressed)
Agent thinks: "The span is too wide for a light rafter. I should either:
  (a) add an interior column to split the span, or
  (b) switch to a tapered rafter, or
  (c) increase the frame spacing to reduce tributary load"
Agent modifies the design and re-runs analysis
```

This is fundamentally different from the current system where sizing just picks a heavier section. The agent has architectural judgment -- it can change the building's configuration, not just the member sizes.

Implementation:
- After the engineering pipeline runs, return the analysis results to the agent
- The agent has a decision prompt: "These members are overstressed. Your options: change geometry, accept heavier sections, or flag for engineer review."
- The agent modifies the plan and re-runs (up to 3 iterations)

Files to create/modify:
- New: `src/bonsai_ai/design_feedback.py` -- formats analysis results for the agent, presents options
- Modify: `src/bonsai_ai/cli.py` -- add the feedback loop (generate -> analyze -> evaluate -> modify -> re-analyze)

### What the Agent Experience Looks Like

```
User: "Design a 60x120 ft PEMB warehouse with 16ft eave height"

Agent: I will design this as a pre-engineered metal building.

[Agent reads project spec sheet if provided]
[Agent reviews available catalog: rigid frames up to 80ft span, Z-purlins, C-girts, insulated panels]

Agent thinks: "60ft clear span, 16ft eave, 4:12 roof pitch. Standard rigid frame spacing 25ft.
  That gives me 5 frames (4 bays at 30ft spacing, total 120ft).
  Purlins at 5ft on center. Girts at 5ft6 on center."

[Agent runs: create_rigid_frame for each frame line]
[Agent runs: create_purlin_layout between frames]
[Agent runs: create_girt_layout on sidewalls]
[Agent runs: create_endwall_frame at each end]
[Agent runs: create_bracing_bay in one sidewall bay and one endwall bay]
[Agent runs: create_metal_panel on all walls and roof]

[Pipeline runs structural analysis]
  -> Frame rafter: unity 0.78 with tapered W24 section
  -> Purlins: unity 0.65 with Z10-12ga at 5ft spacing
  -> Girts: unity 0.52 with C8-12ga at 5.5ft spacing
  -> Bracing: unity 0.45 with HSS4x4x1/4

Agent: "All members adequate. Building complete."

Output: IFC with real PEMB components, structural report, cost summary
```

### Output Quality

- **Geometry**: Major improvement. The IFC represents real PEMB components (rigid frames, purlins, girts, panels) instead of generic rectangles. The building looks like a metal building, not a box.
- **Structural**: Major improvement. The agent selects components with structural awareness. The feedback loop catches geometric problems, not just section inadequacy.
- **Realism**: The building has the right number of purlins, girts, bracing bays. It reads like a real set of erection drawings, not a concept sketch.
- **Cost accuracy**: Much better. The cost summary reflects real PEMB components (frame weight, secondary steel weight, panel area) instead of generic steel tonnage.

### What We Keep vs Discard

| Keep | Discard |
|------|---------|
| Everything from Option 1 | The god-object schema (replaced by discriminated types + PEMB primitives) |
| IfcAuthor (extended with PEMB element creation) | Generic-only generation (PEMB primitives supplement, not replace, the generic ones) |
| Full engineering pipeline | Static section assignment (replaced by catalog-aware generation) |
| Viewer, agents, infrastructure | Nothing major -- this is additive |
| Section library + system catalog (extended) | |

### Risk

| Risk | Severity | Mitigation |
|------|----------|------------|
| PEMB primitives are complex to implement correctly | High | Start with rigid frames only. Add purlins, girts, panels incrementally. |
| Catalog integration makes the system prompt too large | Medium | Use a separate reference document, not inline in the prompt. Summarize key constraints. |
| Feedback loop may oscillate (agent changes geometry, analysis fails differently, agent changes again) | Medium | Cap iterations at 3. On the 3rd failure, accept the best result and flag for review. |
| Tapered members are not in the current section library | High | The section_library.py only has prismatic W/HSS/ROD sections. Tapered members need web depth as a function of position. This is a significant data model extension. |
| One-month timeline is tight for PEMB primitives + feedback loop | Medium | Phase it: week 1-2 catalog integration + feedback loop, week 3-4 PEMB primitives. |

### What the User Sees and Does

The user describes a building (now with PEMB-specific language: "60x120 PEMB warehouse"). They get:
- An IFC file with real PEMB components visible in the viewer
- A structural report showing every member's adequacy
- A cost summary broken down by: primary frames, secondary steel, panels, connections
- If the agent modified the design during the feedback loop, a design log explaining what changed and why

The user can also provide spec sheets (`--doc butler-frame-guide.pdf`) and the agent will reference them during design.

---

## Option 3: Deep Refactor (3-6 months)

### Goal
The agent IS the designer. It operates iteratively through simple CLI tools, one command at a time, with immediate feedback. The tool library grows over time based on what the agent needs. The agent and a maintainer agent communicate to extend the tools.

### What Changes

**1. The `bim` CLI (from simple-tool-interface.md research)**

Replace the entire plan-based generation system with the simple CLI interface. The agent calls bash commands, reads results, decides next steps.

```bash
bim storey "Ground Floor" --elevation 0
bim column-grid "Main Grid" --storey "Ground Floor" --origin 0,0 --bays 5,3 --spacing 8,8 --column-size 0.3,0.3 --height 4.5
bim slab "GF Slab" --storey "Ground Floor" --corner 0,0 --size 40,24 --thickness 0.2 --elevation 0
bim info
bim check
```

Each command:
- Takes 3-8 parameters (not 67)
- Returns JSON to stdout
- Saves the model immediately
- Has `--help` with full documentation
- Is self-describing (the agent can run `bim --help` to learn the interface)

This eliminates:
- The 67-property god-object schema
- The plan compiler
- The system prompt (replaced by `bim --help`)
- The `_to_tool_call()` mapping layer
- The `_coerce_numeric_fields()` workaround

Files to create:
- `scripts/bim.py` -- the CLI (approximately 400-500 lines, one function per subcommand)

Files to deprecate (not delete, but no longer the primary path):
- `src/bonsai_ai_core/action_catalog.py` -- no longer needed for agent-facing interface
- `src/bonsai_ai/planner.py` (the plan compilation logic) -- replaced by direct CLI execution
- `src/bonsai_ai_core/system_prompt.py` -- `bim --help` is the new system prompt

**2. Engineering tools alongside BIM tools**

The agent does not just create geometry. It also runs analysis, queries catalogs, and checks costs.

```bash
# Engineering commands
bim analyze --model out/model.ifc --load-case "gravity"
  -> {"members": 48, "max_unity": 0.87, "overstressed": ["Col-A3: unity 1.12"]}

bim catalog list --family primary_columns_w
  -> ["W10x33", "W10x49", "W12x40", "W12x53", "W14x68", "W14x90"]

bim catalog info W12x53
  -> {"area_in2": 15.6, "ix_in4": 425, "weight_lb_ft": 53, "fy_ksi": 50}

bim cost-estimate --model out/model.ifc
  -> {"total_steel_tons": 12.3, "estimated_cost": "$18,450", "breakdown": {...}}

bim size --model out/model.ifc --strategy grouped
  -> {"iterations": 4, "final_max_unity": 0.91, "sections_changed": 12}

bim resize "Col-A3" --section W14x68
  -> {"element": "Col-A3", "old_section": "W12x40", "new_section": "W14x68"}
```

Files to create:
- Extend `scripts/bim.py` with `analyze`, `catalog`, `cost-estimate`, `size`, `resize` subcommands
- These wrap the existing pipeline stages (structural_source.py, catalog_selector.py, grouped_sizing.py) behind simple CLI interfaces

**3. Iterative agent workflow with real feedback**

The agent builds incrementally, checking its work at each stage:

```
Phase 1: Structure
  bim storey ...
  bim column-grid ...
  bim slab ...
  bim info  # "48 columns, 2 slabs, 3 storeys"
  bim analyze --load-case gravity
    -> "Max unity 0.64. All members adequate."

Phase 2: Envelope
  bim perimeter-walls ...
  bim window ...
  bim check  # "No orphan elements. All windows hosted."
  bim analyze --load-case wind
    -> "Facade columns overstressed: unity 1.3 on HSS6x6"
  bim resize "Facade-Col-01" --section HSS8x8x3/8
  bim analyze --load-case wind
    -> "Max unity 0.88. All members adequate."

Phase 3: Review
  bim cost-estimate
    -> "Total steel: 15.2 tons, $22,800"
  bim info --detailed
    -> Full element list with sections, lengths, weights
```

The agent thinks between commands. It reads the result. It makes judgment calls. This is how a real designer works -- not by producing a complete plan in one shot, but by building up, testing, and refining.

**4. Agent-maintainer communication**

When the agent encounters a limitation in the tools, it tells the maintainer agent:

```
Agent: "I need to create a tapered rigid frame but `bim` does not have a
       rigid-frame command. The closest I can do is place separate columns
       and rafters, but they won't be moment-connected in the analysis model."

Maintainer: "I'll add `bim rigid-frame` as a new subcommand. It will take
            clear span, eave height, roof slope, and optionally column taper
            and rafter taper. The structural model will treat the knee as a
            moment connection. I'll have it ready in the next update."

[Maintainer adds cmd_rigid_frame to scripts/bim.py]
[Maintainer adds rigid frame handling to structural_source.py]
[Next time the agent runs, it uses `bim rigid-frame`]
```

This is how the tool library grows organically:
- The agent discovers what it needs by trying to design real buildings
- The maintainer implements what the agent asks for
- Over time, the CLI accumulates the primitives that actually matter for real buildings
- No premature abstraction -- tools are added in response to real needs

Implementation:
- The agent writes tool requests to a shared file or issue tracker
- The maintainer reads these requests and implements them
- A changelog or version bump signals to the agent that new tools are available
- The agent runs `bim --help` to discover new commands

Files to create:
- Communication protocol (could be as simple as a markdown file in the workspace, or a GitHub issue template)
- The maintainer's implementation workflow (test harness, integration tests for new commands)

**5. Real project context**

The agent can:
- Upload reference photos (`bim reference --photo existing-building.jpg`) -- the agent describes what it sees and uses it as design context
- Read spec sheets (`bim reference --doc butler-catalog.pdf`) -- the agent extracts constraints and applies them
- Ask the user questions (`bim question "What is the intended use of the mezzanine area?"`) -- the agent gathers requirements interactively
- Access site data (`bim site --location "Austin, TX"`) -- wind speed, seismic category, soil conditions

These are not implemented as complex integrations. They are simple tools that provide context. The agent's reasoning handles the rest.

### What the Agent Experience Looks Like

```
User: "I need a 60x120 PEMB warehouse in Austin, TX. 16ft eave height, one
      14x14 overhead door on the south endwall, two 3070 man doors on the
      east sidewall. I want insulated panels, R-19 walls, R-25 roof."

Agent: Let me start by understanding the site conditions.

[bim site --location "Austin, TX"]
  -> {"wind_speed_mph": 115, "exposure": "C", "seismic_sds": 0.15, "ground_snow_psf": 0}

Agent: No snow load, moderate wind. I will design for 115 mph wind, Exposure C.

[bim storey "Ground Floor" --elevation 0]
[bim storey "Eave" --elevation 4.877]  # 16ft

Agent: Building is 60ft wide (18.288m) x 120ft long (36.576m). I will use
5 rigid frames at 30ft (9.144m) spacing.

[bim rigid-frame "Frame-1" --storey "Ground Floor" --origin 0,0 --clear-span 18.288 --eave-height 4.877 --roof-slope 0.25 --frame-spacing 9.144]
  -> {"error": "Unknown command 'rigid-frame'. Run 'bim --help' for available commands."}

Agent: The rigid-frame command is not available yet. I will request it from the
maintainer and use column + beam as a workaround for now.

[bim column "Frame-1-Col-Left" --storey "Ground Floor" --x 0 --y 0 --height 4.877 --size 0.3,0.3]
[bim column "Frame-1-Col-Right" --storey "Ground Floor" --x 18.288 --y 0 --height 4.877 --size 0.3,0.3]
[bim beam "Frame-1-Rafter" --storey "Ground Floor" --start 0,0,4.877 --end 18.288,0,4.877 --size 0.3,0.5]

[... repeats for 5 frames ...]

[bim info]
  -> {"columns": 10, "beams": 5, "storeys": 2}

[bim analyze --load-case gravity]
  -> {"max_unity": 0.43, "all_adequate": true}

[bim analyze --load-case "wind_115_exp_c"]
  -> {"max_unity": 1.67, "overstressed": ["Frame-1-Rafter", "Frame-2-Rafter", ...]}

Agent: Rafters are overstressed in wind. The 60ft span with uniform W-sections
cannot handle 115 mph wind. I need either deeper rafters or a tapered section.

[bim catalog list --family primary_beams_w]
  -> ["W12x26", "W12x35", "W14x30", "W16x31", "W18x35", "W21x44", "W24x55", "W27x84"]

Agent: W27x84 is the deepest available beam. Let me try it.

[bim resize "Frame-1-Rafter" --section W27x84]
[... resize all rafters ...]
[bim analyze --load-case "wind_115_exp_c"]
  -> {"max_unity": 0.94, "all_adequate": true}

Agent: W27x84 works but is heavy. In a real PEMB, tapered rafters would be
more efficient. I am noting this as a tool request for the maintainer.

[Writes tool request: "Need `bim rigid-frame` with tapered member support"]

[bim perimeter-walls "South Endwall" --storey "Ground Floor" --corners 0,0 18.288,0 --height 4.877 --thickness 0.15]
[bim door "OH Door" --storey "Ground Floor" --wall "South Endwall" --offset 2.134 --size 4.267,4.267]

[... continues with envelope, doors, windows ...]

[bim cost-estimate]
  -> {"primary_frames_tons": 8.4, "secondary_steel_tons": 3.1, "panels_sqft": 12800,
      "estimated_total": "$142,000"}

Agent: Building complete. Summary:
  - 5 rigid frames (approximated as column+beam) at 30ft spacing
  - W27x84 rafters, W14x68 columns
  - 60x120ft footprint, 16ft eave height
  - 14x14 overhead door on south, 2 man doors on east
  - Structural analysis passes all load cases (max unity 0.94)
  - Estimated cost: $142,000

  Note: Tapered rigid frame support would reduce primary steel weight by
  approximately 25-30%. Tool request submitted.
```

### Output Quality

- **Geometry**: Depends on available tools. Initially similar to current (columns, beams, slabs). Improves over time as the maintainer adds PEMB-specific commands (rigid-frame, purlin-layout, etc.).
- **Structural**: Best of the three options. The agent checks its own work at every stage. It can change the design based on analysis results, not just upsize sections.
- **Realism**: Grows over time. Each new tool added by the maintainer makes the output more realistic. After 6 months of agent-maintainer collaboration, the tool library should cover most common PEMB components.
- **Adaptability**: Highest. The agent can design buildings the tools do not fully support by approximating with available primitives and flagging gaps.

### What We Keep vs Discard

| Keep | Discard |
|------|---------|
| IfcAuthor (wrapped by bim CLI) | Plan-based generation as the primary path |
| Full engineering pipeline (wrapped by bim analyze/size) | 67-property god-object schema |
| Section library + system catalog | Plan compiler |
| Viewer | System prompt (replaced by bim --help) |
| Agent infrastructure | _to_tool_call() mapping layer |
| Grouped sizing engine | _coerce_numeric_fields() workarounds |

Note: "Discard" means "no longer the agent-facing interface." The plan-based system can remain as an internal implementation detail or a batch mode behind `bim batch`.

### Risk

| Risk | Severity | Mitigation |
|------|----------|------------|
| Building the bim CLI is significant development work | Medium | The research document (simple-tool-interface.md) estimates 400-500 lines. The IfcAuthor methods already exist. The CLI is a thin wrapper. |
| Agent makes more round trips (15-30 commands vs 1 plan) | Medium | Batch mode reduces round trips. Also, each round trip gives the agent feedback, so fewer total attempts are needed. |
| Agent-maintainer communication requires a workflow | Medium | Start simple: markdown files in the workspace. Upgrade to GitHub issues if needed. |
| Initial tool library is sparse -- agent output quality may dip before it improves | High | Run Option 1 in parallel. Keep the plan-based system working while building out the CLI. Switch over when the CLI reaches feature parity. |
| 3-6 month timeline means delayed impact | High | Prioritize the highest-value tools first: rigid-frame, purlin-layout, analyze, size. These cover 80% of PEMB design. |
| The agent may request tools that are expensive to build (tapered members, connection design) | Medium | The maintainer triages requests. Quick wins (new section shapes in the catalog) ship fast. Complex features (tapered members) get queued. |

### What the User Sees and Does

The user describes a building, same as today. But now:

**During design**: The user can watch the agent work in real time (each bim command appears in the agent's output). The user sees the agent's reasoning: "Rafters overstressed, trying W27x84." The user can interrupt: "Use HSS columns instead of W-shapes on the endwall."

**After design**: The user gets:
- An IFC file with real components
- A design log showing every command the agent ran, with results
- A structural report with unity checks per member
- A cost estimate
- A list of tool limitations the agent encountered (e.g., "no tapered frame support")

**Over time**: The user sees the tool library grow. Last month, the agent could only make rectangular buildings. This month, it can create rigid frames. Next month, it can do tapered members. The user's experience improves with each tool addition, without any change to their workflow.

---

## Comparison Summary

| Dimension | Option 1 (Shallow) | Option 2 (Medium) | Option 3 (Deep) |
|-----------|--------------------|--------------------|------------------|
| Timeline | 1-2 weeks | 1-2 months | 3-6 months |
| Geometry quality | Same as current | Significantly better (PEMB primitives) | Grows over time |
| Structural quality | Major improvement (real sections) | Major improvement (catalog-aware + feedback) | Best (iterative verification) |
| Agent intelligence | Low (planner generates, pipeline fixes) | Medium (agent selects components, checks work) | High (agent IS the designer) |
| Risk | Low | Medium | Medium-High (but highest long-term payoff) |
| Architectural change | Small (wire pipeline into cli.py) | Medium (new primitives, feedback loop) | Large (replace plan system with CLI) |
| Maintenance burden | Low | Medium (new primitives need testing) | Low long-term (tools are simple, composable) |
| User experience change | Minimal | Moderate (PEMB-specific features) | Significant (interactive design, growing tool library) |
| What it proves | "We can ship real buildings today" | "We can build PEMB-specific intelligence" | "The agent can grow into a real designer" |

---

## Recommended Path

**Do Option 1 now. Start Option 3 in parallel.**

Option 1 gets us back to shipping real buildings within 2 weeks. The full pipeline already exists -- it just needs to be wired into the default path. The schema fixes and prompt improvements are well-understood changes from the audit.

Option 3 is the right long-term architecture. The bim CLI matches how every commercial BIM scripting tool works, how every modern AI code tool works, and how the agent-maintainer collaboration should work. But it takes time, and we need real output quality NOW.

Option 2 is the trap. It adds PEMB-specific complexity to the existing plan-based architecture -- the same architecture we want to replace. The PEMB primitives are valuable, but they should be implemented as bim CLI subcommands (Option 3), not as new action types in the god-object schema (Option 2).

**Concrete plan:**
1. **Week 1-2**: Ship Option 1. Wire the full pipeline into cli.py. Fix the schema. Deploy the minimal prompt.
2. **Week 2-4**: Build the bim CLI core (storey, column-grid, slab, wall, beam, info, check). Test with the agent.
3. **Month 2-3**: Add engineering commands (analyze, size, catalog, cost-estimate). Add PEMB commands (rigid-frame, purlin-layout).
4. **Month 3-6**: Switch the agent to the bim CLI as its primary interface. Maintain the plan-based system as a batch/compatibility layer. Let agent-maintainer collaboration drive tool library growth.

This way, output quality improves immediately (Option 1), while the long-term architecture takes shape underneath (Option 3).
