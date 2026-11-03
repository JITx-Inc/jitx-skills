"""Fixture for the fence-pour-outline case: the radio board with an RF cavity.

Layer 0 (L1) is poured with GND only over the RF section, the box
``CAVITY_BOX`` (x -17 to 5, y -2 to 8) around the U.FL connector, the feed and
the series inductor. Layers 1 to 3 keep the full GND pours. The cavity pour
carries no tag and no fence rule; the runner adds them. See
``lc_radio_board.py`` for the rest of the layout.
"""

from lc_fixture_util import LcDesign
from lc_radio_board import RadioBoard
from lc_substrate import LcBoard, LcStandard4

CAVITY_BOX = (-17.0, -2.0, 5.0, 8.0)


class FencePourOutlineDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = RadioBoard(l1_box=CAVITY_BOX)
