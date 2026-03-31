"""Compile authored semantic plans into buildable primitive plans."""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, Iterable, List

from .action_catalog import EDIT_ACTIONS
from .semantic_model import build_semantic_model, semantic_model_to_plan
from .schema import validate_action, validate_plan


def compile_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    authored = copy.deepcopy(plan)
    validate_plan(authored)
    semantic_model = build_semantic_model(authored)
    normalized_plan = semantic_model_to_plan(semantic_model)

    compiled_actions: List[Dict[str, Any]] = []
    for index, action in enumerate(normalized_plan["actions"]):
        if action["type"] in EDIT_ACTIONS:
            _apply_edit_action(compiled_actions, action, index=index)
            continue
        compiled_actions.extend(_compile_action(action))

    compiled = {
        "version": normalized_plan["version"],
        "units": normalized_plan["units"],
        "summary": normalized_plan["summary"],
        "assumptions": list(normalized_plan["assumptions"]),
        "actions": compiled_actions,
    }
    validate_plan(compiled, allow_semantic=False)
    return compiled


def _compile_action(action: Dict[str, Any]) -> List[Dict[str, Any]]:
    action_type = action["type"]
    if action_type == "create_stair_run":
        return _compile_stair_run(action)
    if action_type == "create_stair_landing":
        compiled = _inherit_metadata(
            action,
            {
                "type": "create_rect_slab",
                "name": action["name"],
                "storey": action.get("storey"),
                "x": float(action["x"]),
                "y": float(action["y"]),
                "z": float(action["base_z"]),
                "width": float(action["width"]),
                "depth": float(action["depth"]),
                "thickness": float(action["thickness"]),
                "rotation_deg": float(action.get("direction_deg") or 0.0),
            },
        )
        return [_ensure_semantic_identity(compiled)]
    if action_type == "create_connection_plate":
        width = float(action["width"])
        depth = float(action["depth"])
        rotation_deg = float(action.get("rotation_deg") or 0.0)
        angle = math.radians(rotation_deg)
        offset_x = (math.cos(angle) * (width / 2.0)) - (math.sin(angle) * (depth / 2.0))
        offset_y = (math.sin(angle) * (width / 2.0)) + (math.cos(angle) * (depth / 2.0))
        compiled = _inherit_metadata(
            action,
            {
                "type": "create_panel",
                "name": action["name"],
                "storey": action.get("storey"),
                "x": float(action["center_x"]) - offset_x,
                "y": float(action["center_y"]) - offset_y,
                "base_z": float(action["base_z"]),
                "width": width,
                "depth": depth,
                "thickness": float(action["thickness"]),
                "orientation": "horizontal",
                "rotation_deg": rotation_deg,
            },
        )
        return [_ensure_semantic_identity(compiled)]
    if action_type == "generate_column_grid":
        return _compile_column_grid(action)
    if action_type == "generate_perimeter_walls":
        return _compile_perimeter_walls(action)
    if action_type == "generate_floor_plate":
        return _compile_floor_plate(action)
    if action_type == "generate_facade_grid":
        return _compile_facade_grid(action)
    return [_ensure_semantic_identity(copy.deepcopy(action))]


def _compile_stair_run(action: Dict[str, Any]) -> List[Dict[str, Any]]:
    x = float(action["x"])
    y = float(action["y"])
    base_z = float(action["base_z"])
    width = float(action["width"])
    tread_depth = float(action["tread_depth"])
    riser_height = float(action["riser_height"])
    step_count = int(action["step_count"])
    thickness = float(action["thickness"])
    rotation_deg = float(action.get("direction_deg") or 0.0)
    direction = math.radians(rotation_deg)
    dx = math.cos(direction) * tread_depth
    dy = math.sin(direction) * tread_depth

    base_semantics = dict(action.get("semantics") or {})
    stair_id = str(base_semantics.get("element_id") or _slug(action["name"]))
    treads: List[Dict[str, Any]] = []
    for index in range(step_count):
        semantics = copy.deepcopy(base_semantics)
        semantics["element_id"] = f"{stair_id}__tread_{index + 1:02d}"
        semantics.setdefault("parent_id", stair_id)
        semantics.setdefault("assembly_id", stair_id)
        semantics.setdefault("subrole", "stair_tread")
        group_path = list(semantics.get("group_path") or [])
        if "Treads" not in group_path:
            semantics["group_path"] = group_path + ["Treads"]
        tread = _inherit_metadata(
            action,
            {
                "type": "create_rect_slab",
                "name": f"{action['name']} Tread {index + 1:02d}",
                "storey": action.get("storey"),
                "x": x + (dx * index),
                "y": y + (dy * index),
                "z": base_z + (riser_height * index),
                "width": tread_depth,
                "depth": width,
                "thickness": thickness,
                "rotation_deg": rotation_deg,
                "semantics": semantics,
            },
        )
        treads.append(_ensure_semantic_identity(tread))
    return treads


def _column_label(row: int, col: int) -> str:
    """Generate grid labels like A1, A2, ..., B1, B2, ..., AA1, etc."""
    letters = ""
    r = row
    while True:
        letters = chr(ord("A") + (r % 26)) + letters
        r = r // 26 - 1
        if r < 0:
            break
    return f"{letters}{col + 1}"


def _compile_column_grid(action: Dict[str, Any]) -> List[Dict[str, Any]]:
    grid_name = str(action["name"])
    storey = action.get("storey") or action.get("storey_name")
    origin_x = float(action["grid_origin_x"])
    origin_y = float(action["grid_origin_y"])
    base_z = float(action["base_z"])
    bays_x = int(action["bays_x"])
    bays_y = int(action["bays_y"])
    spacing_x = float(action["spacing_x"])
    spacing_y = float(action["spacing_y"])
    col_width = float(action["column_width"])
    col_depth = float(action["column_depth"])
    col_height = float(action["column_height"])
    rotation_deg = float(action.get("rotation_deg") or 0.0)

    base_semantics = dict(action.get("semantics") or {})
    grid_id = str(base_semantics.get("element_id") or _slug(grid_name))

    columns: List[Dict[str, Any]] = []
    for row in range(bays_y + 1):
        for col in range(bays_x + 1):
            label = _column_label(row, col)
            element_name = f"{grid_name}-Col-{label}"
            x = origin_x + col * spacing_x
            y = origin_y + row * spacing_y

            semantics = copy.deepcopy(base_semantics)
            semantics["element_id"] = f"{grid_id}__col_{label.lower()}"
            semantics.setdefault("parent_id", grid_id)
            semantics.setdefault("assembly_id", grid_id)
            semantics.setdefault("subrole", "grid_column")
            group_path = list(semantics.get("group_path") or [])
            if "Columns" not in group_path:
                semantics["group_path"] = group_path + ["Columns"]

            column = _inherit_metadata(
                action,
                {
                    "type": "create_column",
                    "name": element_name,
                    "storey": storey,
                    "x": x,
                    "y": y,
                    "base_z": base_z,
                    "width": col_width,
                    "depth": col_depth,
                    "height": col_height,
                    "rotation_deg": rotation_deg,
                    "semantics": semantics,
                },
            )
            columns.append(_ensure_semantic_identity(column))
    return columns


def _compile_perimeter_walls(action: Dict[str, Any]) -> List[Dict[str, Any]]:
    wall_name = str(action["name"])
    storey = action.get("storey") or action.get("storey_name")
    corners = list(action["corners"])
    base_z = float(action["base_z"])
    height = float(action["height"])
    thickness = float(action["thickness"])

    base_semantics = dict(action.get("semantics") or {})
    wall_id = str(base_semantics.get("element_id") or _slug(wall_name))

    walls: List[Dict[str, Any]] = []
    count = len(corners)
    for index in range(count):
        x1, y1 = float(corners[index][0]), float(corners[index][1])
        x2, y2 = float(corners[(index + 1) % count][0]), float(corners[(index + 1) % count][1])
        segment_label = f"{index + 1:02d}"
        element_name = f"{wall_name}-Seg-{segment_label}"

        semantics = copy.deepcopy(base_semantics)
        semantics["element_id"] = f"{wall_id}__seg_{segment_label}"
        semantics.setdefault("parent_id", wall_id)
        semantics.setdefault("assembly_id", wall_id)
        semantics.setdefault("subrole", "perimeter_wall")
        group_path = list(semantics.get("group_path") or [])
        if "Walls" not in group_path:
            semantics["group_path"] = group_path + ["Walls"]

        wall = _inherit_metadata(
            action,
            {
                "type": "create_wall",
                "name": element_name,
                "storey": storey,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "base_z": base_z,
                "height": height,
                "thickness": thickness,
                "semantics": semantics,
            },
        )
        walls.append(_ensure_semantic_identity(wall))
    return walls


def _compile_floor_plate(action: Dict[str, Any]) -> List[Dict[str, Any]]:
    plate_name = str(action["name"])
    storey = action.get("storey") or action.get("storey_name")
    x = float(action["x"])
    y = float(action["y"])
    z = float(action["z"])
    length = float(action["length"])
    width = float(action["width"])
    thickness = float(action["thickness"])
    rotation_deg = float(action.get("rotation_deg") or 0.0)
    include_beams = bool(action.get("include_edge_beams"))

    base_semantics = dict(action.get("semantics") or {})
    plate_id = str(base_semantics.get("element_id") or _slug(plate_name))

    results: List[Dict[str, Any]] = []

    # Slab
    slab_semantics = copy.deepcopy(base_semantics)
    slab_semantics["element_id"] = f"{plate_id}__slab"
    slab_semantics.setdefault("parent_id", plate_id)
    slab_semantics.setdefault("assembly_id", plate_id)
    slab_semantics.setdefault("subrole", "floor_slab")
    group_path = list(slab_semantics.get("group_path") or [])
    if "Slabs" not in group_path:
        slab_semantics["group_path"] = group_path + ["Slabs"]

    slab = _inherit_metadata(
        action,
        {
            "type": "create_rect_slab",
            "name": f"{plate_name}-Slab",
            "storey": storey,
            "x": x,
            "y": y,
            "z": z,
            "width": length,
            "depth": width,
            "thickness": thickness,
            "rotation_deg": rotation_deg,
            "semantics": slab_semantics,
        },
    )
    results.append(_ensure_semantic_identity(slab))

    # Edge beams
    if include_beams:
        beam_width = float(action["beam_width"])
        beam_depth = float(action["beam_depth"])
        angle = math.radians(rotation_deg)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # The four corners of the floor plate in world coordinates
        # Local corners: (0,0), (length,0), (length,width), (0,width)
        local_corners = [
            (0.0, 0.0),
            (length, 0.0),
            (length, width),
            (0.0, width),
        ]
        world_corners = [
            (x + cos_a * lx - sin_a * ly, y + sin_a * lx + cos_a * ly)
            for lx, ly in local_corners
        ]

        beam_labels = ["South", "East", "North", "West"]
        for beam_index in range(4):
            bx1, by1 = world_corners[beam_index]
            bx2, by2 = world_corners[(beam_index + 1) % 4]
            beam_label = beam_labels[beam_index]
            element_name = f"{plate_name}-Beam-{beam_label}"

            beam_semantics = copy.deepcopy(base_semantics)
            beam_semantics["element_id"] = f"{plate_id}__beam_{beam_label.lower()}"
            beam_semantics.setdefault("parent_id", plate_id)
            beam_semantics.setdefault("assembly_id", plate_id)
            beam_semantics.setdefault("subrole", "edge_beam")
            beam_group_path = list(beam_semantics.get("group_path") or [])
            if "Beams" not in beam_group_path:
                beam_semantics["group_path"] = beam_group_path + ["Beams"]

            beam = _inherit_metadata(
                action,
                {
                    "type": "create_beam",
                    "name": element_name,
                    "storey": storey,
                    "x1": bx1,
                    "y1": by1,
                    "x2": bx2,
                    "y2": by2,
                    "base_z": z,
                    "width": beam_width,
                    "depth": beam_depth,
                    "semantics": beam_semantics,
                },
            )
            results.append(_ensure_semantic_identity(beam))

    return results


def _compile_facade_grid(action: Dict[str, Any]) -> List[Dict[str, Any]]:
    facade_name = str(action["name"])
    storey = action.get("storey") or action.get("storey_name")
    start_x = float(action["start_x"])
    start_y = float(action["start_y"])
    end_x = float(action["end_x"])
    end_y = float(action["end_y"])
    base_z = float(action["base_z"])
    height = float(action["height"])
    panel_width = float(action["panel_width"])
    panel_height = float(action["panel_height"])
    panel_thickness = float(action["panel_thickness"])
    rotation_degrees = float(action.get("rotation_degrees") or 0.0)

    base_semantics = dict(action.get("semantics") or {})
    facade_id = str(base_semantics.get("element_id") or _slug(facade_name))

    semantics = copy.deepcopy(base_semantics)
    semantics["element_id"] = facade_id
    semantics.setdefault("subrole", "facade_curtain_wall")
    group_path = list(semantics.get("group_path") or [])
    if "Curtain Walls" not in group_path:
        semantics["group_path"] = group_path + ["Curtain Walls"]

    top_z = base_z + height
    curtain_wall = _inherit_metadata(
        action,
        {
            "type": "create_curtain_wall",
            "name": facade_name,
            "storey": storey,
            "x1": start_x,
            "y1": start_y,
            "x2": end_x,
            "y2": end_y,
            "base_z": base_z,
            "top_z": top_z,
            "panel_width": panel_width,
            "panel_height": panel_height,
            "thickness": panel_thickness,
            "rotation_degrees": rotation_degrees,
            "semantics": semantics,
        },
    )
    return [_ensure_semantic_identity(curtain_wall)]


def _apply_edit_action(state: List[Dict[str, Any]], action: Dict[str, Any], *, index: int) -> None:
    matches = [item for item in state if _matches_target(item, action)]
    action_type = action["type"]
    if action_type == "delete_element":
        state[:] = [item for item in state if item not in matches]
        return
    if action_type == "move_element":
        dx = float(action.get("dx") or 0.0)
        dy = float(action.get("dy") or 0.0)
        dz = float(action.get("dz") or 0.0)
        for item in matches:
            _apply_offset(item, dx=dx, dy=dy, dz=dz)
        return
    if action_type == "update_element":
        patch = dict(action.get("patch") or {})
        for item in matches:
            _apply_patch(item, patch)
            _ensure_semantic_identity(item)
        return
    if action_type == "replace_section":
        patch = dict(action.get("patch") or {})
        for field in ("section_id", "width", "depth", "thickness"):
            value = action.get(field)
            if value is not None:
                patch[field] = value
        for item in matches:
            _apply_patch(item, patch)
            _ensure_semantic_identity(item)
        return
    if action_type == "rebuild_branch":
        state[:] = [item for item in state if item not in matches]
        replacements = list(action.get("replacement_actions") or [])
        inherited_storey = _first_non_empty(
            [str(action.get("storey") or "").strip()]
            + [str(item.get("storey") or "").strip() for item in matches]
            + [str(item.get("name") or "").strip() for item in state if item.get("type") == "ensure_storey"]
        )
        inherited_path = _first_non_empty_group_path(action, matches)
        for replacement_index, replacement in enumerate(replacements):
            validate_action(replacement_index, replacement, allow_semantic=True)
            if replacement["type"] in EDIT_ACTIONS:
                raise ValueError("rebuild_branch replacement_actions cannot contain nested edit actions.")
            replacement_action = copy.deepcopy(replacement)
            if inherited_storey and not replacement_action.get("storey") and not replacement_action.get("storey_name"):
                replacement_action["storey"] = inherited_storey
            if inherited_path:
                semantics = dict(replacement_action.get("semantics") or {})
                if not semantics.get("group_path"):
                    semantics["group_path"] = inherited_path
                    replacement_action["semantics"] = semantics
            state.extend(_compile_action(replacement_action))
        return
    raise ValueError(f"Unsupported edit action at compile time: {action_type}")


def _matches_target(item: Dict[str, Any], selector_action: Dict[str, Any]) -> bool:
    target_id = str(selector_action.get("target_id") or "").strip()
    target_name = str(selector_action.get("target_name") or "").strip()
    target_path = [str(part).strip() for part in selector_action.get("target_path") or [] if str(part).strip()]
    target_tags = {
        str(tag).strip().lower()
        for tag in selector_action.get("target_selector_tags") or []
        if str(tag).strip()
    }
    semantics = dict(item.get("semantics") or {})
    item_id = str(semantics.get("element_id") or _slug(str(item.get("name") or ""))).strip()
    item_tags = {str(tag).strip().lower() for tag in semantics.get("selector_tags") or [] if str(tag).strip()}
    item_path = [str(part).strip() for part in semantics.get("group_path") or [] if str(part).strip()]

    if target_id and item_id != target_id:
        return False
    if target_name and str(item.get("name") or "").strip() != target_name:
        return False
    if target_path and item_path[: len(target_path)] != target_path:
        return False
    if target_tags and not (item_tags & target_tags):
        return False
    return any((target_id, target_name, target_path, target_tags))


def _apply_offset(action: Dict[str, Any], *, dx: float, dy: float, dz: float) -> None:
    for field, delta in (("x", dx), ("y", dy), ("z", dz), ("base_z", dz), ("top_z", dz), ("end_z", dz)):
        if field in action and isinstance(action[field], (int, float)):
            action[field] = float(action[field]) + delta
    for field, delta in (("x1", dx), ("x2", dx), ("center_x", dx), ("y1", dy), ("y2", dy), ("center_y", dy)):
        if field in action and isinstance(action[field], (int, float)):
            action[field] = float(action[field]) + delta


def _apply_patch(action: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for key, value in patch.items():
        if key in {"semantics", "presentation", "foundation"} and isinstance(value, dict):
            merged = dict(action.get(key) or {})
            for nested_key, nested_value in value.items():
                if nested_value is None:
                    merged.pop(nested_key, None)
                else:
                    merged[nested_key] = copy.deepcopy(nested_value)
            action[key] = merged
            continue
        if value is None:
            action.pop(key, None)
        else:
            action[key] = copy.deepcopy(value)


def _inherit_metadata(source: Dict[str, Any], compiled: Dict[str, Any]) -> Dict[str, Any]:
    for field in (
        "notes",
        "semantics",
        "presentation",
        "foundation",
        "storey_name",
        "wall_name",
        "offset_along_wall",
        "sill_height",
    ):
        value = source.get(field)
        if value is None or field in compiled:
            continue
        compiled[field] = copy.deepcopy(value)
    return compiled


def _ensure_semantic_identity(action: Dict[str, Any]) -> Dict[str, Any]:
    if action["type"] == "ensure_storey":
        return action
    semantics = dict(action.get("semantics") or {})
    semantics.setdefault("element_id", _slug(str(action.get("name") or "element")))
    semantics.setdefault("collection_key", semantics["element_id"])
    action["semantics"] = semantics
    return action


def _first_non_empty(values: Iterable[str]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _first_non_empty_group_path(selector_action: Dict[str, Any], matches: List[Dict[str, Any]]) -> list[str] | None:
    selector_path = [str(part).strip() for part in selector_action.get("target_path") or [] if str(part).strip()]
    if selector_path:
        return selector_path
    for item in matches:
        semantics = dict(item.get("semantics") or {})
        path = [str(part).strip() for part in semantics.get("group_path") or [] if str(part).strip()]
        if path:
            return path
    return None


def _slug(value: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "element"
