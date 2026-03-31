from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    from bonsai_ai_core.defaults import DEFAULT_MODELS as CORE_DEFAULT_MODELS
    from bonsai_ai_core.defaults import ENV_KEYS
    from bonsai_ai_core import build_plan as build_core_plan
    from bonsai_ai_core import compile_plan as compile_core_plan
except ModuleNotFoundError:  # pragma: no cover - compatibility for script entrypoints that only add ./src
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from bonsai_ai_core.defaults import DEFAULT_MODELS as CORE_DEFAULT_MODELS
    from bonsai_ai_core.defaults import ENV_KEYS
    from bonsai_ai_core import build_plan as build_core_plan
    from bonsai_ai_core import compile_plan as compile_core_plan


JsonDict = Dict[str, object]

DEFAULT_MODELS = {
    "openai": CORE_DEFAULT_MODELS["openai"],
    "anthropic": CORE_DEFAULT_MODELS["anthropic"],
    "gemini": CORE_DEFAULT_MODELS["google"],
}

DEFAULT_ENV_VARS = {
    "openai": ENV_KEYS["openai"][0],
    "anthropic": ENV_KEYS["anthropic"][0],
    "gemini": ENV_KEYS["google"][0],
}


@dataclass
class PlannedToolCall:
    id: str
    name: str
    arguments: JsonDict


@dataclass
class PlanResult:
    provider: str
    model: str
    tool_calls: List[PlannedToolCall]
    raw_text: str = ""


class PlannerError(RuntimeError):
    pass


_TOOL_NAME_MAP = {
    "ensure_storey": "ensure_storey",
    "create_rect_slab": "create_rectangular_slab",
    "create_wall": "create_wall",
    "create_column": "create_column",
    "create_beam": "create_beam",
    "create_panel": "create_panel",
    "create_window": "create_window",
    "create_door": "create_door",
    "create_curtain_wall": "create_curtain_wall",
    "create_footing": "create_footing",
}


def _provider_name(provider: str) -> str:
    value = provider.strip().lower()
    if value == "gemini":
        return "google"
    return value


def _scene_prompt(user_prompt: str, scene_summary: str, progress_summary: str = "") -> str:
    parts = [user_prompt.strip()]
    if scene_summary.strip():
        parts.append(f"Scene summary:\n{scene_summary.strip()}")
    if progress_summary.strip():
        parts.append(f"Completed work so far:\n{progress_summary.strip()}")
    return "\n\n".join(part for part in parts if part)


def _resolve_api_key(api_key: str | None, api_key_env: str | None) -> str | None:
    if api_key:
        return api_key
    if api_key_env:
        value = os.getenv(api_key_env)
        if value:
            return value
    return None


def _to_tool_call(action: Dict[str, object], index: int) -> PlannedToolCall:
    action_type = str(action["type"])
    try:
        tool_name = _TOOL_NAME_MAP[action_type]
    except KeyError as exc:
        raise PlannerError(f"Compiled plan emitted unsupported action '{action_type}' for legacy tool execution.") from exc
    storey_name = action.get("storey_name") or action.get("storey")
    if tool_name == "ensure_storey":
        arguments = {"name": action["name"], "elevation": action["elevation"]}
    elif tool_name == "create_rectangular_slab":
        arguments = {
            "name": action["name"],
            "storey_name": storey_name,
            "x": action["x"],
            "y": action["y"],
            "z": action["z"],
            "length": action.get("length", action["width"]),
            "width": action.get("depth", action["width"]),
            "thickness": action["thickness"],
            "rotation_deg": action.get("rotation_deg"),
            "semantics": action.get("semantics"),
            "presentation": action.get("presentation"),
            "foundation": action.get("foundation"),
        }
    elif tool_name == "create_wall":
        arguments = {
            "name": action["name"],
            "storey_name": storey_name,
            "start_x": action["x1"],
            "start_y": action["y1"],
            "end_x": action["x2"],
            "end_y": action["y2"],
            "base_z": action["base_z"],
            "height": action["height"],
            "thickness": action["thickness"],
            "semantics": action.get("semantics"),
            "presentation": action.get("presentation"),
            "foundation": action.get("foundation"),
        }
    elif tool_name == "create_beam":
        arguments = {
            "name": action["name"],
            "storey_name": storey_name,
            "start_x": action["x1"],
            "start_y": action["y1"],
            "end_x": action["x2"],
            "end_y": action["y2"],
            "base_z": action["base_z"],
            "end_z": action.get("end_z"),
            "width": action["width"],
            "depth": action["depth"],
            "semantics": action.get("semantics"),
            "presentation": action.get("presentation"),
            "foundation": action.get("foundation"),
        }
    elif tool_name == "create_curtain_wall" and all(key in action for key in ("x1", "y1", "x2", "y2")):
        dx = float(action["x2"]) - float(action["x1"])
        dy = float(action["y2"]) - float(action["y1"])
        arguments = {
            "name": action["name"],
            "storey_name": storey_name,
            "x": action["x1"],
            "y": action["y1"],
            "base_z": action["base_z"],
            "width": math.hypot(dx, dy),
            "height": float(action["top_z"]) - float(action["base_z"]),
            "rotation_degrees": math.degrees(math.atan2(dy, dx)),
            "panel_width": action["panel_width"],
            "panel_height": action["panel_height"],
            "panel_thickness": action.get("panel_thickness", action["thickness"]),
            "semantics": action.get("semantics"),
            "presentation": action.get("presentation"),
            "foundation": action.get("foundation"),
        }
    else:
        arguments = dict(action)
        arguments.pop("type", None)
        if storey_name is not None:
            arguments["storey_name"] = storey_name
        arguments.pop("storey", None)
    arguments = {key: value for key, value in arguments.items() if value is not None}
    return PlannedToolCall(id=f"compiled-{index:03d}", name=tool_name, arguments=arguments)


def create_plan(
    provider: str,
    user_prompt: str,
    scene_summary: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_key_env: Optional[str] = None,
    progress_summary: str = "",
) -> PlanResult:
    provider_name = provider.strip().lower()
    if provider_name not in DEFAULT_MODELS:
        raise PlannerError(f"Unsupported provider: {provider}")
    core_provider = _provider_name(provider_name)
    try:
        authored_plan = build_core_plan(
            prompt=_scene_prompt(user_prompt, scene_summary, progress_summary),
            provider=core_provider,
            model=model or DEFAULT_MODELS[provider_name],
            api_key=_resolve_api_key(api_key, api_key_env),
        )
        compiled_plan = compile_core_plan(authored_plan)
    except Exception as exc:
        raise PlannerError(str(exc)) from exc

    tool_calls = [_to_tool_call(action, index) for index, action in enumerate(compiled_plan["actions"], start=1)]
    return PlanResult(
        provider=provider_name,
        model=model or DEFAULT_MODELS[provider_name],
        tool_calls=tool_calls,
        raw_text="COMPLETE" if not tool_calls else "",
    )
