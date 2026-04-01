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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _round6(value: float) -> float:
    """Round to 6 decimal places to avoid floating-point noise."""
    return round(value, 6)


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

    def generate(self) -> Dict[str, Any]:
        """Generate the full building. Returns summary stats."""
        self._generate_storeys()
        self._generate_column_grid()
        self._generate_beam_grid()
        self._generate_floor_plates()
        self._generate_facades()
        self._generate_openings()
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
        all align to the same grid.
        """
        xs = self.grid["xs"]
        ys = self.grid["ys"]
        col_width, col_depth = self.structure["column_size"]

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
                    )
                    self.counts["columns"] += 1

            self.log.append(
                f"Columns: {storey_name} - "
                f"{len(xs)}x{len(ys)} = {len(xs) * len(ys)} columns"
            )

    def _generate_beam_grid(self) -> None:
        """Create beams along every gridline for each story.

        X-direction beams: constant Y, span between adjacent X gridlines.
        Y-direction beams: constant X, span between adjacent Y gridlines.
        Uses the SAME grid variables as columns.
        """
        xs = self.grid["xs"]
        ys = self.grid["ys"]
        beam_width, beam_depth = self.structure["beam_size"]

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
                    )
                    self.counts["beams"] += 1
                    beam_count += 1

            self.log.append(f"Beams: {storey_name} - {beam_count} beams")

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
