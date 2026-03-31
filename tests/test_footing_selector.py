from __future__ import annotations

import unittest

from bonsai_ai.contracts import AnalysisResult, DesignBrief, DesignPackage, PhysicalModelSpec, StructuralSourceElement, StructuralSourceModel
from bonsai_ai.footing_selector import build_starter_footing_summary


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


if __name__ == "__main__":
    unittest.main()
