"""Fixture for the route-around-with-sketch case: two edge SMA jacks and a
column of five ground vias standing across the straight path between their
centre pads.

``RF`` joins the two centre pins and has no route. The vias sit at x = 0,
0.75 apart, from y = -2.5 to 0.5 (pads 0.500 across), centred 1.0 below
the path: the column reaches 2.75 below the line between the pads and 0.75
above it, so the detour above is the shorter one. See ``cl_launch_board.py``
for the placement.
"""

from cl_launch_board import LaunchBoard
from cl_parts import ClDesign

COLUMN_Y = -1.0


class RouteAroundWithSketchDesign(ClDesign):
    circuit = LaunchBoard(via_column=True, column_y=COLUMN_Y)
