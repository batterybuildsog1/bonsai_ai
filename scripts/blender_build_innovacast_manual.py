from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

from bonsai_ai_blender.integration import BonsaiAIExecutor


INCH = 0.0254
FOOT = 0.3048


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(_script_argv())

    bpy.ops.preferences.addon_enable(module="bonsai_ai_blender")

    panel_width = 4.0 * FOOT
    panel_height = 16.58 * FOOT
    wythe_thickness = 2.25 * INCH
    foam_gap = 3.0 * INCH
    second_wythe_offset = wythe_thickness + foam_gap

    plan = {
        "version": "1.0",
        "units": "meters",
        "summary": "Engineering representation of one InnovaCast precast insulated cladding panel section.",
        "assumptions": [
            "Modeled as two concrete wythes using supported IfcWall geometry because the addon schema does not support a native insulated sandwich panel.",
            "The 3 inch foam core, wire mesh, rebar hangers at 24 inch spacing, and Tapcon anchor hardware are documented but not modeled as internal IFC subcomponents in this smoke test.",
            "Geometry reflects the report basis: 4 ft panel width, 16.58 ft supported height, 7.5 inch overall assembly depth from 2.25 inch concrete wythes plus 3 inch foam core.",
            "Engineering limits from the reports such as 4000 psi minimum concrete and 24 inch top fastener spacing remain design metadata rather than explicit geometry.",
        ],
        "actions": [
            {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
            {
                "type": "create_wall",
                "name": "InnovaCast Exterior Wythe",
                "storey": "Level 0",
                "x1": 0.0,
                "y1": 0.0,
                "x2": panel_width,
                "y2": 0.0,
                "base_z": 0.0,
                "height": panel_height,
                "thickness": wythe_thickness,
            },
            {
                "type": "create_wall",
                "name": "InnovaCast Interior Wythe",
                "storey": "Level 0",
                "x1": 0.0,
                "y1": second_wythe_offset,
                "x2": panel_width,
                "y2": second_wythe_offset,
                "base_z": 0.0,
                "height": panel_height,
                "thickness": wythe_thickness,
            },
        ],
    }

    result = BonsaiAIExecutor(auto_create_project=True).execute_plan(plan)
    _require(result["created"], "No objects were created")

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_result = bpy.ops.bim.save_project(filepath=str(output_path))
    _require("FINISHED" in export_result, f"IFC export failed: {export_result}")

    print(
        json.dumps(
            {
                "created": result["created"],
                "action_count": result["action_count"],
                "summary": plan["summary"],
                "assumptions": plan["assumptions"],
                "output_ifc": str(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
