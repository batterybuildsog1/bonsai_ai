"""bonsai_fea_fast -- High-performance FEA solver with vectorized assembly.

Architecture:
    1. Vectorized assembly: compute ALL element stiffness matrices and transforms
       using batched numpy operations (no per-element Python function calls)
    2. Factor-once-solve-many via scipy Cholesky
    3. Vectorized post-processing

Performance strategy:
    - Pre-compute all element lengths, rotation matrices in bulk numpy operations
    - Build all 12x12 local stiffness matrices as a (n_elements, 12, 12) batch
    - Batch matmul via np.einsum or @ broadcasting for T^T @ ke @ T
    - Single scatter-add loop for global assembly (unavoidably serial)
"""

import os
import sys
import numpy as np
from scipy.linalg import cho_factor, cho_solve

# Import the Mojo module if available
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import bonsai_fea as _mojo
    _HAS_MOJO = True
except ImportError:
    _HAS_MOJO = False


# ============================================================================
# Vectorized element computation (all elements at once)
# ============================================================================

def _batch_element_geometry(nodes, elements):
    """Compute element lengths and direction cosines for ALL elements at once.

    Args:
        nodes: (n_nodes, 3) float64
        elements: (n_elements, 2) int

    Returns:
        dx, dy, dz: (n_elements,) coordinate differences
        L: (n_elements,) element lengths
        lx: (n_elements, 3) unit vectors along elements
    """
    ni_coords = nodes[elements[:, 0]]  # (n_elem, 3)
    nj_coords = nodes[elements[:, 1]]  # (n_elem, 3)
    diff = nj_coords - ni_coords       # (n_elem, 3)
    dx, dy, dz = diff[:, 0], diff[:, 1], diff[:, 2]
    L = np.sqrt(dx**2 + dy**2 + dz**2)
    lx = diff / L[:, np.newaxis]       # (n_elem, 3)
    return dx, dy, dz, L, lx


def _batch_transforms(lx, L):
    """Build 12x12 transformation matrices for ALL elements at once.

    Args:
        lx: (n_elements, 3) unit vectors along elements
        L: (n_elements,) element lengths

    Returns:
        T: (n_elements, 12, 12) transformation matrices
        R: (n_elements, 3, 3) rotation matrices
    """
    n = len(L)
    gz = np.array([0.0, 0.0, 1.0])
    tol = 1e-8

    # Compute local coordinate systems for each element
    ly = np.zeros((n, 3))
    lz = np.zeros((n, 3))

    # Dot product of each lx with global Z
    dot_xz = np.abs(lx[:, 2])  # lx . [0,0,1] = lx_z
    is_vert = dot_xz > (1.0 - tol)

    # --- Handle vertical members ---
    if np.any(is_vert):
        iv = np.where(is_vert)[0]
        # ly = cross(gz, lx) for vertical members
        ly_v = np.cross(gz, lx[iv])
        ly_norms = np.linalg.norm(ly_v, axis=1, keepdims=True)
        # Where norm is too small, use global Y
        small = (ly_norms.ravel() < tol)
        ly_v[small] = [0.0, 1.0, 0.0]
        ly_v[~small] = ly_v[~small] / ly_norms[~small]
        ly[iv] = ly_v
        lz[iv] = np.cross(lx[iv], ly[iv])

    # --- Handle standard (non-vertical) members ---
    if np.any(~is_vert):
        inv = np.where(~is_vert)[0]
        # Project global Z onto plane perpendicular to lx
        lz_temp = gz - lx[inv] * lx[inv, 2:3]  # gz - lx * (lx . gz)
        lz_norms = np.linalg.norm(lz_temp, axis=1, keepdims=True)
        ok = (lz_norms.ravel() > tol)

        if np.any(ok):
            idx_ok = inv[ok]
            lz[idx_ok] = lz_temp[ok] / lz_norms[ok]

        if np.any(~ok):
            idx_bad = inv[~ok]
            gy = np.array([0.0, 1.0, 0.0])
            lz_fallback = np.cross(lx[idx_bad], gy)
            lz_fallback /= np.linalg.norm(lz_fallback, axis=1, keepdims=True)
            lz[idx_bad] = lz_fallback

        ly[inv] = np.cross(lz[inv], lx[inv])

    # Build R: (n, 3, 3) where R[e] = [[lx], [ly], [lz]]
    R = np.stack([lx, ly, lz], axis=1)  # (n, 3, 3)

    # Build T: (n, 12, 12) block diagonal [R, R, R, R]
    T = np.zeros((n, 12, 12))
    T[:, 0:3, 0:3] = R
    T[:, 3:6, 3:6] = R
    T[:, 6:9, 6:9] = R
    T[:, 9:12, 9:12] = R

    return T, R


def _batch_local_stiffness(properties, L):
    """Build 12x12 local stiffness matrices for ALL elements at once.

    Args:
        properties: (n_elements, 6) float64 [E, A, Iy, Iz, J, G]
        L: (n_elements,) element lengths

    Returns:
        ke: (n_elements, 12, 12) local stiffness matrices
    """
    n = len(L)
    E = properties[:, 0]
    A = properties[:, 1]
    Iy = properties[:, 2]
    Iz = properties[:, 3]
    J = properties[:, 4]
    G = properties[:, 5]

    L2 = L * L
    L3 = L2 * L

    ke = np.zeros((n, 12, 12))

    # Axial
    ea_l = E * A / L
    ke[:, 0, 0] = ea_l;  ke[:, 0, 6] = -ea_l
    ke[:, 6, 0] = -ea_l; ke[:, 6, 6] = ea_l

    # Torsion
    gj_l = G * J / L
    ke[:, 3, 3] = gj_l;  ke[:, 3, 9] = -gj_l
    ke[:, 9, 3] = -gj_l; ke[:, 9, 9] = gj_l

    # Bending about z (Iz)
    eiz = E * Iz
    a = 12 * eiz / L3
    b = 6 * eiz / L2
    c = 4 * eiz / L
    d = 2 * eiz / L

    ke[:, 1, 1] = a;   ke[:, 1, 5] = b;   ke[:, 1, 7] = -a;  ke[:, 1, 11] = b
    ke[:, 5, 1] = b;   ke[:, 5, 5] = c;   ke[:, 5, 7] = -b;  ke[:, 5, 11] = d
    ke[:, 7, 1] = -a;  ke[:, 7, 5] = -b;  ke[:, 7, 7] = a;   ke[:, 7, 11] = -b
    ke[:, 11, 1] = b;  ke[:, 11, 5] = d;  ke[:, 11, 7] = -b; ke[:, 11, 11] = c

    # Bending about y (Iy)
    eiy = E * Iy
    a = 12 * eiy / L3
    b = 6 * eiy / L2
    c = 4 * eiy / L
    d = 2 * eiy / L

    ke[:, 2, 2] = a;    ke[:, 2, 4] = -b;  ke[:, 2, 8] = -a;  ke[:, 2, 10] = -b
    ke[:, 4, 2] = -b;   ke[:, 4, 4] = c;   ke[:, 4, 8] = b;   ke[:, 4, 10] = d
    ke[:, 8, 2] = -a;   ke[:, 8, 4] = b;   ke[:, 8, 8] = a;   ke[:, 8, 10] = b
    ke[:, 10, 2] = -b;  ke[:, 10, 4] = d;  ke[:, 10, 8] = b;  ke[:, 10, 10] = c

    return ke


def _batch_dof_maps(elements):
    """Build DOF maps for ALL elements at once.

    Args:
        elements: (n_elements, 2) int

    Returns:
        dof_maps: (n_elements, 12) int array of global DOF indices
    """
    ni = elements[:, 0]  # (n_elem,)
    nj = elements[:, 1]  # (n_elem,)

    # Build DOF map: [ni*6+0, ..., ni*6+5, nj*6+0, ..., nj*6+5]
    offsets = np.arange(6)  # [0, 1, 2, 3, 4, 5]
    dof_i = ni[:, np.newaxis] * 6 + offsets  # (n_elem, 6)
    dof_j = nj[:, np.newaxis] * 6 + offsets  # (n_elem, 6)
    return np.hstack([dof_i, dof_j])  # (n_elem, 12)


# ============================================================================
# Vectorized assembly
# ============================================================================

def assemble_vectorized(nodes, elements, properties):
    """Assemble global stiffness matrix using vectorized numpy operations.

    Instead of per-element Python function calls, this computes ALL element
    matrices in bulk using numpy broadcasting, then does a single scatter-add loop.

    Args:
        nodes: (n_nodes, 3) float64
        elements: (n_elements, 2) int
        properties: (n_elements, 6) float64 [E, A, Iy, Iz, J, G]

    Returns:
        K_global: (n_dof, n_dof) float64
        ke_locals: (n_elements, 12, 12) local stiffness matrices
        transforms: (n_elements, 12, 12) transformation matrices
        dof_maps: (n_elements, 12) DOF index maps
    """
    n_nodes = nodes.shape[0]
    n_elements = elements.shape[0]
    n_dof = n_nodes * 6

    # 1) Batch compute geometry
    dx, dy, dz, L, lx = _batch_element_geometry(nodes, elements)

    # 2) Batch compute transforms: T is (n_elem, 12, 12)
    T, R = _batch_transforms(lx, L)

    # 3) Batch compute local stiffness: ke is (n_elem, 12, 12)
    ke_locals = _batch_local_stiffness(properties, L)

    # 4) Batch compute global stiffness: ke_global = T^T @ ke_local @ T
    #    Using np.einsum for batch matrix multiply
    #    ke_global[e] = T[e].T @ ke_locals[e] @ T[e]
    temp = np.einsum('eij,ejk->eik', ke_locals, T)       # ke @ T  -> (n_elem, 12, 12)
    ke_globals = np.einsum('eji,ejk->eik', T, temp)       # T^T @ temp -> (n_elem, 12, 12)

    # 5) Build DOF maps
    dof_maps = _batch_dof_maps(elements)

    # 6) Scatter-add into global matrix (this loop is unavoidably serial)
    K = np.zeros((n_dof, n_dof))
    for e in range(n_elements):
        dofs = dof_maps[e]
        ix = np.ix_(dofs, dofs)
        K[ix] += ke_globals[e]

    return K, ke_locals, T, dof_maps


# ============================================================================
# Legacy per-element assembly (kept for comparison)
# ============================================================================

def beam_local_stiffness(E, A, Iy, Iz, J, G, L):
    """12x12 local stiffness matrix for 3-D Euler-Bernoulli beam element.

    DOF order per node: [Dx, Dy, Dz, Rx, Ry, Rz]
    """
    k = np.zeros((12, 12))

    # Axial
    ea_l = E * A / L
    k[0, 0] = k[6, 6] = ea_l
    k[0, 6] = k[6, 0] = -ea_l

    # Torsion
    gj_l = G * J / L
    k[3, 3] = k[9, 9] = gj_l
    k[3, 9] = k[9, 3] = -gj_l

    # Bending about z (Iz) -- bending in x-y plane
    L2, L3 = L * L, L * L * L
    eiz = E * Iz
    a, b, c, d = 12 * eiz / L3, 6 * eiz / L2, 4 * eiz / L, 2 * eiz / L
    k[1, 1] = k[7, 7] = a
    k[1, 7] = k[7, 1] = -a
    k[1, 5] = k[1, 11] = k[5, 1] = k[11, 1] = b
    k[7, 5] = k[7, 11] = k[5, 7] = k[11, 7] = -b
    k[5, 5] = k[11, 11] = c
    k[5, 11] = k[11, 5] = d
    k[5, 7] = k[7, 5] = -b

    # Bending about y (Iy) -- bending in x-z plane
    eiy = E * Iy
    a, b, c, d = 12 * eiy / L3, 6 * eiy / L2, 4 * eiy / L, 2 * eiy / L
    k[2, 2] = k[8, 8] = a
    k[2, 8] = k[8, 2] = -a
    k[2, 4] = k[2, 10] = -b
    k[4, 2] = k[10, 2] = -b
    k[8, 4] = k[8, 10] = b
    k[4, 8] = k[10, 8] = b
    k[4, 4] = k[10, 10] = c
    k[4, 10] = k[10, 4] = d

    return k


def beam_transform(x1, y1, z1, x2, y2, z2):
    """12x12 local-to-global transformation matrix for 3-D beam element."""
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    L = np.sqrt(dx**2 + dy**2 + dz**2)
    lx = np.array([dx, dy, dz]) / L
    gz = np.array([0.0, 0.0, 1.0])
    tol = 1e-8

    if abs(np.dot(lx, gz)) > 1 - tol:
        gy = np.array([0.0, 1.0, 0.0])
        ly = np.cross(gz, lx)
        n = np.linalg.norm(ly)
        ly = gy if n < tol else ly / n
        lz = np.cross(lx, ly)
    else:
        lz_temp = gz - lx * np.dot(gz, lx)
        n = np.linalg.norm(lz_temp)
        if n > tol:
            lz = lz_temp / n
        else:
            lz = np.cross(lx, np.array([0, 1, 0]))
            lz = lz / np.linalg.norm(lz)
        ly = np.cross(lz, lx)

    R = np.array([lx, ly, lz])
    T = np.zeros((12, 12))
    T[0:3, 0:3] = R
    T[3:6, 3:6] = R
    T[6:9, 6:9] = R
    T[9:12, 9:12] = R
    return T


def assemble(nodes, elements, properties):
    """Legacy per-element assembly (kept for comparison and compatibility)."""
    n_nodes = nodes.shape[0]
    n_elements = elements.shape[0]
    n_dof = n_nodes * 6

    K = np.zeros((n_dof, n_dof))
    ke_locals = []
    transforms = []
    dof_maps = []

    for e in range(n_elements):
        ni, nj = elements[e]
        x1, y1, z1 = nodes[ni]
        x2, y2, z2 = nodes[nj]
        E, A, Iy, Iz, J, G = properties[e]
        L = np.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

        ke_local = beam_local_stiffness(E, A, Iy, Iz, J, G, L)
        T = beam_transform(x1, y1, z1, x2, y2, z2)
        ke_global = T.T @ ke_local @ T

        dofs = np.array([ni * 6 + d for d in range(6)] + [nj * 6 + d for d in range(6)])
        ix = np.ix_(dofs, dofs)
        K[ix] += ke_global

        ke_locals.append(ke_local)
        transforms.append(T)
        dof_maps.append(dofs)

    return K, ke_locals, transforms, dof_maps


# ============================================================================
# Solvers
# ============================================================================

def solve(nodes, elements, properties, loads, supports):
    """Full FEA solve using vectorized assembly + factor-once-solve-many.

    Uses batched numpy operations to compute all element matrices at once,
    eliminating per-element Python function call overhead.

    Args:
        nodes: (n_nodes, 3) float64 array of [x, y, z] coordinates.
        elements: (n_elements, 2) int array of [node_i, node_j] connectivity.
        properties: (n_elements, 6) float64 array of [E, A, Iy, Iz, J, G].
        loads: (n_load_cases, n_dof) float64 array of force vectors.
        supports: (n_dof,) bool array -- True = fixed DOF.

    Returns:
        dict with displacements, reactions, element_forces, etc.
    """
    return solve_vectorized(nodes, elements, properties, loads, supports)


def solve_vectorized(nodes, elements, properties, loads, supports):
    """Full FEA solve with vectorized assembly (fastest pure-Python path)."""
    n_nodes = nodes.shape[0]
    n_elements = elements.shape[0]
    n_dof = n_nodes * 6
    n_loads = loads.shape[0]

    # 1) Vectorized assembly
    K, ke_locals, transforms, dof_maps = assemble_vectorized(nodes, elements, properties)

    # 2) Partition
    free = np.where(~supports)[0]
    fixed = np.where(supports)[0]
    K_ff = K[np.ix_(free, free)]

    # 3) Factor once (Cholesky)
    cho = cho_factor(K_ff)

    # 4) Solve per load case
    displacements = np.zeros((n_loads, n_dof))
    reactions = np.zeros((n_loads, n_dof))

    for lc in range(n_loads):
        F_free = loads[lc][free]
        u_free = cho_solve(cho, F_free)
        u_full = np.zeros(n_dof)
        u_full[free] = u_free
        displacements[lc] = u_full
        reactions[lc] = K @ u_full - loads[lc]

    # 5) Vectorized post-processing: element forces
    # Gather element displacements for all elements at once
    # dof_maps is (n_elem, 12), displacements is (n_loads, n_dof)
    # u_elem_global[lc, e, :] = displacements[lc, dof_maps[e, :]]
    u_elem_global = displacements[:, dof_maps]  # (n_loads, n_elem, 12)

    # Transform to local: u_local = T @ u_global for each element
    # transforms is (n_elem, 12, 12)
    u_elem_local = np.einsum('eij,lej->lei', transforms, u_elem_global)  # (n_loads, n_elem, 12)

    # Local forces: f = ke @ u_local
    # ke_locals is (n_elem, 12, 12)
    element_forces = np.einsum('eij,lej->lei', ke_locals, u_elem_local)  # (n_loads, n_elem, 12)

    return {
        "displacements": displacements,
        "reactions": reactions,
        "element_forces": element_forces,
        "n_free_dofs": len(free),
        "free_dofs": free,
        "fixed_dofs": fixed,
    }


def solve_numpy(nodes, elements, properties, loads, supports):
    """Full FEA solve using per-element NumPy assembly + scipy Cholesky.

    Slower legacy path, kept for comparison/compatibility.
    """
    n_nodes = nodes.shape[0]
    n_elements = elements.shape[0]
    n_dof = n_nodes * 6
    n_loads = loads.shape[0]

    # 1) Assemble
    K, ke_locals, transforms, dof_maps = assemble(nodes, elements, properties)

    # 2) Partition
    free = np.where(~supports)[0]
    fixed = np.where(supports)[0]
    K_ff = K[np.ix_(free, free)]

    # 3) Factor once (Cholesky)
    cho = cho_factor(K_ff)

    # 4) Solve per load case
    displacements = np.zeros((n_loads, n_dof))
    reactions = np.zeros((n_loads, n_dof))

    for lc in range(n_loads):
        F_free = loads[lc][free]
        u_free = cho_solve(cho, F_free)
        u_full = np.zeros(n_dof)
        u_full[free] = u_free
        displacements[lc] = u_full
        reactions[lc] = K @ u_full - loads[lc]

    # 5) Element forces
    element_forces = np.zeros((n_loads, n_elements, 12))
    for e in range(n_elements):
        for lc in range(n_loads):
            u_elem = displacements[lc][dof_maps[e]]
            u_local = transforms[e] @ u_elem
            element_forces[lc, e] = ke_locals[e] @ u_local

    return {
        "displacements": displacements,
        "reactions": reactions,
        "element_forces": element_forces,
        "n_free_dofs": len(free),
        "free_dofs": free,
        "fixed_dofs": fixed,
    }


def solve_factored(K_ff, loads_free):
    """Factor-once-solve-many using Cholesky decomposition.

    Args:
        K_ff: (n_free, n_free) SPD stiffness matrix.
        loads_free: (n_cases, n_free) load vectors.

    Returns:
        (n_cases, n_free) displacement array.
    """
    if _HAS_MOJO:
        return _mojo.solve_factored(K_ff, loads_free)
    else:
        cho = cho_factor(K_ff)
        n_cases = loads_free.shape[0]
        n_free = loads_free.shape[1]
        u = np.zeros((n_cases, n_free))
        for lc in range(n_cases):
            u[lc] = cho_solve(cho, loads_free[lc])
        return u
