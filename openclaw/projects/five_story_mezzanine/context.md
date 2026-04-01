# Five Story Mezzanine Commercial Building

## Design Intent

5-story commercial building with structural steel frame, steel cladding, and double-height mezzanine decks on floors 3-4 (east and west sides). Ground floor retail with glass storefront on south facade.

## Key Constraints

- Footprint: 40m x 25m
- Structural grid: 8m x 8m (6x4 bays)
- Floor-to-floor: 4.0m (ground floor 4.5m)
- Mezzanines at floors 3-4: 10m deep, east and west sides, +2.0m above floor
- Steel cladding: 2.0m x 3.5m panels, 4mm thick
- South ground floor: glass curtain wall

## Estimated Element Count

- Storeys: 7 (Ground + 5 floors + roof, plus 2 mezzanine sub-levels)
- Columns: ~150 (30 grid points x 5 floors) + ~20 mezzanine edge columns
- Beams: ~180 (grid lines x 5 floors) + ~20 mezzanine edge beams
- Slabs: 6 (5 floors + roof) + 4 mezzanine decks
- Curtain walls/cladding: 4 facades x 5 floors
- Windows: ~60 (punched windows on east/west, floors 2-5)
- Doors: 2 (main + service)
- **Total: ~500-600 elements**

## Key Decisions

(Updated as the project progresses)

## Current State

- [x] Prompt written (out/five_story_mezzanine/prompt.txt)
- [x] IFC generated + patched (out/five_story_mezzanine/five_story_mezzanine.ifc)
  - 174 columns, 285 beams, 9 slabs, 4 curtain walls, 330 cladding plates
  - 20 perimeter walls (4 facades × 5 floors, 150mm backing behind curtain panels)
  - 2 doors (main entrance south L1, service entrance north L1)
  - 32 windows (east + west facades, floors 2–5, 4 bays each)
  - Patches: scripts/patch_five_story_beams.py, scripts/patch_five_story_openings.py
- [ ] Structural analysis run
- [ ] Viewed in web viewer
- [ ] Component selections started
