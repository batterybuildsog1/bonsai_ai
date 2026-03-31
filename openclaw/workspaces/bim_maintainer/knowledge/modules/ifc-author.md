# IFC Author

## Purpose
The core geometry engine that creates native IFC4 elements using IfcOpenShell, applying tool calls to build slabs, walls, columns, beams, panels, doors, windows, curtain walls, and footings.

## How It Works

### IfcAuthor class (1110 lines, ~48KB)
**Constructor:** `IfcAuthor(path)` opens an existing IFC file or creates a new IFC4 project file. Calls `_ensure_contexts()` to guarantee a Body/MODEL_VIEW sub-context exists.

**Key properties:**
- `body_context` -- finds the IfcGeometricRepresentationSubContext with ContextType=Model, ContextIdentifier=Body, TargetView=MODEL_VIEW.
- `AI_PSET = "Pset_BonsaiAI"` -- all semantic metadata is stored in this custom property set on each element.

**Metadata system:**
- `_metadata(product)` reads `Pset_BonsaiAI` and JSON-decodes any string values that look like JSON.
- `_write_metadata(product, properties)` creates or updates the pset. Normalizes numpy scalars, serializes dicts/lists to JSON strings.
- `_merged_metadata(base, extra)` merges two dicts, skipping None values.
- `_presentation_metadata(payload)` extracts presentation-related fields (material_key, glass_material_key, window_type, etc.) from both nested `presentation` object and legacy flat keys.
- `_foundation_metadata(payload)` extracts foundation-related fields with alias normalization (e.g., `imposed_load_kn` -> `imposed_load_kn`, `total_rebar_weight_kg` -> `rebar_weight_kg`).

**Element creation methods (each returns ExecutionResult):**
- `ensure_project(project_name, site_name, building_name)` -- creates IfcProject/IfcSite/IfcBuilding hierarchy with SI units.
- `ensure_storey(name, elevation)` -- creates/updates IfcBuildingStorey, writes elevation metadata.
- `create_rectangular_slab(name, storey_name, x, y, z, length, width, thickness, rotation_deg, **semantic_metadata)` -- creates IfcSlab with a polyline-based slab representation. Supports rotation.
- `create_wall(name, storey_name, start_x/y, end_x/y, base_z, height, thickness)` -- creates IfcWall using wall representation. Calculates length/angle from endpoints.
- `create_column(name, storey_name, x, y, base_z, width, depth, height, rotation_deg)` -- creates IfcColumn with rectangular profile and extrusion.
- `create_beam(name, storey_name, start_x/y, end_x/y, base_z, width, depth, end_z)` -- creates IfcBeam using `_member_transform()` for proper 3D orientation. Uses rectangular profile.
- `create_panel(name, storey_name, x, y, base_z, width, height, depth, thickness, orientation, rotation_deg)` -- creates IfcPlate. Vertical panels use wall representation; horizontal panels use slab representation.
- `create_door(name, storey_name, wall_name, offset_along_wall, width, height, thickness)` -- creates IfcOpeningElement + IfcDoor, hosted in a wall via `_wall_frame()` and `_opening_transform()`.
- `create_window(...)` -- same pattern as door, with additional sill_height parameter.
- `create_curtain_wall(name, storey_name, x, y, base_z, width, height, rotation_degrees, panel_width, panel_height, panel_thickness)` -- creates IfcCurtainWall + grid of IfcPlate panels aggregated under it.
- `create_footing(name, storey_name, x, y, base_z, length, width, thickness, rotation_deg)` -- creates IfcFooting with slab representation. Writes extensive foundation metadata (rebar, bearing, etc.).

**Dispatch:**
- `apply_tool_call(tool_name, arguments)` dispatches to the correct method via a dict lookup.
- `apply_plan(tool_calls)` iterates over PlannedToolCall objects.

**Utilities:**
- `_member_transform(start, end)` computes a 4x4 transformation matrix for beam-like members using cross products for local axes.
- `scene_summary()` returns a text summary of the current model state for replanning context.
- `debug_dump()` returns JSON with element counts by type.

### ExecutionResult dataclass
Fields: `tool_name`, `element_name`, `message`, `ifc_class`, `global_id`, `metadata`.

### AuthoringError
Custom RuntimeError for recoverable authoring failures (zero-length walls/beams, missing storeys, missing walls for openings).

## Current State
Fully implemented with all 11 element types. Every element gets rich metadata in Pset_BonsaiAI including structural kind, material ref, section ref, and any semantic/presentation/foundation data passed through.

## Known Issues
- No `update_element` or `delete_element` capability -- elements are write-only after creation.
- All structural sections use `IfcRectangleProfileDef` regardless of the actual catalog section (W shapes, HSS, etc.). Real I-beam profiles are not modeled.
- `_wall_frame()` reads metadata from the pset to recover wall geometry, creating a circular dependency between writing and reading metadata. If pset writing fails silently, wall-hosted elements (doors/windows) break.
- Curtain wall panels are placed in world space using trigonometry rather than relative to the curtain wall placement, which could accumulate floating point drift for large facades.
- `scene_summary()` truncates to 20 items per type and 12 semantic samples, which could miss important context for large models.

## Last Reviewed
2026-03-31
