"""Fixture for the thermal-by-pad-class case: the buck board, no relief rules.

The GND pads inside the layer-0 pour are the terminal block's pole-2 pads
(through hole), the two 10 uF input capacitors' p2 pads and the 100 nF input
capacitor's p2 pad. No pad has a relief rule, so every one joins the pour
solid. See ``lc_power_board.py`` for the layout.
"""

from lc_fixture_util import LcDesign
from lc_power_board import PowerBoard
from lc_substrate import LcBoard, LcStandard4


class ThermalByPadClassDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = PowerBoard()
