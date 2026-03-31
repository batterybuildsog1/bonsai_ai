from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Optional

from .contracts import SectionSpec, StructuralSourceModel
from .section_library import family_material_id, resolve_catalog_section, starter_catalog_material_specs


def resolve_catalog_sections(
    source_model: StructuralSourceModel,
    catalog: Dict[str, Any],
    *,
    group_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    group_overrides = group_overrides or {}
    sections_by_id = {section.id: section for section in source_model.sections}
    materials_by_id = {material.id: material for material in source_model.materials}

    for material in starter_catalog_material_specs():
        materials_by_id.setdefault(material.id, material)

    selected_counts: Counter[str] = Counter()
    unresolved: list[dict[str, Any]] = []

    for element in source_model.elements:
        selection = dict(element.metadata.get("catalog_selection") or {})
        if selection.get("selection_status") != "selected":
            continue
        preferred_family_id = str(selection.get("preferred_family_id") or "").strip()
        sizing_group_id = str(selection.get("sizing_group_id") or "").strip()
        preferred_section_id = str(
            group_overrides.get(sizing_group_id)
            or selection.get("preferred_section_id")
            or ""
        ).strip()
        if not preferred_family_id or not preferred_section_id:
            unresolved.append({"element_id": element.id, "reason": "missing_selection"})
            continue
        resolved_material_id = family_material_id(catalog, preferred_family_id)
        section_spec = resolve_catalog_section(preferred_family_id, preferred_section_id, resolved_material_id)
        if section_spec is None:
            unresolved.append(
                {
                    "element_id": element.id,
                    "catalog_family_id": preferred_family_id,
                    "preferred_section_id": preferred_section_id,
                    "reason": "unresolved_catalog_section",
                }
            )
            continue
        sections_by_id.setdefault(section_spec.id, section_spec)
        element.section_id = section_spec.id
        element.metadata["resolved_catalog_section_id"] = section_spec.id
        element.metadata["resolved_catalog_section_name"] = preferred_section_id
        element.metadata["resolved_catalog_family_id"] = preferred_family_id
        selection["resolved_section_id"] = section_spec.id
        selection["resolved_section_name"] = preferred_section_id
        element.metadata["catalog_selection"] = selection
        selected_counts[preferred_section_id] += 1

    source_model.sections = list(sections_by_id.values())
    source_model.materials = list(materials_by_id.values())
    summary = {
        "resolved_section_counts": dict(selected_counts),
        "resolved_group_overrides": dict(group_overrides),
        "unresolved": unresolved,
        "resolved_section_total": int(sum(selected_counts.values())),
    }
    source_model.metadata["catalog_resolution_summary"] = summary
    return summary
