"""Check for the rf-connector-launch case.

Usage: check_rf_connector_launch.py <output-dir>

Builds <output>/fixture_rf_connector_launch.py, captures it, and checks the
launch against the prompt. Every number below is the prompt's, or the
fixture's, or worked from them:

- every route realized on layer 0, every trace 0.30 wide (``CPWG_50_FENCED``),
  and one connected piece of routed copper joining the two SMA centre pads;
- each exit: the 2.5 mm past the inner end of each centre pad is covered
  by trace segments on the pad's axis (both ends within 0.01 mm of it,
  under 0.1 degree to it). Spike C4: a pad-to-pad code route does not leave
  a pad along its axis; a RoutePoint on the axis does;
- each exit's tangency square: GND ``Copper`` on L1 covers the 0.20 mm
  square the prompt places on the inside of the turn (toward the other
  jack's row), its near side C = 1.0 off the 0.30 trace's copper edge,
  1.15 off the axis, from the RoutePoint to 0.20 mm past it; read 0.01 in
  from each side of the square, so a square up to 0.01 off its place still
  covers it. Each copper piece that reaches into it is no larger than 0.20
  on a side and is joined to the net named GND. A route keepout between the
  copper edge and the square's far side, past the RoutePoint, in its place
  fails as such. No routed copper comes within C of either square, less
  0.001: the gap is read from each trace's centre line, arcs sampled on the
  arc every 1 degree, less half the width (``cl_check.copper_gap``), so a
  chord sits inside its arc by at most r(1 - cos 0.5 deg), under 0.0001 at
  the 1.15 bend. Reading the copper as a polygon instead would put it up to 0.04
  nearer: jitx's ``discretize`` at its 0.01 tolerance can stroke an arc of
  under two steps as one chord, which on the 1.15 bend (a 15.1 degree step)
  covers up to 30 degrees and sits up to 1.15 (1 - cos 15.1 deg) = 0.040
  inside it. RF copper over a square
  fails here even when the build reports no issue. From the pad's inner end
  through the square's far edge, routed copper covers the axis and the
  centre line stays within 0.01 mm of it. Past the far edge the line turns
  around the square's corner: some trace holds an arc centred within 0.01
  of that corner (the RoutePoint plus 0.20 along, 1.15 across) with a
  centre-line radius of 0.15 + C = 1.15 within 0.01;
- each cutout: across the axis at stations along the pad and the 2.0 mm
  taper, the realized L2 GND pour's void reaches h(s) on each side, within
  0.02 mm, where h is 0.9 under the pad and k / (s + s0) along the taper,
  from 0.9 at s = 0 to the 0.35 half slot (0.30 trace and a 0.20 gap each
  side) at s = 2.0: s0 = 2.0 * 0.35 / (0.9 - 0.35), k = 0.9 * s0. Past the
  taper the pour covers the axis again;
- the coplanar pour: an L1 GND pour that realizes, whose nearest copper to
  the line between x = -20 and 20 is 0.20 to 0.23 off the line's copper,
  and that fills at least half of the band 0.2 to 0.5 off the line there;
- the obstacle: routed copper stays at least the prompt's P3_CLEAR from the
  P3V3 test pad's copper (read as for the squares, less 0.001), and every
  generated via's 0.500 pad (row 11) at least the fab sheet's 0.100
  copper-to-copper space (row 4) from it; line copper over the pad is
  reported as running through it. Neither fence row may lose vias beside
  the pad (the prompt): along the stretch of
  the line nearest the pad, the 6.0 mm of its centre line centred on the
  point closest to the pad, each of the four rows (0.75 and 1.35 off the
  centre line, each side) holds vias with no gap between neighbours, and
  none from either end of the stretch to the nearest via, wider than the
  1.0 pitch plus 0.5. One missing via leaves a gap of two pitches, 2.0;
  the 0.5 allows for a row's spacing on the outside of a bend. A via
  belongs to a row when its centre stands within 0.1 of the row's
  distance from the centre line, on that side. The prompt's P3_CLEAR is worked
  from the fence: on the pad's side the outer row stands 1.2 from the
  line's copper edge toward the pad, so a via there can stand
  P3_CLEAR - 1.2 from the pad's copper and its 0.500 pad P3_CLEAR - 1.45.
  The fab sheet's 0.100 needs P3_CLEAR at least 1.55; at 1.5 a via landing
  at the nearest point would stand 0.05 off, under it, so 1.5 holds only
  where the vias happen to fall;
- no keepout around the test pad (the prompt): no ``KeepOut`` on any layer
  reaches within AROUND = 3.0 of the pad's copper, a stated bound for
  "around the pad": at P3_CLEAR the far-side outer row's via pads start
  1.7 + 0.30 + 1.2 - 0.25 = 2.95 from the pad, so 3.0 covers every fence
  via pad. Read after the row gaps, so a keepout that eats
  the fence fails on the rows first;
- the fence: the vias the runtime generated, read by their distance to the
  routed line's centre line, stand in two rows (two distinct distances, each
  held by at least four vias), the two rows ``CPWG_50_FENCED`` declares;
- no via placed in code stands on a fence row: ``CPWG_50_FENCED``'s
  ``ViaFencePattern(offset=0.6, initial_offset=0.6, num_rows=2)`` puts the
  rows 0.6 and 1.2 from the trace edge, 0.75 and 1.35 from the centre line
  of a 0.30 trace, and a via placed in code whose 0.500 pad covers either
  distance is a hand fence. A via elsewhere, such as one tying the L2 pour to
  GND, is not scored. No Copper or OverlappableCopper is drawn in code but
  the two squares.
"""

import math
import sys
from collections import Counter
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, box
from shapely.geometry.base import BaseGeometry

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

from jitx.copper import Copper, Pour  # noqa: E402
from jitx.feature import OverlappableCopper  # noqa: E402
from jitx.inspect import visit  # noqa: E402

WIDTH = 0.30
EXIT = 2.5
DRIFT = 0.01
ANGLE = 0.1
GAP = 0.20
SQUARE = 0.20
C = 1.0
RADIUS = WIDTH / 2 + C
R_TOL = 0.01
SAG = 1e-3
P3_CLEAR = 1.7
AROUND = 3.0
COPPER_SPACE = 0.100
CUT_HALF = 1.8 / 2
TAPER = 2.0
SLOT_HALF = WIDTH / 2 + GAP
H_TOL = 0.02
L1_GAP = (GAP - 1e-3, GAP + 0.03)
FENCE_ROWS = (WIDTH / 2 + 0.6, WIDTH / 2 + 1.2)
VIA_PAD = 0.500
PITCH = 1.0
ROW_ALLOW = 0.5
ROW_BAND = 0.1
STRETCH = 6.0


def h(s: float) -> float:
    """The cutout's half-width ``s`` along the axis from the pad's inner end."""
    if s <= 0:
        return CUT_HALF
    s0 = TAPER * SLOT_HALF / (CUT_HALF - SLOT_HALF)
    return CUT_HALF * s0 / (s + s0)


def row_gaps(lines: BaseGeometry | None, tp: BaseGeometry, gen: list[tuple[float, float]]) -> None:
    """Fail each fence row with a gap over PITCH + ROW_ALLOW along the
    STRETCH of centre line centred on its nearest point to the test pad."""
    path = shapely.line_merge(lines) if lines is not None else None
    if path is None or path.is_empty:
        L.fail("no routed centre line to read the fence rows along")
        return
    path = min(getattr(path, "geoms", [path]), key=lambda g: g.distance(tp))
    mid = path.project(tp.centroid)
    lo, hi = mid - STRETCH / 2, mid + STRETCH / 2
    limit = PITCH + ROW_ALLOW
    for side in (1, -1):
        for d in FENCE_ROWS:
            row = []
            for x, y in gen:
                v = Point(x, y)
                at = path.project(v)
                if not lo <= at <= hi or abs(path.distance(v) - d) > ROW_BAND:
                    continue
                p, q = path.interpolate(max(at - 0.01, 0.0)), path.interpolate(min(at + 0.01, path.length))
                cross = (q.x - p.x) * (y - p.y) - (q.y - p.y) * (x - p.x)
                if cross * side > 0:
                    row.append((at, v))
            row.sort(key=lambda r: r[0])
            gaps = [row[0][0] - lo] if row else [STRETCH]
            gaps += [a[1].distance(b[1]) for a, b in zip(row, row[1:])]
            gaps += [hi - row[-1][0]] if row else []
            worst = max(gaps)
            print(f"fence row {d:.2f} off the centre line, side {side:+d}, along the {STRETCH} mm nearest the test pad: {len(row)} vias, widest gap {worst:.3f}")
            if worst > limit + 1e-3:
                L.fail(f"fence row {d:.2f} off the line, side {side:+d}, has a {worst:.3f} mm gap beside the P3V3 test pad, over {limit}")


out = L.output_dir()
with L.built(out, "fixture_rf_connector_launch", "RfConnectorLaunchDesign") as rd:
    from cl_parts import PadChip

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
    centre = shapely.union_all([L.centreline(t) for wr in routes for t in L.world_traces(wr)]) if routes else None
    pours = L.world_pours(rd)
    l2 = shapely.union_all([g for _, p, g in pours if int(p.layer) == 1] or [shapely.Polygon()])
    l1 = shapely.union_all([g for _, p, g in pours if int(p.layer) == 0] or [shapely.Polygon()])
    keepouts = shapely.union_all([g for g in L.route_keepouts(rd, 0)] or [shapely.Polygon()])
    inside = copper.intersection(keepouts).area
    print(f"routed copper inside L1 route keepouts: {inside:.5f} mm2")
    if inside > 1e-4:
        L.fail(f"routed copper runs {inside:.4f} mm2 inside an L1 route keepout")
    gnd = L.net_members(rd, "GND")
    drawn = [(t, c) for t, c in visit(rd.root, Copper) if not isinstance(c, Pour) and int(c.layer) == 0]
    drawn_g = [(str(t.path), L.geom(c.shape if t.transform is None else t.transform * c.shape), id(c) in gnd) for t, c in drawn]
    squares_used = set()

    for k, pad in enumerate(pads):
        x0, y0, x1, y1 = pad.bounds
        yc = (y0 + y1) / 2
        # j1 sits on the left edge and points +x; j2 on the right points -x.
        inner, sign = (x1, 1.0) if k == 0 else (x0, -1.0)
        # The line turns toward the other jack's row: the inside of the turn.
        other = pads[1 - k].centroid.y
        turn = 1.0 if other > yc else -1.0
        point = inner + sign * EXIT
        a, b = sorted((inner, inner + sign * EXIT))
        far = point + sign * SQUARE
        c, d = sorted((inner, far))
        sx0, sx1 = sorted((point, far))
        sy0, sy1 = sorted((yc + turn * (WIDTH / 2 + C), yc + turn * (WIDTH / 2 + C + SQUARE)))
        want = box(sx0 + 0.01, sy0 + 0.01, sx1 - 0.01, sy1 - 0.01)
        mine = [(path, g, on_gnd) for path, g, on_gnd in drawn_g if g.intersection(want).area > 1e-6]
        squares_used |= {path for path, _, _ in mine}
        got = want.intersection(shapely.union_all([g for _, g, _ in mine] or [shapely.Polygon()])).area / want.area
        sizes = [(round(g.bounds[2] - g.bounds[0], 4), round(g.bounds[3] - g.bounds[1], 4)) for _, g, _ in mine]
        # A route keepout anywhere between the copper edge and the square's
        # far side, past the RoutePoint, stands in place of the square.
        by0, by1 = sorted((yc + turn * WIDTH / 2, yc + turn * (WIDTH / 2 + C + SQUARE)))
        ko = box(sx0, by0, sx1, by1).intersection(keepouts).area
        print(f"pad {k + 1}: tangency square on side {turn:+.0f}: L1 copper covers {got:.3f} of it, sizes {sizes}, on GND {[n for _, _, n in mine]}; route keepouts beside it {ko:.4f} mm2")
        if got < 0.99 and ko > 1e-3:
            L.fail(f"pad {k + 1}: the tangency square past the RoutePoint is a route keepout, not GND copper")
        elif got < 0.99:
            L.fail(f"pad {k + 1}: no GND copper square on the inside of the turn past the RoutePoint ({got:.3f} of it covered)")
        if any(max(z) > SQUARE + 1e-3 for z in sizes):
            L.fail(f"pad {k + 1}: tangency copper larger than the {SQUARE} mm square: {sizes}")
        if not all(n for _, _, n in mine):
            L.fail(f"pad {k + 1}: tangency square not on GND")
        for _, g, _ in mine:
            near = L.copper_gap(routes, g)
            print(f"pad {k + 1}: routed copper {near:.4f} from the square (centre-line reading), {L.gap(copper, g)} as a polygon")
            if near < 0:
                L.fail(f"pad {k + 1}: routed copper overlaps the GND tangency square")
            elif near < C - SAG:
                L.fail(f"pad {k + 1}: routed copper {near:.4f} from the tangency square, under its {C} clearance")
        corner = (far, yc + turn * (WIDTH / 2 + C))
        bends = [(a, math.dist(a.center, corner)) for wr in routes for tr in L.world_traces(wr) for a in L.arcs(tr)]
        bends = [(round(a.radius, 4), round(d, 4)) for a, d in bends if d < 0.5]
        print(f"pad {k + 1}: arcs centred within 0.5 of the square's corner {corner}: (radius, centre off the corner) {bends}")
        if not any(d <= R_TOL and abs(r - RADIUS) <= R_TOL for r, d in bends):
            L.fail(f"pad {k + 1}: no bend of radius {RADIUS} centred on the tangency square's corner: {bends}")
        held = copper.intersection(LineString([(c, yc), (d, yc)])).length
        band = centre.intersection(box(c, yc - 5.0, d, yc + 5.0)) if centre is not None else LineString()
        if band.is_empty:
            L.fail(f"pad {k + 1}: no routed centre line from the pad through the square's far edge")
        else:
            drift = max(abs(band.bounds[1] - yc), abs(band.bounds[3] - yc))
            print(f"pad {k + 1}: from the pad's inner end {inner:.3f} through the square's far edge {far:.3f}: copper on {held:.3f} of the {d - c:.3f} mm axis, centre line {drift:.4f} off it")
            if drift > DRIFT or held < d - c - 1e-3:
                L.fail(f"pad {k + 1}: the line does not hold the axis through the square's far edge (centre line {drift:.4f} off it, axis covered {held:.3f} of {d - c:.3f})")
        on_axis = []
        for p, q, _ in segs:
            if p == q or max(abs(p[1] - yc), abs(q[1] - yc)) > DRIFT:
                continue
            t = abs(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))) % 180
            if min(t, 180 - t) <= ANGLE:
                on_axis.append(LineString([(p[0], 0.0), (q[0], 0.0)]))
        cover = shapely.union_all(on_axis) if on_axis else LineString()
        covered = cover.intersection(LineString([(a, 0.0), (b, 0.0)])).length
        print(f"pad {k + 1}: {covered:.3f} of the {EXIT} mm exit covered by trace segments on the axis")
        if covered < EXIT - 1e-3:
            L.fail(f"pad {k + 1}: only {covered:.3f} of the {EXIT} mm exit runs straight on the pad axis")

        stations = [-1.0, -0.5] + [TAPER * i / 8 for i in range(1, 8)]
        worst = 0.0
        for s in stations:
            x = inner + sign * s
            cut = LineString([(x, yc - 3.0), (x, yc + 3.0)])
            void = cut.difference(l2)
            hole = [g for g in getattr(void, "geoms", [void]) if g.distance(Point(x, yc)) < 1e-9]
            if len(hole) != 1:
                L.fail(f"pad {k + 1}: L2 pour covers the axis at s = {s:.2f}, inside the cutout")
                continue
            hy0, hy1 = hole[0].bounds[1], hole[0].bounds[3]
            if hy1 >= yc + 3.0 - 1e-6 or hy0 <= yc - 3.0 + 1e-6:
                L.fail(f"pad {k + 1}: no L2 pour within 3 mm of the axis at s = {s:.2f}")
                continue
            dev = max(abs(hy1 - yc - h(s)), abs(yc - hy0 - h(s)))
            worst = max(worst, dev)
            print(f"pad {k + 1}: s {s:+.2f}: void {yc - hy0:.4f} / {hy1 - yc:.4f} off the axis, h(s) {h(s):.4f}")
            if dev > H_TOL:
                L.fail(f"pad {k + 1}: L2 void at s = {s:.2f} is {dev:.4f} off h(s) = {h(s):.4f}")
        past = Point(inner + sign * (TAPER + 0.1), yc)
        if not l2.contains(past):
            L.fail(f"pad {k + 1}: no L2 pour on the axis 0.1 past the taper")
        print(f"pad {k + 1}: worst cutout deviation {worst:.4f} (limit {H_TOL})")

    if l1.is_empty:
        L.fail("no L1 GND pour realized beside the line")
    else:
        mid = copper.intersection(box(-20.0, -20.0, 20.0, 20.0))
        g = L.gap(l1, mid)
        ring = mid.buffer(0.5).difference(mid.buffer(0.2)).intersection(box(-20.0, -20.0, 20.0, 20.0))
        filled = ring.intersection(l1).area / ring.area if ring.area else 0.0
        print(f"L1 pour: gap {g} to the line, fills {filled:.3f} of the band 0.2 to 0.5 off it")
        if not (L1_GAP[0] <= g <= L1_GAP[1]):
            L.fail(f"L1 pour stands {g} off the line, not {GAP}")
        if filled < 0.5:
            L.fail(f"L1 pour fills only {filled:.3f} of the band beside the line")

    tps = L.chip_pads(rd, PadChip)
    if len(tps) != 1:
        L.fail(f"expected the one P3V3 test pad, found {len(tps)}")
    gen = L.generated_vias(rd)
    for tp in tps:
        through = copper.intersection(tp).area
        if through > 0:
            L.fail(f"line copper runs through the P3V3 test pad ({through:.4f} mm2)")
        dl = L.copper_gap(routes, tp)
        dv = min((L.gap(Point(x, y).buffer(VIA_PAD / 2), tp) for x, y in gen), default=math.inf)
        print(f"P3V3 test pad: line copper {dl:.4f} from it (centre-line reading), {L.gap(copper, tp)} as a polygon; nearest generated via pad {dv}")
        if dl < P3_CLEAR - SAG:
            L.fail(f"line copper {dl:.4f} from the P3V3 test pad, under {P3_CLEAR}")
        if dv < COPPER_SPACE - 1e-4:
            L.fail(f"a fence via pad {dv} from the P3V3 test pad, under the fab sheet's {COPPER_SPACE}")

    lines = centre
    rows = Counter(round(lines.distance(Point(x, y)), 2) for x, y in gen) if lines is not None else Counter()
    held = sorted(d for d, n in rows.items() if n >= 4)
    print(f"{len(gen)} generated vias; rows (distance from the centre line: count) {dict(sorted(rows.items()))}")
    if len(held) != 2:
        L.fail(f"generated vias stand at {held} from the line, not in two rows")
    for tp in tps:
        row_gaps(lines, tp, gen)
        reach = AROUND
        zone = tp.buffer(reach)
        near = [g for flag in ("route", "via", "pour") for layer in range(4) for g in L.keepouts(rd, layer, flag) if g.intersects(zone)]
        print(f"keepouts within {reach:.2f} of the P3V3 test pad: {len(near)}")
        if near:
            L.fail(f"a KeepOut within {reach:.2f} of the P3V3 test pad, where the prompt asks for a rule and no keepout")
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
    extra = [path for path, _, _ in drawn_g if path not in squares_used]
    extra += [str(t.path) for t, c in visit(rd.root, (Copper, OverlappableCopper)) if not isinstance(c, Pour) and int(c.layer) != 0]
    extra += [str(t.path) for t, _ in visit(rd.root, OverlappableCopper)]
    if extra:
        L.fail(f"copper drawn in code other than the two tangency squares: {sorted(set(extra))}")
L.finish()
