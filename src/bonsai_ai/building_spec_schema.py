"""JSON Schema for the building spec -- the declarative input to BuildingGenerator.

The AI generates JSON conforming to this schema. Only ``footprint`` and
``stories`` are required; every other field has sensible defaults that the
deterministic generators fill in.
"""

from __future__ import annotations

from typing import Any, Dict


# ---------------------------------------------------------------------------
# Shared sub-schemas
# ---------------------------------------------------------------------------

_FACADE_SPEC: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["wall", "curtain_wall", "panel_array"],
            "description": "'wall' = solid wall with optional punched windows. 'curtain_wall' = glass facade. 'panel_array' = insulated concrete panels.",
        },
        "material": {
            "type": "string",
            "enum": ["concrete", "concrete_insulated", "metal", "cmu", "brick"],
        },
        "thickness": {"type": "number", "description": "Wall thickness, meters."},
        "stories": {
            "type": "string",
            "enum": ["all", "ground_only", "upper_only"],
            "description": "Which stories this facade applies to.",
        },
        "windows": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "enum": ["per_bay", "ribbon", "none"],
                },
                "count_per_bay": {"type": "integer"},
                "width": {"type": "number", "description": "Window width, meters."},
                "height": {"type": "number", "description": "Window height, meters."},
                "sill_height": {"type": "number", "description": "Sill height above floor, meters."},
            },
        },
        "curtain_wall": {
            "type": "object",
            "properties": {
                "panel_width": {"type": "number"},
                "panel_height": {"type": "number"},
                "panel_thickness": {"type": "number"},
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Main schema
# ---------------------------------------------------------------------------

BUILDING_SPEC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["footprint", "stories"],
    "properties": {
        "project_name": {
            "type": "string",
            "description": "Name for the IFC project.",
        },

        # -- Footprint --
        "footprint": {
            "type": "object",
            "required": ["length", "width"],
            "properties": {
                "length": {
                    "type": "number",
                    "description": "Building extent along X axis in meters.",
                },
                "width": {
                    "type": "number",
                    "description": "Building extent along Y axis in meters.",
                },
                "origin": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Origin [x, y] in meters. Default [0, 0].",
                },
            },
        },

        # -- Grid --
        "grid": {
            "type": "object",
            "description": "Structural column grid. Generator adjusts spacing to fit footprint evenly.",
            "properties": {
                "spacing_x": {"type": "number", "description": "Target bay spacing in X, meters."},
                "spacing_y": {"type": "number", "description": "Target bay spacing in Y, meters."},
                "bays_x": {"type": "integer", "description": "Explicit bay count in X. Overrides spacing_x."},
                "bays_y": {"type": "integer", "description": "Explicit bay count in Y. Overrides spacing_y."},
            },
        },

        # -- Stories --
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["height"],
                "properties": {
                    "name": {"type": "string", "description": "Storey name. Defaults to 'Level N'."},
                    "height": {"type": "number", "description": "Floor-to-floor height in meters."},
                    "elevation": {
                        "type": "number",
                        "description": "Storey elevation in meters. Auto-calculated if omitted.",
                    },
                    "program": {
                        "type": "string",
                        "enum": [
                            "retail",
                            "office",
                            "parking",
                            "residential",
                            "industrial",
                            "mezzanine",
                            "mechanical",
                            "lobby",
                            "warehouse",
                        ],
                        "description": "Program type. Affects slab thickness defaults.",
                    },
                    "slab_thickness": {
                        "type": "number",
                        "description": "Override slab thickness for this floor, meters.",
                    },
                    "exclude_slab": {
                        "type": "boolean",
                        "description": "If true, no slab is generated for this storey.",
                    },
                },
            },
            "minItems": 1,
        },

        # -- Structure --
        "structure": {
            "type": "object",
            "description": "Structural system parameters.",
            "properties": {
                "frame_type": {
                    "type": "string",
                    "enum": ["braced", "moment", "rigid", "post_and_beam"],
                },
                "column_section": {
                    "type": "string",
                    "description": "Column section. 'auto' = from catalog. Or metric dims '0.3x0.3'.",
                },
                "beam_section": {
                    "type": "string",
                    "description": "Beam section. Same format as column_section.",
                },
                "slab_thickness": {
                    "type": "number",
                    "description": "Default slab thickness in meters.",
                },
                "roof_type": {
                    "type": "string",
                    "enum": ["flat_slab", "standing_seam", "metal_deck", "concrete"],
                },
            },
        },

        # -- Facades --
        "facades": {
            "type": "object",
            "description": "Envelope per cardinal face. Missing faces default to concrete wall.",
            "properties": {
                "north": _FACADE_SPEC,
                "south": _FACADE_SPEC,
                "east": _FACADE_SPEC,
                "west": _FACADE_SPEC,
            },
        },

        # -- Entries --
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["face"],
                "properties": {
                    "face": {
                        "type": "string",
                        "enum": ["north", "south", "east", "west"],
                    },
                    "type": {
                        "type": "string",
                        "enum": ["single", "double", "revolving", "overhead", "service"],
                    },
                    "width": {"type": "number", "description": "Door width, meters."},
                    "height": {"type": "number", "description": "Door height, meters."},
                    "position": {
                        "type": "string",
                        "enum": ["center", "left_third", "right_third"],
                    },
                    "position_offset": {
                        "type": "number",
                        "description": "Explicit offset along wall, meters.",
                    },
                    "story_index": {
                        "type": "integer",
                        "description": "Which story this entry is on (0-indexed).",
                    },
                },
            },
        },

        # -- Mezzanines --
        "mezzanines": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["story_index"],
                "properties": {
                    "story_index": {"type": "integer"},
                    "sides": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["north", "south", "east", "west", "full"],
                        },
                    },
                    "depth": {
                        "type": "number",
                        "description": "How far the mezzanine extends from the wall, meters.",
                    },
                    "height_fraction": {
                        "type": "number",
                        "description": "Mezzanine slab placed at this fraction of the story height.",
                    },
                    "slab_thickness": {"type": "number"},
                },
            },
        },

        # -- Roof --
        "roof": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["flat_slab", "standing_seam", "metal_deck", "concrete"],
                },
                "thickness": {"type": "number", "description": "Roof slab thickness, meters."},
            },
        },

        # -- Foundation --
        "foundation": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["spread_footings", "mat_slab", "grade_beams", "piles"],
                },
                "bearing_elevation": {
                    "type": "number",
                    "description": "Top-of-footing elevation, meters.",
                },
                "soil_bearing_kpa": {
                    "type": "number",
                    "description": "Allowable soil bearing pressure.",
                },
            },
        },
    },
}


def building_spec_schema() -> Dict[str, Any]:
    """Return a copy of the building spec JSON schema."""
    import copy
    return copy.deepcopy(BUILDING_SPEC_SCHEMA)
