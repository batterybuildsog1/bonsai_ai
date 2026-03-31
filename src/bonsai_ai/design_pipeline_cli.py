from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from .analysis_exports import JsonAnalysisExportBackend
from .contracts import AnalysisDomain, AnalysisRequest, DesignBrief, LoadCase, SourceDocument
from .execution import IfcPhysicalModelBackend
from .freecad_runner import run_freecad_handoff
from .pipeline import DesignPipeline
from .planner_backends import CorePhysicalPlannerBackend
from .pynite_backend import PyNiteSolverBackend
from .results_bundle import JsonResultsBundleBackend

DEFAULT_ENGINEERING_SCOPES = [
    "global_frame",
    "roof_load_path",
    "facade_support",
    "substructure",
    "opening_support",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deep-refactor design pipeline CLI for BIM + analysis handoff.")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model")
    parser.add_argument("--api-key", help="Explicit API key. Prefer env vars for regular use.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--doc", action="append", default=[], help="Reference document path. Repeatable.")
    parser.add_argument(
        "--analysis-domain",
        action="append",
        choices=[domain.value for domain in AnalysisDomain],
        default=[],
        help="Include an engineering analysis domain in the handoff package.",
    )
    parser.add_argument("--solver", default="calculix")
    parser.add_argument("--freecad-handoff", action="store_true", help="Emit FreeCAD-oriented handoff artifacts.")
    parser.add_argument("--run-freecad", action="store_true", help="Run the generated FreeCAD macro if FreeCAD is installed.")
    parser.add_argument("--freecad-executable", help="Explicit path or command name for the FreeCAD executable.")
    parser.add_argument("--freecad-timeout", type=int, default=240, help="FreeCAD execution timeout in seconds.")
    parser.add_argument("--design-code", action="append", default=[])
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--service-tier", default="priority")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    analysis_domains = [AnalysisDomain(value) for value in args.analysis_domain]
    brief = DesignBrief(
        prompt=args.prompt,
        documents=[SourceDocument(name=os.path.basename(path), path=path) for path in args.doc],
        analysis_domains=analysis_domains,
    )
    analysis_request = None
    if analysis_domains:
        analysis_request = AnalysisRequest(
            solver=args.solver,
            design_codes=args.design_code or [],
            load_cases=[
                LoadCase(
                    name=f"{domain.value}_default",
                    domain=domain,
                    code_basis=(args.design_code[0] if args.design_code else "unspecified"),
                )
                for domain in analysis_domains
            ],
            export_options={
                "freecad_handoff": bool(args.freecad_handoff or analysis_domains),
                "engineering_scopes": list(DEFAULT_ENGINEERING_SCOPES),
            },
        )

    solver_backend = PyNiteSolverBackend() if args.solver == "pynite" and analysis_request else None
    pipeline = DesignPipeline(
        planner=CorePhysicalPlannerBackend(
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            reasoning_effort=args.reasoning_effort,
            service_tier=args.service_tier,
        ),
        physical_backend=IfcPhysicalModelBackend(),
        analysis_exporter=JsonAnalysisExportBackend(include_freecad_handoff=bool(args.freecad_handoff or analysis_domains)),
        solver=solver_backend,
        results_backend=JsonResultsBundleBackend(),
    )
    package = pipeline.run(brief=brief, output_dir=args.output_dir, analysis_request=analysis_request)
    print(f"Wrote design package to {args.output_dir}")
    if package.results_artifacts:
        print("Primary bundle:")
        for artifact in package.results_artifacts:
            print(f"- {artifact.kind.value}: {artifact.path}")
    if package.physical_artifacts:
        print("Physical artifacts:")
        for artifact in package.physical_artifacts:
            print(f"- {artifact.kind.value}: {artifact.path}")
    if package.analysis_artifacts:
        print("Analysis artifacts:")
        for artifact in package.analysis_artifacts:
            print(f"- {artifact.kind.value}: {artifact.path}")
    if args.run_freecad and (Path(args.output_dir) / "freecad_handoff.json").exists():
        freecad_artifacts = run_freecad_handoff(
            args.output_dir,
            freecad_bin=args.freecad_executable,
            timeout_seconds=args.freecad_timeout,
        )
        package.analysis_artifacts.extend(freecad_artifacts)
        package.results_artifacts = list(JsonResultsBundleBackend().build(package, Path(args.output_dir)))
        DesignPipeline.write_manifest(package, Path(args.output_dir) / "design_package.json")
        print("FreeCAD artifacts:")
        for artifact in freecad_artifacts:
            print(f"- {artifact.kind.value}: {artifact.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
