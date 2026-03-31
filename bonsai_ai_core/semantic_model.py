"""Semantic model normalization and edit/rebuild helpers."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, List

from .action_catalog import EDIT_ACTIONS
from .schema import validate_plan


JsonDict = Dict[str, Any]


def build_semantic_model(plan: Dict[str, Any]) -> Dict[str, Any]:
    authored = copy.deepcopy(plan)
    validate_plan(authored)

    elements: List[JsonDict] = []
    seen_ids: set[str] = set()
    for index, action in enumerate(authored["actions"]):
        if action["type"] in EDIT_ACTIONS:
            _apply_edit_action(elements, action, seen_ids)
            continue
        elements.append(_normalize_element(action, index=index, seen_ids=seen_ids))

    return {
        "version": authored["version"],
        "units": authored["units"],
        "summary": authored["summary"],
        "assumptions": list(authored["assumptions"]),
        "elements": [
            {
                "id": element["id"],
                "type": element["type"],
                "name": element["name"],
                "storey": element["storey"],
                "parent_id": element["parent_id"],
                "assembly_id": element["assembly_id"],
                "branch_path": list(element["branch_path"]),
                "selector_tags": list(element["selector_tags"]),
                "action": copy.deepcopy(element["action"]),
            }
            for element in elements
        ],
    }


def semantic_model_to_plan(model: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "version": model["version"],
        "units": model["units"],
        "summary": model["summary"],
        "assumptions": list(model["assumptions"]),
        "actions": [copy.deepcopy(element["action"]) for element in model.get("elements", [])],
    }


def _apply_edit_action(elements: List[JsonDict], action: JsonDict, seen_ids: set[str]) -> None:
    action_type = action["type"]
    matched = _match_elements(elements, action)
    if action_type == "update_element":
        patch = dict(action.get("patch") or {})
        for element in matched:
            _merge_action_patch(element["action"], patch)
            _refresh_element_index(element)
        return
    if action_type == "delete_element":
        doomed_ids = {element["id"] for element in matched}
        elements[:] = [element for element in elements if element["id"] not in doomed_ids]
        return
    if action_type == "move_element":
        dx = float(action.get("dx") or 0.0)
        dy = float(action.get("dy") or 0.0)
        dz = float(action.get("dz") or 0.0)
        for element in matched:
            _move_action(element["action"], dx=dx, dy=dy, dz=dz)
            _refresh_element_index(element)
        return
    if action_type == "replace_section":
        patch = dict(action.get("patch") or {})
        for field in ("section_id", "width", "depth", "thickness"):
            if action.get(field) is not None:
                patch[field] = action[field]
        for element in matched:
            _merge_action_patch(element["action"], patch)
            _refresh_element_index(element)
        return
    if action_type == "rebuild_branch":
        replacements = list(action.get("replacement_actions") or [])
        doomed_ids = {element["id"] for element in matched}
        insert_at = min((index for index, element in enumerate(elements) if element["id"] in doomed_ids), default=len(elements))
        elements[:] = [element for element in elements if element["id"] not in doomed_ids]
        inherited_storey = _first_non_empty(
            [str(action.get("storey") or "").strip()] + [str(element.get("storey") or "").strip() for element in matched]
        )
        inherited_path = _first_non_empty_branch_path(action, matched)
        inherited_parent_id = _first_non_empty(
            [str((element.get("parent_id") or "")) for element in matched]
        )
        inherited_assembly_id = _first_non_empty(
            [str((element.get("assembly_id") or "")) for element in matched]
        )
        normalized = [
            _normalize_element(
                _inherit_rebuild_defaults(
                    replacement,
                    storey=inherited_storey,
                    branch_path=inherited_path,
                    parent_id=inherited_parent_id,
                    assembly_id=inherited_assembly_id,
                ),
                index=insert_at + offset,
                seen_ids=seen_ids,
            )
            for offset, replacement in enumerate(replacements)
        ]
        elements[insert_at:insert_at] = normalized
        return
    raise ValueError(f"Unsupported semantic edit action: {action_type}")


def _normalize_element(action: JsonDict, *, index: int, seen_ids: set[str]) -> JsonDict:
    normalized = copy.deepcopy(action)
    semantics = _semantic_payload(normalized)
    element_id = _unique_element_id(
        str(semantics.get("element_id") or _suggest_element_id(normalized, index=index)),
        seen_ids,
    )
    semantics["element_id"] = element_id
    normalized["semantics"] = semantics

    branch_path = _branch_path(normalized, semantics)
    selector_tags = [str(tag) for tag in semantics.get("selector_tags") or [] if str(tag).strip()]
    return {
        "id": element_id,
        "type": str(normalized["type"]),
        "name": str(normalized["name"]),
        "storey": normalized.get("storey") or normalized.get("storey_name"),
        "parent_id": semantics.get("parent_id"),
        "assembly_id": semantics.get("assembly_id"),
        "branch_path": branch_path,
        "selector_tags": selector_tags,
        "action": normalized,
    }


def _semantic_payload(action: JsonDict) -> JsonDict:
    semantics = dict(action.get("semantics") or {})
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
        value = action.get(field)
        if value is not None and field not in semantics:
            semantics[field] = value
    return semantics


def _suggest_element_id(action: JsonDict, *, index: int) -> str:
    storey = str(action.get("storey") or action.get("storey_name") or "global")
    base = f"{action['type']}-{storey}-{action['name']}-{index + 1}"
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug or f"element-{index + 1}"


def _unique_element_id(candidate: str, seen_ids: set[str]) -> str:
    value = candidate
    suffix = 2
    while value in seen_ids:
        value = f"{candidate}-{suffix}"
        suffix += 1
    seen_ids.add(value)
    return value


def _branch_path(action: JsonDict, semantics: JsonDict) -> List[str]:
    action_type = str(action["type"])
    if action_type == "ensure_storey":
        return [str(action["name"])]
    path: List[str] = []
    storey = action.get("storey") or action.get("storey_name")
    if storey:
        path.append(str(storey))
    for field in ("role", "system_name", "subrole"):
        value = semantics.get(field)
        if value:
            path.append(str(value))
    group_path = semantics.get("group_path") or []
    if isinstance(group_path, str):
        group_path = [group_path]
    for value in group_path:
        token = str(value).strip()
        if token:
            path.append(token)
    if not path:
        path.append(str(action["name"]))
    return path


def _match_elements(elements: Iterable[JsonDict], selector: JsonDict) -> List[JsonDict]:
    target_id = selector.get("target_id")
    target_name = selector.get("target_name")
    target_path = [str(part).strip() for part in selector.get("target_path") or [] if str(part).strip()]
    target_tags = {str(tag).strip() for tag in selector.get("target_selector_tags") or [] if str(tag).strip()}

    matches: List[JsonDict] = []
    for element in elements:
        if target_id and element["id"] != target_id:
            continue
        if target_name and element["name"] != target_name:
            continue
        if target_path and not _path_matches(element["branch_path"], target_path):
            continue
        if target_tags and not target_tags.intersection(set(element["selector_tags"])):
            continue
        matches.append(element)
    return matches


def _path_matches(branch_path: List[str], target_path: List[str]) -> bool:
    if len(target_path) > len(branch_path):
        return False
    if branch_path[: len(target_path)] == target_path:
        return True
    for index in range(0, len(branch_path) - len(target_path) + 1):
        if branch_path[index : index + len(target_path)] == target_path:
            return True
    return False


def _merge_action_patch(action: JsonDict, patch: JsonDict) -> None:
    for key, value in patch.items():
        if key in {"semantics", "presentation", "foundation"} and isinstance(value, dict):
            current = dict(action.get(key) or {})
            current.update(value)
            action[key] = current
            continue
        action[key] = copy.deepcopy(value)


def _move_action(action: JsonDict, *, dx: float, dy: float, dz: float) -> None:
    for field in ("x", "x1", "x2", "center_x"):
        if isinstance(action.get(field), (int, float)):
            action[field] = float(action[field]) + dx
    for field in ("y", "y1", "y2", "center_y"):
        if isinstance(action.get(field), (int, float)):
            action[field] = float(action[field]) + dy
    for field in ("z", "base_z", "top_z", "end_z", "elevation"):
        if isinstance(action.get(field), (int, float)):
            action[field] = float(action[field]) + dz
    if isinstance(action.get("sill_height"), (int, float)):
        action["sill_height"] = float(action["sill_height"]) + dz
    if isinstance(action.get("offset_along_wall"), (int, float)) and dx:
        action["offset_along_wall"] = float(action["offset_along_wall"]) + dx


def _refresh_element_index(element: JsonDict) -> None:
    semantics = _semantic_payload(element["action"])
    semantics["element_id"] = element["id"]
    element["action"]["semantics"] = semantics
    element["type"] = str(element["action"]["type"])
    element["name"] = str(element["action"]["name"])
    element["storey"] = element["action"].get("storey") or element["action"].get("storey_name")
    element["parent_id"] = semantics.get("parent_id")
    element["assembly_id"] = semantics.get("assembly_id")
    element["branch_path"] = _branch_path(element["action"], semantics)
    element["selector_tags"] = [str(tag) for tag in semantics.get("selector_tags") or [] if str(tag).strip()]


def _first_non_empty(values: Iterable[str]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _first_non_empty_branch_path(selector: JsonDict, matched: Iterable[JsonDict]) -> List[str] | None:
    selector_path = [str(part).strip() for part in selector.get("target_path") or [] if str(part).strip()]
    if selector_path:
        return selector_path
    for element in matched:
        semantics = dict(element.get("action", {}).get("semantics") or {})
        group_path = [str(part).strip() for part in semantics.get("group_path") or [] if str(part).strip()]
        if group_path:
            return group_path
    return None


def _inherit_rebuild_defaults(
    replacement: JsonDict,
    *,
    storey: str | None,
    branch_path: List[str] | None,
    parent_id: str | None,
    assembly_id: str | None,
) -> JsonDict:
    normalized = copy.deepcopy(replacement)
    if storey and not normalized.get("storey") and not normalized.get("storey_name"):
        normalized["storey"] = storey
    semantics = dict(normalized.get("semantics") or {})
    if branch_path and not semantics.get("group_path"):
        semantics["group_path"] = list(branch_path)
    if parent_id and not semantics.get("parent_id"):
        semantics["parent_id"] = parent_id
    if assembly_id and not semantics.get("assembly_id"):
        semantics["assembly_id"] = assembly_id
    if semantics:
        normalized["semantics"] = semantics
    return normalized
