"""Persistent styling and organization helpers for imported IFC scenes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import bpy
import ifcopenshell
import ifcopenshell.util.element
from mathutils import Vector


AI_PSET = "Pset_BonsaiAI"
VIEW_ROOT_NAME = "Bonsai AI View"
STOREYS_ROOT_NAME = "Storeys"
PRESENTATION_COLLECTION = "Presentation"
SOURCE_ROOT_NAME = "IFC Source"
VIEW_ROOT_KEY = "bonsai_ai_view_root"
PATH_KEY_PROP = "bonsai_ai_path_key"
SECTION_HELPER_NAME = "BonsaiSectionBox"
SECTION_MODIFIER_NAME = "Bonsai AI Section"

ROLE_LABELS = {
    "beam": "Structure",
    "column": "Structure",
    "panel": "Cladding",
    "curtain_wall": "Openings",
    "door": "Openings",
    "window": "Openings",
    "wall": "Envelope",
    "slab": "Envelope",
    "footing": "Foundations",
    "foundation": "Foundations",
    "storey": "Storeys",
}

SPATIAL_IFC_CLASSES = {"IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey"}


def _parse_jsonish(raw: Any) -> Any:
    if isinstance(raw, str) and raw[:1] in {"{", "["}:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _parse_group_path(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            payload = _parse_jsonish(stripped)
            if isinstance(payload, list):
                return [str(item).strip() for item in payload if str(item).strip()]
        if "/" in stripped:
            return [part.strip() for part in stripped.split("/") if part.strip()]
        if ">" in stripped:
            return [part.strip() for part in stripped.split(">") if part.strip()]
        return [stripped]
    return []


def _normalize_meta(raw_meta: dict[str, Any]) -> dict[str, Any]:
    parsed = {key: _parse_jsonish(value) for key, value in raw_meta.items()}
    semantics = dict(parsed.get("semantics")) if isinstance(parsed.get("semantics"), dict) else {}
    presentation = dict(parsed.get("presentation")) if isinstance(parsed.get("presentation"), dict) else {}
    foundation = dict(parsed.get("foundation")) if isinstance(parsed.get("foundation"), dict) else {}

    for field in (
        "element_id",
        "parent_id",
        "assembly_id",
        "role",
        "subrole",
        "system_name",
        "group_name",
        "group_path",
        "parent_name",
        "collection_key",
        "selector_tags",
        "is_exposed",
        "view_mode",
    ):
        value = parsed.get(field)
        if value is not None and field not in semantics:
            semantics[field] = value

    for field in (
        "presentation_style",
        "style_preset",
        "material_key",
        "material_preset",
        "glass_material_key",
        "frame_material_key",
        "window_type",
        "frame_style",
        "glazing_style",
        "transparency",
        "mullion_pattern",
        "is_storefront",
    ):
        value = parsed.get(field)
        if value is not None and field not in presentation:
            presentation[field] = value

    if "material_key" not in presentation and presentation.get("material_preset") is not None:
        presentation["material_key"] = presentation["material_preset"]
    if "presentation_style" not in presentation and presentation.get("style_preset") is not None:
        presentation["presentation_style"] = presentation["style_preset"]

    for field in (
        "foundation_type",
        "bearing_elevation",
        "support_for",
        "soil_assumption",
        "structural_role",
        "load_combo",
        "imposed_load_kN",
        "imposed_load_kn",
        "service_reaction_kN",
        "service_reaction_kn",
        "allowable_bearing_kpa",
        "concrete_strength_mpa",
        "rebar_yield_strength_mpa",
        "rebar_grade",
        "rebar_weight_kg",
        "total_rebar_weight_kg",
        "rebar_bar_diameter_mm",
        "rebar_spacing_mm",
        "rebar_layer_count",
        "rebar_schedule",
        "basis_notes",
    ):
        value = parsed.get(field)
        if value is not None and field not in foundation:
            foundation[field] = value

    if "imposed_load_kN" not in foundation and foundation.get("imposed_load_kn") is not None:
        foundation["imposed_load_kN"] = foundation["imposed_load_kn"]
    if "service_reaction_kN" not in foundation and foundation.get("service_reaction_kn") is not None:
        foundation["service_reaction_kN"] = foundation["service_reaction_kn"]
    if "rebar_weight_kg" not in foundation and foundation.get("total_rebar_weight_kg") is not None:
        foundation["rebar_weight_kg"] = foundation["total_rebar_weight_kg"]

    return {
        "raw": parsed,
        "semantics": semantics,
        "presentation": presentation,
        "foundation": foundation,
    }


def _find_root_collection() -> bpy.types.Collection | None:
    for collection in bpy.data.collections:
        if collection.get(PATH_KEY_PROP) == VIEW_ROOT_KEY:
            return collection
    return bpy.data.collections.get(VIEW_ROOT_NAME)


def _find_child_collection(parent: bpy.types.Collection | None, path_key: str) -> bpy.types.Collection | None:
    children = bpy.context.scene.collection.children if parent is None else parent.children
    for collection in children:
        if collection.get(PATH_KEY_PROP) == path_key:
            return collection
    return None


def _collection_display_name(label: str, path_key: str) -> str:
    if bpy.data.collections.get(label) is None:
        return label
    parts = [part.strip() for part in path_key.split(" / ") if part.strip()]
    if len(parts) >= 2:
        parent_key = parts[-2]
        parent_label = parent_key.split("::", 1)[-1].replace("_", " ").strip()
        if parent_label and parent_label.lower() != label.lower():
            candidate = f"{label} - {parent_label}"
            if bpy.data.collections.get(candidate) is None:
                return candidate
    return f"{label} - {parts[-1].split('::', 1)[-1].replace('_', ' ').strip()}"


def ensure_collection(label: str, parent: bpy.types.Collection | None = None, *, path_key: str) -> tuple[bpy.types.Collection, bool]:
    collection = _find_child_collection(parent, path_key)
    created = False
    if collection is None:
        collection = bpy.data.collections.new(_collection_display_name(label, path_key))
        created = True
    collection["bonsai_ai_label"] = label
    collection[PATH_KEY_PROP] = path_key

    if parent is None:
        if collection.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(collection)
    elif collection.name not in parent.children:
        parent.children.link(collection)
    return collection, created


def ensure_collection_path(segments: list[tuple[str, str]]) -> tuple[bpy.types.Collection, int]:
    if not segments:
        raise ValueError("Collection path must contain at least one segment.")
    parent = None
    collection = None
    created = 0
    accumulated: list[str] = []
    labels: list[str] = []
    for label, key_segment in segments:
        accumulated.append(key_segment)
        labels.append(label)
        collection, did_create = ensure_collection(label, parent=parent, path_key=" / ".join(accumulated))
        if did_create:
            created += 1
        collection["bonsai_ai_tree_path"] = " / ".join(labels)
        parent = collection
    return collection, created


def _delete_collection_tree(collection: bpy.types.Collection) -> None:
    for child in list(collection.children):
        _delete_collection_tree(child)
    if collection.users == 1:
        bpy.data.collections.remove(collection)


def reset_view_tree() -> None:
    root = _find_root_collection()
    if root is not None:
        _delete_collection_tree(root)


def _object_storey_name(obj: bpy.types.Object) -> str:
    for collection in obj.users_collection:
        if collection.name.startswith("IfcBuildingStorey/"):
            return collection.name.split("/", 1)[1]
    return "Unassigned"


def _raw_locator_from_name(name: str) -> tuple[str | None, str | None]:
    if "/" not in name:
        return None, None
    ifc_class, element_name = name.split("/", 1)
    return ifc_class, element_name


def _ifc_locator(obj: bpy.types.Object) -> tuple[str | None, str | None]:
    ifc_class = obj.get("bonsai_ai_ifc_class")
    source_name = obj.get("bonsai_ai_source_name")
    if isinstance(ifc_class, str) and isinstance(source_name, str):
        return ifc_class, source_name
    return _raw_locator_from_name(obj.name)


def load_semantic_records(ifc_path: str | Path) -> dict[tuple[str, str], dict[str, Any]]:
    model = ifcopenshell.open(str(Path(ifc_path).resolve()))
    records: dict[tuple[str, str], dict[str, Any]] = {}
    tracked_types = (
        "IfcWall",
        "IfcSlab",
        "IfcColumn",
        "IfcBeam",
        "IfcPlate",
        "IfcCurtainWall",
        "IfcWindow",
        "IfcDoor",
        "IfcFooting",
    )
    for ifc_type in tracked_types:
        for entity in model.by_type(ifc_type):
            name = getattr(entity, "Name", None)
            if not name:
                continue
            psets = ifcopenshell.util.element.get_psets(entity, psets_only=True, should_inherit=False)
            normalized = _normalize_meta(dict(psets.get(AI_PSET, {})))
            normalized["global_id"] = getattr(entity, "GlobalId", None)
            normalized["ifc_class"] = ifc_type
            normalized["ifc_name"] = name
            records[(ifc_type, name)] = normalized
    return records


def _semantic_role(ifc_class: str, meta: dict[str, Any]) -> str:
    semantics = meta.get("semantics", {})
    raw = meta.get("raw", {})
    explicit = str(semantics.get("role") or raw.get("Role") or raw.get("role") or "").strip()
    if explicit:
        return ROLE_LABELS.get(explicit.lower(), explicit.title())
    structural_kind = str(raw.get("StructuralKind") or "").strip().lower()
    if structural_kind:
        return ROLE_LABELS.get(structural_kind, structural_kind.title())
    return ROLE_LABELS.get(ifc_class.replace("Ifc", "").lower(), ifc_class.replace("Ifc", ""))


def _semantic_path(obj: bpy.types.Object, meta: dict[str, Any]) -> list[tuple[str, str]]:
    semantics = meta.get("semantics", {})
    storey = _object_storey_name(obj)
    role = _semantic_role(_ifc_locator(obj)[0] or "", meta)
    system_name = str(semantics.get("system_name") or meta.get("raw", {}).get("SystemName") or "").strip()
    subrole = str(semantics.get("subrole") or meta.get("raw", {}).get("Subrole") or "").strip()
    group_name = str(semantics.get("group_name") or meta.get("raw", {}).get("GroupName") or "").strip()
    group_path = _parse_group_path(semantics.get("group_path") or meta.get("raw", {}).get("GroupPath") or group_name)

    segments = [
        (VIEW_ROOT_NAME, VIEW_ROOT_KEY),
        (STOREYS_ROOT_NAME, "storeys"),
        (storey, f"storey::{storey}"),
        (role, f"role::{role}"),
    ]
    if system_name:
        segments.append((system_name, f"system::{system_name}"))
    if subrole:
        segments.append((subrole.replace("_", " ").title(), f"subrole::{subrole}"))
    for group in group_path:
        segments.append((group, f"group::{group}"))
    return segments


def _clean_display_name(obj: bpy.types.Object, meta: dict[str, Any]) -> str:
    semantics = meta.get("semantics", {})
    presentation = meta.get("presentation", {})
    _, source_name = _ifc_locator(obj)
    source_name = source_name or obj.name
    preferred = (
        semantics.get("group_name")
        or semantics.get("subrole")
        or presentation.get("window_type")
        or source_name
    )
    cleaned = str(preferred).replace("_", " ").strip()
    if cleaned.lower().startswith("ifc"):
        cleaned = cleaned.split("/", 1)[-1]
    return cleaned or source_name


def _ensure_material(
    name: str,
    *,
    base_color: tuple[float, float, float, float],
    roughness: float,
    metallic: float = 0.0,
    transmission: float = 0.0,
    ior: float = 1.45,
) -> bpy.types.Material:
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (320, 0)
    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.location = (0, 0)
    shader.inputs["Base Color"].default_value = base_color
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    transmission_input = shader.inputs.get("Transmission Weight") or shader.inputs.get("Transmission")
    if transmission_input is not None:
        transmission_input.default_value = transmission
    shader.inputs["IOR"].default_value = ior
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material.blend_method = "BLEND" if transmission > 0.0 else "OPAQUE"
    if hasattr(material, "shadow_method"):
        material.shadow_method = "HASHED" if transmission > 0.0 else "OPAQUE"
    return material


def ensure_material_library() -> dict[str, bpy.types.Material]:
    return {
        "concrete": _ensure_material("Bonsai_Concrete", base_color=(0.82, 0.82, 0.80, 1.0), roughness=0.88),
        "slab": _ensure_material("Bonsai_Slab", base_color=(0.72, 0.73, 0.75, 1.0), roughness=0.92),
        "cladding": _ensure_material("Bonsai_Cladding", base_color=(0.87, 0.84, 0.79, 1.0), roughness=0.72),
        "accent": _ensure_material("Bonsai_Accent", base_color=(0.81, 0.37, 0.22, 1.0), roughness=0.62),
        "steel": _ensure_material("Bonsai_Steel", base_color=(0.23, 0.28, 0.32, 1.0), roughness=0.42, metallic=0.65),
        "steel_dark": _ensure_material("Bonsai_SteelDark", base_color=(0.16, 0.18, 0.21, 1.0), roughness=0.34, metallic=0.75),
        "glass": _ensure_material("Bonsai_Glass", base_color=(0.74, 0.88, 0.94, 0.24), roughness=0.02, transmission=0.96, ior=1.45),
        "door": _ensure_material("Bonsai_Door", base_color=(0.50, 0.34, 0.18, 1.0), roughness=0.58),
        "foundation": _ensure_material("Bonsai_Foundation", base_color=(0.58, 0.60, 0.62, 1.0), roughness=0.95),
        "default": _ensure_material("Bonsai_Default", base_color=(0.68, 0.68, 0.68, 1.0), roughness=0.7),
    }


def _material_key(obj: bpy.types.Object, meta: dict[str, Any]) -> str:
    ifc_class, _ = _ifc_locator(obj)
    semantics = meta.get("semantics", {})
    presentation = meta.get("presentation", {})
    raw = meta.get("raw", {})
    presentation_style = str(
        presentation.get("presentation_style")
        or raw.get("PresentationStyle")
        or raw.get("presentation_style")
        or ""
    ).strip().lower()
    material_key = str(
        presentation.get("material_key")
        or raw.get("MaterialKey")
        or raw.get("material_key")
        or ""
    ).strip().lower()
    if material_key:
        return material_key
    if presentation_style in {"accent", "accent_panel"}:
        return "accent"
    if ifc_class == "IfcWindow":
        return "glass"
    if ifc_class == "IfcDoor":
        return "door"
    if ifc_class in {"IfcBeam", "IfcColumn"}:
        if str(semantics.get("role") or "").strip().lower() == "railings":
            return "steel_dark"
        return "steel"
    if ifc_class == "IfcFooting":
        return "foundation"
    if ifc_class == "IfcPlate":
        return "accent" if "accent" in obj.name.lower() else "cladding"
    if ifc_class == "IfcSlab":
        return "slab"
    if ifc_class == "IfcWall":
        return "concrete"
    return "default"


def apply_materials(ifc_path: str | Path) -> dict[str, int]:
    records = load_semantic_records(ifc_path)
    materials = ensure_material_library()
    styled_count = 0
    for obj in bpy.data.objects:
        if obj.type in {"CAMERA", "LIGHT"}:
            continue
        locator = _ifc_locator(obj)
        if locator[0] in SPATIAL_IFC_CLASSES:
            continue
        meta = records.get(locator, {"raw": {}, "semantics": {}, "presentation": {}, "foundation": {}})
        material = materials[_material_key(obj, meta)]
        obj.color = material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
        if hasattr(obj.data, "materials"):
            obj.data.materials.clear()
            obj.data.materials.append(material)
        obj["bonsai_ai_role"] = _semantic_role(locator[0] or "", meta) if locator[0] else "Ungrouped"
        styled_count += 1
    return {"styled_objects": styled_count}


def _ensure_review_cameras(presentation: bpy.types.Collection) -> dict[str, int]:
    created = 0
    camera_specs = (
        ("Review Iso", (38.0, -34.0, 24.0), (1.05, 0.0, 0.85)),
        ("Review Street", (-26.0, -24.0, 8.0), (1.35, 0.0, -0.8)),
        ("Review Terrace", (20.0, -8.0, 11.5), (1.15, 0.0, 1.1)),
    )
    for name, location, rotation in camera_specs:
        camera = bpy.data.objects.get(name)
        if camera is None or camera.type != "CAMERA":
            camera_data = bpy.data.cameras.new(name=name)
            camera = bpy.data.objects.new(name, camera_data)
            presentation.objects.link(camera)
            created += 1
        camera.location = location
        camera.rotation_euler = rotation
        camera.data.lens = 32 if name == "Review Iso" else 40
    if bpy.context.scene.camera is None:
        bpy.context.scene.camera = bpy.data.objects.get("Review Iso")
    return {"camera_count": len([obj for obj in bpy.data.objects if obj.type == "CAMERA" and obj.name.startswith("Review ")]), "created_cameras": created}


def ensure_studio_scene() -> dict[str, int]:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 64
    scene.eevee.taa_samples = 32
    scene.eevee.use_raytracing = True
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.93, 0.93, 0.92)
    scene.display.shading.show_object_outline = True
    scene.display.shading.show_shadows = True
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.8

    world = scene.world or bpy.data.worlds.new("BonsaiStudioWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs[0].default_value = (0.97, 0.97, 0.96, 1.0)
        background.inputs[1].default_value = 0.85

    presentation, _ = ensure_collection_path(
        [
            (VIEW_ROOT_NAME, VIEW_ROOT_KEY),
            (PRESENTATION_COLLECTION, "presentation"),
        ]
    )
    light_created = 0
    sun = bpy.data.objects.get("BonsaiStudioSun")
    if sun is None or sun.type != "LIGHT":
        light_data = bpy.data.lights.new(name="BonsaiStudioSun", type="SUN")
        light_data.energy = 2.2
        sun = bpy.data.objects.new("BonsaiStudioSun", light_data)
        presentation.objects.link(sun)
        light_created += 1
    sun.rotation_euler = (0.9, 0.0, 0.75)
    camera_report = _ensure_review_cameras(presentation)
    return {"light_count": len([obj for obj in bpy.data.objects if obj.type == "LIGHT" and obj.name == "BonsaiStudioSun"]), "created_lights": light_created, **camera_report}


def organize_objects_into_tree(ifc_path: str | Path) -> dict[str, int]:
    records = load_semantic_records(ifc_path)
    created_collections = 0
    semantic_objects = [obj for obj in bpy.data.objects if obj.type not in {"CAMERA", "LIGHT"}]
    processed = 0
    for obj in semantic_objects:
        raw_locator = _raw_locator_from_name(obj.name)
        if raw_locator[0] in SPATIAL_IFC_CLASSES:
            continue
        meta = records.get(raw_locator, {"raw": {}, "semantics": {}, "presentation": {}, "foundation": {}})
        ifc_class, source_name = raw_locator
        if ifc_class:
            obj["bonsai_ai_ifc_class"] = ifc_class
        if source_name:
            obj["bonsai_ai_source_name"] = source_name
        if meta.get("global_id"):
            obj["bonsai_ai_global_id"] = meta["global_id"]
        semantics = meta.get("semantics", {})
        if semantics.get("element_id"):
            obj["bonsai_ai_element_id"] = semantics["element_id"]
        if semantics.get("parent_id"):
            obj["bonsai_ai_parent_id"] = semantics["parent_id"]
        if semantics.get("assembly_id"):
            obj["bonsai_ai_assembly_id"] = semantics["assembly_id"]
        obj["bonsai_ai_source_collections"] = [collection.name for collection in obj.users_collection]
        path = _semantic_path(obj, meta)
        target, created = ensure_collection_path(path)
        created_collections += created
        if obj not in tuple(target.objects):
            target.objects.link(obj)
        obj["bonsai_ai_group_path"] = "/".join(label for label, _ in path[1:])
        obj["bonsai_ai_display_name"] = _clean_display_name(obj, meta)
        if obj.name.startswith("Ifc") and source_name:
            obj.name = obj["bonsai_ai_display_name"]
        processed += 1
    tree_collections = len([collection for collection in bpy.data.collections if str(collection.get(PATH_KEY_PROP, "")).startswith(VIEW_ROOT_KEY)])
    return {"organized_objects": processed, "view_collection_count": tree_collections, "created_collections": created_collections}


def organize_source_collections() -> dict[str, int]:
    source_root, created = ensure_collection(SOURCE_ROOT_NAME, path_key="source_root")
    collapsed = 0
    for collection in list(bpy.context.scene.collection.children):
        if collection == source_root:
            continue
        path_key = str(collection.get(PATH_KEY_PROP) or "")
        if path_key.startswith(VIEW_ROOT_KEY):
            continue
        if collection.name not in source_root.children:
            source_root.children.link(collection)
        bpy.context.scene.collection.children.unlink(collection)
        collection.hide_viewport = True
        collection.hide_render = True
        collapsed += 1
    source_root.hide_viewport = True
    source_root.hide_render = True
    return {"collapsed_source_collections": collapsed, "created_source_root": 1 if created else 0}


def bake_presentation(ifc_path: str | Path) -> dict[str, int]:
    bpy.context.scene["bonsai_ai_last_ifc_path"] = str(Path(ifc_path).resolve())
    reset_view_tree()
    organize_report = organize_objects_into_tree(ifc_path)
    source_report = organize_source_collections()
    material_report = apply_materials(ifc_path)
    scene_report = ensure_studio_scene()
    return {**organize_report, **source_report, **material_report, **scene_report}


def _walk_layer_collections(layer_collection: bpy.types.LayerCollection):
    yield layer_collection
    for child in layer_collection.children:
        yield from _walk_layer_collections(child)


def find_layer_collection_by_tree_path(tree_path: str) -> bpy.types.LayerCollection | None:
    for layer in _walk_layer_collections(bpy.context.view_layer.layer_collection):
        collection = layer.collection
        if str(collection.get(PATH_KEY_PROP) or "") == tree_path:
            return layer
    return None


def show_all_semantic_collections() -> int:
    changed = 0
    for layer in _walk_layer_collections(bpy.context.view_layer.layer_collection):
        path_key = str(layer.collection.get(PATH_KEY_PROP) or "")
        if path_key.startswith(VIEW_ROOT_KEY):
            if layer.exclude:
                changed += 1
            layer.exclude = False
            layer.hide_viewport = False
    return changed


def isolate_semantic_branch(tree_path: str) -> int:
    changed = 0
    for layer in _walk_layer_collections(bpy.context.view_layer.layer_collection):
        path_key = str(layer.collection.get(PATH_KEY_PROP) or "")
        if not path_key.startswith(VIEW_ROOT_KEY):
            continue
        visible = path_key.startswith(tree_path) or tree_path.startswith(path_key)
        if layer.exclude == visible:
            changed += 1
        layer.exclude = not visible
        layer.hide_viewport = not visible
    return changed


def isolate_role(role_name: str) -> int:
    target_prefix = f"role::{role_name}"
    target_path = None
    for collection in bpy.data.collections:
        path_key = str(collection.get(PATH_KEY_PROP) or "")
        if target_prefix in path_key:
            target_path = path_key
            break
    if target_path is None:
        raise ValueError(f"Semantic role '{role_name}' was not found in the current review tree.")
    return isolate_semantic_branch(target_path)


def selected_object_metadata(ifc_path: str | Path) -> dict[str, Any]:
    selected = [obj for obj in bpy.context.selected_objects if obj.type not in {"CAMERA", "LIGHT"}]
    if not selected:
        raise ValueError("Select one or more review objects first.")
    records = load_semantic_records(ifc_path)
    selected_payload = []
    for obj in selected:
        locator = _ifc_locator(obj)
        meta = records.get(locator, {"raw": {}, "semantics": {}, "presentation": {}, "foundation": {}})
        selected_payload.append(
            {
                "active": obj == bpy.context.view_layer.objects.active,
                "object_name": obj.name,
                "ifc_class": locator[0],
                "source_name": locator[1],
                "element_id": obj.get("bonsai_ai_element_id"),
                "parent_id": obj.get("bonsai_ai_parent_id"),
                "assembly_id": obj.get("bonsai_ai_assembly_id"),
                "group_path": obj.get("bonsai_ai_group_path"),
                "display_name": obj.get("bonsai_ai_display_name"),
                "metadata": meta,
            }
        )
    primary = next((item for item in selected_payload if item["active"]), selected_payload[0])
    return {
        "selected_count": len(selected),
        "active_object": primary["object_name"],
        "ifc_class": primary["ifc_class"],
        "source_name": primary["source_name"],
        "element_id": primary["element_id"],
        "parent_id": primary["parent_id"],
        "assembly_id": primary["assembly_id"],
        "group_path": primary["group_path"],
        "display_name": primary["display_name"],
        "metadata": primary["metadata"],
        "selected_objects": selected_payload,
    }


def isolate_selected_branch() -> int:
    selected = [obj for obj in bpy.context.selected_objects if obj.type not in {"CAMERA", "LIGHT"}]
    if not selected:
        raise ValueError("Select a review object first.")
    group_path = str(selected[0].get("bonsai_ai_group_path") or "").strip()
    if not group_path:
        raise ValueError("The selected object does not have a semantic review branch yet. Bake presentation first.")
    tree_path = f"{VIEW_ROOT_KEY} / storeys / {group_path.replace('/', ' / ')}"
    return isolate_semantic_branch(tree_path)


def _semantic_review_objects() -> list[bpy.types.Object]:
    return [
        obj
        for obj in bpy.data.objects
        if obj.type not in {"CAMERA", "LIGHT"}
        and str(obj.get("bonsai_ai_group_path") or "").strip()
        and obj.name != SECTION_HELPER_NAME
    ]


def clear_section_box() -> int:
    cleared = 0
    helper = bpy.data.objects.get(SECTION_HELPER_NAME)
    for obj in _semantic_review_objects():
        modifier = obj.modifiers.get(SECTION_MODIFIER_NAME)
        if modifier is not None:
            obj.modifiers.remove(modifier)
            cleared += 1
    if helper is not None:
        for collection in list(helper.users_collection):
            collection.objects.unlink(helper)
        bpy.data.objects.remove(helper)
    mesh = bpy.data.meshes.get(SECTION_HELPER_NAME)
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)
    return cleared


def apply_section_box_from_selection(padding: float = 1.0) -> dict[str, int]:
    selected = [obj for obj in bpy.context.selected_objects if obj.type not in {"CAMERA", "LIGHT"}]
    if not selected:
        raise ValueError("Select one or more review objects first.")

    coords: list[tuple[float, float, float]] = []
    for obj in selected:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            coords.append((world.x, world.y, world.z))
    if not coords:
        raise ValueError("The current selection does not expose usable bounds.")

    min_x = min(point[0] for point in coords) - padding
    min_y = min(point[1] for point in coords) - padding
    min_z = min(point[2] for point in coords) - padding
    max_x = max(point[0] for point in coords) + padding
    max_y = max(point[1] for point in coords) + padding
    max_z = max(point[2] for point in coords) + padding

    clear_section_box()

    presentation, _ = ensure_collection_path(
        [
            (VIEW_ROOT_NAME, VIEW_ROOT_KEY),
            (PRESENTATION_COLLECTION, "presentation"),
        ]
    )
    bpy.ops.mesh.primitive_cube_add(location=((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0))
    helper = bpy.context.active_object
    helper.name = SECTION_HELPER_NAME
    helper.scale = ((max_x - min_x) / 2.0, (max_y - min_y) / 2.0, (max_z - min_z) / 2.0)
    helper.display_type = "WIRE"
    helper.hide_render = True
    helper["bonsai_ai_section_helper"] = True
    for collection in list(helper.users_collection):
        collection.objects.unlink(helper)
    presentation.objects.link(helper)

    affected = 0
    for obj in _semantic_review_objects():
        modifier = obj.modifiers.get(SECTION_MODIFIER_NAME)
        if modifier is None:
            modifier = obj.modifiers.new(name=SECTION_MODIFIER_NAME, type="BOOLEAN")
        modifier.operation = "INTERSECT"
        modifier.object = helper
        affected += 1
    return {"affected_objects": affected, "selected_objects": len(selected)}
