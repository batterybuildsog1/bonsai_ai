"""Validation for building specs.

Catches the common issues that trip up the deterministic generators:
grid not fitting footprint, unreasonable dimensions, missing required
fields, inconsistent elevations, etc.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List


def validate_spec(spec: Dict[str, Any]) -> List[str]:
    """Validate a building spec. Returns a list of issues (empty = valid).

    This is the evaluator in the evaluator-optimizer pattern. The list of
    issues is fed back to the AI so it can revise the spec.
    """
    issues: List[str] = []

    # -----------------------------------------------------------------------
    # Required fields
    # -----------------------------------------------------------------------
    if not isinstance(spec, dict):
        return ["Spec must be a JSON object."]

    if "footprint" not in spec:
        issues.append("Missing required field 'footprint'.")
    if "stories" not in spec:
        issues.append("Missing required field 'stories'.")

    if issues:
        return issues  # Can't validate further without these

    # -----------------------------------------------------------------------
    # Footprint
    # -----------------------------------------------------------------------
    fp = spec["footprint"]
    if not isinstance(fp, dict):
        issues.append("'footprint' must be an object.")
        return issues

    length = fp.get("length")
    width = fp.get("width")

    if length is None or width is None:
        issues.append("Footprint must have 'length' and 'width'.")
        return issues

    if not isinstance(length, (int, float)) or not isinstance(width, (int, float)):
        issues.append("Footprint length and width must be numbers.")
        return issues

    if length < 3:
        issues.append(f"Footprint length {length}m is too small (minimum 3m).")
    if length > 500:
        issues.append(f"Footprint length {length}m is unusually large (maximum 500m).")
    if width < 3:
        issues.append(f"Footprint width {width}m is too small (minimum 3m).")
    if width > 500:
        issues.append(f"Footprint width {width}m is unusually large (maximum 500m).")

    # -----------------------------------------------------------------------
    # Stories
    # -----------------------------------------------------------------------
    stories = spec["stories"]
    if not isinstance(stories, list) or len(stories) == 0:
        issues.append("'stories' must be a non-empty array.")
        return issues

    valid_programs = {
        "retail", "office", "parking", "residential",
        "industrial", "mezzanine", "mechanical", "lobby", "warehouse",
    }

    cumulative_elevation = 0.0
    for i, story in enumerate(stories):
        if not isinstance(story, dict):
            issues.append(f"stories[{i}] must be an object.")
            continue

        height = story.get("height")
        if height is None:
            issues.append(f"stories[{i}] missing required 'height'.")
            continue
        if not isinstance(height, (int, float)):
            issues.append(f"stories[{i}] height must be a number.")
            continue
        if height < 2.0:
            issues.append(f"stories[{i}] height {height}m is too short (minimum 2.0m).")
        if height > 20.0:
            issues.append(f"stories[{i}] height {height}m is unusually tall (maximum 20.0m).")

        # Check elevation consistency if provided
        if "elevation" in story:
            expected = round(cumulative_elevation, 6)
            actual = story["elevation"]
            if isinstance(actual, (int, float)) and abs(actual - expected) > 0.01:
                issues.append(
                    f"stories[{i}] elevation {actual}m does not match cumulative "
                    f"height {expected}m. Remove elevation or fix story heights."
                )

        program = story.get("program")
        if program is not None and program not in valid_programs:
            issues.append(
                f"stories[{i}] program '{program}' is not valid. "
                f"Must be one of: {', '.join(sorted(valid_programs))}."
            )

        if isinstance(height, (int, float)):
            cumulative_elevation += height

    # -----------------------------------------------------------------------
    # Grid fits footprint
    # -----------------------------------------------------------------------
    if "grid" in spec and isinstance(spec["grid"], dict):
        grid = spec["grid"]

        for axis, dim_name, dim_value in [
            ("x", "length", length),
            ("y", "width", width),
        ]:
            spacing_key = f"spacing_{axis}"
            bays_key = f"bays_{axis}"

            if spacing_key in grid and bays_key not in grid:
                spacing = grid[spacing_key]
                if isinstance(spacing, (int, float)) and spacing > 0 and isinstance(dim_value, (int, float)) and dim_value > 0:
                    bays = dim_value / spacing
                    remainder = abs(bays - round(bays))
                    if remainder > 0.01:
                        suggested_bays = round(bays)
                        if suggested_bays < 1:
                            suggested_bays = 1
                        suggested_spacing = round(dim_value / suggested_bays, 4)
                        issues.append(
                            f"Grid spacing_{axis} {spacing}m does not divide evenly into "
                            f"footprint {dim_name} {dim_value}m "
                            f"({dim_value}/{spacing} = {bays:.3f} bays). "
                            f"Suggest spacing_{axis}={suggested_spacing}m for {suggested_bays} even bays."
                        )
                    if spacing < 2.0:
                        issues.append(f"Grid spacing_{axis} {spacing}m is unusually small (minimum 2m).")
                    if spacing > 20.0:
                        issues.append(f"Grid spacing_{axis} {spacing}m is unusually large (maximum 20m).")

            if bays_key in grid:
                bays_val = grid[bays_key]
                if isinstance(bays_val, (int, float)) and isinstance(dim_value, (int, float)):
                    if bays_val < 1:
                        issues.append(f"Grid {bays_key} must be at least 1.")
                    elif dim_value > 0:
                        effective_spacing = dim_value / bays_val
                        if effective_spacing < 2.0:
                            issues.append(
                                f"Grid {bays_key}={bays_val} produces {effective_spacing:.2f}m spacing "
                                f"(unusually small for footprint {dim_name}={dim_value}m)."
                            )
                        if effective_spacing > 20.0:
                            issues.append(
                                f"Grid {bays_key}={bays_val} produces {effective_spacing:.2f}m spacing "
                                f"(unusually large for footprint {dim_name}={dim_value}m)."
                            )

    # -----------------------------------------------------------------------
    # Structure
    # -----------------------------------------------------------------------
    if "structure" in spec and isinstance(spec["structure"], dict):
        structure = spec["structure"]
        valid_frame_types = {"braced", "moment", "rigid", "post_and_beam"}
        frame_type = structure.get("frame_type")
        if frame_type is not None and frame_type not in valid_frame_types:
            issues.append(
                f"structure.frame_type '{frame_type}' is not valid. "
                f"Must be one of: {', '.join(sorted(valid_frame_types))}."
            )

        slab_t = structure.get("slab_thickness")
        if slab_t is not None and isinstance(slab_t, (int, float)):
            if slab_t < 0.05:
                issues.append(f"structure.slab_thickness {slab_t}m is too thin (minimum 0.05m).")
            if slab_t > 1.0:
                issues.append(f"structure.slab_thickness {slab_t}m is unusually thick (maximum 1.0m).")

        valid_roof_types = {"flat_slab", "standing_seam", "metal_deck", "concrete"}
        roof_type = structure.get("roof_type")
        if roof_type is not None and roof_type not in valid_roof_types:
            issues.append(
                f"structure.roof_type '{roof_type}' is not valid. "
                f"Must be one of: {', '.join(sorted(valid_roof_types))}."
            )

    # -----------------------------------------------------------------------
    # Facades
    # -----------------------------------------------------------------------
    if "facades" in spec and isinstance(spec["facades"], dict):
        valid_faces = {"north", "south", "east", "west"}
        valid_facade_types = {"wall", "curtain_wall", "panel_array"}
        valid_window_patterns = {"per_bay", "ribbon", "none"}

        for face_name, fspec in spec["facades"].items():
            if face_name not in valid_faces:
                issues.append(f"facades.{face_name} is not a valid face (north/south/east/west).")
                continue
            if not isinstance(fspec, dict):
                continue

            ftype = fspec.get("type")
            if ftype is not None and ftype not in valid_facade_types:
                issues.append(
                    f"facades.{face_name}.type '{ftype}' is not valid. "
                    f"Must be one of: {', '.join(sorted(valid_facade_types))}."
                )

            windows = fspec.get("windows")
            if isinstance(windows, dict):
                pattern = windows.get("pattern")
                if pattern is not None and pattern not in valid_window_patterns:
                    issues.append(
                        f"facades.{face_name}.windows.pattern '{pattern}' is not valid. "
                        f"Must be one of: {', '.join(sorted(valid_window_patterns))}."
                    )

    # -----------------------------------------------------------------------
    # Entries
    # -----------------------------------------------------------------------
    if "entries" in spec and isinstance(spec["entries"], list):
        valid_entry_types = {"single", "double", "revolving", "overhead", "service"}

        for i, entry in enumerate(spec["entries"]):
            if not isinstance(entry, dict):
                issues.append(f"entries[{i}] must be an object.")
                continue

            face = entry.get("face")
            if face is None:
                issues.append(f"entries[{i}] missing required 'face'.")
            elif face not in {"north", "south", "east", "west"}:
                issues.append(f"entries[{i}].face '{face}' is not valid (north/south/east/west).")

            entry_type = entry.get("type")
            if entry_type is not None and entry_type not in valid_entry_types:
                issues.append(
                    f"entries[{i}].type '{entry_type}' is not valid. "
                    f"Must be one of: {', '.join(sorted(valid_entry_types))}."
                )

            # Check entry position is within wall length
            if face and isinstance(length, (int, float)) and isinstance(width, (int, float)):
                wall_length = length if face in ("north", "south") else width
                entry_width = entry.get("width", 2.0)
                offset = entry.get("position_offset")
                if isinstance(offset, (int, float)) and isinstance(entry_width, (int, float)):
                    if offset < 0 or offset + entry_width > wall_length:
                        issues.append(
                            f"entries[{i}] position_offset {offset}m + width {entry_width}m "
                            f"exceeds {face} wall length {wall_length}m."
                        )

            story_index = entry.get("story_index", 0)
            if isinstance(story_index, int) and isinstance(stories, list):
                if story_index < 0 or story_index >= len(stories):
                    issues.append(
                        f"entries[{i}].story_index {story_index} is out of range "
                        f"(building has {len(stories)} stories)."
                    )

    # -----------------------------------------------------------------------
    # Mezzanines
    # -----------------------------------------------------------------------
    if "mezzanines" in spec and isinstance(spec["mezzanines"], list):
        for i, mezz in enumerate(spec["mezzanines"]):
            if not isinstance(mezz, dict):
                issues.append(f"mezzanines[{i}] must be an object.")
                continue
            si = mezz.get("story_index")
            if si is None:
                issues.append(f"mezzanines[{i}] missing required 'story_index'.")
            elif isinstance(si, int) and isinstance(stories, list):
                if si < 0 or si >= len(stories):
                    issues.append(
                        f"mezzanines[{i}].story_index {si} is out of range "
                        f"(building has {len(stories)} stories)."
                    )
            depth = mezz.get("depth")
            if depth is not None and isinstance(depth, (int, float)):
                if isinstance(width, (int, float)) and depth > width:
                    issues.append(
                        f"mezzanines[{i}].depth {depth}m exceeds building width {width}m."
                    )

    # -----------------------------------------------------------------------
    # Total building height sanity
    # -----------------------------------------------------------------------
    if isinstance(stories, list) and all(isinstance(s, dict) and isinstance(s.get("height"), (int, float)) for s in stories):
        total_height = sum(s["height"] for s in stories)
        if total_height > 200:
            issues.append(f"Total building height {total_height}m is unusually tall (> 200m).")

    return issues
