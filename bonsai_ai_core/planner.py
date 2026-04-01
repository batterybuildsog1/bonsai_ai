"""Prompting and validation for Bonsai AI plans."""

from __future__ import annotations

from typing import Any, Dict

from .errors import ProviderError, ValidationError
from .providers import ProviderRequest, get_provider
from .schema import validate_plan


SYSTEM_PROMPT = """You are Bonsai AI, a BIM planning model for Blender + Bonsai.

Return JSON matching the provided schema. Use metric units (meters).

## Element Placement

- Slab and panel x/y is the bottom-left corner. Column x/y is the center.
- For slabs: length is the X-axis extent, width is the Y-axis extent. A 40m x 25m building at origin (0,0) has length=40, width=25.
- Element base_z should match its assigned storey elevation.
- When generators share a footprint, use the same origin coordinates.
- Column grids must span the full building footprint. If the building is 25m wide and bays are 8m, use 4 bays (0, 8, 16, 25) not 3 bays (0, 8, 16, 24).
- Place beams at every column-to-column gridline on each floor (both X and Y directions).
- Include a roof slab at the top of the building (above the highest storey).
- Prefer a small number of clear actions over many micro-actions.

## Generators (prefer these for regular patterns)

- `generate_column_grid`: regular column grids. Expands to (bays_x+1)*(bays_y+1) columns.
- `generate_beam_grid`: beams at every gridline. Use the same grid parameters as generate_column_grid. Expands to bays_x*(bays_y+1) EW beams + bays_y*(bays_x+1) NS beams.
- `generate_perimeter_walls`: walls around a polygon. Expands to one wall per edge.
- `generate_floor_plate`: slab with optional perimeter beams. Set include_edge_beams=true for framed floors.
- `generate_facade_grid`: curtain wall facade with panel dimensions.
- `generate_opening_array`: evenly spaced windows or doors along a wall. Use instead of individual create_window/create_door for repetitive facades.
- Fall back to individual create_* actions for irregular or custom geometry.

## Primitives

- Interior partitions: create_wall.
- Steel framing: create_beam. Connection plates: create_connection_plate.
- Facade panels: create_panel or create_curtain_wall.
- Doors and windows require an IfcWall host (cannot be placed in curtain walls).
- Footings: create_footing. Include foundation metadata when the prompt has structural intent.
- Stairs: create_stair_run and create_stair_landing (approximate; note in assumptions).
- Unsupported element types: approximate with supported primitives and note in assumptions.

## Metadata (optional, use when helpful)

- `semantics`: grouping, naming, selector tags, view modes. Use group_path for review trees.
- `presentation`: glazing, material, frame intent.
- `foundation`: loads, bearing, concrete, reinforcement.

## Editing (when modifying an existing model)

- Target elements via target_id from selection context. Use target_path or target_selector_tags for branches.
- update_element with patch for metadata changes.
- move_element with dx/dy/dz for spatial adjustments.
- replace_section for steel or shell sizing changes.
- rebuild_branch with replacement_actions for regenerating a local branch.
- Prefer semantic edits over recreating the whole building.

## Naming

- Give every action a stable, descriptive name.
- Use absolute coordinates in world space.
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
