"""Fixture for the route-config-length case: two single-ended lines between
fictional one-pin chips, not routed.

- ``CLK``: ``clk_a`` at (-20, 10) to ``clk_b`` at (20, 10), inside a GND
  pour on L1 (x -24 to 24, y 6 to 14), anchored by a GND through via at
  (22, 13).
- ``DATA``: ``data_a`` at (-20, -8) to ``data_b`` at (20, -8), constrained
  to 300 +/- 2 ps pad to pad on ``MS_50`` (0.30 wide, 1.6e11 m/s, so
  160 mm/ns): the straight 40 mm path is 250 ps, so the line needs about
  8 mm more copper than the straight path.

The chips are ``PadChip`` (cl_parts.py): one 0.6 mm square pad each.
"""

from jitx.circuit import Circuit
from jitx.copper import Pour
from jitx.net import Net
from jitx.shapes.composites import rectangle
from jitx.si import Constrain, Topology
from jitx.toleranced import Toleranced

from cl_parts import ClDesign, PadChip
from cl_substrate import ClStandard4

DATA_DELAY = Toleranced(300e-12, 2e-12)


class LengthBoard(Circuit):
    def __init__(self) -> None:
        self.clk_a = PadChip().at(-20.0, 10.0)
        self.clk_b = PadChip().at(20.0, 10.0)
        self.data_a = PadChip().at(-20.0, -8.0)
        self.data_b = PadChip().at(20.0, -8.0)
        self.CLK = Net([self.clk_a.io, self.clk_b.io], name="CLK")
        self.DATA = Net([self.data_a.io, self.data_b.io], name="DATA")
        self.GND = Net(name="GND")
        self.clk_pour = Pour(rectangle(48.0, 8.0).at(0.0, 10.0), layer=0)
        self.clk_pour_anchor = ClStandard4.ThVia().at(22.0, 13.0)
        self.GND += self.clk_pour
        self.GND += self.clk_pour_anchor
        self.data_timing = (
            Constrain(Topology(self.data_a.io, self.data_b.io)).timing(DATA_DELAY).structure(ClStandard4.MS_50)
        )


class RouteConfigLengthDesign(ClDesign):
    circuit = LengthBoard()
