# FreeCAD Handoff

## Purpose
Generates FreeCAD-compatible handoff artifacts (JSON payload + Python macro) from the analytical model, and optionally runs FreeCAD to produce .FCStd files.

## How It Works

### freecad_handoff.py (399 lines)
**`FreeCADHandoffBuilder`**:
- `build(package)` converts the analytical model into a FreeCAD-friendly JSON payload:
  - For each element, calls `_box_payload()` to compute Part::Box primitive with placement (base position + rotation axis + angle) and dimensions (length, width, height).
  - Handles 6 geometry patterns: wall (start/end + height), beam (start/end + width/depth), column (origin + dimensions), 3D beam (with axis-angle rotation), horizontal panel/foundation (origin + length + width + thickness), vertical panel (origin + width + height + thickness).
  - Includes materials, sections, load cases, load combinations, and metadata.
- `write_json()` and `write_macro()` write the JSON and Python script.
- `render_freecad_handoff_script()` generates a self-contained Python macro that:
  - Reads the handoff JSON.
  - Creates Part::Box objects in FreeCAD with proper placements.
  - Adds BonsaiId and BonsaiKind custom properties.
  - Saves the document as .FCStd.
  - Writes a `freecad_run_report.json` with status.

**`FreeCADHandoffExporter`**:
- `export(package, output_dir)` creates both JSON and macro files, returns 2 artifacts.

### freecad_runner.py (218 lines)
**`find_freecad_binary(preferred)`**: searches for FreeCAD executable in:
1. Explicit path or `shutil.which()` lookup.
2. `FREECAD_BIN` env var.
3. `shutil.which("FreeCADCmd")` / `shutil.which("FreeCAD")`.
4. Hardcoded macOS paths (6 candidates in /Applications and ~/Applications).

**`run_freecad_handoff(output_dir, executable, freecad_bin, timeout_seconds)`**:
1. Finds FreeCAD binary. If not found, writes a "skipped" report and returns.
2. Executes the macro via `_execute_freecad()`:
   - Sets env vars: `BONSAI_FREECAD_HANDOFF`, `BONSAI_FREECAD_OUTPUT`, `BONSAI_FREECAD_RESULT`.
   - Tries command variants: `FreeCADCmd macro.py` or `FreeCAD -c macro.py` / `FreeCAD macro.py`.
   - Handles timeout with `subprocess.TimeoutExpired`.
   - Records all attempts in the result JSON.
3. Returns artifacts: report JSON + optional .FCStd model.

## Current State
Fully implemented. The handoff produces a complete FreeCAD-readable package that can be run headlessly or interactively.

## Known Issues
- All elements are represented as Part::Box primitives regardless of actual shape. I-beams, HSS tubes, and complex profiles are all rectangular boxes.
- `_axis_angle_from_x_axis()` uses a simplified rotation calculation that may not handle all 3D orientations correctly (particularly beams with significant dz component).
- The macro uses double-brace escaping `{{` in an f-string, which is correct but fragile for future edits.
- `_command_variants()` only supports macOS-style paths. Linux and Windows FreeCAD installations would need additional search paths.
- Duplicate beam handling code in `_box_payload()` (lines 107-120 and 134-154 both handle beam kind).

## Last Reviewed
2026-03-31
