# Mojo FEA Assembly Optimization -- Research & Implementation Plan

**Date:** 2026-03-30
**Status:** Research complete, implementation ready

## Problem Statement

The Mojo FEA module (`bonsai_fea.mojo`) is SLOWER than NumPy for medium-to-large
problems because the assembly loop makes too many Python/Mojo interop calls per
element:

| Problem | DOF | NumPy (ms) | Mojo (ms) | Mojo speedup |
|---------|----:|-----------:|----------:|-------------:|
| Small (2x2) | 54 | 0.5 | 1.8 | 0.28x (slower) |
| Medium (5x3) | 144 | 1.4 | 5.7 | 0.25x (slower) |
| Large (10x5) | 396 | 5.3 | 19.8 | 0.27x (slower) |
| XL (20x8) | 1134 | 27.1 | 72.9 | 0.37x (slower) |
| XXL (30x10) | 2046 | 95.1 | 182.2 | 0.52x (slower) |

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

At 600 elements, that is ~60,000 interop calls just for assembly. Each call
involves PythonObject allocation, reference counting, and GIL acquisition.

## Research Findings

### 1. Zero-Copy Pointer Access (CONFIRMED WORKING)

Mojo can get a raw typed pointer to numpy array data with zero copy:

```mojo
from std.python import Python

def process_array() raises:
    np = Python.import_module("numpy")
    arr = np.array(Python.list(1, 2, 3, 4, 5, 6, 7, 8, 9))
    ptr = arr.ctypes.data.unsafe_get_as_pointer[DType.int64]()
    for i in range(9):
        print(ptr[i])  # Direct memory access, no PythonObject overhead
```

**Source:** [Mojo Unsafe Pointers docs](https://docs.modular.com/mojo/manual/pointers/unsafe-pointers/)

This is the key enabler. Once we have raw pointers to the numpy arrays, we can
do the entire assembly loop in pure Mojo without any PythonObject interop.

### 2. SIMD Vectorization Available

Mojo's `vectorize` function can process multiple float64 values simultaneously:

```mojo
from algorithm.functional import vectorize

fn process[width: Int](i: Int):
    var vals = ptr.load[width=width](i)
    # Process SIMD vector of `width` elements

vectorize[process, simdwidthof[Float64]()](n)
```

For 12x12 matrix operations, the inner loops can be SIMD-vectorized. On ARM
NEON (M5), SIMD width for Float64 is 2, so each operation handles 2 doubles.

### 3. Buffer Protocol Not Yet Supported

Mojo does not yet support Python's buffer protocol natively. The
`unsafe_get_as_pointer` via `ctypes.data` is the current best path.

**Feature request:** [modular/modular#1515](https://github.com/modular/modular/issues/1515)

### 4. MLX for Batched Element Stiffness (VIABLE BUT COMPLEX)

MLX's batched matmul could compute all element stiffness matrices simultaneously
on the GPU. However:
- Element stiffness matrices are only 12x12 (too small for GPU to be efficient)
- The scatter-add assembly step has irregular memory access (poor GPU fit)
- Adds dependency complexity for marginal gain at typical FEA sizes
- **Verdict: Not worth it for beam FEA. Better suited for large plate/solid FEA.**

### 5. numpy.ctypeslib (ALTERNATIVE PATH)

Could compile the Mojo assembly kernel to a standalone .so and call it via
ctypes, completely bypassing PythonObject:

```python
import ctypes
import numpy.ctypeslib as ctl
lib = ctl.load_library('bonsai_fea_kernel', '.')
lib.assemble_batch.argtypes = [
    ctl.ndpointer(dtype=np.float64, ndim=2, flags='C'),  # nodes
    ctl.ndpointer(dtype=np.int32, ndim=2, flags='C'),    # elements
    ...
]
```

This would work but requires maintaining a separate C-ABI export alongside the
PythonModuleBuilder exports. The `unsafe_get_as_pointer` approach is simpler
since it works within the existing module structure.

## Implementation Plan

### Strategy: Batch Assembly via Raw Pointers

Instead of per-element PythonObject interop, the optimized `solve()` function will:

1. **Cross boundary ONCE**: Accept numpy arrays as PythonObject, immediately
   extract raw pointers via `ctypes.data.unsafe_get_as_pointer`
2. **Assembly in pure Mojo**: Loop over elements using raw pointer arithmetic,
   build 12x12 stiffness matrices using Mojo Float64 math (no PythonObject),
   scatter-add into global K using direct pointer writes
3. **Return to Python**: Convert the assembled K_global back to numpy for
   Cholesky solve (scipy is already fast at this)

### Expected Performance

- Assembly loop: ~100x reduction in overhead (eliminate ~100 interop calls/element)
- Stiffness computation: Native Float64 math instead of PythonObject arithmetic
- Matrix multiply: SIMD-vectorized 12x12 matmul
- Target: Match or beat NumPy assembly speed, then Cholesky dominates total time

### Architecture

```
Python                          Mojo
------                          ----
nodes (np.float64)  ------>  UnsafePointer[Float64] via ctypes.data
elements (np.int64) ------>  UnsafePointer[Int64] via ctypes.data
properties (np.float64) -->  UnsafePointer[Float64] via ctypes.data

                             for e in range(n_elements):
                                 # Pure Mojo pointer arithmetic
                                 ni = elem_ptr[e*2]
                                 nj = elem_ptr[e*2+1]
                                 # Compute ke_local in pure Float64
                                 # SIMD matmul: T^T @ ke @ T
                                 # Scatter-add to K_global pointer

K_global (np.float64)  <--  Write results back to numpy array

scipy.cho_factor(K_ff)        # Cholesky in scipy (already fast)
scipy.cho_solve(cho, F)       # Back-substitution per load case
```

### Implementation Steps

1. Add `assemble_batch()` function to `bonsai_fea.mojo` that:
   - Accepts nodes, elements, properties as PythonObject (numpy arrays)
   - Extracts raw pointers immediately
   - Does full assembly loop in pure Mojo
   - Returns assembled K_global as numpy array

2. Add pure-Mojo helper functions:
   - `_beam_ke_local_native()` -- compute 12x12 stiffness using Float64
   - `_beam_transform_native()` -- compute 12x12 transform using Float64
   - `_matmul_12x12()` -- SIMD-optimized 12x12 matrix multiply

3. Update `bonsai_fea_fast.py` to use `bonsai_fea.assemble_batch()` for assembly
   instead of its own Python loop

4. Run benchmarks to measure improvement

## References

- [Mojo Unsafe Pointers](https://docs.modular.com/mojo/manual/pointers/unsafe-pointers/)
- [UnsafePointer API](https://docs.modular.com/mojo/stdlib/memory/unsafe_pointer/UnsafePointer/)
- [PythonModuleBuilder API](https://docs.modular.com/mojo/std/python/bindings/PythonModuleBuilder/)
- [Zero-Copy Mojo/Python Discussion](https://hexshift.medium.com/zero-copy-data-sharing-between-python-and-mojo-is-it-possible-yet-and-what-are-the-workarounds-3d7d7ba62382)
- [Mojo Buffer Protocol Feature Request](https://github.com/modular/modular/issues/1515)
- [NumPy ctypeslib docs](https://numpy.org/doc/stable/reference/routines.ctypeslib.html)
- [Cython-to-Mojo Translation](https://fnands.com/blog/2025/sklearn-mojo-dbscan-inner/)
- [Mojo vectorize API](https://docs.modular.com/mojo/stdlib/algorithm/functional/vectorize/)
