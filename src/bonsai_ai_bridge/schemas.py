from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError, field_validator


SUPPORTED_ACTIONS: dict[str, dict[str, Any]] = {
    "ensure_project": {
        "description": "Create an IFC project if one does not already exist.",
        "required": [],
        "optional": ["project_name", "site_name", "building_name", "default_storey", "schema"],
    },
    "ensure_storey": {
        "description": "Create or reuse a building storey by name and elevation in meters.",
        "required": ["storey", "elevation"],
        "optional": [],
    },
    "create_slab": {
        "description": "Create a rectangular slab. x/y/z are base-center coordinates in meters.",
        "required": ["x", "y", "z", "width", "depth", "thickness"],
        "optional": ["storey", "rotation_degrees", "ifc_class"],
    },
    "create_wall": {
        "description": "Create a straight wall box. x/y/z are base-center coordinates in meters.",
        "required": ["x", "y", "z", "length", "thickness", "height"],
        "optional": ["storey", "rotation_degrees", "ifc_class"],
    },
    "create_column": {
        "description": "Create a rectangular column. x/y/z are base-center coordinates in meters.",
        "required": ["x", "y", "z", "width", "depth", "height"],
        "optional": ["storey", "rotation_degrees", "ifc_class"],
    },
    "create_beam": {
        "description": "Create a rectangular beam. x/y/z are base-center coordinates in meters.",
        "required": ["x", "y", "z", "length", "width", "depth"],
        "optional": ["storey", "rotation_degrees", "ifc_class"],
    },
    "create_panel": {
        "description": "Create a vertical panel or plate. x/y/z are base-center coordinates in meters.",
        "required": ["x", "y", "z", "width", "height", "thickness"],
        "optional": ["storey", "rotation_degrees", "ifc_class"],
    },
    "create_panel_grid": {
        "description": "Create a grid of IfcPlate panels for a curtain-wall-like facade.",
        "required": ["x", "y", "z", "panel_width", "panel_height", "thickness", "columns", "rows"],
        "optional": ["storey", "gap_x", "gap_y", "rotation_degrees"],
    },
    "create_window": {
        "description": "Create a window box. If host is supplied and matches a wall, create an opening.",
        "required": ["x", "y", "z", "width", "depth", "height"],
        "optional": ["storey", "rotation_degrees", "host"],
    },
    "create_door": {
        "description": "Create a door box. If host is supplied and matches a wall, create an opening.",
        "required": ["x", "y", "z", "width", "depth", "height"],
        "optional": ["storey", "rotation_degrees", "host"],
    },
}


PLANNER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "assumptions", "actions"],
    "properties": {
        "summary": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "params"],
                "properties": {
                    "kind": {"type": "string", "enum": sorted(SUPPORTED_ACTIONS.keys())},
                    "name": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
        },
    },
}


class Action(BaseModel):
    kind: str
    name: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        if value not in SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported action kind: {value}")
        return value


class BuildingPlan(BaseModel):
    summary: str
    assumptions: List[str] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)


@dataclass
class ValidationIssue:
    action_index: int
    message: str


def action_spec_text() -> str:
    lines: List[str] = []
    for kind, spec in SUPPORTED_ACTIONS.items():
        required = ", ".join(spec["required"]) or "none"
        optional = ", ".join(spec["optional"]) or "none"
        lines.append(f"- {kind}: {spec['description']}")
        lines.append(f"  required params: {required}")
        lines.append(f"  optional params: {optional}")
    return "\n".join(lines)


def parse_plan_text(raw_text: str) -> BuildingPlan:
    text = raw_text.strip()
    if not text:
        raise ValueError("Empty model response")

    try:
        return BuildingPlan.model_validate_json(text)
    except ValidationError:
        pass
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Model response did not contain a JSON object")

    candidate = text[start : end + 1]
    return BuildingPlan.model_validate_json(candidate)


def validate_plan(plan: BuildingPlan) -> Tuple[BuildingPlan, List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    normalized_actions: List[Action] = []

    for index, action in enumerate(plan.actions):
        spec = SUPPORTED_ACTIONS[action.kind]
        params = dict(action.params)

        for key in spec["required"]:
            if key not in params:
                issues.append(ValidationIssue(index, f"Missing required param '{key}'"))

        for key, value in list(params.items()):
            if isinstance(value, (int, float)):
                continue
            if key in {"x", "y", "z", "width", "depth", "height", "thickness", "length", "rotation_degrees", "panel_width", "panel_height", "gap_x", "gap_y", "elevation"}:
                try:
                    params[key] = float(value)
                except (TypeError, ValueError):
                    issues.append(ValidationIssue(index, f"Param '{key}' must be numeric"))
            if key in {"rows", "columns"}:
                try:
                    params[key] = int(value)
                except (TypeError, ValueError):
                    issues.append(ValidationIssue(index, f"Param '{key}' must be an integer"))

        normalized_actions.append(Action(kind=action.kind, name=action.name, params=params))

    normalized = BuildingPlan(summary=plan.summary, assumptions=plan.assumptions, actions=normalized_actions)
    return normalized, issues
