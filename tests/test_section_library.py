from __future__ import annotations

import unittest

from bonsai_ai.section_library import resolve_catalog_section, starter_catalog_material_specs


class SectionLibraryTests(unittest.TestCase):
    def test_resolve_catalog_section_uses_official_starter_properties(self) -> None:
        section = resolve_catalog_section("primary_columns_w", "W10x33", "steel_w_shapes")
        assert section is not None
        self.assertEqual(section.material_id, "steel_w_shapes")
        self.assertEqual(section.metadata["catalog_section_name"], "W10X33")
        self.assertGreater(section.metadata["section_properties"]["area_m2"], 0.0)
        self.assertGreater(section.metadata["section_properties"]["ix_m4"], 0.0)
        self.assertGreater(section.metadata["section_properties"]["weight_n_per_m"], 0.0)

    def test_starter_catalog_material_specs_include_strength_properties(self) -> None:
        materials = {material.id: material for material in starter_catalog_material_specs()}
        self.assertIn("steel_w_shapes", materials)
        self.assertIn("steel_hss", materials)
        self.assertGreater(materials["steel_w_shapes"].properties["fy_pa"], 0.0)


if __name__ == "__main__":
    unittest.main()
