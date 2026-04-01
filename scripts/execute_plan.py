#!/usr/bin/env python3
"""Execute a BIM plan JSON and produce an IFC file.

Usage:
    echo '{"version":"1","units":"meters","actions":[...]}' | python3 scripts/execute_plan.py --output model.ifc
    python3 scripts/execute_plan.py --plan-file plan.json --output model.ifc
    python3 scripts/execute_plan.py --plan-file plan.json --output model.ifc --append

Output (JSON to stdout):
    {
        "success": true,
        "output_path": "/absolute/path/to/model.ifc",
        "actions_executed": 47,
        "errors": [],
        "scene_summary": "Project: AI Project\\nStoreys: ...",
        "element_counts": {"walls": 12, "slabs": 5, ...}
    }

Exit codes:
    0: success (JSON result on stdout)
    1: failure (JSON error on stdout)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path so imports work when called standalone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _error(message: str) -> int:
    """Print a JSON error to stdout and return exit code 1."""
    print(json.dumps({"success": False, "errors": [message]}))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute a BIM plan JSON and produce an IFC file."
    )
    parser.add_argument(
        "--plan-file",
        help="Path to plan JSON file. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output IFC file path.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing IFC file instead of overwriting.",
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Plan is already compiled (skip compile_plan step).",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Read the plan
    # ------------------------------------------------------------------
    if args.plan_file:
        plan_path = Path(args.plan_file)
        if not plan_path.exists():
            return _error(f"Plan file not found: {args.plan_file}")
        raw = plan_path.read_text()
    else:
        # Read from stdin
        if sys.stdin.isatty():
            return _error("No plan provided. Pipe JSON via stdin or use --plan-file.")
        raw = sys.stdin.read()

    if not raw.strip():
        return _error("Empty plan input.")

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid JSON: {exc}")

    # ------------------------------------------------------------------
    # Ensure plan has required top-level keys
    # ------------------------------------------------------------------
    if "version" not in plan:
        plan["version"] = "1"
    if "units" not in plan:
        plan["units"] = "meters"
    if "summary" not in plan:
        plan["summary"] = "Executed plan"
    if "assumptions" not in plan:
        plan["assumptions"] = []
    if "actions" not in plan:
        return _error("Plan has no 'actions' array.")

    if not plan["actions"]:
        return _error("Plan 'actions' array is empty.")

    # ------------------------------------------------------------------
    # Import Bonsai AI modules (after path setup)
    # ------------------------------------------------------------------
    try:
        from bonsai_ai_core import compile_plan as compile_core_plan
    except ImportError as exc:
        return _error(f"Failed to import bonsai_ai_core: {exc}")

    try:
        from bonsai_ai.ifc_author import AuthoringError, IfcAuthor
        from bonsai_ai.execution import HeadlessIfcExecutor
        from bonsai_ai.iterative_planner import _normalize_actions
    except ImportError as exc:
        return _error(f"Failed to import bonsai_ai: {exc}")

    # ------------------------------------------------------------------
    # Normalize LLM quirks in action types and field names
    # ------------------------------------------------------------------
    _normalize_actions(plan["actions"])

    # ------------------------------------------------------------------
    # Compile (semantic -> primitive actions)
    # ------------------------------------------------------------------
    if not args.skip_compile:
        try:
            plan = compile_core_plan(plan)
        except Exception as exc:
            return _error(f"Compilation failed: {exc}")

    # ------------------------------------------------------------------
    # Ensure output directory exists
    # ------------------------------------------------------------------
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Delete existing file if not appending
    # ------------------------------------------------------------------
    if not args.append and output_path.exists():
        output_path.unlink()

    # ------------------------------------------------------------------
    # Execute via HeadlessIfcExecutor
    # ------------------------------------------------------------------
    errors = []
    executor = HeadlessIfcExecutor(overwrite_existing=not args.append)
    try:
        report = executor.execute_plan(plan, str(output_path))
    except Exception as exc:
        return _error(f"Execution failed: {exc}")

    # ------------------------------------------------------------------
    # Read back scene summary and element counts
    # ------------------------------------------------------------------
    try:
        author = IfcAuthor(str(output_path))
        summary = author.scene_summary()
        debug_raw = author.debug_dump()
        element_counts = json.loads(debug_raw)
    except Exception as exc:
        summary = f"(Could not read scene summary: {exc})"
        element_counts = {}

    # ------------------------------------------------------------------
    # Output JSON result
    # ------------------------------------------------------------------
    result = {
        "success": True,
        "output_path": str(output_path),
        "actions_executed": len(report.created),
        "errors": errors,
        "scene_summary": summary,
        "element_counts": element_counts,
        "created": report.created[:50],  # cap for readability
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
