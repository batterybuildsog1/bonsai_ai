from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _scene_bounds() -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in bpy.data.objects:
        if obj.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            continue
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return Vector((0.0, 0.0, 0.0)), Vector((1.0, 1.0, 1.0))
    min_corner = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    max_corner = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return min_corner, max_corner


def _ensure_camera(name: str) -> bpy.types.Object:
    camera_data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, camera_data)
    bpy.context.scene.collection.objects.link(camera)
    return camera


def _look_at(camera: bpy.types.Object, target: Vector) -> None:
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _render(camera: bpy.types.Object, output_path: Path) -> None:
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.filepath = str(output_path)
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
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1200
    scene.render.film_transparent = False

    min_corner, max_corner = _scene_bounds()
    center = (min_corner + max_corner) / 2.0
    size = max(max_corner.x - min_corner.x, max(max_corner.y - min_corner.y, max_corner.z - min_corner.z))

    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA":
            bpy.data.objects.remove(obj, do_unlink=True)

    iso = _ensure_camera("ReviewIso")
    iso.data.type = "ORTHO"
    iso.data.ortho_scale = size * 1.3
    iso.location = center + Vector((size * 1.1, -size * 1.1, size * 0.9))
    _look_at(iso, center)
    _render(iso, output_dir / "review_iso.png")

    front = _ensure_camera("ReviewFront")
    front.data.type = "ORTHO"
    front.data.ortho_scale = size * 1.15
    front.location = center + Vector((0.0, -size * 1.6, size * 0.15))
    _look_at(front, center)
    _render(front, output_dir / "review_front.png")

    side = _ensure_camera("ReviewSide")
    side.data.type = "ORTHO"
    side.data.ortho_scale = size * 1.15
    side.location = center + Vector((size * 1.6, 0.0, size * 0.15))
    _look_at(side, center)
    _render(side, output_dir / "review_side.png")

    print(
        {
            "blend": str(blend_path),
            "output_dir": str(output_dir),
            "renders": ["review_iso.png", "review_front.png", "review_side.png"],
        }
    )


if __name__ == "__main__":
    main()
