"""Placement and parts helpers shared by the layout-constraints eval fixtures.

Not a design rule and not part of any answer: it parks every component a
fixture does not place by hand in rows inside a strip of the board, so the
build is the same every time and parked parts stay out of the copper the case
measures.
"""

from jitx.circuit import Circuit
from jitx.component import Component
from jitx.inspect import visit
from jitx.transform import Transform
from jitx.design import Design
from jitxlib.parts import CapacitorQuery, InductorQuery, ResistorQuery
from jitxlib.parts.provider import PartSource
from jitxlib.parts.providers.csv_parts import CsvParts

# The parts chain every fixture Design names: the jitxexamples example
# catalogue (as py-components configures it), then non-orderable ideal parts.
LC_PARTS = PartSource(
    [CsvParts(path="parts/example-passives.csv", package="jitxexamples"), "ideal"],
    label="lc-eval",
)


class LcDesign(Design):
    """Base for every fixture Design: the parts chain and the query defaults
    (the smallest package the assembler places, as the JS2 kit design states
    them). Substrate, board and circuit come from the fixture."""

    parts = LC_PARTS
    resistor_defaults = ResistorQuery(case=["0402", "0603", "0805", "1206"])
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805", "1206", "1210"])
    inductor_defaults = InductorQuery()


def park(
    circuit: Circuit,
    placed: list[Component],
    x0: float,
    x1: float,
    y: float,
    pitch: float = 3.0,
    row_step: float = -3.0,
) -> int:
    """Place every component under ``circuit`` that is not in ``placed`` in
    rows from ``(x0, y)`` rightwards to ``x1``, then on rows ``row_step``
    apart. Returns the number of components parked."""
    skip = {id(c) for c in placed}
    x, row_y, n = x0, y, 0
    for _, comp in visit(circuit, Component):
        if id(comp) in skip:
            continue
        circuit.place(comp, Transform.translate(x, row_y))
        n += 1
        x += pitch
        if x > x1:
            x = x0
            row_y += row_step
    return n
