"""Fixture for the permissive-rule-outranks-protection case: the buck board
with a rule set that has a broad escape rule above a protection rule.

See ``lc_power_board.py`` for the layout and the rules the TPS62933 library
circuit carries.
"""

from jitx.constraints import AnyObject, IsCopper, IsTrace, OnLayer, Tag, design_constraint

from lc_fixture_util import LcDesign
from lc_power_board import PowerBoard
from lc_substrate import LcBoard, LcStandard4


class InputRail(Tag):
    """The 24 V input rail."""


class RuledPowerBoard(PowerBoard):
    def __init__(self) -> None:
        super().__init__()
        InputRail().assign(self.VIN)
        # Priority ladder: 0 defaults, 1 rail width, 2 rail keep-away, 4 escapes.
        self.default_width = design_constraint(IsTrace).trace_width(0.15)
        self.default_space = design_constraint(IsCopper, IsCopper).clearance(0.15)
        self.vin_width = design_constraint(InputRail(), priority=1).trace_width(0.5)
        # 24 V input: keep 0.6 mm from everything, pours included.
        self.vin_keepaway = design_constraint(InputRail(), AnyObject, priority=2).clearance(0.6)
        # The TPS62933's 0.5 mm-pitch pads need 0.1 mm spacing to escape on L1.
        self.escape_space = design_constraint(IsTrace & OnLayer(0), AnyObject, priority=4).clearance(0.1)


class PermissiveRuleOutranksProtectionDesign(LcDesign):
    substrate = LcStandard4()
    board = LcBoard()
    circuit = RuledPowerBoard()
