# Package-Specific Examples

## Table of Contents

- [Example 1: Simple SOIC-8 (NE555 Timer)](#example-1-simple-soic-8-ne555-timer)
- [Example 2: SOT23-5 (LMV321 Op-Amp)](#example-2-sot23-5-lmv321-op-amp)
- [Example 3: SON-8 with Thermal Pad (LM1117)](#example-3-son-8-with-thermal-pad-lm1117)
- [Example 4: QFN-56 with Port Arrays (RP2040)](#example-4-qfn-56-with-port-arrays-rp2040)
- [Example 5: QFP-48 (STM32F103C8)](#example-5-qfp-48-stm32f103c8)
- [Example 6: BGA with Named Pins and NC Positions](#example-6-bga-with-named-pins-and-nc-positions)
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
from jitx.toleranced import Toleranced
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
        .narrow(Toleranced.min_max(4.81, 5.0))  # Package length
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

## Example 2: SOT23-5 (LMV321 Op-Amp)

```python
"""
Texas Instruments LMV321 Single Op-Amp

Component definition for the LMV321 in SOT-23-5 package.

Pad layout:
    1 5
    2
    3 4
"""

import jitx
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitxlib.landpatterns.generators.sot import SOT23_5, SOTLeadProfile, SOTLead
from jitxlib.landpatterns.ipc import DensityLevel
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column


class LMV321(jitx.Component):
    mpn = "LMV321IDBVR"
    manufacturer = "Texas Instruments"
    reference_designator_prefix = "U"
    datasheet = "https://www.ti.com/lit/ds/symlink/lmv321.pdf"

    # Pins in package order (1-5)
    INp = Port()    # Pin 1 — Non-inverting input
    GND = Port()    # Pin 2 — Ground
    INn = Port()    # Pin 3 — Inverting input
    OUT = Port()    # Pin 4 — Output
    VCC = Port()    # Pin 5 — Supply

    # SOT-23-5 landpattern
    landpattern = (
        SOT23_5()
        .lead_profile(
            SOTLeadProfile(
                span=Toleranced.min_max(2.6, 3.0),
            )
        )
        .package_body(
            RectanglePackage(
                width=Toleranced.min_max(1.45, 1.75),
                length=Toleranced.min_max(2.75, 3.05),
                height=Toleranced.min_max(0.9, 1.45),
            )
        )
        .density_level(DensityLevel.B)
    )

    # Op-amp symbol: inputs left, output right, power in columns
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(INp, INn),
            right=PinGroup(OUT),
        ),
        columns=Column(
            up=PinGroup(VCC),
            down=PinGroup(GND),
        ),
    )


Device: type[LMV321] = LMV321
```

**SOT notes:**
- `SOTLeadProfile` defaults: `pitch=0.95`, `type=SOTLead()` (small gull-wing). Only `span` is typically required.
- To customize lead dimensions: `SOTLeadProfile(span=..., type=SOTLead(length=..., width=...))`.
- `SOT23_3` and `SOT23_6` follow the same pattern with different pad counts.

## Example 3: SON-8 with Thermal Pad (LM1117)

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
    GND = [Port() for _ in range(2)]   # Pin 1 & 2
    VOUT = [Port() for _ in range(2)]  # Pin 3 & 4
    NC = [Port().no_connect() for _ in range(2)] # Pin 5 & 6
    VIN = [Port() for _ in range(2)]   # Pin 7 & Pin 8 (also VIN)

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
            left=PinGroup(VIN[0], VIN[1], NC[0], NC[1]),  # NC pins included
            right=PinGroup(VOUT[0], VOUT[1]),
        ),
        columns=Column(
            down=PinGroup(GND[0], GND[1], TAB),
        ),
    )

    def __init__(self):
        lp = self.landpattern
        # Explicit mapping for thermal pad
        self.mappings = [PadMapping({
            self.GND[0]: [lp.p[1]],
            self.GND[1]: [lp.p[2]],
            self.VOUT[0]: [lp.p[3]],
            self.VOUT[1]: [lp.p[4]],
            self.NC[0]: [lp.p[5]],
            self.NC[1]: [lp.p[6]],
            self.VIN[0]: [lp.p[7]],
            self.VIN[1]: [lp.p[8]],
            self.TAB: [lp.thermal_pads[0]],
        })]


Device: type[LM1117_WSON] = LM1117_WSON
```

## Example 4: QFN-56 with Port Arrays (RP2040)

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

## Example 5: QFP-48 (STM32F103C8)

```python
"""
STMicroelectronics STM32F103C8 ARM Cortex-M3 Microcontroller

Component definition for the STM32F103C8 in LQFP-48 package.
Demonstrates 4-sided gull-wing QFP with many pins.
"""

import jitx
from jitx import PadMapping
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitx.shapes.composites import rectangle
from jitxlib.landpatterns.generators.qfp import QFP, QFPLead
from jitxlib.landpatterns.leads import LeadProfile
from jitxlib.landpatterns.ipc import DensityLevel
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column


class STM32F103C8(jitx.Component):
    """STM32F103C8 in LQFP-48 package.

    48 pins, 12 per side, 0.5mm pitch.
    Pin 1 is top-left, numbering counter-clockwise.
    """

    mpn = "STM32F103C8T6"
    manufacturer = "STMicroelectronics"
    reference_designator_prefix = "U"
    datasheet = "https://www.st.com/resource/en/datasheet/stm32f103c8.pdf"

    # Power
    VBAT = Port()
    VDD = [Port() for _ in range(3)]
    VDDA = Port()
    VSS = [Port() for _ in range(3)]
    VSSA = Port()

    # Reset and boot
    NRST = Port()
    BOOT0 = Port()

    # Oscillator
    OSC_IN = Port()
    OSC_OUT = Port()

    # Port A
    PA = [Port() for _ in range(16)]

    # Port B
    PB = [Port() for _ in range(16)]

    # Port C
    PC13 = Port()
    PC14 = Port()
    PC15 = Port()

    # Port D
    PD0 = Port()
    PD1 = Port()

    # LQFP-48: 7x7mm body, 0.5mm pitch, gull-wing leads
    landpattern = (
        QFP(num_leads=48)
        .lead_profile(
            LeadProfile(
                span=Toleranced.min_max(8.8, 9.2),
                pitch=0.5,
                type=QFPLead(
                    length=Toleranced.min_max(0.45, 0.75),
                    width=Toleranced.min_max(0.17, 0.27),
                ),
            )
        )
        .package_body(
            RectanglePackage(
                width=Toleranced.min_max(6.9, 7.1),
                length=Toleranced.min_max(6.9, 7.1),
                height=Toleranced.min_max(1.35, 1.45),
            )
        )
        .density_level(DensityLevel.B)
    )

    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(
                *PA[:8], NRST, BOOT0,
                OSC_IN, OSC_OUT,
            ),
            right=PinGroup(
                *PA[8:], *PB[:8],
            ),
        ),
        columns=Column(
            up=PinGroup(VBAT, *VDD, VDDA),
            down=PinGroup(*VSS, VSSA,
                          PC13, PC14, PC15, PD0, PD1,
                          *PB[8:]),
        ),
    )

    def __init__(self):
        lp = self.landpattern
        # LQFP-48 pin 1 = VBAT (top-left), counter-clockwise
        self.mappings = [PadMapping({
            self.VBAT: [lp.p[1]],
            self.PC13: [lp.p[2]],
            self.PC14: [lp.p[3]],
            self.PC15: [lp.p[4]],
            self.PD0: [lp.p[5]],
            self.PD1: [lp.p[6]],
            self.NRST: [lp.p[7]],
            self.VSSA: [lp.p[8]],
            self.VDDA: [lp.p[9]],
            self.PA[0]: [lp.p[10]],
            self.PA[1]: [lp.p[11]],
            self.PA[2]: [lp.p[12]],
            # ... continue for all 48 pins
            self.VSS[0]: [lp.p[23]],
            self.VDD[0]: [lp.p[24]],
            # ... remaining pins
        })]


Device: type[STM32F103C8] = STM32F103C8
```

**QFP notes:**
- `QFP(num_leads=N)` — total pin count must be divisible by 4 for uniform sides.
- For asymmetric pin counts: `QFP(num_rows=(left, bottom, right, top))`.
- `QFPLead` defaults to `BigGullWingLeads` protrusion type.
- Pin numbering: counter-clockwise starting at pin 1 (top-left).
- For asymmetric lead profiles (different span on X vs Y sides), pass two `LeadProfile` objects: `.lead_profile(x_profile, y_profile)`.

## Example 6: BGA with Named Pins and NC Positions

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
    OQSPIF_D = [Port() for _ in range(8)]
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

    # not all physical pins have a Port() example in this code snippet
    # ...

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
                    left=PinGroup([self.OQSPIF_D[i] for i in range(8)]),
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

1. **Row naming convention**: Row letters come from `ABCDEFGHJKLMNPRTUVWY` — I, O, Q, S, X, and Z are skipped — rolling over to two letters (`AA`, `AB`, …) past row 19. Row index 0 is `A`, so a 12-row BGA is A, B, C, D, E, F, G, H, J, K, L, M.

2. **Grid planner**: Use `is_active()` returning `False` for depopulated positions, `None` to defer to default.

3. **Pad naming**: BGA pads accessed via `lp.A[1]` or `lp.B[12]` (dict-style).

4. **NC vs Depopulated**:
   - **NC**: Physical ball exists but not connected. Use `Port().no_connect()`, include in symbol.
   - **Depopulated**: No physical ball. Mark inactive in grid planner, no port needed.

   `no_connect()` works from the component's `__init__`, which is where it belongs for a ball the
   vendor defines as NC — that is a property of the part, not of a board that uses it. (The docstring
   shows it called from the enclosing circuit; that is the *other* case, a pin this design leaves
   open.) On a large BGA the NC group runs to dozens of balls, and leaving them as ordinary ports
   makes "intentionally open per the vendor" and "the board designer forgot to wire it"
   indistinguishable to every downstream unconnected-port check.

5. **Package dimensions**: Body size is overall package. Ball array centered within.

6. **`ball_diameter` is the PCB land diameter, not the package's ball.** This is the one BGA
   parameter whose name points at the wrong document. The mechanical drawing gives you a ball
   diameter — often as a min/nom/max triple, sitting right next to the pitch, which is exactly where
   you are already reading — and it is *not* what this argument wants. The land diameter comes from
   the manual's **PCB design-rule table**, keyed by pitch, and it is a different number.

   **Don't take that on trust: open `jitxlib/landpatterns/generators/bga.py` and read what the
   parameter drives** (`self.pad_shape(Circle(diameter=ball_diameter))`) before you pass anything to
   it. Reading the source for yourself is what makes this stick — an assertion here reads like
   trivia and gets skipped.

   Passing the physical ball builds a valid, plausible, silently oversized land pattern. Record in a
   comment which document each number came from.

7. **Reaching pads: add a public adapter, don't touch `_`-prefixed members.** Verification code needs
   pad-by-position access, and the framework's accessor is internal. Wrap it once in a subclass:

   ```python
   class MyBGA(BGA):
       def get_pad(self, row: int, column: int) -> Pad:
           """Both 0-indexed, matching emitted coordinates: ball A1 is get_pad(0, 0)."""
           return self._get_pad(row, column + 1)
   ```

   Design code never reaches into `_`-prefixed framework members directly — the adapter is the
   sanctioned boundary.

   **Make the adapter's convention the same one your coordinates use.** The framework numbers
   columns from 1 (matching the ball reference "A1"), while a generated module carries fully
   zero-indexed `(row, col)` coordinates. Those differ by one, and the whole value of the adapter is
   that it absorbs that difference *once* — so take 0-indexed arguments and do the `+ 1` inside.
   Write it the other way, taking a 1-indexed column, and every call site converts instead
   (`get_pad(row, col + 1)`), which is the same off-by-one risk you added the adapter to remove, now
   scattered. State the convention in the docstring either way, because a reader cannot tell from
   the signature.

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

**Key:** Row index 0 = TOP row (`A`), row 11 = BOTTOM (`M` in a 12-row BGA). The `(center_row - r)` term is what puts row 0 at the largest y.
