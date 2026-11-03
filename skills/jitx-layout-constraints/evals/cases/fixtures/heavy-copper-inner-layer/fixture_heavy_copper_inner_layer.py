"""Fixture for the heavy-copper-inner-layer case: the buck board on the
LcHeavyInner4 stackup (fab sheet row 2: L2 is 2 oz, L3 is 0.5 oz).

On top of the buck board (``lc_power_board.py``):

- VIN runs on layer 1 (L2) between two VIN through vias at (-10, 5) and
  (10, 5), ``vin_l2``;
- a sense net, VSENSE, runs on layer 2 (L3) between two through vias at
  (-10, -5) and (10, -5), ``sense_l3``;
- the board defaults are 0.15 width and 0.15 space (fab rows 3 and 4 plus
  0.05). There is no per-layer rule.

GND pours cover all four layers.
"""

from jitx.circuit import Route
from jitx.constraints import IsCopper, IsTrace, design_constraint
from jitx.net import Net

from lc_fixture_util import LcDesign
from lc_power_board import PowerBoard
from lc_substrate import LcBoard, LcHeavyInner4


class HeavyInnerBoard(PowerBoard):
    def __init__(self) -> None:
        super().__init__()
        self.vin_vias = [LcHeavyInner4.ThVia().at(x, 5.0) for x in (-10.0, 10.0)]
        for v in self.vin_vias:
            self.VIN += v
        self.vin_l2 = Route(self.vin_vias[0], self.vin_vias[1], layer=1)
        self.sense_vias = [LcHeavyInner4.ThVia().at(x, -5.0) for x in (-10.0, 10.0)]
        self.VSENSE = Net(self.sense_vias, name="VSENSE")
        self.sense_l3 = Route(self.sense_vias[0], self.sense_vias[1], layer=2)
        self.default_width = design_constraint(IsTrace).trace_width(0.15)
        self.default_space = design_constraint(IsCopper, IsCopper).clearance(0.15)


class HeavyCopperInnerLayerDesign(LcDesign):
    substrate = LcHeavyInner4()
    board = LcBoard()
    circuit = HeavyInnerBoard()
