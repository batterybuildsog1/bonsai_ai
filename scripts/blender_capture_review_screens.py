from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import mathutils


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _renderable_objects():
    return [obj for obj in bpy.data.objects if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}]


def _world_bbox(objects) -> tuple[mathutils.Vector, mathutils.Vector]:
    matrix_points = []
    for obj in objects:
        for corner in obj.bound_box:
            matrix_points.append(obj.matrix_world @ mathutils.Vector(corner))
    mins = mathutils.Vector((min(v.x for v in matrix_points), min(v.y for v in matrix_points), min(v.z for v in matrix_points)))
    maxs = mathutils.Vector((max(v.x for v in matrix_points), max(v.y for v in matrix_points), max(v.z for v in matrix_points)))
    return mins, maxs


def _ensure_camera(name: str) -> bpy.types.Object:
    camera_data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, camera_data)
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera


def _point_camera(camera: bpy.types.Object, location: mathutils.Vector, target: mathutils.Vector) -> None:
    direction = target - location
    camera.location = location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _render_view(camera: bpy.types.Object, output_path: Path) -> None:
    bpy.context.scene.camera = camera
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)


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
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900

    objects = _renderable_objects()
    if not objects:
        raise RuntimeError("No renderable objects found in the loaded Blender file.")

    mins, maxs = _world_bbox(objects)
    center = (mins + maxs) * 0.5
    dims = maxs - mins
    radius = max(dims.x, dims.y, dims.z, 1.0)

    south = _ensure_camera("ReviewSouth")
    south.data.type = "ORTHO"
    south.data.ortho_scale = max(dims.x, dims.z) * 1.2
    _point_camera(south, mathutils.Vector((center.x, mins.y - radius * 1.6, center.z)), center)

    top = _ensure_camera("ReviewTop")
    top.data.type = "ORTHO"
    top.data.ortho_scale = max(dims.x, dims.y) * 1.15
    _point_camera(top, mathutils.Vector((center.x, center.y, maxs.z + radius * 1.6)), center)

    iso = _ensure_camera("ReviewIso")
    iso.data.type = "PERSP"
    iso.data.lens = 32
    _point_camera(
        iso,
        mathutils.Vector((mins.x - radius * 1.2, mins.y - radius * 1.4, center.z + radius * 0.9)),
        center,
    )

    outputs = {
        "review_south.png": south,
        "review_top.png": top,
        "review_iso.png": iso,
    }
    for filename, camera in outputs.items():
        _render_view(camera, output_dir / filename)

    print(
        json.dumps(
            {
                "blend": str(blend_path),
                "output_dir": str(output_dir),
                "screenshots": sorted(outputs.keys()),
                "object_count": len(objects),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
