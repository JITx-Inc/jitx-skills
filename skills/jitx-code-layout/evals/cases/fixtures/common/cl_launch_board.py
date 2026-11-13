"""Two edge-launch SMA jacks facing each other across the 60 x 40 mm board.

Parts come from jitxexamples (py-components e6bf1cb): the Würth WR-SMA end
launch jack ``60312202114514``. Its land pattern's origin is the body face,
which sits on the board edge, with +x running into the board along the
centre pad (0.61 wide, 1.97 long).

- ``j1`` on the left edge at (-30, 0), centre pad pointing +x.
- ``j2`` on the right edge at (30, 0), turned 180 degrees.
- ``RF``: the two centre pins. ``GND``: the two shells.

Options add what a case needs around the line:

- ``via_column``: five ``ClStandard4.ThVia`` on GND at x = 0, 0.75 apart,
  centred on y = ``column_y``, across the straight path between the centre
  pads. With ``column_y`` below 0 the column reaches further below the path
  than above it, so the +y detour is the shorter one.
- ``j2_fenced``: a ring of ``ClStandard4.ThVia`` on GND around ``j2``'s
  centre pad, 0.75 apart, and a layer-0 route keepout over the ring's band,
  closing every way in to that pad on L1.

No route, pour or rule. Layout is the runner's job.
"""

from jitx.circuit import Circuit
from jitx.feature import KeepOut
from jitx.layerindex import LayerSet
from jitx.net import Net
from jitx.shapes.composites import rectangle

from jitxexamples.components.connectors.wurth_elektronik_60312202114514 import (
    Wurth60312202114514,
)

from cl_substrate import ClStandard4

EDGE_X = 30.0
COLUMN_PITCH = 0.75
COLUMN_COUNT = 5


class LaunchBoard(Circuit):
    def __init__(self, via_column: bool = False, j2_fenced: bool = False, column_y: float = 0.0) -> None:
        self.j1 = Wurth60312202114514().at(-EDGE_X, 0.0)
        self.j2 = Wurth60312202114514().at(EDGE_X, 0.0, rotate=180)

        self.RF = Net([self.j1.sig, self.j2.sig], name="RF")
        self.GND = Net([self.j1.gnd, self.j2.gnd], name="GND")

        if via_column:
            first = column_y - (COLUMN_COUNT - 1) * COLUMN_PITCH / 2
            self.column = [ClStandard4.ThVia().at(0.0, first + k * COLUMN_PITCH) for k in range(COLUMN_COUNT)]
            for v in self.column:
                self.GND += v

        if j2_fenced:
            # A rectangle of vias 3.0 mm out from the centre pad (x 28.03 to
            # 30, y -0.305 to 0.305), open only at the board edge.
            x0, x1, y0, y1 = 25.0, 29.6, -3.0, 3.0
            sites: list[tuple[float, float]] = []
            n = round((y1 - y0) / COLUMN_PITCH)
            sites += [(x0, y0 + k * (y1 - y0) / n) for k in range(n + 1)]
            m = round((x1 - x0) / COLUMN_PITCH)
            for k in range(1, m + 1):
                x = x0 + k * (x1 - x0) / m
                sites += [(x, y0), (x, y1)]
            self.fence = [ClStandard4.ThVia().at(x, y) for x, y in sites]
            for v in self.fence:
                self.GND += v
            # The band the ring stands on, closed on layer 0 to routes.
            self.fence_keepout = [
                KeepOut(rectangle(0.8, y1 - y0 + 0.8).at(x0, 0.0), layers=LayerSet(0), route=True),
                KeepOut(rectangle(x1 - x0 + 0.8, 0.8).at((x0 + x1) / 2, y0), layers=LayerSet(0), route=True),
                KeepOut(rectangle(x1 - x0 + 0.8, 0.8).at((x0 + x1) / 2, y1), layers=LayerSet(0), route=True),
            ]
