# Path B Evaluation: Mojo + Rust Hybrid with Python Orchestration

**Date:** 2026-03-30
**Verdict:** Do not pursue. Consolidate on Python + Rust. Drop Mojo.

---

## The Thesis

Python orchestrates (AI, agents, pipeline). Mojo handles server-side compute
(FEA, tessellation, batch transforms). Rust/IFC-Lite handles browser-side
rendering and IFC intelligence. Each language does what it's best at.

This sounds elegant in a slide deck. In practice, it is a trap.

---

## Question 1: What Is the Realistic Maintenance Burden of 3 Languages for a 1-2 Person Team?

**Answer: Unsustainable.**

Academic research on polyglot codebases (ICSE 2023, Springer Journal of
Software Engineering Research and Development) consistently finds:

- Cross-language boundaries are where bugs cluster. Each boundary requires
  its own test harness, error handling strategy, and data serialization
  format.
- Developers report an average of 7 languages and 3 linked language pairs
  per project, but the problems concentrate at the link points:
  "understandability and changeability" degrade significantly.
- Developers avoid refactoring across language boundaries for fear of
  breaking unknown contracts, leading to code rot.

For Bonsai AI specifically, the burden is concrete:

| Concern | Python | Mojo | Rust |
|---------|--------|------|------|
| Package manager | pip/uv | magic (Mojo-specific) | cargo |
| Build system | setuptools/hatch | mojo build | cargo/wasm-pack |
| CI toolchain | pytest, mypy | mojo test (immature) | cargo test, wasm-pack test |
| Debugger | pdb, PyCharm | print() (no real debugger) | rust-gdb, VSCode |
| IDE support | Excellent | Basic (VS Code extension) | Excellent (rust-analyzer) |
| Linter/formatter | ruff, black | None stable | clippy, rustfmt |
| Error handling | exceptions | raises (Python-like) | Result<T, E> |
| Dependency ecosystem | 500K+ packages | ~50 packages | 150K+ crates |

A 1-2 person team must maintain fluency in all three. When you hit a bug at
the Mojo/Python boundary (which happens constantly -- see Question 2), you
need to understand both sides simultaneously. When Mojo has a breaking change
(which it will -- see Question 3), you need to drop everything and fix it.

**The real cost is not writing the code. It is debugging it, updating it, and
onboarding anyone else to it.**

For comparison, FreeCAD (a mature CAD project with dozens of contributors)
uses exactly two languages: C++ core with Python bindings via a custom XML
binding generator. They have spent years building tooling around that single
boundary. Blender: C/C++ core, Python scripting. Two languages, one boundary.
These projects have 50-200+ contributors and still find the two-language
boundary challenging.

Bonsai AI would have three languages with two boundaries (Python/Mojo and
Rust/WASM), maintained by 1-2 people.

---

## Question 2: How Do You Test Across Language Boundaries?

**Answer: Painfully, with incomplete coverage.**

The current Mojo FEA module (`bonsai_fea.mojo`) illustrates the problem:

**The good:** 9/9 analytical test cases pass. Correctness is verified.

**The bad:** The module is slower than NumPy for every problem size tested
(0.25x-0.52x of NumPy speed). The bottleneck is the Python/Mojo interop
layer itself -- ~100 PythonObject boundary crossings per element, each
involving heap allocation, reference counting, and GIL acquisition. This
means the performance bug is IN the language boundary, not in the algorithm.

How do you debug this? You cannot step through a Mojo function in a Python
debugger. Mojo has no production debugger. You are reduced to:

1. Inserting print statements in Mojo code
2. Recompiling the .so module
3. Re-running the Python test
4. Staring at timing numbers

For the Rust/WASM side (IFC-Lite), testing requires:

1. A browser environment (or Node.js with WASM + WebGPU polyfill)
2. A separate test harness (cargo test for Rust, playwright for browser)
3. Integration tests that verify Rust WASM output matches Python-generated IFC

The cross-language integration test matrix looks like this:

```
Python unit tests                    (pytest)
Mojo unit tests                      (mojo test, immature)
Rust unit tests                      (cargo test)
Python -> Mojo integration tests     (pytest calling .so, timing-dependent)
Python -> Rust/WASM integration tests (not possible directly)
Python -> artifacts -> Rust/WASM     (file-based, requires browser or Node)
End-to-end                           (Python pipeline + browser viewer)
```

That is 7 test categories across 3 toolchains. For a 1-2 person team, the
realistic outcome is that cross-boundary tests get written once and then
slowly rot as the individual languages evolve.

---

## Question 3: What Happens When Mojo Has a Breaking Change?

**Answer: It will break your production pipeline, and you will have no choice
but to fix it immediately or pin forever.**

Mojo's roadmap is explicit about this:

- Mojo 1.0 is expected "sometime in 2026" (Modular blog, March 2026).
- Phase 2 of the roadmap will introduce breaking changes to both the
  language and standard library AFTER 1.0.
- The compiler will not be open-sourced until 1.0 (committed by end of
  2026 at latest).
- Pre-1.0 releases (0.25, 0.26, etc.) already show API churn: the
  tessellation module uses `from std.python` while the FEA module uses
  different import paths. The `PythonModuleBuilder` API has changed between
  minor versions.

The practical impact:

1. **You cannot pin Mojo versions safely.** Mojo is distributed through
   Modular's toolchain (magic). There is no equivalent of `pip install
   mojo==0.26.2` that works reliably across machines.
2. **When Mojo updates break your code, there is no fallback.** Unlike
   Python (where you can pin packages) or Rust (where editions provide
   backward compatibility), Mojo pre-1.0 offers no stability guarantees.
3. **Your CI must track Mojo releases.** Every Mojo release is a potential
   fire drill.

The tessellation module (`bonsai_tessellate.mojo`) uses `UnsafePointer`,
`@fieldwise_init`, and low-level memory management that could change at any
time. The FEA module depends on `PythonModuleBuilder` which is explicitly
experimental.

**Contrast with Rust:** Rust has had a stable 1.0 since 2015. The edition
system (2015, 2018, 2021, 2024) provides forward compatibility. Cargo
handles version pinning flawlessly. Code written in Rust 1.0 still compiles
on the latest rustc.

---

## Question 4: Is the Mojo Tessellation (21x) Worth the Complexity vs IfcOpenShell?

**Answer: The 21x number is real but irrelevant to the actual pipeline.**

Let us work through the math:

- IfcOpenShell tessellation: ~31us per element (from benchmarks)
- Mojo tessellation: ~1.5us per element (21x faster)
- Typical building: 200 elements

| Approach | Time for 200 elements | Time in context of 41s pipeline |
|----------|----------------------|--------------------------------|
| IfcOpenShell | 6.2ms | 0.015% of pipeline time |
| Mojo SIMD | 0.3ms | 0.0007% of pipeline time |
| Savings | 5.9ms | 5.9ms |

You save **5.9 milliseconds** on a 41-second pipeline. The AI planner alone
takes 15 seconds. The FEA solver takes 3-20 seconds. The redundant deepcopy
in grouped sizing wastes more time per iteration than the total tessellation
cost.

Even at 10,000 elements (a very large building):

| Approach | Time for 10K elements |
|----------|----------------------|
| IfcOpenShell | 310ms |
| Mojo SIMD | 15ms |
| Savings | 295ms |

295ms saved on a pipeline that takes minutes for a 10K element building.

**The tessellation module is a technical achievement that solves a problem
you do not have.** The complexity it adds (a second language, a second build
system, a second test framework, memory management with UnsafePointer, manual
vertex/index buffer management) is not justified by 6ms of savings.

The Mojo tessellation module is 450+ lines of manual vertex allocation,
unsafe pointer arithmetic, and triangle index computation. The equivalent
IfcOpenShell call is one line:

```python
shape = ifcopenshell.geom.create_shape(settings, element)
```

---

## Question 5: Could Rust (via PyO3) Replace Mojo Entirely?

**Answer: Yes, and it should.**

Rust via PyO3 can do everything Mojo does for Bonsai AI, plus:

| Capability | Mojo | Rust + PyO3 |
|-----------|------|-------------|
| Python extension modules | Yes (PythonModuleBuilder) | Yes (PyO3, mature) |
| SIMD vectorization | Yes (ARM NEON) | Yes (std::simd, portable-simd, auto-vectorization) |
| WASM compilation | No | Yes (wasm-pack, wasm-bindgen) |
| Browser execution | No | Yes (same codebase via feature flags) |
| Stable ABI | No (pre-1.0) | Yes (since 2015) |
| Ecosystem | ~50 packages | 150K+ crates |
| FEA libraries | None | fenris, quick-fea, finite_element_method crate |
| OpenCascade bindings | None | opencascade-rs (Rust bindings to OCCT) |
| GPU compute | Metal Tier 3 (buggy) | wgpu (cross-platform, production) |
| Debugger | None | rust-gdb, LLDB, VSCode |
| Profiler | None | perf, flamegraph, cargo-criterion |

The critical advantage: **Rust can compile the same codebase for both
server (native binary, PyO3 bindings) and browser (WASM, wasm-bindgen).**

This means:

1. FEA solver written in Rust can run server-side (called from Python via
   PyO3) AND client-side (in browser via WASM) from the same source code.
2. Tessellation written in Rust can produce fragments server-side AND run
   geometry processing in the browser.
3. IFC parsing logic (already in Rust via IFC-Lite) can be shared between
   server and browser.

With Mojo, you are permanently locked into server-side only. Any compute
you want in the browser requires a DIFFERENT language (Rust/WASM). With Rust
everywhere, you write the compute kernel once and deploy it twice.

### Performance comparison

PyO3 benchmark data (2025-2026):

- Per-call overhead: 0.14ms (PyO3) vs 3.56ms (NumPy) for mean calculation
- Rust SIMD: `std::simd` (portable) or `std::arch` (platform-specific) give
  equivalent performance to Mojo NEON on ARM
- Both Rust and Mojo compile to LLVM IR (Mojo targets MLIR, which emits
  LLVM). Final machine code performance is comparable for equivalent
  algorithms.

The honest truth: Mojo's SIMD ergonomics are slightly nicer than Rust's for
writing vectorized loops. But "slightly nicer syntax" does not justify a
third language in your stack.

---

## Question 6: What Is the Realistic Timeline for This Stack to Be Stable?

**Answer for Path B (Python + Mojo + Rust): 18-24 months minimum.**

| Milestone | Dependency | Estimated date |
|-----------|-----------|---------------|
| Mojo 1.0 release | Modular | H2 2026 (optimistic) |
| Mojo compiler open-source | Mojo 1.0 | End of 2026 |
| Mojo buffer protocol | Post-1.0 feature | 2027 |
| Mojo Metal GPU stable | Post-1.0 | 2027+ |
| `unsafe_get_as_pointer` proven reliable | Needs more testing | Unknown |
| IFC-Lite production-stable | Solo developer project | 6-12 months |
| Full integration tested | All of the above | H1 2027 at earliest |

**Answer for Path A (Python + Rust): 3-6 months.**

| Milestone | Dependency | Estimated date |
|-----------|-----------|---------------|
| PyO3 FEA module (replace PyNite) | Well-understood work | 4-6 weeks |
| PyO3 tessellation module | Port existing Mojo code | 2-3 weeks |
| WASM build of same Rust code | wasm-pack (proven) | 1-2 weeks |
| IFC-Lite integration (already done) | Existing | Done |
| Full integration tested | CI with cargo test + pytest | 2-4 weeks |

Rust gives you a stable, tested, dual-target stack in 3-6 months.
Mojo makes you wait 12-18 months for a language to stabilize, for a
server-only result that Rust already delivers.

---

## What Other BIM/CAD Projects Use Multi-Language Stacks?

### Two-Language Stacks (the norm)

| Project | Languages | Boundary | Team size |
|---------|-----------|----------|-----------|
| FreeCAD | C++ + Python | Custom XML binding generator | ~100 contributors |
| Blender | C/C++ + Python | RNA/DNA + ctypes | ~200 contributors |
| IfcOpenShell | C++ + Python | SWIG bindings | ~30 contributors |
| Vectorworks | C++ + Python | Built-in Python engine | Commercial team |
| OpenSCAD | C++ + (scripting language) | Internal | ~20 contributors |

### Three-Language Stacks (rare, only at scale)

| Project | Languages | Notes |
|---------|-----------|-------|
| Autodesk Revit | C++ + C# + Python | Hundreds of engineers, massive team |
| Tekla Structures | C++ + C# + Python | Commercial, large team |
| Vectorworks 2025 | C++ + Python + Vue.js | The Vue.js is only for a web palette UI, not core compute |

The pattern is clear: **two-language stacks are the maximum that
small-to-medium teams can sustain.** The projects with three languages are
either commercial products with large engineering teams, or the third
language is confined to a thin UI layer (not core compute).

No BIM project of any size uses Mojo. The ecosystem is too young.

---

## The Honest Recommendation

### Drop Mojo. Go Python + Rust.

The Mojo work was not wasted. It proved three things:

1. **Factor-once-solve-many (Cholesky) is the right FEA architecture.**
   The 8-15x speedup from factoring K once comes from the algorithm, not the
   language. Implement this in Rust or even in pure Python/SciPy (the
   `bonsai_fea_fast` hybrid already does this).

2. **The assembly loop bottleneck is interop, not compute.** This tells you
   that any compiled language with zero-copy Python bindings will solve the
   problem. Rust + PyO3 has zero-copy ndarray support via the `numpy` crate
   for PyO3. No `unsafe_get_as_pointer` research needed.

3. **SIMD tessellation works but does not matter for BIM-scale models.**
   The 21x speedup saves 6ms on a typical building. Keep using IfcOpenShell.

### The Recommended Two-Language Stack

```
Python (orchestration, AI, agents, IfcOpenShell IFC generation)
    |
    +-- PyO3 Rust extensions (.so/.dylib)
    |     +-- bonsai_fea_rs: FEA solver (factor-once-solve-many)
    |     +-- bonsai_fragments_rs: fragment pre-computation (if needed)
    |     +-- (tessellation: skip, use IfcOpenShell)
    |
    +-- writes artifacts to disk
              |
              v
Rust/WASM (browser, same crate compiled to wasm32)
    +-- ifc-lite-core: IFC parsing + property queries
    +-- bonsai_fea_rs: client-side what-if analysis (same code!)
    +-- WebGPU rendering
```

### Migration Path

| Week | Action |
|------|--------|
| 1-2 | Create `bonsai_fea_rs` Rust crate with PyO3 bindings. Port the factor-once-solve-many algorithm (not the Mojo code -- port the algorithm from `bonsai_fea_fast.py`). |
| 3-4 | Benchmark against `bonsai_fea_fast.py`. Target: match or beat NumPy assembly + SciPy Cholesky. |
| 5-6 | Add WASM build target to same crate. Verify it runs in browser via wasm-bindgen. |
| 7-8 | Integration test: Python pipeline calls Rust FEA, browser loads same WASM for what-if. |
| 9-10 | Remove Mojo modules from the project. Archive `mojo_modules/` for reference. |

### What You Keep

- All the algorithmic insights from the Mojo work (factor-once, SIMD sizing)
- IFC-Lite integration (already Rust)
- Python orchestration layer (unchanged)
- A two-language stack that a 1-2 person team can actually maintain

### What You Lose

- Mojo's slightly nicer SIMD syntax
- The novelty factor of using a cutting-edge language
- Nothing else

---

## Summary Table

| Criterion | Path B (Py+Mojo+Rust) | Recommended (Py+Rust) |
|-----------|----------------------|----------------------|
| Languages to maintain | 3 | 2 |
| Language boundaries | 2 (Py/Mojo, Rust/WASM) | 1 (Py/Rust via PyO3) |
| Build systems | 3 (pip, magic, cargo) | 2 (pip, cargo) |
| Browser compute | Rust only | Rust (same code as server) |
| Server compute | Mojo + Python | Rust + Python |
| FEA in browser | Not possible | Yes (same crate, WASM target) |
| Stability risk | High (Mojo pre-1.0) | Low (Rust stable since 2015) |
| Debuggability | Poor (no Mojo debugger) | Good (rust-gdb, LLDB) |
| Onboarding a new developer | Must learn 3 languages | Must learn 2 languages |
| Time to production | 18-24 months | 3-6 months |
| Tessellation approach | Mojo SIMD (saves 6ms) | IfcOpenShell (good enough) |
| FEA solver | Mojo (currently slower than NumPy) | Rust + PyO3 (zero-copy proven) |
| GPU compute | Mojo Metal (Tier 3, buggy) | wgpu (cross-platform, stable) |
| Ecosystem maturity | Mojo: pre-1.0, ~50 packages | Rust: 11 years stable, 150K crates |

---

## Sources

### Mojo Stability and Roadmap
- [The Path to Mojo 1.0 (Modular Blog)](https://www.modular.com/blog/the-path-to-mojo-1-0)
- [Mojo Roadmap (Modular Docs)](https://docs.modular.com/mojo/roadmap/)
- [Mojo 1.0 Roadmap Analysis (Databooth)](https://www.databooth.com.au/posts/mojo/mojo-v1-roadmap/)
- [Mojo-Python Interop in Late 2025 (Deep Engineering)](https://medium.com/deep-engineering/deep-engineering-21-mojo-python-interop-in-late-2025-with-ivo-balbaert-76b654f9e806)

### PyO3 and Rust-Python Integration
- [PyO3 Performance Guide](https://pyo3.rs/main/performance)
- [PyO3 GitHub](https://github.com/PyO3/pyo3)
- [Rust-Python FFI with PyO3 (Johal.in)](https://johal.in/rust-python-ffi-with-pyo3-creating-high-speed-extensions-for-performance-critical-apps/)
- [Why Python Developers Are Turning to Rust with PyO3 (Medium)](https://medium.com/@muruganantham52524/why-python-developers-are-turning-to-rust-with-pyo3-for-faster-ai-and-data-science-in-2025-cd5991973a4d)
- [PyO3 Design Strategy Discussion](https://github.com/PyO3/pyo3/discussions/4780)

### Rust SIMD and Performance
- [The State of SIMD in Rust in 2025 (Medium)](https://shnatsel.medium.com/the-state-of-simd-in-rust-in-2025-32c263e5f53d)
- [Rust vs Python Performance 2026 (Rustify)](https://rustify.rs/articles/rust-vs-python-performance-2026)
- [Mojo vs Rust (Modular Blog)](https://www.modular.com/blog/mojo-vs-rust)

### Rust FEA Libraries
- [fenris: Advanced Finite Element Computations in Rust](https://github.com/InteractiveComputerGraphics/fenris)
- [quick-fea: Structural Analysis in Rust](https://github.com/LukeMinnich/quick-fea)
- [finite_element_method crate (docs.rs)](https://docs.rs/finite_element_method)

### Rust in CAD/BIM
- [opencascade-rs: Rust Bindings to OpenCascade](https://github.com/bschwind/opencascade-rs)
- [ifc-lite: Browser-native IFC Viewer (GitHub)](https://github.com/louistrue/ifc-lite)
- [ifc-lite-core Rust Crate (lib.rs)](https://lib.rs/crates/ifc-lite-core)

### Polyglot Codebase Research
- [Demystifying Issues in Multilingual Development (ICSE 2023)](https://chapering.github.io/pubs/icse23haoran.pdf)
- [On Multi-Language Software Development (Springer)](https://link.springer.com/article/10.1186/s40411-017-0035-z)
- [Approaching Polyglot Programming (Harvard)](https://glassmanlab.seas.harvard.edu/papers/Rebecca_PLATEAU.pdf)

### BIM/CAD Architecture
- [FreeCAD Python Integration (DeepWiki)](https://deepwiki.com/FreeCAD/FreeCAD/2.4-draft-workbench)
- [FreeCAD Python Binding for C++ (Dev Handbook)](https://freecad.github.io/DevelopersHandbook/technical/CreatePythonBindingForCpp.html)
- [Rust vs C++ Comparison for 2026 (JetBrains RustRover)](https://blog.jetbrains.com/rust/2025/12/16/rust-vs-cpp-comparison-for-2026/)

### WASM and Dual-Target Compilation
- [Rust/PyO3 Support in Pyodide](https://blog.pyodide.org/posts/rust-pyo3-support-in-pyodide/)
- [PyO3 WASM Discussion (GitHub)](https://github.com/PyO3/pyo3/discussions/1935)
