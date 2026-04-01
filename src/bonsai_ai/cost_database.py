"""Unit cost database for concept-level building cost estimation.

US national average installed costs, 2025-2026.
Sources: RSMeans, ENR, industry averages.

These are concept-level costs for early design budgeting -- not detailed
bid pricing.  The research agent will refine these with location-specific
data when available.
"""

from __future__ import annotations

from typing import Dict

# Unit costs (USD, installed, US national average 2025-2026)
COST_DB: Dict[str, float] = {
    # Steel (fabricated + erected)
    "steel_per_kg": 2.80,                  # ~$1.27/lb -> $2.80/kg
    "steel_connection_per_joint": 450,      # per beam-column connection

    # Concrete
    "concrete_per_m3": 180,                 # ready-mix, placed, finished (~$138/CY)
    "rebar_per_kg": 2.20,                   # in-place

    # Foundation
    "footing_per_m3": 220,                  # excavate + form + rebar + concrete + backfill
    "slab_on_grade_per_m2": 65,             # 4" slab with vapor barrier

    # Envelope
    "concrete_wall_per_m2": 95,             # insulated precast/tilt-up
    "metal_panel_per_m2": 75,               # insulated metal panel
    "curtain_wall_per_m2": 450,             # aluminum + glass storefront

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

# Conversion constants
M2_TO_SF = 10.7639104                       # 1 m^2 = 10.764 ft^2
