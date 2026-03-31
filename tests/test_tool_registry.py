"""Tests for the deferred / selective tool loading registry."""

from __future__ import annotations

import unittest

from bonsai_ai.tool_registry import (
    TOOL_CATEGORIES,
    as_anthropic_tools_for_phase,
    as_anthropic_tools_for_phases,
    as_openai_tools_for_phase,
    as_openai_tools_for_phases,
    available_phases,
    get_tool_summary_for_phase,
    get_tool_summary_for_phases,
    get_tools_for_phase,
    get_tools_for_phases,
)
from bonsai_ai.tool_specs import TOOL_SPECS


class TestToolCategories(unittest.TestCase):
    """Verify that the TOOL_CATEGORIES mapping is self-consistent."""

    def test_all_categories_are_non_empty(self) -> None:
        for phase, names in TOOL_CATEGORIES.items():
            self.assertIsInstance(names, list, f"Phase '{phase}' must map to a list")
            self.assertTrue(len(names) > 0, f"Phase '{phase}' has no tools")

    def test_available_phases_returns_all_keys(self) -> None:
        self.assertEqual(available_phases(), list(TOOL_CATEGORIES.keys()))

    def test_no_duplicate_names_within_a_phase(self) -> None:
        for phase, names in TOOL_CATEGORIES.items():
            self.assertEqual(len(names), len(set(names)), f"Phase '{phase}' has duplicate tool names")


class TestGetToolsForPhase(unittest.TestCase):
    """Tests for get_tools_for_phase()."""

    def test_structure_phase_returns_expected_count(self) -> None:
        specs = get_tools_for_phase("structure")
        self.assertEqual(len(specs), 5)
        names = {s.name for s in specs}
        self.assertIn("generate_column_grid", names)
        self.assertIn("create_column", names)
        self.assertIn("create_beam", names)
        self.assertIn("generate_floor_plate", names)
        self.assertIn("create_rectangular_slab", names)

    def test_structure_phase_is_subset_of_all_tools(self) -> None:
        specs = get_tools_for_phase("structure")
        self.assertTrue(len(specs) < len(TOOL_SPECS))

    def test_setup_phase(self) -> None:
        specs = get_tools_for_phase("setup")
        names = [s.name for s in specs]
        self.assertEqual(names, ["ensure_project", "ensure_storey"])

    def test_envelope_phase(self) -> None:
        specs = get_tools_for_phase("envelope")
        names = {s.name for s in specs}
        self.assertIn("create_wall", names)
        self.assertIn("generate_perimeter_walls", names)
        self.assertIn("create_curtain_wall", names)

    def test_openings_phase(self) -> None:
        specs = get_tools_for_phase("openings")
        names = {s.name for s in specs}
        self.assertEqual(names, {"create_door", "create_window"})

    def test_foundations_phase(self) -> None:
        specs = get_tools_for_phase("foundations")
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "create_footing")

    def test_unknown_phase_raises_key_error(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            get_tools_for_phase("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_stairs_phase_returns_empty_for_now(self) -> None:
        # Stair tool specs don't exist yet; the category is forward-compatible.
        specs = get_tools_for_phase("stairs")
        self.assertEqual(specs, [])

    def test_editing_phase_returns_empty_for_now(self) -> None:
        # Editing tool specs don't exist yet; the category is forward-compatible.
        specs = get_tools_for_phase("editing")
        self.assertEqual(specs, [])


class TestGetToolsForPhases(unittest.TestCase):
    """Tests for get_tools_for_phases() (multi-phase, deduped)."""

    def test_single_phase_matches_get_tools_for_phase(self) -> None:
        single = get_tools_for_phase("structure")
        multi = get_tools_for_phases(["structure"])
        self.assertEqual([s.name for s in single], [s.name for s in multi])

    def test_two_phases_are_deduped(self) -> None:
        specs = get_tools_for_phases(["setup", "structure"])
        names = [s.name for s in specs]
        self.assertEqual(len(names), len(set(names)), "Should have no duplicates")
        # Setup tools come first
        self.assertEqual(names[0], "ensure_project")
        self.assertEqual(names[1], "ensure_storey")

    def test_all_concrete_phases_cover_all_existing_specs(self) -> None:
        """Every existing ToolSpec should appear in at least one phase."""
        concrete_phases = [p for p in TOOL_CATEGORIES if p not in ("stairs", "editing")]
        all_phase_specs = get_tools_for_phases(concrete_phases)
        phase_names = {s.name for s in all_phase_specs}
        all_names = {s.name for s in TOOL_SPECS}
        self.assertEqual(phase_names, all_names)

    def test_unknown_phase_raises(self) -> None:
        with self.assertRaises(KeyError):
            get_tools_for_phases(["setup", "bogus"])


class TestToolSummary(unittest.TestCase):
    """Tests for the compact text summary functions."""

    def test_structure_summary_under_500_chars(self) -> None:
        summary = get_tool_summary_for_phase("structure")
        self.assertLessEqual(len(summary), 500)

    def test_summary_contains_tool_names(self) -> None:
        summary = get_tool_summary_for_phase("structure")
        self.assertIn("generate_column_grid", summary)
        self.assertIn("create_beam", summary)

    def test_summary_contains_phase_label(self) -> None:
        summary = get_tool_summary_for_phase("envelope")
        self.assertIn("[envelope]", summary)

    def test_summary_for_empty_phase(self) -> None:
        summary = get_tool_summary_for_phase("stairs")
        self.assertIn("No tools available", summary)

    def test_multi_phase_summary(self) -> None:
        summary = get_tool_summary_for_phases(["setup", "openings"])
        self.assertIn("ensure_project", summary)
        self.assertIn("create_door", summary)

    def test_every_phase_summary_is_compact(self) -> None:
        for phase in TOOL_CATEGORIES:
            summary = get_tool_summary_for_phase(phase)
            # 600 chars is generous; most are well under 500
            self.assertLessEqual(
                len(summary), 600,
                f"Summary for phase '{phase}' is {len(summary)} chars (limit: 600)",
            )


class TestProviderFormattedTools(unittest.TestCase):
    """Tests for as_openai_tools_for_phase / as_anthropic_tools_for_phase."""

    def test_openai_tools_for_structure_count(self) -> None:
        tools = as_openai_tools_for_phase("structure")
        self.assertEqual(len(tools), 5)

    def test_openai_tools_have_strict_flag(self) -> None:
        for tool in as_openai_tools_for_phase("structure"):
            self.assertEqual(tool["type"], "function")
            self.assertTrue(tool["function"]["strict"])

    def test_anthropic_tools_for_envelope_count(self) -> None:
        tools = as_anthropic_tools_for_phase("envelope")
        self.assertEqual(len(tools), 5)

    def test_anthropic_tools_have_input_schema(self) -> None:
        for tool in as_anthropic_tools_for_phase("envelope"):
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("input_schema", tool)

    def test_openai_multi_phase(self) -> None:
        tools = as_openai_tools_for_phases(["setup", "openings"])
        names = {t["function"]["name"] for t in tools}
        self.assertEqual(names, {"ensure_project", "ensure_storey", "create_door", "create_window"})

    def test_anthropic_multi_phase(self) -> None:
        tools = as_anthropic_tools_for_phases(["setup", "openings"])
        names = {t["name"] for t in tools}
        self.assertEqual(names, {"ensure_project", "ensure_storey", "create_door", "create_window"})

    def test_phase_tools_much_smaller_than_all_tools(self) -> None:
        """Core requirement: phase filtering should return far fewer tools than total."""
        all_count = len(TOOL_SPECS)
        structure_count = len(as_openai_tools_for_phase("structure"))
        # structure is 5 out of 15 => ~33%.  We expect < 50% for any single phase.
        self.assertLess(structure_count, all_count * 0.5)


class TestBackwardCompatibility(unittest.TestCase):
    """Ensure the registry does not break existing tool_specs imports."""

    def test_tool_specs_still_exports_all(self) -> None:
        from bonsai_ai.tool_specs import as_openai_tools, as_anthropic_tools, tool_names

        self.assertEqual(len(as_openai_tools()), len(TOOL_SPECS))
        self.assertEqual(len(as_anthropic_tools()), len(TOOL_SPECS))
        self.assertEqual(len(tool_names()), len(TOOL_SPECS))


if __name__ == "__main__":
    unittest.main()
