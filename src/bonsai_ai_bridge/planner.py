from __future__ import annotations

from textwrap import dedent
from typing import Any, Optional

from bonsai_ai_bridge.providers import DEFAULT_MODELS, get_provider
from bonsai_ai_bridge.schemas import PLANNER_JSON_SCHEMA, BuildingPlan, action_spec_text, parse_plan_text, validate_plan


SYSTEM_PROMPT = dedent(
    """
    You are an architectural BIM planning assistant for Blender + Bonsai.
    Convert the user's request into a concise execution plan for IFC-native authoring.

    Rules:
    - Output only actions supported by the schema.
    - Use meters for all dimensions and coordinates.
    - Prefer simple, buildable geometry over vague descriptions.
    - If the user asks for a whole building, include ensure_project first.
    - If multiple levels are implied, create ensure_storey actions before geometry for those levels.
    - For walls, slabs, columns, beams, panels, doors, and windows, use explicit dimensions.
    - For curtain walls, prefer create_panel_grid or multiple create_panel actions.
    - If a door or window should cut into a wall, set the host field to the exact wall name used earlier.
    - Keep assumptions brief and explicit.
    - Do not invent unsupported BIM systems or materials.
    """
).strip()


def build_user_prompt(prompt: str, scene_context: Optional[dict[str, Any]]) -> str:
    context_lines = ["Current scene context:"]
    if not scene_context:
        context_lines.append("- No context provided")
    else:
        for key, value in scene_context.items():
            context_lines.append(f"- {key}: {value}")

    return dedent(
        f"""
        User request:
        {prompt.strip()}

        Supported actions:
        {action_spec_text()}

        Coordinate conventions:
        - x/y/z are object base-center coordinates in meters.
        - rotation_degrees rotates around global Z.
        - Slabs use width (local X) and depth (local Y).
        - Walls use length (local X) and thickness (local Y).
        - Doors and windows are simple solid fillings unless a host wall is provided.

        {chr(10).join(context_lines)}
        """
    ).strip()


async def generate_plan(
    *,
    provider_name: str,
    model: Optional[str],
    prompt: str,
    scene_context: Optional[dict[str, Any]] = None,
) -> BuildingPlan:
    provider = get_provider(provider_name)
    target_model = model or DEFAULT_MODELS[provider.name]
    user_prompt = build_user_prompt(prompt, scene_context)
    raw_text = await provider.generate_plan_text(
        model=target_model,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        json_schema=PLANNER_JSON_SCHEMA,
    )
    parsed = parse_plan_text(raw_text)
    validated, issues = validate_plan(parsed)
    if issues:
        joined = "; ".join(f"action {issue.action_index}: {issue.message}" for issue in issues)
        raise ValueError(f"Model returned an invalid plan: {joined}")
    return validated
