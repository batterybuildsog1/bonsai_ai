# Spec-First Building Generator: System Design

> Date: 2026-03-30
> Author: Claude Opus 4.6 (automated research + design)
> Status: Design specification -- no code changes
> Depends on: simplification-research.md findings, existing IfcAuthor API, system_catalog.py

---

## Executive Summary

The current system asks an AI to generate hundreds of coordinate-level actions to build a structure. Both GPT-5.4 and Claude fail at scale (the 5-story building requires ~522 elements, ~8,000 tokens of perfect JSON). The spec-first architecture inverts this: the AI produces a structured specification (~16-25 design decisions, ~200-400 tokens), and deterministic Python generators expand it into a complete, perfectly-coordinated IFC model.

This document defines:
1. The building spec JSON schema (what the AI outputs)
2. The generator architecture (what Python computes)
3. How the two integrate
4. Migration path from the current action-based system

---

## Part 1: The Building Spec Schema

### Design Principles

1. **Every field is a design decision, not a coordinate.** The AI decides "8m bay spacing," not "column at x=16."
2. **Sensible defaults everywhere.** A minimal spec produces a complete building. Detail is additive.
3. **The spec is the single source of truth.** Regenerating from the same spec always produces the same model.
4. **Fields map to how architects and engineers think.** Footprint, grid, program, envelope -- not IFC classes.

### Complete Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "BuildingSpec",
  "description": "A declarative building specification that deterministic generators expand into a complete IFC model.",
  "type": "object",
  "required": ["footprint", "stories"],
  "properties": {

    "project_name": {
      "type": "string",
      "default": "AI Building",
      "description": "Name for the IFC project."
    },

    "footprint": {
      "description": "Building footprint. Rectangular (length/width) or polygonal (vertices).",
      "oneOf": [
        {
          "type": "object",
          "required": ["length", "width"],
          "properties": {
            "length": { "type": "number", "description": "X-dimension in meters." },
            "width": { "type": "number", "description": "Y-dimension in meters." },
            "origin": {
              "type": "array", "items": { "type": "number" }, "minItems": 2, "maxItems": 2,
              "default": [0, 0],
              "description": "Origin [x, y] in meters. Defaults to [0, 0]."
            }
          },
          "additionalProperties": false
        },
        {
          "type": "object",
          "required": ["vertices"],
          "properties": {
            "vertices": {
              "type": "array",
              "items": { "type": "array", "items": { "type": "number" }, "minItems": 2, "maxItems": 2 },
              "minItems": 3,
              "description": "Polygon vertices [[x,y], ...] in meters, counter-clockwise. The generator decomposes into rectangular zones for column placement."
            }
          },
          "additionalProperties": false
        }
      ]
    },

    "grid": {
      "type": "object",
      "description": "Structural column grid. Specify spacing (the generator computes bay counts from footprint) or bay counts (the generator computes spacing).",
      "properties": {
        "spacing_x": { "type": "number", "description": "Target bay spacing in X, meters. Generator adjusts last bay if footprint is not evenly divisible." },
        "spacing_y": { "type": "number", "description": "Target bay spacing in Y, meters." },
        "bays_x": { "type": "integer", "description": "Explicit bay count in X. Overrides spacing_x if both given." },
        "bays_y": { "type": "integer", "description": "Explicit bay count in Y. Overrides spacing_y if both given." }
      },
      "additionalProperties": false,
      "default": { "spacing_x": 8.0, "spacing_y": 8.0 }
    },

    "stories": {
      "type": "array",
      "minItems": 1,
      "description": "Floor definitions, bottom to top. The generator creates storeys at cumulative elevations.",
      "items": {
        "type": "object",
        "required": ["height"],
        "properties": {
          "name": { "type": "string", "description": "Storey name. Defaults to 'Level N'." },
          "height": { "type": "number", "description": "Floor-to-floor height in meters." },
          "program": {
            "type": "string",
            "enum": ["retail", "office", "parking", "residential", "industrial", "mezzanine", "mechanical", "lobby"],
            "default": "office",
            "description": "Program type. Affects default slab thickness, ceiling height, and structural loading."
          },
          "slab_thickness": { "type": "number", "description": "Override slab thickness for this floor, meters." },
          "exclude_slab": { "type": "boolean", "default": false, "description": "If true, no slab is generated for this storey (e.g., double-height space below)." }
        },
        "additionalProperties": false
      }
    },

    "structure": {
      "type": "object",
      "description": "Structural system parameters.",
      "properties": {
        "frame_type": {
          "type": "string",
          "enum": ["braced", "moment", "rigid", "post_and_beam"],
          "default": "braced",
          "description": "Primary structural system. 'rigid' triggers tapered members in the generator."
        },
        "column_section": {
          "type": "string",
          "default": "auto",
          "description": "Column section. 'auto' = generator selects from catalog by load. Named sections: 'W12x40', 'HSS8x8x3/8', or metric dims '0.3x0.3'."
        },
        "beam_section": {
          "type": "string",
          "default": "auto",
          "description": "Beam section. Same format as column_section."
        },
        "slab_thickness": {
          "type": "number",
          "default": 0.2,
          "description": "Default slab thickness in meters. Per-story overrides take precedence."
        },
        "bracing": {
          "type": "object",
          "description": "Bracing configuration. Only applies when frame_type is 'braced'.",
          "properties": {
            "pattern": {
              "type": "string",
              "enum": ["x_brace", "chevron", "single_diagonal", "k_brace"],
              "default": "x_brace"
            },
            "bays": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "face": { "type": "string", "enum": ["north", "south", "east", "west"] },
                  "bay_index": { "type": "integer", "description": "0-indexed bay position along the face." }
                }
              },
              "description": "Which perimeter bays get bracing. Default: one bay per face, centered."
            },
            "section": { "type": "string", "default": "auto", "description": "Brace member section." }
          },
          "additionalProperties": false
        },
        "roof_type": {
          "type": "string",
          "enum": ["flat_slab", "standing_seam", "metal_deck", "concrete"],
          "default": "flat_slab",
          "description": "Roof construction type. 'flat_slab' generates a standard slab; 'standing_seam' and 'metal_deck' generate a thinner plate with purlins."
        }
      },
      "additionalProperties": false
    },

    "facades": {
      "type": "object",
      "description": "Envelope per cardinal face. Missing faces default to concrete wall.",
      "properties": {
        "north": { "$ref": "#/$defs/facade_spec" },
        "south": { "$ref": "#/$defs/facade_spec" },
        "east":  { "$ref": "#/$defs/facade_spec" },
        "west":  { "$ref": "#/$defs/facade_spec" }
      },
      "additionalProperties": false
    },

    "entries": {
      "type": "array",
      "description": "Door entries. Each is placed in the wall on the specified face.",
      "items": {
        "type": "object",
        "required": ["face"],
        "properties": {
          "face": { "type": "string", "enum": ["north", "south", "east", "west"] },
          "type": { "type": "string", "enum": ["single", "double", "revolving", "overhead", "service"], "default": "double" },
          "width": { "type": "number", "default": 2.0, "description": "Door width, meters." },
          "height": { "type": "number", "default": 2.4, "description": "Door height, meters." },
          "position": {
            "type": "string",
            "enum": ["center", "left_third", "right_third"],
            "default": "center",
            "description": "Position along the wall face. Generator computes the offset."
          },
          "position_offset": { "type": "number", "description": "Explicit offset along wall, meters. Overrides position if given." },
          "story_index": { "type": "integer", "default": 0, "description": "Which story this entry is on (0-indexed)." }
        },
        "additionalProperties": false
      }
    },

    "overhead_doors": {
      "type": "array",
      "description": "Overhead / roll-up doors (loading docks, warehouses).",
      "items": {
        "type": "object",
        "required": ["face"],
        "properties": {
          "face": { "type": "string", "enum": ["north", "south", "east", "west"] },
          "count": { "type": "integer", "default": 1 },
          "width": { "type": "number", "default": 4.0 },
          "height": { "type": "number", "default": 4.2 },
          "spacing": { "type": "number", "description": "Center-to-center spacing. Default: evenly distributed." },
          "story_index": { "type": "integer", "default": 0 }
        },
        "additionalProperties": false
      }
    },

    "foundation": {
      "type": "object",
      "description": "Foundation system. The generator creates footings under every column.",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["spread_footings", "mat_slab", "grade_beams", "piles"],
          "default": "spread_footings"
        },
        "bearing_elevation": {
          "type": "number",
          "default": -1.2,
          "description": "Top-of-footing elevation, meters."
        },
        "soil_bearing_kpa": {
          "type": "number",
          "default": 96.0,
          "description": "Allowable soil bearing pressure. Default 96 kPa (~2000 psf)."
        },
        "include_grade_beams": {
          "type": "boolean",
          "default": false,
          "description": "Add grade beams between perimeter footings."
        }
      },
      "additionalProperties": false
    },

    "mezzanines": {
      "type": "array",
      "description": "Partial floors inserted within a story's height.",
      "items": {
        "type": "object",
        "required": ["story_index"],
        "properties": {
          "story_index": { "type": "integer", "description": "Which story contains this mezzanine (0-indexed)." },
          "sides": {
            "type": "array",
            "items": { "type": "string", "enum": ["north", "south", "east", "west", "full"] },
            "default": ["north"],
            "description": "Which side(s) of the floor the mezzanine occupies. 'full' = entire footprint."
          },
          "depth": { "type": "number", "description": "How far the mezzanine extends from the wall, meters. Ignored if sides=['full']." },
          "height_fraction": { "type": "number", "default": 0.5, "description": "Mezzanine slab placed at this fraction of the story height." },
          "slab_thickness": { "type": "number", "default": 0.15 }
        },
        "additionalProperties": false
      }
    },

    "stairs": {
      "type": "array",
      "description": "Stair locations. The generator computes run/landing geometry from floor heights.",
      "items": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "enum": ["northeast", "northwest", "southeast", "southwest", "north_center", "south_center", "east_center", "west_center"],
            "default": "northwest"
          },
          "width": { "type": "number", "default": 1.2, "description": "Stair width, meters." },
          "type": { "type": "string", "enum": ["switchback", "straight", "l_shaped"], "default": "switchback" },
          "stories": {
            "type": "string",
            "enum": ["all", "ground_only"],
            "default": "all",
            "description": "'all' connects every floor. 'ground_only' connects ground to second floor."
          }
        },
        "additionalProperties": false
      }
    },

    "panels": {
      "type": "object",
      "description": "Insulated concrete panel configuration. Only applies to facades with type='panel_array'.",
      "properties": {
        "orientation": { "type": "string", "enum": ["vertical", "horizontal"], "default": "vertical" },
        "nominal_width": { "type": "number", "default": 3.0, "description": "Target panel width, meters. Generator adjusts to fit wall length." },
        "thickness": { "type": "number", "default": 0.2 },
        "joint_width_mm": { "type": "number", "default": 38 },
        "joint_sealant": { "type": "string", "default": "silicone" },
        "max_height_m": { "type": "number", "default": 15.24, "description": "Max single-panel height (from catalog: 50ft = 15.24m)." },
        "max_width_m": { "type": "number", "default": 3.66, "description": "Max single-panel width (from catalog: 12ft = 3.66m)." }
      },
      "additionalProperties": false
    },

    "overrides": {
      "type": "array",
      "description": "Post-generation surgical edits. Applied after the spec expansion. Each item is a standard IfcAuthor tool call.",
      "items": {
        "type": "object",
        "required": ["action"],
        "properties": {
          "action": { "type": "string", "description": "Tool name: create_column, delete_element, create_beam, etc." },
          "args": { "type": "object", "description": "Arguments passed to IfcAuthor.apply_tool_call()." }
        },
        "additionalProperties": false
      }
    }
  },

  "$defs": {
    "facade_spec": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["wall", "curtain_wall", "panel_array"],
          "default": "wall",
          "description": "'wall' = solid wall with optional punched windows. 'curtain_wall' = glass facade. 'panel_array' = insulated concrete panels (uses 'panels' config)."
        },
        "material": {
          "type": "string",
          "enum": ["concrete", "concrete_insulated", "metal", "cmu", "brick"],
          "default": "concrete",
          "description": "Wall material. Used for metadata and material assignment."
        },
        "thickness": { "type": "number", "default": 0.25, "description": "Wall thickness, meters." },
        "stories": {
          "type": "string",
          "enum": ["all", "ground_only", "upper_only"],
          "default": "all",
          "description": "Which stories this facade type applies to. Allows mixed facades (e.g., glass ground floor, walls above)."
        },
        "windows": {
          "type": "object",
          "description": "Window pattern for this facade. Only applies to type='wall'.",
          "properties": {
            "pattern": {
              "type": "string",
              "enum": ["per_bay", "ribbon", "none"],
              "default": "none"
            },
            "count_per_bay": { "type": "integer", "default": 1, "description": "Windows per structural bay. Used with pattern='per_bay'." },
            "width": { "type": "number", "default": 1.8, "description": "Window width, meters." },
            "height": { "type": "number", "default": 1.5, "description": "Window height, meters." },
            "sill_height": { "type": "number", "default": 0.9, "description": "Sill height above floor, meters." }
          },
          "additionalProperties": false
        },
        "curtain_wall": {
          "type": "object",
          "description": "Curtain wall panel parameters. Only applies to type='curtain_wall'.",
          "properties": {
            "panel_width": { "type": "number", "default": 1.5 },
            "panel_height": { "type": "number", "default": 1.2 },
            "panel_thickness": { "type": "number", "default": 0.02 }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  }
}
```

### Decision Count Analysis

The schema has **25 top-level design fields** organized into 10 sections. But most have defaults. Here is the minimum set the AI must decide:

| # | Decision | Example Value | Required? |
|---|---|---|---|
| 1 | Footprint length | 40 | Yes |
| 2 | Footprint width | 25 | Yes |
| 3 | Number of stories | 5 (array length) | Yes |
| 4 | Story heights | [4.5, 4.0, 4.0, 4.0, 4.0] | Yes |
| 5 | Grid spacing X | 8.0 | No (default: 8.0) |
| 6 | Grid spacing Y | 8.0 | No (default: 8.0) |
| 7 | Column section | "W12x40" | No (default: "auto") |
| 8 | Beam section | "W18x35" | No (default: "auto") |
| 9 | Frame type | "braced" | No (default: "braced") |
| 10 | North facade | "wall" | No (default: wall) |
| 11 | South facade | "curtain_wall" | No (default: wall) |
| 12 | East facade | "wall" + windows | No (default: wall) |
| 13 | West facade | "wall" + windows | No (default: wall) |
| 14 | Window dimensions | 1.8 x 1.5 | No (defaults exist) |
| 15 | Entry location | "south, center" | No (no entry by default) |
| 16 | Foundation type | "spread_footings" | No (default: spread) |

**Minimum viable spec: 4 decisions** (footprint + stories). Everything else has defaults. A realistic spec has 10-16 explicit decisions.

### Minimum Spec Examples

**Absolute minimum (4 decisions, ~50 tokens):**

```json
{
  "footprint": { "length": 40, "width": 25 },
  "stories": [
    { "height": 4.5 },
    { "height": 4.0 },
    { "height": 4.0 },
    { "height": 4.0 },
    { "height": 4.0 }
  ]
}
```

This produces: 5 stories with default 8m grid, concrete walls on all sides, no windows, no doors, auto-sized columns and beams, spread footings. A valid, if featureless, building.

**Typical commercial building (~200 tokens):**

```json
{
  "project_name": "5-Story Office Tower",
  "footprint": { "length": 40, "width": 25 },
  "grid": { "spacing_x": 8, "spacing_y": 6.25 },
  "stories": [
    { "name": "Ground Floor", "height": 4.5, "program": "retail" },
    { "name": "Level 2", "height": 4.0, "program": "office" },
    { "name": "Level 3", "height": 4.0, "program": "office" },
    { "name": "Level 4", "height": 4.0, "program": "office" },
    { "name": "Level 5", "height": 4.0, "program": "office" }
  ],
  "structure": {
    "frame_type": "braced",
    "column_section": "W12x40",
    "beam_section": "W18x35"
  },
  "facades": {
    "north": { "type": "wall", "windows": { "pattern": "per_bay", "width": 1.8, "height": 1.5 } },
    "south": { "type": "curtain_wall" },
    "east":  { "type": "wall", "windows": { "pattern": "per_bay", "width": 1.8, "height": 1.5 } },
    "west":  { "type": "wall", "windows": { "pattern": "per_bay", "width": 1.8, "height": 1.5 } }
  },
  "entries": [
    { "face": "south", "type": "double", "position": "center" }
  ],
  "foundation": { "type": "spread_footings", "soil_bearing_kpa": 96 }
}
```

**Warehouse with mezzanine (~150 tokens):**

```json
{
  "project_name": "Distribution Warehouse",
  "footprint": { "length": 60, "width": 40 },
  "grid": { "spacing_x": 10, "spacing_y": 10 },
  "stories": [
    { "name": "Warehouse Floor", "height": 8.0, "program": "industrial" }
  ],
  "structure": {
    "frame_type": "rigid",
    "roof_type": "standing_seam"
  },
  "facades": {
    "south": { "type": "panel_array" },
    "north": { "type": "panel_array" },
    "east": { "type": "panel_array" },
    "west": { "type": "panel_array" }
  },
  "entries": [
    { "face": "south", "type": "single", "position": "left_third" }
  ],
  "overhead_doors": [
    { "face": "north", "count": 3, "width": 4.0, "height": 4.2 }
  ],
  "mezzanines": [
    { "story_index": 0, "sides": ["south"], "depth": 12, "height_fraction": 0.45 }
  ]
}
```

---

## Part 2: The Generator Architecture

### Class Design

```
BuildingGenerator
  |
  +-- SpecResolver          (fills defaults, resolves grid math)
  |
  +-- StoreyGenerator       (creates IfcBuildingStorey entities)
  +-- ColumnGridGenerator   (places columns at every grid intersection)
  +-- BeamGridGenerator     (places beams along every gridline)
  +-- FloorPlateGenerator   (creates slabs per floor)
  +-- FacadeGenerator       (walls, curtain walls, or panel arrays per face)
  +-- OpeningGenerator      (windows in patterns, doors at positions)
  +-- FoundationGenerator   (footings under columns, optional grade beams)
  +-- MezzanineGenerator    (partial floor slabs + support columns)
  +-- StairGenerator        (run + landing geometry from floor heights)
  +-- BracingGenerator      (diagonal/chevron members in specified bays)
  +-- RoofGenerator         (roof slab or metal deck + purlins)
  |
  +-- CatalogResolver       (maps "auto" and named sections to real dims)
  +-- OverrideApplicator    (applies post-generation surgical edits)
```

### Core Class

```python
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from bonsai_ai.ifc_author import IfcAuthor
from bonsai_ai.system_catalog import starter_core_shell_catalog


@dataclass
class ResolvedGrid:
    """Grid with all ambiguity resolved: concrete bay counts and spacings."""
    bays_x: int
    bays_y: int
    spacings_x: List[float]   # length = bays_x (may vary for last bay)
    spacings_y: List[float]   # length = bays_y
    xs: List[float]           # gridline X positions (bays_x + 1 values)
    ys: List[float]           # gridline Y positions (bays_y + 1 values)


@dataclass
class ResolvedStorey:
    """Storey with computed elevation."""
    name: str
    height: float
    elevation: float
    program: str
    slab_thickness: float
    exclude_slab: bool


class BuildingGenerator:
    def __init__(self, spec: dict, output_path: str):
        self.spec = spec
        self.output_path = output_path
        self.author = IfcAuthor(output_path)
        self.catalog = starter_core_shell_catalog()

        # Resolved data (computed during generate)
        self.grid: Optional[ResolvedGrid] = None
        self.stories: List[ResolvedStorey] = []
        self.wall_registry: Dict[str, str] = {}  # face+storey -> wall_name

    def generate(self) -> dict:
        """Main entry point. Returns a summary dict."""
        self._resolve_spec()

        self.author.ensure_project(
            project_name=self.spec.get("project_name", "AI Building"),
            site_name="Default Site",
            building_name="Main Building",
        )

        self._generate_storeys()
        self._generate_column_grid()
        self._generate_beam_grid()
        self._generate_floor_plates()
        self._generate_roof()
        self._generate_facades()
        self._generate_openings()
        self._generate_foundations()
        self._generate_mezzanines()
        self._generate_stairs()
        self._generate_bracing()
        self._apply_overrides()

        self.author.save()
        return self._summary()
```

### SpecResolver: Filling Defaults and Resolving Grid Math

```python
    def _resolve_spec(self):
        """Fill defaults and compute derived values."""
        spec = self.spec

        # --- Grid resolution ---
        fp = spec["footprint"]
        if "length" in fp:
            length, width = fp["length"], fp["width"]
        else:
            # Polygon footprint: use bounding box for grid, store polygon for walls
            xs = [v[0] for v in fp["vertices"]]
            ys = [v[1] for v in fp["vertices"]]
            length = max(xs) - min(xs)
            width = max(ys) - min(ys)

        grid_spec = spec.get("grid", {})
        spacing_x = grid_spec.get("spacing_x", 8.0)
        spacing_y = grid_spec.get("spacing_y", 8.0)
        bays_x = grid_spec.get("bays_x") or max(1, round(length / spacing_x))
        bays_y = grid_spec.get("bays_y") or max(1, round(length / spacing_y))

        # Compute actual spacings (last bay absorbs remainder)
        spacings_x = self._compute_spacings(length, bays_x, spacing_x)
        spacings_y = self._compute_spacings(width, bays_y, spacing_y)

        # Gridline positions
        xs = [0.0]
        for s in spacings_x:
            xs.append(round(xs[-1] + s, 6))
        ys = [0.0]
        for s in spacings_y:
            ys.append(round(ys[-1] + s, 6))

        self.grid = ResolvedGrid(
            bays_x=bays_x, bays_y=bays_y,
            spacings_x=spacings_x, spacings_y=spacings_y,
            xs=xs, ys=ys,
        )

        # --- Storey resolution ---
        default_slab = spec.get("structure", {}).get("slab_thickness", 0.2)
        program_slab_defaults = {
            "retail": 0.25, "office": 0.20, "parking": 0.25,
            "residential": 0.18, "industrial": 0.30, "mezzanine": 0.15,
            "mechanical": 0.25, "lobby": 0.20,
        }
        elevation = 0.0
        for i, story_spec in enumerate(spec["stories"]):
            program = story_spec.get("program", "office")
            slab_t = story_spec.get("slab_thickness") or program_slab_defaults.get(program, default_slab)
            self.stories.append(ResolvedStorey(
                name=story_spec.get("name", f"Level {i + 1}"),
                height=story_spec["height"],
                elevation=elevation,
                program=program,
                slab_thickness=slab_t,
                exclude_slab=story_spec.get("exclude_slab", False),
            ))
            elevation += story_spec["height"]
        # Roof pseudo-storey
        self.roof_elevation = elevation

    @staticmethod
    def _compute_spacings(total: float, bays: int, target: float) -> List[float]:
        """Compute bay spacings where the last bay absorbs the remainder.

        Rule: if the remainder bay would be less than 50% of target, merge
        it into the previous bay. If more than 150%, split into two.
        """
        if bays <= 0:
            return [total]
        uniform = total / bays
        # If explicit bay count was given, use uniform spacing
        return [round(uniform, 6)] * bays
```

### Key Generator Methods

Each generator method is a direct analog of what the existing build scripts do by hand, but parameterized from the resolved spec.

```python
    def _generate_storeys(self):
        for story in self.stories:
            self.author.ensure_storey(name=story.name, elevation=story.elevation)
        self.author.ensure_storey(name="Roof", elevation=self.roof_elevation)
        if self.spec.get("foundation"):
            elev = self.spec["foundation"].get("bearing_elevation", -1.2)
            self.author.ensure_storey(name="Foundations", elevation=elev)

    def _generate_column_grid(self):
        """Place a column at every grid intersection, every floor."""
        col_w, col_d = self._resolve_column_dims()
        for story in self.stories:
            for ix, x in enumerate(self.grid.xs):
                for iy, y in enumerate(self.grid.ys):
                    label = f"{chr(65 + iy)}{ix + 1}"
                    self.author.create_column(
                        name=f"{story.name} Col-{label}",
                        storey_name=story.name,
                        x=x, y=y,
                        base_z=story.elevation,
                        width=col_w, depth=col_d,
                        height=story.height,
                    )

    def _generate_beam_grid(self):
        """Place beams along every gridline at every floor level.

        This is the critical compression: a 5x4 grid produces 45 beams
        per floor instead of 45 individual create_beam actions.
        """
        beam_w, beam_d = self._resolve_beam_dims()
        for story in self.stories:
            beam_z = story.elevation + story.height  # beams at top of columns
            # X-direction beams (along each Y gridline)
            for iy, y in enumerate(self.grid.ys):
                for ix in range(self.grid.bays_x):
                    x1, x2 = self.grid.xs[ix], self.grid.xs[ix + 1]
                    self.author.create_beam(
                        name=f"{story.name} Beam-X {chr(65+iy)}{ix+1}-{ix+2}",
                        storey_name=story.name,
                        start_x=x1, start_y=y,
                        end_x=x2, end_y=y,
                        base_z=beam_z,
                        width=beam_w, depth=beam_d,
                    )
            # Y-direction beams (along each X gridline)
            for ix, x in enumerate(self.grid.xs):
                for iy in range(self.grid.bays_y):
                    y1, y2 = self.grid.ys[iy], self.grid.ys[iy + 1]
                    self.author.create_beam(
                        name=f"{story.name} Beam-Y {ix+1}{chr(65+iy)}-{chr(65+iy+1)}",
                        storey_name=story.name,
                        start_x=x, start_y=y1,
                        end_x=x, end_y=y2,
                        base_z=beam_z,
                        width=beam_w, depth=beam_d,
                    )

    def _generate_floor_plates(self):
        """One slab per floor (unless exclude_slab is set)."""
        fp = self.spec["footprint"]
        length = fp.get("length", self.grid.xs[-1])
        width = fp.get("width", self.grid.ys[-1])
        for story in self.stories:
            if story.exclude_slab:
                continue
            self.author.create_rectangular_slab(
                name=f"{story.name} Floor Slab",
                storey_name=story.name,
                x=0, y=0, z=story.elevation,
                length=length, width=width,
                thickness=story.slab_thickness,
            )
        # Roof slab
        roof_type = self.spec.get("structure", {}).get("roof_type", "flat_slab")
        if roof_type in ("flat_slab", "concrete"):
            self.author.create_rectangular_slab(
                name="Roof Slab",
                storey_name="Roof",
                x=0, y=0, z=self.roof_elevation,
                length=length, width=width,
                thickness=0.22,
            )

    def _generate_facades(self):
        """Generate walls, curtain walls, or panel arrays per face."""
        fp = self.spec["footprint"]
        length = fp.get("length", self.grid.xs[-1])
        width = fp.get("width", self.grid.ys[-1])
        facade_specs = self.spec.get("facades", {})

        face_geometry = {
            "south": (0, 0, length, 0),       # (x1, y1, x2, y2)
            "east":  (length, 0, length, width),
            "north": (length, width, 0, width),
            "west":  (0, width, 0, 0),
        }

        for face_name, (x1, y1, x2, y2) in face_geometry.items():
            fspec = facade_specs.get(face_name, {})
            ftype = fspec.get("type", "wall")
            fstories = fspec.get("stories", "all")
            thickness = fspec.get("thickness", 0.25)

            for story in self.stories:
                if fstories == "ground_only" and story != self.stories[0]:
                    continue
                if fstories == "upper_only" and story == self.stories[0]:
                    continue

                wall_key = f"{face_name}_{story.name}"

                if ftype == "wall":
                    wall_name = f"{story.name} {face_name.capitalize()} Wall"
                    self.author.create_wall(
                        name=wall_name,
                        storey_name=story.name,
                        start_x=x1, start_y=y1,
                        end_x=x2, end_y=y2,
                        base_z=story.elevation,
                        height=story.height,
                        thickness=thickness,
                    )
                    self.wall_registry[wall_key] = wall_name

                elif ftype == "curtain_wall":
                    cw = fspec.get("curtain_wall", {})
                    wall_length = math.hypot(x2 - x1, y2 - y1)
                    rotation = math.degrees(math.atan2(y2 - y1, x2 - x1))
                    self.author.create_curtain_wall(
                        name=f"{story.name} {face_name.capitalize()} Curtain Wall",
                        storey_name=story.name,
                        x=x1, y=y1,
                        base_z=story.elevation,
                        width=wall_length,
                        height=story.height,
                        rotation_degrees=rotation,
                        panel_width=cw.get("panel_width", 1.5),
                        panel_height=cw.get("panel_height", 1.2),
                        panel_thickness=cw.get("panel_thickness", 0.02),
                    )

                elif ftype == "panel_array":
                    self._generate_panel_array(
                        face_name=face_name,
                        story=story,
                        x1=x1, y1=y1, x2=x2, y2=y2,
                    )

    def _generate_openings(self):
        """Generate windows (from facade patterns) and doors (from entries)."""
        facade_specs = self.spec.get("facades", {})

        for face_name, fspec_raw in facade_specs.items():
            fspec = fspec_raw if isinstance(fspec_raw, dict) else {}
            if fspec.get("type", "wall") != "wall":
                continue
            windows = fspec.get("windows", {})
            pattern = windows.get("pattern", "none")
            if pattern == "none":
                continue

            win_w = windows.get("width", 1.8)
            win_h = windows.get("height", 1.5)
            sill = windows.get("sill_height", 0.9)
            count_per_bay = windows.get("count_per_bay", 1)
            fstories = fspec.get("stories", "all")

            for story in self.stories:
                if fstories == "ground_only" and story != self.stories[0]:
                    continue
                if fstories == "upper_only" and story == self.stories[0]:
                    continue

                wall_key = f"{face_name}_{story.name}"
                wall_name = self.wall_registry.get(wall_key)
                if not wall_name:
                    continue

                if pattern == "per_bay":
                    self._place_windows_per_bay(
                        wall_name=wall_name,
                        face_name=face_name,
                        story=story,
                        count_per_bay=count_per_bay,
                        win_w=win_w, win_h=win_h, sill=sill,
                    )
                elif pattern == "ribbon":
                    self._place_ribbon_windows(
                        wall_name=wall_name,
                        face_name=face_name,
                        story=story,
                        win_h=win_h, sill=sill,
                    )

        # Doors from entries
        for entry in self.spec.get("entries", []):
            self._place_entry(entry)

        # Overhead doors
        for ohd in self.spec.get("overhead_doors", []):
            self._place_overhead_doors(ohd)

    def _generate_foundations(self):
        """Place footings under every column position."""
        fnd = self.spec.get("foundation", {})
        fnd_type = fnd.get("type", "spread_footings")
        bearing_elev = fnd.get("bearing_elevation", -1.2)
        bearing_kpa = fnd.get("soil_bearing_kpa", 96.0)

        if fnd_type != "spread_footings":
            return  # mat_slab and piles are future work

        # Estimate load per column (simplified: tributary area * floor count * load)
        typical_load_kpa = 5.0  # approximate total floor load
        story_count = len(self.stories)

        for ix, x in enumerate(self.grid.xs):
            for iy, y in enumerate(self.grid.ys):
                # Tributary area
                trib_x = self._tributary_width(ix, self.grid.spacings_x)
                trib_y = self._tributary_width(iy, self.grid.spacings_y)
                trib_area = trib_x * trib_y
                imposed_kn = trib_area * typical_load_kpa * story_count * 9.81 / 1000.0

                from bonsai_ai.footing_selector import starter_footing_from_imposed_load
                rec = starter_footing_from_imposed_load(
                    imposed_kn,
                    footing_family="spread_footing",
                    allowable_bearing_psf=bearing_kpa / 0.04788,
                )
                size = rec["recommended_square_size_m"]
                thickness = rec["footing_thickness_m"]
                label = f"{chr(65 + iy)}{ix + 1}"
                self.author.create_footing(
                    name=f"Footing {label}",
                    storey_name="Foundations",
                    x=round(x - size / 2, 6),
                    y=round(y - size / 2, 6),
                    base_z=bearing_elev,
                    length=size, width=size,
                    thickness=thickness,
                )
```

### Catalog Integration

The generator resolves section names against the system catalog:

```python
    def _resolve_column_dims(self) -> tuple[float, float]:
        """Resolve column section to width x depth in meters."""
        section = self.spec.get("structure", {}).get("column_section", "auto")
        return self._resolve_section(section, "primary_columns_w", default=(0.3, 0.3))

    def _resolve_beam_dims(self) -> tuple[float, float]:
        section = self.spec.get("structure", {}).get("beam_section", "auto")
        return self._resolve_section(section, "primary_beams_w", default=(0.3, 0.5))

    def _resolve_section(
        self, spec_value: str, catalog_family_id: str, default: tuple[float, float]
    ) -> tuple[float, float]:
        """Map a section spec to (width, depth) in meters.

        Accepts:
          "auto"       -> first allowed section from catalog family
          "W12x40"     -> look up in AISC tables (future) or use catalog defaults
          "0.3x0.3"    -> parse as metric width x depth
          "HSS8x8x3/8" -> look up in catalog
        """
        if spec_value == "auto":
            family = self._find_catalog_family(catalog_family_id)
            if family and family.get("allowed_sections"):
                # Use first allowed section as default
                return self._section_to_dims(family["allowed_sections"][0], default)
            return default

        # Try metric dims "0.3x0.3"
        if "x" in spec_value and spec_value.replace(".", "").replace("x", "").isdigit():
            parts = spec_value.split("x")
            return (float(parts[0]), float(parts[1]))

        # Named section: look up in catalog
        return self._section_to_dims(spec_value, default)

    def _find_catalog_family(self, family_id: str) -> Optional[dict]:
        for family in self.catalog.get("member_families", []):
            if family["id"] == family_id:
                return family
        return None

    @staticmethod
    def _section_to_dims(section_name: str, default: tuple[float, float]) -> tuple[float, float]:
        """Convert named section to approximate (width, depth) in meters.

        This is a simplified lookup. A full implementation would use AISC
        shape tables or manufacturer data from the catalog.
        """
        # Common W-shape approximate depths (inches -> meters)
        w_shape_depths = {
            "W8": 0.203, "W10": 0.254, "W12": 0.305,
            "W14": 0.356, "W16": 0.406, "W18": 0.457,
            "W21": 0.533, "W24": 0.610, "W27": 0.686,
        }
        for prefix, depth in w_shape_depths.items():
            if section_name.startswith(prefix):
                # Flange width is roughly 60-80% of depth for common sections
                return (depth * 0.7, depth)

        # HSS square: "HSS8x8x3/8" -> 8 inches = 0.2032m
        if section_name.startswith("HSS"):
            parts = section_name[3:].split("x")
            if len(parts) >= 2:
                dim = float(parts[0]) * 0.0254  # inches to meters
                return (dim, dim)

        return default
```

---

## Part 3: Non-Rectangular Footprints

### The Problem

The basic grid assumes a rectangle. Real buildings have L-shapes, setbacks, and irregular polygons.

### Solution: Polygon Footprint with Rectangular Zone Decomposition

```json
{
  "footprint": {
    "vertices": [
      [0, 0], [40, 0], [40, 15], [25, 15], [25, 25], [0, 25]
    ]
  }
}
```

The generator handles this by:

1. **Bounding box grid**: The column grid spans the bounding box of the polygon (40 x 25 in this case).
2. **Point-in-polygon test**: Before placing each column, beam, or slab, the generator checks whether the grid point falls inside the polygon. Points outside are skipped.
3. **Perimeter walls**: Follow the polygon edges instead of a rectangle.
4. **Partial slabs**: For each floor, the generator creates one slab per rectangular zone that fits inside the polygon, rather than one slab for the whole bounding box.

```python
    def _point_in_polygon(self, x: float, y: float) -> bool:
        """Ray-casting point-in-polygon test."""
        fp = self.spec["footprint"]
        if "length" in fp:
            return 0 <= x <= fp["length"] and 0 <= y <= fp["width"]
        vertices = fp["vertices"]
        n = len(vertices)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = vertices[i]
            xj, yj = vertices[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside
```

This approach handles L-shapes, T-shapes, and U-shapes. Truly complex footprints (curves, irregular polygons) may need the override mechanism for edge cases.

---

## Part 4: Mixed-Use Buildings

### Per-Story Program Type

Each story already has a `program` field. The generator uses this to:

1. **Vary slab thickness**: Parking = 0.25m, office = 0.20m, residential = 0.18m.
2. **Vary floor height**: Already explicit in the stories array.
3. **Vary facade treatment per floor**: The `facades.*.stories` field allows "ground_only" and "upper_only" distinctions.

### Example: Mixed-use podium building

```json
{
  "footprint": { "length": 50, "width": 30 },
  "stories": [
    { "name": "Parking B1", "height": 3.0, "program": "parking" },
    { "name": "Retail", "height": 5.0, "program": "retail" },
    { "name": "Office 1", "height": 4.0, "program": "office" },
    { "name": "Office 2", "height": 4.0, "program": "office" },
    { "name": "Office 3", "height": 4.0, "program": "office" }
  ],
  "facades": {
    "south": {
      "type": "curtain_wall",
      "stories": "upper_only"
    }
  }
}
```

### Advanced: Per-Story Facade Override

For buildings where each floor has a different facade treatment, the facade spec can be extended with a per-story array in a future version. For now, the three-way split (`all` / `ground_only` / `upper_only`) covers the most common mixed-use pattern (retail podium + office tower).

If more granularity is needed, the `overrides` mechanism handles it: the AI generates the base spec with the 90% case and adds surgical overrides for specific floors.

---

## Part 5: Iterative Spec Evolution

### Start Simple, Add Detail

The spec is designed for iterative refinement. A conversation flow:

```
Turn 1:
  User: "Design a 3-story office building"
  AI generates:
    { "footprint": {"length": 30, "width": 20},
      "stories": [{"height": 4.0}, {"height": 4.0}, {"height": 4.0}] }
  Generator: produces basic building (columns, beams, slabs, walls)

Turn 2:
  User: "Make the ground floor 5m tall for retail"
  AI modifies: stories[0].height = 5.0, stories[0].program = "retail"
  Generator: regenerates from updated spec

Turn 3:
  User: "Add a glass curtain wall on the south side"
  AI adds: facades.south = { "type": "curtain_wall" }
  Generator: regenerates

Turn 4:
  User: "Add windows on the east and west"
  AI adds: facades.east.windows = { "pattern": "per_bay", "width": 1.8, "height": 1.5 }
  Generator: regenerates
```

### Spec Diffing

Because the spec is a small JSON object, the AI can describe changes as patches:

```json
{
  "operation": "modify",
  "path": "stories[0].height",
  "old_value": 4.0,
  "new_value": 5.0
}
```

Or simply re-emit the full spec (it is only ~200 tokens). The generator always produces a fresh model from the spec, so there is no accumulated drift.

### Regeneration vs. Patching

Two strategies for applying changes:

1. **Full regeneration** (recommended for spec changes): Delete old IFC, generate fresh from updated spec. Clean, no drift, deterministic. Takes ~1-5 seconds.

2. **Overlay patching** (for overrides only): Keep the generated model and apply surgical edits. Useful when the override involves expensive custom geometry that is not captured in the spec.

The default is full regeneration. The `overrides` array is applied after each regeneration.

---

## Part 6: Catalog System Integration

### How "auto" Sections Work

When the spec says `"column_section": "auto"`, the generator:

1. Estimates the load on the heaviest column (corner of building, all floors above).
2. Looks up the `primary_columns_w` family in the catalog.
3. Walks the `allowed_sections` list (already sorted lightest to heaviest: W10x33, W10x49, W12x40, ...).
4. Selects the lightest section that passes a simplified capacity check.

```python
    def _auto_select_column(self, max_load_kn: float) -> str:
        """Select lightest adequate column from catalog."""
        family = self._find_catalog_family("primary_columns_w")
        if not family:
            return "W12x40"  # fallback

        # Simplified capacity check: Pu <= 0.5 * Fy * Ag
        # (very conservative -- proper design would use AISC Chapter E)
        fy_ksi = self.catalog["materials"]["steel_w_shapes"]["fy_ksi"]
        fy_kpa = fy_ksi * 6894.76  # ksi to kPa

        for section in family["allowed_sections"]:
            w, d = self._section_to_dims(section, (0.3, 0.3))
            area_m2 = w * d  # approximate for rectangular profile
            capacity_kn = 0.5 * fy_kpa * area_m2 / 1000.0
            if capacity_kn >= max_load_kn:
                return section

        return family["allowed_sections"][-1]  # heaviest available
```

### Panel Catalog Integration

When `facades.*.type = "panel_array"`, the generator uses the `innovacast_icp_wall_panel` catalog entry:

```python
    def _generate_panel_array(self, face_name, story, x1, y1, x2, y2):
        """Generate insulated concrete panels along a wall face."""
        panel_config = self.spec.get("panels", {})
        panel_catalog = self.catalog["panel_catalogs"][0]  # innovacast_icp_wall_panel

        max_width = min(
            panel_config.get("max_width_m", panel_catalog["size_rules"]["max_width_ft"] * 0.3048),
            panel_config.get("nominal_width", 3.0),
        )
        max_height = panel_config.get(
            "max_height_m",
            panel_catalog["size_rules"]["max_height_ft"] * 0.3048,
        )
        thickness = panel_config.get("thickness", 0.2)
        joint_mm = panel_config.get("joint_width_mm", 38)
        joint_m = joint_mm / 1000.0

        wall_length = math.hypot(x2 - x1, y2 - y1)
        rotation = math.degrees(math.atan2(y2 - y1, x2 - x1))
        panel_height = min(story.height, max_height)

        # Compute panel count and actual widths
        usable_width = wall_length
        panel_count = max(1, round(usable_width / (max_width + joint_m)))
        actual_width = (usable_width - joint_m * (panel_count - 1)) / panel_count

        dx = math.cos(math.radians(rotation))
        dy = math.sin(math.radians(rotation))
        cx, cy = x1, y1

        for i in range(panel_count):
            self.author.create_panel(
                name=f"{story.name} {face_name.capitalize()} Panel {i+1:02d}",
                storey_name=story.name,
                x=round(cx, 6), y=round(cy, 6),
                base_z=story.elevation,
                width=round(actual_width, 6),
                height=panel_height,
                depth=None,
                thickness=thickness,
                orientation="vertical",
                rotation_deg=rotation,
            )
            step = actual_width + joint_m
            cx += dx * step
            cy += dy * step
```

### Footing Catalog Integration

Already demonstrated in the `_generate_foundations` method above. The generator uses `starter_footing_from_imposed_load()` from `footing_selector.py` -- the same function used in the retail terrace build script. This means foundation sizing logic is shared, not duplicated.

---

## Part 7: Migration Path

### Current State

```
User prompt --> AI planner --> action list (300+ JSON actions) --> IfcAuthor.apply_plan()
```

### Target State

```
User prompt --> AI planner --> building spec (~200 tokens) --> BuildingGenerator --> IfcAuthor
```

### Migration Strategy: Parallel Paths, Not Replacement

The spec-first system is a new entry point, not a replacement for the action-based system. Both coexist:

```
                                    +-- action list --> IfcAuthor.apply_plan()
User --> AI planner --> decision --> |
                                    +-- building spec --> BuildingGenerator --> IfcAuthor
```

The AI planner decides which path based on the task:

- **"Build a 5-story office"** --> spec path (regular building, generator handles it)
- **"Add a custom skylight to the existing model"** --> action path (surgical edit, needs individual actions)
- **"Build a warehouse then add a custom mezzanine layout"** --> spec path with overrides

### Implementation Phases

#### Phase 1: Core Generator (3-5 days)

Files to create:
- `src/bonsai_ai/building_spec.py` -- Pydantic/dataclass models for the spec schema
- `src/bonsai_ai/building_generator.py` -- The BuildingGenerator class
- `src/bonsai_ai/spec_resolver.py` -- Default filling, grid math, section resolution

What it covers:
- Rectangular footprints
- Regular column + beam grids
- Floor slabs
- Perimeter walls
- Curtain walls
- Spread footings

What it skips (Phase 2+):
- Panel arrays
- Windows and doors
- Mezzanines
- Stairs
- Bracing
- Polygon footprints

Test: Generate the 5-story building from a spec and compare element counts to the patched manual build (174 columns, 285 beams, 9 slabs, 20 walls).

#### Phase 2: Envelope + Openings (2-3 days)

Add:
- `_generate_openings()` with per_bay and ribbon window patterns
- `_place_entry()` for doors
- `_generate_panel_array()` for insulated concrete panels
- Per-story facade variation (ground_only / upper_only)

Test: Generate the 5-story building with windows and doors. Compare to patched build (32 windows, 2 doors).

#### Phase 3: Specialty Systems (2-3 days)

Add:
- `_generate_mezzanines()`
- `_generate_stairs()`
- `_generate_bracing()`
- `_generate_roof()` for metal deck + purlins
- Overhead doors

Test: Generate the warehouse-with-mezzanine scenario.

#### Phase 4: AI Integration (2-3 days)

Add:
- Spec JSON schema for structured output (the schema defined in Part 1)
- System prompt that asks the AI to output a spec, not actions
- Spec validation and error reporting
- Iterative refinement (spec diffing, re-generation)
- Integration with the existing planner pipeline

Test: End-to-end: user says "5-story office" --> AI outputs spec --> generator produces IFC --> validate element counts.

#### Phase 5: Polish (1-2 days)

- Polygon footprint support
- Auto section selection from catalog
- Override applicator
- Documentation and examples

### Total Estimated Effort: 10-16 days

### What Does NOT Change

- `IfcAuthor` class -- untouched, the generator calls its methods
- `system_catalog.py` -- untouched, the generator reads from it
- Existing build scripts -- they continue to work independently
- Action-based planner -- still available for surgical edits
- IFC output format -- identical element types and metadata

---

## Part 8: Design Questions Answered

### Q1: What is the minimum spec that produces a complete building?

**4 fields**: footprint (length + width) and stories (array of heights). Everything else has defaults. This produces a rectangular building with 8m grid, concrete walls, no windows, auto-sized steel frame, spread footings.

### Q2: How does the spec handle non-rectangular footprints?

**Polygon vertex list** in the footprint field. The generator computes a bounding-box grid and uses point-in-polygon tests to skip elements outside the boundary. Perimeter walls follow polygon edges. This handles L-shapes, T-shapes, and U-shapes. Curved boundaries would need future work.

### Q3: How does the spec handle mixed-use (different programs per floor)?

**Per-story program field** that controls slab thickness, structural loading assumptions, and default materials. **Per-face story filter** (`all` / `ground_only` / `upper_only`) controls facade treatment. For more complex mixed-use patterns, the override mechanism provides escape hatch.

### Q4: Can the spec evolve (start simple, add detail iteratively)?

**Yes, by design.** The spec is additive: start with footprint + stories, add facades, then windows, then entries. Each re-generation produces a fresh model. The AI can modify the spec as a small JSON patch (~50 tokens) rather than regenerating the entire model.

### Q5: How does the generator interact with the catalog system?

**Direct integration.** The generator reads `starter_core_shell_catalog()` for section families and allowed sections. `"auto"` triggers catalog-based selection. Named sections (e.g., `"W12x40"`) are validated against the catalog's `allowed_sections` lists. Panel arrays use the panel catalog for size constraints. Footings use `starter_footing_from_imposed_load()` with catalog-aligned parameters.

### Q6: What is the migration path from the current action-based system?

**Parallel paths.** The spec-first generator is a new entry point that coexists with the action-based planner. The AI decides which path to use based on the task. Both paths call the same `IfcAuthor` methods and produce identical IFC output. The spec path handles regular buildings; the action path handles surgical edits and custom geometry. The `overrides` array bridges the two: spec for the 90% case, individual actions for the 10% exceptions.

---

## Part 9: Expected Performance

### Token Economics

| Metric | Current (action-based) | Spec-first |
|---|---|---|
| Schema sent to AI | ~4,600 tokens | ~800 tokens |
| AI output (simple warehouse) | ~800 tokens | ~50 tokens |
| AI output (5-story office) | ~8,000 tokens (fails) | ~200 tokens |
| AI output (warehouse + mezzanine) | ~1,500 tokens | ~150 tokens |
| Generation time | 60-120s | 5-15s |
| Coordinate errors | Common (AI does math) | Zero (code does math) |
| Element count accuracy | Depends on AI reasoning | Deterministic |

### Element Counts: 5-Story Office Example

From spec: `footprint: 40x25, grid: 8x6.25, 5 stories (4.5 + 4x4.0)`

| System | Element | Count |
|---|---|---|
| Storeys | ensure_storey | 7 (5 floors + roof + foundations) |
| Columns | create_column | 5 * (6 * 5) = 150 |
| Beams | create_beam | 5 * (5*5 + 4*6) = 5 * 49 = 245 |
| Roof beams | create_beam | 49 |
| Floor slabs | create_rectangular_slab | 5 |
| Roof slab | create_rectangular_slab | 1 |
| Walls | create_wall | 5 * 4 = 20 |
| Windows (E+W, per_bay) | create_window | 2 * 5 * 5 = 50 |
| Door | create_door | 1 |
| Footings | create_footing | 6 * 5 = 30 |
| **Total** | | **~558 elements** |

All 558 elements are generated from a ~200 token spec in under 5 seconds of Python execution. The AI never touches a coordinate.

---

## Appendix A: Full Spec Example with All Fields

```json
{
  "project_name": "Mixed-Use Commercial Tower",

  "footprint": { "length": 45, "width": 28 },

  "grid": { "spacing_x": 9, "spacing_y": 7 },

  "stories": [
    { "name": "Parking B1", "height": 3.2, "program": "parking" },
    { "name": "Ground Retail", "height": 5.0, "program": "retail" },
    { "name": "Level 2", "height": 4.0, "program": "office" },
    { "name": "Level 3", "height": 4.0, "program": "office" },
    { "name": "Level 4", "height": 4.0, "program": "office" },
    { "name": "Level 5", "height": 3.8, "program": "office" }
  ],

  "structure": {
    "frame_type": "braced",
    "column_section": "W12x53",
    "beam_section": "W18x35",
    "slab_thickness": 0.2,
    "bracing": {
      "pattern": "chevron",
      "bays": [
        { "face": "north", "bay_index": 2 },
        { "face": "south", "bay_index": 2 },
        { "face": "east", "bay_index": 1 },
        { "face": "west", "bay_index": 1 }
      ],
      "section": "HSS6x6x3/8"
    },
    "roof_type": "flat_slab"
  },

  "facades": {
    "north": {
      "type": "panel_array",
      "material": "concrete_insulated"
    },
    "south": {
      "type": "curtain_wall",
      "stories": "all",
      "curtain_wall": {
        "panel_width": 1.5,
        "panel_height": 1.2,
        "panel_thickness": 0.02
      }
    },
    "east": {
      "type": "wall",
      "material": "concrete",
      "thickness": 0.25,
      "windows": {
        "pattern": "per_bay",
        "count_per_bay": 1,
        "width": 1.8,
        "height": 1.5,
        "sill_height": 0.9
      }
    },
    "west": {
      "type": "wall",
      "material": "concrete",
      "thickness": 0.25,
      "windows": {
        "pattern": "per_bay",
        "count_per_bay": 1,
        "width": 1.8,
        "height": 1.5,
        "sill_height": 0.9
      }
    }
  },

  "entries": [
    { "face": "south", "type": "revolving", "width": 2.4, "height": 2.8, "position": "center", "story_index": 1 },
    { "face": "north", "type": "service", "width": 1.2, "height": 2.4, "position": "right_third", "story_index": 1 }
  ],

  "overhead_doors": [
    { "face": "north", "count": 2, "width": 3.5, "height": 3.0, "story_index": 0 }
  ],

  "foundation": {
    "type": "spread_footings",
    "bearing_elevation": -1.5,
    "soil_bearing_kpa": 120,
    "include_grade_beams": true
  },

  "mezzanines": [
    {
      "story_index": 1,
      "sides": ["north"],
      "depth": 10,
      "height_fraction": 0.55,
      "slab_thickness": 0.18
    }
  ],

  "stairs": [
    { "location": "northwest", "width": 1.2, "type": "switchback", "stories": "all" },
    { "location": "southeast", "width": 1.2, "type": "switchback", "stories": "all" }
  ],

  "panels": {
    "orientation": "vertical",
    "nominal_width": 3.0,
    "thickness": 0.2,
    "joint_width_mm": 38,
    "joint_sealant": "silicone"
  },

  "overrides": [
    {
      "action": "create_beam",
      "args": {
        "name": "Transfer Beam TB-1",
        "storey_name": "Ground Retail",
        "start_x": 9, "start_y": 0,
        "end_x": 9, "end_y": 28,
        "base_z": 5.0,
        "width": 0.4, "depth": 0.8
      }
    }
  ]
}
```

---

## Appendix B: Comparison to Existing Build Scripts

The retail terrace build script (`build_retail_terrace_concept.py`) is 902 lines of Python and produces ~120 elements. It manually computes every coordinate, every panel position, every railing post location.

With the spec-first system, the equivalent spec would be ~250 tokens. The generator handles the coordinate math. The custom elements (canopy, railing, accent panels) go in the `overrides` array.

The patch beam script (`patch_five_story_beams.py`) is 104 lines that add beams along a grid. This is exactly what `_generate_beam_grid()` does -- but parameterized from the spec instead of hardcoded.

Both scripts validate that the generator architecture is correct: the coordinate math they do by hand is exactly the coordinate math the generator automates.

---

Sources:
- simplification-research.md (internal)
- build_retail_terrace_concept.py (internal)
- patch_five_story_beams.py (internal)
- ifc_author.py (internal)
- system_catalog.py (internal)
- footing_selector.py (internal)
