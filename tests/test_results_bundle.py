from __future__ import annotations

import json
import unittest
from pathlib import Path

from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    AnalysisResult,
    ArtifactFormat,
    ArtifactKind,
    DesignBrief,
    DesignPackage,
    LoadCase,
    PhysicalModelSpec,
    PipelineArtifact,
)
from bonsai_ai.results_bundle import JsonResultsBundleBackend


class ResultsBundleTests(unittest.TestCase):
    def test_results_bundle_uses_relative_entrypoints(self) -> None:
        output_dir = Path("/tmp/bonsai_results_bundle_test")
        output_dir.mkdir(parents=True, exist_ok=True)

        package = DesignPackage(
            brief=DesignBrief(prompt="Bridge bundle test", analysis_domains=[AnalysisDomain.WIND]),
            physical_model=PhysicalModelSpec(
                summary="Bundle summary",
                assumptions=["approximate"],
                plan={"version": "1.0", "actions": [{"type": "ensure_storey", "name": "Level 0", "elevation": 0.0}]},
                metadata={
                    "execution_report": {
                        "created": ["Level 0"],
                        "messages": ["Storey ready"],
                        "items": [
                            {
                                "action_type": "ensure_storey",
                                "element_name": "Level 0",
                                "ifc_class": "IfcBuildingStorey",
                                "global_id": "123",
                                "metadata": {"storey_name": "Level 0"},
                            }
                        ],
                    }
                },
            ),
            physical_artifacts=[
                PipelineArtifact(kind=ArtifactKind.PHYSICAL_IFC, format=ArtifactFormat.IFC, path=str(output_dir / "model.ifc")),
                PipelineArtifact(kind=ArtifactKind.BIM_PLAN, format=ArtifactFormat.JSON, path=str(output_dir / "physical_model_plan.json")),
            ],
            analysis_request=AnalysisRequest(
                solver="calculix",
                design_codes=["ASCE 7-22"],
                load_cases=[LoadCase(name="Wind LC1", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22")],
            ),
            analysis_artifacts=[
                PipelineArtifact(kind=ArtifactKind.ANALYTICAL_MODEL, format=ArtifactFormat.JSON, path=str(output_dir / "analytical_model.json")),
                PipelineArtifact(kind=ArtifactKind.SOLVER_INPUT, format=ArtifactFormat.JSON, path=str(output_dir / "solver_request.json")),
                PipelineArtifact(
                    kind=ArtifactKind.ENGINEERING_MODEL,
                    format=ArtifactFormat.JSON,
                    path=str(output_dir / "engineering_model.global_frame.json"),
                    metadata={"role": "engineering_model", "scope": "global_frame", "label": "Engineering Model (global_frame)"},
                ),
            ],
            analysis_result=AnalysisResult(solver="calculix", governing_cases=["Wind LC1"], unity_checks={"panel": 0.85}),
        )
        package.engineering_model_summary = {
            "requested_scopes": ["global_frame", "substructure", "bad_scope"],
            "emitted_scopes": ["global_frame"],
            "invalid_scopes": ["bad_scope"],
            "scope_diagnostics": {
                "global_frame": {"standalone_ready": True, "support_count": 2},
            },
            "warnings": ["Ignored unsupported engineering scopes: bad_scope"],
        }

        artifacts = JsonResultsBundleBackend().build(package, output_dir)

        self.assertEqual(artifacts[0].kind, ArtifactKind.RESULTS_BUNDLE)
        bundle = json.loads((output_dir / "results_bundle.json").read_text())
        self.assertEqual(bundle["entrypoints"]["physical_ifc"], "model.ifc")
        self.assertEqual(bundle["entrypoints"]["engineering_model_global_frame"], "engineering_model.global_frame.json")
        self.assertEqual(bundle["analysis_summary"]["solver"], "calculix")
        self.assertEqual(bundle["artifacts"][0]["path"], "model.ifc")
        self.assertEqual(bundle["diagnostics"]["invalid_engineering_scopes"], ["bad_scope"])
        self.assertEqual(bundle["diagnostics"]["missing_artifacts"], ["engineering_model:substructure", "engineering_model_invalid:bad_scope"])


if __name__ == "__main__":
    unittest.main()
