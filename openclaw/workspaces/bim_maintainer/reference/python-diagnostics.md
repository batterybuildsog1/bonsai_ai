# Python Diagnostics Report

Generated: 2026-03-30

## Environment Summary

| Component | Version | Path |
|-----------|---------|------|
| System Python | 3.9.6 | `/usr/bin/python3` (Xcode CLI Tools) |
| Homebrew Python | 3.12.13 | `/opt/homebrew/bin/python3.12` |
| Blender Python | 3.11.11 | `/Applications/Blender.app/Contents/Resources/4.4/python/bin/python3.11` |
| Project venv | 3.9.6 | `.venv/bin/python3` |
| System pip | 21.2.4 | `/usr/bin/pip3` (severely outdated) |
| venv pip | 21.2.4 | `.venv/bin/pip3` (severely outdated) |

## Test Results

- **System Python (no venv):** 62 tests run, 1 failure (footing eccentricity), 0 errors
- **venv with pytest:** 52 tests collected, 1 failure, **3 test modules fail to collect** due to missing `ifcopenshell`
- **Skipped by unittest discovery:** `test_schemas.py` (uses pytest-style functions, not unittest.TestCase) -- passes when run via pytest

---

## FAILURE 1: Incomplete Virtual Environment (Dependency Issue)

**Severity:** HIGH -- blocks 3 test modules and the entire IFC authoring pipeline

**Symptom:** When running tests from `.venv`, these modules fail to import:
- `tests/test_execution.py` -- `ModuleNotFoundError: No module named 'ifcopenshell'`
- `tests/test_ifc_author.py` -- `ModuleNotFoundError: No module named 'ifcopenshell'`
- `tests/test_grouped_sizing.py` -- cascading from `ifc_author.py -> ifcopenshell`

**Root cause:** The `.venv` was created from system Python 3.9.6 but only has partial dependencies installed. Missing packages:
- `ifcopenshell` (required -- IFC file operations)
- `numpy` (required by ifcopenshell and PyNiteFEA)
- `scipy` (required by PyNiteFEA)
- `PyNiteFEA` (required -- structural analysis)

These packages are installed in the **system** site-packages but not in the venv (which has `include-system-site-packages = false`).

**Why it happens:** `pip install -e ".[dev]"` fails because pip 21.2.4 does not support PEP 660 editable installs from `pyproject.toml` without a `setup.py`. The error: `"A pyproject.toml file was found, but editable mode currently requires a setuptools-based build."` Also, `pyproject.toml` has no `[project.optional-dependencies] dev` section, so there is no `[dev]` extra defined at all.

**Fix:**
```bash
cd /Users/alanknudson/Applications/Bonsai_ai
.venv/bin/python3 -m pip install --upgrade pip setuptools
.venv/bin/python3 -m pip install -e .
# Or without editable mode:
.venv/bin/python3 -m pip install ifcopenshell numpy scipy PyNiteFEA
```

Also add a `[project.optional-dependencies]` section to `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0"]
```

---

## FAILURE 2: Footing Eccentricity Test Failure (Code Bug)

**Severity:** MEDIUM -- incorrect engineering output for eccentric footings

**Symptom:** `test_starter_footing_accounts_for_eccentricity` fails:
```
AssertionError: 7.0 not greater than 7.0
```

**Root cause:** In `footing_selector.py` line 80, the `math.ceil(... * 2.0) / 2.0` rounding (round to nearest 0.5 ft) erases the eccentricity effect. For 400 kN load:
- Concentric: `sqrt(44.96) = 6.71 ft` -> rounds to **7.0 ft**
- Eccentric (e_x=0.25m, e_y=0.10m): `kern_min = 4.92 ft` which is less than 6.71, so `max(6.71, 4.92)` = 6.71 -> rounds to **7.0 ft**

The kern check only governs when eccentricity is large enough to push the kern minimum above the concentric size. With the test's inputs (400 kN, 0.25m/0.10m eccentricity), the kern minimum (4.92 ft) is well below the concentric size (6.71 ft), so eccentricity has no effect on the final size.

**Fix (in `footing_selector.py`):** Either:
1. Change the test to use a load/eccentricity combination where kern actually governs (e.g., lower load or higher eccentricity), OR
2. Add a safety factor or upsize increment when eccentricity is present, e.g.:
```python
if eccentricity_x_m or eccentricity_y_m:
    square_size_ft = max(square_size_ft, math.ceil((math.sqrt(max(required_area_ft2, 1.0)) * 1.1) * 2.0) / 2.0)
```

---

## FAILURE 3: PyNite Axis Swap (Code Bug)

**Severity:** HIGH -- produces wrong structural analysis results for asymmetric sections

**Location:** `src/bonsai_ai/pynite_backend.py` lines 492-493

**Bug:** `_section_properties()` maps:
- `ix_m4` -> `iy` (should be strong-axis, mapped to PyNite weak-axis)
- `iy_m4` -> `iz` (should be weak-axis, mapped to PyNite strong-axis)

```python
"iy": float(explicit.get("ix_m4", explicit.get("iy_m4", 0.0))),
"iz": float(explicit.get("iy_m4", explicit.get("iz_m4", 0.0))),
```

Convention: AISC uses Ix = strong axis (about X), Iy = weak axis (about Y). PyNite uses Iy = bending about member local y-axis, Iz = bending about member local z-axis. For a typical beam/column, Iy (PyNite) should map to Iy (AISC weak axis) and Iz (PyNite) should map to Ix (AISC strong axis). The current mapping is inverted.

**Impact:** For symmetric sections (HSS square tubes), this has no effect. For W-shapes (which have Ix >> Iy), this swaps the strong and weak axes, producing unconservative deflection and demand results.

**Fix:**
```python
"iy": float(explicit.get("iy_m4", 0.0)),  # weak axis
"iz": float(explicit.get("ix_m4", 0.0)),  # strong axis
```

---

## FAILURE 4: Duplicate Metadata Key in semantic_model.py (Code Bug)

**Severity:** LOW -- dead code, no runtime crash

**Location:** `bonsai_ai_core/semantic_model.py` lines 49 and 68

**Bug:** The `build_semantic_model()` return dict has two `"metadata"` keys. Python dict literals silently let the second value overwrite the first. The first metadata (lines 49-53) with only `element_count`, `assembly_count`, `root_count` is dead code. The second metadata (lines 68-75) is the one that survives, and it is a superset that also includes `role_counts`, `storey_counts`, `action_type_counts`.

**Impact:** No runtime error. The wasted computation of the first metadata block is negligible. However, this is confusing and fragile.

**Fix:** Remove the first `"metadata"` block (lines 49-53).

---

## FAILURE 5: Cold-Formed C/Z Section Records Missing (Feature Gap / Bug)

**Severity:** MEDIUM -- catalog resolution fails for secondary members

**Location:** `src/bonsai_ai/section_library.py` and `src/bonsai_ai/system_catalog.py`

**Bug:** The system catalog defines three cold-formed member families:
- `wall_girts_c` with allowed sections: C8-12ga, C8-10ga, C10-12ga, C10-10ga, C12-12ga, C12-10ga, C14-10ga
- `roof_purlins_z` with allowed sections: Z8-12ga, Z8-10ga, Z10-12ga, Z10-10ga, Z12-12ga, Z12-10ga, Z14-10ga
- `roof_purlins_c` with allowed sections: C8-12ga, C10-12ga, C12-12ga, C12-10ga, C14-10ga

None of these section names exist in `starter_section_records()`. The only records are W-shapes, HSS, and ROD. When `resolve_catalog_section()` is called for any cold-formed section, it returns `None`.

**Impact:** Any building design that includes wall girts or roof purlins will fail to resolve section properties. The catalog selector maps `panel_joint_support` -> `wall_girts_c` and `roof_edge_support` -> `roof_purlins_z`, so these roles silently get no section properties.

**Fix:** Add `CatalogSectionRecord` entries for cold-formed C and Z sections to `starter_section_records()`, using manufacturer catalog values.

---

## FAILURE 6: Bridge Server Blocking (Performance Bug)

**Severity:** MEDIUM -- blocks FastAPI event loop during design jobs

**Location:** `src/bonsai_ai_bridge/server.py` line 96, `src/bonsai_ai_bridge/orchestrator.py` line 74

**Bug:** `create_design_job()` is an `async def` FastAPI endpoint that calls `orchestrator.run_design_job()` synchronously. `run_design_job()` is a regular `def` (not async) that does heavy computation (planning, IFC authoring, structural analysis, sizing, FreeCAD handoff). This blocks the FastAPI event loop for the entire duration of the job.

**Impact:** During a design job, the server cannot respond to health checks, other API calls, or WebSocket messages. The Blender addon will time out waiting for responses.

**Fix:** Run the synchronous job in an executor:
```python
import asyncio
job = await asyncio.get_event_loop().run_in_executor(
    None, lambda: orchestrator.run_design_job(...)
)
```
Or refactor `run_design_job()` to be async.

---

## FAILURE 7: pip/setuptools Version Mismatch (Environment Issue)

**Severity:** MEDIUM -- prevents editable install

**Symptom:** `pip install -e ".[dev]"` fails with:
```
ERROR: File "setup.py" or "setup.cfg" not found. Directory cannot be installed in editable mode.
(A "pyproject.toml" file was found, but editable mode currently requires a setuptools-based build.)
```

**Root cause:** pip 21.2.4 and setuptools 58.0.4 are too old to support PEP 660 editable installs from pure `pyproject.toml` projects. This requires pip >= 21.3 and setuptools >= 64.

**Fix:**
```bash
pip install --upgrade pip setuptools
```

---

## FAILURE 8: pytest Not Available on Default Python (Environment Issue)

**Severity:** LOW -- tests can still run via unittest, or activate venv first

**Symptom:** `python3 -m pytest` fails with `No module named pytest` when run outside the venv.

**Root cause:** pytest is installed in `.venv` but not in system Python. The default `python3` is `/usr/bin/python3` (system 3.9.6), which does not have pytest. Additionally, `test_schemas.py` uses bare pytest-style functions (no TestCase class), so it is invisible to `unittest discover`.

**Fix:** Always activate the venv before running tests:
```bash
source .venv/bin/activate
pytest tests/
```

---

## FAILURE 9: Three Different Python Versions (Environment Issue)

**Severity:** LOW (currently) -- potential future compatibility issue

**Details:**
- System/venv: Python 3.9.6 (Xcode CLI Tools)
- Homebrew: Python 3.12.13
- Blender: Python 3.11.11

The project requires `>=3.9` per `pyproject.toml`. All three satisfy this, but:
- Python 3.9 is EOL (October 2025). Security patches are no longer provided.
- The Blender addon runs inside Blender's Python 3.11, which has different packages available.
- Dependencies installed in system Python 3.9 are not available to Homebrew Python 3.12 or Blender Python 3.11.

**Fix:** Consider upgrading the venv to Homebrew Python 3.12:
```bash
rm -rf .venv
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip setuptools
.venv/bin/pip install -e .
.venv/bin/pip install pytest
```

---

## Summary Table

| # | Issue | Category | Severity | Blocks Tests |
|---|-------|----------|----------|-------------|
| 1 | Incomplete venv (missing ifcopenshell, numpy, scipy, PyNiteFEA) | Dependency | HIGH | 3 modules |
| 2 | Footing eccentricity test fails (kern < concentric size) | Code bug | MEDIUM | 1 test |
| 3 | PyNite axis swap (ix_m4/iy_m4 inverted) | Code bug | HIGH | 0 (silent) |
| 4 | Duplicate metadata key in semantic_model.py | Code bug | LOW | 0 |
| 5 | Cold-formed C/Z sections missing from section_library | Code bug | MEDIUM | 0 (silent) |
| 6 | Bridge server run_design_job blocks event loop | Performance | MEDIUM | 0 |
| 7 | pip/setuptools too old for editable install | Environment | MEDIUM | 0 |
| 8 | pytest missing from system Python | Environment | LOW | 0 |
| 9 | Three Python versions (3.9, 3.11, 3.12) | Environment | LOW | 0 |
