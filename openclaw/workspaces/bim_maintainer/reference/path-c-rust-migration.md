# Path C: Incremental Rust Migration with Python Bridge

**Date:** 2026-03-30
**Status:** Evaluation (not a recommendation)
**Evaluator context:** 1-2 person team, Bonsai AI BIM generation + structural analysis platform

---

## The Thesis

Replace three languages (Python + Mojo + Rust) with two (Python + Rust). Rust subsumes
both Mojo (server-side compute) and the browser stack (IFC-Lite already does this). One
compiled language, one ecosystem, one toolchain for all performance-critical work.

**Architecture:**
- Python: AI planner, agent orchestration, pipeline coordination (unchanged)
- Rust via PyO3: FEA solver, geometry tessellation, IFC parsing, fragment generation
- Rust via WASM: Browser rendering (IFC-Lite), property queries, element interaction

---

## 1. PyO3 Maturity Assessment

### Verdict: Production-ready, battle-tested

PyO3 (currently v0.28.2) is pre-1.0 but widely deployed in production. The projects that
depend on it are not experiments -- they are critical infrastructure:

| Project | What it does | Scale |
|---------|-------------|-------|
| **Polars** | DataFrame library | 31k+ GitHub stars, weekly releases, VC-funded company |
| **Pydantic v2** | Data validation | Downloaded 300M+/month, core Python ecosystem |
| **Ruff** | Python linter | Replaced flake8/pylint for most of the Python community |
| **cryptography** | Python crypto lib | Used by pip itself |
| **Granian** | HTTP server | Production Rust server for Python apps |

**Key data point:** The Anise toolkit (PyO3-based) was used to softly land Firefly Blue
Ghost on the Moon on Feb 2, 2025. If PyO3 is reliable enough for lunar landings, it is
reliable enough for structural analysis.

### PyO3 Call Overhead

This is the critical number for Bonsai:

| Scenario | Latency |
|----------|---------|
| Trivial function (pure Rust) | ~60 ns |
| Same function via PyO3 | ~20-40 ns overhead per call |
| Worst case with type conversion | ~22 us |

**What this means for Bonsai:** The overhead matters only for fine-grained calls (calling
Rust per-element in a tight loop). It does NOT matter for batch operations (pass the entire
stiffness matrix to Rust, get results back). This is the same problem Mojo has -- the
interop layer is the bottleneck for small operations.

**Comparison to Mojo interop overhead:** Your benchmarks show Mojo's PythonObject interop
makes assembly 3.5x SLOWER than pure NumPy for the same algorithm. PyO3 has the same
fundamental constraint (Python<->native boundary crossing), but its boundary is more mature
and better optimized. The key insight from your build session applies equally: batch the
work on the Rust side, minimize boundary crossings.

### Maturin (Build Tooling)

Maturin is the standard build tool for PyO3 projects. It handles wheel building, cross-
compilation, and publishing. Pain points:

- Complex project layouts can fight maturin's opinionated structure
- Cross-platform wheels (manylinux, macOS universal, Windows) require CI attention
- Rust compiler requires glibc 2.17+ on Linux

For a 1-2 person team targeting macOS (dev) + Linux (deploy), this is manageable.
Polars and Pydantic have solved these problems already and their CI configs are public.

---

## 2. faer-rs for FEA: Honest Assessment

### Verdict: Promising but unproven for production FEA

**What faer provides:**
- Dense matrix operations competitive with OpenBLAS (710ms vs 849ms on 2000x2000 spectral
  decomposition -- faer is actually faster)
- Sparse matrix support including Cholesky, LU decompositions
- Pure Rust (no FORTRAN dependencies, no LAPACK linking headaches)
- Parallelism configurable per-call (important for server workloads)

**What faer does NOT provide:**
- A complete FEA framework (element formulation, meshing, boundary conditions)
- Proven sparse solver performance at FEA scale (1000-100000 DOF)
- The ecosystem depth of SciPy (decades of edge-case fixes, extensive documentation)

**The fenris comparison:** fenris is an actual Rust FEA library built on nalgebra. Its own
README says: "Production usage strongly discouraged... API completely unstable...
documentation severely lacking." Last meaningful update was years ago. This is the state
of Rust FEA tooling.

**Realistic assessment for Bonsai's needs:**

Your current FEA operates at 54-2046 DOF. This is tiny by FEA standards. At this scale:
- SciPy's Cholesky solves in 48ms for 2046 DOF (your benchmark data)
- faer would likely be comparable or faster for the solve step
- The bottleneck is assembly, not solving

**The hard truth:** You would be writing the FEA assembly logic in Rust from scratch.
faer/nalgebra give you linear algebra primitives, not structural analysis. You need:
- Element stiffness matrix formulation (beam, plate, shell elements)
- Global assembly with connectivity mapping
- Boundary condition application
- Load combination management
- Post-processing (reactions, internal forces, deflections)

This is months of work for a domain expert, and correctness is non-negotiable in
structural engineering.

---

## 3. IFC-Lite Dependency Risk

### Verdict: HIGH risk, needs mitigation strategy

**Current state of IFC-Lite (March 2026):**
- 150 GitHub stars, 34 forks
- Solo developer (Louis Trumpler / louistrue)
- Active development (v2.1.5 released March 29, 2026)
- 263 closed PRs, 8 open -- good velocity
- Full IFC4X3 schema support (876 entities), IFC5 support
- 18 npm packages, 3 Rust crates
- Performance: first triangles in ~200ms, 5x faster geometry than alternatives

**Why this is risky:**

1. **Bus factor of 1.** One developer maintaining 18 npm packages + 3 Rust crates +
   full IFC4X3 + IFC5 support. This is heroic but unsustainable. If Louis gets a job
   offer, burns out, or shifts focus, the project stalls.

2. **IFC is a monster spec.** IFC4X3 has 876 entity types with complex inheritance and
   geometry rules. "Full support" likely means "parses all entities" not "handles every
   geometric edge case that IfcOpenShell's 20-year-old C++ engine handles."

3. **No alternative Rust IFC parser is mature.** ifc_rs by MetabuildDev is v0.1.0-alpha.9,
   updated 12 months ago. If IFC-Lite stalls, there is no drop-in replacement.

4. **Your browser viewer already depends on it.** This is sunk cost that increases
   switching cost over time.

**Mitigation strategies:**
- Use IFC-Lite for browser rendering only (Phase 1 -- already done)
- Do NOT replace IfcOpenShell for server-side IFC authoring until IFC-Lite proves
  stable over 12+ months
- Keep IfcOpenShell as the server-side IFC engine indefinitely
- If wrapping ifc-lite-core for PyO3, maintain an abstraction layer that can fall back
  to IfcOpenShell
- Consider contributing to IFC-Lite to reduce bus-factor risk

---

## 4. Lessons from Python+Rust Projects

### What Polars, Pydantic, and Ruff teach us

**Polars (DataFrame library):**
- Started as a solo project by Ritchie Vink
- Formed a company in 2023, raised $4M seed from Bain Capital
- Team grew to ~4-6 core developers
- Key lesson: The Rust core does ALL computation. Python is a thin wrapper. Zero-copy
  data passing via Arrow format. The boundary is wide (pass DataFrames) not deep
  (per-element calls).

**Pydantic v2 (data validation):**
- One developer worked full-time for approximately one year on pydantic-core in Rust
- Result: 4-50x faster validation
- Key lesson: Clean separation. pydantic (Python) defines models. pydantic-core (Rust)
  validates and serializes. The Rust side has no Python dependencies at all.

**Ruff (linter):**
- Written entirely in Rust, Python is just the CLI wrapper
- Key lesson: When the core is 100% Rust, you get maximum performance. The Python layer
  is configuration and reporting only.

**The pattern that works:**
1. Rust owns all data and computation within its boundary
2. Python sends large batches in, receives large batches out
3. The boundary is coarse-grained (not per-element)
4. Rust side has zero Python dependencies (pure Rust + Rust crates only)

**How this maps to Bonsai:**
- Good fit: Pass entire structural model to Rust, get back all results
- Good fit: Pass IFC file bytes to Rust, get back parsed model
- Bad fit: Calling Rust per-element during assembly (same problem as Mojo)
- The assembly loop must live entirely in Rust to avoid boundary overhead

---

## 5. Rust vs Mojo: Developer Experience for Compute Kernels

### Honest comparison for YOUR use case (structural FEA)

| Dimension | Mojo | Rust |
|-----------|------|------|
| **Learning curve** | Moderate (Python-like syntax) | Steep (ownership, lifetimes, traits) |
| **Time to first useful code** | Days (if you know Python) | 2-4 weeks (borrow checker fight) |
| **SIMD access** | First-class, ergonomic | Via std::simd (nightly) or packed_simd |
| **Matrix math ergonomics** | Built-in tensor types | Via nalgebra/faer (external crates) |
| **Debugging** | Immature tooling | Excellent (rust-analyzer, cargo test, miri) |
| **Error messages** | Improving but cryptic | Famously helpful compiler errors |
| **Ecosystem depth** | Shallow (young language) | Deep (crates.io, 150k+ crates) |
| **Stability** | Pre-1.0, breaking changes planned | Edition-stable since 2015 |
| **GPU kernels** | First-class (cpu+gpu unified) | Via wgpu/compute shaders (separate) |
| **Python interop** | Native but overhead-prone | PyO3 (mature, overhead-prone) |
| **Browser target** | None | WASM (first-class, production-proven) |
| **Hiring** | Near-impossible | Hard but possible |

**The DX verdict:**

For writing a matrix multiply kernel or a SIMD-vectorized inner loop, Mojo is genuinely
faster to develop in. Its Python-like syntax and built-in SIMD types mean less ceremony.
Your benchmark of 510 ns/op for 12x12 matrix multiply in compiled Mojo is excellent.

For writing a complete FEA solver with proper error handling, testing, documentation, and
long-term maintenance, Rust is significantly better. The type system catches entire
categories of bugs at compile time. Cargo's testing and benchmarking are excellent. The
ecosystem has real libraries (faer, nalgebra) not prototypes.

**The real question is: what are you actually building?**

If you are building isolated SIMD kernels called from Python: Mojo wins on DX.
If you are building a complete structural analysis library: Rust wins on everything
except initial development speed.

---

## 6. Mojo Risk Factors (Context for Comparison)

Mojo has its own risks that make the Rust path more attractive:

1. **Mojo 1.0 not shipped.** Planned for H1 2026 but not released. A source-breaking
   Mojo 2.0 is already planned after that. Your code will need migration.

2. **Interop is the bottleneck you already hit.** Your benchmarks prove it: Mojo assembly
   is 3.5x slower than NumPy for the same algorithm because of PythonObject overhead.
   Mojo's promise of "Python speed-up" fails when the work involves crossing the boundary
   frequently.

3. **No browser target.** Mojo compiles to native only. You need Rust/WASM for the browser
   regardless. Path C eliminates a language; the Mojo path keeps three.

4. **Ecosystem depth.** Mojo has no equivalent to faer, nalgebra, serde, rayon, or the
   thousands of battle-tested Rust crates.

5. **Modular dependency.** Mojo is controlled by one company. If Modular pivots, raises
   prices, or fails, you are stranded. Rust is governed by an open foundation.

---

## 7. Phase-by-Phase Effort Estimate (1-2 Person Team)

### Phase 1: Browser viewer with IFC-Lite (DONE)
- Effort: Already complete
- Risk: Low (isolated, can revert to Three.js/web-ifc)
- Value: Immediate (faster viewer)

### Phase 2: ifc-lite-core via PyO3 for server-side IFC parsing
- Effort: 3-6 weeks
  - 1 week: PyO3/maturin setup, CI, wheel building
  - 1-2 weeks: Wrap ifc-lite-core parsing functions
  - 1-2 weeks: Integration testing against IfcOpenShell output
  - 1 week: Edge case handling, error propagation
- Risk: MEDIUM
  - ifc-lite-core may not handle all IFC constructs your pipeline uses
  - IfcOpenShell's authoring API (create_entity, etc.) has no Rust equivalent
  - You would only get faster PARSING, not faster AUTHORING
- Value: Moderate (parsing speed matters for large model ingestion, but your current
  bottleneck is AI planning, not IFC parsing)
- **Honest take:** This is a nice-to-have, not a need-to-have. IfcOpenShell parses your
  generated models in under 1 second. The payoff is only meaningful for loading large
  existing models (the 450MB file that takes 1m40s).

### Phase 3: Rust FEA module with faer-rs + nalgebra-sparse
- Effort: 4-8 months (THIS IS THE BIG ONE)
  - 2-4 weeks: Rust proficiency for numerical code (if not already fluent)
  - 2-4 weeks: Element formulation library (beam, column, brace -- reimplementing
    what bonsai_fea already does in Python)
  - 2-4 weeks: Sparse assembly with proper connectivity mapping
  - 2-4 weeks: Cholesky factorization integration with faer
  - 2-4 weeks: Load combination, boundary conditions, post-processing
  - 2-4 weeks: PyO3 wrapping with proper error handling and NumPy interop
  - 4-8 weeks: Validation against known results, edge cases, numerical stability
  - Ongoing: Documentation, testing, maintenance
- Risk: HIGH
  - Structural analysis correctness is non-negotiable (life-safety implications)
  - Validation against reference solutions takes as long as implementation
  - faer's sparse solvers are less proven than SciPy's (decades of edge-case fixes)
  - You are rebuilding something that already works (bonsai_fea_fast solves 2046 DOF
    in 91ms -- is that actually too slow?)
- Value: LOW-TO-MODERATE for current scale
  - At 2046 DOF, your hybrid solver takes 91ms. Even a 10x speedup (9ms) does not
    meaningfully change the user experience when AI planning takes 60-360 seconds.
  - Value increases only if you scale to 10,000+ DOF problems where SciPy's Cholesky
    becomes the bottleneck (it won't for typical building structures).
- **Honest take:** This is the phase where Path C's cost/benefit ratio breaks down for
  a 1-2 person team. You would spend 4-8 months rebuilding something that works, to save
  ~80ms on a pipeline where the AI planner consumes 99% of wall-clock time.

### Phase 4: Rust tessellation module via PyO3
- Effort: 3-6 weeks
  - Leverage IFC-Lite's existing geometry crates
  - Wrap tessellation pipeline for server-side fragment generation
- Risk: MEDIUM (depends on IFC-Lite geometry crate stability)
- Value: MODERATE (faster fragment generation for the viewer pipeline)

### Phase 5: Unified Rust library (server + browser)
- Effort: 2-4 weeks (integration and conditional compilation)
- Risk: LOW (if phases 2-4 are done, this is architecture cleanup)
- Value: HIGH (one codebase, one test suite, one set of bugs to fix)

### Total realistic timeline: 8-14 months for Phases 2-5

This assumes one developer working roughly half-time on the migration while maintaining
the existing Python pipeline. Full-time focus could compress to 5-9 months.

---

## 8. Is This Actually Simpler Than Mojo?

### No. It is a different kind of complexity.

**Mojo complexity (what you have now):**
- Learning a pre-1.0 language with shifting APIs
- Fighting the PythonObject interop boundary
- No browser target (still need Rust for WASM)
- Limited ecosystem (few libraries, few StackOverflow answers)
- Vendor lock-in to Modular

**Rust complexity (what you would get):**
- Steep learning curve (ownership, lifetimes, borrow checker)
- PyO3 boundary crossing (same fundamental problem as Mojo interop)
- Build complexity (Cargo + maturin + Python packaging)
- Longer time to first working code
- More verbose syntax for numerical work

**What Rust eliminates:**
- Third language (Mojo) from the stack
- Vendor dependency (Modular)
- Browser/server code split (one language for both)
- Ecosystem risk (Rust is not going anywhere)

**What Rust does NOT eliminate:**
- The interop overhead problem (PyO3 has the same boundary cost as Mojo)
- The need to rewrite compute code in a non-Python language
- The testing and validation burden

**Net assessment:** Path C trades one set of problems for another. The Rust problems
are better understood and have more community solutions, but they are not smaller.
The key advantage is strategic: fewer languages, more mature ecosystem, no vendor risk,
and browser+server unification.

---

## 9. The Brutal Bottom Line

### What Path C gets right:
1. **Language consolidation is real value.** Two languages instead of three. One compiled
   toolchain instead of two. This compounds over years.
2. **Browser+server unification is real value.** One Rust codebase compiling to both
   WASM and native is genuinely powerful and unique to Rust.
3. **Ecosystem maturity is real value.** PyO3, faer, nalgebra, wgpu, serde, rayon --
   these are battle-tested. Mojo's ecosystem is embryonic by comparison.
4. **No vendor risk.** Rust is governed by an open foundation. Mojo is controlled by
   Modular. This matters for a multi-year project.

### What Path C gets wrong:
1. **The ROI on Phase 3 (FEA) is terrible.** You would spend 4-8 months to save ~80ms
   on a pipeline where the AI planner burns 60-360 seconds. The bottleneck is not the
   FEA solver. It is not even close.
2. **faer-rs is not SciPy.** SciPy's sparse solvers have decades of hardening. faer is
   excellent but young. For life-safety structural calculations, "young" is a risk.
3. **IFC-Lite dependency is fragile.** Building your server-side stack on a solo-developer
   project is a strategic risk that increases with each phase.
4. **Rust's learning curve is real.** A Python developer writing their first Rust FEA
   solver will fight the borrow checker for weeks before becoming productive. This is
   not a weekend project.

### The recommended variant of Path C:

**Do Phases 1 and 2 only. Skip 3 and 4. Revisit when the bottleneck shifts.**

- Phase 1 (browser viewer): Already done. Good.
- Phase 2 (IFC parsing via PyO3): Do this IF and WHEN large-model ingestion becomes a
  real bottleneck. Keep IfcOpenShell for authoring. Effort: 3-6 weeks.
- Phase 3 (Rust FEA): Do NOT do this now. Your hybrid solver works. The bottleneck is
  AI planning latency, not FEA speed. Revisit only if you hit 10,000+ DOF problems
  where SciPy chokes.
- Phase 4 (Rust tessellation): Do this only if viewer fragment generation becomes a
  user-facing bottleneck.
- Phase 5 (unification): Only makes sense after 3-4 are done.

**The biggest win available right now is not a language migration.** It is:
1. Prompt caching (2-5x on planner rounds -- the actual bottleneck)
2. Reducing planner rounds (algorithmic improvement)
3. Template-based generation for common building types (skip the planner entirely)

These require zero Rust. They attack the 99% of wall-clock time that the FEA solver
does not touch.

### Timeline for the recommended approach:
- Now: Keep Python + IfcOpenShell + hybrid FEA solver + IFC-Lite browser viewer
- Q2 2026: Implement prompt caching and planner optimizations (days, not months)
- Q3 2026: Evaluate IFC-Lite server-side parsing if large-model ingestion is needed
- 2027+: Revisit Rust FEA only if problem scale grows beyond SciPy's comfort zone

### The one-sentence verdict:

Path C is strategically sound but tactically premature -- the Rust migration invests
months of effort optimizing the 1% of your pipeline that is already fast enough, while
the 99% bottleneck (AI planner latency) needs zero Rust to fix.
