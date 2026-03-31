from __future__ import annotations

import json
import math
from urllib import error, request

import bpy
import mathutils

bl_info = {
    "name": "Bonsai AI Bridge",
    "author": "OpenAI Codex",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Bonsai AI",
    "description": "Use AI providers over API to generate IFC-native BIM objects in Bonsai",
    "category": "3D View",
}


def bonsai_available() -> bool:
    try:
        import bonsai.core.project  # noqa: F401
        import bonsai.core.root  # noqa: F401
        import bonsai.tool  # noqa: F401
        import ifcopenshell.util.representation  # noqa: F401
        return True
    except Exception:
        return False


def get_bridge_props(context: bpy.types.Context) -> "BonsaiAIProperties":
    return context.scene.bonsai_ai_bridge


class BonsaiAIProperties(bpy.types.PropertyGroup):
    bridge_url: bpy.props.StringProperty(name="Bridge URL", default="http://127.0.0.1:8765")
    provider: bpy.props.EnumProperty(
        name="Provider",
        items=[
            ("openai", "OpenAI", ""),
            ("anthropic", "Anthropic", ""),
            ("google", "Google", ""),
        ],
        default="openai",
    )
    model: bpy.props.StringProperty(name="Model", default="gpt-5.4")
    prompt: bpy.props.StringProperty(name="Prompt", default="")
    include_scene_context: bpy.props.BoolProperty(name="Include Scene Context", default=True)
    last_plan_json: bpy.props.StringProperty(name="Last Plan JSON", default="")
    last_summary: bpy.props.StringProperty(name="Last Summary", default="")


class BONSAI_AI_OT_plan(bpy.types.Operator):
    bl_idname = "bonsai_ai.plan"
    bl_label = "Plan"

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = get_bridge_props(context)
        if not props.prompt.strip():
            self.report({"ERROR"}, "Prompt is empty")
            return {"CANCELLED"}

        try:
            plan = request_plan(context)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        props.last_plan_json = json.dumps(plan, indent=2)
        props.last_summary = plan.get("summary", "")
        self.report({"INFO"}, props.last_summary or "Plan generated")
        return {"FINISHED"}


class BONSAI_AI_OT_execute_last_plan(bpy.types.Operator):
    bl_idname = "bonsai_ai.execute_last_plan"
    bl_label = "Execute Last Plan"

    def execute(self, context: bpy.types.Context) -> set[str]:
        if not bonsai_available():
            self.report({"ERROR"}, "Bonsai is not available in this Blender session")
            return {"CANCELLED"}

        props = get_bridge_props(context)
        if not props.last_plan_json.strip():
            self.report({"ERROR"}, "No saved plan to execute")
            return {"CANCELLED"}

        try:
            plan = json.loads(props.last_plan_json)
            summary = execute_plan(plan)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        props.last_summary = summary
        self.report({"INFO"}, summary)
        return {"FINISHED"}


class BONSAI_AI_OT_plan_and_execute(bpy.types.Operator):
    bl_idname = "bonsai_ai.plan_and_execute"
    bl_label = "Plan + Execute"

    def execute(self, context: bpy.types.Context) -> set[str]:
        plan_result = bpy.ops.bonsai_ai.plan()
        if "FINISHED" not in plan_result:
            return {"CANCELLED"}
        return bpy.ops.bonsai_ai.execute_last_plan()


class BONSAI_AI_PT_panel(bpy.types.Panel):
    bl_label = "Bonsai AI"
    bl_idname = "BONSAI_AI_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai AI"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = get_bridge_props(context)

        if not bonsai_available():
            box = layout.box()
            box.label(text="Bonsai not detected in this Blender session.", icon="ERROR")
            box.label(text="Install/enable Bonsai first.")
            return

        layout.prop(props, "bridge_url")
        layout.prop(props, "provider")
        layout.prop(props, "model")
        layout.prop(props, "include_scene_context")
        layout.prop(props, "prompt")

        row = layout.row(align=True)
        row.operator("bonsai_ai.plan")
        row.operator("bonsai_ai.plan_and_execute")
        layout.operator("bonsai_ai.execute_last_plan")

        if props.last_summary:
            box = layout.box()
            box.label(text="Last Result")
            box.label(text=props.last_summary[:120])


def request_plan(context: bpy.types.Context) -> dict:
    props = get_bridge_props(context)
    payload = {
        "provider": props.provider,
        "model": props.model or None,
        "prompt": props.prompt,
        "scene_context": collect_scene_context() if props.include_scene_context else None,
    }
    body = json.dumps(payload).encode("utf-8")
    endpoint = props.bridge_url.rstrip("/") + "/v1/plan"
    req = request.Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Bridge request failed: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach bridge at {endpoint}: {exc.reason}") from exc


def collect_scene_context() -> dict:
    try:
        import bonsai.tool as tool
    except Exception:
        return {"bonsai": "unavailable"}

    elements = []
    if tool.Ifc.get():
        for obj in list(bpy.data.objects)[:200]:
            element = tool.Ifc.get_entity(obj)
            if not element:
                continue
            elements.append(
                {
                    "name": obj.name,
                    "ifc_class": element.is_a(),
                    "location": [round(float(v), 3) for v in obj.location],
                }
            )

    return {
        "scene_name": bpy.context.scene.name,
        "object_count": len(bpy.data.objects),
        "ifc_elements": elements[:100],
    }


def execute_plan(plan: dict) -> str:
    import bonsai.core.project as core_project
    import bonsai.core.root as core_root
    import bonsai.tool as tool
    import ifcopenshell.api.feature
    import ifcopenshell.util.representation

    ensure_project_if_needed(core_project, tool)

    created = 0
    for action in plan.get("actions", []):
        kind = action["kind"]
        name = action.get("name") or kind
        params = dict(action.get("params", {}))
        if kind == "ensure_project":
            ensure_project_if_needed(core_project, tool, params)
            continue
        if kind == "ensure_storey":
            ensure_storey(tool, params["storey"], float(params["elevation"]))
            continue
        if kind == "create_slab":
            create_box_element(tool, core_root, "IfcSlab", name, params, size_keys=("width", "depth", "thickness"))
            created += 1
            continue
        if kind == "create_wall":
            create_box_element(tool, core_root, params.get("ifc_class", "IfcWall"), name, params, size_keys=("length", "thickness", "height"))
            created += 1
            continue
        if kind == "create_column":
            create_box_element(tool, core_root, params.get("ifc_class", "IfcColumn"), name, params, size_keys=("width", "depth", "height"))
            created += 1
            continue
        if kind == "create_beam":
            create_box_element(tool, core_root, params.get("ifc_class", "IfcBeam"), name, params, size_keys=("length", "width", "depth"))
            created += 1
            continue
        if kind == "create_panel":
            create_box_element(tool, core_root, params.get("ifc_class", "IfcPlate"), name, params, size_keys=("width", "thickness", "height"))
            created += 1
            continue
        if kind == "create_panel_grid":
            created += create_panel_grid(tool, core_root, name, params)
            continue
        if kind == "create_window":
            create_filling_element(tool, core_root, "IfcWindow", name, params)
            created += 1
            continue
        if kind == "create_door":
            create_filling_element(tool, core_root, "IfcDoor", name, params)
            created += 1
            continue
        raise RuntimeError(f"Unsupported action kind at execution time: {kind}")

    return plan.get("summary") or f"Executed {created} BIM actions"


def ensure_project_if_needed(core_project, tool, params: dict | None = None) -> None:
    params = params or {}
    if tool.Ifc.get():
        return
    core_project.create_project(
        tool.Ifc,
        tool.Georeference,
        tool.Project,
        tool.Spatial,
        params.get("schema", "IFC4"),
        None,
    )


def ensure_storey(tool, storey_name: str, elevation: float):
    existing = find_ifc_entity_by_name(tool, "IfcBuildingStorey", storey_name)
    if existing:
        tool.Spatial.set_default_container(existing)
        obj = tool.Ifc.get_object(existing)
        if obj:
            obj.location.z = elevation
        return existing

    body = get_body_context(tool)
    obj = bpy.data.objects.new(storey_name, None)
    obj.location = (0.0, 0.0, elevation)
    bpy.context.scene.collection.objects.link(obj)

    import bonsai.core.root as core_root

    entity = core_root.assign_class(
        tool.Ifc,
        tool.Collector,
        tool.Root,
        obj=obj,
        ifc_class="IfcBuildingStorey",
        should_add_representation=False,
    )
    building = tool.Ifc.get().by_type("IfcBuilding")[0]
    tool.Ifc.run("aggregate.assign_object", products=[entity], relating_object=building)
    tool.Spatial.set_default_container(entity)
    return entity


def get_body_context(tool):
    import ifcopenshell.util.representation

    return ifcopenshell.util.representation.get_context(tool.Ifc.get(), "Model", "Body", "MODEL_VIEW")


def find_ifc_entity_by_name(tool, ifc_class: str, name: str):
    for entity in tool.Ifc.get().by_type(ifc_class):
        obj = tool.Ifc.get_object(entity)
        if obj and obj.name == name:
            return entity
        if getattr(entity, "Name", None) == name:
            return entity
    return None


def set_storey_container(tool, storey_name: str | None):
    if not storey_name:
        return None
    existing = find_ifc_entity_by_name(tool, "IfcBuildingStorey", storey_name)
    if existing:
        tool.Spatial.set_default_container(existing)
        return existing
    return ensure_storey(tool, storey_name, 0.0)


def create_box_mesh(name: str, size_x: float, size_y: float, size_z: float) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + "_mesh")
    sx = size_x / 2.0
    sy = size_y / 2.0
    sz = size_z
    verts = [
        (-sx, -sy, 0.0),
        (sx, -sy, 0.0),
        (sx, sy, 0.0),
        (-sx, sy, 0.0),
        (-sx, -sy, sz),
        (sx, -sy, sz),
        (sx, sy, sz),
        (-sx, sy, sz),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def create_box_element(tool, core_root, ifc_class: str, name: str, params: dict, size_keys: tuple[str, str, str]) -> bpy.types.Object:
    size_x = float(params[size_keys[0]])
    size_y = float(params[size_keys[1]])
    size_z = float(params[size_keys[2]])
    x = float(params["x"])
    y = float(params["y"])
    z = float(params["z"])
    rotation = math.radians(float(params.get("rotation_degrees", 0.0)))

    set_storey_container(tool, params.get("storey"))
    obj = create_box_mesh(name, size_x, size_y, size_z)
    obj.location = (x, y, z)
    obj.rotation_euler = (0.0, 0.0, rotation)
    bpy.context.view_layer.objects.active = obj

    body = get_body_context(tool)
    core_root.assign_class(
        tool.Ifc,
        tool.Collector,
        tool.Root,
        obj=obj,
        ifc_class=ifc_class,
        context=body,
    )
    return obj


def create_panel_grid(tool, core_root, base_name: str, params: dict) -> int:
    count = 0
    cols = int(params["columns"])
    rows = int(params["rows"])
    panel_width = float(params["panel_width"])
    panel_height = float(params["panel_height"])
    thickness = float(params["thickness"])
    gap_x = float(params.get("gap_x", 0.05))
    gap_y = float(params.get("gap_y", 0.05))
    origin_x = float(params["x"])
    origin_y = float(params["y"])
    origin_z = float(params["z"])
    rotation = float(params.get("rotation_degrees", 0.0))

    total_width = cols * panel_width + max(cols - 1, 0) * gap_x
    for row in range(rows):
        for col in range(cols):
            x = origin_x - total_width / 2.0 + panel_width / 2.0 + col * (panel_width + gap_x)
            z = origin_z + row * (panel_height + gap_y)
            create_box_element(
                tool,
                core_root,
                "IfcPlate",
                f"{base_name} {row + 1}-{col + 1}",
                {
                    "x": x,
                    "y": origin_y,
                    "z": z,
                    "width": panel_width,
                    "thickness": thickness,
                    "height": panel_height,
                    "rotation_degrees": rotation,
                    "storey": params.get("storey"),
                },
                size_keys=("width", "thickness", "height"),
            )
            count += 1
    return count


def create_filling_element(tool, core_root, ifc_class: str, name: str, params: dict) -> bpy.types.Object:
    obj = create_box_element(
        tool,
        core_root,
        ifc_class,
        name,
        {
            "x": params["x"],
            "y": params["y"],
            "z": params["z"],
            "width": params["width"],
            "depth": params["depth"],
            "height": params["height"],
            "rotation_degrees": params.get("rotation_degrees", 0.0),
            "storey": params.get("storey"),
        },
        size_keys=("width", "depth", "height"),
    )
    host_name = params.get("host")
    if host_name:
        host_obj = find_object_by_name(host_name)
        if host_obj:
            try:
                from bonsai.bim.module.model.opening import FilledOpeningGenerator

                FilledOpeningGenerator().generate(obj, host_obj, target=mathutils.Vector(obj.matrix_world.translation))
            except Exception as exc:
                print(f"Failed to add opening for {name}: {exc}")
    return obj


def find_object_by_name(name: str) -> bpy.types.Object | None:
    if name in bpy.data.objects:
        return bpy.data.objects[name]
    lowered = name.lower()
    for obj in bpy.data.objects:
        if obj.name.lower() == lowered:
            return obj
    return None


classes = (
    BonsaiAIProperties,
    BONSAI_AI_OT_plan,
    BONSAI_AI_OT_execute_last_plan,
    BONSAI_AI_OT_plan_and_execute,
    BONSAI_AI_PT_panel,
)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bonsai_ai_bridge = bpy.props.PointerProperty(type=BonsaiAIProperties)


def unregister() -> None:
    del bpy.types.Scene.bonsai_ai_bridge
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
