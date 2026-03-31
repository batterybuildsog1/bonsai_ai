from __future__ import annotations

bl_info = {
    "name": "Bonsai AI",
    "author": "OpenAI Codex",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Bonsai AI",
    "description": "Direct prompt-to-IFC authoring for Blender Bonsai without MCP.",
    "category": "3D View",
}


def register() -> None:
    """Legacy no-op addon entrypoint.

    The maintained Blender UI now lives in the `bonsai_ai_blender` package.
    """


def unregister() -> None:
    """Legacy no-op addon entrypoint."""
