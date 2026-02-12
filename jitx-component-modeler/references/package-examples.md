# Package-Specific Examples

## Table of Contents

- [Example 1: Simple SOIC-8 (NE555 Timer)](#example-1-simple-soic-8-ne555-timer)
- [Example 2: SON-8 with Thermal Pad (LM1117)](#example-2-son-8-with-thermal-pad-lm1117)
- [Example 3: QFN-56 with Port Arrays (RP2040)](#example-3-qfn-56-with-port-arrays-rp2040)
- [Example 4: BGA with Named Pins and NC Positions](#example-4-bga-with-named-pins-and-nc-positions)
- [BGA-Specific Notes](#bga-specific-notes)
- [Non-Uniform BGAs (CRITICAL)](#non-uniform-bgas-critical)

## Example 1: Simple SOIC-8 (NE555 Timer)

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

## Example 2: SON-8 with Thermal Pad (LM1117)

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

## Example 3: QFN-56 with Port Arrays (RP2040)

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

## Example 4: BGA with Named Pins and NC Positions

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

## BGA-Specific Notes

1. **Row naming convention**: BGA rows use letters A-Z (skipping I and O). For a 12-row BGA: A, B, C, D, E, F, G, H, J, K, L, M.

2. **Grid planner**: Use `is_active()` returning `False` for depopulated positions, `None` to defer to default.

3. **Pad naming**: BGA pads accessed via `lp.A[1]` or `lp.B[12]` (dict-style).

4. **NC vs Depopulated**:
   - **NC**: Physical ball exists but not connected. Use `Port().no_connect()`, include in symbol.
   - **Depopulated**: No physical ball. Mark inactive in grid planner, no port needed.

5. **Package dimensions**: Body size is overall package. Ball array centered within.

## Non-Uniform BGAs (CRITICAL)

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
