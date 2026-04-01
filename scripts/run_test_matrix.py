#!/usr/bin/env python3
"""Run a 4-difficulty x 2-model comparison test matrix.

Runs 4 building prompts (simple -> very hard) against 2 models (GPT-5.4 and
Claude Opus) using the existing direct planner or OpenClaw iterative session.

Usage:
    # Direct planner (needs API keys in env or OpenClaw auth-profiles):
    python3 scripts/run_test_matrix.py

    # Single difficulty only:
    python3 scripts/run_test_matrix.py --difficulty simple

    # Single model only:
    python3 scripts/run_test_matrix.py --model openai

    # Via OpenClaw iterative session:
    python3 scripts/run_test_matrix.py --via-openclaw

    # Dry run (plan only, no IFC):
    python3 scripts/run_test_matrix.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ──────────────────────────── Prompts ────────────────────────────────────────

PROMPTS: Dict[str, str] = {
    "simple": """\
Design a single-story steel warehouse:
- 30m x 20m rectangular footprint, clear span, 6m eave height
- Origin at (0, 0, 0), long axis along X
- Steel rigid frame: 6 columns at grid intersections (0.3x0.3m HSS)
  - Column grid: 3 bays @ 10m along X (x=0, 10, 20, 30), 1 bay @ 20m along Y (y=0, 20)
- Steel beams (0.3x0.4m) connecting columns at 6m height along X and Y
- Metal roof: single concrete slab (0.15m thick) at 6m representing roof deck
- Concrete slab on grade (0.2m thick) at z=0
- 2 overhead doors on the south wall (y=0): each 4m wide x 4.5m tall, centered at x=10 and x=20
- 1 personnel door on the east wall (x=30): 1.0m wide x 2.1m tall, centered at y=10
- Perimeter walls (0.2m metal panel) on all 4 sides, full height
- No windows
""",

    "medium": """\
Design a 2-story office building:
- 20m x 15m rectangular footprint, origin at (0, 0, 0), long axis along X
- Ground floor height 4.0m, upper floor height 3.5m (total 7.5m to roof)
- Structural grid: 4m x 5m spacing
  - X grid: 5 bays @ 4m (columns at x=0, 4, 8, 12, 16, 20)
  - Y grid: 3 bays @ 5m (columns at y=0, 5, 10, 15)
- Concrete columns (0.35x0.35m) at all 24 grid intersections, both floors
- Concrete beams (0.3x0.5m) spanning between columns at 4.0m and 7.5m
- Concrete slabs (0.2m thick) at ground (z=0), level 1 (z=4.0), and roof (z=7.5)
- Perimeter walls (0.2m concrete) on all 4 sides, both floors
- Windows on all 4 sides: 1.8m wide x 1.5m tall, sill at 0.9m above floor
  - Spaced every 4m along X walls (at x=2, 6, 10, 14, 18)
  - Spaced every 5m along Y walls (at y=2.5, 7.5, 12.5)
- Main entrance on the south wall (y=0): glass double door 2.0m wide x 2.4m tall at x=10
- Rear exit on the north wall (y=15): single door 1.0m x 2.1m at x=10
""",

    "hard": """\
Design a 5-story commercial building:
- 40m x 25m footprint, 8m structural grid (5 bays x 3 bays + 1 partial)
  - X grid at x=0, 8, 16, 24, 32, 40
  - Y grid at y=0, 8, 16, 25 (last bay is 9m)
- Origin at (0, 0, 0), long axis along X
- Ground floor 4.5m (retail), upper floors 4.0m each (total 20.5m)
- Storeys: Ground (z=0), Level 1 (z=4.5), Level 2 (z=8.5), Level 3 (z=12.5), Level 4 (z=16.5), Roof (z=20.5)
- Steel columns (0.3x0.3m) at all grid intersections on every floor
- Steel beams (0.3x0.5m) spanning between columns at each level
- Concrete slabs (0.2m thick) at each level including ground and roof
- East and west walls (x=0, x=40): concrete walls (0.2m) with punched windows
  - Windows: 1.8m x 1.5m, sill 0.9m, spaced every 4m
- North wall (y=25): concrete wall (0.2m) with punched windows same as east/west
- South ground floor: glass curtain wall (1.5m x 4.0m panels) across full width
- South upper floors: concrete wall (0.2m) with windows
- Mezzanines at floors 3 and 4 (z=12.5 and z=16.5): east and west sides, 10m deep from each edge
- Main entrance: south facade double door 2.4m wide x 2.8m tall, centered at x=20
- Service door: north facade single door 1.2m x 2.4m at x=20
""",

    "very_hard": """\
Design a mixed-use building with underground parking:
- 60m x 30m rectangular footprint, origin at (0, 0, 0), long axis along X
- 8 storeys total: 2 underground parking, 1 ground retail, 5 upper office floors
- Structural grid: 7.5m x 10m
  - X grid: 8 bays @ 7.5m (columns at x=0, 7.5, 15, 22.5, 30, 37.5, 45, 52.5, 60)
  - Y grid: 3 bays @ 10m (columns at y=0, 10, 20, 30)
- Storeys with elevations:
  - Parking B2: z=-7.0 (3.5m floor-to-floor)
  - Parking B1: z=-3.5 (3.5m floor-to-floor)
  - Ground (retail): z=0.0 (5.0m floor-to-floor)
  - Level 1: z=5.0 (4.0m floor-to-floor)
  - Level 2: z=9.0 (4.0m)
  - Level 3: z=13.0 (4.0m)
  - Level 4: z=17.0 (4.0m)
  - Level 5: z=21.0 (4.0m)
  - Roof: z=25.0
- Steel columns (0.4x0.4m) at all 36 grid intersections, all 8 levels
- Steel beams (0.3x0.6m) spanning between columns at every level
- Concrete slabs (0.25m) at every level from B2 to roof (10 total)
- Basement walls (0.3m concrete) around full perimeter at B2 and B1 levels
- Ground floor south facade (y=0): full glass curtain wall (2.0m x 4.5m panels)
- Ground floor east/west/north: concrete walls (0.2m) with large retail windows (3.0m x 3.0m, sill 0.5m) every 7.5m
- Upper floors (L1-L5) all facades: metal panel walls (0.15m) with ribbon windows (2.5m x 1.5m, sill 0.9m) every 3.75m
- Parking levels: concrete walls (0.3m) on perimeter, no windows
- 2 stair cores: located at x=7.5 and x=52.5, spanning y=10 to y=20
  - Each core: 4 walls forming a 7.5m x 10m shaft, all levels from B2 to roof
  - Door openings: 1.0m x 2.1m on each level per core
- 2 elevator shafts: at x=15 and x=45, spanning y=12.5 to y=17.5
  - Each shaft: 4 walls forming a 3.0m x 5.0m enclosure, all levels
  - Door openings: 1.2m x 2.4m on each level per shaft
- Main retail entrance: south facade, double door 3.0m x 3.5m at x=30
- Parking ramp entry: north facade at ground level, overhead door 6.0m x 3.0m at x=30
- Service entrance: east facade, single door 1.2m x 2.4m at x=60, y=15
""",
}


# ──────────────────────────── Model config ───────────────────────────────────

MODELS = {
    "openai": {
        "provider": "openai",
        "model": "gpt-5.4",
        "label": "GPT-5.4",
    },
    "anthropic": {
        "provider": "anthropic",
        "model": "claude-opus-4-6",
        "label": "Claude Opus 4.6",
    },
}

DIFFICULTIES = ["simple", "medium", "hard", "very_hard"]
DIFFICULTY_LABELS = {
    "simple": "Simple (warehouse)",
    "medium": "Medium (2-story office)",
    "hard": "Hard (5-story commercial)",
    "very_hard": "Very Hard (mixed-use + parking)",
}

EXPECTED_ELEMENT_RANGE = {
    "simple": (20, 40),
    "medium": (50, 100),
    "hard": (150, 300),
    "very_hard": (400, 700),
}


# ──────────────────────────── Imports (lazy) ─────────────────────────────────

def _import_planner():
    from bonsai_ai.planner import (
        DEFAULT_ENV_VARS,
        DEFAULT_MODELS as PLANNER_DEFAULT_MODELS,
        PlannerError,
        create_plan,
    )
    return create_plan, PlannerError, DEFAULT_ENV_VARS

def _import_author():
    from bonsai_ai.ifc_author import AuthoringError, IfcAuthor
    return IfcAuthor, AuthoringError

def _import_iterative():
    from bonsai_ai.iterative_planner import create_iterative_plan_via_openclaw
    return create_iterative_plan_via_openclaw


# ──────────────────────────── API key resolution ─────────────────────────────

OPENCLAW_AUTH_PATHS = [
    Path.home() / ".openclaw/agents/bim_operator/agent/auth-profiles.json",
    Path.home() / ".openclaw/agents/main/agent/auth-profiles.json",
]


def resolve_api_key(provider: str) -> Optional[str]:
    """Resolve API key from env vars or OpenClaw auth-profiles."""
    env_vars = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    env_var = env_vars.get(provider)
    if env_var:
        value = os.environ.get(env_var)
        if value:
            return value

    # Try OpenClaw auth-profiles
    profile_key = f"{provider}:default"
    for path in OPENCLAW_AUTH_PATHS:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            profiles = data.get("profiles", {})
            profile = profiles.get(profile_key, {})
            key = profile.get("key")
            if key:
                return key
        except Exception:
            continue
    return None


# ──────────────────────────── Direct planner runner ──────────────────────────

MAX_ROUNDS = 12


def run_direct_planner(
    provider: str,
    model: str,
    api_key: str,
    prompt: str,
    output_dir: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run the direct planner loop (re-uses logic from run_comparison_test.py)."""
    create_plan, PlannerError, _ = _import_planner()
    IfcAuthor, AuthoringError = _import_author()

    output_dir.mkdir(parents=True, exist_ok=True)
    ifc_path = output_dir / "building.ifc"
    plan_path = output_dir / "plan.json"
    log_path = output_dir / "build_log.txt"

    author = IfcAuthor(str(ifc_path))
    all_calls: list[dict] = []
    progress_lines: list[str] = []
    log_lines: list[str] = []
    seen_rounds: set = set()
    failed_calls: set = set()
    element_types: Counter = Counter()
    error_count = 0

    start_time = time.time()
    log_lines.append(f"Provider: {provider}")
    log_lines.append(f"Model: {model}")
    log_lines.append(f"Prompt: {prompt[:300]}...")
    log_lines.append(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append("")

    for round_num in range(MAX_ROUNDS):
        log_lines.append(f"--- Round {round_num + 1} ---")
        round_start = time.time()

        try:
            plan = create_plan(
                provider=provider,
                model=model,
                api_key=api_key,
                user_prompt=prompt,
                scene_summary=author.scene_summary(),
                progress_summary="\n".join(progress_lines),
            )
        except Exception as exc:
            log_lines.append(f"PLANNER ERROR: {exc}")
            error_count += 1
            break

        round_elapsed = time.time() - round_start
        log_lines.append(
            f"Planning took {round_elapsed:.1f}s, "
            f"got {len(plan.tool_calls)} tool calls"
        )

        if not plan.tool_calls:
            log_lines.append("No tool calls - planner considers work complete.")
            break

        # Duplicate round detection
        round_sig = tuple(
            (c.name, json.dumps(c.arguments, sort_keys=True))
            for c in plan.tool_calls
        )
        if round_sig in seen_rounds:
            log_lines.append("Planner repeated a previous round, aborting.")
            error_count += 1
            break
        seen_rounds.add(round_sig)

        for call in plan.tool_calls:
            all_calls.append({
                "round": round_num + 1,
                "id": call.id,
                "name": call.name,
                "arguments": call.arguments,
            })

        if dry_run:
            for call in plan.tool_calls:
                msg = f"[dry-run] {call.name}: {json.dumps(call.arguments, sort_keys=True)}"
                progress_lines.append(msg)
                log_lines.append(msg)
            continue

        # Execute
        for call in plan.tool_calls:
            try:
                result = author.apply_tool_call(call.name, call.arguments)
                progress_lines.append(f"{result.tool_name}: {result.message}")
                log_lines.append(f"  OK {result.tool_name}: {result.message}")
                if result.ifc_class:
                    element_types[result.ifc_class] += 1
            except AuthoringError as exc:
                error_count += 1
                failed_sig = (call.name, json.dumps(call.arguments, sort_keys=True))
                if failed_sig in failed_calls:
                    log_lines.append(f"  REPEATED FAILURE {call.name}: {exc}")
                    break
                failed_calls.add(failed_sig)
                progress_lines.append(
                    f"FAILED {call.name}: {exc}. "
                    "Replan from the updated scene summary and avoid this mistake."
                )
                log_lines.append(f"  FAIL {call.name}: {exc}")
    else:
        log_lines.append("WARNING: Reached maximum rounds without completion.")

    elapsed = time.time() - start_time

    if not dry_run:
        author.save()

    # Save plan.json
    plan_data = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "tool_calls": all_calls,
        "total_actions": len(all_calls),
        "errors": error_count,
        "elapsed_seconds": round(elapsed, 1),
        "element_types": dict(element_types),
    }
    plan_path.write_text(json.dumps(plan_data, indent=2))

    # Save build log
    log_lines.append("")
    log_lines.append(f"Elapsed: {elapsed:.1f}s")
    log_lines.append(f"Total tool calls: {len(all_calls)}")
    log_lines.append(f"Errors: {error_count}")
    log_lines.append(f"Element types: {dict(element_types)}")
    if not dry_run:
        log_lines.append(f"IFC file: {ifc_path.resolve()}")
        try:
            log_lines.append("")
            log_lines.append("Debug dump:")
            log_lines.append(author.debug_dump())
        except Exception:
            pass
    log_path.write_text("\n".join(log_lines))

    return {
        "provider": provider,
        "model": model,
        "output_dir": str(output_dir.resolve()),
        "ifc_file": str(ifc_path.resolve()),
        "total_actions": len(all_calls),
        "errors": error_count,
        "elapsed_seconds": round(elapsed, 1),
        "element_types": dict(element_types),
    }


# ──────────────────────────── OpenClaw iterative runner ──────────────────────

def run_via_openclaw(
    prompt: str,
    output_dir: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run via OpenClaw iterative session (uses the model configured in OpenClaw)."""
    create_iterative = _import_iterative()

    output_dir.mkdir(parents=True, exist_ok=True)
    ifc_path = output_dir / "building.ifc"

    start_time = time.time()
    result = create_iterative(
        user_prompt=prompt,
        output_path=str(ifc_path),
        dry_run=dry_run,
    )
    elapsed = time.time() - start_time

    # Save plan summary
    plan_path = output_dir / "plan.json"
    result["prompt"] = prompt
    plan_path.write_text(json.dumps(result, indent=2))

    return {
        "provider": "openclaw",
        "model": "iterative-session",
        "output_dir": str(output_dir.resolve()),
        "ifc_file": str(ifc_path.resolve()),
        "total_actions": result.get("total_actions", 0),
        "errors": result.get("total_errors", 0),
        "elapsed_seconds": round(elapsed, 1),
        "element_types": {},  # iterative planner doesn't track these directly
    }


# ──────────────────────────── Scene analysis ─────────────────────────────────

def analyze_scene(ifc_path: str) -> Dict[str, Any]:
    """Run query_scene.py on an IFC file and return parsed results."""
    script = ROOT / "scripts" / "query_scene.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), ifc_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception as exc:
        return {"success": False, "errors": [str(exc)]}
    return {"success": False, "errors": [proc.stderr[:500] if proc.stderr else "unknown"]}


def compute_quality_scores(
    scene: Dict[str, Any],
    difficulty: str,
    prompt: str,
) -> Dict[str, Any]:
    """Compute quality metrics from scene analysis results."""
    if not scene.get("success"):
        return {
            "spatial_coherence": 0,
            "slab_orientation": "N/A",
            "column_coverage": 0,
            "beam_completeness": 0,
            "wall_door_window": "N/A",
            "overall_score": 0,
            "notes": "Scene analysis failed",
        }

    counts = scene.get("element_counts", {})
    storeys = scene.get("storeys", [])
    validation = scene.get("validation", {})

    # Parse expected footprint from prompt
    # (Simple heuristic: look for "NNm x NNm" patterns)
    import re
    footprint_match = re.search(r'(\d+)m?\s*x\s*(\d+)m?', prompt)
    expected_x = float(footprint_match.group(1)) if footprint_match else 0
    expected_y = float(footprint_match.group(2)) if footprint_match else 0

    notes = []

    # 1. Element count in expected range
    total_elements = sum(
        v for k, v in counts.items()
        if isinstance(v, (int, float)) and k not in ("total",)
    )
    lo, hi = EXPECTED_ELEMENT_RANGE.get(difficulty, (0, 9999))
    if lo <= total_elements <= hi:
        count_score = 1.0
    elif total_elements > 0:
        count_score = 0.5
        notes.append(f"Element count {total_elements} outside expected {lo}-{hi}")
    else:
        count_score = 0.0
        notes.append("No elements found")

    # 2. Storey count
    expected_storeys_map = {
        "simple": 1,
        "medium": 2,
        "hard": 5,
        "very_hard": 8,
    }
    expected_storeys = expected_storeys_map.get(difficulty, 1)
    actual_storeys = len(storeys)
    if actual_storeys >= expected_storeys:
        storey_score = 1.0
    elif actual_storeys > 0:
        storey_score = actual_storeys / expected_storeys
        notes.append(f"Expected {expected_storeys} storeys, got {actual_storeys}")
    else:
        storey_score = 0.0
        notes.append("No storeys")

    # 3. Column presence
    col_count = counts.get("columns", counts.get("IfcColumn", 0))
    has_columns = 1.0 if col_count > 0 else 0.0
    if col_count == 0:
        notes.append("No columns")

    # 4. Slab presence
    slab_count = counts.get("slabs", counts.get("IfcSlab", 0))
    has_slabs = 1.0 if slab_count > 0 else 0.0
    if slab_count == 0:
        notes.append("No slabs")

    # 5. Wall presence
    wall_count = counts.get("walls", counts.get("IfcWall", 0))
    has_walls = 1.0 if wall_count > 0 else 0.0

    # 6. Orphan elements (lower is better)
    orphans = validation.get("orphan_elements", 0)
    orphan_penalty = min(orphans * 0.1, 0.5)
    if orphans > 0:
        notes.append(f"{orphans} orphan elements")

    # Overall weighted score (1-5 scale)
    raw = (
        count_score * 0.20
        + storey_score * 0.20
        + has_columns * 0.15
        + has_slabs * 0.15
        + has_walls * 0.15
        - orphan_penalty * 0.15
    )
    # Normalize to 1-5
    overall = max(1, min(5, round(raw * 5, 1)))

    return {
        "total_elements": total_elements,
        "storey_count": actual_storeys,
        "expected_storeys": expected_storeys,
        "column_count": col_count,
        "slab_count": slab_count,
        "wall_count": wall_count,
        "orphan_elements": orphans,
        "overall_score": overall,
        "notes": "; ".join(notes) if notes else "OK",
    }


# ──────────────────────────── Comparison table ───────────────────────────────

def print_comparison_table(results: List[Dict[str, Any]]) -> None:
    """Print a formatted comparison table of all test results."""
    # Header
    print()
    print("=" * 120)
    print("COMPARISON TEST MATRIX RESULTS")
    print("=" * 120)
    print()

    # Table header
    header = (
        f"{'Difficulty':<22} {'Model':<18} {'Actions':>8} {'Errors':>7} "
        f"{'Time':>7} {'Elements':>9} {'Storeys':>8} {'Score':>6} {'Notes'}"
    )
    print(header)
    print("-" * 120)

    for r in results:
        quality = r.get("quality", {})
        diff_label = DIFFICULTY_LABELS.get(r["difficulty"], r["difficulty"])[:21]
        model_label = MODELS.get(r["model_key"], {}).get("label", r["model_key"])[:17]

        line = (
            f"{diff_label:<22} {model_label:<18} "
            f"{r['total_actions']:>8} {r['errors']:>7} "
            f"{r['elapsed_seconds']:>6.1f}s "
            f"{quality.get('total_elements', '?'):>9} "
            f"{quality.get('storey_count', '?'):>4}/{quality.get('expected_storeys', '?'):<3} "
            f"{quality.get('overall_score', '?'):>5}/5 "
            f"{quality.get('notes', '')}"
        )
        print(line)

        # Blank line between difficulty levels
        if r.get("_last_in_group"):
            print()

    print("-" * 120)
    print()

    # Summary per model
    print("MODEL SUMMARY:")
    print()
    for model_key, model_info in MODELS.items():
        model_results = [r for r in results if r["model_key"] == model_key]
        if not model_results:
            continue
        total_actions = sum(r["total_actions"] for r in model_results)
        total_errors = sum(r["errors"] for r in model_results)
        total_time = sum(r["elapsed_seconds"] for r in model_results)
        avg_score = (
            sum(r.get("quality", {}).get("overall_score", 0) for r in model_results)
            / len(model_results)
        )
        print(
            f"  {model_info['label']:<20} "
            f"Tests: {len(model_results)}  "
            f"Actions: {total_actions}  "
            f"Errors: {total_errors}  "
            f"Time: {total_time:.1f}s  "
            f"Avg Score: {avg_score:.1f}/5"
        )
    print()


# ──────────────────────────── Main ───────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run 4-difficulty x 2-model comparison test matrix."
    )
    parser.add_argument(
        "--difficulty",
        choices=DIFFICULTIES,
        default=None,
        help="Run only this difficulty (default: all 4).",
    )
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        default=None,
        help="Run only this model (default: both).",
    )
    parser.add_argument(
        "--via-openclaw",
        action="store_true",
        help="Use OpenClaw iterative session instead of direct planner.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only, do not execute tool calls or write IFC.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Root output directory (default: out/tests/).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    difficulties = [args.difficulty] if args.difficulty else DIFFICULTIES
    model_keys = [args.model] if args.model else list(MODELS.keys())
    output_root = Path(args.output_root) if args.output_root else ROOT / "out" / "tests"
    via_openclaw = args.via_openclaw
    dry_run = args.dry_run

    print("=" * 80)
    print("BONSAI AI - COMPARISON TEST MATRIX")
    print("=" * 80)
    print(f"Difficulties: {', '.join(difficulties)}")
    print(f"Models:       {', '.join(model_keys)}")
    print(f"Mode:         {'OpenClaw iterative' if via_openclaw else 'Direct planner'}")
    print(f"Output:       {output_root.resolve()}")
    if dry_run:
        print("              *** DRY RUN - no IFC files will be generated ***")
    print()

    # Pre-check API keys (direct planner only)
    if not via_openclaw:
        for model_key in model_keys:
            provider = MODELS[model_key]["provider"]
            key = resolve_api_key(provider)
            if not key:
                print(
                    f"WARNING: No API key found for {provider}. "
                    f"Set the appropriate env var or add to OpenClaw auth-profiles."
                )
                print(f"  Skipping {MODELS[model_key]['label']}.")
                model_keys = [k for k in model_keys if k != model_key]
        if not model_keys:
            print("ERROR: No models available (no API keys found).")
            return 1

    # Run matrix
    all_results: List[Dict[str, Any]] = []
    total_start = time.time()

    for diff_idx, difficulty in enumerate(difficulties):
        prompt = PROMPTS[difficulty]
        print(f"\n{'='*60}")
        print(f"DIFFICULTY: {DIFFICULTY_LABELS[difficulty]}")
        print(f"{'='*60}")

        for model_idx, model_key in enumerate(model_keys):
            model_info = MODELS[model_key]
            dir_name = f"{difficulty}_{model_key}"
            output_dir = output_root / dir_name

            print(f"\n--- {DIFFICULTY_LABELS[difficulty]} / {model_info['label']} ---")
            print(f"    Output: {output_dir}")

            try:
                if via_openclaw:
                    summary = run_via_openclaw(
                        prompt=prompt,
                        output_dir=output_dir,
                        dry_run=dry_run,
                    )
                else:
                    api_key = resolve_api_key(model_info["provider"])
                    if not api_key:
                        print(f"    SKIP: no API key for {model_info['provider']}")
                        continue
                    summary = run_direct_planner(
                        provider=model_info["provider"],
                        model=model_info["model"],
                        api_key=api_key,
                        prompt=prompt,
                        output_dir=output_dir,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                print(f"    FAILED: {exc}")
                summary = {
                    "provider": model_info["provider"],
                    "model": model_info["model"],
                    "output_dir": str(output_dir.resolve()),
                    "ifc_file": "",
                    "total_actions": 0,
                    "errors": 1,
                    "elapsed_seconds": 0,
                    "element_types": {},
                }

            # Print immediate summary
            print(f"    Actions: {summary['total_actions']}")
            print(f"    Errors:  {summary['errors']}")
            print(f"    Time:    {summary['elapsed_seconds']}s")

            # Analyze scene (skip if dry run or no IFC)
            quality = {}
            ifc_file = summary.get("ifc_file", "")
            if not dry_run and ifc_file and Path(ifc_file).exists():
                print(f"    Analyzing scene...")
                scene = analyze_scene(ifc_file)

                # Save scene analysis
                scene_path = output_dir / "scene_analysis.json"
                scene_path.write_text(json.dumps(scene, indent=2))

                quality = compute_quality_scores(scene, difficulty, prompt)
                print(f"    Score:   {quality.get('overall_score', '?')}/5")
                if quality.get("notes") and quality["notes"] != "OK":
                    print(f"    Notes:   {quality['notes']}")
            else:
                quality = {
                    "total_elements": 0,
                    "storey_count": 0,
                    "expected_storeys": 0,
                    "overall_score": 0,
                    "notes": "dry run" if dry_run else "no IFC",
                }

            # Collect result
            is_last = (model_idx == len(model_keys) - 1)
            all_results.append({
                "difficulty": difficulty,
                "model_key": model_key,
                "total_actions": summary["total_actions"],
                "errors": summary["errors"],
                "elapsed_seconds": summary["elapsed_seconds"],
                "element_types": summary.get("element_types", {}),
                "quality": quality,
                "output_dir": summary["output_dir"],
                "_last_in_group": is_last,
            })

    total_elapsed = time.time() - total_start

    # Save full results
    results_path = output_root / "matrix_results.json"
    output_root.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nFull results saved to: {results_path}")

    # Print comparison table
    print_comparison_table(all_results)

    print(f"Total elapsed: {total_elapsed:.1f}s")
    print(f"Results: {results_path.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
