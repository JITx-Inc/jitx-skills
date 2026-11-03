"""Fixture for the edge-and-isolation-slot case: the buck board with an
isolation slot and pours that run past the board edge.

The GND pours on all four layers cover x -22..22, y -17..17, wider than the
40 x 30 board, so the board edge clips them. A 1 x 10 mm slot is milled
through the board at x 11.5..12.5, y -5..5 (``SLOT``, a ``Cutout``). No rule
sets an edge or slot clearance; the substrate's fab floor is row 8's 0.300 to
the outline. See ``lc_power_board.py`` for the layout.
"""

from jitx.feature import Cutout
from jitx.shapes.composites import rectangle

from lc_fixture_util import LcDesign
from lc_power_board import PowerBoard
from lc_substrate import LcBoard, LcStandard4

SLOT_CENTRE = (12.0, 0.0)
SLOT_SIZE = (1.0, 10.0)


class SlottedPowerBoard(PowerBoard):
    def __init__(self) -> None:
        super().__init__(pour_box=(-22.0, -17.0, 22.0, 17.0))
        self.slot = Cutout(rectangle(*SLOT_SIZE).at(*SLOT_CENTRE))


class EdgeAndIsolationSlotDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = SlottedPowerBoard()
