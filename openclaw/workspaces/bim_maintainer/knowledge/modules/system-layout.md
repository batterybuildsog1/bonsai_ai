# System Layout

## Purpose
Organizes structural source elements into a hierarchical layout model of systems, zones, and members for downstream analysis and reporting.

## How It Works

### system_layout.py (187 lines)
**Data classes:**
- `LayoutMemberRef(id, kind, role, family, system_id, assembly_id, layout_zone_id, layout_zone_kind, interface_type, storey)`
- `LayoutZone(id, kind, system_id, assembly_ids, member_count, role_counts, family_counts, interface_counts, storeys, members)`
- `LayoutSystem(id, family_counts, role_counts, zone_ids, member_count)`
- `StructuralLayoutModel(schema_version, systems, zones, family_counts, role_counts, summary)`

**`build_system_layout(source_model)`**:
1. Groups elements by `layout_zone_id` (falling back to `parent_id` or `zone:{id}`).
2. Groups elements by `system_id` (falling back to `{family}_system`).
3. Builds `LayoutZone` objects with member refs, role/family/interface counts, and storey lists.
4. Builds `LayoutSystem` objects linking to their zone IDs.
5. Returns a dict with the layout model plus zone buckets organized by `ZONE_KIND_BUCKETS` mapping (13 kinds -> bucket names like `frame_lines`, `brace_bays`, `facade_zones`, etc.).
6. Adds a summary with counts of each zone type.

**`_infer_zone_kind(zone_id)`** uses prefix matching (e.g., `frame_line:` -> `frame_line`, `facade:` -> `facade_zone`) as a fallback when `layout_zone_kind` is not set.

## Current State
Fully implemented. The layout model provides a structured view of the building's structural organization that powers the load path model and engineering model scoping.

## Known Issues
- The zone bucketing duplicates the zones list -- each zone appears both in the `zones` list and in its typed bucket (e.g., `frame_lines`), doubling memory for large models.
- `_zone_from_elements()` uses `first.layout_zone_kind` for the zone kind, which assumes all members in a zone share the same kind. If a zone has mixed kinds (which shouldn't happen but could from bad semantic data), only the first element's kind is used.
- No mechanism to merge or split zones after initial construction.

## Last Reviewed
2026-03-31
