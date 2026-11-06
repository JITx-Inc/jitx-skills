"""The Microchip KSZ9031RNX gigabit PHY on the 60 x 40 mm board, its
supplies joined and its planes poured.

Parts come from jitxexamples (py-components e6bf1cb): ``KSZ9031RNX`` in its
default package (48-lead 7 x 7 QFN, land pattern figure 13-3: 0.30 x 0.85
contact pads at 0.50 pitch, a 3.60 mm square exposed pad with four paste
windows).

- ``phy`` at the origin, unrotated.
- ``GND``: the exposed pad (``P_GND``) and ``VSS``; a pour over the whole
  board on L2, anchored by a GND through via at (-27, -17).
- ``1V2``: ``DVDDL`` (six pins), ``AVDDL`` (two) and ``AVDDL_PLL``; a pour
  over the whole board on L3, anchored by a 1V2 through via at (27, -17).
- ``3V3``: ``DVDDH`` (three pins) and ``AVDDH`` (two).

No route, and no via near the part. Layout is the runner's job.
"""

from jitx.circuit import Circuit
from jitx.copper import Pour
from jitx.net import Net
from jitx.shapes.composites import rectangle

from jitxexamples.components.ethernet_phys.microchip_KSZ9031RNX import KSZ9031RNX

from cl_substrate import BOARD_H, BOARD_W, ClFabConstraints, ClStandard4

EDGE = ClFabConstraints.min_copper_edge_space


class PhyBoard(Circuit):
    def __init__(self) -> None:
        self.phy = KSZ9031RNX().at(0.0, 0.0)

        self.GND = Net([self.phy.P_GND, self.phy.VSS], name="GND")
        self.V1V2 = Net([*self.phy.DVDDL, *self.phy.AVDDL, self.phy.AVDDL_PLL], name="1V2")
        self.V3V3 = Net([*self.phy.DVDDH, *self.phy.AVDDH], name="3V3")

        plane = rectangle(BOARD_W - 2 * EDGE, BOARD_H - 2 * EDGE)
        self.gnd_plane = Pour(plane, layer=1)
        self.v1v2_plane = Pour(plane, layer=2)
        self.gnd_anchor = ClStandard4.ThVia().at(-27.0, -17.0)
        self.v1v2_anchor = ClStandard4.ThVia().at(27.0, -17.0)
        self.GND += self.gnd_plane
        self.GND += self.gnd_anchor
        self.V1V2 += self.v1v2_plane
        self.V1V2 += self.v1v2_anchor
