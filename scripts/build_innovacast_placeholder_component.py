from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bonsai_ai.analysis_exports import JsonAnalysisExportBackend
from bonsai_ai.contracts import (
    AnalysisDomain,
    AnalysisRequest,
    AnalyticalModel,
    DesignBrief,
    DesignPackage,
    LoadCase,
    MaterialSpec,
    PhysicalModelSpec,
    SectionSpec,
    StructuralElement,
)
from bonsai_ai.execution import IfcPhysicalModelBackend
from bonsai_ai.freecad_runner import run_freecad_handoff
from bonsai_ai.pipeline import DesignPipeline
from bonsai_ai.results_bundle import JsonResultsBundleBackend


FT_TO_M = 0.3048
IN_TO_M = 0.0254
FREECAD_CMD = "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"


def ft(value: float) -> float:
    return round(value * FT_TO_M, 6)


def inch(value: float) -> float:
    return round(value * IN_TO_M, 6)


def component_spec() -> dict:
    return {
        "component_id": "InnovaCast_Insulated_Cladding_Panel_v1",
        "component_family": "precast_insulated_cladding_panel",
        "version": "1.0",
        "units": "imperial_source_with_metric_exports",
        "geometry": {
            "default_width_ft": 12.0,
            "default_height_ft": 12.4,
            "max_width_ft": 12.0,
            "total_thickness_in": 7.5,
            "installed_orientation": "vertical",
        },
        "layer_stack": [
            {"name": "Exterior concrete wythe", "material": "concrete", "thickness_in": 2.25},
            {"name": "Foam core", "material": "foam", "thickness_in": 3.0},
            {"name": "Interior concrete wythe", "material": "concrete", "thickness_in": 2.25},
        ],
        "structural_basis": {
            "panel_dead_load_psf": {"min": 55.0, "max": 60.0, "status": "provisional"},
            "tested_panel_weight_psf": 50.0,
            "max_vertical_support_interval_ft": 16.58,
            "top_fastener_spacing_in": 24.0,
            "middle_girt_anchor_spacing_in": 30.0,
            "bottom_girt_anchor_spacing_in": 30.0,
            "fastener": "Buildex Large Diameter Tapcon+ 3/8 in x 3 in",
            "minimum_concrete_strength_psi": 4000,
        },
        "connection_details": {
            "top_clip": "ASTM A572 steel clip",
            "footing_mount": '4 in x 6 in x 7/16 in x 16 in L-angle x2',
            "bearing_requirement": "Panels bear on footings",
        },
        "limitations": [
            "Use as above-grade cladding only in this placeholder component package.",
            "Not validated as a 12-foot below-grade retaining wall component.",
            "Current cladding analysis states a maximum eave height of 40 feet.",
            "Roof pitch limitation in the report is 2:12 maximum.",
            "Differential backfill demand at the panel base must not exceed the report basis.",
        ],
        "source_documents": [
            "/Users/alanknudson/Downloads/InnovaCast Cladding Report of Analysis_12-2-25.pdf",
            "/Users/alanknudson/Downloads/T240-25-INNOVACAST FWC 090325.pdf",
            "/Users/alanknudson/Downloads/ICP DETAIL                                        88 S 6500 W CEDAR CITY, UTAH 84721.pdf",
        ],
    }


def build_component(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    spec = component_spec()
    (output_dir / "innovacast_icp_placeholder_component_spec.json").write_text(json.dumps(spec, indent=2))

    plan = {
        "version": "1.0",
        "units": "meters",
        "summary": "Placeholder InnovaCast insulated cladding panel component represented as two concrete wythes and a foam core gap.",
        "assumptions": list(spec["limitations"]),
        "actions": [
            {"type": "ensure_storey", "name": "Component Level", "elevation": 0.0},
            {
                "type": "create_wall",
                "name": "InnovaCast Exterior Wythe",
                "storey": "Component Level",
                "x1": 0.0,
                "y1": 0.0,
                "x2": ft(12.0),
                "y2": 0.0,
                "base_z": 0.0,
                "height": ft(12.4),
                "thickness": inch(2.25),
            },
            {
                "type": "create_wall",
                "name": "InnovaCast Interior Wythe",
                "storey": "Component Level",
                "x1": 0.0,
                "y1": inch(5.25),
                "x2": ft(12.0),
                "y2": inch(5.25),
                "base_z": 0.0,
                "height": ft(12.4),
                "thickness": inch(2.25),
            },
        ],
    }
    (output_dir / "component_plan.json").write_text(json.dumps(plan, indent=2))

    brief = DesignBrief(
        prompt="Reusable InnovaCast placeholder cladding panel component.",
        analysis_domains=[AnalysisDomain.GRAVITY],
        metadata={"component_id": spec["component_id"]},
    )
    physical_model = PhysicalModelSpec(summary=plan["summary"], assumptions=plan["assumptions"], plan=plan)
    package = DesignPackage(
        brief=brief,
        physical_model=physical_model,
        analysis_request=AnalysisRequest(
            solver="pynite",
            design_codes=["ASCE 7-22"],
            load_cases=[LoadCase(name="Gravity", domain=AnalysisDomain.GRAVITY, code_basis="ASCE 7-22")],
            export_options={"freecad_handoff": True},
        ),
        analytical_model=AnalyticalModel(
            materials=[
                MaterialSpec(
                    id="panel_concrete",
                    family="concrete",
                    model="elastic_isotropic",
                    properties={"density_kg_m3": 2400, "elastic_modulus_pa": 27_000_000_000, "poisson_ratio": 0.2},
                )
            ],
            sections=[
                SectionSpec(
                    id="innovacast_wythe_section",
                    kind="shell",
                    material_id="panel_concrete",
                    dimensions={"thickness": inch(2.25)},
                    metadata={
                        "component_id": spec["component_id"],
                        "representation": "dual_wythe_placeholder",
                    },
                )
            ],
            elements=[
                StructuralElement(
                    id="innovacast_exterior_wythe",
                    kind="wall",
                    section_id="innovacast_wythe_section",
                    geometry={
                        "start": [0.0, 0.0, 0.0],
                        "end": [ft(12.0), 0.0, 0.0],
                        "height": ft(12.4),
                        "thickness": inch(2.25),
                    },
                    metadata={
                        "source_name": "InnovaCast Exterior Wythe",
                        "component_id": spec["component_id"],
                        "layer": "exterior_wythe",
                    },
                ),
                StructuralElement(
                    id="innovacast_interior_wythe",
                    kind="wall",
                    section_id="innovacast_wythe_section",
                    geometry={
                        "start": [0.0, inch(5.25), 0.0],
                        "end": [ft(12.0), inch(5.25), 0.0],
                        "height": ft(12.4),
                        "thickness": inch(2.25),
                    },
                    metadata={
                        "source_name": "InnovaCast Interior Wythe",
                        "component_id": spec["component_id"],
                        "layer": "internal_wythe",
                    },
                ),
            ],
            load_cases=[LoadCase(name="Gravity", domain=AnalysisDomain.GRAVITY, code_basis="ASCE 7-22")],
            metadata={
                "summary": plan["summary"],
                "assumptions": list(plan["assumptions"]),
                "analysis_domains": [AnalysisDomain.GRAVITY.value],
                "component_id": spec["component_id"],
            },
        ),
    )

    package.physical_artifacts = list(IfcPhysicalModelBackend(filename="innovacast_icp_placeholder.ifc").materialize(package, output_dir))
    package.analysis_artifacts = list(JsonAnalysisExportBackend().export(package, output_dir))
    package.review_artifacts = list(run_freecad_handoff(output_dir, freecad_bin=FREECAD_CMD, timeout_seconds=120))
    package.results_artifacts = list(JsonResultsBundleBackend().build(package, output_dir))
    DesignPipeline.write_manifest(package, output_dir / "component_design_package.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(ROOT / "out" / "components" / "innovacast_icp_placeholder_v1"))
    args = parser.parse_args()
    build_component(Path(args.output_dir).resolve())


if __name__ == "__main__":
    main()
