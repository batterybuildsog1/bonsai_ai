"""Facade and opening generators for the spec-first BuildingGenerator.

This module generates the building envelope: perimeter walls, curtain walls,
windows (per-bay and ribbon patterns), and doors. It is called by
BuildingGenerator._generate_facades() and _generate_openings().

All IFC creation is delegated to IfcAuthor methods -- this module computes
geometry (positions, offsets, rotations) and issues the correct calls.

Facade geometry conventions (origin at footprint [0, 0]):
  South: y=0,      runs X from 0 to length
  North: y=width,  runs X from 0 to length  (note: reversed winding in design doc, but wall runs left-to-right for consistent offset math)
  East:  x=length, runs Y from 0 to width
  West:  x=0,      runs Y from 0 to width

Wall naming: "{storey_name} {Face} Wall"  e.g. "Level 1 South Wall"
  This is the canonical name used for window/door hosting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from bonsai_ai.ifc_author import IfcAuthor


# ---------------------------------------------------------------------------
# Data classes shared with BuildingGenerator
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Face geometry helpers
# ---------------------------------------------------------------------------

def _face_geometry(length: float, width: float) -> Dict[str, Tuple[float, float, float, float]]:
    """Return (start_x, start_y, end_x, end_y) for each cardinal face.

    All walls run in the positive direction along their axis so that
    offset_along_wall increases from left to right / bottom to top
    when viewed from outside.
    """
    return {
        "south": (0.0, 0.0, length, 0.0),
        "north": (0.0, width, length, width),
        "east":  (length, 0.0, length, width),
        "west":  (0.0, 0.0, 0.0, width),
    }


def _wall_length(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _bay_centres_along_face(
    face_name: str, grid: ResolvedGrid
) -> List[float]:
    """Return the centre of each structural bay measured as offset along the wall.

    South/North walls run in X -> bay centres from grid.xs midpoints.
    East/West walls run in Y -> bay centres from grid.ys midpoints.
    """
    if face_name in ("south", "north"):
        positions = grid.xs
    else:
        positions = grid.ys

    centres = []
    for i in range(len(positions) - 1):
        centres.append((positions[i] + positions[i + 1]) / 2.0)
    return centres


def _bay_widths_along_face(
    face_name: str, grid: ResolvedGrid
) -> List[float]:
    """Return the width of each structural bay along the wall axis."""
    if face_name in ("south", "north"):
        return list(grid.spacings_x)
    else:
        return list(grid.spacings_y)


# ---------------------------------------------------------------------------
# generate_facade_walls
# ---------------------------------------------------------------------------

def generate_facade_walls(
    author: IfcAuthor,
    spec: dict,
    grid: ResolvedGrid,
    stories: List[ResolvedStorey],
) -> Dict[str, str]:
    """Create perimeter walls / curtain walls for every facade and storey.

    Returns:
        wall_names: dict mapping "{face}_{storey_name}" to the wall element
        name, so that generate_windows / generate_doors can reference them.
    """
    fp = spec["footprint"]
    length = fp.get("length", grid.xs[-1])
    width = fp.get("width", grid.ys[-1])
    facade_specs = spec.get("facades", {})
    faces = _face_geometry(length, width)

    wall_names: Dict[str, str] = {}
    walls_created = 0
    curtain_walls_created = 0

    for face_name, (x1, y1, x2, y2) in faces.items():
        fspec = facade_specs.get(face_name, {})
        ftype = fspec.get("type", "wall")
        thickness = fspec.get("thickness", 0.25)
        material = fspec.get("material", "concrete")

        # "mixed" facade: ground floor uses ground_spec, upper floors use upper_spec
        ground_spec = fspec.get("ground", None)
        upper_spec = fspec.get("upper", None)
        is_mixed = ftype == "mixed"

        for story in stories:
            is_ground = story == stories[0]

            # Determine effective type for this storey
            if is_mixed:
                if is_ground and ground_spec:
                    eff_type = ground_spec.get("type", "curtain_wall")
                    eff_spec = ground_spec
                elif not is_ground and upper_spec:
                    eff_type = upper_spec.get("type", "wall")
                    eff_spec = upper_spec
                else:
                    eff_type = "wall"
                    eff_spec = fspec
            else:
                eff_type = ftype
                eff_spec = fspec

            # Handle "stories" filter (all / ground_only / upper_only)
            fstories = eff_spec.get("stories", fspec.get("stories", "all"))
            if fstories == "ground_only" and not is_ground:
                continue
            if fstories == "upper_only" and is_ground:
                continue

            wall_key = f"{face_name}_{story.name}"

            if eff_type == "wall":
                wall_name = f"{story.name} {face_name.capitalize()} Wall"
                eff_thickness = eff_spec.get("thickness", thickness)
                eff_material = eff_spec.get("material", material)
                author.create_wall(
                    name=wall_name,
                    storey_name=story.name,
                    start_x=x1, start_y=y1,
                    end_x=x2, end_y=y2,
                    base_z=story.elevation,
                    height=story.height,
                    thickness=eff_thickness,
                    material=eff_material,
                )
                wall_names[wall_key] = wall_name
                walls_created += 1

            elif eff_type == "curtain_wall":
                cw_params = eff_spec.get("curtain_wall", {})
                # Also support panel_size shorthand from spec format
                panel_size = eff_spec.get("panel_size", None)
                if panel_size and isinstance(panel_size, (list, tuple)) and len(panel_size) == 2:
                    panel_w, panel_h = panel_size
                else:
                    panel_w = cw_params.get("panel_width", 1.5)
                    panel_h = cw_params.get("panel_height", 1.2)
                panel_t = cw_params.get("panel_thickness", 0.02)
                wlen = _wall_length(x1, y1, x2, y2)
                rotation = math.degrees(math.atan2(y2 - y1, x2 - x1))
                cw_name = f"{story.name} {face_name.capitalize()} Curtain Wall"
                author.create_curtain_wall(
                    name=cw_name,
                    storey_name=story.name,
                    x=x1, y=y1,
                    base_z=story.elevation,
                    width=wlen,
                    height=story.height,
                    rotation_degrees=rotation,
                    panel_width=panel_w,
                    panel_height=panel_h,
                    panel_thickness=panel_t,
                )
                curtain_walls_created += 1
                # Curtain walls don't get registered for window hosting

    return wall_names


# ---------------------------------------------------------------------------
# generate_windows
# ---------------------------------------------------------------------------

def generate_windows(
    author: IfcAuthor,
    spec: dict,
    grid: ResolvedGrid,
    stories: List[ResolvedStorey],
    wall_names: Dict[str, str],
) -> int:
    """Place windows in walls according to facade specs.

    Supports:
      - "per_bay": one (or N) window(s) centred in each structural bay
      - "ribbon": continuous strip window (one long window per bay)
      - "none": skip

    Returns the total number of windows created.
    """
    facade_specs = spec.get("facades", {})
    windows_created = 0

    for face_name, fspec_raw in facade_specs.items():
        fspec = fspec_raw if isinstance(fspec_raw, dict) else {}
        ftype = fspec.get("type", "wall")

        # For mixed facades, only upper stories get windows (on wall portions)
        if ftype == "mixed":
            upper_spec = fspec.get("upper", {})
            if upper_spec.get("type", "wall") != "wall":
                continue
            windows_cfg = upper_spec.get("windows", {})
            applicable_stories = stories[1:]  # skip ground floor
        elif ftype != "wall":
            continue
        else:
            windows_cfg = fspec.get("windows", {})
            # Check for "stories" filter in the windows config itself
            win_stories_filter = windows_cfg.get("stories", "all")
            if win_stories_filter == "upper_only":
                applicable_stories = stories[1:]  # skip ground floor
            elif win_stories_filter == "ground_only":
                applicable_stories = stories[:1]
            else:
                # Default: skip ground floor if entries (doors) exist on
                # this facade -- ground floor with a door is typically
                # solid wall, not windowed.
                entries = spec.get("entries", [])
                has_ground_entry = any(
                    e.get("facade", e.get("face", "")) == face_name
                    and e.get("story_index", 0) == 0
                    for e in entries
                )
                if has_ground_entry:
                    applicable_stories = stories[1:]  # skip ground floor
                else:
                    applicable_stories = list(stories)

        pattern = windows_cfg.get("pattern", "none")
        if pattern == "none":
            continue

        win_w = windows_cfg.get("width", windows_cfg.get("size", [1.8, 1.5])[0] if "size" in windows_cfg else 1.8)
        win_h = windows_cfg.get("height", windows_cfg.get("size", [1.8, 1.5])[1] if "size" in windows_cfg else 1.5)
        sill = windows_cfg.get("sill_height", windows_cfg.get("sill", 0.9))
        count_per_bay = windows_cfg.get("count_per_bay", 1)

        # Handle "stories" filter on the facade spec
        fstories = fspec.get("stories", "all")

        for story in applicable_stories:
            is_ground = story == stories[0]
            if fstories == "ground_only" and not is_ground:
                continue
            if fstories == "upper_only" and is_ground:
                continue

            wall_key = f"{face_name}_{story.name}"
            wall_name = wall_names.get(wall_key)
            if not wall_name:
                continue  # no wall to host windows (e.g., curtain wall storey)

            if pattern == "per_bay":
                windows_created += _place_windows_per_bay(
                    author=author,
                    wall_name=wall_name,
                    face_name=face_name,
                    story=story,
                    grid=grid,
                    count_per_bay=count_per_bay,
                    win_w=win_w,
                    win_h=win_h,
                    sill=sill,
                )
            elif pattern == "ribbon":
                windows_created += _place_ribbon_windows(
                    author=author,
                    wall_name=wall_name,
                    face_name=face_name,
                    story=story,
                    grid=grid,
                    win_h=win_h,
                    sill=sill,
                )

    return windows_created


def _place_windows_per_bay(
    author: IfcAuthor,
    wall_name: str,
    face_name: str,
    story: ResolvedStorey,
    grid: ResolvedGrid,
    count_per_bay: int,
    win_w: float,
    win_h: float,
    sill: float,
) -> int:
    """Place one (or more) window(s) centred in each structural bay.

    For per_bay with count=1:
      offset = bay_centre - win_w / 2

    For per_bay with count>1:
      Windows are evenly distributed within the bay.

    Following patch_five_story_openings.py pattern: each window gets a unique
    name like "Level 2 East Window Bay 1".
    """
    bay_centres = _bay_centres_along_face(face_name, grid)
    bay_widths = _bay_widths_along_face(face_name, grid)
    count = 0

    for bay_idx, (centre, bay_w) in enumerate(zip(bay_centres, bay_widths), start=1):
        if count_per_bay == 1:
            # Single window centred in bay
            offset = centre - win_w / 2.0
            if offset < 0:
                offset = 0.0  # clamp to wall start
            name = f"{story.name} {face_name.capitalize()} Window Bay {bay_idx}"
            author.create_window(
                name=name,
                storey_name=story.name,
                wall_name=wall_name,
                offset_along_wall=offset,
                sill_height=sill,
                width=win_w,
                height=win_h,
                thickness=0.05,
            )
            count += 1
        else:
            # Multiple windows per bay: evenly spaced
            spacing = bay_w / (count_per_bay + 1)
            bay_start = centre - bay_w / 2.0
            for win_idx in range(1, count_per_bay + 1):
                pos = bay_start + spacing * win_idx
                offset = pos - win_w / 2.0
                if offset < 0:
                    offset = 0.0
                name = f"{story.name} {face_name.capitalize()} Window Bay {bay_idx}-{win_idx}"
                author.create_window(
                    name=name,
                    storey_name=story.name,
                    wall_name=wall_name,
                    offset_along_wall=offset,
                    sill_height=sill,
                    width=win_w,
                    height=win_h,
                    thickness=0.05,
                )
                count += 1

    return count


def _place_ribbon_windows(
    author: IfcAuthor,
    wall_name: str,
    face_name: str,
    story: ResolvedStorey,
    grid: ResolvedGrid,
    win_h: float,
    sill: float,
) -> int:
    """Place continuous strip (ribbon) windows: one window per bay that spans
    most of the bay width, with a small margin on each side.

    Ribbon window width = bay_width - 2 * margin, where margin = 0.15m
    (to leave a thin mullion between bays).
    """
    bay_centres = _bay_centres_along_face(face_name, grid)
    bay_widths = _bay_widths_along_face(face_name, grid)
    margin = 0.15  # mullion/frame margin each side
    count = 0

    for bay_idx, (centre, bay_w) in enumerate(zip(bay_centres, bay_widths), start=1):
        ribbon_w = bay_w - 2 * margin
        if ribbon_w <= 0.3:
            continue  # bay too narrow for ribbon window
        offset = centre - ribbon_w / 2.0
        if offset < 0:
            offset = 0.0
        name = f"{story.name} {face_name.capitalize()} Ribbon Window Bay {bay_idx}"
        author.create_window(
            name=name,
            storey_name=story.name,
            wall_name=wall_name,
            offset_along_wall=offset,
            sill_height=sill,
            width=ribbon_w,
            height=win_h,
            thickness=0.05,
        )
        count += 1

    return count


# ---------------------------------------------------------------------------
# generate_doors
# ---------------------------------------------------------------------------

def generate_doors(
    author: IfcAuthor,
    spec: dict,
    grid: ResolvedGrid,
    stories: List[ResolvedStorey],
    wall_names: Dict[str, str],
) -> int:
    """Place doors from the spec 'entries' list.

    Each entry specifies:
      - face: which facade
      - type: single_door, double_door, etc. (for naming)
      - width, height: door dimensions
      - position: "center", "left_third", "right_third" -- or --
      - position_x / position_offset: explicit offset along wall

    Returns the total number of doors created.
    """
    entries = spec.get("entries", [])
    fp = spec["footprint"]
    length = fp.get("length", grid.xs[-1])
    width = fp.get("width", grid.ys[-1])
    faces = _face_geometry(length, width)
    doors_created = 0

    for entry_idx, entry in enumerate(entries):
        face_name = entry.get("facade", entry.get("face", "south"))
        door_type = entry.get("type", "double_door")
        door_w = entry.get("width", 2.0)
        door_h = entry.get("height", 2.4)
        story_index = entry.get("story_index", 0)

        if story_index >= len(stories):
            continue
        story = stories[story_index]

        wall_key = f"{face_name}_{story.name}"
        wall_name = wall_names.get(wall_key)
        if not wall_name:
            continue  # no wall on this face for this storey

        # Compute offset along wall
        x1, y1, x2, y2 = faces[face_name]
        wlen = _wall_length(x1, y1, x2, y2)

        # Explicit offset takes precedence
        if "position_x" in entry:
            offset = entry["position_x"] - door_w / 2.0
        elif "position_offset" in entry:
            offset = entry["position_offset"]
        else:
            position = entry.get("position", "center")
            offset = _position_to_offset(position, wlen, door_w)

        if offset < 0:
            offset = 0.0
        if offset + door_w > wlen:
            offset = wlen - door_w

        # Build a descriptive name
        door_name = entry.get("name", f"{face_name.capitalize()} {door_type.replace('_', ' ').title()} {entry_idx + 1}")

        author.create_door(
            name=door_name,
            storey_name=story.name,
            wall_name=wall_name,
            offset_along_wall=offset,
            width=door_w,
            height=door_h,
            thickness=0.05,
        )
        doors_created += 1

    return doors_created


def _position_to_offset(position: str, wall_length: float, door_width: float) -> float:
    """Convert a named position to an offset along the wall."""
    if position == "center":
        return wall_length / 2.0 - door_width / 2.0
    elif position == "left_third":
        return wall_length / 3.0 - door_width / 2.0
    elif position == "right_third":
        return 2.0 * wall_length / 3.0 - door_width / 2.0
    else:
        # Default to center
        return wall_length / 2.0 - door_width / 2.0
