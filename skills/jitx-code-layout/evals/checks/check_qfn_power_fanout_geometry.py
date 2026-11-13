"""Check for the qfn-power-fanout-geometry case.

Usage: check_qfn_power_fanout_geometry.py <output-dir>

Builds <output>/fixture_qfn_power_fanout_geometry.py, captures it, and checks
the fanout of the KSZ9031RNX's six DVDDL pins (14, 18, 23, 26, 30, 39, the
part's docstring) against the prompt and the land pattern:

- every route realized, on layer 0;
- each DVDDL pad is touched by routed copper, and that copper stays
  narrower than the pad, the prompt's stated purpose for the neck ("so the
  copper on the pad stays narrower than the pad"). The pad's width is its
  short side as captured (0.30, land pattern figure 13-3 X1). The routed
  copper over the pad is cut across the pad's long axis every 0.005 along
  it and at both ends, and no cut may span the pad's width less 0.001.
  The end cuts make the round-end case exact at any step. The 0.005 step
  was first chosen to put about six cuts in the full-width band a 0.40
  run's round end leaves with its RoutePoint 0.10 past the edge (about
  0.033 long in a synthetic round-cap probe). The 0.25 neck width itself
  is judged, not checked here;
- the connected piece of routed copper that leaves each pad reaches a via
  placed in code. Every route whose endpoint is that via (the via or its
  port), and every other route whose copper lies in that piece and does
  not touch the pad, has every realized trace drawn 0.40 wide (the
  prompt's run width, within 0.001). A route whose round end reaches
  back over the pad (its start less than half its width past the edge)
  touches the pad and is not width-checked here, so a neck built from two
  0.25 routes fails when its split point lies 0.125 or more past the
  edge, and a narrower run route that starts that close to the pad is
  left to the judge. A neck's copper never touches the via disc: with the
  0.50 ThVia the runtime refuses a 0.40 run whose RoutePoint is within
  about 0.45 of the via centre ("Overlapping target shapes"). Copper with
  no drawn width, such as a ``Route.Target`` taper, fails;
- that via stands outside the package body (7.00 square, the part's BODY)
  and its centre lies inside the realized L3 1V2 pour, so it joins the
  plane; each pin has its own via, six in all;
- no Copper or OverlappableCopper is drawn in code: the prompt asks for
  code routes.
"""

import sys
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

PINS = (14, 18, 23, 26, 30, 39)
RUN = 0.40
BODY_HALF = 7.00 / 2
TOL = 1e-3
CUT_STEP = 0.005


def widest_cut(over: BaseGeometry, pad: BaseGeometry) -> float:
    """Longest cut through ``over`` across the pad's long axis, stepping CUT_STEP along it."""
    bx0, by0, bx1, by1 = pad.bounds
    along_y = by1 - by0 > bx1 - bx0
    lo, hi = (by0, by1) if along_y else (bx0, bx1)
    best = 0.0
    for t in [lo + k * CUT_STEP for k in range(int((hi - lo) / CUT_STEP) + 1)] + [hi]:
        cut = LineString([(bx0 - 1, t), (bx1 + 1, t)] if along_y else [(t, by0 - 1), (t, by1 + 1)])
        best = max(best, over.intersection(cut).length)
    return round(best, 4)


out = L.output_dir()
with L.built(out, "fixture_qfn_power_fanout_geometry", "QfnPowerFanoutGeometryDesign") as rd:
    from jitx.inspect import visit
    from jitxexamples.components.ethernet_phys.microchip_KSZ9031RNX import KSZ9031RNX

    phy = [c for _, c in visit(rd.root, KSZ9031RNX)][0]
    routes = L.realized_routes(rd, layer=0)
    planes = [g for _, p, g in L.world_pours(rd) if int(p.layer) == 2]
    plane = shapely.union_all(planes) if planes else shapely.Polygon()
    if plane.is_empty:
        L.fail("the L3 1V2 pour did not realize")
    vias = [
        (x, y, v, Point(x, y).buffer(float(v.diameter) / 2))
        for x, y, v in L.placed_vias(rd)
        if max(abs(x), abs(y)) > BODY_HALF and plane.contains(Point(x, y))
    ]
    shapes = []  # (route path, width, geometry) of every realized trace shape
    for wr in routes:
        for tr in L.world_traces(wr):
            for s in tr:
                w = getattr(getattr(s, "geometry", s), "width", None)
                shapes.append((wr.path, None if w is None else round(float(w), 4), L.geom(s)))
    copper = shapely.union_all([g for _, _, g in shapes]) if shapes else shapely.Polygon()
    pieces = list(getattr(copper, "geoms", [copper]))
    used: set[tuple[float, float]] = set()
    for pin in PINS:
        pad = L.pad_world(rd, phy.landpattern.p[pin])
        bx0, by0, bx1, by1 = pad.bounds
        pad_w = round(min(bx1 - bx0, by1 - by0), 4)
        over = copper.intersection(pad)
        if over.area <= 1e-6:
            L.fail(f"pin {pin}: no routed copper on the pad")
            continue
        widest = widest_cut(over, pad)
        if widest >= pad_w - TOL:
            L.fail(f"pin {pin}: routed copper spans {widest} across the {pad_w} pad, not narrower than the pad")
        piece = next((pc for pc in pieces if pc.distance(pad) < 1e-3), None)
        hit = [(x, y, v, disc) for x, y, v, disc in vias if piece is not None and piece.distance(disc) < 1e-3]
        if not hit:
            L.fail(f"pin {pin}: the fanout reaches no code-placed via outside the body on the 1V2 plane")
            continue
        x, y, via, _ = hit[0]
        ends = (via, via.port)
        at_via = sorted(
            {w for wr in routes if any(wr.route.source is e or wr.route.destination is e for e in ends) for w in L.trace_widths(wr.route)},
            key=str,
        )
        if not at_via or any(w is None or abs(w - RUN) >= TOL for w in at_via):
            L.fail(f"pin {pin}: widths of the routes ending at the via {at_via}, not all drawn {RUN}")
        off_pad = sorted(
            {
                w
                for wr in routes
                if piece is not None
                and piece.distance(g := L.route_geom(wr)) < 1e-3
                and not g.is_empty
                and g.distance(pad) >= 1e-3
                for w in L.trace_widths(wr.route)
            },
            key=str,
        )
        if any(w is None or abs(w - RUN) >= TOL for w in off_pad):
            L.fail(f"pin {pin}: widths of the routes off the pad {off_pad}, not all drawn {RUN}")
        used.add((round(x, 3), round(y, 3)))
        print(
            f"pin {pin}: pad {pad_w} wide, widest cut over it {widest}, widths of the routes ending at the via {at_via}, widths off the pad {off_pad}, via {x:.3f}, {y:.3f}"
        )
    if len(used) != len(PINS):
        L.fail(f"{len(used)} distinct fanout vias for {len(PINS)} pins")
    L.no_authored_copper(rd, "code routes were asked for")
L.finish()
