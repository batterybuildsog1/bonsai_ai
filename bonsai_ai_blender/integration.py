"""Blender/Bonsai execution helpers."""

from __future__ import annotations

import importlib
import json
import math
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import bpy
import ifcopenshell.api.geometry
import ifcopenshell.api.spatial
import ifcopenshell.util.representation
from mathutils import Matrix, Vector


_BONSAI_RUNTIME: SimpleNamespace | None = None


def _load_bonsai_runtime() -> SimpleNamespace:
    global _BONSAI_RUNTIME
    if _BONSAI_RUNTIME is not None:
        return _BONSAI_RUNTIME

    _BONSAI_RUNTIME = SimpleNamespace(
        core_geometry=importlib.import_module("bonsai.core.geometry"),
        core_root=importlib.import_module("bonsai.core.root"),
        tool=importlib.import_module("bonsai.tool"),
    )
    return _BONSAI_RUNTIME


class BonsaiAIExecutor:
    def __init__(self, auto_create_project: bool = True):
        self.auto_create_project = auto_create_project
        self.created: List[str] = []
        runtime = _load_bonsai_runtime()
        self.core_geometry = runtime.core_geometry
        self.core_root = runtime.core_root
        self.tool = runtime.tool
        self.ensure_project()
        self.file = self.tool.Ifc.get()
        if self.file is None:
            raise RuntimeError("No active IFC project was found.")

    def ensure_project(self) -> None:
        if self.tool.Ifc.get():
            return
        if not self.auto_create_project:
            raise RuntimeError("No active IFC project. Enable auto-create project or create one in Bonsai first.")
        bpy.ops.bim.create_project()

    def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        for action in plan["actions"]:
            getattr(self, action["type"])(action)
        return {
            "summary": plan["summary"],
            "assumptions": plan["assumptions"],
            "created": self.created,
            "action_count": len(plan["actions"]),
        }

    def ensure_storey(self, action: Dict[str, Any]) -> None:
        self._ensure_storey(action["name"], float(action["elevation"]))
        self.created.append(action["name"])

    def create_rect_slab(self, action: Dict[str, Any]) -> None:
        storey = self._ensure_storey(action.get("storey") or "My Storey", float(action["z"]))
        obj = bpy.data.objects.new(action["name"], bpy.data.meshes.new(f"{action['name']}_mesh"))
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = Matrix.Translation((action["x"], action["y"], action["z"]))
        bpy.context.view_layer.update()

        element = self.core_root.assign_class(
            self.tool.Ifc,
            self.tool.Collector,
            self.tool.Root,
            obj=obj,
            ifc_class="IfcSlab",
            should_add_representation=False,
        )
        ifcopenshell.api.spatial.assign_container(self.file, products=[element], relating_structure=storey)
        self.core_geometry.edit_object_placement(self.tool.Ifc, self.tool.Geometry, self.tool.Surveyor, obj=obj)

        body = self._body_context()
        polyline = [
            (0.0, 0.0),
            (float(action["width"]), 0.0),
            (float(action["width"]), float(action["depth"])),
            (0.0, float(action["depth"])),
            (0.0, 0.0),
        ]
        rep = ifcopenshell.api.geometry.add_slab_representation(
            self.file,
            context=body,
            depth=float(action["thickness"]),
            polyline=polyline,
        )
        ifcopenshell.api.geometry.assign_representation(self.file, product=element, representation=rep)
        self.core_geometry.switch_representation(self.tool.Ifc, self.tool.Geometry, obj=obj, representation=rep)
        self.created.append(action["name"])

    def create_wall(self, action: Dict[str, Any]) -> None:
        storey = self._ensure_storey(action.get("storey") or "My Storey", float(action["base_z"]))
        p1 = Vector((float(action["x1"]), float(action["y1"]), float(action["base_z"])))
        p2 = Vector((float(action["x2"]), float(action["y2"]), float(action["base_z"])))
        direction = p2 - p1
        length = direction.length
        if length <= 0:
            raise RuntimeError(f"Wall '{action['name']}' has zero length.")
        yaw = math.atan2(direction.y, direction.x)

        obj = bpy.data.objects.new(action["name"], bpy.data.meshes.new(f"{action['name']}_mesh"))
        bpy.context.scene.collection.objects.link(obj)
        matrix_world = Matrix.Rotation(yaw, 4, "Z")
        matrix_world.translation = p1
        obj.matrix_world = matrix_world
        bpy.context.view_layer.update()

        element = self.core_root.assign_class(
            self.tool.Ifc,
            self.tool.Collector,
            self.tool.Root,
            obj=obj,
            ifc_class="IfcWall",
            should_add_representation=False,
        )
        ifcopenshell.api.spatial.assign_container(self.file, products=[element], relating_structure=storey)
        self.core_geometry.edit_object_placement(self.tool.Ifc, self.tool.Geometry, self.tool.Surveyor, obj=obj)

        rep = ifcopenshell.api.geometry.add_wall_representation(
            self.file,
            context=self._body_context(),
            length=length,
            height=float(action["height"]),
            thickness=float(action["thickness"]),
        )
        ifcopenshell.api.geometry.assign_representation(self.file, product=element, representation=rep)
        self.core_geometry.switch_representation(self.tool.Ifc, self.tool.Geometry, obj=obj, representation=rep)
        self.created.append(action["name"])

    def create_column(self, action: Dict[str, Any]) -> None:
        storey = self._ensure_storey(action.get("storey") or "My Storey", float(action["base_z"]))
        obj = bpy.data.objects.new(action["name"], bpy.data.meshes.new(f"{action['name']}_mesh"))
        bpy.context.scene.collection.objects.link(obj)
        rotation = math.radians(float(action.get("rotation_deg") or 0.0))
        matrix_world = Matrix.Rotation(rotation, 4, "Z")
        matrix_world.translation = (action["x"], action["y"], action["base_z"])
        obj.matrix_world = matrix_world
        bpy.context.view_layer.update()

        element = self.core_root.assign_class(
            self.tool.Ifc,
            self.tool.Collector,
            self.tool.Root,
            obj=obj,
            ifc_class="IfcColumn",
            should_add_representation=False,
        )
        ifcopenshell.api.spatial.assign_container(self.file, products=[element], relating_structure=storey)
        self.core_geometry.edit_object_placement(self.tool.Ifc, self.tool.Geometry, self.tool.Surveyor, obj=obj)

        profile = self.file.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            XDim=float(action["width"]),
            YDim=float(action["depth"]),
        )
        rep = ifcopenshell.api.geometry.add_profile_representation(
            self.file,
            context=self._body_context(),
            profile=profile,
            depth=float(action["height"]),
        )
        ifcopenshell.api.geometry.assign_representation(self.file, product=element, representation=rep)
        self.core_geometry.switch_representation(self.tool.Ifc, self.tool.Geometry, obj=obj, representation=rep)
        self.created.append(action["name"])

    def create_curtain_wall(self, action: Dict[str, Any]) -> None:
        storey = self._ensure_storey(action.get("storey") or "My Storey", float(action["base_z"]))
        p1 = Vector((float(action["x1"]), float(action["y1"]), 0.0))
        p2 = Vector((float(action["x2"]), float(action["y2"]), 0.0))
        span = p2 - p1
        length = span.length
        if length <= 0:
            raise RuntimeError(f"Curtain wall '{action['name']}' has zero span.")
        tangent = span.normalized()
        normal = Vector((-tangent.y, tangent.x, 0.0))
        up = Vector((0.0, 0.0, 1.0))
        panel_width = float(action["panel_width"])
        panel_height = float(action["panel_height"])
        gap = float(action.get("panel_gap") or 0.05)
        thickness = float(action["thickness"])
        base_z = float(action["base_z"])
        top_z = float(action["top_z"])

        columns = max(1, int((length + gap) // (panel_width + gap)))
        rows = max(1, int(((top_z - base_z) + gap) // (panel_height + gap)))
        start_offset = (length - (columns * panel_width + max(columns - 1, 0) * gap)) / 2.0

        for row in range(rows):
            for col in range(columns):
                panel_name = f"{action['name']}_{row + 1:02d}_{col + 1:02d}"
                origin = Vector((p1.x, p1.y, base_z))
                origin += tangent * (start_offset + col * (panel_width + gap))
                origin += up * (row * (panel_height + gap))
                self._create_panel(panel_name, origin, tangent, up, normal, panel_width, panel_height, thickness, storey)

    def _create_panel(
        self,
        name: str,
        origin: Vector,
        tangent: Vector,
        up: Vector,
        normal: Vector,
        width: float,
        height: float,
        thickness: float,
        storey,
    ) -> None:
        obj = bpy.data.objects.new(name, bpy.data.meshes.new(f"{name}_mesh"))
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = Matrix(
            (
                (tangent.x, up.x, normal.x, origin.x),
                (tangent.y, up.y, normal.y, origin.y),
                (tangent.z, up.z, normal.z, origin.z),
                (0.0, 0.0, 0.0, 1.0),
            )
        )
        bpy.context.view_layer.update()

        element = self.core_root.assign_class(
            self.tool.Ifc,
            self.tool.Collector,
            self.tool.Root,
            obj=obj,
            ifc_class="IfcPlate",
            should_add_representation=False,
        )
        ifcopenshell.api.spatial.assign_container(self.file, products=[element], relating_structure=storey)
        self.core_geometry.edit_object_placement(self.tool.Ifc, self.tool.Geometry, self.tool.Surveyor, obj=obj)

        profile = self.file.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            XDim=width,
            YDim=height,
        )
        rep = ifcopenshell.api.geometry.add_profile_representation(
            self.file,
            context=self._body_context(),
            profile=profile,
            depth=thickness,
            cardinal_point="bottom left",
        )
        ifcopenshell.api.geometry.assign_representation(self.file, product=element, representation=rep)
        self.core_geometry.switch_representation(self.tool.Ifc, self.tool.Geometry, obj=obj, representation=rep)
        self.created.append(name)

    def _body_context(self):
        context = ifcopenshell.util.representation.get_context(self.file, "Model", "Body", "MODEL_VIEW")
        if not context:
            raise RuntimeError("Bonsai project is missing the Model/Body/MODEL_VIEW context.")
        return context

    def _ensure_storey(self, name: str, elevation: float):
        storey = self._find_storey(name)
        if storey:
            obj = self.tool.Ifc.get_object(storey)
            if obj:
                obj.location.z = elevation
            return storey

        building = self._first_entity("IfcBuilding")
        if building is None:
            raise RuntimeError("No IfcBuilding found in the active IFC project.")
        obj = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = (0.0, 0.0, elevation)
        bpy.context.view_layer.update()

        storey = self.core_root.assign_class(
            self.tool.Ifc,
            self.tool.Collector,
            self.tool.Root,
            obj=obj,
            ifc_class="IfcBuildingStorey",
            should_add_representation=False,
        )
        building_obj = self.tool.Ifc.get_object(building)
        if not building_obj:
            raise RuntimeError("Could not resolve the Blender object for the active IfcBuilding.")
        self.tool.Project.run_aggregate_assign_object(relating_obj=building_obj, related_obj=obj)
        return storey

    def _find_storey(self, name: str):
        for storey in self.file.by_type("IfcBuildingStorey"):
            if getattr(storey, "Name", None) == name:
                return storey
        return None

    def _first_entity(self, ifc_class: str):
        entities = self.file.by_type(ifc_class)
        return entities[0] if entities else None


def ensure_text_block(name: str, starter_text: str = "") -> bpy.types.Text:
    text = bpy.data.texts.get(name)
    if text:
        return text
    text = bpy.data.texts.new(name)
    if starter_text:
        text.write(starter_text)
    return text


def text_to_string(name: str) -> str:
    text = bpy.data.texts.get(name)
    return text.as_string() if text else ""


def replace_text(name: str, content: str) -> None:
    text = ensure_text_block(name)
    text.clear()
    text.write(content)


def result_to_log(result: Dict[str, Any]) -> str:
    return json.dumps(result, indent=2)
