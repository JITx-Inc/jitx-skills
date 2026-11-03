"""Fixture for the bga-power-escape case: a hex-grid BGA with one power ball.

The part is ``GenericHexGridBGA`` from the jitxexamples ``si_bga_optimization``
demo: 21 rows by 8 columns on a hex grid, nearest ball centres 1.0 apart, 0.5
balls. Every ball that is not a signal lane is a GND port; here the ball at
row 4, column 2 (``GND[33]``) is taken off GND and made the core rail, VCORE.

Layout, on ``LcStandard4`` and the 40 x 30 mm ``LcBoard``:

- the BGA at (4, 0), unrotated. The VCORE ball sits at (2.268, 5.5), one
  column in from the left edge, between the edge column's balls at
  (1.402, 6.0) and (1.402, 5.0), both GND;
- two VCORE through vias, 0.8 across so the 0.5 class fits (fab row 11's
  0.500 is a minimum; spike S8: a trace wider than its via pads came back as
  a Polygon with no width), at
  (-1, 5.5) just outside the package body and at (-12, 5.5);
- ``vcore_escape``, a code route on layer 0 from the VCORE ball to the first
  via, and ``vcore_trunk``, a code route on layer 0 from that via to the
  second;
- a VCORE class: ``design_constraint(VcoreTag()).trace_width(0.5)`` and
  ``design_constraint(VcoreTag(), True).clearance(0.2)``.

The signal lanes are left unconnected.
"""

from jitx.circuit import Circuit, Route
from jitx.constraints import Tag, design_constraint
from jitx.net import Net
from jitx.transform import Transform

from jitxexamples.demos.si_bga_optimization.generic_bga import GenericHexGridBGA

from lc_fixture_util import LcDesign
from lc_substrate import LcBoard, LcStandard4

VCORE_BALL = 33


class VcoreTag(Tag):
    """The core rail."""


class PowerVia(LcStandard4.ThVia):
    diameter = 0.8


class BgaBoard(Circuit):
    def __init__(self) -> None:
        self.bga = GenericHexGridBGA()
        self.place(self.bga, Transform((4.0, 0.0), 0))
        gnd = [p for i, p in enumerate(self.bga.GND) if i != VCORE_BALL]
        self.GND = Net(gnd, name="GND")
        self.vcore_vias = [PowerVia().at(-1.0, 5.5), PowerVia().at(-12.0, 5.5)]
        self.VCORE = Net([self.bga.GND[VCORE_BALL], *self.vcore_vias], name="VCORE")
        self.vcore_escape = Route(self.bga.GND[VCORE_BALL], self.vcore_vias[0], layer=0)
        self.vcore_trunk = Route(self.vcore_vias[0], self.vcore_vias[1], layer=0)
        VcoreTag().assign(self.VCORE)
        self.vcore_width = design_constraint(VcoreTag()).trace_width(0.5)
        self.vcore_space = design_constraint(VcoreTag(), True).clearance(0.2)


class BgaPowerEscapeDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = BgaBoard()
