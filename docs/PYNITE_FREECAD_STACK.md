# PyNite + FreeCAD Stack

This repo should treat the PyNite + FreeCAD path as a handoff stack, not as a full in-repo replacement for FreeCAD.

## Practical boundary

- `Bonsai / IFC authoring`: create the physical building package and keep IFC as the primary geometric artifact.
- `In-repo analysis export`: write `analytical_model.json` and `solver_request.json` as the normalized structural handoff.
- `PyNite`: run fast frame-oriented analysis and publish a compact solver result artifact for the results bundle.
- `FreeCAD`: consume the IFC plus normalized bundle for downstream engineering review, refinement, and optional detailed FEM workflows.

## What we need now

- A stable pipeline contract that always produces:
  - `physical_model.ifc` or equivalent IFC output
  - `analytical_model.json`
  - `solver_request.json`
  - `results_bundle.json`
- A PyNite solver adapter that emits a machine-readable `solver_result` artifact.
- A lightweight `freecad_handoff.json` or equivalent report artifact so FreeCAD-facing tooling knows which IFC and result files belong together.

## Nice to have later

- Direct FreeCAD automation from this repo.
- Round-tripping detailed FE meshes back into the authoring workflow.
- Rich visualization artifacts beyond the normalized results bundle.

## Product direction

The important product direction is: this repo owns authoring, normalized exports, and fast analysis packaging. FreeCAD owns the deeper engineering workspace when a user needs a real downstream structural tool. That keeps the repo focused on stable artifacts instead of rebuilding FreeCAD inside the pipeline.
