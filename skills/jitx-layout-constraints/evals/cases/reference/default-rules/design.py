"""Reference design for the scope of a rule stored on a child Circuit.

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
    design_constraint,
)
from jitx.shapes.composites import rectangle
from jitxlib.jlcpcb import JLC04161H_7628
from jitxlib.landpatterns.twopin.smt import SMT
from jitxlib.symbols.resistor import ResistorSymbol

TOP_LAYER = 0  # JLC04161H_7628 top conductor index, jitxlib/jlcpcb/JLC04161H_7628.py:27
DEFAULT_TRACE_WIDTH = 0.12  # skill default: 0.12 mm default trace width
CHILD_RULE_WIDTH = 0.30  # skill test value: 0.30 mm child-declared trace width
POWER_WIDTH = 0.20  # skill default: 0.20 mm power and ground trace width
THERMAL_SPOKE_WIDTH = 0.20  # skill default: 0.20 mm thermal spoke width
THERMAL_SPOKE_COUNT = 4  # skill default: 4 thermal spokes
WIDTH_TOLERANCE = 0.001  # skill test tolerance: 0.001 mm


class SpanningTag(Tag):
    """A tag assigned to the named net that spans both child circuits."""


class PowerTag(Tag):
    """Power-net class used by the fourth board default."""


class GroundTag(Tag):
    """Ground-net class used by the fourth board default."""


class ProbeBoard(Board):
    shape = rectangle(24.0, 14.0)  # skill test board: 24.0 mm width, 14.0 mm height


class ProbeTerminal(Component):
    """A placed library landpattern pad used as a route endpoint."""

    route_pad = Port()
    unused = Port()
    landpattern = SMT("0402")
    symbol = ResistorSymbol()
    reference_designator_prefix = "TP"


class RoutedChild(Circuit):
    bus = Port()

    def __init__(self):
        left_x = -7.0  # skill test geometry: -7.0 mm x coordinate
        right_x = 7.0  # skill test geometry: 7.0 mm x coordinate
        self.start = ProbeTerminal().at(left_x, 0.0)
        self.end = RoutePoint(layer=TOP_LAYER).at(right_x, 0.0)
        self.start.unused.no_connect()
        self.local_net = Net([self.bus, self.start.route_pad, self.end.port])
        self.routes = [
            Route(
                self.start.route_pad,
                self.end.pad,
                layer=TOP_LAYER,
                sketch=[(left_x, 0.0), (right_x, 0.0)],
            )
        ]


class RuleOwner(RoutedChild):
    def __init__(self):
        super().__init__()
        self.width_rule = design_constraint(SpanningTag(), priority=2).trace_width(
            CHILD_RULE_WIDTH
        )


class Sibling(RoutedChild):
    pass


class TopCircuit(Circuit):
    def __init__(self):
        child_offset = 2.0  # skill test geometry: 2.0 mm from board center
        self.rule_owner = RuleOwner().at(0.0, child_offset)
        self.sibling = Sibling().at(0.0, -child_offset)
        self.spanning_net = Net(
            [self.rule_owner.bus, self.sibling.bus],
            name="SPAN",
        )
        Tags(SpanningTag()).assign(self.spanning_net)


class DefaultRulesDesign(Design):
    substrate = JLC04161H_7628()
    board = ProbeBoard()
    circuit = TopCircuit()

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
                POWER_WIDTH
            ),
        ]
