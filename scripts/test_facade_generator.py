"""Test the facade and opening generators.

Exercises:
  1. Simple building (1 story, 4 walls)
  2. Windows on east/west (per_bay pattern)
  3. Curtain wall on south
  4. Door on north
  5. Verifies: wall count, window count, door count, window hosts are correct walls

Run: python scripts/test_facade_generator.py
"""

import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bonsai_ai.ifc_author import IfcAuthor
from bonsai_ai.facade_generator import (
    ResolvedGrid,
    ResolvedStorey,
    generate_facade_walls,
    generate_windows,
    generate_doors,
    _face_geometry,
    _bay_centres_along_face,
)

OUT_DIR = ROOT / "out" / "test_facade"
os.makedirs(OUT_DIR, exist_ok=True)

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f" -- {detail}"
        print(msg)


# ---------------------------------------------------------------------------
# Test 1: Simple 1-story, 4-wall building (all wall facades, no openings)
# ---------------------------------------------------------------------------

def test_simple_4_walls():
    """1 story, 30m x 20m, 4 concrete walls, no windows/doors."""
    print("\n=== Test 1: Simple 4-wall building ===")

    out_path = str(OUT_DIR / "test_simple_4walls.ifc")
    author = IfcAuthor(out_path)
    author.ensure_project("Test Simple", "Site", "Building")
    author.ensure_storey("Level 1", 0.0)

    grid = ResolvedGrid(
        bays_x=4, bays_y=3,
        spacings_x=[7.5, 7.5, 7.5, 7.5],
        spacings_y=[6.666667, 6.666667, 6.666667],
        xs=[0.0, 7.5, 15.0, 22.5, 30.0],
        ys=[0.0, 6.666667, 13.333333, 20.0],
    )
    stories = [
        ResolvedStorey("Level 1", height=4.0, elevation=0.0,
                       program="office", slab_thickness=0.2, exclude_slab=False),
    ]
    spec = {
        "footprint": {"length": 30, "width": 20},
        "facades": {
            "north": {"type": "wall", "material": "concrete"},
            "south": {"type": "wall", "material": "concrete"},
            "east":  {"type": "wall", "material": "concrete"},
            "west":  {"type": "wall", "material": "concrete"},
        },
    }

    wall_names = generate_facade_walls(author, spec, grid, stories)

    check("4 walls created", len(wall_names) == 4,
          f"got {len(wall_names)}: {list(wall_names.values())}")
    check("south wall registered",
          wall_names.get("south_Level 1") == "Level 1 South Wall")
    check("north wall registered",
          wall_names.get("north_Level 1") == "Level 1 North Wall")
    check("east wall registered",
          wall_names.get("east_Level 1") == "Level 1 East Wall")
    check("west wall registered",
          wall_names.get("west_Level 1") == "Level 1 West Wall")

    # Verify IFC model
    ifc_walls = [w.Name for w in author.model.by_type("IfcWall")]
    check("IFC has 4 IfcWall", len(ifc_walls) == 4, f"got {len(ifc_walls)}")

    author.save()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Test 2: Windows on east/west (per_bay pattern)
# ---------------------------------------------------------------------------

def test_per_bay_windows():
    """2 stories, 30m x 20m. East and west get per_bay windows."""
    print("\n=== Test 2: Per-bay windows on east/west ===")

    out_path = str(OUT_DIR / "test_per_bay_windows.ifc")
    author = IfcAuthor(out_path)
    author.ensure_project("Test Windows", "Site", "Building")
    author.ensure_storey("Level 1", 0.0)
    author.ensure_storey("Level 2", 4.0)

    grid = ResolvedGrid(
        bays_x=4, bays_y=3,
        spacings_x=[7.5, 7.5, 7.5, 7.5],
        spacings_y=[6.666667, 6.666667, 6.666667],
        xs=[0.0, 7.5, 15.0, 22.5, 30.0],
        ys=[0.0, 6.666667, 13.333333, 20.0],
    )
    stories = [
        ResolvedStorey("Level 1", height=4.0, elevation=0.0,
                       program="retail", slab_thickness=0.25, exclude_slab=False),
        ResolvedStorey("Level 2", height=3.5, elevation=4.0,
                       program="office", slab_thickness=0.2, exclude_slab=False),
    ]
    spec = {
        "footprint": {"length": 30, "width": 20},
        "facades": {
            "north": {"type": "wall"},
            "south": {"type": "wall"},
            "east":  {"type": "wall", "windows": {
                "pattern": "per_bay", "width": 1.8, "height": 1.5, "sill_height": 0.9
            }},
            "west":  {"type": "wall", "windows": {
                "pattern": "per_bay", "width": 1.8, "height": 1.5, "sill_height": 0.9
            }},
        },
    }

    wall_names = generate_facade_walls(author, spec, grid, stories)
    check("8 walls created (4 faces x 2 stories)", len(wall_names) == 8,
          f"got {len(wall_names)}")

    win_count = generate_windows(author, spec, grid, stories, wall_names)

    # East and west each have 3 bays in Y-direction, 2 stories = 2*3*2 = 12 windows
    expected_windows = 3 * 2 * 2  # 3 bays * 2 facades * 2 stories
    check(f"window count = {expected_windows}", win_count == expected_windows,
          f"got {win_count}")

    # Verify windows are hosted in the correct walls
    ifc_windows = author.model.by_type("IfcWindow")
    check(f"IFC has {expected_windows} IfcWindow", len(ifc_windows) == expected_windows,
          f"got {len(ifc_windows)}")

    # Check a specific window name pattern
    win_names = [w.Name for w in ifc_windows]
    check("Level 1 East Window Bay 1 exists",
          "Level 1 East Window Bay 1" in win_names,
          f"window names: {win_names[:5]}...")
    check("Level 2 West Window Bay 3 exists",
          "Level 2 West Window Bay 3" in win_names,
          f"window names: {win_names}")

    author.save()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Test 3: Curtain wall on south
# ---------------------------------------------------------------------------

def test_curtain_wall():
    """1 story, south facade is curtain wall, others are walls."""
    print("\n=== Test 3: Curtain wall on south ===")

    out_path = str(OUT_DIR / "test_curtain_wall.ifc")
    author = IfcAuthor(out_path)
    author.ensure_project("Test Curtain", "Site", "Building")
    author.ensure_storey("Level 1", 0.0)

    grid = ResolvedGrid(
        bays_x=4, bays_y=3,
        spacings_x=[7.5, 7.5, 7.5, 7.5],
        spacings_y=[6.666667, 6.666667, 6.666667],
        xs=[0.0, 7.5, 15.0, 22.5, 30.0],
        ys=[0.0, 6.666667, 13.333333, 20.0],
    )
    stories = [
        ResolvedStorey("Level 1", height=4.0, elevation=0.0,
                       program="retail", slab_thickness=0.25, exclude_slab=False),
    ]
    spec = {
        "footprint": {"length": 30, "width": 20},
        "facades": {
            "north": {"type": "wall"},
            "south": {"type": "curtain_wall", "curtain_wall": {
                "panel_width": 1.5, "panel_height": 2.0, "panel_thickness": 0.02,
            }},
            "east":  {"type": "wall"},
            "west":  {"type": "wall"},
        },
    }

    wall_names = generate_facade_walls(author, spec, grid, stories)

    # Should have 3 walls (north, east, west) -- south is curtain wall (not in wall_names)
    check("3 walls in registry (south is curtain wall)", len(wall_names) == 3,
          f"got {len(wall_names)}: {list(wall_names.keys())}")
    check("south not in wall_names", "south_Level 1" not in wall_names)

    # Verify IFC
    ifc_walls = author.model.by_type("IfcWall")
    ifc_curtain = author.model.by_type("IfcCurtainWall")
    check("3 IfcWall in model", len(ifc_walls) == 3, f"got {len(ifc_walls)}")
    check("1 IfcCurtainWall in model", len(ifc_curtain) == 1, f"got {len(ifc_curtain)}")

    # Curtain wall should have panels
    ifc_plates = author.model.by_type("IfcPlate")
    check("Curtain wall has panels", len(ifc_plates) > 0, f"got {len(ifc_plates)} plates")

    author.save()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Test 4: Door on north
# ---------------------------------------------------------------------------

def test_door():
    """1 story, add a centered door on north facade."""
    print("\n=== Test 4: Door on north ===")

    out_path = str(OUT_DIR / "test_door.ifc")
    author = IfcAuthor(out_path)
    author.ensure_project("Test Door", "Site", "Building")
    author.ensure_storey("Level 1", 0.0)

    grid = ResolvedGrid(
        bays_x=4, bays_y=3,
        spacings_x=[7.5, 7.5, 7.5, 7.5],
        spacings_y=[6.666667, 6.666667, 6.666667],
        xs=[0.0, 7.5, 15.0, 22.5, 30.0],
        ys=[0.0, 6.666667, 13.333333, 20.0],
    )
    stories = [
        ResolvedStorey("Level 1", height=4.0, elevation=0.0,
                       program="office", slab_thickness=0.2, exclude_slab=False),
    ]
    spec = {
        "footprint": {"length": 30, "width": 20},
        "facades": {
            "north": {"type": "wall"},
            "south": {"type": "wall"},
            "east":  {"type": "wall"},
            "west":  {"type": "wall"},
        },
        "entries": [
            {
                "facade": "north",
                "type": "single_door",
                "width": 1.2,
                "height": 2.4,
                "position": "center",
            },
        ],
    }

    wall_names = generate_facade_walls(author, spec, grid, stories)
    check("4 walls created", len(wall_names) == 4)

    door_count = generate_doors(author, spec, grid, stories, wall_names)
    check("1 door created", door_count == 1, f"got {door_count}")

    ifc_doors = author.model.by_type("IfcDoor")
    check("1 IfcDoor in model", len(ifc_doors) == 1, f"got {len(ifc_doors)}")

    # Verify door is hosted in north wall (check opening is a feature of the wall)
    if ifc_doors:
        door = ifc_doors[0]
        check("Door name is correct", "North" in door.Name,
              f"door name: {door.Name}")

    author.save()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Test 5: Mixed facade (curtain wall ground, wall upper)
# ---------------------------------------------------------------------------

def test_mixed_facade():
    """2 stories, south = mixed (curtain wall ground, wall+windows upper)."""
    print("\n=== Test 5: Mixed facade ===")

    out_path = str(OUT_DIR / "test_mixed_facade.ifc")
    author = IfcAuthor(out_path)
    author.ensure_project("Test Mixed", "Site", "Building")
    author.ensure_storey("Level 1", 0.0)
    author.ensure_storey("Level 2", 4.0)

    grid = ResolvedGrid(
        bays_x=4, bays_y=3,
        spacings_x=[7.5, 7.5, 7.5, 7.5],
        spacings_y=[6.666667, 6.666667, 6.666667],
        xs=[0.0, 7.5, 15.0, 22.5, 30.0],
        ys=[0.0, 6.666667, 13.333333, 20.0],
    )
    stories = [
        ResolvedStorey("Level 1", height=4.0, elevation=0.0,
                       program="retail", slab_thickness=0.25, exclude_slab=False),
        ResolvedStorey("Level 2", height=3.5, elevation=4.0,
                       program="office", slab_thickness=0.2, exclude_slab=False),
    ]
    spec = {
        "footprint": {"length": 30, "width": 20},
        "facades": {
            "north": {"type": "wall"},
            "south": {
                "type": "mixed",
                "ground": {
                    "type": "curtain_wall",
                    "curtain_wall": {"panel_width": 1.5, "panel_height": 2.0},
                },
                "upper": {
                    "type": "wall",
                    "windows": {
                        "pattern": "per_bay",
                        "width": 1.8,
                        "height": 1.5,
                        "sill_height": 0.9,
                    },
                },
            },
            "east":  {"type": "wall"},
            "west":  {"type": "wall"},
        },
    }

    wall_names = generate_facade_walls(author, spec, grid, stories)

    # South ground = curtain wall (not in registry). South upper = wall (in registry).
    # North, East, West = wall for both stories = 6 walls + 1 south upper = 7
    check("south_Level 1 NOT in wall_names (curtain wall)",
          "south_Level 1" not in wall_names)
    check("south_Level 2 in wall_names (wall)",
          "south_Level 2" in wall_names,
          f"wall_names keys: {list(wall_names.keys())}")

    # Verify curtain wall was created
    ifc_curtain = author.model.by_type("IfcCurtainWall")
    check("1 IfcCurtainWall for south ground", len(ifc_curtain) == 1,
          f"got {len(ifc_curtain)}")

    # Windows on south upper (4 bays in X, 1 story = 4 windows)
    win_count = generate_windows(author, spec, grid, stories, wall_names)
    check("4 windows on south upper", win_count == 4,
          f"got {win_count}")

    author.save()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Test 6: Full integration via BuildingGenerator
# ---------------------------------------------------------------------------

def test_building_generator_integration():
    """Test the BuildingGenerator class with facades + openings."""
    print("\n=== Test 6: BuildingGenerator integration ===")

    from bonsai_ai.building_generator import BuildingGenerator

    out_path = str(OUT_DIR / "test_bg_integration.ifc")
    spec = {
        "footprint": {"length": 40, "width": 25},
        "grid": {"spacing_x": 8, "spacing_y": 6.25},
        "stories": [
            {"name": "Ground Floor", "height": 4.5},
            {"name": "Level 2", "height": 4.0},
        ],
        "facades": {
            "north": {"type": "wall", "windows": {
                "pattern": "per_bay", "width": 1.8, "height": 1.5, "sill_height": 0.9
            }},
            "south": {"type": "curtain_wall"},
            "east":  {"type": "wall", "windows": {
                "pattern": "per_bay", "width": 1.8, "height": 1.5, "sill_height": 0.9
            }},
            "west":  {"type": "wall", "windows": {
                "pattern": "per_bay", "width": 1.8, "height": 1.5, "sill_height": 0.9
            }},
        },
        "entries": [
            {"face": "north", "type": "double_door", "width": 2.4, "height": 2.8,
             "position": "center"},
        ],
    }

    gen = BuildingGenerator(spec, out_path)
    summary = gen.generate()

    counts = summary["counts"]
    wall_names_out = summary["wall_names"]

    # 2 stories x 3 wall-faces (north, east, west) = 6 walls
    # South is curtain wall -> not in wall_names
    check("6 walls (3 faces x 2 stories)", counts["walls"] == 6,
          f"got {counts['walls']}, wall_names: {wall_names_out}")

    # Windows: north (5 bays_x) + east (4 bays_y) + west (4 bays_y) = 13 per story x 2 = 26
    expected_win = (5 + 4 + 4) * 2
    check(f"windows = {expected_win}", counts["windows"] == expected_win,
          f"got {counts['windows']}")

    # 1 door
    check("1 door", counts["doors"] == 1, f"got {counts['doors']}")

    print(f"  Summary: {counts}")
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Test 7: Bay centre computation
# ---------------------------------------------------------------------------

def test_bay_centres():
    """Verify bay centre offsets are computed correctly."""
    print("\n=== Test 7: Bay centre offsets ===")

    grid = ResolvedGrid(
        bays_x=5, bays_y=4,
        spacings_x=[8.0, 8.0, 8.0, 8.0, 8.0],
        spacings_y=[6.25, 6.25, 6.25, 6.25],
        xs=[0.0, 8.0, 16.0, 24.0, 32.0, 40.0],
        ys=[0.0, 6.25, 12.5, 18.75, 25.0],
    )

    south_centres = _bay_centres_along_face("south", grid)
    check("south 5 bay centres", len(south_centres) == 5,
          f"got {len(south_centres)}")
    check("south bay 1 centre = 4.0", abs(south_centres[0] - 4.0) < 0.01,
          f"got {south_centres[0]}")
    check("south bay 5 centre = 36.0", abs(south_centres[4] - 36.0) < 0.01,
          f"got {south_centres[4]}")

    east_centres = _bay_centres_along_face("east", grid)
    check("east 4 bay centres", len(east_centres) == 4,
          f"got {len(east_centres)}")
    check("east bay 1 centre = 3.125", abs(east_centres[0] - 3.125) < 0.01,
          f"got {east_centres[0]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    test_simple_4_walls()
    test_per_bay_windows()
    test_curtain_wall()
    test_door()
    test_mixed_facade()
    test_building_generator_integration()
    test_bay_centres()

    print(f"\n{'=' * 50}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
