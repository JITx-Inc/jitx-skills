"""Reference designs for stitch-via class discovery on JITX 4.4.

Each design applies one unary rule to the same tagged ground pour. The via
definition is reached through the predefined substrate's mixin, declared as a
direct nested attribute of a substrate subclass, or declared at module scope.
The rule and its condition remain structural attributes under each Design, as
required by the traversal at ``jitx/_translate/design.py:187``.
"""

from __future__ import annotations

from jitx import Circuit, Net, Pour
from jitx.board import Board
from jitx.constraints import SquareViaStitchGrid, Tag, design_constraint
from jitx.design import Design
from jitx.shapes.composites import rectangle
from jitxlib.jlcpcb import JLC04161H_7628

BOARD_SIZE = 12.0  # skill default: 12.0 mm board width and height for this probe.
POUR_SIZE = 8.0  # skill default: 8.0 mm pour width and height for this probe.
STITCH_PITCH = 2.0  # skill default: 2.0 mm stitch-via center pitch.
STITCH_INSET = 0.5  # skill default: 0.5 mm boundary-to-center inset.
EDGE_SPACE = JLC04161H_7628.constraints.min_copper_edge_space


class GndPourTag(Tag):
    """Marks the ground pour selected by the stitch rule."""


class StitchBoard(Board):
    shape = rectangle(BOARD_SIZE, BOARD_SIZE)
    signal_area = rectangle(
        BOARD_SIZE - 2.0 * EDGE_SPACE,
        BOARD_SIZE - 2.0 * EDGE_SPACE,
    )


class StitchCircuit(Circuit):
    def __init__(self) -> None:
        self.GND = Net(name="GND")
        self.gnd_pour = Pour(rectangle(POUR_SIZE, POUR_SIZE), layer=0)
        self.GND += self.gnd_pour
        GndPourTag().assign(self.gnd_pour)


class DirectAttributeSubstrate(JLC04161H_7628):
    DirectStitchVia = JLC04161H_7628.StdViaPreferred
    """The mixin's same via class, re-declared as a direct attribute."""


class ModuleScopeStitchVia(JLC04161H_7628.StdViaPreferred):
    """The same mixin via geometry, declared as a module-scope Via subclass."""

    name = "Module Scope Stitch Via"


class MixinViaDesign(Design):
    board = StitchBoard()
    substrate = JLC04161H_7628()
    circuit = StitchCircuit()

    def __init__(self) -> None:
        self.rules = [
            design_constraint(GndPourTag()).stitch_via(
                JLC04161H_7628.StdViaPreferred,
                SquareViaStitchGrid(pitch=STITCH_PITCH, inset=STITCH_INSET),
            )
        ]


class DirectAttributeViaDesign(Design):
    board = StitchBoard()
    substrate = DirectAttributeSubstrate()
    circuit = StitchCircuit()

    def __init__(self) -> None:
        self.rules = [
            design_constraint(GndPourTag()).stitch_via(
                DirectAttributeSubstrate.DirectStitchVia,
                SquareViaStitchGrid(pitch=STITCH_PITCH, inset=STITCH_INSET),
            )
        ]


class ModuleScopeViaDesign(Design):
    board = StitchBoard()
    substrate = JLC04161H_7628()
    circuit = StitchCircuit()

    def __init__(self) -> None:
        self.rules = [
            design_constraint(GndPourTag()).stitch_via(
                ModuleScopeStitchVia,
                SquareViaStitchGrid(pitch=STITCH_PITCH, inset=STITCH_INSET),
            )
        ]
