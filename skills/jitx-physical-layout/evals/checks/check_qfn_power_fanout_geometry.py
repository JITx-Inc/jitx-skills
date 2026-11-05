"""Check for the qfn-power-fanout-geometry case.

Usage: check_qfn_power_fanout_geometry.py <output-dir>

Builds <output>/fixture_qfn_power_fanout_geometry.py, captures it, and checks
the fanout of the KSZ9031RNX's six DVDDL pins (14, 18, 23, 26, 30, 39, the
part's docstring) against the prompt and the land pattern:

- every route realized, on layer 0;
- each DVDDL pad is touched by routed copper, and the routed copper over
  the pad is nowhere wider than 0.25 (the prompt's neck), which is under
  the pad's own width, its short side as captured (0.30, land pattern
  figure 13-3 X1). The width is measured on the copper, whatever construct
  made it: the copper over the pad, shrunk by half the neck plus 0.001,
  must vanish. That holds for a 0.25 trace at any angle across the pad
  and fails for copper that fills the pad's 0.30;
- the connected piece of routed copper that leaves each pad carries the
  prompt's 0.40 run width past the pad: a realized trace drawn 0.40 wide,
  or, for copper with no drawn width, the piece outside the pad shrunk by
  half of 0.40 less 0.001 is not empty. Only the lower bound is read from
  the geometry, since a bend in a 0.40 trace survives a larger shrink; and
  the piece reaches a via placed in code;
- that via stands outside the package body (7.00 square, the part's BODY)
  and its centre lies inside the realized L3 1V2 pour, so it joins the
  plane; each pin has its own via, six in all;
- no Copper or OverlappableCopper is drawn in code: the prompt asks for
  code routes.
"""

import sys
from pathlib import Path

import shapely
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

PINS = (14, 18, 23, 26, 30, 39)
NECK = 0.25
RUN = 0.40
BODY_HALF = 7.00 / 2
TOL = 1e-3


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
        (x, y, Point(x, y).buffer(float(v.diameter) / 2))
        for x, y, v in L.placed_vias(rd)
        if max(abs(x), abs(y)) > BODY_HALF and plane.contains(Point(x, y))
    ]
    shapes = []  # (route path, width, geometry) of every realized trace shape
    for path, r in routes:
        for tr in r.traces or []:
            for s in tr.shapes:
                w = getattr(getattr(s, "geometry", s), "width", None)
                shapes.append((path, None if w is None else round(float(w), 4), L.geom(s)))
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
        necked = over.buffer(-(NECK / 2 + TOL)).is_empty
        if not necked:
            L.fail(f"pin {pin}: routed copper over the {pad_w} pad is wider than the {NECK} neck somewhere")
        piece = next((pc for pc in pieces if pc.distance(pad) < 1e-3), None)
        drawn = piece is not None and any(
            w is not None and abs(w - RUN) < TOL and g.distance(piece) < 1e-3 for _, w, g in shapes
        )
        reached = piece is not None and not piece.difference(pad).buffer(-(RUN / 2 - TOL)).is_empty
        run = "drawn 0.40 trace" if drawn else "0.40 reached by copper with no drawn width" if reached else "none"
        if not (drawn or reached):
            L.fail(f"pin {pin}: the fanout carries no {RUN} run past the pad")
        hit = [(x, y) for x, y, disc in vias if piece is not None and piece.distance(disc) < 1e-3]
        if not hit:
            L.fail(f"pin {pin}: the fanout reaches no code-placed via outside the body on the 1V2 plane")
            continue
        used.add((round(hit[0][0], 3), round(hit[0][1], 3)))
        print(
            f"pin {pin}: pad {pad_w} wide, neck within {NECK}: {necked}, run: {run}, via {hit[0][0]:.3f}, {hit[0][1]:.3f}"
        )
    if len(used) != len(PINS):
        L.fail(f"{len(used)} distinct fanout vias for {len(PINS)} pins")
    L.no_authored_copper(rd, "code routes were asked for")
L.finish()
