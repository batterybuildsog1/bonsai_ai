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


class FastSolverTests(unittest.TestCase):
    """Tests for the factor-once-solve-many Cholesky solver."""

    def _build_portal_frame(self):
        """Build a simple portal frame with 2 load cases and 3 combos using real PyNite."""
        try:
            pynite = load_pynite_module()
        except RuntimeError:
            self.skipTest("PyNite not installed")
        m = pynite.FEModel3D()
        m.add_material("steel", 200e9, 200e9 / (2 * (1 + 0.3)), 0.3, 7850)
        m.add_section("s1", 0.01, 1e-5, 1e-5, 2e-5)
        m.add_node("N1", 0, 0, 0)
        m.add_node("N2", 0, 0, 3)
        m.add_node("N3", 6, 0, 3)
        m.add_node("N4", 6, 0, 0)
        m.add_member("C1", "N1", "N2", "steel", "s1")
        m.add_member("B1", "N2", "N3", "steel", "s1")
        m.add_member("C2", "N3", "N4", "steel", "s1")
        m.def_support("N1", support_DX=True, support_DY=True, support_DZ=True,
                       support_RX=True, support_RY=True, support_RZ=True)
        m.def_support("N4", support_DX=True, support_DY=True, support_DZ=True,
                       support_RX=True, support_RY=True, support_RZ=True)
        m.add_member_dist_load("B1", "FZ", -10000, -10000, case="DL")
        m.add_node_load("N2", "FX", 5000, case="WL")
        m.add_load_combo("1.2DL+1.0WL", {"DL": 1.2, "WL": 1.0})
        m.add_load_combo("1.4DL", {"DL": 1.4})
        m.add_load_combo("0.9DL+1.0WL", {"DL": 0.9, "WL": 1.0})
        return m

    def test_fast_solver_matches_pynite(self) -> None:
        """Verify factor-once solver produces identical results to PyNite's spsolve."""
        m_pynite = self._build_portal_frame()
        m_pynite.analyze_linear(log=False)

        m_fast = self._build_portal_frame()
        PyNiteSolverBackend._run_solver_fast(m_fast)

        combos = ["1.2DL+1.0WL", "1.4DL", "0.9DL+1.0WL"]
        nodes = ["N1", "N2", "N3", "N4"]
        for combo in combos:
            for nname in nodes:
                np = m_pynite.nodes[nname]
                nf = m_fast.nodes[nname]
                for attr in ("DX", "DY", "DZ", "RX", "RY", "RZ"):
                    vp = float(getattr(np, attr).get(combo, 0.0))
                    vf = float(getattr(nf, attr).get(combo, 0.0))
                    self.assertAlmostEqual(vp, vf, places=10,
                                           msg=f"{combo}/{nname}/{attr}")
            for nname in ("N1", "N4"):
                np = m_pynite.nodes[nname]
                nf = m_fast.nodes[nname]
                for attr in ("RxnFX", "RxnFY", "RxnFZ", "RxnMX", "RxnMY", "RxnMZ"):
                    vp = float(getattr(np, attr).get(combo, 0.0))
                    vf = float(getattr(nf, attr).get(combo, 0.0))
                    self.assertAlmostEqual(vp, vf, places=5,
                                           msg=f"{combo}/{nname}/{attr}")

    def test_fast_solver_sets_solution_flag(self) -> None:
        m = self._build_portal_frame()
        PyNiteSolverBackend._run_solver_fast(m)
        self.assertEqual(m.solution, "Linear")

    def test_env_flag_pynite_skips_fast_path(self) -> None:
        """Setting BONSAI_FEA_SOLVER=pynite should use the original solver."""
        m = self._build_portal_frame()
        with mock.patch.dict("os.environ", {"BONSAI_FEA_SOLVER": "pynite"}):
            PyNiteSolverBackend._run_solver(m)
        self.assertEqual(m.solution, "Linear")

    def test_env_flag_fast_uses_cholesky(self) -> None:
        """Setting BONSAI_FEA_SOLVER=fast should use the Cholesky solver."""
        m = self._build_portal_frame()
        with mock.patch.dict("os.environ", {"BONSAI_FEA_SOLVER": "fast"}):
            PyNiteSolverBackend._run_solver(m)
        self.assertEqual(m.solution, "Linear")
        # Verify some node has non-zero displacement
        n2 = m.nodes["N2"]
        self.assertNotEqual(n2.DZ.get("1.4DL", 0.0), 0.0)

    def test_fast_solver_fallback_on_fake_model(self) -> None:
        """The fast solver should gracefully fall back for non-PyNite models."""
        fake_model = _FakeFEModel3D()
        fake_model.load_combos = {"test": {"DL": 1.0}}
        # This should not raise -- it should fall back to analyze_linear
        PyNiteSolverBackend._run_solver(fake_model)


if __name__ == "__main__":
    unittest.main()
