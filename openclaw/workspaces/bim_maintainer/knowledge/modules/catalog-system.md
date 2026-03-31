# Catalog System

## Purpose
Maps structural roles to catalog families and resolves specific sections (e.g., W12x26) for each element, forming the bridge between the structural source model and real steel section properties.

## How It Works

### catalog_selector.py (113 lines)
- **`ROLE_TO_SELECTION`** dict maps 16 structural roles to preferred/alternate catalog families:
  - `primary_column` -> `primary_columns_w` (alt: `primary_columns_hss`)
  - `floor_beam` -> `primary_beams_w`
  - `brace` -> `brace_hss` (alt: `brace_rod`)
  - `facade_post` -> `facade_posts_hss`
  - `opening_header` -> `opening_support_w`
  - `foundation` -> `interior_spread_footing` (alt: `pedestal_on_spread`)
  - etc.
- **`apply_catalog_selection(source_model, catalog)`**:
  1. Builds lookup dicts from `catalog["member_families"]` and `catalog["footing_families"]`.
  2. For each element in `source_model.elements`, looks up `ROLE_TO_SELECTION[element.role]`.
  3. If found, writes a `catalog_selection` dict into `element.metadata` containing: `preferred_family_id`, `alternate_family_ids`, `candidate_sections`, `preferred_section_id` (first candidate), `shape_family`, `material`, `selection_mode`, `sizing_group_id`.
  4. The `sizing_group_id` is composed as `{family_id}|{role}|{assembly}`.
  5. Returns a summary with selected/unmatched counts per element.

### catalog_resolver.py (71 lines)
- **`resolve_catalog_sections(source_model, catalog, group_overrides=None)`**:
  1. For each element with `catalog_selection.selection_status == "selected"`, resolves a concrete `SectionSpec` via `resolve_catalog_section()` from `section_library.py`.
  2. Supports `group_overrides` dict mapping sizing_group_id -> section name, allowing the sizing loop to override defaults.
  3. Sets `element.section_id` and writes resolution metadata back to `element.metadata`.
  4. Updates `source_model.sections` and `source_model.materials` with resolved specs.
  5. Returns a resolution summary with counts and unresolved elements.

## Current State
Fully implemented. The two-step selection + resolution design cleanly separates family selection (what type of member) from section resolution (what specific size).

## Known Issues
- `ROLE_TO_SELECTION` has no entry for `secondary_beam`, meaning beams without a specific member_role get `selection_status: "unsupported"` and are excluded from sizing.
- The `preferred_section_id` defaults to the first element of `allowed_sections`, which is typically the lightest section -- not necessarily the best starting point for iterative sizing.
- `resolve_catalog_section()` does case-insensitive lookup via `.upper()` but `allowed_sections` in the catalog use mixed case (e.g., `"W10x33"` vs lookup key `"W10X33"`), which works because `starter_section_records()` keys are all uppercase.

## Last Reviewed
2026-03-31
