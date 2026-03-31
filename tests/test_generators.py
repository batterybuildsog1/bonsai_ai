import math
import unittest

from bonsai_ai_core.compiler import compile_plan


def _base_plan(actions):
    return {
        "version": "1.0",
        "units": "meters",
        "summary": "Generator test",
        "assumptions": [],
        "actions": [{"type": "ensure_storey", "name": "Level 0", "elevation": 0.0}] + actions,
    }


class GenerateColumnGridTests(unittest.TestCase):
    def test_basic_2x2_grid_produces_9_columns(self):
        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Grid-A",
                "storey": "Level 0",
                "grid_origin_x": 0.0,
                "grid_origin_y": 0.0,
                "base_z": 0.0,
                "bays_x": 2,
                "bays_y": 2,
                "spacing_x": 8.0,
                "spacing_y": 10.0,
                "column_width": 0.3,
                "column_depth": 0.3,
                "column_height": 4.0,
                "semantics": {"role": "structure", "group_path": ["Structure"]},
            }
        ])
        compiled = compile_plan(plan)
        columns = [a for a in compiled["actions"] if a["type"] == "create_column"]
        self.assertEqual(len(columns), 9)  # (2+1) * (2+1)

    def test_column_coordinates(self):
        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Grid-B",
                "storey": "Level 0",
                "grid_origin_x": 5.0,
                "grid_origin_y": 10.0,
                "base_z": 0.0,
                "bays_x": 1,
                "bays_y": 1,
                "spacing_x": 6.0,
                "spacing_y": 8.0,
                "column_width": 0.4,
                "column_depth": 0.4,
                "column_height": 3.5,
            }
        ])
        compiled = compile_plan(plan)
        columns = [a for a in compiled["actions"] if a["type"] == "create_column"]
        self.assertEqual(len(columns), 4)  # (1+1) * (1+1)

        # Verify coordinates
        coords = sorted([(c["x"], c["y"]) for c in columns])
        expected = sorted([
            (5.0, 10.0),   # A1
            (11.0, 10.0),  # A2
            (5.0, 18.0),   # B1
            (11.0, 18.0),  # B2
        ])
        self.assertEqual(coords, expected)

    def test_column_naming_convention(self):
        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Main Grid",
                "storey": "Level 0",
                "grid_origin_x": 0.0,
                "grid_origin_y": 0.0,
                "base_z": 0.0,
                "bays_x": 1,
                "bays_y": 1,
                "spacing_x": 8.0,
                "spacing_y": 8.0,
                "column_width": 0.3,
                "column_depth": 0.3,
                "column_height": 4.0,
            }
        ])
        compiled = compile_plan(plan)
        columns = [a for a in compiled["actions"] if a["type"] == "create_column"]
        names = [c["name"] for c in columns]
        self.assertIn("Main Grid-Col-A1", names)
        self.assertIn("Main Grid-Col-A2", names)
        self.assertIn("Main Grid-Col-B1", names)
        self.assertIn("Main Grid-Col-B2", names)

    def test_column_semantics_propagation(self):
        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Grid-C",
                "storey": "Level 0",
                "grid_origin_x": 0.0,
                "grid_origin_y": 0.0,
                "base_z": 0.0,
                "bays_x": 1,
                "bays_y": 0,
                "spacing_x": 6.0,
                "spacing_y": 6.0,
                "column_width": 0.3,
                "column_depth": 0.3,
                "column_height": 4.0,
                "semantics": {"element_id": "primary_grid", "role": "structure", "group_path": ["Structure"]},
            }
        ])
        compiled = compile_plan(plan)
        columns = [a for a in compiled["actions"] if a["type"] == "create_column"]
        self.assertEqual(len(columns), 2)
        col = columns[0]
        self.assertEqual(col["semantics"]["parent_id"], "primary_grid")
        self.assertEqual(col["semantics"]["assembly_id"], "primary_grid")
        self.assertIn("Columns", col["semantics"]["group_path"])

    def test_column_grid_with_rotation(self):
        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Rotated Grid",
                "storey": "Level 0",
                "grid_origin_x": 0.0,
                "grid_origin_y": 0.0,
                "base_z": 0.0,
                "bays_x": 1,
                "bays_y": 0,
                "spacing_x": 6.0,
                "spacing_y": 6.0,
                "column_width": 0.3,
                "column_depth": 0.3,
                "column_height": 4.0,
                "rotation_deg": 45.0,
            }
        ])
        compiled = compile_plan(plan)
        columns = [a for a in compiled["actions"] if a["type"] == "create_column"]
        self.assertEqual(columns[0]["rotation_deg"], 45.0)

    def test_large_grid_count(self):
        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Large Grid",
                "storey": "Level 0",
                "grid_origin_x": 0.0,
                "grid_origin_y": 0.0,
                "base_z": 0.0,
                "bays_x": 5,
                "bays_y": 3,
                "spacing_x": 8.0,
                "spacing_y": 10.0,
                "column_width": 0.3,
                "column_depth": 0.3,
                "column_height": 4.0,
            }
        ])
        compiled = compile_plan(plan)
        columns = [a for a in compiled["actions"] if a["type"] == "create_column"]
        self.assertEqual(len(columns), 24)  # (5+1) * (3+1)


class GeneratePerimeterWallsTests(unittest.TestCase):
    def test_rectangle_produces_4_walls(self):
        plan = _base_plan([
            {
                "type": "generate_perimeter_walls",
                "name": "Perimeter",
                "storey": "Level 0",
                "corners": [[0, 0], [20, 0], [20, 15], [0, 15]],
                "base_z": 0.0,
                "height": 4.0,
                "thickness": 0.2,
            }
        ])
        compiled = compile_plan(plan)
        walls = [a for a in compiled["actions"] if a["type"] == "create_wall"]
        self.assertEqual(len(walls), 4)

    def test_wall_coordinates_form_closed_loop(self):
        corners = [[0, 0], [10, 0], [10, 10], [0, 10]]
        plan = _base_plan([
            {
                "type": "generate_perimeter_walls",
                "name": "Box",
                "storey": "Level 0",
                "corners": corners,
                "base_z": 0.0,
                "height": 3.0,
                "thickness": 0.15,
            }
        ])
        compiled = compile_plan(plan)
        walls = [a for a in compiled["actions"] if a["type"] == "create_wall"]

        # First wall: corner 0 -> corner 1
        self.assertEqual(walls[0]["x1"], 0.0)
        self.assertEqual(walls[0]["y1"], 0.0)
        self.assertEqual(walls[0]["x2"], 10.0)
        self.assertEqual(walls[0]["y2"], 0.0)

        # Last wall: corner 3 -> corner 0 (closes the loop)
        self.assertEqual(walls[3]["x1"], 0.0)
        self.assertEqual(walls[3]["y1"], 10.0)
        self.assertEqual(walls[3]["x2"], 0.0)
        self.assertEqual(walls[3]["y2"], 0.0)

    def test_wall_naming(self):
        plan = _base_plan([
            {
                "type": "generate_perimeter_walls",
                "name": "Envelope",
                "storey": "Level 0",
                "corners": [[0, 0], [5, 0], [5, 5]],
                "base_z": 0.0,
                "height": 3.0,
                "thickness": 0.2,
            }
        ])
        compiled = compile_plan(plan)
        walls = [a for a in compiled["actions"] if a["type"] == "create_wall"]
        self.assertEqual(len(walls), 3)
        self.assertEqual(walls[0]["name"], "Envelope-Seg-01")
        self.assertEqual(walls[1]["name"], "Envelope-Seg-02")
        self.assertEqual(walls[2]["name"], "Envelope-Seg-03")

    def test_wall_semantics(self):
        plan = _base_plan([
            {
                "type": "generate_perimeter_walls",
                "name": "Walls",
                "storey": "Level 0",
                "corners": [[0, 0], [10, 0], [10, 10], [0, 10]],
                "base_z": 0.0,
                "height": 3.0,
                "thickness": 0.2,
                "semantics": {"element_id": "perim_walls", "role": "envelope"},
            }
        ])
        compiled = compile_plan(plan)
        walls = [a for a in compiled["actions"] if a["type"] == "create_wall"]
        wall = walls[0]
        self.assertEqual(wall["semantics"]["parent_id"], "perim_walls")
        self.assertEqual(wall["semantics"]["subrole"], "perimeter_wall")
        self.assertIn("Walls", wall["semantics"]["group_path"])


class GenerateFloorPlateTests(unittest.TestCase):
    def test_slab_only(self):
        plan = _base_plan([
            {
                "type": "generate_floor_plate",
                "name": "Floor L1",
                "storey": "Level 0",
                "x": 0.0,
                "y": 0.0,
                "z": 4.0,
                "length": 20.0,
                "width": 15.0,
                "thickness": 0.2,
            }
        ])
        compiled = compile_plan(plan)
        slabs = [a for a in compiled["actions"] if a["type"] == "create_rect_slab"]
        beams = [a for a in compiled["actions"] if a["type"] == "create_beam"]
        self.assertEqual(len(slabs), 1)
        self.assertEqual(len(beams), 0)
        self.assertEqual(slabs[0]["name"], "Floor L1-Slab")
        self.assertEqual(slabs[0]["z"], 4.0)
        self.assertEqual(slabs[0]["width"], 20.0)  # length maps to slab width
        self.assertEqual(slabs[0]["depth"], 15.0)  # width maps to slab depth

    def test_slab_with_edge_beams(self):
        plan = _base_plan([
            {
                "type": "generate_floor_plate",
                "name": "Floor L1",
                "storey": "Level 0",
                "x": 0.0,
                "y": 0.0,
                "z": 4.0,
                "length": 20.0,
                "width": 15.0,
                "thickness": 0.2,
                "include_edge_beams": True,
                "beam_width": 0.3,
                "beam_depth": 0.5,
            }
        ])
        compiled = compile_plan(plan)
        slabs = [a for a in compiled["actions"] if a["type"] == "create_rect_slab"]
        beams = [a for a in compiled["actions"] if a["type"] == "create_beam"]
        self.assertEqual(len(slabs), 1)
        self.assertEqual(len(beams), 4)

    def test_edge_beam_coordinates_no_rotation(self):
        plan = _base_plan([
            {
                "type": "generate_floor_plate",
                "name": "Floor",
                "storey": "Level 0",
                "x": 0.0,
                "y": 0.0,
                "z": 4.0,
                "length": 10.0,
                "width": 5.0,
                "thickness": 0.2,
                "include_edge_beams": True,
                "beam_width": 0.2,
                "beam_depth": 0.4,
            }
        ])
        compiled = compile_plan(plan)
        beams = [a for a in compiled["actions"] if a["type"] == "create_beam"]
        self.assertEqual(len(beams), 4)

        # South beam: (0,0) -> (10,0)
        south = next(b for b in beams if "South" in b["name"])
        self.assertAlmostEqual(south["x1"], 0.0)
        self.assertAlmostEqual(south["y1"], 0.0)
        self.assertAlmostEqual(south["x2"], 10.0)
        self.assertAlmostEqual(south["y2"], 0.0)

        # East beam: (10,0) -> (10,5)
        east = next(b for b in beams if "East" in b["name"])
        self.assertAlmostEqual(east["x1"], 10.0)
        self.assertAlmostEqual(east["y1"], 0.0)
        self.assertAlmostEqual(east["x2"], 10.0)
        self.assertAlmostEqual(east["y2"], 5.0)

        # North beam: (10,5) -> (0,5)
        north = next(b for b in beams if "North" in b["name"])
        self.assertAlmostEqual(north["x1"], 10.0)
        self.assertAlmostEqual(north["y1"], 5.0)
        self.assertAlmostEqual(north["x2"], 0.0)
        self.assertAlmostEqual(north["y2"], 5.0)

        # West beam: (0,5) -> (0,0)
        west = next(b for b in beams if "West" in b["name"])
        self.assertAlmostEqual(west["x1"], 0.0)
        self.assertAlmostEqual(west["y1"], 5.0)
        self.assertAlmostEqual(west["x2"], 0.0)
        self.assertAlmostEqual(west["y2"], 0.0)

    def test_floor_plate_semantics(self):
        plan = _base_plan([
            {
                "type": "generate_floor_plate",
                "name": "Floor",
                "storey": "Level 0",
                "x": 0.0,
                "y": 0.0,
                "z": 4.0,
                "length": 10.0,
                "width": 5.0,
                "thickness": 0.2,
                "include_edge_beams": True,
                "beam_width": 0.2,
                "beam_depth": 0.4,
                "semantics": {"element_id": "floor_1", "group_path": ["Structure"]},
            }
        ])
        compiled = compile_plan(plan)
        slabs = [a for a in compiled["actions"] if a["type"] == "create_rect_slab"]
        beams = [a for a in compiled["actions"] if a["type"] == "create_beam"]
        self.assertEqual(slabs[0]["semantics"]["parent_id"], "floor_1")
        self.assertEqual(slabs[0]["semantics"]["subrole"], "floor_slab")
        self.assertIn("Slabs", slabs[0]["semantics"]["group_path"])
        self.assertEqual(beams[0]["semantics"]["parent_id"], "floor_1")
        self.assertEqual(beams[0]["semantics"]["subrole"], "edge_beam")
        self.assertIn("Beams", beams[0]["semantics"]["group_path"])


class GenerateFacadeGridTests(unittest.TestCase):
    def test_produces_curtain_wall(self):
        plan = _base_plan([
            {
                "type": "generate_facade_grid",
                "name": "North Facade",
                "storey": "Level 0",
                "start_x": 0.0,
                "start_y": 15.0,
                "end_x": 20.0,
                "end_y": 15.0,
                "base_z": 0.0,
                "height": 4.0,
                "panel_width": 1.5,
                "panel_height": 1.2,
                "panel_thickness": 0.05,
            }
        ])
        compiled = compile_plan(plan)
        curtains = [a for a in compiled["actions"] if a["type"] == "create_curtain_wall"]
        self.assertEqual(len(curtains), 1)
        cw = curtains[0]
        self.assertEqual(cw["name"], "North Facade")
        self.assertEqual(cw["x1"], 0.0)
        self.assertEqual(cw["y1"], 15.0)
        self.assertEqual(cw["x2"], 20.0)
        self.assertEqual(cw["y2"], 15.0)
        self.assertEqual(cw["base_z"], 0.0)
        self.assertEqual(cw["top_z"], 4.0)
        self.assertEqual(cw["panel_width"], 1.5)
        self.assertEqual(cw["panel_height"], 1.2)
        self.assertEqual(cw["thickness"], 0.05)

    def test_facade_grid_semantics(self):
        plan = _base_plan([
            {
                "type": "generate_facade_grid",
                "name": "South Facade",
                "storey": "Level 0",
                "start_x": 0.0,
                "start_y": 0.0,
                "end_x": 20.0,
                "end_y": 0.0,
                "base_z": 0.0,
                "height": 4.0,
                "panel_width": 1.5,
                "panel_height": 1.2,
                "panel_thickness": 0.05,
                "semantics": {"role": "envelope", "group_path": ["Envelope"]},
            }
        ])
        compiled = compile_plan(plan)
        curtain = [a for a in compiled["actions"] if a["type"] == "create_curtain_wall"][0]
        self.assertEqual(curtain["semantics"]["subrole"], "facade_curtain_wall")
        self.assertIn("Curtain Walls", curtain["semantics"]["group_path"])

    def test_facade_with_rotation(self):
        plan = _base_plan([
            {
                "type": "generate_facade_grid",
                "name": "Angled Facade",
                "storey": "Level 0",
                "start_x": 0.0,
                "start_y": 0.0,
                "end_x": 10.0,
                "end_y": 0.0,
                "base_z": 0.0,
                "height": 3.0,
                "panel_width": 1.0,
                "panel_height": 1.0,
                "panel_thickness": 0.04,
                "rotation_degrees": 30.0,
            }
        ])
        compiled = compile_plan(plan)
        curtain = [a for a in compiled["actions"] if a["type"] == "create_curtain_wall"][0]
        self.assertEqual(curtain["rotation_degrees"], 30.0)


class IntegrationTests(unittest.TestCase):
    """Test that generators compose correctly with other actions in a plan."""

    def test_full_building_skeleton(self):
        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Structure",
                "storey": "Level 0",
                "grid_origin_x": 0.0,
                "grid_origin_y": 0.0,
                "base_z": 0.0,
                "bays_x": 2,
                "bays_y": 1,
                "spacing_x": 8.0,
                "spacing_y": 10.0,
                "column_width": 0.3,
                "column_depth": 0.3,
                "column_height": 4.0,
            },
            {
                "type": "generate_floor_plate",
                "name": "Floor L1",
                "storey": "Level 0",
                "x": 0.0,
                "y": 0.0,
                "z": 4.0,
                "length": 16.0,
                "width": 10.0,
                "thickness": 0.2,
            },
            {
                "type": "generate_perimeter_walls",
                "name": "Envelope",
                "storey": "Level 0",
                "corners": [[0, 0], [16, 0], [16, 10], [0, 10]],
                "base_z": 0.0,
                "height": 4.0,
                "thickness": 0.2,
            },
        ])
        compiled = compile_plan(plan)
        columns = [a for a in compiled["actions"] if a["type"] == "create_column"]
        slabs = [a for a in compiled["actions"] if a["type"] == "create_rect_slab"]
        walls = [a for a in compiled["actions"] if a["type"] == "create_wall"]
        self.assertEqual(len(columns), 6)  # (2+1) * (1+1)
        self.assertEqual(len(slabs), 1)
        self.assertEqual(len(walls), 4)

    def test_generators_mixed_with_individual_actions(self):
        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Grid",
                "storey": "Level 0",
                "grid_origin_x": 0.0,
                "grid_origin_y": 0.0,
                "base_z": 0.0,
                "bays_x": 1,
                "bays_y": 1,
                "spacing_x": 8.0,
                "spacing_y": 8.0,
                "column_width": 0.3,
                "column_depth": 0.3,
                "column_height": 4.0,
            },
            {
                "type": "create_beam",
                "name": "Transfer Beam",
                "storey": "Level 0",
                "x1": 0.0,
                "y1": 4.0,
                "x2": 8.0,
                "y2": 4.0,
                "base_z": 4.0,
                "width": 0.4,
                "depth": 0.6,
            },
        ])
        compiled = compile_plan(plan)
        columns = [a for a in compiled["actions"] if a["type"] == "create_column"]
        beams = [a for a in compiled["actions"] if a["type"] == "create_beam"]
        self.assertEqual(len(columns), 4)
        self.assertEqual(len(beams), 1)
        self.assertEqual(beams[0]["name"], "Transfer Beam")


class ValidationTests(unittest.TestCase):
    """Test that validation catches bad generator inputs."""

    def test_column_grid_missing_bays(self):
        from bonsai_ai_core.schema import validate_plan
        from bonsai_ai_core.errors import ValidationError

        plan = _base_plan([
            {
                "type": "generate_column_grid",
                "name": "Bad Grid",
                "storey": "Level 0",
                "grid_origin_x": 0.0,
                "grid_origin_y": 0.0,
                "base_z": 0.0,
                "spacing_x": 8.0,
                "spacing_y": 10.0,
                "column_width": 0.3,
                "column_depth": 0.3,
                "column_height": 4.0,
            }
        ])
        with self.assertRaises(ValidationError):
            validate_plan(plan)

    def test_perimeter_walls_too_few_corners(self):
        from bonsai_ai_core.schema import validate_plan
        from bonsai_ai_core.errors import ValidationError

        plan = _base_plan([
            {
                "type": "generate_perimeter_walls",
                "name": "Bad Walls",
                "storey": "Level 0",
                "corners": [[0, 0], [10, 0]],
                "base_z": 0.0,
                "height": 3.0,
                "thickness": 0.2,
            }
        ])
        with self.assertRaises(ValidationError):
            validate_plan(plan)

    def test_floor_plate_beams_without_dimensions(self):
        from bonsai_ai_core.schema import validate_plan
        from bonsai_ai_core.errors import ValidationError

        plan = _base_plan([
            {
                "type": "generate_floor_plate",
                "name": "Bad Floor",
                "storey": "Level 0",
                "x": 0.0,
                "y": 0.0,
                "z": 4.0,
                "length": 10.0,
                "width": 5.0,
                "thickness": 0.2,
                "include_edge_beams": True,
            }
        ])
        with self.assertRaises(ValidationError):
            validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
