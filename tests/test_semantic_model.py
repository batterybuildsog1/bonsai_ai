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


if __name__ == "__main__":
    unittest.main()
