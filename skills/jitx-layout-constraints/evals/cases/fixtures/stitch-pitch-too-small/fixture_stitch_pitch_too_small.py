"""Fixture for the stitch-pitch-too-small case: the radio board, unstitched.

The ground pours on all four layers carry no tag and no rule; the runner adds
them. See ``lc_radio_board.py`` for the layout.
"""

from lc_fixture_util import LcDesign
from lc_radio_board import RadioBoard
from lc_substrate import LcBoard, LcStandard4


class StitchPitchTooSmallDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = RadioBoard()
