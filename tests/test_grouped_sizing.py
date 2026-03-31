from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bonsai_ai.contracts import (
    DesignBrief,
    DesignPackage,
    MaterialSpec,
    PhysicalModelSpec,
    SectionSpec,
    StructuralSourceElement,
    StructuralSourceModel,
)
from bonsai_ai.grouped_sizing import _write_roundtripped_physical_outputs
from bonsai_ai.plan_roundtrip import apply_sized_sections_to_physical_model


class GroupedSizingOutputTests(unittest.TestCase):
    def test_writes_sized_physical_outputs(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="Sized outputs"),
            physical_model=PhysicalModelSpec(
                summary="Sized outputs",
                assumptions=[],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "summary": "Sized outputs",
                    "assumptions": [],
                    "actions": [
                        {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                        {
                            "type": "create_column",
                            "name": "Column A",
                            "storey": "Level 0",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.25,
                            "depth": 0.25,
                            "height": 4.0,
                            "semantics": {"element_id": "column_a"},
                        },
                    ],
                },
                authored_plan={
                    "version": "1.0",
                    "units": "meters",
                    "summary": "Sized outputs",
                    "assumptions": [],
                    "actions": [
                        {"type": "ensure_storey", "name": "Level 0", "elevation": 0.0},
                        {
                            "type": "create_column",
                            "name": "Column A",
                            "storey": "Level 0",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.25,
                            "depth": 0.25,
                            "height": 4.0,
                            "semantics": {"element_id": "column_a"},
                        },
                    ],
                },
                semantic_model={
                    "version": "1.0",
                    "units": "meters",
                    "summary": "Sized outputs",
                    "assumptions": [],
                    "assemblies": [],
                    "roots": [],
                    "metadata": {},
                    "elements": [
                        {
                            "id": "column_a",
                            "type": "create_column",
                            "name": "Column A",
                            "storey": "Level 0",
                            "parent_id": None,
                            "assembly_id": None,
                            "branch_path": ["Level 0"],
                            "selector_tags": [],
                            "action": {
                                "type": "create_column",
                                "name": "Column A",
                                "storey": "Level 0",
                                "x": 0.0,
                                "y": 0.0,
                                "base_z": 0.0,
                                "width": 0.25,
                                "depth": 0.25,
                                "height": 4.0,
                                "semantics": {"element_id": "column_a"},
                            },
                        }
                    ],
                },
            ),
        )
        source_model = StructuralSourceModel(
            materials=[MaterialSpec(id="steel_w_shapes", family="steel", model="elastic_isotropic")],
            sections=[
                SectionSpec(
                    id="catalog_primary_columns_w_w10x33",
                    kind="catalog_profile",
                    material_id="steel_w_shapes",
                    dimensions={"width": 0.210, "depth": 0.264},
                    metadata={"catalog_section_name": "W10X33"},
                )
            ],
            elements=[
                StructuralSourceElement(
                    id="column_a",
                    kind="column",
                    role="primary_column",
                    section_id="catalog_primary_columns_w_w10x33",
                    metadata={"source_name": "Column A"},
                )
            ],
        )

        apply_sized_sections_to_physical_model(package.physical_model, source_model)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = _write_roundtripped_physical_outputs(package, Path(tmpdir))

            paths = {Path(artifact.path).name for artifact in artifacts}
            self.assertIn("physical_model_sized_plan.json", paths)
            self.assertIn("physical_model_sized_authored_plan.json", paths)
            self.assertIn("physical_model_sized_semantic_model.json", paths)
            self.assertIn("physical_model_sized.ifc", paths)


if __name__ == "__main__":
    unittest.main()
