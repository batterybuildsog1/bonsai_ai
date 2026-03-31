# Section Library

## Purpose
Provides AISC steel section properties and a starter catalog of member families, materials, and footing types for structural design.

## How It Works

### section_library.py (297 lines)
- **Unit constants:** `INCH_TO_M`, `IN2_TO_M2`, `IN4_TO_M4`, `LB_PER_FT_TO_N_PER_M`, `KSI_TO_PA`.
- **`CatalogSectionRecord`** frozen dataclass with imperial properties and computed SI property accessors:
  - `area_m2`, `ix_m4`, `iy_m4`, `j_m4`, `depth_m`, `width_m`, `weight_n_per_m`
  - `section_modulus_major_m3` = `ix_m4 / (depth_m / 2)`
  - `section_modulus_minor_m3` = `iy_m4 / (width_m / 2)`
- **`starter_catalog_material_specs()`** returns 3 `MaterialSpec` instances:
  - `steel_w_shapes` (ASTM A992, Fy=50ksi)
  - `steel_hss` (ASTM A500 Grade C, Fy=50ksi)
  - `steel_rod` (Fy=36ksi)
- **`starter_section_records()`** returns a dict of 27 `CatalogSectionRecord` instances:
  - 18 W-shapes: W8X18, W10X22, W10X33, W10X49, W12X26, W12X35, W12X40, W12X53, W14X30, W14X68, W14X90, W16X31, W16X77, W18X35, W18X86, W21X44, W24X55, W27X84
  - 6 HSS sections: HSS4X4X1/4 through HSS12X12X1/2
  - 3 Rod sections: ROD1" through ROD1-1/2"
- **`resolve_catalog_section(family_id, section_name, material_id)`** looks up the section record, builds a `SectionSpec` with SI dimensions (width, depth, web/flange thickness) and detailed metadata (section properties, imperial reference, catalog source).
- **`family_material_id(catalog, family_id)`** looks up the material for a family in the catalog dict.
- Helper factories: `_w_record()`, `_hss_record()`, `_rod_record()` construct records with correct shape family and material assignments.

### system_catalog.py (205 lines)
- **`starter_core_shell_catalog()`** returns a comprehensive catalog dict:
  - `design_intent`: target use, default systems (W-shape frame + HSS braces, cold-formed secondary, spread footings).
  - `source_strategy`: section properties from AISC, pricing from public seed + vendor override.
  - `materials`: steel_w_shapes (A992), steel_hss (A500 Grade C), cold_formed_secondary, panel_concrete.
  - `panel_catalogs`: 1 entry (innovacast_icp_wall_panel with size rules).
  - `member_families`: 10 families covering primary columns (W and HSS), primary beams, braces (HSS and rod), facade posts, wall girts, roof purlins (Z and C), opening support.
  - `connection_families`: 5 families (shear tab, gusset, base plate, secondary clip, panel support).
  - `footing_families`: 5 families (interior spread, perimeter retaining, pedestal, grade beam, micropile cap).
  - `selection_defaults`: mapping from role categories to preferred families.
- **`starter_catalog_summary(catalog)`** returns a simplified summary dict.

## Current State
Fully implemented with a realistic starter catalog. The 27 section records cover common structural steel shapes with accurate AISC v16 properties.

## Known Issues
- Cold-formed sections (C and Z purlins/girts) are listed in the catalog families but have no corresponding `CatalogSectionRecord` entries in `starter_section_records()`, meaning they cannot be resolved to actual section properties. They will fail silently in `resolve_catalog_section()`.
- Rod sections use a simplified formula for weight (`area * 12 * 0.283`) rather than actual catalog values.
- The catalog is hardcoded -- no mechanism to load external catalog data or vendor-specific sections.
- `connection_families` are defined but never used by any downstream code.

## Last Reviewed
2026-03-31
