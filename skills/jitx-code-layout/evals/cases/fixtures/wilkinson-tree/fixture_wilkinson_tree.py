"""Fixture for the wilkinson-tree case: a 1:4 Wilkinson divider tree, wired,
with no geometry.

The board is 90 x 100 mm, centred on the origin, on the Pellingham
``ClStandard4`` stackup. ``WkSubstrate`` adds one structure to it:
``ARM_71``, the 70.7 ohm divider arm on L1, 0.17 wide with the same
velocity as the substrate's other L1 structures (1.6e11 mm/s). The fenced
line is the substrate's ``CPWG_50_FENCED`` (0.30 trace, 0.20 clearance, two
rows of ``ThVia`` fence each side). Neither is applied to a net.

Parts:

- ``IsoResistor100``: a fictional 100 ohm isolation resistor, two 0.8 mm
  square pads 1.6 mm apart centre to centre (pins ``p1`` and ``p2``). Not a
  real product.
- The Würth WR-SMA end launch jack ``60312202114514`` from jitxexamples
  (py-components e6bf1cb). Its land pattern's origin is the body face, on
  the board edge, with +x running into the board along the centre pad
  (0.61 wide, 1.97 long).

Circuits:

- ``WilkinsonCell``: one 1:2 divider. Ports ``sig_in``, ``sig_out_a``,
  ``sig_out_b`` and ``GND``; the isolation resistor ``iso`` between the two
  output nets (``p1`` on ``out_a``, ``p2`` on ``out_b``). No position, no
  copper, no port pads.
- ``WilkinsonTree``: three cells, ``first`` feeding ``second[0]`` (from
  ``sig_out_a``) and ``second[1]`` (from ``sig_out_b``). Ports ``rf_in``,
  ``rf_out[0..3]`` (``second[0]`` a and b, then ``second[1]`` a and b) and
  ``GND``. No positions.
- ``WilkinsonBoard``: the tree, the input jack ``j_in`` on the left edge at
  (-45, -3), and the four output jacks ``j_out[0..3]`` on the right edge at
  y = -37.5, -12.5, 12.5 and 37.5 (25 mm apart), turned 180 degrees, with
  ``j_out[k]`` joined to ``rf_out[k]``. It carries the matching: each output
  path's delay within 1.0 ps of output 0's
  (``ConstrainReferenceDifference``).
"""

from jitx.board import Board
from jitx.circuit import Circuit
from jitx.component import Component
from jitx.design import Design
from jitx.feature import Courtyard, Soldermask
from jitx.landpattern import Landpattern, Pad
from jitx.net import Net, Port, Topology
from jitx.shapes.composites import rectangle
from jitx.si import ConstrainReferenceDifference, RoutingStructure
from jitx.units import ohm
from jitxlib.symbols.box import BoxSymbol

from jitxexamples.components.connectors.wurth_elektronik_60312202114514 import (
    Wurth60312202114514,
)

from cl_substrate import ClStandard4

BOARD_W = 90.0
BOARD_H = 100.0
OUTPUT_YS = (-37.5, -12.5, 12.5, 37.5)
INPUT_Y = -3.0
TIMING_TOLERANCE = 1.0e-12


class WkSubstrate(ClStandard4):
    """``ClStandard4`` with the divider arm structure."""

    # 70.7 ohm divider arm on L1 over the L2 ground. The impedance is a label
    # on the width, as on the substrate's other structures.
    ARM_71 = RoutingStructure(
        name="ARM_71",
        impedance=70.7 * ohm,
        layers={
            0: RoutingStructure.Layer(
                trace_width=0.17,
                clearance=0.20,
                velocity=1.6e11,
                insertion_loss=0.03,
            ),
        },
    )


class WkBoard(Board):
    shape = rectangle(BOARD_W, BOARD_H)


class IsoPad(Pad):
    shape = rectangle(0.8, 0.8)
    soldermask = Soldermask(shape)


class IsoPads(Landpattern):
    def __init__(self) -> None:
        self.p1 = IsoPad().at(-0.8, 0.0)
        self.p2 = IsoPad().at(0.8, 0.0)
        self.courtyard = Courtyard(rectangle(2.8, 1.4))


class IsoResistor100(Component):
    """Fictional 100 ohm isolation resistor. Not a real product."""

    manufacturer = "Fictional"
    mpn = "CL-EVAL-ISO100"
    reference_designator_prefix = "R"

    p1 = Port()
    p2 = Port()

    def __init__(self) -> None:
        self.landpattern = IsoPads()
        self.symbol = BoxSymbol()


class WilkinsonCell(Circuit):
    """One 1:2 divider: ports and the isolation resistor, no geometry."""

    sig_in = Port()
    sig_out_a = Port()
    sig_out_b = Port()
    GND = Port()

    def __init__(self) -> None:
        self.iso = IsoResistor100()
        self.line_in = Net([self.sig_in])
        self.out_a = Net([self.sig_out_a, self.iso.p1])
        self.out_b = Net([self.sig_out_b, self.iso.p2])


class WilkinsonTree(Circuit):
    """Three cells as a 1:4 tree, one feeding two."""

    rf_in = Port()
    rf_out = [Port() for _ in range(4)]
    GND = Port()

    def __init__(self) -> None:
        self.first = WilkinsonCell()
        self.second = [WilkinsonCell(), WilkinsonCell()]
        self.ground = Net([self.GND, self.first.GND] + [c.GND for c in self.second])
        self.feed = Net([self.rf_in, self.first.sig_in])
        self.joins = [
            Net([self.first.sig_out_a, self.second[0].sig_in]),
            Net([self.first.sig_out_b, self.second[1].sig_in]),
        ]
        cell_outs = [p for c in self.second for p in (c.sig_out_a, c.sig_out_b)]
        self.outs = [Net([o, p]) for o, p in zip(self.rf_out, cell_outs, strict=True)]


class WilkinsonBoard(Circuit):
    """The tree between one input jack and four output jacks."""

    def __init__(self) -> None:
        self.tree = WilkinsonTree()
        self.j_in = Wurth60312202114514().at(-BOARD_W / 2, INPUT_Y)
        self.j_out = [Wurth60312202114514().at(BOARD_W / 2, y, rotate=180) for y in OUTPUT_YS]
        self.GND = Net([self.tree.GND, self.j_in.gnd] + [j.gnd for j in self.j_out], name="GND")
        self.RF_IN = Net([self.j_in.sig, self.tree.rf_in], name="RF_IN")
        self.RF_OUT = [
            Net([j.sig, o], name=f"RF_OUT{k}") for k, (j, o) in enumerate(zip(self.j_out, self.tree.rf_out, strict=True))
        ]
        paths = [Topology(self.j_in.sig, j.sig) for j in self.j_out]
        self.matching = ConstrainReferenceDifference(paths[0], paths[1:]).timing_difference(TIMING_TOLERANCE)


class WilkinsonTreeDesign(Design):
    substrate = WkSubstrate()
    board = WkBoard()
    circuit = WilkinsonBoard()
