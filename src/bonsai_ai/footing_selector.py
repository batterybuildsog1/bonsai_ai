from __future__ import annotations

import math
from typing import Any, Dict

from .contracts import DesignPackage

NEWTON_TO_LBF = 0.22480894387096
LBF_TO_KN = 0.0044482216152605
FT_TO_M = 0.3048
PSF_TO_KPA = 0.04788025898

REBAR_WEIGHT_LB_PER_FT = {
    "#5": 1.043,
    "#6": 1.502,
    "#7": 2.044,
}

REBAR_DIAMETER_MM = {
    "#5": 15.9,
    "#6": 19.1,
    "#7": 22.2,
}


def _starter_reinforcement(service_vertical_lbf: float, square_size_ft: float) -> Dict[str, Any]:
    if service_vertical_lbf <= 80000.0:
        concrete_strength_mpa = 28.0
        rebar_grade_mpa = 420.0
        rebar_grade = "ASTM A615 Grade 60"
        bar_mark = "#5"
        spacing_in = 12.0
        thickness_in = 18.0
    elif service_vertical_lbf <= 150000.0:
        concrete_strength_mpa = 35.0
        rebar_grade_mpa = 420.0
        rebar_grade = "ASTM A615 Grade 60"
        bar_mark = "#6"
        spacing_in = 10.0
        thickness_in = 22.0
    else:
        concrete_strength_mpa = 41.0
        rebar_grade_mpa = 520.0
        rebar_grade = "ASTM A706 Grade 75"
        bar_mark = "#7"
        spacing_in = 9.0
        thickness_in = 28.0

    clear_cover_in = 3.0
    clear_span_in = max((square_size_ft * 12.0) - (2.0 * clear_cover_in), 12.0)
    bars_each_way = max(2, math.ceil(clear_span_in / spacing_in) + 1)
    bar_length_ft = max(square_size_ft - ((2.0 * clear_cover_in) / 12.0), 1.0)
    total_length_ft = bars_each_way * 2.0 * bar_length_ft
    rebar_weight_lb = total_length_ft * REBAR_WEIGHT_LB_PER_FT[bar_mark]
    return {
        "footing_thickness_m": round(thickness_in * 0.0254, 3),
        "concrete_strength_mpa": concrete_strength_mpa,
        "rebar_yield_strength_mpa": rebar_grade_mpa,
        "rebar_grade": rebar_grade,
        "rebar_bar_diameter_mm": REBAR_DIAMETER_MM[bar_mark],
        "rebar_spacing_mm": round(spacing_in * 25.4, 1),
        "rebar_layer_count": 1 if service_vertical_lbf <= 150000.0 else 2,
        "rebar_schedule": [f"Bottom mat {bar_mark} @ {int(spacing_in)} in each way"],
        "rebar_weight_kg": round(rebar_weight_lb * 0.45359237, 1),
    }


def starter_footing_from_imposed_load(
    imposed_load_kn: float,
    *,
    footing_family: str = "interior_spread_footing",
    allowable_bearing_psf: float = 2000.0,
    eccentricity_x_m: float = 0.0,
    eccentricity_y_m: float = 0.0,
    basis_note: str | None = None,
) -> Dict[str, Any]:
    service_vertical_lbf = max(float(imposed_load_kn), 1.0) / LBF_TO_KN
    required_area_ft2 = service_vertical_lbf / allowable_bearing_psf if allowable_bearing_psf else 0.0
    kern_min_size_ft = max((6.0 * abs(float(eccentricity_x_m))) / FT_TO_M, (6.0 * abs(float(eccentricity_y_m))) / FT_TO_M, 0.0)
    square_size_ft = math.ceil(max(math.sqrt(max(required_area_ft2, 1.0)), kern_min_size_ft, 1.0) * 2.0) / 2.0
    reinforcement = _starter_reinforcement(service_vertical_lbf, square_size_ft)
    return {
        "family": footing_family,
        "imposed_load_kn": round(float(imposed_load_kn), 2),
        "required_area_ft2": round(required_area_ft2, 2),
        "recommended_square_size_ft": square_size_ft,
        "recommended_square_size_m": round(square_size_ft * FT_TO_M, 3),
        "eccentricity_x_m": round(float(eccentricity_x_m), 4),
        "eccentricity_y_m": round(float(eccentricity_y_m), 4),
        "required_square_size_for_kern_ft": round(kern_min_size_ft, 2),
        "allowable_bearing_psf": allowable_bearing_psf,
        "allowable_bearing_kpa": round(allowable_bearing_psf * PSF_TO_KPA, 2),
        **reinforcement,
        "basis_notes": basis_note
        or "Starter footing sizing from imposed load using concept-level allowable bearing and middle-third eccentricity checks until geotechnical-specific design is available.",
    }


def build_starter_footing_summary(package: DesignPackage) -> Dict[str, Any]:
    if not package.analysis_result or not package.structural_source_model:
        return {"status": "not_available"}

    support_reactions = dict((package.analysis_result.summary or {}).get("support_target_reactions") or {})
    if not support_reactions:
        return {"status": "not_available"}

    combo_name, combo_reactions = max(
        support_reactions.items(),
        key=lambda item: max((abs(float(reaction.get("fz") or 0.0)) for reaction in item[1].values()), default=0.0),
    )
    columns = [element for element in package.structural_source_model.elements if element.kind == "column"]
    if not columns:
        return {"status": "not_available"}

    min_x = min(float(element.geometry["origin"][0]) for element in columns)
    max_x = max(float(element.geometry["origin"][0]) for element in columns)
    min_y = min(float(element.geometry["origin"][1]) for element in columns)
    max_y = max(float(element.geometry["origin"][1]) for element in columns)
    tolerance = 1e-6

    footings = []
    total_area_ft2 = 0.0
    for element in columns:
        reaction = combo_reactions.get(element.id)
        if not reaction:
            continue
        x = float(element.geometry["origin"][0])
        y = float(element.geometry["origin"][1])
        on_perimeter = (
            math.isclose(x, min_x, abs_tol=tolerance)
            or math.isclose(x, max_x, abs_tol=tolerance)
            or math.isclose(y, min_y, abs_tol=tolerance)
            or math.isclose(y, max_y, abs_tol=tolerance)
        )
        footing_family = "perimeter_spread_footing" if on_perimeter else "interior_spread_footing"
        allowable_bearing_psf = 2000.0
        service_vertical_lbf = abs(float(reaction.get("fz") or 0.0)) * NEWTON_TO_LBF
        required_area_ft2 = service_vertical_lbf / allowable_bearing_psf if allowable_bearing_psf else 0.0
        moment_x_nm = abs(float(reaction.get("mx") or 0.0))
        moment_y_nm = abs(float(reaction.get("my") or 0.0))
        imposed_load_kn = round(service_vertical_lbf * LBF_TO_KN, 2)
        eccentricity_x_m = moment_y_nm / max(imposed_load_kn * 1000.0, 1.0)
        eccentricity_y_m = moment_x_nm / max(imposed_load_kn * 1000.0, 1.0)
        kern_min_size_ft = max((6.0 * eccentricity_x_m) / FT_TO_M, (6.0 * eccentricity_y_m) / FT_TO_M, 0.0)
        square_size_ft = math.ceil(max(math.sqrt(max(required_area_ft2, 1.0)), kern_min_size_ft, 1.0) * 2.0) / 2.0
        reinforcement = _starter_reinforcement(service_vertical_lbf, square_size_ft)
        footing = {
            "target_id": element.id,
            "family": footing_family,
            "combo": combo_name,
            "service_vertical_lbf_proxy": round(service_vertical_lbf, 2),
            "imposed_load_kn": imposed_load_kn,
            "moment_x_nm": round(moment_x_nm, 2),
            "moment_y_nm": round(moment_y_nm, 2),
            "eccentricity_x_m": round(eccentricity_x_m, 4),
            "eccentricity_y_m": round(eccentricity_y_m, 4),
            "required_area_ft2": round(required_area_ft2, 2),
            "recommended_square_size_ft": square_size_ft,
            "recommended_square_size_m": round(square_size_ft * FT_TO_M, 3),
            "required_square_size_for_kern_ft": round(kern_min_size_ft, 2),
            "allowable_bearing_psf": allowable_bearing_psf,
            "allowable_bearing_kpa": round(allowable_bearing_psf * PSF_TO_KPA, 2),
            **reinforcement,
            "basis_note": "Conservative starter sizing from solved support reactions using 2,000 psf allowable bearing and middle-third eccentricity checks until geotech-specific footing design is wired in.",
        }
        footings.append(footing)
        total_area_ft2 += square_size_ft * square_size_ft

    return {
        "status": "completed",
        "governing_combo": combo_name,
        "footing_count": len(footings),
        "total_recommended_plan_area_ft2": round(total_area_ft2, 2),
        "footings": footings,
    }
