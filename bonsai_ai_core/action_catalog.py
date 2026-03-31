"""Shared action names and metadata schemas used across planning surfaces."""

from __future__ import annotations

from typing import Any, Dict, Mapping


JsonDict = Dict[str, Any]


BUILDABLE_ACTIONS = (
    "ensure_storey",
    "create_rect_slab",
    "create_wall",
    "create_column",
    "create_beam",
    "create_panel",
    "create_window",
    "create_door",
    "create_curtain_wall",
    "create_footing",
)

SEMANTIC_ACTIONS = (
    "create_stair_run",
    "create_stair_landing",
    "create_connection_plate",
    "generate_column_grid",
    "generate_perimeter_walls",
    "generate_floor_plate",
    "generate_facade_grid",
)

EDIT_ACTIONS = (
    "update_element",
    "delete_element",
    "move_element",
    "replace_section",
    "rebuild_branch",
)

SUPPORTED_ACTIONS = BUILDABLE_ACTIONS + SEMANTIC_ACTIONS + EDIT_ACTIONS


def _string(description: str) -> JsonDict:
    return {"type": "string", "description": description}


def _number(description: str) -> JsonDict:
    return {"type": "number", "description": description}


def _integer(description: str) -> JsonDict:
    return {"type": "integer", "description": description}


def _boolean(description: str) -> JsonDict:
    return {"type": "boolean", "description": description}


def _enum(description: str, values: list[str]) -> JsonDict:
    return {"type": "string", "description": description, "enum": values}


def _string_array(description: str) -> JsonDict:
    return {"type": "array", "description": description, "items": {"type": "string"}}


def object_schema(description: str, properties: Mapping[str, JsonDict]) -> JsonDict:
    return {
        "type": "object",
        "description": description,
        "additionalProperties": False,
        "properties": dict(properties),
    }


def merge_properties(*groups: Mapping[str, JsonDict]) -> JsonDict:
    merged: JsonDict = {}
    for group in groups:
        merged.update(group)
    return merged


COMMON_SEMANTIC_PROPERTIES: JsonDict = {
    "element_id": _string("Stable semantic element identifier used by AI editing, rebuilds, and review selection."),
    "parent_id": _string("Optional semantic parent identifier for nested assemblies or grouped subcomponents."),
    "assembly_id": _string("Optional stable assembly identifier for reusable grouped systems."),
    "role": _string("High-level semantic role, such as structure, envelope, openings, foundations, or cladding."),
    "subrole": _string("Optional subrole, such as perimeter_column, storefront_window, or spread_footing."),
    "system_name": _string("Human-readable system name for import grouping and reporting."),
    "group_name": _string("Display group name for a collection or tree node."),
    "group_path": _string_array("Ordered tree path for grouping and selection, from coarse to fine."),
    "parent_name": _string("Optional parent display name for nested grouping."),
    "collection_key": _string("Stable collection key used by downstream import and styling tools."),
    "selector_tags": _string_array("Optional tags used by Blender selection helpers and filters."),
    "is_exposed": _boolean("Whether the element should be treated as exposed or visible in review views."),
    "view_mode": _string("Optional default view mode hint, such as normal, isolate, or xray."),
}

COMMON_PRESENTATION_PROPERTIES: JsonDict = {
    "presentation_style": _string("Presentation preset key for Blender styling."),
    "material_key": _string("Material library key for Blender styling."),
}

WINDOW_PRESENTATION_PROPERTIES: JsonDict = {
    "window_type": _string("Window type, such as storefront, punched, ribbon, or service."),
    "frame_style": _string("Frame style key for the window."),
    "glazing_style": _string("Glazing style key for the window."),
    "glass_material_key": _string("Material library key for the glass."),
    "frame_material_key": _string("Material library key for the frame."),
    "transparency": _number("Transparency hint between 0 and 1."),
    "mullion_pattern": _string_array("Optional mullion pattern or segmentation tokens."),
    "is_storefront": _boolean("Whether the window should be treated as storefront glazing."),
}

FOOTING_PROPERTIES: JsonDict = {
    "foundation_type": _string("Foundation type, such as spread_footing or strip_footing."),
    "bearing_elevation": _number("Bearing or founding elevation in meters."),
    "support_for": _string("Name or identifier of the supported element or assembly."),
    "soil_assumption": _string("Text note describing the assumed soil condition."),
    "structural_role": _string("Structural role, such as interior, perimeter, or retaining."),
    "load_combo": _string("Governing load combination identifier."),
    "imposed_load_kN": _number("Imposed load or governing reaction in kilonewtons."),
    "service_reaction_kN": _number("Service vertical reaction in kilonewtons."),
    "allowable_bearing_kpa": _number("Allowable bearing pressure in kPa."),
    "concrete_strength_mpa": _number("Specified concrete strength in MPa."),
    "rebar_yield_strength_mpa": _number("Yield strength of reinforcing steel in MPa."),
    "rebar_grade": _string("Rebar grade or specification key."),
    "rebar_weight_kg": _number("Estimated rebar weight for the footing in kilograms."),
    "rebar_bar_diameter_mm": _number("Primary reinforcing bar diameter in millimeters."),
    "rebar_spacing_mm": _number("Primary reinforcing bar spacing in millimeters."),
    "rebar_layer_count": _number("Estimated count of reinforcement layers."),
    "rebar_schedule": _string_array("Short reinforcement schedule notes."),
    "basis_notes": _string("Short note explaining the engineering basis for the footing design."),
}

SEMANTICS_OBJECT = object_schema(
    "Optional semantic metadata used for grouping, naming, and selection trees in Blender/Bonsai.",
    COMMON_SEMANTIC_PROPERTIES,
)

PRESENTATION_OBJECT = object_schema(
    "Optional presentation metadata used during style-baking and saved blend generation.",
    merge_properties(COMMON_PRESENTATION_PROPERTIES, WINDOW_PRESENTATION_PROPERTIES),
)

FOUNDATION_OBJECT = object_schema("Optional footing and foundation design metadata tied to imposed loads.", FOOTING_PROPERTIES)


COMMON_ACTION_PROPERTIES: JsonDict = {
    "type": {"type": "string", "enum": list(SUPPORTED_ACTIONS)},
    "name": _string("Stable descriptive action or element name."),
    "target_id": _string("Stable semantic element identifier targeted by an edit or rebuild action."),
    "target_name": _string("Stable name of an existing authored element to edit."),
    "target_path": _string_array("Semantic tree path of the branch to rebuild or isolate."),
    "target_selector_tags": _string_array("Selector tags used to target one or more semantic elements."),
    "storey": _string("Storey label for plan actions that target a storey by name."),
    "storey_name": _string("Explicit storey label used by IFC authoring calls."),
    "wall_name": _string("Name of an existing host wall."),
    "notes": _string("Optional notes for the action."),
    "section_id": _string("Optional named structural section identifier for replace-section actions."),
    "patch": {"type": "object", "description": "Top-level or nested field updates applied by semantic edit actions.", "additionalProperties": True},
    "x": _number("X coordinate in meters."),
    "y": _number("Y coordinate in meters."),
    "z": _number("Z coordinate in meters."),
    "dx": _number("Offset in X for move actions, in meters."),
    "dy": _number("Offset in Y for move actions, in meters."),
    "dz": _number("Offset in Z for move actions, in meters."),
    "x1": _number("First X coordinate in meters."),
    "y1": _number("First Y coordinate in meters."),
    "x2": _number("Second X coordinate in meters."),
    "y2": _number("Second Y coordinate in meters."),
    "width": _number("Width in meters."),
    "depth": _number("Depth in meters."),
    "length": _number("Length in meters."),
    "height": _number("Height in meters."),
    "thickness": _number("Thickness in meters."),
    "center_x": _number("Center X coordinate in meters."),
    "center_y": _number("Center Y coordinate in meters."),
    "tread_depth": _number("Tread depth in meters."),
    "riser_height": _number("Riser height in meters."),
    "step_count": _integer("Number of stair steps."),
    "direction_deg": _number("Direction or heading in degrees."),
    "elevation": _number("Elevation in meters."),
    "orientation": _enum("Orientation for plate-like elements.", ["vertical", "horizontal"]),
    "rotation_deg": _number("Rotation in degrees."),
    "rotation_degrees": _number("Rotation in degrees."),
    "panel_width": _number("Panel width in meters."),
    "panel_height": _number("Panel height in meters."),
    "panel_gap": _number("Panel gap in meters."),
    "panel_thickness": _number("Panel thickness in meters."),
    "base_z": _number("Base elevation in meters."),
    "top_z": _number("Top elevation in meters."),
    "end_z": _number("End elevation in meters."),
    "offset_along_wall": _number("Offset along a host wall in meters."),
    "sill_height": _number("Sill height in meters."),
    "replacement_actions": {
        "type": "array",
        "description": "Replacement authored actions for branch rebuild operations.",
        "items": {"type": "object", "additionalProperties": True},
    },
    # Parametric generator fields
    "grid_origin_x": _number("Grid origin X coordinate in meters."),
    "grid_origin_y": _number("Grid origin Y coordinate in meters."),
    "bays_x": _integer("Number of bays in the X direction."),
    "bays_y": _integer("Number of bays in the Y direction."),
    "spacing_x": _number("Bay spacing in the X direction in meters."),
    "spacing_y": _number("Bay spacing in the Y direction in meters."),
    "column_width": _number("Column width in meters."),
    "column_depth": _number("Column depth in meters."),
    "column_height": _number("Column height in meters."),
    "corners": {
        "type": "array",
        "description": "Array of [x, y] polygon vertices defining a perimeter.",
        "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
    },
    "include_edge_beams": _boolean("Whether to generate perimeter beams around the floor plate."),
    "beam_width": _number("Beam width in meters."),
    "beam_depth": _number("Beam depth in meters."),
    "start_x": _number("Start X coordinate in meters."),
    "start_y": _number("Start Y coordinate in meters."),
    "end_x": _number("End X coordinate in meters."),
    "end_y": _number("End Y coordinate in meters."),
    "semantics": SEMANTICS_OBJECT,
    "presentation": PRESENTATION_OBJECT,
    "foundation": FOUNDATION_OBJECT,
}
