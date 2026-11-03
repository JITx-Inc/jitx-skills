"""Check for the edge-and-isolation-slot case.

Usage: check_edge_and_isolation_slot.py <output-dir>

Builds <output>/fixture_edge_and_isolation_slot.py, captures it, and measures
each GND pour's computed copper on layers 0 to 3 against the prompt:

- 1.0 from the outer edge of the 40 x 30 board;
- 1.5 from the slot at x 11.5..12.5, y -5..5.

Spike S7 measured pour pullback at the rule's value plus at most 0.01 for
both IsBoardEdge and IsHole rules, so each gap must lie in [value, value +
0.03]. S7: IsBoardEdge covers the outer edge only; a slot needs IsHole (which
covers cutouts, outline holes and via drills).
"""

import sys
from pathlib import Path

from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402

EDGE = 1.0
SLOT = 1.5
BOARD = box(-20.0, -15.0, 20.0, 15.0)
SLOT_BOX = box(11.5, -5.0, 12.5, 5.0)


def within(label: str, got: float, want: float) -> None:
    if want - 1e-3 <= got <= want + 0.03:
        L.ok(f"{label} {got}")
    else:
        L.fail(f"{label} {got}, expected {want} (+0.01)")


out = L.output_dir()
with L.built(out, "fixture_edge_and_isolation_slot", "EdgeAndIsolationSlotDesign") as rd:
    pours = [(p.layer, g) for _, p, g in L.world_pours(rd)]
    if sorted(layer for layer, g in pours if not g.is_empty) != [0, 1, 2, 3]:
        L.fail("expected one GND pour with copper on each of layers 0 to 3")
    for layer, g in pours:
        if g.is_empty:
            continue
        within(f"layer {layer} pour to the board edge", L.gap(g, BOARD.exterior), EDGE)
        within(f"layer {layer} pour to the slot", L.gap(g, SLOT_BOX), SLOT)
L.finish()
