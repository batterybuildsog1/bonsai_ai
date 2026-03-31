from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_bake_presentation():
    module_path = ROOT / "bonsai_ai_blender" / "presentation.py"
    spec = importlib.util.spec_from_file_location("bonsai_ai_blender.presentation", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load presentation helpers from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.bake_presentation


bake_presentation = _load_bake_presentation()


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _import_ifc(path: Path) -> str:
    bpy.ops.preferences.addon_enable(module="bonsai")
    bim_ops = getattr(bpy.ops, "bim", None)
    if bim_ops is None:
        raise RuntimeError("Bonsai BIM operators are not available in this Blender session.")

    for operator_name in ("load_project", "load_ifc", "open_project"):
        operator = getattr(bim_ops, operator_name, None)
        if operator is None:
            continue
        try:
            result = operator(filepath=str(path))
        except TypeError:
            result = operator("INVOKE_DEFAULT", filepath=str(path))
        if "FINISHED" in result:
            return operator_name
    raise RuntimeError(f"Unable to import IFC via Bonsai operators for {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc", required=True)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--styled-blend", help="Optional path for a styled and organized blend file.")
    args = parser.parse_args(_script_argv())

    ifc_path = Path(args.ifc).resolve()
    blend_path = Path(args.blend).resolve()
    if not ifc_path.exists():
        raise FileNotFoundError(f"IFC not found: {ifc_path}")

    bpy.ops.wm.read_homefile(use_empty=True)
    operator_name = _import_ifc(ifc_path)
    phases = ["import"]

    blend_path.parent.mkdir(parents=True, exist_ok=True)
    save_result = bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    if "FINISHED" not in save_result:
        raise RuntimeError(f"Blender save failed: {save_result}")
    phases.append("save_raw")

    styled_blend = None
    presentation_report = None
    if args.styled_blend:
        styled_blend = Path(args.styled_blend).resolve()
        presentation_report = bake_presentation(ifc_path)
        phases.extend(["organize", "style", "view_setup"])
        styled_blend.parent.mkdir(parents=True, exist_ok=True)
        styled_result = bpy.ops.wm.save_as_mainfile(filepath=str(styled_blend))
        if "FINISHED" not in styled_result:
            raise RuntimeError(f"Styled Blender save failed: {styled_result}")
        phases.append("save_styled")

    print(
        json.dumps(
            {
                "ifc": str(ifc_path),
                "blend": str(blend_path),
                "styled_blend": str(styled_blend) if styled_blend else None,
                "import_operator": operator_name,
                "phases": phases,
                "object_count": len(bpy.data.objects),
                "collection_count": len(bpy.data.collections),
                "presentation_report": presentation_report,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
