"""Minimal direct-connect candidates for JITX 4.4 capture and ODB++ checks."""

from importlib import import_module
from typing import Any, cast

from jitx import (
    Board,
    Circuit,
    Component,
    Design,
    Landpattern,
    Net,
    Pad,
    PadMapping,
    Port,
    Pour,
)
from jitx.constraints import IsPad, Tag, design_constraint
from jitx.shapes.composites import rectangle
from jitx.shapes.primitive import Circle
from jitxlib.symbols.box import BoxSymbol

JLC04161H_7628 = cast(Any, import_module("jitxlib.jlcpcb")).JLC04161H_7628
JLCPCBRules = cast(Any, import_module("jitxlib.jlcpcb.rules")).JLCPCBRules


TEST_PAD_DIAMETER = 1.6  # skill default: 1.6 mm test-pad diameter
DEFAULT_THERMAL_GAP = JLCPCBRules.min_copper_copper_space  # JLCPCBRules clearance field
BOARD_WIDTH = 12.0  # skill default: 12.0 mm test-board width
BOARD_HEIGHT = 8.0  # skill default: 8.0 mm test-board height
POUR_WIDTH = 10.0  # skill default: 10.0 mm test-pour width
POUR_HEIGHT = 6.0  # skill default: 6.0 mm test-pour height
DEFAULT_THERMAL_SPOKE_WIDTH = 0.2  # skill default: 0.2 mm spoke width
DEFAULT_THERMAL_SPOKE_COUNT = 4  # skill default: 4 thermal spokes
WIDE_SPOKE_COUNT = 4  # skill default: 4 overlapping wide spokes


class DirectConnectTag(Tag):
    """Marks the pad whose default thermal relief is under test."""


class TestPad(Pad):
    shape = Circle(diameter=TEST_PAD_DIAMETER)


class TestLandpattern(Landpattern):
    thermal_pad = TestPad().at(-2.5, 0)
    tagged_pad = TestPad().at(2.5, 0)


class TestComponent(Component):
    reference_designator_prefix = "TP"
    GND = Port()
    landpattern = TestLandpattern()
    symbol = BoxSymbol()

    def __init__(self) -> None:
        self.mappings = [
            PadMapping(
                {
                    self.GND: [
                        self.landpattern.thermal_pad,
                        self.landpattern.tagged_pad,
                    ]
                }
            )
        ]


class TestBoard(Board):
    shape = rectangle(BOARD_WIDTH, BOARD_HEIGHT)


class TestCircuit(Circuit):
    GND = Net(name="GND")
    test = TestComponent().at(0, 0)
    ground_pour = Pour(rectangle(POUR_WIDTH, POUR_HEIGHT), layer=0)

    def __init__(self) -> None:
        self.GND += self.test.GND
        self.GND += self.ground_pour
        DirectConnectTag().assign(self.test.landpattern.tagged_pad)


class DirectConnectNoEffectDesign(Design):
    """Candidate 1: a higher-priority tagged unary rule with no effect."""

    substrate = JLC04161H_7628()
    board = TestBoard()
    circuit = TestCircuit()

    def __init__(self) -> None:
        self.rules = [
            design_constraint(IsPad).thermal_relief(
                DEFAULT_THERMAL_GAP,
                DEFAULT_THERMAL_SPOKE_WIDTH,
                DEFAULT_THERMAL_SPOKE_COUNT,
            ),
            design_constraint(DirectConnectTag(), priority=1),
        ]


class DirectConnectWideSpokeDesign(Design):
    """Candidate 2: minimum-gap relief with pad-wide overlapping spokes."""

    substrate = JLC04161H_7628()
    board = TestBoard()
    circuit = TestCircuit()

    def __init__(self) -> None:
        self.rules = [
            design_constraint(IsPad).thermal_relief(
                DEFAULT_THERMAL_GAP,
                DEFAULT_THERMAL_SPOKE_WIDTH,
                DEFAULT_THERMAL_SPOKE_COUNT,
            ),
            design_constraint(DirectConnectTag(), priority=1).thermal_relief(
                JLCPCBRules.min_copper_copper_space,
                TEST_PAD_DIAMETER,
                WIDE_SPOKE_COUNT,
            ),
        ]
