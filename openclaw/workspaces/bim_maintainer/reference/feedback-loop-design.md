# Feedback Loop Design: Agent Self-Verification

## Problem

The BIM operator agent generates IFC actions blind. It never checks whether what
it produced matches what it intended. The quality audit (`quality-audit-comparison.md`)
found the same spatial errors in both builds -- column grids that don't span the
footprint, beams that are missing, slabs rotated 90 degrees -- because the agent
has no mechanism to notice these problems before the human opens the file.

This design adds a predict-execute-compare loop that makes the agent accountable
for its own outputs and surfaces open questions for the human after every run.

---

## 1. Prediction Format

Before executing each phase, the agent must return a `predictions` block alongside
its `actions`. The predictions express what the agent *believes* will be true in
the IFC model after its actions are applied.

### Schema

```json
{
  "version": "1",
  "units": "meters",
  "summary": "...",
  "assumptions": [],
  "actions": [ ... ],
  "predictions": {
    "element_counts": {
      "columns": 24,
      "beams": 10,
      "slabs": 1,
      "walls": 0,
      "doors": 0,
      "windows": 0
    },
    "bounding_box": {
      "x": [0, 40],
      "y": [0, 25],
      "z": [0, 4.5]
    },
    "expected_changes": "24 columns on 8m grid covering 40x25m footprint, 1 slab at origin, 10 perimeter beams",
    "grid_check": {
      "x_spacing": 8.0,
      "x_count": 6,
      "x_extent": 40.0,
      "x_remainder": 0.0,
      "y_spacing": 8.0,
      "y_count": 4,
      "y_extent": 24.0,
      "y_remainder": 1.0
    },
    "concerns": [
      "Grid Y spacing (8m) doesn't divide evenly into 25m -- last bay will be 9m or building will be 24m"
    ],
    "questions": [
      "Should the last Y bay be 9m to reach 25m, or should the building be 24m wide?"
    ]
  }
}
```

### Field definitions

| Field | Type | Purpose |
|---|---|---|
| `element_counts` | `dict[str, int]` | Element counts this phase will ADD (not cumulative). Keys match `debug_dump()` keys. |
| `bounding_box` | `dict[str, [min, max]]` | Expected spatial extents of the ENTIRE model after this phase, in meters. |
| `expected_changes` | `str` | One-sentence human-readable description of what should change. |
| `grid_check` | `dict` | For structure phase only. The agent's arithmetic on grid spacing vs building dimensions. Makes the agent show its work so the orchestrator can catch `y_remainder != 0`. |
| `concerns` | `list[str]` | Anything the agent thinks might be wrong but is proceeding with anyway. |
| `questions` | `list[str]` | Questions the agent cannot resolve from the brief alone. These accumulate into `questions.md`. |

### Why predictions are per-phase, not per-action

Per-action predictions would be noisy (a single `create_column` doesn't have
meaningful spatial assertions). Phase-level predictions match the granularity
where spatial coherence matters: "do all 24 columns span the footprint?"

---

## 2. Comparison Logic

After applying a phase's actions, the orchestrator computes actuals from the IFC
model and compares them against the agent's predictions.

### Data sources for actuals

- **Element counts**: `author.debug_dump()` already returns counts by type. Diff
  the counts before and after the phase to get the delta.
- **Bounding box**: New method `author.bounding_box()` (see Section 6 below).
  Iterates all placed products and returns `{x: [min, max], y: [min, max], z: [min, max]}`.
- **Grid regularity**: New method `author.column_grid_analysis()`. Extracts all
  column X/Y positions and detects the spacing pattern and coverage gaps.

### Comparison result schema

```json
{
  "phase": "structure",
  "prediction_vs_actual": {
    "element_counts": {
      "columns": {"predicted": 24, "actual": 30, "delta": 6, "match": false},
      "beams":   {"predicted": 10, "actual": 4,  "delta": -6, "match": false},
      "slabs":   {"predicted": 1,  "actual": 1,  "delta": 0,  "match": true}
    },
    "bounding_box": {
      "x": {"predicted": [0, 40], "actual": [0, 40], "match": true},
      "y": {"predicted": [0, 25], "actual": [0, 24], "match": false, "delta": "-1m at max"},
      "z": {"predicted": [0, 4.5], "actual": [0, 4.5], "match": true}
    },
    "concerns_validated": [
      {
        "concern": "Grid Y spacing doesn't divide evenly into 25m",
        "outcome": "CONFIRMED -- Y extent is 24m, 1m gap at north edge"
      }
    ],
    "spatial_issues": [
      "Y extent is 24m, expected 25m -- 1m gap at north edge",
      "Only 4 beams placed, expected 10 -- most grid lines have no beam"
    ],
    "severity": "warning"
  }
}
```

### Matching rules

| Check | Match condition | Severity if failed |
|---|---|---|
| Element count | `actual == predicted` | `info` if within 10%, `warning` if off by >10%, `error` if zero |
| Bounding box axis | `abs(actual - predicted) < 0.1m` | `warning` if off by <1m, `error` if off by >1m |
| Grid remainder | `grid_check.x_remainder == 0 and grid_check.y_remainder == 0` | `warning` (the agent flagged this itself) |
| Concerns | Cross-reference with actuals | Informational -- confirms the agent was right to worry |

### Severity escalation

- `info`: Log and continue. The agent was close enough.
- `warning`: Feed back to the agent in the next turn. Let it decide whether to fix.
- `error`: Halt the phase. Ask the agent for a corrective plan before proceeding.

---

## 3. Feedback Message Format

The comparison result is formatted as natural language and injected into the
next turn's prompt, replacing the current `completed_summary` string.

### Template

```
Phase {phase_name} executed. {applied} actions applied, {failed} failed.

Prediction vs actual:
- Columns: predicted {p}, got {a} ({delta_description})
- Beams: predicted {p}, got {a} ({delta_description})
- Bounding box X: {match_or_delta}
- Bounding box Y: {match_or_delta}
- Bounding box Z: {match_or_delta}

{severity_block}

Your concerns from this phase:
- "{concern}" -> {outcome}

Current scene: {scene_summary}
```

### Severity blocks

For `warning`:
```
NOTE: Some predictions did not match. Review the deltas above before proceeding.
If you need to fix the Y grid, output corrective actions now. Otherwise, proceed
to the next phase.
```

For `error`:
```
STOP: Critical mismatch detected. You predicted {description} but the model shows
{actual_description}. Output corrective actions before proceeding to the next phase.
Return JSON with {"corrective": true, "actions": [...]}.
```

### Why natural language, not JSON

The agent is an LLM. It processes natural language natively. Structured JSON
comparisons are for the orchestrator's internal logic; the agent gets a readable
summary that clearly states what went wrong and what to do about it.

---

## 4. Question Log Format

Questions accumulate across all phases and are written to `questions.md` in the
output directory after the build completes.

### File: `{output_dir}/questions.md`

```markdown
# Agent Questions (for human review)

Build: {session_id}
Date: {timestamp}
Model: {output_path}

## Structure Phase

1. The column grid Y-spacing (8m) doesn't divide evenly into the 25m building
   width. I used 3 bays ending at 24m. Should the last bay be 9m instead? Or
   should the building be 24m wide?
   **Context:** Y bounding box is 0-24m, building brief says 25m.

2. The brief says "10 perimeter beams" but a full perimeter grid requires 20+.
   I placed beams on the long edges only. Should short edges also have beams?
   **Context:** 4 beams placed, covering X=0 and X=40 grid lines only.

## Envelope Phase

3. The south facade: I used a curtain wall on the ground floor only. Should all
   floors have glass, or is the upper facade intentionally opaque?
   **Context:** 1 curtain wall placed at Z=0..4.5, south face only.

## Mezzanines Phase

4. Mezzanine edge columns: I made them full-storey height (0-4.5m). Should they
   only span from floor slab to mezzanine slab (0-2m)?
   **Context:** 6 mezzanine columns, all 4.5m tall.

---

## Prediction Accuracy Summary

| Phase | Predicted | Actual | Match Rate |
|---|---|---|---|
| storeys | 5 storeys | 5 storeys | 100% |
| structure | 24 col, 10 beam, 1 slab | 30 col, 4 beam, 1 slab | 33% |
| envelope | 4 walls, 1 curtain | 4 walls, 1 curtain | 100% |
| openings | 8 windows, 2 doors | 8 windows, 1 door | 90% |

Overall prediction accuracy: 72%
```

### Purpose of the accuracy summary

Over many builds, this table reveals systematic biases. If the agent consistently
under-predicts beam counts, that points to a gap in the system prompt's framing
rules. If bounding box predictions are always off on one axis, that points to the
slab Length/Width swap bug documented in the quality audit.

---

## 5. Integration into `iterative_planner.py`

### Modified build loop

The changes to the main `build()` method in `IterativeBuilder` are concentrated
in the per-phase loop (lines ~401-493 of the current file). The new flow for
each phase:

```
for each phase:
    1. Get scene state BEFORE (element counts + bounding box)  <-- NEW
    2. Build execution prompt (unchanged)
    3. Call agent -- response now includes `predictions` block  <-- PARSE NEW FIELD
    4. Execute actions against IFC (unchanged)
    5. Get scene state AFTER (element counts + bounding box)    <-- NEW
    6. Compute delta (after - before)                           <-- NEW
    7. Compare delta vs predictions                             <-- NEW
    8. Format feedback message with comparison results          <-- REPLACES completed_summary
    9. Accumulate questions from predictions.questions           <-- NEW
   10. If severity == error, run corrective turn                <-- NEW
   11. Continue to next phase
```

### New data classes

```python
@dataclass
class PhasePrediction:
    """Agent's predictions for a phase, parsed from its response."""
    element_counts: Dict[str, int] = field(default_factory=dict)
    bounding_box: Dict[str, List[float]] = field(default_factory=dict)
    expected_changes: str = ""
    grid_check: Dict[str, float] = field(default_factory=dict)
    concerns: List[str] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)


@dataclass
class PhaseComparison:
    """Result of comparing predictions to actuals."""
    phase_name: str
    element_deltas: Dict[str, Dict[str, Any]]  # {type: {predicted, actual, delta, match}}
    bbox_deltas: Dict[str, Dict[str, Any]]      # {axis: {predicted, actual, match, delta}}
    concerns_validated: List[Dict[str, str]]
    spatial_issues: List[str]
    severity: str  # "info", "warning", "error"
```

### New methods on `IterativeBuilder`

```python
def _snapshot_state(self, author: IfcAuthor) -> Dict[str, Any]:
    """Capture element counts and bounding box from current model state."""
    counts = json.loads(author.debug_dump())
    bbox = author.bounding_box()  # new method, see Section 6
    return {"element_counts": counts, "bounding_box": bbox}


def _parse_predictions(self, data: Dict[str, Any]) -> Optional[PhasePrediction]:
    """Extract predictions block from agent response. Returns None if absent."""
    preds = data.get("predictions")
    if not preds or not isinstance(preds, dict):
        return None
    return PhasePrediction(
        element_counts=preds.get("element_counts", {}),
        bounding_box=preds.get("bounding_box", {}),
        expected_changes=preds.get("expected_changes", ""),
        grid_check=preds.get("grid_check", {}),
        concerns=preds.get("concerns", []),
        questions=preds.get("questions", []),
    )


def _compare(
    self,
    phase_name: str,
    prediction: PhasePrediction,
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> PhaseComparison:
    """Compare predicted vs actual changes."""
    # Element count deltas: actual_added = after[type] - before[type]
    element_deltas = {}
    for etype in set(list(prediction.element_counts.keys()) +
                     list(after["element_counts"].keys())):
        predicted = prediction.element_counts.get(etype, 0)
        actual_added = (
            after["element_counts"].get(etype, 0)
            - before["element_counts"].get(etype, 0)
        )
        element_deltas[etype] = {
            "predicted": predicted,
            "actual": actual_added,
            "delta": actual_added - predicted,
            "match": actual_added == predicted,
        }

    # Bounding box deltas: compare predicted total bbox vs actual total bbox
    bbox_deltas = {}
    for axis in ("x", "y", "z"):
        pred_range = prediction.bounding_box.get(axis)
        actual_range = after["bounding_box"].get(axis)
        if pred_range and actual_range:
            match = (
                abs(pred_range[0] - actual_range[0]) < 0.1
                and abs(pred_range[1] - actual_range[1]) < 0.1
            )
            delta_desc = ""
            if not match:
                parts = []
                if abs(pred_range[0] - actual_range[0]) >= 0.1:
                    parts.append(
                        f"min off by {actual_range[0] - pred_range[0]:+.1f}m"
                    )
                if abs(pred_range[1] - actual_range[1]) >= 0.1:
                    parts.append(
                        f"max off by {actual_range[1] - pred_range[1]:+.1f}m"
                    )
                delta_desc = ", ".join(parts)
            bbox_deltas[axis] = {
                "predicted": pred_range,
                "actual": actual_range,
                "match": match,
                "delta": delta_desc,
            }

    # Validate concerns against actuals
    concerns_validated = []
    spatial_issues = []
    for concern in prediction.concerns:
        # Check if the concern materialized
        # Simple heuristic: if any bbox axis doesn't match, the concern is confirmed
        outcome = "NOT CONFIRMED -- actuals match predictions"
        for axis, bd in bbox_deltas.items():
            if not bd["match"]:
                outcome = f"CONFIRMED -- {axis} axis: {bd['delta']}"
                break
        concerns_validated.append({"concern": concern, "outcome": outcome})

    # Detect spatial issues from mismatches
    for axis, bd in bbox_deltas.items():
        if not bd["match"]:
            spatial_issues.append(
                f"{axis.upper()} extent: predicted {bd['predicted']}, "
                f"got {bd['actual']} -- {bd['delta']}"
            )
    for etype, ed in element_deltas.items():
        if not ed["match"] and ed["predicted"] > 0 and ed["actual"] == 0:
            spatial_issues.append(
                f"No {etype} created (predicted {ed['predicted']})"
            )

    # Severity
    severity = "info"
    has_count_error = any(
        ed["predicted"] > 0 and ed["actual"] == 0
        for ed in element_deltas.values()
    )
    has_bbox_error = any(
        not bd["match"]
        and bd.get("delta")
        and any(
            abs(float(v.split("by")[1].rstrip("m"))) > 1.0
            for v in bd["delta"].split(", ")
            if "by" in v
        )
        for bd in bbox_deltas.values()
    )
    if has_count_error or has_bbox_error:
        severity = "error"
    elif any(not ed["match"] for ed in element_deltas.values()):
        severity = "warning"
    elif any(not bd["match"] for bd in bbox_deltas.values()):
        severity = "warning"

    return PhaseComparison(
        phase_name=phase_name,
        element_deltas=element_deltas,
        bbox_deltas=bbox_deltas,
        concerns_validated=concerns_validated,
        spatial_issues=spatial_issues,
        severity=severity,
    )


def _format_feedback(self, result: TurnResult, comparison: Optional[PhaseComparison]) -> str:
    """Format turn result + comparison as feedback for the agent's next turn."""
    lines = [
        f"Phase {result.phase_name} executed. "
        f"{result.actions_applied} actions applied, {result.actions_failed} failed."
    ]

    if comparison:
        lines.append("")
        lines.append("Prediction vs actual:")
        for etype, ed in comparison.element_deltas.items():
            if ed["predicted"] > 0 or ed["actual"] > 0:
                status = "OK" if ed["match"] else f"delta {ed['delta']:+d}"
                lines.append(
                    f"- {etype}: predicted {ed['predicted']}, "
                    f"got {ed['actual']} ({status})"
                )
        for axis, bd in comparison.bbox_deltas.items():
            status = "OK" if bd["match"] else bd["delta"]
            lines.append(
                f"- Bounding box {axis.upper()}: "
                f"predicted {bd['predicted']}, got {bd['actual']} ({status})"
            )

        if comparison.concerns_validated:
            lines.append("")
            lines.append("Your concerns:")
            for cv in comparison.concerns_validated:
                lines.append(f"- \"{cv['concern']}\" -> {cv['outcome']}")

        if comparison.spatial_issues:
            lines.append("")
            if comparison.severity == "error":
                lines.append(
                    "STOP: Critical mismatch. Output corrective actions "
                    "before proceeding. Return {\"corrective\": true, \"actions\": [...]}."
                )
            elif comparison.severity == "warning":
                lines.append(
                    "NOTE: Some predictions did not match. Review the deltas above. "
                    "If correction is needed, output corrective actions now. "
                    "Otherwise, proceed to the next phase."
                )

    if result.errors:
        lines.append("")
        for err in result.errors[:5]:
            lines.append(f"  Error: {err}")

    return "\n".join(lines)
```

### Modified execution prompt

The `_execution_prompt` method adds one line to request predictions:

```python
# After existing format instruction, before "Respond with ONLY the JSON."
parts.append(
    'Also include a "predictions" block with: '
    '"element_counts" (what this phase ADDS), '
    '"bounding_box" (total model extents after this phase), '
    '"expected_changes" (one sentence), '
    '"concerns" (anything you think might be wrong), '
    '"questions" (what you cannot determine from the brief).'
)
```

The return format instruction becomes:
```python
parts.append(
    'Return JSON: {"version":"1", "units":"meters", '
    '"summary":"...", "assumptions":[], "actions":[...], '
    '"predictions":{...}}'
)
```

### Modified build loop (pseudocode diff)

```python
# In build(), replace the per-phase loop body:

all_questions: List[Dict[str, Any]] = []  # (phase, question, context)
all_comparisons: List[PhaseComparison] = []

for i, phase in enumerate(phases, 1):
    phase_name = phase["name"]
    turn_t0 = time.time()

    # --- NEW: Snapshot BEFORE ---
    state_before = self._snapshot_state(author)

    scene_summary = author.scene_summary() or "Empty IFC model"
    prompt = self._execution_prompt(phase, completed_summary, scene_summary)
    output = self._call_agent(prompt)
    data = _extract_json(output)
    actions = data.get("actions", [])

    # --- NEW: Parse predictions ---
    prediction = self._parse_predictions(data)

    if not actions:
        # ... existing no-actions handling ...
        continue

    # Execute actions (unchanged)
    applied, failed, errors = self._execute_actions(actions, phase_name, author)

    # --- NEW: Snapshot AFTER ---
    state_after = self._snapshot_state(author)

    # --- NEW: Compare ---
    comparison = None
    if prediction:
        comparison = self._compare(phase_name, prediction, state_before, state_after)
        all_comparisons.append(comparison)

        # Accumulate questions
        for q in prediction.questions:
            all_questions.append({
                "phase": phase_name,
                "question": q,
                "context": prediction.expected_changes,
            })

    result = TurnResult(
        phase_name=phase_name,
        actions_applied=applied,
        actions_failed=failed,
        errors=errors,
        elapsed_seconds=time.time() - turn_t0,
    )
    self.turn_results.append(result)

    # --- CHANGED: Feedback now includes comparison ---
    completed_summary = self._format_feedback(result, comparison)

    # --- NEW: Corrective turn on error ---
    if comparison and comparison.severity == "error":
        print(f"[iterative]   {phase_name}: MISMATCH -- running corrective turn")
        corrective_output = self._call_agent(completed_summary)
        corrective_data = _extract_json(corrective_output)
        corrective_actions = corrective_data.get("actions", [])
        if corrective_actions and corrective_data.get("corrective"):
            c_applied, c_failed, c_errors = self._execute_actions(
                corrective_actions, phase_name, author
            )
            total_actions += c_applied
            total_errors += c_failed
            # Re-snapshot and re-compare for the log
            state_after_fix = self._snapshot_state(author)
            if prediction:
                fix_comparison = self._compare(
                    f"{phase_name}_fix", prediction, state_before, state_after_fix
                )
                all_comparisons.append(fix_comparison)
            completed_summary = (
                f"Phase {phase_name} corrective turn: "
                f"{c_applied} applied, {c_failed} failed."
            )

    # ... existing retry logic for total failures (applied == 0) stays ...

# --- NEW: Write questions.md ---
self._write_questions(all_questions, all_comparisons)
```

### `_write_questions` method

```python
def _write_questions(
    self,
    questions: List[Dict[str, Any]],
    comparisons: List[PhaseComparison],
) -> None:
    """Write questions.md to the output directory."""
    output_dir = Path(self.output_path).parent
    questions_path = output_dir / "questions.md"

    lines = [
        "# Agent Questions (for human review)",
        "",
        f"Build: {self.session_id}",
        f"Model: {self.output_path}",
        "",
    ]

    if not questions:
        lines.append("No questions raised during this build.")
    else:
        current_phase = None
        q_num = 1
        for q in questions:
            if q["phase"] != current_phase:
                current_phase = q["phase"]
                lines.append(f"## {current_phase.title()} Phase")
                lines.append("")
            lines.append(f"{q_num}. {q['question']}")
            lines.append(f"   **Context:** {q['context']}")
            lines.append("")
            q_num += 1

    # Prediction accuracy summary
    if comparisons:
        lines.append("---")
        lines.append("")
        lines.append("## Prediction Accuracy Summary")
        lines.append("")
        lines.append("| Phase | Element Matches | BBox Matches | Severity |")
        lines.append("|---|---|---|---|")
        for comp in comparisons:
            total_e = len(comp.element_deltas)
            match_e = sum(1 for ed in comp.element_deltas.values() if ed["match"])
            total_b = len(comp.bbox_deltas)
            match_b = sum(1 for bd in comp.bbox_deltas.values() if bd["match"])
            lines.append(
                f"| {comp.phase_name} "
                f"| {match_e}/{total_e} "
                f"| {match_b}/{total_b} "
                f"| {comp.severity} |"
            )
        lines.append("")

    questions_path.write_text("\n".join(lines))
    print(f"[iterative] Questions written to {questions_path}")
```

---

## 6. Changes to `execute_plan.py` and `ifc_author.py`

### New method: `IfcAuthor.bounding_box()`

This is the key new capability. It iterates all placed products and computes the
overall model extents.

```python
def bounding_box(self) -> Dict[str, List[float]]:
    """Compute the axis-aligned bounding box of all placed elements.

    Returns {"x": [min, max], "y": [min, max], "z": [min, max]}
    or empty dict if no elements are placed.
    """
    import ifcopenshell.util.placement
    import numpy as np

    xs, ys, zs = [], [], []

    for ifc_class in (
        "IfcWall", "IfcSlab", "IfcColumn", "IfcBeam",
        "IfcDoor", "IfcWindow", "IfcCurtainWall",
        "IfcPlate", "IfcFooting",
    ):
        for elem in self.model.by_type(ifc_class):
            placement = getattr(elem, "ObjectPlacement", None)
            if not placement:
                continue
            try:
                matrix = ifcopenshell.util.placement.get_local_placement(placement)
                x, y, z = float(matrix[0][3]), float(matrix[1][3]), float(matrix[2][3])
                xs.append(x)
                ys.append(y)
                zs.append(z)
            except Exception:
                continue

    if not xs:
        return {}

    return {
        "x": [round(min(xs), 2), round(max(xs), 2)],
        "y": [round(min(ys), 2), round(max(ys), 2)],
        "z": [round(min(zs), 2), round(max(zs), 2)],
    }
```

**Limitation:** This returns placement origins, not true geometric extents (which
would require computing profile dimensions + placement). For the feedback loop,
placement origins are sufficient -- if columns are placed at X=0..40 and Y=0..24,
the bounding box correctly shows the grid doesn't reach Y=25. A future enhancement
can add profile-aware extents using `ifcopenshell.util.shape`.

### New method: `IfcAuthor.column_grid_analysis()`

```python
def column_grid_analysis(self) -> Dict[str, Any]:
    """Analyze the column grid for regularity and coverage.

    Returns spacing pattern, detected grid dimensions, and gaps.
    """
    import ifcopenshell.util.placement

    positions = []
    for col in self.model.by_type("IfcColumn"):
        placement = getattr(col, "ObjectPlacement", None)
        if not placement:
            continue
        try:
            matrix = ifcopenshell.util.placement.get_local_placement(placement)
            x, y = float(matrix[0][3]), float(matrix[1][3])
            positions.append((round(x, 2), round(y, 2)))
        except Exception:
            continue

    if not positions:
        return {"column_count": 0}

    xs = sorted(set(p[0] for p in positions))
    ys = sorted(set(p[1] for p in positions))

    # Detect spacing
    x_spacings = [round(xs[i+1] - xs[i], 2) for i in range(len(xs)-1)] if len(xs) > 1 else []
    y_spacings = [round(ys[i+1] - ys[i], 2) for i in range(len(ys)-1)] if len(ys) > 1 else []

    return {
        "column_count": len(positions),
        "x_lines": xs,
        "y_lines": ys,
        "x_spacings": x_spacings,
        "y_spacings": y_spacings,
        "x_extent": [xs[0], xs[-1]] if xs else [],
        "y_extent": [ys[0], ys[-1]] if ys else [],
        "x_regular": len(set(x_spacings)) <= 1 if x_spacings else True,
        "y_regular": len(set(y_spacings)) <= 1 if y_spacings else True,
    }
```

### Changes to `execute_plan.py`

The standalone `execute_plan.py` script gains an optional `--predictions` flag
that accepts a JSON file with predictions and outputs the comparison alongside
the execution result.

```python
parser.add_argument(
    "--predictions",
    help="Path to predictions JSON file. If provided, output includes comparison.",
)
```

After execution, if `--predictions` is provided:

```python
if args.predictions:
    pred_path = Path(args.predictions)
    if pred_path.exists():
        preds = json.loads(pred_path.read_text())
        bbox = author.bounding_box()
        grid = author.column_grid_analysis()
        result["prediction_comparison"] = {
            "bounding_box": {
                "predicted": preds.get("bounding_box", {}),
                "actual": bbox,
            },
            "element_counts": {
                "predicted": preds.get("element_counts", {}),
                "actual": element_counts,
            },
            "grid_analysis": grid,
        }
```

### Changes to `query_scene.py`

Add bounding box and grid analysis to the inspection output:

```python
# After existing validation section
bbox = author.bounding_box()
grid = author.column_grid_analysis()

result["bounding_box"] = bbox
result["grid_analysis"] = grid
```

This lets humans run `query_scene.py` on any model to see the same spatial data
the feedback loop uses internally.

---

## 7. Graceful Degradation

The system must work even when the agent does not return predictions (older
prompts, model failures, truncated responses).

- `_parse_predictions` returns `None` if the block is missing.
- `_compare` is only called when predictions exist.
- `_format_feedback` falls back to the current `_format_turn_report` behavior
  when comparison is `None`.
- `questions.md` is written even if empty (confirms no questions were raised).

The prediction prompt addition is advisory. If the agent ignores it and returns
only `actions`, the build proceeds exactly as it does today. Over time, as the
system prompt is refined, prediction compliance should increase.

---

## 8. What This Catches (Mapped to Known Issues)

Every critical issue from the quality audit would be caught or surfaced:

| Quality Audit Issue | Feedback Loop Detection |
|---|---|
| Slab L/W ambiguity (slabs rotated 90 deg) | Bounding box X/Y will be swapped vs prediction. Agent predicts X=0..40, actual shows X=0..25. Severity: **error**. |
| Column grid doesn't fit building width | `grid_check.y_remainder != 0` in predictions. Bounding box Y will be 24m not 25m. Severity: **warning**, with the agent's own concern confirmed. |
| Insufficient beams | Element count: predicted 20, actual 4. Severity: **warning**. |
| No self-verification | This entire design IS the self-verification. |
| Curtain wall overflow | Bounding box Z exceeds storey height. Severity: **warning**. |

---

## 9. Implementation Order

1. **`IfcAuthor.bounding_box()`** -- standalone method, no dependencies, testable
   immediately against existing IFC files.
2. **`IfcAuthor.column_grid_analysis()`** -- same.
3. **`PhasePrediction` and `PhaseComparison` dataclasses** -- pure data, no side effects.
4. **`_parse_predictions`, `_compare`, `_format_feedback`** -- the core logic,
   unit-testable with mock data.
5. **Modified `_execution_prompt`** -- add predictions request to the prompt.
6. **Modified `build()` loop** -- wire everything together.
7. **`_write_questions`** -- output file generation.
8. **`query_scene.py` additions** -- expose bbox and grid analysis to CLI.
9. **`execute_plan.py --predictions`** -- standalone comparison mode.

Steps 1-4 can be implemented and tested without changing any existing behavior.
Step 5 is a prompt change that might affect model output, so it should be tested
on a throwaway build first. Steps 6-9 integrate everything.
