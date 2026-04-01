# Live Construction Pricing APIs & Freight Research

**Date**: March 30, 2026
**Scope**: Programmatic pricing sources, freight/shipping cost factors, real quote structure
**Purpose**: Determine what data feeds exist for live construction material pricing and how to model freight costs in our estimating system

---

## 1. Steel Pricing APIs & Data Feeds

### 1.1 Direct APIs (Programmatic Access)

#### Metals-API (metals-api.com)
- **What it covers**: US Midwest Domestic Hot-Rolled Coil Steel (US-HRC) spot pricing, historical data back to 2019
- **Endpoints**: Latest rates, historical rates, time-series, fluctuation data
- **Update frequency**: Every 60 seconds (Silver plan+), every 10 minutes (lower tiers)
- **Pricing**: $19.99/mo (2,500 calls) to $999/mo (5M calls); annual saves ~17%
- **Limitation**: Primarily precious/base metals. HRC is available as symbol `US-HRC`, but **structural shapes (W-beams, channels, angles) are NOT individually priced** -- HRC is only a proxy for mill steel costs
- **Verdict**: Useful as a steel cost index/trend signal, not for quoting specific structural shapes

#### Zyla API Hub - HRC Steel Rates API
- **What it covers**: Real-time and historical HRC steel prices
- **Format**: REST/JSON
- **Verdict**: Similar to Metals-API; HRC only, no structural shape-specific pricing

#### MetalpriceAPI (metalpriceapi.com)
- **What it covers**: Precious metals and forex, some industrial metals
- **Verdict**: Not focused on steel; limited relevance

### 1.2 Steel Market Data Services (Subscription, Not Pure API)

#### CRU Group (crugroup.com)
- **Industry standard**: The CRU HRC Index is the settlement price for CME US Midwest HRC futures/options
- **Coverage**: Global steel prices, raw materials, regional breakdowns
- **Access**: Enterprise subscription; likely $10,000+/year. No public API documented
- **Verdict**: Gold standard for steel market intelligence, but not for lightweight API integration

#### S&P Global / Platts
- **Coverage**: 250+ steel benchmarks worldwide; daily pricing for HRC, plate, rebar, structural
- **Access**: Enterprise subscription; used as basis for contract settlement by producers, traders, consumers
- **SBB Steel Markets Daily**: Detailed daily steel price assessments
- **Verdict**: Comprehensive but enterprise-priced. Could potentially negotiate data feed access

#### Fastmarkets (formerly Metal Bulletin)
- **Coverage**: 2,000+ ferrous and non-ferrous price assessments globally
- **Note**: Acquired and discontinued the SteelBenchmarker price series (March 2019)
- **Verdict**: Major price reporting agency; enterprise tier

#### MEPS International (mepsinternational.com)
- **Coverage**: Global steel prices, indexes, forecasts for flat and long products
- **Verdict**: Another enterprise subscription source

#### Steel Market Update (steelmarketupdate.com)
- **Coverage**: US steel prices (flat-rolled, structural, plate), scrap, futures, momentum indicators
- **Interactive tools**: Price ranges, trend analysis, forward curves
- **Verdict**: Excellent US-focused data; subscription required, no documented API

### 1.3 Free/Public Data Sources

#### BLS Producer Price Index (PPI) -- FREE API
- **API endpoint**: `https://api.bls.gov/publicAPI/v2/timeSeries/data/`
- **Authentication**: v1 = no registration (25 series/query, 10-year range); v2 = free registration key (50 series/query, 20-year range)
- **Format**: POST request with JSON body; returns JSON
- **Key series IDs for construction**:
  - `PCU33231233231212` -- Fabricated structural iron/steel for commercial/residential buildings
  - `WPU10740510` -- Fabricated structural iron/steel for industrial buildings, bar joists
  - `WPU101707` -- Cold rolled steel sheet and strip
  - `PCU23622` -- Nonresidential building construction (output price)
  - `WPU101` -- Iron and steel (commodity group)
- **Update frequency**: Monthly
- **Limitation**: Index values (not dollar prices); lagging by 1-2 months
- **Verdict**: ESSENTIAL free resource for tracking cost trends and validating escalation factors. Should be integrated into our system

#### FRED (Federal Reserve Economic Data)
- **Access**: Free API with registration
- **Coverage**: Mirrors BLS PPI data plus other economic indicators
- **Series**: Same PPI codes accessible via FRED API (e.g., `PCU33231233231212`)
- **Verdict**: Alternative/complementary access to BLS data with good charting tools

#### Trading Economics
- **Coverage**: HRC Steel price history and charts (currently ~$975/metric ton as of Feb 2026)
- **API**: Available with subscription
- **Verdict**: Good for quick price checks; not free for API use

### 1.4 Mill-Published Pricing

#### Nucor Consumer Spot Price (CSP)
- **What it is**: Nucor's weekly, market-driven price for HRC spot sales
- **Recent history**:
  - May 2025: $880/ton (reduced $20/ton)
  - June 2025: $900/ton
  - Nov 2025: $895/ton (3rd consecutive weekly increase)
  - Late 2025: $950/ton held into Q1 2026
  - CSI (California Steel Industries, Nucor JV): typically $40-60/ton premium
- **Electronic access**: NOT available via public API. Published via press releases and trade media (Steel Market Update, steelindustry.news). Could be scraped but terms of service issues
- **Verdict**: Important market signal, but not directly usable as an automated feed

#### SDI (Steel Dynamics)
- Similar to Nucor; publishes price announcements through trade channels
- No public API

#### AISC Published Data
- AISC collects and averages published pricing from domestic wide-flange mills monthly
- **Access**: Full-member fabricators get quarterly reports; interactive stats at aisc.org/industrystats
- **Verdict**: Most relevant to structural steel specifically, but behind a membership wall

---

## 2. Construction Cost Database APIs

### 2.1 1build -- BEST OPTION for Live Unit Costs

- **Coverage**: 68 million live material, labor, and equipment costs for every US county (3,000+ counties)
- **API type**: GraphQL (POST to `https://gateway-external.1build.com/`)
- **Auth**: API key in `1build-api-key` HTTP header
- **Data model**:
  - `sources` query: search by location (state/county or zip/coords), category, search term
  - Returns: name, description, rates (material/labor in USD cents), production rates, CSI/NAHB classification, images
  - `categoryTreeItems`: hierarchical category browsing (free to query)
  - `sourcesBatch`: bulk retrieval up to 1,000 items by ID
- **Billing**: Per-source query (not per API call for category browsing)
- **Pricing**: Not published; contact help@1build.com
- **Coverage**: All CSI divisions, nearly every trade
- **Verdict**: STRONGEST CANDIDATE for integration. GraphQL interface is developer-friendly. Described as "Plaid for construction cost data." YC-backed. Used by CostCertified, Buildxact, STACK

### 2.2 RSMeans / Gordian

- **Coverage**: 92,000+ unit line items, 970+ locations, updated annually (30,000+ research hours/year)
- **API**: **No public API available** as of March 2026
- **Platform**: RSMeans Data Online recently migrated to Gordian Cloud Platform with AI-driven search
- **Electronic data**: Some "electronic toolset" exists for manipulating RSMeans data within an organization's environment (likely data export/bulk license)
- **Pricing**: Subscription to RSMeans Data Online (exact cost not published; typically $2,000-$5,000/year depending on tier)
- **Verdict**: Industry gold standard for unit costs but NO API integration path. Could license data for offline use. Worth contacting Gordian about custom API access for our use case

### 2.3 ENR Cost Data (Engineering News-Record)

- **Coverage**: Building material prices from 20 major US cities, 60 construction materials; Construction Cost Index (CCI) and Building Cost Index (BCI); weekly updates
- **API**: Documented as available for enterprise integration; details behind paywall
- **Access**: ENRCostData.com/purchase for plan options; supports CSV/Excel exports
- **Verdict**: Good supplementary source for material price indexes. Worth investigating API tier pricing

### 2.4 Cotality Construction API

- **Coverage**: Construction data and building approvals across the development cycle (Australia-focused)
- **Verdict**: Likely not relevant for US commercial construction; appears more focused on residential/approvals data in AU market

---

## 3. Shipping & Freight Cost Analysis

### 3.1 Structural Steel Freight

#### Flatbed Trucking Rates (2025-2026)
| Metric | Rate |
|--------|------|
| National average flatbed spot rate (March 2026) | $2.95/mile |
| Midwest average | $3.14/mile |
| West average | $2.39/mile |
| Steel-specific premium over general flatbed | +$0.20-$0.50/mile |
| Typical full truckload (FTL) capacity | 40,000-48,000 lbs (20-24 tons) |
| Typical FTL cost | ~$2,000 base + distance variable |

#### Freight Cost Calculation Model

For a **full truckload of structural steel (~20 tons)**:

| Distance | Est. Cost (at ~$3.00/mile) | Cost per Ton |
|----------|---------------------------|-------------|
| 200 miles (regional) | $600 | $30/ton |
| 500 miles | $1,500 | $75/ton |
| 1,000 miles | $3,000 | $150/ton |
| 1,400 miles (AR to SLC) | $4,200 | $210/ton |

**Per-pound conversion**: Divide per-ton by 2,000
- 200 miles: ~$0.015/lb
- 500 miles: ~$0.038/lb
- 1,000 miles: ~$0.075/lb
- 1,400 miles: ~$0.105/lb

These align with the user's initial estimate of $0.03-$0.10/lb depending on distance.

#### Key Variables
- **LTL (Less Than Truckload)**: Significantly more expensive per pound than FTL
- **Urgency**: Expedited shipping can double costs
- **Season**: Q2-Q3 construction season = higher demand = higher rates
- **Fuel surcharges**: Fluctuate with diesel prices, typically 20-30% of base rate
- **Accessorials**: Tarping ($50-$150), liftgate, residential delivery add costs

### 3.2 Concrete Delivery

#### Ready-Mix Concrete Pricing (2026)
| Component | Cost |
|-----------|------|
| Base cost (3000 PSI standard mix) | $119-$150/cubic yard |
| Standard delivery radius | 15-20 miles (included in base price) |
| Additional distance charge | $5-$10/mile beyond radius |
| Short load fee (under 3-5 yards) | $50-$150 |
| Saturday delivery surcharge | $75-$125 |
| Pump truck rental | $150-$300 |
| Delivery fee (flat) | $60-$100 |

#### Travel Distance Constraints
- **Maximum practical radius**: 60-90 minutes from batch plant
- **Standard included radius**: 15-20 miles
- **Beyond 20 miles**: $9.50-$10/mile surcharge
- **Critical constraint**: Concrete begins to set; typically must be placed within 90 minutes of batching (or 300 drum revolutions)
- **For our SLC project**: Multiple batch plants within 20-mile radius; no delivery premium expected

### 3.3 Precast Concrete Panel Delivery

| Component | Cost |
|-----------|------|
| Transportation cost per SF of panel | $2.60-$6.50/SF |
| Panel crane pick cost | $1,500-$2,500 per pick |
| Typical panel width (for flatbed transport) | 8-13 feet |
| Panel size limited by: | Weight limits, bridge clearances, crane capacity, site access |

#### Precast vs. Tilt-Up
- **Precast**: Manufactured offsite, shipped by flatbed. Transportation is a significant cost component, especially for long distances
- **Tilt-up**: Cast on-site, NO transportation cost for panels. Significant cost advantage when applicable
- **For our SLC project**: Harper Precast (53 acres, North SLC near I-15) and Olympus Precast (Bluffdale) are local options; relatively short delivery distances

---

## 4. Real Steel Quote Structure

### 4.1 Component Breakdown (per pound)

Based on 2025-2026 industry data for standard commercial construction:

| Line Item | Range ($/lb) | % of Total | Notes |
|-----------|-------------|-----------|-------|
| Raw material (mill price) | $0.40-$0.65 | 20-30% | A992 wide flange base; A913 Gr.65 adds 10-15% |
| Fabrication (shop labor) | $0.60-$1.50 | 30-40% | Simple shear tabs at low end; complex moment connections at high end |
| Detailing/shop drawings | $0.05-$0.15 | 3-5% | Often included in fabrication bid; BIM detailing may be separate |
| Coatings | $0.10-$0.40 | 5-10% | Shop primer baseline; galvanizing $0.25-$0.60/lb; intumescent $1.20-$2.00/lb |
| Freight to site | $0.02-$0.12 | 2-5% | Distance-dependent; see Section 3.1 |
| Erection (field labor) | $0.40-$0.80 | 25-35% | Bolted connections cheaper than field welding |
| **TOTAL installed** | **$1.60-$3.50** | **100%** | Simple warehouse to complex commercial |

### 4.2 Rule of Thumb
Traditional industry rule: **1/3 material, 1/3 shop labor, 1/3 erection**

This still roughly holds for standard commercial, though fabrication has grown as a share due to labor cost increases.

### 4.3 Additional Cost Items Not in Base Quote
- **CJP weld inspection (NDT)**: $200-$500 per weld
- **Overhead & profit**: 5-10% on top
- **Mobilization/demobilization**: Crane setup, rigging, scaffolding
- **Shear studs for composite deck**: Typically bid with deck, not steel
- **Miscellaneous metals**: Lintels, embed plates, loose angles -- often 10-15% of structural steel tonnage

### 4.4 Recommended Cost Model Structure

For our estimating system, each structural steel assembly should carry:

```
steel_cost = {
    "material": {
        "weight_lbs": calculated_from_BIM,
        "unit_rate_per_lb": lookup(grade, shape, market_date),
        "source": "1build_api OR manual_quote"
    },
    "fabrication": {
        "complexity_tier": "simple|standard|complex|seismic",
        "unit_rate_per_lb": lookup(complexity, region),
    },
    "detailing": {
        "rate_per_lb": 0.08,  # default; override with actual bid
    },
    "coating": {
        "type": "primer|galvanized|intumescent",
        "rate_per_lb": lookup(coating_type),
    },
    "freight": {
        "distance_miles": calculated,
        "rate_per_mile": flatbed_market_rate,
        "load_tons": min(weight / 2000, 22),  # FTL capacity cap
        "cost_per_lb": (distance * rate_per_mile) / (load_tons * 2000),
    },
    "erection": {
        "connection_type": "bolted|welded|mixed",
        "rate_per_lb": lookup(connection_type, height, region),
    }
}
```

---

## 5. SLC-Specific Analysis (5-Story, 40x25m Building)

### 5.1 Steel Supply Chain

#### Nearest Structural Steel Mills
| Mill | Location | Distance to SLC | Products |
|------|----------|----------------|----------|
| Nucor-Yamato | Blytheville, AR | ~1,400 miles | Wide flange, H-pile, channels, I-beams (2.5M ton/yr capacity) |
| SDI Structural & Rail | Columbia City, IN | ~1,700 miles | Wide flange, American Standard beams (2.6M ton/yr capacity) |
| Nucor Berkeley | Huger, SC | ~2,200 miles | Plate, sheet (not structural shapes) |

**Note**: There is NO structural shape rolling mill in the Mountain West region. All wide flange beams must ship from the eastern half of the US, making freight a significant cost factor for SLC projects.

#### Local Service Centers (SLC Metro)
| Supplier | Location | Products/Services |
|----------|---------|-------------------|
| Triple-S Steel | 1840 S 700 W, SLC | Tubing, channel, flat bar, round bar, pipe, angle |
| Brown Strauss Steel | SLC | Wide flange, HSS, channel, angle (deep inventory) |
| Wasatch Steel | SLC area | Full-service processing (bending, cutting, punching) |
| Ryerson | SLC | National distributor; broad product line |
| Metal Supermarkets | SLC | 8,000+ metal types, no minimums |
| Pacific Steel & Recycling | SLC | Regional supplier |
| Blue Star Steel | SLC | Custom structural, tanks, vessels |

**Service center markup**: Typically 15-30% over mill base for the convenience of local inventory, smaller quantities, and faster delivery. For a 5-story building project, the fabricator will likely order directly from the mill (Nucor-Yamato or SDI) for the main structural package, with service center fills for miscellaneous/urgent items.

### 5.2 Estimated Steel Freight for Our Project

Assumptions:
- Structural steel weight: ~150-200 tons for a 5-story 40x25m building
- Source: Nucor-Yamato (Blytheville, AR) -- 1,400 miles
- Truckloads needed: 8-10 (at ~20 tons/load)
- Flatbed rate: ~$3.00/mile (West region average with steel premium)

| Item | Calculation | Cost |
|------|-----------|------|
| Per-truck cost | 1,400 mi x $3.00/mi | $4,200 |
| Cost per ton | $4,200 / 20 tons | $210/ton |
| Cost per pound | $210 / 2,000 | $0.105/lb |
| Total project freight (180 tons) | 9 trucks x $4,200 | ~$37,800 |

**Freight as % of material cost**: At $0.50/lb material, freight of $0.105/lb = **21% adder** -- significant for an SLC project.

**Alternative**: If fabricator stocks or has relationships with service centers carrying wide flange in SLC, freight portion drops to ~$0.02-$0.04/lb (local delivery). But they still paid mill freight to get it to SLC initially.

### 5.3 Concrete Supply

- **Batch plants**: Multiple within SLC metro (20-mile radius); no distance surcharge expected
- **Ready-mix cost**: $125-$150/yard delivered (standard 3000-4000 PSI)
- **For a 5-story building**: Foundations, slabs on grade, and composite floor slabs will use ready-mix; structural concrete elements may be precast

### 5.4 Precast Supply

| Plant | Location | Distance from SLC Core |
|-------|----------|----------------------|
| Harper Precast | North SLC (adjacent I-15) | ~10 miles |
| Olympus Precast | Bluffdale, UT | ~20 miles |
| CONFAB Inc. | Utah (exact location varies) | Regional |
| Northwest Pipe / Geneva Precast | SLC (new 41,000 SF facility) | Local |

**Verdict**: Excellent local precast availability. Transportation costs for precast panels would be minimal ($2.60-$4.00/SF) given proximity. Tilt-up is also viable for ground-floor walls, eliminating panel transport entirely.

---

## 6. Recommended API Integration Strategy

### Tier 1: Implement Now (Free)

1. **BLS PPI API** -- Monthly construction cost indexes
   - Series: `PCU33231233231212` (fabricated structural steel, commercial/residential)
   - Use for: Escalation factors, trend validation, historical cost normalization
   - Integration: Simple POST request, JSON response, free with registration
   - Example request:
     ```json
     POST https://api.bls.gov/publicAPI/v2/timeSeries/data/
     {
       "seriesid": ["PCU33231233231212", "WPU10740510"],
       "startyear": "2024",
       "endyear": "2026",
       "registrationkey": "YOUR_KEY"
     }
     ```

2. **FRED API** -- Same PPI data with better tooling
   - Free API key from fred.stlouisfed.org
   - Useful for charting and data exploration

### Tier 2: Evaluate (Paid)

3. **1build API** -- Live unit costs by county
   - Best-in-class for granular material/labor costs
   - GraphQL interface; county-level precision
   - Contact for pricing; likely $500-$2,000/month based on usage
   - **Priority integration**: This is the closest thing to "live RSMeans via API"

4. **Metals-API** -- Steel HRC spot pricing
   - $20-$80/month for basic plans
   - Use as a market signal to adjust material cost estimates
   - Limitation: HRC only; structural shapes must be derived with a conversion factor

### Tier 3: Future (Enterprise)

5. **ENR Cost Data API** -- Weekly material prices, cost indexes
6. **CRU / Platts / Fastmarkets** -- Deep steel market intelligence
7. **RSMeans data license** -- If Gordian ever offers API access

### Freight Integration

Build an internal freight estimation module:
- Input: origin ZIP (mill/service center), destination ZIP (job site), tonnage
- Lookup: DAT Freight & Analytics publishes lane-level rates (API available)
- Calculation: `freight_per_ton = distance_miles * rate_per_mile / tons_per_truck`
- Fallback: Use the table from Section 3.1 as static lookup

---

## 7. Key Findings Summary

1. **No single API gives live structural steel prices** -- HRC spot is available (Metals-API, ~$950/ton as of Q1 2026), but structural shapes (wide flange, HSS, angles) are priced at the fabricator/service center level with mill extras, shape extras, and quantity premiums. There is no public real-time feed for W14x90 at $X/lb.

2. **1build is the best construction cost API** -- 68M data points, county-level, all CSI divisions, GraphQL. This is where we should invest integration effort.

3. **BLS PPI is free and essential** -- Monthly index data for cost escalation is available via a well-documented REST API. Series `PCU33231233231212` tracks fabricated structural steel specifically.

4. **Freight is a major SLC cost factor** -- No structural mills in the Mountain West. All wide flange ships ~1,400+ miles from Nucor-Yamato (AR) or SDI (IN), adding $150-$210/ton (~$0.08-$0.11/lb, or ~20% of material cost). Our estimating system MUST model freight explicitly, not bury it in unit rates.

5. **Concrete and precast are locally sourced** -- SLC has excellent local supply for both ready-mix (multiple batch plants within 20 mi) and precast (Harper, Olympus, Geneva/NWP all in metro). Freight is minimal for these materials.

6. **The 1/3-1/3-1/3 rule still holds** -- For standard commercial steel: ~1/3 material, ~1/3 fabrication, ~1/3 erection. Our cost model should break these out as separate line items, not lump them.

7. **Nucor CSP is the closest thing to a public steel price signal** -- Published weekly via press releases; currently ~$950/ton for HRC. Not directly API-accessible but could be monitored via news feed parsing.

---

## Sources

### Steel Pricing APIs
- [Metals-API: US-HRC Pricing](https://metals-api.com/symbols/US-HRC)
- [Metals-API Pricing Plans](https://metals-api.com/pricing)
- [Zyla API Hub: HRC Steel Rates](https://zylalabs.com/api-marketplace/finance/hrc+steel+rates+api/3902)
- [Trading Economics: HRC Steel](https://tradingeconomics.com/commodity/hrc-steel)
- [Steel Market Update: Pricing](https://www.steelmarketupdate.com/pricing-and-analysis/pricing/)
- [CRU Index Explainer (Boyd Metals)](https://blog.boydmetals.com/understanding-the-cru-index-and-steel-prices)

### Steel Market & Mill Pricing
- [Nucor CSP Price Moves (steelindustry.news)](https://steelindustry.news/nucor-steel-price-moves-what-the-latest-csp-hrc-increase-signals-for-2026-buyers/)
- [Nucor Holds $950/ton into Q1 2026](https://steelindustry.news/nucor-continues-to-hold-steel-price-at-950-ton-what-q1-2026-holds-for-steel-prices-tariffs-and-market-recovery/)
- [AISC Economics](https://www.aisc.org/economics/)
- [S&P Global / Platts: Steel](https://www.spglobal.com/energy/en/commodity/metals/ferrous/steel)
- [Fastmarkets: Steel Prices](https://www.fastmarkets.com/metals-and-mining/steel-and-steel-raw-materials/steel-prices/)
- [Ryerson: Market Intelligence](https://www.ryerson.com/metal-resources/metal-market-intelligence/are-steel-prices-coming-down)

### Construction Cost APIs
- [1build: Live Construction Cost API](https://www.1build.com/)
- [1build API Reference](https://developer.1build.com/1build-api-reference/)
- [RSMeans Data Online](https://www.rsmeans.com/)
- [RSMeans API Page](https://www.rsmeans.com/products/services/api.aspx)
- [ENR Cost Data Dashboard](https://www.enr.com/Cost-Data-Dashboard)
- [Cotality Construction API](https://www.cotality.com/au/products/construction-api)

### BLS / Government Data
- [BLS PPI Home](https://www.bls.gov/ppi/)
- [BLS Developer API](https://www.bls.gov/developers/home.htm)
- [BLS API v2 Signatures](https://www.bls.gov/developers/api_signature_v2.htm)
- [FRED: Fabricated Structural Steel PPI](https://fred.stlouisfed.org/series/PCU33231233231212)
- [FRED: Fabricated Structural Iron/Steel for Industrial Buildings](https://fred.stlouisfed.org/series/WPU10740510)
- [BLS PPI Series ID Codes](https://www.bls.gov/ppi/data-retrieval-guide/producer-price-index-commodity-data-series-id-codes.txt)

### Freight & Shipping
- [DAT Flatbed National Rates](https://www.dat.com/trendlines/flatbed/national-rates)
- [DAT Flatbed Report: Steel Output 2026](https://www.dat.com/blog/flatbed-report-steel-output-rises-to-start-2026-signaling-firmer-flatbed-freight-demand)
- [Lynx Freight: 2025 Flatbed Rates Guide](https://lynxfreight.com/2025-flatbed-trucking-rates-per-mile-a-cost-guide-for-smart-freight-planning/)
- [SteelOnTheNet: Freight Costs](https://www.steelonthenet.com/freight.html)
- [Steel Transportation (RPM Moves)](https://www.rpmmoves.com/blog/steel-transportation-how-is-steel-shipped)

### Concrete & Precast
- [Angi: Concrete Cost Per Yard 2026](https://www.angi.com/articles/how-much-does-it-cost-deliver-concrete.htm)
- [HomeGuide: Concrete Prices 2026](https://homeguide.com/costs/concrete-prices)
- [Fixr: Concrete Delivery Cost](https://www.fixr.com/costs/concrete-delivery)
- [PCI Cost Drivers of Precast](https://info.pci-ma.org/blog/cost-drivers-of-building-with-precast-concrete)
- [Harper Precast SLC](https://harperprecast.com/about/facility/)
- [Olympus Precast](https://olympusprecast.com/)

### Steel Fabrication Costs
- [Steel Construction Costs Reference](https://steelcalculator.app/reference/steel-construction-costs/)
- [SteelOnCall: Fabrication Cost Estimation](https://steeloncall.com/blog/structural-steel-fabrication-cost-estimation)
- [The Fabricator: Hidden Cost Drivers](https://www.thefabricator.com/thefabricator/article/shopmanagement/the-hidden-cost-drivers-and-overlooked-details-of-structural-steel-fabrication)

### Steel Mills & Service Centers
- [Nucor-Yamato Steel](https://nucoryamato.com/)
- [SDI Structural & Rail Division](https://www.sdisrd.com/)
- [AISC: Structural Steel Service Centers](https://www.aisc.org/globalassets/why-steel/service-center-brochure.pdf)
- [Leeco Steel: Mill vs Supplier Comparison](https://www.leecosteel.com/news/post/mill-vs-supplier-where-to-buy-steel-plate/)
- [Triple-S Steel SLC](https://www.triple-s-steel.com/utah/)
- [Ryerson SLC](https://www.ryerson.com/locations/united-states/utah/salt-lake-city)
- [Brown Strauss SLC](https://www.brownstrauss.com/locations/salt-lake-city/)
