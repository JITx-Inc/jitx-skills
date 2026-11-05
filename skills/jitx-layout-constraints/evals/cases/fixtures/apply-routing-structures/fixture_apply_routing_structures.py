"""Fixture for the apply-routing-structures case: the radio board with its
feed in two segments and a timing constraint on it.

The feed runs from the U.FL signal pad to an RF_ANT through via at (-9, 3)
(``feed_escape``) and on from the via to the series inductor (``feed``),
both on layer 0. A signal constraint times the path from the connector's
signal pin to the inductor. The substrate defines CPWG_50 and NECK_50; nothing
applies either, so the build reports a missing routing structure. See
``lc_radio_board.py`` for the layout.
"""

from jitx.net import Topology
from jitx.si import Constrain

from lc_fixture_util import LcDesign
from lc_radio_board import RadioBoard
from lc_substrate import LcBoard, LcStandard4


class TimedRadio(RadioBoard):
    def __init__(self) -> None:
        super().__init__(feed_via_x=-9.0)
        self.feed_timing = Constrain(Topology(self.ufl.component.SIG, self.ufl.L.p1)).timing(1e-9)


class ApplyRoutingStructuresDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = TimedRadio()
