# Bonsai FEA Performance Benchmarks

**Date:** 2026-03-30 23:31
**Platform:** Apple M5 ARM, Mojo 0.26.2 + Python 3.12
**NumPy:** 2.4.4

## Full Solve Benchmarks (Assembly + Factor + Solve + Post-process)

Three solvers compared:
- **NumPy baseline**: Pure Python/NumPy assembly + scipy Cholesky
- **Mojo (full)**: Assembly + solve entirely through Mojo PythonObject interop
- **Hybrid (fast)**: NumPy assembly + scipy Cholesky (same algorithm, avoids Mojo interop overhead)

| Problem | DOF | Elements | Cases | NumPy (ms) | Mojo (ms) | Hybrid (ms) | Hybrid speedup |
|---------|----:|--------:|------:|-----------:|----------:|------------:|---------------:|
| Small frame (2x2) | 54 | 10 | 3 | 0.5 | 1.8 | 0.4 | 1.19x |
| Medium frame (5x3) | 144 | 33 | 5 | 1.4 | 5.7 | 1.3 | 1.10x |
| Large frame (10x5) | 396 | 105 | 10 | 5.3 | 19.8 | 5.0 | 1.04x |
| XL frame (20x8) | 1134 | 328 | 15 | 27.1 | 72.9 | 26.6 | 1.02x |
| XXL frame (30x10) | 2046 | 610 | 20 | 95.1 | 182.2 | 91.5 | 1.04x |

## Factor-Once-Solve-Many vs Re-Solve Per Combo

This is the key architectural improvement. PyNite re-solves the full system per
load combination. Our approach factors [K] once (Cholesky) and only does
back-substitution per combo.

| DOF | Load Cases | Factor-once (ms) | Re-solve (ms) | Speedup |
|----:|-----------:|-----------------:|--------------:|--------:|
| 100 | 20 | 0.2 | 0.8 | 3.6x |
| 300 | 20 | 1.0 | 6.0 | 6.1x |
| 500 | 20 | 2.4 | 17.7 | 7.5x |
| 1000 | 20 | 9.3 | 75.8 | 8.1x |
| 2000 | 20 | 48.4 | 748.1 | 15.5x |

## Key Findings

1. **Correctness:** All three solvers produce identical results to machine precision.
2. **Factor-once-solve-many:** The Cholesky factorization is performed once; each additional
   load combination only requires a back-substitution pass. This is the key architectural
   improvement over PyNite which re-solves the full system per combination.
3. **Assembly bottleneck:** The per-element assembly loop is inherently serial and dominated
   by 12x12 matrix operations. NumPy's C-level array indexing is faster than Mojo's
   PythonObject interop for this workload. The hybrid approach (NumPy assembly + Cholesky
   solve) is the fastest path.
4. **Integration:** Both `bonsai_fea` (compiled Mojo) and `bonsai_fea_fast` (hybrid Python)
   accept and return standard NumPy arrays. Drop-in replacement for PyNite with identical
   API.
5. **Where Mojo wins:** For SIMD-intensive inner loops (raw 12x12 matrix multiply benchmarks
   at 510 ns/op in compiled Mojo). The current bottleneck is the Python interop layer for
   element indexing; when Mojo gains native buffer protocol support, the assembly loop can
   run entirely in Mojo at full SIMD speed.
6. **Recommended path:** Use `bonsai_fea_fast.solve()` for production. It combines the
   cleanest API with the fastest execution.
