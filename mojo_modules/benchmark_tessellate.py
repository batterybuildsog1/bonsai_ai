#!/usr/bin/env python3
"""Benchmark: Mojo tessellation vs IfcOpenShell geometry generation.

Compares wall creation times for 100, 500, and 1000 elements:
  - IfcOpenShell: full IFC geometry (create entity, representation, placement)
  - Mojo: pure tessellation via subprocess (compiled binary)

Run from the mojo_modules/ directory:
    python benchmark_tessellate.py
"""

import math
import os
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Mojo benchmark (runs compiled binary via subprocess)
# ---------------------------------------------------------------------------

MOJO_BIN = os.path.expanduser("~/Library/Python/3.9/bin/mojo")
TESS_MOJO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bonsai_tessellate.mojo")


def benchmark_mojo():
    """Run the Mojo self-test/benchmark and capture output."""
    print("=== Mojo Tessellation Benchmark ===")
    print(f"Running: {MOJO_BIN} run {TESS_MOJO}")
    print()

    result = subprocess.run(
        [MOJO_BIN, "run", TESS_MOJO],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print("ERROR running Mojo:")
        print(result.stderr)
        return

    # Extract benchmark lines
    in_bench = False
    for line in result.stdout.splitlines():
        if "Benchmark" in line:
            in_bench = True
        if in_bench:
            print(line)

    print()


# ---------------------------------------------------------------------------
# IfcOpenShell benchmark
# ---------------------------------------------------------------------------


def benchmark_ifcopenshell():
    """Benchmark IfcOpenShell wall creation for comparison."""
    print("=== IfcOpenShell Geometry Benchmark ===")

    try:
        import ifcopenshell
        import ifcopenshell.api.context
        import ifcopenshell.api.geometry
        import ifcopenshell.api.project
        import ifcopenshell.api.root
        import numpy as np
    except ImportError:
        print("IfcOpenShell not available -- skipping.")
        print("Install with: pip install ifcopenshell")
        return

    for n in [100, 500, 1000]:
        # Fresh model each time
        model = ifcopenshell.api.project.create_file(version="IFC4")
        project = ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="Bench")

        # Set up units and contexts
        ifcopenshell.api.unit.assign_unit(model)
        model3d = ifcopenshell.api.context.add_context(model, context_type="Model")
        body = ifcopenshell.api.context.add_context(
            model,
            context_type="Model",
            context_identifier="Body",
            target_view="MODEL_VIEW",
            parent=model3d,
        )

        start = time.perf_counter_ns()
        for i in range(n):
            wall = ifcopenshell.api.root.create_entity(model, ifc_class="IfcWall", name=f"W{i}")

            # Placement matrix (rotation + translation)
            angle = 0.0
            matrix = np.eye(4)
            matrix[0, 0] = math.cos(angle)
            matrix[0, 1] = -math.sin(angle)
            matrix[1, 0] = math.sin(angle)
            matrix[1, 1] = math.cos(angle)
            matrix[:, 3][0:3] = (float(i), 0.0, 0.0)
            ifcopenshell.api.geometry.edit_object_placement(
                model, product=wall, matrix=matrix, is_si=True
            )

            # Wall representation
            rep = ifcopenshell.api.geometry.add_wall_representation(
                model, context=body, length=5.0, height=3.0, thickness=0.2
            )
            ifcopenshell.api.geometry.assign_representation(
                model, product=wall, representation=rep
            )

        elapsed_ns = time.perf_counter_ns() - start
        elapsed_us = elapsed_ns / 1000
        per_element_us = elapsed_us / n
        print(f"  {n:>5} walls: {elapsed_us:>10.0f} us total, {per_element_us:.1f} us/element")

    print()


# ---------------------------------------------------------------------------
# Comparison summary
# ---------------------------------------------------------------------------


def compare():
    """Run both benchmarks and print comparison."""
    print("=" * 64)
    print("  Bonsai Tessellation Benchmark")
    print("  Mojo 0.25.6 vs IfcOpenShell geometry generation")
    print("=" * 64)
    print()

    benchmark_mojo()
    benchmark_ifcopenshell()

    print("=" * 64)
    print("  Summary")
    print("=" * 64)
    print()
    print("  Mojo tessellation produces the same geometric output")
    print("  (vertices + indices + normals) that Three.js / WebGPU need,")
    print("  bypassing the IFC schema entirely for visualization.")
    print()
    print("  IfcOpenShell creates full IFC4 entities with schema validation,")
    print("  property sets, and representation items -- necessary for the")
    print("  authoritative .ifc file but much heavier for real-time preview.")
    print()
    print("  The Mojo path is intended for the viewer's real-time preview;")
    print("  IfcOpenShell remains the source of truth for the .ifc model.")
    print()


if __name__ == "__main__":
    compare()
