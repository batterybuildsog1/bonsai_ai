from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from .contracts import StructuralSourceElement, StructuralSourceModel


@dataclass
class LayoutMemberRef:
    id: str
    kind: str
    role: str
    family: str
    system_id: str | None = None
    assembly_id: str | None = None
    layout_zone_id: str | None = None
    layout_zone_kind: str | None = None
    interface_type: str | None = None
    storey: str | None = None


@dataclass
class LayoutZone:
    id: str
    kind: str
    system_id: str | None = None
    assembly_ids: List[str] = field(default_factory=list)
    member_count: int = 0
    role_counts: Dict[str, int] = field(default_factory=dict)
    family_counts: Dict[str, int] = field(default_factory=dict)
    interface_counts: Dict[str, int] = field(default_factory=dict)
    storeys: List[str] = field(default_factory=list)
    members: List[LayoutMemberRef] = field(default_factory=list)


@dataclass
class LayoutSystem:
    id: str
    family_counts: Dict[str, int] = field(default_factory=dict)
    role_counts: Dict[str, int] = field(default_factory=dict)
    zone_ids: List[str] = field(default_factory=list)
    member_count: int = 0


@dataclass
class StructuralLayoutModel:
    schema_version: str = "2.0"
    systems: List[LayoutSystem] = field(default_factory=list)
    zones: List[LayoutZone] = field(default_factory=list)
    family_counts: Dict[str, int] = field(default_factory=dict)
    role_counts: Dict[str, int] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)


ZONE_KIND_BUCKETS = {
    "frame_line": "frame_lines",
    "brace_bay": "brace_bays",
    "collector_line": "collector_lines",
    "roof_frame": "roof_frames",
    "floor_framing_zone": "floor_framing_zones",
    "facade_zone": "facade_zones",
    "facade_support_zone": "facade_support_zones",
    "opening_zone": "opening_zones",
    "diaphragm_zone": "diaphragm_zones",
    "substructure_zone": "substructure_zones",
    "foundation_zone": "foundation_zones",
    "curtain_wall_zone": "curtain_wall_zones",
    "member_group": "member_groups",
    "unknown_zone": "unclassified_zones",
}


def build_system_layout(source_model: StructuralSourceModel) -> Dict[str, Any]:
    zone_map: dict[str, list[StructuralSourceElement]] = defaultdict(list)
    system_map: dict[str, list[StructuralSourceElement]] = defaultdict(list)
    family_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()

    for element in source_model.elements:
        family_counts[element.structural_family] += 1
        role_counts[element.role] += 1
        zone_id = element.layout_zone_id or element.parent_id or f"zone:{element.id}"
        zone_map[zone_id].append(element)
        system_id = element.system_id or f"{element.structural_family}_system"
        system_map[system_id].append(element)

    zones = [_zone_from_elements(zone_id, members) for zone_id, members in sorted(zone_map.items())]
    systems = [_system_from_elements(system_id, members, zones) for system_id, members in sorted(system_map.items())]

    layout_model = StructuralLayoutModel(
        systems=systems,
        zones=zones,
        family_counts=dict(family_counts),
        role_counts=dict(role_counts),
    )
    layout = asdict(layout_model)
    buckets: Dict[str, List[Dict[str, Any]]] = {bucket: [] for bucket in ZONE_KIND_BUCKETS.values()}
    for zone in layout["zones"]:
        bucket_name = ZONE_KIND_BUCKETS.get(zone["kind"], "unclassified_zones")
        buckets.setdefault(bucket_name, []).append(zone)
    layout.update(buckets)
    layout["summary"] = {
        "system_count": len(layout["systems"]),
        "zone_count": len(layout["zones"]),
        "frame_line_count": len(layout["frame_lines"]),
        "brace_bay_count": len(layout["brace_bays"]),
        "collector_line_count": len(layout["collector_lines"]),
        "facade_zone_count": len(layout["facade_zones"]),
        "facade_support_zone_count": len(layout["facade_support_zones"]),
        "opening_zone_count": len(layout["opening_zones"]),
        "substructure_zone_count": len(layout["substructure_zones"]) + len(layout["foundation_zones"]),
    }
    return layout


def _zone_from_elements(zone_id: str, members: List[StructuralSourceElement]) -> LayoutZone:
    first = members[0]
    role_counts = Counter(member.role for member in members)
    family_counts = Counter(member.structural_family for member in members)
    interface_counts = Counter(str(member.interface_type or "unknown") for member in members)
    assembly_ids = sorted({member.assembly_id for member in members if member.assembly_id})
    storeys = sorted({member.storey for member in members if member.storey})
    member_refs = [
        LayoutMemberRef(
            id=member.id,
            kind=member.kind,
            role=member.role,
            family=member.structural_family,
            system_id=member.system_id,
            assembly_id=member.assembly_id,
            layout_zone_id=member.layout_zone_id,
            layout_zone_kind=member.layout_zone_kind,
            interface_type=member.interface_type,
            storey=member.storey,
        )
        for member in members
    ]
    return LayoutZone(
        id=zone_id,
        kind=str(first.layout_zone_kind or _infer_zone_kind(zone_id)),
        system_id=first.system_id,
        assembly_ids=assembly_ids,
        member_count=len(members),
        role_counts=dict(role_counts),
        family_counts=dict(family_counts),
        interface_counts=dict(interface_counts),
        storeys=storeys,
        members=member_refs,
    )


def _system_from_elements(system_id: str, members: List[StructuralSourceElement], zones: List[LayoutZone]) -> LayoutSystem:
    family_counts = Counter(member.structural_family for member in members)
    role_counts = Counter(member.role for member in members)
    member_zone_ids = {member.layout_zone_id or member.parent_id or f"zone:{member.id}" for member in members}
    zone_ids = sorted(zone.id for zone in zones if zone.id in member_zone_ids)
    return LayoutSystem(
        id=system_id,
        family_counts=dict(family_counts),
        role_counts=dict(role_counts),
        zone_ids=zone_ids,
        member_count=len(members),
    )


def _infer_zone_kind(zone_id: str) -> str:
    for prefix, kind in (
        ("frame_line:", "frame_line"),
        ("brace_bay:", "brace_bay"),
        ("collector_line:", "collector_line"),
        ("roof_frame:", "roof_frame"),
        ("floor_framing:", "floor_framing_zone"),
        ("facade:", "facade_zone"),
        ("facade_support:", "facade_support_zone"),
        ("opening:", "opening_zone"),
        ("diaphragm:", "diaphragm_zone"),
        ("substructure:", "substructure_zone"),
        ("foundation:", "foundation_zone"),
        ("curtain_wall:", "curtain_wall_zone"),
        ("member_group:", "member_group"),
    ):
        if zone_id.startswith(prefix):
            return kind
    return "unknown_zone"
