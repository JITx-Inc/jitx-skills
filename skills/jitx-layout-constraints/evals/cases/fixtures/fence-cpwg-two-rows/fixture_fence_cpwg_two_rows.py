"""Fixture for the fence-cpwg-two-rows case: the radio board, feed unfenced.

The RF feed is a plain code route on layer 0 at the default width. The
substrate defines the grounded coplanar structure CPWG_50 (width 0.30, gap
0.20 on layer 0) but nothing applies it and it has no fence. Ground pours
cover all four layers, with a GND anchor via 2.5 mm either side of the feed
so the coplanar ground on each side has its own same-net object. See
``lc_radio_board.py`` for the layout.
"""

from lc_fixture_util import LcDesign
from lc_radio_board import RadioBoard
from lc_substrate import LcBoard, LcStandard4


class FenceCpwgTwoRowsDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = RadioBoard()
