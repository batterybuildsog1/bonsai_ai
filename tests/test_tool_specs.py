from __future__ import annotations

import unittest

from bonsai_ai.tool_specs import TOOL_SPECS, as_openai_tools


class ToolSpecTests(unittest.TestCase):
    def test_all_schemas_are_strict_objects(self) -> None:
        for spec in TOOL_SPECS:
            self.assertEqual(spec.schema["type"], "object")
            self.assertFalse(spec.schema["additionalProperties"])
            self.assertTrue(set(spec.schema["required"]).issubset(set(spec.schema["properties"].keys())))

        window_spec = next(spec for spec in TOOL_SPECS if spec.name == "create_window")
        self.assertIn("presentation", window_spec.schema["properties"])
        self.assertIn("glass_material_key", window_spec.schema["properties"]["presentation"]["properties"])
        self.assertNotIn("presentation", window_spec.schema["required"])

        footing_spec = next(spec for spec in TOOL_SPECS if spec.name == "create_footing")
        self.assertIn("foundation", footing_spec.schema["properties"])
        self.assertIn("rebar_weight_kg", footing_spec.schema["properties"]["foundation"]["properties"])
        self.assertNotIn("foundation", footing_spec.schema["required"])

    def test_openai_tools_mark_strict(self) -> None:
        for tool in as_openai_tools():
            self.assertTrue(tool["function"]["strict"])


if __name__ == "__main__":
    unittest.main()
