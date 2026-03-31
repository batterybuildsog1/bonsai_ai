from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _camera_output_name(camera_name: str) -> str:
    if camera_name == "Review Iso":
        return "concept_iso_southeast"
    if camera_name == "Review Street":
        return "concept_south_elevation"
    if camera_name == "Review Terrace":
        return "concept_east_elevation"
    return camera_name.lower().replace(" ", "_")


def _review_cameras() -> list[bpy.types.Object]:
    preferred = ["Review Iso", "Review Street", "Review Terrace"]
    cameras = [bpy.data.objects.get(name) for name in preferred]
    cameras = [camera for camera in cameras if camera is not None and camera.type == "CAMERA"]
    if cameras:
        return cameras
    return [obj for obj in bpy.data.objects if obj.type == "CAMERA"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(_script_argv())

    blend_path = Path(args.blend).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1200
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.8

    rendered = []
    cameras = _review_cameras()
    if not cameras:
        raise RuntimeError("No cameras were found in the styled blend. Bake presentation first.")
    for camera_obj in cameras:
        scene.camera = camera_obj
        output_path = output_dir / f"{_camera_output_name(camera_obj.name)}.png"
        scene.render.filepath = str(output_path)
        bpy.ops.render.render(write_still=True)
        rendered.append(str(output_path))

    print(json.dumps({"blend": str(blend_path), "renders": rendered}, indent=2))


if __name__ == "__main__":
    main()
