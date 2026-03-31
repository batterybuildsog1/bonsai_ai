# Project Template

When starting a new project, create this structure under `projects/<project-name>/`:

```
projects/<project-name>/
├── context.md              ← design intent, key decisions, constraints
├── log.md                  ← session-by-session work log
│
├── inspiration/
│   ├── index.md            ← descriptions of all visual references
│   ├── notes.md            ← human notes about design intent from images
│   └── (image files)       ← .jpg, .png — read directly with vision
│
├── site/
│   ├── index.md            ← structured summary of all site constraints
│   ├── zoning.md           ← setbacks, FAR, height, use restrictions
│   ├── survey.md           ← grades, elevations, boundaries, easements
│   ├── soils.md            ← bearing capacity, water table, recommendations
│   ├── photos/             ← site photos (readable with vision)
│   └── raw/                ← source PDFs + text extractions
│
├── components/
│   ├── index.md            ← master component schedule
│   ├── selections/         ← per-system spec files
│   │   └── <system>.md     ← dimensions, properties, "Impact on Model"
│   └── specs/              ← manufacturer PDFs + text extractions
```

## Starter content for context.md

```markdown
# <Project Name>

## Design Intent
(What is this building? What are we trying to achieve?)

## Key Constraints
- Site: (reference site/index.md once populated)
- Budget:
- Timeline:
- Program requirements:

## Key Decisions
(Updated as the project progresses)

## Current State
- [ ] Site constraints documented
- [ ] Inspiration collected
- [ ] Initial massing complete
- [ ] Structure laid out
- [ ] Envelope defined
- [ ] Openings placed
- [ ] Component selections started
```

## Starter content for components/index.md

```markdown
# Component Schedule

| System | Status | Selection | Spec File | Impact on Model |
|--------|--------|-----------|-----------|-----------------|
| Structure - beams | Generic | — | — | — |
| Structure - columns | Generic | — | — | — |
| Cladding | Generic | — | — | — |
| Windows | Generic | — | — | — |
| Roofing | Generic | — | — | — |

## Pending Selections
(Items under review)
```

## Starter content for site/index.md

```markdown
# Site Constraints Summary

## Location
(Address, jurisdiction)

## Envelope
- Max height:
- Setbacks: front / side / rear
- FAR:

## Site Conditions
- Grade range:
- Soil bearing:
- Water table:

## Source Documents
(List uploaded PDFs in raw/ with extraction status)
```
