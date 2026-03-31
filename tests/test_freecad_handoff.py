from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    AnalyticalModel,
    DesignBrief,
    DesignPackage,
    LoadAction,
    LoadCase,
    LoadCombination,
    MaterialSpec,
    SectionSpec,
    StructuralElement,
)
from bonsai_ai.freecad_handoff import FreeCADHandoffBuilder, render_freecad_handoff_script


class FreeCADHandoffTests(unittest.TestCase):
    def test_builder_creates_useful_box_payloads(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="Floor handoff", analysis_domains=[AnalysisDomain.GRAVITY]),
            analytical_model=AnalyticalModel(
                units="meters",
                materials=[
                    MaterialSpec(
                        id="steel_default",
                        family="steel",
                        model="elastic_isotropic",
                        properties={"elastic_modulus_pa": 200_000_000_000},
                    )
                ],
                sections=[
                    SectionSpec(
                        id="column_section",
                        kind="rect_profile",
                        material_id="steel_default",
                        dimensions={"width": 0.3, "depth": 0.3},
                    ),
                    SectionSpec(
                        id="beam_section",
                        kind="rect_profile",
                        material_id="steel_default",
                        dimensions={"width": 0.25, "depth": 0.5},
                    )
                ],
                elements=[
                    StructuralElement(
                        id="grid_a1_col",
                        kind="column",
                        section_id="column_section",
                        geometry={"origin": [0.0, 0.0, 0.0], "width": 0.3, "depth": 0.3, "height": 4.5},
                        orientation={"rotation_deg": 15.0},
                        metadata={"source_name": "Grid A1 Column"},
                    ),
                    StructuralElement(
                        id="panel_1",
                        kind="panel",
                        section_id="column_section",
                        geometry={"origin": [0.0, 0.0, 4.5], "length": 6.0, "width": 2.4, "thickness": 0.2},
                        metadata={"source_name": "Floor Panel 1"},
                    ),
                    StructuralElement(
                        id="beam_a1_b1",
                        kind="beam",
                        section_id="beam_section",
                        geometry={"start": [0.0, 0.0, 4.5], "end": [6.0, 0.0, 4.5], "width": 0.25, "depth": 0.5},
                        metadata={"source_name": "Grid A1-B1 Beam"},
                    ),
                ],
                load_cases=[
                    LoadCase(
                        name="Gravity",
                        domain=AnalysisDomain.GRAVITY,
                        code_basis="ASCE 7-22",
                        actions=[LoadAction(target_id="all", kind="self_weight", magnitude=1.0)],
                    )
                ],
                load_combinations=[
                    LoadCombination(name="1.0D", case_factors={"Gravity": 1.0}, code_basis="ASCE 7-22")
                ],
                metadata={"summary": "FreeCAD handoff summary", "assumptions": ["panel stiffness simplified"]},
            ),
            analysis_request=AnalysisRequest(
                solver="calculix",
                design_codes=["ASCE 7-22"],
                load_cases=[LoadCase(name="Gravity", domain=AnalysisDomain.GRAVITY, code_basis="ASCE 7-22")],
            ),
        )

        payload = FreeCADHandoffBuilder().build(package)

        self.assertEqual(payload["solver"], "calculix")
        self.assertEqual(payload["objects"][0]["label"], "Grid A1 Column")
        self.assertEqual(payload["objects"][0]["dimensions"]["height"], 4.5)
        self.assertEqual(payload["objects"][1]["dimensions"]["length"], 6.0)
        self.assertEqual(payload["objects"][2]["label"], "Grid A1-B1 Beam")
        self.assertEqual(payload["objects"][2]["dimensions"]["height"], 0.5)
        self.assertEqual(payload["load_combinations"][0]["name"], "1.0D")
        self.assertEqual(payload["metadata"]["object_count"], 3)

    def test_builder_writes_json_and_macro(self) -> None:
        payload = {
            "schema_version": "1.0",
            "objects": [{"id": "wall_1", "label": "Wall 1", "primitive": "Part::Box", "dimensions": {"length": 1.0, "width": 0.2, "height": 3.0}, "placement": {"base": [0.0, 0.0, 0.0], "rotation_axis": [0.0, 0.0, 1.0], "rotation_deg": 0.0}}],
        }

        with tempfile.TemporaryDirectory(prefix="bonsai_freecad_handoff_test_") as temp_dir:
            json_path = Path(temp_dir) / "freecad_handoff.json"
            macro_path = Path(temp_dir) / "freecad_handoff.py"

            FreeCADHandoffBuilder.write_json(json_path, payload)
            FreeCADHandoffBuilder.write_macro(macro_path)

            self.assertEqual(json.loads(json_path.read_text())["objects"][0]["label"], "Wall 1")
            macro = macro_path.read_text()
            self.assertIn("FreeCAD.newDocument", macro)
            self.assertIn("freecad_handoff.json", macro)
            self.assertIn("Part::Box", macro)

    def test_render_freecad_handoff_script_is_explicit_about_inputs(self) -> None:
        script = render_freecad_handoff_script(handoff_filename="handoff_payload.json")

        self.assertIn("handoff_payload.json", script)
        self.assertIn("build_document", script)
        self.assertIn("document.recompute()", script)


if __name__ == "__main__":
    unittest.main()
