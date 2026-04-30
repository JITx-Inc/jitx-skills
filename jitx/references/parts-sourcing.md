# Parts Sourcing and Footprint Data

How to get component data (datasheets, footprints, pinouts) into JITX projects. Multiple data sources are supported — the user chooses what's appropriate for their workflow.

## Data Sources (in priority order)

### 1. User-Provided Data (preferred)

Users may supply their own:

- **Datasheets** — PDF files placed in `datasheets/<mpn>.pdf`
- **KiCad footprints** — `.kicad_mod` files placed in `kicad_footprints/`
- **Specifications** — pin count, package type, dimensions provided directly
- **Existing component libraries** — pre-built JITX components from their codebase

Always ask if the user has data before reaching for external tools.

### 2. JITX Standard Generators (for standard packages)

For standard packages, use JITX landpattern generators — no external data needed:

| Package | Generator |
|---------|-----------|
| QFN | `QFN(...)` |
| SON/DFN | `SON(...)` |
| SOIC | `SOIC(...)` |
| SOT-23/SOT-223 | jitxlib standard library |
| QFP | `QFP(...)` |
| BGA | `BGA(...)` |

Dimensions come from the datasheet (user-provided or fetched). No footprint download needed.

### 3. LCSC/EasyEDA Lookup (opt-in only — requires user approval)

> **Licensing note:** EasyEDA component data may have its own terms of use. The `parts2jitx` tool and the LCSC/EasyEDA data flow should be treated as a separate, optional integration. **Do not use this data source without explicit user approval.** Ask the user before suggesting LCSC lookup — some users (especially commercial) will not want EasyEDA-sourced data in their project.

For non-standard packages (connectors, RF modules, unusual mechanical) where the user doesn't have a footprint and has approved LCSC/EasyEDA as a data source, the `parts2jitx` pip package provides automated lookup:

```bash
pip install parts2jitx
```

**CLI commands:**

```bash
# Check stock and pricing
parts2jitx-lcsc C165948

# Download KiCad footprint
parts2jitx-lcsc C165948 --footprint -o kicad_footprints/usb_c.kicad_mod

# Get pinout
parts2jitx-lcsc C165948 --pinout

# Convert KiCad footprint to JITX component
parts2jitx-kicad kicad_footprints/usb_c.kicad_mod --class-name USB_C_16P \
    --manufacturer "Korean Hroparts Elec" --mpn "TYPE-C-31-M-12"
```

**When to suggest LCSC lookup (only after user approval):**
- User needs a non-standard footprint, doesn't have one, and approves LCSC as a source
- User wants to verify stock/pricing for a JLCPCB order
- User provides an LCSC part number (C-prefix)

**When NOT to use:**
- User has their own footprint data
- Standard package with JITX generators available
- User has not explicitly approved LCSC/EasyEDA sourcing
- Commercial projects where data provenance matters

### Converting User-Provided KiCad Footprints

Users who already have `.kicad_mod` files (from KiCad libraries, vendor downloads, or their own designs) can convert them with `parts2jitx-kicad`:

```bash
parts2jitx-kicad my_footprint.kicad_mod --class-name MyConnector \
    --manufacturer "Amphenol" --mpn "12345" \
    -o src/<namespace>/components/connectors/amphenol_12345.py
```

This works with any `.kicad_mod` file regardless of source — not just LCSC/EasyEDA.

## Data Audit (Project Builder)

In the Project Builder workflow, Phase 0 includes a **data source audit** before any work begins. The orchestrator presents a table showing where each component's data will come from, and the user approves or provides alternatives. See `references/project-builder-flow.md` Phase 0 for details.

## Part Selection Workflow

1. **Claude proposes ideal parts** based on engineering requirements: voltage/current ratings, package thermal limits, peripheral set, interface support, proven reliability. Weigh tradeoffs (dropout vs efficiency, pin count vs board area, feature set vs complexity).

2. **Identify data source** for each part: does the user have a datasheet? A footprint? Or should we search/download?

3. **Record chosen parts** in PLAN.md with MPN, package, key specs, data source, and rationale.

## Footprint Workflow

### Standard packages — use JITX generators

Dimensions from the datasheet mechanical drawing. No external footprint needed.

### Non-standard packages — convert from KiCad

Source the `.kicad_mod` from one of:
- User's existing KiCad library
- Manufacturer's KiCad library download
- LCSC/EasyEDA (via `parts2jitx-lcsc --footprint`, only if user has approved this data source)

Then convert: `parts2jitx-kicad <file.kicad_mod> --class-name MyPart`

**NEVER hand-craft pad positions for non-standard packages.** Use the converter output as the base. If you must add pads the converter didn't generate, verify shapes against the datasheet mechanical drawing: round holes use `circle(radius)`, oval holes use `capsule(width, height)`.

Always use `BoxSymbol`. Never convert KiCad schematic symbol graphics.

## Project Directory Convention

All sourced data must be saved to the project for reproducibility:

```
project/
├── datasheets/          # PDFs (from manufacturer sites or user-provided)
├── kicad_footprints/    # .kicad_mod files (from any source)
└── src/<namespace>/
    └── components/      # Generated JITX Python
```
