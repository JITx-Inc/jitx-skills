"""Fixture for the rf-connector-launch case: two edge-launch SMA jacks, not
routed, offset so the line between them has to turn.

Parts come from jitxexamples (py-components e6bf1cb): the Würth WR-SMA end
launch jack ``60312202114514``. Its land pattern's origin is the body face,
which sits on the board edge, with +x running into the board along the
centre pad (0.61 wide, 1.97 long).

- ``j1`` on the left edge at (-30, -10), centre pad pointing +x.
- ``j2`` on the right edge at (30, 10), turned 180 degrees.
- ``RF``: the two centre pins. ``GND``: the two shells.

The substrate defines ``CPWG_50_FENCED`` (0.30 trace, 0.20 clearance, two
rows of ``ThVia`` fence each side) and applies it to nothing. No route, pour
or rule.
"""

from jitx.circuit import Circuit
from jitx.net import Net
from jitx.transform import Transform

from jitxexamples.components.connectors.wurth_elektronik_60312202114514 import (
    Wurth60312202114514,
)

from cl_parts import ClDesign


class LaunchPair(Circuit):
    def __init__(self) -> None:
        self.j1 = Wurth60312202114514()
        self.j2 = Wurth60312202114514()
        self.place(self.j1, Transform((-30.0, -10.0), 0))
        self.place(self.j2, Transform((30.0, 10.0), 180))
        self.RF = Net([self.j1.sig, self.j2.sig], name="RF")
        self.GND = Net([self.j1.gnd, self.j2.gnd], name="GND")


class RfConnectorLaunchDesign(ClDesign):
    circuit = LaunchPair()
