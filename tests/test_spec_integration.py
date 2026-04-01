"""Tests for the spec-first integration: schema, validator, planner defaults, and CLI.

Runs in two tiers:
  - Tier 1 (always): building_spec_schema + spec_validator (pure logic, no provider deps)
  - Tier 2 (when full env available): spec_planner defaults, CLI args, system prompt
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure the source directory is on the path
ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Check if the full provider chain is importable
_HAS_FULL_ENV = False
try:
    from bonsai_ai.spec_planner import _fill_defaults, _adjust_spacing, SPEC_SYSTEM_PROMPT
    from bonsai_ai.cli import build_parser
    _HAS_FULL_ENV = True
except (ImportError, ModuleNotFoundError):
    pass


# ---------------------------------------------------------------------------
# Test data: simple, medium, hard building prompts
# ---------------------------------------------------------------------------

SIMPLE_SPEC = {
    "footprint": {"length": 20, "width": 15},
    "stories": [
        {"name": "Level 1", "height": 4.0}
    ],
}

MEDIUM_SPEC = {
    "project_name": "5-Story Office Tower",
    "footprint": {"length": 40, "width": 25},
    "grid": {"spacing_x": 8, "spacing_y": 6.25},
    "stories": [
        {"name": "Ground Floor", "height": 4.5, "program": "retail"},
        {"name": "Level 2", "height": 4.0, "program": "office"},
        {"name": "Level 3", "height": 4.0, "program": "office"},
        {"name": "Level 4", "height": 4.0, "program": "office"},
        {"name": "Level 5", "height": 4.0, "program": "office"},
    ],
    "structure": {"frame_type": "braced"},
    "facades": {
        "north": {"type": "wall", "windows": {"pattern": "per_bay", "width": 1.8, "height": 1.5}},
        "south": {"type": "curtain_wall"},
        "east": {"type": "wall", "windows": {"pattern": "per_bay", "width": 1.8, "height": 1.5}},
        "west": {"type": "wall", "windows": {"pattern": "per_bay", "width": 1.8, "height": 1.5}},
    },
    "entries": [
        {"face": "south", "type": "double", "position": "center"}
    ],
}

HARD_SPEC = {
    "project_name": "Warehouse with Mezzanine",
    "footprint": {"length": 60, "width": 40},
    "grid": {"spacing_x": 10, "spacing_y": 10},
    "stories": [
        {"name": "Warehouse Floor", "height": 8.0, "program": "industrial"}
    ],
    "structure": {"frame_type": "rigid", "roof_type": "standing_seam"},
    "facades": {
        "north": {"type": "wall"},
        "south": {"type": "wall"},
        "east": {"type": "wall"},
        "west": {"type": "wall"},
    },
    "entries": [
        {"face": "south", "type": "single", "position": "left_third"}
    ],
    "mezzanines": [
        {"story_index": 0, "sides": ["south"], "depth": 12, "height_fraction": 0.45}
    ],
}


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestBuildingSpecSchema(unittest.TestCase):
    def test_schema_has_required_fields(self):
        from bonsai_ai.building_spec_schema import BUILDING_SPEC_SCHEMA
        self.assertEqual(BUILDING_SPEC_SCHEMA["type"], "object")
        self.assertIn("footprint", BUILDING_SPEC_SCHEMA["required"])
        self.assertIn("stories", BUILDING_SPEC_SCHEMA["required"])

    def test_schema_has_optional_sections(self):
        from bonsai_ai.building_spec_schema import BUILDING_SPEC_SCHEMA
        props = BUILDING_SPEC_SCHEMA["properties"]
        for key in ["grid", "structure", "facades", "entries", "mezzanines", "roof", "foundation"]:
            self.assertIn(key, props, f"Missing optional section: {key}")

    def test_building_spec_schema_returns_copy(self):
        from bonsai_ai.building_spec_schema import building_spec_schema
        schema1 = building_spec_schema()
        schema2 = building_spec_schema()
        self.assertEqual(schema1, schema2)
        # Mutating one should not affect the other
        schema1["properties"]["footprint"]["extra"] = True
        self.assertNotIn("extra", schema2["properties"]["footprint"])

    def test_footprint_requires_length_and_width(self):
        from bonsai_ai.building_spec_schema import BUILDING_SPEC_SCHEMA
        fp_props = BUILDING_SPEC_SCHEMA["properties"]["footprint"]["properties"]
        self.assertIn("length", fp_props)
        self.assertIn("width", fp_props)

    def test_stories_items_require_height(self):
        from bonsai_ai.building_spec_schema import BUILDING_SPEC_SCHEMA
        story_item = BUILDING_SPEC_SCHEMA["properties"]["stories"]["items"]
        self.assertIn("height", story_item["required"])


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestSpecValidator(unittest.TestCase):
    def test_valid_simple_spec(self):
        from bonsai_ai.spec_validator import validate_spec
        issues = validate_spec(SIMPLE_SPEC)
        self.assertEqual(issues, [])

    def test_valid_medium_spec(self):
        from bonsai_ai.spec_validator import validate_spec
        issues = validate_spec(MEDIUM_SPEC)
        self.assertEqual(issues, [])

    def test_valid_hard_spec(self):
        from bonsai_ai.spec_validator import validate_spec
        issues = validate_spec(HARD_SPEC)
        self.assertEqual(issues, [])

    def test_missing_footprint(self):
        from bonsai_ai.spec_validator import validate_spec
        issues = validate_spec({"stories": [{"height": 4.0}]})
        self.assertTrue(any("footprint" in i for i in issues))

    def test_missing_stories(self):
        from bonsai_ai.spec_validator import validate_spec
        issues = validate_spec({"footprint": {"length": 20, "width": 15}})
        self.assertTrue(any("stories" in i for i in issues))

    def test_footprint_too_small(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {"footprint": {"length": 1, "width": 15}, "stories": [{"height": 4}]}
        issues = validate_spec(spec)
        self.assertTrue(any("too small" in i for i in issues))

    def test_footprint_too_large(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {"footprint": {"length": 600, "width": 15}, "stories": [{"height": 4}]}
        issues = validate_spec(spec)
        self.assertTrue(any("unusually large" in i for i in issues))

    def test_story_too_short(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {"footprint": {"length": 20, "width": 15}, "stories": [{"height": 1.0}]}
        issues = validate_spec(spec)
        self.assertTrue(any("too short" in i for i in issues))

    def test_story_too_tall(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {"footprint": {"length": 20, "width": 15}, "stories": [{"height": 25.0}]}
        issues = validate_spec(spec)
        self.assertTrue(any("unusually tall" in i for i in issues))

    def test_grid_not_dividing_evenly(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 25, "width": 15},
            "grid": {"spacing_x": 7},
            "stories": [{"height": 4}],
        }
        issues = validate_spec(spec)
        self.assertTrue(any("does not divide evenly" in i for i in issues))

    def test_grid_divides_evenly(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 40, "width": 25},
            "grid": {"spacing_x": 8, "spacing_y": 6.25},
            "stories": [{"height": 4}],
        }
        issues = validate_spec(spec)
        self.assertEqual(issues, [])

    def test_invalid_program(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [{"height": 4, "program": "swimming_pool"}],
        }
        issues = validate_spec(spec)
        self.assertTrue(any("swimming_pool" in i for i in issues))

    def test_invalid_facade_type(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [{"height": 4}],
            "facades": {"north": {"type": "glass_curtain"}},
        }
        issues = validate_spec(spec)
        self.assertTrue(any("glass_curtain" in i for i in issues))

    def test_entry_out_of_range_story_index(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [{"height": 4}],
            "entries": [{"face": "south", "story_index": 5}],
        }
        issues = validate_spec(spec)
        self.assertTrue(any("out of range" in i for i in issues))

    def test_mezzanine_out_of_range(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [{"height": 4}],
            "mezzanines": [{"story_index": 3}],
        }
        issues = validate_spec(spec)
        self.assertTrue(any("out of range" in i for i in issues))

    def test_mezzanine_depth_exceeds_width(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [{"height": 4}],
            "mezzanines": [{"story_index": 0, "depth": 20}],
        }
        issues = validate_spec(spec)
        self.assertTrue(any("exceeds building width" in i for i in issues))

    def test_elevation_inconsistency(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [
                {"height": 4, "elevation": 0},
                {"height": 4, "elevation": 5},  # should be 4, not 5
            ],
        }
        issues = validate_spec(spec)
        self.assertTrue(any("does not match cumulative" in i for i in issues))

    def test_valid_elevations_pass(self):
        from bonsai_ai.spec_validator import validate_spec
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [
                {"height": 4, "elevation": 0},
                {"height": 4, "elevation": 4},
            ],
        }
        issues = validate_spec(spec)
        self.assertEqual(issues, [])


# ---------------------------------------------------------------------------
# Planner defaults tests
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAS_FULL_ENV, "Full provider env not available")
class TestSpecPlannerDefaults(unittest.TestCase):
    def test_fill_defaults_auto_calculates_elevations(self):
        from bonsai_ai.spec_planner import _fill_defaults
        spec = {
            "footprint": {"length": 40, "width": 25},
            "stories": [
                {"height": 4.5},
                {"height": 4.0},
                {"height": 4.0},
            ],
        }
        result = _fill_defaults(spec)
        self.assertEqual(result["stories"][0]["elevation"], 0.0)
        self.assertEqual(result["stories"][1]["elevation"], 4.5)
        self.assertEqual(result["stories"][2]["elevation"], 8.5)

    def test_fill_defaults_auto_names_stories(self):
        from bonsai_ai.spec_planner import _fill_defaults
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [{"height": 4}, {"height": 4}],
        }
        result = _fill_defaults(spec)
        self.assertEqual(result["stories"][0]["name"], "Level 1")
        self.assertEqual(result["stories"][1]["name"], "Level 2")

    def test_fill_defaults_preserves_existing_names(self):
        from bonsai_ai.spec_planner import _fill_defaults
        spec = {
            "footprint": {"length": 20, "width": 15},
            "stories": [{"height": 4, "name": "Ground Floor"}],
        }
        result = _fill_defaults(spec)
        self.assertEqual(result["stories"][0]["name"], "Ground Floor")

    def test_fill_defaults_adjusts_grid_spacing(self):
        from bonsai_ai.spec_planner import _fill_defaults
        spec = {
            "footprint": {"length": 25, "width": 15},
            "grid": {"spacing_x": 7},
            "stories": [{"height": 4}],
        }
        result = _fill_defaults(spec)
        # 25 / 7 ~ 3.57 -> rounds to 4 bays -> spacing = 6.25
        # Or rounds to 3 bays -> spacing = 8.333
        spacing = result["grid"]["spacing_x"]
        bays = 25.0 / spacing
        # Must divide evenly
        self.assertAlmostEqual(bays, round(bays), places=4)

    def test_adjust_spacing_even_division(self):
        from bonsai_ai.spec_planner import _adjust_spacing
        # 40m with target 8m -> exactly 5 bays -> stays at 8
        self.assertAlmostEqual(_adjust_spacing(40, 8), 8.0, places=4)
        # 25m with target 8m -> round(3.125) = 3 bays -> 25/3 = 8.333...
        result = _adjust_spacing(25, 8)
        self.assertAlmostEqual(25.0 / result, round(25.0 / result), places=4)
        # 25m with target 6.25 -> round(4) = 4 bays -> 6.25
        self.assertAlmostEqual(_adjust_spacing(25, 6.25), 6.25, places=4)

    def test_fill_defaults_adds_grid_when_missing(self):
        from bonsai_ai.spec_planner import _fill_defaults
        spec = {
            "footprint": {"length": 40, "width": 25},
            "stories": [{"height": 4}],
        }
        result = _fill_defaults(spec)
        self.assertIn("grid", result)
        self.assertIn("spacing_x", result["grid"])
        self.assertIn("spacing_y", result["grid"])


# ---------------------------------------------------------------------------
# CLI argument tests
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAS_FULL_ENV, "Full provider env not available")
class TestCLISpecFirst(unittest.TestCase):
    def test_parser_accepts_spec_first_flag(self):
        from bonsai_ai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--spec-first",
            "--provider", "openai",
            "--output", "test.ifc",
            "--prompt", "Build a simple box",
        ])
        self.assertTrue(args.spec_first)

    def test_parser_default_no_spec_first(self):
        from bonsai_ai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--output", "test.ifc",
            "--prompt", "Build a simple box",
        ])
        self.assertFalse(args.spec_first)


# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAS_FULL_ENV, "Full provider env not available")
class TestSpecSystemPrompt(unittest.TestCase):
    def test_prompt_under_300_words(self):
        from bonsai_ai.spec_planner import SPEC_SYSTEM_PROMPT
        word_count = len(SPEC_SYSTEM_PROMPT.split())
        self.assertLessEqual(word_count, 300,
            f"SPEC_SYSTEM_PROMPT is {word_count} words, must be <= 300")

    def test_prompt_mentions_required_fields(self):
        from bonsai_ai.spec_planner import SPEC_SYSTEM_PROMPT
        self.assertIn("footprint", SPEC_SYSTEM_PROMPT)
        self.assertIn("stories", SPEC_SYSTEM_PROMPT)

    def test_prompt_mentions_grid_rule(self):
        from bonsai_ai.spec_planner import SPEC_SYSTEM_PROMPT
        self.assertIn("divide evenly", SPEC_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
