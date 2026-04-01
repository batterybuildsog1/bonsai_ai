# Pre-Engineered Metal Building (PEMB) Workflow Research

Deep research into how PEMB companies actually design and deliver buildings, conducted to identify where Bonsai AI should focus its efforts.

---

## 1. The PEMB Industry at a Glance

**Market size**: USD $12.98 billion in 2024, projected to reach $27.10 billion by 2033 (8.6% CAGR).

**Major manufacturers**: Nucor Building Systems, BlueScope Buildings (Butler Manufacturing), American Buildings, Cornerstone Building Brands, Kirby Building Systems, PEMB-USA, Great Western Buildings, Ceco Building Systems, VP Buildings (Varco Pruden).

**How the industry works**: PEMB manufacturers sell through a dealer/builder network. The manufacturer designs and fabricates the steel building system. The dealer sells to the end customer and typically hires or acts as the general contractor for erection. This is a franchise-like model where the manufacturer controls the engineering and fabrication, while the dealer controls the customer relationship and construction.

**What makes PEMB different from conventional**: Everything is pre-designed using parametric software. A building can be fully engineered from a few inputs (width, length, height, loads, location) in minutes, not weeks. Components arrive numbered, pre-punched, ready to bolt together. This is the construction industry's closest analog to manufacturing.

---

## 2. The Complete PEMB Workflow: Inquiry to Occupancy

### Phase 1: Client Inquiry and Scoping (Day 1-3)

**What happens**: Customer contacts a PEMB dealer/builder with a project need. The dealer captures basic requirements.

**Information the estimator needs**:
- Building use (warehouse, manufacturing, office, retail, agricultural)
- Dimensions: Width x Length x Eave Height
- Roof slope preference (single slope, double slope, X:12 pitch)
- Location (determines wind, snow, seismic loads via building code)
- Special features: crane systems, mezzanines, overhead doors, dock levelers
- Wall/roof panel type: standing seam vs. screw-down roof, insulated panels
- Framing: rigid frame vs. post-and-beam endwalls, hot-rolled vs. cold-formed
- Colors for wall and roof panels
- Code requirements: sprinklers, occupancy classification, fire rating

### Phase 2: Preliminary Design and Budgetary Estimate (Day 3-7)

**What happens**: The dealer enters building parameters into manufacturer's quoting software (or the manufacturer does this). Software generates a preliminary design and bill of materials within minutes.

**Key software**: MBS (Metal Building Software) is the dominant tool, used by 300+ manufacturers across 6 continents. Building data can be entered in as few as 2 minutes. The software immediately produces:
- Weight-optimized structural design from the manufacturer's inventory
- Complete bill of materials with accurate costing
- Preliminary elevation drawings
- Budget price for the building package

**Cost structure breakdown**:
- Steel building kit (primary/secondary framing, panels, trim, fasteners): 40-50% of total project cost
- Labor and erection: 30-40% of total cost
- Site preparation and foundation: 10-20% of total cost
- Freight and delivery: ~10% of total cost
- Typical range: $15-65/sf depending on building type, complexity, and location

**Estimating tools in use**:
- MBS (manufacturer-side) -- full design + costing in minutes
- Metal Building Bid Wizard (MMBW) -- Excel-based, dealer-side erection estimating
- Steel Erection Bid Wizard (SEBW) -- structural steel erection cost estimating
- 247PRO -- cloud-based PEMB cost calculator
- Nucor eQuote -- Nucor's proprietary web-based estimation tool
- Steel Estimating Solutions -- CAD-based estimating with BIM integration

### Phase 3: Contract and Order (Week 1-2)

**What happens**: Customer accepts the bid. Contract is signed specifying scope, timeline, cost. Manufacturer receives the order and begins detailed engineering.

### Phase 4: Detailed Engineering (Weeks 2-6)

**What happens**: This is the phase where the manufacturer's engineering department takes the preliminary design and produces the full engineering package. This is the most critical phase and historically the biggest bottleneck.

**What the manufacturer's engineer produces**:
- Structural calculations (dead loads, live loads, wind loads, snow loads, seismic forces)
- Rigid frame design (tapered members optimized for weight)
- Connection design (moment connections, base plates, bracing connections)
- Secondary member design (purlins, girts, eave struts)
- Cold-formed member design
- Foundation reaction loads (provided to the EOR/foundation engineer)
- Anchor bolt layout plans
- Complete bill of materials for fabrication

**What the manufacturer does NOT produce** (EOR responsibility):
- Foundation design (the manufacturer provides reactions; someone else designs the foundation)
- Site coordination and layout
- MEP coordination (mechanical, electrical, plumbing)
- Overall building code compliance confirmation
- Architectural drawings for non-structural elements
- Coordination with other trades

**Software used for structural design**:
- MBS Rigid Frame module -- designs rigid frames, endwall frames, all cold-formed members, wind framing, eave extensions, canopies, facia beams, and connection plates. Handles 30+ US and international building codes.
- MkaPEB (RAMCADDS) -- newer AI-powered alternative, 10x cheaper than MBS. Automatically calculates wind/snow loads, recognizes accumulation areas, adjusts loads by wind direction. Uses AI to find lightest/most economical sections. 51 template structures (21 trusses, 18 portal frames, 12 PEB types).
- SteelSmart System -- for cold-formed steel member design (studs, joists, shear walls, trusses, rafters)
- Quikframe -- 2D frame analysis with tapered member support
- Quikport -- portal frame design with elastic and elastic-plastic methods
- STAAD.Pro -- general structural analysis
- General FEA tools (for non-standard conditions)

**Key insight about tapered frame design**: PEMB rigid frames use tapered I-sections (deeper at the knee/haunch, shallower at midspan) to optimize steel weight. This is the core engineering IP of PEMB manufacturers. MBS and MkaPEB handle this natively. General-purpose structural software (STAAD, SAP2000, ETABS) requires modeling tapered members as a series of prismatic elements, which is slower and less optimized.

### Phase 5: Drawing Production (Weeks 4-8, overlapping with Phase 4)

**Three types of drawings are produced**:

#### 5a. Approval Drawings
- Submitted to the customer and EOR for review
- Show overall building dimensions, frame layouts, openings, accessories
- Used to confirm the design matches the customer's intent
- Typically 5-15 sheets

#### 5b. Permit Drawings (PE-stamped)
- Submitted to the local building department for permit
- Include structural calculations showing load analysis
- Foundation plans with anchor bolt locations, sizes, embedment depths, concrete specifications
- Framing plans showing column layouts, beam sizes, bracing locations, connection details
- Roof and wall elevations with panel layouts, trim details, opening locations
- PE stamp valid for the project's state and county
- Most jurisdictions require PE-stamped drawings for permit

**Permit requirements specific to metal/steel buildings**:
- Structural calculations demonstrating code compliance
- Foundation design including column reactions by basic load case (per IBC Section 1605)
- Wind load analysis per ASCE 7
- Seismic design category determination
- Fire rating documentation if required by occupancy
- Energy code compliance (insulation, thermal bridging)
- Accessibility compliance where applicable

#### 5c. Construction Documents (Erection Drawings + Shop Drawings)

**Erection drawings** (for the field crew):
- Anchor bolt plans -- layout, size, embedment of all anchor bolts (NOT a foundation design; it shows bolt placement only)
- Frame erection plans -- assembly sequence, lifting details, bracing requirements
- Roof framing plans -- purlin layout, bracing
- Wall framing plans -- girt layout, wind bracing
- Panel layout drawings
- Trim and flashing details
- Every component is numbered for field identification

**Shop drawings** (for the fabrication shop):
- Detailed fabrication drawings for each steel member
- Dimensions, connection details, bolt patterns, weld sizes
- Plate sizes and hole patterns
- CNC-ready data for automated fabrication equipment
- General Notes specifying material specs, welding requirements, bolting specs, fabrication tolerances, erection tolerances

**Automation level**: MBS generates erection drawings and shop drawings automatically from the building model, often without any manual CAD editing. The entire process from building entry to all required output can take place in a matter of minutes. MBS clients report 50%+ reduction in design/detailing/drafting time compared to other software.

### Phase 6: Fabrication (Weeks 6-14, overlapping with Phases 4-5)

**What happens**: Steel members are fabricated using CAD/CAM-driven processes. Every component arrives numbered with pre-punched bolt holes. Fabrication takes 4-8 weeks from order for standard buildings, up to 16 weeks for complex/large buildings.

**Key point**: Fabrication runs in parallel with foundation construction. This parallel processing is the #1 schedule advantage of PEMB over conventional construction.

### Phase 7: Site Preparation and Foundation (Weeks 4-10, parallel with fabrication)

**What happens**: While the building is being fabricated, the site is being prepared and the foundation poured. The foundation contractor works from the anchor bolt plan provided by the manufacturer.

**Critical coordination point**: Anchor bolt placement must be precise. Misaligned anchor bolts can require complete teardown/rework. This is the most common field error.

**Foundation design responsibility**: The manufacturer provides anchor bolt layouts and column reaction loads. The EOR or a separate foundation engineer designs the actual foundation (footings, grade beams, slab). This is a gap in the PEMB workflow -- the manufacturer designs everything above the base plate but nothing below it.

### Phase 8: Erection (Weeks 10-14+)

**Timeline by building size**:
- Small building (2,400 sf / 40x60): 2-3 days
- Medium building (10,000 sf): ~7 weeks total including foundation
- Large building (50,000-100,000 sf): 2-4 weeks erection only
- Very large (1M+ sf): Varies dramatically (31 days to 8 months reported)

**Erection sequence** (for a ~10,000 sf building):
1. Weeks 1-2: Site prep, anchor bolt installation, concrete pour and cure
2. Weeks 3-4: Steel delivery, column placement, girt/purlin installation (crew of 4 can install ~400 ft of purlins/day)
3. Week 5: Cross-bracing, alignment checks, bolt torque verification
4. Week 6: Roof sheeting, trim, flashing, weatherproofing (1-2 panels per man-hour for standard 26-gauge)
5. Week 7: Wall panels, doors, hardware, punch list

**Productivity benchmarks**:
- 400 ft of purlins per day (4-person crew)
- 1-2 wall/roof panels per man-hour (standard 26-gauge)

### Phase 9: Closeout

Building inspection, occupancy permit, warranty documentation.

---

## 3. What Makes PEMB Fast (vs. Conventional Construction)

| Factor | PEMB | Conventional Steel | Conventional Concrete |
|--------|------|-------------------|----------------------|
| Design time | Minutes to days (parametric) | Weeks to months (custom) | Weeks to months (custom) |
| Engineering | Automated by manufacturer software | Manual by structural engineer | Manual by structural engineer |
| Fabrication | 4-8 weeks, factory-controlled | 8-16 weeks, custom fabrication | Cast-in-place or precast, 4-12 weeks |
| Site work | Parallel with fabrication | Sequential | Sequential |
| Erection | Days to weeks (bolt-together) | Weeks to months (weld/bolt) | Weeks to months (form/pour/cure) |
| Total timeline | 8-20 weeks typical | 6-12 months | 6-18 months |
| Cost | $15-65/sf | $30-100/sf | $40-150/sf |
| Design flexibility | Limited (rectangular, 1-2 stories) | High (any shape, multi-story) | Highest (any shape, any height) |

**The core speed advantages**:
1. **Parametric design**: A building is defined by ~20 parameters, not hundreds of custom drawings. Software generates everything from those parameters.
2. **Parallel processing**: Foundation and fabrication happen simultaneously. No waiting.
3. **Pre-fabrication**: Components arrive ready to assemble. No field cutting, welding, or fitting.
4. **Standardized connections**: Every connection is pre-designed and pre-detailed. No field engineering decisions.
5. **Numbered components**: Erection is literally following numbered instructions.

**The core limitation**: PEMB is optimized for simple rectangular buildings, typically 1-2 stories, with clear spans. It struggles with complex geometry, multi-story, irregular shapes, or high architectural finish requirements.

---

## 4. The Role of the Engineer of Record (EOR) vs. PEMB Manufacturer

This is a critical distinction that many people misunderstand:

**The PEMB manufacturer's engineer** (Specialty Structural Engineer / SSE):
- Designs the steel building system (frames, purlins, girts, bracing, panels)
- Provides PE-stamped drawings and calculations for the building system
- Provides anchor bolt layouts and column reaction loads
- Does NOT design foundations
- Does NOT coordinate with other trades
- Does NOT serve as the EOR

**The Engineer of Record (EOR)**:
- Establishes design criteria (loads, codes, deflection limits)
- Reviews and approves the manufacturer's submittals
- Designs the foundation
- Coordinates MEP, fire protection, accessibility
- Ensures overall building code compliance
- Is liable if the building fails

**The delegation model**: PEMB engineering is a delegated function. The EOR tells the manufacturer what loads and criteria to design to. The manufacturer designs the building system to those criteria. The EOR reviews and approves. This is fundamentally different from conventional construction where the EOR designs everything.

---

## 5. Software Ecosystem Summary

### Manufacturer-Side (Design + Fabrication)

| Software | Purpose | Used By | Key Capability |
|----------|---------|---------|----------------|
| **MBS (Metal Building Software)** | Complete design, detailing, costing, drafting | 300+ manufacturers, 6 continents | Building entry to full output in minutes; 30+ building codes; auto shop/erection drawings |
| **MkaPEB (RAMCADDS)** | AI-powered PEB design + analysis | Growing adoption | AI section optimization; auto wind/snow loads; 10x cheaper than MBS |
| **Tekla Structures** | 3D BIM modeling, detailing, fabrication | Major manufacturers (Garco, etc.) | MBS-Tekla link auto-generates 3D model from MBS data; CNC interfaces |
| **SmartBuild Systems** | Metal building design | Post-frame and metal building | API integration with MBS |
| **Nucor eQuote** | Web-based estimation | Nucor dealers | Proprietary web quoting |
| **Nucor NBS Toolbox** | Field app | Nucor network | Proprietary field tools |

### Dealer/Builder-Side (Estimating + Project Management)

| Software | Purpose | Key Capability |
|----------|---------|----------------|
| **Metal Building Bid Wizard (MMBW)** | Erection estimating | Excel-based; auto-formats bid proposals; includes labor, crane, equipment, fuel |
| **Steel Erection Bid Wizard (SEBW)** | Structural steel erection estimating | Imports takeoffs from Tekla, Bluebeam, OnScreen Takeoff |
| **247PRO** | PEMB cost calculator | Cloud-based; template-driven; proposal generation |
| **Steel Estimating Solutions** | CAD-based estimating | 3D visualization; auto quantity calculation |

### EOR/Foundation Engineer Side

| Software | Purpose |
|----------|---------|
| **STAAD.Pro** | General structural analysis |
| **RISA** | Structural analysis and design |
| **Enercalc** | Foundation design, retaining walls |
| **CivilBay spreadsheets** | Anchor bolt design (ACI 318), crane beam design |
| **Revit** | BIM coordination (limited PEMB support) |

### Panel Manufacturer BIM Tools

| Manufacturer | BIM Tools |
|-------------|-----------|
| **Kingspan** | BIM Bundle (Revit families LOD 200/300 via BIM 360); BIM Configure (online configurator, 140+ export formats, dozen+ parameters) |
| **Metl-Span** | 2D and 3D BIM models for collaboration |
| **MBCI** | Partners with All Weather, Metl-Span, Kingspan for IMP specification |

---

## 6. Panel Systems: How They Are Specified and Detailed

### Insulated Metal Panels (IMPs)

IMPs consist of two metal skins surrounding an insulating core (polyurethane, polyisocyanurate, or mineral wool). Units connect through tongue-and-groove joinery.

**Specification process**:
1. Architect selects panel type based on thermal performance, fire rating, aesthetics
2. Panel thickness determined by R-value requirements and energy code
3. Color and finish selected from manufacturer palettes
4. Panel manufacturer provides shop drawings showing panel layout, trim details, flashing
5. BIM tools (Kingspan BIM Configure, Metl-Span BIM files) allow parametric configuration in Revit

**Connection to steel frame**: Panels attach to secondary framing (girts for walls, purlins for roof) with concealed or exposed fasteners. The exterior panel joint serves as a wall drainage channel.

### Insulated Concrete Panels (Tilt-Up / Precast Sandwich Panels)

Sandwich panels consist of two concrete wythes separated by rigid insulation, connected by composite ties through the insulation.

**Connection to steel frame**:
- Welded connections are most common: loose plate welded between embedded plates in concrete and steel
- Steel frames may require stiffening at precast connections
- Tiebacks resist out-of-plane forces (wind, seismic, eccentricity)
- PCI provides 20+ recommended fully insulated wall panel details in PDF/DWG

**Key difference from IMP**: Insulated concrete panels provide both structure and enclosure. They can be load-bearing walls that eliminate the need for some steel framing. This is why tilt-up construction is competitive with PEMB for large single-story buildings.

---

## 7. Where AI Could Eliminate the Biggest Time Wastes

### Current Bottlenecks (Ranked by Time Impact)

**1. Design Approval Cycle (weeks to months wasted)**
The design and engineering phase can feel like an endless relay race: architects draw plans, engineers make adjustments, stakeholders request changes, and the cycle repeats. Large-scale projects often spend half a year or more in design approvals before steel is ordered. AI could compress this by generating multiple design options simultaneously, auto-checking code compliance, and enabling real-time collaborative design reviews.

**2. Quoting and Estimating (days wasted per bid)**
Traditional estimating takes a senior estimator 6-8 hours per building. Firms spend 40-60% of estimation time on data gathering and manual calculations. AI-powered quoting has demonstrated:
- 90% reduction in estimating time (6-8 hours down to 20-30 minutes)
- 95%+ accuracy (vs. 15-20% error rates traditionally)
- 25-40% higher bid win rates
- 3x more bids pursued quarterly
- ROI within 90 days

**3. Foundation Design Gap (weeks wasted)**
The PEMB manufacturer designs everything above the base plate. The foundation is someone else's problem. This handoff is a consistent delay point. The manufacturer provides reaction loads; a separate engineer must interpret them and design the foundation. An AI system that could auto-generate foundation designs from PEMB reaction data would close this gap.

**4. Permitting (2 weeks to 3+ months wasted)**
Simple rural permits take ~2 weeks. Complex urban permits can take 3+ months. The permit set is largely standardized for PEMB (structural calcs, foundation plan, framing plans, elevations). AI could auto-generate permit-ready document packages tuned to local jurisdiction requirements.

**5. Coordination Between Trades (ongoing waste)**
PEMB manufacturers don't coordinate with MEP, fire protection, or other trades. The dealer system creates finger-pointing when field issues arise. AI-powered clash detection and coordination could bridge this gap.

**6. Data Finding and Management (20% of professional time wasted)**
Construction professionals report spending close to 20% of their time finding the right data. An integrated AI system could eliminate this entirely.

### Specific AI Opportunities for Bonsai

| Opportunity | Current State | AI Target | Impact |
|------------|---------------|-----------|--------|
| **Instant building design from requirements** | MBS does this in 2 min for PEMB | Extend to ALL building types (office, multi-story, mixed-use) | Bring PEMB speed to conventional construction |
| **Auto-generate permit sets** | Manual compilation, 2-12 weeks | Auto-generate from BIM model, jurisdiction-aware | Compress permitting to days |
| **Foundation design from reactions** | Manual engineering, 1-4 weeks | Auto-generate from manufacturer reaction data | Eliminate the #1 handoff delay |
| **Multi-option generative design** | 1-2 options manually explored | Hundreds of options evaluated against constraints | Better buildings, faster decisions |
| **Real-time cost estimation** | 6-8 hours per estimate | Instant with current material pricing | 3x more bids, higher win rate |
| **Clash detection across trades** | Manual or limited BIM coordination | AI-powered automatic detection and resolution suggestions | Fewer field surprises |
| **Panel system specification** | Manual selection from manufacturer catalogs | AI recommends optimal panel system for thermal/structural/cost requirements | Faster enclosure decisions |
| **Construction scheduling** | Manual or template-based | AI-optimized from BIM model + historical data | 15-20% schedule reduction |

---

## 8. Could Bonsai AI Replicate the PEMB Speed Advantage for Office Buildings?

### Why PEMB is Fast (the Transferable Principles)

1. **Parametric design**: The building is defined by a small number of parameters. Everything else is derived. This is the #1 principle to transfer.
2. **Automated engineering**: Structural design is automated, not manual. The software knows the manufacturer's inventory, codes, and detailing rules.
3. **Standardized connections**: Every connection type is pre-designed. No custom engineering per joint.
4. **Integrated cost model**: Design and cost are computed simultaneously. No separate estimating phase.
5. **Automated drawing production**: Drawings are generated from the model, not drawn by hand.
6. **Factory fabrication**: Components are made in a controlled environment with CNC precision.

### What Would Need to Change for Office Buildings

Office buildings are more complex than PEMB warehouses:
- Multi-story (2-20+ stories vs. 1-2 for PEMB)
- Mixed structural systems (steel frame + concrete cores, post-tensioned slabs)
- Complex MEP systems (HVAC distribution, plumbing risers, electrical panels)
- Architectural finish requirements (curtain walls, interior partitions, ceilings)
- Fire protection systems (sprinklers, rated assemblies, stair pressurization)
- Accessibility requirements
- Parking structures (often integrated)
- Zoning and FAR constraints

### The Bonsai AI Approach

To replicate PEMB speed for office buildings, Bonsai AI would need to:

1. **Create a parametric office building system**: Define an office building by ~50-100 parameters (vs. ~20 for PEMB). Let AI derive the complete structural, MEP, and architectural design from those parameters.

2. **Build a library of pre-designed systems**: Like PEMB's standardized connections, create pre-engineered subsystems for office buildings (floor systems, core layouts, curtain wall assemblies, MEP risers, stair/elevator cores).

3. **Automate structural engineering**: Use AI to size members, design connections, and optimize material usage -- the way MBS does for rigid frames, but for moment frames, braced frames, and concrete cores.

4. **Auto-generate permit sets**: The PEMB industry has shown that automated drawing production works. Extend this to office building permit sets with jurisdiction-aware requirements.

5. **Integrate cost estimation**: Like MBS, compute cost simultaneously with design. No separate estimating step.

6. **Close the foundation gap**: Auto-design foundations from structural reactions, something even PEMB hasn't fully automated.

7. **Coordinate all trades in one model**: Unlike PEMB where the manufacturer only handles structure + envelope, an AI system for office buildings must coordinate structure, MEP, fire protection, and architecture simultaneously.

### Realistic Timeline Comparison

| Phase | PEMB (current) | Office (current) | Office (with Bonsai AI target) |
|-------|----------------|-------------------|-------------------------------|
| Concept to bid | 1-3 days | 2-4 weeks | 1-3 days |
| Detailed design | 2-4 weeks | 2-6 months | 2-4 weeks |
| Permitting | 2 weeks - 3 months | 1-6 months | 2-4 weeks |
| Fabrication/procurement | 4-8 weeks | 8-16 weeks | 4-8 weeks (with pre-engineered systems) |
| Construction | 2-7 weeks | 6-18 months | 3-9 months |
| **Total** | **8-20 weeks** | **12-30 months** | **4-12 months** |

The target: cut office building timelines by 50-60%, matching the speed advantage PEMB has over conventional construction.

---

## 9. Key Takeaways for Bonsai AI Strategy

### The PEMB industry has already proven that:
- Parametric design works: define 20 parameters, get a complete building
- Automated engineering works: MBS designs a building in 2 minutes
- Automated drawing production works: full shop and erection drawings without manual CAD
- Integrated cost models work: design and cost computed simultaneously
- Factory fabrication works: pre-punched, pre-numbered components bolt together fast

### The gaps that even PEMB hasn't solved:
- Foundation design is still a manual handoff
- MEP coordination doesn't exist in the PEMB workflow
- Multi-story buildings are outside PEMB's capability
- Architectural finishes beyond metal panels are not integrated
- Permitting is still manual document compilation
- Trade coordination relies on human project managers

### Where Bonsai AI should focus first:
1. **Instant parametric design for commercial buildings** -- extend the MBS model beyond simple rectangles
2. **Auto-generated permit packages** -- the most universally valuable automation
3. **Foundation auto-design from structural reactions** -- close the biggest handoff gap
4. **Real-time integrated estimating** -- design + cost simultaneously
5. **Generative design for optimization** -- explore hundreds of options, not one or two

### The competitive moat:
PEMB manufacturers have 30+ years of accumulated engineering rules baked into software like MBS. Replicating this for general commercial construction would require building a similar rules engine, but AI can leapfrog rules-based systems by learning from thousands of completed projects. The key differentiator would be handling complexity that PEMB can't: multi-story, mixed-use, complex geometry, full MEP integration.

---

## Sources

### PEMB Design Process
- [Pre-Engineered Metal Building (PEMB): Costs, Advantages](https://www.buildingsguide.com/build/pre-engineered-metal-building/)
- [Metal Building Pre-Construction Planning Guide](https://www.buildingsguide.com/build/metal-building-planning/)
- [Steel Structure Design Process of Pre-Engineered Building (Pebsteel)](https://pebsteel.com/en/steel-structure-design-process-of-pre-engineered-building/)
- [Understanding the Engineering Process and Types of Drawings for a PEMB](https://www.mtnssb.com/understanding-the-engineering-process-and-types-of-drawings-for-a-pre-engineered-metal-building-pemb/)

### Software Tools
- [Metal Building Software Inc (MBS)](https://mbsweb.com/)
- [MBS Program Overview -- Rigid Frame](https://mbsweb.com/program-overview-rigid-frame/)
- [MBS Estimating and Detailing](https://www.mbs-estimating.com/)
- [SmartBuild Systems](https://smartbuildsystems.com/smartbuild-for-all-metal-buildings/)
- [SteelSmart System](https://www.steelsmartsystem.com/)
- [MkaPEB -- AI-Powered PEB Design (RAMCADDS)](https://www.ramcadds.com/product/mkapeb-2/)
- [5 Powerful PEMB Estimating Tools](https://steelestimatingsolutions.com/steel-estimating-for-pemb-estimating-tool/)
- [Metal Building Bid Wizard](https://steelestimatingsolutions.com/mmbw/)

### BIM Integration
- [Full BIM Process for All Pre-Engineered Buildings (Trimble/Tekla)](https://www.trimble.com/blog/construction/en-US/article/full-bim-process-for-all-pre-engineered-buildings)
- [MBS and Tekla Powers Combine for PEBs](http://videos.trimble.com/structures/watch/CTFHiZydMUiFTZZDxxUSHM?chapter=1)
- [BIM -- Garco Buildings](https://www.garcobuildings.com/products-systems/bim/)
- [Kingspan Insulated Panel BIM Tools](https://www.kingspan.com/us/en/services/insulated-panel-bim-tools/)
- [Metl-Span 2D and 3D BIM Models](https://metlspan.com/resources/bim-files/)

### Major Manufacturers
- [Nucor Building Systems](https://www.nucorbuildingsystems.com/)
- [BlueScope Buildings North America](https://bluescopebuildings.com/)
- [Butler Manufacturing](https://www.butlermfg.com/)

### Timelines and Comparison
- [PEMB Erection Timeline: Phase-by-Phase Breakdown](https://www.alpha-labor-co.com/blog/pemb-erection-timeline)
- [Steel Building Timeline: Realistic Schedule](https://ztsteelstructure.com/steel-building-timeline-realistic-schedule-from-design-to-move-in/)
- [PEMB vs. Conventional Steel Construction](https://www.alpha-labor-co.com/blog/pre-engineered-metal-buildings-vs-conventional-steel-construction)
- [Speed to Market: How PEMBs Cut Construction Time by 30%](https://www.tylerbuilding.com/post/speed-to-market-how-pre-engineered-metal-buildings-cut-construction-time-by-30)

### Estimating and Pricing
- [Step-by-Step Guide to Estimating PEMB Costs (247PRO)](https://www.247pro.com/blog/step-by-step-guide-to-estimating-the-cost-of-pre-engineered-metal-buildings-pembs-and-steel-structures)
- [Steel Building Cost Estimator: Contractor's Guide to PEMB Pricing (CECO)](https://www.cecobuildings.com/blog/steel-building-cost-estimator-a-contractors-guide-to-pemb-pricing/)
- [From Days to Minutes: AI Revolutionizing Metal Building Quoting](https://medium.com/@prayagvakharia/from-days-to-minutes-how-ai-is-revolutionizing-metal-building-quoting-in-construction-a723caa54df8)

### Permits and Engineering
- [Building Permit Requirements for Prefabricated Metal Buildings (Portland)](https://www.portland.gov/ppd/documents/building-permit-requirements-prefabricated-metal-buildings/download)
- [PEMB Guidelines White Paper (Georgia)](https://gsfic.georgia.gov/document/document/pemb-guidelineswhite-paper/download)
- [Does a PEMB Require a Structural Engineer? (IONIC)](https://ionicdezigns.com/2022/05/16/ask-ionic-does-a-pemb-pre-engineered-metal-building-require-a-structural-engineer/)
- [Being the Engineer of Record on a Metal Building Project (STRUCTURE Magazine)](https://www.structuremag.org/webinar/being-the-engineer-of-record-on-a-metal-building-project/)
- [The Role of the Specialty Structural Engineer (Build Steel)](https://buildsteel.org/framing-products/structural/the-role-of-the-specialty-structural-engineer/)

### Panel Systems
- [Insulated Metal Panel IBC Specifications](https://www.metalconstruction.org/index.php/online-education/imp-ibc-specifications-roof-and-wall)
- [Connections for Architectural Precast Concrete (PCI)](https://www.enterpriseprecast.com/wp-content/uploads/2023/05/DN-32-Connections-for-Architectural-Precast.pdf)
- [Structural Concrete Insulated Panel (SCIP) (PCI Journal)](https://www.pci.org/PCI_Docs/Publications/PCI%20Journal/2022/March-April/20-0024_Mashal_MA22.pdf)
- [TIPS Panel -- Insulated Tilt-Up](https://www.tipspanel.com)

### AI in Construction
- [AI in Construction: Future of Steel Building](https://metalprobuildings.com/how-ai-and-robotics-are-changing-steel-building-construction/)
- [Metal Fabrication Trends 2025: AI and Automation](https://machinetoolnews.ai/metal-fabrication-trends-2025/)
- [Top 2025 AI Construction Trends (Autodesk)](https://www.autodesk.com/blogs/construction/top-2025-ai-construction-trends-according-to-the-experts/)

### Market Data
- [U.S. Pre-engineered Metal Building Market Size Report, 2033 (Grand View Research)](https://www.grandviewresearch.com/industry-analysis/us-pre-engineered-metal-building-market-report)
- [U.S. PEMB Market Forecast to $27B+ (GlobeNewsWire)](https://www.globenewswire.com/news-release/2024/08/22/2934417/0/en/U-S-Pre-engineered-Metal-Building-Industry-Report-2024-Growth-in-Warehousing-Activities-and-Rising-Economic-Development-in-Western-Southern-US-Driving-Growth.html)
