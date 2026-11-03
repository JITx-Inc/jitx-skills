"""Fixture for the rule-did-not-fire case: the buck board with its rule set.

The board's own rules are below. The 0.5 mm VIN width is the one the user
says is not taking. See ``lc_power_board.py`` for the layout; the buck
board removes the TPS62933 library circuit's own rules.
"""

from jitx.constraints import IsCopper, IsTrace, Tag, design_constraint

from lc_fixture_util import LcDesign
from lc_power_board import PowerBoard
from lc_substrate import LcBoard, LcStandard4


class InputRail(Tag):
    """The 24 V input rail."""


class RuledPowerBoard(PowerBoard):
    def __init__(self) -> None:
        super().__init__()
        InputRail().assign(self.VIN)
        # Board defaults (fab sheet rows 3 and 4 plus margin).
        self.default_width = design_constraint(IsTrace).trace_width(0.15)
        self.default_space = design_constraint(IsCopper, IsCopper).clearance(0.15)
        # 24 V input: 0.5 mm wide.
        self.vin_width = design_constraint(InputRail()).trace_width(0.5)


class RuleDidNotFireDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = RuledPowerBoard()
