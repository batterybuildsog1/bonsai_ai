from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bonsai_ai.analysis_exports import JsonAnalysisExportBackend
from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    ArtifactFormat,
    ArtifactKind,
    DesignBrief,
    DesignPackage,
    LoadCase,
    LoadCombination,
    PipelineArtifact,
    PhysicalModelSpec,
)
from bonsai_ai.execution import IfcPhysicalModelBackend
from bonsai_ai.footing_selector import build_starter_footing_summary
from bonsai_ai.freecad_runner import run_freecad_handoff
from bonsai_ai.grouped_sizing import GroupedSectionSizer
from bonsai_ai.pipeline import DesignPipeline
from bonsai_ai.pynite_backend import PyNiteSolverBackend
from bonsai_ai.results_bundle import JsonResultsBundleBackend
from bonsai_ai.system_catalog import starter_catalog_summary, starter_core_shell_catalog


FT_TO_M = 0.3048

BUILDING_WIDTH_FT = 96.0
BUILDING_LENGTH_FT = 115.0
BASEMENT_DEPTH_FT = 12.0
ABOVE_GRADE_HEIGHT_FT = 62.0
STORY_COUNT = 5

PANEL_MAX_WIDTH_FT = 12.0
PANEL_JOINT_GAP_FT = 1.5 / 12.0
PANEL_THICKNESS_FT = 7.5 / 12.0
RETAINING_WALL_THICKNESS_FT = 12.0 / 12.0
SLAB_THICKNESS_FT = 10.0 / 12.0
ROOF_THICKNESS_FT = 8.0 / 12.0
COLUMN_SIZE_FT = 20.0 / 12.0
MAIN_PANEL_TIER_HEIGHT_FT = 50.0
TOP_PANEL_TIER_HEIGHT_FT = 12.0
FLOOR_BEAM_WIDTH_FT = 10.0 / 12.0
FLOOR_BEAM_DEPTH_FT = 24.0 / 12.0
FLOOR_GIRDER_WIDTH_FT = 12.0 / 12.0
FLOOR_GIRDER_DEPTH_FT = 30.0 / 12.0
ROOF_BEAM_WIDTH_FT = 8.0 / 12.0
ROOF_BEAM_DEPTH_FT = 18.0 / 12.0
ROOF_GIRDER_WIDTH_FT = 10.0 / 12.0
ROOF_GIRDER_DEPTH_FT = 24.0 / 12.0
PERIMETER_SPANDREL_WIDTH_FT = 12.0 / 12.0
PERIMETER_SPANDREL_DEPTH_FT = 28.0 / 12.0
PANEL_SUPPORT_WIDTH_FT = 8.0 / 12.0
PANEL_SUPPORT_DEPTH_FT = 16.0 / 12.0
PRIMARY_ROOF_FRAME_WIDTH_FT = 14.0 / 12.0
PRIMARY_ROOF_FRAME_DEPTH_FT = 36.0 / 12.0
PERIMETER_POST_WIDTH_FT = 8.0 / 12.0
PERIMETER_POST_DEPTH_FT = 12.0 / 12.0
OPENING_JAMB_WIDTH_FT = 8.0 / 12.0
OPENING_JAMB_DEPTH_FT = 10.0 / 12.0
OPENING_HEADER_WIDTH_FT = 8.0 / 12.0
OPENING_HEADER_DEPTH_FT = 18.0 / 12.0
OPENING_SILL_WIDTH_FT = 6.0 / 12.0
OPENING_SILL_DEPTH_FT = 12.0 / 12.0
COLLECTOR_WIDTH_FT = 10.0 / 12.0
COLLECTOR_DEPTH_FT = 20.0 / 12.0
ROOF_BRACE_WIDTH_FT = 4.0 / 12.0
ROOF_BRACE_DEPTH_FT = 4.0 / 12.0

FLOOR_TO_FLOOR_FT = ABOVE_GRADE_HEIGHT_FT / STORY_COUNT
BASEMENT_Z = -BASEMENT_DEPTH_FT * FT_TO_M
ROOF_Z = ABOVE_GRADE_HEIGHT_FT * FT_TO_M

X_GRID_FT = [0.0, 24.0, 48.0, 72.0, 96.0]
Y_GRID_FT = [0.0, 28.75, 57.5, 86.25, 115.0]

FREECAD_CMD = "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
COMPONENT_OUTPUT_DIR = ROOT / "out" / "components" / "innovacast_icp_placeholder_v1"
COMPONENT_SPEC_PATH = COMPONENT_OUTPUT_DIR / "innovacast_icp_placeholder_component_spec.json"
COMPONENT_ID = "InnovaCast_Insulated_Cladding_Panel_v1"
REFERENCE_PEMB_WIDTH_FT = 112.0
REFERENCE_PEMB_LENGTH_FT = 300.0
REFERENCE_PEMB_EAVE_HEIGHT_FT = 40.0
ENGINEERING_SCOPES = [
    "global_frame",
    "roof_load_path",
    "facade_support",
    "substructure",
    "opening_support",
]


def ft(value: float) -> float:
    return round(value * FT_TO_M, 6)


def level_elevations_ft() -> list[tuple[str, float]]:
    levels = [("Basement", -BASEMENT_DEPTH_FT)]
    for index in range(STORY_COUNT):
        levels.append((f"Level {index + 1}", round(index * FLOOR_TO_FLOOR_FT, 6)))
    levels.append(("Roof", ABOVE_GRADE_HEIGHT_FT))
    return levels


def panel_segments_ft(total_length_ft: float) -> list[tuple[float, float]]:
    segments: list[tuple[float, float]] = []
    cursor = 0.0
    while cursor + PANEL_MAX_WIDTH_FT < total_length_ft - 1e-6:
        segments.append((cursor, PANEL_MAX_WIDTH_FT))
        cursor += PANEL_MAX_WIDTH_FT
    remainder = round(total_length_ft - cursor, 6)
    if remainder > 0:
        segments.append((cursor, remainder))
    return segments


def panel_spans_ft(total_length_ft: float) -> list[tuple[float, float, float]]:
    nominal_segments = panel_segments_ft(total_length_ft)
    spans: list[tuple[float, float, float]] = []
    for index, (nominal_start_ft, nominal_width_ft) in enumerate(nominal_segments):
        left_trim_ft = PANEL_JOINT_GAP_FT / 2.0 if index > 0 else 0.0
        right_trim_ft = PANEL_JOINT_GAP_FT / 2.0 if index < len(nominal_segments) - 1 else 0.0
        actual_start_ft = nominal_start_ft + left_trim_ft
        actual_width_ft = nominal_width_ft - left_trim_ft - right_trim_ft
        spans.append((round(actual_start_ft, 6), round(actual_width_ft, 6), nominal_width_ft))
    return spans


def _centered_offset_ft(segment_width_ft: float, opening_width_ft: float) -> float:
    return round(max(0.5, (segment_width_ft - opening_width_ft) / 2.0), 6)


def _beam_action(
    *,
    name: str,
    storey: str,
    x1_ft: float,
    y1_ft: float,
    x2_ft: float,
    y2_ft: float,
    base_z_ft: float,
    width_ft: float,
    depth_ft: float,
    member_role: str | None = None,
) -> dict:
    action = {
        "type": "create_beam",
        "name": name,
        "storey": storey,
        "x1": ft(x1_ft),
        "y1": ft(y1_ft),
        "x2": ft(x2_ft),
        "y2": ft(y2_ft),
        "base_z": ft(base_z_ft),
        "width": ft(width_ft),
        "depth": ft(depth_ft),
    }
    if member_role:
        action["member_role"] = member_role
    return action


def _brace_action(
    *,
    name: str,
    storey: str,
    x1_ft: float,
    y1_ft: float,
    z1_ft: float,
    x2_ft: float,
    y2_ft: float,
    z2_ft: float,
    width_ft: float = 4.0 / 12.0,
    depth_ft: float = 4.0 / 12.0,
) -> dict:
    action = _beam_action(
        name=name,
        storey=storey,
        x1_ft=x1_ft,
        y1_ft=y1_ft,
        x2_ft=x2_ft,
        y2_ft=y2_ft,
        base_z_ft=z1_ft,
        width_ft=width_ft,
        depth_ft=depth_ft,
        member_role="brace",
    )
    action["end_z"] = ft(z2_ft)
    return action


def _perimeter_beam_segments(
    *,
    z_ft: float,
    storey: str,
    prefix: str,
    width_ft: float,
    depth_ft: float,
    member_role: str,
) -> list[dict]:
    actions: list[dict] = []
    for x1_ft, x2_ft in zip(X_GRID_FT[:-1], X_GRID_FT[1:]):
        actions.append(
            _beam_action(
                name=f"{prefix} South X{x1_ft:05.2f}-{x2_ft:05.2f}",
                storey=storey,
                x1_ft=x1_ft,
                y1_ft=0.0,
                x2_ft=x2_ft,
                y2_ft=0.0,
                base_z_ft=z_ft,
                width_ft=width_ft,
                depth_ft=depth_ft,
                member_role=member_role,
            )
        )
        actions.append(
            _beam_action(
                name=f"{prefix} North X{x1_ft:05.2f}-{x2_ft:05.2f}",
                storey=storey,
                x1_ft=x1_ft,
                y1_ft=BUILDING_LENGTH_FT,
                x2_ft=x2_ft,
                y2_ft=BUILDING_LENGTH_FT,
                base_z_ft=z_ft,
                width_ft=width_ft,
                depth_ft=depth_ft,
                member_role=member_role,
            )
        )
    for y1_ft, y2_ft in zip(Y_GRID_FT[:-1], Y_GRID_FT[1:]):
        actions.append(
            _beam_action(
                name=f"{prefix} West Y{y1_ft:05.2f}-{y2_ft:05.2f}",
                storey=storey,
                x1_ft=0.0,
                y1_ft=y1_ft,
                x2_ft=0.0,
                y2_ft=y2_ft,
                base_z_ft=z_ft,
                width_ft=width_ft,
                depth_ft=depth_ft,
                member_role=member_role,
            )
        )
        actions.append(
            _beam_action(
                name=f"{prefix} East Y{y1_ft:05.2f}-{y2_ft:05.2f}",
                storey=storey,
                x1_ft=BUILDING_WIDTH_FT,
                y1_ft=y1_ft,
                x2_ft=BUILDING_WIDTH_FT,
                y2_ft=y2_ft,
                base_z_ft=z_ft,
                width_ft=width_ft,
                depth_ft=depth_ft,
                member_role=member_role,
            )
        )
    return actions


def _near_any(value_ft: float, grid_ft: list[float], tolerance_ft: float = 0.5) -> bool:
    return any(abs(value_ft - candidate_ft) <= tolerance_ft for candidate_ft in grid_ft)


def _column_profile_ft(x_ft: float, y_ft: float) -> tuple[float, float, str]:
    is_sidewall = x_ft in {0.0, BUILDING_WIDTH_FT}
    is_endwall = y_ft in {0.0, BUILDING_LENGTH_FT}
    if is_sidewall and is_endwall:
        return (30.0 / 12.0, 30.0 / 12.0, "corner_frame_column")
    if is_sidewall:
        return (26.0 / 12.0, 30.0 / 12.0, "sidewall_frame_column")
    if is_endwall:
        return (20.0 / 12.0, 24.0 / 12.0, "endwall_column")
    return (18.0 / 12.0, 22.0 / 12.0, "interior_gravity_column")


def _panel_assignment(
    *,
    panel_name: str,
    storey: str,
    facade: str,
    segment_index: int,
    tier_name: str,
    panel_orientation: str,
    width_ft: float,
    nominal_width_ft: float,
    height_ft: float,
    base_z_ft: float,
) -> dict:
    return {
        "target_name": panel_name,
        "component_id": COMPONENT_ID,
        "component_spec_path": str(COMPONENT_SPEC_PATH),
        "representation": "panel_shell_placeholder",
        "storey": storey,
        "facade": facade,
        "tier_name": tier_name,
        "panel_orientation": panel_orientation,
        "segment_index": segment_index,
        "panel_width_ft": round(width_ft, 3),
        "panel_nominal_width_ft": round(nominal_width_ft, 3),
        "panel_height_ft": round(height_ft, 3),
        "base_z_ft": round(base_z_ft, 3),
        "joint_gap_ft": round(PANEL_JOINT_GAP_FT, 3),
    }


def _maybe_window_action(
    *,
    story_index: int,
    facade: str,
    segment_index: int,
    segment_width_ft: float,
    panel_name: str,
    storey: str,
) -> dict | None:
    if segment_width_ft < 8.0:
        return None

    if facade in {"East", "West"}:
        if story_index == 0 and 3 <= segment_index <= 7 and segment_width_ft >= 10.0:
            width_ft = 6.0
            height_ft = 7.0
            sill_ft = 2.5
        elif story_index >= 1 and 2 <= segment_index <= 8 and segment_width_ft >= 10.0:
            width_ft = 6.0
            height_ft = 5.0
            sill_ft = 3.0
        else:
            return None
    elif facade in {"North", "South"}:
        if story_index >= 1 and 3 <= segment_index <= 6 and segment_width_ft >= 10.0:
            width_ft = 5.0
            height_ft = 5.0
            sill_ft = 3.0
        else:
            return None
    else:
        return None

    return {
        "type": "create_window",
        "name": f"{panel_name} Window",
        "storey": storey,
        "wall_name": panel_name,
        "offset_along_wall": ft(_centered_offset_ft(segment_width_ft, width_ft)),
        "sill_height": ft(sill_ft),
        "width": ft(width_ft),
        "height": ft(height_ft),
        "thickness": ft(PANEL_THICKNESS_FT),
        "base_z": 0.0,
    }


def _maybe_door_action(
    *,
    story_index: int,
    facade: str,
    segment_index: int,
    segment_width_ft: float,
    panel_name: str,
    storey: str,
) -> dict | None:
    if story_index != 0 or facade != "South" or segment_width_ft < 10.0:
        return None
    if segment_index not in {4, 5}:
        return None
    width_ft = 3.5
    return {
        "type": "create_door",
        "name": f"{panel_name} Entry Door",
        "storey": storey,
        "wall_name": panel_name,
        "offset_along_wall": ft(_centered_offset_ft(segment_width_ft, width_ft)),
        "width": ft(width_ft),
        "height": ft(7.0),
        "thickness": ft(PANEL_THICKNESS_FT),
        "base_z": 0.0,
    }


def _opening_points_ft(wall_action: dict, offset_ft: float, width_ft: float) -> tuple[tuple[float, float], tuple[float, float]]:
    x1_ft = float(wall_action["x1"]) / FT_TO_M
    y1_ft = float(wall_action["y1"]) / FT_TO_M
    x2_ft = float(wall_action["x2"]) / FT_TO_M
    y2_ft = float(wall_action["y2"]) / FT_TO_M
    dx_ft = x2_ft - x1_ft
    dy_ft = y2_ft - y1_ft
    length_ft = (dx_ft**2 + dy_ft**2) ** 0.5
    if length_ft <= 1e-6:
        raise ValueError(f"Wall {wall_action['name']} has zero length")
    ux_ft = dx_ft / length_ft
    uy_ft = dy_ft / length_ft
    start = (x1_ft + ux_ft * offset_ft, y1_ft + uy_ft * offset_ft)
    end = (start[0] + ux_ft * width_ft, start[1] + uy_ft * width_ft)
    return start, end


def _opening_frame_actions(opening: dict, wall_action: dict, opening_kind: str) -> list[dict]:
    offset_ft = float(opening["offset_along_wall"]) / FT_TO_M
    width_ft = float(opening["width"]) / FT_TO_M
    height_ft = float(opening["height"]) / FT_TO_M
    sill_ft = float(opening.get("sill_height", opening.get("base_z", 0.0))) / FT_TO_M
    wall_base_ft = float(wall_action["base_z"]) / FT_TO_M
    jamb_base_ft = wall_base_ft + sill_ft
    left_pt, right_pt = _opening_points_ft(wall_action, offset_ft, width_ft)
    header_z_ft = jamb_base_ft + height_ft
    member_prefix = "Window" if opening_kind == "window" else "Door"
    actions = [
        {
            "type": "create_column",
            "name": f"{opening['name']} Left Jamb",
            "storey": opening["storey"],
            "x": ft(left_pt[0]),
            "y": ft(left_pt[1]),
            "base_z": ft(jamb_base_ft),
            "width": ft(OPENING_JAMB_WIDTH_FT),
            "depth": ft(OPENING_JAMB_DEPTH_FT),
            "height": ft(height_ft),
        },
        {
            "type": "create_column",
            "name": f"{opening['name']} Right Jamb",
            "storey": opening["storey"],
            "x": ft(right_pt[0]),
            "y": ft(right_pt[1]),
            "base_z": ft(jamb_base_ft),
            "width": ft(OPENING_JAMB_WIDTH_FT),
            "depth": ft(OPENING_JAMB_DEPTH_FT),
            "height": ft(height_ft),
        },
        _beam_action(
            name=f"{opening['name']} Header",
            storey=opening["storey"],
            x1_ft=left_pt[0],
            y1_ft=left_pt[1],
            x2_ft=right_pt[0],
            y2_ft=right_pt[1],
            base_z_ft=header_z_ft,
            width_ft=OPENING_HEADER_WIDTH_FT,
            depth_ft=OPENING_HEADER_DEPTH_FT,
            member_role=f"{opening_kind}_header",
        ),
    ]
    if opening_kind == "window":
        actions.append(
            _beam_action(
                name=f"{opening['name']} Sill",
                storey=opening["storey"],
                x1_ft=left_pt[0],
                y1_ft=left_pt[1],
                x2_ft=right_pt[0],
                y2_ft=right_pt[1],
                base_z_ft=jamb_base_ft,
                width_ft=OPENING_SILL_WIDTH_FT,
                depth_ft=OPENING_SILL_DEPTH_FT,
                member_role="window_sill",
            )
        )
    return actions


def build_plan() -> tuple[dict, list[dict], dict]:
    actions: list[dict] = []
    component_assignments: list[dict] = []
    openings = {"windows": [], "doors": []}

    def add_panel_wall(
        *,
        facade: str,
        tier_name: str,
        panel_orientation: str,
        segment_index: int,
        start_ft: float,
        width_ft: float,
        nominal_width_ft: float,
        base_z_ft: float,
        height_ft: float,
    ) -> str:
        panel_name = f"{tier_name} {facade} Panel {segment_index:02d}"
        if facade == "South":
            x1_ft = start_ft
            y1_ft = 0.0
            x2_ft = start_ft + width_ft
            y2_ft = 0.0
        elif facade == "North":
            x1_ft = BUILDING_WIDTH_FT - start_ft
            y1_ft = BUILDING_LENGTH_FT
            x2_ft = BUILDING_WIDTH_FT - (start_ft + width_ft)
            y2_ft = BUILDING_LENGTH_FT
        elif facade == "East":
            x1_ft = BUILDING_WIDTH_FT
            y1_ft = start_ft
            x2_ft = BUILDING_WIDTH_FT
            y2_ft = start_ft + width_ft
        elif facade == "West":
            x1_ft = 0.0
            y1_ft = BUILDING_LENGTH_FT - start_ft
            x2_ft = 0.0
            y2_ft = BUILDING_LENGTH_FT - (start_ft + width_ft)
        else:
            raise ValueError(f"Unsupported facade: {facade}")

        actions.append(
            {
                "type": "create_wall",
                "name": panel_name,
                "storey": "Level 1" if tier_name == "Main Tier" else "Roof",
                "x1": ft(x1_ft),
                "y1": ft(y1_ft),
                "x2": ft(x2_ft),
                "y2": ft(y2_ft),
                "base_z": ft(base_z_ft),
                "height": ft(height_ft),
                "thickness": ft(PANEL_THICKNESS_FT),
            }
        )
        component_assignments.append(
            _panel_assignment(
                panel_name=panel_name,
                storey="Level 1" if tier_name == "Main Tier" else "Roof",
                facade=facade,
                segment_index=segment_index,
                tier_name=tier_name,
                panel_orientation=panel_orientation,
                width_ft=width_ft,
                nominal_width_ft=nominal_width_ft,
                height_ft=height_ft,
                base_z_ft=base_z_ft,
            )
        )
        return panel_name

    def add_window_for_level(
        *,
        host_wall: str,
        host_tier_base_ft: float,
        level_number: int,
        facade: str,
        segment_index: int,
        segment_width_ft: float,
    ) -> None:
        if segment_width_ft < 8.0:
            return
        floor_base_ft = (level_number - 1) * FLOOR_TO_FLOOR_FT

        if facade in {"East", "West"}:
            if level_number == 1 and 3 <= segment_index <= 7 and segment_width_ft >= 10.0:
                width_ft = 6.0
                height_ft = 7.0
                sill_above_floor_ft = 2.5
            elif level_number >= 2 and 2 <= segment_index <= 8 and segment_width_ft >= 10.0:
                width_ft = 6.0
                height_ft = 5.0
                sill_above_floor_ft = 3.0
            else:
                return
        elif facade in {"North", "South"}:
            if level_number >= 2 and 3 <= segment_index <= 6 and segment_width_ft >= 10.0:
                width_ft = 5.0
                height_ft = 5.0
                sill_above_floor_ft = 3.0
            else:
                return
        else:
            return

        window = {
            "type": "create_window",
            "name": f"{host_wall} L{level_number} Window",
            "storey": "Level 1" if level_number <= 4 else "Roof",
            "wall_name": host_wall,
            "offset_along_wall": ft(_centered_offset_ft(segment_width_ft, width_ft)),
            "sill_height": ft((floor_base_ft + sill_above_floor_ft) - host_tier_base_ft),
            "width": ft(width_ft),
            "height": ft(height_ft),
            "thickness": ft(PANEL_THICKNESS_FT),
            "base_z": 0.0,
        }
        actions.append(window)
        openings["windows"].append(dict(window))

    for storey_name, elevation_ft in level_elevations_ft():
        actions.append({"type": "ensure_storey", "name": storey_name, "elevation": ft(elevation_ft)})

    slab_levels = [("Basement Slab", "Basement", -BASEMENT_DEPTH_FT, SLAB_THICKNESS_FT)]
    for index in range(STORY_COUNT):
        slab_levels.append((f"Floor Plate L{index + 1}", f"Level {index + 1}", index * FLOOR_TO_FLOOR_FT, SLAB_THICKNESS_FT))
    slab_levels.append(("Roof Plate", "Roof", ABOVE_GRADE_HEIGHT_FT, ROOF_THICKNESS_FT))

    for name, storey, z_ft, thickness_ft in slab_levels:
        actions.append(
            {
                "type": "create_rect_slab",
                "name": name,
                "storey": storey,
                "x": 0.0,
                "y": 0.0,
                "z": ft(z_ft),
                "width": ft(BUILDING_WIDTH_FT),
                "depth": ft(BUILDING_LENGTH_FT),
                "thickness": ft(thickness_ft),
            }
        )

    retaining = [
        ("Basement Retaining South", 0.0, 0.0, BUILDING_WIDTH_FT, 0.0),
        ("Basement Retaining East", BUILDING_WIDTH_FT, 0.0, BUILDING_WIDTH_FT, BUILDING_LENGTH_FT),
        ("Basement Retaining North", BUILDING_WIDTH_FT, BUILDING_LENGTH_FT, 0.0, BUILDING_LENGTH_FT),
        ("Basement Retaining West", 0.0, BUILDING_LENGTH_FT, 0.0, 0.0),
    ]
    for name, x1_ft, y1_ft, x2_ft, y2_ft in retaining:
        actions.append(
            {
                "type": "create_wall",
                "name": name,
                "storey": "Basement",
                "x1": ft(x1_ft),
                "y1": ft(y1_ft),
                "x2": ft(x2_ft),
                "y2": ft(y2_ft),
                "base_z": BASEMENT_Z,
                "height": ft(BASEMENT_DEPTH_FT),
                "thickness": ft(RETAINING_WALL_THICKNESS_FT),
            }
        )

    short_side_spans = panel_spans_ft(BUILDING_WIDTH_FT)
    long_side_spans = panel_spans_ft(BUILDING_LENGTH_FT)
    tier_specs = [
        {"name": "Main Tier", "base_z_ft": 0.0, "height_ft": MAIN_PANEL_TIER_HEIGHT_FT, "orientation": "vertical"},
        {"name": "Top Tier", "base_z_ft": MAIN_PANEL_TIER_HEIGHT_FT, "height_ft": TOP_PANEL_TIER_HEIGHT_FT, "orientation": "horizontal"},
    ]

    for tier in tier_specs:
        for facade in ("South", "North"):
            for seg_index, (start_ft, width_ft, nominal_width_ft) in enumerate(short_side_spans, start=1):
                panel_name = add_panel_wall(
                    facade=facade,
                    tier_name=tier["name"],
                    panel_orientation=tier["orientation"],
                    segment_index=seg_index,
                    start_ft=start_ft,
                    width_ft=width_ft,
                    nominal_width_ft=nominal_width_ft,
                    base_z_ft=tier["base_z_ft"],
                    height_ft=tier["height_ft"],
                )
                if tier["name"] == "Main Tier":
                    for level_number in (1, 2, 3, 4):
                        add_window_for_level(
                            host_wall=panel_name,
                            host_tier_base_ft=tier["base_z_ft"],
                            level_number=level_number,
                            facade=facade,
                            segment_index=seg_index,
                            segment_width_ft=width_ft,
                        )
                    if facade == "South" and seg_index in {4, 5} and width_ft >= 10.0:
                        door = {
                            "type": "create_door",
                            "name": f"{panel_name} Entry Door",
                            "storey": "Level 1",
                            "wall_name": panel_name,
                            "offset_along_wall": ft(_centered_offset_ft(width_ft, 3.5)),
                            "width": ft(3.5),
                            "height": ft(7.0),
                            "thickness": ft(PANEL_THICKNESS_FT),
                            "base_z": 0.0,
                        }
                        actions.append(door)
                        openings["doors"].append(dict(door))
                else:
                    add_window_for_level(
                        host_wall=panel_name,
                        host_tier_base_ft=tier["base_z_ft"],
                        level_number=5,
                        facade=facade,
                        segment_index=seg_index,
                        segment_width_ft=width_ft,
                    )

        for facade in ("East", "West"):
            for seg_index, (start_ft, width_ft, nominal_width_ft) in enumerate(long_side_spans, start=1):
                panel_name = add_panel_wall(
                    facade=facade,
                    tier_name=tier["name"],
                    panel_orientation=tier["orientation"],
                    segment_index=seg_index,
                    start_ft=start_ft,
                    width_ft=width_ft,
                    nominal_width_ft=nominal_width_ft,
                    base_z_ft=tier["base_z_ft"],
                    height_ft=tier["height_ft"],
                )
                if tier["name"] == "Main Tier":
                    for level_number in (1, 2, 3, 4):
                        add_window_for_level(
                            host_wall=panel_name,
                            host_tier_base_ft=tier["base_z_ft"],
                            level_number=level_number,
                            facade=facade,
                            segment_index=seg_index,
                            segment_width_ft=width_ft,
                        )
                else:
                    add_window_for_level(
                        host_wall=panel_name,
                        host_tier_base_ft=tier["base_z_ft"],
                        level_number=5,
                        facade=facade,
                        segment_index=seg_index,
                        segment_width_ft=width_ft,
                    )

    wall_actions_by_name = {
        action["name"]: action
        for action in actions
        if action["type"] == "create_wall"
    }
    for window in openings["windows"]:
        wall_action = wall_actions_by_name.get(str(window["wall_name"]))
        if wall_action:
            actions.extend(_opening_frame_actions(window, wall_action, "window"))
    for door in openings["doors"]:
        wall_action = wall_actions_by_name.get(str(door["wall_name"]))
        if wall_action:
            actions.extend(_opening_frame_actions(door, wall_action, "door"))

    vertical_segments = [("Basement", -BASEMENT_DEPTH_FT, 0.0)] + [
        (f"Level {index + 1}", index * FLOOR_TO_FLOOR_FT, (index + 1) * FLOOR_TO_FLOOR_FT)
        for index in range(STORY_COUNT)
    ]
    for x_ft in X_GRID_FT:
        for y_ft in Y_GRID_FT:
            column_width_ft, column_depth_ft, column_role = _column_profile_ft(x_ft, y_ft)
            for segment_index, (storey, start_ft, end_ft) in enumerate(vertical_segments, start=1):
                actions.append(
                    {
                        "type": "create_column",
                        "name": f"{column_role} X{int(x_ft):03d}_Y{int(round(y_ft)):03d}_Seg{segment_index}",
                        "storey": storey,
                        "x": ft(x_ft),
                        "y": ft(y_ft),
                        "base_z": ft(start_ft),
                        "width": ft(column_width_ft),
                        "depth": ft(column_depth_ft),
                        "height": ft(end_ft - start_ft),
                    }
                )

    south_north_joint_positions_ft = [
        nominal_start_ft + nominal_width_ft
        for nominal_start_ft, nominal_width_ft in panel_segments_ft(BUILDING_WIDTH_FT)[:-1]
        if not _near_any(nominal_start_ft + nominal_width_ft, X_GRID_FT)
    ]
    east_west_joint_positions_ft = [
        nominal_start_ft + nominal_width_ft
        for nominal_start_ft, nominal_width_ft in panel_segments_ft(BUILDING_LENGTH_FT)[:-1]
        if not _near_any(nominal_start_ft + nominal_width_ft, Y_GRID_FT)
    ]
    perimeter_post_lines = []
    perimeter_post_lines.extend(("South", x_ft, 0.75) for x_ft in south_north_joint_positions_ft)
    perimeter_post_lines.extend(("North", x_ft, BUILDING_LENGTH_FT - 0.75) for x_ft in south_north_joint_positions_ft)
    perimeter_post_lines.extend(("West", 0.75, y_ft) for y_ft in east_west_joint_positions_ft)
    perimeter_post_lines.extend(("East", BUILDING_WIDTH_FT - 0.75, y_ft) for y_ft in east_west_joint_positions_ft)
    for facade_name, x_ft, y_ft in perimeter_post_lines:
        for segment_index, (storey, start_ft, end_ft) in enumerate(vertical_segments[1:], start=1):
            actions.append(
                {
                    "type": "create_column",
                    "name": f"{facade_name} Facade Post X{int(round(x_ft)):03d}_Y{int(round(y_ft)):03d}_Seg{segment_index}",
                    "storey": storey,
                    "x": ft(x_ft),
                    "y": ft(y_ft),
                    "base_z": ft(start_ft),
                    "width": ft(PERIMETER_POST_WIDTH_FT),
                    "depth": ft(PERIMETER_POST_DEPTH_FT),
                    "height": ft(end_ft - start_ft),
                    }
                )

    perimeter_support_levels = [
        ("Level 1", 0.0, "Level 1 Perimeter Spandrel", PERIMETER_SPANDREL_WIDTH_FT, PERIMETER_SPANDREL_DEPTH_FT, "perimeter_spandrel"),
        ("Level 2", FLOOR_TO_FLOOR_FT, "Level 2 Perimeter Spandrel", PERIMETER_SPANDREL_WIDTH_FT, PERIMETER_SPANDREL_DEPTH_FT, "perimeter_spandrel"),
        ("Level 3", FLOOR_TO_FLOOR_FT * 2.0, "Level 3 Perimeter Spandrel", PERIMETER_SPANDREL_WIDTH_FT, PERIMETER_SPANDREL_DEPTH_FT, "perimeter_spandrel"),
        ("Level 4", FLOOR_TO_FLOOR_FT * 3.0, "Level 4 Perimeter Spandrel", PERIMETER_SPANDREL_WIDTH_FT, PERIMETER_SPANDREL_DEPTH_FT, "perimeter_spandrel"),
        ("Roof", MAIN_PANEL_TIER_HEIGHT_FT, "Main Tier Joint Support", PANEL_SUPPORT_WIDTH_FT, PANEL_SUPPORT_DEPTH_FT, "panel_joint_support"),
        ("Roof", ABOVE_GRADE_HEIGHT_FT, "Roof Edge Support", PANEL_SUPPORT_WIDTH_FT, PANEL_SUPPORT_DEPTH_FT, "roof_edge_support"),
    ]
    for storey_name, z_ft, prefix, width_ft, depth_ft, member_role in perimeter_support_levels:
        actions.extend(
            _perimeter_beam_segments(
                z_ft=z_ft,
                storey=storey_name,
                prefix=prefix,
                width_ft=width_ft,
                depth_ft=depth_ft,
                member_role=member_role,
            )
        )

    brace_bays = [
        ("West", 0.0, Y_GRID_FT[0], Y_GRID_FT[1]),
        ("West", 0.0, Y_GRID_FT[2], Y_GRID_FT[3]),
        ("East", BUILDING_WIDTH_FT, Y_GRID_FT[1], Y_GRID_FT[2]),
        ("East", BUILDING_WIDTH_FT, Y_GRID_FT[3], Y_GRID_FT[4]),
        ("South", 0.0, X_GRID_FT[1], X_GRID_FT[2]),
        ("North", BUILDING_LENGTH_FT, X_GRID_FT[2], X_GRID_FT[3]),
    ]
    for face_name, fixed_ft, span_start_ft, span_end_ft in brace_bays:
        if face_name in {"West", "East"}:
            actions.append(
                _brace_action(
                    name=f"{face_name} Brace Bay {span_start_ft:05.2f}-{span_end_ft:05.2f} A",
                    storey="Level 1",
                    x1_ft=fixed_ft,
                    y1_ft=span_start_ft,
                    z1_ft=0.0,
                    x2_ft=fixed_ft,
                    y2_ft=span_end_ft,
                    z2_ft=MAIN_PANEL_TIER_HEIGHT_FT,
                )
            )
            actions.append(
                _brace_action(
                    name=f"{face_name} Brace Bay {span_start_ft:05.2f}-{span_end_ft:05.2f} B",
                    storey="Level 1",
                    x1_ft=fixed_ft,
                    y1_ft=span_end_ft,
                    z1_ft=0.0,
                    x2_ft=fixed_ft,
                    y2_ft=span_start_ft,
                    z2_ft=MAIN_PANEL_TIER_HEIGHT_FT,
                )
            )
            actions.append(
                _beam_action(
                    name=f"{face_name} Collector Bay {span_start_ft:05.2f}-{span_end_ft:05.2f}",
                    storey="Roof",
                    x1_ft=fixed_ft,
                    y1_ft=span_start_ft,
                    x2_ft=fixed_ft,
                    y2_ft=span_end_ft,
                    base_z_ft=MAIN_PANEL_TIER_HEIGHT_FT,
                    width_ft=COLLECTOR_WIDTH_FT,
                    depth_ft=COLLECTOR_DEPTH_FT,
                    member_role="drag_collector",
                )
            )
        else:
            actions.append(
                _brace_action(
                    name=f"{face_name} Brace Bay {span_start_ft:05.2f}-{span_end_ft:05.2f} A",
                    storey="Level 1",
                    x1_ft=span_start_ft,
                    y1_ft=fixed_ft,
                    z1_ft=0.0,
                    x2_ft=span_end_ft,
                    y2_ft=fixed_ft,
                    z2_ft=MAIN_PANEL_TIER_HEIGHT_FT,
                )
            )
            actions.append(
                _beam_action(
                    name=f"{face_name} Collector Bay {span_start_ft:05.2f}-{span_end_ft:05.2f}",
                    storey="Roof",
                    x1_ft=span_start_ft,
                    y1_ft=fixed_ft,
                    x2_ft=span_end_ft,
                    y2_ft=fixed_ft,
                    base_z_ft=MAIN_PANEL_TIER_HEIGHT_FT,
                    width_ft=COLLECTOR_WIDTH_FT,
                    depth_ft=COLLECTOR_DEPTH_FT,
                    member_role="drag_collector",
                )
            )
            actions.append(
                _brace_action(
                    name=f"{face_name} Brace Bay {span_start_ft:05.2f}-{span_end_ft:05.2f} B",
                    storey="Level 1",
                    x1_ft=span_end_ft,
                    y1_ft=fixed_ft,
                    z1_ft=0.0,
                    x2_ft=span_start_ft,
                    y2_ft=fixed_ft,
                    z2_ft=MAIN_PANEL_TIER_HEIGHT_FT,
                )
            )

    roof_brace_bays = [
        ("Roof Brace Bay X24-48 Y28.75-57.50", X_GRID_FT[1], X_GRID_FT[2], Y_GRID_FT[1], Y_GRID_FT[2]),
        ("Roof Brace Bay X48-72 Y57.50-86.25", X_GRID_FT[2], X_GRID_FT[3], Y_GRID_FT[2], Y_GRID_FT[3]),
    ]
    for name, x1_ft, x2_ft, y1_ft, y2_ft in roof_brace_bays:
        actions.append(
            _beam_action(
                name=f"{name} A",
                storey="Roof",
                x1_ft=x1_ft,
                y1_ft=y1_ft,
                x2_ft=x2_ft,
                y2_ft=y2_ft,
                base_z_ft=ABOVE_GRADE_HEIGHT_FT,
                width_ft=ROOF_BRACE_WIDTH_FT,
                depth_ft=ROOF_BRACE_DEPTH_FT,
                member_role="roof_brace",
            )
        )
        actions.append(
            _beam_action(
                name=f"{name} B",
                storey="Roof",
                x1_ft=x1_ft,
                y1_ft=y2_ft,
                x2_ft=x2_ft,
                y2_ft=y1_ft,
                base_z_ft=ABOVE_GRADE_HEIGHT_FT,
                width_ft=ROOF_BRACE_WIDTH_FT,
                depth_ft=ROOF_BRACE_DEPTH_FT,
                member_role="roof_brace",
            )
        )

    framing_levels = [(f"Level {index + 1}", index * FLOOR_TO_FLOOR_FT) for index in range(STORY_COUNT)]
    framing_levels.append(("Roof", ABOVE_GRADE_HEIGHT_FT))
    for storey_name, z_ft in framing_levels:
        is_roof = storey_name == "Roof"
        beam_width_ft = ROOF_BEAM_WIDTH_FT if is_roof else FLOOR_BEAM_WIDTH_FT
        beam_depth_ft = ROOF_BEAM_DEPTH_FT if is_roof else FLOOR_BEAM_DEPTH_FT
        girder_width_ft = ROOF_GIRDER_WIDTH_FT if is_roof else FLOOR_GIRDER_WIDTH_FT
        girder_depth_ft = ROOF_GIRDER_DEPTH_FT if is_roof else FLOOR_GIRDER_DEPTH_FT

        for y_ft in Y_GRID_FT:
            for x1_ft, x2_ft in zip(X_GRID_FT[:-1], X_GRID_FT[1:]):
                is_perimeter_line = y_ft in {0.0, BUILDING_LENGTH_FT}
                member_role = "roof_primary_frame" if is_roof else ("perimeter_spandrel" if is_perimeter_line else "floor_beam")
                width_ft = PRIMARY_ROOF_FRAME_WIDTH_FT if is_roof else (PERIMETER_SPANDREL_WIDTH_FT if is_perimeter_line else beam_width_ft)
                depth_ft = PRIMARY_ROOF_FRAME_DEPTH_FT if is_roof else (PERIMETER_SPANDREL_DEPTH_FT if is_perimeter_line else beam_depth_ft)
                actions.append(
                    _beam_action(
                        name=f"{storey_name} Beam Y{int(round(y_ft)):03d} X{x1_ft:05.2f}-{x2_ft:05.2f}",
                        storey=storey_name,
                        x1_ft=x1_ft,
                        y1_ft=y_ft,
                        x2_ft=x2_ft,
                        y2_ft=y_ft,
                        base_z_ft=z_ft,
                        width_ft=width_ft,
                        depth_ft=depth_ft,
                        member_role=member_role,
                    )
                )

        for x_ft in X_GRID_FT:
            for y1_ft, y2_ft in zip(Y_GRID_FT[:-1], Y_GRID_FT[1:]):
                is_perimeter_line = x_ft in {0.0, BUILDING_WIDTH_FT}
                member_role = "roof_collector" if is_roof else ("perimeter_spandrel" if is_perimeter_line else "floor_girder")
                width_ft = ROOF_GIRDER_WIDTH_FT if is_roof else (PERIMETER_SPANDREL_WIDTH_FT if is_perimeter_line else girder_width_ft)
                depth_ft = ROOF_GIRDER_DEPTH_FT if is_roof else (PERIMETER_SPANDREL_DEPTH_FT if is_perimeter_line else girder_depth_ft)
                actions.append(
                    _beam_action(
                        name=f"{storey_name} Girder X{int(round(x_ft)):03d} Y{y1_ft:05.2f}-{y2_ft:05.2f}",
                        storey=storey_name,
                        x1_ft=x_ft,
                        y1_ft=y1_ft,
                        x2_ft=x_ft,
                        y2_ft=y2_ft,
                        base_z_ft=z_ft,
                        width_ft=width_ft,
                        depth_ft=depth_ft,
                        member_role=member_role,
                    )
                )

    plan = {
        "version": "1.0",
        "units": "meters",
        "summary": "Initial 5-story Tech Ridge shell with 12 ft below-grade substructure, 50 ft main panel tier, and 12 ft upper cap tier.",
        "assumptions": [
            "Floor plate set to 96 ft x 115 ft (~11,040 sf per level).",
            "Five above-grade stories are carried inside a 62 ft above-grade envelope, plus one 12 ft below-grade level.",
            "Below-grade shell is modeled as a 12 ft retaining/substructure concept.",
            "Above-grade cladding is tiered as one 50 ft primary panel zone plus one 12 ft upper cap zone.",
            "Panel modules target 12 ft nominal width with a 1.5 inch vertical joint gap between adjacent panels.",
            "Main tier is tagged as vertical panel orientation; upper cap is tagged as horizontal panel orientation.",
            "Horizontal joint lines are represented by separate wall tiers at 0 ft and 50 ft above grade.",
            "Steel concept grid is shifted toward the CO Buildings PEMB reference rhythm with roughly 24 ft by 28.75 ft baying.",
            "Horizontal steel framing is modeled with heavier perimeter spandrels, roof primary frame members, and secondary interior beams/girders for concept review only.",
            "Vertical steel members are differentiated into heavier perimeter frame columns and lighter interior gravity columns to better match the PEMB reference logic.",
            "PEMB-inspired braced bays are modeled on selected perimeter planes using true 3D diagonal steel members over the 50 ft main tier.",
            "Dedicated perimeter support members are carried at the 50 ft panel joint and roof edge to reflect the stacked 50 ft plus 12 ft panel installation strategy.",
            "Repeated windows and doors are framed with placeholder jamb, header, and sill steel to make facade support demands more legible.",
            "Collector members are added at the tops of selected braced bays to make the lateral load path more explicit in the concept model.",
            "Reference PEMB overall geometry is 112 ft x 300 ft x 40 ft, so its framing logic can inform grid rhythm but not final member sizing for this taller mixed-use shell.",
            "Panel dead load basis carried at roughly 55 to 60 psf for early frame sizing.",
            "InnovaCast placeholder component is referenced as a reusable shell panel package, not a final manufacturer-approved assembly object.",
            "Placeholder windows are patterned from the shorter PEMB reference only for early massing and pricing studies.",
            "Window and door openings are not yet deducted from the early analytical wall idealization.",
            "Wind basis is provisional pending exact parcel/topography confirmation.",
            "Seismic basis from geotech report uses Site Class C and SDS 0.434 / SD1 0.163.",
            "Below-grade retaining structure and steel sizing remain conceptual until the soils report and final structural system are fully integrated.",
        ],
        "actions": actions,
    }
    return plan, component_assignments, openings


def _line_length_ft(action: dict) -> float:
    dx = float(action["x2"]) - float(action["x1"])
    dy = float(action["y2"]) - float(action["y1"])
    dz = float(action.get("end_z", action.get("z2", action.get("base_z", 0.0)))) - float(action.get("base_z", 0.0))
    return (dx**2 + dy**2 + dz**2) ** 0.5 / FT_TO_M


def build_cost_inputs(plan: dict, component_assignments: list[dict], openings: dict) -> dict:
    panel_assignments = list(component_assignments)
    main_tier_panels = [item for item in panel_assignments if item["tier_name"] == "Main Tier"]
    top_tier_panels = [item for item in panel_assignments if item["tier_name"] == "Top Tier"]
    beam_actions = [action for action in plan["actions"] if action["type"] == "create_beam"]
    brace_actions = [action for action in beam_actions if action.get("member_role") == "brace"]
    floor_beam_actions = [action for action in beam_actions if action.get("member_role") == "floor_beam"]
    floor_girder_actions = [action for action in beam_actions if action.get("member_role") == "floor_girder"]
    perimeter_spandrel_actions = [action for action in beam_actions if action.get("member_role") == "perimeter_spandrel"]
    primary_roof_frame_actions = [action for action in beam_actions if action.get("member_role") == "roof_primary_frame"]
    roof_collector_actions = [action for action in beam_actions if action.get("member_role") == "roof_collector"]
    roof_brace_actions = [action for action in beam_actions if action.get("member_role") == "roof_brace"]
    panel_joint_support_actions = [action for action in beam_actions if action.get("member_role") == "panel_joint_support"]
    roof_edge_support_actions = [action for action in beam_actions if action.get("member_role") == "roof_edge_support"]
    drag_collector_actions = [action for action in beam_actions if action.get("member_role") == "drag_collector"]
    window_header_actions = [action for action in beam_actions if action.get("member_role") == "window_header"]
    window_sill_actions = [action for action in beam_actions if action.get("member_role") == "window_sill"]
    door_header_actions = [action for action in beam_actions if action.get("member_role") == "door_header"]
    column_actions = [action for action in plan["actions"] if action["type"] == "create_column"]
    opening_jamb_actions = [action for action in column_actions if " Jamb" in str(action["name"])]
    slab_actions = [action for action in plan["actions"] if action["type"] == "create_rect_slab"]
    retaining_actions = [action for action in plan["actions"] if action["type"] == "create_wall" and str(action["name"]).startswith("Basement Retaining")]

    beam_length_ft = sum(_line_length_ft(action) for action in beam_actions)
    column_length_ft = sum(float(action["height"]) / FT_TO_M for action in column_actions)
    steel_weight_assumptions_lb_per_lf = {
        "floor_beam": 40.0,
        "floor_girder": 65.0,
        "perimeter_spandrel": 72.0,
        "roof_primary_frame": 95.0,
        "roof_collector": 55.0,
        "panel_joint_support": 28.0,
        "roof_edge_support": 24.0,
        "drag_collector": 48.0,
        "roof_brace": 18.0,
        "opening_header": 22.0,
        "opening_sill": 16.0,
        "opening_jamb": 20.0,
        "column": 70.0,
        "brace": 18.0,
    }
    steel_weight_proxy_lb = (
        sum(_line_length_ft(action) for action in floor_beam_actions) * steel_weight_assumptions_lb_per_lf["floor_beam"]
        + sum(_line_length_ft(action) for action in floor_girder_actions) * steel_weight_assumptions_lb_per_lf["floor_girder"]
        + sum(_line_length_ft(action) for action in perimeter_spandrel_actions) * steel_weight_assumptions_lb_per_lf["perimeter_spandrel"]
        + sum(_line_length_ft(action) for action in primary_roof_frame_actions) * steel_weight_assumptions_lb_per_lf["roof_primary_frame"]
        + sum(_line_length_ft(action) for action in roof_collector_actions) * steel_weight_assumptions_lb_per_lf["roof_collector"]
        + sum(_line_length_ft(action) for action in roof_brace_actions) * steel_weight_assumptions_lb_per_lf["roof_brace"]
        + sum(_line_length_ft(action) for action in panel_joint_support_actions) * steel_weight_assumptions_lb_per_lf["panel_joint_support"]
        + sum(_line_length_ft(action) for action in roof_edge_support_actions) * steel_weight_assumptions_lb_per_lf["roof_edge_support"]
        + sum(_line_length_ft(action) for action in drag_collector_actions) * steel_weight_assumptions_lb_per_lf["drag_collector"]
        + (
            sum(_line_length_ft(action) for action in window_header_actions + door_header_actions)
            * steel_weight_assumptions_lb_per_lf["opening_header"]
        )
        + sum(_line_length_ft(action) for action in window_sill_actions) * steel_weight_assumptions_lb_per_lf["opening_sill"]
        + sum(float(action["height"]) / FT_TO_M for action in opening_jamb_actions) * steel_weight_assumptions_lb_per_lf["opening_jamb"]
        + sum(_line_length_ft(action) for action in brace_actions) * steel_weight_assumptions_lb_per_lf["brace"]
        + column_length_ft * steel_weight_assumptions_lb_per_lf["column"]
    )
    steel_tonnage_estimate = round(steel_weight_proxy_lb / 2000.0, 1)
    floor_plate_area_sf = sum(
        (float(action["width"]) / FT_TO_M) * (float(action["depth"]) / FT_TO_M)
        for action in slab_actions
        if "Floor Plate" in str(action["name"])
    )
    roof_area_sf = sum(
        (float(action["width"]) / FT_TO_M) * (float(action["depth"]) / FT_TO_M)
        for action in slab_actions
        if "Roof Plate" in str(action["name"])
    )
    basement_area_sf = sum(
        (float(action["width"]) / FT_TO_M) * (float(action["depth"]) / FT_TO_M)
        for action in slab_actions
        if "Basement Slab" in str(action["name"])
    )
    retaining_wall_area_sf = sum(_line_length_ft(action) * (float(action["height"]) / FT_TO_M) for action in retaining_actions)
    panel_area_sf = sum(item["panel_width_ft"] * item["panel_height_ft"] for item in panel_assignments)

    return {
        "schema_version": "1.0",
        "building": {
            "width_ft": BUILDING_WIDTH_FT,
            "length_ft": BUILDING_LENGTH_FT,
            "above_grade_height_ft": ABOVE_GRADE_HEIGHT_FT,
            "below_grade_depth_ft": BASEMENT_DEPTH_FT,
            "gross_floor_plate_sf": BUILDING_WIDTH_FT * BUILDING_LENGTH_FT,
            "story_count": STORY_COUNT,
        },
        "quantities": {
            "panel_count_total": len(panel_assignments),
            "panel_count_main_tier": len(main_tier_panels),
            "panel_count_top_tier": len(top_tier_panels),
            "panel_area_sf_total": round(panel_area_sf, 1),
            "panel_area_sf_main_tier": round(sum(item["panel_width_ft"] * item["panel_height_ft"] for item in main_tier_panels), 1),
            "panel_area_sf_top_tier": round(sum(item["panel_width_ft"] * item["panel_height_ft"] for item in top_tier_panels), 1),
            "window_count": len(openings["windows"]),
            "window_area_sf": round(
                sum((float(item["width"]) / FT_TO_M) * (float(item["height"]) / FT_TO_M) for item in openings["windows"]),
                1,
            ),
            "door_count": len(openings["doors"]),
            "door_area_sf": round(
                sum((float(item["width"]) / FT_TO_M) * (float(item["height"]) / FT_TO_M) for item in openings["doors"]),
                1,
            ),
            "steel_floor_beam_lineal_ft": round(sum(_line_length_ft(action) for action in floor_beam_actions), 1),
            "steel_floor_girder_lineal_ft": round(sum(_line_length_ft(action) for action in floor_girder_actions), 1),
            "steel_perimeter_spandrel_lineal_ft": round(sum(_line_length_ft(action) for action in perimeter_spandrel_actions), 1),
            "steel_roof_primary_frame_lineal_ft": round(sum(_line_length_ft(action) for action in primary_roof_frame_actions), 1),
            "steel_roof_collector_lineal_ft": round(sum(_line_length_ft(action) for action in roof_collector_actions), 1),
            "steel_roof_brace_lineal_ft": round(sum(_line_length_ft(action) for action in roof_brace_actions), 1),
            "steel_brace_lineal_ft": round(sum(_line_length_ft(action) for action in brace_actions), 1),
            "steel_panel_joint_support_lineal_ft": round(sum(_line_length_ft(action) for action in panel_joint_support_actions), 1),
            "steel_roof_edge_support_lineal_ft": round(sum(_line_length_ft(action) for action in roof_edge_support_actions), 1),
            "steel_drag_collector_lineal_ft": round(sum(_line_length_ft(action) for action in drag_collector_actions), 1),
            "opening_header_lineal_ft": round(sum(_line_length_ft(action) for action in window_header_actions + door_header_actions), 1),
            "opening_sill_lineal_ft": round(sum(_line_length_ft(action) for action in window_sill_actions), 1),
            "opening_jamb_lineal_ft": round(sum(float(action["height"]) / FT_TO_M for action in opening_jamb_actions), 1),
            "steel_beam_lineal_ft": round(beam_length_ft, 1),
            "steel_column_lineal_ft": round(column_length_ft, 1),
            "steel_tonnage_proxy_tons": steel_tonnage_estimate,
            "floor_plate_area_sf": round(floor_plate_area_sf, 1),
            "roof_area_sf": round(roof_area_sf, 1),
            "basement_slab_area_sf": round(basement_area_sf, 1),
            "retaining_wall_area_sf": round(retaining_wall_area_sf, 1),
            "excavation_volume_cy_proxy": round((BUILDING_WIDTH_FT * BUILDING_LENGTH_FT * BASEMENT_DEPTH_FT) / 27.0, 1),
        },
        "input_costs": {
            "insulated_precast_panel_installed_usd_per_sf": {
                "low": 50.0,
                "mid": 75.0,
                "high": 100.0,
                "source_label": "JW Precast standard wall panels",
                "source_url": "https://jwprecastconcrete.com/cost-precast-concrete-services",
            },
            "structural_steel_supply_usd_per_ton": {
                "low": 4072.0,
                "mid": 4492.0,
                "high": 4541.0,
                "source_label": "Linbeck Q2 2025 construction market forecast",
                "source_url": "https://www.linbeck.com/wp-content/uploads/2025/07/q2-2025-construction-market-forecast.pdf",
            },
            "structural_steel_erection_usd_per_ton": {
                "low": 400.0,
                "mid": 750.0,
                "high": 1200.0,
                "source_label": "Steel Estimating Solutions 2025 U.S. data",
                "source_url": "https://steelestimatingsolutions.com/steel-erection-cost-estimator/",
            },
            "storefront_window_installed_usd_per_sf": {
                "low": 50.0,
                "mid": 100.0,
                "high": 150.0,
                "source_label": "Aprodoor storefront guide",
                "source_url": "https://www.aprodoor.com/commercial-storefront-windows-cost/",
            },
            "glazed_entry_door_usd_each": {
                "low": 1300.0,
                "mid": 2600.0,
                "high": 4000.0,
                "source_label": "Montgomery County FCI replacement allowance",
                "source_url": "https://ww2.montgomeryschoolsmd.org/departments/facilities/FCI/reports/172559.25R000-078.354%20-%20Meadow%20Hall%20Elementary%20School%20-%20Rockville%2C%20MD%20-%20FCA%28RevisedFinal%29.pdf",
            },
            "ready_mix_concrete_usd_per_cy": {
                "low": 140.0,
                "mid": 180.0,
                "high": 220.0,
                "source_label": "BuilderToolKits / Concrete Network planning ranges",
                "source_url": "https://www.buildertoolkits.com/concrete/cost-per-yard",
            },
            "excavation_usd_per_cy": {
                "low": 2.5,
                "mid": 8.75,
                "high": 15.0,
                "source_label": "HomeGuide excavation guide",
                "source_url": "https://homeguide.com/costs/excavation-cost",
            },
            "micropile_allowance_note": {
                "value": None,
                "note": "Leave blank until micropile count and embed depth are defined against the geotech report.",
            },
            "crane_allowance_note": {
                "value": None,
                "note": "Price separately for the 12 ft top tier if crane placement is chosen.",
            },
            "internal_ramp_allowance_note": {
                "value": None,
                "note": "Price separately for temporary internal ramp/platform and productivity loss if crane is avoided.",
            },
        },
        "steel_weight_assumptions_lb_per_lf": steel_weight_assumptions_lb_per_lf,
        "site_options": {
            "top_tier_installation_options": [
                {
                    "option": "crane_assist",
                    "description": "External crane pick for the upper 12 ft cap tier.",
                    "added_cost_field": "top_tier_crane_allowance",
                },
                {
                    "option": "internal_ramp_and_forklift",
                    "description": "Temporary internal ramp / platform strategy for the upper 12 ft cap tier.",
                    "added_cost_field": "top_tier_internal_ramp_allowance",
                },
            ]
        },
        "cost_breakdown": {
            "shell_enclosure": {
                "panel_area_sf": round(panel_area_sf, 1),
                "window_area_sf": round(
                    sum((float(item["width"]) / FT_TO_M) * (float(item["height"]) / FT_TO_M) for item in openings["windows"]),
                    1,
                ),
                "door_count": len(openings["doors"]),
                "notes": [
                    "Use insulated precast panel installed $/sf inputs for the shell envelope.",
                    "Top-tier installation should carry either crane or internal ramp allowance separately.",
                ],
            },
            "steel_superstructure": {
                "primary_roof_frame_lineal_ft": round(sum(_line_length_ft(action) for action in primary_roof_frame_actions), 1),
                "roof_collector_lineal_ft": round(sum(_line_length_ft(action) for action in roof_collector_actions), 1),
                "roof_brace_lineal_ft": round(sum(_line_length_ft(action) for action in roof_brace_actions), 1),
                "perimeter_spandrel_lineal_ft": round(sum(_line_length_ft(action) for action in perimeter_spandrel_actions), 1),
                "floor_beam_lineal_ft": round(sum(_line_length_ft(action) for action in floor_beam_actions), 1),
                "floor_girder_lineal_ft": round(sum(_line_length_ft(action) for action in floor_girder_actions), 1),
                "panel_joint_support_lineal_ft": round(sum(_line_length_ft(action) for action in panel_joint_support_actions), 1),
                "roof_edge_support_lineal_ft": round(sum(_line_length_ft(action) for action in roof_edge_support_actions), 1),
                "drag_collector_lineal_ft": round(sum(_line_length_ft(action) for action in drag_collector_actions), 1),
                "brace_lineal_ft": round(sum(_line_length_ft(action) for action in brace_actions), 1),
                "opening_header_lineal_ft": round(sum(_line_length_ft(action) for action in window_header_actions + door_header_actions), 1),
                "opening_sill_lineal_ft": round(sum(_line_length_ft(action) for action in window_sill_actions), 1),
                "opening_jamb_lineal_ft": round(sum(float(action["height"]) / FT_TO_M for action in opening_jamb_actions), 1),
                "column_lineal_ft": round(column_length_ft, 1),
            },
            "substructure": {
                "basement_slab_area_sf": round(basement_area_sf, 1),
                "retaining_wall_area_sf": round(retaining_wall_area_sf, 1),
                "excavation_volume_cy_proxy": round((BUILDING_WIDTH_FT * BUILDING_LENGTH_FT * BASEMENT_DEPTH_FT) / 27.0, 1),
                "notes": [
                    "Use soils-report-based footing, retaining, and micropile allowances as those are defined.",
                    "Below-grade wall and shoring pricing should remain separate from the above-grade shell cost.",
                ],
            },
        },
        "alternates": {
            "steel_plus_precast_floor": {
                "description": "Steel frame with precast floor and roof panels.",
                "quantity_basis": {"floor_area_sf": round(floor_plate_area_sf, 1), "roof_area_sf": round(roof_area_sf, 1)},
                "unit_cost_inputs": {
                    "precast_floor_panel_installed_usd_per_sf": None,
                    "precast_roof_panel_installed_usd_per_sf": None,
                },
            },
            "wood_plus_gypcrete_floor": {
                "description": "Steel shell with wood-framed floors and gypcrete topping.",
                "quantity_basis": {"floor_area_sf": round(floor_plate_area_sf, 1), "roof_area_sf": round(roof_area_sf, 1)},
                "unit_cost_inputs": {
                    "wood_floor_framing_usd_per_sf": None,
                    "subfloor_usd_per_sf": None,
                    "gypcrete_usd_per_sf": None,
                    "acoustic_assembly_usd_per_sf": None,
                },
            },
        },
    }


def render_cost_markdown(cost_inputs: dict) -> str:
    q = cost_inputs["quantities"]
    unit_costs = cost_inputs["input_costs"]
    lines = [
        "# Tech Ridge Cost Inputs",
        "",
        "## Quantities",
        "",
        f"- Panels: {q['panel_count_total']} total ({q['panel_count_main_tier']} main tier, {q['panel_count_top_tier']} top tier)",
        f"- Panel area: {q['panel_area_sf_total']} sf",
        f"- Windows: {q['window_count']} ({q['window_area_sf']} sf)",
        f"- Doors: {q['door_count']} ({q['door_area_sf']} sf)",
        f"- Steel beams total: {q['steel_beam_lineal_ft']} lf",
        f"- Steel floor beams: {q['steel_floor_beam_lineal_ft']} lf",
        f"- Steel floor girders: {q['steel_floor_girder_lineal_ft']} lf",
        f"- Steel perimeter spandrels: {q['steel_perimeter_spandrel_lineal_ft']} lf",
        f"- Steel roof primary frames: {q['steel_roof_primary_frame_lineal_ft']} lf",
        f"- Steel roof collectors: {q['steel_roof_collector_lineal_ft']} lf",
        f"- Steel roof braces: {q['steel_roof_brace_lineal_ft']} lf",
        f"- Steel braces: {q['steel_brace_lineal_ft']} lf",
        f"- Steel panel joint supports: {q['steel_panel_joint_support_lineal_ft']} lf",
        f"- Steel roof edge supports: {q['steel_roof_edge_support_lineal_ft']} lf",
        f"- Steel drag collectors: {q['steel_drag_collector_lineal_ft']} lf",
        f"- Opening headers: {q['opening_header_lineal_ft']} lf",
        f"- Opening sills: {q['opening_sill_lineal_ft']} lf",
        f"- Opening jambs: {q['opening_jamb_lineal_ft']} lf",
        f"- Steel columns: {q['steel_column_lineal_ft']} lf",
        f"- Steel tonnage proxy: {q['steel_tonnage_proxy_tons']} tons",
        f"- Floor plate area: {q['floor_plate_area_sf']} sf",
        f"- Roof area: {q['roof_area_sf']} sf",
        f"- Basement slab area: {q['basement_slab_area_sf']} sf",
        f"- Retaining wall area: {q['retaining_wall_area_sf']} sf",
        f"- Excavation proxy: {q['excavation_volume_cy_proxy']} cy",
        "",
        "## Unit Cost Inputs To Fill",
        "",
    ]
    for key, value in unit_costs.items():
        if isinstance(value, dict) and {"low", "mid", "high"}.issubset(value):
            lines.append(
                f"- {key}: {value['low']} / {value['mid']} / {value['high']} | source: {value['source_label']} | {value['source_url']}"
            )
        else:
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Steel Weight Assumptions", ""])
    for key, value in cost_inputs["steel_weight_assumptions_lb_per_lf"].items():
        lines.append(f"- {key}: {value} lb/lf")
    lines.extend(["", "## Cost Breakdown Buckets", ""])
    for section_name, section in cost_inputs["cost_breakdown"].items():
        lines.append(f"- {section_name}:")
        for key, value in section.items():
            lines.append(f"  - {key}: {value}")
    lines.extend(
        [
            "",
            "## Floor System Alternates",
            "",
            "- steel_plus_precast_floor: fill precast installed unit costs for the floor and roof areas",
            "- wood_plus_gypcrete_floor: fill wood framing, subfloor, topping, and acoustic assembly costs for the floor areas",
            "",
            "## Installation Options",
            "",
            "- crane_assist: price crane mobilization and upper-tier picks separately",
            "- internal_ramp_and_forklift: price temporary internal ramp/platform, staging, and productivity penalty separately",
        ]
    )
    return "\n".join(lines) + "\n"


def _clear_generated_outputs(output_dir: Path, *, preserve_physical_artifacts: bool = False) -> None:
    if not output_dir.exists():
        return
    preserve_names = {"techridge_initial_shell.blend"}
    if preserve_physical_artifacts:
        preserve_names.update(
            {
                "techridge_initial_shell.ifc",
                "freecad_handoff.FCStd",
                "freecad_handoff.json",
                "freecad_handoff.py",
                "freecad_run_report.json",
            }
        )
    preserve_prefixes = ("review_renders",)
    for child in output_dir.iterdir():
        if child.name in preserve_names or child.name.startswith(preserve_prefixes):
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def build_package(output_dir: Path, *, fast_analysis: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    _clear_generated_outputs(output_dir, preserve_physical_artifacts=fast_analysis)
    system_catalog = starter_core_shell_catalog()
    plan, component_assignments, openings = build_plan()
    (output_dir / "techridge_initial_shell_plan.json").write_text(json.dumps(plan, indent=2))
    (output_dir / "system_catalog.json").write_text(json.dumps(system_catalog, indent=2))
    component_reference = {
        "component_id": COMPONENT_ID,
        "component_spec_path": str(COMPONENT_SPEC_PATH),
        "component_package_dir": str(COMPONENT_OUTPUT_DIR),
        "assignments_file": "component_assignments.json",
    }
    (output_dir / "component_reference.json").write_text(json.dumps(component_reference, indent=2))
    (output_dir / "component_assignments.json").write_text(json.dumps(component_assignments, indent=2))
    (output_dir / "placeholder_openings.json").write_text(json.dumps(openings, indent=2))
    cost_inputs = build_cost_inputs(plan, component_assignments, openings)
    (output_dir / "cost_inputs.json").write_text(json.dumps(cost_inputs, indent=2))
    (output_dir / "cost_table.md").write_text(render_cost_markdown(cost_inputs))
    (output_dir / "steel_scaling_basis.md").write_text(
        "\n".join(
            [
                "# Tech Ridge Steel Scaling Basis",
                "",
                "Use the CO Buildings Cedar City PEMB as a framing-reference template, not a direct member-size template.",
                "",
                f"- Reference PEMB: {REFERENCE_PEMB_WIDTH_FT:.0f} ft x {REFERENCE_PEMB_LENGTH_FT:.0f} ft x {REFERENCE_PEMB_EAVE_HEIGHT_FT:.0f} ft eave",
                f"- Tech Ridge shell: {BUILDING_WIDTH_FT:.0f} ft x {BUILDING_LENGTH_FT:.0f} ft x {ABOVE_GRADE_HEIGHT_FT:.0f} ft above grade plus {BASEMENT_DEPTH_FT:.0f} ft below grade",
                f"- Width ratio: {BUILDING_WIDTH_FT / REFERENCE_PEMB_WIDTH_FT:.3f}",
                f"- Length ratio: {BUILDING_LENGTH_FT / REFERENCE_PEMB_LENGTH_FT:.3f}",
                f"- Above-grade height ratio: {ABOVE_GRADE_HEIGHT_FT / REFERENCE_PEMB_EAVE_HEIGHT_FT:.3f}",
                f"- Total structural height ratio including basement: {(ABOVE_GRADE_HEIGHT_FT + BASEMENT_DEPTH_FT) / REFERENCE_PEMB_EAVE_HEIGHT_FT:.3f}",
                "",
                "What can transfer:",
                "- frame rhythm and bay spacing tendencies",
                "- bracing-zone concepts",
                "- secondary steel logic for girts and purlins",
                "",
                "What cannot transfer directly:",
                "- final member sizes",
                "- base reactions and footing sizes",
                "- drift-sensitive lateral system assumptions",
                "- panel support reactions for the taller 62 ft above-grade shell",
            ]
        )
        + "\n"
    )

    brief = DesignBrief(
        prompt="Initial 5-story Tech Ridge shell using InnovaCast panels on a steel superstructure.",
        analysis_domains=[AnalysisDomain.GRAVITY, AnalysisDomain.WIND],
        constraints=[
            "Use InnovaCast insulated concrete panels as the above-grade cladding shell.",
            "Maximum panel width 12 feet; prefer 12-foot modules where possible.",
            "Support panel tiers at floor lines or other support intervals within 16.58 feet.",
            "Treat the 12-foot below-grade portion as separate substructure and retaining design.",
        ],
        metadata={
            "site_name": "Tech Ridge, St. George, Utah",
            "site_class": "C",
            "sds": 0.434,
            "sd1": 0.163,
            "wind_basis_note": "Provisional Risk Category II / Exposure C / 115 mph assumption for early shell sizing only.",
            "geotech_report": "Landmark Project No. 240480",
            "reference_pemb": "CO Buildings / InnovaCast PEMB reference",
            "component_id": COMPONENT_ID,
            "component_spec_path": str(COMPONENT_SPEC_PATH),
        },
    )
    physical_model = PhysicalModelSpec(
        summary=plan["summary"],
        assumptions=list(plan["assumptions"]),
        plan=plan,
        metadata={
            "source_reports": [
                "/Users/alanknudson/Downloads/InnovaCast Cladding Report of Analysis_12-2-25.pdf",
                "/Users/alanknudson/Downloads/T240-25-INNOVACAST FWC 090325.pdf",
                "/Users/alanknudson/Downloads/ICP DETAIL                                        88 S 6500 W CEDAR CITY, UTAH 84721.pdf",
                "/Users/alanknudson/Library/Mobile Documents/com~apple~CloudDocs/240480 Tech Ridge Planning Area 1.2 GR Sealed.pdf",
                "/Users/alanknudson/Downloads/PEMB.pdf",
            ],
            "component_reference": component_reference,
            "window_count_placeholder": len(openings["windows"]),
            "door_count_placeholder": len(openings["doors"]),
            "cost_inputs_file": "cost_inputs.json",
            "system_catalog_file": "system_catalog.json",
            "system_catalog_data": system_catalog,
            "system_catalog_summary": starter_catalog_summary(system_catalog),
        },
    )
    primary_analysis_profile = "global_fast" if fast_analysis else "global_full"
    secondary_profiles = [
        profile
        for profile in ("global_fast", "global_full", "facade_support", "substructure")
        if profile != primary_analysis_profile
    ]

    analysis_request = AnalysisRequest(
        solver="pynite",
        design_codes=["ASCE 7-22", "AISC 360-22"],
        load_cases=[
            LoadCase(name="Gravity", domain=AnalysisDomain.GRAVITY, code_basis="ASCE 7-22"),
            LoadCase(name="Wind X+", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22", parameters={"pressure_kpa": 1.4, "direction": "global_x"}),
            LoadCase(name="Wind Y+", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22", parameters={"pressure_kpa": 1.4, "direction": "global_y"}),
        ],
        load_combinations=[
            LoadCombination(name="ULS Gravity + Wind X", case_factors={"Gravity": 1.2, "Wind X+": 1.0}, code_basis="ASCE 7-22"),
            LoadCombination(name="ULS Gravity + Wind Y", case_factors={"Gravity": 1.2, "Wind Y+": 1.0}, code_basis="ASCE 7-22"),
        ],
        export_options={
            "freecad_handoff": not fast_analysis,
            "analysis_profile": primary_analysis_profile,
            "analysis_profiles": secondary_profiles,
            "engineering_scopes": ENGINEERING_SCOPES,
        },
        metadata={
            "site_class": "C",
            "sds": 0.434,
            "sd1": 0.163,
            "wind_pressure_kpa": 1.4,
            "note": "Initial shell sizing package only. Seismic and footing design will be refined in later iterations.",
            "solver_iteration_mode": primary_analysis_profile,
            "fast_analysis": fast_analysis,
            "enable_grouped_sizing": True,
        },
    )
    package = DesignPackage(brief=brief, physical_model=physical_model, analysis_request=analysis_request)

    if not fast_analysis:
        physical_backend = IfcPhysicalModelBackend(filename="techridge_initial_shell.ifc")
        package.physical_artifacts = list(physical_backend.materialize(package, output_dir))
    package.analysis_artifacts = list(JsonAnalysisExportBackend(include_freecad_handoff=not fast_analysis).export(package, output_dir))
    if analysis_request.metadata.get("enable_grouped_sizing"):
        package.analysis_result, sizing_summary, sizing_artifacts = GroupedSectionSizer().size(package, output_dir)
        package.analysis_artifacts.extend(sizing_artifacts)
    else:
        package.analysis_result = PyNiteSolverBackend().analyze(analysis_request, package, output_dir)
    package.analysis_artifacts.extend(package.analysis_result.artifacts)
    footing_summary = build_starter_footing_summary(package)
    (output_dir / "footing_design_summary.json").write_text(json.dumps(footing_summary, indent=2))
    if not fast_analysis:
        package.review_artifacts = list(run_freecad_handoff(output_dir, freecad_bin=FREECAD_CMD, timeout_seconds=180))
    package.review_artifacts.append(
        PipelineArtifact(
            kind=ArtifactKind.ENGINEERING_REPORT,
            format=ArtifactFormat.JSON,
            path=str(output_dir / "footing_design_summary.json"),
            metadata={"role": "engineering_report", "label": "Footing Design Summary", "report_kind": "footing_design_summary", "is_primary": False},
        )
    )
    package.review_artifacts.append(
        PipelineArtifact(
            kind=ArtifactKind.ENGINEERING_REPORT,
            format=ArtifactFormat.JSON,
            path=str(output_dir / "cost_inputs.json"),
            metadata={"role": "engineering_report", "label": "Cost Inputs", "is_primary": False},
        )
    )
    package.review_artifacts.append(
        PipelineArtifact(
            kind=ArtifactKind.ENGINEERING_REPORT,
            format=ArtifactFormat.JSON,
            path=str(output_dir / "system_catalog.json"),
            metadata={"role": "engineering_report", "label": "Starter System Catalog", "report_kind": "system_catalog", "is_primary": False},
        )
    )
    package.results_artifacts = list(JsonResultsBundleBackend().build(package, output_dir))
    DesignPipeline.write_manifest(package, output_dir / "design_package.json")
    return package.to_manifest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(ROOT / "out" / "techridge_initial_shell"))
    parser.add_argument("--fast-analysis", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    manifest = build_package(output_dir, fast_analysis=bool(args.fast_analysis))
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "manifest_path": str(output_dir / "design_package.json"),
                "brief": manifest["brief"]["prompt"],
                "fast_analysis": bool(args.fast_analysis),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
