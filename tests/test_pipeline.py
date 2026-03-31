from __future__ import annotations

import json
import unittest
from pathlib import Path

from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    ArtifactFormat,
    ArtifactKind,
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
            summary=f"Planned: {brief.prompt}",
            assumptions=["approximate geometry"],
            plan={"version": "1.0", "actions": [{"type": "create_wall", "name": "Wall A"}]},
        )


class FakePhysicalBackend:
    def materialize(self, package, output_dir: Path):
        return [
            PipelineArtifact(
                kind=ArtifactKind.PHYSICAL_IFC,
                format=ArtifactFormat.IFC,
                path=str(output_dir / "model.ifc"),
            )
        ]


class FakeAnalysisExporter:
    def export(self, package, output_dir: Path):
        return [
            PipelineArtifact(
                kind=ArtifactKind.ANALYTICAL_MODEL,
                format=ArtifactFormat.CALCULIX_INP,
                path=str(output_dir / "model.inp"),
            )
        ]


class FakeSolver:
    def analyze(self, request, package, output_dir: Path):
        from bonsai_ai.contracts import AnalysisResult

        return AnalysisResult(
            solver=request.solver,
            governing_cases=[request.load_cases[0].name],
            unity_checks={"wall_panel": 0.82},
        )


class PipelineTests(unittest.TestCase):
    def test_design_pipeline_writes_manifest(self) -> None:
        tmp_path = Path("/tmp/bonsai_pipeline_test")
        tmp_path.mkdir(parents=True, exist_ok=True)

        brief = DesignBrief(
            prompt="Create one insulated panel",
            analysis_domains=[AnalysisDomain.WIND, AnalysisDomain.SEISMIC],
        )
        request = AnalysisRequest(
            solver="calculix",
            design_codes=["ASCE 7-22", "ACI 318-19"],
            load_cases=[LoadCase(name="Wind LC1", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22")],
        )
        pipeline = DesignPipeline(
            planner=FakePlanner(),
            physical_backend=FakePhysicalBackend(),
            analysis_exporter=FakeAnalysisExporter(),
            solver=FakeSolver(),
            results_backend=JsonResultsBundleBackend(),
        )

        package = pipeline.run(brief=brief, output_dir=tmp_path, analysis_request=request)

        self.assertIsNotNone(package.physical_model)
        self.assertIsNotNone(package.analysis_result)
        self.assertEqual(len(package.results_artifacts), 1)
        manifest = json.loads((tmp_path / "design_package.json").read_text())
        self.assertEqual(manifest["analysis_request"]["solver"], "calculix")
        self.assertEqual(manifest["analysis_result"]["unity_checks"]["wall_panel"], 0.82)
        self.assertEqual(manifest["results_artifacts"][0]["kind"], "results_bundle")
        bundle = json.loads((tmp_path / "results_bundle.json").read_text())
        self.assertEqual(bundle["entrypoints"]["physical_ifc"], "model.ifc")


if __name__ == "__main__":
    unittest.main()
