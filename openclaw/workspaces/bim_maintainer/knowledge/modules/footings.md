# Footing Selector

## Purpose
Sizes spread footings from solver reactions using concept-level allowable bearing pressure and prescriptive reinforcement rules.

## How It Works

### footing_selector.py (159 lines)
**Constants:**
- `NEWTON_TO_LBF`, `LBF_TO_KN`, `FT_TO_M`, `PSF_TO_KPA` unit conversions.
- `REBAR_WEIGHT_LB_PER_FT` and `REBAR_DIAMETER_MM` for #5, #6, #7 bars.

**`_starter_reinforcement(service_vertical_lbf, square_size_ft)`**:
- Three tiers based on service vertical load:
  - <= 80k lbf: fc'=28MPa, #5 @ 12" o.c., 18" thick
  - <= 150k lbf: fc'=35MPa, #6 @ 10" o.c., 22" thick
  - > 150k lbf: fc'=41MPa, #7 @ 9" o.c., 28" thick, 2 layers
- Computes bars each way, total rebar length, and rebar weight.

**`starter_footing_from_imposed_load(imposed_load_kn, footing_family, allowable_bearing_psf, basis_note)`**:
- Converts imposed load to lbf.
- Computes required area = load / bearing pressure.
- Rounds up to nearest 0.5 ft square.
- Returns a dict with recommended size, reinforcement, and basis notes.

**`build_starter_footing_summary(package)`**:
- Reads support reactions from `package.analysis_result.summary["support_target_reactions"]`.
- Finds the governing combo (max absolute Fz).
- For each column, determines if it's on the perimeter (min/max x or y coordinate).
- Computes a starter footing using 2,000 psf allowable bearing.
- Returns a summary with all footings and total recommended plan area.

## Current State
Fully implemented with a conservative, concept-level approach.

## Known Issues
- Uses a flat 2,000 psf allowable bearing for all footings regardless of soil conditions -- this is acknowledged in the basis_note.
- Perimeter detection uses a simple min/max bounding box, which fails for L-shaped or irregular floor plans.
- Only #5, #6, #7 bars are supported. Larger projects needing #8+ would not be handled.
- No punching shear check is performed.
- The function is never called in the main pipeline (`design_pipeline_cli.py` or `DesignPipeline`). It appears to be available for manual/external use only.

## Last Reviewed
2026-03-31
