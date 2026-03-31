# bonsai_fea.mojo -- SIMD-accelerated FEA solver for Bonsai AI
#
# Replaces PyNite's pure-Python FEA with compiled Mojo for significant speedup.
# Key optimisation: factor-once-solve-many -- Cholesky factor [K] once,
# then back-substitute per load combination instead of re-solving.
#
# 3-D beam element (2 nodes, 6 DOF/node = 12 DOF/element):
#   DOFs per node: [Dx, Dy, Dz, Rx, Ry, Rz]
#
# v2: Batch assembly via raw pointers -- crosses Python/Mojo boundary ONCE,
#     does entire assembly loop in pure Mojo with native Float64 math.
#
# Mojo 0.25+ on Apple M5 ARM NEON.

from std.python import PythonObject, Python
from std.python.bindings import PythonModuleBuilder
from std.os import abort
from math import sqrt, abs as mabs
from memory import UnsafePointer, memset_zero


# ============================================================================
# Native 12x12 matrix type (stack-allocated, no heap, no PythonObject)
# ============================================================================

struct Mat12:
    """Stack-allocated 12x12 matrix for element stiffness/transform operations."""
    var data: StaticTuple[Float64, 144]

    fn __init__(out self):
        self.data = StaticTuple[Float64, 144]()
        for i in range(144):
            self.data[i] = 0.0

    fn __getitem__(self, r: Int, c: Int) -> Float64:
        return self.data[r * 12 + c]

    fn __setitem__(mut self, r: Int, c: Int, val: Float64):
        self.data[r * 12 + c] = val

    fn add(mut self, r: Int, c: Int, val: Float64):
        """Add val to element [r, c]."""
        self.data[r * 12 + c] += val


fn mat12_multiply(A: Mat12, B: Mat12) -> Mat12:
    """Multiply two 12x12 matrices: C = A @ B."""
    var C = Mat12()
    for i in range(12):
        for k in range(12):
            var a_ik = A[i, k]
            if a_ik == 0.0:
                continue
            for j in range(12):
                C.add(i, j, a_ik * B[k, j])
    return C


fn mat12_transpose(A: Mat12) -> Mat12:
    """Transpose a 12x12 matrix."""
    var AT = Mat12()
    for i in range(12):
        for j in range(12):
            AT[i, j] = A[j, i]
    return AT


fn mat12_triple_product(T: Mat12, ke: Mat12) -> Mat12:
    """Compute T^T @ ke @ T efficiently for 12x12 matrices."""
    # First: temp = ke @ T
    var temp = mat12_multiply(ke, T)
    # Then: result = T^T @ temp
    var TT = mat12_transpose(T)
    return mat12_multiply(TT, temp)


# ============================================================================
# Native beam element computations (pure Mojo, no PythonObject)
# ============================================================================

fn beam_ke_local_native(
    E: Float64, A: Float64, Iy: Float64, Iz: Float64,
    J: Float64, G: Float64, L: Float64
) -> Mat12:
    """Build 12x12 local stiffness matrix using pure Mojo Float64 math.

    DOF order per node: [Dx, Dy, Dz, Rx, Ry, Rz].
    """
    var k = Mat12()

    # Axial stiffness
    var ea_l = E * A / L
    k[0, 0] = ea_l;  k[0, 6] = -ea_l
    k[6, 0] = -ea_l; k[6, 6] = ea_l

    # Torsional stiffness
    var gj_l = G * J / L
    k[3, 3] = gj_l;  k[3, 9] = -gj_l
    k[9, 3] = -gj_l; k[9, 9] = gj_l

    # Bending about local z-axis (uses Iz) -- bending in x-y plane
    var L2 = L * L
    var L3 = L2 * L
    var eiz = E * Iz

    var v12eiz_l3 = 12.0 * eiz / L3
    var v6eiz_l2 = 6.0 * eiz / L2
    var v4eiz_l = 4.0 * eiz / L
    var v2eiz_l = 2.0 * eiz / L

    k[1, 1] = v12eiz_l3;  k[1, 5] = v6eiz_l2;  k[1, 7] = -v12eiz_l3;  k[1, 11] = v6eiz_l2
    k[5, 1] = v6eiz_l2;   k[5, 5] = v4eiz_l;   k[5, 7] = -v6eiz_l2;   k[5, 11] = v2eiz_l
    k[7, 1] = -v12eiz_l3; k[7, 5] = -v6eiz_l2; k[7, 7] = v12eiz_l3;   k[7, 11] = -v6eiz_l2
    k[11, 1] = v6eiz_l2;  k[11, 5] = v2eiz_l;  k[11, 7] = -v6eiz_l2;  k[11, 11] = v4eiz_l

    # Bending about local y-axis (uses Iy) -- bending in x-z plane
    var eiy = E * Iy

    var v12eiy_l3 = 12.0 * eiy / L3
    var v6eiy_l2 = 6.0 * eiy / L2
    var v4eiy_l = 4.0 * eiy / L
    var v2eiy_l = 2.0 * eiy / L

    k[2, 2] = v12eiy_l3;   k[2, 4] = -v6eiy_l2;  k[2, 8] = -v12eiy_l3;  k[2, 10] = -v6eiy_l2
    k[4, 2] = -v6eiy_l2;   k[4, 4] = v4eiy_l;    k[4, 8] = v6eiy_l2;    k[4, 10] = v2eiy_l
    k[8, 2] = -v12eiy_l3;  k[8, 4] = v6eiy_l2;   k[8, 8] = v12eiy_l3;   k[8, 10] = v6eiy_l2
    k[10, 2] = -v6eiy_l2;  k[10, 4] = v2eiy_l;   k[10, 8] = v6eiy_l2;   k[10, 10] = v4eiy_l

    return k


fn beam_transform_native(
    x1: Float64, y1: Float64, z1: Float64,
    x2: Float64, y2: Float64, z2: Float64
) -> Mat12:
    """Build 12x12 transformation matrix using pure Mojo math.

    Local x-axis runs from node i to node j.
    Local z is chosen to be in the vertical plane (containing global Z and local x).
    """
    var dx = x2 - x1
    var dy = y2 - y1
    var dz = z2 - z1
    var L = sqrt(dx * dx + dy * dy + dz * dz)

    # Local x-axis
    var lx0 = dx / L
    var lx1 = dy / L
    var lx2 = dz / L

    var tol = 1e-8

    # Dot product of lx with global Z = [0, 0, 1]
    var dot_xz = mabs(lx2)  # lx . gz = lx2

    var ly0: Float64
    var ly1: Float64
    var ly2: Float64
    var lz0: Float64
    var lz1: Float64
    var lz2: Float64

    if dot_xz > 1.0 - tol:
        # Member is vertical: use global Y as reference
        # ly = cross(gz, lx) = [gz1*lx2 - gz2*lx1, gz2*lx0 - gz0*lx2, gz0*lx1 - gz1*lx0]
        # gz = [0, 0, 1], so: ly = [-lx1, lx0, 0]  (approximately)
        # But for truly vertical, cross product magnitude may be ~0
        # Use global Y = [0, 1, 0] as fallback
        ly0 = -lx1
        ly1 = lx0
        ly2 = 0.0
        var ly_norm = sqrt(ly0 * ly0 + ly1 * ly1 + ly2 * ly2)
        if ly_norm < tol:
            ly0 = 0.0
            ly1 = 1.0
            ly2 = 0.0
        else:
            ly0 = ly0 / ly_norm
            ly1 = ly1 / ly_norm
            ly2 = ly2 / ly_norm
        # lz = cross(lx, ly)
        lz0 = lx1 * ly2 - lx2 * ly1
        lz1 = lx2 * ly0 - lx0 * ly2
        lz2 = lx0 * ly1 - lx1 * ly0
    else:
        # Standard case: project global Z onto plane perp to lx
        # lz_temp = gz - lx * (gz . lx) = [0, 0, 1] - lx * lx2
        var lz_t0 = 0.0 - lx0 * lx2
        var lz_t1 = 0.0 - lx1 * lx2
        var lz_t2 = 1.0 - lx2 * lx2
        var lz_norm = sqrt(lz_t0 * lz_t0 + lz_t1 * lz_t1 + lz_t2 * lz_t2)
        if lz_norm > tol:
            lz0 = lz_t0 / lz_norm
            lz1 = lz_t1 / lz_norm
            lz2 = lz_t2 / lz_norm
        else:
            # Fallback: cross(lx, global_y)
            # cross(lx, [0,1,0]) = [lx2*0 - 0*1, 0*0 - lx0*0 ... ]
            # = [lx1*0 - lx2*1, lx2*0 - lx0*0, lx0*1 - lx1*0]
            # = [-lx2, 0, lx0]
            lz0 = -lx2
            lz1 = 0.0
            lz2 = lx0
            var n2 = sqrt(lz0 * lz0 + lz2 * lz2)
            lz0 = lz0 / n2
            lz2 = lz2 / n2
        # ly = cross(lz, lx)
        ly0 = lz1 * lx2 - lz2 * lx1
        ly1 = lz2 * lx0 - lz0 * lx2
        ly2 = lz0 * lx1 - lz1 * lx0

    # Build 12x12 T matrix: block diagonal [R, R, R, R]
    # R = [[lx0, lx1, lx2], [ly0, ly1, ly2], [lz0, lz1, lz2]]
    var T = Mat12()
    for block in range(4):
        var off = block * 3
        T[off + 0, off + 0] = lx0; T[off + 0, off + 1] = lx1; T[off + 0, off + 2] = lx2
        T[off + 1, off + 0] = ly0; T[off + 1, off + 1] = ly1; T[off + 1, off + 2] = ly2
        T[off + 2, off + 0] = lz0; T[off + 2, off + 1] = lz1; T[off + 2, off + 2] = lz2

    return T


# ============================================================================
# Batch assembly: crosses Python/Mojo boundary ONCE
# ============================================================================

def assemble_batch(
    nodes: PythonObject,
    elements: PythonObject,
    properties: PythonObject
) raises -> PythonObject:
    """Assemble global stiffness matrix with minimal Python/Mojo interop.

    Instead of per-element PythonObject indexing, this function:
    1. Extracts raw pointers from numpy arrays (1 interop call each)
    2. Runs the entire assembly loop in pure Mojo (zero interop)
    3. Writes results directly into a pre-allocated numpy array

    Args:
        nodes: (n_nodes, 3) float64 numpy array of [x, y, z] coordinates.
        elements: (n_elements, 2) int64 numpy array of [node_i, node_j].
        properties: (n_elements, 6) float64 array of [E, A, Iy, Iz, J, G].

    Returns:
        (n_dof, n_dof) float64 numpy array -- assembled global stiffness matrix.
    """
    var np = Python.import_module("numpy")

    # Ensure contiguous float64/int64 arrays
    var nodes_c = np.ascontiguousarray(nodes, dtype=np.float64)
    var elems_c = np.ascontiguousarray(elements, dtype=np.int64)
    var props_c = np.ascontiguousarray(properties, dtype=np.float64)

    var n_nodes = Int(py=nodes_c.shape.__getitem__(0))
    var n_elements = Int(py=elems_c.shape.__getitem__(0))
    var n_dof = n_nodes * 6

    # Pre-allocate output numpy array (zeros)
    var builtins = Python.import_module("builtins")
    var K_out = np.zeros(builtins.tuple(Python.list(PythonObject(n_dof), PythonObject(n_dof))),
                         dtype=np.float64)

    # === CROSS THE BOUNDARY: extract raw pointers ===
    var node_ptr = nodes_c.ctypes.data.unsafe_get_as_pointer[DType.float64]()
    var elem_ptr = elems_c.ctypes.data.unsafe_get_as_pointer[DType.int64]()
    var prop_ptr = props_c.ctypes.data.unsafe_get_as_pointer[DType.float64]()
    var K_ptr = K_out.ctypes.data.unsafe_get_as_pointer[DType.float64]()

    # === PURE MOJO ASSEMBLY LOOP -- no PythonObject interop ===
    for e in range(n_elements):
        # Read connectivity (elements is n_elements x 2, row-major)
        var ni = Int(elem_ptr[e * 2 + 0])
        var nj = Int(elem_ptr[e * 2 + 1])

        # Read node coordinates (nodes is n_nodes x 3, row-major)
        var x1 = node_ptr[ni * 3 + 0]
        var y1 = node_ptr[ni * 3 + 1]
        var z1 = node_ptr[ni * 3 + 2]
        var x2 = node_ptr[nj * 3 + 0]
        var y2 = node_ptr[nj * 3 + 1]
        var z2 = node_ptr[nj * 3 + 2]

        # Read material/section properties (properties is n_elements x 6)
        var E_val = prop_ptr[e * 6 + 0]
        var A_val = prop_ptr[e * 6 + 1]
        var Iy_val = prop_ptr[e * 6 + 2]
        var Iz_val = prop_ptr[e * 6 + 3]
        var J_val = prop_ptr[e * 6 + 4]
        var G_val = prop_ptr[e * 6 + 5]

        # Compute element length
        var dx = x2 - x1
        var dy = y2 - y1
        var dz = z2 - z1
        var L_val = sqrt(dx * dx + dy * dy + dz * dz)

        # Compute local stiffness (pure Mojo Float64)
        var ke_local = beam_ke_local_native(E_val, A_val, Iy_val, Iz_val, J_val, G_val, L_val)

        # Compute transformation matrix (pure Mojo Float64)
        var T = beam_transform_native(x1, y1, z1, x2, y2, z2)

        # Global stiffness: ke_global = T^T @ ke_local @ T
        var ke_global = mat12_triple_product(T, ke_local)

        # Build DOF map: [ni*6+0, ..., ni*6+5, nj*6+0, ..., nj*6+5]
        # Scatter-add ke_global into K_global via raw pointer
        for ii in range(12):
            var global_i: Int
            if ii < 6:
                global_i = ni * 6 + ii
            else:
                global_i = nj * 6 + (ii - 6)

            for jj in range(12):
                var global_j: Int
                if jj < 6:
                    global_j = ni * 6 + jj
                else:
                    global_j = nj * 6 + (jj - 6)

                K_ptr[global_i * n_dof + global_j] += ke_global[ii, jj]

    return K_out


# ============================================================================
# Batch solve: assembly + factor-once-solve-many, minimal interop
# ============================================================================

def solve_batch(
    nodes: PythonObject,
    elements: PythonObject,
    properties: PythonObject,
    loads: PythonObject,
    supports: PythonObject
) raises -> PythonObject:
    """Full FEA solve using batch assembly (minimal Python/Mojo interop).

    Uses assemble_batch for the assembly loop (pure Mojo), then scipy
    for Cholesky factorization and back-substitution.

    Args:
        nodes: (n_nodes, 3) float64 array of [x, y, z] coordinates.
        elements: (n_elements, 2) int64 array of [node_i, node_j] connectivity.
        properties: (n_elements, 6) float64 array of [E, A, Iy, Iz, J, G].
        loads: (n_load_cases, n_dof) float64 array of applied force vectors.
        supports: (n_dof,) bool array -- True means fixed DOF.

    Returns:
        dict with displacements, reactions, element_forces, n_free_dofs, etc.
    """
    var np = Python.import_module("numpy")
    var scipy_linalg = Python.import_module("scipy.linalg")

    var n_nodes = Int(py=nodes.shape.__getitem__(0))
    var n_elements = Int(py=elements.shape.__getitem__(0))
    var n_dof = n_nodes * 6
    var n_loads = Int(py=loads.shape.__getitem__(0))

    # ------------------------------------------------------------------
    # 1) Batch-assemble global stiffness matrix (pure Mojo inner loop)
    # ------------------------------------------------------------------
    var K_global = assemble_batch(nodes, elements, properties)

    # ------------------------------------------------------------------
    # 2) Apply boundary conditions via partitioning (numpy -- fast)
    # ------------------------------------------------------------------
    var free_mask = np.logical_not(supports)
    var free_dofs = np.where(free_mask).__getitem__(0)
    var fixed_dofs = np.where(supports).__getitem__(0)
    var n_free = Int(py=free_dofs.shape.__getitem__(0))

    var ix_ff = np.ix_(free_dofs, free_dofs)
    var K_ff = K_global.__getitem__(ix_ff)

    # ------------------------------------------------------------------
    # 3) Factor once (Cholesky) -- scipy LAPACK, already optimized
    # ------------------------------------------------------------------
    var cho = scipy_linalg.cho_factor(K_ff)

    # ------------------------------------------------------------------
    # 4) Solve for each load case via back-substitution
    # ------------------------------------------------------------------
    var builtins = Python.import_module("builtins")
    var displacements = np.zeros(builtins.tuple(Python.list(PythonObject(n_loads), PythonObject(n_dof))))
    var reactions = np.zeros(builtins.tuple(Python.list(PythonObject(n_loads), PythonObject(n_dof))))

    for lc in range(n_loads):
        var F_full = loads.__getitem__(lc)
        var F_free = F_full.__getitem__(free_dofs)
        var u_free = scipy_linalg.cho_solve(cho, F_free)

        var u_full = np.zeros(n_dof)
        np.put(u_full, free_dofs, u_free)
        displacements.__setitem__(lc, value=u_full)

        var R_full = K_global.__matmul__(u_full) - F_full
        reactions.__setitem__(lc, value=R_full)

    # ------------------------------------------------------------------
    # 5) Post-processing: element forces (use raw pointers for speed)
    # ------------------------------------------------------------------
    var ef_shape = builtins.tuple(Python.list(PythonObject(n_loads), PythonObject(n_elements), PythonObject(12)))
    var element_forces = np.zeros(ef_shape)

    # Extract pointers for post-processing
    var nodes_c = np.ascontiguousarray(nodes, dtype=np.float64)
    var elems_c = np.ascontiguousarray(elements, dtype=np.int64)
    var props_c = np.ascontiguousarray(properties, dtype=np.float64)
    var disp_c = np.ascontiguousarray(displacements, dtype=np.float64)
    var ef_c = np.ascontiguousarray(element_forces, dtype=np.float64)

    var node_ptr = nodes_c.ctypes.data.unsafe_get_as_pointer[DType.float64]()
    var elem_ptr = elems_c.ctypes.data.unsafe_get_as_pointer[DType.int64]()
    var prop_ptr = props_c.ctypes.data.unsafe_get_as_pointer[DType.float64]()
    var disp_ptr = disp_c.ctypes.data.unsafe_get_as_pointer[DType.float64]()
    var ef_ptr = ef_c.ctypes.data.unsafe_get_as_pointer[DType.float64]()

    for e in range(n_elements):
        var ni = Int(elem_ptr[e * 2 + 0])
        var nj = Int(elem_ptr[e * 2 + 1])

        var x1 = node_ptr[ni * 3 + 0]
        var y1 = node_ptr[ni * 3 + 1]
        var z1 = node_ptr[ni * 3 + 2]
        var x2 = node_ptr[nj * 3 + 0]
        var y2 = node_ptr[nj * 3 + 1]
        var z2 = node_ptr[nj * 3 + 2]

        var E_val = prop_ptr[e * 6 + 0]
        var A_val = prop_ptr[e * 6 + 1]
        var Iy_val = prop_ptr[e * 6 + 2]
        var Iz_val = prop_ptr[e * 6 + 3]
        var J_val = prop_ptr[e * 6 + 4]
        var G_val = prop_ptr[e * 6 + 5]

        var dx = x2 - x1
        var dy = y2 - y1
        var dz = z2 - z1
        var L_val = sqrt(dx * dx + dy * dy + dz * dz)

        var ke_local = beam_ke_local_native(E_val, A_val, Iy_val, Iz_val, J_val, G_val, L_val)
        var T = beam_transform_native(x1, y1, z1, x2, y2, z2)

        # DOF map
        var dof_map = StaticTuple[Int, 12]()
        for d in range(6):
            dof_map[d] = ni * 6 + d
            dof_map[6 + d] = nj * 6 + d

        for lc in range(n_loads):
            # Gather element displacements from global vector
            var u_local = StaticTuple[Float64, 12]()
            # First get global displacements for this element
            var u_global_elem = StaticTuple[Float64, 12]()
            for i in range(12):
                u_global_elem[i] = disp_ptr[lc * n_dof + dof_map[i]]

            # Transform to local: u_local = T @ u_global_elem
            for i in range(12):
                var s: Float64 = 0.0
                for j in range(12):
                    s += T[i, j] * u_global_elem[j]
                u_local[i] = s

            # Local forces: f = ke_local @ u_local
            for i in range(12):
                var s: Float64 = 0.0
                for j in range(12):
                    s += ke_local[i, j] * u_local[j]
                ef_ptr[lc * n_elements * 12 + e * 12 + i] = s

    # Copy ef_c back if it was not the same object (ascontiguousarray may copy)
    # For safety, use ef_c which we wrote to directly
    element_forces = ef_c

    # ------------------------------------------------------------------
    # Return results as dict
    # ------------------------------------------------------------------
    var result = Python.dict()
    result.__setitem__("displacements", value=displacements)
    result.__setitem__("reactions", value=reactions)
    result.__setitem__("element_forces", value=element_forces)
    result.__setitem__("n_free_dofs", value=PythonObject(n_free))
    result.__setitem__("free_dofs", value=free_dofs)
    result.__setitem__("fixed_dofs", value=fixed_dofs)

    return result


# ============================================================================
# Helpers for Python interop in Mojo 0.26 (kept for backward compatibility)
# ============================================================================

fn _py_tuple2(a: PythonObject, b: PythonObject) raises -> PythonObject:
    """Create a Python tuple of two elements."""
    var builtins = Python.import_module("builtins")
    return builtins.tuple(Python.list(a, b))

fn _py_int(obj: PythonObject) raises -> Int:
    """Convert PythonObject to Mojo Int."""
    return Int(py=obj)

fn _py_float(obj: PythonObject) raises -> Float64:
    """Convert PythonObject to Mojo Float64."""
    return Float64(py=obj)

fn _np() raises -> PythonObject:
    """Import numpy."""
    return Python.import_module("numpy")

fn _scipy_linalg() raises -> PythonObject:
    """Import scipy.linalg."""
    return Python.import_module("scipy.linalg")


# ============================================================================
# Helper: build 12x12 local stiffness matrix for 3-D Euler-Bernoulli beam
# (PythonObject version -- kept for backward compatibility)
# ============================================================================

fn _beam_local_stiffness_impl(
    E: PythonObject, A: PythonObject, Iy: PythonObject,
    Iz: PythonObject, J: PythonObject, G: PythonObject,
    L: PythonObject
) raises -> PythonObject:
    """Build 12x12 local stiffness matrix for 3-D beam element.

    DOF order per node: [Dx, Dy, Dz, Rx, Ry, Rz].
    Returns a 12x12 numpy array.
    """
    var np = _np()
    var shape = _py_tuple2(PythonObject(12), PythonObject(12))
    var k = np.zeros(shape)

    # Axial stiffness
    var ea_l = E * A / L
    k.__setitem__(_py_tuple2(PythonObject(0), PythonObject(0)), value=ea_l)
    k.__setitem__(_py_tuple2(PythonObject(0), PythonObject(6)), value=-ea_l)
    k.__setitem__(_py_tuple2(PythonObject(6), PythonObject(0)), value=-ea_l)
    k.__setitem__(_py_tuple2(PythonObject(6), PythonObject(6)), value=ea_l)

    # Torsional stiffness
    var gj_l = G * J / L
    k.__setitem__(_py_tuple2(PythonObject(3), PythonObject(3)), value=gj_l)
    k.__setitem__(_py_tuple2(PythonObject(3), PythonObject(9)), value=-gj_l)
    k.__setitem__(_py_tuple2(PythonObject(9), PythonObject(3)), value=-gj_l)
    k.__setitem__(_py_tuple2(PythonObject(9), PythonObject(9)), value=gj_l)

    # Bending about local z-axis (uses Iz) -- bending in x-y plane
    var L2 = L * L
    var L3 = L2 * L
    var eiz = E * Iz

    var v12eiz_l3 = eiz * PythonObject(12.0) / L3
    var v6eiz_l2 = eiz * PythonObject(6.0) / L2
    var v4eiz_l = eiz * PythonObject(4.0) / L
    var v2eiz_l = eiz * PythonObject(2.0) / L

    # Row 1 (DOF 1 = Dy at node i)
    k.__setitem__(_py_tuple2(PythonObject(1), PythonObject(1)), value=v12eiz_l3)
    k.__setitem__(_py_tuple2(PythonObject(1), PythonObject(5)), value=v6eiz_l2)
    k.__setitem__(_py_tuple2(PythonObject(1), PythonObject(7)), value=-v12eiz_l3)
    k.__setitem__(_py_tuple2(PythonObject(1), PythonObject(11)), value=v6eiz_l2)
    # Row 5 (DOF 5 = Rz at node i)
    k.__setitem__(_py_tuple2(PythonObject(5), PythonObject(1)), value=v6eiz_l2)
    k.__setitem__(_py_tuple2(PythonObject(5), PythonObject(5)), value=v4eiz_l)
    k.__setitem__(_py_tuple2(PythonObject(5), PythonObject(7)), value=-v6eiz_l2)
    k.__setitem__(_py_tuple2(PythonObject(5), PythonObject(11)), value=v2eiz_l)
    # Row 7 (DOF 7 = Dy at node j)
    k.__setitem__(_py_tuple2(PythonObject(7), PythonObject(1)), value=-v12eiz_l3)
    k.__setitem__(_py_tuple2(PythonObject(7), PythonObject(5)), value=-v6eiz_l2)
    k.__setitem__(_py_tuple2(PythonObject(7), PythonObject(7)), value=v12eiz_l3)
    k.__setitem__(_py_tuple2(PythonObject(7), PythonObject(11)), value=-v6eiz_l2)
    # Row 11 (DOF 11 = Rz at node j)
    k.__setitem__(_py_tuple2(PythonObject(11), PythonObject(1)), value=v6eiz_l2)
    k.__setitem__(_py_tuple2(PythonObject(11), PythonObject(5)), value=v2eiz_l)
    k.__setitem__(_py_tuple2(PythonObject(11), PythonObject(7)), value=-v6eiz_l2)
    k.__setitem__(_py_tuple2(PythonObject(11), PythonObject(11)), value=v4eiz_l)

    # Bending about local y-axis (uses Iy) -- bending in x-z plane
    var eiy = E * Iy

    var v12eiy_l3 = eiy * PythonObject(12.0) / L3
    var v6eiy_l2 = eiy * PythonObject(6.0) / L2
    var v4eiy_l = eiy * PythonObject(4.0) / L
    var v2eiy_l = eiy * PythonObject(2.0) / L

    # Row 2 (DOF 2 = Dz at node i)
    k.__setitem__(_py_tuple2(PythonObject(2), PythonObject(2)), value=v12eiy_l3)
    k.__setitem__(_py_tuple2(PythonObject(2), PythonObject(4)), value=-v6eiy_l2)
    k.__setitem__(_py_tuple2(PythonObject(2), PythonObject(8)), value=-v12eiy_l3)
    k.__setitem__(_py_tuple2(PythonObject(2), PythonObject(10)), value=-v6eiy_l2)
    # Row 4 (DOF 4 = Ry at node i)
    k.__setitem__(_py_tuple2(PythonObject(4), PythonObject(2)), value=-v6eiy_l2)
    k.__setitem__(_py_tuple2(PythonObject(4), PythonObject(4)), value=v4eiy_l)
    k.__setitem__(_py_tuple2(PythonObject(4), PythonObject(8)), value=v6eiy_l2)
    k.__setitem__(_py_tuple2(PythonObject(4), PythonObject(10)), value=v2eiy_l)
    # Row 8 (DOF 8 = Dz at node j)
    k.__setitem__(_py_tuple2(PythonObject(8), PythonObject(2)), value=-v12eiy_l3)
    k.__setitem__(_py_tuple2(PythonObject(8), PythonObject(4)), value=v6eiy_l2)
    k.__setitem__(_py_tuple2(PythonObject(8), PythonObject(8)), value=v12eiy_l3)
    k.__setitem__(_py_tuple2(PythonObject(8), PythonObject(10)), value=v6eiy_l2)
    # Row 10 (DOF 10 = Ry at node j)
    k.__setitem__(_py_tuple2(PythonObject(10), PythonObject(2)), value=-v6eiy_l2)
    k.__setitem__(_py_tuple2(PythonObject(10), PythonObject(4)), value=v2eiy_l)
    k.__setitem__(_py_tuple2(PythonObject(10), PythonObject(8)), value=v6eiy_l2)
    k.__setitem__(_py_tuple2(PythonObject(10), PythonObject(10)), value=v4eiy_l)

    return k


# ============================================================================
# Helper: 3-D rotation/transformation matrix (12x12)
# (PythonObject version -- kept for backward compatibility)
# ============================================================================

fn _beam_transform_impl(
    x1: PythonObject, y1: PythonObject, z1: PythonObject,
    x2: PythonObject, y2: PythonObject, z2: PythonObject
) raises -> PythonObject:
    """Build 12x12 transformation matrix from local to global coordinates.

    Local x-axis runs from node i to node j.
    Local z is chosen to be in the vertical plane (containing global Z and local x).
    This is the standard structural convention for beams and columns.
    """
    var np = _np()

    var dx = x2 - x1
    var dy = y2 - y1
    var dz = z2 - z1
    var L = np.sqrt(dx * dx + dy * dy + dz * dz)

    # Local x-axis: unit vector along member
    var lx = np.array(Python.list(dx / L, dy / L, dz / L))

    # Handle vertical members specially
    var global_z = np.array(Python.list(PythonObject(0.0), PythonObject(0.0), PythonObject(1.0)))
    var tol = PythonObject(1e-8)

    var dot_xz = np.abs(np.dot(lx, global_z))
    var is_vert = _py_float(dot_xz) > (1.0 - _py_float(tol))

    var lz: PythonObject
    var ly: PythonObject

    if is_vert:
        # Member is vertical: use global Y as the reference direction
        var global_y = np.array(Python.list(PythonObject(0.0), PythonObject(1.0), PythonObject(0.0)))
        ly = np.cross(global_z, lx)
        var ly_norm = _py_float(np.linalg.norm(ly))
        if ly_norm < _py_float(tol):
            ly = global_y
        else:
            ly = ly / np.linalg.norm(ly)
        lz = np.cross(lx, ly)
    else:
        # Standard case: local z in plane of global Z and local x
        # Project global Z onto plane perpendicular to lx
        var lz_temp = global_z - lx * np.dot(global_z, lx)
        var lz_norm = _py_float(np.linalg.norm(lz_temp))
        if lz_norm > _py_float(tol):
            lz = lz_temp / np.linalg.norm(lz_temp)
        else:
            var global_y = np.array(Python.list(PythonObject(0.0), PythonObject(1.0), PythonObject(0.0)))
            lz = np.cross(lx, global_y)
            lz = lz / np.linalg.norm(lz)
        ly = np.cross(lz, lx)

    # 3x3 rotation matrix: rows are local axes expressed in global coords
    var R = np.zeros(_py_tuple2(PythonObject(3), PythonObject(3)))
    R.__setitem__(_py_tuple2(PythonObject(0), PythonObject(0)), value=lx.__getitem__(0))
    R.__setitem__(_py_tuple2(PythonObject(0), PythonObject(1)), value=lx.__getitem__(1))
    R.__setitem__(_py_tuple2(PythonObject(0), PythonObject(2)), value=lx.__getitem__(2))
    R.__setitem__(_py_tuple2(PythonObject(1), PythonObject(0)), value=ly.__getitem__(0))
    R.__setitem__(_py_tuple2(PythonObject(1), PythonObject(1)), value=ly.__getitem__(1))
    R.__setitem__(_py_tuple2(PythonObject(1), PythonObject(2)), value=ly.__getitem__(2))
    R.__setitem__(_py_tuple2(PythonObject(2), PythonObject(0)), value=lz.__getitem__(0))
    R.__setitem__(_py_tuple2(PythonObject(2), PythonObject(1)), value=lz.__getitem__(1))
    R.__setitem__(_py_tuple2(PythonObject(2), PythonObject(2)), value=lz.__getitem__(2))

    # 12x12 transformation matrix: block diagonal [R, R, R, R]
    var T = np.zeros(_py_tuple2(PythonObject(12), PythonObject(12)))
    var builtins = Python.import_module("builtins")
    var s03 = Python.evaluate("slice(0,3)")
    var s36 = Python.evaluate("slice(3,6)")
    var s69 = Python.evaluate("slice(6,9)")
    var s912 = Python.evaluate("slice(9,12)")

    T.__setitem__(builtins.tuple(Python.list(s03, s03)), value=R)
    T.__setitem__(builtins.tuple(Python.list(s36, s36)), value=R)
    T.__setitem__(builtins.tuple(Python.list(s69, s69)), value=R)
    T.__setitem__(builtins.tuple(Python.list(s912, s912)), value=R)

    return T


# ============================================================================
# Core solver: assemble + factor-once-solve-many (original PythonObject version)
# ============================================================================

def solve(
    nodes: PythonObject,
    elements: PythonObject,
    properties: PythonObject,
    loads: PythonObject,
    supports: PythonObject
) raises -> PythonObject:
    """Solve the FEA system.

    Args:
        nodes: (n_nodes, 3) float64 array of [x, y, z] coordinates.
        elements: (n_elements, 2) int array of [node_i, node_j] connectivity.
        properties: (n_elements, 6) float64 array of [E, A, Iy, Iz, J, G].
        loads: (n_load_cases, n_dof) float64 array of applied force vectors.
        supports: (n_dof,) bool array -- True means fixed DOF.

    Returns:
        dict with displacements, reactions, element_forces, n_free_dofs, etc.
    """
    var np = _np()
    var scipy_linalg = _scipy_linalg()
    var builtins = Python.import_module("builtins")

    var n_nodes = _py_int(nodes.shape.__getitem__(0))
    var n_elements = _py_int(elements.shape.__getitem__(0))
    var n_dof = n_nodes * 6
    var n_loads = _py_int(loads.shape.__getitem__(0))

    # ------------------------------------------------------------------
    # 1) Assemble global stiffness matrix
    # ------------------------------------------------------------------
    var K_global = np.zeros(_py_tuple2(PythonObject(n_dof), PythonObject(n_dof)))

    var ke_globals = Python.list()
    var elem_dof_maps = Python.list()

    for e in range(n_elements):
        var ni = _py_int(elements.__getitem__(_py_tuple2(PythonObject(e), PythonObject(0))))
        var nj = _py_int(elements.__getitem__(_py_tuple2(PythonObject(e), PythonObject(1))))

        var x1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(0)))
        var y1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(1)))
        var z1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(2)))
        var x2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(0)))
        var y2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(1)))
        var z2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(2)))

        var E_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(0)))
        var A_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(1)))
        var Iy_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(2)))
        var Iz_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(3)))
        var J_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(4)))
        var G_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(5)))

        var dx = x2 - x1
        var dy = y2 - y1
        var dz = z2 - z1
        var L_val = np.sqrt(dx * dx + dy * dy + dz * dz)

        # Local stiffness
        var ke_local = _beam_local_stiffness_impl(E_val, A_val, Iy_val, Iz_val, J_val, G_val, L_val)

        # Transformation matrix
        var T = _beam_transform_impl(x1, y1, z1, x2, y2, z2)

        # Global stiffness: ke_global = T^T @ ke_local @ T
        var ke_global = T.T.__matmul__(ke_local).__matmul__(T)
        _ = ke_globals.append(ke_global)

        # DOF map
        var dof_list = Python.list()
        for d in range(6):
            _ = dof_list.append(ni * 6 + d)
        for d in range(6):
            _ = dof_list.append(nj * 6 + d)
        var dof_arr = np.array(dof_list)
        _ = elem_dof_maps.append(dof_arr)

        # Scatter into global matrix
        var ix = np.ix_(dof_arr, dof_arr)
        K_global.__setitem__(ix, value=K_global.__getitem__(ix) + ke_global)

    # ------------------------------------------------------------------
    # 2) Apply boundary conditions via partitioning
    # ------------------------------------------------------------------
    var free_mask = np.logical_not(supports)
    var free_dofs = np.where(free_mask).__getitem__(0)
    var fixed_dofs = np.where(supports).__getitem__(0)
    var n_free = _py_int(free_dofs.shape.__getitem__(0))

    # Extract free-free partition of K
    var ix_ff = np.ix_(free_dofs, free_dofs)
    var K_ff = K_global.__getitem__(ix_ff)

    # ------------------------------------------------------------------
    # 3) Factor once (Cholesky) -- the key optimisation
    # ------------------------------------------------------------------
    var cho = scipy_linalg.cho_factor(K_ff)

    # ------------------------------------------------------------------
    # 4) Solve for each load case via back-substitution
    # ------------------------------------------------------------------
    var displacements = np.zeros(_py_tuple2(PythonObject(n_loads), PythonObject(n_dof)))
    var reactions = np.zeros(_py_tuple2(PythonObject(n_loads), PythonObject(n_dof)))

    for lc in range(n_loads):
        var F_full = loads.__getitem__(lc)
        var F_free = F_full.__getitem__(free_dofs)

        # Solve using pre-factored Cholesky
        var u_free = scipy_linalg.cho_solve(cho, F_free)

        # Scatter back to full displacement vector
        var u_full = np.zeros(n_dof)
        np.put(u_full, free_dofs, u_free)
        displacements.__setitem__(lc, value=u_full)

        # Reactions = K_global @ u - F
        var R_full = K_global.__matmul__(u_full) - F_full
        reactions.__setitem__(lc, value=R_full)

    # ------------------------------------------------------------------
    # 5) Post-processing: element forces from global displacements
    # ------------------------------------------------------------------
    var ef_shape = builtins.tuple(Python.list(PythonObject(n_loads), PythonObject(n_elements), PythonObject(12)))
    var element_forces = np.zeros(ef_shape)

    for e in range(n_elements):
        var ni = _py_int(elements.__getitem__(_py_tuple2(PythonObject(e), PythonObject(0))))
        var nj = _py_int(elements.__getitem__(_py_tuple2(PythonObject(e), PythonObject(1))))

        var x1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(0)))
        var y1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(1)))
        var z1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(2)))
        var x2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(0)))
        var y2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(1)))
        var z2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(2)))

        var E_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(0)))
        var A_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(1)))
        var Iy_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(2)))
        var Iz_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(3)))
        var J_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(4)))
        var G_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(5)))

        var dx = x2 - x1
        var dy = y2 - y1
        var dz = z2 - z1
        var L_val = np.sqrt(dx * dx + dy * dy + dz * dz)

        var ke_local = _beam_local_stiffness_impl(E_val, A_val, Iy_val, Iz_val, J_val, G_val, L_val)
        var T = _beam_transform_impl(x1, y1, z1, x2, y2, z2)

        var dof_map = elem_dof_maps.__getitem__(e)

        for lc in range(n_loads):
            var u_elem_global = displacements.__getitem__(lc).__getitem__(dof_map)
            # Transform to local: u_local = T @ u_global
            var u_elem_local = T.__matmul__(u_elem_global)
            # Local forces: f_local = ke_local @ u_local
            var f_local = ke_local.__matmul__(u_elem_local)
            element_forces.__setitem__(_py_tuple2(PythonObject(lc), PythonObject(e)), value=f_local)

    # ------------------------------------------------------------------
    # Return results as dict
    # ------------------------------------------------------------------
    var result = Python.dict()
    result.__setitem__("displacements", value=displacements)
    result.__setitem__("reactions", value=reactions)
    result.__setitem__("element_forces", value=element_forces)
    result.__setitem__("n_free_dofs", value=PythonObject(n_free))
    result.__setitem__("free_dofs", value=free_dofs)
    result.__setitem__("fixed_dofs", value=fixed_dofs)

    return result


# ============================================================================
# Optimised solve: pre-assembled K (for external assembly)
# ============================================================================

def solve_factored(
    K_ff: PythonObject,
    loads_free: PythonObject
) raises -> PythonObject:
    """Solve multiple load cases with pre-assembled free-DOF stiffness matrix.

    Uses factor-once-solve-many: Cholesky factor K_ff once, solve per case.

    Args:
        K_ff: (n_free, n_free) float64 symmetric positive definite stiffness.
        loads_free: (n_cases, n_free) float64 load vectors for free DOFs.

    Returns:
        (n_cases, n_free) float64 displacement array.
    """
    var np = _np()
    var scipy_linalg = _scipy_linalg()

    var n_cases = _py_int(loads_free.shape.__getitem__(0))
    var n_free = _py_int(loads_free.shape.__getitem__(1))

    # Factor once
    var cho = scipy_linalg.cho_factor(K_ff)

    # Solve each load case
    var u = np.zeros(_py_tuple2(PythonObject(n_cases), PythonObject(n_free)))
    for lc in range(n_cases):
        var F = loads_free.__getitem__(lc)
        var x = scipy_linalg.cho_solve(cho, F)
        u.__setitem__(lc, value=x)

    return u


# ============================================================================
# Utility: assemble global stiffness matrix only (PythonObject version)
# ============================================================================

def assemble_stiffness(
    nodes: PythonObject,
    elements: PythonObject,
    properties: PythonObject
) raises -> PythonObject:
    """Assemble the global stiffness matrix without solving.

    Args:
        nodes: (n_nodes, 3) float64 node coordinates.
        elements: (n_elements, 2) int element connectivity.
        properties: (n_elements, 6) float64 [E, A, Iy, Iz, J, G].

    Returns:
        (n_dof, n_dof) float64 global stiffness matrix.
    """
    var np = _np()

    var n_nodes = _py_int(nodes.shape.__getitem__(0))
    var n_elements = _py_int(elements.shape.__getitem__(0))
    var n_dof = n_nodes * 6

    var K_global = np.zeros(_py_tuple2(PythonObject(n_dof), PythonObject(n_dof)))

    for e in range(n_elements):
        var ni = _py_int(elements.__getitem__(_py_tuple2(PythonObject(e), PythonObject(0))))
        var nj = _py_int(elements.__getitem__(_py_tuple2(PythonObject(e), PythonObject(1))))

        var x1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(0)))
        var y1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(1)))
        var z1 = nodes.__getitem__(_py_tuple2(PythonObject(ni), PythonObject(2)))
        var x2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(0)))
        var y2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(1)))
        var z2 = nodes.__getitem__(_py_tuple2(PythonObject(nj), PythonObject(2)))

        var E_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(0)))
        var A_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(1)))
        var Iy_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(2)))
        var Iz_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(3)))
        var J_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(4)))
        var G_val = properties.__getitem__(_py_tuple2(PythonObject(e), PythonObject(5)))

        var dx = x2 - x1
        var dy = y2 - y1
        var dz = z2 - z1
        var L_val = np.sqrt(dx * dx + dy * dy + dz * dz)

        var ke_local = _beam_local_stiffness_impl(E_val, A_val, Iy_val, Iz_val, J_val, G_val, L_val)
        var T = _beam_transform_impl(x1, y1, z1, x2, y2, z2)
        var ke_global = T.T.__matmul__(ke_local).__matmul__(T)

        # DOF map
        var dof_list = Python.list()
        for d in range(6):
            _ = dof_list.append(ni * 6 + d)
        for d in range(6):
            _ = dof_list.append(nj * 6 + d)
        var dof_arr = np.array(dof_list)

        var ix = np.ix_(dof_arr, dof_arr)
        K_global.__setitem__(ix, value=K_global.__getitem__(ix) + ke_global)

    return K_global


# ============================================================================
# Public wrappers for element-level functions (variadic for > 6 args)
# ============================================================================

def beam_local_stiffness(py_self: PythonObject, args: PythonObject) raises -> PythonObject:
    """Compute 12x12 local stiffness matrix. Args: E, A, Iy, Iz, J, G, L."""
    return _beam_local_stiffness_impl(
        args.__getitem__(0), args.__getitem__(1), args.__getitem__(2),
        args.__getitem__(3), args.__getitem__(4), args.__getitem__(5),
        args.__getitem__(6)
    )

def beam_transform_matrix(
    x1: PythonObject, y1: PythonObject, z1: PythonObject,
    x2: PythonObject, y2: PythonObject, z2: PythonObject
) raises -> PythonObject:
    """Compute 12x12 local-to-global transformation matrix."""
    return _beam_transform_impl(x1, y1, z1, x2, y2, z2)


# ============================================================================
# Module init: register all Python-callable functions
# ============================================================================

@export
def PyInit_bonsai_fea() -> PythonObject:
    try:
        var m = PythonModuleBuilder("bonsai_fea")
        m.def_function[solve](
            "solve",
            docstring="Solve 3D beam FEA: nodes, elements, properties, loads, supports."
        )
        m.def_function[solve_batch](
            "solve_batch",
            docstring="Solve 3D beam FEA with batch assembly (fast): nodes, elements, properties, loads, supports."
        )
        m.def_function[solve_factored](
            "solve_factored",
            docstring="Factor-once-solve-many with pre-assembled K_ff."
        )
        m.def_function[assemble_stiffness](
            "assemble_stiffness",
            docstring="Assemble global stiffness matrix (PythonObject interop version)."
        )
        m.def_function[assemble_batch](
            "assemble_batch",
            docstring="Assemble global stiffness matrix via batch raw-pointer access (fast)."
        )
        m.def_py_function[beam_local_stiffness](
            "beam_local_stiffness",
            docstring="12x12 local stiffness matrix for 3D beam (E, A, Iy, Iz, J, G, L)."
        )
        m.def_function[beam_transform_matrix](
            "beam_transform_matrix",
            docstring="12x12 local-to-global transformation matrix (x1,y1,z1,x2,y2,z2)."
        )
        return m.finalize()
    except e:
        abort("Error creating bonsai_fea module")
        return PythonObject(None)
