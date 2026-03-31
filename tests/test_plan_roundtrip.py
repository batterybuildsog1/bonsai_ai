from __future__ import annotations

import unittest

from bonsai_ai.contracts import MaterialSpec, SectionSpec, StructuralSourceElement, StructuralSourceModel
from bonsai_ai.plan_roundtrip import apply_sized_sections_to_plan


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


if __name__ == "__main__":
    unittest.main()
