"""Unit cost database for concept-level building cost estimation.

US national average installed costs, sourced March 2026.

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

CONCRETE SOURCES (2026):
  - ConcreteNetwork.com (updated Mar 4, 2026): $160-$195/CY national avg, ~$180/CY
    https://www.concretenetwork.com/concrete-prices.html
  - HomeGuide.com (2026): 3000 PSI $130-$140/CY, 4000 PSI $140-$155/CY
    https://homeguide.com/costs/concrete-prices
  - LawnStarter (2026): 4000 PSI $161-$173/CY; 5000 PSI $178-$193/CY
    https://www.lawnstarter.com/blog/cost/concrete-price-per-yard/
  - Formwork: $4-$14/SF (homewyse.com, Jan 2026)
    https://www.homewyse.com/costs/cost_of_insulated_panels.html

REBAR SOURCES (2026):
  - HomeGuide.com: #4 $900-$1,000/ton, #5 $950-$1,050/ton (2026)
  - General: $0.50-$1.00/lb material ($1.10-$2.20/kg)

ENVELOPE SOURCES (2026):
  - Insulated precast/tilt-up: $32-$48/SF installed (HomeGuide, Angi 2026)
  - Insulated metal panels: $7-$14/SF material only (steelbuildinginsulation.com)
    https://steelbuildinginsulation.com/how-much-do-foam-insulated-panels-cost/
    Installation adds $1-$3/SF -> $8-$17/SF installed
  - Storefront glazing: $25-$75/SF installed (Mannlee 2026)
    https://www.mannleecw.com/curtain-wall-cost/
  - Curtain wall: $25-$150+/SF; unitized $100-$150/SF (Mannlee 2026)
  - Window wall: $15-$60/SF (Mannlee 2026)

These are concept-level costs for early design budgeting -- not detailed
bid pricing.  The research agent will refine these with location-specific
data when available.
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

    # Rebar (furnished + installed)
    # Source: HomeGuide 2026: #4 $900-$1000/ton, #5 $950-$1050/ton
    # Installed with tying: add ~$0.30/lb -> ~$1.30/lb total = $2.87/kg
    "rebar_per_kg": 2.87,                   # ~$1.30/lb in-place, #4/#5 avg

    # Foundation
    # Source: homewyse.com Jan 2026: formwork $4-$14/SF
    # Complete footing: excavate + form + rebar + concrete + backfill
    # Concrete $167/CY + rebar + formwork + labor -> ~$255/m3 all-in
    "footing_per_m3": 255,                  # complete spread footing, installed
    "slab_on_grade_per_m2": 70,             # 4" slab with vapor barrier

    # Envelope
    # Insulated metal panels: $7-$14/SF material + $1-$3/SF install = $8-$17/SF
    #   Source: https://steelbuildinginsulation.com/how-much-do-foam-insulated-panels-cost/
    #   Mid = $12.50/SF installed (2" R-15 to 8" R-48 range)
    # Storefront/curtain wall: $25-$150+/SF installed
    #   Source: https://www.mannleecw.com/curtain-wall-cost/
    #   Standard stick-built storefront mid = $50/SF
    #   Unitized curtain wall: $100-$150/SF
    "concrete_wall_per_m2": 135,            # insulated metal panel, $12.50/SF mid installed
    "metal_panel_per_m2": 135,              # insulated metal panel $12.50/SF (steelbuildinginsulation.com)
    "curtain_wall_per_m2": 540,             # aluminum storefront glazing, $50/SF mid (mannleecw.com)

    # Openings
    "window_each": 650,                     # punched commercial window, installed
    "door_single": 1200,                    # hollow metal, installed
    "door_double": 2400,                    # pair, installed
    "overhead_door_each": 3500,             # 12x14 insulated

    # Roof
    "metal_roof_per_m2": 55,               # standing seam, installed

    # Soft costs (as fraction of construction subtotal)
    "design_pct": 0.06,                     # 6% of construction
    "permits_pct": 0.02,                    # 2%
    "contingency_pct": 0.10,                # 10%
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

# Conversion constants
M2_TO_SF = 10.7639104                       # 1 m^2 = 10.764 ft^2
