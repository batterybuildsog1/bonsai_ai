"""Patch five_story_mezzanine.ifc: add perimeter walls, doors, and windows.

The original build produced 0 doors and 0 windows because IFC door/window
elements require an IfcWall host, but the building uses all-curtain-wall envelope.

This script adds:
  - Thin backing walls on all 4 facades at every floor level (behind the curtain panels)
  - Main entrance door: south facade, ground floor, centred at x=20m, 2.4m × 2.8m
  - Service entrance door: north facade, ground floor, x=35m, 1.2m × 2.4m
  - Punched windows: east and west facades, floors 2–5, 1.8m × 1.5m, sill @0.9m,
    one per structural bay (4 bays at Y centres 3.125, 9.375, 15.625, 21.875m)

Building geometry:
  Footprint: X 0–40m, Y 0–25m
  South facade: y=0, runs X 0→40m
  North facade: y=25, runs X 0→40m
  East  facade: x=40, runs Y 0→25m
  West  facade: x=0,  runs Y 0→25m

Floor-to-floor heights:
  Level 1: base 0.0,  height 4.5m
  Level 2: base 4.5,  height 4.0m
  Level 3: base 8.5,  height 4.0m
  Level 4: base 12.5, height 4.0m
  Level 5: base 16.5, height 4.0m
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bonsai_ai.ifc_author import IfcAuthor

IFC_PATH = ROOT / "out" / "five_story_mezzanine" / "five_story_mezzanine.ifc"

WALL_THICKNESS = 0.15  # thin backing wall behind curtain panels

STOREYS = [
    ("Level 1", 0.0,  4.5),
    ("Level 2", 4.5,  4.0),
    ("Level 3", 8.5,  4.0),
    ("Level 4", 12.5, 4.0),
    ("Level 5", 16.5, 4.0),
]

# Y positions of structural bay centres on east/west facades
BAY_CENTRES_Y = [3.125, 9.375, 15.625, 21.875]


def main() -> None:
    print(f"Loading {IFC_PATH}")
    author = IfcAuthor(str(IFC_PATH))

    walls_added = 0
    doors_added = 0
    windows_added = 0
    errors = 0

    def _err(label: str, exc: Exception) -> None:
        nonlocal errors
        errors += 1
        print(f"  ERROR {label}: {exc}")

    # ------------------------------------------------------------------
    # 1. Perimeter walls — one per facade per floor
    # ------------------------------------------------------------------
    for storey, base_z, height in STOREYS:
        # South (y=0): x 0→40
        try:
            author.create_wall(
                name=f"{storey} South Perimeter Wall",
                storey_name=storey,
                start_x=0.0, start_y=0.0,
                end_x=40.0,  end_y=0.0,
                base_z=base_z, height=height,
                thickness=WALL_THICKNESS,
            )
            walls_added += 1
        except Exception as exc:
            _err(f"{storey} South Perimeter Wall", exc)

        # North (y=25): x 0→40
        try:
            author.create_wall(
                name=f"{storey} North Perimeter Wall",
                storey_name=storey,
                start_x=0.0, start_y=25.0,
                end_x=40.0,  end_y=25.0,
                base_z=base_z, height=height,
                thickness=WALL_THICKNESS,
            )
            walls_added += 1
        except Exception as exc:
            _err(f"{storey} North Perimeter Wall", exc)

        # East (x=40): y 0→25
        try:
            author.create_wall(
                name=f"{storey} East Perimeter Wall",
                storey_name=storey,
                start_x=40.0, start_y=0.0,
                end_x=40.0,   end_y=25.0,
                base_z=base_z, height=height,
                thickness=WALL_THICKNESS,
            )
            walls_added += 1
        except Exception as exc:
            _err(f"{storey} East Perimeter Wall", exc)

        # West (x=0): y 0→25
        try:
            author.create_wall(
                name=f"{storey} West Perimeter Wall",
                storey_name=storey,
                start_x=0.0, start_y=0.0,
                end_x=0.0,   end_y=25.0,
                base_z=base_z, height=height,
                thickness=WALL_THICKNESS,
            )
            walls_added += 1
        except Exception as exc:
            _err(f"{storey} West Perimeter Wall", exc)

    print(f"  {walls_added} perimeter walls added")

    # ------------------------------------------------------------------
    # 2. Doors — ground floor only
    # ------------------------------------------------------------------

    # Main entrance: south facade, centred at x=20m, 2.4m wide × 2.8m high
    # offset_along_wall = 20 - 2.4/2 = 18.8m from x=0 (wall start)
    try:
        author.create_door(
            name="Main Entrance Double Door",
            storey_name="Level 1",
            wall_name="Level 1 South Perimeter Wall",
            offset_along_wall=18.8,
            width=2.4,
            height=2.8,
            thickness=0.05,
        )
        doors_added += 1
    except Exception as exc:
        _err("Main Entrance Double Door", exc)

    # Service entrance: north facade, at x=35m, 1.2m wide × 2.4m high
    # offset_along_wall = 35m from x=0 (wall runs x 0→40)
    try:
        author.create_door(
            name="Service Entrance Door",
            storey_name="Level 1",
            wall_name="Level 1 North Perimeter Wall",
            offset_along_wall=35.0,
            width=1.2,
            height=2.4,
            thickness=0.05,
        )
        doors_added += 1
    except Exception as exc:
        _err("Service Entrance Door", exc)

    print(f"  {doors_added} doors added")

    # ------------------------------------------------------------------
    # 3. Windows — east and west facades, floors 2–5, 1 per bay
    # ------------------------------------------------------------------
    upper_storeys = [s for s in STOREYS if s[0] != "Level 1"]

    for storey, base_z, _h in upper_storeys:
        floor_num = storey.split()[-1]  # "2", "3", etc.

        for bay_idx, bay_y in enumerate(BAY_CENTRES_Y, start=1):
            # East facade wall runs y 0→25; offset = bay centre - window_half_width
            east_offset = bay_y - 0.9  # 1.8/2
            try:
                author.create_window(
                    name=f"Level {floor_num} East Window Bay {bay_idx}",
                    storey_name=storey,
                    wall_name=f"{storey} East Perimeter Wall",
                    offset_along_wall=east_offset,
                    sill_height=0.9,
                    width=1.8,
                    height=1.5,
                    thickness=0.05,
                )
                windows_added += 1
            except Exception as exc:
                _err(f"Level {floor_num} East Window Bay {bay_idx}", exc)

            # West facade wall runs y 0→25; same offsets
            try:
                author.create_window(
                    name=f"Level {floor_num} West Window Bay {bay_idx}",
                    storey_name=storey,
                    wall_name=f"{storey} West Perimeter Wall",
                    offset_along_wall=east_offset,
                    sill_height=0.9,
                    width=1.8,
                    height=1.5,
                    thickness=0.05,
                )
                windows_added += 1
            except Exception as exc:
                _err(f"Level {floor_num} West Window Bay {bay_idx}", exc)

    print(f"  {windows_added} windows added")

    # ------------------------------------------------------------------
    author.save()
    print(
        f"\nComplete: {walls_added} walls, {doors_added} doors, "
        f"{windows_added} windows added, {errors} errors"
    )
    print(author.debug_dump())


if __name__ == "__main__":
    main()
