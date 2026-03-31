from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _ensure_camera(name: str = "ReviewCamera"):
    camera_obj = bpy.data.objects.get(name)
    if camera_obj is not None:
        return camera_obj
    camera_data = bpy.data.cameras.new(name)
    camera_obj = bpy.data.objects.new(name, camera_data)
    bpy.context.scene.collection.objects.link(camera_obj)
    return camera_obj


def _focus_camera(camera_obj, location: tuple[float, float, float], target: tuple[float, float, float]) -> None:
    camera_obj.location = location
    direction = Vector(target) - camera_obj.location
    camera_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _ensure_material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (280, 0)
    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.location = (0, 0)
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = 0.55
    shader.inputs["Specular IOR Level"].default_value = 0.15
    shader.inputs["Emission Color"].default_value = color
    shader.inputs["Emission Strength"].default_value = 0.2
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def _assign_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    if not hasattr(obj.data, "materials"):
        return
    materials = obj.data.materials
    materials.clear()
    materials.append(material)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=["full", "steel_only", "columns_only"], default="full")
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
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.92, 0.92, 0.92)
    scene.display.shading.show_object_outline = True
    scene.display.shading.show_shadows = True
    scene.render.film_transparent = False
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 1.0

    world = scene.world or bpy.data.worlds.new("ReviewWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs[0].default_value = (0.92, 0.92, 0.92, 1.0)
        background.inputs[1].default_value = 0.6

    type_colors = {
        "IfcBeam/": (0.85, 0.2, 0.15, 1.0),
        "IfcColumn/": (0.16, 0.33, 0.75, 1.0),
        "IfcWall/": (0.78, 0.78, 0.78, 1.0),
        "IfcSlab/": (0.62, 0.66, 0.70, 1.0),
        "IfcWindow/": (0.22, 0.55, 0.78, 1.0),
        "IfcDoor/": (0.45, 0.28, 0.14, 1.0),
    }

    materials_by_prefix = {
        prefix: _ensure_material(f"Review_{prefix.replace('/', '_')}", color) for prefix, color in type_colors.items()
    }
    default_material = _ensure_material("Review_Default", (0.7, 0.7, 0.7, 1.0))

    for obj in bpy.data.objects:
        if obj.type == "CAMERA":
            continue
        obj.hide_render = False
        for prefix, color in type_colors.items():
            if obj.name.startswith(prefix):
                obj.color = color
                _assign_material(obj, materials_by_prefix[prefix])
                break
        else:
            obj.color = (0.55, 0.55, 0.55, 1.0)
            _assign_material(obj, default_material)

    camera_obj = _ensure_camera()
    scene.camera = camera_obj

    if args.mode == "steel_only":
        for obj in bpy.data.objects:
            if obj.type == "CAMERA":
                continue
            obj.hide_render = not (obj.name.startswith("IfcBeam/") or obj.name.startswith("IfcColumn/"))
            if not obj.hide_render:
                obj.color = (0.86, 0.24, 0.18, 1.0) if obj.name.startswith("IfcBeam/") else (0.15, 0.36, 0.82, 1.0)
                material_name = "IfcBeam/" if obj.name.startswith("IfcBeam/") else "IfcColumn/"
                _assign_material(obj, materials_by_prefix[material_name])
    elif args.mode == "columns_only":
        for obj in bpy.data.objects:
            if obj.type == "CAMERA":
                continue
            obj.hide_render = not obj.name.startswith("IfcColumn/")
            if not obj.hide_render:
                obj.color = (0.15, 0.36, 0.82, 1.0)
                _assign_material(obj, materials_by_prefix["IfcColumn/"])

    target = (14.63, 17.53, 9.0)
    views = {
        "iso_southeast": (60.0, -35.0, 32.0),
        "south_elevation": (14.63, -28.0, 16.0),
        "east_elevation": (58.0, 17.53, 16.0),
        "aerial": (48.0, -18.0, 58.0),
    }

    rendered = []
    for name, location in views.items():
        _focus_camera(camera_obj, location, target)
        output_path = output_dir / f"{name}.png"
        scene.render.filepath = str(output_path)
        bpy.ops.render.render(write_still=True)
        rendered.append(str(output_path))

    print(json.dumps({"blend": str(blend_path), "renders": rendered}, indent=2))


if __name__ == "__main__":
    main()
