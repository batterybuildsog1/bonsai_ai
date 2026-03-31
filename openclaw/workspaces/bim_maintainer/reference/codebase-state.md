# Codebase State

## Last Updated

2026-03-30 (initial snapshot)

## Architecture Summary

Bonsai AI is a Python-based BIM authoring system that generates native IFC files from natural language prompts.

Three execution paths:
1. **CLI** (`src/bonsai_ai/cli.py`) -- direct prompt-to-IFC
2. **Blender Addon** (`bonsai_ai_blender/`) -- interactive UI in Blender 4.4+
3. **Bridge Server** (`src/bonsai_ai_bridge/server.py`) -- FastAPI REST interface

Three AI providers, all using raw HTTP (no SDK):
- OpenAI gpt-5.4 (primary)
- Anthropic claude-opus-4-6
- Gemini gemini-2.5-flash-lite

## Module Sizes (approximate)

| Module | Size | Complexity |
|--------|------|------------|
| ifc_author.py | 36KB | High -- core geometry engine |
| structural_source.py | 47KB | High -- structural model extraction |
| pynite_backend.py | 26KB | High -- FEA solver integration |
| ui.py (blender) | 33KB | Medium -- Blender UI/operators |
| planner.py (src) | 275 lines | Low -- clean provider dispatch |
| tool_specs.py | 240 lines | Low -- declarative tool definitions |
| cli.py | 91 lines | Low -- thin CLI wrapper |

## Recent Changes

(Updated after each session)

## Test Coverage

20 test modules in `tests/`. Key ones:
- test_execution.py -- IFC authoring integration
- test_ifc_author.py -- low-level IFC operations
- test_providers.py -- provider API integration
- test_pynite_backend.py -- structural analysis
- test_schema.py -- plan validation
