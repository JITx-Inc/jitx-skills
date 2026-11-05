"""Check for the hex-bga-escape case.

Usage: check_hex_bga_escape.py <output-dir>

Builds <output>/fixture_hex_bga_escape.py, captures it, and checks the
escape against the prompt:

- every route realized on layer 0, and the issue report has no "Unable to
  find path";
- every ball pad of the BGA's four signal balls and every pad of the two
  pair chips touched by routed copper;
- inside the ball field (the bounding box of the BGA's ball pads), every
  trace is 0.08 wide and every coupled route's two traces stand 0.10 apart:
  ``DIFF_100_FIELD``, the structure the prompt asks for there. Below the
  field, every trace is 0.15 wide and every coupled route's traces stand
  0.20 apart: ``DIFF_100``, which the prompt asks the nets to keep. Width is
  the realized trace's drawn width; gap is the distance between the two
  traces' copper;
- at least one coupled route in the field and one below it on each pair:
  the pair is split at a control point, not narrowed for its whole length;
- the 0.08 copper reaches no further than 2.345 below the field box. The
  prompt asks for DIFF_100 everywhere outside the field; spike C8 split a
  pair at control points 4.0, 4.5 and 6.0 below the ball centres of a
  field whose pad edge sat at 3.655, and the transition followed the
  control point each time, so a split 6.0 - 3.655 = 2.345 below the field
  edge is the furthest a tested escape put it. A neck that runs on toward
  the chips fails here;
- every ground ball keeps its via: at least 52 of the 56 ball pads hold a
  via centre placed in code (the fixture places one in each ground ball);
- no Copper or OverlappableCopper is drawn in code.
"""

import sys
from pathlib import Path

import shapely
from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

NECK = (0.08, 0.10)
FULL = (0.15, 0.20)
TOL = 0.005
MAX_NECK_OUT = 6.0 - 3.655
BALLS = 56
SIGNAL_BALLS = 4

out = L.output_dir()
with L.built(out, "fixture_hex_bga_escape", "HexBgaEscapeDesign") as rd:
    from jitx.component import Component

    from cl_parts import PairChip

    balls = L.chip_pads(rd, Component, mpn="CL-EVAL-HEXBGA56")
    chip_pads = L.chip_pads(rd, PairChip)
    if len(balls) != BALLS:
        L.fail(f"{len(balls)} BGA ball pads, not {BALLS}")
    field = box(*shapely.union_all(balls).bounds)
    routes = L.realized_routes(rd, layer=0)
    copper = shapely.union_all([L.route_geom(r) for _, r in routes]) if routes else shapely.Polygon()
    touched = [b for b in balls if b.distance(copper) < 1e-3]
    if len(touched) != SIGNAL_BALLS:
        L.fail(f"routed copper touches {len(touched)} ball pads, not the {SIGNAL_BALLS} signal balls")
    if any(p.distance(copper) > 1e-3 for p in chip_pads) or len(chip_pads) != 4:
        L.fail("routed copper does not reach every pair chip pad")
    counts = {"field": 0, "below": 0}
    for path, r in routes:
        g = L.route_geom(r)
        where = "field" if g.intersects(field) else "below"
        want_w, want_gap = NECK if where == "field" else FULL
        widths = L.trace_widths(r)
        if where == "field":
            outside = g.difference(field)
            reach = max((field.distance(Point(c)) for c in shapely.get_coordinates(outside)), default=0.0)
            print(f"{path}: neck copper reaches {reach:.3f} outside the field")
            if reach > MAX_NECK_OUT + TOL:
                L.fail(f"{path}: 0.08 copper runs {reach:.3f} outside the field, past {MAX_NECK_OUT:.3f}")
        gap = None
        traces = r.traces
        if traces is not None and len(traces) == 2:
            a, b = (shapely.union_all([L.geom(s) for s in t.shapes]) for t in traces)
            gap = round(a.distance(b), 4)
            counts[where] += 1
        print(f"{path}: {where}, widths {widths}, gap {gap}")
        if any(w is None or abs(w - want_w) > TOL for w in widths):
            L.fail(f"{path}: widths {widths} {'inside' if where == 'field' else 'below'} the field, not {want_w}")
        if gap is not None and abs(gap - want_gap) > TOL:
            L.fail(f"{path}: pair gap {gap} {'inside' if where == 'field' else 'below'} the field, not {want_gap}")
    print(f"coupled routes: {counts}")
    if counts["field"] < 2 or counts["below"] < 2:
        L.fail(f"coupled routes {counts}: each pair needs a narrow section in the field and a full one below it")
    vias = [Point(x, y) for x, y, _ in L.placed_vias(rd)]
    held = sum(1 for b in balls if any(b.contains(v) for v in vias))
    print(f"{held} ball pads hold a placed via")
    if held < BALLS - SIGNAL_BALLS:
        L.fail(f"only {held} ball pads hold a via; the {BALLS - SIGNAL_BALLS} ground balls each had one")
    text = L.issues_text(rd)
    bad = L.issue_kinds(text, "Unable to find path")
    print("issues:", text.strip().splitlines()[:4])
    if bad:
        L.fail(f"routes not made: {bad}")
    L.no_authored_copper(rd, "code routes on the substrate's structures were asked for")
L.finish()
