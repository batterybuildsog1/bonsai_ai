from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


ROLE_COLORS = {
    "primary_column": (0.12, 0.29, 0.56, 1.0),
    "gravity_column": (0.26, 0.48, 0.78, 1.0),
    "facade_post": (0.10, 0.55, 0.53, 1.0),
    "opening_column": (0.78, 0.82, 0.88, 1.0),
    "brace": (0.82, 0.16, 0.16, 1.0),
    "drag_collector": (0.88, 0.48, 0.12, 1.0),
    "roof_collector": (0.93, 0.62, 0.18, 1.0),
    "roof_primary_frame": (0.35, 0.20, 0.05, 1.0),
    "perimeter_spandrel": (0.24, 0.28, 0.33, 1.0),
    "panel_joint_support": (0.10, 0.42, 0.48, 1.0),
    "roof_edge_support": (0.10, 0.42, 0.48, 1.0),
    "floor_girder": (0.38, 0.43, 0.50, 1.0),
    "floor_beam": (0.52, 0.57, 0.64, 1.0),
    "window_header": (0.74, 0.77, 0.82, 1.0),
    "window_sill": (0.82, 0.84, 0.88, 1.0),
    "door_header": (0.74, 0.77, 0.82, 1.0),
    "default_beam": (0.42, 0.46, 0.52, 1.0),
}


def _load_plan(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    plan = json.loads(path.read_text())
    beam_roles: dict[str, str] = {}
    column_roles: dict[str, str] = {}
    for action in plan.get("actions", []):
        if action.get("type") == "create_beam":
            beam_roles[str(action["name"])] = str(action.get("member_role") or "unclassified")
        elif action.get("type") == "create_column":
            name = str(action["name"])
            lowered = name.lower()
            if "jamb" in lowered:
                role = "opening_column"
            elif "facade post" in lowered:
                role = "facade_post"
            elif "corner_frame_column" in lowered or "sidewall_frame_column" in lowered or "endwall_column" in lowered:
                role = "primary_column"
            elif "interior_gravity_column" in lowered:
                role = "gravity_column"
            else:
                role = "column"
            column_roles[name] = role
    return beam_roles, column_roles


def _ensure_camera(name: str = "StructuralReviewCamera") -> bpy.types.Object:
    camera_obj = bpy.data.objects.get(name)
    if camera_obj is not None:
        return camera_obj
    camera_data = bpy.data.cameras.new(name)
    camera_obj = bpy.data.objects.new(name, camera_data)
    bpy.context.scene.collection.objects.link(camera_obj)
    return camera_obj


def _focus_camera(camera_obj: bpy.types.Object, location: tuple[float, float, float], target: tuple[float, float, float]) -> None:
    camera_obj.location = location
    direction = Vector(target) - camera_obj.location
    camera_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _ensure_sun(name: str = "StructuralSun") -> bpy.types.Object:
    sun = bpy.data.objects.get(name)
    if sun is not None:
        return sun
    sun_data = bpy.data.lights.new(name, type="SUN")
    sun = bpy.data.objects.new(name, sun_data)
    bpy.context.scene.collection.objects.link(sun)
    return sun


def _role_material(role: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    material_name = f"StructuralRole_{role}"
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(material_name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    for node in list(nodes):
        nodes.remove(node)
    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = 0.42
    principled.inputs["Specular IOR Level"].default_value = 0.35
    emission_color = tuple(min(1.0, channel * 1.08) for channel in color[:3]) + (1.0,)
    principled.inputs["Emission Color"].default_value = emission_color
    principled.inputs["Emission Strength"].default_value = 0.18
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return material


def _configure_scene() -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1200
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.55
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = 0.35
    scene.eevee.taa_render_samples = 32
    world = scene.world or bpy.data.worlds.new("StructuralRoleWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs[0].default_value = (0.96, 0.97, 0.99, 1.0)
        background.inputs[1].default_value = 1.35

    sun = _ensure_sun()
    if sun.data:
        sun.data.energy = 3.2
        sun.rotation_euler = (0.9, 0.2, 0.6)


def _object_role(obj: bpy.types.Object, beam_roles: dict[str, str], column_roles: dict[str, str]) -> str | None:
    if obj.name.startswith("IfcBeam/"):
        return beam_roles.get(obj.name.split("/", 1)[1], "default_beam")
    if obj.name.startswith("IfcColumn/"):
        return column_roles.get(obj.name.split("/", 1)[1], "column")
    return None


def _apply_mode(mode: str, beam_roles: dict[str, str], column_roles: dict[str, str]) -> None:
    primary_visible_roles = {
        "primary_column",
        "gravity_column",
        "brace",
        "drag_collector",
        "roof_collector",
        "roof_primary_frame",
        "perimeter_spandrel",
        "panel_joint_support",
        "roof_edge_support",
    }
    all_steel_visible_roles = primary_visible_roles | {"facade_post", "floor_girder", "floor_beam"}
    for obj in bpy.data.objects:
        if obj.type in {"CAMERA", "LIGHT"}:
            continue
        role = _object_role(obj, beam_roles, column_roles)
        obj.hide_render = True
        if role is None:
            continue
        if mode == "primary_frame":
            visible = role in primary_visible_roles
        elif mode == "all_steel":
            visible = role in all_steel_visible_roles
        elif mode == "primary_columns":
            visible = role in {"primary_column", "gravity_column", "brace", "roof_primary_frame", "perimeter_spandrel", "drag_collector", "roof_collector"}
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        obj.hide_render = not visible
        if visible:
            color = ROLE_COLORS.get(role, ROLE_COLORS["default_beam"])
            material = _role_material(role, color)
            if getattr(obj.data, "materials", None) is not None:
                obj.data.materials.clear()
                obj.data.materials.append(material)
            obj.color = color


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=["primary_frame", "all_steel", "primary_columns"], default="primary_frame")
    args = parser.parse_args(_script_argv())

    blend_path = Path(args.blend).resolve()
    plan_path = Path(args.plan).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    _configure_scene()
    beam_roles, column_roles = _load_plan(plan_path)
    _apply_mode(args.mode, beam_roles, column_roles)

    camera = _ensure_camera()
    bpy.context.scene.camera = camera
    target = (14.6, 17.5, 8.5)
    views = {
        "iso_southeast": (53.0, -14.0, 26.0),
        "aerial": (42.0, -10.0, 52.0),
        "south_oblique": (14.6, -22.0, 15.0),
    }
    rendered: list[str] = []
    for name, location in views.items():
        _focus_camera(camera, location, target)
        output_path = output_dir / f"{name}.png"
        bpy.context.scene.render.filepath = str(output_path)
        bpy.ops.render.render(write_still=True)
        rendered.append(str(output_path))

    print(json.dumps({"mode": args.mode, "renders": rendered}, indent=2))


if __name__ == "__main__":
    main()
