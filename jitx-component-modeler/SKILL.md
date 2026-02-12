---
name: jitx-component-modeler
description: Create JITX Python component code for electronic parts. ALWAYS use this skill when user asks to create a component, model a part, generate a component, add a component, or make a JITX component - even without a datasheet. Triggers on part numbers (NE555, LM1117, RP2040, etc.) and package types (SOIC, QFN, BGA, SON, SOT). Supports multi-unit symbols, thermal pads, and complex pin mappings.
---

# JITX Component Generation Skill

Generate JITX Python component code from datasheets and specifications.

## Environment Setup

Before generating components, check and fix the JITX environment automatically:

```bash
# Check for JITX project
if [ ! -f pyproject.toml ] || ! grep -q "jitx" pyproject.toml; then
  echo "ERROR: Not a JITX project (no pyproject.toml with jitx dependency)"
  exit 1
fi

# Create venv if missing
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate venv and install deps
source .venv/bin/activate
pip install -e . --quiet

# Verify
python -c "import jitx; print(f'JITX ready: {jitx.__version__}')"
```

Run this automatically when starting component work. Don't ask user to do manual setup.

**Recommended:** Install pyright for type checking:
```bash
claude plugin install pyright-lsp@claude-plugins-official
pip install pyright
```

## Datasheet Handling

**ALWAYS save datasheets locally before reading.**

When user provides a URL or asks to download a datasheet:
1. Download the PDF using WebFetch
2. Save to `datasheets/<mpn>.pdf` in the project (create folder if needed)
3. Then use the extraction process in Step 0

This ensures:
- Datasheet is available for future reference
- Consistent file paths for extraction scripts
- No repeated downloads

**AVOID REDUNDANT WEB SEARCHES**

Once you have the datasheet PDF, extract pinout, package dimensions, and pin descriptions from it using Step 0. Do NOT search for info that's already in the datasheet.

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

**Always extract relevant pages first:**

```python
# Run this inline to find and extract pages (requires: pip install pymupdf)
import fitz  # PyMuPDF

def find_and_extract(input_pdf, keywords, output_pdf):
    """Find pages with keywords and extract to smaller PDF."""
    doc = fitz.open(input_pdf)
    pages_to_extract = set()

    # Find pages containing keywords
    for page_num, page in enumerate(doc):
        text = page.get_text().lower()
        if any(kw.lower() in text for kw in keywords):
            pages_to_extract.add(page_num)

    # Extract to new PDF
    new_doc = fitz.open()
    for idx in sorted(pages_to_extract):
        new_doc.insert_pdf(doc, from_page=idx, to_page=idx)
    new_doc.save(output_pdf)
    print(f"Extracted {len(pages_to_extract)} pages: {sorted(p+1 for p in pages_to_extract)}")
    doc.close()
    new_doc.close()

# Usage:
find_and_extract(
    "datasheet.pdf",
    ["pinout", "pin description", "dimension", "package", "ball map", "mechanical"],
    "datasheet_extract.pdf"
)
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

If the datasheet covers multiple package options or component variants, **use AskUserQuestion** to ask the user which one to model:

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
    └── Custom/unusual → Manual Landpattern
```

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
# from jitxlib.landpatterns.generators.sot import SOT23_3, SOT23_5, SOT23_6, SOTLeadProfile
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

    # Symbol definition
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

### Example 1: Simple SOIC-8 (NE555 Timer)

```python
"""
Texas Instruments NE555 Precision Timer

Component definition for the NE555 timer in SOIC-8 package.
"""

import jitx
from jitx.net import Port
from jitxlib.landpatterns.generators.soic import SOIC, SOIC_DEFAULT_LEAD_PROFILE
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row


class NE555(jitx.Component):
    mpn = "NE555"
    manufacturer = "Texas Instruments"
    reference_designator_prefix = "U"
    datasheet = "https://www.ti.com/lit/ds/symlink/ne555.pdf"

    # Pins in package order (1-8)
    GND = Port()    # Pin 1
    TRIG = Port()   # Pin 2
    OUT = Port()    # Pin 3
    RESET = Port()  # Pin 4
    CONT = Port()   # Pin 5
    THRES = Port()  # Pin 6
    DISCH = Port()  # Pin 7
    VCC = Port()    # Pin 8

    # SOIC-8 narrow body (3.9mm width)
    landpattern = (
        SOIC(num_leads=8)
        .lead_profile(SOIC_DEFAULT_LEAD_PROFILE)
        .narrow(jitx.Toleranced.min_max(4.81, 5.0))  # Package length
    )

    # Symbol with functional grouping
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(GND, TRIG, OUT, RESET),
            right=PinGroup(VCC, DISCH, THRES, CONT),
        ),
    )


Device: type[NE555] = NE555
```

### Example 2: SON-8 with Thermal Pad (LM1117)

```python
"""
Texas Instruments LM1117 800mA LDO Regulator

Component definition for the LM1117 in SON-8 (WSON) package.
"""

import jitx
from jitx import PadMapping
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitx.shapes.composites import rectangle
from jitxlib.landpatterns.generators.son import SON, SONLead
from jitxlib.landpatterns.leads import LeadProfile
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column


class LM1117_WSON(jitx.Component):
    mpn = "LM1117IMPX-3.3/NOPB"
    manufacturer = "Texas Instruments"
    reference_designator_prefix = "U"
    datasheet = "https://www.ti.com/lit/ds/symlink/lm1117.pdf"

    # Pins (SON-8 with exposed pad)
    TAB = Port()    # Exposed thermal pad (also GND)
    GND = Port()    # Pin 1
    GND2 = Port()   # Pin 2 (also GND)
    VOUT = Port()   # Pin 3
    VOUT2 = Port()  # Pin 4 (also VOUT)
    NC1 = Port().no_connect()  # Pin 5
    NC2 = Port().no_connect()  # Pin 6
    VIN = Port()    # Pin 7
    VIN2 = Port()   # Pin 8 (also VIN)

    landpattern = (
        SON(num_leads=8)
        .lead_profile(
            LeadProfile(
                span=Toleranced.min_max(2.9, 3.1),  # Terminal span
                pitch=0.5,
                type=SONLead(
                    length=Toleranced.min_max(0.3, 0.5),
                    width=Toleranced.min_max(0.18, 0.30),
                ),
            ),
        )
        .package_body(
            RectanglePackage(
                width=Toleranced.min_max(2.9, 3.1),
                length=Toleranced.min_max(2.9, 3.1),
                height=Toleranced.min_max(0.7, 0.8),
            )
        )
        .thermal_pad(rectangle(1.68, 1.45))  # Exposed pad dimensions
    )

    # All ports must be in symbol, including NC pins
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(VIN, VIN2, NC1, NC2),  # NC pins included
            right=PinGroup(VOUT, VOUT2),
        ),
        columns=Column(
            down=PinGroup(GND, GND2, TAB),
        ),
    )

    def __init__(self):
        lp = self.landpattern
        # Explicit mapping for thermal pad
        self.mappings = [PadMapping({
            self.GND: [lp.p[1]],
            self.GND2: [lp.p[2]],
            self.VOUT: [lp.p[3]],
            self.VOUT2: [lp.p[4]],
            self.NC1: [lp.p[5]],
            self.NC2: [lp.p[6]],
            self.VIN: [lp.p[7]],
            self.VIN2: [lp.p[8]],
            self.TAB: [lp.thermal_pads[0]],
        })]


Device: type[LM1117_WSON] = LM1117_WSON
```

### Example 3: QFN-56 with Port Arrays (RP2040)

```python
"""
Raspberry Pi RP2040 Microcontroller

Component definition for the RP2040 in QFN-56 package.
"""

import jitx
from jitx import PadMapping
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitx.shapes.composites import rectangle
from jitxlib.landpatterns.generators.qfn import QFN, QFNLead
from jitxlib.landpatterns.leads import LeadProfile
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.landpatterns.ipc import DensityLevel
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column


class RP2040(jitx.Component):
    mpn = "RP2040"
    manufacturer = "Raspberry Pi"
    reference_designator_prefix = "U"
    datasheet = "https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf"

    # Power pins
    IOVDD = [Port() for _ in range(6)]
    DVDD = [Port() for _ in range(2)]
    USB_VDD = Port()
    ADC_AVDD = Port()
    VREG_IN = Port()
    VREG_VOUT = Port()

    # GPIO pins
    GPIO = [Port() for _ in range(30)]

    # Other pins
    GND = Port()
    XIN = Port()
    XOUT = Port()
    RUN = Port()
    SWCLK = Port()
    SWD = Port()
    TESTEN = Port()
    USB_DM = Port()
    USB_DP = Port()
    QSPI_SCLK = Port()
    QSPI_SS = Port()
    QSPI_SD0 = Port()
    QSPI_SD1 = Port()
    QSPI_SD2 = Port()
    QSPI_SD3 = Port()

    landpattern = (
        QFN(num_leads=56)
        .lead_profile(
            LeadProfile(
                span=Toleranced.exact(7.0),
                pitch=0.4,
                type=QFNLead(
                    length=Toleranced.min_max(0.3, 0.5),
                    width=Toleranced.min_typ_max(0.13, 0.18, 0.23),
                ),
            ),
        )
        .package_body(
            RectanglePackage(
                width=Toleranced.exact(7.0),
                length=Toleranced.exact(7.0),
                height=Toleranced.min_max(0.9, 0.9),
            )
        )
        .thermal_pad(rectangle(3.1, 3.1))
        .density_level(DensityLevel.C)
    )

    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(QSPI_SS, QSPI_SD0, QSPI_SD1, QSPI_SD2, QSPI_SD3, QSPI_SCLK,
                         XIN, XOUT, RUN, SWCLK, SWD),
            right=PinGroup(USB_DP, USB_DM, *GPIO),
        ),
        columns=Column(
            up=PinGroup(*IOVDD, *DVDD, USB_VDD, ADC_AVDD, VREG_IN, VREG_VOUT),
            down=PinGroup(GND, TESTEN),
        ),
    )

    def __init__(self):
        lp = self.landpattern
        # Build comprehensive pin mapping
        # (See full example in reference for complete mapping)
        self.mappings = [PadMapping({
            self.IOVDD[5]: [lp.p[1]],
            self.GPIO[0]: [lp.p[2]],
            # ... continue for all pins
            self.GND: [lp.thermal_pads[0]],
        })]


Device: type[RP2040] = RP2040
```

### Example 4: BGA with Named Pins and NC Positions

```python
"""
BGA component example based on a typical wireless SoC.

Demonstrates:
- BGA landpattern with fine pitch (0.45mm)
- Named GPIO ports with arrays
- Multiple power domains (VDD, VBAT, VSS)
- NC (No Connect) positions handled as inactive
- Proper symbol layout for complex ICs
"""

import jitx
from jitx import PadMapping
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitxlib.landpatterns.generators.bga import BGA
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.landpatterns.pads import SMDPadConfig
from jitxlib.landpatterns.grid_planner import GridPlanner
from jitxlib.landpatterns.grid_layout import GridPosition
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column


class InactivePositionsPlanner(GridPlanner):
    """Custom grid planner for specific inactive ball positions.

    BGA packages often have depopulated positions or NC balls that
    should not have pads generated.
    """

    def __init__(self, inactive_positions: set[tuple[int, int]]):
        """
        Args:
            inactive_positions: Set of (row, col) tuples for inactive balls.
                               Uses 0-indexed positions matching GridPosition.
        """
        self.inactive = inactive_positions

    def is_active(self, pos: GridPosition, num_rows: int, num_cols: int) -> bool | None:
        """Return False for inactive positions, None to defer to default."""
        if (pos.row, pos.column) in self.inactive:
            return False
        return None  # Defer to default (active)


class WirelessSoC(jitx.Component):
    """Example wireless SoC in VFBGA package.

    Package: VFBGA-132 (12x12 grid, 0.45mm pitch)
    - 144 total positions
    - 12 NC positions in bottom-right corner
    - 132 active balls
    """

    mpn = "EXAMPLE-SOC-132"
    manufacturer = "Example Semiconductor"
    reference_designator_prefix = "U"
    datasheet = "https://example.com/datasheet.pdf"

    # RF Front-End
    RFIOP = Port()
    RFIOM = Port()
    V14RF = Port()

    # OQSPI Flash Interface
    OQSPIF_D0 = Port()
    OQSPIF_D1 = Port()
    OQSPIF_D2 = Port()
    OQSPIF_D3 = Port()
    OQSPIF_D4 = Port()
    OQSPIF_D5 = Port()
    OQSPIF_D6 = Port()
    OQSPIF_D7 = Port()
    OQSPIF_CLK = Port()
    OQSPIF_CS = Port()

    # Power
    VBAT = Port()
    V18 = Port()
    V18F = Port()
    V12 = Port()
    VSS = Port()
    GND_RF = Port()

    # GPIO
    P0_05 = Port()
    P0_06 = Port()

    def __init__(self):
        # NC positions (0-indexed row, col)
        inactive_positions = {
            (8, 9), (8, 10), (8, 11),
            (9, 9), (9, 10), (9, 11),
            (10, 9), (10, 10), (10, 11),
            (11, 9), (11, 10), (11, 11),
        }

        grid_planner = InactivePositionsPlanner(inactive_positions)

        self.landpattern = (
            BGA(
                num_rows=12,
                num_cols=12,
                pitch=0.45,
                ball_diameter=0.25,
            )
            .grid_planner(grid_planner)
            .pad_config(SMDPadConfig())  # Required for BGA
            .package_body(
                RectanglePackage(
                    width=Toleranced.min_max(5.93, 6.07),
                    length=Toleranced.min_max(6.13, 6.27),
                    height=Toleranced.min_max(0.72, 0.92),
                )
            )
        )

        self.symbol = BoxSymbol(
            rows=[
                Row(
                    left=PinGroup(self.RFIOP, self.RFIOM),
                    right=PinGroup(self.V14RF),
                ),
                Row(
                    left=PinGroup(self.OQSPIF_D0, self.OQSPIF_D1, self.OQSPIF_D2,
                                  self.OQSPIF_D3, self.OQSPIF_D4, self.OQSPIF_D5,
                                  self.OQSPIF_D6, self.OQSPIF_D7),
                    right=PinGroup(self.OQSPIF_CLK, self.OQSPIF_CS),
                ),
            ],
            columns=Column(
                up=PinGroup(self.VBAT, self.V18, self.V18F, self.V12),
                down=PinGroup(self.VSS, self.GND_RF),
            ),
        )


Device: type[WirelessSoC] = WirelessSoC
```

**BGA-Specific Notes:**

1. **Row naming convention**: BGA rows use letters A-Z (skipping I and O). For a 12-row BGA: A, B, C, D, E, F, G, H, J, K, L, M.

2. **Grid planner**: Use `is_active()` returning `False` for depopulated positions, `None` to defer to default.

3. **Pad naming**: BGA pads accessed via `lp.A[1]` or `lp.B[12]` (dict-style).

4. **NC vs Depopulated**:
   - **NC**: Physical ball exists but not connected. Use `Port().no_connect()`, include in symbol.
   - **Depopulated**: No physical ball. Mark inactive in grid planner, no port needed.

5. **Package dimensions**: Body size is overall package. Ball array centered within.

### Non-Uniform BGAs (CRITICAL)

**IMPORTANT:** Some BGAs have balls NOT on a regular grid. Check mechanical drawing for:
- Different pitch in some regions
- Offset ball groups
- Split grids

**Pattern for non-uniform BGAs:**

```python
from collections.abc import Iterable

from jitx.transform import Transform
from jitxlib.landpatterns.generators.bga import BGADecorated
from jitxlib.landpatterns.grid_layout import A1, AlphaDictNumbering, GridPosition


class CustomBGA_Base(BGADecorated):
    """Custom BGA base with offset for specific pad positions.

    IMPORTANT: Extend BGADecorated, NOT BGA!
    BGA already includes A1 and AlphaDictNumbering mixins.
    """

    def __init__(self, num_rows: int, num_cols: int, ball_diameter: float, pitch: float):
        super().__init__(num_rows, num_cols, ball_diameter, pitch)
        self._pitch = pitch
        self._offset_rows = {0, 1, 2, 3}
        self._offset_cols = {8, 9, 10, 11}
        self._x_offset = 0.2975
        self._y_offset = 0.2075

    def _generate_layout(self) -> Iterable[GridPosition]:
        num_rows = self._num_rows
        num_cols = self._num_cols
        pitch = self._pitch
        center_row = (num_rows - 1) / 2.0
        center_col = (num_cols - 1) / 2.0

        for r in range(num_rows):
            row_y = (center_row - r) * pitch
            for c in range(num_cols):
                x = (c - center_col) * pitch
                if r in self._offset_rows and c in self._offset_cols:
                    x += self._x_offset
                    y = row_y + self._y_offset
                else:
                    y = row_y
                yield GridPosition(r, c, Transform.translate(x, y))


class CustomBGA(A1, AlphaDictNumbering, CustomBGA_Base):
    pass
```

**Key:** Row 0 = TOP row (M in 12-row BGA), row 11 = BOTTOM (A).

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
| D2 / E2 | Thermal pad size | `.thermal_pad(rectangle(D2, E2))` |

## Common Patterns

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
- `Q` - Transistors (MOSFETs, BJTs)
- `D` - Diodes
- `R` - Resistors
- `C` - Capacitors
- `L` - Inductors
- `J` - Connectors
- `Y` - Crystals/oscillators

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

## PadMapping Requirements

- **Automatic mapping (no PadMapping needed):** Ports mapped to pads in declaration order.
- **Explicit PadMapping required when:**
  - Thermal pad exists (map to `lp.thermal_pads[0]`)
  - Ports declared out of pin order
  - Multiple ports map to same pad
  - Pin 1 is not the first declared port

## Verification Process

### Test Harness

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

## Step 6: Capture Application Circuit (Optional)

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
            for _ in range(2):
                Capacitor(capacitance=10e-6, rated_voltage=50.0).insert(
                    self.buck.VIN, self.GND, short_trace=True
                )

        # Feedback voltage divider
        vdiv_cons = VoltageDividerConstraints(
            v_in=output_voltage, v_out=0.8, current=0.8/10e3,
            base_query=ResistorQuery(case=["0402"])
        )
        self.fb_div = voltage_divider_from_constraints(vdiv_cons)
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
