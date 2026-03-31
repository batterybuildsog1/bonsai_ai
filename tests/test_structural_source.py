from __future__ import annotations

import unittest

from bonsai_ai.contracts import (
    AnalysisDomain,
    EngineeringModelScope,
    AnalysisProfile,
    AnalysisRequest,
    DesignBrief,
    DesignPackage,
    LoadCase,
    PhysicalModelSpec,
)
from bonsai_ai.load_path import build_load_path_model
from bonsai_ai.structural_source import StructuralAnalysisReducer, StructuralEngineeringModelEmitter, StructuralSourceModelBuilder
from bonsai_ai.system_layout import build_system_layout


class StructuralSourceTests(unittest.TestCase):
    def test_structural_source_builder_assigns_roles(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="Source build", analysis_domains=[AnalysisDomain.WIND]),
            physical_model=PhysicalModelSpec(
                summary="Source summary",
                assumptions=["role mapping"],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {
                            "type": "create_column",
                            "name": "corner_frame_column X000_Y000_Seg1",
                            "storey": "Level 1",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.5,
                            "depth": 0.5,
                            "height": 4.0,
                        },
                        {
                            "type": "create_column",
                            "name": "South Facade Post X010_Y000_Seg1",
                            "storey": "Level 1",
                            "x": 1.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.2,
                            "depth": 0.2,
                            "height": 4.0,
                        },
                        {
                            "type": "create_beam",
                            "name": "Roof Collector",
                            "storey": "Roof",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 5.0,
                            "y2": 0.0,
                            "base_z": 4.0,
                            "width": 0.3,
                            "depth": 0.6,
                            "member_role": "roof_collector",
                        },
                        {
                            "type": "create_beam",
                            "name": "Window 01 Header",
                            "storey": "Level 1",
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
                            "name": "Roof Plate",
                            "storey": "Roof",
                            "x": 0.0,
                            "y": 0.0,
                            "z": 4.0,
                            "width": 6.0,
                            "depth": 8.0,
                            "thickness": 0.2,
                        },
                    ],
                },
            ),
        )

        source = StructuralSourceModelBuilder().build(package)
        roles = {element.id: element.role for element in source.elements}
        families = {element.id: element.structural_family for element in source.elements}
        parents = {element.id: element.parent_id for element in source.elements}
        systems = {element.id: element.system_id for element in source.elements}
        zone_kinds = {element.id: element.layout_zone_kind for element in source.elements}
        interfaces = {element.id: element.interface_type for element in source.elements}
        self.assertEqual(roles["corner_frame_column_x000_y000_seg1"], "primary_column")
        self.assertEqual(roles["south_facade_post_x010_y000_seg1"], "facade_post")
        self.assertEqual(roles["roof_collector"], "roof_collector")
        self.assertEqual(roles["window_01_header"], "opening_header")
        self.assertEqual(roles["basement_retaining_west"], "retaining")
        self.assertEqual(roles["roof_plate"], "diaphragm")
        self.assertEqual(families["corner_frame_column_x000_y000_seg1"], "primary_frame")
        self.assertEqual(families["south_facade_post_x010_y000_seg1"], "facade_support")
        self.assertEqual(families["window_01_header"], "opening_support")
        self.assertEqual(families["basement_retaining_west"], "substructure")
        self.assertEqual(parents["window_01_header"], "opening:window_01")
        self.assertEqual(parents["basement_retaining_west"], "substructure:retaining_loop")
        self.assertEqual(systems["corner_frame_column_x000_y000_seg1"], "primary_frame_system")
        self.assertEqual(zone_kinds["window_01_header"], "opening_zone")
        self.assertEqual(interfaces["roof_collector"], "collector_transfer")
        self.assertEqual(len(source.supports), 1)
        self.assertEqual(source.supports[0].target_id, "corner_frame_column_x000_y000_seg1")
        self.assertIn("primary_frame", source.metadata["family_counts"])
        self.assertIn("primary_frame_system", source.metadata["system_counts"])
        self.assertIn("frame_line", source.metadata["zone_kind_counts"])

    def test_structural_source_builder_prefers_semantic_ids_and_assemblies(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="Semantic ids", analysis_domains=[AnalysisDomain.WIND]),
            physical_model=PhysicalModelSpec(
                summary="Semantic ids",
                assumptions=[],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {
                            "type": "create_column",
                            "name": "Primary Column Raw",
                            "storey": "Level 1",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.5,
                            "depth": 0.5,
                            "height": 4.0,
                            "semantics": {
                                "element_id": "column:grid_a1",
                                "parent_id": "frame_line:grid_a",
                                "assembly_id": "frame_line:grid_a",
                                "system_name": "Primary Frame",
                                "role": "primary_column",
                            },
                        },
                        {
                            "type": "create_footing",
                            "name": "Footing Raw",
                            "storey": "Foundations",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": -1.2,
                            "length": 2.4,
                            "width": 2.4,
                            "thickness": 0.75,
                            "semantics": {
                                "element_id": "footing:grid_a1",
                                "parent_id": "subgrade:spread_footings",
                                "assembly_id": "subgrade:spread_footings",
                                "system_name": "Subgrade Spread Footings",
                                "role": "foundation",
                            },
                            "foundation": {
                                "imposed_load_kN": 850.0,
                                "rebar_weight_kg": 190.0,
                            },
                        },
                    ],
                },
            ),
        )

        source = StructuralSourceModelBuilder().build(package)
        element_index = {element.id: element for element in source.elements}
        column = element_index["column:grid_a1"]
        footing = element_index["footing:grid_a1"]

        self.assertEqual(column.parent_id, "frame_line:grid_a")
        self.assertEqual(column.assembly_id, "frame_line:grid_a")
        self.assertEqual(column.system_id, "system:primary_frame")
        self.assertEqual(footing.parent_id, "subgrade:spread_footings")
        self.assertEqual(footing.assembly_id, "subgrade:spread_footings")
        self.assertEqual(footing.system_id, "system:subgrade_spread_footings")
        self.assertEqual(footing.metadata["imposed_load_kN"], 850.0)
        self.assertEqual(footing.metadata["rebar_weight_kg"], 190.0)

    def test_structural_source_builder_carries_semantic_branch_lineage(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="Semantic lineage", analysis_domains=[AnalysisDomain.WIND]),
            physical_model=PhysicalModelSpec(
                summary="Semantic lineage",
                assumptions=[],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {
                            "type": "create_column",
                            "name": "Column Raw",
                            "storey": "Level 1",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.4,
                            "depth": 0.4,
                            "height": 4.0,
                            "semantics": {"element_id": "column_a"},
                        }
                    ],
                },
                semantic_model={
                    "version": "1.0",
                    "units": "meters",
                    "summary": "Semantic lineage",
                    "assumptions": [],
                    "assemblies": [
                        {
                            "id": "assembly:frame_line_a",
                            "name": "frame_line_a",
                            "kind": "assembly",
                            "parent_id": "branch:level-1-structure-primary",
                            "branch_path": ["Level 1", "Structure", "Primary"],
                            "children_ids": [],
                            "element_ids": ["column_a"],
                            "metadata": {},
                        }
                    ],
                    "roots": ["branch:level-1"],
                    "metadata": {"element_count": 1, "assembly_count": 1, "root_count": 1},
                    "elements": [
                        {
                            "id": "column_a",
                            "type": "create_column",
                            "name": "Column Raw",
                            "storey": "Level 1",
                            "parent_id": "frame_line_a",
                            "assembly_id": "primary_frame_a",
                            "branch_path": ["Level 1", "Structure", "Primary"],
                            "selector_tags": ["primary"],
                            "action": {
                                "type": "create_column",
                                "name": "Column Raw",
                                "storey": "Level 1",
                                "x": 0.0,
                                "y": 0.0,
                                "base_z": 0.0,
                                "width": 0.4,
                                "depth": 0.4,
                                "height": 4.0,
                                "semantics": {
                                    "element_id": "column_a",
                                    "role": "primary_column",
                                    "system_name": "Primary Frame",
                                    "parent_id": "frame_line_a",
                                    "assembly_id": "primary_frame_a",
                                },
                            },
                        }
                    ],
                },
            ),
        )

        source = StructuralSourceModelBuilder().build(package)
        column = next(element for element in source.elements if element.id == "column_a")

        self.assertEqual(column.parent_id, "frame_line_a")
        self.assertEqual(column.assembly_id, "primary_frame_a")
        self.assertEqual(column.system_id, "system:primary_frame")
        self.assertEqual(column.metadata["semantic_branch_path"], ["Level 1", "Structure", "Primary"])
        self.assertTrue(column.metadata["semantic_record_present"])
        self.assertEqual(source.metadata["semantic_model_element_count"], 1)
        self.assertEqual(source.metadata["semantic_model_assembly_count"], 1)

    def test_reducer_emits_profile_specific_models(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="Reduce", analysis_domains=[AnalysisDomain.WIND]),
            physical_model=PhysicalModelSpec(
                summary="Reduce summary",
                assumptions=["profiles"],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {
                            "type": "create_column",
                            "name": "Main Column",
                            "storey": "Level 1",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.5,
                            "depth": 0.5,
                            "height": 5.0,
                        },
                        {
                            "type": "create_beam",
                            "name": "Brace A",
                            "storey": "Level 1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 0.0,
                            "end_z": 5.0,
                            "width": 0.2,
                            "depth": 0.2,
                            "member_role": "brace",
                        },
                        {
                            "type": "create_beam",
                            "name": "Perimeter Spandrel",
                            "storey": "Level 1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 5.0,
                            "width": 0.2,
                            "depth": 0.4,
                            "member_role": "perimeter_spandrel",
                        },
                        {
                            "type": "create_wall",
                            "name": "Facade Wall",
                            "storey": "Level 1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 0.0,
                            "height": 5.0,
                            "thickness": 0.2,
                        },
                    ],
                },
            ),
            analysis_request=AnalysisRequest(
                solver="pynite",
                design_codes=["ASCE 7-22"],
                load_cases=[LoadCase(name="Wind X+", domain=AnalysisDomain.WIND, code_basis="ASCE 7-22", parameters={"pressure_kpa": 1.2})],
            ),
        )
        source = StructuralSourceModelBuilder().build(package)
        load_path_model = build_load_path_model(source, build_system_layout(source))
        reducer = StructuralAnalysisReducer()

        fast_model = reducer.reduce(source, AnalysisProfile.GLOBAL_FAST, package.analysis_request, summary="", assumptions=[], analysis_domains=[], source_plan_version="1.0", load_path_model=load_path_model)
        full_model = reducer.reduce(source, AnalysisProfile.GLOBAL_FULL, package.analysis_request, summary="", assumptions=[], analysis_domains=[], source_plan_version="1.0", load_path_model=load_path_model)
        facade_model = reducer.reduce(source, AnalysisProfile.FACADE_SUPPORT, package.analysis_request, summary="", assumptions=[], analysis_domains=[], source_plan_version="1.0", load_path_model=load_path_model)

        self.assertEqual({element.kind for element in fast_model.elements}, {"beam", "column"})
        self.assertIn("wall", {element.kind for element in full_model.elements})
        self.assertIn("beam", {element.kind for element in facade_model.elements})
        self.assertEqual(fast_model.metadata["analysis_profile"], "global_fast")
        self.assertEqual(full_model.load_cases[0].actions[0].kind, "pressure")
        self.assertEqual(fast_model.load_cases[0].actions[0].kind, "point_load")
        self.assertEqual(full_model.load_cases[0].actions[0].metadata["source"], "load_path_wind_surface")
        self.assertEqual(fast_model.load_cases[0].actions[0].metadata["source"], "load_path_wind_collector")
        fast_roles = {element.metadata["analysis_role"] for element in fast_model.elements}
        self.assertIn("primary_column", fast_roles)
        self.assertIn("brace", fast_roles)
        self.assertIn("perimeter_spandrel", {element.metadata["analysis_role"] for element in facade_model.elements})
        fast_element = next(element for element in fast_model.elements if element.id == "main_column")
        self.assertEqual(fast_element.metadata["system_id"], "primary_frame_system")
        self.assertEqual(fast_element.metadata["layout_zone_kind"], "frame_line")

    def test_structural_source_builder_uses_semantic_model_records_when_present(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="Semantic handoff"),
            physical_model=PhysicalModelSpec(
                summary="Semantic handoff summary",
                assumptions=[],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {
                            "type": "create_column",
                            "name": "Column A",
                            "storey": "Level 1",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.4,
                            "depth": 0.4,
                            "height": 4.0,
                            "semantics": {"element_id": "column_a"},
                        }
                    ],
                },
                semantic_model={
                    "version": "1.0",
                    "units": "meters",
                    "summary": "Semantic handoff summary",
                    "assumptions": [],
                    "roots": ["branch:level-1-structure"],
                    "metadata": {"element_count": 1, "assembly_count": 2, "root_count": 1},
                    "assemblies": [],
                    "elements": [
                        {
                            "id": "column_a",
                            "type": "create_column",
                            "name": "Column A",
                            "storey": "Level 1",
                            "parent_id": "frame_line:grid_a",
                            "assembly_id": "primary_frame:grid_a",
                            "branch_path": ["Level 1", "Structure", "Grid A"],
                            "selector_tags": ["primary"],
                            "action": {
                                "type": "create_column",
                                "name": "Column A",
                                "storey": "Level 1",
                                "x": 0.0,
                                "y": 0.0,
                                "base_z": 0.0,
                                "width": 0.4,
                                "depth": 0.4,
                                "height": 4.0,
                                "semantics": {
                                    "element_id": "column_a",
                                    "role": "primary_column",
                                    "system_name": "Primary Frame",
                                    "parent_id": "frame_line:grid_a",
                                    "assembly_id": "primary_frame:grid_a",
                                    "group_path": ["Structure", "Grid A"],
                                },
                            },
                        }
                    ],
                },
            ),
        )

        source = StructuralSourceModelBuilder().build(package)

        column = source.elements[0]
        self.assertEqual(column.parent_id, "frame_line:grid_a")
        self.assertEqual(column.assembly_id, "primary_frame:grid_a")
        self.assertEqual(column.system_id, "system:primary_frame")
        self.assertEqual(source.metadata["semantic_model_element_count"], 1)
        self.assertEqual(source.metadata["semantic_model_assembly_count"], 2)

    def test_engineering_model_emitter_scopes(self) -> None:
        package = DesignPackage(
            brief=DesignBrief(prompt="Emit engineering models", analysis_domains=[AnalysisDomain.WIND]),
            physical_model=PhysicalModelSpec(
                summary="Emitter summary",
                assumptions=["engineering scopes"],
                plan={
                    "version": "1.0",
                    "units": "meters",
                    "actions": [
                        {
                            "type": "create_column",
                            "name": "corner_frame_column X000_Y000_Seg1",
                            "storey": "Level 1",
                            "x": 0.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.5,
                            "depth": 0.5,
                            "height": 5.0,
                        },
                        {
                            "type": "create_column",
                            "name": "South Facade Post X010_Y000_Seg1",
                            "storey": "Level 1",
                            "x": 1.0,
                            "y": 0.0,
                            "base_z": 0.0,
                            "width": 0.2,
                            "depth": 0.2,
                            "height": 5.0,
                        },
                        {
                            "type": "create_beam",
                            "name": "Roof Primary",
                            "storey": "Roof",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 5.0,
                            "y2": 0.0,
                            "base_z": 5.0,
                            "width": 0.3,
                            "depth": 0.6,
                            "member_role": "roof_primary_frame",
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
                            "name": "Brace A",
                            "storey": "Level 1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 0.0,
                            "end_z": 5.0,
                            "width": 0.2,
                            "depth": 0.2,
                            "member_role": "brace",
                        },
                        {
                            "type": "create_beam",
                            "name": "Window Header",
                            "storey": "Level 1",
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
                            "name": "Facade Wall",
                            "storey": "Level 1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "base_z": 0.0,
                            "height": 5.0,
                            "thickness": 0.2,
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
                            "name": "Foundation Slab",
                            "storey": "Basement",
                            "x": 0.0,
                            "y": 0.0,
                            "z": -3.0,
                            "width": 6.0,
                            "depth": 8.0,
                            "thickness": 0.25,
                        },
                    ],
                },
            ),
        )
        source = StructuralSourceModelBuilder().build(package)
        emitter = StructuralEngineeringModelEmitter()

        global_frame = emitter.emit(source, EngineeringModelScope.GLOBAL_FRAME, summary="", assumptions=[], source_plan_version="1.0")
        facade = emitter.emit(source, EngineeringModelScope.FACADE_SUPPORT, summary="", assumptions=[], source_plan_version="1.0")
        substructure = emitter.emit(source, EngineeringModelScope.SUBSTRUCTURE, summary="", assumptions=[], source_plan_version="1.0")
        opening_support = emitter.emit(source, EngineeringModelScope.OPENING_SUPPORT, summary="", assumptions=[], source_plan_version="1.0")

        self.assertEqual(global_frame.scope, "global_frame")
        self.assertIn("brace", {element.metadata["analysis_role"] for element in global_frame.elements})
        self.assertNotIn("opening_header", {element.metadata["analysis_role"] for element in global_frame.elements})
        self.assertTrue(global_frame.metadata["standalone_ready"])
        self.assertGreater(global_frame.metadata["support_count"], 0)
        self.assertIn("primary_frame", global_frame.metadata["family_counts"])
        self.assertGreater(global_frame.metadata["parent_count"], 0)
        self.assertIn("facade_post", {element.metadata["analysis_role"] for element in facade.elements})
        self.assertIn("opening_header", {element.metadata["analysis_role"] for element in facade.elements})
        self.assertTrue(facade.metadata["standalone_ready"])
        self.assertIn("facade_support", facade.metadata["family_counts"])
        self.assertIn("retaining", {element.metadata["analysis_role"] for element in substructure.elements})
        self.assertIn("foundation", {element.metadata["analysis_role"] for element in substructure.elements})
        self.assertTrue(substructure.metadata["standalone_ready"])
        self.assertIn("substructure", substructure.metadata["family_counts"])
        self.assertFalse(opening_support.metadata["standalone_ready"])
        self.assertEqual(opening_support.metadata["support_expectation"], "derived_from_parent")
        self.assertIn("parent engineering model", opening_support.metadata["warnings"][0])


if __name__ == "__main__":
    unittest.main()
