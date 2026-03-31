from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bonsai_ai.analysis_exports import JsonAnalysisExportBackend
from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    AnalysisResult,
    ArtifactFormat,
    ArtifactKind,
    ArtifactRole,
    DesignBrief,
    LoadCase,
    PhysicalModelSpec,
    PipelineArtifact,
)
from bonsai_ai.pipeline import DesignPipeline
from bonsai_ai.results_bundle import JsonResultsBundleBackend


class FakePlanner:
    def build_physical_model(self, brief: DesignBrief) -> PhysicalModelSpec:
        return PhysicalModelSpec(
            summary=f"Steel concept for: {brief.prompt}",
            assumptions=["Early-stage steel framing assumptions only."],
            plan={
                "version": "1.0",
                "units": "meters",
                "actions": [
                    {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                    {
                        "type": "create_wall",
                        "name": "North Braced Bay",
                        "storey": "Level 0",
                        "x1": 0.0,
                        "y1": 0.0,
                        "x2": 8.0,
                        "y2": 0.0,
                        "base_z": 0.0,
                        "height": 6.0,
                        "thickness": 0.2,
                    },
                    {
                        "type": "create_column",
                        "name": "Corner Column",
                        "storey": "Level 0",
                        "x": 0.0,
                        "y": 0.0,
                        "base_z": 0.0,
                        "width": 0.3,
                        "depth": 0.3,
                        "height": 6.0,
                    },
                ],
            },
            metadata={
                "execution_report": {
                    "created": ["Level 0", "North Braced Bay", "Corner Column"],
                    "messages": ["Placeholder IFC export ready."],
                    "items": [
                        {
                            "action_type": "ensure_storey",
                            "element_name": "Level 0",
                            "ifc_class": "IfcBuildingStorey",
                            "metadata": {"storey_name": "Level 0"},
                        },
                        {
                            "action_type": "create_wall",
                            "element_name": "North Braced Bay",
                            "ifc_class": "IfcWall",
                            "metadata": {"storey_name": "Level 0"},
                        },
                        {
                            "action_type": "create_column",
                            "element_name": "Corner Column",
                            "ifc_class": "IfcColumn",
                            "metadata": {"storey_name": "Level 0"},
                        },
                    ],
                }
            },
        )


class FakePhysicalBackend:
    def materialize(self, package, output_dir: Path):
        ifc_path = output_dir / "office.ifc"
        plan_path = output_dir / "physical_model_plan.json"
        ifc_path.write_text("ISO-10303-21;")
        plan_path.write_text(json.dumps(package.physical_model.plan, indent=2))
        return [
            PipelineArtifact(
                kind=ArtifactKind.PHYSICAL_IFC,
                format=ArtifactFormat.IFC,
                path=str(ifc_path),
                metadata={"role": ArtifactRole.PRIMARY_IFC.value, "label": "Primary IFC", "is_primary": True},
            ),
            PipelineArtifact(
                kind=ArtifactKind.BIM_PLAN,
                format=ArtifactFormat.JSON,
                path=str(plan_path),
                metadata={"role": ArtifactRole.BIM_PLAN.value, "label": "Physical Model Plan"},
            ),
        ]


class FakePyNiteSolver:
    def analyze(self, request, package, output_dir: Path):
        results_path = output_dir / "pynite_results.json"
        freecad_handoff_path = output_dir / "freecad_handoff.json"

        results_path.write_text(
            json.dumps(
                {
                    "solver": "pynite",
                    "status": "completed",
                    "max_displacement_mm": 14.2,
                    "governing_case": request.load_cases[0].name,
                },
                indent=2,
            )
        )
        freecad_handoff_path.write_text(
            json.dumps(
                {
                    "consumer": "freecad",
                    "physical_ifc": "office.ifc",
                    "analytical_model": "analytical_model.json",
                    "solver_result": "pynite_results.json",
                    "note": "FreeCAD owns downstream engineering review or refinement; PyNite owns the fast frame solve.",
                },
                indent=2,
            )
        )

        return AnalysisResult(
            solver="pynite",
            status="completed",
            governing_cases=[request.load_cases[0].name],
            unity_checks={"corner_column": 0.74},
            summary={"max_displacement_mm": 14.2},
            artifacts=[
                PipelineArtifact(
                    kind=ArtifactKind.SOLVER_RESULT,
                    format=ArtifactFormat.JSON,
                    path=str(results_path),
                    metadata={"role": ArtifactRole.SOLVER_RESULT.value, "label": "PyNite Results", "engine": "pynite"},
                ),
                PipelineArtifact(
                    kind=ArtifactKind.ENGINEERING_REPORT,
                    format=ArtifactFormat.JSON,
                    path=str(freecad_handoff_path),
                    metadata={
                        "role": ArtifactRole.ENGINEERING_REPORT.value,
                        "label": "FreeCAD Handoff",
                        "consumer": "freecad",
                    },
                ),
            ],
        )


class SolverPipelineIntegrationTests(unittest.TestCase):
    def test_pipeline_publishes_ifc_analysis_and_freecad_handoff_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            brief = DesignBrief(
                prompt="Design a simple steel office frame.",
                analysis_domains=[AnalysisDomain.WIND, AnalysisDomain.STRUCTURAL_STEEL],
            )
            request = AnalysisRequest(
                solver="pynite",
                design_codes=["AISC 360-22"],
                load_cases=[LoadCase(name="Wind X+", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22")],
                metadata={"handoff_target": "freecad"},
            )
            pipeline = DesignPipeline(
                planner=FakePlanner(),
                physical_backend=FakePhysicalBackend(),
                analysis_exporter=JsonAnalysisExportBackend(),
                solver=FakePyNiteSolver(),
                results_backend=JsonResultsBundleBackend(),
            )

            package = pipeline.run(brief=brief, output_dir=output_dir, analysis_request=request)

            self.assertTrue((output_dir / "office.ifc").exists())
            self.assertTrue((output_dir / "analytical_model.json").exists())
            self.assertTrue((output_dir / "solver_request.json").exists())
            self.assertTrue((output_dir / "pynite_results.json").exists())
            self.assertTrue((output_dir / "freecad_handoff.json").exists())
            self.assertEqual(package.analysis_result.solver, "pynite")
            self.assertEqual(len(package.results_artifacts), 1)

            bundle = json.loads((output_dir / "results_bundle.json").read_text())
            self.assertEqual(bundle["entrypoints"]["physical_ifc"], "office.ifc")
            self.assertEqual(bundle["entrypoints"]["physical_plan"], "physical_model_plan.json")
            self.assertEqual(bundle["entrypoints"]["analytical_model"], "analytical_model.json")
            self.assertEqual(bundle["entrypoints"]["solver_request"], "solver_request.json")
            self.assertEqual(bundle["entrypoints"]["solver_result"], "pynite_results.json")
            self.assertEqual(bundle["analysis_summary"]["solver"], "pynite")
            self.assertEqual(bundle["analysis_summary"]["unity_checks"]["corner_column"], 0.74)

            artifact_index = {artifact["label"]: artifact for artifact in bundle["artifacts"]}
            self.assertTrue(artifact_index["Primary IFC"]["is_primary"])
            self.assertEqual(artifact_index["Primary IFC"]["role"], ArtifactRole.PRIMARY_IFC.value)
            self.assertEqual(artifact_index["PyNite Results"]["role"], ArtifactRole.SOLVER_RESULT.value)
            self.assertEqual(artifact_index["FreeCAD Handoff"]["role"], ArtifactRole.ENGINEERING_REPORT.value)
            self.assertEqual(artifact_index["FreeCAD Handoff"]["metadata"]["consumer"], "freecad")


if __name__ == "__main__":
    unittest.main()
