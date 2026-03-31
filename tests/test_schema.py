import unittest

from bonsai_ai_core.schema import validate_plan


class ValidatePlanTests(unittest.TestCase):
    def test_valid_plan_passes(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Simple office shell",
            "assumptions": ["No doors or windows yet."],
            "actions": [
                {"type": "ensure_storey", "name": "Level 1", "elevation": 0},
                {
                    "type": "create_wall",
                    "name": "North Wall",
                    "storey": "Level 1",
                    "x1": 0,
                    "y1": 0,
                    "x2": 10,
                    "y2": 0,
                    "base_z": 0,
                    "height": 4,
                    "thickness": 0.2,
                },
            ],
        }
        validated = validate_plan(plan)
        self.assertEqual(validated["actions"][0]["name"], "Level 1")

    def test_invalid_top_z_fails(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Bad facade",
            "assumptions": [],
            "actions": [
                {
                    "type": "create_curtain_wall",
                    "name": "South Curtain Wall",
                    "x1": 0,
                    "y1": 0,
                    "x2": 10,
                    "y2": 0,
                    "base_z": 4,
                    "top_z": 3,
                    "panel_width": 1.5,
                    "panel_height": 3,
                    "thickness": 0.08,
                }
            ],
        }
        with self.assertRaises(Exception):
            validate_plan(plan)

    def test_numeric_string_and_new_primitives_are_normalized(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Steel and panel test",
            "assumptions": [],
            "actions": [
                {
                    "type": "create_beam",
                    "name": "Beam A",
                    "storey": "Level 1",
                    "x1": "0",
                    "y1": "0",
                    "x2": "6.0",
                    "y2": "0",
                    "base_z": "3.5",
                    "width": "0.3",
                    "depth": "0.5",
                },
                {
                    "type": "create_panel",
                    "name": "Panel A",
                    "storey": "Level 1",
                    "x": "2.0",
                    "y": "0.0",
                    "base_z": "0.0",
                    "width": "1.2",
                    "height": "3.0",
                    "thickness": "0.08",
                },
            ],
        }
        validated = validate_plan(plan)
        self.assertEqual(validated["actions"][0]["base_z"], 3.5)
        self.assertEqual(validated["actions"][1]["thickness"], 0.08)

    def test_common_alias_fields_are_normalized(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Alias normalization test",
            "assumptions": [],
            "actions": [
                {
                    "type": "create_column",
                    "name": "Column A",
                    "x": 0,
                    "y": 0,
                    "z": "0",
                    "width": 0.3,
                    "depth": 0.3,
                    "height": 4.0,
                },
                {
                    "type": "create_rect_slab",
                    "name": "Plate A",
                    "x": 0,
                    "y": 0,
                    "width": 0.35,
                    "depth": 0.35,
                    "thickness": 0.02,
                    "elevation": "3.9",
                },
            ],
        }
        validated = validate_plan(plan)
        self.assertEqual(validated["actions"][0]["base_z"], 0)
        self.assertEqual(validated["actions"][1]["z"], 3.9)

    def test_semantic_stair_and_connection_actions_validate(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Semantic authored plan",
            "assumptions": [],
            "actions": [
                {
                    "type": "create_stair_run",
                    "name": "Stair Run A",
                    "storey": "Level 0",
                    "x": 0,
                    "y": 0,
                    "base_z": 0,
                    "width": 1.2,
                    "tread_depth": 0.28,
                    "riser_height": 0.175,
                    "step_count": 10,
                    "thickness": 0.08,
                    "direction_deg": 90,
                },
                {
                    "type": "create_connection_plate",
                    "name": "Plate A",
                    "storey": "Level 0",
                    "center_x": 3.0,
                    "center_y": 4.0,
                    "base_z": 3.9,
                    "width": 0.35,
                    "depth": 0.35,
                    "thickness": 0.02,
                },
            ],
        }
        validated = validate_plan(plan)
        self.assertEqual(validated["actions"][0]["step_count"], 10)
        self.assertEqual(validated["actions"][1]["center_x"], 3.0)

    def test_connection_plate_center_aliases_accept_x_and_y(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Connection plate aliases",
            "assumptions": [],
            "actions": [
                {
                    "type": "create_connection_plate",
                    "name": "Plate A",
                    "storey": "Level 0",
                    "x": "3.0",
                    "y": "4.0",
                    "base_z": "3.9",
                    "width": "0.35",
                    "depth": "0.35",
                    "thickness": "0.02",
                }
            ],
        }
        validated = validate_plan(plan)
        self.assertEqual(validated["actions"][0]["center_x"], 3)
        self.assertEqual(validated["actions"][0]["center_y"], 4)

    def test_semantic_edit_actions_validate(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Semantic edit plan",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_column",
                    "name": "Column A",
                    "storey": "Level 0",
                    "x": 0.0,
                    "y": 0.0,
                    "base_z": 0.0,
                    "width": 0.3,
                    "depth": 0.3,
                    "height": 4.0,
                    "semantics": {
                        "element_id": "column_a",
                        "group_path": ["Structure", "Columns"],
                        "selector_tags": ["primary"],
                    },
                },
                {"type": "update_element", "name": "Update Column A", "target_id": "column_a", "patch": {"notes": "Updated"}},
                {"type": "move_element", "name": "Move Column A", "target_name": "Column A", "dx": 1.0, "dz": 0.2},
                {"type": "replace_section", "name": "Resize Column A", "target_path": ["Structure", "Columns"], "width": 0.4, "depth": 0.5},
                {"type": "delete_element", "name": "Delete Primary Columns", "target_selector_tags": ["primary"]},
                {
                    "type": "rebuild_branch",
                    "name": "Rebuild Primary Columns",
                    "target_path": ["Structure", "Columns"],
                    "replacement_actions": [
                        {
                            "type": "create_column",
                            "name": "Column B",
                            "storey": "Level 0",
                            "x": 1.0,
                            "y": 2.0,
                            "base_z": 0.0,
                            "width": 0.35,
                            "depth": 0.35,
                            "height": 4.0,
                        }
                    ],
                },
            ],
        }
        validated = validate_plan(plan)
        self.assertEqual(validated["actions"][2]["patch"]["notes"], "Updated")
        self.assertEqual(validated["actions"][3]["dx"], 1.0)


if __name__ == "__main__":
    unittest.main()
