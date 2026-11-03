"""Fixture for the default-net-classes case: the buck board, no board rules.

Two code routes on layer 0 inside the GND pour: ``vin_route`` on VIN between
the two 10 uF input capacitors, and ``ss_route`` on the soft-start net from
the regulator's SS pin to its capacitor. The board has no rule of its own; the
TPS62933 library circuit carries its own rules (see ``lc_power_board.py``).
"""

from lc_fixture_util import LcDesign
from lc_power_board import PowerBoard
from lc_substrate import LcBoard, LcStandard4


class DefaultNetClassesDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = PowerBoard(ss_route=True)
