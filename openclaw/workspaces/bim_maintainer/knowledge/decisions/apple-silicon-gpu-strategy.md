# Architecture Decision: Apple Silicon GPU Strategy

## Date
2026-03-31

## Hardware
Apple M5 (base): 10 GPU cores, ~5.1 TFLOPS FP32, 130 GB/s effective bandwidth, Metal 4

## Key Finding

For BIM-scale compute on Apple Silicon, **the CPU (AMX/Accelerate) is competitive with the GPU for most workloads**. The M5 GPU gives 2-5x over optimized CPU for parallel portions, but after Amdahl's law expect 1.5-3x end-to-end. This is NOT the 50-100x seen on discrete NVIDIA GPUs.

## Tiered GPU Strategy

### Tier 1: Use NOW (production-viable)
- **MLX** for dense linear algebra (matmul, solve, cholesky, eigh) — runs on GPU with zero custom kernels
- **Apple Accelerate via NumPy/SciPy** for sparse solvers — uses AMX coprocessor on CPU
- Both are pip-installable and work today

### Tier 2: Use for specific GPU workloads
- **pymetal-cpp / pyobjc + Metal** for custom GPU kernels (vertex transforms, parallel element processing)
- Write MSL kernels, dispatch from Python
- Mature Metal API underneath

### Tier 3: Experimental only
- **Mojo Metal** — promising but too many sharp edges (no kernel debug, zero-copy bugs, 32-bit atomics only)
- Wait for 1-2 more releases

### Do NOT attempt on GPU
- BVH construction (do on CPU)
- Sparse global FEA assembly (atomics issues)
- Neural Accelerator access from Mojo (only via MLX/Metal 4)

## What Maps to GPU Well on M5

| Workload | GPU fit | Why |
|---|---|---|
| Vertex transforms (4x4 * vec4) | Good above 100K vertices | Embarrassingly parallel, no atomics |
| Element stiffness (12x12 per element) | Good above 1000 elements | Independent per element |
| Dense matmul (MLX) | Good | Neural accelerator boost |
| Dense solve/cholesky (MLX) | Good for <5000 DOF | MLX has these built in |
| Sparse matrix-vector product | Mediocre | Bandwidth-bound, irregular access |
| BVH traversal | Possible | Read-only tree walk |
| BVH construction | Bad | Needs atomics + complex control flow |
| Global sparse assembly | Bad | Scatter-add needs 64-bit atomics |

## Mojo Metal Specific Issues (0.25.6.1)
- No print/debug inside GPU kernels
- Zero-copy (unified memory) gives incorrect results — must use explicit copies
- syncwarp() has no memory fence on Apple (execution sync only)
- Only 32-bit atomics available
- No GPU kernel debugging tools

## Practical Approach for Bonsai AI

1. FEA solver: **Mojo CPU SIMD** for element stiffness + assembly, **MLX GPU** for dense solve when <5000 DOF, **SciPy sparse** for larger
2. Tessellation: **Mojo CPU SIMD** (vertex count is usually <100K for buildings, launch overhead dominates)
3. Batch transforms: **Mojo CPU SIMD** for now, add Metal dispatch when models grow
4. Re-evaluate Mojo Metal every quarter as the backend matures

## Sources
- Apple M5 Roofline: michaelstinkerings.org
- Mojo Apple GPU Forum: forum.modular.com/t/apple-silicon-gpu-support-in-mojo/2295
- MLX linalg: ml-explore.github.io/mlx
- pymetal-cpp: github.com/shakfu/pymetal-cpp
