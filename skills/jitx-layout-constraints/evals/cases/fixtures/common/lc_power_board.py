"""A placed 24 V input buck board for the layout-constraints evals.

Parts come from jitxexamples (py-components ``origin/main`` 9c398d3): the
TPS62933DRLR application circuit (``TPS62933DRLRCircuit``) and a two-pole
Weidmuller LSF-SMT terminal block. The TPS62933 circuit as shipped tags VIN
and VOUT with its own ``PowerNetTag``, SW_NODE with ``SwTag`` and BST_MID
with ``BstTag``, and carries three rules of its own:
``design_constraint(PowerNetTag()).trace_width(0.25)`` and 0.25 clearances
from ``SwTag`` and ``BstTag`` to everything, all at priority 0. This board
removes those three rules (``drop_library_rules``) so no case measures a
width or clearance the fixture did not state; the tags stay.

Layout, on ``LcStandard4`` and the 40 x 30 mm ``LcBoard``:

- the terminal block at (-14, 0), the converter IC at (6, 0);
- the two 10 uF input capacitors at (-6, 2) and (0, 2), turned 270 and 90
  degrees so their p1 pads face each other along y = 2;
- the 100 nF input capacitor ``c_inp_sm`` at (-5, -3);
- a code route on layer 0 on VIN from the first input capacitor's p1 to the
  second's, ``vin_route``;
- GND pours on all four layers over x -18..18, y -7..7 (a fixture may pass
  ``pour_box``), anchored by the GND pads inside them;
- with ``ss_route``, the soft-start capacitor ``c_ss`` at (6, -3.5) and a code
  route on layer 0 from the IC's SS pin to its p1, ``ss_route``;
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

LIBRARY_RULES = ("power_trace_rule", "sw_clearance_rule", "bst_clearance_rule")
"""The rule attributes TPS62933DRLRCircuit sets on itself."""


def drop_library_rules(reg: TPS62933DRLRCircuit) -> None:
    """Remove the TPS62933 circuit's own design rules, keeping its tags. In
    this suite's own run (2026-11-03) the rules no longer appeared in the
    captured design after this, and the VIN route came back at the fab
    default 0.1 instead of the library's 0.25."""
    for name in LIBRARY_RULES:
        delattr(reg, name)


class PowerBoard(Circuit):
    def __init__(
        self,
        pour_box: tuple[float, float, float, float] = POUR_BOX,
        ss_route: bool = False,
    ) -> None:
        self.term = LSF_SMT(2)
        self.reg = TPS62933DRLRCircuit(input_voltage=24.0)
        drop_library_rules(self.reg)
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
        placed = [self.term, self.reg.buck, c1, c2, self.reg.c_inp_sm]
        if ss_route:
            self.place(self.reg.c_ss, Transform((6.0, -3.5), 0))
            self.ss_route = Route(self.reg.buck.SS, self.reg.c_ss.p1, layer=0)
            placed.append(self.reg.c_ss)

        self.pours = [Pour(box(*pour_box), layer=layer) for layer in range(4)]
        for p in self.pours:
            self.GND += p

        park(self, placed, x0=-18.0, x1=18.0, y=-9.5)
