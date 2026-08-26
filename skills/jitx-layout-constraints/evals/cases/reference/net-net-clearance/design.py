"""Reference designs for net-to-net clearance and fabrication-floor behavior.

API claims are checked against ``jitx/constraints.py:71``,
``jitx/constraints.py:910``, ``jitx/constraints.py:1160``, and
``jitx/substrate.py:161`` in the installed JITX package.
"""

from jitx import Board, Circuit, Component, Design, Net, Port, RoutePoint
from jitx.circuit import Route
from jitx.constraints import (
    BinaryDesignConstraint,
    IsCopper,
    IsPad,
    IsTrace,
    Tag,
    Tags,
    UnaryDesignConstraint,
)
from jitx.shapes.composites import rectangle
from jitxlib.jlcpcb import JLC04161H_7628
from jitxlib.landpatterns.twopin.smt import SMT
from jitxlib.symbols.resistor import ResistorSymbol

TOP_LAYER = 0  # JLC04161H_7628 top conductor index, jitxlib/jlcpcb/JLC04161H_7628.py:27
DEFAULT_TRACE_WIDTH = 0.20  # skill default: 0.20 mm trace width
DEFAULT_TAGGED_WIDTH = 0.20  # skill default: 0.20 mm tagged power and ground width
THERMAL_SPOKE_WIDTH = 0.20  # skill default: 0.20 mm thermal spoke width
THERMAL_SPOKE_COUNT = 4  # skill default: 4 thermal spokes
WIDTH_TOLERANCE = 0.001  # skill test tolerance: 0.001 mm
EXAMPLE_CLEARANCE = (
    0.25  # skill example: 0.25 mm above JLCPCBRules.min_copper_copper_space
)
BELOW_FLOOR_CLEARANCE = (
    0.05  # skill test value: 0.05 mm below JLCPCBRules.min_copper_copper_space
)


class PowerTag(Tag):
    """Power-net class for the clearance probe."""


class GroundTag(Tag):
    """Ground-net class for the clearance probe."""


class ProbeBoard(Board):
    shape = rectangle(24.0, 12.0)  # skill test board: 24.0 mm width, 12.0 mm height


class ProbeTerminal(Component):
    """A placed library landpattern pad used as a route endpoint."""

    route_pad = Port()
    unused = Port()
    landpattern = SMT("0402")
    symbol = ResistorSymbol()
    reference_designator_prefix = "TP"


class ParallelRoutes(Circuit):
    """Two pad-to-point routes whose sketches converge side by side."""

    middle_offset = 0.10  # skill test geometry: 0.10 mm from centerline

    def __init__(self):
        endpoint_offset = 1.50  # skill test geometry: 1.50 mm from centerline
        left_x = -8.0  # skill test geometry: -8.0 mm x coordinate
        right_x = 8.0  # skill test geometry: 8.0 mm x coordinate
        turn_x = 2.0  # skill test geometry: 2.0 mm from board center

        self.power_pad = ProbeTerminal().at(left_x, endpoint_offset)
        self.power_point = RoutePoint(layer=TOP_LAYER).at(right_x, endpoint_offset)
        self.ground_pad = ProbeTerminal().at(left_x, -endpoint_offset)
        self.ground_point = RoutePoint(layer=TOP_LAYER).at(right_x, -endpoint_offset)
        self.power_pad.unused.no_connect()
        self.ground_pad.unused.no_connect()

        self.power = Net(
            [self.power_pad.route_pad, self.power_point.port],
            name="POWER",
        )
        self.ground = Net(
            [self.ground_pad.route_pad, self.ground_point.port],
            name="GROUND",
        )
        Tags(PowerTag()).assign(self.power)
        Tags(GroundTag()).assign(self.ground)

        power_route = Route(
            self.power_pad.route_pad,
            self.power_point.pad,
            layer=TOP_LAYER,
            sketch=[
                (left_x, endpoint_offset),
                (-turn_x, self.middle_offset),
                (turn_x, self.middle_offset),
                (right_x, endpoint_offset),
            ],
        )
        ground_route = Route(
            self.ground_pad.route_pad,
            self.ground_point.pad,
            layer=TOP_LAYER,
            sketch=[
                (left_x, -endpoint_offset),
                (-turn_x, -self.middle_offset),
                (turn_x, -self.middle_offset),
                (right_x, -endpoint_offset),
            ],
        )
        self.routes = [power_route, ground_route]


class BelowFloorParallelRoutes(ParallelRoutes):
    middle_offset = 0.03  # skill test geometry: 0.03 mm from centerline


class _ClearanceDesign(Design):
    substrate = JLC04161H_7628()
    board = ProbeBoard()
    requested_clearance: float

    def __init__(self):
        fab = self.substrate.constraints
        self.rules = [
            UnaryDesignConstraint(IsTrace).trace_width(DEFAULT_TRACE_WIDTH),
            BinaryDesignConstraint(IsCopper, IsCopper).clearance(
                fab.min_copper_copper_space
            ),
            UnaryDesignConstraint(IsPad).thermal_relief(
                fab.min_copper_copper_space,
                THERMAL_SPOKE_WIDTH,
                THERMAL_SPOKE_COUNT,
            ),
            UnaryDesignConstraint(PowerTag() | GroundTag(), priority=1).trace_width(
                DEFAULT_TAGGED_WIDTH
            ),
            BinaryDesignConstraint(PowerTag(), GroundTag(), priority=2).clearance(
                self.requested_clearance
            ),
        ]


class NetNetClearanceDesign(_ClearanceDesign):
    """The skill example clearance above the fabrication floor."""

    circuit = ParallelRoutes()
    requested_clearance = EXAMPLE_CLEARANCE


class BelowFloorClearanceDesign(_ClearanceDesign):
    """A clearance request intentionally below the fabrication floor."""

    circuit = BelowFloorParallelRoutes()
    requested_clearance = BELOW_FLOOR_CLEARANCE
