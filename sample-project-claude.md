# CLAUDE.md

## Project Overview

This is a JITX hardware design project.

**Always invoke `/jitx` at the start of any session.** The skill handles environment setup, sub-skill routing, and the project builder workflow for complete board designs.

### Workflows

- **Single task** (one component, one circuit, one substrate): `/jitx` routes to the appropriate subskill directly.
- **Complete board design** (multiple components, circuits, substrate): `/jitx` triggers the Project Builder workflow — start with Phase 0 to create PLAN.md and ARCHITECTURE.md before writing any code.

## Project-Specific Notes

- `designs/` — Build output. **Never delete** (may contain manual layout edits).
- `datasheets/` — Component datasheets for reference.
- `kicad_footprints/` — KiCad footprint files for non-standard packages.
