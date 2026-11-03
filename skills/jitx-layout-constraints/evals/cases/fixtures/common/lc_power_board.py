"""A placed 24 V input buck board for the layout-constraints evals.

Parts come from jitxexamples (py-components ``origin/main`` 9c398d3): the
TPS62933DRLR application circuit (``TPS62933DRLRCircuit``) and a two-pole
Weidmuller LSF-SMT terminal block. The TPS62933 circuit as shipped tags VIN
and VOUT with its own ``PowerNetTag`` and carries
``design_constraint(PowerNetTag()).trace_width(0.25)`` at priority 0, plus
clearance rules on its switch and bootstrap nets; those are part of the
library circuit, not of this board.

Layout, on ``LcStandard4`` and the 40 x 30 mm ``LcBoard``:

- the terminal block at (-14, 0), the converter IC at (6, 0);
- the two 10 uF input capacitors at (-6, 2) and (0, 2), turned 270 and 90
  degrees so their p1 pads face each other along y = 2;
- the 100 nF input capacitor ``c_inp_sm`` at (-5, -3);
- a code route on layer 0 on VIN from the first input capacitor's p1 to the
  second's, ``vin_route``;
- GND pours on all four layers over x -18..18, y -7..7, anchored by the GND
  pads inside them;
- every other part parked in rows below y -8.
"""

from jitx.circuit import Circuit, Route
from jitx.copper import Pour
from jitx.net import Net
from jitx.transform import Transform

from jitxexamples.components.connectors.weidmuller_LSF_SMT import LSF_SMT
from jitxexamples.components.power_switchmode.texas_instruments_TPS62933DRLR import (
    TPS62933DRLRCircuit,
)

from lc_fixture_util import park
from lc_radio_board import box

POUR_BOX = (-18.0, -7.0, 18.0, 7.0)


class PowerBoard(Circuit):
    def __init__(self) -> None:
        self.term = LSF_SMT(2)
        self.reg = TPS62933DRLRCircuit(input_voltage=24.0)
        self.place(self.term, Transform((-14.0, 0.0), 90))
        self.place(self.reg.buck, Transform((6.0, 0.0), 0))
        c1, c2 = self.reg.input_caps
        self.place(c1, Transform((-6.0, 2.0), 270))
        self.place(c2, Transform((0.0, 2.0), 90))
        self.place(self.reg.c_inp_sm, Transform((-5.0, -3.0), 0))

        self.VIN = Net([self.term.p[1], self.reg.vin.Vp], name="VIN")
        self.GND = Net([self.term.p[2], self.reg.vin.Vn, self.reg.vout.Vn], name="GND")
        self.VOUT = Net([self.reg.vout.Vp], name="VOUT")

        self.vin_route = Route(c1.p1, c2.p1, layer=0)

        self.pours = [Pour(box(*POUR_BOX), layer=layer) for layer in range(4)]
        for p in self.pours:
            self.GND += p

        park(self, [self.term, self.reg.buck, c1, c2, self.reg.c_inp_sm], x0=-18.0, x1=18.0, y=-9.5)
