"""Fixture for the fine-pitch-high-clearance-escape case: the buck board with
its switch node routed to the inductor.

On top of the buck board (``lc_power_board.py``):

- the inductor ``reg.Ind`` at (6, 5);
- a SW_NODE through via at (3, 0.75), ``sw_via``, 0.8 across (fab row 11's
  0.500 is a minimum). In this suite's own run (2026-11-03) a 0.6 trace
  leaving a 0.5 via came back as a Polygon with no width (spike S8 saw the
  same for a 0.5 trace between 0.45 vias); from the 0.8 via it is an
  ArcPolyline 0.6 wide;
- ``sw_escape``, a code route on layer 0 from the IC's SW pin (pad 5 of the
  SOT-583 land pattern) to that via, and ``sw_trunk``, a code route on layer
  0 from the via to the inductor's p1;
- a switch-node class width, ``design_constraint(SwTag()).trace_width(0.6)``.

The TPS62933 library circuit already tags SW_NODE with ``SwTag`` and carries
``design_constraint(SwTag(), True).clearance(0.25)``. The land pattern's pads
are 0.28 x 0.68 at a 0.5 pitch, so the SW pad and the BST pad beside it are
0.22 apart.
"""

from jitx.circuit import Route
from jitx.constraints import design_constraint
from jitx.net import Net
from jitx.transform import Transform

from jitxexamples.components.power_switchmode.texas_instruments_TPS62933DRLR import SwTag

from lc_fixture_util import LcDesign
from lc_power_board import PowerBoard
from lc_substrate import LcBoard, LcStandard4


class SwVia(LcStandard4.ThVia):
    diameter = 0.8


class SwitchNodeBoard(PowerBoard):
    def __init__(self) -> None:
        super().__init__()
        reg = self.reg
        self.place(reg.Ind, Transform((6.0, 5.0), 0))
        self.sw_via = SwVia().at(3.0, 0.75)
        # Joined here: a via added to the library circuit's own net from this
        # circuit fails translation ("multiple parents").
        self.SW_TAP = Net([reg.buck.SW, self.sw_via])
        self.sw_escape = Route(reg.buck.SW, self.sw_via, layer=0)
        self.sw_trunk = Route(self.sw_via, reg.Ind.p1, layer=0)
        self.sw_width = design_constraint(SwTag()).trace_width(0.6)


class FinePitchHighClearanceEscapeDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = SwitchNodeBoard()
