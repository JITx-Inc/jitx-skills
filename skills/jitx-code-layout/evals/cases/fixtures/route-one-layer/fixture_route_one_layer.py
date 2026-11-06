"""Fixture for the route-one-layer case: two edge SMA jacks, not connected
by copper.

``RF`` joins the two centre pins and has no route. The substrate defines the
50 ohm microstrip ``MS_50`` (0.30 wide on L1); nothing applies it. See
``cl_launch_board.py`` for the placement.
"""

from cl_launch_board import LaunchBoard
from cl_parts import ClDesign


class RouteOneLayerDesign(ClDesign):
    circuit = LaunchBoard()
