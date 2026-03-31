from __future__ import annotations

from typing import Any, Dict


def starter_core_shell_catalog() -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "catalog_id": "starter_core_shell_v1",
        "design_intent": {
            "target_use": "Core and shell multistory commercial buildings with steel superstructure, panelized facade, and footing design.",
            "default_primary_system": "w_shape_frame_with_hss_braces",
            "default_secondary_wall_system": "cold_formed_c_girts_with_hss_posts",
            "default_secondary_roof_system": "cold_formed_z_purlins",
            "default_foundation_system": "spread_footings_plus_perimeter_retaining_footings",
            "selection_strategy": "Choose from approved family catalogs first; do not invent one-off members unless explicitly allowed.",
        },
        "source_strategy": {
            "strength_and_section_properties": {
                "status": "reliable_online",
                "approach": "Use official shape/property sources and manufacturer section-property manuals as the system of record.",
            },
            "pricing": {
                "status": "seed_plus_override",
                "approach": "Use public online pricing only as seed/default values and allow vendor/project overrides for production estimates.",
            },
        },
        "materials": {
            "steel_w_shapes": {"spec": "ASTM A992", "fy_ksi": 50, "fu_ksi": 65},
            "steel_hss": {"spec": "ASTM A500 Grade C", "fy_ksi": 50, "fu_ksi": 62},
            "cold_formed_secondary": {"spec": "Manufacturer catalog basis", "note": "Confirm coating, gauge, and section properties from approved manufacturer tables."},
            "panel_concrete": {"spec": "Project/report basis", "note": "Panel engineering remains report- and manufacturer-based."},
        },
        "panel_catalogs": [
            {
                "id": "innovacast_icp_wall_panel",
                "family": "panel_system",
                "usage": ["facade_panel", "roof_cap_panel"],
                "defaults": {"orientation": "vertical", "joint_gap_in": 1.5},
                "size_rules": {
                    "max_height_ft": 50.0,
                    "max_width_ft": 12.0,
                    "width_increment_in": 6,
                    "height_increment_ft": 2,
                    "min_width_ft": 6.0,
                    "min_height_ft": 8.0,
                },
            }
        ],
        "member_families": [
            {
                "id": "primary_columns_w",
                "family": "primary_frame",
                "usage": ["primary_column"],
                "shape_family": "W",
                "material": "steel_w_shapes",
                "allowed_sections": ["W10x33", "W10x49", "W12x40", "W12x53", "W14x68", "W14x90", "W16x77", "W18x86"],
                "pricing_mode": "public_seed_plus_vendor_override",
            },
            {
                "id": "primary_columns_hss",
                "family": "primary_frame",
                "usage": ["alternate_primary_column", "facade_column"],
                "shape_family": "HSS",
                "material": "steel_hss",
                "allowed_sections": ["HSS6x6x3/8", "HSS8x8x3/8", "HSS10x10x1/2", "HSS12x12x1/2"],
                "pricing_mode": "public_seed_plus_vendor_override",
            },
            {
                "id": "primary_beams_w",
                "family": "primary_frame",
                "usage": ["primary_beam", "primary_girder", "spandrel_beam"],
                "shape_family": "W",
                "material": "steel_w_shapes",
                "allowed_sections": ["W12x26", "W12x35", "W14x30", "W16x31", "W18x35", "W21x44", "W24x55", "W27x84"],
                "pricing_mode": "public_seed_plus_vendor_override",
            },
            {
                "id": "brace_hss",
                "family": "primary_frame",
                "usage": ["brace", "braced_frame_member"],
                "shape_family": "HSS",
                "material": "steel_hss",
                "allowed_sections": ["HSS4x4x1/4", "HSS6x6x1/4", "HSS6x6x3/8", "HSS8x8x3/8"],
                "pricing_mode": "public_seed_plus_vendor_override",
            },
            {
                "id": "brace_rod",
                "family": "primary_frame",
                "usage": ["alternate_brace", "rod_brace"],
                "shape_family": "ROD",
                "material": "steel_hss",
                "allowed_sections": ['ROD1"', 'ROD1-1/4"', 'ROD1-1/2"'],
                "pricing_mode": "vendor_override_preferred",
            },
            {
                "id": "facade_posts_hss",
                "family": "facade_support",
                "usage": ["facade_post", "panel_support_post"],
                "shape_family": "HSS",
                "material": "steel_hss",
                "allowed_sections": ["HSS4x4x1/4", "HSS6x6x1/4", "HSS8x8x3/8", "HSS10x10x1/2"],
                "pricing_mode": "public_seed_plus_vendor_override",
            },
            {
                "id": "wall_girts_c",
                "family": "facade_support",
                "usage": ["wall_girt", "facade_secondary"],
                "shape_family": "C",
                "material": "cold_formed_secondary",
                "allowed_sections": ["C8-12ga", "C8-10ga", "C10-12ga", "C10-10ga", "C12-12ga", "C12-10ga", "C14-10ga"],
                "pricing_mode": "manufacturer_seed_plus_vendor_override",
            },
            {
                "id": "roof_purlins_z",
                "family": "facade_support",
                "usage": ["roof_purlin", "roof_secondary"],
                "shape_family": "Z",
                "material": "cold_formed_secondary",
                "allowed_sections": ["Z8-12ga", "Z8-10ga", "Z10-12ga", "Z10-10ga", "Z12-12ga", "Z12-10ga", "Z14-10ga"],
                "pricing_mode": "manufacturer_seed_plus_vendor_override",
            },
            {
                "id": "roof_purlins_c",
                "family": "facade_support",
                "usage": ["alternate_roof_purlin"],
                "shape_family": "C",
                "material": "cold_formed_secondary",
                "allowed_sections": ["C8-12ga", "C10-12ga", "C12-12ga", "C12-10ga", "C14-10ga"],
                "pricing_mode": "manufacturer_seed_plus_vendor_override",
            },
            {
                "id": "opening_support_w",
                "family": "opening_support",
                "usage": ["opening_header", "opening_transfer"],
                "shape_family": "W",
                "material": "steel_w_shapes",
                "allowed_sections": ["W8x18", "W10x22", "W12x26", "W14x30"],
                "pricing_mode": "public_seed_plus_vendor_override",
            },
        ],
        "connection_families": [
            {"id": "simple_shear_tab", "usage": ["beam_to_column", "beam_to_girder"]},
            {"id": "brace_gusset", "usage": ["brace_to_frame"]},
            {"id": "base_plate_anchor", "usage": ["column_to_foundation"]},
            {"id": "secondary_clip", "usage": ["girt_or_purlin_to_primary"]},
            {"id": "panel_support_embed_or_clip", "usage": ["panel_to_support_steel"]},
        ],
        "footing_families": [
            {
                "id": "interior_spread_footing",
                "family": "substructure",
                "usage": ["interior_column_support"],
                "status": "starter_default",
            },
            {
                "id": "perimeter_retaining_footing",
                "family": "substructure",
                "usage": ["retaining_wall_support", "perimeter_wall_support"],
                "status": "starter_default",
            },
            {
                "id": "pedestal_on_spread",
                "family": "substructure",
                "usage": ["base_plate_support"],
                "status": "starter_default",
            },
            {
                "id": "grade_beam_tie",
                "family": "substructure",
                "usage": ["conditional_tie_or_transfer"],
                "status": "starter_optional",
            },
            {
                "id": "micropile_cap",
                "family": "substructure",
                "usage": ["deferred_geotech_driven_option"],
                "status": "defer_until_needed",
            },
        ],
        "selection_defaults": {
            "primary_columns": "primary_columns_w",
            "primary_beams": "primary_beams_w",
            "braces": "brace_hss",
            "facade_posts": "facade_posts_hss",
            "wall_secondary": "wall_girts_c",
            "roof_secondary": "roof_purlins_z",
            "openings": "opening_support_w",
            "interior_footings": "interior_spread_footing",
            "perimeter_foundation": "perimeter_retaining_footing",
        },
    }


def starter_catalog_summary(catalog: Dict[str, Any] | None = None) -> Dict[str, Any]:
    catalog = catalog or starter_core_shell_catalog()
    return {
        "catalog_id": catalog["catalog_id"],
        "default_primary_system": catalog["design_intent"]["default_primary_system"],
        "member_family_count": len(catalog["member_families"]),
        "panel_catalog_count": len(catalog["panel_catalogs"]),
        "footing_family_count": len(catalog["footing_families"]),
        "defaults": dict(catalog["selection_defaults"]),
    }
