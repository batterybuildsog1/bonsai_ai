# IfcWindow Dark Hole Rendering Bug -- Root Cause Analysis & Fix Plan

## Summary

IfcWindow objects render as dark/black voids in the Bonsai web viewer, while
IfcPlate curtain wall panels render correctly as translucent glass. This
document identifies the root causes across both viewer engines and the IFC
authoring layer, then proposes three fix options.

---

## Architecture Context

- **Default engine**: `ifc-lite` (set in `viewer/src/main.js` line 21)
- **IFC-Lite viewer**: `viewer/src/ifc-lite-viewer.js` -- uses `@ifc-lite/geometry` WASM + Three.js
- **Legacy viewer**: `viewer/src/viewer.js` (aliased as `viewer-legacy.js`) -- uses `web-ifc` + Three.js
- **IFC authoring**: `src/bonsai_ai/ifc_author.py` -- generates the IFC file with ifcopenshell

---

## Root Cause Analysis

### Finding 1: IFC-Lite viewer has correct material mapping (NOT the main problem)

The IFC-Lite viewer's `getTypeMaterial()` function (line 57-118 of `ifc-lite-viewer.js`)
**does** include IfcWindow:

```js
case "window":
  color = 0xa8d8ea; opacity = 0.50; roughness = 0.05; metalness = 0.1;
  side = THREE.DoubleSide; break;
```

And the `@ifc-lite/geometry` default-materials.js also defines IfcWindow:

```js
'IfcWindow': {
  baseColor: [0.6, 0.8, 0.95, 0.3], // Sky blue, transparent
  metallic: 0.0, roughness: 0.1,
},
```

So the material palette is not missing IfcWindow. The viewer will render a
window mesh as translucent blue **if it receives one**.

### Finding 2: The real problem is IfcOpeningElement subtraction (Cause C)

The `create_window()` function in `ifc_author.py` (line 786-845) creates:

1. An **IfcOpeningElement** with a box the full wall thickness + 0.2m overshoot
   (`thickness=frame["thickness"] + 0.2`), placed at y_shift=-0.1 (punching
   through the wall)
2. An **IfcWindow** entity with parametric window representation via
   `add_window_representation()`, placed at y_shift=+0.05 (offset into the wall)
3. The opening is linked to the wall via `add_feature()` (boolean void subtraction)
4. The window is linked as a filling via `add_filling()`

**The IFC-Lite WASM geometry engine (Rust) and web-ifc both process boolean
subtraction of IfcOpeningElement from the host wall.** This is confirmed by the
`ifc-lite-mesh-collector.js` which calls `parseMeshes()` on the WASM side --
the Rust engine handles CSG/void operations internally.

**However, the problem emerges from the interaction of three factors:**

#### Factor A: Wall opening subtraction works, but the window geometry is complex and thin

The `add_window_representation()` with default `WindowLiningProperties` produces:
- **LiningDepth**: 0.05m (50mm)
- **LiningThickness**: 0.05m (50mm)
- **FrameDepth**: 0.035m (35mm)
- **FrameThickness**: 0.035m (35mm)
- Glass pane thickness: approximately 0.015m (15mm) -- derived from
  LiningDepth - FrameDepth = 15mm

The window is placed at y_shift=+0.05m from the wall start face. With a wall
typically 0.2-0.3m thick, the window geometry sits inside the wall void but
the glass pane is only ~15mm thick.

#### Factor B: The glass pane is a thin swept solid that causes z-fighting

A 15mm pane inside a ~250mm wall void means:
- The pane surfaces are very close to the wall void surfaces
- With depth buffer precision spread over the full scene, z-fighting is likely
- The pane may be fully or partially occluded by the wall void back face

#### Factor C: `depthWrite: false` for transparent objects means the window loses depth test against the dark void interior

In `ifc-lite-viewer.js` line 113:
```js
depthWrite: opacity >= 1.0,
```

The window material has opacity=0.50, so `depthWrite` is **false**. This means:
- The wall void interior (opaque wall material, depthWrite=true) writes to depth buffer
- The window glass (transparent, depthWrite=false) does NOT write to depth buffer
- **Render order becomes critical**: if the wall renders before the window, the
  wall's interior faces at the opening write to the depth buffer. The window
  glass, being transparent with `depthWrite: false`, may fail the depth test
  against the wall's inner surfaces and simply not render.

The result: you see the dark interior of the wall opening -- a "dark hole."

### Finding 3: The legacy web-ifc viewer has the same problem (plus no type material palette)

The legacy `viewer.js` uses `pg.color` from web-ifc's `StreamAllMeshes()` to
set material color. web-ifc provides a default gray color for IfcWindow (since
the IFC file likely has no IfcSurfaceStyle assigned to the window). There is
no type-based material palette in the legacy viewer at all -- everything gets
the embedded IFC color.

The legacy viewer uses `side: THREE.DoubleSide` for all meshes but still has
the same fundamental depth-write/render-order problem.

### Finding 4: Why IfcPlate curtain wall panels work correctly

Curtain wall panels (`IfcPlate`) are created with `add_wall_representation()`
(line 908-914 in `ifc_author.py`). They are **freestanding** geometry -- no
IfcOpeningElement, no boolean subtraction, no wall void to compete with for
depth buffer priority. The panel is just a thin box floating in space, rendered
with the translucent material.

Key difference: **IfcPlate has no surrounding opaque wall surfaces competing
for the depth buffer.** The window does.

### Finding 5: Neither viewer handles transparent sorting

Three.js renders transparent objects after opaque objects by default, but it
does **not** sort transparent objects by camera distance. With the wall void
interior writing to the depth buffer first (opaque pass), the window glass
(transparent pass) can fail the depth test entirely.

---

## Fix Options

### Option 1: Viewer-side fix -- force window glass to render correctly (Viewer code only)

**What to change**: `viewer/src/ifc-lite-viewer.js`

Modify `meshDataToThreeMesh()` to give IfcWindow meshes special rendering treatment:

1. Set `depthWrite: true` on window material (ensures glass writes to depth buffer)
2. Set `polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1`
   (pushes glass forward in depth buffer to win against wall void surfaces)
3. Set `renderOrder: 1` on IfcWindow meshes (ensures they render after walls
   but during the opaque pass, before other transparent objects)
4. Consider adding `alphaTest: 0.01` to avoid fully transparent fragments
   writing to depth buffer

```js
// In meshDataToThreeMesh(), after material assignment:
if (ifcType === 'IfcWindow') {
  material = material.clone(); // don't mutate shared type material
  material.depthWrite = true;
  material.polygonOffset = true;
  material.polygonOffsetFactor = -1;
  material.polygonOffsetUnits = -1;
  mesh.renderOrder = 1;
}
```

Also apply the same logic in the legacy `viewer.js` by checking the expressID
against the element index after geometry loading is complete.

**Difficulty**: Low (5-10 lines of viewer code)

**Expected result**: Window glass becomes visible as translucent blue, punching
through the dark wall void. Minor z-fighting artifacts possible at edges where
glass meets lining, but the dark hole problem is solved.

**Risk**: `depthWrite: true` on transparent geometry can cause other transparent
objects behind the window to disappear. Acceptable tradeoff for architectural
visualization where you rarely look through two transparent surfaces.

---

### Option 2: IFC authoring fix -- make windows use simpler geometry (Authoring code only)

**What to change**: `src/bonsai_ai/ifc_author.py` -- `create_window()` method

Replace the parametric `add_window_representation()` with a simple
`add_wall_representation()` (same as curtain wall panels), producing a single
flat pane that fills the opening:

```python
# Instead of:
window_rep = ifcopenshell.api.geometry.add_window_representation(
    self.model, context=body,
    overall_height=float(height), overall_width=float(width),
)

# Use:
window_rep = ifcopenshell.api.geometry.add_wall_representation(
    self.model, context=body,
    length=float(width), height=float(height),
    thickness=0.01,  # 10mm glass pane
)
```

Also adjust the window placement y_shift to center the 10mm pane in the wall
void (instead of 0.05, use `frame["thickness"] / 2`).

This produces geometry identical in structure to IfcPlate curtain wall panels,
which already render correctly.

**Difficulty**: Low-Medium (modify create_window, adjust placement math,
regenerate test IFC files)

**Expected result**: Windows render identically to curtain wall glass panels --
translucent blue pane visible in the wall opening. No frame/lining detail,
but for concept-level BIM models this is appropriate.

**Risk**: Loss of parametric window detail (lining, frame, mullions). The
IfcWindow entity still carries the correct IFC semantics, but the geometry
is simplified. This may matter if the model is exported to detailed design
tools later.

---

### Option 3: Combined fix -- authoring simplification + viewer depth handling (Both)

**What to change**: Both `ifc_author.py` and `ifc-lite-viewer.js`

This is the belt-and-suspenders approach:

**Authoring side** (ifc_author.py):
- Keep `add_window_representation()` for rich IFC semantics
- Add an explicit `IfcSurfaceStyle` to the window representation with a blue
  translucent color (RGBA ~[0.6, 0.85, 0.95, 0.3]). This ensures both web-ifc
  and IFC-Lite pick up the correct color from the IFC file itself rather than
  relying on viewer-side type mapping.

```python
# After creating window representation:
style = ifcopenshell.api.style.add_style(self.model, name="Glass")
ifcopenshell.api.style.add_surface_style(
    self.model, style=style,
    ifc_class="IfcSurfaceStyleRendering",
    attributes={
        "SurfaceColour": {"Name": None, "Red": 0.6, "Green": 0.85, "Blue": 0.95},
        "Transparency": 0.7,
    },
)
ifcopenshell.api.style.assign_material_style(
    self.model, material=..., style=style, context=body,
)
```

**Viewer side** (ifc-lite-viewer.js):
- Apply the depth/render-order fix from Option 1 for IfcWindow meshes
- Additionally, set `side: THREE.DoubleSide` to ensure the thin glass pane
  is visible from both sides

**Difficulty**: Medium (changes in two codebases, need to test IFC style
assignment compatibility with both viewer engines)

**Expected result**: Best visual quality. The IFC file itself carries the
correct transparent glass style, so any IFC viewer (not just Bonsai's) will
render windows as glass. The viewer-side depth fix ensures correct rendering
even when the IFC style is missing.

**Risk**: Style assignment in ifcopenshell requires correct material/style
linkage which can be fragile. Need to verify that both `@ifc-lite/geometry`
WASM and `web-ifc` properly read `IfcSurfaceStyle` and apply it to the mesh
color output.

---

## Recommendation

**Start with Option 1** (viewer-only fix). It is the fastest to implement,
requires no IFC regeneration, and solves the visible symptom immediately.
The core issue is a depth buffer conflict between the opaque wall void and
the transparent window glass -- fixing the render order and depth write
behavior resolves this directly.

**Follow up with Option 2 or 3** if concept-level models don't need parametric
window detail. Option 2 (simple pane geometry) eliminates the z-fighting
root cause entirely and is the most robust long-term solution for
auto-generated BIM models.

---

## Files Referenced

| File | Role |
|------|------|
| `viewer/src/main.js` | Boot sequence, engine selection (ifc-lite is default) |
| `viewer/src/ifc-lite-viewer.js` | IFC-Lite viewer: type-material palette + mesh creation |
| `viewer/src/viewer.js` | Legacy web-ifc viewer (no type palette, uses IFC embedded colors) |
| `src/bonsai_ai/ifc_author.py` | IFC authoring: `create_window()` at line 786 |
| `node_modules/@ifc-lite/geometry/dist/default-materials.js` | IFC-Lite default material definitions |
| `node_modules/@ifc-lite/geometry/dist/ifc-lite-mesh-collector.js` | WASM mesh collection (handles CSG internally) |

## Key Code Locations

- **Type material palette**: `ifc-lite-viewer.js` lines 55-118 (`getTypeMaterial()`)
- **Mesh creation with type resolution**: `ifc-lite-viewer.js` lines 570-614 (`meshDataToThreeMesh()`)
- **Window creation + opening**: `ifc_author.py` lines 786-845 (`create_window()`)
- **Curtain wall panel creation**: `ifc_author.py` lines 847-945 (`create_curtain_wall()`)
- **depthWrite: false for transparent**: `ifc-lite-viewer.js` line 113
