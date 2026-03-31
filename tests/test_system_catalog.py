from __future__ import annotations

import unittest

from bonsai_ai.system_catalog import starter_catalog_summary, starter_core_shell_catalog


class SystemCatalogTests(unittest.TestCase):
    def test_starter_catalog_has_expected_defaults(self) -> None:
        catalog = starter_core_shell_catalog()

        self.assertEqual(catalog["catalog_id"], "starter_core_shell_v1")
        self.assertEqual(catalog["design_intent"]["default_primary_system"], "w_shape_frame_with_hss_braces")
        self.assertEqual(catalog["selection_defaults"]["primary_columns"], "primary_columns_w")
        self.assertEqual(catalog["selection_defaults"]["braces"], "brace_hss")
        self.assertEqual(catalog["selection_defaults"]["interior_footings"], "interior_spread_footing")
        self.assertEqual(catalog["panel_catalogs"][0]["size_rules"]["max_height_ft"], 50.0)
        self.assertEqual(catalog["panel_catalogs"][0]["size_rules"]["max_width_ft"], 12.0)
        self.assertEqual(catalog["panel_catalogs"][0]["size_rules"]["width_increment_in"], 6)
        self.assertEqual(catalog["panel_catalogs"][0]["size_rules"]["height_increment_ft"], 2)
        self.assertGreaterEqual(len(catalog["member_families"]), 8)

    def test_catalog_summary_matches_catalog(self) -> None:
        catalog = starter_core_shell_catalog()
        summary = starter_catalog_summary(catalog)

        self.assertEqual(summary["catalog_id"], catalog["catalog_id"])
        self.assertEqual(summary["member_family_count"], len(catalog["member_families"]))
        self.assertEqual(summary["panel_catalog_count"], len(catalog["panel_catalogs"]))
        self.assertEqual(summary["footing_family_count"], len(catalog["footing_families"]))
        self.assertEqual(summary["defaults"]["roof_secondary"], "roof_purlins_z")


if __name__ == "__main__":
    unittest.main()
