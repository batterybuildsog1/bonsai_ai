"""Patch five_story_mezzanine.ifc: add full structural beam grid.

The original build only produced 40 beams (edge-only from generate_floor_plate,
several placed outside the building footprint). This script adds the complete
grid: X-direction beams along every row and Y-direction beams along every column,
at every floor level.

Grid (from actual IFC column positions):
  X: 0, 8, 16, 24, 32, 40  (6 columns, 5 bays of 8m)
  Y: 0, 6.25, 12.5, 18.75, 25.0  (5 rows, 4 bays)

Storeys:
  Level 1 @ 0.0m, Level 2 @ 4.5m, Level 3 @ 8.5m, Level 4 @ 12.5m, Level 5 @ 16.5m

Beam section: 0.3m wide × 0.5m deep (W-section equivalent), per design spec.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bonsai_ai.ifc_author import IfcAuthor

IFC_PATH = ROOT / "out" / "five_story_mezzanine" / "five_story_mezzanine.ifc"

# Actual column grid positions (from IFC column query)
XS = [0.0, 8.0, 16.0, 24.0, 32.0, 40.0]
YS = [0.0, 6.25, 12.5, 18.75, 25.0]

STOREYS = [
    ("Level 1", 0.0),
    ("Level 2", 4.5),
    ("Level 3", 8.5),
    ("Level 4", 12.5),
    ("Level 5", 16.5),
]

BEAM_WIDTH = 0.3
BEAM_DEPTH = 0.5


def main() -> None:
    print(f"Loading {IFC_PATH}")
    author = IfcAuthor(str(IFC_PATH))

    added = 0
    errors = 0

    for storey_name, elev in STOREYS:
        # X-direction beams: constant Y, span across adjacent X columns
        for yi, y in enumerate(YS):
            for xi in range(len(XS) - 1):
                x1, x2 = XS[xi], XS[xi + 1]
                name = f"{storey_name} Beam-X Y{yi+1} X{xi+1}-{xi+2}"
                try:
                    author.create_beam(
                        name=name,
                        storey_name=storey_name,
                        start_x=x1,
                        start_y=y,
                        end_x=x2,
                        end_y=y,
                        base_z=elev,
                        width=BEAM_WIDTH,
                        depth=BEAM_DEPTH,
                    )
                    added += 1
                except Exception as exc:
                    print(f"  ERROR {name}: {exc}")
                    errors += 1

        # Y-direction beams: constant X, span across adjacent Y rows
        for xi, x in enumerate(XS):
            for yi in range(len(YS) - 1):
                y1, y2 = YS[yi], YS[yi + 1]
                name = f"{storey_name} Beam-Y X{xi+1} Y{yi+1}-{yi+2}"
                try:
                    author.create_beam(
                        name=name,
                        storey_name=storey_name,
                        start_x=x,
                        start_y=y1,
                        end_x=x,
                        end_y=y2,
                        base_z=elev,
                        width=BEAM_WIDTH,
                        depth=BEAM_DEPTH,
                    )
                    added += 1
                except Exception as exc:
                    print(f"  ERROR {name}: {exc}")
                    errors += 1

        print(f"  {storey_name}: done")

    author.save()
    print(f"\nComplete: {added} beams added, {errors} errors")
    print(author.debug_dump())


if __name__ == "__main__":
    main()
