"""UI, props, and operators for the Blender addon."""

from __future__ import annotations

import json
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from .presentation import (
    apply_section_box_from_selection,
    bake_presentation,
    clear_section_box,
    isolate_role,
    isolate_selected_branch,
    selected_object_metadata,
    show_all_semantic_collections,
)
from .runtime import load_core, load_headless_executor

EXAMPLE_PROMPT = """Create a simple 2-storey office concept in meters.

Ground floor:
- 20m x 30m slab at z=0
- exterior walls 4m high and 0.2m thick
- interior partition walls creating 8 offices
- south facade curtain wall from z=0.5 to z=3.5

Level 2:
- 20m x 30m slab at z=4
- repeat exterior walls
- lighter partition layout
"""

EXAMPLE_DOC = """Project brief / engineering notes
- Structural grid: 8m x 8m nominal
- Floor-to-floor height: 4.0m
- Exterior wall thickness: 0.20m
- Curtain wall panel module: 1.5m x 3.0m
- Keep a 1.5m circulation zone near the main south facade
"""

DOC_IMPORT_SUFFIXES = {".txt", ".md", ".markdown", ".json", ".csv", ".yaml", ".yml"}
DOC_IMPORT_FILTER = "*.txt;*.md;*.markdown;*.json;*.csv;*.yaml;*.yml"
DOC_CONTEXT_LIMIT = 24000
SHORTCUT_HINT = "Cmd/Ctrl+T in the 3D View"
SETTINGS_SHORTCUT_HINT = "Cmd/Ctrl+Shift+T in the 3D View"
DEFAULT_ARTIFACT_DIR = str(Path.home() / "Downloads" / "bonsai_ai_bridge")
ADDON_MODULE = (__package__ or "bonsai_ai_blender").split(".")[0]
PROVIDER_ITEMS = (
    ("openai", "OpenAI", "Use the OpenAI Responses API"),
    ("anthropic", "Anthropic", "Use the Anthropic Messages API"),
    ("google", "Google", "Use the Gemini API"),
)
OPENAI_REASONING_ITEMS = (
    ("medium", "Medium", "Recommended balance for planning speed and accuracy"),
    ("high", "High", "More reasoning for harder engineering prompts"),
    ("low", "Low", "Fastest, but less robust on complex plans"),
)
OPENAI_SERVICE_TIER_ITEMS = (
    ("priority", "Priority", "Prefer the priority processing lane when available"),
    ("auto", "Auto", "Let OpenAI route the request normally"),
    ("default", "Default", "Use the standard processing tier"),
)
ROLE_ISOLATE_ITEMS = (
    ("Structure", "Structure", "Show primary steel and other structural members"),
    ("Envelope", "Envelope", "Show walls, roof shells, and envelope surfaces"),
    ("Openings", "Openings", "Show windows, doors, and glazed systems"),
    ("Cladding", "Cladding", "Show individual panels and cladding assemblies"),
    ("Foundations", "Foundations", "Show footings, shells, and subgrade assemblies"),
)

addon_keymaps = []


def _client():
    from . import client

    return client


def _ai_core():
    return load_core()


def _ensure_text_block_local(name: str, starter_text: str = ""):
    text = bpy.data.texts.get(name)
    if text:
        return text
    text = bpy.data.texts.new(name)
    if starter_text:
        text.write(starter_text)
    return text


def _text_to_string_local(name: str) -> str:
    text = bpy.data.texts.get(name)
    return text.as_string() if text else ""


def _replace_text_local(name: str, content: str) -> None:
    text = _ensure_text_block_local(name)
    text.clear()
    text.write(content)


def _import_ifc_local(path: str | Path) -> str:
    bim_ops = getattr(bpy.ops, "bim", None)
    if bim_ops:
        for operator_name in ("load_project", "load_ifc", "open_project"):
            operator = getattr(bim_ops, operator_name, None)
            if operator is None:
                continue
            try:
                operator(filepath=str(path))
                report = bake_presentation(path)
                return (
                    f"Imported primary IFC from {path}. "
                    f"Styled {report.get('styled_objects', 0)} objects across "
                    f"{report.get('view_collection_count', 0)} review collections."
                )
            except TypeError:
                try:
                    operator("INVOKE_DEFAULT", filepath=str(path))
                    report = bake_presentation(path)
                    return (
                        f"Imported primary IFC from {path}. "
                        f"Styled {report.get('styled_objects', 0)} objects across "
                        f"{report.get('view_collection_count', 0)} review collections."
                    )
                except Exception:
                    continue
            except Exception:
                continue
    return f"Generated IFC at {path}. Open it in Bonsai if automatic import is unavailable."


def _resolve_presentation_ifc(settings) -> Path:
    scene_path = bpy.context.scene.get("bonsai_ai_last_ifc_path")
    if isinstance(scene_path, str) and scene_path:
        candidate = Path(scene_path).expanduser()
        if candidate.exists():
            return candidate
    candidate = Path(settings.artifact_download_dir).expanduser() / "bonsai_ai_live.ifc"
    if candidate.exists():
        return candidate
    raise FileNotFoundError("No IFC path is available yet. Build or import an IFC first.")


def _addon_preferences(context=None):
    prefs_owner = context.preferences if context else bpy.context.preferences
    addon = prefs_owner.addons.get(ADDON_MODULE)
    return addon.preferences if addon else None


class BonsaiAIAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_MODULE

    bridge_url: StringProperty(name="Bridge URL", default="http://127.0.0.1:8765")
    provider: EnumProperty(name="Provider", items=PROVIDER_ITEMS, default="openai")
    model: StringProperty(name="Model", default="gpt-5.4")
    auto_create_project: BoolProperty(name="Auto-Create IFC Project", default=True)
    include_docs_context: BoolProperty(name="Use Docs Context", default=True)
    openai_api_key: StringProperty(name="OpenAI API Key", subtype="PASSWORD")
    anthropic_api_key: StringProperty(name="Anthropic API Key", subtype="PASSWORD")
    google_api_key: StringProperty(name="Google API Key", subtype="PASSWORD")
    openai_reasoning_effort: EnumProperty(
        name="OpenAI Reasoning",
        items=OPENAI_REASONING_ITEMS,
        default="medium",
    )
    openai_service_tier: EnumProperty(
        name="OpenAI Service Tier",
        items=OPENAI_SERVICE_TIER_ITEMS,
        default="priority",
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Saved defaults for Bonsai AI")

        col = layout.column(align=True)
        col.prop(self, "bridge_url")
        col.prop(self, "provider")
        col.prop(self, "model")
        col.prop(self, "auto_create_project")
        col.prop(self, "include_docs_context")
        if self.provider == "openai":
            col.prop(self, "openai_reasoning_effort")
            col.prop(self, "openai_service_tier")

        box = layout.box()
        box.label(text="Saved API Keys")
        if self.provider == "openai":
            box.prop(self, "openai_api_key", text="")
        elif self.provider == "anthropic":
            box.prop(self, "anthropic_api_key", text="")
        else:
            box.prop(self, "google_api_key", text="")

        layout.label(text="These values are stored in Blender user preferences.")


class BonsaiAISettings(bpy.types.PropertyGroup):
    bridge_url: StringProperty(name="Bridge URL", default="http://127.0.0.1:8765")
    job_id: StringProperty(name="Job ID", default="")
    artifact_download_dir: StringProperty(name="Artifact Folder", subtype="DIR_PATH", default=DEFAULT_ARTIFACT_DIR)
    provider: EnumProperty(name="Provider", items=PROVIDER_ITEMS, default="openai")
    model: StringProperty(name="Model", default="gpt-5.4")
    auto_create_project: BoolProperty(name="Auto-Create IFC Project", default=True)
    include_docs_context: BoolProperty(name="Use Docs Context", default=True)
    prompt_text_name: StringProperty(name="Prompt Text", default="Bonsai AI Prompt")
    docs_text_name: StringProperty(name="Docs Text", default="Bonsai AI Docs")
    plan_text_name: StringProperty(name="Plan Text", default="Bonsai AI Last Plan")
    results_text_name: StringProperty(name="Results Text", default="Bonsai AI Results")
    log_text_name: StringProperty(name="Log Text", default="Bonsai AI Log")
    status: StringProperty(name="Status", default=f"Idle. Shortcut: {SHORTCUT_HINT}")
    openai_api_key: StringProperty(name="OpenAI API Key", subtype="PASSWORD")
    anthropic_api_key: StringProperty(name="Anthropic API Key", subtype="PASSWORD")
    google_api_key: StringProperty(name="Google API Key", subtype="PASSWORD")
    openai_reasoning_effort: EnumProperty(
        name="OpenAI Reasoning",
        items=OPENAI_REASONING_ITEMS,
        default="medium",
    )
    openai_service_tier: EnumProperty(
        name="OpenAI Service Tier",
        items=OPENAI_SERVICE_TIER_ITEMS,
        default="priority",
    )
    initialized_from_preferences: BoolProperty(default=False, options={"HIDDEN"})


def _ensure_settings_initialized(context):
    settings = context.scene.bonsai_ai_settings
    prefs = _addon_preferences(context)
    if prefs is None:
        return settings

    if not settings.initialized_from_preferences:
        settings.bridge_url = prefs.bridge_url
        settings.provider = prefs.provider
        settings.model = prefs.model
        settings.auto_create_project = prefs.auto_create_project
        settings.include_docs_context = prefs.include_docs_context
        settings.openai_reasoning_effort = prefs.openai_reasoning_effort
        settings.openai_service_tier = prefs.openai_service_tier
        settings.initialized_from_preferences = True

    if not settings.openai_api_key and prefs.openai_api_key:
        settings.openai_api_key = prefs.openai_api_key
    if not settings.anthropic_api_key and prefs.anthropic_api_key:
        settings.anthropic_api_key = prefs.anthropic_api_key
    if not settings.google_api_key and prefs.google_api_key:
        settings.google_api_key = prefs.google_api_key
    return settings


def _save_settings_to_preferences(context) -> None:
    settings = context.scene.bonsai_ai_settings
    prefs = _addon_preferences(context)
    if prefs is None:
        return

    prefs.bridge_url = settings.bridge_url
    prefs.provider = settings.provider
    prefs.model = settings.model
    prefs.auto_create_project = settings.auto_create_project
    prefs.include_docs_context = settings.include_docs_context
    prefs.openai_reasoning_effort = settings.openai_reasoning_effort
    prefs.openai_service_tier = settings.openai_service_tier
    prefs.openai_api_key = settings.openai_api_key
    prefs.anthropic_api_key = settings.anthropic_api_key
    prefs.google_api_key = settings.google_api_key
    try:
        bpy.ops.wm.save_userpref()
    except Exception:
        return


def _api_key(settings: BonsaiAISettings, context=None) -> str | None:
    if settings.provider == "openai":
        if settings.openai_api_key:
            return settings.openai_api_key
        prefs = _addon_preferences(context)
        return prefs.openai_api_key or None if prefs else None
    if settings.provider == "anthropic":
        if settings.anthropic_api_key:
            return settings.anthropic_api_key
        prefs = _addon_preferences(context)
        return prefs.anthropic_api_key or None if prefs else None
    if settings.google_api_key:
        return settings.google_api_key
    prefs = _addon_preferences(context)
    return prefs.google_api_key or None if prefs else None


def _truncate_docs(text: str) -> str:
    if len(text) <= DOC_CONTEXT_LIMIT:
        return text
    remaining = len(text) - DOC_CONTEXT_LIMIT
    return text[:DOC_CONTEXT_LIMIT].rstrip() + f"\n\n[Truncated {remaining} extra characters from the reference document.]"


def _selection_context(settings: BonsaiAISettings) -> dict | None:
    scene_path = bpy.context.scene.get("bonsai_ai_last_ifc_path")
    if not isinstance(scene_path, str) or not scene_path:
        return None
    try:
        return selected_object_metadata(scene_path)
    except Exception:
        return None


def _compose_prompt(settings: BonsaiAISettings) -> str:
    prompt = _text_to_string_local(settings.prompt_text_name).strip()
    if not prompt:
        return ""
    parts = [prompt]
    selection = _selection_context(settings)
    if selection:
        parts.append(
            "Selection context:\n"
            f"{json.dumps(selection, indent=2)}\n\n"
            "When the request is modifying the current model, prefer semantic edit actions "
            "(update_element, move_element, replace_section, delete_element, rebuild_branch) "
            "and target the selected element_id values or their semantic paths."
        )
    if not settings.include_docs_context:
        return "\n\n".join(parts)
    docs_text = _text_to_string_local(settings.docs_text_name).strip()
    if not docs_text:
        return "\n\n".join(parts)
    docs_text = _truncate_docs(docs_text)
    parts.append(
        "Reference document context:\n"
        f"{docs_text}\n\n"
        "Use the reference document to extract dimensions, constraints, engineering notes, and design intent. "
        "If the document and prompt conflict, follow the explicit user prompt and record the conflict in assumptions."
    )
    return "\n\n".join(parts)


def _draw_provider_settings(layout, settings: BonsaiAISettings) -> None:
    col = layout.column(align=True)
    col.prop(settings, "bridge_url")
    col.prop(settings, "provider")
    col.prop(settings, "model")
    col.prop(settings, "auto_create_project")
    if settings.provider == "openai":
        col.separator()
        col.prop(settings, "openai_reasoning_effort")
        col.prop(settings, "openai_service_tier")

    box = layout.box()
    box.label(text="API Key")
    if settings.provider == "openai":
        box.prop(settings, "openai_api_key", text="")
    elif settings.provider == "anthropic":
        box.prop(settings, "anthropic_api_key", text="")
    else:
        box.prop(settings, "google_api_key", text="")

    text_box = layout.box()
    text_box.label(text="Text Blocks")
    text_box.prop(settings, "include_docs_context")
    text_box.prop(settings, "prompt_text_name")
    text_box.prop(settings, "docs_text_name")
    text_box.prop(settings, "plan_text_name")
    text_box.prop(settings, "results_text_name")
    text_box.prop(settings, "log_text_name")
    text_box.prop(settings, "artifact_download_dir")


def _read_doc_file(path_text: str) -> tuple[str, Path]:
    path = Path(path_text).expanduser()
    if path.suffix.lower() not in DOC_IMPORT_SUFFIXES:
        raise ValueError("Only text-based docs are supported here right now: txt, md, json, csv, yaml.")
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("This file is not valid UTF-8 text. Paste extracted text into the Docs block instead.") from exc
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    return raw, path


def _run_plan(settings: BonsaiAISettings, context, *, execute_build: bool) -> None:
    prompt = _compose_prompt(settings)
    if not prompt:
        raise ValueError("Prompt text is empty. Open the prompt text block and add a request.")

    plan = None
    last_exc = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        settings.status = "Planning..." if attempt == 1 else f"Planning retry {attempt}/{max_attempts}..."
        try:
            plan = _ai_core().build_plan(
                prompt=prompt,
                provider=settings.provider,
                model=settings.model.strip() or None,
                api_key=_api_key(settings, context),
                reasoning_effort=settings.openai_reasoning_effort if settings.provider == "openai" else None,
                service_tier=settings.openai_service_tier if settings.provider == "openai" else None,
            )
            break
        except Exception as exc:
            last_exc = exc
    if plan is None:
        raise last_exc or RuntimeError("Planning failed.")
    _replace_text_local(settings.plan_text_name, json.dumps(plan, indent=2))
    settings.status = f"Planned {len(plan['actions'])} action(s)."
    if execute_build:
        compiled_plan = _ai_core().compile_plan(plan)
        _replace_text_local(settings.results_text_name, json.dumps(compiled_plan, indent=2))
        output_dir = Path(settings.artifact_download_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "bonsai_ai_live.ifc"
        executor_cls = load_headless_executor()
        report = executor_cls(default_storey_name="Level 0", overwrite_existing=True).execute_plan(compiled_plan, output_path)
        import_message = _import_ifc_local(output_path)
        _replace_text_local(
            settings.log_text_name,
            json.dumps(
                {
                    "summary": plan["summary"],
                    "assumptions": plan["assumptions"],
                    "authored_action_count": len(plan["actions"]),
                    "compiled_action_count": len(compiled_plan["actions"]),
                    "created": report.created,
                    "messages": report.messages,
                    "output_ifc": report.output_path,
                    "import_message": import_message,
                },
                indent=2,
            ),
        )
        settings.status = f"Built {len(report.created)} object(s)."


def _last_job_payload(settings: BonsaiAISettings) -> dict | None:
    raw = _text_to_string_local(settings.log_text_name).strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or "artifacts" not in payload:
        return None
    return payload


def _artifact_available(job: dict | None, role: str) -> bool:
    if not job:
        return False
    if role == "results":
        return bool(_client().list_artifacts(job, role="solver_result") or _client().list_artifacts(job, role="results_bundle"))
    return bool(_client().list_artifacts(job, role=role))


class BONSAI_AI_OT_open_text(bpy.types.Operator):
    bl_idname = "bonsai_ai.open_text"
    bl_label = "Open Text Block"
    bl_description = "Create the requested text block if needed and open it in the first available text editor"

    target: StringProperty()

    def execute(self, context):
        settings = context.scene.bonsai_ai_settings
        if self.target == "prompt":
            name = settings.prompt_text_name
            text = _ensure_text_block_local(name, EXAMPLE_PROMPT)
        elif self.target == "docs":
            name = settings.docs_text_name
            text = _ensure_text_block_local(name, EXAMPLE_DOC)
        elif self.target == "plan":
            name = settings.plan_text_name
            text = _ensure_text_block_local(name, "{}")
        elif self.target == "results":
            name = settings.results_text_name
            text = _ensure_text_block_local(name, "{}")
        else:
            name = settings.log_text_name
            text = _ensure_text_block_local(name, "")

        for area in context.screen.areas:
            if area.type == "TEXT_EDITOR":
                area.spaces.active.text = text
                break
        settings.status = f"Opened '{name}'."
        return {"FINISHED"}


class BONSAI_AI_OT_import_doc(bpy.types.Operator, ImportHelper):
    bl_idname = "bonsai_ai.import_doc"
    bl_label = "Import Text Doc"
    bl_description = "Load a text-based spec file into the Bonsai AI docs text block"

    filename_ext = ".txt"
    filter_glob: StringProperty(default=DOC_IMPORT_FILTER, options={"HIDDEN"})

    def execute(self, context):
        try:
            settings = _ensure_settings_initialized(context)
            raw, path = _read_doc_file(self.filepath)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        _replace_text_local(settings.docs_text_name, raw)
        settings.status = f"Loaded '{path.name}' into '{settings.docs_text_name}'."
        return {"FINISHED"}


class BONSAI_AI_OT_import_design_package(bpy.types.Operator, ImportHelper):
    bl_idname = "bonsai_ai.import_design_package"
    bl_label = "Import Design JSON"
    bl_description = "Load a design package manifest or plan JSON produced outside Blender"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            settings.status = _client().import_design_artifact(self.filepath, settings)
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_submit_design_job(bpy.types.Operator):
    bl_idname = "bonsai_ai.submit_design_job"
    bl_label = "Submit Design Job"
    bl_description = "Submit prompt and docs to the Bonsai AI bridge service and receive artifact metadata"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        prompt = _compose_prompt(settings)
        if not prompt:
            self.report({"ERROR"}, "Prompt text is empty.")
            return {"CANCELLED"}
        selection = _selection_context(settings)
        payload = {
            "provider": settings.provider,
            "model": settings.model.strip() or None,
            "prompt": prompt,
            "docs_text": _text_to_string_local(settings.docs_text_name).strip() or None,
            "scene_context": {"status": settings.status, "selection": selection},
            "reasoning_effort": settings.openai_reasoning_effort if settings.provider == "openai" else None,
            "service_tier": settings.openai_service_tier if settings.provider == "openai" else None,
        }
        try:
            job = _client().submit_design_job(settings.bridge_url, payload)
            settings.job_id = job["id"]
            _replace_text_local(settings.log_text_name, json.dumps(job, indent=2))
            settings.status = f"Submitted job {settings.job_id} ({job.get('stage', 'planning')})."
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_refresh_design_job(bpy.types.Operator):
    bl_idname = "bonsai_ai.refresh_design_job"
    bl_label = "Refresh Job"
    bl_description = "Refresh the latest bridge job status"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        if not settings.job_id:
            self.report({"ERROR"}, "No bridge job has been submitted yet.")
            return {"CANCELLED"}
        try:
            job = _client().get_job(settings.bridge_url, settings.job_id)
            _replace_text_local(settings.log_text_name, json.dumps(job, indent=2))
            settings.status = f"Job {settings.job_id}: {job['status']} {job['stage']} ({job.get('progress_pct', 0)}%)."
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_import_job_artifact(bpy.types.Operator):
    bl_idname = "bonsai_ai.import_job_artifact"
    bl_label = "Import Job Artifact"
    bl_description = "Download the selected bridge artifact and import the useful data into Blender"

    artifact_role: StringProperty()

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        if not settings.job_id:
            self.report({"ERROR"}, "No bridge job has been submitted yet.")
            return {"CANCELLED"}
        try:
            job = _client().get_job(settings.bridge_url, settings.job_id)
            message = _client().import_job_artifact(
                settings.bridge_url,
                job,
                settings,
                self.artifact_role,
                settings.artifact_download_dir,
            )
            _replace_text_local(settings.log_text_name, json.dumps(job, indent=2))
            settings.status = message
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_open_settings(bpy.types.Operator):
    bl_idname = "bonsai_ai.open_settings"
    bl_label = "Bonsai AI Settings"
    bl_description = "Open Bonsai AI settings, including API keys and OpenAI request options"

    def invoke(self, context, event):
        _ensure_settings_initialized(context)
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Quick Prompt: {SHORTCUT_HINT}")
        layout.label(text=f"Settings: {SETTINGS_SHORTCUT_HINT}")
        layout.label(text="Press OK to save these defaults into Blender user preferences.")
        _draw_provider_settings(layout, _ensure_settings_initialized(context))

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        _save_settings_to_preferences(context)
        settings.status = "Settings saved to Blender preferences."
        return {"FINISHED"}


class BONSAI_AI_OT_quick_prompt(bpy.types.Operator):
    bl_idname = "bonsai_ai.quick_prompt"
    bl_label = "Quick Prompt"
    bl_description = "Open a lightweight prompt dialog and optionally build immediately"

    prompt_input: StringProperty(name="Prompt")
    docs_input: StringProperty(name="Quick Notes")
    doc_path: StringProperty(name="Doc File", subtype="FILE_PATH")
    append_docs: BoolProperty(name="Append To Existing Docs", default=False)
    build_now: BoolProperty(name="Build Immediately", default=True)

    def invoke(self, context, event):
        settings = _ensure_settings_initialized(context)
        existing_prompt = _text_to_string_local(settings.prompt_text_name).strip()
        self.prompt_input = existing_prompt
        self.docs_input = ""
        self.doc_path = ""
        self.append_docs = False
        self.build_now = True
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        settings = _ensure_settings_initialized(context)

        layout.label(text=f"Shortcut: {SHORTCUT_HINT}")
        layout.label(text=f"Using {settings.provider} / {settings.model}")
        layout.prop(self, "prompt_input", text="Ask")
        layout.prop(self, "docs_input", text="Docs Notes")
        layout.prop(self, "doc_path")
        layout.prop(self, "append_docs")
        layout.prop(self, "build_now")
        layout.label(text="Tip: use the panel Prompt/Docs buttons for longer multi-line text.")

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        prompt = self.prompt_input.strip()
        if not prompt:
            self.report({"ERROR"}, "Prompt is empty.")
            return {"CANCELLED"}

        _replace_text_local(settings.prompt_text_name, prompt)

        try:
            docs_chunks = []
            if self.append_docs:
                existing_docs = _text_to_string_local(settings.docs_text_name).strip()
                if existing_docs:
                    docs_chunks.append(existing_docs)
            if self.docs_input.strip():
                docs_chunks.append(self.docs_input.strip())
            if self.doc_path.strip():
                raw, _ = _read_doc_file(self.doc_path.strip())
                docs_chunks.append(raw)
        except ValueError as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if docs_chunks:
            _replace_text_local(settings.docs_text_name, "\n\n".join(chunk for chunk in docs_chunks if chunk))

        try:
            _run_plan(settings, context, execute_build=self.build_now)
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_plan(bpy.types.Operator):
    bl_idname = "bonsai_ai.plan"
    bl_label = "Plan"
    bl_description = "Send the prompt to the selected model and write a validated plan JSON block"

    execute_build: BoolProperty(default=False)

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            _run_plan(settings, context, execute_build=self.execute_build)
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_apply_plan(bpy.types.Operator):
    bl_idname = "bonsai_ai.apply_plan"
    bl_label = "Build From Plan"
    bl_description = "Apply the current JSON plan text to the active Bonsai project"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        raw = _text_to_string_local(settings.plan_text_name).strip()
        if not raw:
            self.report({"ERROR"}, "Plan text is empty.")
            return {"CANCELLED"}
        try:
            plan = json.loads(raw)
            plan = _ai_core().validate_plan(plan)
            compiled_plan = _ai_core().compile_plan(plan)
            _replace_text_local(settings.results_text_name, json.dumps(compiled_plan, indent=2))
            settings.status = "Building..."
            output_dir = Path(settings.artifact_download_dir).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "bonsai_ai_live.ifc"
            executor_cls = load_headless_executor()
            report = executor_cls(default_storey_name="Level 0", overwrite_existing=True).execute_plan(compiled_plan, output_path)
            import_message = _import_ifc_local(output_path)
            _replace_text_local(
                settings.log_text_name,
                json.dumps(
                    {
                        "summary": plan["summary"],
                        "assumptions": plan["assumptions"],
                        "authored_action_count": len(plan["actions"]),
                        "compiled_action_count": len(compiled_plan["actions"]),
                        "created": report.created,
                        "messages": report.messages,
                        "output_ifc": report.output_path,
                        "import_message": import_message,
                    },
                    indent=2,
                ),
            )
            settings.status = f"Built {len(report.created)} object(s)."
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_bake_presentation(bpy.types.Operator):
    bl_idname = "bonsai_ai.bake_presentation"
    bl_label = "Bake Presentation"
    bl_description = "Rebuild the nested review tree, materials, and studio view from the latest IFC"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            ifc_path = _resolve_presentation_ifc(settings)
            report = bake_presentation(ifc_path)
            settings.status = (
                f"Presentation baked: {report.get('styled_objects', 0)} objects, "
                f"{report.get('view_collection_count', 0)} collections."
            )
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_show_all_review(bpy.types.Operator):
    bl_idname = "bonsai_ai.show_all_review"
    bl_label = "Show All"
    bl_description = "Show all collections under the Bonsai AI review hierarchy"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            changed = show_all_semantic_collections()
            settings.status = f"Review tree reset. Updated {changed} collection visibility flags."
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_isolate_review_role(bpy.types.Operator):
    bl_idname = "bonsai_ai.isolate_review_role"
    bl_label = "Isolate Role"
    bl_description = "Show only one semantic branch of the review hierarchy"

    role_name: EnumProperty(name="Role", items=ROLE_ISOLATE_ITEMS, default="Structure")

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            changed = isolate_role(self.role_name)
            settings.status = f"Isolated {self.role_name}. Updated {changed} collection visibility flags."
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_isolate_selected_branch(bpy.types.Operator):
    bl_idname = "bonsai_ai.isolate_selected_branch"
    bl_label = "Isolate Selected Branch"
    bl_description = "Show only the semantic review branch for the active selection"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            changed = isolate_selected_branch()
            settings.status = f"Selected branch isolated. Updated {changed} collection visibility flags."
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_inspect_selection(bpy.types.Operator):
    bl_idname = "bonsai_ai.inspect_selection"
    bl_label = "Inspect Selection"
    bl_description = "Dump the selected semantic element metadata into the Results text block"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            ifc_path = _resolve_presentation_ifc(settings)
            payload = selected_object_metadata(ifc_path)
            _replace_text_local(settings.results_text_name, json.dumps(payload, indent=2))
            settings.status = f"Selection metadata captured for {payload.get('active_object', 'selection')}."
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_apply_section_box(bpy.types.Operator):
    bl_idname = "bonsai_ai.apply_section_box"
    bl_label = "Section Box"
    bl_description = "Create a non-destructive cutaway box around the current selection"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            report = apply_section_box_from_selection()
            settings.status = (
                f"Section box applied to {report.get('affected_objects', 0)} objects "
                f"from {report.get('selected_objects', 0)} selected objects."
            )
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_OT_clear_section_box(bpy.types.Operator):
    bl_idname = "bonsai_ai.clear_section_box"
    bl_label = "Clear Section"
    bl_description = "Remove the active section box cutaway from the review model"

    def execute(self, context):
        settings = _ensure_settings_initialized(context)
        try:
            cleared = clear_section_box()
            settings.status = f"Section box cleared from {cleared} objects."
        except Exception as exc:
            settings.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class BONSAI_AI_PT_panel(bpy.types.Panel):
    bl_label = "Bonsai AI"
    bl_idname = "BONSAI_AI_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai AI"

    def draw(self, context):
        layout = self.layout
        settings = _ensure_settings_initialized(context)

        col = layout.column(align=True)
        col.prop(settings, "provider")
        col.prop(settings, "model")

        row = layout.row(align=True)
        row.operator("bonsai_ai.quick_prompt", text="Quick Prompt")
        row.operator("bonsai_ai.open_settings", text="Settings")
        row.operator("bonsai_ai.import_doc", text="Import Doc")
        layout.operator("bonsai_ai.import_design_package", text="Import JSON")

        bridge_box = layout.box()
        bridge_box.label(text="Bridge Client")
        bridge_box.prop(settings, "bridge_url")
        bridge_box.prop(settings, "job_id")
        bridge_box.prop(settings, "artifact_download_dir")
        row = bridge_box.row(align=True)
        row.operator("bonsai_ai.submit_design_job", text="Submit")
        row.operator("bonsai_ai.refresh_design_job", text="Refresh")

        job = _last_job_payload(settings)
        artifact_box = layout.box()
        artifact_box.label(text="Bridge Artifacts")
        if job:
            artifact_box.label(text=f"Stage: {job.get('stage', 'unknown')} ({job.get('progress_pct', 0)}%)")
            artifact_box.label(text=f"Primary IFC: {'Ready' if _artifact_available(job, 'primary_ifc') else 'Missing'}")
            artifact_box.label(text=f"Results: {'Ready' if _artifact_available(job, 'results') else 'Missing'}")
            artifact_box.label(text=f"Report: {'Ready' if _artifact_available(job, 'engineering_report') else 'Missing'}")
            row = artifact_box.row(align=True)
            row.operator("bonsai_ai.import_job_artifact", text="Import IFC").artifact_role = "primary_ifc"
            row.operator("bonsai_ai.import_job_artifact", text="Import Results").artifact_role = "results"
            if _artifact_available(job, "engineering_report"):
                artifact_box.operator("bonsai_ai.import_job_artifact", text="Import Report").artifact_role = "engineering_report"
        else:
            artifact_box.label(text="Refresh a bridge job to see importable artifacts.")

        key_box = layout.box()
        key_box.label(text=f"Quick Access: {SHORTCUT_HINT}")
        key_box.operator("bonsai_ai.quick_prompt", text="Open Quick Prompt")
        key_box.label(text="Saved API keys and defaults live in Blender preferences.")
        key_box.label(text=f"Settings shortcut: {SETTINGS_SHORTCUT_HINT}")

        docs_box = layout.box()
        docs_box.label(text="Text Blocks")
        docs_box.prop(settings, "include_docs_context")
        row = docs_box.row(align=True)
        row.operator("bonsai_ai.open_text", text="Prompt").target = "prompt"
        row.operator("bonsai_ai.open_text", text="Docs").target = "docs"
        row.operator("bonsai_ai.open_text", text="Plan").target = "plan"
        row.operator("bonsai_ai.open_text", text="Results").target = "results"
        row.operator("bonsai_ai.open_text", text="Log").target = "log"

        legacy_box = layout.box()
        legacy_box.label(text="Legacy / Debug")
        row = legacy_box.row(align=True)
        row.operator("bonsai_ai.plan", text="Plan").execute_build = False
        row.operator("bonsai_ai.apply_plan", text="Build")
        legacy_box.operator("bonsai_ai.plan", text="Plan + Build").execute_build = True

        review_box = layout.box()
        review_box.label(text="Review View")
        row = review_box.row(align=True)
        row.operator("bonsai_ai.bake_presentation", text="Bake Presentation")
        row.operator("bonsai_ai.show_all_review", text="Show All")
        row = review_box.row(align=True)
        row.operator("bonsai_ai.isolate_selected_branch", text="Isolate Selection")
        row.operator("bonsai_ai.inspect_selection", text="Inspect Selection")
        row = review_box.row(align=True)
        row.operator("bonsai_ai.isolate_review_role", text="Structure").role_name = "Structure"
        row.operator("bonsai_ai.isolate_review_role", text="Envelope").role_name = "Envelope"
        row = review_box.row(align=True)
        row.operator("bonsai_ai.isolate_review_role", text="Openings").role_name = "Openings"
        row.operator("bonsai_ai.isolate_review_role", text="Cladding").role_name = "Cladding"
        review_box.operator("bonsai_ai.isolate_review_role", text="Foundations").role_name = "Foundations"
        row = review_box.row(align=True)
        row.operator("bonsai_ai.apply_section_box", text="Section Box")
        row.operator("bonsai_ai.clear_section_box", text="Clear Section")

        layout.separator()
        layout.label(text=f"Status: {settings.status}")


CLASSES = (
    BonsaiAIAddonPreferences,
    BonsaiAISettings,
    BONSAI_AI_OT_open_text,
    BONSAI_AI_OT_import_doc,
    BONSAI_AI_OT_import_design_package,
    BONSAI_AI_OT_submit_design_job,
    BONSAI_AI_OT_refresh_design_job,
    BONSAI_AI_OT_import_job_artifact,
    BONSAI_AI_OT_open_settings,
    BONSAI_AI_OT_quick_prompt,
    BONSAI_AI_OT_plan,
    BONSAI_AI_OT_apply_plan,
    BONSAI_AI_OT_bake_presentation,
    BONSAI_AI_OT_show_all_review,
    BONSAI_AI_OT_isolate_review_role,
    BONSAI_AI_OT_isolate_selected_branch,
    BONSAI_AI_OT_inspect_selection,
    BONSAI_AI_OT_apply_section_box,
    BONSAI_AI_OT_clear_section_box,
    BONSAI_AI_PT_panel,
)


def _register_keymaps() -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return

    km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
    addon_keymaps.append((km, km.keymap_items.new("bonsai_ai.quick_prompt", "T", "PRESS", oskey=True)))
    addon_keymaps.append((km, km.keymap_items.new("bonsai_ai.quick_prompt", "T", "PRESS", ctrl=True)))
    addon_keymaps.append((km, km.keymap_items.new("bonsai_ai.open_settings", "T", "PRESS", oskey=True, shift=True)))
    addon_keymaps.append((km, km.keymap_items.new("bonsai_ai.open_settings", "T", "PRESS", ctrl=True, shift=True)))


def _unregister_keymaps() -> None:
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bonsai_ai_settings = PointerProperty(type=BonsaiAISettings)
    _register_keymaps()


def unregister():
    _unregister_keymaps()
    del bpy.types.Scene.bonsai_ai_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
