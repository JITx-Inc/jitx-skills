"""Check for the route-around-with-sketch case.

Usage: check_route_around_with_sketch.py <output-dir>

Builds <output>/fixture_route_around_with_sketch.py, captures it, and checks
the RF line against the prompt and the fixture:

- the five ground vias of the column still stand at x = 0, y -1.5 to 1.5,
  0.75 apart (cl_launch_board.py), so the obstacle was not moved or removed;
- the design has at least one Route, and every route realized on layer 0;
- the routed copper is one connected piece touching both SMA centre pads;
- where that copper crosses the column's centre line, x = 0, all of it lies
  below the column: its top edge is under the lowest via pad's bottom edge,
  -1.5 - 0.500 / 2 = -1.75 (row 11 pad). The prompt names the side below.
  With no sketch the router passes the column above, so a plain route
  fails here; a route through the column fails here too;
- no Copper or OverlappableCopper is drawn in code: the prompt asks for a
  code route.
"""

import sys
from pathlib import Path

import shapely
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

COLUMN = [(0.0, -1.5 + 0.75 * k) for k in range(5)]
VIA_PAD = 0.500
LOWEST_PAD_EDGE = -1.5 - VIA_PAD / 2

out = L.output_dir()
with L.built(out, "fixture_route_around_with_sketch", "RouteAroundWithSketchDesign") as rd:
    placed = [(round(x, 3), round(y, 3)) for x, y, _ in L.placed_vias(rd)]
    missing = [s for s in COLUMN if s not in placed]
    print(f"code-placed vias: {sorted(placed)}")
    if missing:
        L.fail(f"column vias missing or moved: {missing}")
    else:
        L.ok("the five column vias stand where the fixture put them")
    routes = L.realized_routes(rd, layer=0)
    copper = shapely.union_all([L.route_geom(r) for _, r in routes]) if routes else shapely.Polygon()
    pads = L.sma_centre_pads(rd)
    if len(pads) != 2 or not L.joins(copper, pads[0], pads[1]):
        L.fail("no connected piece of routed copper touches both SMA centre pads")
    else:
        L.ok("routed copper joins both SMA centre pads")
    cross = copper.intersection(LineString([(0.0, -20.0), (0.0, 20.0)]))
    if cross.is_empty:
        L.fail("the routed copper does not cross x = 0")
    else:
        _, lo, _, hi = cross.bounds
        print(f"copper at x = 0 spans y {lo:.3f} to {hi:.3f} (centre {(lo + hi) / 2:.3f})")
        if hi >= LOWEST_PAD_EDGE:
            L.fail(f"copper at x = 0 reaches y {hi:.3f}, not below the column's lowest pad edge {LOWEST_PAD_EDGE}")
        else:
            L.ok("the line passes below the column")
    L.no_authored_copper(rd, "a code route was asked for")
L.finish()
