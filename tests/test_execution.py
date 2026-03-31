from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
import sys
import types
from pathlib import Path

import ifcopenshell

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "bonsai_ai"


def _load_bonsai_module(name: str):
    package = sys.modules.get("bonsai_ai")
    if package is None:
        package = types.ModuleType("bonsai_ai")
        package.__path__ = [str(SRC)]
        sys.modules["bonsai_ai"] = package
    full_name = f"bonsai_ai.{name}"
    module = sys.modules.get(full_name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(full_name, SRC / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load bonsai_ai.{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


_load_bonsai_module("contracts")
_load_bonsai_module("ifc_author")
_load_bonsai_module("pipeline")
execution_module = _load_bonsai_module("execution")
HeadlessIfcExecutor = execution_module.HeadlessIfcExecutor


class HeadlessExecutionTests(unittest.TestCase):
    def test_headless_executor_materializes_ifc_from_plan(self) -> None:
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Simple structural panel test",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_wall",
                    "name": "Panel Exterior",
                    "storey": "Level 0",
                    "x1": 0.0,
                    "y1": 0.0,
                    "x2": 1.2,
                    "y2": 0.0,
                    "base_z": 0.0,
                    "height": 5.0,
                    "thickness": 0.057,
                },
                {
                    "type": "create_column",
                    "name": "Panel Support",
                    "storey": "Level 0",
                    "x": 0.0,
                    "y": 0.2,
                    "base_z": 0.0,
                    "width": 0.2,
                    "depth": 0.2,
                    "height": 5.0,
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "headless.ifc")
            report = HeadlessIfcExecutor().execute_plan(plan, output)

            self.assertTrue(os.path.exists(output))
            self.assertIn("Panel Exterior", report.created)
            self.assertEqual(report.items[1].ifc_class, "IfcWall")
            self.assertEqual(report.items[2].ifc_class, "IfcColumn")
            model = ifcopenshell.open(output)
            self.assertEqual(len(model.by_type("IfcWall")), 1)
            self.assertEqual(len(model.by_type("IfcColumn")), 1)

    def test_headless_executor_materializes_beams_and_panels(self) -> None:
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Steel frame and panel test",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_beam",
                    "name": "Beam A",
                    "storey": "Level 0",
                    "x1": 0.0,
                    "y1": 0.0,
                    "x2": 6.0,
                    "y2": 0.0,
                    "base_z": 3.5,
                    "end_z": 4.5,
                    "width": 0.3,
                    "depth": 0.5,
                },
                {
                    "type": "create_panel",
                    "name": "Panel A",
                    "storey": "Level 0",
                    "x": 2.0,
                    "y": 0.0,
                    "base_z": 0.0,
                    "width": 1.2,
                    "height": 3.0,
                    "thickness": 0.08,
                },
                {
                    "type": "create_panel",
                    "name": "Plate A",
                    "storey": "Level 0",
                    "x": 0.0,
                    "y": 0.0,
                    "base_z": 3.9,
                    "width": 0.35,
                    "depth": 0.35,
                    "thickness": 0.02,
                    "orientation": "horizontal",
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "headless.ifc")
            report = HeadlessIfcExecutor().execute_plan(plan, output)

            self.assertTrue(os.path.exists(output))
            self.assertIn("Beam A", report.created)
            self.assertIn("Panel A", report.created)
            self.assertIn("Plate A", report.created)
            model = ifcopenshell.open(output)
            self.assertEqual(len(model.by_type("IfcBeam")), 1)
            self.assertEqual(len(model.by_type("IfcPlate")), 2)

    def test_headless_executor_materializes_footing_with_metadata(self) -> None:
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Footing metadata test",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Foundations", "elevation": -1.2},
                {
                    "type": "create_footing",
                    "name": "Pad Footing 1",
                    "storey": "Foundations",
                    "x": 0.0,
                    "y": 0.0,
                    "base_z": -1.2,
                    "length": 2.4,
                    "width": 2.4,
                    "thickness": 0.75,
                    "foundation": {
                        "imposed_load_kn": 680.0,
                        "concrete_strength_mpa": 35.0,
                        "rebar_grade": "Grade 60",
                        "rebar_weight_kg": 145.5,
                    },
                    "semantics": {"role": "foundations", "group_path": ["Foundations", "Grid A1"]},
                    "basis_notes": "Starter footing sized from imposed column load metadata.",
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "headless.ifc")
            report = HeadlessIfcExecutor().execute_plan(plan, output)

            self.assertTrue(os.path.exists(output))
            self.assertIn("Pad Footing 1", report.created)
            self.assertEqual(report.items[1].ifc_class, "IfcFooting")
            self.assertEqual(report.items[1].metadata["ImposedLoadKN"], 680.0)
            self.assertEqual(report.items[1].metadata["ConcreteStrengthMPa"], 35.0)
            self.assertEqual(report.items[1].metadata["RebarGrade"], "Grade 60")
            self.assertEqual(report.items[1].metadata["RebarWeightKg"], 145.5)
            self.assertEqual(report.items[1].metadata["semantics"]["group_path"], ["Foundations", "Grid A1"])
            model = ifcopenshell.open(output)
            self.assertEqual(len(model.by_type("IfcFooting")), 1)

    def test_headless_executor_overwrites_existing_output_when_enabled(self) -> None:
        first_plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "First plan",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_wall",
                    "name": "Wall A",
                    "storey": "Level 0",
                    "x1": 0.0,
                    "y1": 0.0,
                    "x2": 4.0,
                    "y2": 0.0,
                    "base_z": 0.0,
                    "height": 3.0,
                    "thickness": 0.2,
                },
            ],
        }
        second_plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Second plan",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_column",
                    "name": "Column A",
                    "storey": "Level 0",
                    "x": 1.0,
                    "y": 1.0,
                    "base_z": 0.0,
                    "width": 0.3,
                    "depth": 0.3,
                    "height": 3.0,
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "headless.ifc")
            HeadlessIfcExecutor(overwrite_existing=True).execute_plan(first_plan, output)
            HeadlessIfcExecutor(overwrite_existing=True).execute_plan(second_plan, output)

            model = ifcopenshell.open(output)
            self.assertEqual(len(model.by_type("IfcWall")), 0)
            self.assertEqual(len(model.by_type("IfcColumn")), 1)

    def test_headless_executor_overwrites_existing_ifc(self) -> None:
        plan_a = {
            "version": "1.0",
            "units": "meters",
            "summary": "First plan",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_beam",
                    "name": "Beam A",
                    "storey": "Level 0",
                    "x1": 0.0,
                    "y1": 0.0,
                    "x2": 4.0,
                    "y2": 0.0,
                    "base_z": 3.0,
                    "width": 0.2,
                    "depth": 0.4,
                },
            ],
        }
        plan_b = {
            "version": "1.0",
            "units": "meters",
            "summary": "Second plan",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_panel",
                    "name": "Plate A",
                    "storey": "Level 0",
                    "x": 0.0,
                    "y": 0.0,
                    "base_z": 3.5,
                    "width": 0.35,
                    "depth": 0.35,
                    "thickness": 0.02,
                    "orientation": "horizontal",
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "headless.ifc")
            executor = HeadlessIfcExecutor(overwrite_existing=True)
            executor.execute_plan(plan_a, output)
            executor.execute_plan(plan_b, output)

            model = ifcopenshell.open(output)
            self.assertEqual(len(model.by_type("IfcBeam")), 0)
            self.assertEqual(len(model.by_type("IfcPlate")), 1)

    def test_headless_executor_materializes_footings(self) -> None:
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Foundation test",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_footing",
                    "name": "Footing A",
                    "storey": "Level 0",
                    "x": 0.0,
                    "y": 0.0,
                    "base_z": -1.0,
                    "width": 2.2,
                    "depth": 2.2,
                    "thickness": 0.55,
                    "foundation": {
                        "foundation_type": "spread_footing",
                        "service_reaction_kN": 320.0,
                        "concrete_strength_mpa": 35.0,
                        "rebar_grade": "ASTM A615 Grade 60",
                        "rebar_weight_kg": 120.0,
                    },
                    "semantics": {
                        "role": "foundations",
                        "group_path": ["Substructure", "Footings"],
                    },
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "foundation.ifc")
            report = HeadlessIfcExecutor().execute_plan(plan, output)
            self.assertIn("Footing A", report.created)
            model = ifcopenshell.open(output)
            self.assertEqual(len(model.by_type("IfcFooting")), 1)


if __name__ == "__main__":
    unittest.main()
