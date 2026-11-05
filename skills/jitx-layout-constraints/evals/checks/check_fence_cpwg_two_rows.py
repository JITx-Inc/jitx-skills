"""Check for the fence-cpwg-two-rows case.

Usage: check_fence_cpwg_two_rows.py <output-dir>

Builds <output>/fixture_fence_cpwg_two_rows.py, captures it, and checks the
antenna feed against values worked out from the prompt, the substrate and the
fab sheet:

- the feed is realized at CPWG_50's width, 0.30 (lc_substrate.py);
- the layer-0 pour sits at CPWG_50's gap, 0.20, plus the 0.01 the runtime
  adds, so within [0.20, 0.23]: a wider net clearance would push
  the coplanar ground out;
- the layer-0 pour is present on both sides of the feed;
- generated vias exist (``lc_check.generated_vias``, which does not say
  which rule made them). A stitch grid cannot stand in for a row: the feed
  rises 0.52 over 14.82 (lc_radio_board.py), so a grid row parallel to the
  board's x axis stays inside a 0.04 row band for 0.04 / 0.0351 = 1.14 mm,
  3 vias at most at the 0.500 fab floor pitch, against the 13 a row needs
  (fence_common);
- if every row band is empty, the failure names the likely cause: a
  fence_via rule fences no route, a route fence comes from
  RoutingStructure.Layer.fence;
- two rows per side at 0.35 + 0.500 / 2 = 0.60 mm (prompt's pad-edge spacing,
  via pad from fab row 11) and 0.60 + 0.60 = 1.20 mm from the trace edge to
  the via centre, each with floor(L / 1.0) sites on the straight run, less one
  allowed per row and at least one full row per side (fence_common);
- the steps along each row are the prompt's 1.0 mm pitch;
- no generated via pad sits in the coplanar gap: edge distance minus 0.250 is at
  least 0.20;
- the design still places exactly the six GND anchor vias of the fixture
  (lc_radio_board.py), so no via was placed in code.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fence_common as FC  # noqa: E402
import lc_check as L  # noqa: E402

WIDTH = 0.30
GAP = 0.20
PAD = 0.500
O1 = 0.35 + PAD / 2
O = 0.60
PITCH = 1.0
ANCHORS = 6

out = L.output_dir()
with L.built(out, "fixture_fence_cpwg_two_rows", "FenceCpwgTwoRowsDesign") as rd:
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
            print(f"sites per row per side on the straight run: {n}")
            on_rows = 0
            for side in (1, -1):
                counts = []
                for k in (1, 2):
                    target = O1 + (k - 1) * O
                    row = FC.straight_row(feed, side, target - FC.ROW_TOL, target + FC.ROW_TOL)
                    counts.append(len(row))
                    on_rows += len(row)
                    label = f"side {side} row {k} at {target:.2f}"
                    print(f"{label}: {len(row)} vias")
                    if len(row) < n - 1:
                        L.fail(f"{label}: {len(row)} vias, fewer than {n} - 1")
                    FC.check_pitch(row, PITCH, label)
                if max(counts) < n:
                    L.fail(f"side {side}: no row holds all {n} sites")
            if on_rows == 0:
                L.fail(FC.NO_ROUTE_FENCE)
            near = min(v.edge for v in feed.vias)
            if near - PAD / 2 < GAP - 0.01:
                L.fail(f"a generated via pad edge sits {near - PAD / 2:.3f} from the trace, inside the {GAP} gap")
            else:
                L.ok(f"nearest generated via pad edge {near - PAD / 2:.3f} from the trace edge")
L.finish()
