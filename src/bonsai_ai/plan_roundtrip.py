from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Tuple

from .contracts import PhysicalModelSpec, SectionSpec, StructuralSourceModel


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
        _apply_source_element_metadata_to_action(action, element)
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


def apply_sized_sections_to_semantic_model(model: Dict[str, Any], source_model: StructuralSourceModel) -> Dict[str, Any]:
    sections = {section.id: section for section in source_model.sections}
    elements = list(model.get("elements") or [])
    element_index = {str(element.get("id") or "").strip(): element for element in elements if isinstance(element, dict)}

    applied = 0
    unmatched: list[str] = []
    section_counts: Counter[str] = Counter()

    for source_element in source_model.elements:
        if not source_element.section_id:
            continue
        semantic_element = element_index.get(source_element.id)
        if semantic_element is None:
            unmatched.append(source_element.id)
            continue
        section = sections.get(source_element.section_id)
        if section is None:
            unmatched.append(source_element.id)
            continue
        semantic_element["section_id"] = section.id
        action = semantic_element.get("action")
        if isinstance(action, dict):
            _apply_section_to_action(action, section)
            _apply_source_element_metadata_to_action(action, source_element)
        applied += 1
        section_counts[str((section.metadata or {}).get("catalog_section_name") or section.id)] += 1

    model.setdefault("metadata", {})
    if isinstance(model["metadata"], dict):
        model["metadata"]["sizing_roundtrip_summary"] = {
            "applied_count": applied,
            "section_counts": dict(section_counts),
            "unmatched_element_ids": unmatched,
        }
    return dict(model["metadata"]["sizing_roundtrip_summary"]) if isinstance(model.get("metadata"), dict) else {}


def apply_sized_sections_to_physical_model(physical_model: PhysicalModelSpec, source_model: StructuralSourceModel) -> Dict[str, Any]:
    summary = {"compiled_plan": None, "authored_plan": None, "semantic_model": None}
    summary["compiled_plan"] = apply_sized_sections_to_plan(physical_model.plan, source_model)
    if physical_model.authored_plan:
        summary["authored_plan"] = apply_sized_sections_to_plan(physical_model.authored_plan, source_model)
    if physical_model.semantic_model:
        summary["semantic_model"] = apply_sized_sections_to_semantic_model(physical_model.semantic_model, source_model)
    physical_model.metadata["sizing_roundtrip_summary"] = summary
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


def _apply_source_element_metadata_to_action(action: Dict[str, Any], source_element) -> None:
    if action.get("type") != "create_footing":
        return
    foundation = dict(action.get("foundation") or {})
    metadata = dict(source_element.metadata or {})
    for source_key, target_key in (
        ("support_for", "support_for"),
        ("load_combo", "load_combo"),
        ("imposed_load_kN", "imposed_load_kN"),
        ("service_reaction_kN", "service_reaction_kN"),
        ("rebar_weight_kg", "rebar_weight_kg"),
        ("rebar_schedule", "rebar_schedule"),
    ):
        value = metadata.get(source_key)
        if value is not None:
            foundation[target_key] = value
    if foundation:
        action["foundation"] = foundation
