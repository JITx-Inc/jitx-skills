"""Fixture for the unreachable-destination case: two edge SMA jacks, the
right one's centre pad walled in on L1.

``RF`` joins the two centre pins and has no route. A ring of ground vias,
0.75 apart, stands 3 mm around ``j2``'s centre pad, open only at the board
edge, and a layer-0 route keepout covers the ring's band. See
``cl_launch_board.py`` for the placement.
"""

from cl_launch_board import LaunchBoard
from cl_parts import ClDesign


class UnreachableDestinationDesign(ClDesign):
    circuit = LaunchBoard(j2_fenced=True)
