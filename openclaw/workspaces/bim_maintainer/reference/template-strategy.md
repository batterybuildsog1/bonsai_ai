# Template Strategy for Bonsai AI

Date: 2026-03-30

## Why "Template Plan Library" Feels Wrong

The original proposal -- pre-compiled plans for common building types (simple office,
warehouse, etc.) that bypass the AI planner -- is the wrong abstraction. Here is why:

1. **Buildings are not templates.** Every real building is site-specific. Orientation,
   lot shape, setbacks, program mix, and code jurisdiction make "a 3-story office"
   useless without a dozen qualifiers. A static template either matches the user's
   intent exactly (unlikely) or needs so many overrides that you have rebuilt the
   planner with worse ergonomics.

2. **The AI planner is the product.** Bypassing it removes the thing that makes
   Bonsai AI different from a CAD macro library. Users come for natural language
   to BIM, not for a dropdown of pre-made buildings.

3. **The real bottleneck is rounds, not intelligence.** The planner takes 3-15s
   per round, up to 12 rounds. The slowness is network round-trips, not the AI
   thinking hard about what a building should look like. Templates don't fix the
   networking problem -- they sidestep it by removing the AI entirely.

What DOES make sense: giving the AI planner **better tools** so it can express
common patterns in fewer tokens and fewer rounds. That is what commercial BIM
tools actually do.

---

## What Commercial BIM Tools Actually Template

No major BIM tool ships "building templates" in the way the original proposal
imagined. Here is what they DO template, and why:

### Revit: Families + Project Templates

- **Families** are parametric component definitions: a door, a window, a column
  type, a curtain wall panel. Each family has parameters (width, height, material)
  that can be changed per instance. A W12x26 steel column is a family type. So is
  a 36" hollow-core door. Families are COMPONENTS, not buildings.

- **Project Templates** define settings: units, view templates, line styles,
  annotation families, sheet layouts. They contain zero geometry. They are
  workflow scaffolding, not design content.

- **Dynamo scripts** (visual programming) generate parametric patterns: "place
  columns at every grid intersection," "array windows at 1.5m spacing along this
  wall." These are PROCEDURAL GENERATORS, not static templates.

### ArchiCAD: GDL Objects + Favorites

- **GDL objects** are parametric library parts written in Graphisoft's scripting
  language. A stair object knows about building codes (riser height, tread depth,
  handrail requirements). A wall object knows about layers (exterior finish, air
  gap, insulation, structure, interior finish). These are SMART COMPONENTS with
  embedded domain knowledge.

- **Favorites** save a configured component state: "this specific wall type with
  these layers and these materials." They are PRESETS for components, not buildings.

### Grasshopper/Rhino: Clusters + Definitions

- **Grasshopper definitions** are parametric algorithms: "generate a structural
  grid from row count, column count, and spacing." The definition is reusable;
  the parameters change per project.

- **Clusters** encapsulate a subgraph of logic as a reusable component. Like a
  function in programming.

### IFC: Type Products

- **IfcTypeProduct** defines a product specification shared by all occurrences.
  An IfcColumnType with a specific steel profile is instantiated at 30 grid
  locations. The type carries shared geometry and properties; each occurrence
  carries only its unique placement.

### The Pattern

Every tool templates at the COMPONENT level, not the building level. The
reusable unit is:
- A column type (W12x26, HSS6x6x3/8)
- A wall assembly (exterior cavity wall: brick + air gap + insulation + stud + gypsum)
- A stair configuration (straight run, 7" riser, 11" tread, code-compliant)
- A curtain wall module (storefront: aluminum mullions at 5' spacing, IGU panels)
- A structural grid pattern (4x6 bays at 8m x 10m spacing)
- A foundation type (interior spread footing: 6'x6'x18", 4000psi, #5 @ 12" EW)

None of these are buildings. All of them are building SUBSYSTEMS that repeat
across many buildings with parametric variation.

---

## What Repeats in Building Design (and Is Worth Templating)

### Structural Grids

Every steel or concrete frame building has a column grid. The grid is defined by:
- Number of bays in X and Y
- Spacing in X (may vary: 6m, 8m, 10m, or mixed)
- Spacing in Y (may vary)
- Column section (W14x90, HSS8x8x1/2)
- Beam section per span direction
- Storey count and height

The AI currently generates each column and beam individually. For a 4x6 grid over
3 storeys, that is 35 columns + ~66 beams = 101 actions that follow a trivially
predictable pattern. The AI spends tokens and rounds describing what is
fundamentally a nested loop.

### Floor Plates

Every storey has a floor slab. For a rectangular building, this is one
`create_rect_slab` per storey. For L-shaped or T-shaped footprints, it is 2-3
slabs per storey. The pattern is: repeat the footprint shape at each storey
elevation.

### Stair Cores

A stair core repeats at every storey. The configuration (straight run, U-turn,
scissor) is chosen once and then repeated vertically. Each stair run has the same
tread depth, riser height, and width -- only base_z changes per storey. The compiler
already breaks `create_stair_run` into individual treads; the AI should not need
to specify each storey's stair separately.

### Perimeter Walls / Envelope

The building perimeter is defined by the footprint outline. Walls, curtain walls,
or panels follow that outline at each storey. The AI currently describes each wall
segment individually, but the pattern is: trace the footprint, assign wall types
per face (north = curtain wall, south = cavity wall, etc.).

### Foundation Plans

Each column gets a footing. The footing type and size depend on the column load,
which depends on the tributary area and storey count. The pattern is: mirror the
column grid at the foundation level, with footing sizes selected by load.

### Window/Door Arrays

Windows are often arrayed at regular spacing along a wall. Instead of specifying
each window individually, the pattern is: N windows at S spacing starting at
offset O along wall W.

---

## Three Options

### Option 1: EASY -- Parametric Action Generators (the AI's Power Tools)

**What it is:** Pure Python functions that generate lists of plan actions from
parameters. The AI planner calls these as high-level actions; the compiler expands
them into buildable primitives. No new AI models, no template matching, no caching
infrastructure.

**How it works:**

Add 3-5 new semantic action types to `action_catalog.py`:

```
"generate_column_grid"     -- rows, cols, spacing_x, spacing_y, section, storey_list
"generate_perimeter_walls" -- footprint_vertices, height, thickness, storey_list
"generate_floor_plates"    -- footprint_vertices, thickness, storey_list
"generate_stair_core"      -- config (straight/u_turn), width, storey_list, position
"generate_footing_plan"    -- mirror column_grid, footing_type, default_size
```

The AI planner emits these instead of 100+ individual actions. The compiler
(`compiler.py`) expands each generator into the corresponding buildable actions.
The compiled plan is identical to what the AI would have produced manually -- it
just took 5 actions instead of 100+.

**Example:**

Instead of the AI generating:
```json
{"type": "create_column", "name": "Col A1 L1", "x": 0, "y": 0, "base_z": 0, ...},
{"type": "create_column", "name": "Col A2 L1", "x": 8, "y": 0, "base_z": 0, ...},
{"type": "create_column", "name": "Col A3 L1", "x": 16, "y": 0, "base_z": 0, ...},
... (97 more)
```

It generates:
```json
{
  "type": "generate_column_grid",
  "name": "Primary Structure Grid",
  "rows": 4,
  "cols": 6,
  "spacing_x": 8.0,
  "spacing_y": 10.0,
  "base_section": "W14x90",
  "storey_count": 3,
  "storey_height": 4.0,
  "origin_x": 0,
  "origin_y": 0,
  "semantics": {"role": "structure", "group_path": ["Structure", "Columns"]}
}
```

**Effort:** 1-2 weeks for one developer. Each generator is ~50-100 lines of
Python in `compiler.py`. Schema additions in `action_catalog.py`. System prompt
update to teach the AI about the new actions.

**What you gain:**
- Planner round count drops from 8-12 to 2-4 (the AI describes intent, not
  individual elements)
- Token usage drops 5-10x for structural systems
- No new infrastructure -- it is just more compiler logic
- AI creativity is PRESERVED -- the AI still decides the grid dimensions, spacing,
  section sizes, and storey configuration
- Compiled output is identical to hand-specified plans, so all downstream stages
  (IFC authoring, structural analysis, sizing) work unchanged

**What you lose:**
- Nothing meaningful. The AI is not creative about WHERE to place individual
  columns in a grid -- that is a deterministic pattern.

**Does it save meaningful time?**
Yes. If the planner goes from 12 rounds to 3, and each round is 5-15s, you save
45-135s per building. The planner is 90% of wall-clock time.

**Does it constrain creativity?**
No. The AI chooses the parameters. It can still specify irregular grids by
falling back to individual `create_column` actions. The generators are OPTIONAL
tools, not mandatory constraints.

**Does it improve quality?**
Yes. Deterministic grid generation eliminates off-by-one errors and coordinate
typos that the AI sometimes introduces when specifying 100+ elements individually.

**Worth building for a 1-2 person team?**
Absolutely. This is the highest-value, lowest-risk option. It extends the existing
compiler pattern (`create_stair_run` already works this way) to more action types.

---

### Option 2: MEDIUM -- Parametric Generators + Plan Fragment Caching

**What it is:** Option 1 plus a runtime cache that remembers compiled plan
fragments and reuses them when the AI requests similar generators with similar
parameters. Builds on the Agentic Plan Caching research (arxiv 2506.14852) but
adapted to Bonsai's architecture.

**How it works:**

1. **Parametric generators from Option 1** (required foundation).

2. **Plan fragment cache:** After the compiler expands a generator action, hash
   the generator parameters and store the compiled fragment:
   ```python
   cache_key = hash((action_type, rows, cols, spacing_x, spacing_y, section, ...))
   FRAGMENT_CACHE[cache_key] = compiled_actions
   ```
   On the next request with the same parameters, skip compilation and return the
   cached fragment. Compilation is fast (~ms), so the direct time savings are
   small. The real value is enabling the NEXT step.

3. **Prompt-level plan reuse:** Before calling the AI planner, check if the
   user's prompt is semantically similar to a previously completed plan. Use
   keyword extraction (building type, dimensions, storey count) to match against
   a library of completed plans. If a match is found, present the previous plan
   as a starting point in the system prompt:

   ```
   A similar building was previously designed with these parameters:
   [column grid: 4x6 at 8m, 3 storeys at 4m, W14x90 columns, ...]
   Adapt this plan to the current request, or generate a new plan if it
   does not fit.
   ```

   This gives the AI a HEAD START rather than bypassing it. The AI can accept,
   modify, or reject the suggestion. One-shot planning becomes feasible because
   the AI is not starting from scratch.

4. **Catalog-aware defaults:** When the AI specifies a generator, the compiler
   can auto-select section sizes from the existing catalog system (`ROLE_TO_SELECTION`
   in `catalog_selector.py`) if the AI does not specify them. This means the AI
   can say "generate a column grid, 4x6, 8m spacing" without specifying the
   section, and the compiler picks W14x90 based on the catalog defaults.

**Effort:** 3-4 weeks for one developer. Week 1-2: Option 1 generators. Week 3:
fragment cache and keyword matching. Week 4: prompt integration and testing.

**What you gain:**
- Everything from Option 1
- Second-time-around speedup: if the user iterates ("make it 5 bays instead of
  4"), the AI sees the previous plan and only needs to describe the delta
- Catalog-aware defaults reduce the AI's decision burden for routine choices
- The cache grows organically from real usage -- no manual template authoring

**What you lose:**
- Cache management complexity: invalidation, storage, staleness
- Risk of the AI over-relying on cached plans and not adapting enough to new
  requirements
- Testing surface area increases (cache hit/miss paths, keyword matching accuracy)

**Does it save meaningful time?**
Yes, especially for iterative workflows. First generation: same as Option 1.
Subsequent edits: potentially 2-5x faster because the AI sees a starting point.

**Does it constrain creativity?**
Slightly. The cached plan suggestion could anchor the AI toward the previous
design. Mitigation: always present it as a suggestion, not a requirement. The AI
can ignore it entirely.

**Does it improve quality?**
Mixed. Cache hits improve consistency (same parameters = same output). But stale
cache entries could produce designs that do not match updated catalog data or
changed system behavior. Need cache versioning.

**Worth building for a 1-2 person team?**
Yes, but do Option 1 first and ship it. The cache layer is a natural follow-up
once you have generators producing consistent, hashable plan fragments. Do not
try to build both simultaneously.

---

### Option 3: HARD -- Compositional Building Grammar with AI Orchestration

**What it is:** A formal grammar of building subsystems where the AI acts as an
orchestrator that composes subsystems rather than specifying individual elements.
The AI describes building INTENT at a high level; a compositional engine resolves
that intent into geometry.

**How it works:**

1. **Building grammar:** Define a hierarchical system of composable building
   components, inspired by how Grasshopper definitions and GDL objects work:

   ```
   Building
     -> Site (footprint, orientation, setbacks)
     -> Structure
       -> Grid (rows, cols, spacing, section)
       -> Vertical (storey_heights, floor_type)
     -> Envelope
       -> Face[N] (wall_type, window_pattern)
       -> Face[S] (curtain_wall_type)
       -> Roof (type, slope)
     -> Circulation
       -> StairCore (config, position, code_jurisdiction)
       -> Elevator (position, count)
     -> Foundations
       -> Grid_Mirror (footing_type, sizing_rule)
   ```

2. **Subsystem resolvers:** Each node in the grammar has a Python resolver that
   generates plan actions. The column grid resolver knows how to generate columns
   and beams. The envelope resolver knows how to trace a footprint and generate
   walls. The stair resolver knows IBC code requirements (7 3/4" max riser,
   11" min tread, 36" min width).

   These resolvers embed DOMAIN KNOWLEDGE that the AI currently has to
   re-derive from its training data on every request. A stair resolver that
   knows building codes produces better stairs than an AI guessing at dimensions.

3. **AI as orchestrator:** The AI planner's job changes from "specify every
   element" to "describe the building as a composition of subsystems with
   parameters." The system prompt teaches it the grammar:

   ```
   Describe the building using these subsystems:
   - structure(grid_type, rows, cols, spacing, section)
   - envelope(face_assignments: {N: curtain_wall, S: cavity_wall, ...})
   - circulation(stair_type, position)
   - foundations(strategy: mirror_grid)
   Only use individual create_* actions for custom elements that do not
   fit any subsystem.
   ```

4. **Hybrid execution:** The AI can mix high-level subsystem calls with
   individual actions. "Use a standard 4x6 grid BUT add a transfer beam at
   grid line C" becomes a grid generator plus one custom beam action.

5. **Validation layer:** Each subsystem resolver validates its output against
   domain rules. The stair resolver rejects configurations that violate code.
   The grid resolver warns about unusual bay spacings. This catches errors
   BEFORE IFC generation rather than after.

**Effort:** 2-3 months for one developer. This is a significant architectural
addition. Month 1: define the grammar and build 3-4 core resolvers (grid,
envelope, floor plates, stairs). Month 2: AI prompt engineering and orchestration
logic. Month 3: validation layer, testing, iteration.

**What you gain:**
- Planner drops to 1-2 rounds for most buildings (the AI describes intent in
  one high-level plan)
- Embedded domain knowledge produces code-compliant designs by default (stairs
  that meet IBC, footings sized to load, walls with proper fire ratings)
- Clear separation of WHAT (AI decides) from HOW (resolvers implement)
- Subsystem resolvers are independently testable and improvable
- Natural extension point for future subsystems (MEP, site work, roofing)
- The grammar IS the product's moat -- it encodes architectural knowledge that
  competing AI-to-BIM tools would need to replicate

**What you lose:**
- Significant development time (2-3 months is a lot for a 1-2 person team)
- Complexity: the grammar adds an abstraction layer between the AI and the
  compiled plan. Debugging "why did the stair come out wrong" now requires
  understanding the resolver logic, not just the AI output
- Risk of over-engineering: if the grammar is too rigid, users will fight it
  when they need something unusual
- The AI needs to learn a new output format (subsystem composition vs. flat
  action list). Prompt engineering effort is non-trivial.

**Does it save meaningful time?**
Yes, dramatically. If the AI can describe a building in 1 round instead of 12,
the planner stage drops from 60-180s to 5-15s. Combined with faster downstream
stages, total pipeline time could drop to under 20s for typical buildings.

**Does it constrain creativity?**
More than Options 1-2, but with an escape hatch. The AI is constrained to think
in terms of subsystems for standard patterns, but can always fall back to
individual actions for custom elements. The risk is that the grammar encourages
"standard" buildings and makes unusual designs harder to express.

**Does it improve quality?**
Significantly. Code-aware resolvers produce better defaults than the AI guessing.
Stair dimensions meet code. Footing sizes match loads. Wall assemblies have
correct layer sequences. The AI's job shifts from "get the geometry right" to
"get the design intent right," which is what AI is actually good at.

**Worth building for a 1-2 person team?**
Only after Options 1-2 are proven. This is the right long-term architecture, but
it requires Options 1-2 as stepping stones. The generators from Option 1 become
the subsystem resolvers in Option 3. The cache from Option 2 becomes the
experience library. Build incrementally.

---

## Comparison Matrix

| Dimension | Easy (Generators) | Medium (+ Cache) | Hard (Grammar) |
|-----------|-------------------|-------------------|----------------|
| Dev time | 1-2 weeks | 3-4 weeks | 2-3 months |
| Planner rounds | 8-12 -> 2-4 | 2-4 -> 1-2 (repeat) | 1-2 |
| Token savings | 5-10x | 5-10x + cache hits | 10-50x |
| AI creativity | Fully preserved | Mostly preserved | Preserved with escape hatch |
| Quality improvement | Eliminates coord errors | + consistency | + code compliance |
| Architectural risk | None (extends compiler) | Low (additive cache) | Medium (new abstraction) |
| Prerequisite | None | Option 1 | Options 1 + 2 |

---

## Recommendation

**Ship Option 1 first.** It is low-risk, high-value, and extends patterns already
in the codebase (`create_stair_run` -> compiled treads is exactly this pattern).
Start with `generate_column_grid` because it covers the most actions per generator
and structural grids appear in nearly every building.

**Then evaluate Option 2** based on real usage patterns. If users iterate
frequently ("make it wider," "add a storey"), the cache provides compounding
value. If most requests are one-shot, skip the cache and invest in Option 3
resolver infrastructure instead.

**Option 3 is the destination,** but it is a 2-3 month commitment that should
not start until Option 1 proves the generator pattern works and you understand
which subsystems users actually need. Do not design the grammar in a vacuum --
let real usage data tell you which resolvers to build.

---

## What NOT to Build

- **Static building templates** ("here is a complete 3-story office"). Too
  brittle, too specific, does not compose, and users will immediately want to
  change things the template does not support.

- **Template matching from natural language** ("detect that the user wants a
  warehouse and select the warehouse template"). This adds an AI classification
  step that can misfire, and the failure mode is terrible -- the user asks for a
  warehouse with a mezzanine and gets a template without one.

- **A template marketplace or library browser**. This is a product feature for
  a mature tool with thousands of users, not for a 1-2 person team trying to
  ship faster generation. Build the generator infrastructure first; a library
  UI can come later if there is demand.

---

## Sources

### Commercial BIM Tool Patterns
- [Revit Parametric Families Guide](https://blog.blocksrvt.com/en/parametric-families/)
- [Revit Template Best Practices](https://www.revitforum.org/forum/revit-architecture-forum-rac/architecture-and-general-revit-questions/41666-template-file-best-practices)
- [ArchiCAD GDL Parametric Objects](https://help.graphisoft.com/AC/20/INT/AC20Help/03_1_Elements_Virtual_Building/03_1_Elements_Virtual_Building-192.htm)
- [Graphisoft Parametric Objects Download](https://www.graphisoft.com/en-us/downloads/parametric-objects/)
- [IfcTypeProduct Specification (IFC 4.3)](https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcTypeProduct.htm)
- [Grasshopper Parametric BIM](https://www.e-zigurat.com/en/blog/visual-programming-grasshopper/)
- [IgentBIM Parametric Structural Modeling](https://bimvision.eu/igentbim-parametric-modelling-of-structures-in-bimvision/)
- [SKIN Parametric Curtain Wall System (Revit)](https://rdstudio.co/products/skin-revit-curtain-wall-facade-system)

### AI + Parametric Building Generation
- [Text-to-Building: AI-Generated 3D Geometry for Building Design](https://link.springer.com/article/10.1007/s44223-024-00060-5)
- [Generative AI-Powered Parametric Modeling and BIM](https://www.cambridge.org/core/journals/proceedings-of-the-design-society/article/generative-aipowered-parametric-modeling-and-bim-for-architectural-design-and-visualization/A76987B083B87FA9E8579B1DCA532A0B)
- [Automated BIM-Based Structural Design and Cost Optimization](https://www.nature.com/articles/s41598-022-26146-6)

### Agentic Plan Caching Research
- [Agentic Plan Caching: Test-Time Memory for Fast and Cost-Efficient LLM Agents (NeurIPS 2025)](https://arxiv.org/abs/2506.14852)
- [Full Paper (OpenReview)](https://openreview.net/pdf?id=n4V3MSqK77)

### Building Codes and Standards
- [IBC Stairway Code Requirements](https://upsideinnovations.com/blog/ibc-stairs-code/)
- [UL Fire-Rated Wall Assemblies](https://www.knaufnorthamerica.com/en-us/ul-assemblies/wall)
- [Foundation Design Software (spMats)](https://structurepoint.org/soft/software-profile.asp?l_family_id=60)

### Dynamo / Parametric Grid Generation
- [Placing Parametric Columns on Revit Grid Using Dynamo](https://knowledge.autodesk.com/support/revit/learn-explore/caas/screencast/Main/Details/0450e5ca-ee52-4893-ae61-27fa8eed7ed3.html)
- [Dynamo BIM Forum: Grid Spacing](https://forum.dynamobim.com/t/grid-spacing/25438)
