"""Fixture for the route-around-with-sketch case: two edge SMA jacks and a
column of five ground vias standing across the straight path between their
centre pads.

``RF`` joins the two centre pins and has no route. The vias sit at x = 0,
0.75 apart, from y = -1.5 to 1.5 (pads 0.500 across). See
``cl_launch_board.py`` for the placement.
"""

from cl_launch_board import LaunchBoard
from cl_parts import ClDesign


class RouteAroundWithSketchDesign(ClDesign):
    circuit = LaunchBoard(via_column=True)
