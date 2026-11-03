"""Check for the vias-along-the-feed case.

Usage: check_vias_along_the_feed.py <output-dir>

Builds <output>/fixture_vias_along_the_feed.py, captures it, and checks the
antenna feed against values worked out from the prompt, the substrate and the
fab sheet:

- the feed is realized at CPWG_50's width, 0.30, with the layer-0 pour at its
  0.20 gap plus the runtime's 0.01 (spike S9), within [0.20, 0.23];
- the layer-0 pour is present on both sides of the feed;
- the vias are generated, not placed in code: the design still places
  exactly the fixture's six GND anchors. The generated vias are read with
  ``lc_check.generated_vias``, which does not say which rule made them;
  fence_common says why the rows below still single out a route fence;
- on each side, the innermost fence row sits as close as the prompt allows:
  the via pad edge at the 0.20 gap, so the centre 0.20 + 0.500 / 2 = 0.45 from
  the trace edge (fab row 11 via pad; fab row 4's 0.100 space is smaller than
  the gap, so the gap governs), accepted up to 0.50, a 0.05 rounding;
- that row holds floor(L / 1.0) sites on the straight run, less one allowed
  (fence_common), at the prompt's 1.0 mm pitch;
- no generated via pad sits in the coplanar gap.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fence_common as FC  # noqa: E402
import lc_check as L  # noqa: E402

WIDTH = 0.30
GAP = 0.20
PAD = 0.500
O1_MIN = GAP + PAD / 2
O1_MAX = O1_MIN + 0.05
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
            L.fail("no generated vias realized (a fence_via rule fences no route, spike S4)")
        else:
            n = FC.full_count(feed, PITCH)
            print(f"sites per side on the straight run: {n}")
            for side in (1, -1):
                row = FC.straight_row(feed, side, O1_MIN - FC.ROW_TOL, O1_MAX + FC.ROW_TOL)
                label = f"side {side} row within {O1_MIN:.2f} to {O1_MAX:.2f}"
                print(f"{label}: {len(row)} vias")
                if len(row) < n - 1:
                    L.fail(f"{label}: {len(row)} vias, fewer than {n} - 1")
                FC.check_pitch(row, PITCH, label)
            near = min(v.edge for v in feed.vias)
            if near - PAD / 2 < GAP - 0.01:
                L.fail(f"a generated via pad edge sits {near - PAD / 2:.3f} from the trace, inside the {GAP} gap")
            else:
                L.ok(f"nearest generated via pad edge {near - PAD / 2:.3f} from the trace edge")
L.finish()
