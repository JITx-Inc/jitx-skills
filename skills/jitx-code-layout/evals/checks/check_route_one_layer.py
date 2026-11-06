"""Check for the route-one-layer case.

Usage: check_route_one_layer.py <output-dir>

Builds <output>/fixture_route_one_layer.py, captures it, and checks the RF
line against the prompt and the fixture's substrate:

- the design has at least one Route, and every route realized (traces
  present, status routed) on layer 0, the L1 the prompt names;
- every realized trace is 0.30 wide, the trace width of the substrate's
  MS_50 (cl_substrate.py). A route with no rule, structure or Config comes
  out at the fab floor, 0.100 (row 3), so a plain route fails here;
- the routed copper is one connected piece that touches both SMA centre
  pads (the land pattern's ``sig`` pads in board coordinates);
- no Copper or OverlappableCopper is drawn in code: the prompt asks for a
  code route.
"""

import sys
from pathlib import Path

import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

WIDTH = 0.30

out = L.output_dir()
with L.built(out, "fixture_route_one_layer", "RouteOneLayerDesign") as rd:
    routes = L.realized_routes(rd, layer=0)
    widths = [w for wr in routes for w in L.trace_widths(wr.route)]
    print(f"routes realized: {len(routes)}, trace widths: {sorted(set(widths), key=str)}")
    bad = [w for w in widths if w is None or abs(w - WIDTH) > 1e-3]
    if routes and (bad or not widths):
        L.fail(f"trace widths {bad or widths}, not MS_50's {WIDTH}")
    copper = shapely.union_all([L.route_geom(wr) for wr in routes]) if routes else shapely.Polygon()
    pads = L.sma_centre_pads(rd)
    if len(pads) != 2:
        L.fail(f"{len(pads)} SMA centre pads found, the fixture has 2")
    elif not L.joins(copper, pads[0], pads[1]):
        L.fail("no connected piece of routed copper touches both SMA centre pads")
    else:
        L.ok("routed copper joins both SMA centre pads")
    L.no_authored_copper(rd, "a code route was asked for")
L.finish()
