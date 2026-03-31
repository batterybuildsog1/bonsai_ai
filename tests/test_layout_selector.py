from __future__ import annotations

import unittest

from bonsai_ai.catalog_selector import apply_catalog_selection
from bonsai_ai.contracts import AnalysisDomain, DesignBrief, DesignPackage, PhysicalModelSpec
from bonsai_ai.structural_source import StructuralSourceModelBuilder
from bonsai_ai.system_catalog import starter_core_shell_catalog
from bonsai_ai.system_layout import build_system_layout


class LayoutSelectorTests(unittest.TestCase):
    def test_layout_and_catalog_selection_capture_parent_groups(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="layout selector", analysis_domains=[AnalysisDomain.WIND]),
            physical_model=PhysicalModelSpec(
                summary="summary",
                assumptions=[],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {
                            "type": "create_column",
                            "name": "corner_frame_column X000_Y000_Seg1",
                            "storey": "Level 1",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.5,
                            "depth": 0.5,
                            "height": 5.0,
                        },
                        {
                            "type": "create_beam",
                            "name": "West Collector Bay 0.00-24.00",
                            "storey": "Level 1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 0.0,
                            "y2": 5.0,
                            "base_z": 5.0,
                            "width": 0.3,
                            "depth": 0.5,
                            "member_role": "drag_collector",
                        },
                        {
                            "type": "create_beam",
                            "name": "West Brace Bay 0.00-24.00 A",
                            "storey": "Level 1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 0.0,
                            "y2": 5.0,
                            "base_z": 0.0,
                            "end_z": 5.0,
                            "width": 0.2,
                            "depth": 0.2,
                            "member_role": "brace",
                        },
                        {
                            "type": "create_wall",
                            "name": "Main Tier South Panel 01",
                            "storey": "Level 1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 0.0,
                            "height": 5.0,
                            "thickness": 0.2,
                        },
                        {
                            "type": "create_column",
                            "name": "Main Tier South Panel 01 Window Left Jamb",
                            "storey": "Level 1",
                            "x": 1.0,
                            "y": 0.0,
                            "base_z": 1.0,
                            "width": 0.2,
                            "depth": 0.2,
                            "height": 2.0,
                        },
                    ],
                },
            ),
        )

        source_model = StructuralSourceModelBuilder().build(package)
        selection_summary = apply_catalog_selection(source_model, starter_core_shell_catalog())
        layout = build_system_layout(source_model)

        self.assertIn("primary_columns_w", selection_summary["selected_family_counts"])
        self.assertIn("brace_hss", selection_summary["selected_family_counts"])
        self.assertEqual(selection_summary["unmatched_roles"], {"envelope": 1})
        self.assertIn("brace_hss|brace|brace_bay:west_brace_bay_0_00_24_00", selection_summary["sizing_group_counts"])
        element_index = {item["element_id"]: item for item in selection_summary["per_element"]}
        self.assertEqual(element_index["corner_frame_column_x000_y000_seg1"]["catalog_family_id"], "primary_columns_w")
        self.assertEqual(element_index["corner_frame_column_x000_y000_seg1"]["preferred_section_id"], "W10x33")
        self.assertEqual(element_index["west_brace_bay_0_00_24_00_a"]["sizing_group_id"], "brace_hss|brace|brace_bay:west_brace_bay_0_00_24_00")
        self.assertEqual(element_index["main_tier_south_panel_01"]["selection_status"], "unsupported")
        self.assertEqual(layout["summary"]["frame_line_count"], 1)
        self.assertEqual(layout["summary"]["brace_bay_count"], 1)
        self.assertEqual(layout["summary"]["collector_line_count"], 1)
        self.assertEqual(layout["summary"]["facade_zone_count"], 1)
        self.assertEqual(layout["summary"]["opening_zone_count"], 1)
        self.assertGreaterEqual(layout["summary"]["system_count"], 3)
        self.assertEqual(layout["frame_lines"][0]["kind"], "frame_line")
        self.assertEqual(layout["opening_zones"][0]["kind"], "opening_zone")
        system_ids = {system["id"] for system in layout["systems"]}
        self.assertIn("primary_frame_system", system_ids)
        self.assertIn("panel_system", system_ids)


if __name__ == "__main__":
    unittest.main()
