"""Spec-first building generator.

The AI makes design decisions (spec). Python does coordinate math.
This module deterministically expands a structured building spec into a
complete IFC model by calling IfcAuthor methods directly -- the same
pattern used by the build scripts (build_retail_terrace_concept.py,
patch_five_story_beams.py, etc.).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


from .ifc_author import IfcAuthor
from .facade_generator import (  # noqa: F401
    ResolvedGrid as _FacadeResolvedGrid,
    ResolvedStorey as _FacadeResolvedStorey,
    generate_facade_walls,
    generate_windows,
    generate_doors,
)
from .section_library import starter_section_records, INCH_TO_M
from .footing_selector import starter_footing_from_imposed_load, PSF_TO_KPA


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_GRID = {"spacing_x": 8.0, "spacing_y": 8.0}
_DEFAULT_STRUCTURE = {
    "column_size": [0.3, 0.3],
    "beam_size": [0.3, 0.5],
    "slab_thickness": 0.2,
}
_DEFAULT_WALLS = {
    "thickness": 0.2,
    "facades": ["north", "south", "east", "west"],
}
_DEFAULT_FOUNDATION = {
    "type": "spread_footings",
    "soil_bearing_kpa": 96.0,  # ~2000 psf
    "concrete_mpa": 28,
    "bearing_elevation": -1.2,
}

# Floor load assumptions for gravity load estimation (kPa)
_FLOOR_LOAD_KPA = {
    "office": {"dead": 5.8, "live": 2.4},     # 0.2m slab + superimposed
    "retail": {"dead": 5.8, "live": 4.8},
    "parking": {"dead": 5.8, "live": 2.4},
    "residential": {"dead": 5.8, "live": 1.9},
}

# Heuristic auto-sizing: pick section based on number of stories
# These are conservative concept-level defaults
_AUTO_COLUMN_BY_STORIES = {
    1: "W10X33",
    2: "W10X49",
    3: "W12X40",
    4: "W12X53",
    5: "W14X68",
    6: "W14X90",
}
_AUTO_BEAM_BY_SPAN = {
    6.0: "W12X26",
    8.0: "W16X31",
    10.0: "W18X35",
    12.0: "W21X44",
    15.0: "W24X55",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _round6(value: float) -> float:
    """Round to 6 decimal places to avoid floating-point noise."""
    return round(value, 6)


def _resolve_section(section_name: str, role: str, num_stories: int = 1,
                     max_span: float = 8.0) -> Optional[Dict[str, Any]]:
    """Resolve a section name to profile dimensions.

    If section_name is "auto", pick a reasonable default based on building
    parameters. Returns None if no section found (falls back to rectangular).

    Returns dict with: profile_type, width, depth, web_thickness,
                       flange_thickness, section_name
    """
    if section_name == "auto":
        if role == "column":
            # Pick by number of stories; clamp to largest available
            max_key = max(_AUTO_COLUMN_BY_STORIES.keys())
            section_name = _AUTO_COLUMN_BY_STORIES.get(
                min(num_stories, max_key),
                _AUTO_COLUMN_BY_STORIES[max_key],
            )
        elif role == "beam":
            # Pick by max span; find the smallest section that covers the span
            chosen = None
            for span_limit in sorted(_AUTO_BEAM_BY_SPAN.keys()):
                chosen = _AUTO_BEAM_BY_SPAN[span_limit]
                if span_limit >= max_span:
                    break
            section_name = chosen or "W16X31"
        else:
            return None

    catalog = starter_section_records()
    record = catalog.get(section_name.upper().replace(" ", ""))
    if record is None:
        return None

    result: Dict[str, Any] = {
        "section_name": record.name,
        "width": record.width_m,
        "depth": record.depth_m,
    }

    if record.shape_family == "W" and record.tw_in is not None and record.tf_in is not None:
        result["profile_type"] = "I"
        result["web_thickness"] = record.tw_in * INCH_TO_M
        result["flange_thickness"] = record.tf_in * INCH_TO_M
    else:
        result["profile_type"] = "rectangular"
        result["web_thickness"] = None
        result["flange_thickness"] = None

    return result


def _compute_grid(footprint: Dict[str, Any], grid: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the actual grid positions from footprint and grid spec.

    KEY: Adjust spacing so the grid FITS the footprint exactly.
    If footprint is 25m and target spacing is 8m, use 3 bays at 8.33m
    (not 3 bays at 8m = 24m with a 1m gap).

    Returns dict with: bays_x, bays_y, spacing_x, spacing_y, xs, ys
    """
    length = footprint["length"]
    width = footprint["width"]

    # Determine bay counts
    if "bays_x" in grid:
        bays_x = grid["bays_x"]
    else:
        spacing_x = grid.get("spacing_x", 8.0)
        bays_x = max(1, round(length / spacing_x))

    if "bays_y" in grid:
        bays_y = grid["bays_y"]
    else:
        spacing_y = grid.get("spacing_y", 8.0)
        bays_y = max(1, round(width / spacing_y))

    # Adjust spacing to fit exactly
    actual_spacing_x = length / bays_x
    actual_spacing_y = width / bays_y

    # Compute grid line positions
    xs = [_round6(ix * actual_spacing_x) for ix in range(bays_x + 1)]
    ys = [_round6(iy * actual_spacing_y) for iy in range(bays_y + 1)]

    return {
        "bays_x": bays_x,
        "bays_y": bays_y,
        "spacing_x": actual_spacing_x,
        "spacing_y": actual_spacing_y,
        "xs": xs,
        "ys": ys,
    }


def _resolve_stories(stories_spec: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve story specs, computing elevations if not provided.

    Returns a list of dicts with: name, height, elevation.
    """
    resolved = []
    cumulative_elevation = 0.0
    for idx, story in enumerate(stories_spec):
        name = story.get("name", f"Level {idx + 1}")
        height = story["height"]
        elevation = story.get("elevation", cumulative_elevation)
        resolved.append({
            "name": name,
            "height": height,
            "elevation": _round6(elevation),
        })
        cumulative_elevation = elevation + height
    return resolved


# ---------------------------------------------------------------------------
# BuildingGenerator
# ---------------------------------------------------------------------------

class BuildingGenerator:
    """Generates a complete IFC building from a structured spec.

    The AI makes design decisions (spec). Python does coordinate math.
    """

    def __init__(self, spec: Dict[str, Any], output_path: str):
        self.spec = spec
        self.output_path = output_path
        # Create parent directories if needed
        parent = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(parent, exist_ok=True)
        self.author = IfcAuthor(output_path)
        self.log: List[str] = []  # track what was generated
        self.counts: Dict[str, int] = {
            "storeys": 0,
            "columns": 0,
            "beams": 0,
            "slabs": 0,
            "walls": 0,
            "windows": 0,
            "doors": 0,
            "curtain_walls": 0,
            "footings": 0,
        }
        self.wall_names: Dict[str, str] = {}  # "{face}_{storey}" -> wall element name

        # Resolve shared state once: footprint, grid, stories, structure, walls
        self.footprint = spec["footprint"]
        self.grid = _compute_grid(
            self.footprint,
            spec.get("grid", _DEFAULT_GRID),
        )
        self.stories = _resolve_stories(spec["stories"])
        self.structure = {**_DEFAULT_STRUCTURE, **spec.get("structure", {})}
        self.walls_spec = {**_DEFAULT_WALLS, **spec.get("walls", {})}
        self.foundation_spec = {**_DEFAULT_FOUNDATION, **spec.get("foundation", {})}

        # Resolve steel sections (column_section / beam_section)
        max_span = max(self.grid["spacing_x"], self.grid["spacing_y"])
        num_stories = len(self.stories)

        col_section_name = self.structure.get("column_section")
        if col_section_name:
            self._column_section = _resolve_section(
                col_section_name, "column",
                num_stories=num_stories, max_span=max_span,
            )
        else:
            self._column_section = None

        beam_section_name = self.structure.get("beam_section")
        if beam_section_name:
            self._beam_section = _resolve_section(
                beam_section_name, "beam",
                num_stories=num_stories, max_span=max_span,
            )
        else:
            self._beam_section = None

    def generate(self) -> Dict[str, Any]:
        """Generate the full building. Returns summary stats."""
        self._generate_storeys()
        self._generate_column_grid()
        self._generate_beam_grid()
        self._generate_floor_plates()
        self._generate_facades()
        self._generate_openings()
        self._generate_foundations()
        self.author.save()
        return self._summary()

    # ------------------------------------------------------------------
    # Sub-generators
    # ------------------------------------------------------------------

    def _generate_storeys(self) -> None:
        """Create one IfcBuildingStorey per story at the correct elevation."""
        for story in self.stories:
            self.author.ensure_storey(
                name=story["name"],
                elevation=story["elevation"],
            )
            self.counts["storeys"] += 1
            self.log.append(f"Storey: {story['name']} @ {story['elevation']}m")

    def _generate_column_grid(self) -> None:
        """Create columns at every grid intersection for each story.

        Uses the shared grid (xs, ys) so columns, beams, slabs, and walls
        all align to the same grid.  When a steel section is resolved
        (column_section in spec), uses IfcIShapeProfileDef for real
        I-beam rendering.
        """
        xs = self.grid["xs"]
        ys = self.grid["ys"]

        # Use resolved I-beam section or fall back to rectangular
        sec = self._column_section
        if sec:
            col_width = sec["width"]
            col_depth = sec["depth"]
            profile_type = sec["profile_type"]
            web_thickness = sec["web_thickness"]
            flange_thickness = sec["flange_thickness"]
            section_name = sec["section_name"]
        else:
            col_width, col_depth = self.structure["column_size"]
            profile_type = "rectangular"
            web_thickness = None
            flange_thickness = None
            section_name = None

        for story in self.stories:
            storey_name = story["name"]
            base_z = story["elevation"]
            height = story["height"]

            for ix, x in enumerate(xs):
                for iy, y in enumerate(ys):
                    col_name = f"{storey_name} Col X{ix + 1} Y{iy + 1}"
                    self.author.create_column(
                        name=col_name,
                        storey_name=storey_name,
                        x=x,
                        y=y,
                        base_z=base_z,
                        width=col_width,
                        depth=col_depth,
                        height=height,
                        profile_type=profile_type,
                        web_thickness=web_thickness,
                        flange_thickness=flange_thickness,
                        section_name=section_name,
                    )
                    self.counts["columns"] += 1

            section_label = section_name or f"{col_width}x{col_depth}"
            self.log.append(
                f"Columns: {storey_name} - "
                f"{len(xs)}x{len(ys)} = {len(xs) * len(ys)} columns "
                f"({section_label}, {profile_type})"
            )

    def _generate_beam_grid(self) -> None:
        """Create beams along every gridline for each story.

        X-direction beams: constant Y, span between adjacent X gridlines.
        Y-direction beams: constant X, span between adjacent Y gridlines.
        Uses the SAME grid variables as columns.  When a steel section is
        resolved (beam_section in spec), uses IfcIShapeProfileDef.
        """
        xs = self.grid["xs"]
        ys = self.grid["ys"]

        # Use resolved I-beam section or fall back to rectangular
        sec = self._beam_section
        if sec:
            beam_width = sec["width"]
            beam_depth = sec["depth"]
            profile_type = sec["profile_type"]
            web_thickness = sec["web_thickness"]
            flange_thickness = sec["flange_thickness"]
            section_name = sec["section_name"]
        else:
            beam_width, beam_depth = self.structure["beam_size"]
            profile_type = "rectangular"
            web_thickness = None
            flange_thickness = None
            section_name = None

        for story in self.stories:
            storey_name = story["name"]
            base_z = story["elevation"]
            beam_count = 0

            # X-direction beams: constant Y, span across adjacent X columns
            for iy, y in enumerate(ys):
                for ix in range(len(xs) - 1):
                    x1, x2 = xs[ix], xs[ix + 1]
                    beam_name = f"{storey_name} Beam-X Y{iy + 1} X{ix + 1}-{ix + 2}"
                    self.author.create_beam(
                        name=beam_name,
                        storey_name=storey_name,
                        start_x=x1,
                        start_y=y,
                        end_x=x2,
                        end_y=y,
                        base_z=base_z,
                        width=beam_width,
                        depth=beam_depth,
                        profile_type=profile_type,
                        web_thickness=web_thickness,
                        flange_thickness=flange_thickness,
                        section_name=section_name,
                    )
                    self.counts["beams"] += 1
                    beam_count += 1

            # Y-direction beams: constant X, span across adjacent Y rows
            for ix, x in enumerate(xs):
                for iy in range(len(ys) - 1):
                    y1, y2 = ys[iy], ys[iy + 1]
                    beam_name = f"{storey_name} Beam-Y X{ix + 1} Y{iy + 1}-{iy + 2}"
                    self.author.create_beam(
                        name=beam_name,
                        storey_name=storey_name,
                        start_x=x,
                        start_y=y1,
                        end_x=x,
                        end_y=y2,
                        base_z=base_z,
                        width=beam_width,
                        depth=beam_depth,
                        profile_type=profile_type,
                        web_thickness=web_thickness,
                        flange_thickness=flange_thickness,
                        section_name=section_name,
                    )
                    self.counts["beams"] += 1
                    beam_count += 1

            section_label = section_name or f"{beam_width}x{beam_depth}"
            self.log.append(
                f"Beams: {storey_name} - {beam_count} beams "
                f"({section_label}, {profile_type})"
            )

    def _generate_floor_plates(self) -> None:
        """Create one slab per story spanning the full footprint.

        Slab is placed at origin (0, 0) at the story elevation.
        """
        length = self.footprint["length"]
        width = self.footprint["width"]
        slab_thickness = self.structure["slab_thickness"]

        for story in self.stories:
            storey_name = story["name"]
            elevation = story["elevation"]

            # Per-story override
            per_story_thickness = None
            for s in self.spec["stories"]:
                if s.get("name") == storey_name and "slab_thickness" in s:
                    per_story_thickness = s["slab_thickness"]
                    break
            thickness = per_story_thickness if per_story_thickness is not None else slab_thickness

            # Skip slab if explicitly excluded
            for s in self.spec["stories"]:
                if s.get("name") == storey_name and s.get("exclude_slab"):
                    self.log.append(f"Slab: {storey_name} - SKIPPED (exclude_slab)")
                    break
            else:
                slab_name = f"{storey_name} Floor Slab"
                self.author.create_rectangular_slab(
                    name=slab_name,
                    storey_name=storey_name,
                    x=0.0,
                    y=0.0,
                    z=elevation,
                    length=length,
                    width=width,
                    thickness=thickness,
                )
                self.counts["slabs"] += 1
                self.log.append(
                    f"Slab: {storey_name} - {length}m x {width}m x {thickness}m"
                )

        # --- Roof slab: close the top of the building ---
        top_story = self.stories[-1]
        roof_elevation = _round6(top_story["elevation"] + top_story["height"])
        self.author.create_rectangular_slab(
            name="Roof Slab",
            storey_name=top_story["name"],  # assign to top storey
            x=0.0,
            y=0.0,
            z=roof_elevation,
            length=length,
            width=width,
            thickness=slab_thickness,
        )
        self.counts["slabs"] += 1
        self.log.append(
            f"Slab: Roof @ {roof_elevation}m - {length}m x {width}m x {slab_thickness}m"
        )

    def _generate_foundations(self) -> None:
        """Generate spread footings under each ground-floor column.

        Estimates gravity loads from tributary area and floor loads, then
        calls footing_selector.starter_footing_from_imposed_load() to size
        each footing.  Only runs when spec includes a 'foundation' section
        or column_section / beam_section (implying a real structural model).
        """
        foundation = self.foundation_spec
        if foundation.get("type") == "none":
            self.log.append("Foundations: skipped (type=none)")
            return

        # Only generate footings if explicitly requested via foundation spec
        # or if steel sections are specified (real structural model)
        has_explicit_foundation = "foundation" in self.spec
        has_steel = self._column_section is not None or self._beam_section is not None
        if not has_explicit_foundation and not has_steel:
            self.log.append("Foundations: skipped (no foundation spec or steel sections)")
            return

        xs = self.grid["xs"]
        ys = self.grid["ys"]
        num_stories = len(self.stories)
        spacing_x = self.grid["spacing_x"]
        spacing_y = self.grid["spacing_y"]

        bearing_elevation = foundation.get("bearing_elevation", -1.2)
        soil_bearing_kpa = foundation.get("soil_bearing_kpa", 96.0)
        # Convert kPa to psf for the footing_selector (it uses imperial internally)
        allowable_bearing_psf = soil_bearing_kpa / PSF_TO_KPA

        # Determine floor loads
        program = "office"  # default
        if self.stories:
            program = self.stories[0].get("program", "office")
        loads = _FLOOR_LOAD_KPA.get(program, _FLOOR_LOAD_KPA["office"])
        service_load_kpa = loads["dead"] + loads["live"]  # service-level per floor

        # Ensure we have a storey to assign footings to (use lowest storey)
        ground_storey_name = self.stories[0]["name"]

        # Determine edge positions for interior vs perimeter classification
        min_x, max_x = xs[0], xs[-1]
        min_y, max_y = ys[0], ys[-1]
        tol = 1e-6

        footing_count = 0
        for ix, x in enumerate(xs):
            for iy, y in enumerate(ys):
                # Compute tributary area
                on_x_edge = abs(x - min_x) < tol or abs(x - max_x) < tol
                on_y_edge = abs(y - min_y) < tol or abs(y - max_y) < tol

                if on_x_edge and on_y_edge:
                    trib_factor = 0.25  # corner
                elif on_x_edge or on_y_edge:
                    trib_factor = 0.5   # edge
                else:
                    trib_factor = 1.0   # interior

                tributary_area = spacing_x * spacing_y * trib_factor
                # Service load: sum over all stories
                service_load_kn = tributary_area * service_load_kpa * num_stories

                on_perimeter = on_x_edge or on_y_edge
                footing_family = "perimeter_spread_footing" if on_perimeter else "interior_spread_footing"

                # Size the footing
                footing_result = starter_footing_from_imposed_load(
                    imposed_load_kn=service_load_kn,
                    footing_family=footing_family,
                    allowable_bearing_psf=allowable_bearing_psf,
                )

                pad_size = footing_result["recommended_square_size_m"]
                thickness = footing_result["footing_thickness_m"]

                # Place footing centered on column grid intersection
                footing_x = x - pad_size / 2.0
                footing_y = y - pad_size / 2.0

                footing_name = f"Footing X{ix + 1} Y{iy + 1}"
                self.author.create_footing(
                    name=footing_name,
                    storey_name=ground_storey_name,
                    x=footing_x,
                    y=footing_y,
                    base_z=bearing_elevation,
                    length=pad_size,
                    width=pad_size,
                    thickness=thickness,
                    foundation_type="spread_footing",
                    bearing_elevation=bearing_elevation,
                    support_for=f"Col X{ix + 1} Y{iy + 1}",
                    imposed_load_kn=round(service_load_kn, 2),
                    allowable_bearing_kpa=round(soil_bearing_kpa, 2),
                    concrete_strength_mpa=footing_result.get("concrete_strength_mpa"),
                    rebar_grade=footing_result.get("rebar_grade"),
                    rebar_bar_diameter_mm=footing_result.get("rebar_bar_diameter_mm"),
                    rebar_spacing_mm=footing_result.get("rebar_spacing_mm"),
                    rebar_weight_kg=footing_result.get("rebar_weight_kg"),
                    basis_notes=footing_result.get("basis_notes"),
                )
                self.counts["footings"] += 1
                footing_count += 1

        self.log.append(
            f"Foundations: {footing_count} spread footings at z={bearing_elevation}m"
        )

    def _generate_facades(self) -> None:
        """Generate facade walls (walls, curtain walls, mixed) per face per storey.

        Delegates to facade_generator.generate_facade_walls(). If the spec
        contains the new 'facades' key, it is used. Otherwise falls back to
        the legacy 'walls' key for backward compatibility.
        """
        facade_grid = self._to_facade_grid()
        facade_stories = self._to_facade_stories()

        # If spec uses the new facades format, pass through directly.
        # Otherwise synthesise a minimal facade spec from legacy walls spec.
        if "facades" in self.spec:
            facade_spec = self.spec
        else:
            # Legacy compatibility: convert old walls spec to new facades format
            thickness = self.walls_spec["thickness"]
            facades_list = self.walls_spec.get(
                "facades", ["north", "south", "east", "west"]
            )
            facade_spec = dict(self.spec)
            facade_spec["facades"] = {
                face: {"type": "wall", "thickness": thickness}
                for face in facades_list
            }

        self.wall_names = generate_facade_walls(
            author=self.author,
            spec=facade_spec,
            grid=facade_grid,
            stories=facade_stories,
        )

        self.counts["walls"] = len(self.wall_names)
        self.log.append(f"Facades: {len(self.wall_names)} walls created")

    def _generate_openings(self) -> None:
        """Generate windows and doors from spec.

        Windows come from facade specs (per_bay, ribbon, none patterns).
        Doors come from 'entries' list.
        Delegates to facade_generator.generate_windows() / generate_doors().
        """
        if not self.wall_names:
            return

        facade_grid = self._to_facade_grid()
        facade_stories = self._to_facade_stories()

        # Windows
        if "facades" in self.spec:
            win_count = generate_windows(
                author=self.author,
                spec=self.spec,
                grid=facade_grid,
                stories=facade_stories,
                wall_names=self.wall_names,
            )
            self.counts["windows"] = win_count
            if win_count:
                self.log.append(f"Windows: {win_count} windows created")

        # Doors
        if "entries" in self.spec:
            door_count = generate_doors(
                author=self.author,
                spec=self.spec,
                grid=facade_grid,
                stories=facade_stories,
                wall_names=self.wall_names,
            )
            self.counts["doors"] = door_count
            if door_count:
                self.log.append(f"Doors: {door_count} doors created")

    # ------------------------------------------------------------------
    # Facade-generator data adapters
    # ------------------------------------------------------------------

    def _to_facade_grid(self) -> _FacadeResolvedGrid:
        """Convert our grid dict to the facade_generator's ResolvedGrid."""
        return _FacadeResolvedGrid(
            bays_x=self.grid["bays_x"],
            bays_y=self.grid["bays_y"],
            spacings_x=[self.grid["spacing_x"]] * self.grid["bays_x"],
            spacings_y=[self.grid["spacing_y"]] * self.grid["bays_y"],
            xs=self.grid["xs"],
            ys=self.grid["ys"],
        )

    def _to_facade_stories(self) -> List[_FacadeResolvedStorey]:
        """Convert our story dicts to facade_generator's ResolvedStorey."""
        return [
            _FacadeResolvedStorey(
                name=s["name"],
                height=s["height"],
                elevation=s["elevation"],
                program=s.get("program", "office"),
                slab_thickness=s.get("slab_thickness", 0.2),
                exclude_slab=s.get("exclude_slab", False),
            )
            for s in self.stories
        ]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _summary(self) -> Dict[str, Any]:
        """Return a summary of what was generated."""
        return {
            "output_path": self.output_path,
            "footprint": {
                "length": self.footprint["length"],
                "width": self.footprint["width"],
            },
            "grid": {
                "bays_x": self.grid["bays_x"],
                "bays_y": self.grid["bays_y"],
                "spacing_x": _round6(self.grid["spacing_x"]),
                "spacing_y": _round6(self.grid["spacing_y"]),
                "xs": self.grid["xs"],
                "ys": self.grid["ys"],
            },
            "stories": len(self.stories),
            "counts": dict(self.counts),
            "wall_names": dict(self.wall_names),
            "log": list(self.log),
            "ifc_summary": self.author.debug_dump(),
        }


# ---------------------------------------------------------------------------
# Convenience: generate from a spec dict or a JSON file path
# ---------------------------------------------------------------------------

def generate_from_spec(spec: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    """One-shot: build an IFC from a spec dict."""
    gen = BuildingGenerator(spec, output_path)
    return gen.generate()


def generate_from_json(spec_path: str, output_path: str) -> Dict[str, Any]:
    """One-shot: load a JSON spec file and build an IFC."""
    with open(spec_path, "r") as f:
        spec = json.load(f)
    return generate_from_spec(spec, output_path)
