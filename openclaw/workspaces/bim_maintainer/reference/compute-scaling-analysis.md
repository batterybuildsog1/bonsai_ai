# Compute Scaling Analysis: How Bottlenecks Shift as BIM Models Grow

**Date:** 2026-03-30
**Question:** "As our models get bigger, does compute get more important?"
**Short answer:** Yes, but not yet. The crossover is around 2,000-5,000 DOF (~500-1,000 structural elements). Below that, AI planning dominates. Above that, FEA compute takes over. You are about to enter the transition zone with the 5-story office building.

---

## 1. How Real Buildings Scale

### Element counts by building type

| Building type | Structural elements | Total BIM elements | DOF (structural) | IFC file size |
|--------------|--------------------:|-------------------:|------------------:|--------------:|
| 2-story house | 30-80 | 200-500 | 100-300 | 1-5 MB |
| 5-story office (next project) | 400-800 | 2,000-5,000 | 1,500-4,000 | 10-40 MB |
| 20-story tower | 3,000-8,000 | 15,000-40,000 | 15,000-40,000 | 80-300 MB |
| Hospital/campus | 10,000-50,000 | 50,000-200,000 | 50,000-200,000+ | 200 MB - 1+ GB |

**How the numbers are derived:**

A 5-story office building with a 6x4 column grid at 7.5m spacing:
- Columns: 24 per floor x 5 floors = **120 columns**
- Primary beams: ~30 per floor x 5 = **150 beams**
- Secondary beams: ~40 per floor x 5 = **200 beams**
- Slabs: 1 per floor x 5 = **5 slabs** (or ~20-30 slab panels if modeled as plates)
- Bracing/lateral: ~20-40 members
- **Total structural: ~500-550 elements**
- Envelope (walls, curtain walls): ~200
- Openings (windows, doors): ~300
- Stairs, elevators, misc: ~100
- **Total BIM elements: ~1,100-1,500** (structural discipline only could be ~500)
- **DOF: ~550 elements x 6 DOF/node x 2 nodes/element, minus shared nodes ~ 2,000-3,500**

For Revit, typical project file sizes range from 150-500 MB (a 40,000 sq ft building averages ~150 MB). Hospital projects regularly produce 500 MB - 1 GB+ files. Revit's rule of thumb: your RAM should be 20x your .rvt file size.

IFC structural-only files are much smaller than full Revit files because they contain less geometry detail. A structural-only IFC for a 5-story office would be ~10-30 MB.

### DOF scaling math

Each beam/column element has 2 nodes, each node has 6 DOF (3 translations + 3 rotations). After merging shared nodes at connections:

- N elements with ~60% node sharing: DOF ~ N * 12 * 0.4 = ~5N
- 100 elements -> ~500 DOF
- 500 elements -> ~2,500 DOF
- 5,000 elements -> ~25,000 DOF
- 50,000 elements -> ~250,000 DOF

For plate/shell elements (slabs, walls), DOF grows faster because each element has 4+ nodes.

---

## 2. Pipeline Bottleneck Map by Scale

### Current timing breakdown (measured, 200 elements / ~800 DOF)

```
AI Planner:          15 s    (36%)   <- DOMINANT
Grouped Sizing:      20 s    (49%)
  - FEA solve x4-5:  12-15 s
  - deepcopy/rebuild:  5-8 s
IFC Authoring:        2 s    (5%)
Analysis Export:       1 s    (2%)
Everything else:      3 s    (7%)
Total:              ~41 s
```

### Projected timing at each scale

The table below projects how each stage scales. Measured values are marked with an asterisk.

| Stage | Scaling behavior | 200 elem / 800 DOF* | 500 elem / 2,500 DOF | 5,000 elem / 25,000 DOF | 50,000 elem / 250,000 DOF |
|-------|-----------------|----:|----:|----:|----:|
| **AI Planner** | O(rounds x prompt_size). Scales with complexity, not element count directly. More complex buildings need more rounds, larger prompts. | 15 s | 20-40 s | 60-120 s | 300+ s (need templates) |
| **FEA factorization (dense)** | O(n^3) where n = DOF | 0.05 s* | 1-3 s | 500-1500 s | impossible |
| **FEA factorization (sparse, CHOLMOD)** | O(n^1.2-1.5) for banded structures | 0.01 s | 0.05-0.2 s | 1-5 s | 20-120 s |
| **FEA assembly** | O(elements) -- linear, small constant | 0.01 s | 0.03 s | 0.3 s | 3 s |
| **FEA back-substitution (per combo)** | O(n^2) dense, O(n) sparse | 0.001 s | 0.005 s | 0.05 s | 0.5 s |
| **IFC authoring** | O(elements), IfcOpenShell C++ core | 0.5 s | 1-2 s | 10-20 s | 60-180 s |
| **IFC file parsing** | ~20 MB/s for IfcOpenShell | N/A (gen only) | <1 s | 2-5 s | 10-60 s |
| **Structural source model** | O(elements), pure Python | 0.2 s | 0.5 s | 5 s | 50 s |
| **JSON serialization** | O(elements), json.dumps | 0.1 s | 0.3 s | 3 s | 30 s |
| **deepcopy per sizing iteration** | O(elements), Python GC pressure | 0.5 s | 1-3 s | 10-30 s | 100+ s |
| **Memory (Python process)** | ~1 KB per element + model overhead | ~50 MB | ~100 MB | ~500 MB - 1 GB | 5-10 GB |
| **Web viewer (browser)** | GPU memory + JS heap | smooth | smooth | needs optimization | needs streaming/LOD |

### The crossover points

```
    100        500      2,000     10,000     50,000    250,000  DOF
     |          |         |          |          |          |
     |  AI PLANNER DOMINATES         |          |          |
     |  (network-bound, 90%+)        |          |          |
     |          |         |          |          |          |
     |          |    TRANSITION      |          |          |
     |          |    (AI + FEA       |          |          |
     |          |     both matter)   |          |          |
     |          |         |          |          |          |
     |          |         |    FEA COMPUTE DOMINATES      |
     |          |         |    (O(n^3) dense explodes)    |
     |          |         |          |          |          |
     |          |         |          |    SPARSE SOLVER    |
     |          |         |          |    REQUIRED         |
     |          |         |          |    (dense impossible)|
     |          |         |          |          |          |
     |          |         |          |          |   MEMORY  |
     |          |         |          |          |   WALL    |
     |          |         |          |          |          |
```

**Key crossover points:**

1. **~500 DOF:** FEA factorization starts being noticeable (>10ms per solve), but AI planner still dominates at 15+ seconds.

2. **~2,000 DOF (current sweet spot):** FEA factorization takes ~50ms (dense) or ~10ms (sparse). Factor-once-solve-many becomes critical -- without it, 20 load combos at 50ms each = 1s; with it, 50ms + 20 x 5ms = 150ms. **This is where the 15.5x factor-once optimization matters.**

3. **~5,000 DOF (5-story office):** Dense Cholesky takes ~1-3 seconds. Still manageable for a single solve, but grouped sizing with 4-8 iterations x 5 solves = 20-120 seconds of FEA alone. **FEA compute becomes co-dominant with AI planning.** Sparse solver gives 10-50x advantage.

4. **~25,000 DOF (20-story tower):** Dense Cholesky takes 500-1500 seconds -- effectively impossible. **Sparse solver is mandatory.** CHOLMOD handles this in 1-5 seconds. The bottleneck shifts to FEA assembly (seconds) and IFC authoring (10-20 seconds).

5. **~100,000+ DOF (hospital/campus):** Even CHOLMOD takes 20-120 seconds. Need iterative solvers (multigrid, preconditioned conjugate gradient) or domain decomposition. Python's memory usage becomes a concern (5-10 GB for model data). **This is beyond our near-term scope.**

---

## 3. When Each Optimization Matters

### Optimization impact by scale

| Optimization | Speedup | Current (200 elem) | 5-story (500 elem) | 20-story (5,000 elem) | Hospital (50,000 elem) |
|-------------|---------|:---:|:---:|:---:|:---:|
| **Prompt caching** (2-5x on rounds 2+) | AI rounds | Saves 5-10 s | Saves 10-25 s | Saves 30-60 s | Saves 100+ s |
| **Smart replanning** (12 rounds -> 3) | AI rounds | Saves 30-45 s | Saves 40-60 s | Critical | Essential |
| **Template system** (skip AI for common patterns) | AI rounds | Nice-to-have | Important | Critical | Essential |
| **Factor-once FEA** (15.5x) | FEA solve | Saves 0.7 s* | Saves 10-40 s | Saves minutes | Saves hours |
| **Sparse solver** (CHOLMOD) | FEA solve | No benefit | 5-10x | **Mandatory** | **Mandatory** |
| **MLX GPU matmul** (55x at 2000x2000) | FEA factorize | No benefit (too small) | Marginal | 3-10x | 5-20x |
| **Numba assembly** (10-50x on loop) | FEA assembly | Saves <1 ms | Saves 10-50 ms | Saves 1-5 s | Saves 10-50 s |
| **Eliminate redundant computation** (30-50%) | Pipeline | Saves 10-15 s | Saves 15-25 s | Saves minutes | Saves minutes |
| **Replace deepcopy** | Sizing loop | Saves 2-4 s | Saves 5-15 s | Saves 30-120 s | Impractical without fix |
| **orjson** (5-10x JSON) | Serialization | Saves <0.5 s | Saves 1-2 s | Saves 10-20 s | Saves 50+ s |
| **Mojo tessellation** (21x) | Geometry | Saves 6 ms | Saves 15 ms | Saves 150 ms | Saves 1.5 s |
| **Rust IFC parsing** | IFC I/O | N/A (gen only) | Saves <1 s | Saves 2-5 s | Saves 30-120 s |
| **Batch IFC authoring** | IFC write | Saves <1 s | Saves 1-2 s | Saves 5-15 s | Saves 30-100 s |
| **Pipeline caching** (60-70%) | All stages | Saves 20-28 s | Saves 30-50 s | Saves minutes | Saves minutes |
| **Browser streaming/LOD** | Viewer | Not needed | Not needed | Recommended | **Required** |

### What matters NOW vs NEXT vs LATER

**NOW (current 200-element models):**
The AI planner is 90%+ of wall time. Compute optimizations save single-digit seconds on a 41-second pipeline. The right priorities are:
1. Prompt caching (trivial effort, 2-5x on planner)
2. Smart replanning (reduce 12 rounds to 3)
3. Eliminate redundant computation (30-50% pipeline savings)
4. Factor-once FEA (already built, just needs integration)

**NEXT (5-story office, 500 elements):**
FEA becomes co-dominant. The priorities shift:
1. Factor-once FEA integration -- now saves 10-40 seconds, not just 0.7 s
2. Sparse solver (CHOLMOD via scikit-sparse) -- insurance for upper bound of DOF range
3. Replace deepcopy with incremental updates -- sizing loop becomes painful
4. Template system for repetitive elements (column grids, floor plates)

**LATER (20-story tower, 5,000+ elements):**
Compute dominates. Language-level optimizations start to matter:
1. Sparse solver is mandatory (dense is impossible)
2. Rust/PyO3 FEA module or Numba-compiled assembly
3. MLX GPU for factorization
4. IFC batch authoring or Rust IFC generation
5. Browser needs streaming/LOD/tiling

---

## 4. Deep Dive: FEA Solver Scaling

### Dense vs Sparse Cholesky -- the math

**Dense Cholesky** (scipy.linalg.cho_factor):
- Complexity: O(n^3 / 3) where n = DOF
- Memory: O(n^2) -- stores full dense matrix
- At 2,000 DOF: ~48 ms (measured)
- At 5,000 DOF: ~750 ms (projected, cubic scaling from measurement)
- At 10,000 DOF: ~6 s
- At 25,000 DOF: ~94 s
- At 50,000 DOF: ~750 s (12.5 minutes)

**Sparse Cholesky** (CHOLMOD via scikit-sparse):
- Complexity: O(n * bw^2) where bw = bandwidth, typically O(n^1.2-1.5) for well-ordered structural meshes
- Memory: O(n * bw) -- stores only non-zero fill
- A beam frame with N elements has bandwidth ~ sqrt(N) when optimally ordered
- At 2,000 DOF: ~5-10 ms
- At 5,000 DOF: ~20-80 ms
- At 25,000 DOF: ~0.5-3 s
- At 100,000 DOF: ~5-30 s
- At 250,000 DOF: ~20-120 s

**The crossover:** For typical structural frame problems, sparse becomes faster than dense at roughly 500-1,000 DOF. Below that, the overhead of sparse data structures and symbolic analysis exceeds the savings from skipping zeros.

### Factor-once-solve-many amplifies the advantage

| DOF | Load combos | Re-solve each (dense) | Factor-once (dense) | Factor-once (sparse) |
|----:|---:|----:|----:|----:|
| 500 | 20 | 350 ms | 18 ms + 20 x 1 ms = 38 ms | ~15 ms |
| 2,000 | 20 | 15 s | 48 ms + 20 x 5 ms = 148 ms* | ~30 ms |
| 5,000 | 20 | 250 s | 750 ms + 20 x 12 ms = 990 ms | ~100 ms |
| 25,000 | 20 | impossible | 94 s + 20 x 60 ms = 95 s | ~3-5 s |

*Measured at 2,000 DOF: factor-once = 48 ms, 15.5x faster than re-solve.

### When each solver strategy is appropriate

| DOF range | Strategy | Implementation |
|-----------|----------|----------------|
| < 500 | Dense Cholesky, factor-once | scipy.linalg.cho_factor (current) |
| 500 - 5,000 | Sparse Cholesky, factor-once | scikit-sparse CHOLMOD |
| 5,000 - 100,000 | Sparse Cholesky + fill-reducing permutation | CHOLMOD with AMD/METIS ordering |
| 100,000+ | Iterative solver (PCG + ILU preconditioner) | scipy.sparse.linalg.cg or PETSc |

### GPU acceleration (MLX)

MLX's 55x speedup was measured at 2000x2000 dense matmul. For Cholesky factorization:
- GPU excels at dense operations on large matrices (>1000x1000)
- GPU launch overhead makes it slower for small matrices (<500x500)
- Sparse factorization on GPU is less mature (irregular memory access patterns)

**Estimated crossover for MLX Cholesky:**
- Below ~1,000 DOF: CPU faster (launch overhead dominates)
- 1,000-5,000 DOF: GPU starts winning for dense, 2-5x
- 5,000+ DOF: GPU wins 5-20x for dense. But sparse CHOLMOD on CPU may still beat GPU dense.
- For sparse: NVIDIA has GPU CHOLMOD, MLX does not (yet). This is a potential future advantage.

---

## 5. Deep Dive: IFC File I/O Scaling

### IfcOpenShell performance characteristics

**Authoring (creating new models):**
- Element creation: ~31 us per element (C++ core)
- Property set attachment: ~50 us per element
- Total per element: ~80-100 us
- 200 elements: ~20 ms (negligible)
- 5,000 elements: ~500 ms (still fast)
- 50,000 elements: ~5 s (starting to matter)

**Parsing (opening existing files):**
- Throughput: ~20 MB/s on modern hardware
- 10 MB file: ~0.5 s
- 50 MB file: ~2.5 s
- 200 MB file: ~10-20 s (performance issues reported above 200 MB)
- 450 MB file: ~100 s (1m40s, documented in IfcOpenShell issue #5026)
- 1 GB file: 3-5 minutes (IfcOpenShell issue #2056, multiprocessing attempted)

**Geometry processing (tessellation for viewing):**
- IfcOpenShell: ~31 us/element (C++ OpenCascade kernel)
- Boolean subtraction for openings gets progressively slower (O(n^2) for n openings on one element)
- 200 elements: ~6 ms
- 5,000 elements: ~155 ms
- 50,000 elements: ~1.5 s (without complex booleans)
- With many boolean operations: can be 10-100x slower

**When IFC I/O becomes a bottleneck:**
- Authoring: ~50,000+ elements (seconds of creation time)
- Parsing: ~200+ MB files (10+ second open times)
- Geometry: When boolean subtraction count is high (many window/door openings in walls)

### Web viewer limits

Browser-based IFC viewing has hard constraints:
- JavaScript heap: ~1-2 GB on most browsers
- WebGL/WebGPU vertex buffer: practical limit ~2-5M triangles for interactive rates
- File parsing in browser (web-ifc): significantly slower than native IfcOpenShell

| Model scale | Browser experience | Optimization needed |
|-------------|-------------------|---------------------|
| < 1,000 elements / < 10 MB | Smooth, no issues | None |
| 1,000-10,000 elements / 10-100 MB | Usable with care | Geometry simplification |
| 10,000-50,000 elements / 100-300 MB | Slow loading, possible crashes | Fragment streaming, LOD, spatial partitioning |
| 50,000+ elements / 300+ MB | Unusable without optimization | Spatial tiling, progressive loading, server-side culling |

**For the 5-story office (~1,500 BIM elements, ~15-30 MB IFC):** The web viewer will handle it comfortably. No streaming or LOD needed.

**For a 20-story tower (~20,000 elements, ~150 MB IFC):** Browser loading will take several seconds. Consider pre-converting to a binary fragment format (what xeokit's XKT and IFC-Lite do).

---

## 6. Deep Dive: Memory Scaling

### Python process memory budget

| Component | Per-element cost | 200 elements | 5,000 elements | 50,000 elements |
|-----------|----------------:|-------------:|----------------:|----------------:|
| IfcOpenShell model (C++ heap) | ~2-5 KB | 1 MB | 10-25 MB | 100-250 MB |
| StructuralSourceModel (Python dicts) | ~1-2 KB | 0.4 MB | 5-10 MB | 50-100 MB |
| Analytical model (dataclasses) | ~0.5-1 KB | 0.2 MB | 2.5-5 MB | 25-50 MB |
| Stiffness matrix (dense, n^2 floats) | depends on DOF | 5 MB (800 DOF) | 50 MB (2,500 DOF) | 5 GB (25,000 DOF) |
| Stiffness matrix (sparse) | ~10-50 x n bytes | 0.1 MB | 1-5 MB | 10-50 MB |
| deepcopy of source model (per iteration) | same as original | 0.4 MB | 5-10 MB | 50-100 MB |
| JSON strings in memory | ~2-5 KB | 1 MB | 10-25 MB | 100-250 MB |
| **Total (dense solver)** | -- | **~8 MB** | **~85 MB** | **~5.3 GB** |
| **Total (sparse solver)** | -- | **~3 MB** | **~35 MB** | **~350 MB** |

**When memory becomes a problem:**

- At 200 elements / 800 DOF: No issues. Any modern machine handles this.
- At 500 elements / 2,500 DOF: Dense matrix is 50 MB. Still fine with 8+ GB RAM.
- At 5,000 elements / 25,000 DOF: Dense matrix is **5 GB** -- will crash on 8 GB machines. Sparse matrix is ~10-50 MB, fine.
- At 50,000 elements / 250,000 DOF: Dense is impossible (500 GB). Sparse is ~350 MB total -- manageable on 16 GB machines. But Python's deepcopy per sizing iteration creates ~100 MB of transient objects, causing GC pressure.

**The memory wall:**
- Dense solver: hits the wall at ~5,000-8,000 DOF (dense matrix exceeds available RAM)
- Sparse solver: pushes the wall to ~100,000-200,000 DOF
- Python process (total): ~50,000 elements before needing 16+ GB RAM for the model data alone
- deepcopy overhead: becomes the memory bottleneck before the solver matrix does (for sparse)

---

## 7. The 5-Story Office Building: Specific Projections

### Element count estimate

| Category | Elements | Notes |
|----------|--------:|-------|
| Columns | 120-150 | 24 columns x 5 floors + corner/edge variations |
| Primary beams | 120-180 | ~30 per floor spanning between columns |
| Secondary beams | 100-200 | ~30 per floor, shorter spans |
| Bracing | 20-40 | Lateral resistance, concentrated at core |
| Slabs | 5-25 | 1 per floor (or panelized) |
| Walls (structural) | 20-40 | Core walls, shear walls |
| Walls (partition/envelope) | 100-200 | Non-structural |
| Windows | 100-200 | Facade openings |
| Doors | 50-100 | Interior + exterior |
| Stairs | 10-20 | 2 stair cores x 5 floors |
| Foundations | 20-30 | Footings under columns |
| **Total structural** | **~450-700** | For FEA |
| **Total BIM** | **~700-1,200** | All disciplines |

### Pipeline timing projection

Using scaling relationships from measured data:

| Stage | Current (200 elem) | 5-story (550 struct elem) | With optimizations |
|-------|-------------------:|-------------------------:|-------------------:|
| AI Planner (12 rounds) | 15 s | 25-50 s | 8-15 s (caching + fewer rounds) |
| IFC Authoring | 2 s | 4-6 s | 2-3 s (cached lookups) |
| Structural Source Model | 0.2 s | 0.5-1 s | 0.2-0.4 s (memoized) |
| Analysis Export | 1 s | 2-3 s | 0.8-1.5 s (no redundancy) |
| FEA solve (dense, per solve) | 0.05 s | 1-3 s | -- |
| FEA solve (sparse, per solve) | -- | 0.02-0.1 s | 0.02-0.1 s |
| Grouped sizing (4 iter, dense) | 20 s | 60-150 s | -- |
| Grouped sizing (4 iter, factor-once + sparse) | -- | 2-8 s | 2-8 s |
| JSON output | 0.1 s | 0.3-0.5 s | 0.05-0.1 s (orjson) |
| **Total (current architecture)** | **~41 s** | **~100-220 s** | -- |
| **Total (with all Tier 1-2 optimizations)** | **~12-17 s** | **~15-30 s** | This is the target |

### IFC file size

- Structural-only model: ~550 elements x ~5-10 KB/element in IFC-SPF = **~3-5 MB**
- Full BIM model: ~1,200 elements x ~10-20 KB/element = **~12-24 MB**
- With property sets, metadata, and geometry representations: **~15-30 MB**

This is well within IfcOpenShell's comfort zone for both authoring and parsing. Web viewer handles it without any optimization.

### Memory requirements

- Dense stiffness matrix at 3,000 DOF: ~72 MB (manageable)
- Sparse stiffness matrix at 3,000 DOF: ~2-5 MB (trivial)
- Full Python process with dense solver: ~150-200 MB
- Full Python process with sparse solver: ~80-120 MB

No memory issues on any modern machine.

### Web viewer

At ~1,200 BIM elements with ~10,000-30,000 triangles: the browser renders this trivially. IFC-Lite or web-ifc will load in under 1 second. No optimization needed.

---

## 8. Summary: The Bottleneck Migration Path

```
CURRENT STATE (200 elements, ~800 DOF)
  Bottleneck: AI Planner (90%)
  FEA: trivial (50 ms)
  Priority: Reduce planner rounds, prompt caching
  Compute matters: NO

5-STORY OFFICE (550 elements, ~2,500-3,500 DOF)
  Bottleneck: AI Planner (50%) + FEA Sizing (40%)
  FEA: noticeable (1-3 s dense per solve, 60-150 s sizing loop)
  Priority: Factor-once FEA, sparse solver, PLUS planner optimization
  Compute matters: YES, BECOMING CO-DOMINANT

20-STORY TOWER (5,000 elements, ~25,000 DOF)
  Bottleneck: FEA Compute (70%) + IFC I/O (15%)
  FEA: dominant (dense impossible, sparse 1-5 s per solve)
  Priority: Sparse solver mandatory, compiled assembly, IFC optimization
  Compute matters: YES, DOMINANT

HOSPITAL/CAMPUS (50,000 elements, ~250,000 DOF)
  Bottleneck: Everything (FEA, IFC, memory, viewer)
  FEA: heavy (sparse 20-120 s, iterative solver needed)
  Priority: Compiled solver (Rust), streaming IFC, spatial partitioning
  Compute matters: YES, CRITICAL PATH
```

### The honest answer to "does compute get more important?"

**Yes, and the transition happens at exactly the scale you are about to build.**

For the current 2-story house models, compute is noise. The AI planner is the only thing worth optimizing.

For the 5-story office, you enter the transition zone. Without factor-once FEA and sparse solvers, the sizing loop will take 60-150 seconds -- longer than the AI planner. With those optimizations (which are already built in bonsai_fea_fast), sizing drops to 2-8 seconds and the planner remains dominant.

**The critical insight: the optimizations you have already built (factor-once at 15.5x, sparse-ready architecture) are what keep compute from becoming the bottleneck at the 5-story scale. Without them, you would hit a wall.** The 15.5x speedup at 2,000 DOF scales even better at 3,000+ DOF because the cubic dense cost grows faster than the linear back-substitution cost.

For buildings beyond 20 stories, compute unambiguously dominates, and language-level optimizations (Rust FEA, Numba assembly, GPU factorization) become the right investment. But that is a problem for 2027, not today.

### Priority roadmap, scaled to building complexity

| Time horizon | Target building | Top priority | Compute priority |
|-------------|----------------|--------------|-----------------|
| Now | 2-story house | Prompt caching, reduce rounds | Low |
| Q2 2026 | 5-story office | Factor-once + sparse FEA, eliminate redundancy | Medium |
| Q3-Q4 2026 | 10-20 story tower | Compiled assembly, CHOLMOD, template system | High |
| 2027+ | Hospital/campus | Rust FEA solver, streaming IFC, GPU factorization | Critical |

---

## Sources

### BIM Model Sizes and IFC Performance
- [IfcOpenShell: Slow file opening (Issue #5026)](https://github.com/IfcOpenShell/IfcOpenShell/issues/5026)
- [IfcOpenShell: Slow to open large file (Issue #664)](https://github.com/IfcOpenShell/IfcOpenShell/issues/664)
- [IfcOpenShell: Performance issue parsing 100k elements (Issue #569)](https://github.com/IfcOpenShell/IfcOpenShell/issues/569)
- [IfcOpenShell: 1 GB file with multiprocessing (Issue #2056)](https://github.com/IfcOpenShell/IfcOpenShell/issues/2056)
- [IfcOpenShell: Slow performance vs XBim (Issue #6712)](https://github.com/IfcOpenShell/IfcOpenShell/issues/6712)
- [IfcOpenShell Optimizer Tutorial](https://academy.ifcopenshell.org/posts/ifcopenshell-optimizer-tutorial/)
- [Revit typical file sizes (Modlar)](https://www.modlar.com/answers/46/what-is-an-average-file-size-for-revit/)
- [Revit file size management (Autodesk)](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Are-there-recommended-model-File-sizes-for-Revit-and-Navisworks.html)
- [Managing Revit File Size (ArchOverFlow)](https://archoverflow.com/managing-revit-file-size-performance/)
- [Revit 2026 System Requirements](https://www.myarchitectai.com/blog/revit-system-requirements)

### FEA Solver Scaling
- [SimScale: Choosing FEM Solvers (Direct vs Iterative)](https://www.simscale.com/blog/how-to-choose-solvers-for-fem/)
- [DIANA FEA: Sparse Linear System Solution](https://manuals.dianafea.com/d102/Theory/Theorych51.html)
- [ETH Zurich: FEM and Sparse Linear System Solving](https://people.inf.ethz.ch/arbenz/FEM17/pdfs/lecture6.pdf)
- [nAG: Dense vs Sparse -- The Right Tool](https://nag.com/insights/the-right-tool-for-the-job-dense-v-sparse/)
- [CHOLMOD: Supernodal Sparse Cholesky (ACM TOMS)](https://dl.acm.org/doi/10.1145/1391989.1391995)
- [scikit-sparse CHOLMOD documentation](https://scikit-sparse.readthedocs.io/en/latest/overview.html)
- [GPU-Accelerated Sparse Cholesky (ResearchGate)](https://www.researchgate.net/publication/304531882_Accelerating_Sparse_Cholesky_Factorization_on_GPUs)
- [FEATool: FEM Assembly and Solver Benchmarks](https://www.featool.com/fem/2015/10/19/FEM-Assembly-and-Solver-Benchmarks/)

### Web Viewer Performance
- [Handling Large IFC Files in Web Applications (AlterSquare)](https://altersquare.medium.com/handling-large-ifc-files-in-web-applications-performance-optimization-guide-66de9e63506f)
- [1GB IFC Files in the Browser: Culling, Tiling, Compression (AlterSquare)](https://altersquare.medium.com/how-we-made-1gb-ifc-files-usable-in-the-browser-culling-tiling-and-compression-explained-2e36de1ec179)
- [xeokit BIM Viewer SDK](https://xeokit.io/)
- [Dynamically Loading IFC Models in Browser (SpringerOpen)](https://vciba.springeropen.com/articles/10.1186/s42492-019-0011-z)

### Structural Engineering References
- [SteelConstruction.info: Multi-Storey Buildings Guide](https://www.steelconstruction.info/Engineering_students'_guide_to_multi-storey_buildings)
- [SteelConstruction.info: Concept Design](https://www.steelconstruction.info/Concept_design)

### Bonsai AI Internal Measurements
- pipeline-performance-analysis.md -- Stage-by-stage profiling, 200-element baseline
- performance-benchmarks.md -- Factor-once 15.5x, hybrid solver benchmarks
- mojo-fea-optimization.md -- Assembly interop overhead analysis
- process-speed-improvements.md -- AI planner dominance, prompt caching research
- path-a-python-optimize.md -- Python ceiling analysis, MLX benchmarks
