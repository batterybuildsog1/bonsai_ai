"""Cost estimation from IFC models.

Extracts material quantities from a Bonsai AI IFC model (via Pset_BonsaiAI
properties) and prices them against a unit cost database to produce a
concept-level cost report.

Usage:
    python3 -m bonsai_ai.cost_estimator out/spec_steel/building.ifc
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

import ifcopenshell
import ifcopenshell.util.element

from .cost_database import COST_DB, M2_TO_SF
from .section_library import starter_section_records, LB_PER_FT_TO_N_PER_M

# Gravity: 1 N/m = 1 / 9.80665 kg/m
GRAVITY = 9.80665


# ---------------------------------------------------------------------------
# Quantity extraction
# ---------------------------------------------------------------------------

def _get_pset(element) -> Dict[str, Any]:
    """Read Pset_BonsaiAI from an IFC element."""
    raw = ifcopenshell.util.element.get_psets(
        element, psets_only=True, should_inherit=False,
    ).get("Pset_BonsaiAI", {})
    parsed: Dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, str) and value[:1] in {"{", "["}:
            try:
                parsed[key] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        parsed[key] = value
    return parsed


def _section_weight_kg_per_m(section_name: str) -> Optional[float]:
    """Look up weight in kg/m for a named AISC section.

    The section library stores weight_n_per_m (Newtons per meter).
    Convert to kg/m by dividing by gravity (9.80665).
    """
    if not section_name:
        return None
    catalog = starter_section_records()
    record = catalog.get(section_name.upper().replace(" ", ""))
    if record is None:
        return None
    return record.weight_n_per_m / GRAVITY


def extract_quantities(ifc_path: str) -> Dict[str, Any]:
    """Extract material quantities from an IFC model.

    Reads Pset_BonsaiAI properties from each element to determine
    dimensions, section names, and structural roles.

    Returns a dict with categorized quantities suitable for cost pricing.
    """
    model = ifcopenshell.open(ifc_path)

    quantities: Dict[str, Any] = {
        "steel_columns": {
            "count": 0,
            "total_weight_kg": 0.0,
            "total_length_m": 0.0,
            "sections": {},  # section_name -> {count, weight_kg, length_m}
        },
        "steel_beams": {
            "count": 0,
            "total_weight_kg": 0.0,
            "total_length_m": 0.0,
            "sections": {},
        },
        "concrete_slabs": {
            "count": 0,
            "total_volume_m3": 0.0,
            "total_area_m2": 0.0,
        },
        "walls": {
            "count": 0,
            "total_area_m2": 0.0,
        },
        "curtain_walls": {
            "count": 0,
            "total_area_m2": 0.0,
        },
        "windows": {"count": 0},
        "doors": {"count": 0},
        "footings": {
            "count": 0,
            "total_volume_m3": 0.0,
            "total_rebar_kg": 0.0,
        },
        "connections": 0,
        "gross_floor_area_m2": 0.0,
        "num_stories": 0,
    }

    # --- Storeys (for gross floor area) ---
    storeys = model.by_type("IfcBuildingStorey")
    quantities["num_stories"] = len(storeys)

    # --- Columns ---
    for col in model.by_type("IfcColumn"):
        pset = _get_pset(col)
        section_name = pset.get("SectionName") or pset.get("SectionRef") or ""
        height = float(pset.get("Height", 0))
        profile_type = pset.get("ProfileType", "rectangular")

        if profile_type == "I" and section_name:
            # Steel I-beam column
            weight_per_m = _section_weight_kg_per_m(section_name)
            if weight_per_m and height > 0:
                member_weight = weight_per_m * height
                quantities["steel_columns"]["count"] += 1
                quantities["steel_columns"]["total_weight_kg"] += member_weight
                quantities["steel_columns"]["total_length_m"] += height

                sec = quantities["steel_columns"]["sections"].setdefault(
                    section_name, {"count": 0, "weight_kg": 0.0, "length_m": 0.0},
                )
                sec["count"] += 1
                sec["weight_kg"] += member_weight
                sec["length_m"] += height

    # --- Beams ---
    for beam in model.by_type("IfcBeam"):
        pset = _get_pset(beam)
        section_name = pset.get("SectionName") or pset.get("SectionRef") or ""
        length = float(pset.get("Length", 0))
        profile_type = pset.get("ProfileType", "rectangular")

        if profile_type == "I" and section_name:
            weight_per_m = _section_weight_kg_per_m(section_name)
            if weight_per_m and length > 0:
                member_weight = weight_per_m * length
                quantities["steel_beams"]["count"] += 1
                quantities["steel_beams"]["total_weight_kg"] += member_weight
                quantities["steel_beams"]["total_length_m"] += length

                sec = quantities["steel_beams"]["sections"].setdefault(
                    section_name, {"count": 0, "weight_kg": 0.0, "length_m": 0.0},
                )
                sec["count"] += 1
                sec["weight_kg"] += member_weight
                sec["length_m"] += length

    # --- Slabs ---
    for slab in model.by_type("IfcSlab"):
        pset = _get_pset(slab)
        length = float(pset.get("Length", 0))
        width = float(pset.get("Width", 0))
        thickness = float(pset.get("Thickness", 0))

        if length > 0 and width > 0 and thickness > 0:
            area = length * width
            volume = area * thickness
            quantities["concrete_slabs"]["count"] += 1
            quantities["concrete_slabs"]["total_volume_m3"] += volume
            quantities["concrete_slabs"]["total_area_m2"] += area

    # --- Walls ---
    for wall in model.by_type("IfcWall"):
        pset = _get_pset(wall)
        sx = float(pset.get("StartX", 0))
        sy = float(pset.get("StartY", 0))
        ex = float(pset.get("EndX", 0))
        ey = float(pset.get("EndY", 0))
        height = float(pset.get("Height", 0))

        wall_length = math.hypot(ex - sx, ey - sy)
        if wall_length > 0 and height > 0:
            area = wall_length * height
            quantities["walls"]["count"] += 1
            quantities["walls"]["total_area_m2"] += area

    # --- Curtain Walls ---
    for cw in model.by_type("IfcCurtainWall"):
        pset = _get_pset(cw)
        width = float(pset.get("Width", 0))
        height = float(pset.get("Height", 0))

        if width > 0 and height > 0:
            area = width * height
            quantities["curtain_walls"]["count"] += 1
            quantities["curtain_walls"]["total_area_m2"] += area

    # --- Windows ---
    quantities["windows"]["count"] = len(model.by_type("IfcWindow"))

    # --- Doors ---
    quantities["doors"]["count"] = len(model.by_type("IfcDoor"))

    # --- Footings ---
    for footing in model.by_type("IfcFooting"):
        pset = _get_pset(footing)
        length = float(pset.get("Length", 0))
        width = float(pset.get("Width", 0))
        thickness = float(pset.get("Thickness", 0))

        if length > 0 and width > 0 and thickness > 0:
            volume = length * width * thickness
            quantities["footings"]["count"] += 1
            quantities["footings"]["total_volume_m3"] += volume

            # Rebar weight from footing pset
            rebar_kg = pset.get("RebarWeightKg") or pset.get("TotalRebarWeightKg")
            if rebar_kg:
                quantities["footings"]["total_rebar_kg"] += float(rebar_kg)

    # --- Connections (heuristic: each beam end connects to a column/beam) ---
    # Approximate: 2 connections per beam (each end)
    total_beams = quantities["steel_beams"]["count"]
    quantities["connections"] = total_beams * 2

    # --- Gross floor area ---
    # Use slab area (excludes roof slab, which is the last one)
    # Actually: all slabs contribute to floor area for cost purposes (including roof)
    # but for $/SF, we want the usable floor area = slab area - roof
    slab_count = quantities["concrete_slabs"]["count"]
    if slab_count > 0 and quantities["concrete_slabs"]["total_area_m2"] > 0:
        # Each slab has the same area (footprint); gross area = num_stories * footprint
        single_slab_area = quantities["concrete_slabs"]["total_area_m2"] / slab_count
        num_stories = quantities["num_stories"]
        quantities["gross_floor_area_m2"] = single_slab_area * num_stories

    return quantities


# ---------------------------------------------------------------------------
# Cost report generation
# ---------------------------------------------------------------------------

def generate_cost_report(
    quantities: Dict[str, Any],
    cost_db: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Generate a cost estimate from extracted quantities.

    Returns a dict with line_items, subtotal, contingency, total, and
    per-area metrics.
    """
    if cost_db is None:
        cost_db = COST_DB

    line_items: List[Dict[str, Any]] = []

    # --- Steel columns ---
    steel_col = quantities["steel_columns"]
    if steel_col["total_weight_kg"] > 0:
        cost = steel_col["total_weight_kg"] * cost_db["steel_per_kg"]
        detail = ""
        for sec_name, sec_data in sorted(steel_col["sections"].items()):
            detail += f" {sec_name}: {sec_data['count']} members"
        line_items.append({
            "category": "Structure",
            "item": f"Steel columns ({steel_col['count']}){detail}",
            "quantity": f"{steel_col['total_weight_kg']:.0f} kg",
            "unit_cost": f"${cost_db['steel_per_kg']:.2f}/kg",
            "total": cost,
        })

    # --- Steel beams ---
    steel_beam = quantities["steel_beams"]
    if steel_beam["total_weight_kg"] > 0:
        cost = steel_beam["total_weight_kg"] * cost_db["steel_per_kg"]
        detail = ""
        for sec_name, sec_data in sorted(steel_beam["sections"].items()):
            detail += f" {sec_name}: {sec_data['count']} members"
        line_items.append({
            "category": "Structure",
            "item": f"Steel beams ({steel_beam['count']}){detail}",
            "quantity": f"{steel_beam['total_weight_kg']:.0f} kg",
            "unit_cost": f"${cost_db['steel_per_kg']:.2f}/kg",
            "total": cost,
        })

    # --- Steel connections ---
    connections = quantities.get("connections", 0)
    if connections > 0:
        cost = connections * cost_db["steel_connection_per_joint"]
        line_items.append({
            "category": "Structure",
            "item": f"Steel connections ({connections} joints)",
            "quantity": f"{connections} ea",
            "unit_cost": f"${cost_db['steel_connection_per_joint']:.0f}/joint",
            "total": cost,
        })

    # --- Concrete slabs ---
    slabs = quantities["concrete_slabs"]
    if slabs["total_volume_m3"] > 0:
        cost = slabs["total_volume_m3"] * cost_db["concrete_per_m3"]
        line_items.append({
            "category": "Structure",
            "item": f"Concrete slabs ({slabs['count']})",
            "quantity": f"{slabs['total_volume_m3']:.1f} m\u00b3",
            "unit_cost": f"${cost_db['concrete_per_m3']:.0f}/m\u00b3",
            "total": cost,
        })

    # --- Footings ---
    footings = quantities["footings"]
    if footings["total_volume_m3"] > 0:
        cost = footings["total_volume_m3"] * cost_db["footing_per_m3"]
        line_items.append({
            "category": "Foundation",
            "item": f"Spread footings ({footings['count']})",
            "quantity": f"{footings['total_volume_m3']:.1f} m\u00b3",
            "unit_cost": f"${cost_db['footing_per_m3']:.0f}/m\u00b3",
            "total": cost,
        })

    # --- Footing rebar ---
    if footings["total_rebar_kg"] > 0:
        cost = footings["total_rebar_kg"] * cost_db["rebar_per_kg"]
        line_items.append({
            "category": "Foundation",
            "item": f"Footing rebar",
            "quantity": f"{footings['total_rebar_kg']:.0f} kg",
            "unit_cost": f"${cost_db['rebar_per_kg']:.2f}/kg",
            "total": cost,
        })

    # --- Walls ---
    walls = quantities["walls"]
    if walls["total_area_m2"] > 0:
        cost = walls["total_area_m2"] * cost_db["concrete_wall_per_m2"]
        line_items.append({
            "category": "Envelope",
            "item": f"Concrete/insulated walls ({walls['count']})",
            "quantity": f"{walls['total_area_m2']:.0f} m\u00b2",
            "unit_cost": f"${cost_db['concrete_wall_per_m2']:.0f}/m\u00b2",
            "total": cost,
        })

    # --- Curtain walls ---
    curtain = quantities["curtain_walls"]
    if curtain["total_area_m2"] > 0:
        cost = curtain["total_area_m2"] * cost_db["curtain_wall_per_m2"]
        line_items.append({
            "category": "Envelope",
            "item": f"Curtain wall ({curtain['count']})",
            "quantity": f"{curtain['total_area_m2']:.0f} m\u00b2",
            "unit_cost": f"${cost_db['curtain_wall_per_m2']:.0f}/m\u00b2",
            "total": cost,
        })

    # --- Windows ---
    win_count = quantities["windows"]["count"]
    if win_count > 0:
        cost = win_count * cost_db["window_each"]
        line_items.append({
            "category": "Envelope",
            "item": f"Windows ({win_count})",
            "quantity": f"{win_count} ea",
            "unit_cost": f"${cost_db['window_each']:.0f}/ea",
            "total": cost,
        })

    # --- Doors ---
    door_count = quantities["doors"]["count"]
    if door_count > 0:
        cost = door_count * cost_db["door_single"]
        line_items.append({
            "category": "Envelope",
            "item": f"Doors ({door_count})",
            "quantity": f"{door_count} ea",
            "unit_cost": f"${cost_db['door_single']:.0f}/ea",
            "total": cost,
        })

    # --- Roof (use footprint area for metal roof) ---
    # Roof area = one slab area (the building footprint)
    if slabs["count"] > 0:
        roof_area_m2 = slabs["total_area_m2"] / slabs["count"]
        cost = roof_area_m2 * cost_db["metal_roof_per_m2"]
        line_items.append({
            "category": "Roof",
            "item": "Metal roof (standing seam)",
            "quantity": f"{roof_area_m2:.0f} m\u00b2",
            "unit_cost": f"${cost_db['metal_roof_per_m2']:.0f}/m\u00b2",
            "total": cost,
        })

    # --- Totals ---
    subtotal = sum(item["total"] for item in line_items)
    contingency = subtotal * cost_db["contingency_pct"]
    total = subtotal + contingency

    gross_area_m2 = quantities.get("gross_floor_area_m2", 0)
    gross_area_sf = gross_area_m2 * M2_TO_SF
    cost_per_m2 = total / max(gross_area_m2, 1)
    cost_per_sf = total / max(gross_area_sf, 1)

    return {
        "line_items": line_items,
        "subtotal": subtotal,
        "contingency": contingency,
        "contingency_pct": cost_db["contingency_pct"],
        "total": total,
        "gross_floor_area_m2": gross_area_m2,
        "gross_floor_area_sf": gross_area_sf,
        "cost_per_m2": cost_per_m2,
        "cost_per_sf": cost_per_sf,
    }


# ---------------------------------------------------------------------------
# Formatted text report
# ---------------------------------------------------------------------------

def format_cost_report(report: Dict[str, Any]) -> str:
    """Format a cost report dict as human-readable text."""
    lines: List[str] = []
    lines.append("")
    lines.append("Building Cost Estimate")
    lines.append("=" * 72)

    # Group line items by category
    categories: Dict[str, List[Dict[str, Any]]] = {}
    for item in report["line_items"]:
        cat = item["category"]
        categories.setdefault(cat, []).append(item)

    for cat_name, items in categories.items():
        lines.append(f"\n  {cat_name}:")
        for item in items:
            qty = item["quantity"]
            unit = item["unit_cost"]
            total = item["total"]
            lines.append(f"    {item['item']}")
            lines.append(f"      {qty} @ {unit} = ${total:,.0f}")

    lines.append("")
    lines.append("-" * 72)
    lines.append(f"  Subtotal:                             ${report['subtotal']:>14,.0f}")
    pct = report["contingency_pct"]
    lines.append(f"  Contingency ({pct:.0%}):                    ${report['contingency']:>14,.0f}")
    lines.append("=" * 72)
    lines.append(f"  TOTAL:                                ${report['total']:>14,.0f}")
    lines.append("")

    if report["gross_floor_area_m2"] > 0:
        lines.append(f"  Gross floor area:  {report['gross_floor_area_m2']:,.0f} m\u00b2  "
                      f"({report['gross_floor_area_sf']:,.0f} SF)")
        lines.append(f"  Cost per m\u00b2:       ${report['cost_per_m2']:,.2f}/m\u00b2")
        lines.append(f"  Cost per SF:       ${report['cost_per_sf']:,.2f}/SF")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a cost estimate from a Bonsai AI IFC model.",
    )
    parser.add_argument(
        "ifc_path",
        help="Path to the IFC file to estimate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text.",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        help="Write report to a file (default: stdout).",
    )

    args = parser.parse_args(argv)

    if not os.path.exists(args.ifc_path):
        print(f"Error: IFC file not found: {args.ifc_path}", file=sys.stderr)
        return 1

    # Extract and price
    quantities = extract_quantities(args.ifc_path)
    report = generate_cost_report(quantities)

    # Add quantities to JSON output for transparency
    report_with_quantities = {
        "quantities": quantities,
        **report,
    }

    if args.json:
        output = json.dumps(report_with_quantities, indent=2)
    else:
        output = format_cost_report(report)

    if args.output:
        output_dir = os.path.dirname(os.path.abspath(args.output))
        os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        # Always write the JSON alongside for programmatic access
        json_path = os.path.splitext(args.output)[0] + ".json"
        with open(json_path, "w") as f:
            json.dump(report_with_quantities, f, indent=2)
        print(f"Cost report written to {args.output}")
        print(f"JSON data written to {json_path}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
