"""A placed and routed 2.4 GHz radio board for the layout-constraints evals.

Parts come from jitxexamples (py-components ``origin/main`` 9c398d3): the
Hirose U.FL-R-SMT(10) connector circuit, whose series inductor ``L`` ends the
feed. (The nRF52840 reference circuit at that commit does not translate on jitx
4.6.0, an assertion at ``jitx/_translate/idmap.py:801``, so the radio itself is
not on the board; the feed is what the cases constrain.)

Layout, on ``LcStandard4`` (``lc_substrate.py``) and the 40 x 30 mm ``LcBoard``:

- U.FL connector at (-14, 3), turned so its signal pad faces +x.
- The connector circuit's series inductor ``L`` at (2, 3), on the feed.
- The RF feed: a code route on layer 0 from the U.FL signal pad to ``L.p1``,
  straight along y = 3.
- GND pours on all four layers over x -18..18, y -7..13.
- GND through vias that anchor the pours: two beside the feed on layer 0,
  2.5 mm either side of it at x -5, so the coplanar ground on both sides of the
  feed has its own same-net object, and one in each corner of the pour region.
- Every other part parked in rows below y -8, outside the pours.

The board carries no design rule. Rules are the runner's job.
"""

from jitx.circuit import Circuit, Route
from jitx.copper import Pour
from jitx.net import Net
from jitx.shapes.primitive import Polygon
from jitx.transform import Transform

from jitxexamples.components.connectors.hirose_electric_co_ltd_U_FL_R_SMT_10 import (
    U_FL_R_SMT_10,
)

from lc_fixture_util import park
from lc_substrate import LcStandard4

FEED_Y = 3.0
POUR_BOX = (-18.0, -7.0, 18.0, 13.0)


def box(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


class RadioBoard(Circuit):
    def __init__(self) -> None:
        self.ufl = U_FL_R_SMT_10()

        self.place(self.ufl.component, Transform((-14.0, FEED_Y), -90))
        self.place(self.ufl.L, Transform((2.0, FEED_Y), 0))

        self.GND = Net([self.ufl.gnd], name="GND")
        self.ANT = Net([self.ufl.sig], name="RF_ANT")

        # The RF feed, U.FL signal pad to the series inductor, on layer 0.
        self.feed = Route(self.ufl.component.SIG, self.ufl.L.p1, layer=0)

        self.pours = [Pour(box(*POUR_BOX), layer=layer) for layer in range(4)]
        for p in self.pours:
            self.GND += p

        x0, y0, x1, y1 = POUR_BOX
        anchor_sites = [
            (-5.0, FEED_Y + 2.5),
            (-5.0, FEED_Y - 2.5),
            (x0 + 0.4, y0 + 0.4),
            (x1 - 0.4, y0 + 0.4),
            (x0 + 0.4, y1 - 0.4),
            (x1 - 0.4, y1 - 0.4),
        ]
        self.anchors = [LcStandard4.ThVia().at(x, y) for x, y in anchor_sites]
        for v in self.anchors:
            self.GND += v

        park(
            self,
            [self.ufl.component, self.ufl.L],
            x0=-18.0,
            x1=18.0,
            y=-9.5,
        )
