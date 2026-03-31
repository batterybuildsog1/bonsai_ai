# Path A Evaluation: Stay Python, Optimize Aggressively, Add MLX for GPU

**Date:** 2026-03-30
**Status:** Recommended path
**Verdict:** This is the correct path. The data overwhelmingly supports it.

---

## Executive Summary

Path A is not just viable -- it is the only path that makes engineering sense given what we now know. The performance data from the build session tells a clear story: Bonsai AI's bottlenecks are algorithmic waste, redundant computation, and network latency. None of these are language-level problems. Adding Mojo to the production stack would increase complexity for marginal gain in areas that are not bottlenecks, while leaving the actual bottlenecks untouched.

This evaluation is structured as an honest assessment, not a sales pitch. Where Python will hit ceilings, those are called out explicitly.

---

## 1. Realistic Total Speedup from Python-Only Optimizations

### The numbers we have

| Optimization | Speedup | Source | Language needed |
|-------------|---------|--------|-----------------|
| Factor-once-solve-many (Cholesky) | 7.5-15.5x on solve | Measured benchmarks | NumPy/SciPy (Python) |
| Eliminate redundant computation | 30-50% pipeline time | Pipeline profiler analysis | Pure Python refactoring |
| Caching + dedup across stages | 60-70% total pipeline | Pipeline profiler analysis | Pure Python refactoring |
| Prompt caching (API config) | 2-5x on AI rounds 2+ | OpenAI/Anthropic docs | Config change |
| Smart replanning (12 rounds -> 2-3) | 4-6x on planning stage | Architecture analysis | Python logic |
| MLX GPU matmul | 55x at 2000x2000 | Measured benchmarks | Python (MLX library) |
| orjson serialization | 5-10x on JSON writes | Library benchmarks | Python (drop-in) |

### Compound speedup estimate

The pipeline profiler showed a typical 200-element building takes ~41 seconds today. The bottleneck breakdown:

```
Planner (network-bound):     15 s   (36% of wall-clock)
Grouped sizing (4 iters):    20 s   (49% of wall-clock)
  - PyNite solver x4-5:       12-15 s
  - deepcopy + rebuild:        5-8 s
IFC authoring:                2 s    (5%)
Analysis export:              1 s    (2%)
Everything else:              3 s    (7%)
```

**After Tier 1-2 Python optimizations (1-2 weeks of work):**

| Stage | Before | After | How |
|-------|--------|-------|-----|
| Planner | 15 s | 5-8 s | Prompt caching + smart replanning (3 rounds instead of 12, 2-5x cache benefit on rounds 2+) |
| Grouped sizing | 20 s | 4-6 s | Factor-once (15x on solve), skip redundant rebuilds, eliminate deepcopy, skip final solver when no groups advanced |
| IFC authoring | 2 s | 1 s | Cache body_context/hierarchy, skip second IFC write |
| Analysis export | 1 s | 0.3 s | Eliminate double source model build, double catalog ops |
| Other | 3 s | 2 s | orjson, memoization |
| **Total** | **~41 s** | **~12-17 s** | **2.4-3.4x faster** |

**After Tier 3-4 Python optimizations (adding MLX GPU, parallel scopes, async pipeline):**

| Stage | After Tier 1-2 | After Tier 3-4 | How |
|-------|----------------|----------------|-----|
| Planner | 5-8 s | 3-5 s | Template system for common patterns, streaming execution |
| Grouped sizing | 4-6 s | 1.5-3 s | MLX GPU for element stiffness assembly (55x matmul), parallel combo solving |
| IFC authoring | 1 s | 0.5 s | Batch pset writes, entity index caching |
| Analysis export | 0.3 s | 0.15 s | Parallel scope emission |
| Other | 2 s | 1 s | Async file I/O |
| **Total** | **~12-17 s** | **~6-10 s** | **4-7x total from baseline** |

### Honest assessment of these estimates

The Tier 1-2 estimates are high-confidence. They are based on measured benchmarks (factor-once: 15.5x at 2000 DOF) and profiled redundancy (double source model builds, double catalog ops, N+1 solver runs). These are not speculative -- they are bugs being fixed.

The Tier 3-4 estimates are moderate-confidence. MLX GPU matmul is measured at 55x, but the real-world benefit depends on the assembly loop structure. Element stiffness assembly involves many 12x12 operations -- small enough that launch overhead could eat into the 55x. The realistic gain for assembly is probably 5-15x, not 55x, because the 55x was measured at 2000x2000 which is the global stiffness matrix size, not the per-element size.

**Bottom line: 3-4x from easy Python fixes, 5-7x with more effort. This takes a 41-second pipeline to 6-13 seconds.**

---

## 2. Maintenance Burden: Single-Language vs Multi-Language

### What single-language (Python) actually means for this codebase

The codebase today is ~15,000 lines of Python across ~35 modules. The team has one primary developer (you) plus AI agents. Here is the honest maintenance comparison:

**Python-only stack:**

| Dimension | Assessment |
|-----------|-----------|
| Build system | `pip install -e .` with pyproject.toml. One command. |
| CI/CD | `pytest tests/` runs all 62 tests. One step. |
| Debugging | pdb, print statements, full stack traces. Every tool works. |
| Profiling | cProfile, line_profiler, py-spy. Mature, well-documented. |
| Dependency management | pip/uv. Well-understood, large ecosystem. |
| AI agent compatibility | Claude, GPT, Gemini all write excellent Python. Zero friction. |
| Hiring (future) | Any Python developer can contribute on day one. |
| Type checking | mypy/pyright. Optional but available for the whole stack. |
| IDE support | Full autocomplete, go-to-definition, refactoring across entire codebase. |

**Python + Mojo + Rust/WASM stack:**

| Dimension | Assessment |
|-----------|-----------|
| Build system | pip + Mojo compiler (0.26.2, still pre-1.0) + cargo + wasm-pack. Three toolchains. |
| CI/CD | Python tests + Mojo compilation + Rust compilation + WASM build. Four stages, three different failure modes. |
| Debugging | Python: pdb. Mojo: print-based (limited debugger support as of 0.26). Rust: gdb/lldb. Three different mental models. |
| Profiling | Python profilers cannot see into Mojo or Rust. Each language needs its own profiling tools. Cross-language bottlenecks are invisible. |
| Dependency management | pip + Mojo packages (immature ecosystem) + Cargo.toml. Package version conflicts across boundaries. |
| AI agent compatibility | Agents write decent Mojo (limited training data, language is new) and good Rust. But cross-language interop code is where bugs live, and agents have the least training data there. |
| Hiring (future) | Need developers who know Python AND Mojo AND Rust. This intersection is nearly empty in 2026. |
| Type checking | Python: mypy. Mojo: built-in (strong). Rust: built-in (strong). But the interop boundaries are where type mismatches hide. |
| IDE support | Python: excellent. Mojo: basic (VS Code extension, no JetBrains). Rust: excellent. Interop: nothing. |

### The interop tax

The build session proved this conclusively. Mojo FEA was **slower** than NumPy for production-size problems specifically because of the Python-to-Mojo interop overhead. The raw Mojo SIMD math was fast (510 ns for 12x12 matmul), but calling it from Python through PythonObject wrappers turned a 5ms operation into a 20ms operation.

This is not a Mojo problem per se -- it is a fundamental tax of any FFI boundary. Cython has the same issue (though less severe because it compiles to C extensions that Python's C API calls directly). The performance cliff appears exactly when you have many small calls across the boundary (like assembling 200 element stiffness matrices), as opposed to one large call (like a single 2000x2000 matmul).

**The interop tax means: multi-language stacks only win when you can batch work into large, infrequent cross-language calls. Bonsai's FEA assembly loop is the opposite -- many small calls.**

### What we keep from the multi-language world

IFC-Lite (Rust/WASM) is already integrated for the web viewer and stays. This is justified because:
1. It runs in the browser, where Python cannot run.
2. It is a separate process, not an FFI boundary -- no interop tax.
3. The Rust/WASM ecosystem for WebGPU rendering is genuinely superior to anything Python offers client-side.
4. It is maintained by someone else (open-source library).

This is the right kind of multi-language: clear boundary, different runtime, genuinely no alternative.

---

## 3. Python-Native Performance Alternatives

### Numba (JIT compilation)

| Aspect | Assessment |
|--------|-----------|
| What it does | JIT-compiles Python functions with type annotations to LLVM machine code |
| Sweet spot | Tight numerical loops, array operations, stencil computations |
| Applicability | Element stiffness assembly loop, global stiffness scatter, post-processing loops |
| Performance | Typically 10-100x over pure Python loops, comparable to C |
| GIL behavior | `@njit(nogil=True)` releases the GIL, enabling true parallelism |
| Ecosystem maturity | Stable, production-ready, 10+ years old, backed by Anaconda |
| Warm-up cost | First call compiles (~0.5-2s). Subsequent calls are fast. Cache compilation to disk with `@njit(cache=True)` |
| Limitation | Cannot JIT-compile code that calls arbitrary Python objects. Must operate on numpy arrays and basic types. IfcOpenShell calls cannot be JIT-compiled. |

**Where Numba would help in Bonsai AI:**
- `_assemble_global_stiffness()`: The inner loop that scatters 12x12 element matrices into the global stiffness matrix. This is a textbook Numba target -- pure array indexing, no Python objects.
- Post-processing loops in `_build_summary()` and `_member_demands()`: Currently iterate nodes/members in Python. Numba could vectorize these.
- The `_element_id()` string processing would NOT benefit (Numba does not handle strings well).

**Estimated gain:** 10-50x on the assembly inner loop. For a 2000-DOF problem, assembly is ~10ms today. Numba could bring this to 0.2-1ms. But assembly is already dwarfed by the Cholesky factorization (48ms at 2000 DOF), so this is a small absolute gain.

### Cython

| Aspect | Assessment |
|--------|-----------|
| What it does | Compiles Python-like code to C extensions |
| Sweet spot | Wrapping C libraries, tight loops, releasing GIL for parallelism |
| Applicability | Same targets as Numba, plus potential wrapping of C FEA solvers |
| Performance | Comparable to Numba when fully typed. Slower when partially typed. |
| Complexity | Requires `.pyx` files, a build step, and careful type annotation |
| Ecosystem maturity | Very stable, used by scipy, pandas, scikit-learn |

**Verdict:** Numba is preferred over Cython for Bonsai AI because:
1. Numba requires zero build infrastructure changes (it is a pip install + decorator).
2. Cython requires a compilation step in the build pipeline, adding complexity.
3. Numba's JIT model means you can profile first, then annotate the hot function, without restructuring the code.
4. For the specific patterns in Bonsai (array scatter, matrix ops), Numba and Cython perform similarly.

### cffi / ctypes

| Aspect | Assessment |
|--------|-----------|
| What it does | Call C functions from Python without writing C extensions |
| Sweet spot | Wrapping existing C/Fortran libraries (LAPACK, MUMPS, SuiteSparse) |
| Applicability | Replacing SciPy's Cholesky with a direct CHOLMOD/MUMPS call for very large problems |
| When it matters | When SciPy's sparse Cholesky (which already wraps LAPACK) is too slow |
| Current state | SciPy already wraps LAPACK via compiled Fortran. Going lower-level has diminishing returns. |

**Verdict:** Not needed now. SciPy's `cho_factor`/`cho_solve` is already a thin wrapper over optimized LAPACK. Calling LAPACK directly via cffi would save microseconds. Only relevant if we need a solver that SciPy does not expose (like MUMPS for multi-frontal sparse solvers on 100,000+ DOF problems).

### multiprocessing / ProcessPoolExecutor

| Aspect | Assessment |
|--------|-----------|
| What it does | Bypasses the GIL by running Python code in separate processes |
| Sweet spot | CPU-bound parallelism across independent tasks |
| Applicability | Parallel engineering scope emission (5 independent scopes), parallel combo solving |
| Limitation | Data must be pickled across process boundaries. Large numpy arrays can use shared memory (`multiprocessing.shared_memory`). |
| When it helps | When you have 3+ independent CPU-bound tasks that each take > 100ms |

**Where it helps in Bonsai AI:**
- Engineering scope emission: 5 independent scopes, each taking ~50-200ms. Parallel execution saves 200-800ms.
- Independent sizing groups: Groups that do not share nodes could be analyzed in parallel. This requires careful dependency analysis.
- Not useful for the planner (network-bound, not CPU-bound).

### MLX (Apple Silicon GPU)

| Aspect | Assessment |
|--------|-----------|
| What it does | GPU-accelerated array operations on Apple Silicon unified memory |
| Sweet spot | Large matrix operations (matmul, solve, decomposition) |
| Measured performance | 55x faster than NumPy at 2000x2000 matmul |
| Applicability | Global stiffness assembly (batch matmul), Cholesky factorization |
| Limitation | Only works on Apple Silicon. Production code must fall back to NumPy on other hardware. |
| Risk | Creates an Apple Silicon dependency for peak performance. Cloud deployment (typically x86 Linux) would not benefit. |

**Where MLX makes sense in Bonsai AI:**
- The Cholesky factorization for large problems (2000+ DOF) is the single most expensive CPU operation after planner rounds. If MLX can accelerate `cho_factor` on GPU, the factor-once-solve-many approach becomes even more dominant.
- Batch element stiffness assembly: Instead of assembling 200 elements in a Python loop, batch all 200 as a single (200, 12, 12) tensor operation on GPU. This eliminates the loop entirely.

**Honest caveat:** Bonsai's typical problem sizes (50-2000 DOF) may be too small for GPU to beat CPU. GPU shines when the matrix is large enough to amortize the launch overhead. At 200 DOF, NumPy on CPU might still win. The 55x measurement was at 2000x2000 -- the crossover point needs profiling.

**Recommendation:** Add MLX as an optional accelerator behind a feature flag. Use it when available, fall back to NumPy/SciPy otherwise. Do not make it a hard dependency.

---

## 4. The Quality Story

This is where Path A's advantage is most clear-cut and least debatable.

### Single-language testing

Current state: 62 tests, 61 passing, 1 known failure (footing eccentricity). All tests are in Python, testing Python code.

With Path A, every new optimization is testable with the same framework:

```python
# Before: test the factor-once-solve-many approach
def test_factor_once_matches_full_solve():
    K = build_test_stiffness(dof=500)
    loads = [random_load_vector(500) for _ in range(20)]

    # Full solve per combo (PyNite's approach)
    results_full = [scipy.linalg.solve(K, f) for f in loads]

    # Factor once, solve many
    L, low = scipy.linalg.cho_factor(K)
    results_fast = [scipy.linalg.cho_solve((L, low), f) for f in loads]

    for full, fast in zip(results_full, results_fast):
        np.testing.assert_allclose(full, fast, atol=1e-10)
```

This test is readable, debuggable, and runs in milliseconds. The equivalent test for a Mojo FEA module would require:
1. Building the Mojo module (compilation step that can fail independently).
2. Importing through PythonObject wrappers (which have their own bugs).
3. Debugging assertion failures across the FFI boundary (stack traces end at the wrapper).
4. Maintaining the test when Mojo's PythonObject API changes between versions.

### Cross-validation is simpler

The QA plan calls for cross-validation between solvers (compare Bonsai FEA results against PyNite and analytical solutions). With everything in Python:
- Both solvers return numpy arrays.
- `np.testing.assert_allclose()` works directly.
- If a cross-validation fails, you can step through both solvers in the same debugger session.
- Test fixtures (stiffness matrices, load vectors, expected results) are plain numpy arrays, shareable between all tests.

With a Mojo solver, cross-validation requires marshaling data across the FFI boundary, which adds a layer where bugs can hide. The build session proved this: the Mojo FEA produced correct results, but the interop overhead made it slower. If there had been a subtle numerical difference, finding it would have required debugging in two languages simultaneously.

### Regression testing coverage

Python-only means:
- `coverage.py` measures test coverage for the entire codebase, including the solver.
- `pytest-benchmark` can track performance regressions across all modules.
- `hypothesis` (property-based testing) can generate random structural models and verify invariants.
- All of these tools work out of the box. None of them can see into compiled Mojo or Rust code.

### The PyNite axis swap as a cautionary tale

The build session discovered that `_section_properties()` was silently swapping major/minor axes, producing unconservative results for asymmetric sections. This bug was found by reading the Python code.

If this mapping had been in a Mojo interop layer, the bug would have been harder to find because:
1. The mapping would involve PythonObject attribute access, which is opaque to Python tooling.
2. The Mojo side would produce numerically correct results (correct math, wrong inputs).
3. The Python side would see correct-looking outputs (plausible deflection values).
4. Only a domain expert reviewing the Mojo-Python boundary code would catch it.

With Python-only, the fix was a two-line change in a single file, immediately testable.

---

## 5. The Ceiling: Where Python Becomes the Actual Bottleneck

This is the most important section. Path A has real limits. Here is where they are.

### Ceiling 1: Very large models (10,000+ DOF)

At 10,000 DOF with 20 load combinations, the Cholesky factorization alone takes ~2-5 seconds on CPU (SciPy). Assembly takes ~1-2 seconds in a Python loop. For a building with 1000+ structural members, this becomes the dominant cost.

**When you hit it:** Multi-story steel structures with 500+ unique members, detailed connection modeling, or parametric studies with thousands of analysis runs.

**Mitigation within Python:**
- MLX GPU Cholesky could reduce factorization to ~100ms (estimated from the 55x matmul benchmark, though sparse factorization may not scale the same way).
- Numba-compiled assembly loop could reduce assembly to ~50ms.
- SciPy sparse solvers (already used by PyNite) scale better than dense for truly large problems.
- SuiteSparse CHOLMOD (available via `scikit-sparse`) handles 100,000+ DOF problems efficiently and is callable from Python.

**When Python truly cannot help:** If you need real-time FEA feedback (< 50ms solve time) for interactive design exploration at 10,000+ DOF, you need a compiled solver. But this is an application domain far beyond Bonsai AI's current scope. Typical Bonsai buildings are 50-500 members / 100-2000 DOF.

### Ceiling 2: Massive IFC files (100MB+)

IfcOpenShell's parsing of large existing files is slow (1m40s for a 450MB file, per their issue tracker). Bonsai AI generates files from scratch (fast), but if the product evolves to edit existing large IFC models, parsing becomes a bottleneck.

**When you hit it:** Import/edit workflows on existing BIM models from Revit/ArchiCAD (which regularly produce 100MB+ IFC files).

**Mitigation within Python:** IfcOpenShell's C++ core already does the heavy parsing. Python is just the API layer. The bottleneck is in the C++ parser, not the Python wrapper. Replacing the Python layer with Mojo would not help.

**Real solution:** Incremental IFC editing (IfcOpenShell Issue #1222, IFC5 spec direction). This is an ecosystem-level improvement, not a language-level one.

### Ceiling 3: Real-time geometry visualization

Tessellation of IFC geometry for the web viewer needs to be fast. The Mojo tessellation benchmark showed 21x over pure Python. However, IfcOpenShell's C++ tessellation is already fast (31us per element), so the Python overhead is negligible.

**When you hit it:** If Bonsai AI needs to tessellate geometry client-side in the browser for real-time interaction, Python cannot run there. This is why IFC-Lite (Rust/WASM) exists and stays.

**But note:** This is not a Python ceiling -- it is a browser runtime constraint. The server-side Python code does not need to tessellate at all if the client handles it.

### Ceiling 4: Concurrent users under load

Python's GIL means a single process can only execute one thread of Python code at a time. For the bridge server handling multiple simultaneous design jobs, each job blocks the event loop (known issue #6 in the diagnostics report).

**When you hit it:** When more than 2-3 users submit design jobs simultaneously.

**Mitigation within Python:**
- `asyncio` + `run_in_executor()` for CPU-bound stages (already identified as the fix).
- `gunicorn` with multiple worker processes (standard Python web deployment).
- Separate the planner (network-bound, async-friendly) from the solver (CPU-bound, run in process pool).
- At scale: Celery task queue with dedicated worker processes per job.

**When Python truly cannot help:** If you need sub-millisecond response times on the hot path (like a real-time collaborative editing server), Python's per-request overhead (~1ms minimum) adds up. But Bonsai's design jobs take 10+ seconds -- the Python overhead is noise.

### Ceiling 5: Extreme parametric optimization

Running thousands of FEA variations (Monte Carlo analysis, topology optimization, genetic algorithm member sizing) requires the solver to be called thousands of times.

**When you hit it:** Automated design optimization with 1000+ solver evaluations.

**Mitigation within Python:**
- Factor-once-solve-many is the key enabler. 1000 load combinations with one factorization is fundamentally O(n^3 + 1000*n^2) instead of 1000*O(n^3).
- Numba-compiled parametric variation loop.
- MLX GPU batch evaluation of multiple designs in parallel.
- Surrogate modeling (train a neural network on solver results, evaluate the surrogate instead of the solver for 99% of evaluations).

**When Python truly cannot help:** If each parametric variation requires a new factorization (because the stiffness matrix changes, not just the loads), and you need 10,000+ variations, the accumulated factorization time dominates regardless of language. The solution is mathematical (surrogate models, adjoint methods, reduced-order models), not a language change.

---

## 6. Risk Assessment

### Risks of Path A

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Python performance insufficient for future feature X | Low-Medium | Medium | MLX, Numba, scikit-sparse provide headroom. Can always add a compiled module for a specific bottleneck later. |
| MLX Apple Silicon dependency limits deployment | Medium | Low | MLX is an optional accelerator, not a hard dependency. NumPy/SciPy fallback always works. |
| Team grows and wants a "real" language | Low | Low | Python is the most popular language for a reason. Structural engineering tools (OpenSees, SAP2000 API, ETABS API) are overwhelmingly Python. |
| IfcOpenShell Python API becomes a bottleneck | Low | Medium | IfcOpenShell's core is C++. The Python layer is thin. |
| Need browser-side computation | Already addressed | N/A | IFC-Lite (Rust/WASM) handles this. Not a Python problem. |

### Risks we avoid by NOT choosing multi-language

| Risk | Probability (if multi-language) | Impact | Notes |
|------|--------------------------------|--------|-------|
| Mojo breaking changes (pre-1.0) | High | High | Mojo is actively evolving. API changes could break Bonsai between releases. |
| Three-toolchain build failures | High | Medium | Any of pip/Mojo/cargo can fail independently. CI becomes 3x more fragile. |
| Interop bugs at FFI boundaries | Medium | High | The build session demonstrated this: correct Mojo code + correct Python code = slow system due to interop overhead. |
| AI agent code quality for Mojo | Medium | Medium | Limited training data for Mojo. Agents generate Python confidently; Mojo less so. |
| Debugging cross-language issues | High | Medium | Every developer hour spent debugging FFI is an hour not spent on features. |

---

## 7. Implementation Roadmap

### Phase 1: Algorithmic Quick Wins (3-5 days)

These are measured, high-confidence improvements:

1. **Factor-once-solve-many** -- Replace PyNite's per-combo full solve with Cholesky factorize-once + back-substitution. 7.5-15.5x solver speedup, measured.
2. **Cache body_context + project hierarchy** in IfcAuthor. Eliminates ~400 entity scans per IFC write.
3. **Memoize _semantic_meta()** per element. Eliminates 5x redundant dict lookups per element.
4. **Cache _section_properties()** by section_id. Many elements share sections.
5. **Make _reserved_fields() a class constant.** Frozenset, not per-call set construction.
6. **Fix _element_id() while loop.** Single regex substitution.

**Expected outcome:** ~28s pipeline (from 41s baseline), 32% faster.

### Phase 2: Eliminate Redundancy (1-2 weeks)

7. **Build StructuralSourceModel once, reuse.** Currently built twice (AnalyticalModelBuilder.build + export).
8. **Run catalog selection/resolution once.** Currently runs in export() and again in grouped sizing setup.
9. **Skip final PyNite solver run** when no groups advanced in last sizing iteration.
10. **Replace deepcopy(package)** with lightweight trial wrapper sharing immutable data.
11. **Skip second IFC write** in grouped sizing when plan is unchanged.
12. **Add prompt caching** for Anthropic (explicit cache_control breakpoints) and verify for OpenAI (check cached_tokens in response).
13. **Smart replanning** -- targeted failure retry instead of full replan. Reduce 12 rounds to 2-3.

**Expected outcome:** ~12-17s pipeline, 2.4-3.4x from baseline.

### Phase 3: MLX + Parallelism (2-4 weeks)

14. **MLX GPU Cholesky factorization** (optional, behind feature flag). Profile to find crossover point vs CPU.
15. **MLX batch element assembly.** Reshape element assembly as batch tensor operation instead of Python loop.
16. **Parallel engineering scope emission** with ProcessPoolExecutor.
17. **orjson** for all JSON serialization (5-10x faster, drop-in).
18. **Async pipeline orchestration** -- planner and file I/O stages run async, CPU stages in process pool.

**Expected outcome:** ~6-10s pipeline, 4-7x from baseline.

### Phase 4: Template System + Ceiling Pushers (1-2 months)

19. **Pre-compiled plan library** for 5 common building types. Near-instant for matched templates.
20. **Numba-compiled assembly** for the element stiffness scatter loop (if profiling shows it is still a bottleneck after MLX).
21. **scikit-sparse CHOLMOD** for very large models (10,000+ DOF) that exceed SciPy's dense Cholesky performance.
22. **Parametric action generators** to reduce planner rounds for repetitive patterns (column grids, floor plates).

**Expected outcome:** Common designs complete in 1-3s. Complex designs in 5-10s.

---

## 8. What We Are Explicitly NOT Doing (and Why)

| Decision | Rationale |
|----------|-----------|
| Not adding Mojo to production stack | Slower than NumPy for production FEA due to interop overhead. Pre-1.0 language with API churn risk. Marginal tessellation gain (21x) is on a non-bottleneck (31us baseline). |
| Not replacing IfcOpenShell | It is fast enough for authoring (sub-second). Its C++ core handles the heavy lifting. The Python API is thin and clean. |
| Not building a custom C FEA solver | SciPy + CHOLMOD + factor-once-solve-many covers the relevant problem sizes. Custom solver is months of work for marginal gain. |
| Not switching to Rust for the backend | Python is the lingua franca of structural engineering tools. The team's velocity in Python far exceeds what any other language offers. The bottlenecks are algorithmic and network-bound, not language-bound. |
| Not making MLX a hard dependency | Limits deployment to Apple Silicon. Must always have NumPy/SciPy fallback. |

---

## 9. The Uncomfortable Conclusion

The build session produced an uncomfortable but clarifying result: **the most important optimizations are boring.** They are:

1. Do not re-solve what you already solved (factor-once: 15.5x).
2. Do not rebuild what has not changed (eliminate redundancy: 30-50%).
3. Do not ask the AI 12 times when 3 times suffice (smart replanning: 4-6x).
4. Cache the parts of the prompt that do not change (prompt caching: 2-5x).

None of these require a new language. None of them require GPU compute. None of them require exotic toolchains. They require careful profiling, disciplined refactoring, and domain understanding.

The Mojo and MLX experiments were valuable as research -- they proved where the real bottlenecks are by showing where the bottlenecks are NOT. Tessellation at 31us is not a bottleneck. Element-level matmul at 510ns is not a bottleneck. The bottlenecks are architectural: redundant computation, excessive planner rounds, and failure to exploit the mathematical structure of the problem (factorize once, solve many).

**Path A is not a compromise. It is the path that addresses the actual bottlenecks with the least risk, lowest maintenance burden, and highest confidence of success.**

---

## Appendix: Key Data Points

All measurements from the 2026-03-30 build session on Apple M5 ARM, Python 3.12, Mojo 0.26.2.

| Measurement | Value | Source |
|-------------|-------|--------|
| Factor-once vs re-solve (2000 DOF, 20 combos) | 15.5x faster | performance-benchmarks.md |
| Mojo FEA vs NumPy (medium-large problems) | Mojo SLOWER (1.8-3.7x) | performance-benchmarks.md |
| Mojo tessellation vs pure Python | 21x faster | build session notes |
| IfcOpenShell geometry creation | 31us/element | build session notes |
| MLX GPU matmul vs NumPy (2000x2000) | 55x faster | build session notes |
| Pipeline redundant computation waste | 30-50% of time | pipeline-performance-analysis.md |
| Pipeline total savings from caching + dedup | 60-70% | pipeline-performance-analysis.md |
| AI planner share of wall-clock time | ~90% | process-speed-improvements.md |
| Test suite | 61/62 passing | python-diagnostics.md |
| Codebase size | ~15,000 lines Python | codebase-state.md |
