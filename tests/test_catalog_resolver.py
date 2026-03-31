from __future__ import annotations

import unittest

from bonsai_ai.catalog_resolver import resolve_catalog_sections
from bonsai_ai.catalog_selector import apply_catalog_selection
from bonsai_ai.contracts import MaterialSpec, SectionSpec, StructuralSourceElement, StructuralSourceModel
from bonsai_ai.system_catalog import starter_core_shell_catalog


class CatalogResolverTests(unittest.TestCase):
    def test_resolve_catalog_sections_updates_source_elements(self) -> None:
        source_model = StructuralSourceModel(
            materials=[
                MaterialSpec(
                    id="steel_default",
                    family="steel",
                    model="elastic_isotropic",
                    properties={"density_kg_m3": 7850, "elastic_modulus_pa": 200_000_000_000, "poisson_ratio": 0.3},
                )
            ],
            sections=[
                SectionSpec(
                    id="column_0.3000x0.3000",
                    kind="rect_profile",
                    material_id="steel_default",
                    dimensions={"width": 0.3, "depth": 0.3},
                )
            ],
            elements=[
                StructuralSourceElement(
                    id="frame_column_a",
                    kind="column",
                    role="primary_column",
                    structural_family="primary_frame",
                    parent_id="frame_line:primary:x0_y0",
                    section_id="column_0.3000x0.3000",
                    geometry={"origin": [0.0, 0.0, 0.0], "height": 6.0, "width": 0.3, "depth": 0.3},
                )
            ],
        )
        catalog = starter_core_shell_catalog()
        apply_catalog_selection(source_model, catalog)
        summary = resolve_catalog_sections(source_model, catalog)

        self.assertEqual(summary["resolved_section_total"], 1)
        self.assertTrue(source_model.elements[0].section_id.startswith("catalog_primary_columns_w_"))
        resolved_section = next(section for section in source_model.sections if section.id == source_model.elements[0].section_id)
        self.assertEqual(resolved_section.material_id, "steel_w_shapes")
        self.assertGreater(resolved_section.metadata["section_properties"]["section_modulus_major_m3"], 0.0)


if __name__ == "__main__":
    unittest.main()
