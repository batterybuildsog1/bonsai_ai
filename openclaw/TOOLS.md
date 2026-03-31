# TOOLS.md - Bonsai AI Operator

## Core Tools

### `memory_search`

Use first when you need to recall project context, prompt patterns, or prior session work.

Covers:
- `MEMORY.md`
- `memory/`
- `projects/`
- `reference/`

### `memory_get`

Use when you already know which memory result you need and want fuller text.

### `read`

Use to inspect specific files. You can read both text files and images.

**Text files:**
- Project context: `projects/<name>/context.md`
- Site constraints: `projects/<name>/site/*.md`
- Component specs: `projects/<name>/components/selections/*.md`
- Bonsai source (reference only): `/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/`
- Tool specs: `/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/tool_specs.py`
- Project outputs: `/Users/alanknudson/Applications/Bonsai_ai/out/`

**Image files (vision-capable):**
- Inspiration photos: `projects/<name>/inspiration/*.jpg`, `*.png`
- Site photos: `projects/<name>/site/photos/*.jpg`, `*.png`
- Spec sheet images: `projects/<name>/components/specs/*.jpg`, `*.png`
- Rendered views: any `.jpg`, `.png` in the project tree

When reading images, describe what you see in terms relevant to BIM authoring:
architectural features, materials, proportions, structural systems, facade treatments.

### `sessions_spawn`

Use to hand off to the `bim_maintainer` agent when:
- You need a new authoring tool that doesn't exist yet
- You hit a bug or limitation in the planner or IFC author
- A pattern of failures suggests a code fix is more effective than prompt workarounds
- You want to discuss what it would take to add a capability

Include in your handoff message:
- What you're trying to do
- Why current tools don't cover it
- What the tool interface might look like (name, inputs, behavior)
- Any relevant project context

## Per-Project Documents

Each project under `projects/<name>/` has three document categories.

See `reference/project-template.md` for the full structure and starter content.

### Reading project documents at session start

1. `projects/<name>/context.md` -- always read first (design intent)
2. `projects/<name>/site/index.md` -- check before envelope/massing prompts
3. `projects/<name>/components/index.md` -- check before using dimensions
4. `projects/<name>/inspiration/index.md` -- check for design references

### When new documents are uploaded

When the human adds files to a project:
- **Images**: Read them directly. Describe architectural features and update `index.md`.
- **PDFs**: Check for `.txt` extraction alongside. If missing, note it. Read the `.txt`.
- **Spec sheets**: Extract key properties into `selections/<system>.md` with "Impact on Model" section.

## Bonsai AI Execution

### CLI (direct)

```bash
PYTHONPATH=src python3 -m bonsai_ai.cli \
  --provider openai \
  --output /absolute/path/output.ifc \
  --prompt "..."
```

### CLI (design pipeline with analysis)

```bash
python3 -m bonsai_ai.design_pipeline_cli \
  --provider openai \
  --output-dir ./out/<project> \
  --prompt "..." \
  --analysis-domain gravity wind
```

### Blender Addon

- Sidebar panel: `View3D > Sidebar > Bonsai AI`
- Settings shortcut: `Cmd+Shift+T` / `Ctrl+Shift+T`
- Execute shortcut: `Cmd+T` / `Ctrl+T`

## Provider Defaults

| Provider | Model | Notes |
|----------|-------|-------|
| OpenAI | gpt-5.4 | reasoning: medium, tier: priority, vision-capable |
| Anthropic | claude-opus-4-6 | good for complex plans |
| Gemini | gemini-2.5-flash-lite | fastest for simple iterations |

## Execution Scripts

### `scripts/execute_plan.py` -- Execute a BIM plan

Takes a JSON plan (via stdin or `--plan-file`), compiles it, executes via IfcAuthor, and outputs structured JSON.

**Input:** BIM plan JSON with `version`, `units`, `summary`, `assumptions`, `actions`.

**Output (JSON to stdout):**
```json
{
  "success": true,
  "output_path": "/absolute/path/to/model.ifc",
  "actions_executed": 47,
  "errors": [],
  "scene_summary": "Project: AI Project\nStoreys: ...",
  "element_counts": {"walls": 12, "slabs": 5, "columns": 20, ...},
  "created": ["Ground Floor", "Level 1", "GF-Grid-Col-A1", ...]
}
```

**Flags:**
- `--output <path>` (required): IFC output file path
- `--plan-file <path>`: read plan from file instead of stdin
- `--append`: add to existing IFC instead of overwriting
- `--skip-compile`: plan is already in compiled/primitive form

**Usage:**
```bash
cd /Users/alanknudson/Applications/Bonsai_ai && \
PYTHONPATH=src:. python3 scripts/execute_plan.py \
  --output out/project/model.ifc <<'PLAN'
{"version":"1","units":"meters","summary":"...","assumptions":[],"actions":[...]}
PLAN
```

### `scripts/query_scene.py` -- Inspect model state

Non-destructive model inspector. Returns structured information about an existing IFC file.

**Output (JSON to stdout):**
```json
{
  "success": true,
  "model_path": "/absolute/path/to/model.ifc",
  "element_counts": {"walls": 12, "slabs": 5, ...},
  "storeys": [
    {"name": "Ground Floor", "elevation": 0.0, "element_count": 15}
  ],
  "scene_summary": "Project: AI Project\nStoreys: ...",
  "validation": {
    "orphan_elements": 0,
    "elements_without_storey": []
  }
}
```

**Usage:**
```bash
cd /Users/alanknudson/Applications/Bonsai_ai && \
PYTHONPATH=src:. python3 scripts/query_scene.py out/project/model.ifc
```

## Iterative Builder (CLI)

Session-based iterative planner that maintains conversation context across all phases:

```bash
cd /Users/alanknudson/Applications/Bonsai_ai && \
PYTHONPATH=src python3 -m bonsai_ai.cli \
  --iterative \
  --output out/project/model.ifc \
  --prompt "Design a 2-story office building..."
```

The `--iterative` flag uses a single OpenClaw session for all phases, so the agent remembers storey names, grid origins, and prior decisions. This produces better spatial consistency than the default phased planner.

## Local Runtime Notes

- All dimensions in meters
- Max planner rounds: 12
- Planner temperature: 0.1
- IFC output format: IFC4
- Scene summary is injected into each planner round automatically
- Progress summary carries across rounds for multi-step plans
- imageModel is configured to gpt-5.4 for vision tasks
