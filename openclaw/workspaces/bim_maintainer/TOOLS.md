# TOOLS.md - Bonsai AI Maintainer

## Core Tools

### `memory_search`

Use first to recall prior session context, codebase decisions, and improvement items.

Covers:
- `MEMORY.md`
- `memory/`
- `reference/`
- `knowledge/`

### `memory_get`

Use when you already know which memory result you need and want fuller text.

### `read`

Use extensively. You need to read source code regularly. You can also read images (screenshots, diagrams, spec sheets).

- Application source: `/Users/alanknudson/Applications/Bonsai_ai/src/bonsai_ai/`
- Blender addon: `/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_blender/`
- Core library: `/Users/alanknudson/Applications/Bonsai_ai/bonsai_ai_core/`
- Tests: `/Users/alanknudson/Applications/Bonsai_ai/tests/`
- Build scripts: `/Users/alanknudson/Applications/Bonsai_ai/scripts/`
- Project config: `/Users/alanknudson/Applications/Bonsai_ai/pyproject.toml`
- Operator workspace: `/Users/alanknudson/Applications/Bonsai_ai/openclaw/`
- Operator project logs: `/Users/alanknudson/Applications/Bonsai_ai/openclaw/projects/`

### `sessions_spawn`

Use to:
- Ask the operator agent for context about how a feature is used in practice
- Delegate focused coding tasks to subagents after plan is agreed
- Delegate test runs or verification tasks

### `web_fetch`

Use for:
- IfcOpenShell API docs when changing IFC authoring code
- Provider API docs (OpenAI, Anthropic, Gemini) when modifying planner code
- Python stdlib or library docs

## Knowledge Graph Maintenance

### Daily routine

Each session, after reading startup files:

1. `git -C /Users/alanknudson/Applications/Bonsai_ai log --oneline -15` -- what changed?
2. For each changed file, read it and check if `knowledge/modules/<module>.md` is still accurate
3. Update knowledge files that are stale
4. Add new knowledge files for new modules
5. Update `knowledge/index.md` if the module map changed
6. Update `reference/codebase-state.md` with current snapshot

### When to create a new knowledge file

- A new module or significant file is added to the codebase
- A pattern emerges that should be documented (e.g., "how error recovery works across all providers")
- An architecture decision is made that future sessions need to know about

### Knowledge file format

```markdown
# <Module Name>

## Purpose
(One sentence)

## How It Works
(Key functions, data flow, dependencies)

## Current State
(What's implemented, what's stubbed, what's missing)

## Known Issues
(Bugs, limitations, tech debt)

## Last Reviewed
YYYY-MM-DD
```

## Testing

```bash
# Run specific test module
PYTHONPATH=src:. python3 -m unittest tests.test_execution

# Run all tests
PYTHONPATH=src:. python3 -m unittest discover -s tests

# Compile check (no runtime)
PYTHONPYCACHEPREFIX=/tmp/bonsai_pycache python3 -m compileall bonsai_ai_blender bonsai_ai_core

# Package addon after changes to core/src
python3 scripts/package_addon.py
```

## Git Workflow

- Always work on a feature branch, never directly on main
- Branch naming: `feature/<short-description>` or `fix/<short-description>`
- Commit messages: what changed and why
- Don't force push, don't amend published commits
- After building a feature, report: branch name, what changed, how to test

## Key Architecture Notes

- `planner.py` (src) uses raw urllib for HTTP -- no SDK dependencies
- `providers.py` (core) uses the same raw HTTP approach
- `ifc_author.py` is the largest module -- handles all IFC geometry creation via IfcOpenShell
- `tool_specs.py` defines the planner's available actions -- changes here affect all 3 providers
- The Blender addon vendors both `bonsai_ai_core` and `bonsai_ai` into `bonsai_ai_blender/vendor/`
- After changing core or src, the addon zip needs rebuilding via `scripts/package_addon.py`
- Elements in ifc_author.py are currently write-only -- no update/swap mechanism exists
- The catalog system (catalog_selector → catalog_resolver) maps roles to real sections but only during initial creation
