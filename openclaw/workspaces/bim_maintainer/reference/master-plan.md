# Bonsai AI Master Plan

## Date: 2026-04-01
## Vision

Quickly design, cost, present, permit, and construct commercial steel buildings at a speed unheard of before today. The AI makes design decisions. Python does construction math. The output is permit-ready drawings, cost packages, and constructable IFC models.

## Architecture: Spec-First

```
User describes building → AI generates ~200-token spec (16 design decisions)
→ BuildingGenerator expands to 500+ elements deterministically (zero coordinate errors)
→ Engineering pipeline sizes members, designs footings
→ Cost estimator prices the building from quantities
→ 2D drawing generator produces permit sheets
→ Viewer presents the building for client review
```

## Current State (2026-04-01)

### Done
- [x] BuildingGenerator: spec → IFC in 2.2 seconds, 435 elements
- [x] Real AISC I-beam profiles (W12x40, W10x26, auto-sizing)
- [x] Gravity-sized spread footings (24 footings, load-based)
- [x] Correct grid coverage (auto-adjusts spacing to fit footprint)
- [x] Per-bay windows, curtain walls, mixed facades, doors
- [x] Roof slab, ground plane
- [x] Web viewer with IFC rendering
- [x] OpenClaw agents (operator + maintainer)
- [x] Blender agent panel (Phases 1-5)
- [x] Factor-once FEA solver (7.5-15.5x faster)
- [x] Pipeline caches and performance fixes

### Remaining Issues
- [ ] Windows render as dark voids (depth buffer — needs geometry fix)
- [ ] No 2D permit drawings
- [ ] No cost estimation
- [ ] No connection details
- [ ] No code compliance checks
- [ ] No landscaping/site beyond ground plane
- [ ] No tapered frames (rigid frame system)
- [ ] No insulated panel joints (1-inch gap + sealant)
- [ ] Dead code cleanup (mojo_modules, tool_registry, etc.)

## Phase 1: Cost Estimation (THIS WEEK)

Integrated into the engineering pipeline. Cost constrains design — you size members for loads AND budget.

### What to build
- Quantity extraction from IFC (steel weight, concrete volume, panel area)
- Unit cost database ($/ton steel, $/CY concrete, $/SF cladding, $/LF foundation)
- Cost report generator (line items + totals + $/SF building cost)
- Integration with BuildingGenerator output
- Cost comparison between design alternatives

### Deliverable
```
Building Cost Estimate
━━━━━━━━━━━━━━━━━━━━
Structure:
  Steel columns (W12x40): 120 × 4.5m × 59.5 kg/m = 32,130 kg @ $2.80/kg = $89,964
  Steel beams (W10x26): 190 × 8.0m × 38.7 kg/m = 58,824 kg @ $2.80/kg = $164,707
  Concrete slabs: 6 × 40m × 25m × 0.2m = 1,200 m³ @ $180/m³ = $216,000
Foundation:
  Spread footings: 24 × 1.5m × 1.5m × 0.4m = 21.6 m³ @ $220/m³ = $4,752
Envelope:
  Concrete walls: 19 walls, 2,470 m² @ $95/m² = $234,650
  Curtain wall: 180 m² @ $450/m² = $81,000
  Windows: 70 × $650 each = $45,500
  Doors: 2 × $1,200 each = $2,400
━━━━━━━━━━━━━━━━━━━━
Subtotal: $838,973
Contingency (10%): $83,897
Total: $922,870
Cost per SF: $922,870 / (40×25×5) × 10.764 = $17.13/SF
```

## Phase 2: 2D Permit Drawings (THIS MONTH)

### What to build
- SVG extraction via ifcopenshell.draw (floor plans, sections, elevations)
- Annotation templates (dimensions, grid lines, member labels)
- Sheet layout (title block, sheet numbering)
- PDF assembly
- Foundation plan with footing sizes and rebar

### Deliverable
- 6-8 sheet permit set as PDF
- Automated from the IFC model

## Phase 3: Rendering Quality (THIS MONTH)

### What to build
- Fix window geometry (thicker panes like curtain wall panels)
- AI rendering pipeline (screenshot → ControlNet → photorealistic)
- OR: Twinmotion export path (IFC → one-click import)
- Camera presets in the web viewer

## Phase 4: Code Compliance (THIS QUARTER)

### What to build
- IBC Table 503 lookup (construction type × occupancy → max height/area)
- Egress width calculations
- Fire separation requirements
- Accessibility checks (ADA)

## Phase 5: Construction Details (THIS QUARTER)

### What to build
- Connection detail templates (base plate, splice, knee brace)
- Insulated panel joint details (1-inch gap, Sika Flex sealant)
- Tapered rigid frame geometry
- Purlin/girt secondary framing
- Erection sequence

## Phase 6: Full Pipeline Integration (NEXT QUARTER)

### What to build
- End-to-end: prompt → spec → IFC → analysis → sizing → cost → drawings → presentation
- The agent operates the full pipeline iteratively
- Client-facing web portal for review
- Version comparison (design A vs design B with cost delta)

## Key Principles

1. **AI makes decisions, Python does math** — never ask the AI to compute coordinates
2. **Quality over speed** — but we get both because deterministic generation is fast AND correct
3. **Real components** — AISC sections, not rectangular boxes. Insulated panels with joints, not abstract walls.
4. **The output is the product** — permit drawings, cost reports, and client presentations. Not just 3D geometry.
5. **The agent operates the app** — it uses the tools iteratively with feedback, not one-shot generation
6. **Cost constrains design** — every member size decision has a cost implication
