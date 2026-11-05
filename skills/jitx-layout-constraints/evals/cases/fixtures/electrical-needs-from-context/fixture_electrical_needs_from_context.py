"""PSU-ISO-01: a 48 V input board with a 3.3 V output through U1, a Corrow
Power CPI-4833 isolated DC/DC module.

Parts: J1 and J2 are two-pad SMD headers; U1 is a four-pad SMD module, input
pads 1 and 2, output pads 3 and 4. All pads are on layer 0. Board:
``LcStandard4`` and the 40 x 30 mm ``LcBoard``.

- J1 at (-15, 0): pad 1 on ``VIN48`` at (-15, 1.5), pad 2 on ``GND_P`` at
  (-15, -1.5).
- U1 at (0, 0): pad 1 on ``VIN48`` at (-5, 1.27), pad 2 on ``GND_P`` at
  (-5, -1.27), pad 3 on ``V3V3`` at (5, 1.27), pad 4 on ``GND_S`` at
  (5, -1.27).
- J2 at (15, 0): pad 1 on ``V3V3`` at (15, 1.5), pad 2 on ``GND_S`` at
  (15, -1.5).
- Routes on layer 0: ``vin_route`` on ``VIN48`` from J1 pad 1 to U1 pad 1, and
  ``v3_route`` on ``V3V3`` from U1 pad 3 to J2 pad 1.
- ``GND_P`` pours on all four layers over x -19..-0.5, y -14..14
  (``PRIMARY_BOX``), with ``GND_P`` through vias at (-10, -8) and (-10, 8).
- ``GND_S`` pours on all four layers over x 0.5..19, y -14..14
  (``SECONDARY_BOX``), with ``GND_S`` through vias at (10, -8) and (10, 8).
"""

from jitx.circuit import Circuit, Route
from jitx.component import Component
from jitx.copper import Pour
from jitx.feature import Soldermask
from jitx.landpattern import Landpattern, Pad, PadMapping
from jitx.net import Net, Port
from jitx.shapes.composites import rectangle
from jitx.transform import Transform
from jitxlib.symbols.box import BoxSymbol

from lc_fixture_util import LcDesign
from lc_radio_board import box
from lc_substrate import LcBoard, LcStandard4

PRIMARY_BOX = (-19.0, -14.0, -0.5, 14.0)
SECONDARY_BOX = (0.5, -14.0, 19.0, 14.0)
PRIMARY_ANCHORS = ((-10.0, -8.0), (-10.0, 8.0))
SECONDARY_ANCHORS = ((10.0, -8.0), (10.0, 8.0))


class SmdPad(Pad):
    def __init__(self, w: float, h: float) -> None:
        self.shape = rectangle(w, h)
        self.soldermask = Soldermask(rectangle(w + 0.1, h + 0.1))


class Header2Landpattern(Landpattern):
    def __init__(self) -> None:
        self.p1 = SmdPad(2.0, 1.5).at(0.0, 1.5)
        self.p2 = SmdPad(2.0, 1.5).at(0.0, -1.5)


class Header2(Component):
    """Two-way SMD wire-to-board header, pads 2.0 x 1.5 on a 3.0 pitch."""

    reference_designator_prefix = "J"
    manufacturer = "Generic"
    mpn = "HDR-2-SMD"

    def __init__(self) -> None:
        self.p1 = Port()
        self.p2 = Port()
        self.landpattern = Header2Landpattern()
        self.symbol = BoxSymbol()
        self.pad_mapping = PadMapping({self.p1: self.landpattern.p1, self.p2: self.landpattern.p2})


class Cpi4833Landpattern(Landpattern):
    """Pads 1 and 2 (input) at x -5, pads 3 and 4 (output) at x +5."""

    def __init__(self) -> None:
        self.p1 = SmdPad(1.6, 1.0).at(-5.0, 1.27)
        self.p2 = SmdPad(1.6, 1.0).at(-5.0, -1.27)
        self.p3 = SmdPad(1.6, 1.0).at(5.0, 1.27)
        self.p4 = SmdPad(1.6, 1.0).at(5.0, -1.27)


class Cpi4833(Component):
    """Corrow Power CPI-4833 isolated DC/DC module, 36 to 60 V in, 3.3 V out.
    Pad 1 +VIN, pad 2 -VIN, pad 3 +VOUT, pad 4 -VOUT."""

    reference_designator_prefix = "U"
    manufacturer = "Corrow Power"
    mpn = "CPI-4833"

    def __init__(self) -> None:
        self.vin = Port()
        self.vin_rtn = Port()
        self.vout = Port()
        self.vout_rtn = Port()
        self.landpattern = Cpi4833Landpattern()
        self.symbol = BoxSymbol()
        self.pad_mapping = PadMapping(
            {
                self.vin: self.landpattern.p1,
                self.vin_rtn: self.landpattern.p2,
                self.vout: self.landpattern.p3,
                self.vout_rtn: self.landpattern.p4,
            }
        )


class IsolatedSupplyBoard(Circuit):
    def __init__(self) -> None:
        self.j1 = Header2()
        self.u1 = Cpi4833()
        self.j2 = Header2()
        self.place(self.j1, Transform((-15.0, 0.0), 0))
        self.place(self.u1, Transform((0.0, 0.0), 0))
        self.place(self.j2, Transform((15.0, 0.0), 0))

        # Primary side.
        self.VIN48 = Net([self.j1.p1, self.u1.vin], name="VIN48")
        self.GND_P = Net([self.j1.p2, self.u1.vin_rtn], name="GND_P")
        # Secondary side.
        self.V3V3 = Net([self.u1.vout, self.j2.p1], name="V3V3")
        self.GND_S = Net([self.u1.vout_rtn, self.j2.p2], name="GND_S")

        self.vin_route = Route(self.j1.p1, self.u1.vin, layer=0)
        self.v3_route = Route(self.u1.vout, self.j2.p1, layer=0)

        self.primary_pours = [Pour(box(*PRIMARY_BOX), layer=layer) for layer in range(4)]
        for p in self.primary_pours:
            self.GND_P += p
        self.secondary_pours = [Pour(box(*SECONDARY_BOX), layer=layer) for layer in range(4)]
        for p in self.secondary_pours:
            self.GND_S += p

        self.primary_anchors = [LcStandard4.ThVia().at(x, y) for x, y in PRIMARY_ANCHORS]
        for v in self.primary_anchors:
            self.GND_P += v
        self.secondary_anchors = [LcStandard4.ThVia().at(x, y) for x, y in SECONDARY_ANCHORS]
        for v in self.secondary_anchors:
            self.GND_S += v


class ElectricalNeedsFromContextDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = IsolatedSupplyBoard()
