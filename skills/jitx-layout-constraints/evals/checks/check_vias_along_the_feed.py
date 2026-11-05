"""Check for the vias-along-the-feed case.

Usage: check_vias_along_the_feed.py <output-dir>

Builds <output>/fixture_vias_along_the_feed.py, captures it, and checks the
antenna feed against values worked out from the prompt, the substrate and the
fab sheet:

- the feed is realized at CPWG_50's width, 0.30, with the layer-0 pour at its
  0.20 gap plus the runtime's 0.01, within [0.20, 0.23];
- the layer-0 pour is present on both sides of the feed;
- the vias are generated, not placed in code: the design still places
  exactly the fixture's six GND anchors. The generated vias are read with
  ``lc_check.generated_vias``, which does not say which rule made them. A
  stitch grid cannot stand in for the row: the feed rises 0.52 over 14.82
  (lc_radio_board.py), so a grid row parallel to the board's x axis stays
  inside the 0.08 band (0.44 to 0.52) for 0.08 / 0.0351 = 2.28 mm, 5 vias at
  most at the 0.500 fab floor pitch, against the 13 the row needs
  (fence_common);
- if both row bands are empty, the failure names the likely cause: a
  fence_via rule fences no route, a route fence comes from
  RoutingStructure.Layer.fence;
- on each side, the innermost fence row sits as close as the prompt allows:
  the via pad edge at the coplanar gap, CPWG_50's 0.20 clearance plus the
  runtime's 0.01 (0.21, measured on jitx 4.6), so the centre
  0.21 + 0.500 / 2 = 0.46 from the trace edge (fab row 11 via pad; fab row 4's
  0.100 space is smaller than the gap, so the gap governs), accepted up to
  0.50;
- that row holds floor(L / 1.0) sites on the straight run, less one allowed
  (fence_common), at the prompt's 1.0 mm pitch;
- no generated via pad sits in the coplanar gap: every pad edge is at least
  0.21 from the trace edge, less 0.005, half the 0.01 step between offsets
  (a 0.45 row puts the pad edge at 0.20, inside the gap).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fence_common as FC  # noqa: E402
import lc_check as L  # noqa: E402

WIDTH = 0.30
GAP = 0.20
COPLANAR_GAP = GAP + 0.01  # the structure's clearance plus 0.01, measured on jitx 4.6
PAD = 0.500
O1_MIN = COPLANAR_GAP + PAD / 2
O1_MAX = 0.50
PITCH = 1.0
ANCHORS = 6

out = L.output_dir()
with L.built(out, "fixture_vias_along_the_feed", "ViasAlongTheFeedDesign") as rd:
    feed = FC.measure(rd, rd.root.circuit.feed)
    placed = L.placed_vias(rd)
    print(f"code-placed vias: {len(placed)}")
    if len(placed) != ANCHORS:
        L.fail(f"{len(placed)} code-placed vias; the fixture has {ANCHORS}")
    if feed is not None:
        print(f"feed width {feed.width}, run length {feed.length:.3f}, generated vias {len(feed.vias)}")
        if abs(feed.width - WIDTH) > 1e-3:
            L.fail(f"feed width {feed.width}, not CPWG_50's {WIDTH}")
        g = FC.layer_gap(rd, feed, 0)
        if g is None or not (GAP - 1e-3 <= g <= GAP + 0.03):
            L.fail(f"layer-0 pour gap to the feed {g}, not CPWG_50's {GAP} (+0.01)")
        FC.pour_both_sides(rd, feed, 0, GAP + 0.05)
        if not feed.vias:
            L.fail(FC.NO_ROUTE_FENCE)
        else:
            n = FC.full_count(feed, PITCH)
            print(f"sites per side on the straight run: {n}")
            on_rows = 0
            for side in (1, -1):
                row = FC.straight_row(feed, side, O1_MIN - FC.ROW_TOL, O1_MAX + FC.ROW_TOL)
                on_rows += len(row)
                label = f"side {side} row within {O1_MIN:.2f} to {O1_MAX:.2f}"
                print(f"{label}: {len(row)} vias")
                if len(row) < n - 1:
                    L.fail(f"{label}: {len(row)} vias, fewer than {n} - 1")
                FC.check_pitch(row, PITCH, label)
            if on_rows == 0:
                L.fail(FC.NO_ROUTE_FENCE)
            near = min(v.edge for v in feed.vias)
            if near - PAD / 2 < COPLANAR_GAP - 0.005:
                L.fail(
                    f"a generated via pad edge sits {near - PAD / 2:.3f} from the trace, inside the {COPLANAR_GAP:.2f} gap"
                )
            else:
                L.ok(f"nearest generated via pad edge {near - PAD / 2:.3f} from the trace edge")
L.finish()
