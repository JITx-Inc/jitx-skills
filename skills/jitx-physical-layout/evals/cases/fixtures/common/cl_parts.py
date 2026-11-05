"""Fictional parts and the Design base for the code-layout eval fixtures.

The fixtures use jitxexamples parts where a real one fits (the Würth WR-SMA
end launch, the Microchip KSZ9031RNX, the generic hex-grid BGA). The parts
here are fictional and not orderable: plain square pads for the cases that
test a route between two points and nothing about the part.
"""

from jitx.design import Design
from jitx.component import Component
from jitx.feature import Courtyard, Soldermask
from jitx.landpattern import Landpattern, Pad
from jitx.net import DiffPair, Port
from jitx.shapes.composites import rectangle
from jitxlib.symbols.box import BoxSymbol

from cl_substrate import ClBoard, ClStandard4

PAD = 0.6
"""Side of the fictional parts' square pads, in mm."""

PAIR_PITCH = 1.0
"""Centre-to-centre spacing of a fictional pair chip's two pads, in mm."""

STAGGER = 2.0
"""How far the staggered chip's ``p`` pad sits behind its ``n`` pad, in mm."""


class SquarePad(Pad):
    """A ``PAD`` mm square SMD pad, mask opening the same size."""

    shape = rectangle(PAD, PAD)
    soldermask = Soldermask(shape)


class OnePad(Landpattern):
    def __init__(self) -> None:
        self.pad = SquarePad()
        self.courtyard = Courtyard(rectangle(1.2, 1.2))


class PairPads(Landpattern):
    """``p`` below ``n``, ``PAIR_PITCH`` apart on y."""

    def __init__(self, stagger: float = 0.0) -> None:
        self.p_pad = SquarePad().at(-stagger, -PAIR_PITCH / 2)
        self.n_pad = SquarePad().at(0.0, PAIR_PITCH / 2)
        self.courtyard = Courtyard(rectangle(1.2 + stagger, 2.2).at(-stagger / 2, 0.0))


class PadChip(Component):
    """Fictional one-pin chip, pin ``io``. Not a real product."""

    manufacturer = "Fictional"
    mpn = "CL-EVAL-1PIN"
    reference_designator_prefix = "U"

    io = Port()

    def __init__(self) -> None:
        self.landpattern = OnePad()
        self.symbol = BoxSymbol()


class PairChip(Component):
    """Fictional chip with one differential pair, ``d``. Not a real product."""

    manufacturer = "Fictional"
    mpn = "CL-EVAL-1PAIR"
    reference_designator_prefix = "U"

    d = DiffPair()

    def __init__(self) -> None:
        self.landpattern = PairPads()
        self.symbol = BoxSymbol()


class StaggeredPairChip(Component):
    """Fictional chip whose ``p`` pad sits ``STAGGER`` mm behind its ``n``
    pad (towards -x), so a pair leaving it towards +x starts with ``n``
    shorter than ``p``. Not a real product."""

    manufacturer = "Fictional"
    mpn = "CL-EVAL-1PAIR-STAGGERED"
    reference_designator_prefix = "U"

    d = DiffPair()

    def __init__(self) -> None:
        self.landpattern = PairPads(stagger=STAGGER)
        self.symbol = BoxSymbol()


class ClDesign(Design):
    """Base for every fixture Design: the substrate and the board. The
    circuit comes from the fixture."""

    substrate = ClStandard4()
    board = ClBoard()
