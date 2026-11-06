"""Fixture for the qfn-thermal-vias case: the KSZ9031RNX PHY with its supplies joined
and its GND (L2) and 1V2 (L3) planes poured, before any layout near the part.

See ``cl_phy_board.py`` for the nets and planes.
"""

from cl_parts import ClDesign
from cl_phy_board import PhyBoard


class QfnThermalViasDesign(ClDesign):
    circuit = PhyBoard()
