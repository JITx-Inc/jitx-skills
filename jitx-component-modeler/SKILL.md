---
name: jitx-component-modeler
description: Create JITX Python component code from datasheets, KiCad footprints, or user specifications. ALWAYS use this skill when user asks to "create a component", "model a part", "generate a component", "add a component", or "make a JITX component" - even without a datasheet. Also triggers on part numbers (NE555, LM1117, RP2040, etc.) and package types (SOIC, QFN, BGA, SON, SOT). Supports user-provided data, JITX generators for standard packages, and optional LCSC/EasyEDA fallback for non-standard footprints. Supports multi-unit symbols, thermal pads, and complex pin mappings.
---

# JITX Component Generation Skill

Generate JITX Python component code from datasheets, user-provided KiCad footprints, or specifications. Data can come from multiple sources — always prefer user-provided data over automated lookups.

## Rule 0 — Verify every API before using it

Do not guess at imports, class names, or chain methods, especially for `Landpattern` / `Pad` / `PadMapping` / generator imports. Common landmines that have all been caught as wrong guesses:

- `Landpattern` and `PadMapping` live in **`jitx.landpattern`**, NOT `jitxlib.landpatterns.core`.
- `PadMapping` keys are **`Port` objects** and values are **`Pad` objects (or sequences of them)** — never strings or pad-number ints.
- `Pad` subclasses have no `add_pad()`; positioning is via `.at(x, y)` from the `Positionable` mixin.
- `Rectangle` is **not a class** — use the function `rectangle(w, h, radius=…)` from `jitx.shapes.composites`. `Circle` *is* a class.
- The SOT generator family only exports `SOT23_3`, `SOT23_5`, `SOT23_6` — there is no `SOT89_3`, `SOT223_3`, or `SOT583_8`. Fall back to a custom `Landpattern` subclass for those.
- `BGADepop` and `QFN_DEFAULT_LEAD_PROFILE` do not exist as exported symbols — see `references/package-examples.md`.

Verification order: (1) canonical repos `github.com/JITx-Inc/py-jitx` and `github.com/JITx-Inc/py-jitx-stdlib`; (2) `https://docs.jitx.com/llms.txt`; (3) installed venv site-packages or `~/.jitx/`. If unresolvable, document as unknown — do not invent an import.

## No fabrication — source authority for geometry and pinout

> **Do not write dimensions, pin labels, or pad assignments from memory.**
>
> If you find yourself writing **"typical dimensions"**, **"reasonable defaults"**, **"user can refine specific values later"**, **"approximate"**, **"will adjust later"**, or any synonym for guessed / default / placeholder geometry on a component that has a real MPN, **stop**. This skill is not a pattern catalog you can skim and walk away from — it is the rule that you don't ship a landpattern from memory.
>
> For every named component (anything with an MPN, distributor part number, or user-supplied datasheet), before writing landpattern dimensions or pin labels, work down this ladder until you have a source:
>
> 1. **Manufacturer's current datasheet** — open the mechanical drawing page (use `extract_pages.py` to pull only those pages — do not read the full PDF). Cite the page/figure where you got each dimension.
> 2. **Sourcing-channel lookup** — if the user has named LCSC/JLCPCB, `parts2jitx-lcsc <C-number>` (stock, lifecycle, datasheet URL) and `parts2jitx-lcsc <C-number> --pinout` (pin labels). Use it as channel evidence and as a pin-label cross-check. Datasheet remains higher authority where they disagree; document the conflict.
> 3. **Ask the user** — for an LCSC C-number, a user-supplied `.kicad_mod`, or the datasheet itself.
>
> If none of the three produce a source, the component is **blocked**. Do not proceed by estimating. The only way out is for the user to explicitly authorize a non-MPN generic component (e.g. "use a typical 0.4 mm pitch QFN-56, this is a placeholder"). Record that authorization in the task acceptance block under `Notes`.
>
> This callout exists because a test session of this skill loaded this very file, said "I have the patterns, I'll proceed without invoking the modeler skill further — writing each component directly with reasonable typical dimensions" — and then fabricated nine components. That is the failure this rule forbids.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

### Verify optional library availability before importing

Before recommending an import from an optional companion library (e.g.
`jitxexamples.components.switchmode_power`, `jitxlib.protocols.*`,
`jitxlib.voltage_divider`), **verify it's importable first**:

```bash
python -c "import jitxexamples"        # ModuleNotFoundError = not installed
python -c "import jitxlib.voltage_divider"
```

`jitxexamples` in particular is **not** installed by `pip install jitx` or
`pip install jitxlib-parts`. If it's missing, port the component from
scratch rather than recommending an import that will fail. Similarly,
`jitxlib.voltage_divider` does not exist in `jitx-4.0.5` (introduced
later) — verify before generating code that imports it.

## Datasheet Handling

**ALWAYS save datasheets locally before reading.**

When user provides a URL or asks to download a datasheet:
1. Download the PDF using curl or wget via Bash
2. Save to `datasheets/<mpn>.pdf` in the project (create folder if needed)
3. Then use the extraction process in Step 0

This ensures:
- Datasheet is available for future reference
- Consistent file paths for extraction scripts
- No repeated downloads

**AVOID REDUNDANT WEB SEARCHES**

Once the datasheet PDF is available, extract pinout, package dimensions, and pin descriptions from it using Step 0. Do NOT search for info that's already in the datasheet. **Also: do NOT write dimensions or pin labels from memory or "typical values" when the datasheet is available.** See "No fabrication — source authority for geometry and pinout" at the top of this file.

**When additional searches ARE appropriate:**
- Datasheet lacks package mechanical drawings (common for simple parts)
- Complex packages (200+ pins) where cross-referencing helps catch errors
- Need separate package drawing document (e.g., TI's MPDS files)

**When searching:**
- Use manufacturer sites: ti.com, analog.com, st.com, nxp.com, microchip.com, infineon.com, onsemi.com
- Search pattern: `"<MPN> datasheet" site:<manufacturer>.com`
- Avoid distributor sites, random aggregators, or unverified PDFs

## Output Location

**ALWAYS place components in a `components/` folder**, even for single components.

### Standard Structure
```
project/
└── src/<namespace>/
    └── components/
        ├── __init__.py
        ├── <category>/
        │   ├── __init__.py
        │   └── <manufacturer>_<mpn>.py
        └── <category>/
            └── ...
```

If `src/<namespace>/` doesn't exist, use:
```
project/
└── components/
    ├── __init__.py
    └── <manufacturer>_<mpn>.py
```

**Category examples:** mcus, connectors, power_linear_regulators, opamp, flash, crystals, leds, logic, timers, buttons, transceivers, diodes_tvs, isolators, power_switchmode

**File naming:** `<manufacturer>_<mpn>.py` - lowercase, underscores for spaces/special chars
- `texas_instruments_NE555.py`
- `raspberry_pi_RP2040.py`
- `renesas_DA14705.py`

## Instructions

When generating a JITX component from a datasheet or specification, follow this structured approach:

### Step 0: Handle Datasheets (CRITICAL)

**NEVER read a full datasheet PDF directly.** Even 50-page PDFs consume excessive context.

**Always extract relevant pages first** using `scripts/extract_pages.py`:

```bash
# Find pages containing keywords
python scripts/extract_pages.py datasheet.pdf --find "pinout" "pin description" "dimension" "package" "ball map" "mechanical"

# Extract matched pages to a smaller PDF
python scripts/extract_pages.py datasheet.pdf --pages 10 11 12 -o datasheet_extract.pdf
```

Then read only the extracted PDF.

**Key pages to find:**
- Pin assignment / ball map (usually pages 10-20)
- Pin description table
- Package mechanical drawing (usually near end)
- Ordering information

**If pymupdf not available**, ask user to provide:
- Pin count and package type
- Screenshot of pinout/ball map
- Package dimensions (body size, pitch, ball/lead size)

**Do NOT** just read the PDF and hope for the best - this will exhaust context.

### Step 1: Extract Key Information

**Before generating from scratch:** for a reusable IC family or common package pattern, search existing references first — see `jitx/references/parts-sourcing.md` "Reference Search Order for Component Modeling". User libraries → `jitxexamples.components` → vendor reference design → generate. Document `searched: found <path>` or `searched: no analog` in the task acceptance block.

**IMPORTANT: Multiple Packages/Variants**

If the datasheet covers multiple package options or component variants, ask the user which one to model:

```
Example: "The datasheet shows 3 package options for this part:
- SOIC-8 (NE555DR)
- PDIP-8 (NE555P)
- VSSOP-8 (NE555DGKR)

Which package would you like me to model?"
```

Do NOT assume or pick one arbitrarily. Ask first.

From the datasheet (or extracted pages), extract:
1. **Component identification**: Manufacturer, MPN, description
2. **Package type**: SOIC, SOT, QFN, BGA, SON, etc.
3. **Pin count**: Total number of pins
4. **Pin functions**: Pin names and functions from pinout table (see Pin Naming below)
5. **Package dimensions**:
   - Body width/length (D, E dimensions)
   - Body height (A dimension)
   - Lead span (E1/D1 or terminal span)
   - Lead pitch (e dimension)
   - Lead width (b dimension)
   - Lead length (L dimension)

### Step 2: Select Package Generator

Use this decision tree to select the appropriate generator:

```
Is it a 2-sided package?
├── Yes, ≤6 pins → SOT23_3, SOT23_5, or SOT23_6
├── Yes, SOT-89 / SOT-223 (asymmetric, wide thermal-tab middle pad)
│       → Custom Landpattern — no jitxlib generator. Do NOT substitute
│         SOT23_3, pad 2 is a wide thermal tab and SOT-23 will produce
│         wrong pad dimensions. See references/package-examples.md
│         §"Custom Landpatterns".
├── Yes, >6 pins with gull-wing leads → SOIC
├── Yes, >6 pins with flat leads (no-lead) → SON
└── No (4-sided or array)
    ├── 4-sided gull-wing leads → QFP
    ├── 4-sided flat/no-lead → QFN
    ├── Bottom ball array → BGA
    └── Custom/unusual (connectors, RF modules, irregular pads)
        → Convert from a KiCad footprint (.kicad_mod):
          parts2jitx-kicad fp.kicad_mod --class-name MyPart
          NEVER hand-craft pad positions for non-standard packages.

    Exception: mechanical / vendor-defined footprints (Tag-Connect TC2050,
    pogo-pin fixtures, castellated edges, fiducials, board-edge contacts).
    No purchasable component model exists; vendor mechanical drawing is
    the source of truth. See parts-sourcing.md "Mechanical / Vendor-Defined
    Footprints" for the workflow and verification checklist.
```

### Standard-Package Decision Rule (parts2jitx + LCSC workflows)

When using `parts2jitx-lcsc` for a part whose package is in the standard set (`QFN`, `SON`, `DFN`, `SOIC`, `SOT-23`, `SOT-223`, `QFP`, `BGA`), use `parts2jitx-lcsc` for stock / pricing / pinout evidence and **default to the JITX generator** for the landpattern, with dimensions from the datasheet's mechanical drawing.

| LCSC package | Use parts2jitx for | Default landpattern |
|--------------|--------------------|---------------------|
| QFN-* | Stock, pinout, datasheet URL | `QFN(...)` |
| SON-* / DFN-* | Stock, pinout, datasheet URL | `SON(...)` |
| SOIC-* | Stock, pinout, datasheet URL | `SOIC(...)` |
| SOT-23 / SOT-223 | Stock, pinout, datasheet URL | jitxlib standard library |
| QFP-* | Stock, pinout, datasheet URL | `QFP(...)` |
| BGA-* | Stock, pinout, datasheet URL | `BGA(...)` |
| Non-standard (connectors, RF modules, irregular pads) | Stock, pinout, footprint download | KiCad import via `parts2jitx-kicad` |

Why default to the generator: JITX standard generators use datasheet mechanical dimensions and produce reviewable, parameterized code. KiCad-imported footprints carry the importer's quirks, may use non-standard pad shapes, and are harder to audit against the datasheet.

The SOT generator family (`jitxlib.landpatterns.generators.sot`) only exports `SOT23_3`, `SOT23_5`, `SOT23_6`. **There is no `SOT89`, `SOT223`, `SOT583` generator.** For SOT-223 and other thermal-tab packages without a generator, place pads manually at the manufacturer's recommended-footprint coordinates from the datasheet, or import via `parts2jitx-kicad` as below.

**Fall back to KiCad import when the generator can't represent the package.** Some "QFN-like" parts (especially regulators from TI, Micrel, Microchip) have specialty paddle geometry — split paddles, non-standard thermal pad dimensions, asymmetric layouts — that the generic `QFN(...)` / `SON(...)` generator can't express cleanly. When this happens:

1. Try the generator first against the datasheet mechanical drawing.
2. If the generator can't represent the paddle (or the lead layout), import the KiCad footprint via `parts2jitx-kicad` and verify pad-by-pad against the datasheet.
3. Document the reason for falling back in the task acceptance block under `Notes` (e.g. "TPS62903 split thermal paddle not expressible in QFN generator — imported from KiCad and verified against figure 9-1 page 18").

**Getting a .kicad_mod for non-standard packages** (in priority order):
1. **User-provided** — ask if they have a `.kicad_mod` from their KiCad library or manufacturer download
2. **Manufacturer KiCad library** — many vendors (Molex, TE, Amphenol) publish official KiCad footprints
3. **LCSC / EasyEDA footprint ingestion (requires explicit per-project approval)** — using EasyEDA-sourced `.kicad_mod` as the footprint data source needs user opt-in (terms of use). `parts2jitx-lcsc` *lookup/evidence* is implied when LCSC/JLCPCB is the named sourcing channel, but downloading and converting the footprint is the separate, opt-in path. Install `parts2jitx` if not already available, then use:
   ```bash
   pip install parts2jitx
   parts2jitx-lcsc C165948 --footprint -o kicad_footprints/fp.kicad_mod
   parts2jitx-kicad kicad_footprints/fp.kicad_mod --class-name MyPart
   ```
   Ask the user before using LCSC data — commercial users may not want EasyEDA-sourced data in their project.

### Step 3: Generate Component Code

Use this template structure:

```python
"""
{Manufacturer} {MPN} - {Description}

Component definition for the {full description}.
"""

import jitx
from jitx import PadMapping
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column
# Import appropriate landpattern generator:
# from jitxlib.landpatterns.generators.soic import SOIC, SOIC_DEFAULT_LEAD_PROFILE
# from jitxlib.landpatterns.generators.sot import SOT23_3, SOT23_5, SOT23_6, SOTLead, SOTLeadProfile
# from jitxlib.landpatterns.generators.qfn import QFN, QFNLead
# from jitxlib.landpatterns.generators.son import SON, SONLead
# from jitxlib.landpatterns.generators.bga import BGA
from jitxlib.landpatterns.leads import LeadProfile
from jitxlib.landpatterns.package import RectanglePackage


class {ComponentClassName}(jitx.Component):
    """Brief description of the component."""

    mpn = "{MPN}"
    manufacturer = "{Manufacturer}"
    reference_designator_prefix = "U"  # or "Q" for transistors, etc.
    datasheet = "{datasheet_url}"

    # Define ports for each pin
    # Single pins:
    VCC = Port()
    GND = Port()

    # Pin arrays (for many similar pins):
    GPIO = [Port() for _ in range(N)]

    # Landpattern definition
    landpattern = (
        {Generator}(num_leads=N)
        .lead_profile(...)
        .package_body(...)
        # Optional: .thermal_pad(...)
    )

    # Symbol definition — use BARE attribute names (GND, VCC), NEVER self.GND
    # (self does not exist at class scope)
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(...),
            right=PinGroup(...),
        ),
        columns=Column(
            up=PinGroup(...),    # Power pins typically go up
            down=PinGroup(...),  # Ground pins typically go down
        ),
    )

    # For non-standard pin ordering, add explicit mapping in __init__:
    def __init__(self):
        lp = self.landpattern
        self.mappings = [PadMapping({
            self.PIN1: [lp.p[1]],
            self.PIN2: [lp.p[2]],
            # ...
        })]


Device: type[{ComponentClassName}] = {ComponentClassName}
```

## Package-Specific Examples

For complete examples of each package type (SOIC, SOT, SON, QFN, QFP, BGA), including thermal pads,
port arrays, inactive positions, and non-uniform BGA grids, see
[references/package-examples.md](references/package-examples.md). Specifically:

- **SOT family** — only `SOT23_3`, `SOT23_5`, `SOT23_6` are generators. SOT-89, SOT-223, SOT-583 must be built as custom landpatterns.
- **Custom Landpatterns** — for irregular footprints (headphone jacks, barrel connectors, exotic SOT packages). Subclass `jitx.landpattern.Landpattern` and assign `SMDPad`/`THPad`/`NPTHPad` instances positioned with `.at(x, y)`.
- **PadMapping reference** — for the canonical key/value pattern (`Port → Pad | Sequence[Pad]`), multi-pad rails, and thermal-pad bonding.

## Dimension Mapping Reference

| Datasheet Symbol | Description | JITX Parameter |
|-----------------|-------------|----------------|
| D | Package length | `RectanglePackage.length` |
| E | Package width | `RectanglePackage.width` |
| A | Package height | `RectanglePackage.height` (**required keyword arg** — omitting it raises `TypeError: __init__() missing 1 required keyword-only argument: 'height'` at class definition time) |
| E1 / D1 | Lead span | `LeadProfile.span` |
| e | Lead pitch | `LeadProfile.pitch` |
| b | Lead width | `SMDLead.width` / `QFNLead.width` |
| L | Lead length | `SMDLead.length` / `QFNLead.length` |
| D2 / E2 | Thermal pad size | `.thermal_pad(rectangle(E2, D2))` — **E2 is width (X), D2 is height (Y)**. D=along pins, E=across. Do NOT write rectangle(D2, E2). |

## Common Patterns

### Class-Level vs Instance-Level

Ports, landpattern, and symbol defined at **class level** (no `self`). The exception to this is if a parameter is needed at the class initialization time then the definition can be done in the initialization function:

```python
class MyIC(jitx.Component):
    GND = Port()          # class-level: no self
    VCC = Port()

    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(GND),    # bare name, NEVER self.GND
            right=PinGroup(VCC),   # bare name, NEVER self.VCC
        ),
    )
```

Only use `self` inside `__init__` (for PadMapping, multi-unit symbols).

### Toleranced Values

```python
Toleranced.min_max(3.8, 4.0)           # Min-max range (most common)
Toleranced(5.0, 0.1)                    # Nominal ± tolerance
Toleranced.min_typ_max(0.13, 0.18, 0.23)  # Asymmetric
Toleranced.exact(7.0)                   # BSC = Basic
```

### Capacitor dielectric temperature codes

For `Capacitor` parts, the `temperature_coefficient_code` kwarg (note:
`_code` suffix — `temperature_coefficient` alone is wrong) controls the
EIA dielectric class:

| Code | Class | Variation over −55…+125°C | Use case |
|---|---|---|---|
| `"C0G"` / `"NP0"` | Class I | ±30 ppm/°C (negligible) | RC filter time constants, oscillator timing, antenna matching, crystal load caps — anything where capacitance must be stable |
| `"X5R"` | Class II | ±15% over −55…+85°C | General decoupling, less temperature-sensitive |
| `"X7R"` | Class II | ±15% over −55…+125°C | **Implicit default** for the parts DB. Standard bulk decoupling. |
| `"X8R"` | Class II | ±15% over −55…+150°C | High-temp automotive / industrial |
| `"Y5V"` | Class II | +22% / −82% over −30…+85°C | Avoid for analog — silently detunes RF / timing circuits |

For RF, timing, oscillator load caps, and any analog circuit whose value
must be stable over temperature, explicitly request `"C0G"`:

```python
self.c_match = Capacitor(
    capacitance=2.2e-12,
    temperature_coefficient_code="C0G",
    case="0402",
)
```

Without the explicit kwarg, the parts DB defaults to X7R, and a 2.2 pF
RF matching cap may resolve to a part that drifts ±15% over temperature —
detuning antennas, filters, and oscillators with no build-time warning.

### Querying a passive by MPN

For `Resistor` / `Capacitor` / `Inductor`, pass `mpn` and `manufacturer`
as kwargs (the 3.x `database-part(...)` function does not exist in 4.x):

```python
self.r1 = Resistor(mpn="RC0402FR-0710KL", manufacturer="Yageo")
self.c1 = Capacitor(mpn="GRM155R71H103KA88D", manufacturer="Murata")
```

The 4.x parts DB does **not** have 1-to-1 coverage of the 3.x OCDB. An
MPN that resolved fine in Stanza can return zero hits in 4.x:

```
ValueError: No components meeting requirements:
  {'category': 'inductor', 'mpn': 'IHLP2525CZER4R7M11',
   'manufacturer': 'Vishay'}
```

There is no user-visible pattern to which MPNs resolve and which don't.
**Fallback for non-critical parts**: drop the MPN and query by value
instead — the DB usually has *some* matching part:

```python
self.L = Inductor(inductance=4.7e-6)   # part DB picks any matching SKU
```

For non-passives (crystals, encoders, connectors, mechanical parts),
**there is no MPN-lookup path** *for the OCDB connector / mechanical
library* — `jitxlib.connectors` / `jitx.ocdb` do not exist. But the
generic `Part(mpn=…)` lookup against the parts DB **does** resolve
many connector / IC MPNs; see the caveats below before using it.
For irregular pad arrangements (USB-C receptacles, audio jacks, edge
connectors), use the custom `Landpattern` + `Pad.at()` pattern in
`references/package-examples.md` §"Custom Landpatterns".

#### Parts DB caveats (jitxlib-parts 1.1.0a0, as of 2026-05-14)

**Some MPNs hit resolver bugs even though they're in the DB.** Known
examples:

| MPN | Manufacturer | Error |
|---|---|---|
| `UCD1V331MNL1GS` | Nichicon (polymer cap) | `'CapacitorSymbol' object has no attribute 'a'` |
| `LQG15WZ2N0C02D` | Murata (RF inductor) | `KeyError: 'max_current'` in `build_two_pin_mappings` |
| `WPN4020H6R8MT` | Sunlord (inductor) | `KeyError: 'max_current'` (same) |

Workaround: drop the MPN and query by value — `Capacitor(capacitance=22e-6)`,
`Inductor(inductance=2.0e-9, case="0402")`. If the design requires a
specific MPN for compliance, file a `jitxlib-parts` bug rather than
working around it in user code.

**Cross-ref**: for value-side issues — computed values that don't
match an E-series step, or sub-nH RF inductors that fail the default
case constraint — see
`jitx-skills:jitx-circuit-builder` §"Snap computed values to a
standard E-series" and §"Relaxing query defaults for outsize parts".

**Don't pass redundant value kwargs alongside `mpn=`.** The Python
parts DB treats every kwarg as an AND filter — unlike Stanza, where
`database-part(["mpn" => …])` is keyed only on MPN and ignores other
fields. If you pass `Inductor(mpn="WPN4020H6R8MT", inductance=l_value)`
with a computed `l_value` that doesn't match the part's actual 6.8 µH,
the query fails with "No components meeting requirements" and no
hint that the `inductance` kwarg is the conflicting field. **Rule**:
when using `mpn=` on `Resistor` / `Capacitor` / `Inductor`, omit the
`value` / `capacitance` / `inductance` / `resistance` argument. The
MPN is the unique key.

**`manufacturer=` is fuzzy-matched** (case-insensitive substring).
`Part(mpn="AS78L05RTR-E1", manufacturer="Diodes Inc.")` resolves
cleanly even though the stored manufacturer is `"DIODES INCORPORATED"`.
The query succeeds; the resolved metadata reads the canonical name.
Don't assume exact-match semantics when comparing the input string
to the resolved part's manufacturer field.

#### Port access on parts-DB-resolved components

Port-access convention depends on **how the part was sourced**, not
on what kind of part it is. Three distinct conventions:

| Component source | Port access |
|---|---|
| `Resistor(resistance=…)` / `Capacitor(capacitance=…)` / `Inductor(inductance=…)` from `jitxlib.parts` | `.p1`, `.p2` |
| `Part(mpn="…")` whose physical layout is a generic SMD package (speaker terminal, pushbutton, generic 2-pin) | `.p[1]`, `.p[2]`, … (port array, 1-indexed) |
| `Part(mpn="…")` whose pin-properties names pads (connectors, ICs, encoders) | flat names — `.SDA`, `.VBUS0`, `.GND0`, etc. |

Examples:

```python
# (a) jitxlib.parts.Capacitor — .p1 / .p2
self.c = Capacitor(capacitance=100e-9, case="0402")
self.net_a = self.ic.VCC + self.c.p1
self.net_b = self.ic.GND + self.c.p2

# (b) Part(mpn=…) generic 2-pin / 4-pin — .p[N]
self.spk = Part(mpn="DB128L-5.08-2P-BK-S", manufacturer="DIBO")
self.spk_p = self.stereo.out_a_p + self.spk.p[1]
self.btn = Part(mpn="SKRPADE010", manufacturer="ALPSALPINE")
self.net_a = self.btn.p[1] + self.btn.p[3]   # pushbutton across-pole

# (c) Part(mpn=…) with named pins — flat attribute names
self.usbc = Part(mpn="TYPE-C-31-M-12")
self.usb_dn = self.usbc.DN1 + self.usbc.DN2 + my_usb2.data.n
self.usb_dp = self.usbc.DP1 + self.usbc.DP2 + my_usb2.data.p
self.vbus  = self.usbc.VBUS0 + self.usbc.VBUS1 + self.usbc.VBUS2 + self.usbc.VBUS3
self.gnd   = self.usbc.GND0  + self.usbc.GND1  + self.usbc.GND2  + self.usbc.GND3
```

`Part(mpn=…).p1` raises `AttributeError`; use `.p[1]`. The structural
bundle types (`USB_C_Connector`, etc.) are for **user-defined**
`Component` classes that *choose* to expose a bundle interface — not
for parts-DB-sourced connectors. To net a parts-DB Type-C to a
`USB_2()` bundle elsewhere, wire per-pad as shown.

#### pyright caveat on `Part(mpn=…).<port>`

Every `Part(mpn=…).<port>` access raises
`reportAttributeAccessIssue` ("Cannot access attribute "<NAME>" for
class "Part""). This is **inherent** — port names come from the
parts DB at runtime, so pyright has no way to know what ports the
resolved class will expose. The pd_audio porting session
encountered 54 such errors out of 58 total pyright errors after the
first build smoke-test; this is the dominant class of pyright noise
on any design that uses parts-DB connectors / encoders / ICs.

Two correct ways forward:

1. **Accept the errors and filter when triaging real type errors:**
   ```bash
   pyright src/ 2>&1 | grep -E 'error:' | grep -v 'for class "Part"'
   ```

2. **Wrap the part in a custom `Component` subclass** with declared
   `Port`s and explicit `PadMapping`. More work, but yields pyright-
   clean access. Choose this when the design requires CI gating on
   pyright errors.

The `jitx-port-3-to-4` workflow's "treat any pyright error as
blocking" rule **does not apply** to this class of error.

### Thermal Pad with Paste Subdivision

```python
from jitx.shapes.composites import rectangle
from jitxlib.landpatterns.pads import SMDPadConfig, WindowSubdivide

.thermal_pad(
    shape=rectangle(3.0, 3.0),
    config=SMDPadConfig(paste=WindowSubdivide(padding=0.25)),
)
```

### Reference Designator Prefixes

- `U` - Integrated circuits
- `Q` - Transistors (typically BJTs)
- `D` - Diodes (LEDs)
- `R` - Resistors
- `C` - Capacitors
- `L` - Inductors
- `J` - Connectors
- `Y` or `X`- Crystals/oscillators
- `FB` - Ferrite beads
- `T` - Transformers

## Multi-Unit Symbols

Multiple `BoxSymbol` attributes = separate visual boxes:

```python
def __init__(self):
    self.symbol_a = BoxSymbol(rows=Row(
        left=PinGroup(self.INp[0], self.INn[0]),
        right=PinGroup(self.OUT[0]),
    ))
    self.symbol_b = BoxSymbol(rows=Row(
        left=PinGroup(self.INp[1], self.INn[1]),
        right=PinGroup(self.OUT[1]),
    ))
    # Power unit: use horizontal layout (left=supplies, right=grounds)
    self.symbol_power = BoxSymbol(
        rows=Row(
            left=PinGroup(self.VCC, self.VBAT),
            right=PinGroup(self.VSS, self.GND),
        ),
    )
```

## Pin Naming Best Practices

**Every physical pin/ball MUST have a Port().** Never use "representative samples" — a 142-ball
BGA needs exactly 142 Port() declarations. Enumerate every pin from the datasheet pin table or
ball map row by row. NC (no-connect) pins with physical pads also need ports. 

**One Port per physical pin** — if a ball has a primary name and alternate functions
(SPI_CLK, UART_TX, etc.), create ONE port using the datasheet's primary pin name. Do not create
separate ports for each alternate function of the same physical ball.
Also for Ports that have incrementing numbers in the name, use an indexed Port name instead (GND1, GND2, GND3 -> GND[1 through 3])

**Use real functional names from the datasheet**, not generic placeholders:

```python
# GOOD - from datasheet
OQSPIF_D0 = Port()   # Octal QSPI Flash data bit 0
eMMC_CMD = Port()    # eMMC command line
V18F = Port()        # 1.8V flash supply

# BAD - generic
P0 = Port()          # What does P0 do?
VDD1 = Port()        # Which power domain?
```

## Non-Contiguous Pin Index Sets — Use `dict[int, Port]`

When the device's pin index space is **non-contiguous** (e.g. ESP32-S3 GPIOs 0-14,
17-21, 33-38, 45, 46 — gaps at 15, 16, 22-32, 39-44), a plain `list[Port]` will
collide with the physical pin numbering. Use a `dict[int, Port]` so the index keys
preserve the datasheet's semantic numbering:

```python
class ESP32_S3(jitx.Component):
    # WRONG — list index 15 is unused but still exists, and GPIO38 would map to
    # whatever the 22nd element happens to be:
    # GPIO = [Port() for _ in range(40)]

    # CORRECT — dict keys = datasheet GPIO numbers:
    GPIO: dict[int, Port] = {
        i: Port()
        for i in list(range(15)) + list(range(17, 22)) + list(range(33, 39)) + [45, 46]
    }
    # Access: self.GPIO[38] always refers to physical GPIO38.
```

Unpack into a `BoxSymbol` `PinGroup` with `*GPIO.values()`. The same rule applies to
`PadMapping` when the pad index set is non-contiguous. See the construct-map
(`jitx-port-3-to-4` §3) for the parallel port-on-`Circuit` pattern.

## Marking a Component as Do-Not-Populate (DNP)

There is no `dnp=True` kwarg. Subclass `NonPopulatedComponent` (defined in
`jitx/component.py`), or set `in_bom = False; soldered = False` on a regular
`Component` subclass. **Import from `jitx.component`** — on jitx 4.0.5 the class
is defined at `jitx/component.py:150` but is NOT re-exported from
`jitx/__init__.py`, so `from jitx import NonPopulatedComponent` raises ImportError:

```python
from jitx.component import NonPopulatedComponent

class CFG1Pulldown(NonPopulatedComponent, Resistor):
    pass

# Usage in the parent Circuit:
self.r_cfg1 = CFG1Pulldown(resistance=6.8e3)
```

For ad-hoc, one-off DNP on a query-API passive, set `in_bom` / `soldered`
directly on the instance:

```python
self.c_filter = Capacitor(capacitance=10.0e-12, case="0402")
self.c_filter.in_bom   = False
self.c_filter.soldered = False
```

There is no convenience `.dnp = True` flag — the authoritative fields are
`in_bom: bool | None` and `soldered: bool | None` on `jitx.Component`
(`py-jitx/src/jitx/component.py:93,98`). When the DNP intent is reusable
(same DNP-marked part used in several places), prefer the
`NonPopulatedComponent` subclass or class-level `in_bom = False;
soldered = False` over instance-level override. See
`jitx-circuit-builder/SKILL.md` §"DNP / do-not-populate" for the three
patterns side-by-side.

## Landpattern Constructor Signatures

Do NOT invent constructor parameters — use only these documented signatures:

```python
# SOT — SOTLeadProfile takes ONLY span, nothing else
SOTLeadProfile(span=Toleranced.min_max(2.3, 2.5))

# LeadProfile — used for SOIC, SON, QFN
LeadProfile(
    span=Toleranced.min_max(5.8, 6.2),   # terminal-to-terminal
    pitch=1.27,                            # center-to-center lead spacing
    type=SONLead(length=..., width=...),   # or SMDLead, QFNLead
)

# SON — use .lead_profile() method chain, NOT .lead()
SON(num_leads=8).lead_profile(LeadProfile(span=..., pitch=..., type=SONLead(...)))

# QFP — uses LeadProfile with QFPLead (BigGullWingLeads)
QFP(num_leads=48).lead_profile(LeadProfile(span=..., pitch=0.5, type=QFPLead(...)))
# For asymmetric pin counts: QFP(num_rows=(left, bottom, right, top))
# For asymmetric lead spans: .lead_profile(x_profile, y_profile)

# BGA — constructor takes these 4 args
BGA(num_rows=12, num_cols=12, pitch=0.45, ball_diameter=0.25)
# then chain: .grid_planner(...).pad_config(SMDPadConfig()).package_body(...)
```

> ⚠️ **`.pad_config(SMDPadConfig())` is mandatory on every BGA.** There is no
> built-in default. Omitting the call produces a build error
> `No pad configuration specified` (see Common Build Errors). For BGAs with
> depopulated balls, also chain `.grid_planner(...)` — see
> [references/package-examples.md](references/package-examples.md) Example 6 for the
> `GridPlanner` subclass pattern, and §"Depopulated / non-uniform balls".

### Symbol pin direction — `.up()` / `.down()` / `.right()` / `.left()` are method calls

`Pin.up`, `Pin.down`, `Pin.right`, `Pin.left` look like enum values but
are **method calls** that return configured `Pin` instances:

```python
# WRONG — treats .up as an enum:
GND = Pin(direction=Pin.down, position=(0, -2), length=1)
# AttributeError or silent miswiring

# RIGHT — call the method:
GND = Pin.down((0, -2), length=1)
VCC = Pin.up((0, 2), length=1)
```

Easy to mistype when porting from any source that treats direction as a
property rather than a constructor.

### Port at hierarchy boundaries — use plain `Port()`, not protocol bundles

When a `Component` or `Circuit` exposes a port to its **parent** (i.e. a
boundary that crosses the hierarchy, not an intra-circuit wire), declare
it as a plain `Port()`, not as a protocol bundle (`USB2()`, `I2C()`,
`I2S()`, etc.):

```python
# WRONG — nested sub-ports of a protocol bundle break at the boundary:
class PowerSupplies(Circuit):
    usb = USB2()
# Parent wiring:
self.power.usb.data.p += self.usb_conn.DP1   # silently fails or raises NotImplementedError

# RIGHT — plain Port() works at any boundary:
class PowerSupplies(Circuit):
    usb_dp = Port()
    usb_dn = Port()
# Parent wiring:
self.dp_net = self.power.usb_dp + self.usb_conn.DP1
```

Protocol bundles are for **intra-circuit** wiring — connecting two ports
within the same `Circuit.__init__`. For cross-hierarchy interface ports,
use plain `Port()` and bind into bundles via `provide`/`require` in
the calling circuit (see `jitx-pin-assignment`).

### Pad rotation — `at(x, y, rotate=θ)`, keyword-only

Stanza pad-placement (`pad p[1] : my-pad at loc(x, y, θ)`) is common in
hand-coded `pcb-landpattern` blocks and OCDB-generated component files.
The Python `Pad.at` signature is `at(self, x, y, /, *, rotate=0, on=Side.Top)`
— **`rotate` is keyword-only**. Two natural mis-translations to avoid:

```python
class _LP(Landpattern):
    p1 = _RectPad(0.28, 0.68).at(0.640, -0.750, 90.0)   # FAILS
    # TypeError: Positionable.at() takes from 2 to 3 positional arguments but 4 were given

    p2 = _RectPad(0.28, 0.68).at(0.640, -0.250).rotate(90.0)   # FAILS
    # AttributeError: 'Pad' has no attribute 'rotate'
    # (pyright catches this one before runtime)

    p3 = _RectPad(0.28, 0.68).at(0.640, 0.250, rotate=90.0)   # CORRECT
```

There is no `Pad.rotate(...)` method. The only rotation form is the
keyword arg on `.at()`.

### `.narrow()` vs `.package_body()` for SOIC

SOIC provides a convenience method `.narrow(length)` that sets the package body to the standard SOIC narrow width (3.9mm) with a given length:

```python
# .narrow() — shorthand for narrow-body SOIC (3.9mm width)
SOIC(num_leads=8).lead_profile(SOIC_DEFAULT_LEAD_PROFILE).narrow(Toleranced.min_max(4.81, 5.0))

# Equivalent explicit form using .package_body()
SOIC(num_leads=8).lead_profile(SOIC_DEFAULT_LEAD_PROFILE).package_body(
    RectanglePackage(
        width=Toleranced.exact(3.9),
        length=Toleranced.min_max(4.81, 5.0),
        height=Toleranced.min_max(1.35, 1.75),   # required kwarg — see Dimension Mapping
    )
)
```

Use `.narrow()` for standard narrow-body SOICs. Use `.package_body()` for wide-body SOICs or when specifying all three dimensions (width, length, height).

## PadMapping Requirements

- **Automatic mapping (no PadMapping needed):** Ports mapped to pads in declaration order.
- **Explicit PadMapping required when:**
  - Thermal pad exists (map to `lp.thermal_pads[0]`)
  - Ports declared out of pin order
  - Multiple ports map to same pad
  - Pin 1 is not the first declared port

### Every Port must appear in a PadMapping

When you declare an explicit `PadMapping`, **every `Port` on the
`Component` subclass must appear as a key** — even if it's a
no-connect. `.no_connect()` does **not** satisfy this requirement:
no-connect is for ports that ARE wired to pads but should be
reported as unconnected on the netlist. Calling `.no_connect()` on
a Port that has no pad in the mapping still produces:

```
translation failed:
  <package.Component>'s port <NAME> is not mapped to a pad
```

If a Stanza `pin-properties` entry refers to a pad index that the
4.x landpattern doesn't expose (e.g. a center "case" pad on a
generator that doesn't expose it, or the Stanza-style "pad 0" /
"pad N+1" entry for a thermal pad — see the §"Stanza-pin-number
trap" in `jitx-port-3-to-4/references/pitfalls.md` and §"Stanza-
pin-number trap" in `jitx-port-3-to-4/references/construct-map.md`),
**delete the `Port` from the Component definition** rather than
declaring it. Let the parent Circuit handle case grounding manually
if needed.

### Multi-domain grounds — do not consolidate DGND / AGND / PGND / EP

When the datasheet pin table names **distinct ground domains** (DGND,
AGND, PGND, GND_SUB, GND_AUX, etc.), expose them as **separate ports**
on the `Component`. Do not collapse them into a single `GND` port even
though they are board-tied at the top level.

```python
# ✓ Separate ports — each ground domain gets its own bypass-cap return path.
class TAS5825M(jitx.Component):
    DGND = Port()
    AGND = Port()
    PGND = [Port() for _ in range(4)]   # four power-stage grounds
    EP = Port()                         # exposed pad
    # ... mapped distinctly in PadMapping
```

```python
# ❌ Consolidated GND — every bypass cap routes through the same node,
#    defeating the chip's star-ground topology and producing audible
#    crosstalk on class-D outputs.
class TAS5825M(jitx.Component):
    GND = Port()
```

**Rationale.** Per-domain bypass caps return current through the
corresponding ground pin, which controls EMI and audio noise. The chip
designer chose distinct DGND / AGND / PGND pins specifically so the
high-current power-stage return current does not mix with the
analog-reference return current inside the package. Consolidating at
the Component level forces every bypass cap to wire through the same
global GND, defeating that topology before it reaches the board.

**Signal in the Stanza source.** A Stanza `pin-properties` table with
separate rows for `[DGND | ...]`, `[AGND | ...]`, `[PGND | ...]` is
the explicit cue — preserve the separation. The decision is the same
when the Stanza source consolidates (some legacy 3.x sources do): the
datasheet pin table is authoritative, not the Stanza model.

The consumer `Circuit` ties everything to the board GND at the top
level (`encore/circuits/audio/amp.py`):

```python
self.GND += (
    self.gnd
    + self.amp.DGND
    + self.amp.AGND
    + self.amp.PGND[0] + self.amp.PGND[1]
    + self.amp.PGND[2] + self.amp.PGND[3]
    + self.amp.EP
)
# But per-domain bypass caps wire to the matching domain, not the merged GND:
self.c_mid_pvdd.insert(self.amp.PVDD[0], self.amp.PGND[0], short_trace=True)
self.c_avdd_hf.insert(self.amp.AVDD,    self.amp.AGND,    short_trace=True)
self.c_dvdd_hf.insert(self.amp.DVDD,    self.amp.DGND,    short_trace=True)
```

### PadMapping value side — Landpattern attribute-name conventions

The **value** side of a `PadMapping` entry uses whichever attribute
convention the landpattern source dictates — not a free choice:

| Landpattern source | Pad reference |
|---|---|
| `SOIC` / `SON` / `QFN` / `SOT` / `BGA` (jitxlib generators) | `lp.p[N]` array, **1-indexed** |
| BGA with alpha-row naming | `lp.A[1]`, `lp.B[2]`, … |
| Custom `Landpattern` subclass with attribute-named pads (e.g. `p1 = SMDPad(...)`) | `lp.p1`, `lp.p2`, `lp.<your_name>` |
| Thermal pad on any generator | `lp.thermal_pads[N]`, **zero-indexed** |

Mixing conventions within the same `Component` is fine — they're
different namespaces — but **the natural Stanza-style translation
`p1 = SMDPad(...)` only works for custom Landpatterns**. On a
generator-derived Landpattern (`SOIC(num_leads=10)...`),
`lp.p1` raises `AttributeError: 'SOIC' object has no attribute 'p1'`.
Use `lp.p[1]` there.

See `references/package-examples.md` §"Custom Landpatterns" for the
attribute-named-pads pattern; the SOIC/QFN examples in §"Package-
Specific Examples" above show the `lp.p[N]` form.

### No `PadType` enum in 4.x

Stanza pads carry an explicit `type = SMD` directive:

```stanza
pcb-pad rectangle-smd-pad :
  name = "rectangle-smd-pad"
  type = SMD                          ; ← Stanza form
  shape = Rectangle(0.280, 0.680)
  layer(SolderMask(Top)) = Rectangle(0.382, 0.782)
  layer(Paste(Top)) = Rectangle(0.280, 0.680)
```

There is **no `PadType` enum in 4.x**. A `Pad` subclass is SMD by
default; if it contains a `jitx.feature.Cutout` instance, the build
reclassifies it as through-hole. Don't transcribe `type = SMD`
verbatim — `jitx.PadType` does not exist and the import fails with
`AttributeError`.

Solder-mask and paste-stencil overrides translate to attribute
declarations on the `Pad` subclass instance, not class-level
`layer(...)` calls:

```python
from jitx.landpattern import Pad, SMDPad, Soldermask, Paste
from jitx.shapes.composites import rectangle

class _RectangleSMDPad(Pad):
    shape = rectangle(0.280, 0.680)
    def __init__(self) -> None:
        self.soldermask = Soldermask(rectangle(0.382, 0.782))
        self.paste = Paste(rectangle(0.280, 0.680))
```

If the Stanza source only declares mask/paste overrides that are
within the default expansion ratio, you can drop them entirely and
rely on the default — review with the design owner before doing so.

## Verification Process

### Step 4: Test Harness

```python
import jitx
from jitx.container import inline
from jitx.sample import SampleDesign

from .component import Device


class TestDesign(SampleDesign):
    @inline
    class circuit(jitx.Circuit):
        dut = Device()
```

### Build Command

Always use the available virtual environment. If one is not present, stop and ask.
```bash
python -m jitx build <module>.TestDesign
```

Don't run parallel JITX builds against the same project — sequence them. See `jitx/SKILL.md` "Build Safety".

**Success:** `status: ok`
**Failure:** Python traceback or `status: error`

**Output files** (in `designs/<design_name>/`):
- `cache/netlist.json` - Verify net connections
- `design-info/stable.design` - Design snapshot

### Common Build Errors

| Error | Fix |
|-------|-----|
| `port X not mapped to symbol pin` | Add port to BoxSymbol |
| `port X not mapped to pad` | Check port count = pad count |
| `No pad configuration specified` | BGA needs `.pad_config(SMDPadConfig())` |

### Verification Report

Emit the **task acceptance block** from `jitx/references/completion-blocks.md` "Task Acceptance Block". For a component task, the block's `Primary source` field cites the datasheet pages with the pinout and mechanical drawing; the `Footprint source` field names the JITX generator used (or KiCad import with reason); the `Checks run` field includes the Component checklist from `domain-checklists.md` with N/N items and any issues fixed (pin count vs datasheet, pad count vs landpattern, dimensions vs datasheet mechanical drawing). The acceptance block is the report; do not invent a parallel format.

## Step 5: Capture Application Circuit

**In the project-builder (complete-board) workflow, this step is MANDATORY — not optional.** The application circuit from the datasheet is the foundation for the downstream circuit task; capture it now while the datasheet is open.

In single-task tier (user invoked component-modeler standalone), this step is optional — ask the user.

After generating component code, check the datasheet for "Typical Application", "Reference Design", or "Application Circuit" sections. These provide valuable circuit templates.

**Process (complete-board):**

1. Capture the application circuit without asking. Extract the relevant datasheet figure (use `extract_pages.py`) and invoke `jitx-circuit-builder` to generate the circuit code.

**Process (single-task):**

1. **Ask user** whether to capture the application circuit:
   ```
   "The datasheet includes a Typical Application circuit (Figure X).
   Would you like me to also generate the application circuit code?"
   ```

2. **If yes**, invoke the `jitx-circuit-builder` skill to generate circuit code

3. **Pass context** to circuit-builder:
   - Component class name and import path
   - Datasheet figure reference
   - Component values from schematic (cap values, resistor values, inductor specs)
   - Pin connections shown in the schematic

**Example application circuit output:**

```python
"""
Texas Instruments TPS62933DRLR Application Circuit
From datasheet Figure 23 - Typical Application

3.8-V to 30-V input, 3.3V 3A output buck converter.
"""

from jitx import Circuit, Net
from jitx.toleranced import Toleranced
from jitx.common import Power
from jitxlib.parts import Capacitor, CapacitorQuery, Resistor, Inductor, ResistorQuery
from jitxlib.voltage_divider import VoltageDividerConstraints, voltage_divider_from_constraints

from .texas_instruments_TPS62933DRLR import TPS62933DRLR


class TPS62933DRLRCircuit(Circuit):
    """Buck converter application circuit per datasheet Figure 23."""

    vin = Power()   # Input power (3.8V-30V)
    vout = Power()  # Output power (3.3V)

    def __init__(self, output_voltage=3.3):
        self.GND = Net(name="GND")
        self.VOUT = Net(name="VOUT")
        self.VIN = Net(name="VIN")

        # Main IC
        self.buck = TPS62933DRLR()

        # Power connections
        self.VIN += self.vin.Vp + self.buck.VIN
        self.GND += self.buck.GND + self.vin.Vn + self.vout.Vn

        # Input capacitors (C1, C2 - 10µF each per schematic)
        with CapacitorQuery.refine(type="ceramic", case="0805"):
            self.c_in1 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
            self.c_in1.insert(self.buck.VIN, self.GND, short_trace=True)

            self.c_in2 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
            self.c_in2.insert(self.buck.VIN, self.GND, short_trace=True)

        # Feedback voltage divider
        vdiv_cons = VoltageDividerConstraints(
            v_in=Toleranced.exact(output_voltage),
            v_out=Toleranced.percent(0.8, 3.0),  # MUST have tolerance window
            current=0.8 / 10e3,
            prec_series=[1.00, 0.10],             # REQUIRED
            base_query=ResistorQuery(case=["0402"]),
        )
        self.fb_div = voltage_divider_from_constraints(vdiv_cons, name="feedback")
        self.VOUT += self.fb_div.hi + self.vout.Vp
        self.GND += self.fb_div.lo
        self.nets = [self.fb_div.out + self.buck.FB]

        # Output inductor and capacitors
        self.L = Inductor(inductance=4.7e-6, current_rating=3.9)
        # ... complete circuit per datasheet
```

**File location:** Save application circuits alongside the component:
```
components/
├── power_switchmode/
│   ├── texas_instruments_TPS62933DRLR.py      # Component
│   └── texas_instruments_TPS62933DRLR_circuit.py  # Application circuit
```

## Output Format

When generating a component, provide:

1. Complete Python source code in a code block
2. Verification report (using format above)
3. Any assumptions or decisions made
4. Known limitations or items requiring manual review
5. **Offer to capture application circuit** if datasheet includes one
