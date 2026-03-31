import unittest

from bonsai_ai_core.semantic_model import build_semantic_model


class SemanticModelTests(unittest.TestCase):
    def test_builds_stable_element_ids_and_applies_edits(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Semantic model test",
            "assumptions": [],
            "actions": [
                {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                {
                    "type": "create_wall",
                    "name": "North Wall",
                    "storey": "Level 0",
                    "x1": 0.0,
                    "y1": 0.0,
                    "x2": 10.0,
                    "y2": 0.0,
                    "base_z": 0.0,
                    "height": 4.0,
                    "thickness": 0.2,
                    "semantics": {
                        "element_id": "north_wall",
                        "group_path": ["Envelope", "North"],
                        "selector_tags": ["perimeter"],
                    },
                },
                {
                    "type": "update_element",
                    "name": "Retag North Wall",
                    "target_id": "north_wall",
                    "patch": {"presentation": {"material_key": "accent"}},
                },
                {
                    "type": "move_element",
                    "name": "Lift North Wall",
                    "target_selector_tags": ["perimeter"],
                    "dz": 0.25,
                },
            ],
        }

        model = build_semantic_model(plan)

        self.assertEqual(len(model["elements"]), 2)
        wall = next(element for element in model["elements"] if element["id"] == "north_wall")
        self.assertEqual(wall["action"]["presentation"]["material_key"], "accent")
        self.assertEqual(wall["action"]["base_z"], 0.25)
        self.assertEqual(wall["branch_path"], ["Level 0", "Envelope", "North"])
        self.assertEqual(model["metadata"]["action_type_counts"]["create_wall"], 1)
        self.assertEqual(model["metadata"]["storey_counts"]["Level 0"], 1)
        assembly_names = {node["name"]: node for node in model["assemblies"]}
        self.assertIn("Level 0", assembly_names)
        self.assertIn("Envelope", assembly_names)
        self.assertIn("North", assembly_names)
        self.assertEqual(assembly_names["North"]["element_ids"], ["north_wall"])
        self.assertTrue(model["roots"])

    def test_includes_explicit_parent_and_assembly_nodes(self):
        plan = {
            "version": "1.0",
            "units": "meters",
            "summary": "Assembly model test",
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
                        "group_path": ["Structure", "Frame A"],
                        "parent_id": "frame_line_a",
                        "assembly_id": "primary_frame_a",
                    },
                },
            ],
        }

        model = build_semantic_model(plan)

        assembly_ids = {node["id"]: node for node in model["assemblies"]}
        self.assertIn("assembly:frame_line_a", assembly_ids)
        self.assertIn("assembly:primary_frame_a", assembly_ids)
        self.assertEqual(assembly_ids["assembly:primary_frame_a"]["element_ids"], ["column_a"])


if __name__ == "__main__":
    unittest.main()
