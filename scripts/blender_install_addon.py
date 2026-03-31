from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def _script_argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--module", default="bonsai_ai_blender")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--service-tier")
    parser.add_argument("--set-api-key-from-stdin", action="store_true")
    args = parser.parse_args(_script_argv())

    zip_path = Path(args.zip).resolve()
    if not zip_path.exists():
        raise SystemExit(f"Addon zip not found: {zip_path}")

    bpy.ops.preferences.addon_install(filepath=str(zip_path), overwrite=True)
    bpy.ops.preferences.addon_enable(module=args.module)
    addon = bpy.context.preferences.addons.get(args.module)
    if addon is None:
        raise SystemExit(f"Addon {args.module} is not enabled after install.")

    prefs = getattr(addon, "preferences", None)
    if prefs is not None:
        if args.provider:
            prefs.provider = args.provider
        if args.model:
            prefs.model = args.model
        if args.reasoning_effort:
            prefs.openai_reasoning_effort = args.reasoning_effort
        if args.service_tier:
            prefs.openai_service_tier = args.service_tier
        if args.set_api_key_from_stdin:
            api_key = sys.stdin.read().strip()
            if api_key:
                if getattr(prefs, "provider", args.provider or "openai") == "openai":
                    prefs.openai_api_key = api_key
                elif getattr(prefs, "provider", args.provider or "openai") == "anthropic":
                    prefs.anthropic_api_key = api_key
                else:
                    prefs.google_api_key = api_key
    bpy.ops.wm.save_userpref()
    print(f"Installed and enabled {args.module} from {zip_path}")


if __name__ == "__main__":
    main()
