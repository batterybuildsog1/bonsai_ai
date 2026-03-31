from __future__ import annotations

import json
import unittest
from pathlib import Path

from bonsai_ai.analysis_exports import JsonAnalysisExportBackend
from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    DesignBrief,
    DesignPackage,
    LoadCase,
    PhysicalModelSpec,
    PipelineArtifact,
    ArtifactKind,
    ArtifactFormat,
)


class AnalysisExportTests(unittest.TestCase):
    def test_json_analysis_export_backend_writes_handoff_files(self) -> None:
        output_dir = Path("/tmp/bonsai_analysis_export_test")
        output_dir.mkdir(parents=True, exist_ok=True)

        package = DesignPackage(
            brief=DesignBrief(
                prompt="Panel design",
                analysis_domains=[AnalysisDomain.WIND, AnalysisDomain.SEISMIC],
            ),
            physical_model=PhysicalModelSpec(
                summary="Panel summary",
                assumptions=["foam core unmodeled"],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                        {
                            "type": "create_column",
                            "name": "Base Column",
                            "storey": "Level 0",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": -2.0,
                            "width": 0.4,
                            "depth": 0.4,
                            "height": 2.0,
                        },
                        {
                            "type": "create_wall",
                            "name": "Panel Wythe",
                            "storey": "Level 0",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 0.0,
                            "height": 5.0,
                            "thickness": 0.2,
                        },
                        {
                            "type": "create_beam",
                            "name": "Spandrel Beam",
                            "storey": "Level 0",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 5.0,
                            "end_z": 6.0,
                            "width": 0.3,
                            "depth": 0.6,
                        },
                    ],
                },
            ),
            physical_artifacts=[
                PipelineArtifact(
                    kind=ArtifactKind.PHYSICAL_IFC,
                    format=ArtifactFormat.IFC,
                    path=str(output_dir / "physical.ifc"),
                )
            ],
            analysis_request=AnalysisRequest(
                solver="calculix",
                design_codes=["ASCE 7-22"],
                load_cases=[LoadCase(name="Wind X+", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22")],
            ),
        )

        artifacts = JsonAnalysisExportBackend().export(package, output_dir)

        self.assertEqual(len(artifacts), 9)
        structural_source = json.loads((output_dir / "structural_source_model.json").read_text())
        self.assertEqual(structural_source["elements"][0]["role"], "primary_column")
        system_layout = json.loads((output_dir / "system_layout.json").read_text())
        self.assertIn("frame_lines", system_layout)
        load_path = json.loads((output_dir / "load_path_model.json").read_text())
        self.assertIn("facade_zones", load_path)
        catalog_selection = json.loads((output_dir / "catalog_selection_summary.json").read_text())
        self.assertIn("selected_family_counts", catalog_selection)
        payload = json.loads((output_dir / "analytical_model.json").read_text())
        self.assertEqual(payload["load_cases"][0]["name"], "Wind X+")
        self.assertIn("concrete_default", {item["id"] for item in payload["materials"]})
        self.assertIn("steel_default", {item["id"] for item in payload["materials"]})
        self.assertIn("wall", {item["kind"] for item in payload["elements"]})
        self.assertIn("beam", {item["kind"] for item in payload["elements"]})
        self.assertEqual(payload["metadata"]["analysis_profile"], "global_full")
        beam = next(item for item in payload["elements"] if item["kind"] == "beam")
        self.assertEqual(beam["geometry"]["end"][2], 6.0)
        self.assertEqual(len(payload["supports"]), 1)
        self.assertEqual(payload["supports"][0]["target_id"], "base_column")
        self.assertEqual(payload["load_combinations"][0]["case_factors"]["Wind X+"], 1.0)
        solver_request = json.loads((output_dir / "solver_request.json").read_text())
        self.assertEqual(solver_request["solver"], "calculix")
        self.assertEqual(solver_request["structural_source_model"], "structural_source_model.json")
        self.assertEqual(solver_request["handoff_artifacts"]["freecad_handoff"], "freecad_handoff.json")
        handoff = json.loads((output_dir / "freecad_handoff.json").read_text())
        self.assertEqual(handoff["source_files"]["analytical_model"], "analytical_model.json")
        self.assertEqual(handoff["objects"][0]["primitive"], "Part::Box")
        self.assertIn("beam", {item["kind"] for item in handoff["objects"]})
        macro = (output_dir / "freecad_handoff.py").read_text()
        self.assertIn("freecad_handoff.json", macro)
        self.assertEqual(artifacts[0].metadata["label"], "Structural Source Model")
        self.assertEqual(artifacts[1].metadata["label"], "System Layout")
        self.assertEqual(artifacts[2].metadata["label"], "Load Path Model")
        self.assertEqual(artifacts[3].metadata["label"], "Catalog Selection Summary")
        self.assertEqual(artifacts[6].metadata["label"], "Analysis Profile Summary")
        self.assertEqual(artifacts[7].metadata["label"], "FreeCAD Handoff JSON")
        self.assertEqual(artifacts[8].metadata["label"], "FreeCAD Handoff Script")

    def test_export_writes_engineering_scope_models(self) -> None:
        output_dir = Path("/tmp/bonsai_analysis_export_engineering_models")
        output_dir.mkdir(parents=True, exist_ok=True)

        package = DesignPackage(
            brief=DesignBrief(
                prompt="Engineering models",
                analysis_domains=[AnalysisDomain.WIND, AnalysisDomain.FOOTING],
            ),
            physical_model=PhysicalModelSpec(
                summary="Engineering scope summary",
                assumptions=["role-specific exports"],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                        {
                            "type": "create_column",
                            "name": "corner_frame_column X000_Y000_Seg1",
                            "storey": "Level 0",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": -2.0,
                            "width": 0.4,
                            "depth": 0.4,
                            "height": 2.0,
                        },
                        {
                            "type": "create_column",
                            "name": "South Facade Post X010_Y000_Seg1",
                            "storey": "Level 0",
                            "x": 1.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.2,
                            "depth": 0.2,
                            "height": 5.0,
                        },
                        {
                            "type": "create_beam",
                            "name": "Collector",
                            "storey": "Roof",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 5.0,
                            "y2": 0.0,
                            "base_z": 5.0,
                            "width": 0.25,
                            "depth": 0.4,
                            "member_role": "roof_collector",
                        },
                        {
                            "type": "create_beam",
                            "name": "Window 01 Header",
                            "storey": "Level 0",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 2.0,
                            "y2": 0.0,
                            "base_z": 2.0,
                            "width": 0.2,
                            "depth": 0.3,
                            "member_role": "window_header",
                        },
                        {
                            "type": "create_wall",
                            "name": "Basement Retaining West",
                            "storey": "Basement",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 0.0,
                            "y2": 6.0,
                            "base_z": -3.0,
                            "height": 3.0,
                            "thickness": 0.3,
                        },
                        {
                            "type": "create_rect_slab",
                            "name": "Foundation Footing",
                            "storey": "Basement",
                            "x": 0.0,
                            "y": 0.0,
                            "z": -3.0,
                            "width": 6.0,
                            "depth": 8.0,
                            "thickness": 0.5,
                        },
                    ],
                },
            ),
            analysis_request=AnalysisRequest(
                solver="pynite",
                design_codes=["ASCE 7-22"],
                load_cases=[
                    LoadCase(name="Wind X+", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22"),
                    LoadCase(name="Footing", domain=AnalysisDomain.FOOTING, code_basis="IBC 2021"),
                ],
                export_options={"engineering_scopes": ["global_frame", "facade_support", "substructure"]},
            ),
        )

        artifacts = JsonAnalysisExportBackend(include_freecad_handoff=False).export(package, output_dir)

        global_frame = json.loads((output_dir / "engineering_model.global_frame.json").read_text())
        facade_support = json.loads((output_dir / "engineering_model.facade_support.json").read_text())
        substructure = json.loads((output_dir / "engineering_model.substructure.json").read_text())
        solver_request = json.loads((output_dir / "solver_request.json").read_text())

        self.assertEqual(global_frame["scope"], "global_frame")
        self.assertEqual(facade_support["scope"], "facade_support")
        self.assertEqual(substructure["scope"], "substructure")
        self.assertIn("primary_column", {item["metadata"]["analysis_role"] for item in global_frame["elements"]})
        self.assertIn("opening_header", {item["metadata"]["analysis_role"] for item in facade_support["elements"]})
        self.assertIn("foundation", {item["metadata"]["analysis_role"] for item in substructure["elements"]})
        self.assertEqual(
            solver_request["engineering_models"],
            {
                "global_frame": "engineering_model.global_frame.json",
                "facade_support": "engineering_model.facade_support.json",
                "substructure": "engineering_model.substructure.json",
            },
        )
        engineering_artifacts = [artifact for artifact in artifacts if artifact.kind == ArtifactKind.ENGINEERING_MODEL]
        self.assertEqual(len(engineering_artifacts), 3)
        self.assertEqual(engineering_artifacts[0].metadata["role"], "engineering_model")
        engineering_summary = json.loads((output_dir / "engineering_model_summary.json").read_text())
        self.assertEqual(engineering_summary["requested_scopes"], ["global_frame", "facade_support", "substructure"])
        self.assertEqual(engineering_summary["emitted_scopes"], ["global_frame", "facade_support", "substructure"])
        self.assertTrue(engineering_summary["scope_diagnostics"]["global_frame"]["standalone_ready"])
        self.assertIn("primary_frame", engineering_summary["scope_diagnostics"]["global_frame"]["family_counts"])
        self.assertGreater(engineering_summary["scope_diagnostics"]["global_frame"]["parent_count"], 0)

    def test_invalid_engineering_scope_fails_fast(self) -> None:
        output_dir = Path("/tmp/bonsai_analysis_export_invalid_scope")
        output_dir.mkdir(parents=True, exist_ok=True)

        package = DesignPackage(
            brief=DesignBrief(prompt="Invalid engineering scope", analysis_domains=[AnalysisDomain.WIND]),
            physical_model=PhysicalModelSpec(
                summary="Invalid scope summary",
                assumptions=["warning path"],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {
                            "type": "create_column",
                            "name": "corner_frame_column X000_Y000_Seg1",
                            "storey": "Level 0",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.4,
                            "depth": 0.4,
                            "height": 4.0,
                        }
                    ],
                },
            ),
            analysis_request=AnalysisRequest(
                solver="pynite",
                design_codes=["ASCE 7-22"],
                load_cases=[LoadCase(name="Wind X+", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22")],
                export_options={"engineering_scopes": ["global_frame", "not_a_scope"]},
            ),
        )

        with self.assertRaisesRegex(ValueError, "Unsupported engineering scopes: not_a_scope"):
            JsonAnalysisExportBackend(include_freecad_handoff=False).export(package, output_dir)

    def test_frame_only_mode_filters_surfaces_and_maps_wind_to_collectors(self) -> None:
        output_dir = Path("/tmp/bonsai_analysis_export_frame_only")
        output_dir.mkdir(parents=True, exist_ok=True)

        package = DesignPackage(
            brief=DesignBrief(
                prompt="Frame-only shell check",
                analysis_domains=[AnalysisDomain.WIND],
            ),
            physical_model=PhysicalModelSpec(
                summary="Frame-only summary",
                assumptions=["fast iteration"],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                        {
                            "type": "create_column",
                            "name": "Base Column",
                            "storey": "Level 0",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.4,
                            "depth": 0.4,
                            "height": 3.0,
                        },
                        {
                            "type": "create_beam",
                            "name": "Roof Collector",
                            "storey": "Roof",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 3.0,
                            "width": 0.3,
                            "depth": 0.6,
                            "member_role": "roof_collector",
                        },
                        {
                            "type": "create_wall",
                            "name": "Facade Wall",
                            "storey": "Level 0",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 0.0,
                            "height": 3.0,
                            "thickness": 0.2,
                        },
                    ],
                },
            ),
            analysis_request=AnalysisRequest(
                solver="pynite",
                design_codes=["ASCE 7-22"],
                load_cases=[LoadCase(name="Wind X+", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22", parameters={"pressure_kpa": 1.4})],
                export_options={"analysis_model_mode": "frame_only"},
            ),
        )

        JsonAnalysisExportBackend().export(package, output_dir)

        payload = json.loads((output_dir / "analytical_model.json").read_text())
        self.assertEqual(payload["metadata"]["analysis_profile"], "global_fast")
        self.assertEqual({item["kind"] for item in payload["elements"]}, {"beam", "column"})
        wind_case = payload["load_cases"][0]
        self.assertEqual(wind_case["actions"][0]["kind"], "point_load")
        self.assertEqual(wind_case["actions"][0]["target_id"], "roof_collector")
