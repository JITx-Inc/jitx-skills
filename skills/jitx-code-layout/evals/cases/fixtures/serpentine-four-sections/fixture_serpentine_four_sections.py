"""Fixture for the serpentine-four-sections case: four differential pairs
between fictional one-pair chips, not routed.

Each pair runs from a transmitting chip at x = -20 to a receiving chip at
x = 20, on rows y = 15, 5, -5 and -15 (10 mm apart). The transmitting chip
of row 15 is ``PairChip``; those of rows 5, -5 and -15 are
``StaggeredPairChip``, whose ``p`` pad sits 2.0 mm behind its ``n`` pad, so
those pairs start 2.0 mm out of skew. Every receiving chip is ``PairChip``.

Each pair is constrained with ``ConstrainDiffPair``: P and N each 300 +/- 2
ps pad to pad, within 1 ps of each other, on ``DIFF_100`` (0.15 traces, 0.20
apart, 1.6e11 m/s, so 160 mm/ns). The straight 40 mm path is 250 ps, so
each trace needs about 8 mm more copper than the straight path.
"""

from jitx.circuit import Circuit
from jitx.net import Topology
from jitx.si import ConstrainDiffPair
from jitx.toleranced import Toleranced

from cl_parts import ClDesign, PairChip, StaggeredPairChip
from cl_substrate import ClStandard4

TX_X = -20.0
RX_X = 20.0
ROW_Y = (15.0, 5.0, -5.0, -15.0)
PAIR_DELAY = Toleranced(300e-12, 2e-12)
PAIR_SKEW = 1e-12


class SerpentineBoard(Circuit):
    def __init__(self) -> None:
        self.tx = [PairChip().at(TX_X, ROW_Y[0]), *(StaggeredPairChip().at(TX_X, y) for y in ROW_Y[1:])]
        self.rx = [PairChip().at(RX_X, y) for y in ROW_Y]
        self.pairs = [tx.d + rx.d for tx, rx in zip(self.tx, self.rx, strict=True)]
        self.timing = [
            ConstrainDiffPair(Topology(tx.d, rx.d))
            .timing(PAIR_DELAY)
            .timing_difference(PAIR_SKEW)
            .structure(ClStandard4.DIFF_100)
            for tx, rx in zip(self.tx, self.rx, strict=True)
        ]


class SerpentineFourSectionsDesign(ClDesign):
    circuit = SerpentineBoard()
