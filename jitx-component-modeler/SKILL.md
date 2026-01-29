---
name: jitx-component-modeler
description: Generate JITX Python component code from datasheets. Use when user provides a datasheet PDF and asks to create a JITX component, model a part, or add a component to a JITX project. Supports BGA, QFN, SOIC, SON, SOT packages with multi-unit symbols, thermal pads, and complex pin mappings. Handles single components or batch component creation with proper folder organization.
---

# JITX Component Modeler

Generate JITX Python component definitions from datasheets.

## Environment Setup

Before generating components, verify JITX environment:

```bash
# Must have Python 3.12+, venv active, jitx installed
python --version
which python | grep -q ".venv" || echo "WARNING: activate venv first"
python -c "import jitx" || echo "ERROR: jitx not installed"
```

**Fix issues:**
1. `source .venv/bin/activate`
2. `pip install -e .`

**Recommended:** Install pyright for type checking:
```bash
claude plugin install pyright-lsp@claude-plugins-official
pip install pyright
```

## Workflow Overview

1. **Gather information** - Extract from datasheet or ask user
2. **Determine output location** - Single file or components folder
3. **Select package generator** - BGA, QFN, SOIC, SON, SOT
4. **Generate component code** - Ports, landpattern, symbol
5. **Verify build** - Run `python -m jitx build`

## Finding Component Information

**ONLY use reputable sources for datasheets and package drawings:**

**Manufacturer websites (preferred):**
- Texas Instruments: ti.com
- Analog Devices: analog.com
- Renesas: renesas.com
- STMicroelectronics: st.com
- NXP: nxp.com
- Microchip: microchip.com
- Infineon: infineon.com
- onsemi: onsemi.com
- Raspberry Pi: raspberrypi.com/documentation

**Authorized distributors:**
- Digi-Key: digikey.com
- Mouser: mouser.com
- Arrow: arrow.com
- Newark/Farnell: newark.com, farnell.com

**AVOID:** Random component sites, manual aggregators, or unverified PDFs. These often have incorrect/outdated pinouts, wrong dimensions, or missing pages.

**When searching:** Use `"<MPN> datasheet" site:<manufacturer>.com` or check distributor product pages which link to official datasheets.

## Output Location

### Single Component
Place in project root or current directory:
```
project/
└── <manufacturer>_<mpn>.py
```

### Multiple Components (Default Structure)
Use py-components structure when creating multiple components or user requests organized layout:
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

**Category examples:** mcus, connectors, power_linear_regulators, opamp, flash, crystals, leds, logic, timers, buttons, transceivers, diodes_tvs, isolators, power_switchmode

**File naming:** `<manufacturer>_<mpn>.py` - lowercase, underscores for spaces/special chars
- `texas_instruments_NE555.py`
- `raspberry_pi_RP2040.py`
- `renesas_DA14705.py`

### Customization
Ask user if they want different:
- Namespace (default: project name or `components`)
- Category organization (flat vs categorized)
- File naming convention

## Large Datasheet Handling

For datasheets >2MB or >100 pages, extract relevant pages first:

```bash
# Find relevant pages
python scripts/extract_pages.py datasheet.pdf --find "pinout" "dimension" "package" "ball"

# Extract to smaller PDF
python scripts/extract_pages.py datasheet.pdf --pages 42 43 1020 -o datasheet_package.pdf
```

Key pages: pinout diagram, pin description table, package mechanical drawing, ordering info.

If extraction unavailable, ask user for: pin count, package type, pin names, package dimensions.

## Package Selection

```
2-sided package?
├── Yes, ≤6 pins → SOT23_3, SOT23_5, SOT23_6
├── Yes, >6 pins gull-wing → SOIC
├── Yes, >6 pins no-lead → SON
└── No (4-sided/array)
    ├── 4-sided gull-wing → QFP
    ├── 4-sided no-lead → QFN
    ├── Ball array → BGA
    └── Custom → Manual Landpattern
```

## Component Template

```python
"""
{Manufacturer} {MPN} - {Description}
"""

import jitx
from jitx import PadMapping
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column
from jitxlib.landpatterns.package import RectanglePackage
# Import generator: SOIC, QFN, SON, BGA, SOT23_*


class {ClassName}(jitx.Component):
    mpn = "{MPN}"
    manufacturer = "{Manufacturer}"
    reference_designator_prefix = "U"  # U=IC, Q=transistor, D=diode
    datasheet = "{url}"

    # Ports
    VCC = Port()
    GND = Port()

    # Landpattern
    landpattern = (
        {Generator}(...)
        .lead_profile(...)
        .package_body(RectanglePackage(...))
    )

    # Symbol
    symbol = BoxSymbol(
        rows=Row(left=PinGroup(...), right=PinGroup(...)),
        columns=Column(up=PinGroup(...), down=PinGroup(...)),
    )


Device: type[{ClassName}] = {ClassName}
```

## BGA Handling

### Standard BGA
```python
from jitxlib.landpatterns.generators.bga import BGA
from jitxlib.landpatterns.pads import SMDPadConfig

landpattern = (
    BGA(num_rows=12, num_cols=12, pitch=0.45, ball_diameter=0.25)
    .pad_config(SMDPadConfig())  # Required!
    .package_body(RectanglePackage(...))
)
```

### Inactive Positions (NC/Depopulated)
```python
from jitxlib.landpatterns.grid_planner import GridPlanner
from jitxlib.landpatterns.grid_layout import GridPosition

class NCPlanner(GridPlanner):
    NC_POSITIONS = {(8, 9), (8, 10), ...}  # 0-indexed (row, col)

    def is_active(self, pos: GridPosition, num_rows: int, num_cols: int) -> bool | None:
        return False if (pos.row, pos.column) in self.NC_POSITIONS else None

landpattern = BGA(...).grid_planner(NCPlanner())
```

### Non-Uniform BGA (CRITICAL)
Some BGAs have balls NOT on regular grid. Check mechanical drawing for:
- Different pitch in some regions
- Offset ball groups
- Split grids

**Pattern:**
```python
from jitxlib.landpatterns.generators.bga import BGADecorated  # NOT BGA!
from jitxlib.landpatterns.grid_layout import A1, AlphaDictNumbering, GridPosition
from jitx.transform import Transform

class CustomBGA_Base(BGADecorated):
    def __init__(self, num_rows, num_cols, ball_diameter, pitch):
        super().__init__(num_rows, num_cols, ball_diameter, pitch)
        self._pitch = pitch
        self._offset_rows = {0, 1, 2, 3}  # Which rows get offset
        self._offset_cols = {8, 9, 10, 11}
        self._x_offset = 0.2975  # From datasheet
        self._y_offset = 0.2075

    def _generate_layout(self):
        for r in range(self._num_rows):
            row_y = ((self._num_rows - 1) / 2.0 - r) * self._pitch
            for c in range(self._num_cols):
                x = (c - (self._num_cols - 1) / 2.0) * self._pitch
                if r in self._offset_rows and c in self._offset_cols:
                    x += self._x_offset
                    y = row_y + self._y_offset
                else:
                    y = row_y
                yield GridPosition(r, c, Transform.translate(x, y))

class CustomBGA(A1, AlphaDictNumbering, CustomBGA_Base):
    pass
```

Row 0 = TOP row (M in 12-row), row 11 = BOTTOM (A).

## Multi-Unit Symbols

Multiple `BoxSymbol` attributes = separate visual boxes:

```python
def __init__(self):
    self.symbol_rf = BoxSymbol(rows=Row(...))      # Unit 1
    self.symbol_digital = BoxSymbol(rows=Row(...)) # Unit 2
    # Power unit: use horizontal layout (left=supplies, right=grounds)
    self.symbol_power = BoxSymbol(
        rows=Row(
            left=PinGroup(self.VCC, self.VBAT),
            right=PinGroup(self.VSS, self.GND),
        ),
    )
```

## Thermal Pads

```python
from jitx.shapes.composites import rectangle

landpattern = SON(...).thermal_pad(rectangle(1.68, 1.45))

# In __init__:
self.mappings = [PadMapping({
    self.TAB: [self.landpattern.thermal_pads[0]],
    ...
})]
```

## Dimension Mapping

| Datasheet | JITX |
|-----------|------|
| D (length) | `RectanglePackage.length` |
| E (width) | `RectanglePackage.width` |
| A (height) | `RectanglePackage.height` |
| E1/D1 (span) | `LeadProfile.span` |
| e (pitch) | `LeadProfile.pitch` |
| b (lead width) | `*Lead.width` |
| L (lead length) | `*Lead.length` |
| D2/E2 (thermal) | `.thermal_pad(rectangle(E2, D2))` |

## Toleranced Values

```python
Toleranced.min_max(3.8, 4.0)           # Range
Toleranced(5.0, 0.1)                    # Nominal ± tolerance
Toleranced.min_typ_max(0.13, 0.18, 0.23)  # Asymmetric
Toleranced.exact(7.0)                   # BSC/Basic
```

## Pin Naming

Use datasheet names exactly:
- `OQSPIF_D0`, `eMMC_CLK`, `V18F`, `M33_SWDIO`
- NOT generic: `GPIO5`, `VDD1`, `P0`

For arrays: `GPIO = [Port() for _ in range(30)]`

## Verification

### Test Harness
```python
from jitx.sample import SampleDesign
from jitx.container import inline

class TestDesign(SampleDesign):
    @inline
    class circuit(jitx.Circuit):
        dut = Device()
```

### Build Command
```bash
python -m jitx build module.TestDesign
```

**Success:** `status: ok`
**Failure:** Python traceback or `status: error`

**Output files** (in `designs/<design_name>/`):
- `cache/netlist.json` - Verify net connections
- `design-info/stable.design` - Design snapshot

### Introspection
```python
from jitx.inspect import extract
from jitx.landpattern import Pad
from jitx.net import Port

ports = list(extract(comp, Port))
pads = list(extract(comp.landpattern, Pad))
assert len(ports) == len(pads)  # Or +1 for thermal
```

### Verification Report
```
## Verification Report
- Pin count: Datasheet N = Generated N ✓
- Pad count: Landpattern N = Ports N ✓
- Dimensions: All within tolerance ✓
- Issues: [any discrepancies]
```

## Common Errors

| Error | Fix |
|-------|-----|
| `port X not mapped to symbol pin` | Add port to BoxSymbol |
| `port X not mapped to pad` | Check port count = pad count |
| `No pad configuration` | BGA needs `.pad_config(SMDPadConfig())` |

## Reference Designator Prefixes

U=IC, Q=transistor, D=diode, R=resistor, C=capacitor, L=inductor, J=connector, Y=crystal
