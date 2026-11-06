"""Check for the rf-connector-launch case.

Usage: check_rf_connector_launch.py <output-dir>

Builds <output>/fixture_rf_connector_launch.py, captures it, and checks the
launch against the prompt:

- every route realized on layer 0, every trace 0.30 wide (``CPWG_50_FENCED``),
  and one connected piece of routed copper joining the two SMA centre pads;
- each exit: the 2.0 mm past the inner end of each centre pad is covered by
  trace segments on the pad's axis (both ends within 0.01 mm of it, under
  0.1 degree to it), and the routed copper there drifts no more than
  0.01 mm past half the trace width from the axis, read short of the far
  end by half a trace, where the next route's turn begins. Spike C4: a
  pad-to-pad code route does not leave a pad along its axis; a
  RoutePoint on the axis does;
- each cutout: the realized L2 GND pour has no copper over the centre pad's
  outline grown by 0.5 mm (the prompt's cutout), and does have copper within
  1.5 mm of that outline, so the void is a cutout in a pour and not a
  missing pour;
- the fence: the vias the runtime generated, read by their distance to the
  routed line's centre line, stand in two rows (two distinct distances, each
  held by at least four vias), the two rows ``CPWG_50_FENCED`` declares;
- no via placed in code stands on a fence row: ``CPWG_50_FENCED``'s
  ``ViaFencePattern(offset=0.6, initial_offset=0.6, num_rows=2)`` puts the
  rows 0.6 and 1.2 from the trace edge, 0.75 and 1.35 from the centre line
  of a 0.30 trace, and a via placed in code whose 0.500 pad (row 11)
  covers either distance is a hand fence. A via elsewhere, such as one
  tying the L2 pour to GND, is not scored. No Copper or OverlappableCopper
  is drawn in code.
"""

import math
import sys
from collections import Counter
from pathlib import Path

import shapely
from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

WIDTH = 0.30
EXIT = 2.0
GROW = 0.5
DRIFT = 0.01
ANGLE = 0.1
FENCE_ROWS = (WIDTH / 2 + 0.6, WIDTH / 2 + 1.2)
VIA_PAD = 0.500

out = L.output_dir()
with L.built(out, "fixture_rf_connector_launch", "RfConnectorLaunchDesign") as rd:
    routes = L.realized_routes(rd, layer=0)
    widths = sorted({w for wr in routes for w in L.trace_widths(wr.route)}, key=str)
    print(f"trace widths {widths}")
    if any(w is None or abs(w - WIDTH) > 1e-3 for w in widths):
        L.fail(f"trace widths {widths}, not {WIDTH}")
    copper = shapely.union_all([L.route_geom(wr) for wr in routes]) if routes else shapely.Polygon()
    pads = L.sma_centre_pads(rd)
    if len(pads) != 2 or L.piece_touching(copper, *pads) is None:
        L.fail("no connected piece of routed copper joins the two SMA centre pads")
    segs = [s for wr in routes for s in L.segments(wr)]
    pours = [g for _, p, g in L.world_pours(rd) if int(p.layer) == 1]
    l2 = shapely.union_all(pours) if pours else shapely.Polygon()
    for k, pad in enumerate(pads):
        x0, y0, x1, y1 = pad.bounds
        yc = (y0 + y1) / 2
        # j1 sits on the left edge and points +x; j2 on the right points -x.
        inner, sign = (x1, 1.0) if k == 0 else (x0, -1.0)
        a, b = sorted((inner, inner + sign * EXIT))
        # The drift is read short of the far end by half a trace, where the
        # next route's turn starts and its round end widens the copper.
        c, d = sorted((inner, inner + sign * (EXIT - WIDTH / 2)))
        band = copper.intersection(box(c, yc - 5.0, d, yc + 5.0))
        if band.is_empty:
            L.fail(f"pad {k + 1}: no routed copper in the {EXIT} mm past the pad")
        else:
            bx0, by0, bx1, by1 = band.bounds
            drift = max(abs(by0 - yc), abs(by1 - yc)) - WIDTH / 2
            print(f"pad {k + 1}: copper from {inner:.3f} on: drift {drift:.4f} off the axis")
            if drift > DRIFT:
                L.fail(f"pad {k + 1}: exit copper drifts {drift:.4f} off the axis")
        # Trace segments on the axis (both ends within DRIFT of it, angle
        # under ANGLE) must cover the whole exit.
        on_axis = []
        for p, q, _ in segs:
            if p == q or max(abs(p[1] - yc), abs(q[1] - yc)) > DRIFT:
                continue
            t = abs(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))) % 180
            if min(t, 180 - t) <= ANGLE:
                on_axis.append(shapely.LineString([(p[0], 0.0), (q[0], 0.0)]))
        cover = shapely.union_all(on_axis) if on_axis else shapely.LineString()
        covered = cover.intersection(shapely.LineString([(a, 0.0), (b, 0.0)])).length
        print(f"pad {k + 1}: {covered:.3f} of the {EXIT} mm exit covered by trace segments on the axis")
        if covered < EXIT - 1e-3:
            L.fail(f"pad {k + 1}: only {covered:.3f} of the {EXIT} mm exit runs straight on the pad axis")
        cut = pad.buffer(GROW - 0.01, join_style="mitre")
        over = l2.intersection(cut).area
        near = l2.intersection(pad.buffer(GROW + 1.5, join_style="mitre")).area
        print(f"pad {k + 1}: L2 pour over the cutout {over:.4f} mm2, within 1.5 mm of it {near:.3f} mm2")
        if over > 1e-4:
            L.fail(f"pad {k + 1}: L2 pour covers {over:.4f} mm2 of the cutout")
        if near < 1.0:
            L.fail(f"pad {k + 1}: no L2 pour around the cutout")
    lines = shapely.union_all([L.centreline(t) for wr in routes for t in L.world_traces(wr)]) if routes else None
    gen = L.generated_vias(rd)
    rows = Counter(round(lines.distance(Point(x, y)), 2) for x, y in gen) if lines is not None else Counter()
    held = sorted(d for d, n in rows.items() if n >= 4)
    print(f"{len(gen)} generated vias; rows (distance from the centre line: count) {dict(sorted(rows.items()))}")
    if len(held) != 2:
        L.fail(f"generated vias stand at {held} from the line, not in two rows")
    hand = (
        [
            (x, y)
            for x, y, _ in L.placed_vias(rd)
            if any(abs(lines.distance(Point(x, y)) - d) < VIA_PAD / 2 for d in FENCE_ROWS)
        ]
        if lines is not None
        else []
    )
    if hand:
        L.fail(f"vias placed in code beside the line, where the structure's fence was asked for: {hand}")
    L.no_authored_copper(rd, "code routes on CPWG_50_FENCED were asked for")
L.finish()
