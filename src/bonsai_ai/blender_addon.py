from __future__ import annotations

import json
from typing import Optional

from .ifc_author import AuthoringError, IfcAuthor
from .planner import DEFAULT_ENV_VARS, DEFAULT_MODELS, create_plan

try:
    import bpy
except ImportError:  # pragma: no cover - only available inside Blender
    bpy = None


if bpy:
    class BonsaiAIProperties(bpy.types.PropertyGroup):
        provider: bpy.props.EnumProperty(
            name="Provider",
            items=[
                ("openai", "OpenAI", ""),
                ("anthropic", "Anthropic", ""),
                ("gemini", "Gemini", ""),
            ],
            default="openai",
        )
        model: bpy.props.StringProperty(name="Model", default=DEFAULT_MODELS["openai"])
        api_key_env: bpy.props.StringProperty(name="API Key Env", default=DEFAULT_ENV_VARS["openai"])
        output_path: bpy.props.StringProperty(name="IFC Path", subtype="FILE_PATH")
        prompt: bpy.props.StringProperty(name="Prompt")


    def _sync_defaults(props: "BonsaiAIProperties") -> None:
        props.model = DEFAULT_MODELS[props.provider]
        props.api_key_env = DEFAULT_ENV_VARS[props.provider]


    class BONSAI_AI_OT_sync_defaults(bpy.types.Operator):
        bl_idname = "bonsai_ai.sync_defaults"
        bl_label = "Use Provider Defaults"

        def execute(self, context):
            _sync_defaults(context.scene.bonsai_ai)
            return {"FINISHED"}


    class BONSAI_AI_OT_generate(bpy.types.Operator):
        bl_idname = "bonsai_ai.generate"
        bl_label = "Generate IFC From Prompt"

        def execute(self, context):
            props = context.scene.bonsai_ai
            if not props.output_path:
                self.report({"ERROR"}, "Choose an IFC output path first")
                return {"CANCELLED"}
            author = IfcAuthor(props.output_path)
            try:
                progress_lines = []
                seen_rounds = set()
                failed_calls = set()
                for _ in range(12):
                    plan = create_plan(
                        provider=props.provider,
                        model=props.model.strip() or None,
                        api_key_env=props.api_key_env.strip() or None,
                        user_prompt=props.prompt,
                        scene_summary=author.scene_summary(),
                        progress_summary="\n".join(progress_lines),
                    )
                    if not plan.tool_calls:
                        break
                    round_signature = tuple(
                        (call.name, json.dumps(call.arguments, sort_keys=True)) for call in plan.tool_calls
                    )
                    if round_signature in seen_rounds:
                        raise RuntimeError("Planner repeated a previous round before completing the request.")
                    seen_rounds.add(round_signature)
                    for call in plan.tool_calls:
                        try:
                            result = author.apply_tool_call(call.name, call.arguments)
                            progress_lines.append(f"{result.tool_name}: {result.message}")
                        except AuthoringError as exc:
                            failed_signature = (call.name, json.dumps(call.arguments, sort_keys=True))
                            if failed_signature in failed_calls:
                                raise RuntimeError(f"Planner repeated a failing tool call: {call.name} -> {exc}") from exc
                            failed_calls.add(failed_signature)
                            progress_lines.append(
                                f"FAILED {call.name}: {exc}. Replan from the updated scene summary and avoid this mistake."
                            )
                else:
                    raise RuntimeError("Planner exceeded the maximum number of rounds.")
                author.save()
            except Exception as exc:  # pragma: no cover - Blender runtime surface
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, f"Wrote IFC to {props.output_path}")
            return {"FINISHED"}


    class BONSAI_AI_PT_panel(bpy.types.Panel):
        bl_label = "Bonsai AI"
        bl_idname = "BONSAI_AI_PT_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Bonsai AI"

        def draw(self, context):
            layout = self.layout
            props = context.scene.bonsai_ai
            layout.prop(props, "provider")
            layout.operator("bonsai_ai.sync_defaults", text="Reset Model Defaults")
            layout.prop(props, "model")
            layout.prop(props, "api_key_env")
            layout.prop(props, "output_path")
            layout.prop(props, "prompt")
            layout.operator("bonsai_ai.generate", text="Generate IFC")


    CLASSES = (
        BonsaiAIProperties,
        BONSAI_AI_OT_sync_defaults,
        BONSAI_AI_OT_generate,
        BONSAI_AI_PT_panel,
    )


    def register() -> None:  # pragma: no cover - Blender runtime only
        for cls in CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.Scene.bonsai_ai = bpy.props.PointerProperty(type=BonsaiAIProperties)


    def unregister() -> None:  # pragma: no cover - Blender runtime only
        del bpy.types.Scene.bonsai_ai
        for cls in reversed(CLASSES):
            bpy.utils.unregister_class(cls)

else:
    def register() -> None:
        return None


    def unregister() -> None:
        return None
