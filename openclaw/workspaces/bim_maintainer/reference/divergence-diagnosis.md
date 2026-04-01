# Bonsai AI Divergence Diagnosis

**Date:** 2026-03-30
**Status:** Brutally honest post-mortem

---

## 1. What the App Can Already Do (That We Are Not Using)

The codebase contains a **complete design pipeline** that goes far beyond what
the prompt-to-IFC path currently exercises. Here is what already exists and
works:

### Full Design Pipeline (`design_pipeline_cli.py` + `pipeline.py`)
- **Plan** -> physical model via LLM
- **IFC materialization** via `IfcPhysicalModelBackend`
- **Structural source model extraction** (`structural_source.py`) -- converts
  the physical plan into a proper engineering model with elements, materials,
  sections, supports, load paths, and analysis domains
- **Catalog selection** (`catalog_selector.py`) -- maps each structural element
  to a real member family from the system catalog based on its role
- **Section resolution** (`catalog_resolver.py`) -- resolves catalog families to
  actual AISC sections with real properties
- **Grouped section sizing** (`grouped_sizing.py`) -- iterates up to 8 times
  through solve-evaluate-upsize loops to find adequate sections for every
  sizing group
- **FEA via PyNite** (`pynite_backend.py`) -- actual structural analysis with
  real member demands
- **FreeCAD handoff** (`freecad_runner.py`) -- exports analysis models for
  further engineering

### Real Component Catalog (`system_catalog.py` + `section_library.py`)
The starter catalog knows about:
- **W-shapes**: W10x33 through W27x84, with full AISC v16 section properties
  (area, Ix, Iy, J, depth, width, tw, tf, weight)
- **HSS tubes**: HSS4x4x1/4 through HSS12x12x1/2
- **Cold-formed girts/purlins**: C8 through C14, Z8 through Z14
- **Rods**: 1" through 1-1/2"
- **Material specs**: ASTM A992 (W-shapes), ASTM A500 Grade C (HSS), with
  yield/ultimate strengths
- **Panel systems**: InnovaCast ICP wall panels with size rules (max 50ft
  height, max 12ft width, 6" width increments)
- **Connection families**: shear tabs, gusset plates, base plates, secondary
  clips, panel embeds
- **Footing families**: spread footings, retaining footings, pedestals, grade
  beam ties, micropile caps

### Techridge Proved It Works
The `build_techridge_initial_shell.py` script ran the **full pipeline** and
produced:
- 150 primary columns assigned to `primary_columns_w`
- 310 primary beams assigned to `primary_beams_w`
- 330 facade posts assigned to `facade_posts_hss`
- 198 opening support members assigned to `opening_support_w`
- 16 wall girts, 16 roof purlins, 16 braces
- All sized to real AISC sections (W8x18, HSS4x4x1/4, etc.) through iterative
  FEA
- Engineering models broken down by scope: global_frame, roof_load_path,
  facade_support, substructure, opening_support
- Analytical models with load cases, material specs, and support conditions
- Cost table with real section-based pricing

**None of this runs when a user types a prompt into the chat interface.** The
chat path stops at "plan" and writes generic IFC geometry. Everything after that
-- catalog selection, member sizing, structural analysis, cost estimation -- is
dead code from the user's perspective.

---

## 2. What We Built That Added Complexity Without Value

### The Planner Proliferation
We now have **four** planner implementations, each worse than the last for the
core use case:

1. **`planner.py` + `bonsai_ai_core`** -- The original. Calls `build_plan()`
   which sends a single prompt to GPT/Claude/Gemini with the full building
   context. The model sees the whole problem at once and returns a coherent
   plan. This produced the retail terrace concept. **This was the best path.**

2. **`openclaw_planner.py`** -- Routes through OpenClaw subprocess instead of
   direct API calls. Added: subprocess management, JSON envelope unwrapping,
   binary location searching, 20-minute timeouts. The agent overhead means the
   model receives the prompt through an intermediary that adds latency and
   parsing fragility. **Net value: authentication convenience at the cost of
   reliability.**

3. **`phased_planner.py`** -- Decomposes building into phases (storeys ->
   structure -> envelope -> openings -> foundations), then fires independent
   subprocess calls per phase. This is the critical mistake.

   **Why phase isolation kills quality:** When the model plans storeys, it does
   not know what the structure phase will need. When it plans structure, it
   cannot reason about facade panel joints. When it plans envelope, it cannot
   coordinate with the structural grid. Each phase is a blind subprocess call
   with a ~1000 character prompt. The model that generated a 12,000 sqft retail
   terrace with 52 columns, 92 beams, 126 railing members, 17 windows, and 4
   doors in a single coherent pass is now asked to generate "storeys" in
   isolation without knowing the building.

   The phased planner also introduced ~300 lines of action normalization code
   (`_normalize_actions`, `_TYPE_ALIASES`, `_FIELD_ALIASES`,
   `_BEAM_FIELD_ALIASES`, `_NUMERIC_FIELDS`, `_coerce_numeric`) to paper over
   the fact that small, context-poor prompts produce worse structured output
   than one rich prompt.

4. **`iterative_planner.py`** -- Adds session persistence so the agent
   "remembers" previous turns. Same phase isolation problem but with
   conversation state. Still fires separate subprocess calls. Still cannot
   reason across concerns. Added: UUID session management, retry logic, turn
   reporting, ~550 lines of code. The retry-on-failure pattern masks the root
   cause (bad plans) with retries that produce equally bad plans.

### The Normalization Tax
Because the phased/iterative planners get worse output from the LLM (due to
smaller context and no native tool calling), we built an entire normalization
layer:

- `_TYPE_ALIASES`: 7 action type mappings
- `_FIELD_ALIASES`: field name remappings
- `_BEAM_FIELD_ALIASES`: beam-specific field fixes
- `_NUMERIC_FIELDS`: 35+ fields that need string-to-number coercion
- `_coerce_numeric()`: strips unit suffixes like "0.5m" or "200mm"
- Fallback dimension borrowing (depth from length, etc.)
- Compilation retry after forced numeric coercion

This normalization code exists because we gave the LLM bad prompts and got bad
structured output. The original `planner.py` using native tool calling did not
need any of this.

### Infrastructure That Serves Infrastructure
- Mojo FEA optimization research (never used in production path)
- Blender addon packaging and distribution pipeline
- Multiple viewer implementations (web, Blender, review renders)
- Cloudflare tunnel setup scripts
- Component packaging system (InnovaCast placeholder)

Each of these is reasonable in isolation. Together they consumed development
time that should have gone to the core question: "Does the AI output look like
a real building?"

---

## 3. Where Quality Went Down and Why

### The Retail Terrace Was the Peak
`build_retail_terrace_concept.py` is 500+ lines of hand-crafted Python that
calls `IfcAuthor` directly. It produced:

- 4 storeys with correct elevations
- 8 walls with concrete material metadata
- 4 slabs at proper thicknesses (0.30m ground, 0.25m upper, 0.22m roof)
- 52 columns with exposed steel semantics
- 92 beams with perimeter frame geometry
- 17 windows hosted in real walls
- 4 doors with proper offsets
- 7 panels with cladding/accent distinction and panel strip logic
- 6 footings sized from imposed loads via `starter_footing_from_imposed_load`
- 126 railing members (posts and rails as steel columns/beams)
- Proper terrace walkway geometry
- Semantic metadata on every element (role, subrole, system_name, group_path,
  view_mode)
- Presentation metadata (material_key, presentation_style)

This was not AI-generated. This was a human writing the ideal output that the
AI should produce. It is the reference implementation we should be measuring
against.

### What the LLM-Driven Path Actually Produces
When a user types a prompt and it goes through the planner path, they get:

- Rectangular boxes with dimensions
- Generic "Wall 1", "Column A1" names
- No material specifications on elements
- No semantic grouping (no system_name, no group_path, no view_mode)
- No presentation metadata (no material_key, no presentation_style)
- Columns defined by width/depth in meters, not by W-shape or HSS designation
- Beams with arbitrary rectangular profiles, not engineering sections
- No cladding panels (the model uses `create_wall` for everything)
- No railing systems
- No foundation sizing from loads
- No connection awareness

The output is geometrically correct enough to render but architecturally
meaningless. A 36m x 31m retail building with terraces becomes "4 walls, 1
slab, some columns."

### Why Quality Degraded at Each Step

**Step 1: Single prompt -> good plan.** The `bonsai_ai_core` planner sends one
rich prompt with the full system prompt, all tool schemas, scene summary, and
the user request. The model (GPT-4/5, Claude) sees everything at once and
generates a coherent, coordinated plan. Tool calling enforces the schema.

**Step 2: OpenClaw routing -> latency + parsing fragility.** Instead of native
tool calling, the model response comes back as a JSON text blob inside an
OpenClaw subprocess stdout, which may be inside a JSON envelope
(`result.payloads[0].text`), may be in stderr, or may need fence extraction.
Five extraction strategies in `_extract_json()` exist because the transport is
unreliable.

**Step 3: Phase decomposition -> broken cross-concern reasoning.** The single
coherent plan is now 6 independent plans. Each phase prompt is ~1000 characters
instead of the original ~3000. The model cannot coordinate:
- Column grid spacing with facade panel joints
- Beam depths with storey heights
- Foundation loads with structural member sizing
- Window positions with structural openings in the facade

**Step 4: Iterative sessions -> accumulating errors.** The iterative planner
feeds error reports from failed phases back into subsequent turns. The model
tries to "fix" spatial misalignments that should not exist if the plan were
generated holistically. Each retry adds confusion to the conversation context.

---

## 4. What the User Actually Wants vs. What We Are Delivering

### What the User Wants

"I want to describe a building using real construction components -- insulated
concrete panels with 1-inch Sika Flex joints, tapered moment frames, W12x26
beams, HSS8x8 columns, real glass storefront systems, foundations sized for my
loads -- and have the AI build it in Blender/IFC, iteratively, so I can review
and refine it. I want to upload my site survey and spec sheets and have the
agent use them."

### What We Deliver

"Here are some rectangular boxes arranged in a building shape. The walls are
0.25m thick. The columns are 0.3m x 0.3m. There is no concept of what material
they are, what engineering section they use, or how they connect to each other.
The foundations are not sized. The panels have no joint gaps. The moment frames
do not exist. Your spec sheets are not referenced."

### The Gap Is Not in Infrastructure

We have the catalog. We have the section library. We have the sizing pipeline.
We have the structural analysis. The gap is that **none of it is connected to
the prompt-driven path.** The user's prompt goes to a planner that outputs
`create_wall(thickness=0.25)` instead of "place an InnovaCast ICP panel, 10ft
wide, 24ft tall, with 1.5in joint gaps, supported by HSS6x6x1/4 facade posts
at the panel joints."

---

## 5. The Gap Between "Rectangular Boxes" and "Real Buildings with Real Components"

### What a Real Building Element Looks Like (from techridge)
```
Element: facade_post
  Catalog family: facade_posts_hss
  Selected section: HSS6x6x1/4
  Material: ASTM A500 Grade C (Fy=50ksi, Fu=62ksi)
  Section properties: A=5.24 in2, Ix=28.6 in4, depth=6.0in
  Sizing group: facade_posts_hss|facade_post|facade:south_main_tier
  Role in load path: supports panel dead load + wind load
  Connected to: panel_support_embed_or_clip -> innovacast_icp_wall_panel
```

### What the Planner Actually Outputs
```
create_column(name="Column 1", x=0, y=0, base_z=0, width=0.3, depth=0.3, height=5.0)
```

No catalog reference. No section designation. No material. No load path
awareness. No connection type. Just a 300mm box that is 5 meters tall.

### The Five Missing Bridges

1. **Prompt -> Catalog awareness.** The LLM prompt does not mention the system
   catalog. The model does not know that W12x26 beams or HSS8x8 columns exist.
   It generates arbitrary dimensions because that is all the tool schema asks
   for.

2. **Tool schema -> Real components.** The `create_column` tool takes
   `width`/`depth` in meters. It does not take a section designation like
   "W14x68" or "HSS8x8x3/8." The tool itself cannot represent a real
   component.

3. **Plan output -> Catalog selection.** The catalog selector
   (`catalog_selector.py`) maps structural roles to member families. But it
   operates on the `StructuralSourceModel`, which is built from the physical
   plan. If the plan has no role metadata, the source model has nothing to
   select from.

4. **Catalog selection -> Section sizing.** The grouped sizer
   (`grouped_sizing.py`) iterates through FEA to find adequate sections. But it
   needs the catalog selection to have run first, and the catalog selection
   needs the structural source model, which needs a plan with proper semantic
   metadata.

5. **Section sizing -> Updated IFC.** Even after sizing, `plan_roundtrip.py`
   applies sized sections back to the physical model. But this only works if
   the full pipeline ran, which it never does on the prompt-driven path.

---

## 6. Why GPT-5.4 with Direct Tool Calling Produced Better Results Than Our Iterative System

### The Single-Prompt Advantage

The `bonsai_ai_core` planner (`build_plan()`) does one thing well: it sends a
rich system prompt with all tool schemas to a frontier model and lets the model
generate the entire plan in one pass. The model can:

- See the full building request and all available tools simultaneously
- Coordinate column grid spacing with beam layouts
- Place windows only in walls (because it knows which walls it just created)
- Size foundations relative to the structure above
- Use generators (column_grid, floor_plate) to reduce action count
- Apply consistent naming and metadata across all elements

This is how GPT-5.4 (or any capable model) works best: give it the full
context and let it reason. Native tool calling schemas enforce the output
format without fragile JSON parsing.

### What We Broke

1. **Context fragmentation.** We split the single rich prompt into 6 tiny
   prompts. Each phase sees ~1000 characters instead of the full building
   context. The model generates storeys without knowing the structure, structure
   without knowing the envelope, envelope without knowing the openings.

2. **Tool calling -> text parsing.** The OpenClaw subprocess path receives the
   model output as text (not as parsed tool calls). We then need 5 JSON
   extraction strategies, action type normalization, field name aliasing, and
   numeric coercion. Every step introduces failure modes that did not exist with
   native tool calling.

3. **Holistic reasoning -> sequential execution.** A frontier model can hold a
   5-story commercial building in context and generate 50+ coordinated actions.
   Our phased system asks it to generate ~8 actions per phase, blind to what
   other phases will do. This is like asking an architect to design the
   foundation without seeing the building above it.

4. **Quality -> complexity.** Every layer we added (OpenClaw routing, phase
   decomposition, session management, normalization, retry logic) was built to
   solve a problem introduced by the previous layer. The original path had none
   of these problems because it did not need any of these solutions.

### The Retail Terrace Lesson

The `build_retail_terrace_concept.py` script was written by a human who
understood the building. It called `IfcAuthor` methods with precise parameters,
semantic metadata, and presentation hints. The question is not "how do we make
the LLM do what a human did in 500 lines of Python" -- it is "how do we give
the LLM enough context and the right tools to approach that level of detail."

The answer was already in the codebase: `design_pipeline_cli.py` runs the full
pipeline (plan -> structural source -> catalog -> sizing -> analysis). The
prompt-driven chat path runs only the plan step and stops. The fix is not more
infrastructure. The fix is connecting what we already built.

---

## Diagnosis Summary

| Aspect | What We Have | What We Use |
|--------|-------------|-------------|
| Section library (AISC v16) | 26 real sections with full properties | Not exposed to planner |
| System catalog | 10 member families, 5 footing families, 5 connection types | Not referenced in prompts |
| Catalog selection | Maps roles to families automatically | Dead code on prompt path |
| Grouped section sizing | Iterative FEA with up-sizing | Dead code on prompt path |
| Material specs | ASTM A992, A500 Grade C, with Fy/Fu | Not in tool schemas |
| Panel systems | InnovaCast ICP with size rules | Not in tool schemas |
| Structural analysis (PyNite) | Full FEA solver | Dead code on prompt path |
| Design pipeline | Plan through results bundle | Only "plan" step used |
| Planner backends | 4 implementations | Each worse than the previous |
| Normalization code | ~200 lines of field/type fixing | Only needed because of bad prompts |

**The root cause is not missing capability. It is that we built the capability,
then built a prompt path that bypasses all of it, then spent months adding
complexity to the prompt path instead of connecting it to the capability we
already had.**
