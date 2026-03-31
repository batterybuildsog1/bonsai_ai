from __future__ import annotations

import json
import types
import unittest
from pathlib import Path
from unittest import mock

from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    AnalyticalModel,
    DesignBrief,
    DesignPackage,
    LoadAction,
    LoadCase,
    LoadCombination,
    MaterialSpec,
    SectionSpec,
    StructuralElement,
    SupportSpec,
)
from bonsai_ai.pynite_backend import PyNiteSolverBackend, load_pynite_module


class _FakeNode:
    def __init__(self, name: str, x: float, y: float, z: float):
        self.name = name
        self.X = x
        self.Y = y
        self.Z = z
        self.DX = {}
        self.DY = {}
        self.DZ = {}
        self.RxnFX = {}
        self.RxnFY = {}
        self.RxnFZ = {}
        self.RxnMX = {}
        self.RxnMY = {}
        self.RxnMZ = {}


class _FakeFEModel3D:
    def __init__(self):
        self.nodes = {}
        self.members = {}
        self.quads = {}
        self.plates = {}
        self.materials = {}
        self.sections = {}
        self.supports = {}
        self.member_loads = []
        self.node_loads = []
        self.quad_pressures = []
        self.load_combos = {}

    def add_material(self, name, E, G, nu, rho):
        self.materials[name] = {"E": E, "G": G, "nu": nu, "rho": rho}

    def add_section(self, name, A, Iy, Iz, J):
        self.sections[name] = {"A": A, "Iy": Iy, "Iz": Iz, "J": J}

    def add_node(self, name, x, y, z):
        self.nodes[name] = _FakeNode(name, x, y, z)

    def add_member(self, name, i_node, j_node, material, section):
        self.members[name] = {"i": i_node, "j": j_node, "material": material, "section": section}

    def add_quad(self, name, i, j, m, n, thickness, material):
        self.quads[name] = {"nodes": [i, j, m, n], "thickness": thickness, "material": material}

    def def_support(self, node_name, **kwargs):
        self.supports[node_name] = kwargs

    def add_node_load(self, node_name, direction, magnitude, case_name):
        self.node_loads.append((node_name, direction, magnitude, case_name))

    def add_member_dist_load(self, member_name, direction, w1, w2, case=None):
        self.member_loads.append((member_name, direction, w1, w2, case))

    def add_quad_surface_pressure(self, quad_name, pressure, case_name):
        self.quad_pressures.append((quad_name, pressure, case_name))

    def add_load_combo(self, name, factors):
        self.load_combos[name] = dict(factors)

    def analyze_linear(self):
        for combo_name in self.load_combos:
            for node_name, node in self.nodes.items():
                node.DX[combo_name] = 0.001 if node_name.endswith("_j") else 0.0
                node.DY[combo_name] = 0.0
                node.DZ[combo_name] = -0.002 if node_name.endswith("_j") else 0.0
                if node_name in self.supports:
                    node.RxnFZ[combo_name] = 12.5
                    node.RxnFX[combo_name] = 0.0
                    node.RxnFY[combo_name] = 0.0
                    node.RxnMX[combo_name] = 0.0
                    node.RxnMY[combo_name] = 0.0
                    node.RxnMZ[combo_name] = 0.0


class PyNiteBackendTests(unittest.TestCase):
    def test_loader_raises_clear_error_when_pynite_missing(self) -> None:
        with mock.patch("bonsai_ai.pynite_backend.importlib.import_module", side_effect=ModuleNotFoundError("Pynite")):
            with self.assertRaises(RuntimeError) as ctx:
                load_pynite_module()
        self.assertIn("PyNite is not installed", str(ctx.exception))

    def test_backend_writes_solver_result_and_returns_summary(self) -> None:
        output_dir = Path("/tmp/bonsai_pynite_backend_test")
        output_dir.mkdir(parents=True, exist_ok=True)

        analytical_model = AnalyticalModel(
            materials=[
                MaterialSpec(
                    id="steel_default",
                    family="steel",
                    model="elastic_isotropic",
                    properties={"density_kg_m3": 7850, "elastic_modulus_pa": 200_000_000_000, "poisson_ratio": 0.3},
                ),
                MaterialSpec(
                    id="concrete_default",
                    family="concrete",
                    model="elastic_isotropic",
                    properties={"density_kg_m3": 2400, "elastic_modulus_pa": 27_000_000_000, "poisson_ratio": 0.2},
                ),
            ],
            sections=[
                SectionSpec(id="col_rect", kind="rect_profile", material_id="steel_default", dimensions={"width": 0.3, "depth": 0.3}),
                SectionSpec(id="beam_rect", kind="rect_profile", material_id="steel_default", dimensions={"width": 0.25, "depth": 0.5}),
                SectionSpec(id="wall_shell", kind="shell", material_id="concrete_default", dimensions={"thickness": 0.2}),
            ],
            elements=[
                StructuralElement(
                    id="column_a",
                    kind="column",
                    section_id="col_rect",
                    geometry={"origin": [0.0, 0.0, 0.0], "height": 3.0, "width": 0.3, "depth": 0.3},
                ),
                StructuralElement(
                    id="wall_a",
                    kind="wall",
                    section_id="wall_shell",
                    geometry={"start": [0.0, 0.0, 0.0], "end": [4.0, 0.0, 0.0], "height": 3.0, "thickness": 0.2},
                ),
                StructuralElement(
                    id="beam_a",
                    kind="beam",
                    section_id="beam_rect",
                    geometry={"start": [0.0, 0.0, 3.0], "end": [4.0, 0.0, 3.0], "width": 0.25, "depth": 0.5},
                ),
            ],
            supports=[
                SupportSpec(
                    id="base_column",
                    target_id="column_a",
                    target_kind="line",
                    restraints={"dx": True, "dy": True, "dz": True, "rx": True, "ry": True, "rz": True},
                )
            ],
            load_cases=[
                LoadCase(
                    name="Gravity",
                    domain=AnalysisDomain.GRAVITY,
                    code_basis="ASCE 7-22",
                    actions=[
                        LoadAction(target_id="column_a", kind="self_weight", magnitude=1.0),
                        LoadAction(target_id="beam_a", kind="self_weight", magnitude=1.0),
                    ],
                ),
                LoadCase(
                    name="Wind X+",
                    domain=AnalysisDomain.WIND,
                    code_basis="ASCE 7-22",
                    actions=[LoadAction(target_id="wall_a", kind="pressure", magnitude=0.75, direction="global_x")],
                ),
            ],
            load_combinations=[LoadCombination(name="ULS", case_factors={"Gravity": 1.2, "Wind X+": 1.0})],
        )
        package = DesignPackage(
            brief=DesignBrief(prompt="Analyze one column and one wall"),
            analytical_model=analytical_model,
        )
        request = AnalysisRequest(
            solver="pynite",
            design_codes=["ASCE 7-22"],
            load_cases=analytical_model.load_cases,
            load_combinations=analytical_model.load_combinations,
        )

        backend = PyNiteSolverBackend(pynite_module=types.SimpleNamespace(FEModel3D=_FakeFEModel3D))
        result = backend.analyze(request, package, output_dir)

        self.assertEqual(result.solver, "pynite")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.governing_cases, ["ULS"])
        self.assertIn("max_displacement", result.summary)
        self.assertIn("support_reactions", result.summary)
        self.assertEqual(result.summary["model_counts"]["members"], 2)
        self.assertEqual(result.summary["model_counts"]["quads"], 1)
        payload = json.loads((output_dir / "solver_result.json").read_text())
        self.assertEqual(payload["solver"], "pynite")
        self.assertEqual(payload["load_combinations"], ["ULS"])
        self.assertEqual(payload["summary"]["model_counts"]["nodes"], 4)
        self.assertAlmostEqual(payload["summary"]["support_reactions"]["ULS"]["fz"], 12.5)
        self.assertAlmostEqual(payload["summary"]["support_target_reactions"]["ULS"]["column_a"]["fz"], 12.5)
        self.assertIn("column_a", payload["summary"]["member_demands"])
        self.assertEqual(payload["summary"]["member_demands"]["column_a"]["length_m"], 3.0)


if __name__ == "__main__":
    unittest.main()
