# Tool Specs

## Purpose
Defines the JSON schemas for all available IFC authoring tools and provides provider-specific formatting for OpenAI, Anthropic, and Gemini.

## How It Works

### tool_specs.py (307 lines)
- **`ToolSpec`** dataclass: `name`, `description`, `schema` (JSON Schema dict).
- **`TOOL_SPECS`** list of 11 ToolSpec instances:
  - `ensure_project` (project_name, site_name, building_name)
  - `ensure_storey` (name, elevation, optional semantics)
  - `create_rectangular_slab` (name, storey_name, x, y, z, length, width, thickness, rotation_deg + metadata)
  - `create_wall` (name, storey_name, start/end x/y, base_z, height, thickness + metadata)
  - `create_column` (name, storey_name, x, y, base_z, width, depth, height, rotation_deg + metadata)
  - `create_beam` (name, storey_name, start/end x/y, base_z, end_z, width, depth + metadata)
  - `create_panel` (name, storey_name, x, y, base_z, width, height, depth, thickness, orientation enum, rotation_deg + metadata)
  - `create_footing` (name, storey_name, x, y, base_z, length, width, thickness, rotation_deg + metadata)
  - `create_door` (name, storey_name, wall_name, offset_along_wall, width, height, thickness + metadata)
  - `create_window` (same as door + sill_height + metadata)
  - `create_curtain_wall` (name, storey_name, x, y, base_z, width, height, rotation_degrees, panel_width, panel_height, panel_thickness + metadata)
- **Common metadata** added via `_with_common_metadata()`: `semantics` (SEMANTICS_OBJECT), `presentation` (PRESENTATION_OBJECT), `foundation` (FOUNDATION_OBJECT) -- all imported from `bonsai_ai_core.action_catalog`.
- **Provider formatters:**
  - `as_openai_tools()` wraps each spec in `{"type": "function", "function": {..., "strict": True}}`.
  - `as_anthropic_tools()` uses `input_schema` key.
  - `as_gemini_tools()` uses `parameters` key.
- `tool_names()` returns list of all tool names.

## Current State
Fully implemented. This module is used by `cli.py`'s planner path (the older direct tool-call approach). The newer pipeline path (`design_pipeline_cli.py`) uses `bonsai_ai_core`'s `action_catalog` and `schema.py` instead, which defines a superset of actions including semantic actions (`create_stair_run`, `create_connection_plate`) and edit actions (`update_element`, `delete_element`, `move_element`, etc.).

## Known Issues
- This file is only used by the legacy `cli.py` path. The pipeline path bypasses it entirely, using `bonsai_ai_core`'s schema instead. This creates a risk of the two diverging.
- `ensure_project` is defined here but not in `_TOOL_NAME_MAP` in `planner.py`, meaning the planner can never emit it through the legacy path.
- All schemas set `additionalProperties: false`, which is correct for strict validation but means any new metadata fields require schema updates.

## Last Reviewed
2026-03-31
