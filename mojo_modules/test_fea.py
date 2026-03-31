"""Correctness tests for bonsai_fea Mojo FEA module.

Verifies that the Mojo solver produces the same results as analytical
solutions for known structural problems.
"""

import sys
import os
import numpy as np
from numpy.testing import assert_allclose

# Ensure the module is found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bonsai_fea


def test_cantilever_beam():
    """Single cantilever beam with point load at free end.

    Analytical solution:
        delta = P * L^3 / (3 * E * I)
        theta = P * L^2 / (2 * E * I)
        V = P (shear)
        M_max = P * L (at fixed end)
    """
    print("Test 1: Cantilever beam with point load")

    L = 5.0
    E = 200e9
    A = 0.01
    Iy = 8.33e-6
    Iz = 8.33e-6
    J = 1e-5
    G = E / (2 * (1 + 0.3))
    P = 10000.0  # 10 kN downward

    nodes = np.array([[0.0, 0.0, 0.0], [L, 0.0, 0.0]])
    elements = np.array([[0, 1]])
    properties = np.array([[E, A, Iy, Iz, J, G]])

    loads = np.zeros((1, 12))
    loads[0, 8] = -P  # Dz at node 1

    supports = np.zeros(12, dtype=bool)
    supports[0:6] = True  # fix node 0

    result = bonsai_fea.solve(nodes, elements, properties, loads, supports)

    # Check deflection
    delta_analytical = P * L**3 / (3 * E * Iy)
    delta_mojo = abs(result["displacements"][0, 8])
    assert_allclose(delta_mojo, delta_analytical, rtol=1e-6,
                    err_msg="Cantilever tip deflection mismatch")

    # Check reaction force
    assert_allclose(result["reactions"][0, 2], P, rtol=1e-6,
                    err_msg="Cantilever vertical reaction mismatch")

    # Check reaction moment (M = P * L)
    assert_allclose(abs(result["reactions"][0, 4]), P * L, rtol=1e-6,
                    err_msg="Cantilever reaction moment mismatch")

    print(f"  Tip deflection: {delta_mojo*1000:.4f} mm (analytical: {delta_analytical*1000:.4f} mm)")
    print(f"  Reaction Fz: {result['reactions'][0, 2]:.1f} N")
    print(f"  Reaction My: {result['reactions'][0, 4]:.1f} Nm")
    print("  PASSED")


def test_simply_supported_beam():
    """Simply supported beam with mid-span point load.

    Two elements, three nodes: [0,0,0] -- [L/2,0,0] -- [L,0,0]
    Supports: pin at node 0 (Dx, Dy, Dz fixed), roller at node 2 (Dz fixed).

    Analytical mid-span deflection:
        delta = P * L^3 / (48 * E * I)
    """
    print("\nTest 2: Simply supported beam with mid-span load")

    L = 10.0
    E = 200e9
    A = 0.01
    Iy = 1e-4
    Iz = 1e-4
    J = 2e-4
    G = E / (2 * (1 + 0.3))
    P = 50000.0  # 50 kN

    nodes = np.array([
        [0.0, 0.0, 0.0],
        [L/2, 0.0, 0.0],
        [L, 0.0, 0.0],
    ])
    elements = np.array([[0, 1], [1, 2]])
    properties = np.array([[E, A, Iy, Iz, J, G]] * 2)

    # 18 DOFs total (3 nodes x 6)
    loads = np.zeros((1, 18))
    loads[0, 8] = -P  # Dz at node 1 (mid-span)

    supports = np.zeros(18, dtype=bool)
    # Pin at node 0: fix Dx, Dy, Dz + Rx (prevent torsional rigid body mode)
    supports[0] = True  # Dx
    supports[1] = True  # Dy
    supports[2] = True  # Dz
    supports[3] = True  # Rx (prevent torsional spin)
    # Roller at node 2: fix Dy, Dz + Rx
    supports[13] = True  # Dy at node 2
    supports[14] = True  # Dz at node 2
    supports[15] = True  # Rx at node 2

    result = bonsai_fea.solve(nodes, elements, properties, loads, supports)

    # Analytical mid-span deflection
    delta_analytical = P * L**3 / (48 * E * Iy)
    delta_mojo = abs(result["displacements"][0, 8])

    print(f"  Mid-span deflection: {delta_mojo*1000:.4f} mm (analytical: {delta_analytical*1000:.4f} mm)")
    assert_allclose(delta_mojo, delta_analytical, rtol=0.01,
                    err_msg="Simply supported mid-span deflection mismatch")

    # Reactions: each support should carry P/2
    Rz_node0 = result["reactions"][0, 2]
    Rz_node2 = result["reactions"][0, 14]
    print(f"  Reaction at node 0 (Dz): {Rz_node0:.1f} N (expect ~{P/2:.1f})")
    print(f"  Reaction at node 2 (Dz): {Rz_node2:.1f} N (expect ~{P/2:.1f})")
    assert_allclose(abs(Rz_node0) + abs(Rz_node2), P, rtol=0.01,
                    err_msg="Simply supported reactions don't sum to applied load")
    print("  PASSED")


def test_axial_bar():
    """Pure axial extension test.

    Single element, axial load only.
    delta = P * L / (E * A)
    """
    print("\nTest 3: Axial bar")

    L = 3.0
    E = 200e9
    A = 0.005
    Iy = 1e-6
    Iz = 1e-6
    J = 1e-6
    G = E / (2 * (1 + 0.3))
    P = 100000.0  # 100 kN axial

    nodes = np.array([[0.0, 0.0, 0.0], [L, 0.0, 0.0]])
    elements = np.array([[0, 1]])
    properties = np.array([[E, A, Iy, Iz, J, G]])

    loads = np.zeros((1, 12))
    loads[0, 6] = P  # Dx at node 1 (axial along x)

    supports = np.zeros(12, dtype=bool)
    supports[0:6] = True  # fix node 0

    result = bonsai_fea.solve(nodes, elements, properties, loads, supports)

    delta_analytical = P * L / (E * A)
    delta_mojo = abs(result["displacements"][0, 6])  # Dx at node 1

    print(f"  Axial extension: {delta_mojo*1e6:.4f} um (analytical: {delta_analytical*1e6:.4f} um)")
    assert_allclose(delta_mojo, delta_analytical, rtol=1e-6,
                    err_msg="Axial extension mismatch")

    # Reaction should equal applied load
    assert_allclose(abs(result["reactions"][0, 0]), P, rtol=1e-6,
                    err_msg="Axial reaction mismatch")
    print("  PASSED")


def test_multi_element_frame():
    """Simple portal frame: two columns + one beam.

    Tests assembly of multiple elements in 3D.
    """
    print("\nTest 4: Portal frame (2 columns + 1 beam)")

    E = 200e9
    A = 0.01
    Iy = 1e-4
    Iz = 1e-4
    J = 2e-4
    G = E / (2 * (1 + 0.3))

    # Frame: 4 nodes
    nodes = np.array([
        [0.0, 0.0, 0.0],   # node 0: base left
        [0.0, 0.0, 4.0],   # node 1: top left
        [6.0, 0.0, 4.0],   # node 2: top right
        [6.0, 0.0, 0.0],   # node 3: base right
    ])
    elements = np.array([
        [0, 1],  # left column
        [1, 2],  # beam
        [2, 3],  # right column
    ])
    properties = np.array([[E, A, Iy, Iz, J, G]] * 3)

    # 24 DOFs total
    loads = np.zeros((1, 24))
    loads[0, 6] = 20000.0  # 20 kN lateral load at node 1 (Dx)

    supports = np.zeros(24, dtype=bool)
    supports[0:6] = True    # fix node 0
    supports[18:24] = True  # fix node 3

    result = bonsai_fea.solve(nodes, elements, properties, loads, supports)

    # Check equilibrium: sum of horizontal reactions = applied load
    Rx_node0 = result["reactions"][0, 0]
    Rx_node3 = result["reactions"][0, 18]
    total_Rx = Rx_node0 + Rx_node3
    print(f"  Lateral load applied: 20000 N")
    print(f"  Reaction Fx at node 0: {Rx_node0:.1f} N")
    print(f"  Reaction Fx at node 3: {Rx_node3:.1f} N")
    print(f"  Sum of horizontal reactions: {total_Rx:.1f} N")
    assert_allclose(abs(total_Rx), 20000.0, rtol=0.01,
                    err_msg="Portal frame horizontal equilibrium violated")

    # Check that displacements are reasonable
    max_disp = np.max(np.abs(result["displacements"]))
    print(f"  Max displacement: {max_disp*1000:.4f} mm")
    assert max_disp > 0, "Portal frame should have non-zero displacements"
    assert max_disp < 1.0, "Portal frame displacement unreasonably large"
    print("  PASSED")


def test_multiple_load_cases():
    """Tests factor-once-solve-many with 3 load cases on same structure."""
    print("\nTest 5: Multiple load cases (factor-once-solve-many)")

    L = 5.0
    E = 200e9
    A = 0.01
    Iy = 8.33e-6
    Iz = 8.33e-6
    J = 1e-5
    G = E / (2 * (1 + 0.3))

    nodes = np.array([[0.0, 0.0, 0.0], [L, 0.0, 0.0]])
    elements = np.array([[0, 1]])
    properties = np.array([[E, A, Iy, Iz, J, G]])

    # 3 load cases
    loads = np.zeros((3, 12))
    loads[0, 8] = -10000.0   # 10 kN down
    loads[1, 8] = -20000.0   # 20 kN down
    loads[2, 6] = 50000.0    # 50 kN axial

    supports = np.zeros(12, dtype=bool)
    supports[0:6] = True

    result = bonsai_fea.solve(nodes, elements, properties, loads, supports)

    assert result["displacements"].shape == (3, 12), \
        f"Expected (3, 12), got {result['displacements'].shape}"

    # Load case 2 should have exactly 2x the deflection of load case 1
    d1 = result["displacements"][0, 8]
    d2 = result["displacements"][1, 8]
    assert_allclose(d2, 2 * d1, rtol=1e-6,
                    err_msg="Linearity check failed: LC2 should be 2x LC1")

    # Load case 3 should have zero Dz deflection (pure axial)
    assert_allclose(result["displacements"][2, 8], 0.0, atol=1e-12,
                    err_msg="Axial load should produce zero transverse deflection")

    print(f"  LC1 tip Dz: {d1*1000:.4f} mm")
    print(f"  LC2 tip Dz: {d2*1000:.4f} mm (should be 2x LC1)")
    print(f"  LC3 tip Dz: {result['displacements'][2, 8]*1000:.6f} mm (should be ~0)")
    print(f"  LC3 tip Dx: {result['displacements'][2, 6]*1e6:.4f} um (axial)")
    print("  PASSED")


def test_element_stiffness_symmetry():
    """Verify the element stiffness matrix is symmetric."""
    print("\nTest 6: Element stiffness matrix symmetry")

    E, A, Iy, Iz, J, G, L = 200e9, 0.01, 1e-4, 1e-4, 2e-4, 77e9, 5.0
    k = bonsai_fea.beam_local_stiffness(E, A, Iy, Iz, J, G, L)

    assert k.shape == (12, 12), f"Expected (12, 12), got {k.shape}"
    assert_allclose(k, k.T, atol=1e-6,
                    err_msg="Element stiffness matrix is not symmetric")
    print(f"  Matrix shape: {k.shape}")
    print(f"  Max asymmetry: {np.max(np.abs(k - k.T)):.2e}")
    print("  PASSED")


def test_transform_orthogonality():
    """Verify the transformation matrix is orthogonal (T^T @ T = I)."""
    print("\nTest 7: Transformation matrix orthogonality")

    # Horizontal beam
    T1 = bonsai_fea.beam_transform_matrix(0.0, 0.0, 0.0, 5.0, 0.0, 0.0)
    assert T1.shape == (12, 12)
    I12 = T1.T @ T1
    assert_allclose(I12, np.eye(12), atol=1e-10,
                    err_msg="Horizontal beam T matrix not orthogonal")
    print("  Horizontal beam: orthogonal")

    # Vertical column
    T2 = bonsai_fea.beam_transform_matrix(0.0, 0.0, 0.0, 0.0, 0.0, 4.0)
    I12_v = T2.T @ T2
    assert_allclose(I12_v, np.eye(12), atol=1e-10,
                    err_msg="Vertical column T matrix not orthogonal")
    print("  Vertical column: orthogonal")

    # Diagonal member
    T3 = bonsai_fea.beam_transform_matrix(0.0, 0.0, 0.0, 3.0, 4.0, 5.0)
    I12_d = T3.T @ T3
    assert_allclose(I12_d, np.eye(12), atol=1e-10,
                    err_msg="Diagonal member T matrix not orthogonal")
    print("  Diagonal member: orthogonal")
    print("  PASSED")


def test_vertical_column():
    """Vertical column with lateral load at top.

    Same as cantilever but vertical: tests transformation matrix for vertical members.
    """
    print("\nTest 8: Vertical column with lateral load")

    H = 4.0  # height
    E = 200e9
    A = 0.01
    Iy = 1e-4
    Iz = 1e-4
    J = 2e-4
    G = E / (2 * (1 + 0.3))
    P = 15000.0  # lateral

    nodes = np.array([
        [0.0, 0.0, 0.0],  # base
        [0.0, 0.0, H],    # top
    ])
    elements = np.array([[0, 1]])
    properties = np.array([[E, A, Iy, Iz, J, G]])

    loads = np.zeros((1, 12))
    loads[0, 6] = P  # Dx at top node

    supports = np.zeros(12, dtype=bool)
    supports[0:6] = True  # fixed base

    result = bonsai_fea.solve(nodes, elements, properties, loads, supports)

    # Analytical: delta = P * L^3 / (3 * E * I)
    # For vertical member with lateral load, uses Iz (bending about z for x-direction load)
    delta_analytical = P * H**3 / (3 * E * Iz)
    delta_mojo = abs(result["displacements"][0, 6])

    print(f"  Lateral deflection: {delta_mojo*1000:.4f} mm (analytical: {delta_analytical*1000:.4f} mm)")
    assert_allclose(delta_mojo, delta_analytical, rtol=0.02,
                    err_msg="Vertical column lateral deflection mismatch")
    print("  PASSED")


def test_solve_factored():
    """Test the solve_factored function directly."""
    print("\nTest 9: solve_factored (factor-once-solve-many)")

    # Create a simple SPD matrix
    np.random.seed(42)
    n = 50
    A = np.random.randn(n, n)
    K = A.T @ A + np.eye(n) * n  # guaranteed SPD

    # Multiple RHS
    n_cases = 10
    F = np.random.randn(n_cases, n)

    # Solve with our function
    u_mojo = bonsai_fea.solve_factored(K, F)

    # Compare with numpy
    u_numpy = np.linalg.solve(K, F.T).T

    assert_allclose(u_mojo, u_numpy, rtol=1e-8,
                    err_msg="solve_factored results don't match numpy")

    print(f"  Matrix size: {n}x{n}, {n_cases} load cases")
    print(f"  Max error: {np.max(np.abs(u_mojo - u_numpy)):.2e}")
    print("  PASSED")


def main():
    print("=" * 60)
    print("Bonsai FEA Module -- Correctness Tests")
    print("=" * 60)

    tests = [
        test_cantilever_beam,
        test_simply_supported_beam,
        test_axial_bar,
        test_multi_element_frame,
        test_multiple_load_cases,
        test_element_stiffness_symmetry,
        test_transform_orthogonality,
        test_vertical_column,
        test_solve_factored,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
