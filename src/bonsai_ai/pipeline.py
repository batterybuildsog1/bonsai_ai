from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol

from .contracts import AnalysisRequest, AnalysisResult, DesignBrief, DesignPackage, PhysicalModelSpec, PipelineArtifact


class PlannerBackend(Protocol):
    def build_physical_model(self, brief: DesignBrief) -> PhysicalModelSpec:
        raise NotImplementedError


class PhysicalModelBackend(Protocol):
    def materialize(self, package: DesignPackage, output_dir: Path) -> List[PipelineArtifact]:
        raise NotImplementedError


class AnalysisExportBackend(Protocol):
    def export(self, package: DesignPackage, output_dir: Path) -> List[PipelineArtifact]:
        raise NotImplementedError


class ResultsBundleBackend(Protocol):
    def build(self, package: DesignPackage, output_dir: Path) -> List[PipelineArtifact]:
        raise NotImplementedError


class SolverBackend(Protocol):
    def analyze(self, request: AnalysisRequest, package: DesignPackage, output_dir: Path) -> AnalysisResult:
        raise NotImplementedError


@dataclass
class DesignPipeline:
    planner: PlannerBackend
    physical_backend: PhysicalModelBackend | None = None
    analysis_exporter: AnalysisExportBackend | None = None
    solver: SolverBackend | None = None
    results_backend: ResultsBundleBackend | None = None

    def run(
        self,
        brief: DesignBrief,
        output_dir: str | Path,
        analysis_request: AnalysisRequest | None = None,
    ) -> DesignPackage:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        package = DesignPackage(brief=brief)
        package.physical_model = self.planner.build_physical_model(brief)

        if self.physical_backend:
            package.physical_artifacts = list(self.physical_backend.materialize(package, target_dir))

        if analysis_request:
            package.analysis_request = analysis_request

        if self.analysis_exporter and package.analysis_request:
            package.analysis_artifacts = list(self.analysis_exporter.export(package, target_dir))

        if self.solver and package.analysis_request:
            package.analysis_result = self.solver.analyze(package.analysis_request, package, target_dir)
            if package.analysis_result.artifacts:
                package.analysis_artifacts.extend(package.analysis_result.artifacts)

        if self.results_backend:
            package.results_artifacts = list(self.results_backend.build(package, target_dir))

        self.write_manifest(package, target_dir / "design_package.json")
        return package

    @staticmethod
    def write_manifest(package: DesignPackage, path: str | Path) -> None:
        target = Path(path)
        target.write_text(json.dumps(package.to_manifest(), indent=2))
