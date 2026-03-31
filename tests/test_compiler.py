import unittest

from bonsai_ai_core.compiler import compile_plan


class CompilePlanTests(unittest.TestCase):
    def test_compiles_stair_and_connection_semantics(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Semantic plan",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_stair_run",
                    "name": "Main Stair",
                    "storey": "Level 0",
                    "x": 10.0,
                    "y": 5.0,
                    "base_z": 0.0,
                    "width": 1.2,
                    "tread_depth": 0.3,
                    "riser_height": 0.18,
                    "step_count": 3,
                    "thickness": 0.08,
                    "direction_deg": 90.0,
                },
                {
                    "type": "create_stair_landing",
                    "name": "Main Stair Landing",
                    "storey": "Level 0",
                    "x": 9.7,
                    "y": 5.9,
                    "base_z": 0.54,
                    "width": 1.2,
                    "depth": 1.2,
                    "thickness": 0.08,
                    "direction_deg": 90.0,
                },
                {
                    "type": "create_connection_plate",
                    "name": "Plate A",
                    "storey": "Level 0",
                    "center_x": 4.0,
                    "center_y": 6.0,
                    "base_z": 3.9,
                    "width": 0.4,
                    "depth": 0.2,
                    "thickness": 0.02,
                    "rotation_deg": 90.0,
                },
            ],
        }

        compiled = compile_plan(plan)

        self.assertEqual(compiled["actions"][0]["type"], "ensure_storey")
        tread_actions = [action for action in compiled["actions"] if action["name"].startswith("Main Stair Tread")]
        self.assertEqual(len(tread_actions), 3)
        self.assertEqual(tread_actions[0]["rotation_deg"], 90.0)
        self.assertEqual(tread_actions[1]["y"], 5.3)
        landing = next(action for action in compiled["actions"] if action["name"] == "Main Stair Landing")
        self.assertEqual(landing["type"], "create_rect_slab")
        plate = next(action for action in compiled["actions"] if action["name"] == "Plate A")
        self.assertEqual(plate["type"], "create_panel")
        self.assertAlmostEqual(plate["x"], 4.1)
        self.assertAlmostEqual(plate["y"], 5.8)
        self.assertEqual(plate["orientation"], "horizontal")
        self.assertAlmostEqual(plate["depth"], 0.2)
        self.assertEqual(plate["rotation_deg"], 90.0)

    def test_preserves_plain_plate_like_slabs_without_heuristics(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Plain slab preservation",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_rect_slab",
                    "name": "Connection Plate East",
                    "storey": "Level 0",
                    "x": 1.0,
                    "y": 2.0,
                    "z": 3.9,
                    "width": 0.35,
                    "depth": 0.35,
                    "thickness": 0.02,
                    "rotation_deg": 45.0,
                },
            ],
        }

        compiled = compile_plan(plan)
        plate = next(action for action in compiled["actions"] if action["name"] == "Connection Plate East")
        self.assertEqual(plate["type"], "create_rect_slab")
        self.assertEqual(plate["z"], 3.9)

    def test_compile_plan_applies_semantic_edit_actions(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Semantic edits",
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
                    "semantics": {"element_id": "col_a", "group_path": ["Structure", "Primary"]},
                },
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
                    "depth": 0.4,
                    "semantics": {"element_id": "beam_a", "group_path": ["Structure", "Primary"]},
                },
                {
                    "type": "move_element",
                    "name": "Move Column",
                    "target_id": "col_a",
                    "dx": 1.5,
                    "dz": 0.5,
                },
                {
                    "type": "replace_section",
                    "name": "Resize Beam",
                    "target_name": "Beam A",
                    "width": 0.35,
                    "depth": 0.6,
                },
                {
                    "type": "rebuild_branch",
                    "name": "Rebuild Primary Structure",
                    "target_path": ["Structure", "Primary"],
                    "replacement_actions": [
                        {
                            "type": "create_column",
                            "name": "Column B",
                            "x": 2.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.4,
                            "depth": 0.4,
                            "height": 4.5,
                            "semantics": {"element_id": "col_b"},
                        }
                    ],
                },
            ],
        }

        compiled = compile_plan(plan)

        created_names = [action["name"] for action in compiled["actions"]]
        self.assertEqual(created_names, ["Level 0", "Column B"])
        column = compiled["actions"][1]
        self.assertEqual(column["storey"], "Level 0")
        self.assertEqual(column["semantics"]["element_id"], "col_b")
        self.assertEqual(column["semantics"]["group_path"], ["Structure", "Primary"])

    def test_compile_plan_adds_semantic_identity_to_compiled_children(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Stair ids",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_stair_run",
                    "name": "Main Stair",
                    "storey": "Level 0",
                    "x": 0.0,
                    "y": 0.0,
                    "base_z": 0.0,
                    "width": 1.2,
                    "tread_depth": 0.3,
                    "riser_height": 0.17,
                    "step_count": 2,
                    "thickness": 0.08,
                    "semantics": {"element_id": "main_stair", "group_path": ["Circulation"]},
                },
            ],
        }

        compiled = compile_plan(plan)
        tread_actions = [action for action in compiled["actions"] if action["type"] == "create_rect_slab"]
        self.assertEqual(tread_actions[0]["semantics"]["element_id"], "main_stair__tread_01")
        self.assertEqual(tread_actions[0]["semantics"]["parent_id"], "main_stair")
        self.assertEqual(tread_actions[0]["semantics"]["assembly_id"], "main_stair")
        self.assertEqual(tread_actions[0]["semantics"]["group_path"], ["Circulation", "Treads"])

    def test_compiles_semantic_edit_sequence_to_final_branch_state(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Semantic edit sequence",
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
                {
                    "type": "update_element",
                    "name": "Update Column A",
                    "target_id": "column_a",
                    "patch": {"presentation": {"material_key": "steel_dark"}},
                },
                {"type": "move_element", "name": "Shift Column A", "target_id": "column_a", "dx": 1.5, "dz": 0.25},
                {"type": "replace_section", "name": "Resize Column A", "target_id": "column_a", "width": 0.45, "depth": 0.55},
                {
                    "type": "rebuild_branch",
                    "name": "Rebuild Column Branch",
                    "target_path": ["Structure", "Columns"],
                    "replacement_actions": [
                        {
                            "type": "create_column",
                            "name": "Column B",
                            "storey": "Level 0",
                            "x": 2.0,
                            "y": 3.0,
                            "base_z": 0.0,
                            "width": 0.5,
                            "depth": 0.6,
                            "height": 5.0,
                            "semantics": {"group_path": ["Structure", "Columns"]},
                        }
                    ],
                },
            ],
        }

        compiled = compile_plan(plan)

        columns = [action for action in compiled["actions"] if action["type"] == "create_column"]
        self.assertEqual(len(columns), 1)
        self.assertEqual(columns[0]["name"], "Column B")
        self.assertEqual(columns[0]["width"], 0.5)
        self.assertEqual(columns[0]["depth"], 0.6)
        self.assertEqual(columns[0]["semantics"]["group_path"], ["Structure", "Columns"])


if __name__ == "__main__":
    unittest.main()
