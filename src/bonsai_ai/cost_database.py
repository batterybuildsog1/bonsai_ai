"""Unit cost database for concept-level building cost estimation.

US national average installed costs, sourced March 2026.
Updated March 2026 with REAL bid-level pricing from TechRidge 1.2 DD Estimate
(Zwick Construction, July 2025) -- 199-unit, 5-story wood-framed over
5-level parking, 283,603 SF, $56.4M total ($160.89/SF bldg).

STEEL PRICING SOURCES (verified March 30, 2026):
  - Nucor-Yamato Steel Co. published price list, Feb 18, 2026
    https://nucoryamato.com/staticdata/pricelist.pdf
    ASTM A992/A572-50, $/cwt (per 100 lbs), FOB mill Blytheville AR
    W10x26: $78.00/cwt  (W10x5.75, 22-30 lb/ft range)
    W12x40: $78.00/cwt  (W12x8, 40-50 lb/ft range)
    W14x68: $78.00/cwt  (W14x10, 61-82 lb/ft range)
    W18x35: $78.00/cwt  (W18x6, 35-46 lb/ft range)
    W14x16 (145-283): $93.50/cwt; W12x12 (65-136): $80.75/cwt
  - Steel Dynamics Inc. (SDI) price list, Jul 14, 2025
    http://stld-cci.com/ShowPDF.ashx?id=52
    W12x8 (40-50): $68.25/cwt; W10x5.75 (22-30): $68.25/cwt
    W14x10 (61-82): $68.25/cwt; W18x6 (35-46): $68.25/cwt
    FOB Columbia City, IN
  - Nucor HRC spot: $1,005/ton (Mar 2026, indexbox.io)
    https://www.indexbox.io/blog/nucor-raises-hot-rolled-coil-price-to-1005-per-short-ton/
  - Phoenix Steel Midwest HRC: $1,023/ton (Mar 25, 2026)
    https://www.phoenixsteelservice.com/usa-steel-base-prices/
  - Structural steel Jan 2026: $2,344/ton fabricated (Gordian/ENR), down 7.18% YoY
    https://www.gordian.com/resources/steel-price-updates/
  - Retail beam material: $0.90-$1.60/lb (Angi/HomeGuide 2026)
    https://homeguide.com/costs/steel-beam-cost
  - Fabrication markup: $0.60-$2.20/lb (steelframestructure.com 2025)
    https://www.steelframestructure.com/structural-steel-price-per-pound.html
  - All-in example (200-ton mid-rise): material $0.65/lb + fab $1.50/lb = $2.15/lb
  - GenSteel forecast: HRC mid-$800s thru year-end 2025, upper-$800s into mid-2026
    https://gensteel.com/building-faqs/steel-building-prices/forecast/
  - TechRidge 1.2 DD: Misc metals $12,500/TN ($6.25/lb) -- light misc steel,
    NOT structural beams. Includes stairs, railings, embed plates, angles, etc.

CONCRETE SOURCES (2026):
  - ConcreteNetwork.com (updated Mar 4, 2026): $160-$195/CY national avg, ~$180/CY
    https://www.concretenetwork.com/concrete-prices.html
  - HomeGuide.com (2026): 3000 PSI $130-$140/CY, 4000 PSI $140-$155/CY
    https://homeguide.com/costs/concrete-prices
  - LawnStarter (2026): 4000 PSI $161-$173/CY; 5000 PSI $178-$193/CY
    https://www.lawnstarter.com/blog/cost/concrete-price-per-yard/
  - Formwork: $4-$14/SF (homewyse.com, Jan 2026)
    https://www.homewyse.com/costs/cost_of_insulated_panels.html
  - TechRidge 1.2 DD (Zwick Construction, Jul 2025):
    Form+place footings (all types): $650/CY (includes forming, rebar placement, pour)
    Concrete columns 1'-6"x2'-0": $950/CY (includes forming for vertical pours)
    Slab on grade 4" units: $5.00/SF ($54/m2)
    Slab on grade 5" parking: $6.00/SF ($65/m2)
    Suspended slab 8" PT 2-way: $17.00/SF ($183/m2)
    Shear wall 12" (3hr fire): $28.50/SF ($307/m2)

REBAR SOURCES (2026):
  - HomeGuide.com: #4 $900-$1,000/ton, #5 $950-$1,050/ton (2026)
  - General: $0.50-$1.00/lb material ($1.10-$2.20/kg)
  - TechRidge 1.2 DD: $1.25/LB in-place ($2.76/kg) -- all footing/wall rebar

ENVELOPE SOURCES (2026):
  - Insulated precast/tilt-up: $32-$48/SF installed (HomeGuide, Angi 2026)
  - Insulated metal panels: $7-$14/SF material only (steelbuildinginsulation.com)
    https://steelbuildinginsulation.com/how-much-do-foam-insulated-panels-cost/
    Installation adds $1-$3/SF -> $8-$17/SF installed
  - Storefront glazing: $25-$75/SF installed (Mannlee 2026)
    https://www.mannleecw.com/curtain-wall-cost/
  - Curtain wall: $25-$150+/SF; unitized $100-$150/SF (Mannlee 2026)
  - Window wall: $15-$60/SF (Mannlee 2026)
  - TechRidge 1.2 DD (Zwick Construction, Jul 2025):
    Brick: $28.00/SF ($301/m2)
    Horizontal metal siding: $36.00/SF ($388/m2) -- architectural, 25% of exterior
    Brake metal: $65.00/SF ($700/m2)
    Windows vinyl: $30.00/SF window area ($323/m2)
    Doors sliders vinyl: $35.00/SF ($377/m2)
    Aluminum storefront: $58.00/SF ($624/m2) -- 5% of exterior
    Aluminum storefront entry door single: $4,252/EA
    Aluminum storefront entry door double: $8,200/EA
    Doors single exterior hollow metal: $3,500/EA
    Batt insulation: $0.85/SF ($9.15/m2)
    Flashing/sheet metal: $0.50/SF ($5.38/m2)
    Caulking exterior: $0.25/SF ($2.69/m2)

ROOFING SOURCES (2026):
  - TechRidge 1.2 DD (Zwick Construction, Jul 2025):
    TPO membrane: $11.35/SF ($122/m2) -- 44,752 SF
    Parapet cap: $16.00/LF ($52.49/m)
    Flashing roof-to-wall: $12.00/LF ($39.37/m)
    Traffic coating residential ext deck: $15.00/SF ($161/m2)

These are concept-level costs for early design budgeting, now calibrated
against real bid-level pricing from TechRidge 1.2 DD Estimate (Zwick
Construction, July 2025).  The research agent will refine these with
location-specific data when available.
"""

from __future__ import annotations

from typing import Dict

# ---------------------------------------------------------------------------
# Mill base prices by AISC section ($/cwt, FOB mill, ASTM A992)
# Source: Nucor-Yamato price list, Feb 18, 2026
#   URL: https://nucoryamato.com/staticdata/pricelist.pdf
#   Replaces Jan 7, 2026 list. Incl. RMS surcharge. Freight NOT included.
# Cross-ref: SDI (Columbia City, IN) Jul 14, 2025 = $68.25/cwt for same
#   URL: http://stld-cci.com/ShowPDF.ashx?id=52
# ---------------------------------------------------------------------------
MILL_PRICES_CWT: Dict[str, float] = {
    # Section    $/cwt   Weight range (lb/ft)   Nucor group       SDI Jul'25
    "W10X26":    78.00,  # 22-30 lb/ft          W10x5.75          $68.25
    "W12X40":    78.00,  # 40-50 lb/ft          W12x8             $68.25
    "W14X68":    78.00,  # 61-82 lb/ft          W14x10            $68.25
    "W18X35":    78.00,  # 35-46 lb/ft          W18x6             $68.25
    "W14X16":    93.50,  # 145-283 lb/ft        W14x16            $83.75
    "W12X12":    80.75,  # 65-136 lb/ft         W12x12            $71.00
    "W8X8":      78.00,  # 31-67 lb/ft          W8x8              $68.25
    "W6X6":      78.00,  # 15-25 lb/ft          W6x6              $68.25
    # Additional sections from Nucor-Yamato Feb 2026:
    "W24X55":    78.00,  # 55-62 lb/ft          W24x7             $68.25
    "W21X44":    78.00,  # 44-57 lb/ft          W21x6.5           $68.25
    "W16X36":    78.00,  # 36-57 lb/ft          W16x7             $68.25
    "W14X30":    78.00,  # 30-38 lb/ft          W14x6.75          $68.25
    "W12X26":    78.00,  # 26-35 lb/ft          W12x6.5           $68.25
    "W10X33":    78.00,  # 33-45 lb/ft          W10x8             $68.25
}

# ---------------------------------------------------------------------------
# Per-section material cost ($/lb and $/ft, FOB mill, Feb 2026)
# Derived from Nucor-Yamato $/cwt prices above
# Retail service-center markup is typically 15-50% above mill: $0.90-$1.60/lb
#   Source: https://homeguide.com/costs/steel-beam-cost (2026)
#   Source: https://www.costowl.com/home-improvement/foundations-framing-steel-i-beam.html
# ---------------------------------------------------------------------------
SECTION_MATERIAL_COSTS: Dict[str, Dict[str, float]] = {
    "W10X26": {
        "per_lb": 0.78, "per_ft": 20.28, "per_ton": 1560,
        "per_kg": 1.72, "wt_lb_per_ft": 26,
        "retail_per_lb_range": (0.90, 1.25),  # costowl.com, retail/service-center
        "source": "Nucor-Yamato Feb 18 2026 $78.00/cwt; SDI Jul 2025 $68.25/cwt",
    },
    "W12X40": {
        "per_lb": 0.78, "per_ft": 31.20, "per_ton": 1560,
        "per_kg": 1.72, "wt_lb_per_ft": 40,
        "retail_per_lb_range": (0.90, 1.25),
        "source": "Nucor-Yamato Feb 18 2026 $78.00/cwt; SDI Jul 2025 $68.25/cwt",
    },
    "W14X68": {
        "per_lb": 0.78, "per_ft": 53.04, "per_ton": 1560,
        "per_kg": 1.72, "wt_lb_per_ft": 68,
        "retail_per_lb_range": (0.90, 1.25),
        "source": "Nucor-Yamato Feb 18 2026 $78.00/cwt; SDI Jul 2025 $68.25/cwt",
    },
    "W18X35": {
        "per_lb": 0.78, "per_ft": 27.30, "per_ton": 1560,
        "per_kg": 1.72, "wt_lb_per_ft": 35,
        "retail_per_lb_range": (0.90, 1.25),
        "source": "Nucor-Yamato Feb 18 2026 $78.00/cwt; SDI Jul 2025 $68.25/cwt",
    },
}

# ---------------------------------------------------------------------------
# Fabrication and erection cost components ($/lb, 2026 national avg)
# Sources:
#   - steelframestructure.com (2025): fab markup $0.60-$2.20/lb
#     https://www.steelframestructure.com/structural-steel-price-per-pound.html
#   - Mid-rise example (200-ton): material $0.65 + fab $1.50 = $2.15/lb all-in
#   - Gordian/ENR Jan 2026: $2,344/ton fabricated = ~$1.17/lb
#     https://www.gordian.com/resources/steel-price-updates/
#   - GenSteel: material 25-40% of total installed cost
#     https://gensteel.com/building-faqs/steel-building-prices/forecast/
# ---------------------------------------------------------------------------
STEEL_COST_COMPONENTS: Dict[str, Dict[str, float]] = {
    "material_mill": {
        "low": 0.68, "mid": 0.78, "high": 0.85,
        "note": "FOB mill; low=SDI Jul'25 $68.25/cwt, mid=Nucor Feb'26 $78/cwt, high=retail",
        "source_url": "https://nucoryamato.com/staticdata/pricelist.pdf",
    },
    "fabrication": {
        "low": 0.60, "mid": 0.85, "high": 1.50,
        "note": "Shop fab (cut, drill, weld, prime); high=complex connections",
        "source_url": "https://www.steelframestructure.com/structural-steel-price-per-pound.html",
    },
    "erection": {
        "low": 0.30, "mid": 0.40, "high": 0.50,
        "note": "Field erection with crane; high=urban/height premium",
    },
    "detailing": {
        "low": 0.05, "mid": 0.07, "high": 0.10,
        "note": "Shop drawings and connection design",
    },
}

# ---------------------------------------------------------------------------
# Unit costs (USD, installed, US national average, March 2026)
# ---------------------------------------------------------------------------
COST_DB: Dict[str, float] = {
    # Steel (fabricated + erected, $/kg installed)
    # Material $0.78/lb (Nucor Feb 18 2026, nucoryamato.com/staticdata/pricelist.pdf)
    #   + fab $0.85/lb + erect $0.40/lb + detailing $0.07/lb = $2.10/lb = $4.63/kg
    # Cross-check: Gordian/ENR Jan 2026 fabricated = $2,344/ton = $1.17/lb (no erection)
    #   https://www.gordian.com/resources/steel-price-updates/
    # Cross-check: steelframestructure.com mid-rise example = $2.15/lb all-in
    #   https://www.steelframestructure.com/structural-steel-price-per-pound.html
    "steel_per_kg": 4.63,                  # $2.10/lb fab+erected, sourced Mar 2026
    "steel_connection_per_joint": 450,      # per beam-column connection

    # Steel -- misc metals (light: stairs, railings, embeds, angles, etc.)
    # TechRidge 1.2 DD: $12,500/short ton = $6.25/lb = $13.78/kg
    # This is MUCH higher than structural steel because misc metals include
    # fabrication-intensive items (stair flights, handrails, embed plates).
    "misc_steel_per_kg": 13.78,            # $6.25/lb, TechRidge 1.2 DD (Zwick Jul 2025)
    "steel_stair_flight_each": 10400,      # per flight, TechRidge 1.2 DD
    "steel_decking_per_m2": 87.74,         # $8.15/SF, TechRidge 1.2 DD
    "stud_rails_each": 250,                # elevated deck stud rails, TechRidge 1.2 DD

    # Concrete (ready-mix, placed, finished)
    # Source: ConcreteNetwork $160-$195/CY, ~$180/CY (updated Mar 4 2026)
    #   https://www.concretenetwork.com/concrete-prices.html
    # Source: LawnStarter 2026: 4000 PSI $161-$173/CY delivered
    #   https://www.lawnstarter.com/blog/cost/concrete-price-per-yard/
    # Source: HomeGuide 2026: 4000 PSI $140-$155/CY (lower, possibly excl. delivery)
    #   https://homeguide.com/costs/concrete-prices
    # Using LawnStarter 4000 PSI mid ($167/CY) as better national avg w/ delivery
    # 1 CY = 0.7646 m3; $167/CY = $218/m3
    "concrete_per_m3": 218,                 # ~$167/CY delivered+placed (4000 PSI)

    # Concrete columns (formed + poured, vertical work)
    # TechRidge 1.2 DD: $950/CY = $1,242/m3 (1'-6"x2'-0" columns)
    "concrete_column_per_m3": 1242,         # $950/CY, TechRidge 1.2 DD

    # Rebar (furnished + installed)
    # Source: HomeGuide 2026: #4 $900-$1000/ton, #5 $950-$1050/ton
    # Installed with tying: add ~$0.30/lb -> ~$1.30/lb total = $2.87/kg
    # TechRidge 1.2 DD: $1.25/LB in-place = $2.76/kg (close to our $2.87)
    "rebar_per_kg": 2.76,                   # $1.25/lb in-place, TechRidge 1.2 DD

    # Foundation
    # TechRidge 1.2 DD: Form+place footings $650/CY = $850/m3
    # This is MUCH higher than our old $255/m3 because the $650/CY is
    # all-in: forming, rebar placement, concrete pour, and stripping.
    # Old estimate was just concrete + rough labor.
    "footing_per_m3": 850,                  # $650/CY all-in, TechRidge 1.2 DD
    "slab_on_grade_per_m2": 54,             # $5.00/SF (4" residential), TechRidge 1.2 DD
    "slab_on_grade_parking_per_m2": 65,     # $6.00/SF (5" parking), TechRidge 1.2 DD
    "suspended_slab_per_m2": 183,           # $17.00/SF (8" PT 2-way), TechRidge 1.2 DD

    # Foundation earthwork
    # TechRidge 1.2 DD:
    "excavation_per_m3": 10.46,             # $8.00/CY footings excavation, TechRidge 1.2 DD
    "backfill_per_m3": 41.84,              # $32.00/CY backfill, TechRidge 1.2 DD
    "over_excavation_per_m3": 48.11,       # $36.79/CY over-excavation 6' deep, TechRidge 1.2 DD
    "footing_drain_per_m": 49.21,          # $15.00/LF, TechRidge 1.2 DD

    # Concrete walls
    # TechRidge 1.2 DD: Foundation walls $25-$28.50/SF
    # Shear wall 12" (3hr fire): $28.50/SF = $307/m2
    "foundation_wall_per_m2": 280,          # $26/SF mid, TechRidge 1.2 DD
    "shear_wall_per_m2": 307,              # $28.50/SF (12" 3hr fire), TechRidge 1.2 DD

    # Envelope
    # TechRidge 1.2 DD prices replace old generic estimates:
    # Brick: $28/SF, Metal siding: $36/SF, Brake metal: $65/SF
    "brick_veneer_per_m2": 301,             # $28.00/SF, TechRidge 1.2 DD
    "metal_siding_per_m2": 388,             # $36.00/SF horizontal architectural, TechRidge 1.2 DD
    "brake_metal_per_m2": 700,              # $65.00/SF, TechRidge 1.2 DD
    "concrete_wall_per_m2": 307,            # shear wall, updated to TechRidge shear wall price
    "metal_panel_per_m2": 135,              # insulated metal panel $12.50/SF (steelbuildinginsulation.com)
    "curtain_wall_per_m2": 624,             # $58/SF aluminum storefront, TechRidge 1.2 DD

    # Insulation & weatherproofing
    "batt_insulation_per_m2": 9.15,        # $0.85/SF, TechRidge 1.2 DD
    "flashing_per_m2": 5.38,              # $0.50/SF, TechRidge 1.2 DD
    "caulking_per_m2": 2.69,              # $0.25/SF, TechRidge 1.2 DD

    # Openings
    # TechRidge 1.2 DD: windows priced per SF of window area, not per unit
    "window_per_m2": 323,                   # $30.00/SF vinyl window area, TechRidge 1.2 DD
    "window_slider_per_m2": 377,            # $35.00/SF vinyl slider, TechRidge 1.2 DD
    "window_each": 650,                     # punched commercial window, installed (generic)
    "door_single": 3500,                    # hollow metal exterior, TechRidge 1.2 DD
    "door_double": 8200,                    # aluminum storefront double, TechRidge 1.2 DD
    "door_storefront_single": 4252,         # aluminum storefront single, TechRidge 1.2 DD
    "door_storefront_double": 8200,         # aluminum storefront double, TechRidge 1.2 DD
    "overhead_door_each": 3500,             # 12x14 insulated (unchanged)

    # Roof
    # TechRidge 1.2 DD: TPO membrane $11.35/SF = $122/m2
    # Old: standing seam metal $55/m2 -- TPO is a different system but
    # more common for flat-roof multifamily
    "tpo_roof_per_m2": 122,               # $11.35/SF TPO membrane, TechRidge 1.2 DD
    "metal_roof_per_m2": 55,               # standing seam (retained for steel buildings)
    "parapet_cap_per_m": 52.49,            # $16.00/LF, TechRidge 1.2 DD
    "roof_flashing_per_m": 39.37,          # $12.00/LF roof-to-wall, TechRidge 1.2 DD
    "traffic_coating_per_m2": 161,         # $15.00/SF residential ext deck, TechRidge 1.2 DD

    # Mechanical (TechRidge 1.2 DD: $30.60/SF bldg total)
    "plumbing_per_m2_units": 156.08,       # $14.50/SF units, TechRidge 1.2 DD
    "plumbing_per_m2_corridors": 21.53,    # $2.00/SF corridors, TechRidge 1.2 DD
    "hvac_per_m2_units": 129.17,           # $12.00/SF units, TechRidge 1.2 DD
    "hvac_per_m2_parking": 24.22,          # $2.25/SF parking, TechRidge 1.2 DD

    # Electrical (TechRidge 1.2 DD: $16.86/SF bldg total)
    "electrical_per_m2_units": 151.24,     # $14.05/SF units, TechRidge 1.2 DD
    "electrical_per_m2_parking": 34.98,    # $3.25/SF parking, TechRidge 1.2 DD

    # Soft costs (as fraction of construction subtotal)
    "design_pct": 0.06,                     # 6% of construction
    "permits_pct": 0.02,                    # 2%
    "contingency_pct": 0.10,                # 10%

    # Soft costs from TechRidge 1.2 DD (Zwick Construction, Jul 2025):
    "contractor_fee_pct": 0.04,             # 4.00% of construction
    "general_liability_pct": 0.011,         # 1.10% of construction
    "cmgc_contingency_pct": 0.0225,         # 2.25% CM/GC contingency
    "design_completion_contingency_pct": 0.0075,  # 0.75% design completion
    "general_conditions_per_month": 191008, # $191,007.60/MO, TechRidge 1.2 DD
}

# ---------------------------------------------------------------------------
# Concrete pricing detail ($/CY, delivered, 2026)
# Sources:
#   HomeGuide: https://homeguide.com/costs/concrete-prices
#   ConcreteNetwork (updated Mar 4, 2026): https://www.concretenetwork.com/concrete-prices.html
#   LawnStarter 2026: https://www.lawnstarter.com/blog/cost/concrete-price-per-yard/
# ---------------------------------------------------------------------------
CONCRETE_PRICES_CY: Dict[str, Dict[str, float]] = {
    "3000_PSI": {"low": 143, "mid": 150, "high": 158,
                 "source": "LawnStarter 2026 ($143-$158); HomeGuide ($130-$140)"},
    "4000_PSI": {"low": 161, "mid": 167, "high": 173,
                 "source": "LawnStarter 2026 ($161-$173); HomeGuide ($140-$155)"},
    "5000_PSI": {"low": 178, "mid": 186, "high": 193,
                 "source": "LawnStarter 2026 ($178-$193)"},
    "national_avg": {"low": 160, "mid": 180, "high": 195,
                     "source": "ConcreteNetwork Mar 2026 ($160-$195)"},
}

# ---------------------------------------------------------------------------
# Concrete regional pricing ($/CY, delivered, 2026)
# Source: https://www.lawnstarter.com/blog/cost/concrete-price-per-yard/
# ---------------------------------------------------------------------------
CONCRETE_REGIONAL_CY: Dict[str, Dict[str, float]] = {
    "houston_tx":  {"low": 118, "high": 130},
    "miami_fl":    {"low": 115, "high": 140},
    "chicago_il":  {"low": 120, "high": 160},
    "phoenix_az":  {"low": 120, "high": 155},
    "los_angeles": {"low": 125, "high": 150},
    "seattle_wa":  {"low": 130, "high": 180},
    "atlanta_ga":  {"low": 155, "high": 170},
    "nyc":         {"low": 150, "high": 185},
}

# ---------------------------------------------------------------------------
# Rebar pricing detail (2026)
# Source: HomeGuide.com 2026
# ---------------------------------------------------------------------------
REBAR_PRICES: Dict[str, Dict[str, float]] = {
    "#4": {"per_ton_low": 900, "per_ton_mid": 950, "per_ton_high": 1000,
           "per_lb_mid": 0.475, "source": "HomeGuide 2026"},
    "#5": {"per_ton_low": 950, "per_ton_mid": 1000, "per_ton_high": 1050,
           "per_lb_mid": 0.50, "source": "HomeGuide 2026"},
}

# ---------------------------------------------------------------------------
# Envelope pricing detail ($/SF installed, 2026)
# ---------------------------------------------------------------------------
ENVELOPE_PRICES_SF: Dict[str, Dict[str, float]] = {
    "insulated_precast": {
        "low": 32, "mid": 40, "high": 48,
        "source": "HomeGuide/Angi 2026, national avg installed",
    },
    "insulated_metal_panel": {
        # Material $7-$14/SF + install $1-$3/SF = $8-$17/SF
        "low": 8, "mid": 12.50, "high": 17,
        "source": "steelbuildinginsulation.com 2026: $7-$14 material + $1-$3 install",
        "source_url": "https://steelbuildinginsulation.com/how-much-do-foam-insulated-panels-cost/",
    },
    "storefront_glazing": {
        "low": 25, "mid": 50, "high": 75,
        "source": "Mannlee 2026, standard aluminum+glass",
        "source_url": "https://www.mannleecw.com/curtain-wall-cost/",
    },
    "curtain_wall": {
        "low": 25, "mid": 75, "high": 150,
        "source": "Mannlee 2026: $25-$150+/SF; unitized $100-$150/SF",
        "source_url": "https://www.mannleecw.com/curtain-wall-cost/",
    },
}

# ---------------------------------------------------------------------------
# Formwork pricing ($/SF, 2026)
# Source: homewyse.com Jan 2026
# ---------------------------------------------------------------------------
FORMWORK_PRICES_SF: Dict[str, Dict[str, float]] = {
    "wood": {"low": 2.0, "mid": 3.0, "high": 4.0},
    "metal": {"low": 3.0, "mid": 4.5, "high": 6.0},
    "composite": {"low": 4.0, "mid": 6.0, "high": 8.0},
    "total_set": {"low": 4.35, "mid": 6.0, "high": 14.0,
                  "source": "homewyse.com Jan 2026"},
}

# ---------------------------------------------------------------------------
# Steel market reference prices (for context / cross-checks, Mar 2026)
# ---------------------------------------------------------------------------
STEEL_MARKET_PRICES: Dict[str, Dict] = {
    "nucor_hrc_spot_mar2026": {
        "price_per_short_ton": 1005,
        "date": "2026-03-01",
        "source_url": "https://www.indexbox.io/blog/nucor-raises-hot-rolled-coil-price-to-1005-per-short-ton/",
    },
    "phoenix_midwest_hrc_mar2026": {
        "price_per_short_ton": 1023,
        "date": "2026-03-25",
        "source_url": "https://www.phoenixsteelservice.com/usa-steel-base-prices/",
    },
    "gordian_enr_structural_jan2026": {
        "price_per_short_ton": 2344,  # fabricated, not erected
        "note": "Down 7.18% YoY",
        "date": "2026-01-01",
        "source_url": "https://www.gordian.com/resources/steel-price-updates/",
    },
    "gensteel_hrc_forecast_mid2026": {
        "range_per_short_ton": (800, 900),
        "note": "Upper-$800s into mid-2026; Section 232 tariffs at 50% since Jun 2025",
        "date": "2025-08-01",
        "source_url": "https://gensteel.com/building-faqs/steel-building-prices/forecast/",
    },
}

# ---------------------------------------------------------------------------
# TechRidge 1.2 DD Estimate -- Real Bid Pricing (Zwick Construction, Jul 2025)
# 199 Units, 5 Wood Framed + 5 Parking Levels, 283,603 SF
# Total: $56,436,961 ($160.89/SF bldg)
# Parking: $12,463,664 | Apartments: $43,973,290
# ---------------------------------------------------------------------------
TECHRIDGE_COSTS: Dict[str, Dict] = {
    # --- Footing & Foundation (items 1-75): $1,959,187 ($5.59/SF bldg) ---
    "footings_excavation": {
        "unit_cost": 8.00, "unit": "CY", "quantity": 3671.65,
        "total": 29373, "metric_cost": 10.46, "metric_unit": "m3",
    },
    "backfill_foundation": {
        "unit_cost": 32.00, "unit": "CY", "quantity": 1639.72,
        "total": 52471, "metric_cost": 41.84, "metric_unit": "m3",
    },
    "backfill_at_ramp": {
        "unit_cost": 32.00, "unit": "CY", "quantity": 2397.33,
        "total": 76715, "metric_cost": 41.84, "metric_unit": "m3",
    },
    "over_excavation_6ft": {
        "unit_cost": 36.79, "unit": "CY", "quantity": 7805.00,
        "metric_cost": 48.11, "metric_unit": "m3",
    },
    "form_place_continuous_FTS2": {
        "unit_cost": 650.00, "unit": "CY", "quantity": 427.11,
        "total": 277622, "metric_cost": 850.08, "metric_unit": "m3",
    },
    "form_place_continuous_FC4": {
        "unit_cost": 650.00, "unit": "CY", "quantity": 403.56,
        "total": 262311, "metric_cost": 850.08, "metric_unit": "m3",
    },
    "form_place_continuous_FC10": {
        "unit_cost": 650.00, "unit": "CY", "quantity": 502.96,
        "total": 326926, "metric_cost": 850.08, "metric_unit": "m3",
    },
    "form_place_continuous_FC11": {
        "unit_cost": 650.00, "unit": "CY", "quantity": 123.52,
        "total": 80287, "metric_cost": 850.08, "metric_unit": "m3",
    },
    "form_place_spot_FS10": {
        "unit_cost": 650.00, "unit": "CY", "quantity": 176.54,
        "total": 114753, "metric_cost": 850.08, "metric_unit": "m3",
    },
    "form_place_spot_FS12": {
        "unit_cost": 650.00, "unit": "CY", "quantity": 61.33,
        "total": 39867, "metric_cost": 850.08, "metric_unit": "m3",
    },
    "form_place_elevator_spots": {
        "unit_cost": 650.00, "unit": "CY", "quantity": 133.33,
        "total": 86667, "metric_cost": 850.08, "metric_unit": "m3",
    },
    "foundation_walls": {
        "unit_cost_range": (25.00, 28.50), "unit": "SF",
        "metric_cost_range": (269, 307), "metric_unit": "m2",
    },
    "footing_drain": {
        "unit_cost": 15.00, "unit": "LF", "quantity": 1285,
        "total": 19275, "metric_cost": 49.21, "metric_unit": "m",
    },
    "rebar_footings": {
        "unit_cost": 1.25, "unit": "LB", "quantity": 160286,
        "total": 200358, "metric_cost": 2.76, "metric_unit": "kg",
    },
    "rebar_spots": {
        "unit_cost": 1.25, "unit": "LB", "quantity": 24129,
        "total": 30161, "metric_cost": 2.76, "metric_unit": "kg",
    },
    "rebar_walls_concrete_4psf": {
        "unit_cost": 1.25, "unit": "LB", "quantity": 25288,
        "total": 31610, "metric_cost": 2.76, "metric_unit": "kg",
    },

    # --- Superstructure (items 76-154): $14,363,641 ($40.95/SF) ---
    "slab_on_grade_4in_units": {
        "unit_cost": 5.00, "unit": "SF", "quantity": 45492,
        "total": 226582, "metric_cost": 53.82, "metric_unit": "m2",
    },
    "slab_on_grade_5in_parking": {
        "unit_cost": 6.00, "unit": "SF", "quantity": 26460,
        "total": 127325, "metric_cost": 64.58, "metric_unit": "m2",
    },
    "concrete_columns_18x24": {
        "unit_cost": 950.00, "unit": "CY", "quantity": 196,
        "total": 186200, "metric_cost": 1242.31, "metric_unit": "m3",
    },
    "suspended_slab_8in_pt_2way": {
        "unit_cost": 17.00, "unit": "SF", "quantity": 85792,
        "total": 1458464, "metric_cost": 183.00, "metric_unit": "m2",
    },
    "rebar_8in_pt_deck_3psf": {
        "unit_cost": 1.25, "unit": "LB", "quantity": 257376,
        "total": 321720, "metric_cost": 2.76, "metric_unit": "kg",
    },
    "rebar_concrete_walls_4psf": {
        "unit_cost": 1.25, "unit": "LB", "quantity": 227760,
        "total": 284700, "metric_cost": 2.76, "metric_unit": "kg",
    },
    "shear_wall_12in_3hr": {
        "unit_cost": 28.50, "unit": "SF", "quantity": 55440,
        "total": 1632558, "metric_cost": 306.77, "metric_unit": "m2",
    },
    "misc_metals_035_lbs_sf": {
        "unit_cost": 12500.00, "unit": "TN", "quantity": 61.39,
        "total": 767353, "per_lb": 6.25, "metric_cost": 13780, "metric_unit": "metric_ton",
    },
    "metal_stair_flights": {
        "unit_cost": 10400.00, "unit": "FLT", "quantity": 66,
        "total": 686400,
    },
    "steel_decking": {
        "unit_cost": 8.15, "unit": "SF", "quantity": 85792,
        "total": 699021, "metric_cost": 87.74, "metric_unit": "m2",
    },
    "elevated_deck_stud_rails": {
        "unit_cost": 250.00, "unit": "EA", "quantity": 1680,
        "total": 420000,
    },

    # --- Exterior Closure (items 155-196): $5,252,427 ($14.97/SF) ---
    "brick": {
        "unit_cost": 28.00, "unit": "SF", "quantity": 20341,
        "total": 569560, "metric_cost": 301.39, "metric_unit": "m2",
    },
    "horizontal_metal_siding": {
        "unit_cost": 36.00, "unit": "SF", "quantity": 28252,
        "total": 1261330, "metric_cost": 387.50, "metric_unit": "m2",
        "note": "25% of exterior area, architectural metal siding",
    },
    "brake_metal": {
        "unit_cost": 65.00, "unit": "SF", "quantity": 6781,
        "total": 440731, "metric_cost": 699.65, "metric_unit": "m2",
    },
    "windows_vinyl": {
        "unit_cost": 30.00, "unit": "SF", "quantity": 20341,
        "total": 610243, "metric_cost": 322.92, "metric_unit": "m2",
    },
    "doors_sliders_vinyl": {
        "unit_cost": 35.00, "unit": "SF", "quantity": 11301,
        "total": 395528, "metric_cost": 376.74, "metric_unit": "m2",
    },
    "aluminum_storefront": {
        "unit_cost": 58.00, "unit": "SF", "quantity": 5650,
        "total": 127000, "metric_cost": 624.31, "metric_unit": "m2",
        "note": "5% of exterior area",
    },
    "storefront_entry_door_single": {
        "unit_cost": 4252.00, "unit": "EA", "quantity": 11,
        "total": 46772,
    },
    "storefront_entry_door_double": {
        "unit_cost": 8200.00, "unit": "EA", "quantity": 1,
        "total": 8200,
    },
    "door_single_exterior_hm": {
        "unit_cost": 3500.00, "unit": "EA", "quantity": 3,
        "total": 10500,
    },
    "batt_insulation": {
        "unit_cost": 0.85, "unit": "SF", "quantity": 48432,
        "total": 41167, "metric_cost": 9.15, "metric_unit": "m2",
    },
    "flashing_sheet_metal": {
        "unit_cost": 0.50, "unit": "SF", "quantity": 123128,
        "total": 61564, "metric_cost": 5.38, "metric_unit": "m2",
    },
    "caulking_exterior": {
        "unit_cost": 0.25, "unit": "SF", "quantity": 123128,
        "total": 30782, "metric_cost": 2.69, "metric_unit": "m2",
    },

    # --- Roofing (items 197-211): $772,273 ($14.70/SF roof) ---
    "tpo_membrane": {
        "unit_cost": 11.35, "unit": "SF", "quantity": 44752,
        "total": 507935, "metric_cost": 122.15, "metric_unit": "m2",
    },
    "parapet_cap": {
        "unit_cost": 16.00, "unit": "LF", "quantity": 1595,
        "total": 25520, "metric_cost": 52.49, "metric_unit": "m",
    },
    "flashing_roof_to_wall": {
        "unit_cost": 12.00, "unit": "LF", "quantity": 680,
        "total": 8160, "metric_cost": 39.37, "metric_unit": "m",
    },
    "traffic_coating_ext_deck": {
        "unit_cost": 15.00, "unit": "SF", "quantity": 11266,
        "total": 168990, "metric_cost": 161.46, "metric_unit": "m2",
    },

    # --- Project-level costs ---
    "general_conditions": {
        "per_month": 191007.60, "months": 26,
        "total": 4966198,
    },
    "contractor_fee": {
        "pct": 0.04, "total": 2257478,
    },
    "general_liability_insurance": {
        "pct": 0.011, "total": 620807,
    },
    "cmgc_contingency": {
        "pct": 0.0225, "total": 1269832,
    },
}

# ---------------------------------------------------------------------------
# TechRidge division totals (for cross-check / benchmarking)
# ---------------------------------------------------------------------------
TECHRIDGE_DIVISION_TOTALS: Dict[str, Dict] = {
    "total_construction": {"total": 56436961, "per_sf": 160.89, "sf": 283603},
    "parking": {"total": 12463664},
    "apartments": {"total": 43973290},
    "footing_foundation": {"total": 1959187, "per_sf": 5.59, "items": "1-75"},
    "superstructure": {"total": 14363641, "per_sf": 40.95, "items": "76-154"},
    "exterior_closure": {"total": 5252427, "per_sf": 14.97, "items": "155-196"},
    "roofing": {"total": 772273, "per_sf_roof": 14.70, "items": "197-211"},
    "mechanical": {"total": 6838739, "per_sf": 30.60, "items": "538-563"},
    "electrical": {"total": 3768286, "per_sf": 16.86, "items": "564-584"},
    "general_conditions": {"total": 4966198, "per_month": 191007.60, "months": 26},
    "contractor_fee": {"total": 2257478, "pct": 0.04},
    "general_liability": {"total": 620807, "pct": 0.011},
    "cmgc_contingency": {"total": 1269832, "pct": 0.0225},
}

# ---------------------------------------------------------------------------
# Soft cost percentages (TechRidge 1.2 DD + industry standard)
# ---------------------------------------------------------------------------
SOFT_COST_PCTS: Dict[str, Dict] = {
    "general_conditions": {
        "per_month": 191008, "typical_months_range": (18, 30),
        "note": "Highly project-specific; TechRidge = 26 months",
        "source": "TechRidge 1.2 DD (Zwick Construction, Jul 2025)",
    },
    "contractor_fee": {
        "pct": 0.04, "range": (0.03, 0.06),
        "source": "TechRidge 1.2 DD (Zwick Construction, Jul 2025)",
    },
    "general_liability_insurance": {
        "pct": 0.011, "range": (0.008, 0.015),
        "source": "TechRidge 1.2 DD (Zwick Construction, Jul 2025)",
    },
    "cmgc_contingency": {
        "pct": 0.0225, "range": (0.01, 0.03),
        "note": "CM/GC contingency for DD-level estimates",
        "source": "TechRidge 1.2 DD (Zwick Construction, Jul 2025)",
    },
    "design_completion_contingency": {
        "pct": 0.0075, "range": (0.005, 0.02),
        "note": "Accounts for design not yet at 100% CD",
        "source": "TechRidge 1.2 DD (Zwick Construction, Jul 2025)",
    },
    "design_fees": {
        "pct": 0.06, "range": (0.04, 0.08),
        "source": "Industry standard",
    },
    "permits_fees": {
        "pct": 0.02, "range": (0.01, 0.04),
        "source": "Industry standard",
    },
}

# ---------------------------------------------------------------------------
# Cost source tracking -- documents where each COST_DB value comes from
# ---------------------------------------------------------------------------
COST_SOURCE: Dict[str, str] = {
    # Steel
    "steel_per_kg": "Nucor-Yamato Feb 2026 + fab/erect buildup, $2.10/lb",
    "steel_connection_per_joint": "Industry estimate, $450/joint",
    "misc_steel_per_kg": "TechRidge 1.2 DD: $12,500/TN misc metals (Zwick Jul 2025)",
    "steel_stair_flight_each": "TechRidge 1.2 DD: $10,400/FLT (Zwick Jul 2025)",
    "steel_decking_per_m2": "TechRidge 1.2 DD: $8.15/SF (Zwick Jul 2025)",
    "stud_rails_each": "TechRidge 1.2 DD: $250/EA (Zwick Jul 2025)",

    # Concrete
    "concrete_per_m3": "LawnStarter 2026 4000 PSI $167/CY = $218/m3",
    "concrete_column_per_m3": "TechRidge 1.2 DD: $950/CY columns (Zwick Jul 2025)",
    "rebar_per_kg": "TechRidge 1.2 DD: $1.25/LB in-place (Zwick Jul 2025)",

    # Foundation
    "footing_per_m3": "TechRidge 1.2 DD: $650/CY form+place all-in (Zwick Jul 2025)",
    "slab_on_grade_per_m2": "TechRidge 1.2 DD: $5.00/SF 4\" units (Zwick Jul 2025)",
    "slab_on_grade_parking_per_m2": "TechRidge 1.2 DD: $6.00/SF 5\" parking (Zwick Jul 2025)",
    "suspended_slab_per_m2": "TechRidge 1.2 DD: $17.00/SF 8\" PT 2-way (Zwick Jul 2025)",
    "excavation_per_m3": "TechRidge 1.2 DD: $8.00/CY (Zwick Jul 2025)",
    "backfill_per_m3": "TechRidge 1.2 DD: $32.00/CY (Zwick Jul 2025)",
    "over_excavation_per_m3": "TechRidge 1.2 DD: $36.79/CY (Zwick Jul 2025)",
    "footing_drain_per_m": "TechRidge 1.2 DD: $15.00/LF (Zwick Jul 2025)",
    "foundation_wall_per_m2": "TechRidge 1.2 DD: $25-$28.50/SF mid=$26/SF (Zwick Jul 2025)",
    "shear_wall_per_m2": "TechRidge 1.2 DD: $28.50/SF 12\" 3hr fire (Zwick Jul 2025)",

    # Envelope
    "brick_veneer_per_m2": "TechRidge 1.2 DD: $28.00/SF (Zwick Jul 2025)",
    "metal_siding_per_m2": "TechRidge 1.2 DD: $36.00/SF architectural (Zwick Jul 2025)",
    "brake_metal_per_m2": "TechRidge 1.2 DD: $65.00/SF (Zwick Jul 2025)",
    "concrete_wall_per_m2": "TechRidge 1.2 DD: $28.50/SF shear wall (Zwick Jul 2025)",
    "metal_panel_per_m2": "steelbuildinginsulation.com 2026: $12.50/SF insulated",
    "curtain_wall_per_m2": "TechRidge 1.2 DD: $58.00/SF aluminum storefront (Zwick Jul 2025)",
    "batt_insulation_per_m2": "TechRidge 1.2 DD: $0.85/SF (Zwick Jul 2025)",
    "flashing_per_m2": "TechRidge 1.2 DD: $0.50/SF (Zwick Jul 2025)",
    "caulking_per_m2": "TechRidge 1.2 DD: $0.25/SF (Zwick Jul 2025)",

    # Openings
    "window_per_m2": "TechRidge 1.2 DD: $30.00/SF vinyl window area (Zwick Jul 2025)",
    "window_slider_per_m2": "TechRidge 1.2 DD: $35.00/SF vinyl slider (Zwick Jul 2025)",
    "window_each": "Industry estimate, $650/EA punched commercial (pre-TechRidge)",
    "door_single": "TechRidge 1.2 DD: $3,500/EA hollow metal exterior (Zwick Jul 2025)",
    "door_double": "TechRidge 1.2 DD: $8,200/EA storefront double (Zwick Jul 2025)",
    "door_storefront_single": "TechRidge 1.2 DD: $4,252/EA (Zwick Jul 2025)",
    "door_storefront_double": "TechRidge 1.2 DD: $8,200/EA (Zwick Jul 2025)",
    "overhead_door_each": "Industry estimate, $3,500/EA 12x14 insulated",

    # Roof
    "tpo_roof_per_m2": "TechRidge 1.2 DD: $11.35/SF TPO membrane (Zwick Jul 2025)",
    "metal_roof_per_m2": "Industry estimate, $55/m2 standing seam",
    "parapet_cap_per_m": "TechRidge 1.2 DD: $16.00/LF (Zwick Jul 2025)",
    "roof_flashing_per_m": "TechRidge 1.2 DD: $12.00/LF (Zwick Jul 2025)",
    "traffic_coating_per_m2": "TechRidge 1.2 DD: $15.00/SF (Zwick Jul 2025)",

    # Mechanical
    "plumbing_per_m2_units": "TechRidge 1.2 DD: $14.50/SF units (Zwick Jul 2025)",
    "plumbing_per_m2_corridors": "TechRidge 1.2 DD: $2.00/SF corridors (Zwick Jul 2025)",
    "hvac_per_m2_units": "TechRidge 1.2 DD: $12.00/SF units (Zwick Jul 2025)",
    "hvac_per_m2_parking": "TechRidge 1.2 DD: $2.25/SF parking (Zwick Jul 2025)",

    # Electrical
    "electrical_per_m2_units": "TechRidge 1.2 DD: $14.05/SF units (Zwick Jul 2025)",
    "electrical_per_m2_parking": "TechRidge 1.2 DD: $3.25/SF parking (Zwick Jul 2025)",

    # Soft costs
    "design_pct": "Industry standard 6%",
    "permits_pct": "Industry standard 2%",
    "contingency_pct": "Industry standard 10% (concept-level)",
    "contractor_fee_pct": "TechRidge 1.2 DD: 4.00% (Zwick Jul 2025)",
    "general_liability_pct": "TechRidge 1.2 DD: 1.10% (Zwick Jul 2025)",
    "cmgc_contingency_pct": "TechRidge 1.2 DD: 2.25% (Zwick Jul 2025)",
    "design_completion_contingency_pct": "TechRidge 1.2 DD: 0.75% (Zwick Jul 2025)",
    "general_conditions_per_month": "TechRidge 1.2 DD: $191,007.60/MO (Zwick Jul 2025)",
}

# Conversion constants
M2_TO_SF = 10.7639104                       # 1 m^2 = 10.764 ft^2
