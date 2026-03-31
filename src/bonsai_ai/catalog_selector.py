from __future__ import annotations

from collections import Counter
from typing import Any, Dict

from .contracts import StructuralSourceModel


ROLE_TO_SELECTION = {
    "primary_column": {"preferred": "primary_columns_w", "alternates": ["primary_columns_hss"]},
    "gravity_column": {"preferred": "primary_columns_w", "alternates": ["primary_columns_hss"]},
    "roof_primary_frame": {"preferred": "primary_beams_w", "alternates": []},
    "floor_beam": {"preferred": "primary_beams_w", "alternates": []},
    "floor_girder": {"preferred": "primary_beams_w", "alternates": []},
    "drag_collector": {"preferred": "primary_beams_w", "alternates": []},
    "roof_collector": {"preferred": "primary_beams_w", "alternates": []},
    "brace": {"preferred": "brace_hss", "alternates": ["brace_rod"]},
    "facade_post": {"preferred": "facade_posts_hss", "alternates": []},
    "perimeter_spandrel": {"preferred": "primary_beams_w", "alternates": []},
    "panel_joint_support": {"preferred": "wall_girts_c", "alternates": ["primary_beams_w"]},
    "roof_edge_support": {"preferred": "roof_purlins_z", "alternates": ["roof_purlins_c"]},
    "opening_header": {"preferred": "opening_support_w", "alternates": []},
    "opening_sill": {"preferred": "opening_support_w", "alternates": []},
    "opening_jamb": {"preferred": "facade_posts_hss", "alternates": ["primary_columns_hss"]},
    "foundation": {"preferred": "interior_spread_footing", "alternates": ["pedestal_on_spread"]},
    "retaining": {"preferred": "perimeter_retaining_footing", "alternates": ["grade_beam_tie"]},
}


def apply_catalog_selection(source_model: StructuralSourceModel, catalog: Dict[str, Any]) -> Dict[str, Any]:
    families_by_id = {family["id"]: family for family in catalog.get("member_families", [])}
    footing_by_id = {family["id"]: family for family in catalog.get("footing_families", [])}
    all_catalogs = {**families_by_id, **footing_by_id}

    preferred_counts: Counter[str] = Counter()
    unmatched_roles: Counter[str] = Counter()
    sizing_group_counts: Counter[str] = Counter()
    per_element: list[Dict[str, Any]] = []

    for element in source_model.elements:
        selection = ROLE_TO_SELECTION.get(element.role)
        if not selection:
            unmatched_roles[element.role] += 1
            per_element.append(
                {
                    "element_id": element.id,
                    "role": element.role,
                    "structural_family": element.structural_family,
                    "parent_id": element.parent_id,
                    "selection_status": "unsupported",
                }
            )
            continue
        preferred_id = selection["preferred"]
        alternates = [item for item in selection.get("alternates", []) if item in all_catalogs]
        preferred = all_catalogs.get(preferred_id)
        if not preferred:
            unmatched_roles[element.role] += 1
            per_element.append(
                {
                    "element_id": element.id,
                    "role": element.role,
                    "structural_family": element.structural_family,
                    "parent_id": element.parent_id,
                    "selection_status": "unsupported",
                }
            )
            continue
        preferred_sections = list(preferred.get("allowed_sections") or [])
        sizing_group_id = _sizing_group_id(element, preferred_id)
        element.metadata["catalog_selection"] = {
            "preferred_family_id": preferred_id,
            "alternate_family_ids": alternates,
            "candidate_sections": preferred_sections,
            "preferred_section_id": preferred_sections[0] if preferred_sections else None,
            "shape_family": preferred.get("shape_family"),
            "material": preferred.get("material"),
            "selection_mode": "catalog_default",
            "sizing_group_id": sizing_group_id,
            "selection_status": "selected",
        }
        preferred_counts[preferred_id] += 1
        sizing_group_counts[sizing_group_id] += 1
        per_element.append(
            {
                "element_id": element.id,
                "role": element.role,
                "structural_family": element.structural_family,
                "parent_id": element.parent_id,
                "catalog_family_id": preferred_id,
                "alternate_family_ids": alternates,
                "candidate_section_ids": preferred_sections,
                "preferred_section_id": preferred_sections[0] if preferred_sections else None,
                "sizing_group_id": sizing_group_id,
                "selection_status": "selected",
            }
        )

    return {
        "schema_version": "1.0",
        "catalog_id": catalog.get("catalog_id"),
        "selected_family_counts": dict(preferred_counts),
        "sizing_group_counts": dict(sizing_group_counts),
        "unmatched_roles": dict(unmatched_roles),
        "selection_defaults": dict(catalog.get("selection_defaults") or {}),
        "per_element": per_element,
    }


def _sizing_group_id(element, preferred_family_id: str) -> str:
    assembly = element.assembly_id or element.parent_id or f"element:{element.id}"
    return f"{preferred_family_id}|{element.role}|{assembly}"
