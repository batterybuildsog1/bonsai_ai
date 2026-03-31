from __future__ import annotations

import unittest

from bonsai_ai.contracts import MaterialSpec, PhysicalModelSpec, SectionSpec, StructuralSourceElement, StructuralSourceModel
from bonsai_ai.plan_roundtrip import apply_sized_sections_to_physical_model, apply_sized_sections_to_plan


class PlanRoundtripTests(unittest.TestCase):
    def test_applies_resolved_section_dimensions_back_to_authored_plan(self) -> None:
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Sized frame",
            "assumptions": [],
            "actions": [
                {
                    "type": "create_column",
                    "name": "Column A",
                    "storey": "Level 0",
                    "x": 0.0,
                    "y": 0.0,
                    "base_z": 0.0,
                    "width": 0.25,
                    "depth": 0.25,
                    "height": 4.0,
                    "semantics": {"element_id": "column_a"},
                }
            ],
        }
        source_model = StructuralSourceModel(
            materials=[MaterialSpec(id="steel_w_shapes", family="steel", model="elastic_isotropic")],
            sections=[
                SectionSpec(
                    id="catalog_primary_columns_w_w10x33",
                    kind="catalog_profile",
                    material_id="steel_w_shapes",
                    dimensions={"width": 0.210, "depth": 0.264},
                    metadata={"catalog_section_name": "W10X33"},
                )
            ],
            elements=[
                StructuralSourceElement(
                    id="column_a",
                    kind="column",
                    role="primary_column",
                    section_id="catalog_primary_columns_w_w10x33",
                    metadata={"source_name": "Column A"},
                )
            ],
        )

        summary = apply_sized_sections_to_plan(plan, source_model)

        action = plan["actions"][0]
        self.assertEqual(action["section_id"], "catalog_primary_columns_w_w10x33")
        self.assertEqual(action["width"], 0.21)
        self.assertEqual(action["depth"], 0.264)
        self.assertEqual(summary["applied_count"], 1)
        self.assertEqual(summary["section_counts"]["W10X33"], 1)
        self.assertEqual(plan["metadata"]["sizing_roundtrip_summary"]["applied_count"], 1)

    def test_applies_resolved_sections_to_authored_plan_and_semantic_model(self) -> None:
        authored_plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Authored frame",
            "assumptions": [],
            "actions": [
                {
                    "type": "create_beam",
                    "name": "Beam A",
                    "storey": "Level 0",
                    "x1": 0.0,
                    "y1": 0.0,
                    "x2": 6.0,
                    "y2": 0.0,
                    "base_z": 4.0,
                    "width": 0.2,
                    "depth": 0.3,
                    "semantics": {"element_id": "beam_a"},
                }
            ],
        }
        physical_model = PhysicalModelSpec(
            summary="Sized frame",
            assumptions=[],
            plan={
                "version": "1.0",
                "units": "meters",
                "summary": "Sized frame",
                "assumptions": [],
                "actions": [
                    {
                        "type": "create_beam",
                        "name": "Beam A",
                        "storey": "Level 0",
                        "x1": 0.0,
                        "y1": 0.0,
                        "x2": 6.0,
                        "y2": 0.0,
                        "base_z": 4.0,
                        "width": 0.2,
                        "depth": 0.3,
                        "semantics": {"element_id": "beam_a"},
                    }
                ],
            },
            authored_plan=authored_plan,
            semantic_model={
                "version": "1.0",
                "units": "meters",
                "summary": "Sized frame",
                "assumptions": [],
                "assemblies": [],
                "roots": [],
                "metadata": {},
                "elements": [
                    {
                        "id": "beam_a",
                        "type": "create_beam",
                        "name": "Beam A",
                        "storey": "Level 0",
                        "parent_id": None,
                        "assembly_id": None,
                        "branch_path": ["Level 0", "Structure"],
                        "selector_tags": [],
                        "action": {
                            "type": "create_beam",
                            "name": "Beam A",
                            "storey": "Level 0",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 6.0,
                            "y2": 0.0,
                            "base_z": 4.0,
                            "width": 0.2,
                            "depth": 0.3,
                            "semantics": {"element_id": "beam_a"},
                        },
                    }
                ],
            },
        )
        source_model = StructuralSourceModel(
            materials=[MaterialSpec(id="steel_w_shapes", family="steel", model="elastic_isotropic")],
            sections=[
                SectionSpec(
                    id="catalog_primary_beams_w_w12x40",
                    kind="catalog_profile",
                    material_id="steel_w_shapes",
                    dimensions={"width": 0.205, "depth": 0.310},
                    metadata={"catalog_section_name": "W12X40"},
                )
            ],
            elements=[
                StructuralSourceElement(
                    id="beam_a",
                    kind="beam",
                    role="floor_beam",
                    section_id="catalog_primary_beams_w_w12x40",
                    metadata={"source_name": "Beam A"},
                )
            ],
        )

        summary = apply_sized_sections_to_physical_model(physical_model, source_model)

        self.assertEqual(physical_model.plan["actions"][0]["section_id"], "catalog_primary_beams_w_w12x40")
        self.assertEqual(physical_model.authored_plan["actions"][0]["depth"], 0.31)
        self.assertEqual(physical_model.semantic_model["elements"][0]["action"]["width"], 0.205)
        self.assertEqual(physical_model.semantic_model["elements"][0]["section_id"], "catalog_primary_beams_w_w12x40")
        self.assertEqual(summary["semantic_model"]["section_counts"]["W12X40"], 1)

    def test_roundtrips_footing_basis_metadata(self) -> None:
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Foundation plan",
            "assumptions": [],
            "actions": [
                {
                    "type": "create_footing",
                    "name": "Footing A",
                    "storey": "Foundations",
                    "x": 0.0,
                    "y": 0.0,
                    "base_z": -1.2,
                    "length": 2.4,
                    "width": 2.4,
                    "thickness": 0.75,
                    "semantics": {"element_id": "footing_a"},
                }
            ],
        }
        source_model = StructuralSourceModel(
            materials=[MaterialSpec(id="concrete_default", family="concrete", model="elastic_isotropic")],
            sections=[
                SectionSpec(
                    id="footing_0.7500",
                    kind="plate",
                    material_id="concrete_default",
                    dimensions={"thickness": 0.75},
                )
            ],
            elements=[
                StructuralSourceElement(
                    id="footing_a",
                    kind="foundation",
                    role="foundation",
                    section_id="footing_0.7500",
                    metadata={
                        "support_for": "column_a",
                        "load_combo": "1.2D+1.6L",
                        "imposed_load_kN": 680.0,
                        "service_reaction_kN": 520.0,
                        "rebar_weight_kg": 145.5,
                        "rebar_schedule": ["T16@200 EW BOT"],
                    },
                )
            ],
        )

        apply_sized_sections_to_plan(plan, source_model)

        foundation = plan["actions"][0]["foundation"]
        self.assertEqual(foundation["support_for"], "column_a")
        self.assertEqual(foundation["load_combo"], "1.2D+1.6L")
        self.assertEqual(foundation["imposed_load_kN"], 680.0)
        self.assertEqual(foundation["rebar_schedule"], ["T16@200 EW BOT"])


if __name__ == "__main__":
    unittest.main()
