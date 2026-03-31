"""bonsai_fea_fast -- High-performance FEA solver combining NumPy assembly + Mojo solve.

Architecture:
    1. Assembly loop in Python/NumPy (vectorized matrix ops, no per-element interop overhead)
       OR batch assembly via Mojo raw pointers (crosses boundary once, not per-element)
    2. Factor-once-solve-many via scipy Cholesky
    3. Post-processing in NumPy

The Mojo batch assembly path (assemble_batch / solve_batch) extracts raw pointers
from numpy arrays and runs the entire element loop in pure Mojo -- no PythonObject
overhead per element. This is the fastest path for medium-to-large problems.
"""

import os
import sys
import numpy as np
from scipy.linalg import cho_factor, cho_solve

# Import the Mojo module for batch assembly + Cholesky solve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import bonsai_fea as _mojo
    _HAS_MOJO = True
    _HAS_BATCH = hasattr(_mojo, 'assemble_batch')
except ImportError:
    _HAS_MOJO = False
    _HAS_BATCH = False


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
    # Fix: signs for the 5,7 and 7,5 entries
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
        # Vertical member
        gy = np.array([0.0, 1.0, 0.0])
        ly = np.cross(gz, lx)
        n = np.linalg.norm(ly)
        ly = gy if n < tol else ly / n
        lz = np.cross(lx, ly)
    else:
        # Standard: project global Z onto perpendicular to lx
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
    """Assemble global stiffness matrix and return element data for post-processing.

    Args:
        nodes: (n_nodes, 3) float64
        elements: (n_elements, 2) int
        properties: (n_elements, 6) float64 [E, A, Iy, Iz, J, G]

    Returns:
        K_global: (n_dof, n_dof) float64
        ke_locals: list of (12, 12) arrays
        transforms: list of (12, 12) arrays
        dof_maps: list of (12,) int arrays
    """
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


def solve(nodes, elements, properties, loads, supports):
    """Full FEA solve: assemble + factor-once-solve-many + post-process.

    Automatically selects the fastest available path:
    1. Mojo batch (if compiled module has assemble_batch): raw-pointer assembly
    2. NumPy assembly + scipy Cholesky (fallback)

    Args:
        nodes: (n_nodes, 3) float64 array of [x, y, z] coordinates.
        elements: (n_elements, 2) int array of [node_i, node_j] connectivity.
        properties: (n_elements, 6) float64 array of [E, A, Iy, Iz, J, G].
        loads: (n_load_cases, n_dof) float64 array of force vectors.
        supports: (n_dof,) bool array -- True = fixed DOF.

    Returns:
        dict with:
            displacements: (n_loads, n_dof)
            reactions: (n_loads, n_dof)
            element_forces: (n_loads, n_elements, 12)
            n_free_dofs: int
            free_dofs: array
            fixed_dofs: array
    """
    # Use Mojo batch solve if available (fastest path)
    if _HAS_BATCH:
        return solve_mojo_batch(nodes, elements, properties, loads, supports)

    return solve_numpy(nodes, elements, properties, loads, supports)


def solve_mojo_batch(nodes, elements, properties, loads, supports):
    """Full FEA solve using Mojo batch assembly (raw pointer, minimal interop).

    The assembly loop runs entirely in Mojo with direct pointer access to
    numpy arrays. Crosses the Python/Mojo boundary once instead of per-element.
    """
    return _mojo.solve_batch(nodes, elements, properties, loads, supports)


def solve_numpy(nodes, elements, properties, loads, supports):
    """Full FEA solve using NumPy assembly + scipy Cholesky.

    Fallback path when Mojo batch assembly is not available.
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
