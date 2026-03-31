# Quality Assurance Plan: Mojo + IFC-Lite Integration

## Date

2026-03-30

## Purpose

Define automated validation systems that **increase** the quality of Bonsai AI's IFC4 output as we add Mojo compute modules (tessellation, FEA, fragments) and IFC-Lite (Rust/WASM viewer parser). Each new technology layer introduces specific risk categories. This plan addresses them with concrete checks, tooling, tolerances, and CI integration.

## Risk Map

| Module | Risk | Severity | Detection Difficulty |
|--------|------|----------|---------------------|
| Mojo Tessellation | Wrong vertex positions, flipped normals, non-manifold geometry, inter-element gaps | High | Medium (automated mesh checks) |
| Mojo FEA | Numerical drift, incorrect boundary conditions, wrong stress recovery, axis swaps | Critical | Hard (requires analytical reference solutions) |
| IFC-Lite | Different IFC interpretation than IfcOpenShell, missing property sets, wrong spatial structure | High | Medium (cross-parser comparison) |
| Pre-computed Fragments | Stale cache, coordinate system mismatch, incomplete element coverage | Medium | Easy (hash-based invalidation) |

---

## 1. Geometry Validation (Mojo Tessellation)

### 1.1 Per-Element Mesh Checks

Run these checks on every tessellated element output from `bonsai_tessellate.so` before writing to fragments or GLB.

| Check | Method | Tool | Tolerance | Fail Action |
|-------|--------|------|-----------|-------------|
| Watertight | Every edge shared by exactly 2 faces | trimesh `is_watertight` | Exact | Block output |
| Manifold | No non-manifold edges or vertices | trimesh `is_watertight` + edge check | Exact | Block output |
| Consistent winding | All face normals point outward, CCW order | trimesh `is_winding_consistent` | Exact | Auto-repair via `trimesh.repair.fix_winding()`, then re-check |
| Degenerate triangles | No zero-area faces | `trimesh.Trimesh.area_faces > epsilon` | area > 1e-10 m^2 | Block output |
| Vertex count | Expected count per element type (box=24, beam=24, etc.) | Assertion | Exact | Block output |
| Index bounds | All indices < vertex count, no negative indices | Array bounds check | Exact | Block output |
| Volume positive | Signed volume > 0 (correct normal orientation) | `trimesh.Trimesh.volume` | > 0 | Auto-repair normals, re-check |
| Bounding box match | Tessellated bbox matches IFC geometric parameters within tolerance | Compare against `(length, width, height)` from IFC metadata | +/- 0.5mm | Warn if > 0.5mm, block if > 2mm |

### 1.2 Inter-Element Checks (Assembly Level)

Run after tessellating all elements in a building model.

| Check | Method | Tolerance |
|-------|--------|-----------|
| Gap detection | For connected elements (beam-to-column, slab-to-beam), verify shared vertices exist within tolerance | 1mm gap tolerance |
| Overlap detection | Check that distinct elements do not interpenetrate beyond tolerance (BIM hard clash threshold) | 3mm overlap tolerance |
| Normal consistency at interfaces | Adjacent element faces at shared surfaces have opposing normals | Dot product < -0.95 |
| Total building volume | Sum of element volumes should approximately match expected gross volume from plan | +/- 5% |
| Floor slab coverage | Horizontal projection of slab elements covers the expected floor area | > 95% of planned area |

### 1.3 Mesh Quality Metrics (Tracked Per Build)

| Metric | Target | Acceptable | Definition |
|--------|--------|------------|------------|
| Minimum face angle | > 30 deg | > 15 deg | Smallest interior angle across all triangles |
| Aspect ratio | < 5:1 | < 10:1 | Longest edge / shortest edge per triangle |
| Element count accuracy | 100% | 100% | All plan elements produce tessellation output |
| Vertex stride | 24 bytes | 24 bytes | Interleaved [x,y,z, nx,ny,nz] Float32 per the spec |

### 1.4 Implementation

```python
# tests/test_tessellation_quality.py
import trimesh
import numpy as np

def validate_element_mesh(vertices: np.ndarray, indices: np.ndarray,
                          expected_bbox: dict) -> list[str]:
    """Validate a single tessellated element. Returns list of errors (empty = pass)."""
    errors = []

    # Reshape from interleaved [x,y,z,nx,ny,nz] to positions and normals
    positions = vertices.reshape(-1, 6)[:, :3]
    normals = vertices.reshape(-1, 6)[:, 3:]
    faces = indices.reshape(-1, 3)

    mesh = trimesh.Trimesh(vertices=positions, faces=faces,
                           vertex_normals=normals, process=False)

    if not mesh.is_watertight:
        errors.append("FAIL: mesh is not watertight")
    if not mesh.is_winding_consistent:
        errors.append("FAIL: inconsistent face winding")
    if mesh.volume < 0:
        errors.append("FAIL: negative volume (inverted normals)")

    zero_area = mesh.area_faces < 1e-10
    if zero_area.any():
        errors.append(f"FAIL: {zero_area.sum()} degenerate triangles")

    # Bounding box comparison
    actual_size = mesh.bounding_box.extents
    for axis, key in enumerate(["length", "width", "height"]):
        if key in expected_bbox:
            diff = abs(actual_size[axis] - expected_bbox[key])
            if diff > 0.002:  # 2mm
                errors.append(f"FAIL: bbox {key} off by {diff*1000:.1f}mm")
            elif diff > 0.0005:  # 0.5mm
                errors.append(f"WARN: bbox {key} off by {diff*1000:.1f}mm")

    # Mesh quality
    angles = mesh.face_angles_sparse
    if angles is not None:
        min_angle_deg = np.degrees(angles.data.min()) if angles.nnz > 0 else 0
        if min_angle_deg < 15:
            errors.append(f"FAIL: minimum angle {min_angle_deg:.1f} deg (< 15)")
        elif min_angle_deg < 30:
            errors.append(f"WARN: minimum angle {min_angle_deg:.1f} deg (< 30)")

    return errors
```

### 1.5 Libraries

| Library | Purpose | Install |
|---------|---------|---------|
| **trimesh** (4.x) | Watertight check, volume, winding, area, bounding box | `pip install trimesh` |
| **PyMeshLab** | Advanced mesh repair, Hausdorff distance, normal re-orientation | `pip install pymeshlab` |
| **numpy** | Vertex/index array operations | Already in stack |

---

## 2. FEA Validation (Mojo FEA)

### 2.1 Benchmark Problem Suite

Every Mojo FEA build must pass these analytical reference problems before deployment. These follow NAFEMS and textbook standards.

#### Tier 1: Exact Analytical Solutions

| Problem | Geometry | Load | Analytical Result | Source |
|---------|----------|------|-------------------|--------|
| **Cantilever beam, end load** | L=3m, W12x26 | P=10kN at tip | delta = PL^3/(3EI) = 0.4827mm, M_max = PL = 30 kN-m | Timoshenko beam theory |
| **Simply supported beam, UDL** | L=6m, W14x30 | w=5kN/m | delta = 5wL^4/(384EI) = 3.218mm, M_max = wL^2/8 = 22.5 kN-m | Euler-Bernoulli |
| **Axial bar** | L=2m, A=0.01m^2, E=200GPa | P=100kN | delta = PL/(AE) = 0.1mm, stress = P/A = 10 MPa | Direct |
| **Portal frame, lateral load** | H=4m, L=6m, fixed base | H=20kN at beam level | Compare reactions, moments to matrix stiffness method solution | Matrix structural analysis |
| **Column under compression** | L=3m, W8x31, fixed-free | P=500kN | Euler buckling check: P_cr = pi^2*EI/(KL)^2, deflection under axial + self-weight | Euler |

Tolerance: all results within **0.1%** of analytical solution.

#### Tier 2: Patch Tests (Element Formulation Verification)

| Test | Purpose | Pass Criterion |
|------|---------|----------------|
| Constant strain patch (beam) | Verify uniform axial strain under uniform axial load | Strain exactly constant across all elements |
| Constant strain patch (quad) | Verify uniform membrane strain on irregular quad mesh | Stress field matches analytical within machine precision |
| Rigid body mode | Zero applied load, arbitrary displacement | Zero strain energy, zero internal forces |
| Single element test | Compare one-element results to hand calculation | Exact match to stiffness matrix theory |

#### Tier 3: Convergence Tests

| Test | Method | Pass Criterion |
|------|--------|----------------|
| h-refinement | Double mesh density for cantilever beam, verify monotonic convergence | Error decreases with each refinement |
| Stress recovery accuracy | Compare nodal stress averaging to element stress | Smooth stress field, no spurious oscillation |

### 2.2 Numerical Quality Checks (Runtime)

Run these checks on every Mojo FEA analysis result.

| Check | Formula | Tolerance | Action on Fail |
|-------|---------|-----------|----------------|
| **Equilibrium** | sum(reactions) - sum(applied_loads) = 0 | < 0.01% of total load | Block result, report imbalance |
| **Residual norm** | \|\|Ku - f\|\| / \|\|f\|\| | < 1e-8 | Warn at 1e-6, block at 1e-4 |
| **Energy balance** | External work W_ext = Internal strain energy U_int | \|W_ext - U_int\| / W_ext < 0.01% | Block result |
| **Positive-definite stiffness** | All eigenvalues of K > 0 (after support application) | No negative eigenvalues | Block: indicates mechanism or instability |
| **Condition number** | cond(K) = lambda_max / lambda_min | < 1e12 | Warn at 1e10, block at 1e14 (ill-conditioned) |
| **Displacement sanity** | max_displacement < L/50 for serviceability | Element-specific limits | Warn (may indicate modeling error) |
| **Reaction sign consistency** | Vertical reactions positive for gravity loads | All R_z > 0 for dead + live | Warn (uplift may be real, but flag for review) |

### 2.3 Cross-Validation: Mojo vs PyNite

During the transition period, run **both** solvers and compare.

| Metric | Tolerance | Notes |
|--------|-----------|-------|
| Max displacement | +/- 0.1% | Both use the same stiffness formulation |
| Support reactions (per node) | +/- 0.1% | Different factorization methods may cause small differences |
| Member forces (axial, shear, moment) | +/- 0.5% | Stress recovery from different post-processing |
| Unity check ratios | +/- 1% | Accumulated from force differences |

Procedure:
1. Run PyNite on the analytical model (existing path)
2. Run Mojo FEA on the same analytical model
3. Compare all outputs with tolerances above
4. Log discrepancies to `quality_report.json`
5. Block deployment if any metric exceeds tolerance

### 2.4 Known Issue: Axis Swap

The existing PyNite backend has a known bug where `_section_properties()` maps `ix_m4` to `iy` and `iy_m4` to `iz` (see `improvement-backlog.md`). The Mojo FEA module must:
1. Use the **correct** axis convention from the start
2. Document which convention is used (local x = member axis, local y = major bending, local z = minor bending)
3. Include a specific benchmark test for asymmetric sections (W-shapes, C-channels) that would fail if axes are swapped

### 2.5 Implementation Sketch

```python
# tests/test_fea_benchmarks.py
import pytest
import numpy as np

# Analytical solutions
CANTILEVER_BENCHMARKS = {
    "tip_deflection_mm": lambda P, L, E, I: (P * L**3) / (3 * E * I) * 1000,
    "max_moment_kNm": lambda P, L, E, I: P * L,
    "max_shear_kN": lambda P, L, E, I: P,
}

class TestFEABenchmarks:
    def test_cantilever_tip_load(self, mojo_fea_solver):
        """Cantilever beam with end point load - Timoshenko reference."""
        P, L, E, I = 10e3, 3.0, 200e9, 8.44e-5  # W12x26
        result = mojo_fea_solver.analyze(cantilever_model(P, L, E, I))

        expected_delta = CANTILEVER_BENCHMARKS["tip_deflection_mm"](P, L, E, I)
        actual_delta = result.max_displacement_mm

        assert abs(actual_delta - expected_delta) / expected_delta < 0.001, \
            f"Tip deflection: expected {expected_delta:.4f}mm, got {actual_delta:.4f}mm"

    def test_equilibrium_check(self, mojo_fea_solver):
        """Verify sum of reactions equals sum of applied loads."""
        result = mojo_fea_solver.analyze(simple_beam_udl())
        total_applied = result.total_applied_load_kN
        total_reactions = sum(r.Fz for r in result.reactions)
        imbalance = abs(total_applied - total_reactions) / abs(total_applied)
        assert imbalance < 1e-6, f"Equilibrium imbalance: {imbalance:.2e}"

    def test_energy_balance(self, mojo_fea_solver):
        """External work must equal internal strain energy."""
        result = mojo_fea_solver.analyze(portal_frame_lateral())
        ratio = abs(result.external_work - result.strain_energy) / result.external_work
        assert ratio < 1e-4, f"Energy imbalance: {ratio:.2e}"
```

---

## 3. IFC Compliance Validation

### 3.1 Schema-Level Validation

| Check | Tool | When | Pass Criterion |
|-------|------|------|----------------|
| STEP syntax | `ifcopenshell.validate` | Every IFC file save | Zero syntax errors |
| IFC4 schema conformance | `ifcopenshell.validate` | Every IFC file save | All entity attributes correct type and cardinality |
| Entity abstractness | `ifcopenshell.validate` | Every IFC file save | No abstract entities instantiated |
| Property set completeness | Custom check | Every IFC file save | All elements have `Pset_BonsaiAI` with required keys |
| Spatial containment | Custom check | Every IFC file save | All IfcElement subtypes contained in an IfcBuildingStorey |

### 3.2 Semantic-Level Validation

| Check | Method | Pass Criterion |
|-------|--------|----------------|
| Every element has a storey | Walk `IfcRelContainedInSpatialStructure` | 100% elements contained |
| Spatial hierarchy complete | Project > Site > Building > Storey chain exists | All 4 levels present |
| No orphan geometry | Every `IfcShapeRepresentation` is referenced by a product | Zero orphans |
| Property completeness | Required Pset_BonsaiAI keys present per element type | See table below |
| Material assignment | Every structural element has an `IfcRelAssociatesMaterial` | 100% for columns, beams, walls |
| Unit consistency | All geometric values in meters, forces in Newtons | Verify IfcSIUnit declarations |
| GlobalId uniqueness | No duplicate GlobalId values | Zero duplicates |

#### Required Pset_BonsaiAI Keys by Element Type

| Element Type | Required Keys |
|-------------|---------------|
| IfcSlab | structural_kind, material_ref, thickness |
| IfcWall | structural_kind, material_ref, height, thickness |
| IfcColumn | structural_kind, material_ref, section_ref, width, depth |
| IfcBeam | structural_kind, material_ref, section_ref, width, depth |
| IfcPlate | structural_kind, orientation |
| IfcFooting | structural_kind, bearing_capacity_kpa |
| IfcDoor | host_wall |
| IfcWindow | host_wall, sill_height |
| IfcCurtainWall | panel_count |

### 3.3 IFC-Lite Cross-Validation

Verify that IFC-Lite (Rust/WASM) interprets the same IFC file identically to IfcOpenShell.

| Check | Method | Tolerance |
|-------|--------|-----------|
| Entity count | Parse with both, compare `by_type()` counts for all types | Exact match |
| Property set values | Read all Pset_BonsaiAI values from both parsers, compare | Exact string match |
| Spatial tree structure | Extract containment hierarchy from both, compare as tree | Exact structure match |
| Geometric placement | Read `IfcLocalPlacement` transforms from both, compare matrices | < 1e-6 per matrix element |
| Element geometry bounds | Compute bounding box from both geometry engines, compare | < 0.5mm per axis |

Implementation:

```python
# tests/test_ifc_cross_validation.py
def test_parser_agreement(ifc_path):
    """IFC-Lite and IfcOpenShell must produce identical interpretations."""
    ios_model = ifcopenshell.open(ifc_path)
    lite_model = ifc_lite.parse(ifc_path)  # WASM via Node.js bridge or native

    # Entity counts
    for ifc_type in ["IfcWall", "IfcColumn", "IfcBeam", "IfcSlab", "IfcPlate",
                     "IfcDoor", "IfcWindow", "IfcFooting", "IfcCurtainWall"]:
        ios_count = len(ios_model.by_type(ifc_type))
        lite_count = lite_model.count(ifc_type)
        assert ios_count == lite_count, \
            f"{ifc_type}: IfcOpenShell={ios_count}, IFC-Lite={lite_count}"

    # Property set values
    for element in ios_model.by_type("IfcProduct"):
        ios_psets = get_psets(element)
        lite_psets = lite_model.get_psets(element.GlobalId)
        if "Pset_BonsaiAI" in ios_psets:
            for key, value in ios_psets["Pset_BonsaiAI"].items():
                assert str(value) == str(lite_psets.get("Pset_BonsaiAI", {}).get(key)), \
                    f"Pset mismatch on {element.Name}.{key}"
```

### 3.4 External Validation

Periodically (monthly or before releases), submit generated IFC files to the buildingSMART Validation Service (https://validation.buildingsmart.org/) and record the results. Target: zero schema violations, zero normative rule violations.

---

## 4. Fragment Cache Integrity

### 4.1 Cache Invalidation

| Check | Method | When |
|-------|--------|------|
| Model hash match | SHA-256 of IFC file must match the hash stored in fragment metadata | Fragment load time |
| Timestamp check | Fragment file mtime must be >= IFC file mtime | Fragment load time |
| Element count match | Number of fragment entries must equal number of IFC products | Fragment load time |
| Coordinate system | Fragment header must declare the same coordinate system as the IFC file (SI meters, Z-up) | Fragment creation + load |

### 4.2 Fragment Completeness

| Check | Method | Pass Criterion |
|-------|--------|----------------|
| All elements present | Cross-reference fragment element IDs against IFC GlobalIds | 100% coverage |
| No stale entries | No fragment entries for elements deleted from the model | Zero orphan fragments |
| Geometry matches | Sample 10% of elements, compare fragment vertex positions to re-tessellated output | < 0.1mm deviation |

### 4.3 Implementation

```python
# src/bonsai_ai/fragment_validator.py
import hashlib
from pathlib import Path

def validate_fragments(ifc_path: Path, fragment_path: Path) -> list[str]:
    """Validate fragment cache against source IFC. Returns errors."""
    errors = []

    # Hash check
    ifc_hash = hashlib.sha256(ifc_path.read_bytes()).hexdigest()
    fragment_meta = read_fragment_header(fragment_path)
    if fragment_meta.get("source_hash") != ifc_hash:
        errors.append(f"STALE: fragment hash {fragment_meta.get('source_hash')[:12]} "
                      f"!= IFC hash {ifc_hash[:12]}")

    # Timestamp check
    if fragment_path.stat().st_mtime < ifc_path.stat().st_mtime:
        errors.append("STALE: fragment older than IFC file")

    # Element count
    ifc_element_count = count_ifc_products(ifc_path)
    fragment_count = fragment_meta.get("element_count", 0)
    if ifc_element_count != fragment_count:
        errors.append(f"COUNT: IFC has {ifc_element_count} elements, "
                      f"fragments has {fragment_count}")

    return errors
```

---

## 5. Cross-Validation: Mojo Tessellation vs IfcOpenShell Geometry

### 5.1 Hausdorff Distance Comparison

For each element, compare the tessellated mesh from Mojo against the tessellated mesh from IfcOpenShell's geometry kernel (OpenCASCADE).

| Metric | Tool | Tolerance | Notes |
|--------|------|-----------|-------|
| Hausdorff distance | PyMeshLab `hausdorff_distance` or trimesh + scipy | < 0.5mm | Maximum surface deviation between the two meshes |
| Volume difference | `abs(vol_mojo - vol_ios) / vol_ios` | < 0.1% | Volumes should be nearly identical |
| Surface area difference | `abs(area_mojo - area_ios) / area_ios` | < 0.5% | Less strict than volume (tessellation creates slightly different triangle decompositions) |
| Vertex count ratio | `count_mojo / count_ios` | 0.5x to 2.0x | Mojo may use fewer or more triangles; topology need not match |

### 5.2 BIM-Specific Tolerances

Based on industry practice and buildingSMART guidance:

| Context | Tolerance | Rationale |
|---------|-----------|-----------|
| Structural geometry (member lengths, positions) | 1mm | Steel fabrication tolerance per AISC Code of Standard Practice |
| Architectural geometry (wall positions, slab edges) | 5mm | Construction tolerance for concrete/masonry |
| Rendering (visual display) | 10mm | Imperceptible at building scale |
| Clash detection (hard clash) | 0-3mm | Industry standard BIM coordination threshold |
| Clash detection (soft clash / clearance) | 25-100mm | Depends on component type and access needs |

For Mojo tessellation, we target the **structural** tolerance: vertices within 1mm of the IfcOpenShell reference for all structural elements.

### 5.3 Test Matrix

Run the cross-validation on every element type at multiple scales.

| Element | Small | Medium | Large |
|---------|-------|--------|-------|
| Column | 0.3x0.3x3m | 0.5x0.5x5m | 1.0x1.0x8m |
| Beam | 0.2x0.3x3m | 0.3x0.5x8m | 0.5x0.8x15m |
| Wall | 3x3x0.2m | 8x4x0.25m | 20x5x0.3m |
| Slab | 5x5x0.15m | 12x12x0.2m | 30x30x0.25m |
| Footing | 1x1x0.3m | 2x2x0.5m | 4x4x0.8m |
| Curtain wall (multi-panel) | 3x3m, 1x1m panels | 10x4m, 1.5x1.2m panels | 20x6m, 2x1.5m panels |

For each case: generate IFC via IfcAuthor, tessellate with both Mojo and IfcOpenShell, compute Hausdorff distance and volume difference.

---

## 6. Regression Testing

### 6.1 Golden File Testing

Maintain a set of known-good reference outputs. On every CI run, regenerate these outputs and compare.

#### Golden Files to Maintain

| File | Content | Comparison Method |
|------|---------|-------------------|
| `golden/techridge_shell.ifc` | Full pipeline output for the techridge benchmark building | Byte-identical after stripping timestamps and GlobalIds |
| `golden/techridge_solver_result.json` | FEA results for techridge | JSON deep-equal with 0.1% numeric tolerance |
| `golden/techridge_tessellation.bin` | Mojo tessellation output | Binary-equal (deterministic output) |
| `golden/techridge_fragments.bin` | Pre-computed fragments | Binary-equal |
| `golden/simple_beam_fea.json` | Cantilever benchmark FEA result | JSON deep-equal with 0.01% tolerance |
| `golden/box_building_ifc_summary.json` | Entity counts, storey list, pset keys for a standard box building | JSON exact match |

#### Comparison Logic

```python
# tests/conftest.py
import json
import math

def json_approx_equal(a, b, rel_tol=0.001):
    """Deep comparison of JSON-like structures with numeric tolerance."""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(json_approx_equal(a[k], b[k], rel_tol) for k in a)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(json_approx_equal(ai, bi, rel_tol) for ai, bi in zip(a, b))
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == 0 and b == 0:
            return True
        return math.isclose(a, b, rel_tol=rel_tol)
    else:
        return a == b
```

### 6.2 Visual Regression Testing

For the viewer (IFC-Lite + WebGPU), capture screenshots and compare.

| View | Camera Position | Resolution | Diff Threshold |
|------|----------------|------------|----------------|
| Front elevation | (0, -50, 10) looking at (0,0,5) | 1920x1080 | < 0.5% pixel diff |
| Plan view | (0, 0, 100) looking down | 1920x1080 | < 0.5% pixel diff |
| 3D perspective | (30, -30, 20) looking at origin | 1920x1080 | < 1% pixel diff |
| Detail: beam-column joint | Close-up on a specific connection | 800x600 | < 0.5% pixel diff |

Tool: Playwright MCP screenshot capture with pixel-by-pixel comparison using a perceptual diff algorithm (SSIM or pixelmatch). Anti-aliasing differences excluded via threshold.

### 6.3 Property-Based Testing

Use Hypothesis to generate random valid buildings and verify invariants.

```python
# tests/test_property_based.py
from hypothesis import given, strategies as st, settings

@given(
    n_columns=st.integers(min_value=2, max_value=20),
    n_beams=st.integers(min_value=1, max_value=30),
    n_stories=st.integers(min_value=1, max_value=5),
    bay_width=st.floats(min_value=3.0, max_value=15.0),
    story_height=st.floats(min_value=2.5, max_value=5.0),
)
@settings(max_examples=50, deadline=30000)
def test_building_invariants(n_columns, n_beams, n_stories, bay_width, story_height):
    """Any valid building must satisfy these invariants."""
    plan = generate_random_building(n_columns, n_beams, n_stories,
                                    bay_width, story_height)
    ifc_path = execute_plan(plan)
    model = ifcopenshell.open(ifc_path)

    # Invariant 1: spatial containment is complete
    all_elements = model.by_type("IfcElement")
    contained = set()
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        for elem in rel.RelatedElements:
            contained.add(elem.id())
    assert len(contained) == len(all_elements), \
        f"{len(all_elements) - len(contained)} orphan elements"

    # Invariant 2: no duplicate GlobalIds
    gids = [e.GlobalId for e in all_elements]
    assert len(gids) == len(set(gids)), "Duplicate GlobalIds found"

    # Invariant 3: all structural elements have metadata
    for elem in model.by_type("IfcColumn") + model.by_type("IfcBeam"):
        psets = get_psets(elem)
        assert "Pset_BonsaiAI" in psets, f"{elem.Name} missing Pset_BonsaiAI"
        assert "structural_kind" in psets["Pset_BonsaiAI"], \
            f"{elem.Name} missing structural_kind"

    # Invariant 4: storey elevations are monotonically increasing
    storeys = sorted(model.by_type("IfcBuildingStorey"),
                     key=lambda s: s.Elevation or 0)
    elevations = [s.Elevation for s in storeys]
    for i in range(1, len(elevations)):
        assert elevations[i] > elevations[i-1], \
            f"Non-monotonic storey elevations: {elevations}"

    # Invariant 5: if FEA runs, equilibrium holds
    if n_columns >= 4 and n_beams >= 2:
        fea_result = run_fea(plan)
        if fea_result.success:
            applied = fea_result.total_applied_vertical_kN
            reactions = fea_result.total_vertical_reaction_kN
            assert abs(applied - reactions) / abs(applied) < 0.001
```

---

## 7. Quality Dashboard

### 7.1 Metrics to Track

#### Geometry Metrics (per build)

| Metric | Source | Target | Alert Threshold |
|--------|--------|--------|-----------------|
| Watertight rate | Tessellation validator | 100% | < 100% |
| Mean Hausdorff distance (Mojo vs IOS) | Cross-validator | < 0.1mm | > 0.5mm |
| Max Hausdorff distance | Cross-validator | < 0.5mm | > 1.0mm |
| Volume agreement rate | Cross-validator | 100% within 0.1% | Any > 0.5% |
| Degenerate triangle count | Tessellation validator | 0 | > 0 |
| Minimum face angle (worst element) | Tessellation validator | > 30 deg | < 15 deg |

#### FEA Metrics (per analysis run)

| Metric | Source | Target | Alert Threshold |
|--------|--------|--------|-----------------|
| Equilibrium error | Runtime check | < 0.001% | > 0.01% |
| Residual norm | Runtime check | < 1e-8 | > 1e-6 |
| Energy balance error | Runtime check | < 0.01% | > 0.1% |
| Condition number | Runtime check | < 1e10 | > 1e12 |
| Benchmark pass rate | CI benchmark suite | 100% | < 100% |
| Max Mojo vs PyNite displacement diff | Cross-validation | < 0.1% | > 0.5% |
| Max unity check diff (Mojo vs PyNite) | Cross-validation | < 1% | > 5% |

#### IFC Metrics (per model)

| Metric | Source | Target | Alert Threshold |
|--------|--------|--------|-----------------|
| Schema validation errors | `ifcopenshell.validate` | 0 | > 0 |
| Spatial containment coverage | Custom check | 100% | < 100% |
| Property completeness rate | Custom check | 100% of required keys | < 95% |
| IfcOpenShell vs IFC-Lite entity count agreement | Cross-validation | 100% | < 100% |
| IfcOpenShell vs IFC-Lite pset agreement | Cross-validation | 100% | < 100% |
| GlobalId uniqueness | Custom check | 100% | < 100% |

#### Pipeline Metrics (per run)

| Metric | Source | Target | Alert Threshold |
|--------|--------|--------|-----------------|
| Golden file pass rate | CI regression suite | 100% | < 100% |
| Fragment cache hit rate | Fragment validator | > 90% (warm runs) | < 50% |
| Fragment staleness incidents | Fragment validator | 0 per week | > 0 |
| Visual regression diff | Screenshot comparison | < 0.5% | > 1% |
| Total test pass rate | pytest | 100% | < 100% |

### 7.2 Dashboard Implementation

Write metrics to a `quality_metrics.json` file after each pipeline run. Structure:

```json
{
  "timestamp": "2026-03-30T15:30:00Z",
  "model": "techridge_initial_shell",
  "geometry": {
    "watertight_rate": 1.0,
    "mean_hausdorff_mm": 0.03,
    "max_hausdorff_mm": 0.12,
    "degenerate_triangles": 0,
    "min_face_angle_deg": 42.3
  },
  "fea": {
    "equilibrium_error": 2.1e-9,
    "residual_norm": 3.4e-10,
    "energy_balance_error": 1.2e-8,
    "condition_number": 4.5e7,
    "benchmark_pass_rate": 1.0,
    "mojo_vs_pynite_max_displacement_diff": 0.0003
  },
  "ifc": {
    "schema_errors": 0,
    "spatial_containment_rate": 1.0,
    "property_completeness_rate": 1.0,
    "globalid_unique": true,
    "parser_agreement_rate": 1.0
  },
  "pipeline": {
    "golden_file_pass_rate": 1.0,
    "fragment_cache_valid": true,
    "visual_regression_max_diff": 0.002,
    "total_tests_passed": 147,
    "total_tests_run": 147
  }
}
```

Track metrics over time in a JSONL append-only log: `quality_metrics.jsonl`. Visualize trends in the web viewer dashboard.

---

## 8. CI Integration

### 8.1 Test Tiers and Execution Strategy

| Tier | Tests | Run When | Duration Target | Block Merge? |
|------|-------|----------|----------------|--------------|
| **T0: Smoke** | IFC schema validation, basic tessellation checks, FEA benchmark (cantilever only) | Every commit | < 30s | Yes |
| **T1: Core** | All FEA benchmarks, all element tessellation checks, IFC property completeness, golden file comparison | Every PR | < 5min | Yes |
| **T2: Cross-validation** | Mojo vs IfcOpenShell geometry, Mojo vs PyNite FEA, IfcOpenShell vs IFC-Lite parsing | Daily + before release | < 30min | Yes (for releases) |
| **T3: Property-based** | Hypothesis-generated random buildings (50 examples) | Weekly + before release | < 60min | No (advisory) |
| **T4: Visual** | Screenshot regression for all standard views | Before release | < 15min | No (advisory, manual review) |

### 8.2 Failure Response Matrix

| Failure Type | Severity | Response |
|-------------|----------|----------|
| FEA benchmark fails | Critical | Block all deployments. Root-cause immediately. |
| Equilibrium check fails | Critical | Block analysis results. Do not serve to users. |
| Watertight check fails | High | Block fragment generation for that element. Fallback to IfcOpenShell tessellation. |
| IFC schema validation fails | High | Block IFC file delivery. Fix before save. |
| Golden file mismatch | Medium | Review diff. If intentional improvement, update golden file. If regression, fix. |
| Hausdorff distance > 1mm | Medium | Log warning. Investigate root cause. Do not block unless > 2mm. |
| Visual regression > 1% | Low | Manual review. May be acceptable rendering change. |
| Property-based test finds violation | Medium | Add as specific regression test. Fix root cause. |

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Before Mojo FEA Ships)

- [ ] Add `ifcopenshell.validate` call to every IFC save in `ifc_author.py` -- blocks saves with schema errors
- [ ] Add spatial containment check to IFC save path
- [ ] Add GlobalId uniqueness check
- [ ] Create FEA benchmark test suite (5 problems from Section 2.1 Tier 1) against PyNite
- [ ] Add equilibrium check to existing `PyNiteSolverBackend._build_summary()`
- [ ] Create golden files for techridge model
- [ ] Add `quality_metrics.json` output to results bundle

### Phase 2: Mojo Tessellation QA (Ships With Tessellation Module)

- [ ] Implement `validate_element_mesh()` function from Section 1.4
- [ ] Add trimesh to project dependencies
- [ ] Create cross-validation harness (Mojo vs IfcOpenShell) from Section 5
- [ ] Run Hausdorff distance comparison on all element types at 3 scales
- [ ] Add tessellation quality metrics to `quality_metrics.json`
- [ ] Create CI T0/T1 test configuration

### Phase 3: Mojo FEA QA (Ships With FEA Module)

- [ ] Port FEA benchmark suite to test against Mojo FEA
- [ ] Implement all runtime numerical checks from Section 2.2
- [ ] Create dual-solver cross-validation harness (Mojo vs PyNite)
- [ ] Add energy balance and residual norm to FEA result output
- [ ] Fix axis swap bug in PyNite backend (so cross-validation has a correct reference)
- [ ] Add condition number monitoring

### Phase 4: IFC-Lite QA (Ships With Viewer Integration)

- [ ] Create cross-parser test harness (IfcOpenShell vs IFC-Lite) from Section 3.3
- [ ] Test on 10+ real-world IFC files from the pipeline
- [ ] Add fragment cache validation from Section 4
- [ ] Implement visual regression testing with Playwright
- [ ] Submit models to buildingSMART Validation Service, record results

### Phase 5: Continuous Quality (Ongoing)

- [ ] Add property-based testing with Hypothesis
- [ ] Set up quality metrics trending in viewer dashboard
- [ ] Monthly buildingSMART validation submission
- [ ] Quarterly review of tolerance thresholds (tighten as confidence grows)
- [ ] Add new golden files for each new building type the pipeline produces

---

## 10. Dependencies

| Package | Version | Purpose | New? |
|---------|---------|---------|------|
| trimesh | >= 4.0 | Mesh quality validation | Yes |
| pymeshlab | >= 2023.12 | Hausdorff distance, advanced mesh repair | Yes |
| hypothesis | >= 6.0 | Property-based testing | Yes |
| ifcopenshell | >= 0.8 | IFC schema validation (existing) | No |
| pytest | >= 8.0 | Test framework (existing) | No |
| numpy | >= 2.0 | Array operations (existing) | No |
| pixelmatch | via Playwright | Visual regression screenshot comparison | Yes (viewer only) |

---

## 11. Success Criteria

The quality assurance system achieves its goal of **increasing** quality (not just maintaining it) when:

1. **Mojo tessellation** produces meshes with Hausdorff distance < 0.5mm from IfcOpenShell geometry AND all meshes are watertight -- a property not currently guaranteed by IfcOpenShell's tessellation
2. **Mojo FEA** passes all NAFEMS-style benchmarks within 0.1% AND the axis swap bug is fixed (improving accuracy over current PyNite for asymmetric sections)
3. **IFC-Lite** achieves 100% property set agreement with IfcOpenShell, catching any existing IFC authoring bugs through the cross-validation process
4. **Fragment cache** has zero staleness incidents through hash-based invalidation, eliminating a class of bugs that currently has no protection
5. **Property-based testing** discovers and fixes invariant violations that hand-written tests miss
6. **Equilibrium and energy balance checks** catch solver errors before they reach users -- a check that the current PyNite path does not perform
7. **All quality metrics trend toward tighter tolerances** over time, measured quarterly

---

## References

- [trimesh documentation](https://trimesh.org/)
- [PyMeshLab GitHub](https://github.com/cnr-isti-vclab/PyMeshLab)
- [buildingSMART IFC Validation Service](https://www.buildingsmart.org/users/services/validation-service/)
- [buildingSMART Validation Service Documentation](https://buildingsmart.github.io/validate/)
- [IfcOpenShell validate module](https://docs.ifcopenshell.org/autoapi/ifcopenshell/validate/index.html)
- [NAFEMS Standard Benchmarks](https://www.nafems.org/publications/resource_center/p18/)
- [NAFEMS Linear Static Benchmarks Volume 1](https://www.nafems.org/publications/browse_buy/browse_by_topic/linear/p07/)
- [FEA Patch Test (Wikipedia)](https://en.wikipedia.org/wiki/Patch_test_(finite_elements))
- [FEA Verification and Validation (control.com)](https://control.com/technical-articles/validation-and-verification-in-finite-element-analysis-fea/)
- [AutoCalcs 3D FEA Solver Verification](https://autocalcs.com/fea-verification)
- [MechanicalC 2D FEA Validation](https://mechanicalc.com/calculators/finite-element-analysis/validation)
- [Hausdorff Distance Between Meshes (Guthe 2005)](https://cg.cs.uni-bonn.de/backend/v1/files/publications/guthe-2005-fast.pdf)
- [IFC Spatial Containment Specification](https://standards.buildingsmart.org/IFC/DEV/IFC4_2/FINAL/HTML/link/spatial-containment.htm)
- [Common IFC Export Mistakes (BIM Corner)](https://bimcorner.com/10-common-ifc-export-mistakes-to-avoid-part-2/)
- [Top 5 BIM Checks Using IDS (Data Octopus)](https://dataoctopus.net/blog-top-5-most-useful-bim-checks-using-information-delivery-specification-ids)
- [Hypothesis Property-Based Testing Library](https://github.com/HypothesisWorks/hypothesis)
- [ANSYS Mesh Quality Metrics](https://www.mechead.com/mesh-quality-checking-ansys-workbench/)
