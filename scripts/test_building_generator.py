"""Test the BuildingGenerator with 3 building specs.

Specs:
  1. Simple warehouse  -- 1 story, 30x20m
  2. Medium office      -- 2 stories, 20x15m
  3. 5-story commercial -- 5 stories, 40x25m

Verifies:
  - Element counts match expectations
  - Grid covers the full footprint (no 1m gaps)
  - Bounding box matches footprint
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bonsai_ai.building_generator import BuildingGenerator

OUT_DIR = ROOT / "out" / "tests" / "building_generator"


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

WAREHOUSE_SPEC = {
    "footprint": {"length": 30, "width": 20},
    "grid": {"spacing_x": 10, "spacing_y": 10},
    "stories": [
        {"name": "Ground Floor", "height": 6.0, "elevation": 0},
    ],
    "structure": {
        "column_size": [0.4, 0.4],
        "beam_size": [0.3, 0.6],
        "slab_thickness": 0.25,
    },
    "walls": {
        "thickness": 0.25,
        "facades": ["north", "south", "east", "west"],
    },
}

OFFICE_SPEC = {
    "footprint": {"length": 20, "width": 15},
    "grid": {"spacing_x": 5, "spacing_y": 5},
    "stories": [
        {"name": "Ground Floor", "height": 4.0, "elevation": 0},
        {"name": "Level 2", "height": 3.5, "elevation": 4.0},
    ],
    "structure": {
        "column_size": [0.3, 0.3],
        "beam_size": [0.25, 0.45],
        "slab_thickness": 0.2,
    },
    "walls": {
        "thickness": 0.2,
        "facades": ["north", "south", "east", "west"],
    },
}

COMMERCIAL_SPEC = {
    "footprint": {"length": 40, "width": 25},
    "grid": {"spacing_x": 8, "spacing_y": 8.33},
    "stories": [
        {"name": "Level 1", "height": 4.5, "elevation": 0},
        {"name": "Level 2", "height": 4.0, "elevation": 4.5},
        {"name": "Level 3", "height": 4.0, "elevation": 8.5},
        {"name": "Level 4", "height": 4.0, "elevation": 12.5},
        {"name": "Level 5", "height": 4.0, "elevation": 16.5},
    ],
    "structure": {
        "column_size": [0.3, 0.3],
        "beam_size": [0.3, 0.5],
        "slab_thickness": 0.2,
    },
    "walls": {
        "thickness": 0.2,
        "facades": ["north", "south", "east", "west"],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


def _assert_close(actual: float, expected: float, msg: str, tol: float = 0.01) -> None:
    if abs(actual - expected) > tol:
        raise AssertionError(f"{msg}: expected {expected}, got {actual}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_warehouse() -> dict:
    """1-story warehouse: 30x20m, 10m grid -> 3x2 bays."""
    print("\n=== Warehouse (1 story, 30x20m) ===")
    path = str(OUT_DIR / "warehouse.ifc")
    gen = BuildingGenerator(WAREHOUSE_SPEC, path)
    summary = gen.generate()

    # Grid: 30/10=3 bays X, 20/10=2 bays Y -> 4x3=12 gridpoints
    _assert(summary["grid"]["bays_x"] == 3, f"bays_x should be 3, got {summary['grid']['bays_x']}")
    _assert(summary["grid"]["bays_y"] == 2, f"bays_y should be 2, got {summary['grid']['bays_y']}")

    # Grid covers full footprint
    xs = summary["grid"]["xs"]
    ys = summary["grid"]["ys"]
    _assert_close(xs[0], 0.0, "xs[0]")
    _assert_close(xs[-1], 30.0, "xs[-1]")
    _assert_close(ys[0], 0.0, "ys[0]")
    _assert_close(ys[-1], 20.0, "ys[-1]")

    # Element counts: 1 story
    counts = summary["counts"]
    _assert(counts["storeys"] == 1, f"storeys: {counts['storeys']}")
    _assert(counts["columns"] == 4 * 3, f"columns: {counts['columns']} (expect 12)")  # (3+1)*(2+1)
    _assert(counts["slabs"] == 1, f"slabs: {counts['slabs']}")
    _assert(counts["walls"] == 4, f"walls: {counts['walls']}")

    # Beams: X-dir: 3 rows * 3 spans = 9, Y-dir: 4 cols * 2 spans = 8 -> 17
    expected_beams = 3 * 3 + 4 * 2  # (bays_y+1)*bays_x + (bays_x+1)*bays_y
    _assert(counts["beams"] == expected_beams, f"beams: {counts['beams']} (expect {expected_beams})")

    print(f"  Counts: {counts}")
    print(f"  Grid: {summary['grid']['bays_x']}x{summary['grid']['bays_y']} bays")
    print(f"  PASS")
    return summary


def test_office() -> dict:
    """2-story office: 20x15m, 5m grid -> 4x3 bays."""
    print("\n=== Office (2 stories, 20x15m) ===")
    path = str(OUT_DIR / "office.ifc")
    gen = BuildingGenerator(OFFICE_SPEC, path)
    summary = gen.generate()

    # Grid: 20/5=4 bays X, 15/5=3 bays Y
    _assert(summary["grid"]["bays_x"] == 4, f"bays_x: {summary['grid']['bays_x']}")
    _assert(summary["grid"]["bays_y"] == 3, f"bays_y: {summary['grid']['bays_y']}")

    # Grid covers full footprint
    xs = summary["grid"]["xs"]
    ys = summary["grid"]["ys"]
    _assert_close(xs[-1], 20.0, "xs[-1]")
    _assert_close(ys[-1], 15.0, "ys[-1]")

    # 2 stories -> 2x each element type
    counts = summary["counts"]
    _assert(counts["storeys"] == 2, f"storeys: {counts['storeys']}")
    _assert(counts["columns"] == 2 * 5 * 4, f"columns: {counts['columns']} (expect 40)")  # 2*(4+1)*(3+1)
    _assert(counts["slabs"] == 2, f"slabs: {counts['slabs']}")
    _assert(counts["walls"] == 8, f"walls: {counts['walls']} (expect 8)")  # 2*4

    # Beams per story: X-dir: 4 rows * 4 spans = 16, Y-dir: 5 cols * 3 spans = 15 -> 31
    beams_per_story = 4 * 4 + 5 * 3  # (bays_y+1)*bays_x + (bays_x+1)*bays_y
    _assert(counts["beams"] == 2 * beams_per_story,
            f"beams: {counts['beams']} (expect {2 * beams_per_story})")

    print(f"  Counts: {counts}")
    print(f"  PASS")
    return summary


def test_commercial() -> dict:
    """5-story commercial: 40x25m, 8/8.33m grid -> 5x3 bays."""
    print("\n=== Commercial (5 stories, 40x25m) ===")
    path = str(OUT_DIR / "commercial.ifc")
    gen = BuildingGenerator(COMMERCIAL_SPEC, path)
    summary = gen.generate()

    # Grid: 40/8=5 bays X, 25/8.33=3 bays Y
    _assert(summary["grid"]["bays_x"] == 5, f"bays_x: {summary['grid']['bays_x']}")
    _assert(summary["grid"]["bays_y"] == 3, f"bays_y: {summary['grid']['bays_y']}")

    # Grid FITS the footprint exactly (no 1m gaps)
    xs = summary["grid"]["xs"]
    ys = summary["grid"]["ys"]
    _assert_close(xs[0], 0.0, "xs[0]")
    _assert_close(xs[-1], 40.0, "xs[-1]")
    _assert_close(ys[0], 0.0, "ys[0]")
    _assert_close(ys[-1], 25.0, "ys[-1]")

    # Adjusted spacing: 40/5=8.0, 25/3=8.333...
    _assert_close(summary["grid"]["spacing_x"], 8.0, "spacing_x")
    _assert_close(summary["grid"]["spacing_y"], 25.0 / 3.0, "spacing_y", tol=0.01)

    # 5 stories
    counts = summary["counts"]
    _assert(counts["storeys"] == 5, f"storeys: {counts['storeys']}")

    # Columns: 5 * (5+1)*(3+1) = 5 * 24 = 120
    _assert(counts["columns"] == 5 * 6 * 4,
            f"columns: {counts['columns']} (expect {5 * 6 * 4})")

    # Slabs: 5
    _assert(counts["slabs"] == 5, f"slabs: {counts['slabs']}")

    # Walls: 5 * 4 = 20
    _assert(counts["walls"] == 20, f"walls: {counts['walls']} (expect 20)")

    # Beams per story: X-dir: 4 rows * 5 spans = 20, Y-dir: 6 cols * 3 spans = 18 -> 38
    beams_per_story = 4 * 5 + 6 * 3  # (bays_y+1)*bays_x + (bays_x+1)*bays_y
    _assert(counts["beams"] == 5 * beams_per_story,
            f"beams: {counts['beams']} (expect {5 * beams_per_story})")

    print(f"  Counts: {counts}")
    print(f"  Grid xs: {xs}")
    print(f"  Grid ys: {ys}")
    print(f"  PASS")
    return summary


def test_grid_coverage() -> None:
    """Verify that grid spacing is adjusted to fit, not truncated."""
    print("\n=== Grid Coverage Test ===")

    # Worst case: 25m / 8m target = 3.125 -> rounds to 3 -> 25/3 = 8.333m
    spec = {
        "footprint": {"length": 25, "width": 25},
        "grid": {"spacing_x": 8, "spacing_y": 8},
        "stories": [{"name": "Test", "height": 3.0}],
    }
    path = str(OUT_DIR / "grid_coverage.ifc")
    gen = BuildingGenerator(spec, path)
    summary = gen.generate()

    xs = summary["grid"]["xs"]
    ys = summary["grid"]["ys"]

    # Must reach 25.0 exactly
    _assert_close(xs[-1], 25.0, "xs[-1] must be 25.0, not 24.0")
    _assert_close(ys[-1], 25.0, "ys[-1] must be 25.0, not 24.0")

    # 25/8 = 3.125, rounds to 3 bays -> spacing = 25/3 = 8.333
    _assert(summary["grid"]["bays_x"] == 3, f"bays_x: {summary['grid']['bays_x']}")
    _assert_close(summary["grid"]["spacing_x"], 25.0 / 3.0, "spacing_x")

    print(f"  Grid: {summary['grid']['bays_x']}x{summary['grid']['bays_y']} bays")
    print(f"  Spacing: {summary['grid']['spacing_x']:.4f} x {summary['grid']['spacing_y']:.4f}")
    print(f"  xs: {xs}")
    print(f"  PASS")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    passed = 0
    failed = 0

    for test_fn in [test_warehouse, test_office, test_commercial, test_grid_coverage]:
        try:
            test_fn()
            passed += 1
        except (AssertionError, Exception) as exc:
            print(f"  FAIL: {exc}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        print("SOME TESTS FAILED")
        return 1
    else:
        print("ALL TESTS PASSED")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
