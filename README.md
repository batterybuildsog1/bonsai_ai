# Bonsai AI

`Bonsai AI` gives you a simpler path than the Claude Desktop + MCP workflow:

- send a natural-language building prompt to OpenAI, Anthropic, or Gemini over API
- turn that prompt into structured BIM tool calls
- author native IFC objects for Bonsai directly

The primary implementation in this repo is the direct path under [src/bonsai_ai](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai).

## Primary path

The direct integration does not require Claude Desktop or MCP.

Files:

- [src/bonsai_ai/cli.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/cli.py): prompt-to-IFC CLI
- [src/bonsai_ai/planner.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/planner.py): multi-provider planner
- [src/bonsai_ai/ifc_author.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/ifc_author.py): native IFC authoring engine
- [src/bonsai_ai/blender_addon.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/blender_addon.py): Blender addon entry point
- [dist/bonsai_ai_addon.zip](/Users/alanknudson/Applications/Bonsai_ai/dist/bonsai_ai_addon.zip): ready-to-install Blender addon zip

Default model targets:

- OpenAI: `gpt-5.4`
- Anthropic: `claude-opus-4-6`
- Gemini: `gemini-2.5-flash-lite`

OpenAI requests in the Blender addon now default to:

- reasoning effort: `medium`
- service tier: `priority`

Supported authoring primitives:

- projects
- storeys
- rectangular slabs
- straight walls
- columns
- curtain walls with `IfcCurtainWall` plus `IfcPlate` panels
- hosted doors
- hosted windows

## Quick start

Set one of these environment variables:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

Then generate an IFC directly:

```bash
PYTHONPATH=src python3 -m bonsai_ai.cli \
  --provider openai \
  --output /absolute/path/office.ifc \
  --prompt "Create a 20m x 30m office slab on Level 0, add perimeter walls 3m high, then add a south curtain wall with 1.5m x 3m panels."
```

Open the resulting IFC in Bonsai.

## Blender addon

The packaged addon is already built:

- [dist/bonsai_ai_addon.zip](/Users/alanknudson/Applications/Bonsai_ai/dist/bonsai_ai_addon.zip)

Install it in Blender 4.4+:

1. `Edit -> Preferences -> Add-ons -> Install`
2. Choose `dist/bonsai_ai_blender.zip`
3. Enable `Bonsai AI`
4. Open the `Bonsai AI` panel in the 3D view sidebar
5. Press `Cmd+T` on macOS or `Ctrl+T` on Windows/Linux in the 3D View to open settings
6. Paste your API key, confirm the OpenAI model/reasoning settings, and enter a prompt

The addon also supports a docs context block:

- `Import Doc` loads `.txt`, `.md`, `.json`, `.csv`, `.yaml`, or `.yml` into a reusable docs text block
- `Prompt` and `Docs` blocks are merged before planning so engineering notes can influence the generated BIM plan

## Alternative bridge path

There is also a bridge-based implementation if you want a local HTTP planner service:

- [src/bonsai_ai_bridge/server.py](/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai_bridge/server.py)
- [blender_addon/bonsai_ai_addon.py](/Users/alanknudson/Applications/Bonsai_ai/blender_addon/bonsai_ai_addon.py)

That path is optional. The direct `src/bonsai_ai` flow is the simplest place to start.

## Verification

Verified locally in this workspace:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_providers
PYTHONPYCACHEPREFIX=/tmp/bonsai_pycache python3 -m compileall bonsai_ai_blender bonsai_ai_core scripts/package_addon.py
python3 scripts/package_addon.py
```

The targeted provider test passed, the Blender addon/core sources compiled, and fresh `dist/bonsai_ai_addon.zip` plus `dist/bonsai_ai_blender.zip` packages were built successfully.

## Docs references

The provider/model choices were checked against primary docs current on March 27, 2026:

- [OpenAI API docs](https://platform.openai.com/docs/api-reference/responses)
- [Anthropic tool use docs](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)
- [Google Gemini model docs](https://ai.google.dev/gemini-api/docs/models)
- [IfcOpenShell geometry creation docs](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html)

I could not fully runtime-test the Blender/Bonsai UI in this shell because this environment is not an active Blender session.
