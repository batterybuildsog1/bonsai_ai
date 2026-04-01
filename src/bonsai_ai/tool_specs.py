from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from bonsai_ai_core.action_catalog import FOUNDATION_OBJECT, PRESENTATION_OBJECT, SEMANTICS_OBJECT


JsonDict = Dict[str, object]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: JsonDict


def _number(description: str) -> JsonDict:
    return {"type": "number", "description": description}


def _string(description: str) -> JsonDict:
    return {"type": "string", "description": description}


def _with_common_metadata(properties: Dict[str, JsonDict]) -> Dict[str, JsonDict]:
    return {
        **properties,
        "semantics": SEMANTICS_OBJECT,
        "presentation": PRESENTATION_OBJECT,
        "foundation": FOUNDATION_OBJECT,
    }


TOOL_SPECS: List[ToolSpec] = [
    ToolSpec(
        name="ensure_project",
        description="Initialize the IFC project hierarchy if it does not exist yet.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "project_name": _string("Project name."),
                "site_name": _string("Site name."),
                "building_name": _string("Building name."),
            },
            "required": ["project_name", "site_name", "building_name"],
        },
    ),
    ToolSpec(
        name="ensure_storey",
        description="Create a building storey if it does not exist.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": _string("Storey name, such as Level 0 or Level 2."),
                "elevation": _number("Storey elevation in meters."),
                "semantics": SEMANTICS_OBJECT,
            },
            "required": ["name", "elevation"],
        },
    ),
    ToolSpec(
        name="create_rectangular_slab",
        description="Create a rectangular slab as a native IfcSlab element.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Element name."),
                    "storey_name": _string("Storey that contains the slab."),
                    "x": _number("Bottom-left corner origin X in meters (NOT center). The slab extends from (x, y) to (x+length, y+width)."),
                    "y": _number("Bottom-left corner origin Y in meters (NOT center). The slab extends from (x, y) to (x+length, y+width)."),
                    "z": _number("Base elevation in meters."),
                    "length": _number("Slab extent along the X axis in meters (east-west dimension for a north-facing building)."),
                    "width": _number("Slab extent along the Y axis in meters (north-south dimension)."),
                    "thickness": _number("Slab thickness in meters."),
                    "rotation_deg": _number("Optional rotation around Z in degrees."),
                }
            ),
            "required": ["name", "storey_name", "x", "y", "z", "length", "width", "thickness"],
        },
    ),
    ToolSpec(
        name="create_wall",
        description="Create a straight native IfcWall between two XY points.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Wall name."),
                    "storey_name": _string("Storey that contains the wall."),
                    "start_x": _number("Wall start X in meters."),
                    "start_y": _number("Wall start Y in meters."),
                    "end_x": _number("Wall end X in meters."),
                    "end_y": _number("Wall end Y in meters."),
                    "base_z": _number("Wall base Z in meters."),
                    "height": _number("Wall height in meters."),
                    "thickness": _number("Wall thickness in meters."),
                }
            ),
            "required": ["name", "storey_name", "start_x", "start_y", "end_x", "end_y", "base_z", "height", "thickness"],
        },
    ),
    ToolSpec(
        name="create_column",
        description="Create a native IfcColumn using a rectangular profile.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Column name."),
                    "storey_name": _string("Storey that contains the column."),
                    "x": _number("Column center X in meters (column is centered on this point)."),
                    "y": _number("Column center Y in meters (column is centered on this point)."),
                    "base_z": _number("Column base Z in meters."),
                    "width": _number("Column width in meters."),
                    "depth": _number("Column depth in meters."),
                    "height": _number("Column height in meters."),
                    "rotation_deg": _number("Optional rotation around Z in degrees."),
                }
            ),
            "required": ["name", "storey_name", "x", "y", "base_z", "width", "depth", "height"],
        },
    ),
    ToolSpec(
        name="create_beam",
        description="Create a native IfcBeam between two 3D points using a rectangular profile.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Beam name."),
                    "storey_name": _string("Storey that contains the beam."),
                    "start_x": _number("Beam start X in meters."),
                    "start_y": _number("Beam start Y in meters."),
                    "end_x": _number("Beam end X in meters."),
                    "end_y": _number("Beam end Y in meters."),
                    "base_z": _number("Beam start Z in meters."),
                    "end_z": _number("Optional beam end Z in meters."),
                    "width": _number("Beam width in meters."),
                    "depth": _number("Beam depth in meters."),
                }
            ),
            "required": ["name", "storey_name", "start_x", "start_y", "end_x", "end_y", "base_z", "width", "depth"],
        },
    ),
    ToolSpec(
        name="create_panel",
        description="Create a native IfcPlate panel, vertical or horizontal.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Panel name."),
                    "storey_name": _string("Storey that contains the panel."),
                    "x": _number("Panel origin X in meters."),
                    "y": _number("Panel origin Y in meters."),
                    "base_z": _number("Panel base Z in meters."),
                    "width": _number("Panel width in meters."),
                    "height": _number("Panel height in meters for vertical panels."),
                    "depth": _number("Panel depth in meters for horizontal panels."),
                    "thickness": _number("Panel thickness in meters."),
                    "orientation": {"type": "string", "enum": ["vertical", "horizontal"], "description": "Panel orientation."},
                    "rotation_deg": _number("Optional rotation around Z in degrees."),
                }
            ),
            "required": ["name", "storey_name", "x", "y", "base_z", "width", "thickness"],
        },
    ),
    ToolSpec(
        name="create_footing",
        description="Create a native IfcFooting for a support condition.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Footing name."),
                    "storey_name": _string("Storey that contains the footing."),
                    "x": _number("Footing origin X in meters."),
                    "y": _number("Footing origin Y in meters."),
                    "base_z": _number("Bottom-of-footing Z in meters."),
                    "length": _number("Footing length in meters."),
                    "width": _number("Footing width in meters."),
                    "thickness": _number("Footing thickness in meters."),
                    "rotation_deg": _number("Optional rotation around Z in degrees."),
                }
            ),
            "required": ["name", "storey_name", "x", "y", "base_z", "length", "width", "thickness"],
        },
    ),
    ToolSpec(
        name="create_door",
        description="Create a native IfcDoor hosted in an existing wall.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Door name."),
                    "storey_name": _string("Storey that contains the door."),
                    "wall_name": _string("Exact wall name to host the door."),
                    "offset_along_wall": _number("Distance from wall start in meters."),
                    "width": _number("Door width in meters."),
                    "height": _number("Door height in meters."),
                    "thickness": _number("Door leaf thickness in meters."),
                }
            ),
            "required": ["name", "storey_name", "wall_name", "offset_along_wall", "width", "height", "thickness"],
        },
    ),
    ToolSpec(
        name="create_window",
        description="Create a native IfcWindow hosted in an existing wall.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Window name."),
                    "storey_name": _string("Storey that contains the window."),
                    "wall_name": _string("Exact wall name to host the window."),
                    "offset_along_wall": _number("Distance from wall start in meters."),
                    "sill_height": _number("Bottom of window above wall base in meters."),
                    "width": _number("Window width in meters."),
                    "height": _number("Window height in meters."),
                    "thickness": _number("Window depth in meters."),
                }
            ),
            "required": ["name", "storey_name", "wall_name", "offset_along_wall", "sill_height", "width", "height", "thickness"],
        },
    ),
    ToolSpec(
        name="create_curtain_wall",
        description="Create a native IfcCurtainWall plus aggregated IfcPlate panels.",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Curtain wall name."),
                    "storey_name": _string("Storey that contains the curtain wall."),
                    "x": _number("Facade origin X in meters."),
                    "y": _number("Facade origin Y in meters."),
                    "base_z": _number("Facade base Z in meters."),
                    "width": _number("Overall facade width in meters."),
                    "height": _number("Overall facade height in meters."),
                    "rotation_degrees": _number("Facade rotation around Z in degrees."),
                    "panel_width": _number("Typical panel width in meters."),
                    "panel_height": _number("Typical panel height in meters."),
                    "panel_thickness": _number("Panel thickness in meters."),
                }
            ),
            "required": ["name", "storey_name", "x", "y", "base_z", "width", "height", "rotation_degrees", "panel_width", "panel_height", "panel_thickness"],
        },
    ),
    # --- Parametric Generators ---
    ToolSpec(
        name="generate_column_grid",
        description=(
            "Generate a rectangular column grid. Compiles into (bays_x+1) * (bays_y+1) create_column calls. "
            "Use this instead of specifying individual columns when the layout follows a regular grid."
        ),
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Grid name, used as prefix for generated column names."),
                    "storey_name": _string("Storey that contains the columns."),
                    "grid_origin_x": _number("Grid origin X coordinate in meters."),
                    "grid_origin_y": _number("Grid origin Y coordinate in meters."),
                    "base_z": _number("Column base Z elevation in meters."),
                    "bays_x": {"type": "integer", "description": "Number of bays in the X direction."},
                    "bays_y": {"type": "integer", "description": "Number of bays in the Y direction."},
                    "spacing_x": _number("Bay spacing in X direction in meters."),
                    "spacing_y": _number("Bay spacing in Y direction in meters."),
                    "column_width": _number("Column cross-section width in meters."),
                    "column_depth": _number("Column cross-section depth in meters."),
                    "column_height": _number("Column height in meters."),
                    "rotation_deg": _number("Optional rotation of columns around Z in degrees."),
                }
            ),
            "required": [
                "name", "storey_name", "grid_origin_x", "grid_origin_y", "base_z",
                "bays_x", "bays_y", "spacing_x", "spacing_y",
                "column_width", "column_depth", "column_height",
            ],
        },
    ),
    ToolSpec(
        name="generate_perimeter_walls",
        description=(
            "Generate walls around a polygon perimeter. Compiles into len(corners) create_wall calls "
            "connecting consecutive vertices. The polygon is automatically closed."
        ),
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Perimeter wall group name."),
                    "storey_name": _string("Storey that contains the walls."),
                    "corners": {
                        "type": "array",
                        "description": "Array of [x, y] polygon vertices defining the perimeter in meters.",
                        "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                    },
                    "base_z": _number("Wall base Z elevation in meters."),
                    "height": _number("Wall height in meters."),
                    "thickness": _number("Wall thickness in meters."),
                }
            ),
            "required": ["name", "storey_name", "corners", "base_z", "height", "thickness"],
        },
    ),
    ToolSpec(
        name="generate_floor_plate",
        description=(
            "Generate a rectangular floor plate with optional perimeter edge beams. "
            "Compiles into 1 create_rect_slab plus optionally 4 create_beam calls."
        ),
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Floor plate name."),
                    "storey_name": _string("Storey that contains the floor plate."),
                    "x": _number("Floor plate origin X in meters."),
                    "y": _number("Floor plate origin Y in meters."),
                    "z": _number("Floor plate elevation in meters."),
                    "length": _number("Floor plate length in meters."),
                    "width": _number("Floor plate width in meters."),
                    "thickness": _number("Slab thickness in meters."),
                    "rotation_deg": _number("Optional rotation around Z in degrees."),
                    "include_edge_beams": {"type": "boolean", "description": "If true, add beams around the perimeter."},
                    "beam_width": _number("Edge beam width in meters (required if include_edge_beams is true)."),
                    "beam_depth": _number("Edge beam depth in meters (required if include_edge_beams is true)."),
                }
            ),
            "required": ["name", "storey_name", "x", "y", "z", "length", "width", "thickness"],
        },
    ),
    ToolSpec(
        name="generate_beam_grid",
        description=(
            "Generate beams at every gridline intersection. Compiles into bays_x*(bays_y+1) east-west beams "
            "plus bays_y*(bays_x+1) north-south beams. Use this after generate_column_grid with matching grid parameters."
        ),
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Beam grid name, used as prefix for generated beam names."),
                    "storey_name": _string("Storey that contains the beams."),
                    "grid_origin_x": _number("Grid origin X coordinate in meters."),
                    "grid_origin_y": _number("Grid origin Y coordinate in meters."),
                    "base_z": _number("Beam base Z elevation in meters."),
                    "bays_x": {"type": "integer", "description": "Number of bays in the X direction."},
                    "bays_y": {"type": "integer", "description": "Number of bays in the Y direction."},
                    "spacing_x": _number("Bay spacing in X direction in meters."),
                    "spacing_y": _number("Bay spacing in Y direction in meters."),
                    "beam_width": _number("Beam cross-section width in meters."),
                    "beam_depth": _number("Beam cross-section depth in meters."),
                }
            ),
            "required": [
                "name", "storey_name", "grid_origin_x", "grid_origin_y", "base_z",
                "bays_x", "bays_y", "spacing_x", "spacing_y",
                "beam_width", "beam_depth",
            ],
        },
    ),
    ToolSpec(
        name="generate_opening_array",
        description=(
            "Generate evenly spaced windows or doors along a wall. Compiles into N create_window "
            "or create_door calls. Use this instead of individual opening calls for repetitive facades."
        ),
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Opening array name, used as prefix for generated opening names."),
                    "storey_name": _string("Storey that contains the openings."),
                    "wall_name": _string("Exact wall name to host the openings."),
                    "count": {"type": "integer", "description": "Number of openings to generate."},
                    "spacing": _number("Center-to-center spacing between openings in meters."),
                    "start_offset": _number("Offset from wall start to the first opening center in meters."),
                    "opening_type": {"type": "string", "enum": ["window", "door"], "description": "Type of opening."},
                    "width": _number("Opening width in meters."),
                    "height": _number("Opening height in meters."),
                    "sill_height": _number("Sill height for windows in meters (ignored for doors)."),
                    "thickness": _number("Opening depth/thickness in meters."),
                }
            ),
            "required": [
                "name", "storey_name", "wall_name",
                "count", "spacing", "start_offset",
                "opening_type", "width", "height", "thickness",
            ],
        },
    ),
    ToolSpec(
        name="generate_facade_grid",
        description=(
            "Generate a curtain wall facade along a line. Compiles into 1 create_curtain_wall call. "
            "Use this for parametric facade definitions with panel dimensions."
        ),
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": _with_common_metadata(
                {
                    "name": _string("Facade name."),
                    "storey_name": _string("Storey that contains the facade."),
                    "start_x": _number("Facade line start X in meters."),
                    "start_y": _number("Facade line start Y in meters."),
                    "end_x": _number("Facade line end X in meters."),
                    "end_y": _number("Facade line end Y in meters."),
                    "base_z": _number("Facade base Z in meters."),
                    "height": _number("Facade height in meters."),
                    "panel_width": _number("Panel width in meters."),
                    "panel_height": _number("Panel height in meters."),
                    "panel_thickness": _number("Panel thickness in meters."),
                    "rotation_degrees": _number("Facade rotation around Z in degrees."),
                }
            ),
            "required": [
                "name", "storey_name", "start_x", "start_y", "end_x", "end_y",
                "base_z", "height", "panel_width", "panel_height", "panel_thickness",
            ],
        },
    ),
]


def as_openai_tools() -> List[JsonDict]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "strict": True,
                "parameters": spec.schema,
            },
        }
        for spec in TOOL_SPECS
    ]


def as_anthropic_tools() -> List[JsonDict]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.schema,
        }
        for spec in TOOL_SPECS
    ]


def as_gemini_tools() -> List[JsonDict]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.schema,
        }
        for spec in TOOL_SPECS
    ]


def tool_names() -> List[str]:
    return [spec.name for spec in TOOL_SPECS]
