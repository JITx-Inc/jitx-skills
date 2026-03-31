# Parts Sourcing and Footprint Conversion

Optional tools for verifying part sourcing and obtaining footprints. Claude selects parts based on engineering requirements and tradeoffs first — these tools are dumb data lookups, not decision makers.

## Setup

```bash
pip install easyeda2kicad requests
```

## Scripts (in this skill's `scripts/` directory)

### `lcsc_lookup.py` — Stock, pricing, datasheet, footprint

Given an LCSC part number, fetches real-time stock/pricing from LCSC and KiCad footprints from EasyEDA. No API keys required.

```bash
# Check stock and pricing
python scripts/lcsc_lookup.py C165948

# Download KiCad footprint
python scripts/lcsc_lookup.py C165948 --footprint -o usb_c.kicad_mod

# Get pinout
python scripts/lcsc_lookup.py C165948 --pinout

# Everything at once
python scripts/lcsc_lookup.py C165948 --all -o usb_c.kicad_mod
```

### `kicad_to_jitx.py` — Convert KiCad footprint to JITX component

Deterministic converter from `.kicad_mod` to JITX Python. Handles all pad types, Y-axis inversion, duplicate names, BoxSymbol layout.

```bash
python scripts/kicad_to_jitx.py usb_c.kicad_mod --class-name USB_C_16P \
    --manufacturer "Korean Hroparts Elec" --mpn "TYPE-C-31-M-12"
```

### Full pipeline: LCSC → KiCad → JITX

**All downloaded data must be saved to the project** — datasheets, KiCad footprints, and generated components. This ensures reproducibility and avoids repeated downloads.

```bash
# 1. Download footprint to project (creates directory if needed)
mkdir -p kicad_footprints
python scripts/lcsc_lookup.py C165948 --footprint -o kicad_footprints/TYPE-C-31-M-12.kicad_mod

# 2. Convert to JITX component (output to project source tree)
python scripts/kicad_to_jitx.py kicad_footprints/TYPE-C-31-M-12.kicad_mod \
    --class-name USB_C_16P \
    --manufacturer "Korean Hroparts Elec" --mpn "TYPE-C-31-M-12" \
    -o src/<namespace>/components/connectors/usb_c_16p.py
```

**Project directory convention:**
```
project/
├── datasheets/          # Downloaded PDFs (from manufacturer sites)
├── kicad_footprints/    # Downloaded .kicad_mod files (from lcsc_lookup.py)
└── src/<namespace>/
    └── components/      # Generated JITX Python (from kicad_to_jitx.py)
```

Copy both scripts into the project's `scripts/` directory so sub-agents can run them.

## Part Selection Workflow

1. **Claude proposes ideal parts** based on engineering requirements: voltage/current ratings, package thermal limits, peripheral set, interface support, proven reliability. Weigh tradeoffs (dropout vs efficiency, pin count vs board area, feature set vs complexity).

2. **Optionally verify sourcing**: if a specific LCSC part number is known, run `lcsc_lookup.py` to check stock and pricing. If the preferred part is unavailable, Claude proposes an alternative — the lookup does not dictate the architecture.

3. **Record chosen parts** in PLAN.md with MPN, LCSC code (if applicable), package, key specs, and rationale.

## Footprint Workflow

### Standard packages — use JITX generators

| Package | Generator |
|---------|-----------|
| QFN | `QFN(...)` |
| SON/DFN | `SON(...)` |
| SOIC | `SOIC(...)` |
| SOT-23/SOT-223 | jitxlib standard library |
| QFP | `QFP(...)` |
| BGA | `BGA(...)` |

### Non-standard packages — use the scripts

For connectors, RF modules, unusual mechanical packages:

1. Find the LCSC part number (from JLCPCB search or Claude's knowledge)
2. Run `lcsc_lookup.py <LCSC_ID> --footprint -o kicad_footprints/<mpn>.kicad_mod`
3. Run `kicad_to_jitx.py kicad_footprints/<mpn>.kicad_mod --class-name MyPart`
4. Review output and build-test
5. If the generated footprint is missing mechanical features (alignment posts, mounting holes) that are in the datasheet but not in EasyEDA's model, add them using `circle()` for round holes and `capsule()` for oval holes — never `rectangle()` for drill cutouts

**NEVER hand-craft pad positions for non-standard packages.** Use the script output as the base. If you must add pads the script didn't generate, verify shapes against the datasheet mechanical drawing: round holes use `circle(radius)`, oval holes use `capsule(width, height)`.

Always use `BoxSymbol`. Never convert KiCad schematic symbol graphics.

