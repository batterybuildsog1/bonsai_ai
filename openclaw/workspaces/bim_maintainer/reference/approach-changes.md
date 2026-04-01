# Approach Changes: From BIM Toy to Design-Build Production Tool

> Date: 2026-03-30
> Status: Research complete, decisions pending
> Goal: Architecturally beautiful renderings, engineered constructable buildings, permittable plans, quick iterative generation of high-end office buildings. Design, cost, present, permit, and construct -- without the overhead of architects and engineers.

---

## Research Summary

Before proposing changes, here is what the research revealed about how the industry actually works in 2026, and where the gaps are between our current system and a production tool.

### How PEMB/Design-Build Actually Works

Pre-engineered metal building companies (Nucor, Butler, Metallic Building Company) use a mature stack: MBS Software for structural design and bill of materials, Tekla Structures for 3D detailing and connection design, and STAAD or similar for structural analysis. The typical timeline from concept to stamped permit drawings is 2-4 weeks for simple buildings, 8-16 weeks for complex ones. After concept approval, the manufacturer's engineer produces stamped drawings including connection details, anchor bolt plans, and erection sequences. The permit review itself takes 2-6 weeks depending on jurisdiction. Total concept-to-approved-permit: 6-12 weeks for a straightforward metal building.

The key insight: PEMB companies do not sell geometry. They sell a complete package -- stamped engineering, fabrication-ready details, bill of materials with pricing, and erection manuals. The 3D model is a means to that end, not the deliverable.

### What Permit Sets Actually Require

A commercial building permit submission typically requires these drawing sheets:

1. **Cover sheet** -- project data, code references, occupancy, construction type
2. **Site plan** -- building on lot, setbacks, parking, utilities, grading
3. **Floor plan(s)** -- one per level, showing walls, doors, dimensions, room labels
4. **Roof plan** -- slopes, drains, equipment, structural framing reference
5. **Elevations** -- all four sides, material callouts, heights, grade lines
6. **Building sections** -- at least two cuts through the building (transverse + longitudinal)
7. **Wall sections / details** -- connection of roof to wall, wall to foundation, typical bay
8. **Foundation plan** -- footing locations, sizes, rebar schedules, bearing elevations
9. **Structural framing plans** -- member sizes, connections, bracing
10. **Structural details** -- base plate, beam-to-column, brace connections, anchor bolts
11. **MEP drawings** -- mechanical, electrical, plumbing (can be separate permits)
12. **Schedules** -- door, window, finish, structural member schedules

Minimum drawing size is typically 24x36 inches. All drawn to scale with dimensions. An engineer's stamp is required on structural sheets in all US jurisdictions.

Our system currently produces none of these. The IFC model contains the 3D geometry, but no jurisdiction accepts an IFC file as a permit submission. 2D drawings are mandatory.

### Rendering Quality Expectations in 2026

82% of clients in a 2024/25 industry survey expect immersive visualization. The standard tools are Twinmotion (powered by Unreal Engine 5, supports IFC import directly), Enscape (real-time plugin for Revit/SketchUp), V-Ray, and Lumion. Three.js is a web rendering library, not an architectural visualization tool -- it can display geometry accurately but lacks the material library, lighting system, asset library (trees, people, cars, furniture), and post-processing pipeline that clients expect. The gap between Three.js wireframe rendering and a Twinmotion presentation is enormous.

AI rendering (Stable Diffusion + ControlNet, Veras by Chaos, ArchiVinci) is now production-ready for converting basic 3D views into photorealistic images. 56% of design professionals use AI rendering tools in their workflow as of 2025. This is the fastest path from our IFC screenshots to client-quality visuals.

### Cost Estimation from BIM

5D BIM (cost-linked models) is mature. IfcOpenShell has a built-in cost API (`ifcopenshell.api.cost`) that can store cost schedules, cost items, and parametric quantity takeoffs directly in the IFC file. For steel buildings specifically, the quantity takeoff is straightforward: extract member lengths, multiply by unit weight per linear foot, apply $/lb steel pricing. Add concrete volume for footings, slab area, and cladding square footage. The data is already in our IFC model -- we just need to extract and price it.

### Competitor Landscape

The competitive space splits into two categories:

**AI design generators** (Maket, Spacio, Snaptrude, ArchiTechtures, ArkDesign): These generate floor plans and massing from constraints. They target the earliest design phase -- "I need a 5,000 SF office" becomes a floor plan. None of them produce structural engineering, permit drawings, or cost estimates. They hand off to traditional architects.

**Construction management platforms** (Procore, Autodesk Construction Cloud, Buildertrend, PlanGrid): These manage projects after design is complete -- RFIs, submittals, scheduling, cost tracking. None of them generate designs or engineering.

**The gap nobody fills**: Going from "I want a 3-story office building on this lot" to "here are your permit drawings, cost estimate, and construction schedule" without a human architect or engineer in the loop. That is the opportunity.

### AI Code Compliance

CodeComply.Ai, CivCheck, PlanCheckPro.AI, and Ichi are all operational in 2026, offering automated plan review against building codes. Florida has authorized private providers to use automated plan review systems as of July 2025. This means we could either build code checking into our generation (preventing violations) or submit to these services for validation (catching violations). Prevention is better.

---

## The Six Proposed Changes

### Change 1: Generate 2D Permit Drawings from the IFC Model

**Why it matters**: This is the single biggest gap between a cool demo and a useful tool. No building department in the US accepts a 3D model as a permit submission. Every project needs 2D plans, elevations, sections, and details on 24x36 sheets. Without this, the user still needs to hire a draftsperson to produce the permit set -- which defeats the entire purpose.

**What it would take**:

IfcOpenShell already has the infrastructure. Its `ifcopenshell.draw` module (via `cut_ifc.py` and `svgwriter.py`) can slice 3D models at horizontal planes to produce floor plans, and at vertical planes to produce sections. BlenderBIM uses this to generate SVG construction drawings with CSS-based styling. The output path is IFC -> SVG -> PDF.

Implementation steps:
1. Define a `DrawingGenerator` class that takes the IFC file and a list of drawing definitions (plan at each floor elevation, 4 elevations, 2 sections minimum).
2. Use IfcOpenShell's section plane API to slice the model and produce SVG vector output.
3. Add annotation layers: dimensions (computed from the model geometry), room labels (from IFC space names), member size callouts (from IFC property sets), grid lines with labels.
4. Compose SVGs onto 24x36 sheet templates with title block, scale bar, north arrow, revision block.
5. Convert SVG sheets to PDF for submission.

The drawing generation does not need to be perfect on day one. Even a basic set -- site plan, floor plans, four elevations, two sections, foundation plan -- with auto-generated dimensions would save the user weeks of drafting time. Details and connection drawings can be added incrementally.

**What the alternative is**: User exports the IFC to Revit or AutoCAD and manually drafts the permit set. This costs $5,000-$15,000 and takes 2-4 weeks for a commercial building. Or they hire a drafting service.

**Honest tradeoffs**: IfcOpenShell's drawing generation is described by its own maintainers as "early alpha" that "needs a significant amount of work to improve usability, speed, and robustness." The SVG output quality is functional but not beautiful. Annotation placement (avoiding overlaps, leader lines, dimension chains) is an unsolved hard problem in automated drafting. We will produce drawings that need human cleanup for the first many iterations.

**Priority**: **This month.** Without permit drawings, the tool cannot be used for its stated purpose. Start with the simplest possible output (floor plans + elevations as SVGs with basic dimensions) and iterate. A mediocre auto-generated permit set that needs 2 hours of cleanup is infinitely more valuable than no permit set.

---

### Change 2: Add a Cost Estimation Layer on Top of the IFC

**Why it matters**: The user wants to "cost buildings" as part of the workflow. A design-build firm's value proposition is "here's what the building looks like, here's what it costs, here's when it's done." Without cost data, the user generates a beautiful model and then has to manually estimate the cost -- or worse, sends it to an estimator who takes a week.

For steel buildings, cost estimation is highly formulable:
- Steel: weight (tons) x $/ton (currently ~$1,800-2,200/ton erected for structural steel)
- Concrete: volume (CY) x $/CY (~$200-350/CY placed for foundations)
- Cladding: area (SF) x $/SF (metal panel ~$15-25/SF, curtain wall ~$60-120/SF)
- Roofing: area (SF) x $/SF (~$8-15/SF for metal roof)
- MEP allowance: $/SF of floor area (~$25-50/SF for office)
- Site work: $/SF of site area (~$5-15/SF)
- Soft costs: % of construction (~15-25% for permits, insurance, fees, contingency)

All the quantities are already in our IFC model. Steel member lengths and section weights come from the section library. Concrete volumes come from footing and slab dimensions. Cladding and roof areas come from wall and roof geometry.

**What it would take**:

1. A `CostEstimator` class that walks the IFC model and extracts quantities by category (structural steel, concrete, cladding, glazing, roofing, sitework).
2. A unit cost database (start with a simple JSON/YAML file of regional cost data, can be updated).
3. A cost summary output: total cost, cost per SF, breakdown by CSI division or custom category.
4. Display in the viewer as an overlay panel, and export as a one-page PDF cost summary.

IfcOpenShell's `ifcopenshell.api.cost` module can store the cost schedule directly in the IFC file, making the cost data part of the model rather than a separate spreadsheet.

**What the alternative is**: Manual quantity takeoff in a spreadsheet, or exporting to a tool like CostX, Sage, or RSMeans. This works but breaks the fast iteration loop -- every design change requires re-estimating.

**Honest tradeoffs**: Automated cost estimates from a conceptual model are inherently rough. Industry standard is +/- 30% at schematic design, +/- 15% at design development, +/- 5% at construction documents. Our estimates will be at the schematic level (+/- 30%) until we add more detail (MEP systems, finishes, site conditions). The danger is that a user presents an AI-generated cost estimate to a client and it's 40% low because we missed something. The estimate must carry a prominent disclaimer and confidence range.

**Priority**: **This month.** The quantity extraction is straightforward Python code against the IFC model. A basic cost report (steel weight x $/ton + concrete volume x $/CY + cladding area x $/SF) can be built in a day. Refinement is ongoing.

---

### Change 3: Export to a Real Rendering Pipeline Instead of Relying on Three.js

**Why it matters**: The user wants "architecturally beautiful renderings" and to "present to clients." Three.js renders geometry accurately, but it is not an architectural visualization tool. It lacks:
- Physically-based materials (brushed steel, reflective glass, textured concrete)
- Environmental lighting (HDRI sky, sun position, ambient occlusion)
- Entourage (people, cars, trees, furniture) that make a scene feel real
- Post-processing (bloom, depth of field, color grading)

The gap between our current viewer and a client presentation is the gap between a CAD wireframe and a magazine photograph.

**Two paths, not mutually exclusive**:

**Path A: Twinmotion export (recommended for client presentations)**

Twinmotion imports IFC files directly, preserves BIM metadata, and produces photorealistic output in minutes. The workflow would be:
1. Our system generates the IFC file (as it does now).
2. User opens the IFC in Twinmotion (free for IFC files under 100MB, which covers our buildings).
3. Twinmotion auto-applies materials, adds environment, and the user picks camera angles.
4. Export stills or video.

This is not automated, but it's fast (30 minutes from IFC to presentation images). We could add a "Prepare for Twinmotion" export step that sets up material assignments as IFC property sets that Twinmotion can read.

**Path B: AI rendering from screenshots (recommended for speed)**

Take a screenshot of our Three.js viewer from a good camera angle, run it through an AI rendering service (Veras, ArchiVinci, or a local Stable Diffusion + ControlNet pipeline) to produce a photorealistic image. This can be automated:
1. Capture the Three.js canvas at a preset camera position.
2. Send to an AI rendering API with a prompt ("modern steel and glass office building, landscaped site, photorealistic, architectural photography").
3. Display the result alongside the 3D model in the viewer.

This takes seconds, not minutes, and can be fully integrated into our tool. The quality is good enough for early client presentations and social media. It's not good enough for final marketing materials.

**What the alternative is**: Keep Three.js as-is and tell users to screenshot and render elsewhere. This works but breaks the workflow and loses the "wow" factor of showing a client a beautiful image generated in real time.

**Honest tradeoffs**: Path A (Twinmotion) requires the user to install and learn another tool, breaking the "all in one" promise. Path B (AI rendering) produces images that don't match the model exactly -- AI will add windows where there are none, change proportions, hallucinate details. For a sales presentation this is fine; for permit or construction documentation this is unacceptable. Both paths require being honest with clients about what's a rendering vs. what's the actual design.

**Priority**: **This quarter.** The Three.js viewer is functional for design review. AI rendering (Path B) could be added this month as an experimental feature. Twinmotion export guidance can be documented this month. Neither blocks the core workflow.

---

### Change 4: Target Single-Story Metal Buildings First, Not Multi-Story Office Towers

**Why it matters**: The current system generates 5-story office buildings. Multi-story steel frame office buildings require:
- Moment frames or braced frames for lateral loads (seismic, wind)
- Floor diaphragm design
- Complex foundation design (spread footings may not work; may need piles or mats)
- Elevator and stair cores
- Fire-rated assemblies
- Complex MEP routing (mechanical rooms, risers, shafts)
- Occupancy separation between floors
- Sophisticated structural engineering (drift limits, P-delta effects)

Single-story pre-engineered metal buildings (warehouses, shops, small offices, retail) require:
- Rigid frame or clear-span portal frames (one structural system, well understood)
- Simple foundations (spread footings, always)
- No elevator, no fire-rated assemblies (usually Type II-B construction)
- Minimal MEP complexity
- One floor plan, one roof plan
- The PEMB industry has commoditized the engineering -- it's formulaic

The PEMB market is $14 billion/year in the US alone. The design-build workflow for a 5,000 SF metal shop building is: customer calls, sales rep draws up a quote in MBS Software in 30 minutes, engineer stamps it in a week, permit in 3-4 weeks, erected in 2-3 weeks. Total: 6-8 weeks, $15-25/SF.

Our tool could collapse the sales-rep-to-stamped-drawings phase to same-day for simple buildings. That is a real, monetizable value proposition.

**What it would take**:

1. Add a rigid frame portal frame system to the generator (two columns + rafter, bolted at knee and ridge). This is a different structural system than the moment-frame grid we generate now.
2. Simplify the spec for single-story: clear span width, eave height, building length, end wall type (full open, partial, closed), roof slope.
3. Add metal wall panel and roof panel cladding (standing seam or R-panel) instead of curtain wall.
4. Connection details for PEMB are standardized: base plate, knee connection, ridge splice, girt/purlin clips. These can be templatized.
5. The permit set for a single-story PEMB is 6-8 sheets, not 15-20 like a multi-story building.

**What the alternative is**: Keep targeting multi-story office buildings. This is a harder problem with a smaller addressable market at the low end (small design-build firms doing office buildings are rarer than those doing warehouses/shops).

**Honest tradeoffs**: Single-story metal buildings are less visually impressive in demos. "Look at this warehouse" is less exciting than "look at this 5-story office tower." But the warehouse can actually get built from our output, while the office tower cannot (yet). There's a tension between what demos well and what ships as a product. Also, PEMB is a commoditized market with thin margins and established players (Nucor, Butler, BlueScope, Chief Industries). Competing on price alone is hard; the value has to come from speed and reducing the engineering bottleneck.

The multi-story capability should not be abandoned -- it's the long-term vision. But validating the tool on single-story buildings first means we can produce a complete, permittable, buildable output sooner.

**Priority**: **This month decision, this quarter execution.** The architectural question is whether to build a parallel single-story generator or adapt the existing multi-story generator. A new `PEMBGenerator` that produces portal frames would be cleaner than trying to make the grid-based `BuildingGenerator` handle both cases. This is a strategic fork, not a code tweak.

---

### Change 5: Build Code Compliance Checking into the Generation Loop

**Why it matters**: A building that violates code gets rejected at permit review. If the user submits plans and gets a correction notice listing 15 code violations, they lose 2-4 weeks and credibility. The AI should prevent code violations at generation time, not let users discover them at the permit counter.

Key code checks for steel commercial buildings:
- **IBC Table 503**: Building height and area limits by construction type and occupancy. A Type II-B (unprotected steel) Business occupancy (Group B) is limited to 3 stories and 19,000 SF per floor without sprinklers. With sprinklers, 4 stories and 28,500 SF. This single check prevents the most common rejection.
- **IBC Chapter 10**: Egress -- number of exits, travel distance, exit width. Two exits minimum above certain occupant loads. Maximum 300-foot travel distance (sprinklered).
- **IBC 1604-1613**: Structural loads -- wind speed by location, seismic design category by location, snow load by location. These drive the structural design.
- **ADA/ICC A117.1**: Accessible route, restroom count, parking count. At least one accessible entrance, 5% of parking spaces accessible.
- **IBC Table 602**: Fire separation distance -- exterior wall fire rating based on distance to property line.
- **Energy code (IECC)**: Wall insulation, roof insulation, window U-factor by climate zone.

Many of these are simple lookups or arithmetic that can be coded as rules. The generation spec should include location (for wind/seismic/snow), occupancy type, and whether sprinklered. The generator should refuse to produce a building that exceeds height/area limits, and should auto-calculate required egress.

**What it would take**:

1. A `CodeChecker` class that takes the building spec and validates it against IBC rules before generation.
2. Lookup tables for IBC 503 (height/area by type/occupancy), wind speeds by zip code (ASCE 7 maps), seismic design categories by zip code, snow loads by location.
3. Egress calculator: occupant load from floor area and occupancy type, required exits, required exit width, maximum travel distance.
4. Integrate the checker into the generation pipeline: check before generating, warn on violations, auto-fix where possible (e.g., add a second exit if only one was specified).

**What the alternative is**: Generate whatever the spec says, let the user figure out code compliance. Or, submit the generated drawings to an AI plan review service (CodeComply, CivCheck) for post-generation checking. The problem with post-generation checking is that it requires rework -- it's cheaper to prevent violations than to fix them.

**Honest tradeoffs**: Building codes are extraordinarily complex. The IBC alone is 700+ pages, and it references dozens of other standards (ASCE 7, ACI 318, AISC 360, NFPA 13, etc.). We cannot encode all of it. But we can encode the 20 rules that cause 80% of permit rejections. The remaining 20% will still require human review. There's also a liability question: if our tool says "code compliant" and the building isn't, who is responsible? We should frame this as "pre-screening" not "certification" -- the engineer's stamp is still required.

**Priority**: **This quarter.** The IBC 503 height/area check is a single lookup table and should be added immediately (it takes 30 minutes to code). Egress checking is a half-day of work. Wind/seismic/snow lookups require a geographic database but are well-documented. Full code compliance is a multi-month effort, but the high-value checks are fast to implement.

---

### Change 6: Produce Connection Details and Structural Calculations, Not Just Member Sizes

**Why it matters**: The roadmap (roadmap-to-real-buildings.md) focuses on getting member sizes right -- W14x68 columns instead of 0.3x0.3m rectangles. That matters for visual accuracy and cost estimation. But a permit reviewer does not approve a building because the beam sizes look right. They need:

1. **Structural calculations**: A calculation package showing that each member's capacity exceeds the demand. Load combinations per ASCE 7, member checks per AISC 360, drift checks, foundation bearing pressure checks. This is typically a 50-200 page PDF for a commercial building.

2. **Connection details**: How the beam connects to the column. Bolted end plate? Welded flange? Shear tab? Each connection type has specific design requirements (bolt size, number of bolts, weld size, plate thickness). A generic "W21x44 beam" without connection details is not constructable.

3. **Engineer's stamp**: A licensed PE must review and stamp the structural drawings and calculations. This is a legal requirement in all 50 states.

The existing `grouped_sizing.py` and FEA pipeline can produce member demand/capacity ratios. That's half of a structural calculation package. The other half is documenting the methodology, load assumptions, and code references in a readable format.

Connection design is a separate discipline. Tools like SDS2, Advance Steel, and IDEA StatiCa automate it, but they cost $5,000-$15,000/year. For PEMB-style buildings, connections are standardized -- a library of 10-15 connection types covers 95% of cases.

**What it would take**:

1. **Calculation report generator**: Take the FEA results and format them into a PDF calculation package. For each member: applied loads, member properties, demand/capacity ratio, code reference. For the building overall: base shear, story drift, overturning. This is template-driven document generation, not new engineering.

2. **Connection library**: Define 10-15 standard connections as parametric templates. Each template takes the connecting member sizes as input and produces: a detail drawing (2D SVG), a bill of materials (bolts, plates, welds), and a capacity check. Start with: base plate, beam-to-column shear tab, beam-to-column moment connection, brace gusset plate, column splice.

3. **Engineer review workflow**: The tool produces the calculations and drawings. A PE reviews them and applies their stamp. We don't replace the engineer -- we do 90% of their work so they can review in hours instead of days.

**What the alternative is**: Output member sizes only, and let a structural engineer produce the calculations and connection details from scratch. This is how it works today in practice, and it costs $10,000-$30,000 for a commercial building's structural engineering.

**Honest tradeoffs**: Automated structural calculations carry significant liability risk. If the tool produces a calculation that says "OK" but the connection fails, people can be hurt. Every calculation must be reviewed by a PE. We should never market this as "no engineer needed" -- it's "engineer-assisted, AI-accelerated." The PE is still liable and must review everything.

Connection design automation is genuinely hard. AISC's Steel Construction Manual has hundreds of pages on connection design. For PEMB connections, it's manageable because they're standardized. For custom multi-story connections, it requires IDEA StatiCa-level software.

**Priority**: **This quarter for calculation reports, next quarter for connections.** The calculation report is document generation from existing FEA data -- it's a formatting problem, not an engineering problem. Connection details require a new subsystem with parametric geometry generation and code-checking logic. Start with the 3-4 most common PEMB connections.

---

## Summary: What Changes, and When

| # | Change | Effort | Priority | Impact |
|---|--------|--------|----------|--------|
| 1 | Generate 2D permit drawings from IFC | 2-3 weeks for basic set | **This month** | Unlocks the entire value proposition -- without this, the tool cannot produce permittable output |
| 2 | Cost estimation layer | 3-5 days for basic estimate | **This month** | Enables design-cost iteration loop that clients and developers demand |
| 3 | Real rendering pipeline (AI + Twinmotion export) | 1 week for AI path, documentation for Twinmotion | **This quarter** | Transforms client presentations from CAD screenshots to magazine-quality images |
| 4 | Target single-story PEMB first | 2-3 weeks for portal frame generator | **Decision this month** | Reduces complexity by 5x, addresses $14B market, produces buildable output sooner |
| 5 | Code compliance checking in generation | 1 week for high-value checks | **This quarter** | Prevents permit rejections, builds trust in the tool's output |
| 6 | Connection details + structural calculations | 2-4 weeks for calc reports, 4-8 weeks for connections | **Next quarter** | Makes the structural output actually permittable and constructable |

### The Critical Path

The order matters. Here is the dependency chain:

```
Change 4 (decide on PEMB target)
    |
    v
Change 1 (2D permit drawings)  -----> Change 5 (code checks baked in)
    |                                       |
    v                                       v
Change 2 (cost estimation)            Change 6 (calculations + connections)
    |
    v
Change 3 (rendering)
```

Change 4 should be decided first because it determines the scope of everything else. A single-story PEMB needs 6-8 drawing sheets; a multi-story office needs 15-20. The code checks are simpler. The connections are standardized. The cost estimation is more accurate (less MEP variability). Everything downstream gets easier.

Change 1 is the highest-impact technical work. Without 2D drawings, the tool is a visualization toy. With them, it's a production tool.

Change 2 is the easiest win. The data is already in the IFC model; we just need to extract and price it.

Change 3 is important for sales but does not block the core workflow.

Changes 5 and 6 add engineering rigor that makes the output trustworthy and permittable.

### What This Changes About the Current Roadmap

The existing roadmap (roadmap-to-real-buildings.md) focuses on Phase 1-3: real steel profiles, footings, site context, and viewer polish. That work remains valid and should continue -- it improves the 3D model quality. But it is necessary, not sufficient.

The roadmap is missing the output layer: the 2D drawings, cost reports, and structural calculations that are the actual deliverables of a design-build firm. The 3D model is a means to produce those deliverables, not the deliverable itself.

The proposed changes add that output layer. They transform the system from "AI generates a 3D building model" to "AI generates a complete design-build package: 3D model, 2D permit drawings, cost estimate, and structural calculations."
