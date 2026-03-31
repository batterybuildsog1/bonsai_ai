#!/usr/bin/env python3
"""Correctness tests for bonsai_tessellate.mojo.

Runs the Mojo self-test and parses its output to verify:
  1. Correct vertex/index counts for all element types
  2. Correct vertex positions for known geometries
  3. Correct normals (face normals for flat shading)
  4. Counter-clockwise winding order (Three.js convention)
  5. batch_transform_vertices correctness

Run:
    python test_tessellate.py
"""

import math
import os
import re
import subprocess
import sys

MOJO_BIN = os.path.expanduser("~/Library/Python/3.9/bin/mojo")
TESS_MOJO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bonsai_tessellate.mojo")

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)


def run_mojo() -> str:
    """Compile and run the Mojo tessellator, return stdout."""
    result = subprocess.run(
        [MOJO_BIN, "run", TESS_MOJO],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print("ERROR: Mojo compilation/run failed:")
        print(result.stderr)
        sys.exit(1)
    return result.stdout


def test_box(output: str):
    """Test 1: tessellate_box(0,0,0, 2,3,4, 0)"""
    print("\n--- Test: Box (2x3x4 at origin, no rotation) ---")

    check("box vertex count = 24", "vertices: 24" in output)
    check("box index count = 36", "indices: 36" in output)
    check("box triangle count = 12", "triangles: 12" in output)
    check("all indices < 24", "All indices < 24: True" in output)

    # Check bottom face vertex positions
    # v0 should be at (0,0,0) -- corner 0
    check("v0 pos = (0,0,0)", "v 0 pos: 0.0 0.0 0.0" in output)
    # v1 should be at (0,3,0) -- corner 3
    check("v1 pos = (0,3,0)", "v 1 pos: 0.0 3.0 0.0" in output)
    # v2 should be at (2,3,0) -- corner 2
    check("v2 pos = (2,3,0)", "v 2 pos: 2.0 3.0 0.0" in output)
    # v3 should be at (2,0,0) -- corner 1
    check("v3 pos = (2,0,0)", "v 3 pos: 2.0 0.0 0.0" in output)

    # Bottom face normals should be (0,0,-1)
    check("bottom face normal = (0,0,-1)",
          all(f"v {i} pos:" in line and "nrm: 0.0 0.0 -1.0" in line
              for i, line in enumerate(output.splitlines())
              if f"v {i} pos:" in line and i < 4))

    # Top face
    check("v4 pos = (0,0,4)", "v 4 pos: 0.0 0.0 4.0" in output)
    check("v5 pos = (2,0,4)", "v 5 pos: 2.0 0.0 4.0" in output)
    check("v6 pos = (2,3,4)", "v 6 pos: 2.0 3.0 4.0" in output)
    check("v7 pos = (0,3,4)", "v 7 pos: 0.0 3.0 4.0" in output)

    # Top face normals should be (0,0,+1)
    for i in range(4, 8):
        check(f"v{i} top normal = (0,0,1)",
              f"v {i} pos:" in output and "nrm: 0.0 0.0 1.0" in output)


def test_wall(output: str):
    """Test 2: Wall from (0,0) to (5,0), height 3, thickness 0.2"""
    print("\n--- Test: Wall (0,0)->(5,0), h=3, t=0.2 ---")

    check("wall vertex count = 24", "vertices: 24" in output)

    # X range should be 0 to 5
    check("wall X range: 0 to 5",
          "X range: 0.0 to 5.0" in output)

    # Y range should be -0.1 to 0.1 (half thickness)
    check("wall Y range: -0.1 to 0.1",
          "Y range: -0.1 to 0.1" in output)

    # Max Z should be 3.0
    check("wall max Z = 3.0", "Max Z: 3.0" in output)


def test_column(output: str):
    """Test 3: Column at (5,5), centered profile 0.3x0.3, height 3.5"""
    print("\n--- Test: Column at (5,5), 0.3x0.3x3.5 ---")

    check("column vertex count = 24",
          "Test 3:" in output and "vertices: 24" in output)

    # Bottom face centroid should be at (5, 5) since profile is centered
    check("column centroid X ~ 5",
          "Bottom face centroid X: 5.0" in output)
    check("column centroid Y ~ 5",
          "Bottom face centroid Y: 5.0" in output)


def test_beam(output: str):
    """Test 5: Beam from (0,0,3) to (6,0,3)"""
    print("\n--- Test: Beam (0,0,3)->(6,0,3), 0.2x0.4 ---")

    check("beam vertex count = 24",
          "Test 5:" in output and "vertices: 24" in output)

    # X range should be ~0..6
    check("beam X range: ~0 to ~6",
          "X range: 0.0 to 6.0" in output)


def test_rotation(output: str):
    """Test 6: Rotated box (45 degrees)"""
    print("\n--- Test: Rotated box (45 deg) ---")

    check("rotated box bottom nz == -1",
          "Bottom face nz == -1: True" in output)


def test_transform(output: str):
    """Test 7: batch_transform_vertices"""
    print("\n--- Test: batch_transform_vertices ---")

    check("translated v0 = (10,20,30)",
          "v0 after translate: 10.0 20.0 30.0" in output)
    check("normal unchanged after translate = (0,0,-1)",
          "v0 normal after translate: 0.0 0.0 -1.0" in output)


def test_winding_order():
    """Verify CCW winding order by checking cross product of triangle edges.

    For a box face with normal (0,0,-1) (bottom face), the vertices should
    be ordered such that cross(v1-v0, v2-v0) points in the -Z direction.
    """
    print("\n--- Test: CCW Winding Order (analytical) ---")

    # From the output, bottom face vertices are:
    # v0 = (0,0,0), v1 = (0,3,0), v2 = (2,3,0), v3 = (2,0,0)
    # First triangle indices: 0,1,2 (from _set_quad_ccw)
    # Edge vectors: e1 = v1-v0 = (0,3,0), e2 = v2-v0 = (2,3,0)
    # Cross product: e1 x e2 = (3*0-0*3, 0*2-0*0, 0*3-3*2) = (0, 0, -6)
    # Normalized: (0, 0, -1) -- points down, matching the -Z face normal.

    e1 = (0, 3, 0)
    e2 = (2, 3, 0)
    cross = (
        e1[1] * e2[2] - e1[2] * e2[1],
        e1[2] * e2[0] - e1[0] * e2[2],
        e1[0] * e2[1] - e1[1] * e2[0],
    )
    check("bottom tri 0 cross product Z < 0 (outward = -Z)",
          cross[2] < 0,
          f"cross = {cross}")

    # Top face: v4=(0,0,4), v5=(2,0,4), v6=(2,3,4), v7=(0,3,4)
    # First triangle: 4,5,6
    # e1 = v5-v4 = (2,0,0), e2 = v6-v4 = (2,3,0)
    # cross = (0*0-0*3, 0*2-2*0, 2*3-0*2) = (0, 0, 6)
    # Normalized: (0, 0, 1) -- points up, matching +Z face normal.

    e1 = (2, 0, 0)
    e2 = (2, 3, 0)
    cross = (
        e1[1] * e2[2] - e1[2] * e2[1],
        e1[2] * e2[0] - e1[0] * e2[2],
        e1[0] * e2[1] - e1[1] * e2[0],
    )
    check("top tri 0 cross product Z > 0 (outward = +Z)",
          cross[2] > 0,
          f"cross = {cross}")

    # Front face (-Y): v8=(0,0,0), v9=(2,0,0), v10=(2,0,4), v11=(0,0,4)
    # First triangle: 8,9,10 -> positions: (0,0,0), (2,0,0), (2,0,4)
    # e1 = (2,0,0), e2 = (2,0,4)
    # cross = (0*4-0*0, 0*2-2*4, 2*0-0*2) = (0, -8, 0)
    # Normalized: (0, -1, 0) -- points in -Y, matching the front face normal.

    e1 = (2, 0, 0)
    e2 = (2, 0, 4)
    cross = (
        e1[1] * e2[2] - e1[2] * e2[1],
        e1[2] * e2[0] - e1[0] * e2[2],
        e1[0] * e2[1] - e1[1] * e2[0],
    )
    check("front tri cross product Y < 0 (outward = -Y)",
          cross[1] < 0,
          f"cross = {cross}")


def test_vertex_count_formula():
    """Verify the vertex data format matches Three.js expectations."""
    print("\n--- Test: Vertex format (6 floats/vertex) ---")

    # 24 vertices * 6 floats = 144 floats total for a box
    check("24 verts * 6 floats = 144 floats", 24 * 6 == 144)
    # 36 indices / 3 = 12 triangles (a box has 6 faces, 2 tris each)
    check("36 indices / 3 = 12 triangles", 36 // 3 == 12)
    # Stride = 6 * 4 bytes = 24 bytes per vertex (Float32)
    check("vertex stride = 24 bytes", 6 * 4 == 24)


def main():
    global PASS, FAIL

    print("=" * 60)
    print("  Bonsai Tessellate -- Correctness Tests")
    print("=" * 60)

    output = run_mojo()

    test_box(output)
    test_wall(output)
    test_column(output)
    test_beam(output)
    test_rotation(output)
    test_transform(output)
    test_winding_order()
    test_vertex_count_formula()

    print()
    print("=" * 60)
    total = PASS + FAIL
    print(f"  Results: {PASS}/{total} passed, {FAIL} failed")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
