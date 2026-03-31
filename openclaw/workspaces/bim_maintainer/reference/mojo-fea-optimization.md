# Mojo FEA Assembly Optimization -- Research & Results

**Date:** 2026-03-31
**Status:** IMPLEMENTED -- vectorized assembly is 1.4-3.2x faster than baseline

## Problem Statement

The Mojo FEA module (`bonsai_fea.mojo`) is SLOWER than NumPy for medium-to-large
problems because the assembly loop makes too many Python/Mojo interop calls per
element:

| Problem | DOF | NumPy (ms) | Mojo (ms) | Mojo speedup |
|---------|----:|-----------:|----------:|-------------:|
| Small (2x2) | 54 | 0.5 | 1.7 | 0.26x (slower) |
| Medium (5x3) | 144 | 1.4 | 5.7 | 0.24x (slower) |
| Large (10x5) | 396 | 5.1 | 19.4 | 0.26x (slower) |
| XL (20x8) | 1134 | 26.6 | 73.3 | 0.36x (slower) |
| XXL (30x10) | 2046 | 95.0 | 178.3 | 0.53x (slower) |

### Root Cause: Per-Element Interop Overhead

The assembly loop in `bonsai_fea.mojo` crosses the Python/Mojo boundary hundreds
of times PER ELEMENT:

```
for e in range(n_elements):           # ~100-600 iterations
    var ni = _py_int(elements.__getitem__(_py_tuple2(...)))  # 2 calls
    var nj = _py_int(elements.__getitem__(_py_tuple2(...)))  # 2 calls
    var x1 = nodes.__getitem__(_py_tuple2(...))              # 6 calls for coords
    ...
    var E_val = properties.__getitem__(_py_tuple2(...))      # 6 calls for props
    ...
    # _beam_local_stiffness_impl: ~36 __setitem__ calls with _py_tuple2
    # _beam_transform_impl: ~30+ __setitem__/__getitem__ calls
    # Total: ~100+ Python/Mojo boundary crossings PER ELEMENT
```

At 600 elements, that is ~60,000 interop calls just for assembly.

## Solution Implemented: Vectorized NumPy Assembly

### Results

| Problem | DOF | Elems | NumPy (ms) | Vectorized (ms) | Speedup |
|---------|----:|------:|-----------:|----------------:|--------:|
| Small (2x2) | 54 | 10 | 0.5 | 0.2 | **2.12x** |
| Medium (5x3) | 144 | 33 | 1.4 | 0.4 | **3.20x** |
| Large (10x5) | 396 | 105 | 5.1 | 2.6 | **1.96x** |
| XL (20x8) | 1134 | 328 | 26.6 | 14.8 | **1.80x** |
| XXL (30x10) | 2046 | 610 | 95.0 | 66.1 | **1.44x** |

**Correctness:** All results match NumPy baseline to machine precision (max error < 2e-12).

### What Changed

Instead of a per-element Python loop that calls `beam_local_stiffness()` and
`beam_transform()` for each element individually, the vectorized assembly:

1. **`_batch_element_geometry()`**: Computes ALL element lengths and direction
   cosines in one numpy operation using fancy indexing
2. **`_batch_transforms()`**: Builds ALL 12x12 transformation matrices at once
   using vectorized cross products and numpy broadcasting
3. **`_batch_local_stiffness()`**: Fills ALL (n_elem, 12, 12) local stiffness
   matrices in one pass using array slicing
4. **`np.einsum('eij,ejk->eik', ...)`**: Batch matrix multiply T^T @ ke @ T
   for all elements simultaneously
5. **Vectorized post-processing**: Element forces via `np.einsum` instead of
   per-element per-load-case Python loops

### Architecture

```
bonsai_fea_fast.solve()
  -> solve_vectorized()
       -> assemble_vectorized()
            -> _batch_element_geometry()    # 1 numpy call for ALL elements
            -> _batch_transforms()          # 1 numpy call for ALL transforms
            -> _batch_local_stiffness()     # 1 numpy call for ALL ke matrices
            -> np.einsum(T^T @ ke @ T)      # 1 call for ALL global ke
            -> scatter-add loop             # unavoidably serial
       -> cho_factor(K_ff)                  # scipy LAPACK, already fast
       -> cho_solve(cho, F) per load case   # fast back-substitution
       -> np.einsum(element forces)         # 1 call for ALL element forces
```

The scatter-add loop (adding element stiffness into the global matrix) remains
serial because each element writes to overlapping DOF indices. This is the only
remaining Python loop and accounts for most of the remaining time at large sizes.

## Research Findings

### 1. Mojo `unsafe_get_as_pointer` -- BROKEN in Mojo 0.25.6.1

The documented approach for zero-copy pointer access:
```mojo
var ptr = arr.ctypes.data.unsafe_get_as_pointer[DType.float64]()
```
**Segfaults at runtime** in Mojo 0.25.6.1 (MAX 25.6.1). The `.ctypes.data`
attribute access itself crashes. This is a known issue with the current version's
Python interop layer.

The alternative `UnsafePointer(unsafe_from_address=addr)` constructor also does
not exist in this version (it is documented for newer versions).

**Recommendation:** Wait for Mojo 0.26+ which should fix the ctypes.data interop.
When available, re-implement `assemble_batch()` in pure Mojo for an additional
~2-5x speedup on the assembly loop itself.

### 2. SIMD Vectorization (for future Mojo batch assembly)

Mojo's `vectorize` function can process multiple float64 values simultaneously.
On ARM NEON (M5), SIMD width for Float64 is 2. The 12x12 matrix multiply inner
loop would benefit from SIMD vectorization when the pointer access works.

### 3. Buffer Protocol Not Yet Supported

Mojo does not yet support Python's buffer protocol natively.
**Feature request:** [modular/modular#1515](https://github.com/modular/modular/issues/1515)

### 4. MLX for Batched Element Stiffness

MLX's batched matmul could compute all element stiffness matrices on the GPU.
However:
- Element stiffness matrices are only 12x12 (too small for GPU efficiency)
- The scatter-add has irregular memory access (poor GPU fit)
- **Verdict: Not worth it for beam FEA. Better for plate/solid FEA.**

### 5. numpy.ctypeslib

Could compile a C/Mojo assembly kernel as a standalone .so and call via ctypes.
This would bypass PythonObject entirely. Viable but adds build complexity.

## Why Vectorized NumPy Beats Per-Element NumPy

The speedup comes from eliminating ~600 Python function calls per solve:

| Operation | Per-Element | Vectorized |
|-----------|------------|------------|
| Element geometry | 600 Python calls | 1 numpy fancy-index |
| Transform matrices | 600 `beam_transform()` calls | 1 batched `np.cross` + broadcast |
| Local stiffness | 600 `beam_local_stiffness()` calls | 1 array-slice fill |
| Global stiffness | 600 `T.T @ ke @ T` calls | 1 `np.einsum` |
| Element forces | 600 * n_loads matmuls | 2 `np.einsum` calls |

Each Python function call has ~1-5 us overhead (frame creation, argument passing,
return value). At 600 elements, that is 0.6-3 ms of pure overhead, which dominates
the actual computation for the 12x12 matrices.

## Future Optimization Paths

1. **Mojo batch assembly (when pointer access works):** Mojo 0.26+ should fix
   `unsafe_get_as_pointer`. Then rewrite assembly in pure Mojo for additional
   speedup on the scatter-add loop.

2. **Sparse assembly:** Use `scipy.sparse.coo_matrix` for assembly instead of
   dense. For problems > 5000 DOF, sparse Cholesky (CHOLMOD) would be faster
   than dense.

3. **np.add.at for scatter-add:** Replace the serial scatter loop with
   `np.add.at(K, (row_idx, col_idx), values)` for the global assembly.

## Files Modified

- `/Users/alanknudson/Applications/Bonsai_ai/mojo_modules/bonsai_fea_fast.py`
  -- Added vectorized assembly functions, `solve_vectorized()` as default path
- `/Users/alanknudson/Applications/Bonsai_ai/mojo_modules/benchmark_fea.py`
  -- Updated to benchmark all four solver paths

## References

- [Mojo Unsafe Pointers](https://docs.modular.com/mojo/manual/pointers/unsafe-pointers/)
- [UnsafePointer API](https://docs.modular.com/mojo/std/memory/unsafe_pointer/UnsafePointer/)
- [PythonModuleBuilder API](https://docs.modular.com/mojo/std/python/bindings/PythonModuleBuilder/)
- [Zero-Copy Mojo/Python Discussion](https://hexshift.medium.com/zero-copy-data-sharing-between-python-and-mojo-is-it-possible-yet-and-what-are-the-workarounds-3d7d7ba62382)
- [Mojo Buffer Protocol Feature Request](https://github.com/modular/modular/issues/1515)
- [NumPy ctypeslib docs](https://numpy.org/doc/stable/reference/routines.ctypeslib.html)
- [Cython-to-Mojo Translation](https://fnands.com/blog/2025/sklearn-mojo-dbscan-inner/)
- [Mojo vectorize API](https://docs.modular.com/mojo/stdlib/algorithm/functional/vectorize/)
- [NumPy einsum docs](https://numpy.org/doc/stable/reference/generated/numpy.einsum.html)
