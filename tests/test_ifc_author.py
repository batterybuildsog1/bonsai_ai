from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import ifcopenshell
from ifcopenshell.util.element import get_psets

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


ifc_author_module = _load_bonsai_module("ifc_author")
AI_PSET = ifc_author_module.AI_PSET
IfcAuthor = ifc_author_module.IfcAuthor


@dataclass
class PlannedToolCall:
    id: str
    name: str
    arguments: dict


class IfcAuthorTests(unittest.TestCase):
    def test_creates_basic_building(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "office.ifc")
            author = IfcAuthor(path)
            plan = [
                PlannedToolCall("1", "ensure_project", {"project_name": "Office", "site_name": "Site", "building_name": "HQ"}),
                PlannedToolCall("2", "ensure_storey", {"name": "Level 0", "elevation": 0.0}),
                PlannedToolCall(
                    "3",
                    "create_rectangular_slab",
                    {"name": "Ground Slab", "storey_name": "Level 0", "x": 0.0, "y": 0.0, "z": 0.0, "length": 20.0, "width": 30.0, "thickness": 0.2},
                ),
                PlannedToolCall(
                    "4",
                    "create_wall",
                    {
                        "name": "South Wall",
                        "storey_name": "Level 0",
                        "start_x": 0.0,
                        "start_y": 0.0,
                        "end_x": 20.0,
                        "end_y": 0.0,
                        "base_z": 0.2,
                        "height": 3.0,
                        "thickness": 0.2,
                    },
                ),
            ]
            author.apply_plan(plan)
            author.save()

            model = ifcopenshell.open(path)
            self.assertEqual(len(model.by_type("IfcProject")), 1)
            self.assertEqual(len(model.by_type("IfcBuildingStorey")), 1)
            self.assertEqual(len(model.by_type("IfcSlab")), 1)
            self.assertEqual(len(model.by_type("IfcWall")), 1)

    def test_creates_hosted_openings_and_curtain_wall(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "components.ifc")
            author = IfcAuthor(path)
            author.ensure_project("Office", "Site", "HQ")
            author.ensure_storey("Level 0", 0.0)
            author.create_wall("Facade Wall", "Level 0", 0.0, 0.0, 10.0, 0.0, 0.0, 3.0, 0.2)
            author.create_door("Front Door", "Level 0", "Facade Wall", 1.0, 0.95, 2.1, 0.05)
            author.create_window("Window A", "Level 0", "Facade Wall", 4.0, 1.0, 1.5, 1.2, 0.05)
            author.create_curtain_wall("South Curtain", "Level 0", 0.0, 5.0, 0.0, 6.0, 3.0, 0.0, 1.5, 1.5, 0.05)
            author.save()

            model = ifcopenshell.open(path)
            self.assertEqual(len(model.by_type("IfcDoor")), 1)
            self.assertEqual(len(model.by_type("IfcWindow")), 1)
            self.assertEqual(len(model.by_type("IfcRelFillsElement")), 2)
            self.assertEqual(len(model.by_type("IfcRelVoidsElement")), 2)
            self.assertEqual(len(model.by_type("IfcCurtainWall")), 1)
            self.assertGreaterEqual(len(model.by_type("IfcPlate")), 1)

    def test_uses_meter_units_for_member_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "members.ifc")
            author = IfcAuthor(path)
            author.ensure_storey("Level 0", 0.0)
            author.create_beam("Test Beam", "Level 0", 0.0, 0.0, 5.0, 0.0, 0.0, 0.5, 1.0)
            author.create_column("Test Column", "Level 0", 0.0, 0.0, 0.0, 0.5, 1.0, 3.0)
            author.save()

            model = ifcopenshell.open(path)
            units = model.by_type("IfcUnitAssignment")[0].Units
            length_unit = next(unit for unit in units if getattr(unit, "UnitType", None) == "LENGTHUNIT")
            self.assertEqual(length_unit.is_a(), "IfcSIUnit")
            self.assertEqual(getattr(length_unit, "Prefix", None), None)
            self.assertEqual(getattr(length_unit, "Name", None), "METRE")

            beam = model.by_type("IfcBeam")[0]
            beam_solid = beam.Representation.Representations[0].Items[0]
            self.assertAlmostEqual(float(beam_solid.SweptArea.XDim), 0.5)
            self.assertAlmostEqual(float(beam_solid.SweptArea.YDim), 1.0)
            self.assertAlmostEqual(float(beam_solid.Depth), 5.0)

            column = model.by_type("IfcColumn")[0]
            column_solid = column.Representation.Representations[0].Items[0]
            self.assertAlmostEqual(float(column_solid.SweptArea.XDim), 0.5)
            self.assertAlmostEqual(float(column_solid.SweptArea.YDim), 1.0)
            self.assertAlmostEqual(float(column_solid.Depth), 3.0)

    def test_creates_footing_with_rebar_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "footings.ifc")
            author = IfcAuthor(path)
            author.ensure_storey("Level 0", 0.0)
            author.create_footing(
                "F1",
                "Level 0",
                0.0,
                0.0,
                -1.2,
                2.4,
                2.4,
                0.6,
                foundation_type="spread_footing",
                service_reaction_kN=450.0,
                concrete_strength_mpa=35.0,
                rebar_grade="ASTM A615 Grade 60",
                rebar_weight_kg=180.0,
                role="foundations",
                group_path=["Substructure", "Footings"],
            )
            author.save()

            model = ifcopenshell.open(path)
            footings = model.by_type("IfcFooting")
            self.assertEqual(len(footings), 1)
            metadata = author._metadata(footings[0])
            self.assertEqual(metadata["FoundationType"], "spread_footing")
            self.assertEqual(metadata["RebarGrade"], "ASTM A615 Grade 60")
            self.assertEqual(metadata["role"], "foundations")
            self.assertIn("Footings", metadata["group_path"])

    def test_creates_footing_with_metadata_and_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "footing.ifc")
            author = IfcAuthor(path)
            author.ensure_storey("Foundations", -1.2)
            author.create_footing(
                name="Pad Footing 1",
                storey_name="Foundations",
                x=0.0,
                y=0.0,
                base_z=-1.2,
                length=2.4,
                width=2.4,
                thickness=0.75,
                imposed_load_kn=680.0,
                concrete_strength_mpa=35.0,
                rebar_grade="Grade 60",
                total_rebar_weight_kg=145.5,
                basis_notes="Starter footing sized from imposed column load metadata.",
                semantic_metadata={"role": "foundations", "group_path": ["Foundations", "Grid A1"]},
            )
            author.save()

            model = ifcopenshell.open(path)
            footing = model.by_type("IfcFooting")[0]
            self.assertIsNotNone(footing.Representation)
            self.assertGreater(len(footing.Representation.Representations[0].Items), 0)

            psets = get_psets(footing, psets_only=True, should_inherit=False)
            footing_pset = psets[AI_PSET]
            self.assertEqual(footing_pset["StructuralKind"], "foundation")
            self.assertEqual(footing_pset["ImposedLoadKN"], 680.0)
            self.assertEqual(footing_pset["ConcreteStrengthMPa"], 35.0)
            self.assertEqual(footing_pset["RebarGrade"], "Grade 60")
            self.assertEqual(footing_pset["TotalRebarWeightKg"], 145.5)
            self.assertEqual(footing_pset["BasisNotes"], "Starter footing sized from imposed column load metadata.")
            self.assertEqual(
                json.loads(footing_pset["semantic_metadata"]),
                {"role": "foundations", "group_path": ["Foundations", "Grid A1"]},
            )


if __name__ == "__main__":
    unittest.main()
