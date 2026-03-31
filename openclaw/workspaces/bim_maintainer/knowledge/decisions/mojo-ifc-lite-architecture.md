# Architecture Decision: Mojo + IFC-Lite Hybrid Stack

## Date
2026-03-31

## Decision
Use Mojo for server-side compute acceleration and IFC-Lite for browser-side rendering and IFC intelligence. The two technologies handle different layers and communicate through binary artifacts on disk.

## Context
Bonsai AI's performance bottlenecks are:
1. FEA computation (PyNite, pure Python) — slowest
2. Geometry tessellation (IfcOpenShell/OpenCASCADE) — heavy
3. IFC parsing in browser (web-ifc WASM, single-threaded) — noticeable
4. Model serialization/conversion — pipeline overhead

## Architecture

```
Python (orchestration, AI, IFC generation)
    │
    ├── Mojo (.so modules called from Python)
    │     ├── bonsai_fea.so — FEA solver (replaces PyNite)
    │     ├── bonsai_tessellate.so — geometry tessellation (SIMD fast path)
    │     └── bonsai_fragments.so — binary fragment writer
    │
    └── writes artifacts to disk
              │
              ▼
IFC-Lite (browser, WASM + WebGPU)
    ├── Load pre-computed fragments → instant render (~200ms)
    ├── Parse full IFC in background → property queries
    ├── WebGPU rendering (zero-copy WASM → GPU)
    └── Element interaction (select, highlight, section)
```

## Build Order

| Step | Module | Technology | Status |
|------|--------|------------|--------|
| 1 | FEA core | Mojo | Building |
| 2 | Tessellation | Mojo | Building |
| 3 | Fragment writer | Mojo (GLB first) | Building |
| 4 | Viewer integration | IFC-Lite | Building |
| 5 | Two-phase loading | Both | Planned |
| 6 | Apple Silicon GPU | Mojo Metal | Future (when stable) |

## Key Principles

- Mojo cannot run in browser (no WASM) — server-side only
- IFC-Lite cannot do heavy compute — viewer-side only
- Communication through binary files, not FFI
- Python orchestrates, Mojo computes, IFC-Lite renders
- Benchmark before and after every change
- Apple Silicon Metal GPU dispatch added incrementally as Mojo support matures

## Two-Phase Load Strategy

1. Phase 1 (0-200ms): Browser loads fragments.bin → WebGPU instant render
2. Phase 2 (background): Browser loads model.ifc via IFC-Lite WASM → property queries available

## Hardware

- Apple M5, 10 cores
- Mojo SIMD: ARM NEON (128-bit) on Apple Silicon
- Metal GPU: Tier 3 support in Mojo (basic ops only as of March 2026)

## References

- Mojo Platform 26.2: https://docs.modular.com/mojo/changelog/
- IFC-Lite: https://github.com/louistrue/ifc-lite
- PyNite bottleneck: regenerates/inverts global stiffness matrix per load combination
- Mojo PythonModuleBuilder: https://docs.modular.com/mojo/manual/python/mojo-from-python/
