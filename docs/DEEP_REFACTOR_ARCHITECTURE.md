# Deep Refactor Architecture

## Goal

Turn Blender into a thin client for an AI-driven design and engineering workflow that can:

- generate a design from prompt plus documents
- author clean BIM and IFC geometry
- export an analytical model for structural checks
- run wind, seismic, gravity, footing, and structural steel analysis in a dedicated solver
- round-trip results back into Blender for review, rendering, and iteration

## Recommendation

Choose the deep target architecture, but build it through a medium first slice:

1. define shared domain contracts
2. introduce a pipeline/orchestration layer outside Blender
3. keep Blender focused on delivery and interactive review
4. hand analysis to a dedicated structural solver stack

## Target Architecture

### Blender Thin Client

Responsibilities:

- prompt and document intake
- scene context capture
- job submission
- progress and status display
- result overlays
- rendering and review

Not responsible for:

- primary planning logic
- project bootstrap in headless automation
- structural solving
- engineering code checks

### Core Pipeline

Responsibilities:

- normalize prompt and reference documents into a `DesignBrief`
- plan a physical model
- materialize IFC artifacts
- export analytical artifacts
- dispatch solver jobs
- collect solver results
- produce a stable manifest for review and audit

The first slice of this layer is implemented in:

- [contracts.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/contracts.py)
- [pipeline.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/pipeline.py)

### Physical BIM Authoring

Two execution backends should exist:

- interactive `BonsaiSessionExecutor` for Blender+Bonsai sessions
- headless `HeadlessIfcExecutor` for CI and automation using direct IFC authoring

The current headless-friendly seam already exists in:

- [ifc_author.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/ifc_author.py)

### Structural Analysis

Use a dedicated solver stack, not Blender, for final engineering checks.

Open-source path:

- IfcOpenShell / Bonsai for IFC authoring
- Ifc2CA for analytical export
- Code_Aster, CalculiX, or a similar solver for structural analysis

Commercial path:

- RFEM
- ETABS / SAP2000
- Tekla Structural Designer
- IDEA StatiCa for detail checks

### Feedback Loop

1. Create a `DesignBrief`
2. Generate a `PhysicalModelSpec`
3. Produce IFC
4. Export analytical model
5. Run solver load cases
6. Import governing ratios and warnings into Blender as overlays and metadata
7. Re-plan against those results

## Near-Term Migration Plan

### Phase 1

- land shared contracts and pipeline manifest
- stop treating Blender as the orchestration center
- keep existing addon UI, but redirect automation to pipeline APIs

### Phase 2

- add explicit executor backends
- move plan execution out of addon internals
- add analytical export adapters

### Phase 3

- add solver connectors and result ingestion
- introduce review overlays and analytical issue visualization in Blender

### Phase 4

- expand the domain schema to handle sandwich panels, connectors, anchors, girt spacing, load cases, and design assumptions as first-class concepts

## Why This Matters

The current background failure shows the core issue: Blender and Bonsai session state should not be the system's source of truth for automation. Geometry authoring, analysis export, solver execution, and review need stable contracts that survive outside a live Blender UI session.
