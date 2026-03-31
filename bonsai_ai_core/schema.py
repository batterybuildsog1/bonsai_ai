"""Action-plan schema and lightweight validation."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable

from .action_catalog import (
    BUILDABLE_ACTIONS,
    COMMON_ACTION_PROPERTIES,
    EDIT_ACTIONS,
    FOUNDATION_OBJECT,
    PRESENTATION_OBJECT,
    SEMANTIC_ACTIONS,
    SEMANTICS_OBJECT,
    SUPPORTED_ACTIONS,
)
from .errors import ValidationError


def plan_schema() -> Dict[str, Any]:
    """Return a provider-friendly JSON schema."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["version", "units", "summary", "assumptions", "actions"],
        "properties": {
            "version": {"type": "string"},
            "units": {"type": "string", "enum": ["meters"]},
            "summary": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "name"],
                    "properties": COMMON_ACTION_PROPERTIES,
                },
            },
        },
    }


def validate_plan(plan: Dict[str, Any], *, allow_semantic: bool = True) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValidationError("Plan must be a JSON object.")
    for field in ("version", "units", "summary", "assumptions", "actions"):
        if field not in plan:
            raise ValidationError(f"Plan is missing required field '{field}'.")
    if plan["units"] != "meters":
        raise ValidationError("Plan units must be 'meters'.")
    if not isinstance(plan["summary"], str):
        raise ValidationError("Plan summary must be a string.")
    if not isinstance(plan["assumptions"], list) or not all(isinstance(v, str) for v in plan["assumptions"]):
        raise ValidationError("Plan assumptions must be a list of strings.")
    actions = plan["actions"]
    if not isinstance(actions, list) or not actions:
        raise ValidationError("Plan must contain at least one action.")
    for index, action in enumerate(actions):
        validate_action(index, action, allow_semantic=allow_semantic)
    return plan


def pretty_plan(plan: Dict[str, Any]) -> str:
    """Return a deterministic pretty-printed JSON view of a plan."""

    return json.dumps(plan, indent=2, sort_keys=True)


def validate_action(index: int, action: Dict[str, Any], *, allow_semantic: bool = True) -> None:
    if not isinstance(action, dict):
        raise ValidationError(f"Action {index} must be an object.")
    _coerce_numeric_fields(action)
    action_type = action.get("type")
    name = action.get("name")
    if action_type not in SUPPORTED_ACTIONS:
        raise ValidationError(f"Action {index} has unsupported type '{action_type}'.")
    if not allow_semantic and action_type in SEMANTIC_ACTIONS + EDIT_ACTIONS:
        raise ValidationError(f"Action {index} type '{action_type}' must be compiled before execution.")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError(f"Action {index} must include a non-empty name.")

    _validate_optional_object(index, action, "semantics")
    _validate_optional_object(index, action, "presentation")
    _validate_optional_object(index, action, "foundation")
    _validate_optional_object(index, action, "patch")
    _validate_replacement_actions(index, action)

    if action_type in EDIT_ACTIONS:
        _require_target_fields(index, action)
        if action_type == "update_element":
            if not isinstance(action.get("patch"), dict) or not action["patch"]:
                raise ValidationError(f"Action {index} update_element must include a non-empty patch object.")
            return
        if action_type == "delete_element":
            return
        if action_type == "move_element":
            if not any(isinstance(action.get(field), (int, float)) for field in ("dx", "dy", "dz")):
                raise ValidationError(f"Action {index} move_element must include at least one of dx, dy, or dz.")
            return
        if action_type == "replace_section":
            has_patch = isinstance(action.get("patch"), dict) and bool(action["patch"])
            has_section_fields = any(action.get(field) is not None for field in ("section_id", "width", "depth", "thickness"))
            if not has_patch and not has_section_fields:
                raise ValidationError(
                    f"Action {index} replace_section must include section_id, geometry fields, or a non-empty patch."
                )
            return
        if action_type == "rebuild_branch":
            replacements = action.get("replacement_actions")
            if not isinstance(replacements, list) or not replacements:
                raise ValidationError(f"Action {index} rebuild_branch must include one or more replacement_actions.")
            for replacement_index, replacement in enumerate(replacements):
                if not isinstance(replacement, dict):
                    raise ValidationError(
                        f"Action {index} replacement_actions[{replacement_index}] must be an object."
                    )
                replacement_type = replacement.get("type")
                if replacement_type in EDIT_ACTIONS:
                    raise ValidationError(
                        f"Action {index} replacement_actions[{replacement_index}] cannot contain nested edit actions."
                    )
                validate_action(replacement_index, replacement, allow_semantic=True)
            return

    if action_type == "create_beam":
        _require_beam_fields(index, action)
        return
    if action_type == "create_panel":
        _require_panel_fields(index, action)
        return
    if action_type == "create_stair_run":
        _require_stair_run_fields(index, action)
        return
    if action_type == "create_stair_landing":
        _require_numeric_fields(index, action, ("x", "y", "base_z", "width", "depth", "thickness"))
        return
    if action_type == "create_connection_plate":
        _require_numeric_fields(index, action, ("center_x", "center_y", "base_z", "width", "depth", "thickness"))
        return

    numeric_requirements = {
        "ensure_storey": ("elevation",),
        "create_rect_slab": ("x", "y", "z", "width", "depth", "thickness"),
        "create_wall": ("x1", "y1", "x2", "y2", "base_z", "height", "thickness"),
        "create_column": ("x", "y", "base_z", "width", "depth", "height"),
        "create_window": ("offset_along_wall", "sill_height", "width", "height", "thickness"),
        "create_door": ("offset_along_wall", "width", "height", "thickness"),
        "create_curtain_wall": (
            "x1",
            "y1",
            "x2",
            "y2",
            "base_z",
            "top_z",
            "panel_width",
            "panel_height",
            "thickness",
        ),
        "create_footing": ("x", "y", "base_z", "length", "width", "thickness"),
    }
    _require_numeric_fields(index, action, numeric_requirements[action_type])
    if action_type == "create_curtain_wall" and action["top_z"] <= action["base_z"]:
        raise ValidationError(f"Action {index} has top_z <= base_z.")
    if action_type in {"create_window", "create_door"}:
        _require_string_fields(index, action, ("wall_name",))


def _validate_optional_object(index: int, action: Dict[str, Any], field: str) -> None:
    value = action.get(field)
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValidationError(f"Action {index} field '{field}' must be an object when provided.")


def _validate_replacement_actions(index: int, action: Dict[str, Any]) -> None:
    replacements = action.get("replacement_actions")
    if replacements is None:
        return
    if not isinstance(replacements, list):
        raise ValidationError(f"Action {index} field 'replacement_actions' must be an array when provided.")
    for replacement_index, replacement in enumerate(replacements):
        try:
            validate_action(replacement_index, replacement, allow_semantic=True)
        except ValidationError as exc:
            raise ValidationError(f"Action {index} replacement_actions[{replacement_index}] is invalid: {exc}") from exc


def _require_target_fields(index: int, action: Dict[str, Any]) -> None:
    has_target = any(
        action.get(field)
        for field in ("target_id", "target_name", "target_path", "target_selector_tags")
    )
    if not has_target:
        raise ValidationError(
            f"Action {index} semantic edit must include target_id, target_name, target_path, or target_selector_tags."
        )


def _require_string_fields(index: int, action: Dict[str, Any], fields: Iterable[str]) -> None:
    for field in fields:
        value = action.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"Action {index} field '{field}' must be a non-empty string.")


def _require_numeric_fields(index: int, action: Dict[str, Any], fields: Iterable[str]) -> None:
    for field in fields:
        value = action.get(field)
        if not isinstance(value, (int, float)):
            raise ValidationError(f"Action {index} field '{field}' must be numeric.")
        if field not in (
            "x",
            "y",
            "z",
            "x1",
            "y1",
            "x2",
            "y2",
            "base_z",
            "top_z",
            "elevation",
            "center_x",
            "center_y",
            "direction_deg",
            "rotation_deg",
            "rotation_degrees",
            "end_z",
            "sill_height",
        ):
            if value <= 0:
                raise ValidationError(f"Action {index} field '{field}' must be greater than zero.")


def _coerce_numeric_fields(action: Dict[str, Any]) -> None:
    action_type = action.get("type")
    if action_type == "create_column" and "base_z" not in action and "z" in action:
        action["base_z"] = action.get("z")
    if action_type == "create_rect_slab" and "z" not in action and "elevation" in action:
        action["z"] = action.get("elevation")
    if action_type in {"create_panel", "create_stair_landing", "create_connection_plate", "create_footing"} and "base_z" not in action:
        if "z" in action:
            action["base_z"] = action.get("z")
        elif "elevation" in action:
            action["base_z"] = action.get("elevation")
    if action_type == "create_connection_plate":
        if "center_x" not in action and "x" in action:
            action["center_x"] = action.get("x")
        if "center_y" not in action and "y" in action:
            action["center_y"] = action.get("y")
    if action_type == "create_panel" and "orientation" not in action:
        action["orientation"] = "vertical"
    if action_type in {"create_window", "create_door", "create_footing"} and "storey_name" in action and "storey" not in action:
        action["storey"] = action.get("storey_name")
    patch = action.get("patch")
    if isinstance(patch, dict):
        _coerce_numeric_patch(patch)
    replacements = action.get("replacement_actions")
    if isinstance(replacements, list):
        for replacement in replacements:
            if isinstance(replacement, dict):
                _coerce_numeric_fields(replacement)
    foundation = action.get("foundation")
    if isinstance(foundation, dict):
        if "imposed_load_kN" not in foundation and foundation.get("imposed_load_kn") is not None:
            foundation["imposed_load_kN"] = foundation["imposed_load_kn"]
        if "service_reaction_kN" not in foundation and foundation.get("service_reaction_kn") is not None:
            foundation["service_reaction_kN"] = foundation["service_reaction_kn"]
        if "material_key" not in action and isinstance(action.get("presentation"), dict):
            presentation = action["presentation"]
            if presentation.get("material_preset") is not None and presentation.get("material_key") is None:
                presentation["material_key"] = presentation["material_preset"]
            if presentation.get("style_preset") is not None and presentation.get("presentation_style") is None:
                presentation["presentation_style"] = presentation["style_preset"]

    numeric_fields = {
        "dx",
        "dy",
        "dz",
        "x",
        "y",
        "z",
        "x1",
        "y1",
        "x2",
        "y2",
        "width",
        "depth",
        "length",
        "height",
        "thickness",
        "center_x",
        "center_y",
        "tread_depth",
        "riser_height",
        "step_count",
        "direction_deg",
        "elevation",
        "rotation_deg",
        "rotation_degrees",
        "panel_width",
        "panel_height",
        "panel_gap",
        "base_z",
        "top_z",
        "end_z",
        "offset_along_wall",
        "sill_height",
        "dx",
        "dy",
        "dz",
    }
    for field in numeric_fields:
        value = action.get(field)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            try:
                parsed = float(stripped)
            except ValueError:
                continue
            if field in {"x", "y", "z", "x1", "y1", "x2", "y2", "elevation", "step_count"} and parsed.is_integer():
                action[field] = int(parsed)
            else:
                action[field] = parsed


def _coerce_numeric_patch(patch: Dict[str, Any]) -> None:
    numeric_fields = {
        "x",
        "y",
        "z",
        "x1",
        "y1",
        "x2",
        "y2",
        "width",
        "depth",
        "length",
        "height",
        "thickness",
        "center_x",
        "center_y",
        "tread_depth",
        "riser_height",
        "step_count",
        "direction_deg",
        "elevation",
        "rotation_deg",
        "rotation_degrees",
        "panel_width",
        "panel_height",
        "panel_gap",
        "base_z",
        "top_z",
        "end_z",
        "offset_along_wall",
        "sill_height",
        "dx",
        "dy",
        "dz",
    }
    for field in numeric_fields:
        value = patch.get(field)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            try:
                parsed = float(stripped)
            except ValueError:
                continue
            if field == "step_count" and parsed.is_integer():
                patch[field] = int(parsed)
            else:
                patch[field] = parsed


def _require_beam_fields(index: int, action: Dict[str, Any]) -> None:
    endpoint_fields = ("x1", "y1", "x2", "y2", "base_z", "width", "depth")
    legacy_fields = ("x", "y", "base_z", "width", "depth", "height")

    if all(field in action for field in endpoint_fields):
        _require_numeric_fields(index, action, endpoint_fields)
        if action["x1"] == action["x2"] and action["y1"] == action["y2"]:
            raise ValidationError(f"Action {index} beam span must have non-zero length.")
        return

    if all(field in action for field in legacy_fields):
        _require_numeric_fields(index, action, legacy_fields)
        return

    raise ValidationError(
        f"Action {index} create_beam must provide either endpoint fields "
        "x1/y1/x2/y2/base_z/width/depth or origin fields x/y/base_z/width/depth/height."
    )


def _require_panel_fields(index: int, action: Dict[str, Any]) -> None:
    orientation = str(action.get("orientation") or "vertical")
    if orientation == "horizontal":
        _require_numeric_fields(index, action, ("x", "y", "base_z", "width", "depth", "thickness"))
        return
    if orientation != "vertical":
        raise ValidationError(f"Action {index} panel orientation '{orientation}' is unsupported.")
    _require_numeric_fields(index, action, ("x", "y", "base_z", "width", "height", "thickness"))


def _require_stair_run_fields(index: int, action: Dict[str, Any]) -> None:
    _require_numeric_fields(
        index,
        action,
        ("x", "y", "base_z", "width", "tread_depth", "riser_height", "step_count", "thickness"),
    )
