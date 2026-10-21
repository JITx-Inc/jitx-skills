"""Each value in board.py against a number copied from the report into the
test, so the report is never read."""

import math

import board


def test_values() -> None:
    assert board.CORE_L3_L4_THICKNESS == 0.1270
    assert board.UV1_PAD == 0.240
    assert board.MIN_COPPER_WIDTH == 0.045
    assert board.SE50_L1_WIDTH == 0.1470
    assert math.isclose(board.SE50_L1_PLANE_L2_WIDTH, 0.240)
