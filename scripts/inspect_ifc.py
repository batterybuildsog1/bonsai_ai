from __future__ import annotations

import argparse
import json
from pathlib import Path

import ifcopenshell


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc", required=True)
    args = parser.parse_args()

    path = Path(args.ifc).resolve()
    model = ifcopenshell.open(str(path))
    tracked = [
        "IfcProject",
        "IfcBuildingStorey",
        "IfcSlab",
        "IfcWall",
        "IfcCurtainWall",
        "IfcPlate",
        "IfcColumn",
        "IfcBeam",
        "IfcMember",
        "IfcDoor",
        "IfcWindow",
        "IfcStair",
        "IfcStairFlight",
        "IfcRailing",
        "IfcFastener",
        "IfcMechanicalFastener",
        "IfcConnectionElement",
    ]
    payload = {"ifc": str(path), "counts": {}, "names": {}}
    for ifc_class in tracked:
        try:
            elements = model.by_type(ifc_class)
        except RuntimeError:
            continue
        payload["counts"][ifc_class] = len(elements)
        if elements:
            payload["names"][ifc_class] = [getattr(element, "Name", None) for element in elements[:20]]
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
