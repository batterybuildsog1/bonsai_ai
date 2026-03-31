from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Tuple

from .contracts import SectionSpec, StructuralSourceModel


def apply_sized_sections_to_plan(plan: Dict[str, Any], source_model: StructuralSourceModel) -> Dict[str, Any]:
    actions = list(plan.get("actions") or [])
    sections = {section.id: section for section in source_model.sections}
    action_index = _build_action_index(actions)

    applied = 0
    unmatched: list[str] = []
    updated_action_names: list[str] = []
    section_counts: Counter[str] = Counter()

    for element in source_model.elements:
        if not element.section_id:
            continue
        match = action_index.get(element.id)
        if match is None:
            source_name = str(element.metadata.get("source_name") or "")
            match = action_index.get(source_name)
        if match is None:
            unmatched.append(element.id)
            continue

        action, _ = match
        section = sections.get(element.section_id)
        if section is None:
            unmatched.append(element.id)
            continue

        _apply_section_to_action(action, section)
        applied += 1
        updated_action_names.append(str(action.get("name") or element.id))
        section_counts[str((section.metadata or {}).get("catalog_section_name") or section.id)] += 1

    summary = {
        "applied_count": applied,
        "updated_action_names": updated_action_names,
        "section_counts": dict(section_counts),
        "unmatched_element_ids": unmatched,
    }
    plan.setdefault("metadata", {})
    if isinstance(plan["metadata"], dict):
        plan["metadata"]["sizing_roundtrip_summary"] = summary
    return summary


def _build_action_index(actions: list[Dict[str, Any]]) -> Dict[str, Tuple[Dict[str, Any], str]]:
    index: Dict[str, Tuple[Dict[str, Any], str]] = {}
    for action in actions:
        name = str(action.get("name") or "").strip()
        if name:
            index.setdefault(name, (action, "name"))
        semantics = action.get("semantics")
        if isinstance(semantics, dict):
            element_id = str(semantics.get("element_id") or "").strip()
            if element_id:
                index[element_id] = (action, "element_id")
    return index


def _apply_section_to_action(action: Dict[str, Any], section: SectionSpec) -> None:
    action["section_id"] = section.id
    dims = dict(section.dimensions or {})
    if action.get("type") in {"create_column", "create_beam"}:
        if dims.get("width") is not None:
            action["width"] = float(dims["width"])
        if dims.get("depth") is not None:
            action["depth"] = float(dims["depth"])
    if action.get("type") in {"create_panel", "create_rect_slab", "create_footing"} and dims.get("thickness") is not None:
        action["thickness"] = float(dims["thickness"])
