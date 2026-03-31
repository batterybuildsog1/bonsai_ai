from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bonsai_ai.ifc_author import IfcAuthor
from bonsai_ai.footing_selector import starter_footing_from_imposed_load


SQM_TO_SQFT = 10.7639

BASE_LENGTH_M = 36.0
BASE_WIDTH_M = 31.0
BASE_AREA_SQFT = BASE_LENGTH_M * BASE_WIDTH_M * SQM_TO_SQFT

GROUND_HEIGHT_M = 5.4
UPPER_HEIGHT_M = 4.2
PARAPET_TOP_M = GROUND_HEIGHT_M + 1.2
UPPER_BASE_Z_M = GROUND_HEIGHT_M
UPPER_ROOF_Z_M = GROUND_HEIGHT_M + UPPER_HEIGHT_M
FOUNDATION_ELEVATION_M = -1.2

GROUND_SLAB_THICKNESS_M = 0.30
UPPER_SLAB_THICKNESS_M = 0.25
ROOF_SLAB_THICKNESS_M = 0.22
WALL_THICKNESS_M = 0.25
CLADDING_THICKNESS_M = 0.08
CANOPY_THICKNESS_M = 0.12

UPPER_LENGTH_M = 24.0
UPPER_WIDTH_M = 18.0
UPPER_ORIGIN_X_M = (BASE_LENGTH_M - UPPER_LENGTH_M) / 2.0
UPPER_ORIGIN_Y_M = (BASE_WIDTH_M - UPPER_WIDTH_M) / 2.0

RAILING_POST_SIZE_M = 0.08
RAILING_TOP_SIZE_M = 0.06
RAILING_TOP_Z_M = GROUND_HEIGHT_M + 1.15
RAILING_MID_Z_M = GROUND_HEIGHT_M + 0.60

FRAME_BEAM_WIDTH_M = 0.22
FRAME_BEAM_DEPTH_M = 0.42


def _metadata(*payloads: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for payload in payloads:
        merged.update(payload)
    return merged


def _semantics(
    role: str,
    *,
    subrole: str | None = None,
    system_name: str | None = None,
    group_name: str | None = None,
    group_path: list[str] | None = None,
    selector_tags: list[str] | None = None,
    is_exposed: bool | None = None,
    view_mode: str | None = None,
) -> dict[str, object]:
    payload = {
        "role": role,
        "subrole": subrole,
        "system_name": system_name,
        "group_name": group_name,
        "group_path": group_path,
        "selector_tags": selector_tags,
        "is_exposed": is_exposed,
        "view_mode": view_mode,
    }
    return {"semantics": {key: value for key, value in payload.items() if value is not None}}


def _presentation(
    *,
    material_key: str | None = None,
    presentation_style: str | None = None,
    window_type: str | None = None,
    frame_style: str | None = None,
    glazing_style: str | None = None,
    glass_material_key: str | None = None,
    frame_material_key: str | None = None,
    is_storefront: bool | None = None,
) -> dict[str, object]:
    payload = {
        "material_key": material_key,
        "presentation_style": presentation_style,
        "window_type": window_type,
        "frame_style": frame_style,
        "glazing_style": glazing_style,
        "glass_material_key": glass_material_key,
        "frame_material_key": frame_material_key,
        "is_storefront": is_storefront,
    }
    return {"presentation": {key: value for key, value in payload.items() if value is not None}}


def _rounded(value: float) -> float:
    return round(value, 6)


def _segment_points(start: tuple[float, float], end: tuple[float, float], spacing: float) -> list[tuple[float, float]]:
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return [start]
    count = max(1, int(length // spacing))
    points = []
    for index in range(count + 1):
        ratio = index / count
        points.append((_rounded(sx + dx * ratio), _rounded(sy + dy * ratio)))
    return points


def _loop_points(points: list[tuple[float, float]], spacing: float) -> list[tuple[float, float]]:
    loop: list[tuple[float, float]] = []
    for start, end in zip(points, points[1:] + points[:1]):
        segment = _segment_points(start, end, spacing)
        if loop:
            segment = segment[1:]
        loop.extend(segment)
    if loop and loop[0] == loop[-1]:
        loop.pop()
    return loop


def _add_wall_box(
    author: IfcAuthor,
    *,
    prefix: str,
    storey: str,
    x: float,
    y: float,
    length: float,
    width: float,
    base_z: float,
    height: float,
    thickness: float = WALL_THICKNESS_M,
) -> None:
    wall_metadata = _metadata(
        _semantics(
            "envelope",
            subrole="perimeter_wall",
            system_name=f"{prefix} Envelope",
            group_path=[prefix, "Perimeter Walls"],
            view_mode="envelope",
        ),
        _presentation(material_key="concrete"),
    )
    author.create_wall(
        name=f"{prefix} South Wall",
        storey_name=storey,
        start_x=x,
        start_y=y,
        end_x=x + length,
        end_y=y,
        base_z=base_z,
        height=height,
        thickness=thickness,
        **wall_metadata,
    )
    author.create_wall(
        name=f"{prefix} East Wall",
        storey_name=storey,
        start_x=x + length,
        start_y=y,
        end_x=x + length,
        end_y=y + width,
        base_z=base_z,
        height=height,
        thickness=thickness,
        **wall_metadata,
    )
    author.create_wall(
        name=f"{prefix} North Wall",
        storey_name=storey,
        start_x=x + length,
        start_y=y + width,
        end_x=x,
        end_y=y + width,
        base_z=base_z,
        height=height,
        thickness=thickness,
        **wall_metadata,
    )
    author.create_wall(
        name=f"{prefix} West Wall",
        storey_name=storey,
        start_x=x,
        start_y=y + width,
        end_x=x,
        end_y=y,
        base_z=base_z,
        height=height,
        thickness=thickness,
        **wall_metadata,
    )


def _add_vertical_panel_strip(
    author: IfcAuthor,
    *,
    storey: str,
    name_prefix: str,
    x: float,
    y: float,
    base_z: float,
    total_width: float,
    height: float,
    rotation_deg: float,
    panel_width: float = 6.0,
    accent_indices: set[int] | None = None,
) -> None:
    accent_indices = accent_indices or set()
    current_x = x
    current_y = y
    remaining = total_width
    index = 1
    step_x = panel_width * math.cos(math.radians(rotation_deg))
    step_y = panel_width * math.sin(math.radians(rotation_deg))
    while remaining > 1e-6:
        width = min(panel_width, remaining)
        panel_kind = "Accent Panel" if index in accent_indices else "Cladding Panel"
        panel_material = "accent" if index in accent_indices else "cladding"
        author.create_panel(
            name=f"{name_prefix} {panel_kind} {index:02d}",
            storey_name=storey,
            x=_rounded(current_x),
            y=_rounded(current_y),
            base_z=base_z,
            width=_rounded(width),
            height=height,
            depth=None,
            thickness=CLADDING_THICKNESS_M,
            orientation="vertical",
            rotation_deg=rotation_deg,
            **_metadata(
                _semantics(
                    "cladding",
                    subrole="accent_panel" if index in accent_indices else "cladding_panel",
                    system_name=f"{name_prefix} Cladding",
                    group_path=[name_prefix, panel_kind],
                    view_mode="envelope",
                ),
                _presentation(material_key=panel_material, presentation_style=panel_material),
            ),
        )
        current_x += step_x
        current_y += step_y
        remaining -= width
        index += 1


def _add_corner_columns(
    author: IfcAuthor,
    *,
    prefix: str,
    storey: str,
    x: float,
    y: float,
    length: float,
    width: float,
    base_z: float,
    height: float,
    size: float,
) -> None:
    for index, (px, py) in enumerate(
        [
            (x + 0.50, y + 0.50),
            (x + length - 0.50 - size, y + 0.50),
            (x + length - 0.50 - size, y + width - 0.50 - size),
            (x + 0.50, y + width - 0.50 - size),
        ],
        start=1,
    ):
        author.create_column(
            name=f"{prefix} Steel Column {index}",
            storey_name=storey,
            x=_rounded(px),
            y=_rounded(py),
            base_z=base_z,
            width=size,
            depth=size,
            height=height,
            **_metadata(
                _semantics(
                    "structure",
                    subrole="corner_column",
                    system_name=f"{prefix} Steel Frame",
                    group_path=[prefix, "Columns", "Corner Columns"],
                    is_exposed=True,
                    view_mode="structure",
                ),
                _presentation(material_key="steel", presentation_style="exposed_steel"),
            ),
        )


def _add_perimeter_frame(
    author: IfcAuthor,
    *,
    prefix: str,
    storey: str,
    x: float,
    y: float,
    length: float,
    width: float,
    base_z: float,
) -> None:
    beam_metadata = _metadata(
        _semantics(
            "structure",
            subrole="perimeter_beam",
            system_name=f"{prefix} Steel Frame",
            group_path=[prefix, "Beams", "Perimeter Frame"],
            is_exposed=True,
            view_mode="structure",
        ),
        _presentation(material_key="steel", presentation_style="exposed_steel"),
    )
    perimeter = [
        ("South Frame Beam", (x + 0.5, y + 0.5), (x + length - 0.5, y + 0.5)),
        ("East Frame Beam", (x + length - 0.5, y + 0.5), (x + length - 0.5, y + width - 0.5)),
        ("North Frame Beam", (x + length - 0.5, y + width - 0.5), (x + 0.5, y + width - 0.5)),
        ("West Frame Beam", (x + 0.5, y + width - 0.5), (x + 0.5, y + 0.5)),
    ]
    for label, start, end in perimeter:
        author.create_beam(
            name=f"{prefix} {label}",
            storey_name=storey,
            start_x=_rounded(start[0]),
            start_y=_rounded(start[1]),
            end_x=_rounded(end[0]),
            end_y=_rounded(end[1]),
            base_z=base_z,
            width=FRAME_BEAM_WIDTH_M,
            depth=FRAME_BEAM_DEPTH_M,
            **beam_metadata,
        )


def _add_spread_footing(
    author: IfcAuthor,
    *,
    name: str,
    x: float,
    y: float,
    imposed_load_kn: float,
    support_for: str,
    group_path: list[str],
) -> None:
    recommendation = starter_footing_from_imposed_load(
        imposed_load_kn,
        footing_family="spread_footing",
        basis_note=f"Concept footing sized from imposed load for {support_for}.",
    )
    footing_size = recommendation["recommended_square_size_m"]
    footing_thickness = recommendation["footing_thickness_m"]
    author.create_footing(
        name=name,
        storey_name="Foundations",
        x=_rounded(x - footing_size / 2.0),
        y=_rounded(y - footing_size / 2.0),
        base_z=FOUNDATION_ELEVATION_M,
        length=footing_size,
        width=footing_size,
        thickness=footing_thickness,
        **_metadata(
            _semantics(
                "foundations",
                subrole="spread_footing",
                system_name="Retail Terrace Foundations",
                group_path=group_path,
                view_mode="foundations",
            ),
            _presentation(material_key="foundation"),
            {
                "foundation": {
                    "foundation_type": "spread_footing",
                    "support_for": support_for,
                    "imposed_load_kn": recommendation["imposed_load_kn"],
                    "allowable_bearing_kpa": recommendation["allowable_bearing_kpa"],
                    "concrete_strength_mpa": recommendation["concrete_strength_mpa"],
                    "rebar_yield_strength_mpa": recommendation["rebar_yield_strength_mpa"],
                    "rebar_grade": recommendation["rebar_grade"],
                    "rebar_weight_kg": recommendation["rebar_weight_kg"],
                    "rebar_bar_diameter_mm": recommendation["rebar_bar_diameter_mm"],
                    "rebar_spacing_mm": recommendation["rebar_spacing_mm"],
                    "rebar_layer_count": recommendation["rebar_layer_count"],
                    "rebar_schedule": recommendation["rebar_schedule"],
                    "basis_notes": recommendation["basis_notes"],
                }
            },
        ),
    )


def _add_terrace_railing(author: IfcAuthor, *, storey: str) -> int:
    railing_metadata = _metadata(
        _semantics(
            "railings",
            subrole="terrace_guardrail",
            system_name="Terrace Guardrail",
            group_path=["Terrace", "Guardrail"],
        ),
        _presentation(material_key="steel_dark", presentation_style="painted_steel"),
    )
    inset = 0.45
    points = _loop_points(
        [
            (inset, inset),
            (BASE_LENGTH_M - inset, inset),
            (BASE_LENGTH_M - inset, BASE_WIDTH_M - inset),
            (inset, BASE_WIDTH_M - inset),
        ],
        spacing=3.0,
    )
    for index, (px, py) in enumerate(points, start=1):
        author.create_column(
            name=f"Terrace Railing Post {index:02d}",
            storey_name=storey,
            x=_rounded(px - RAILING_POST_SIZE_M / 2.0),
            y=_rounded(py - RAILING_POST_SIZE_M / 2.0),
            base_z=UPPER_BASE_Z_M,
            width=RAILING_POST_SIZE_M,
            depth=RAILING_POST_SIZE_M,
            height=1.2,
            **railing_metadata,
        )

    beam_count = 0
    for z_value, label in [(RAILING_TOP_Z_M, "Top Rail"), (RAILING_MID_Z_M, "Mid Rail")]:
        for index, (start, end) in enumerate(zip(points, points[1:] + points[:1]), start=1):
            author.create_beam(
                name=f"Terrace {label} {index:02d}",
                storey_name=storey,
                start_x=start[0],
                start_y=start[1],
                end_x=end[0],
                end_y=end[1],
                base_z=z_value,
                width=RAILING_TOP_SIZE_M,
                depth=RAILING_TOP_SIZE_M,
                **railing_metadata,
            )
            beam_count += 1
    return len(points) + beam_count


def build_concept(output_path: Path, report_path: Path | None = None) -> dict:
    if output_path.exists():
        output_path.unlink()
    author = IfcAuthor(str(output_path))
    author.ensure_project(
        project_name="Retail Terrace Concept",
        site_name="Concept Site",
        building_name="Podium Retail Building",
    )
    author.ensure_storey(name="Foundations", elevation=FOUNDATION_ELEVATION_M)
    author.ensure_storey(name="Ground Floor", elevation=0.0)
    author.ensure_storey(name="Terrace Level", elevation=UPPER_BASE_Z_M)
    author.ensure_storey(name="Roof", elevation=UPPER_ROOF_Z_M)

    author.create_rectangular_slab(
        name="Ground Floor Slab",
        storey_name="Ground Floor",
        x=0.0,
        y=0.0,
        z=0.0,
        length=BASE_LENGTH_M,
        width=BASE_WIDTH_M,
        thickness=GROUND_SLAB_THICKNESS_M,
        **_metadata(
            _semantics("envelope", subrole="ground_slab", system_name="Podium Floor Plates", group_path=["Podium", "Floor Plates"]),
            _presentation(material_key="slab"),
        ),
    )
    author.create_rectangular_slab(
        name="Terrace Podium Slab",
        storey_name="Terrace Level",
        x=0.0,
        y=0.0,
        z=UPPER_BASE_Z_M,
        length=BASE_LENGTH_M,
        width=BASE_WIDTH_M,
        thickness=UPPER_SLAB_THICKNESS_M,
        **_metadata(
            _semantics("envelope", subrole="terrace_slab", system_name="Podium Floor Plates", group_path=["Terrace", "Floor Plates"]),
            _presentation(material_key="slab"),
        ),
    )
    author.create_rectangular_slab(
        name="Upper Level Slab",
        storey_name="Terrace Level",
        x=UPPER_ORIGIN_X_M,
        y=UPPER_ORIGIN_Y_M,
        z=UPPER_BASE_Z_M,
        length=UPPER_LENGTH_M,
        width=UPPER_WIDTH_M,
        thickness=UPPER_SLAB_THICKNESS_M,
        **_metadata(
            _semantics("envelope", subrole="upper_floor_slab", system_name="Upper Volume Floor Plates", group_path=["Upper Volume", "Floor Plates"]),
            _presentation(material_key="slab"),
        ),
    )
    author.create_rectangular_slab(
        name="Upper Roof Slab",
        storey_name="Roof",
        x=UPPER_ORIGIN_X_M,
        y=UPPER_ORIGIN_Y_M,
        z=UPPER_ROOF_Z_M,
        length=UPPER_LENGTH_M,
        width=UPPER_WIDTH_M,
        thickness=ROOF_SLAB_THICKNESS_M,
        **_metadata(
            _semantics("roof", subrole="roof_slab", system_name="Upper Volume Roof", group_path=["Upper Volume", "Roof"]),
            _presentation(material_key="slab"),
        ),
    )

    _add_wall_box(
        author,
        prefix="Ground Retail",
        storey="Ground Floor",
        x=0.0,
        y=0.0,
        length=BASE_LENGTH_M,
        width=BASE_WIDTH_M,
        base_z=0.0,
        height=GROUND_HEIGHT_M,
    )
    _add_wall_box(
        author,
        prefix="Upper Volume",
        storey="Terrace Level",
        x=UPPER_ORIGIN_X_M,
        y=UPPER_ORIGIN_Y_M,
        length=UPPER_LENGTH_M,
        width=UPPER_WIDTH_M,
        base_z=UPPER_BASE_Z_M,
        height=UPPER_HEIGHT_M,
    )

    for index, offset in enumerate([1.5, 8.0, 22.0, 29.0], start=1):
        author.create_window(
            name=f"Retail South Window {index}",
            storey_name="Ground Floor",
            wall_name="Ground Retail South Wall",
            offset_along_wall=offset,
            sill_height=0.65,
            width=5.0,
            height=3.6,
            thickness=0.18,
            **_metadata(
                _semantics("openings", subrole="storefront_window", system_name="Ground Retail Frontage", group_path=["Ground Floor", "South Frontage", "Storefront Bays"]),
                _presentation(
                    material_key="glass",
                    window_type="storefront",
                    frame_style="painted_steel",
                    glazing_style="clear",
                    glass_material_key="glass",
                    frame_material_key="steel_dark",
                    is_storefront=True,
                ),
            ),
        )
    for index, offset in enumerate([8.0, 19.8], start=1):
        author.create_window(
            name=f"Retail East Window {index}",
            storey_name="Ground Floor",
            wall_name="Ground Retail East Wall",
            offset_along_wall=offset,
            sill_height=0.90,
            width=3.6,
            height=3.2,
            thickness=0.18,
            **_metadata(
                _semantics("openings", subrole="retail_display_window", system_name="Ground Retail Side Glazing", group_path=["Ground Floor", "Side Facades", "Display Windows"]),
                _presentation(material_key="glass", window_type="storefront", frame_style="painted_steel", glazing_style="clear", glass_material_key="glass", frame_material_key="steel_dark", is_storefront=True),
            ),
        )
        author.create_window(
            name=f"Retail West Window {index}",
            storey_name="Ground Floor",
            wall_name="Ground Retail West Wall",
            offset_along_wall=offset,
            sill_height=0.90,
            width=3.6,
            height=3.2,
            thickness=0.18,
            **_metadata(
                _semantics("openings", subrole="retail_display_window", system_name="Ground Retail Side Glazing", group_path=["Ground Floor", "Side Facades", "Display Windows"]),
                _presentation(material_key="glass", window_type="storefront", frame_style="painted_steel", glazing_style="clear", glass_material_key="glass", frame_material_key="steel_dark", is_storefront=True),
            ),
        )

    author.create_door(
        name="Main Retail Entry",
        storey_name="Ground Floor",
        wall_name="Ground Retail South Wall",
        offset_along_wall=16.7,
        width=2.6,
        height=3.2,
        thickness=0.10,
        **_metadata(
            _semantics("openings", subrole="main_entry_door", system_name="Ground Retail Entries", group_path=["Ground Floor", "Entries", "Primary"]),
            _presentation(material_key="door", frame_material_key="steel_dark"),
        ),
    )
    author.create_door(
        name="Service Entry",
        storey_name="Ground Floor",
        wall_name="Ground Retail North Wall",
        offset_along_wall=3.0,
        width=1.4,
        height=2.4,
        thickness=0.10,
        **_metadata(
            _semantics("openings", subrole="service_door", system_name="Ground Retail Entries", group_path=["Ground Floor", "Entries", "Service"]),
            _presentation(material_key="door", frame_material_key="steel_dark"),
        ),
    )

    for index, offset in enumerate([1.8, 10.4, 19.0], start=1):
        author.create_window(
            name=f"Upper South Window {index}",
            storey_name="Terrace Level",
            wall_name="Upper Volume South Wall",
            offset_along_wall=offset,
            sill_height=1.0,
            width=3.3,
            height=2.1,
            thickness=0.16,
            **_metadata(
                _semantics("openings", subrole="punched_window", system_name="Upper Volume Openings", group_path=["Upper Volume", "South Facade", "Windows"]),
                _presentation(material_key="glass", window_type="punched", frame_style="painted_steel", glazing_style="clear", glass_material_key="glass", frame_material_key="steel_dark"),
            ),
        )
    for index, offset in enumerate([4.2, 12.8], start=1):
        author.create_window(
            name=f"Upper North Window {index}",
            storey_name="Terrace Level",
            wall_name="Upper Volume North Wall",
            offset_along_wall=offset,
            sill_height=1.05,
            width=4.2,
            height=2.0,
            thickness=0.16,
            **_metadata(
                _semantics("openings", subrole="punched_window", system_name="Upper Volume Openings", group_path=["Upper Volume", "North Facade", "Windows"]),
                _presentation(material_key="glass", window_type="punched", frame_style="painted_steel", glazing_style="clear", glass_material_key="glass", frame_material_key="steel_dark"),
            ),
        )
    for index, offset in enumerate([3.0, 11.2], start=1):
        author.create_window(
            name=f"Upper East Window {index}",
            storey_name="Terrace Level",
            wall_name="Upper Volume East Wall",
            offset_along_wall=offset,
            sill_height=1.0,
            width=3.0,
            height=2.0,
            thickness=0.16,
            **_metadata(
                _semantics("openings", subrole="punched_window", system_name="Upper Volume Openings", group_path=["Upper Volume", "Side Facades", "Windows"]),
                _presentation(material_key="glass", window_type="punched", frame_style="painted_steel", glazing_style="clear", glass_material_key="glass", frame_material_key="steel_dark"),
            ),
        )
        author.create_window(
            name=f"Upper West Window {index}",
            storey_name="Terrace Level",
            wall_name="Upper Volume West Wall",
            offset_along_wall=offset,
            sill_height=1.0,
            width=3.0,
            height=2.0,
            thickness=0.16,
            **_metadata(
                _semantics("openings", subrole="punched_window", system_name="Upper Volume Openings", group_path=["Upper Volume", "Side Facades", "Windows"]),
                _presentation(material_key="glass", window_type="punched", frame_style="painted_steel", glazing_style="clear", glass_material_key="glass", frame_material_key="steel_dark"),
            ),
        )

    author.create_door(
        name="Terrace Access Door West",
        storey_name="Terrace Level",
        wall_name="Upper Volume South Wall",
        offset_along_wall=7.2,
        width=1.6,
        height=2.6,
        thickness=0.10,
        **_metadata(
            _semantics("openings", subrole="terrace_access_door", system_name="Terrace Access", group_path=["Terrace", "Access Doors"]),
            _presentation(material_key="door", frame_material_key="steel_dark"),
        ),
    )
    author.create_door(
        name="Terrace Access Door East",
        storey_name="Terrace Level",
        wall_name="Upper Volume South Wall",
        offset_along_wall=15.2,
        width=1.6,
        height=2.6,
        thickness=0.10,
        **_metadata(
            _semantics("openings", subrole="terrace_access_door", system_name="Terrace Access", group_path=["Terrace", "Access Doors"]),
            _presentation(material_key="door", frame_material_key="steel_dark"),
        ),
    )

    _add_corner_columns(
        author,
        prefix="Podium",
        storey="Ground Floor",
        x=0.0,
        y=0.0,
        length=BASE_LENGTH_M,
        width=BASE_WIDTH_M,
        base_z=0.0,
        height=GROUND_HEIGHT_M,
        size=0.35,
    )
    _add_perimeter_frame(
        author,
        prefix="Podium",
        storey="Ground Floor",
        x=0.0,
        y=0.0,
        length=BASE_LENGTH_M,
        width=BASE_WIDTH_M,
        base_z=GROUND_HEIGHT_M - 0.45,
    )
    _add_corner_columns(
        author,
        prefix="Upper Volume",
        storey="Terrace Level",
        x=UPPER_ORIGIN_X_M,
        y=UPPER_ORIGIN_Y_M,
        length=UPPER_LENGTH_M,
        width=UPPER_WIDTH_M,
        base_z=UPPER_BASE_Z_M,
        height=UPPER_HEIGHT_M,
        size=0.30,
    )
    _add_perimeter_frame(
        author,
        prefix="Upper Volume",
        storey="Terrace Level",
        x=UPPER_ORIGIN_X_M,
        y=UPPER_ORIGIN_Y_M,
        length=UPPER_LENGTH_M,
        width=UPPER_WIDTH_M,
        base_z=UPPER_ROOF_Z_M - 0.45,
    )

    author.create_panel(
        name="South Entry Canopy",
        storey_name="Ground Floor",
        x=12.5,
        y=-2.2,
        base_z=4.45,
        width=11.0,
        height=None,
        depth=2.2,
        thickness=CANOPY_THICKNESS_M,
        orientation="horizontal",
        rotation_deg=0.0,
        **_metadata(
            _semantics("cladding", subrole="entry_canopy", system_name="South Entry Canopy", group_path=["Ground Floor", "Entry Canopy"]),
            _presentation(material_key="accent", presentation_style="accent"),
        ),
    )
    for index, x_value in enumerate([13.2, 22.6], start=1):
        author.create_column(
            name=f"Canopy Steel Post {index}",
            storey_name="Ground Floor",
            x=x_value,
            y=-1.95,
            base_z=0.0,
            width=0.16,
            depth=0.16,
            height=4.45,
            **_metadata(
                _semantics("structure", subrole="canopy_post", system_name="South Entry Canopy", group_path=["Ground Floor", "Entry Canopy", "Posts"], is_exposed=True, view_mode="structure"),
                _presentation(material_key="steel", presentation_style="exposed_steel"),
            ),
        )

    for name, x_value, y_value, width, rotation in [
        ("South Upper Accent Panel West", 9.0, UPPER_ORIGIN_Y_M - 0.10, 4.0, 0.0),
        ("South Upper Accent Panel East", 19.0, UPPER_ORIGIN_Y_M - 0.10, 4.0, 0.0),
        ("North Upper Cladding Panel West", UPPER_ORIGIN_X_M + UPPER_LENGTH_M, UPPER_ORIGIN_Y_M + UPPER_WIDTH_M + 0.10, 5.0, 180.0),
        ("North Upper Cladding Panel East", UPPER_ORIGIN_X_M + 7.0, UPPER_ORIGIN_Y_M + UPPER_WIDTH_M + 0.10, 5.0, 0.0),
        ("East Upper Accent Panel", UPPER_ORIGIN_X_M + UPPER_LENGTH_M + 0.10, 9.2, 4.0, 90.0),
        ("West Upper Accent Panel", UPPER_ORIGIN_X_M - 0.10, 18.4, 4.0, -90.0),
    ]:
        author.create_panel(
            name=name,
            storey_name="Terrace Level",
            x=x_value,
            y=y_value,
            base_z=UPPER_BASE_Z_M,
            width=width,
            height=UPPER_HEIGHT_M,
            depth=None,
            thickness=CLADDING_THICKNESS_M,
            orientation="vertical",
            rotation_deg=rotation,
            **_metadata(
                _semantics(
                    "cladding",
                    subrole="accent_panel" if "Accent" in name else "cladding_panel",
                    system_name="Upper Volume Cladding",
                    group_path=["Upper Volume", "Feature Panels"],
                ),
                _presentation(
                    material_key="accent" if "Accent" in name else "cladding",
                    presentation_style="accent" if "Accent" in name else "cladding",
                ),
            ),
        )

    railing_member_count = _add_terrace_railing(author, storey="Terrace Level")

    for index, (x_value, y_value, load_kn, support_for) in enumerate(
        [
            (0.675, 0.675, 920.0, "Podium Steel Column 1"),
            (BASE_LENGTH_M - 0.675, 0.675, 920.0, "Podium Steel Column 2"),
            (BASE_LENGTH_M - 0.675, BASE_WIDTH_M - 0.675, 920.0, "Podium Steel Column 3"),
            (0.675, BASE_WIDTH_M - 0.675, 920.0, "Podium Steel Column 4"),
            (13.28, -1.87, 180.0, "Canopy Steel Post 1"),
            (22.68, -1.87, 180.0, "Canopy Steel Post 2"),
        ],
        start=1,
    ):
        _add_spread_footing(
            author,
            name=f"Spread Footing {index}",
            x=x_value,
            y=y_value,
            imposed_load_kn=load_kn,
            support_for=support_for,
            group_path=["Substructure", "Spread Footings", support_for],
        )

    author.save()

    summary = json.loads(author.debug_dump())
    report = {
        "output_ifc": str(output_path),
        "design_summary": {
            "base_length_m": BASE_LENGTH_M,
            "base_width_m": BASE_WIDTH_M,
            "base_area_sqft": round(BASE_AREA_SQFT, 1),
            "upper_length_m": UPPER_LENGTH_M,
            "upper_width_m": UPPER_WIDTH_M,
            "ground_height_m": GROUND_HEIGHT_M,
            "upper_height_m": UPPER_HEIGHT_M,
            "terrace_walkway_created": True,
            "railing_members_modeled": railing_member_count,
        },
        "entity_counts": summary,
        "known_limitations": [
            "The repo does not currently author a native IfcRailing element, so the terrace guardrail is modeled with steel IfcColumn posts and IfcBeam rails.",
            "Material styling and facade color are not embedded as presentation styles in the IFC authoring flow, so the concept colorway is applied in Blender review renders.",
            "The prompt-driven CLI path was not used because OPENAI_API_KEY, ANTHROPIC_API_KEY, and GEMINI_API_KEY are unset in this environment.",
        ],
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Target IFC path.")
    parser.add_argument("--report", help="Optional JSON report output path.")
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report).resolve() if args.report else None
    report = build_concept(output_path=output_path, report_path=report_path)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
