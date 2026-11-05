"""Check for the fence-pour-outline case.

Usage: check_fence_pour_outline.py <output-dir>

Builds <output>/fixture_fence_pour_outline.py, captures it, and checks the
ring of ground vias around the L1 cavity pour, whose outline the prompt gives
(x -17 to 5, y -2 to 8, a 22 x 10 box):

- the ring is read from the generated vias (``lc_check.generated_vias``),
  which do not say which rule made them; only those within 1.5 of the cavity
  outline count. A route fence on the feed would also be generated, but the
  feed's nearest point is 3.0 from the outline (it ends at (2.00, 3.51),
  lc_radio_board.py), so it counts only if its rows reach 1.5 from the feed,
  which the prompt does not ask for. A stitch grid on the pour would count
  too, and no reader can split it from the ring: capture does not say which
  rule made a via;
- every via within 1.5 of the outline sits outside it, on the sides at the
  prompt's 0.5 from the outline and at the corners on the diagonal at
  0.5 * sqrt(2) = 0.707 (measured on jitx 4.6: the corner vias of an outward ring sit
  on the corner diagonals);
- the ring holds the derived count: the outline grown by 0.5 with square
  corners is 2 * (22 + 10) + 8 * 0.5 = 68 long, so 68 sites at the 1.0 pitch;
- the steps along the bottom side are the prompt's 1.0 pitch;
- the design still places exactly the fixture's six GND anchor vias.
"""

import math
import sys
from pathlib import Path

from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402

X0, Y0, X1, Y1 = -17.0, -2.0, 5.0, 8.0
OFFSET = 0.5
PITCH = 1.0
TOL = 0.02
ANCHORS = 6
CAVITY = box(X0, Y0, X1, Y1)
EXPECTED = math.floor((2 * ((X1 - X0) + (Y1 - Y0)) + 8 * OFFSET) / PITCH + 1e-9)

out = L.output_dir()
with L.built(out, "fixture_fence_pour_outline", "FencePourOutlineDesign") as rd:
    placed = L.placed_vias(rd)
    print(f"code-placed vias: {len(placed)}")
    if len(placed) != ANCHORS:
        L.fail(f"{len(placed)} code-placed vias; the fixture has {ANCHORS}")
    vias = L.generated_vias(rd)
    near = [(v, CAVITY.exterior.distance(Point(v)), CAVITY.contains(Point(v))) for v in vias]
    near = [n for n in near if n[1] <= 1.5]
    print(f"generated vias {len(vias)}, within 1.5 of the cavity outline {len(near)}")
    inside = [v for v, _, ins in near if ins]
    if inside:
        L.fail(f"{len(inside)} ring vias inside the outline, e.g. {inside[:3]}; the prompt asks for outside")
    ring = [v for v, d, ins in near if not ins and (abs(d - OFFSET) <= TOL or abs(d - OFFSET * math.sqrt(2)) <= TOL)]
    other = [(v, round(d, 3)) for v, d, ins in near if not ins and v not in ring]
    print(f"ring vias at {OFFSET} (sides) or {OFFSET * math.sqrt(2):.3f} (corners): {len(ring)}; derived {EXPECTED}")
    if other:
        L.fail(f"{len(other)} vias near the outline at other distances, e.g. {other[:3]}")
    if len(ring) < EXPECTED:
        L.fail(f"ring holds {len(ring)} vias, fewer than the derived {EXPECTED}")
    elif not other and not inside:
        L.ok(f"ring of {len(ring)} vias at {OFFSET} outside the outline")
    bottom = sorted(v[0] for v in ring if abs(v[1] - (Y0 - OFFSET)) <= TOL)
    steps = [b - a for a, b in zip(bottom, bottom[1:])]
    if steps and any(abs(s - PITCH) > 0.05 * PITCH for s in steps):
        L.fail(f"bottom-side steps {sorted({round(s, 3) for s in steps})} differ from the {PITCH} pitch")
    elif steps:
        L.ok(f"bottom side: {len(bottom)} vias, steps {min(steps):.3f} to {max(steps):.3f}")
L.finish()
