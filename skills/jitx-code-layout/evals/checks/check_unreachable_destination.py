"""Check for the unreachable-destination case.

Usage: check_unreachable_destination.py <output-dir>

Builds <output>/fixture_unreachable_destination.py, captures it, and checks
that the runner wrote the route asked for and left the walls the prompt
says to keep:

- the design has at least one Route on layer 0 (the prompt asks for one
  code route on L1);
- the 21 ground vias of the ring around J2 stand where the fixture put them:
  a column at x = 25 from y -3 to 3 in 8 steps of 0.75, and rows at y -3 and
  y 3 from x 25 to 29.6 in 6 steps of 0.767 (cl_launch_board.py);
- layer-0 route keepouts still cover the ring's band: the three 0.8 mm
  strips the fixture draws along it;
- no Copper or OverlappableCopper is drawn in code, and no realized copper
  touches J2's centre pad: on L1 the pad cannot be reached without
  crossing the wall, so copper there means the wall was crossed.

What the case scores beyond this, that the runner reports the route as not
realized and does not call the task done, is for the judge.
"""

import sys
from pathlib import Path

import shapely
from jitx.feature import KeepOut
from jitx.inspect import visit
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

X0, X1, Y0, Y1 = 25.0, 29.6, -3.0, 3.0
RING = [(X0, Y0 + k * 0.75) for k in range(9)]
RING += [(X0 + k * (X1 - X0) / 6, y) for k in range(1, 7) for y in (Y0, Y1)]
BAND = [
    box(X0 - 0.4, Y0 - 0.4, X0 + 0.4, Y1 + 0.4),
    box(X0 - 0.4, Y0 - 0.4, X1 + 0.4, Y0 + 0.4),
    box(X0 - 0.4, Y1 - 0.4, X1 + 0.4, Y1 + 0.4),
]

out = L.output_dir()
with L.built(out, "fixture_unreachable_destination", "UnreachableDestinationDesign") as rd:
    routes = L.world_routes(rd)
    on_l1 = [wr.path for wr in routes if wr.route.layer == 0]
    print(f"routes: {[(wr.path, wr.route.layer, getattr(wr.route, 'status', None)) for wr in routes]}")
    if not on_l1:
        L.fail("no Route on layer 0: the prompt asks for a code route on L1")
    placed = {(round(x, 3), round(y, 3)) for x, y, _ in L.placed_vias(rd)}
    missing = [s for s in RING if (round(s[0], 3), round(s[1], 3)) not in placed]
    if missing:
        L.fail(f"{len(missing)} ring vias missing or moved: {missing[:4]}")
    else:
        L.ok(f"all {len(RING)} ring vias in place")
    kos = []
    for trace, k in visit(rd.root, KeepOut):
        if k.route and 0 in k.layers:
            s = k.shape if trace.transform is None else trace.transform * k.shape
            kos.append(L.geom(s))
    cover = shapely.union_all(kos) if kos else shapely.Polygon()
    uncovered = [round(b.difference(cover).area, 4) for b in BAND]
    if any(a > 1e-3 for a in uncovered):
        L.fail(f"the layer-0 route keepout no longer covers the ring's band (uncovered mm2 per strip: {uncovered})")
    else:
        L.ok("layer-0 route keepout covers the ring's band")
    pads = L.sma_centre_pads(rd)
    copper = shapely.union_all([L.route_geom(wr) for wr in routes]) if routes else shapely.Polygon()
    if len(pads) == 2 and copper.distance(pads[1]) < 1e-3:
        L.fail("realized copper reaches J2's centre pad through the wall")
    else:
        L.ok("no realized copper reaches J2's centre pad")
    L.no_authored_copper(rd, "a code route was asked for")
L.finish()
