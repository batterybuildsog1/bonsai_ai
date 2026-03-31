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
