bl_info = {
    "name": "Bonsai AI",
    "author": "OpenAI Codex",
    "version": (0, 2, 0),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Bonsai AI",
    "description": "Plan and create native IFC elements in Bonsai using OpenAI, Anthropic, or Gemini APIs.",
    "category": "3D View",
}

from .ui import register, unregister

__all__ = ["register", "unregister"]
