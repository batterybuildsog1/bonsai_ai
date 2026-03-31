"""Runtime imports for the Blender addon."""

from __future__ import annotations


def load_core():
    try:
        from .vendor import bonsai_ai_core  # type: ignore

        return bonsai_ai_core
    except ImportError:
        import bonsai_ai_core

        return bonsai_ai_core


def load_headless_executor():
    try:
        from .vendor.bonsai_ai.execution import HeadlessIfcExecutor  # type: ignore

        return HeadlessIfcExecutor
    except ImportError:
        from bonsai_ai.execution import HeadlessIfcExecutor

        return HeadlessIfcExecutor
