"""Reference design for the build-outputs case: what ``jitx build`` writes.

A top circuit holds one fixture part and a child circuit holding two more, so
the build output has a net at each level of the hierarchy. Every part is a
fictional fixture, not a real product.
"""

from jitx.circuit import Circuit
from jitx.component import Component
from jitx.feature import Courtyard, Soldermask
from jitx.landpattern import Landpattern, Pad
from jitx.net import Net, Port
from jitx.sample import SampleDesign
from jitx.shapes.composites import rectangle
from jitx.symbol import Direction, Pin, Symbol

FIXTURE_MPN = "FIXTURE-2P-0001"


class SquarePad(Pad):
    shape = rectangle(0.6, 0.6)
    soldermask = Soldermask(shape)


class TwoPadLandpattern(Landpattern):
    def __init__(self) -> None:
        self.pads = [SquarePad().at(-0.75, 0), SquarePad().at(0.75, 0)]
        self.courtyard = Courtyard(rectangle(2.5, 1.2))


class TwoPinSymbol(Symbol):
    def __init__(self) -> None:
        self.pins = [
            Pin(at=(-1, 0), length=1, direction=Direction.Left),
            Pin(at=(1, 0), length=1, direction=Direction.Right),
        ]
        self.body = rectangle(2, 1)


class FixtureTwoPin(Component):
    """Fictional two-pin part. Not a real product."""

    mpn = FIXTURE_MPN
    manufacturer = "Fixture"
    reference_designator_prefix = "U"
    a = Port()
    b = Port()

    def __init__(self) -> None:
        self.landpattern = TwoPadLandpattern()
        self.symbol = TwoPinSymbol()


class Stage(Circuit):
    """Two parts in series; ``out`` is the boundary port."""

    out = Port()

    def __init__(self) -> None:
        self.first = FixtureTwoPin().at(-2, 0)
        self.second = FixtureTwoPin().at(2, 0)
        self.MID = self.first.b + self.second.a
        self.OUT = self.out + self.second.b


class Top(Circuit):
    def __init__(self) -> None:
        self.stage = Stage()
        self.load = FixtureTwoPin().at(0, 5)
        self.LINK = Net([self.stage.out, self.load.a], name="LINK")


class BuildOutputsDesign(SampleDesign):
    def __init__(self) -> None:
        self.circuit = Top()
