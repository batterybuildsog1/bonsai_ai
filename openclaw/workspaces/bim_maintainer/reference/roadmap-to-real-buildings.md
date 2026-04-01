# Roadmap: From Generic Spec to Shareable Real Building

> Date: 2026-03-30
> Status: Planning -- no code changes
> Depends on: spec-first-design.md, BuildingGenerator (working), system_catalog.py, section_library.py, footing_selector.py, viewer infrastructure

---

## Where We Are

The BuildingGenerator produces geometrically correct IFC models from a declarative spec:
- Grid-aligned columns, beams, slabs, walls
- Windows per bay, curtain wall panels, doors
- 415+ elements for a 5-story building in 0.75 seconds
- Zero coordinate errors

But the output is GENERIC:
- All columns are 0.3x0.3m rectangles (`IfcRectangleProfileDef`)
- All beams are 0.3x0.5m rectangles (`IfcRectangleProfileDef`)
- No footings under columns
- No site, no ground plane, no landscaping
- Viewer shows the structure but lacks presentation polish

---

## Feature 1: Correctly Sized Steel Members

### What Exists

The codebase already has a complete sizing pipeline:

| Module | Role | Status |
|---|---|---|
| `system_catalog.py` | Defines allowed sections per role (W10x33..W18x86 for columns, W12x26..W27x84 for beams, HSS for braces/facade posts) | Complete |
| `section_library.py` | 24 AISC section records with full properties (area, Ix, Iy, J, depths, flange/web thicknesses) | Complete |
| `catalog_selector.py` | Maps structural roles to catalog families via `ROLE_TO_SELECTION` dict | Complete |
| `catalog_resolver.py` | Resolves catalog family + section name to a `SectionSpec` with metric dimensions | Complete |
| `grouped_sizing.py` | Iterative solve-evaluate-advance loop: runs FEA, checks demand ratios, upsizes groups that fail | Complete |
| `plan_roundtrip.py` | Writes sized section dimensions back into the physical model plan | Complete |
| `structural_source.py` | Builds `StructuralSourceModel` from a physical model's action list | Complete |

### The Gap

The existing pipeline operates on the action-based physical model (`PhysicalModelSpec` with `plan.actions[]`). The `BuildingGenerator` bypasses this entirely -- it calls `IfcAuthor` directly without producing a `PhysicalModelSpec` or `StructuralSourceModel`. The two systems do not currently talk to each other.

### What Needs to Happen

**Option A: Shortcut -- catalog lookup without FEA** (recommended for first pass)

The spec already has `column_section` and `beam_section` fields with "auto" as the default. When the spec says "W12x40" explicitly, the generator can look up the section dimensions from `section_library.py` and use them directly. For "auto", it can pick a reasonable default from the catalog (e.g., middle of the allowed range for the building height).

Steps:
1. Add a `_resolve_section_dims(role, section_name)` method to `BuildingGenerator` that calls `resolve_catalog_section()` from `section_library.py`.
2. When `section_name` is "auto", select based on building height/bay span heuristics (e.g., 5-story office with 8m bays -> W14x68 columns, W21x44 beams).
3. Replace the flat `column_size` and `beam_size` tuples with the resolved section's `width_m` and `depth_m`.

This changes the GEOMETRY immediately -- columns go from 0.3x0.3m to W14 proportions (0.254m x 0.356m).

**Option B: Full pipeline -- FEA-driven sizing**

Wire the BuildingGenerator output into the structural analysis pipeline:
1. After `BuildingGenerator.generate()`, build a `StructuralSourceModel` from the IFC (reverse of what `structural_source.py` does from the action plan).
2. Run `catalog_selector.apply_catalog_selection()` to assign sizing groups.
3. Run `grouped_sizing.GroupedSectionSizer.size()` which iteratively solves with PyNite, evaluates demand ratios, and advances section choices.
4. Apply the final sections back to the IFC model.

This produces ENGINEERED sections but requires FEA and the full pipeline to be wired.

**IFC Profile Question: Answered**

Currently, `ifc_author.py` creates `IfcRectangleProfileDef` for both columns and beams (lines 474 and 547). IfcOpenShell fully supports `IfcIShapeProfileDef` (for W-shapes) and `IfcRectangleHollowProfileDef` (for HSS). To render I-beams correctly:
1. Add a method to `IfcAuthor` that creates the appropriate profile type based on `shape_family` (W -> `IfcIShapeProfileDef`, HSS -> `IfcRectangleHollowProfileDef`, ROD -> `IfcCircleProfileDef`).
2. Pass `depth`, `width`, `tf` (flange thickness), `tw` (web thickness) from the `CatalogSectionRecord`.
3. The web-ifc viewer (Three.js) already handles these profile types -- the mesh generation in `web-ifc` supports all standard IFC profiles.

### Effort and Priority

| Sub-task | Effort | Depends On |
|---|---|---|
| A1. Section lookup for explicit named sections ("W12x40") | 2-3 hours | Nothing new |
| A2. Heuristic auto-sizing (no FEA) | 3-4 hours | A1 |
| A3. IfcIShapeProfileDef / IfcRectangleHollowProfileDef support in IfcAuthor | 4-6 hours | A1 |
| B1. StructuralSourceModel builder from IFC (not from action plan) | 1-2 days | Understanding of structural_source.py |
| B2. Wire grouped_sizing into post-generation step | 1 day | B1 |
| B3. Write sized sections back to IFC | 4-6 hours | B2, plan_roundtrip.py adaptation |

**Recommendation**: Do A1 + A2 + A3 first. This gives visually correct steel profiles in the viewer within a day. Wire up full FEA sizing (B1-B3) as a separate follow-up when precision matters.

---

## Feature 2: Correctly Detailed Footings

### What Exists

| Module | Role | Status |
|---|---|---|
| `footing_selector.py` | Sizes spread footings from imposed loads. Computes pad size, thickness, rebar schedule. Uses `starter_footing_from_imposed_load()` for individual footings and `build_starter_footing_summary()` for the full model. | Complete |
| `ifc_author.py` `create_footing()` | Creates `IfcFooting` entities with rectangular pad geometry, metadata for bearing pressure, rebar, concrete strength | Complete |
| `system_catalog.py` | Defines footing families: interior_spread, perimeter_retaining, pedestal_on_spread, grade_beam_tie | Complete |
| Spec schema | Has a `foundation` section with type, bearing_elevation, soil_bearing_kpa, include_grade_beams | Defined in spec-first-design.md |

### The Gap

The `BuildingGenerator` does not generate footings at all. The spec-first-design.md describes a `_generate_foundations()` method, but it is not implemented in the current `building_generator.py`.

The footing_selector needs column loads as input. In the full pipeline, these come from FEA support reactions (`build_starter_footing_summary` reads `analysis_result.summary.support_target_reactions`). Without FEA, we need estimated loads.

### What Needs to Happen

**Step 1: Gravity load estimation (no FEA)**

Estimate column loads from the building spec using tributary area and assumed floor loads:
- Tributary area per column = `spacing_x * spacing_y` (interior), half that for edge, quarter for corner
- Dead load: slab self-weight (~4.8 kPa for 0.2m concrete) + superimposed dead (~1.0 kPa)
- Live load: per program type (office ~2.4 kPa, retail ~4.8 kPa, parking ~2.4 kPa)
- Factored load per floor = tributary_area * (1.2*DL + 1.6*LL) for strength, or service = DL + LL for bearing
- Cumulative: multiply by number of stories above

This is a simple calculation, no FEA needed. The footing_selector already takes `imposed_load_kn` directly.

**Step 2: Add `_generate_foundations()` to BuildingGenerator**

For each ground-floor column position:
1. Compute estimated service load (tributary area * stories * load per floor)
2. Call `starter_footing_from_imposed_load()` to get pad size and thickness
3. Call `self.author.create_footing()` with the sized dimensions
4. Place at `bearing_elevation` from the spec (default -1.2m)

For perimeter columns, use `perimeter_spread_footing` family. For interior, use `interior_spread_footing`.

Optionally, if `include_grade_beams` is true, add beams connecting perimeter footings.

**Step 3: Later -- FEA-driven footing sizing**

Once Feature 1 Option B is complete, `build_starter_footing_summary()` can use actual support reactions instead of estimated gravity loads. This is a drop-in replacement for Step 1.

### Effort and Priority

| Sub-task | Effort | Depends On |
|---|---|---|
| F1. Gravity load estimator from building spec | 3-4 hours | Nothing |
| F2. `_generate_foundations()` in BuildingGenerator | 3-4 hours | F1 |
| F3. Grade beams between perimeter footings | 2-3 hours | F2 |
| F4. FEA-driven footing sizing integration | 4-6 hours | Feature 1 Option B |

**Recommendation**: F1 + F2 first. Estimated gravity loads are fine for concept-level footing sizing -- the `footing_selector.py` basis notes already call it "starter sizing until geotech-specific design is available." Grade beams (F3) are nice-to-have.

---

## Feature 3: Landscaping and Site

### What Exists

Nothing in the codebase generates landscaping or site elements. The IFC model has an `IfcSite` entity (created by `IfcAuthor.ensure_project()`), but it has no geometry.

### IFC Entities for Site and Landscaping

| Element | IFC Entity | Notes |
|---|---|---|
| Ground plane | `IfcSite` with `IfcShapeRepresentation` (slab-like geometry) | Standard approach. Most viewers render IfcSite geometry. |
| Parking lot | `IfcSlab` assigned to site, or `IfcPavement` (IFC4.3) | Use IfcSlab with PredefinedType="FLOOR" for compatibility |
| Sidewalks | `IfcSlab` with distinct material | Same approach as parking |
| Curbs | `IfcWall` or `IfcBuildingElementProxy` at low height | Simple extruded rectangle |
| Trees | `IfcGeographicElement` (IFC4) or `IfcBuildingElementProxy` | Simplified geometry: cylinder trunk + cone/sphere canopy |
| Bollards | `IfcBuildingElementProxy` | Cylinder geometry |
| Light poles | `IfcBuildingElementProxy` | Cylinder + sphere |
| Property boundary | `IfcSite` property set, or polyline representation | Metadata, not geometry |

### What a First Pass Looks Like

A `SiteGenerator` class, separate from `BuildingGenerator`, that takes the building footprint and spec and generates:

1. **Ground plane**: A large slab at z=0 extending beyond the building footprint (e.g., 2x the footprint area). Green-ish material assignment for grass.
2. **Parking lot**: Rectangular slab on one side of the building. Gray material.
3. **Sidewalks**: Strips along building perimeter and from parking to entries. Lighter gray.
4. **Trees**: Simplified geometry at regular intervals along property edges and in landscape islands. Each tree = one cylinder (trunk) + one cone or sphere (canopy) composed into an `IfcGeographicElement`.
5. **Entry approach**: A wider sidewalk section leading to the main entry door.

### Spec Extension

Add a `site` key to the building spec:

```json
{
  "site": {
    "setback_m": 15,
    "parking": {
      "side": "east",
      "spaces": 40,
      "drive_aisle_width": 7.0
    },
    "landscaping": {
      "tree_spacing_m": 8,
      "tree_locations": ["perimeter", "parking_islands"]
    },
    "sidewalks": {
      "width_m": 1.8,
      "faces": ["south", "west"]
    }
  }
}
```

### Viewer Considerations

- `web-ifc` renders all geometry regardless of IFC class, so `IfcGeographicElement` and `IfcBuildingElementProxy` will show up automatically.
- The viewer's `IFC_TYPE_COLORS` map (in `app.js`) needs entries for `IfcGeographicElement` and ground-plane elements to avoid them all being the default accent color.
- Trees and site elements should have lower opacity or distinct colors to not visually compete with the building.

### Should This Be Separate from BuildingGenerator?

Yes. The `SiteGenerator` should be a separate class that:
- Takes the building footprint and entry locations as input
- Writes to the same IFC file (same `IfcAuthor` instance)
- Assigns site elements to the `IfcSite` container (not to building storeys)
- Can be called after `BuildingGenerator.generate()` completes

This keeps the BuildingGenerator focused on the structure and allows the site to be optional.

### Effort and Priority

| Sub-task | Effort | Depends On |
|---|---|---|
| S1. Ground plane + site boundary | 2-3 hours | Nothing |
| S2. Parking lot geometry | 3-4 hours | S1 |
| S3. Sidewalks from entries to parking/street | 3-4 hours | S1 |
| S4. Simplified tree geometry (cylinder + cone) | 4-6 hours | S1 |
| S5. Viewer color mapping for site elements | 1-2 hours | S1 |
| S6. Site spec schema extension | 2-3 hours | S1 |
| S7. Bollards, light poles, curbs | 3-4 hours | S1 (nice-to-have) |

**Recommendation**: S1 + S5 first -- a green ground plane immediately makes the scene look like a real building instead of floating geometry. Then S3 + S2 for the hardscape. Trees (S4) are high visual impact but more geometry work.

---

## Feature 4: Shareable Building Scene

### What Exists

| Component | Status |
|---|---|
| Web viewer (Three.js + web-ifc) | Working. Loads IFC, renders geometry, click-to-select, element inspector. |
| Cloudflare tunnel | Scripts exist (`start-tunnel.sh`, `setup-cloudflare-tunnel.sh`, `TUNNEL-SETUP.md`). |
| Chat panel | Working. HTTP proxy to Claude API for in-viewer questions. |
| Element inspector | Working. Shows IFC properties, storey membership, type information. |

### What's Missing for a Good Presentation

**Camera presets**: The viewer opens with a default `camera.position.set(20, 15, 20)` which works for small models but is too close for a 5-story building at 40x25m. Need:
- Auto-fit on model load (the `fitAll()` function exists but may need the bounding box to include site elements)
- Named presets: "3/4 perspective" (default), "south elevation", "east elevation", "plan view from above", "entry approach"
- Smooth animated transitions between presets

**Section cuts**: The viewer toolbar has a section cut button (line 42: `root.querySelector('[data-tool="section"]')?.addEventListener("click", () => {})`) but the handler is empty. Need:
- Horizontal section cut at any floor elevation (shows plan view of that level)
- Vertical section cut through the building (shows the steel frame, footings, slabs in profile)
- Three.js clipping planes are the standard approach

**Annotations/dimensions**: Not in the viewer currently. For a shareable scene, key dimensions should be visible:
- Building overall dimensions (length x width x height)
- Bay spacing annotations on the grid
- Floor-to-floor heights on a section cut
- These can be Three.js `CSS2DObject` labels or line+text sprites

**Visual polish**:
- Ground shadows (shadow map is enabled but may need tuning for building scale)
- Material colors that distinguish steel, concrete, glass meaningfully
- Edge outlines for structural members (important for seeing I-beam profiles)
- Background gradient instead of flat dark color

**Sharing mechanics**:
- Cloudflare tunnel already exists for remote access
- Add a "share" button that copies the tunnel URL
- Consider pre-rendering a static screenshot for link previews (Open Graph image)
- Mobile-friendly viewport (OrbitControls with touch)

### Effort and Priority

| Sub-task | Effort | Depends On |
|---|---|---|
| V1. Camera auto-fit for full scene (building + site) | 2-3 hours | Nothing |
| V2. Named camera presets with smooth transitions | 3-4 hours | V1 |
| V3. Section cut implementation (clipping planes) | 4-6 hours | Nothing |
| V4. Dimension annotations (CSS2DObject labels) | 4-6 hours | Nothing |
| V5. Material color refinement + edge outlines | 3-4 hours | Feature 1 (I-beam profiles) |
| V6. Share button + Open Graph preview | 2-3 hours | Tunnel working |
| V7. Mobile touch support | 2-3 hours | Nothing |

**Recommendation**: V1 + V2 first -- camera presets are the highest-impact presentation feature. Then V3 for section cuts which reveal the interior structure. V5 depends on having real steel profiles (Feature 1) to look meaningful.

---

## Recommended Build Order

### Phase 1: Real Steel + Footings (1-2 days)

Makes the model structurally meaningful.

```
A1. Section lookup for named sections     [2-3h]  -> immediate
A2. Heuristic auto-sizing                 [3-4h]  -> after A1
A3. I-shape + HSS profile support in IFC  [4-6h]  -> after A1
F1. Gravity load estimator                [3-4h]  -> immediate (parallel with A1-A3)
F2. Foundation generator                  [3-4h]  -> after F1
```

End state: Building with W14x68 columns (I-shaped!), W21x44 beams, HSS braces, and correctly-sized spread footings at -1.2m. The viewer shows I-beam cross-sections instead of rectangles.

### Phase 2: Site and Ground (0.5-1 day)

Makes the model look like a real building in context.

```
S1. Ground plane                          [2-3h]  -> immediate
S5. Viewer colors for site elements       [1-2h]  -> after S1
S3. Sidewalks                             [3-4h]  -> after S1
S2. Parking lot                           [3-4h]  -> after S1 (parallel with S3)
```

End state: Building sits on a green ground plane with sidewalks and a parking area. No longer floating in a void.

### Phase 3: Viewer Polish (0.5-1 day)

Makes the scene presentable to a team.

```
V1. Camera auto-fit                       [2-3h]  -> immediate
V2. Camera presets                        [3-4h]  -> after V1
V5. Material colors + edge outlines       [3-4h]  -> after Phase 1
V3. Section cuts                          [4-6h]  -> after V1
```

End state: Viewers can orbit a well-lit building, jump to named views, and cut through the structure to see the frame.

### Phase 4: Full Engineering Pipeline (2-3 days, optional)

Connects to FEA for real sizing. Only needed when precision matters.

```
B1. StructuralSourceModel from IFC        [1-2d]  -> after Phase 1
B2. Wire grouped sizing                   [1d]    -> after B1
B3. Write sized sections back to IFC      [4-6h]  -> after B2
F4. FEA-driven footing sizing             [4-6h]  -> after B2
```

End state: Every member is sized by actual FEA demand ratios. Footings use support reactions instead of estimated gravity loads.

### Phase 5: Trees and Extras (0.5-1 day, nice-to-have)

```
S4. Tree geometry                         [4-6h]
S7. Bollards, light poles, curbs          [3-4h]
V4. Dimension annotations                 [4-6h]
V6. Share button + OG preview             [2-3h]
```

---

## Total Effort Summary

| Phase | Effort | Value |
|---|---|---|
| Phase 1: Real Steel + Footings | 1-2 days | HIGH -- transforms generic boxes into recognizable structural steel |
| Phase 2: Site and Ground | 0.5-1 day | HIGH -- context makes it look real |
| Phase 3: Viewer Polish | 0.5-1 day | MEDIUM -- presentation quality for sharing |
| Phase 4: Full FEA Pipeline | 2-3 days | MEDIUM -- engineering accuracy (can defer) |
| Phase 5: Trees and Extras | 0.5-1 day | LOW -- visual polish |
| **Total** | **5-8 days** | |

Phases 1-3 (3-4 days) deliver a shareable building scene with correctly proportioned steel, footings, site context, and a polished viewer. Phase 4 adds engineering rigor. Phase 5 is aesthetic.

---

## Key Technical Decisions to Make Before Building

1. **Profile types**: Should `IfcAuthor.create_column()` and `create_beam()` gain a `profile_type` parameter, or should a new method `create_steel_member()` handle all profile types? (Recommendation: add `profile_type` to existing methods for backward compatibility.)

2. **Section resolution**: Should the `BuildingGenerator` resolve sections at generation time (bake the dimensions into the IFC), or store section names as metadata and resolve later? (Recommendation: resolve at generation time -- the IFC should be self-contained.)

3. **Site generator coupling**: Should `SiteGenerator` take the same spec dict as `BuildingGenerator`, or its own separate spec? (Recommendation: same spec with an optional `site` section. One spec, one model.)

4. **Footing placement coordinate**: Should footings be centered on the column, or should the column origin be at the footing center? (Recommendation: footing centered on column grid intersection, offset by half the footing dimension in x and y.)
