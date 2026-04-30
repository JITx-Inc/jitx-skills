---
name: jitx-component-modeler
description: Create JITX Python component code from datasheets, KiCad footprints, or user specifications. ALWAYS use this skill when user asks to "create a component", "model a part", "generate a component", "add a component", or "make a JITX component" - even without a datasheet. Also triggers on part numbers (NE555, LM1117, RP2040, etc.) and package types (SOIC, QFN, BGA, SON, SOT). Supports user-provided data, JITX generators for standard packages, and optional LCSC/EasyEDA fallback for non-standard footprints. Supports multi-unit symbols, thermal pads, and complex pin mappings.
---

# JITX Component Generation Skill

Generate JITX Python component code from datasheets, user-provided KiCad footprints, or specifications. Data can come from multiple sources — always prefer user-provided data over automated lookups.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

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

Once the datasheet PDF is available, extract pinout, package dimensions, and pin descriptions from it using Step 0. Do NOT search for info that's already in the datasheet.

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
```

**Getting a .kicad_mod for non-standard packages** (in priority order):
1. **User-provided** — ask if they have a `.kicad_mod` from their KiCad library or manufacturer download
2. **Manufacturer KiCad library** — many vendors (Molex, TE, Amphenol) publish official KiCad footprints
3. **LCSC/EasyEDA fallback (opt-in only)** — only if user explicitly approves this data source. Install `parts2jitx` if not already available, then use:
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
[references/package-examples.md](references/package-examples.md).

## Dimension Mapping Reference

| Datasheet Symbol | Description | JITX Parameter |
|-----------------|-------------|----------------|
| D | Package length | `RectanglePackage.length` |
| E | Package width | `RectanglePackage.width` |
| A | Package height | `RectanglePackage.height` |
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

### `.narrow()` vs `.package_body()` for SOIC

SOIC provides a convenience method `.narrow(length)` that sets the package body to the standard SOIC narrow width (3.9mm) with a given length:

```python
# .narrow() — shorthand for narrow-body SOIC (3.9mm width)
SOIC(num_leads=8).lead_profile(SOIC_DEFAULT_LEAD_PROFILE).narrow(Toleranced.min_max(4.81, 5.0))

# Equivalent explicit form using .package_body()
SOIC(num_leads=8).lead_profile(SOIC_DEFAULT_LEAD_PROFILE).package_body(
    RectanglePackage(width=Toleranced.exact(3.9), length=Toleranced.min_max(4.81, 5.0))
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

After generating code, provide:

```
## Verification Report

### Pin Count
- Datasheet: N pins
- Generated: N ports
- Status: ✓ MATCH / ✗ MISMATCH

### Pad Count
- Landpattern: N pads + M thermal
- Ports requiring pads: N + M
- Status: ✓ MATCH / ✗ MISMATCH

### Dimensions
| Parameter | Datasheet | Generated | Status |
|-----------|-----------|-----------|--------|
| Width     | 3.8-4.0mm | min_max(3.8, 4.0) | ✓ |

### Issues Found
- [List any discrepancies or assumptions made]
```

## Step 5: Capture Application Circuit

**In the project builder workflow, this step is MANDATORY — not optional.** The application circuit from the datasheet is the foundation for the circuit task. Always capture it.

After generating component code, check the datasheet for "Typical Application", "Reference Design", or "Application Circuit" sections. These provide valuable circuit templates.

**When to offer:**
- Datasheet includes a schematic with the component
- User is creating a power IC, amplifier, or other circuit-centric component
- Application circuit shows passive values and connections

**Process:**

1. **Ask user** if they want to capture the application circuit:
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
