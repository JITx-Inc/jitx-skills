"""Fixture for the board-ground-pours case: the two-SMA coupon with no copper
but the jacks' pads.

``GND`` joins the two jacks' shells, whose ground pads sit on L1 and L4.
``RF`` joins the centre pins and has no route yet. Nothing lies on L2 or L3.
See ``cl_launch_board.py`` for the placement.
"""

from cl_launch_board import LaunchBoard
from cl_parts import ClDesign


class BoardGroundPoursDesign(ClDesign):
    circuit = LaunchBoard()
