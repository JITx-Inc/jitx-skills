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
- [Custom Landpatterns (irregular footprints)](#custom-landpatterns-irregular-footprints)
- [Generic 2.54 mm pin header (OCDB `pin-header(N)` replacement)](#worked-example-generic-254-mm-pin-header-the-stanza-pin-headern-replacement)
- [PadMapping Reference](#padmapping-reference)

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
- **The SOT family in `jitxlib.landpatterns.generators.sot` only exports `SOT23_3`, `SOT23_5`, `SOT23_6`.** There is **no `SOT89_3`, `SOT223_3`, or `SOT583_8` generator.** For SOT-89 (e.g. AS78L05), SOT-223 (e.g. TPS62933 with thermal tabs), or SOT-583 layouts, fall back to a custom `Landpattern` subclass — see the "Custom landpatterns" section below. Do not guess at an import path by analogy with `SOT23_5`.

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

> ⚠️ **Every BGA landpattern must chain `.pad_config(SMDPadConfig())`.** This is
> not an example-specific detail — there is no built-in default pad config for
> BGAs, and omitting the call fails at build time with `No pad configuration
> specified`. If the BGA has depopulated balls (e.g. an A1 keep-out or
> asymmetric ball map), also chain `.grid_planner(<GridPlanner subclass>)` — see
> the inline `InactivePositionsPlanner` below. `is_active(pos, num_rows,
> num_cols)` returns `False` for inactive positions, `None` to defer to default;
> `pos.row` / `pos.column` are zero-indexed (A1 = row 0, col 0).


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

> ⚠️ **There is no `BGADepop` class and no `depop=` kwarg.** Depopulation is done via `.grid_planner(<GridPlanner subclass>)` as shown in Example 6 above. The `BGA` constructor takes **`num_rows` / `num_cols`** (not `rows` / `cols`), plus `ball_diameter` and `pitch`. Importing a non-existent `BGADepop` symbol is a recurring guess — verify against `github.com/JITx-Inc/py-jitx-stdlib/blob/main/src/jitxlib/landpatterns/generators/bga.py` before assuming the API.

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

## Custom Landpatterns (irregular footprints)

Use this path when a part's footprint is **not** a standard SOIC/QFN/SON/QFP/BGA layout — e.g. a 3.5mm headphone jack (PJ-614), a SOT-89/SOT-223/SOT-583 (none of which have generators in `jitxlib.landpatterns.generators.sot`), a barrel connector, or any vendor-specific irregular pad arrangement. The standard generator chain is insufficient; build the landpattern by hand.

### Key facts (verify before writing code)

- `Landpattern` lives in **`jitx.landpattern`**, *not* `jitxlib.landpatterns.core` or any other module.
- Pad classes (`SMDPad`, `THPad`, `NPTHPad`) live in **`jitxlib.landpatterns.pads`**.
- **There is no `add_pad()` method.** Pads are `Positionable` — set their position with `.at(x, y, on=Side.Top, rotate=0.0)`. Attach pads to the landpattern by declaring them as attributes on the `Landpattern` subclass (or by assigning them in `__init__`); the framework collects them.
- **`Rectangle` is not a class.** Use the function `rectangle(w, h, *, radius=None, chamfer=None, anchor=Anchor.C)` from `jitx.shapes.composites`. `Circle(...)` *is* a class (from `jitx.shapes.primitive`).
- Coordinates are millimetres, centered anchor by default. Top-side pads use `Side.Top` (the default); bottom-side pads pass `on=Side.Bottom`.

### Worked example: PJ-614 headphone jack (7 irregular SMD pads)

```python
import jitx
from jitx import PadMapping
from jitx.landpattern import Landpattern
from jitx.layerindex import Side
from jitx.net import Port
from jitx.shapes.composites import rectangle
from jitxlib.landpatterns.pads import SMDPad


class PJ614Landpattern(Landpattern):
    # Each pad gets a name so PadMapping can reference it.
    # Numbers below are illustrative — use the mechanical drawing.
    p1 = SMDPad(copper=rectangle(2.0, 1.4)).at(0.0, 0.0)
    p2 = SMDPad(copper=rectangle(2.0, 1.4)).at(2.5, 0.0)
    p3 = SMDPad(copper=rectangle(2.0, 1.4)).at(5.0, 0.0)
    p4 = SMDPad(copper=rectangle(2.0, 1.4)).at(7.5, 0.0)
    p5 = SMDPad(copper=rectangle(1.6, 1.6)).at(0.0, -4.5)
    p6 = SMDPad(copper=rectangle(1.6, 1.6)).at(7.5, -4.5)
    shield = SMDPad(copper=rectangle(4.0, 1.2)).at(3.75, -4.5)


class PJ614(jitx.Component):
    mpn = "PJ-614"
    reference_designator_prefix = "J"

    TIP = Port()
    RING = Port()
    SLEEVE = Port()
    SHIELD = Port()

    landpattern = PJ614Landpattern()

    def __init__(self):
        lp = self.landpattern
        self.mappings = [PadMapping({
            self.TIP:    [lp.p1],
            self.RING:   [lp.p2],
            self.SLEEVE: [lp.p3, lp.p4],   # mechanically merged
            self.SHIELD: [lp.p5, lp.p6, lp.shield],
        })]
```

### Variations

- **SOT-89 / SOT-223 with thermal tab**: the heat-spreader pad is just another `SMDPad` (typically larger). Map it to the same `Port` as the collector/drain via a multi-pad list (see PadMapping reference below).
- **Through-hole pads**: use `THPad(copper=Circle(diameter=…), cutout=Circle(diameter=…))` from `jitxlib.landpatterns.pads`.
- **Non-plated mounting holes**: `NPTHPad(cutout=Circle(diameter=…))`.

If a stock generator might exist for your package (e.g. you're tempted to invent `SOT89_3()`), **grep the canonical repo first**: `gh search code --repo JITx-Inc/py-jitx-stdlib SOT89`. Inventing the import is the failure mode this section is here to prevent.

### Worked example: generic 2.54 mm pin header (the Stanza `pin-header(N)` replacement)

Stanza designs lean on OCDB's `pin-header(N)` generator constantly:

```stanza
inst conn : pin-header(5)
net VCC (conn.p[1])
```

There is **no Python equivalent** for OCDB's `pin-header(N)` — neither
`jitxlib.connectors` nor `jitx.ocdb` exists, and `Part(mpn="…")` against
typical generic pin-header MPNs raises
`ValueError: No components meeting requirements`. Build a custom
`Component` with through-hole pads:

```python
import jitx
from jitx import PadMapping
from jitx.landpattern import Landpattern
from jitx.net import Port
from jitx.shapes.primitive import Circle
from jitxlib.landpatterns.pads import THPad
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row


def _pin_header_lp(n: int, pitch: float = 2.54) -> type[Landpattern]:
    """Build a Landpattern subclass with N THPads in a straight row."""

    class LP(Landpattern):
        pass

    # 2.54 mm pitch → 1.7 mm copper / 1.0 mm drill is the JITX 3.x
    # OCDB default for `pin-header`.
    for i in range(n):
        pad = THPad(
            copper=Circle(diameter=1.7),
            cutout=Circle(diameter=1.0),
        ).at(i * pitch, 0.0)
        setattr(LP, f"p{i + 1}", pad)
    return LP


class PinHeader(jitx.Component):
    """N-pin straight-row 2.54 mm header (generic / OCDB `pin-header`)."""

    reference_designator_prefix = "J"

    def __init__(self, n: int = 5, *, pitch: float = 2.54):
        # Ports — Python list with 0-based indexing.  Stanza users
        # accessing `.p[1]` should remember to translate to `.p[0]`.
        self.p = [Port() for _ in range(n)]
        # Landpattern — built per-instance because pad count varies.
        lp_cls = _pin_header_lp(n, pitch=pitch)
        self.landpattern = lp_cls()
        # Symbol — single column of pins on the right side.
        self.symbol = BoxSymbol(rows=Row(right=PinGroup(*self.p)))
        # Pad mapping — `p[i]` ↔ landpattern attribute `p{i+1}`.
        self.mappings = [PadMapping({
            self.p[i]: [getattr(self.landpattern, f"p{i + 1}")]
            for i in range(n)
        })]
```

Caller-side usage matches Stanza one-for-one except for the **1-indexed
→ 0-indexed** flip on pin access:

```python
self.conn = PinHeader(5)
self.VCC += self.conn.p[0]       # was conn.p[1] in Stanza
self.GND += self.conn.p[1]       # was conn.p[2] in Stanza
```

Variations:

- **Two-row 2x N header**: change `_pin_header_lp` to place pads in two
  rows, e.g. `pad.at(i * pitch, row * pitch)` for `row in (0, 1)`. Use
  `BoxSymbol(rows=Row(left=PinGroup(*odd_pins), right=PinGroup(*even_pins)))`.
- **Different pitch** (e.g. 1.27 mm / 2.0 mm): pass `pitch=` and adjust
  copper / drill diameters to the manufacturer drawing.
- **Surface-mount header**: replace `THPad` with `SMDPad(copper=...)`.

This recipe ports the single most common OCDB connector. For other
OCDB connectors (`molex-pico-spox`, `jst-sh`, etc.) the same pattern
applies — build a custom `Component` with manually-positioned pads and
a `BoxSymbol`.

## PadMapping Reference

`PadMapping` is the bridge from a `Component`'s logical `Port`s to the physical `Pad`s of its landpattern.

### Import path

```python
from jitx import PadMapping
# (PadMapping is also reachable at jitx.landpattern.PadMapping)
```

### Signature

```python
PadMapping(entries: Mapping[Port, Pad | Sequence[Pad]])
```

**Keys are `Port` objects** (component attributes — `self.PVDD`, `self.GND[0]`). **Values are `Pad` objects** (landpattern attributes — `lp.p[3]`, `lp.thermal_pads[0]`) **or a sequence of them** when one logical port is bonded to multiple physical pads.

> Common wrong guess: keys-as-strings (`"PVDD"`) and values-as-ints (`3`) or magic-string thermal-pad keys (`"thermal_pad"`). **None of these are valid.** Always pass the actual `Port` and `Pad` objects.

### Single pad

```python
self.mappings = [PadMapping({
    self.GND: [lp.p[2]],
})]
```

### Multiple pads bonded to one rail

```python
self.mappings = [PadMapping({
    self.PVDD: [lp.p[3], lp.p[4]],                 # one port, two power pads
    self.PGND: [lp.p[25], lp.p[26], lp.p[31], lp.p[32]],   # bonded ground
})]
```

### Exposed thermal pad

The thermal pad is a real `Pad` object exposed via `lp.thermal_pads[i]`. Map it like any other pad:

```python
self.mappings = [PadMapping({
    self.GND: [lp.p[1], lp.p[2], lp.thermal_pads[0]],
})]
```

(For QFN / SON generators that chained `.thermal_pad(rectangle(...))`, the resulting pad is `lp.thermal_pads[0]`. For custom landpatterns you declared yourself, use the attribute name you gave it — `lp.tab`, `lp.ep`, etc.)
