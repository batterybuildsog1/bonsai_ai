#!/usr/bin/env python3
"""Non-destructive IFC model inspector.

Usage:
    python3 scripts/query_scene.py out/model.ifc
    python3 scripts/query_scene.py --model out/model.ifc

Output (JSON to stdout):
    {
        "model_path": "/absolute/path/to/model.ifc",
        "element_counts": {"walls": 12, "slabs": 5, "columns": 20, ...},
        "storeys": [
            {"name": "Ground Floor", "elevation": 0.0, "element_count": 15},
            {"name": "Level 1", "elevation": 4.5, "element_count": 12}
        ],
        "scene_summary": "Project: AI Project\\nStoreys: ...",
        "validation": {
            "orphan_elements": 0,
            "elements_without_storey": []
        }
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _error(message: str) -> int:
    print(json.dumps({"success": False, "errors": [message]}))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect an IFC model and return structured JSON."
    )
    parser.add_argument(
        "model",
        nargs="?",
        help="Path to IFC file (positional).",
    )
    parser.add_argument(
        "--model",
        dest="model_flag",
        help="Path to IFC file (flag).",
    )
    args = parser.parse_args()

    model_path = args.model or args.model_flag
    if not model_path:
        return _error("No model path provided. Usage: query_scene.py <model.ifc>")

    model_path = Path(model_path).resolve()
    if not model_path.exists():
        return _error(f"File not found: {model_path}")

    # ------------------------------------------------------------------
    # Import and load
    # ------------------------------------------------------------------
    try:
        import ifcopenshell
        import ifcopenshell.util.element
    except ImportError as exc:
        return _error(f"Failed to import ifcopenshell: {exc}")

    try:
        from bonsai_ai.ifc_author import IfcAuthor
    except ImportError as exc:
        return _error(f"Failed to import bonsai_ai: {exc}")

    try:
        author = IfcAuthor(str(model_path))
    except Exception as exc:
        return _error(f"Failed to open IFC file: {exc}")

    # ------------------------------------------------------------------
    # Element counts
    # ------------------------------------------------------------------
    element_counts = json.loads(author.debug_dump())

    # ------------------------------------------------------------------
    # Storey details
    # ------------------------------------------------------------------
    storeys = []
    for storey in author.model.by_type("IfcBuildingStorey"):
        name = getattr(storey, "Name", None) or "(unnamed)"
        # Get elevation from placement matrix
        placement = getattr(storey, "ObjectPlacement", None)
        elevation = 0.0
        if placement:
            try:
                import ifcopenshell.util.placement
                matrix = ifcopenshell.util.placement.get_local_placement(placement)
                elevation = float(matrix[2][3])
            except Exception:
                pass

        # Count elements contained in this storey
        contained = 0
        for rel in getattr(storey, "ContainsElements", []) or []:
            elements = getattr(rel, "RelatedElements", []) or []
            contained += len(elements)

        storeys.append({
            "name": name,
            "elevation": round(elevation, 4),
            "element_count": contained,
        })

    # Sort by elevation
    storeys.sort(key=lambda s: s["elevation"])

    # ------------------------------------------------------------------
    # Scene summary
    # ------------------------------------------------------------------
    scene_summary = author.scene_summary()

    # ------------------------------------------------------------------
    # Validation checks
    # ------------------------------------------------------------------
    # Find elements not assigned to any storey
    all_spatial_elements = set()
    for ifc_class in ("IfcWall", "IfcSlab", "IfcColumn", "IfcBeam",
                       "IfcDoor", "IfcWindow", "IfcCurtainWall",
                       "IfcPlate", "IfcFooting"):
        for elem in author.model.by_type(ifc_class):
            all_spatial_elements.add(elem)

    contained_elements = set()
    for storey in author.model.by_type("IfcBuildingStorey"):
        for rel in getattr(storey, "ContainsElements", []) or []:
            for elem in getattr(rel, "RelatedElements", []) or []:
                contained_elements.add(elem)

    orphans = all_spatial_elements - contained_elements
    orphan_names = [
        getattr(e, "Name", None) or f"({e.is_a()} #{e.id()})"
        for e in orphans
    ]

    validation = {
        "orphan_elements": len(orphans),
        "elements_without_storey": orphan_names[:20],
    }

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    result = {
        "success": True,
        "model_path": str(model_path),
        "element_counts": element_counts,
        "storeys": storeys,
        "scene_summary": scene_summary,
        "validation": validation,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
