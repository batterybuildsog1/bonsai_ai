from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List

from .contracts import StructuralSourceElement, StructuralSourceModel


def build_load_path_model(source_model: StructuralSourceModel, system_layout: Dict[str, Any] | None = None) -> Dict[str, Any]:
    elements = list(source_model.elements)
    facade_zones = _facade_zone_load_paths(elements)
    diaphragm_zones = _diaphragm_zone_load_paths(elements)
    primary_frame_system = _system_summary(elements, "primary_frame_system")
    substructure_system = _system_summary(elements, "substructure_system")
    return {
        "schema_version": "1.0",
        "facade_zones": facade_zones,
        "diaphragm_zones": diaphragm_zones,
        "systems": {
            "primary_frame_system": primary_frame_system,
            "substructure_system": substructure_system,
        },
        "summary": {
            "facade_zone_count": len(facade_zones),
            "diaphragm_zone_count": len(diaphragm_zones),
            "layout_summary": dict((system_layout or {}).get("summary") or {}),
        },
    }


def _facade_zone_load_paths(elements: Iterable[StructuralSourceElement]) -> List[Dict[str, Any]]:
    all_elements = list(elements)
    zones: Dict[str, List[StructuralSourceElement]] = {}
    for element in all_elements:
        if element.layout_zone_kind != "facade_zone":
            continue
        zone_id = element.layout_zone_id or element.parent_id or f"zone:{element.id}"
        zones.setdefault(zone_id, []).append(element)

    result: List[Dict[str, Any]] = []
    for zone_id, members in sorted(zones.items()):
        facade = _facade_from_zone(zone_id)
        envelope_elements = [member for member in members if member.role == "envelope"]
        support_elements = [
            member
            for member in all_elements
            if member.interface_type in {"panel_support", "collector_transfer", "primary_framing"}
            and _supports_facade(member, facade)
        ]
        area_m2 = sum(_vertical_surface_area(member) for member in envelope_elements)
        result.append(
            {
                "zone_id": zone_id,
                "facade": facade,
                "system_id": members[0].system_id,
                "assembly_ids": sorted({member.assembly_id for member in members if member.assembly_id}),
                "envelope_element_ids": [member.id for member in envelope_elements],
                "support_element_ids": [member.id for member in support_elements],
                "area_m2": area_m2,
                "height_m": max((_element_height(member) for member in envelope_elements), default=0.0),
                "width_m": max((_element_width(member) for member in envelope_elements), default=0.0),
            }
        )
    return result


def _diaphragm_zone_load_paths(elements: Iterable[StructuralSourceElement]) -> List[Dict[str, Any]]:
    zones: Dict[str, List[StructuralSourceElement]] = {}
    for element in elements:
        if element.layout_zone_kind != "diaphragm_zone":
            continue
        zone_id = element.layout_zone_id or element.parent_id or f"zone:{element.id}"
        zones.setdefault(zone_id, []).append(element)

    result: List[Dict[str, Any]] = []
    for zone_id, members in sorted(zones.items()):
        panel_members = [member for member in members if member.role == "diaphragm"]
        area_m2 = sum(_horizontal_surface_area(member) for member in panel_members)
        support_members = [
            member
            for member in elements
            if member.storey in {panel.storey for panel in panel_members}
            and member.system_id == "primary_frame_system"
            and member.role in {"primary_column", "gravity_column", "floor_beam", "floor_girder", "roof_primary_frame"}
        ]
        result.append(
            {
                "zone_id": zone_id,
                "system_id": members[0].system_id,
                "diaphragm_element_ids": [member.id for member in panel_members],
                "support_element_ids": [member.id for member in support_members],
                "area_m2": area_m2,
                "storeys": sorted({member.storey for member in panel_members if member.storey}),
            }
        )
    return result


def _system_summary(elements: Iterable[StructuralSourceElement], system_id: str) -> Dict[str, Any]:
    system_elements = [element for element in elements if element.system_id == system_id]
    return {
        "system_id": system_id,
        "element_ids": [element.id for element in system_elements],
        "element_count": len(system_elements),
        "zone_ids": sorted({element.layout_zone_id for element in system_elements if element.layout_zone_id}),
    }


def _facade_from_zone(zone_id: str) -> str:
    lowered = zone_id.lower()
    for facade in ("south", "north", "east", "west"):
        if f":{facade}:" in lowered or lowered.endswith(f":{facade}") or f":{facade}_" in lowered:
            return facade
    return "unknown"


def _supports_facade(element: StructuralSourceElement, facade: str) -> bool:
    if facade == "unknown":
        return True
    text = " ".join(
        filter(
            None,
            [
                str(element.layout_zone_id or ""),
                str(element.assembly_id or ""),
                str(element.parent_id or ""),
                str(element.metadata.get("source_name") or ""),
            ],
        )
    ).lower()
    if facade in text:
        return True
    return False


def _vertical_surface_area(element: StructuralSourceElement) -> float:
    geometry = dict(element.geometry)
    return max(_element_width(element), 0.0) * max(_element_height(element), 0.0)


def _horizontal_surface_area(element: StructuralSourceElement) -> float:
    geometry = dict(element.geometry)
    length = float(geometry.get("length", geometry.get("width", 0.0)))
    width = float(geometry.get("width", geometry.get("depth", 0.0)))
    return max(length, 0.0) * max(width, 0.0)


def _element_height(element: StructuralSourceElement) -> float:
    geometry = dict(element.geometry)
    return float(geometry.get("height", geometry.get("thickness", 0.0)))


def _element_width(element: StructuralSourceElement) -> float:
    geometry = dict(element.geometry)
    if "start" in geometry and "end" in geometry:
        start = [float(value) for value in geometry.get("start", [0.0, 0.0, 0.0])]
        end = [float(value) for value in geometry.get("end", start)]
        return math.dist(start, end)
    return float(geometry.get("width", geometry.get("length", 0.0)))
