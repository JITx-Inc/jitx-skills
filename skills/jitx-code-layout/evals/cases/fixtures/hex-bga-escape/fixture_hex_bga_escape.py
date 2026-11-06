"""Fixture for the hex-bga-escape case: two differential pairs from a
hex-grid BGA to two fictional pair chips, not routed.

The BGA is a placeholder 56-ball part on the ``HexBGA`` land pattern from
jitxexamples' ``si_bga_optimization`` demo (py-components e6bf1cb): 7 rows
by 8 columns, 1.2 mm ball pitch, 0.5 mm balls. Columns sit
1.2 x sqrt(3)/2 = 1.039 mm apart, so the channel between two columns'
ball pads is 0.539 mm. Its centre is at (0, 7).

- ``bga.lanes[0]`` is on balls (row 2, column 4) for P and (2, 3) for N;
  ``bga.lanes[1]`` on (2, 6) and (2, 5). Each pair's P and N sit in
  neighbouring columns, with the channel between those columns below them.
- Every other ball is on ``GND`` and carries a ``ClStandard4.VipVia`` at its
  centre, joining it to the inner layers.
- ``chips[i]``: a ``PairChip`` turned 90 degrees, 12 mm below the field,
  under the channel of pair ``i``; ``pairs[i]`` is ``bga.lanes[i] +
  chips[i].d``.

The substrate defines ``DIFF_100`` (0.15 traces, 0.20 apart, 0.25
clearance) and ``DIFF_100_FIELD`` (0.08, 0.10 apart, 0.05 clearance) and
applies neither. No route or rule.
"""

from jitx.circuit import Circuit
from jitx.component import Component
from jitx.inspect import visit
from jitx.landpattern import Pad, PadMapping
from jitx.net import DiffPair, Net, Port
from jitx.toleranced import Toleranced
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.landpatterns.pads import SMDPadConfig
from jitxlib.symbols.box import BoxSymbol

from jitxexamples.demos.si_bga_optimization.generic_bga import BGA_BALL_DIAMETER, HexBGA

from cl_parts import ClDesign, PairChip
from cl_substrate import ClStandard4

ROWS = 7
COLS = 8
PITCH = 1.2
"""Ball pitch, in mm. Columns sit PITCH x sqrt(3)/2 = 1.039 mm apart."""
PAIR_BALLS = (((2, 4), (2, 3)), ((2, 6), (2, 5)))
"""Each pair's (P, N) balls as ``HexBGA.get_pad`` (row, column)."""
BGA_AT = (0.0, 7.0)
CHIP_DROP = 12.0


class FieldBGA(Component):
    """A placeholder 56-ball hex-grid BGA with two differential pairs. Not an
    orderable part."""

    manufacturer = "Fictional"
    mpn = "CL-EVAL-HEXBGA56"
    reference_designator_prefix = "U"

    lanes = [DiffPair() for _ in PAIR_BALLS]
    GND = [Port() for _ in range(ROWS * COLS - 2 * len(PAIR_BALLS))]
    landpattern = (
        HexBGA(num_rows=ROWS, num_cols=COLS, pitch=PITCH, ball_diameter=BGA_BALL_DIAMETER)
        .pad_config(SMDPadConfig())
        .package_body(
            RectanglePackage(
                width=Toleranced.exact(7.0), length=Toleranced.exact(7.5), height=Toleranced.min_max(0.8, 1.0)
            )
        )
    )
    symbol = BoxSymbol()

    def __init__(self) -> None:
        lp = self.landpattern
        entries: list[tuple[Port, Pad]] = []
        signal: list[Pad] = []
        for lane, (p_ball, n_ball) in zip(self.lanes, PAIR_BALLS, strict=True):
            p_pad, n_pad = lp.get_pad(*p_ball), lp.get_pad(*n_ball)
            entries += [(lane.p, p_pad), (lane.n, n_pad)]
            signal += [p_pad, n_pad]
        ground = [p for _, p in visit(lp, Pad) if all(p is not s for s in signal)]
        entries += list(zip(self.GND, ground, strict=True))
        self.mappings = [PadMapping(entries)]


def ball_xy(lp: HexBGA, row: int, col: int) -> tuple[float, float]:
    """A ball's centre on the board."""
    pad = lp.get_pad(row, col)
    assert pad.transform is not None
    x, y = pad.transform.translation
    return (BGA_AT[0] + float(x), BGA_AT[1] + float(y))


class EscapeBoard(Circuit):
    def __init__(self) -> None:
        self.bga = FieldBGA().at(*BGA_AT)
        lp = self.bga.landpattern
        signal = {ball for pair in PAIR_BALLS for ball in pair}
        self.GND = Net(name="GND")
        for port in self.bga.GND:
            self.GND += port
        self.ground_vias = [
            ClStandard4.VipVia().at(*ball_xy(lp, r, c))
            for r in range(ROWS)
            for c in range(1, COLS + 1)
            if (r, c) not in signal
        ]
        for v in self.ground_vias:
            self.GND += v
        self.chips = []
        for p_ball, n_ball in PAIR_BALLS:
            (px, py), (nx, ny) = ball_xy(lp, *p_ball), ball_xy(lp, *n_ball)
            self.chips.append(PairChip().at((px + nx) / 2, min(py, ny) - CHIP_DROP, rotate=90))
        self.pairs = [lane + chip.d for lane, chip in zip(self.bga.lanes, self.chips, strict=True)]


class HexBgaEscapeDesign(ClDesign):
    circuit = EscapeBoard()
