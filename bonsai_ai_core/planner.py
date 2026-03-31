"""Prompting and validation for Bonsai AI plans."""

from __future__ import annotations

from typing import Any, Dict

from .errors import ProviderError, ValidationError
from .providers import ProviderRequest, get_provider
from .schema import validate_plan


SYSTEM_PROMPT = """You are Bonsai AI, a BIM planning model for Blender + Bonsai.

Return only JSON that matches the provided schema.

Rules:
- Use metric units in meters.
- Use only these action types: ensure_storey, create_rect_slab, create_wall, create_column, create_beam, create_panel, create_window, create_door, create_curtain_wall, create_footing, create_stair_run, create_stair_landing, create_connection_plate, generate_column_grid, generate_perimeter_walls, generate_floor_plate, generate_facade_grid, update_element, delete_element, move_element, replace_section, rebuild_branch.
- Prefer a small number of clear actions over noisy micro-actions.
- **Parametric generators** reduce token usage and planner rounds for repetitive patterns. Prefer these over many individual actions:
  - `generate_column_grid` for regular column grids. Specify bays_x, bays_y, spacing_x, spacing_y, and column dimensions. Compiles to (bays_x+1)*(bays_y+1) create_column calls.
  - `generate_perimeter_walls` for walls around a footprint polygon. Specify corners as [[x,y],...], height, and thickness. Compiles to one create_wall per edge.
  - `generate_floor_plate` for a rectangular slab with optional perimeter beams. Set include_edge_beams=true with beam_width and beam_depth for framed floors.
  - `generate_facade_grid` for curtain wall facades. Specify start/end points and panel dimensions. Compiles to a single create_curtain_wall.
- Fall back to individual create_* actions only when the pattern is irregular or custom.
- Interior partitions should be modeled as create_wall actions.
- Steel framing members should be modeled as create_beam actions when needed.
- Steel connection details should prefer create_connection_plate actions with center_x, center_y, base_z, width, depth, and thickness.
- Wall or facade panels may be modeled as create_panel actions or create_curtain_wall actions.
- Doors and windows should use create_door and create_window when the prompt calls for actual openings.
- Curtain walls should be modeled as create_curtain_wall actions.
- Footings should use create_footing and should include foundation metadata with imposed load, concrete strength, and rebar assumptions when the prompt includes structural intent.
- Use nested metadata objects when helpful:
  - `semantics` for grouping, naming trees, selector tags, and view modes.
  - `presentation` for glazing, material, storefront, and frame intent.
  - `foundation` for footing loads, bearing assumptions, concrete strength, and reinforcement.
- Use `semantics.group_path` to create a review tree from broad systems to specific subgroups.
- When the prompt is editing an existing model and selection context is provided, prefer semantic edit actions over recreating the whole building.
- When editing a selected object, target `target_id` from the provided selection context whenever available. Use `target_path` or `target_selector_tags` only when the user is clearly addressing a branch or repeated family.
- Use `patch` for nested updates to `semantics`, `presentation`, or `foundation`.
- Use `move_element` with `dx`, `dy`, and `dz` for spatial adjustments.
- Use `replace_section` for real steel or shell sizing changes.
- Use `rebuild_branch` with `replacement_actions` only when a local branch needs to be regenerated instead of patched.
- If the prompt asks for stairs, prefer create_stair_run and create_stair_landing actions and note the approximation in assumptions.
- A create_stair_run should include x, y, base_z, width, tread_depth, riser_height, step_count, thickness, and optional direction_deg.
- A create_stair_landing should include x, y, base_z, width, depth, thickness, and optional direction_deg.
- If the prompt asks for unsupported element types, mention the simplification in assumptions and approximate with the supported primitives.
- Give every action a stable, descriptive name.
- Use absolute coordinates in world space.
- COORDINATE CONVENTION: For slabs and panels, x/y is the BOTTOM-LEFT CORNER ORIGIN (not center). A slab at x=0, y=0 with length=40, width=25 spans from (0,0) to (40,25). For columns, x/y IS the center point. Match column grid origins with slab origins.
- WALL vs CURTAIN WALL: If the design needs windows or doors on a facade, that facade MUST use create_wall (IfcWall), NOT create_curtain_wall. Windows and doors can only be hosted in IfcWall. Use curtain walls only for fully glazed facades without individual openings.
"""


def build_plan(
    prompt: str,
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    reasoning_effort: str | None = None,
    service_tier: str | None = None,
) -> Dict[str, Any]:
    if not prompt.strip():
        raise ProviderError("Prompt cannot be empty.")
    repair_note = ""
    last_error: Exception | None = None
    for _ in range(3):
        user_prompt = prompt.strip()
        if repair_note:
            user_prompt = (
                f"{user_prompt}\n\n"
                "The previous JSON plan was invalid.\n"
                f"Validation error: {repair_note}\n"
                "Return a corrected plan with valid numeric coordinate and size fields. "
                "Do not repeat the same mistake."
            )
        req = ProviderRequest(
            provider=provider,
            model=model,
            api_key=api_key,
            reasoning_effort=reasoning_effort,
            service_tier=service_tier,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        raw_plan = get_provider(req).generate_plan()
        try:
            return validate_plan(raw_plan)
        except ValidationError as exc:
            last_error = exc
            repair_note = str(exc)
    raise last_error or ProviderError("Planner failed to produce a valid plan.")
