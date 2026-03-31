from __future__ import annotations

import unittest

from bonsai_ai.contracts import AnalysisResult, DesignBrief, DesignPackage, PhysicalModelSpec, StructuralSourceElement, StructuralSourceModel
from bonsai_ai.footing_selector import build_starter_footing_summary, starter_footing_from_imposed_load


class FootingSelectorTests(unittest.TestCase):
    def test_build_starter_footing_summary_from_support_reactions(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="test"),
            physical_model=PhysicalModelSpec(summary="test", assumptions=[], plan={"version": "1"}),
            structural_source_model=StructuralSourceModel(
                elements=[
                    StructuralSourceElement(
                        id="col_a",
                        kind="column",
                        role="primary_column",
                        geometry={"origin": [0.0, 0.0, 0.0], "height": 6.0},
                    ),
                    StructuralSourceElement(
                        id="col_b",
                        kind="column",
                        role="primary_column",
                        geometry={"origin": [6.0, 6.0, 0.0], "height": 6.0},
                    ),
                ]
            ),
            analysis_result=AnalysisResult(
                solver="pynite",
                summary={
                    "support_target_reactions": {
                        "ULS": {
                            "col_a": {"fz": 20_000.0},
                            "col_b": {"fz": 10_000.0},
                        }
                    }
                },
            ),
        )
        summary = build_starter_footing_summary(package)
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["footing_count"], 2)
        self.assertGreater(summary["footings"][0]["recommended_square_size_ft"], 0.0)
        self.assertGreater(summary["footings"][0]["rebar_weight_kg"], 0.0)
        self.assertGreater(summary["footings"][0]["concrete_strength_mpa"], 0.0)

    def test_starter_footing_accounts_for_eccentricity(self) -> None:
        concentric = starter_footing_from_imposed_load(400.0)
        eccentric = starter_footing_from_imposed_load(400.0, eccentricity_x_m=0.25, eccentricity_y_m=0.10)

        self.assertGreater(eccentric["recommended_square_size_ft"], concentric["recommended_square_size_ft"])
        self.assertGreater(eccentric["required_square_size_for_kern_ft"], 0.0)
        self.assertGreater(eccentric["eccentricity_x_m"], 0.0)
        self.assertIn("middle-third eccentricity", eccentric["basis_notes"])


if __name__ == "__main__":
    unittest.main()
