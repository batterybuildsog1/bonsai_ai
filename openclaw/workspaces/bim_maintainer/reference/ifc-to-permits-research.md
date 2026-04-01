# IFC to Construction Permit Drawings: Research

> Research date: 2026-03-30
> Goal: Determine how to get from an IFC model to permit-ready construction drawings, and how much can be automated.

---

## Table of Contents

1. [What a Metal Building Permit Set Requires](#1-what-a-metal-building-permit-set-requires)
2. [Tools for IFC to 2D Drawing Extraction](#2-tools-for-ifc-to-2d-drawing-extraction)
3. [IfcOpenShell / IfcConvert (CLI)](#3-ifcopenshell--ifcconvert-cli)
4. [ifcopenshell.draw (Python API)](#4-ifcopenshelldraw-python-api)
5. [Bonsai (BlenderBIM) Drawing Pipeline](#5-bonsai-blenderbim-drawing-pipeline)
6. [FreeCAD BIM Drawing Pipeline](#6-freecad-bim-drawing-pipeline)
7. [Commercial / Other Tools](#7-commercial--other-tools)
8. [IFC to DXF / SVG / PDF Conversion](#8-ifc-to-dxf--svg--pdf-conversion)
9. [What Can Be Automated vs. Requires Human Drafting](#9-what-can-be-automated-vs-requires-human-drafting)
10. [Recommended Pipeline](#10-recommended-pipeline)
11. [Sources](#11-sources)

---

## 1. What a Metal Building Permit Set Requires

Jurisdictions vary, but a typical metal building permit submission requires the following sheets. Each must be drawn to scale, printed in ink/grayscale on standard bond paper (18x24 to 36x48 inches), and stamped by a licensed Professional Engineer (PE).

### Sheet 1: Site Plan (Plot Plan)
- Property lines with dimensions
- Existing buildings on the property
- Proposed building location with setbacks to each property line
- Driveways, easements, and utility locations
- Septic system and well locations (if applicable)
- Parking areas and access roads
- North arrow and scale

### Sheet 2: Foundation Plan
- Anchor bolt locations, sizes, and embedment depths
- Column reaction loads (from manufacturer or PE)
- Footing locations, sizes, and depths
- Rebar schedule and reinforcement details
- Concrete specifications (strength, thickness)
- Grade beam locations (if applicable)
- Frost line depth notation
- Soil bearing capacity reference

### Sheet 3: Floor Plan
- Column grid with dimensions
- Wall locations (exterior and interior)
- Door and window locations with sizes
- Room labels and dimensions
- Overall building dimensions (width x length)
- Fire exits and egress paths

### Sheet 4: Elevations (all 4 sides)
- Building heights (eave, ridge, overall)
- Roof style and pitch
- Door and window locations in elevation
- Wall panel layout and materials
- Trim details
- Grade line

### Sheet 5: Sections (Cross-Section and Wall Section)
- Primary structural frame (columns, rafters, knee braces)
- Roof section showing purlins, insulation, panels
- Wall section showing girts, insulation, panels
- Foundation detail at base of column
- Ridge connection detail
- Eave/haunch connection detail

### Sheet 6: Roof Framing Plan
- Line diagram showing all structural framing
- Beam/column sizes (or shop mark cross-reference table)
- Purlin spacing and sizes
- Struts, X-bracing, and secondary framing
- Member properties table

### Sheet 7: Wall Framing Elevations
- Wall girt locations and sizes
- Bracing locations
- Opening framing (headers, jambs)
- Connection details at base, eave, and corners

### Sheet 8: Structural Details
- Base plate connection (anchor bolts, plate size, welds)
- Knee brace / haunch connection
- Ridge plate connection
- Beam-to-column connections
- Bracing connections
- Any special connections

### Additional Requirements
- Structural calculations (wind, snow, seismic, dead/live loads)
- Risk category classification
- Wind speed and snow load ratings
- Soil report (sometimes)
- Energy compliance documentation (sometimes)

**Key insight:** Many metal building manufacturers provide the engineering package (structural calculations, framing plans, connection details) already stamped by a PE. The site-specific items (site plan, foundation plan with local soil conditions) are typically the owner/architect responsibility.

---

## 2. Tools for IFC to 2D Drawing Extraction

### Open Source

| Tool | Type | Output | Notes |
|------|------|--------|-------|
| **IfcConvert** (IfcOpenShell) | CLI | SVG | Auto-section, auto-elevation, plan views. Most mature open source option. |
| **ifcopenshell.draw** | Python API | SVG | Programmatic control over drawing generation. Same engine as IfcConvert. |
| **Bonsai** (BlenderBIM) | Blender add-on | SVG (then PDF via Inkscape) | Full drawing sheet management, annotations, dimensions, title blocks. |
| **FreeCAD BIM** | Desktop app | SVG, PDF, DXF | Section planes, TechDraw pages, 2D export. Native IFC support improving. |

### Commercial

| Tool | Type | Output | Notes |
|------|------|--------|-------|
| **ARES Commander** (Graebert) | Desktop CAD | DWG | Extract plans, sections, elevations from IFC. BIM-to-CAD automation. |
| **KBim D-Generator** | Specialized | 2D drawings | Specifically designed for building permit drawings from IFC. |
| **usBIM.blueprint** (ACCA) | Cloud-based | DXF, DWG, DWF | Upload IFC, extract floor plans and sections. |
| **OrthoGen** | Desktop | 2D drawings | Automated orthographic drawing production from 3D models. |

---

## 3. IfcOpenShell / IfcConvert (CLI)

IfcConvert is the most capable open-source command-line tool for extracting 2D views from IFC files.

### Key Commands

```bash
# Basic floor plan SVG
IfcConvert model.ifc plan.svg --plan --bounds 1189x841

# Auto-generate section cuts based on model extents
IfcConvert model.ifc sections.svg --auto-section

# Auto-generate all four elevations
IfcConvert model.ifc elevations.svg --auto-elevation

# Floor plan at specific scale (1:100) on A3 sheet
IfcConvert model.ifc plan.svg --plan --scale 1:100 --bounds 420x297

# Section at specific element
IfcConvert model.ifc section.svg --section-ref "GlobalId"

# Section at specific height (e.g., 1.2m above floor)
IfcConvert model.ifc plan.svg --section-height 1.2

# Auto-derive section heights from storey elevations
IfcConvert model.ifc plan.svg --section-height-from-storeys

# Include space names and areas
IfcConvert model.ifc plan.svg --print-space-names --print-space-areas

# Show door swing arcs
IfcConvert model.ifc plan.svg --door-arcs

# Draw storey height reference lines (useful for sections)
IfcConvert model.ifc section.svg --draw-storey-heights

# Exclude certain entity types
IfcConvert model.ifc plan.svg --exclude entities IfcOpeningElement

# Filter to specific entities
IfcConvert model.ifc plan.svg --include entities IfcWall IfcColumn IfcBeam
```

### SVG Rendering Options

| Flag | Purpose |
|------|---------|
| `--svg-poly` | Polygonal hidden line rendering (faster) |
| `--svg-prefilter` | Pre-filter faces before HLR (faster) |
| `--svg-project` | Hidden line rendering on all views, not just elevations |
| `--svg-segment-projection` | Segment projection by original products |
| `--svg-write-poly` | Approximate all curves as polygons |
| `--svg-without-storeys` | Exclude storey drawings |
| `--svg-no-css` | Omit CSS declarations |
| `--svg-xmlns` | Store name/GUID in separate namespace |

### What It Produces

- **Vector SVG** for elements at the cut plane (walls, columns, beams cut in section)
- **Raster rendering** for elements beyond the cut plane (furniture, background elements)
- **CSS classes** based on IFC entity type (allows styling in post-processing)
- **Semantic attributes** (GlobalId, Name) embedded in SVG elements

### Limitations

- No annotations, dimensions, or text labels (must be added in post-processing)
- No title block or sheet layout
- No automatic dimensioning
- Large models can be slow and memory-intensive
- Raster portion has limited quality control

---

## 4. ifcopenshell.draw (Python API)

The `ifcopenshell.draw` module exposes the same engine as IfcConvert but with programmatic control from Python.

### draw_settings Parameters (31 total)

```python
import ifcopenshell.draw as draw

settings = draw.draw_settings()

# Drawing generation modes
settings.auto_floorplan = True      # Auto-generate floor plans
settings.auto_elevation = False     # Auto-generate elevations
settings.auto_section = False       # Auto-generate sections

# Canvas dimensions and scale
settings.width = 297.0              # mm (A3 landscape)
settings.height = 420.0             # mm
settings.scale = 0.01               # 1:100

# Filtering
settings.exclude_entities = "IfcOpeningElement"
settings.include_entities = ""
settings.storey_filter = ""         # Target specific storeys
settings.zone_filter = ""           # Target specific zones
settings.prefilter = True

# Space/zone display
settings.space_names = False        # Show space names
settings.space_areas = False        # Show space areas
settings.arrange_spaces = False
settings.arrange_zones = False

# Geometry options
settings.include_projection = True  # Project beyond-plane elements
settings.include_curves = False     # Draw curves (Plan/Axis)
settings.door_arcs = False          # Door swing arcs
settings.hlr_poly = False           # Polygonal HLR
settings.mirror_y = False

# Caching
settings.cache = False

# CSS styling
settings.css = ""                   # Custom CSS for SVG output
```

### Basic Usage

```python
import ifcopenshell
import ifcopenshell.draw as draw

model = ifcopenshell.open("building.ifc")

settings = draw.draw_settings()
settings.auto_floorplan = True
settings.auto_elevation = True
settings.auto_section = True
settings.scale = 0.01  # 1:100

svg_output = draw.main(settings, files=[model])

with open("drawings.svg", "w") as f:
    f.write(str(svg_output))
```

### Advantages Over CLI

- Can be scripted into automated pipelines
- Can process multiple IFC files (federated models)
- Can be combined with annotation generation, SVG manipulation, PDF assembly
- Integrates with Jupyter notebooks for visual inspection

---

## 5. Bonsai (BlenderBIM) Drawing Pipeline

Bonsai is the most complete open-source tool for going from IFC to annotated construction drawings. It runs as a Blender add-on.

### Drawing Workflow

1. **Open/Create IFC model** in Bonsai
2. **Add drawing views** (plan, section, elevation) via the Drawings and Documents panel
3. **Generate SVG** -- Bonsai cuts the model and outputs SVG to `DATA_DIR/diagrams/`
4. **Add annotations** -- dimensions, text, leaders, levels, symbols, grids
5. **Compose sheets** -- title blocks, multiple views per sheet, drawing numbers
6. **Export** -- open in Inkscape for final touches, export to PDF

### Drawing Types Supported

- Floor plans (horizontal section at configurable height)
- Sections (vertical cuts at configurable locations)
- Elevations (exterior views from any direction)
- Detail views (enlarged areas)
- Shadow diagrams

### Annotation Capabilities

| Type | Description |
|------|-------------|
| **Dimensions** | Linear, angular, radial, diametric. Dynamic from model or overridden. |
| **Coordinates** | Relative/absolute levels, spot elevations, ceiling heights |
| **Text** | Standalone text, text with leaders, tags/symbols |
| **References** | Section symbols, elevation markers, detail indicators |
| **Grids** | IFC grid lines with bubbles |
| **Hatching** | Material patterns and hatching |
| **Special** | Stair/ramp arrows, door swings |
| **Custom** | Arbitrary lines and polygons |

### Sheet Management

- Create sheets with title blocks (logo, project info, sheet number, revision)
- Add multiple drawing views to a single sheet
- Organize into drawing sets
- Export individual sheets or full sets

### Output Format

- SVG (primary output, vector for cut entities, raster for projection)
- Fonts rendered as SVG text for annotation
- Sheets composed as SVG with embedded views
- PDF via Inkscape CLI (`inkscape --export-type=pdf sheet.svg`)

### Automation Potential

Bonsai can be driven headlessly via Blender's Python API:

```bash
blender --background --python generate_drawings.py -- model.ifc
```

This enables scripted generation of all drawing views and sheet layouts without opening the GUI.

### Current Limitations

- Documentation is marked "Work in Progress" (as of 2026)
- Performance can be slow on large models
- Requires Inkscape for PDF output
- Rasterized projection elements have limited quality
- Learning curve for Blender + Bonsai workflow

---

## 6. FreeCAD BIM Drawing Pipeline

FreeCAD provides an alternative open-source path with native IFC support (improving rapidly).

### Workflow

1. **Import IFC** into FreeCAD (or use native IFC mode)
2. **Place Section Planes** where sections/elevations are needed
3. **Create Shape2DView** from building parts and section planes
4. **Add to TechDraw page** with title block
5. **Add dimensions and annotations** in TechDraw
6. **Export** to SVG, PDF, or DXF

### Supported 2D Entities

- Linework (walls, columns, structural members)
- Hatches (material fills)
- Texts (labels, notes)
- Dimensions (linear, angular)
- View definitions (section planes)

### Output Formats

- SVG
- PDF
- DXF
- DWG (via ODA converter)

### Advantages

- Familiar CAD-like interface
- TechDraw provides proper drawing sheet management with title blocks
- Can embed 2D drawings inside IFC models
- Active development with improving native IFC support

### Limitations

- IFC round-tripping still has issues
- TechDraw annotation tools less mature than commercial CAD
- Slower than IfcConvert for batch processing
- Less scriptable than the Python API approach

---

## 7. Commercial / Other Tools

### ARES Commander (Graebert)
- Full DWG-based CAD with BIM drawing extraction
- Import IFC, extract plan/section/elevation views
- Full dimensioning and annotation in DWG
- Batch automation via LISP/API
- Cost: ~$400/year

### KBim D-Generator
- Purpose-built for generating building permit drawings from IFC
- Interactive section line placement
- Automatic 2D drawing generation
- Designed specifically for the IFC-to-permit workflow

### usBIM.blueprint (ACCA Software)
- Cloud-based IFC to 2D conversion
- Upload IFC, get floor plans and sections
- Export to DXF, DWG, DWF
- Live measurement capabilities
- Free tier available

---

## 8. IFC to DXF / SVG / PDF Conversion

### IFC to SVG

| Method | Notes |
|--------|-------|
| `IfcConvert model.ifc output.svg` | Best open-source option. Semantic SVG with CSS classes. |
| `ifcopenshell.draw` Python API | Same engine, scriptable. |
| Bonsai drawing export | Most complete (includes annotations). |
| FreeCAD Shape2DView export | Good for individual views. |

### IFC to DXF/DWG

| Method | Notes |
|--------|-------|
| ARES Commander | Full featured, commercial. |
| usBIM.blueprint | Cloud-based, free tier. |
| ABViewer | Desktop, File > Save As > DXF. |
| Aspose/GroupDocs | Online converters (basic quality). |
| FreeCAD export | Via ODA File Converter for DWG. |

### SVG to PDF (for sheet assembly)

| Library | Notes |
|---------|-------|
| **Inkscape CLI** | `inkscape --export-type=pdf sheet.svg` -- Best quality, handles complex SVG. |
| **svglib + ReportLab** | Python library. `svg2rlg()` + `renderPDF.drawToFile()`. |
| **fpdf2** | Python library. Embeds SVG as vector in PDF. Lightweight. |
| **CairoSVG** | Python library. High quality rendering. |
| **WeasyPrint** | Python library. HTML/CSS to PDF (can embed SVG). |

---

## 9. What Can Be Automated vs. Requires Human Drafting

### Fully Automatable from IFC (80-90% of geometry)

| Item | Tool | Notes |
|------|------|-------|
| Floor plan geometry | IfcConvert / Bonsai | Walls, columns, doors, windows cut at section height |
| Section cuts | IfcConvert / Bonsai | Vertical sections through model |
| Elevations | IfcConvert / Bonsai | All 4 exterior views |
| Roof framing plan | IfcConvert / Bonsai | If structural members are in the IFC model |
| Column grid | Bonsai | If IfcGrid entities exist in the model |
| Member sizes/labels | Bonsai / Python scripting | Extract from IFC properties, place as annotations |
| Material hatching | Bonsai | Based on IfcMaterial assignments |
| Space names/areas | IfcConvert | `--print-space-names --print-space-areas` |
| Door swings | IfcConvert / Bonsai | `--door-arcs` flag |

### Semi-Automatable (need templates + model data)

| Item | Approach | Notes |
|------|----------|-------|
| Dimensions | Bonsai annotation tools or Python scripting | Can snap to model geometry but placement needs rules |
| Title blocks | SVG template + data injection | Project name, date, scale, sheet number from metadata |
| Section/elevation markers | Bonsai reference annotations | Need to define which sections reference which views |
| Detail callouts | Manual placement, content from model | Identify critical connections, extract detail views |
| Schedules (door, window, material) | Python extraction from IFC | Data is in the model, formatting needs templates |
| Sheet organization | Script with templates | Map views to sheets per the permit set structure |

### Requires Human Drafting / Engineering Judgment

| Item | Why |
|------|-----|
| **Site plan** | Property boundaries, setbacks, utilities -- not in the building IFC model |
| **Foundation design** | Requires geotechnical data, local soil conditions, PE judgment |
| **Connection detail design** | Structural engineering judgment for base plates, welds, bolts |
| **Structural calculations** | Load analysis requires engineering software (not just drawing generation) |
| **Code compliance annotations** | Fire ratings, egress requirements, accessibility -- jurisdiction-specific |
| **Dimension placement strategy** | Where to place dimension strings for clarity is a design decision |
| **Notes and specifications** | General notes, material specs, code references |
| **PE stamp** | Licensed engineer must review and stamp |

### Realistic Automation Estimate for a Metal Building Permit Set

| Sheet | Automation Level | Notes |
|-------|-----------------|-------|
| Site Plan | 10% | Mostly manual (survey data, not in IFC) |
| Foundation Plan | 40% | Anchor bolt layout from IFC, but design is engineering |
| Floor Plan | 85% | Geometry automated, dimensions semi-automated |
| Elevations (x4) | 85% | Geometry automated, labels semi-automated |
| Sections | 75% | Cuts automated, annotation needs work |
| Roof Framing | 80% | If structural model is complete |
| Wall Framing | 80% | If structural model is complete |
| Structural Details | 30% | Detail views from model, but design is engineering |

---

## 10. Recommended Pipeline

### Architecture: IFC to Permit PDF Set

```
IFC Model (authored in Bonsai/FreeCAD/Revit)
    |
    v
[IfcOpenShell Python API] ────── Extract geometry + properties
    |
    v
[ifcopenshell.draw / IfcConvert] ── Generate SVG views
    |                                   - auto floor plans
    |                                   - auto sections
    |                                   - auto elevations
    v
[Bonsai (headless) OR Python SVG manipulation]
    |                                   - Add dimensions
    |                                   - Add annotations
    |                                   - Add grid lines
    |                                   - Add hatching
    v
[Sheet Composer (Python)]
    |                                   - SVG templates for title blocks
    |                                   - Place views on sheets
    |                                   - Add sheet numbers, scale, date
    |                                   - Add revision tracking
    v
[Inkscape CLI / svglib+ReportLab]
    |                                   - Convert SVG sheets to PDF
    |                                   - Combine into multi-page PDF
    v
[Permit-Ready PDF Set]
```

### Implementation Strategy

#### Phase 1: Proof of Concept (SVG extraction)
```python
# Generate all basic views from IFC
import ifcopenshell
import ifcopenshell.draw as draw

model = ifcopenshell.open("metal_building.ifc")

# Floor plans
plan_settings = draw.draw_settings()
plan_settings.auto_floorplan = True
plan_settings.door_arcs = True
plan_settings.space_names = True
plan_svg = draw.main(plan_settings, files=[model])

# Elevations
elev_settings = draw.draw_settings()
elev_settings.auto_elevation = True
elev_svg = draw.main(elev_settings, files=[model])

# Sections
section_settings = draw.draw_settings()
section_settings.auto_section = True
section_svg = draw.main(section_settings, files=[model])
```

#### Phase 2: Annotation Engine
- Parse SVG output to identify walls, columns, openings
- Apply dimensioning rules (overall dims, column spacing, opening locations)
- Add text labels (room names, member sizes, material callouts)
- Use IfcOpenShell property extraction to pull member sizes, material names

#### Phase 3: Sheet Assembly
- Create SVG title block templates (company logo, project info fields)
- Map views to sheets per the permit set structure
- Scale and position views on sheets
- Add sheet-level annotations (north arrows, scale bars, revision blocks)

#### Phase 4: PDF Generation
```bash
# Convert each sheet SVG to PDF
inkscape --export-type=pdf sheet_01_site_plan.svg
inkscape --export-type=pdf sheet_02_foundation.svg
inkscape --export-type=pdf sheet_03_floor_plan.svg
# ... etc

# Combine into single PDF
pdfunite sheet_*.pdf permit_set.pdf
# OR use Python: PyPDF2, pikepdf, or reportlab
```

#### Phase 5: Validation
- Check all required sheets are present
- Verify scale is correct on each sheet
- Confirm all required annotations are present
- Cross-reference against jurisdiction checklist

### Alternative: Bonsai-Centric Pipeline

If the IFC model is authored in Bonsai, the entire drawing pipeline stays within one ecosystem:

1. Author IFC model in Bonsai (Blender)
2. Create drawing views in Bonsai's Drawings panel
3. Add annotations, dimensions, grids in Bonsai
4. Compose sheets with title blocks in Bonsai
5. Export sheets as SVG
6. Convert to PDF via Inkscape
7. Submit to jurisdiction

This is currently the most integrated open-source path, but documentation is still incomplete and the workflow has a steeper learning curve.

---

## 11. Sources

### IFC to 2D Drawing Tools
- [OSArch: Tool to quickly output 2D views/sections from IFC](https://community.osarch.org/discussion/803/tool-to-quickly-output-2d-views-sections-from-ifc)
- [OSArch: 2D drawings in DWG from IFC files](https://community.osarch.org/discussion/1450/2d-drawings-in-dwg-from-ifc-files)
- [BibLus: How to create technical drawings from an IFC model](https://biblus.accasoftware.com/en/how-to-create-technical-drawings-from-an-ifc-model/)
- [Graebert: BIM to CAD DWG Drawings Automation](https://www.graebert.com/blog/product-news/bim-to-cad-dwg-drawings-automation-from-rvt-or-ifc/)

### IfcOpenShell / IfcConvert
- [IfcOpenShell GitHub: Construction Drawing Generation Issue #1153](https://github.com/IfcOpenShell/IfcOpenShell/issues/1153)
- [IfcOpenShell GitHub: 2D plan from IFC Discussion #5915](https://github.com/IfcOpenShell/IfcOpenShell/discussions/5915)
- [IfcConvert Usage Documentation](https://docs.ifcopenshell.org/ifcconvert/usage.html)
- [IfcConvert Deep Wiki](https://deepwiki.com/IfcOpenShell/IfcOpenShell/3-ifcconvert)
- [ifcopenshell.draw API Documentation](https://docs.ifcopenshell.org/autoapi/ifcopenshell/draw/index.html)
- [IfcOpenShell Blog: Creating 2D SVG floor plans](http://blog.ifcopenshell.org/2015/07/creating-2d-svg-floor-plans-from-ifc.html)

### Bonsai (BlenderBIM)
- [Bonsai Documentation](https://docs.bonsaibim.org/)
- [Bonsai Drawings Guide](https://docs.bonsaibim.org/guides/drawings/index.html)
- [Bonsai Features Guide (OSArch Wiki)](https://wiki.osarch.org/index.php?title=BlenderBIM_Add-on/BonsaiBIM_Features_Guide)
- [OSArch: What does Bonsai need for a basic architectural drawing pack](https://community.osarch.org/discussion/2737/what-does-bonsai-need-to-be-ready-for-a-basic-architectural-drawing-pack)
- [Bonsai for Dummies (PDF)](https://community.osarch.org/uploads/editor/fb/k1nb9g00cmyt.pdf)
- [Bonsai Tutorials (OpeningDesign)](https://hub.openingdesign.com/OpeningDesign/Bonsai_Tutorials)

### FreeCAD BIM
- [FreeCAD Manual: Generating 2D Drawings](https://wiki.freecad.org/Manual:Generating_2D_drawings)
- [FreeCAD BIM Update 25 (Yorik van Havre)](https://www.patreon.com/posts/freecad-bim-25-114242458)

### Metal Building Permit Requirements
- [Metal-Buildings.org: Metal Building Permits and Codes](https://www.metal-buildings.org/metal-building-permits-and-codes/)
- [Portland.gov: Building Permit Requirements for Prefabricated Metal Buildings](https://www.portland.gov/ppd/documents/building-permit-requirements-prefabricated-metal-buildings/download)
- [City of Calimesa: Metal Building Permit Plan Review Checklist](https://www.calimesa.gov/DocumentCenter/View/1682/Metal-Building-Permit---Plan-Review-Checklist?bidId=)
- [GetCarports: Metal Building Permit Checklist 2026](https://www.getcarports.com/metal-building-permit-checklists)
- [Portland.gov: Plans You Need for a Building Permit](https://www.portland.gov/ppd/documents/plans-you-need-building-permit-brochure-6/download)

### IFC Format Conversion
- [BibLus: Complete Guide to Convert IFC to DXF](https://biblus.accasoftware.com/en/a-complete-guide-to-convert-ifc-files-to-dxf/)
- [Aspose: IFC to SVG Converter](https://products.aspose.app/cad/conversion/ifc-to-svg)

### SVG to PDF Tools
- [fpdf2: SVG Support](https://py-pdf.github.io/fpdf2/SVG.html)
- [svglib on PyPI](https://pypi.org/project/svglib/)
- [ReportLab: Adding SVGs to PDFs](https://blog.pythonlibrary.org/2018/04/12/adding-svg-files-in-reportlab/)

### Automation & AI
- [ScienceDirect: Framework for automated 2D drawing generation from BIM using deep learning](https://www.sciencedirect.com/science/article/abs/pii/S0957417425006402)
- [DataDrivenConstruction: AI Agents for AEC](https://datadrivenconstruction.io/)
- [IfcOpenShell.org](https://ifcopenshell.org/)

---

## Key Takeaways

1. **Yes, 2D plan views can be extracted from IFC automatically.** IfcConvert and ifcopenshell.draw can generate floor plans, sections, and elevations as SVG with a single command or a few lines of Python.

2. **The geometry is the easy part; annotations are the hard part.** Automated section cuts produce clean linework, but dimensions, labels, notes, and detail callouts still require either Bonsai's annotation tools or custom scripting.

3. **Bonsai is the most complete open-source pipeline** for going from IFC to annotated, sheet-organized construction drawings. It handles views, annotations, sheets, and title blocks -- but documentation is still incomplete and the Blender learning curve is real.

4. **A realistic automation level for a metal building permit set is 60-70%.** Geometry extraction, basic views, and sheet composition can be automated. Site plans, foundation engineering, structural details, and PE review cannot.

5. **The recommended approach is a hybrid pipeline:** use ifcopenshell.draw for batch SVG generation, Python scripting for annotation and sheet assembly, and Inkscape/svglib for PDF conversion. Manual work focuses on engineering judgment items (foundation design, connection details, structural calculations) and the PE stamp.

6. **No single open-source tool produces a complete permit-ready PDF set today.** The pipeline requires combining multiple tools. This is an opportunity for automation tooling that ties the pieces together.
