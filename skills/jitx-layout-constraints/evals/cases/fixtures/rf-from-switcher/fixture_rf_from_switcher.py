"""Fixture for the rf-from-switcher case: the radio board with a buck
converter beside the feed.

The radio board's layer-0 GND pour covers only x -18..3 (``GND_L1_BOX``),
around the U.FL connector, the feed and the series inductor; layers 1 to 3
keep the full GND pours. A TPS62933DRLR application circuit sits to the right:
its IC at (6, 3.5), and a layer-0 pour on its switch-node net over x 3.5..9,
y 0..7 (``SW_BOX``), the switch-node copper. The TPS62933 library circuit tags
its switch-node net with its own ``SwTag`` and carries
``design_constraint(SwTag(), True).clearance(0.25)``. No board rule relates
the switcher to the feed. See ``lc_radio_board.py`` for the radio layout.
"""

from jitx.copper import Pour
from jitx.net import Net
from jitx.transform import Transform

from jitxexamples.components.power_switchmode.texas_instruments_TPS62933DRLR import (
    TPS62933DRLRCircuit,
)

from lc_fixture_util import LcDesign, park
from lc_radio_board import RadioBoard, box
from lc_substrate import LcBoard, LcStandard4

GND_L1_BOX = (-18.0, -7.0, 3.0, 13.0)
SW_BOX = (3.5, 0.0, 9.0, 7.0)


class SwitcherWithPour(TPS62933DRLRCircuit):
    """The library circuit plus its switch-node copper, declared in the same
    circuit as the net."""

    def __init__(self) -> None:
        super().__init__(input_voltage=12.0)
        self.sw_pour = Pour(box(*SW_BOX), layer=0)
        self.SW_NODE += self.sw_pour


class RadioWithSwitcher(RadioBoard):
    def __init__(self) -> None:
        super().__init__(l1_box=GND_L1_BOX)
        self.reg = SwitcherWithPour()
        self.place(self.reg.buck, Transform((6.0, 3.5), 0))
        self.GND += self.reg.vin.Vn
        self.GND += self.reg.vout.Vn
        self.VIN = Net([self.reg.vin.Vp], name="VIN")
        self.VOUT = Net([self.reg.vout.Vp], name="VOUT")
        park(self.reg, [self.reg.buck], x0=-18.0, x1=18.0, y=-12.5)


class RfFromSwitcherDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = RadioWithSwitcher()
