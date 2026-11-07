"""Check for the wilkinson-tree case.

Usage: check_wilkinson_tree.py <output-dir>

Builds <output>/fixture_wilkinson_tree.py, captures it, and checks the tree
against the prompt. Every number below is the prompt's or the fixture's, or
worked from them:

- hierarchy: three ``WilkinsonCell`` instances, each under the one
  ``WilkinsonTree``, and each holding exactly one ``OverlappableCopper`` body
  on L1; no other ``Copper`` or ``OverlappableCopper`` in the design but the
  0.20 mm tangency squares (a meander drawn by hand, or a body drawn in the
  tree, fails here);
- arm length: an arm's length is its centre line between the 0.30 copper
  it leaves and the 0.30 copper it reaches, which it meets square on (the
  prompt, with no fillet at either end, and the two arms touching each
  other nowhere but where they leave the 0.30 copper). An opening by
  0.12 mm with square corners (more than half the 0.17 ``ARM_71`` width,
  less than half the 0.30 line) removes the arm copper from each body; cut
  0.1 mm back from the wide copper, so arms that touch at the junction
  part, it leaves two pieces. Each one's area over 0.17, plus what the
  same reading drops from a straight arm of known length between two
  square joins (0.2), is its length, a quarter wavelength at 2.45 GHz on
  ``ARM_71``'s 1.6e11 mm/s: 1.6e11 / 2.45e9 / 4 = 16.327 mm, within 0.5 mm.
  Arms that overlap or run side by side form copper as wide as the stub,
  which no width reading separates; the prompt rules both out;
- coincident keepout: an L1 GND pour realizes, covers none of any body
  (under 0.001 mm2), and its nearest copper stands 0.19 to 0.23 mm off
  each body: the prompt's keepout on the body's outline grown by 0.20, the
  clearance ``ARM_71`` and ``CPWG_50_FENCED`` declare, with up to 0.03
  more. The 0.01 allowed under covers the chord sag of a coarse round
  buffer (0.004 at four segments a quarter circle) and still fails a pour
  that touches the body or stands at half the clearance; an L1 pour
  ``KeepOut`` covers each body;
- region fence: the shape a ``fence_via`` rule's tag is on, over each body,
  is the body copper (their symmetric difference under 0.01 along the
  body's outline). Its rows then sit 0.6 and 1.2 off the copper edge (the
  prompt). Each row is the set of points that distance off the body
  copper, every ring of it, the inside of the loop included. Taken off
  each ring: what lies within 1.85 of a route centre line, and within 0.45
  of a resistor pad. The 1.85 is the route fence's outer row (1.35 off the
  centre line) plus the 0.5 between via centres that the fab sheet's
  0.25 drill (row 12) and 0.25 hole-to-hole space (row 15) set, so a region
  via there would collide with a route fence via. The 0.45 is the prompt's
  0.20 via keepout around a resistor pad plus a 0.25 via pad radius. A
  generated via serves a free stretch when its centre is within that 0.5
  of it, since no other via can stand there; this joins the two stretches
  of a row that pass 0.1 apart between a cell's output legs. The prompt's
  "a via every 1.0 mm" is scored per stretch of the first row at least two
  pitches long (a shorter one holds floor(n / 1.0) - 1 = 0 vias): no gap
  between neighbouring vias along it, or from either end to the nearest,
  over the pitch plus 0.5. One missing via leaves 2.0. Stretches inside the
  loop are scored first. The counts (floor(n / 1.0) - 1 per stretch, summed
  inside and outside the loop, against the vias serving them) and the
  outer row are printed, not scored: the gap rule is the stricter reading
  of the prompt's words, and the outer row reads sparse for a cause not
  found (a build without the body's via keepout read the same);
- via keepouts: the prompt allows two near the bodies and the RF lines,
  the body's outline and the rectangle over the resistor's two pads and
  the gap between them, each grown by 0.20, and a launch cutout under a
  jack's centre pad. A ``KeepOut`` with ``via`` set on any layer that
  meets a body's hull or a route centre line grown by ROUTE_CLEAR (the
  line fence's outer row plus a via pitch's spacing, so the bands the
  region and line fences stand in), meets no jack centre pad, and reaches
  more than 0.001 mm2 past the allowed area fails, so a via keepout that
  eats a line fence or a first-row via the gap rule cannot resolve still
  fails. The allowed area is those two shapes each grown by 0.20 with
  square corners (a mitred offset contains a round one, so either growth a
  runner draws fits) plus DRIFT. Read after the region rows;
- fenced routes: every route realized on L1 at 0.30 (``CPWG_50_FENCED``; a
  route ending on a pad can realize as a polygon trace with no width, read
  as the short side of its minimum rotated rectangle), and the generated
  vias read by distance to the routes' centre lines stand in two rows of at
  least four, 0.75 and 1.35 off it;
- tangency: routed copper meets each body (within 0.05 mm) in exactly three
  places, its three ports. A port's axis runs from the centroid of the body
  copper within 0.6 mm of the contact to the contact; a jack's runs along x
  from the inner end of its centre pad. At each of these 14 ends exactly
  one 0.20 mm L1 copper square (within 0.005 a side) starts 2.0 to 3.0 out
  along the axis, within 0.02 either way, measured where the prompt
  measures it: from the end of the 0.30 stub (the furthest body copper
  along the axis within 1.0 of the contact) or from the inner end of the
  jack's centre pad. Its near side stands 1.15 off the axis (within 0.02),
  the prompt's 1.0 from the 0.30 trace's copper edge. It is joined to
  the net named GND. Routed copper covers the axis from the port through the
  square's far edge, none of it (over 0.0001 mm2) stands outside a strip
  half the trace and 0.01 wide about the axis over the first 2.0 mm, and
  the centre line stays within 0.01 of the axis. Past the far edge the line
  bends on an arc of radius 0.15 + 1.0 = 1.15 within 0.01, centred within
  0.01 of the square's corner. Only at the two ends of the input feed (the
  piece of routed copper touching the input jack), which the prompt keeps
  straight, may it run straight on instead. No routed copper comes within 1.0 of any square, less 0.001,
  read from each trace's centre line as in ``cl_check.copper_gap`` (an arc
  sampled every degree sags under 0.0001 at r = 1.15; a polygon reading of
  the same copper falls up to 0.04 short where jitx strokes a short arc as
  one chord). Envelope copper over a square fails here even when the build
  reports no issue. A square at no port or jack fails;
- matching: the routed copper falls into seven connected pieces (the input
  feed, two joins, four output feeds). Each piece but the one touching the
  input jack has exactly one route with ``Route.Config(envelope_overhead=E)``,
  0 < E <= 3.0, at most five routes (the prompt's exit, bend, matched
  route, bend and entry), and every other route in it no more than 4.0 mm
  along its centre line; a zigzag of control points fails here. The input
  feed's routes are straight and carry no envelope. In the issue report with satisfied
  groups included, which carries every measurement whether met or not:
  three skew measurements (``UnmetTimeDiff``, outputs 1 to 3 against
  output 0, the fixture's constraint resolved through the cells), each
  within the prompt's 1.0 ps, in a report whose categories are complete;
  no signal measurement unmet; no
  ``UnsquiggledRoute`` or ``UnrealizedRoute``; and the unmet report names
  no "signal constraint" and no "Unable to find path".
"""

import math
import sys
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

from jitx.constraints import AtomExpr, Tags, UnaryDesignConstraint  # noqa: E402
from jitx.copper import Copper, Pour  # noqa: E402
from jitx.feature import OverlappableCopper  # noqa: E402
from jitx.inspect import visit  # noqa: E402
from jitx.issue import SignalIntegrityIssue, UnmetTimeDiff, UnrealizedRoute, UnsquiggledRoute  # noqa: E402

WIDTH = 0.30
ARM = 0.17
QUARTER = 1.6e11 / 2.45e9 / 4
ARM_TOL = 0.5
OPEN = 0.12
TRIM = 0.1
TANGENT = 2.0
DRIFT = 0.01
MAX_ENVELOPE = 3.0
EXIT_MAX = 4.0
SECTION_MAX = 5
SQUARE = 0.20
SQ_TOL = 0.005
C = 1.0
RADIUS = WIDTH / 2 + C
R_TOL = 0.01
SAG = 1e-3
PLACE_TOL = 0.02
POINT_MAX = 3.0
PITCH = 1.0
REGION_ROWS = (0.6, 1.2)
FENCE_ROWS = (WIDTH / 2 + REGION_ROWS[0], WIDTH / 2 + REGION_ROWS[1])
# Fab sheet rows 12 and 15: a 0.25 drill, and 0.25 between drill edges, so
# via centres at least 0.5 apart. A region via nearer a route centre line
# than its outer fence row (1.35) plus 0.5 can collide with a route fence via.
VIA_SPACE = 0.125 + 0.25 + 0.125
ROUTE_CLEAR = FENCE_ROWS[1] + VIA_SPACE
VIA_R = 0.25
RESISTOR_CLEAR = 0.20
# A missing via leaves a gap of two pitches, 2.0; the 0.5 over the pitch
# fails that and allows for the row's spacing around a corner, as in the
# rf-connector-launch check.
ROW_GAP = PITCH + 0.5
KEEPOUT_GROW = 0.20
POUR_GAP = (0.19, 0.23)
SKEW = 1.0e-12


def arm_pieces(g: BaseGeometry) -> list[BaseGeometry]:
    """The arm copper of a body: what an opening by OPEN removes, less the
    copper within TRIM of what it keeps, in pieces over 0.3 mm2. The
    opening keeps square corners (mitre joins): a round one reaches into an
    arm where it meets wide copper, by an amount that turns on whether the
    join is onto a stub's end or its side."""
    opened = g.buffer(-OPEN, join_style="mitre").buffer(OPEN, join_style="mitre")
    thin = g.difference(opened.buffer(TRIM))
    return [p for p in getattr(thin, "geoms", [thin]) if p.area > 0.3]


def end_allowance() -> float:
    """Arm length the reading drops at its two ends, worked on a straight
    ARM-wide arm of known length meeting WIDTH copper square on at both
    ends: the known length less the area reading."""
    known = 5.0
    g = shapely.union_all(
        [
            shapely.box(-2.0, -WIDTH / 2, 0.0, WIDTH / 2),
            shapely.box(0.0, -ARM / 2, known, ARM / 2),
            shapely.box(known, -WIDTH / 2, known + 2.0, WIDTH / 2),
        ]
    )
    (piece,) = arm_pieces(g)
    return known - piece.area / ARM


def is_square(g: BaseGeometry) -> bool:
    """Whether ``g`` is a SQUARE mm square, within SQ_TOL on each side."""
    if g.is_empty or abs(g.area - g.minimum_rotated_rectangle.area) > 1e-6:
        return False
    xy = list(g.minimum_rotated_rectangle.exterior.coords)
    return all(abs(math.dist(xy[i], xy[i + 1]) - SQUARE) <= SQ_TOL for i in range(2))


def straight(geom: BaseGeometry) -> tuple[bool, float]:
    """Whether a route's copper is one straight strip (its minimum rotated
    rectangle no wider than the trace and 0.02), and the strip's length
    less one trace width, the end caps."""
    if geom.is_empty:
        return False, 0.0
    box = geom.minimum_rotated_rectangle
    xy = list(box.exterior.coords)
    sides = sorted(math.dist(xy[i], xy[i + 1]) for i in range(2))
    return sides[0] <= WIDTH + 2 * DRIFT, sides[1] - WIDTH


def strip_width(geom: BaseGeometry) -> float:
    """Short side of a straight trace polygon's minimum rotated rectangle."""
    xy = list(geom.minimum_rotated_rectangle.exterior.coords)
    return round(min(math.dist(xy[i], xy[i + 1]) for i in range(2)), 4)


def axis_line(shapes: list) -> LineString:
    """A realized trace's centre line: ``L.centreline`` for a trace with a
    width, the long axis of its strip for a polygon trace."""
    g = getattr(shapes[0], "geometry", shapes[0]) if shapes else None
    if g is not None and getattr(g, "width", None) is None:
        xy = list(L.geom(shapes[0]).minimum_rotated_rectangle.exterior.coords)[:4]
        i = 0 if math.dist(xy[0], xy[1]) < math.dist(xy[1], xy[2]) else 1
        a = ((xy[i][0] + xy[i + 1][0]) / 2, (xy[i][1] + xy[i + 1][1]) / 2)
        b = ((xy[i + 2][0] + xy[(i + 3) % 4][0]) / 2, (xy[i + 2][1] + xy[(i + 3) % 4][1]) / 2)
        return LineString([a, b])
    return L.centreline(shapes)


out = L.output_dir()
with L.built(out, "fixture_wilkinson_tree", "WilkinsonTreeDesign", wait=120.0) as rd:
    mod = sys.modules["fixture_wilkinson_tree"]
    cells = [(str(t.path), c) for t, c in visit(rd.root, mod.WilkinsonCell)]
    trees = [str(t.path) for t, _ in visit(rd.root, mod.WilkinsonTree)]
    print(f"tree instances {trees}; cell instances {[p for p, _ in cells]}")
    if len(trees) != 1 or len(cells) != 3:
        L.fail(f"expected one WilkinsonTree and three WilkinsonCell, found {len(trees)} and {len(cells)}")
    elif any(not p.startswith(trees[0] + ".") for p, _ in cells):
        L.fail("a WilkinsonCell is not under the WilkinsonTree")

    gnd = L.net_members(rd, "GND")
    bodies = []
    squares = []
    for tr, cu in visit(rd.root, (Copper, OverlappableCopper)):
        if isinstance(cu, Pour):
            continue
        path = str(tr.path)
        g = L.geom(cu.shape if tr.transform is None else tr.transform * cu.shape)
        layer = int(cu.layer)
        if not isinstance(cu, OverlappableCopper) and layer == 0 and is_square(g):
            squares.append((path, g, id(cu) in gnd))
            continue
        owner = [cp for cp, _ in cells if path.startswith(cp + ".")]
        if not owner:
            L.fail(f"copper drawn outside a cell: {path}")
            continue
        bodies.append((owner[0], path, g, layer))
    print(f"{len(squares)} {SQUARE} mm copper squares on L1, {sum(1 for s in squares if s[2])} on GND")
    for cp, _ in cells:
        mine = [b for b in bodies if b[0] == cp]
        kinds = [type(c).__name__ for t, c in visit(rd.root, OverlappableCopper) if str(t.path).startswith(cp + ".")]
        if len(mine) != 1 or kinds != ["OverlappableCopper"] or mine[0][3] != 0:
            L.fail(f"{cp}: expected one OverlappableCopper body on L1, found {len(mine)} drawn ({kinds})")
    body_geoms = [g for _, _, g, _ in bodies]

    allowance = end_allowance()
    print(f"arm end allowance {allowance:.4f} mm (a straight arm meeting the wide copper square on)")
    for owner, path, g, _ in bodies:
        # Each arm's length is its centre line between the wide copper it
        # leaves and the wide copper it reaches (the prompt), read as its
        # area over ARM plus what the reading drops at two square ends.
        arms = arm_pieces(g)
        lengths = sorted(round(p.area / ARM + allowance, 3) for p in arms)
        print(f"{owner}: arm pieces {lengths} mm (quarter wave {QUARTER:.3f})")
        if len(arms) != 2:
            L.fail(f"{owner}: {len(arms)} pieces of {ARM}-wide arm copper, not two")
        for n in lengths:
            if abs(n - QUARTER) > ARM_TOL:
                L.fail(f"{owner}: arm {n} mm long, not {QUARTER:.3f} within {ARM_TOL}")

    pours = L.world_pours(rd)
    iso_pads = shapely.union_all(L.chip_pads(rd, mod.IsoResistor100) or [shapely.Polygon()])
    l1 = shapely.union_all([g for _, p, g in pours if int(p.layer) == 0] or [shapely.Polygon()])
    pour_keepouts = shapely.union_all(L.keepouts(rd, 0, "pour") or [shapely.Polygon()])
    if l1.is_empty:
        L.fail("no L1 GND pour realized")
    for owner, _, g, _ in bodies:
        over = l1.intersection(g).area
        near = L.gap(l1, g) if not l1.is_empty else None
        bare = g.difference(pour_keepouts).area
        print(f"{owner}: L1 pour over the body {over:.4f} mm2, {near} from it; body outside pour keepouts {bare:.4f} mm2")
        if over > 1e-3:
            L.fail(f"{owner}: L1 pour covers {over:.4f} mm2 of the body")
        if near is not None and not POUR_GAP[0] <= near <= POUR_GAP[1]:
            L.fail(f"{owner}: L1 pour stands {near:.3f} off the body, not {POUR_GAP[0]} to {POUR_GAP[1]}")
        if bare > 1e-3:
            L.fail(f"{owner}: no pour KeepOut over {bare:.4f} mm2 of the body")

    routes = L.realized_routes(rd, layer=0)
    widths = set()
    for wr in routes:
        for tr in L.world_traces(wr):
            for s in tr:
                w = getattr(getattr(s, "geometry", s), "width", None)
                widths.add(round(float(w), 4) if w is not None else strip_width(L.geom(s)))
    widths = sorted(widths)
    print(f"{len(routes)} routes realized; trace widths {widths} (a polygon trace read as its strip width)")
    if any(w is None or abs(w - WIDTH) > 1e-3 for w in widths):
        L.fail(f"trace widths {widths}, not {WIDTH}")
    lines = [axis_line(t) for wr in routes for t in L.world_traces(wr)]
    centre = shapely.union_all(lines) if lines else LineString()
    gen = L.generated_vias(rd)
    rows = {d: sum(1 for x, y in gen if abs(centre.distance(Point(x, y)) - d) < 0.02) for d in FENCE_ROWS}
    print(f"{len(gen)} generated vias; route fence rows {rows}")
    if any(n < 4 for n in rows.values()):
        L.fail(f"route fence rows {rows}: not two rows of the structure's fence")
    # The region fence: the shape a fence_via rule's tag is on, over each
    # body, is the body copper (the prompt), so its rows sit where a
    # CPWG_50_FENCED line's would, measured from the copper edge.
    rules = [c for _, c in visit(rd.root, UnaryDesignConstraint) if c.fence_via_constraint is not None]
    fence_tags = tuple(type(c.condition.atom) for c in rules if isinstance(c.condition, AtomExpr))
    print(f"fence_via rules {[repr(c) for c in rules]}")
    regions = [(path, g) for path, p, g in pours if fence_tags and any(isinstance(t, fence_tags) for t in getattr(Tags.get(p), "tags", []))]
    print(f"fence-tagged pours {[(path, round(g.area, 3)) for path, g in regions]}")
    for owner, _, g, _ in bodies:
        mine = [r for _, r in regions if r.intersects(g)]
        if not mine:
            L.fail(f"{owner}: no fence-tagged shape over the body, so no region fence")
            continue
        region = shapely.union_all(mine)
        diff = region.symmetric_difference(g).area
        tol = DRIFT * g.exterior.length
        print(f"{owner}: fence region differs from the body copper by {diff:.4f} mm2 (tolerance {tol:.4f}: {DRIFT} along its {g.exterior.length:.3f} mm outline)")
        if diff > tol:
            L.fail(f"{owner}: the fence region is not the body copper: they differ by {diff:.4f} mm2, over {tol:.4f}")
            continue
        # Each row is the body outline offset by the row's distance (a true
        # offset, round at convex corners), every ring of it, the inside of
        # the loop included. Free of it: what lies within ROUTE_CLEAR of a
        # route centre line, and within RESISTOR_CLEAR plus a via pad's
        # radius of a resistor pad (the prompt's via keepout there). Pieces
        # are line-merged so a ring's start point does not split a stretch.
        # Each stretch is scored by its widest gap; floor(n / PITCH) - 1,
        # the vias a piece of length n holds, is printed.
        hull = g.convex_hull
        holes = hull.difference(g.buffer(1e-3))
        loop = max(getattr(holes, "geoms", [holes]), key=lambda q: q.area)
        iso_here = iso_pads.intersection(hull.buffer(1.0))
        for r in REGION_ROWS:
            buf = g.buffer(r, quad_segs=32)
            rings = shapely.union_all([buf.exterior, *buf.interiors])
            free = rings.difference(centre.buffer(ROUTE_CLEAR)).difference(iso_here.buffer(RESISTOR_CLEAR + VIA_R))
            if not free.is_empty:
                free = shapely.line_merge(free)
            pieces = [q for q in getattr(free, "geoms", [free]) if not q.is_empty and q.length > 1e-6]
            tally = {"inside the loop": [0, 0, 0.0], "outside the loop": [0, 0, 0.0]}
            worst: list[tuple[str, float, float]] = []
            for q in pieces:
                where = "inside the loop" if loop.contains(q.interpolate(0.5, normalized=True)) else "outside the loop"
                at = sorted(q.project(Point(x, y)) for x, y in gen if q.distance(Point(x, y)) <= VIA_SPACE)
                gaps = [b - a for a, b in zip([0.0, *at], [*at, q.length])]
                tally[where][0] += max(0, math.floor(q.length / PITCH) - 1)
                tally[where][1] += len(at)
                tally[where][2] += q.length
                worst.append((where, max(gaps), q.length))
                print(f"{owner}: row {r} {where}: piece {q.length:.3f} mm from ({q.coords[0][0]:.2f}, {q.coords[0][1]:.2f}), {len(at)} vias, widest gap {max(gaps):.3f}")
            for where, (need, have, length) in tally.items():
                widest = max((w for z, w, _ in worst if z == where), default=0.0)
                print(f"{owner}: row {r} {where}: {length:.3f} mm free, room for {need}, {have} region fence vias on it, widest gap {widest:.3f}")
            if r == REGION_ROWS[0]:
                # A stretch under two pitches holds no via by the count rule
                # (floor(n) - 1 = 0), so its gaps are not scored.
                for where, w, n in sorted(worst, key=lambda z: z[0] != "inside the loop"):
                    if n >= 2 * PITCH and w > ROW_GAP:
                        L.fail(f"{owner}: the first row {where} has a {w:.3f} mm gap on a {n:.3f} mm free stretch, over {ROW_GAP}")
                        break

    # Near the bodies and the RF lines the prompt allows two via keepouts,
    # the body's outline and the rectangle over the resistor's two pads and
    # the gap between them, each grown by 0.20 (square corners allowed),
    # and a launch cutout under a jack's centre pad. Any other via keepout
    # there can eat a fence the gap rule or the route rows do not resolve.
    near_bodies = shapely.union_all([g.convex_hull.buffer(ROUTE_CLEAR) for g in body_geoms] + [centre.buffer(ROUTE_CLEAR)])
    launch_pads = shapely.union_all(L.sma_centre_pads(rd))
    allowed = shapely.union_all(
        [g.buffer(KEEPOUT_GROW + DRIFT, join_style="mitre") for g in body_geoms]
        + [
            iso_pads.intersection(g.convex_hull.buffer(1.0)).minimum_rotated_rectangle.buffer(KEEPOUT_GROW + DRIFT, join_style="mitre")
            for g in body_geoms
        ]
    )
    for layer in range(4):
        for k in L.keepouts(rd, layer, "via"):
            if not k.intersects(near_bodies) or k.intersects(launch_pads):
                continue
            extra = k.difference(allowed).area
            if extra > 1e-3:
                c = k.centroid
                L.fail(f"a via KeepOut on layer {layer} near ({c.x:.3f}, {c.y:.3f}) reaches {extra:.4f} mm2 past the body and the resistor's pad rectangle grown by {KEEPOUT_GROW}, the only via keepouts the prompt allows near the bodies and RF lines")

    geoms = {wr.path: L.route_geom(wr) for wr in routes}
    copper = shapely.union_all(list(geoms.values())) if geoms else shapely.Polygon()
    pieces = list(getattr(copper, "geoms", [copper]))
    jacks = L.sma_centre_pads(rd)
    jin = jacks[0] if jacks else None
    input_piece = next((q for q in pieces if jin is not None and q.distance(jin) < 1e-3), None)
    route_keep = L.route_keepouts(rd, 0)
    used: set[str] = set()
    ends = []
    for owner, _, g, _ in bodies:
        touch = copper.intersection(g.buffer(0.05))
        contacts = [c for c in getattr(touch, "geoms", [touch]) if not c.is_empty and c.area > 1e-4]
        print(f"{owner}: {len(contacts)} places where routed copper meets the body")
        if len(contacts) != 3:
            L.fail(f"{owner}: routed copper meets the body at {len(contacts)} places, not its three ports")
        for c in contacts:
            cx, cy = c.centroid.x, c.centroid.y
            near = g.intersection(Point(cx, cy).buffer(0.6))
            n = math.hypot(cx - near.centroid.x, cy - near.centroid.y) if not near.is_empty else 0.0
            if n < 1e-6:
                L.fail(f"{owner}: no body copper at ({cx:.3f}, {cy:.3f}) to take the port axis from")
                continue
            ux, uy = (cx - near.centroid.x) / n, (cy - near.centroid.y) / n
            # The prompt measures the RoutePoint from the end of the 0.30
            # stub: the furthest body copper along the axis near the contact.
            stub = g.intersection(shapely.Polygon([(cx + ux * s - uy * w, cy + uy * s + ux * w) for s, w in ((-1.0, -0.2), (1.0, -0.2), (1.0, 0.2), (-1.0, 0.2))]))
            tip = max(((x - cx) * ux + (y - cy) * uy for x, y in shapely.get_coordinates(stub)), default=0.0)
            ends.append((f"{owner}: port at ({cx:.3f}, {cy:.3f})", (cx, cy), (ux, uy), tip))
    for k, pad in enumerate(jacks):
        # A jack's line leaves the inner end of its centre pad along x, into the board.
        x0, y0, x1, y1 = pad.bounds
        inward = 1.0 if pad.centroid.x < 0 else -1.0
        ends.append((f"jack pad {k}", (x1 if inward > 0 else x0, (y0 + y1) / 2), (inward, 0.0), 0.0))

    for name, (cx, cy), (ux, uy), tip in ends:
        on_input = input_piece is not None and Point(cx, cy).distance(input_piece) < 0.1

        def slab(
            s0: float, s1: float, t0: float, t1: float, o: tuple[float, float] = (cx, cy), u: tuple[float, float] = (ux, uy)
        ) -> shapely.Polygon:
            """The box s0..s1 along the axis and t0..t1 across it."""
            return shapely.Polygon(
                [(o[0] + u[0] * s - u[1] * t, o[1] + u[1] * s + u[0] * t) for s, t in ((s0, t0), (s1, t0), (s1, t1), (s0, t1))]
            )

        wide = copper.intersection(slab(0.0, TANGENT - WIDTH / 2, -2.0, 2.0)).difference(shapely.union_all(body_geoms).buffer(0.05))
        stray = wide.difference(slab(0.0, TANGENT, -(WIDTH / 2 + DRIFT), WIDTH / 2 + DRIFT)).area
        # The square: GND copper beside the line, its near side C off the
        # copper (WIDTH / 2 + C off the axis), from the RoutePoint, 2.0 to
        # POINT_MAX out, to SQUARE further.
        found = []
        for path, sg, on_gnd in squares:
            loc = [((x - cx) * ux + (y - cy) * uy, (y - cy) * ux - (x - cx) * uy) for x, y in sg.exterior.coords]
            s0, s1 = min(s for s, _ in loc), max(s for s, _ in loc)
            t0, t1 = min(t for _, t in loc), max(t for _, t in loc)
            side = 1.0 if t0 + t1 > 0 else -1.0
            near_t = min(abs(t0), abs(t1))
            if TANGENT - PLACE_TOL <= s0 - tip <= POINT_MAX + PLACE_TOL and abs(near_t - RADIUS) <= PLACE_TOL:
                found.append((path, sg, on_gnd, s0, s1, side))
        print(f"{name}: stub end {tip:.3f} along; copper squares beside the exit (along from, to, side, on GND) {[(round(f[3], 3), round(f[4], 3), f[5], f[2]) for f in found]}")
        if len(found) != 1:
            L.fail(f"{name}: {len(found)} {SQUARE} mm copper squares {RADIUS} off the axis past the exit's RoutePoint, not one")
            continue
        path, sg, on_gnd, s0, far, side = found[0]
        used.add(path)
        if not on_gnd:
            L.fail(f"{name}: the tangency square is not on GND")
        reach = far
        band = centre.intersection(slab(0.0, reach, -1.0, 1.0))
        pts = [p for line in getattr(band, "geoms", [band]) for p in getattr(line, "coords", [])]
        drift = max((abs((y - cy) * ux - (x - cx) * uy) for x, y in pts), default=None)
        axis = LineString([(cx, cy), (cx + ux * reach, cy + uy * reach)])
        held = axis.intersection(copper).length
        print(f"{name}: copper on the axis {held:.3f} of {reach:.3f}, centre line {drift} off it, off the strip {stray:.5f} mm2")
        if held < reach - 1e-3 or stray > 1e-4 or drift is None or drift > DRIFT:
            L.fail(f"{name}: the line does not hold the axis from the port through the square's far edge, {reach:.3f} mm")
        # Past the far edge the line runs straight on (the input feed) or
        # turns around the square's corner at RADIUS.
        on = centre.intersection(slab(reach, reach + 1.0, -1.0, 1.0))
        more = [p for line in getattr(on, "geoms", [on]) for p in getattr(line, "coords", [])]
        if on_input and more and max(abs((y - cy) * ux - (x - cx) * uy) for x, y in more) <= DRIFT:
            print(f"{name}: on the input feed, the line runs straight on past the square")
        else:
            corner = (cx + ux * far - uy * side * RADIUS, cy + uy * far + ux * side * RADIUS)
            bends = [(round(a.radius, 4), round(math.dist(a.center, corner), 4)) for wr in routes for tr in L.world_traces(wr) for a in L.arcs(tr)]
            bends = [b for b in bends if b[1] < 0.5]
            print(f"{name}: arcs centred within 0.5 of the square's corner: (radius, centre off the corner) {bends}")
            if not any(d <= R_TOL and abs(r - RADIUS) <= R_TOL for r, d in bends):
                L.fail(f"{name}: no bend of radius {RADIUS} centred on the tangency square's corner: {bends}")
    for path, sg, _ in squares:
        gap = L.copper_gap(routes, sg)
        print(f"{path}: routed copper {gap:.4f} from it (centre-line reading), {L.gap(copper, sg)} as a polygon")
        if gap < 0:
            L.fail(f"{path}: routed copper overlaps the GND tangency square")
        elif gap < C - SAG:
            L.fail(f"{path}: routed copper {gap:.4f} from the tangency square, under its {C} clearance")
    stray_sq = [path for path, _, _ in squares if path not in used]
    if stray_sq:
        L.fail(f"copper squares at no connection point: {stray_sq}")
    inside = copper.intersection(shapely.union_all(route_keep)).area if route_keep else 0.0
    print(f"routed copper inside route keepouts {inside:.5f} mm2")
    if inside > 1e-4:
        L.fail(f"routed copper inside route keepouts: {inside:.5f} mm2")

    print(f"{len(pieces)} pieces of routed copper")
    if len(pieces) != 7:
        L.fail(f"{len(pieces)} pieces of routed copper, not the input feed, two joins and four output feeds")
    for i, piece in enumerate(pieces):
        members = [wr for wr in routes if geoms[wr.path].intersects(piece)]
        is_input = jin is not None and piece.distance(jin) < 1e-3
        configured = []
        for wr in members:
            env = getattr(wr.route.config, "envelope_overhead", None) if wr.route.config is not None else None
            if env:
                configured.append((wr.path, env))
                if is_input:
                    L.fail(f"{wr.path}: the input feed carries an envelope, where the prompt keeps it straight")
                if env > MAX_ENVELOPE + 1e-9:
                    L.fail(f"{wr.path}: envelope {env}, over {MAX_ENVELOPE}")
                continue
            if is_input:
                ok, _ = straight(geoms[wr.path])
                if not ok:
                    L.fail(f"{wr.path}: the input feed is not straight")
                continue
            length = sum(axis_line(tr).length for tr in L.world_traces(wr))
            if length > EXIT_MAX:
                L.fail(f"{wr.path}: a {length:.3f} mm route with no envelope on a matched section, over {EXIT_MAX}")
        name = "input feed" if is_input else f"piece {i}"
        print(f"{name}: {len(members)} routes, configured {configured}")
        if not is_input:
            if len(configured) != 1:
                L.fail(f"{name}: {len(configured)} routes with an envelope, not one")
            if len(members) > SECTION_MAX:
                L.fail(f"{name}: {len(members)} routes, more than the exit, bend, matched route, bend and entry")

    # The report with satisfied groups carries every measurement, met or
    # not; each measurement says whether it is met.
    report = rd.issues(satisfied=True, wait=15.0)
    if not report.complete:
        L.fail("the issue report is incomplete: a category is still pending after the wait")
    bad = L.issue_kinds(L.issues_text(rd), "signal constraint", "Unable to find path")
    bad += [i.text for i in report.of(UnsquiggledRoute) + report.of(UnrealizedRoute)]
    bad += [i.text for i in report.of(SignalIntegrityIssue) if not i.satisfied]
    if bad:
        L.fail(f"issues: {bad}")
    skews = report.of(UnmetTimeDiff)
    for d in skews:
        worst = max(abs(v) for v in d.measured_range) if d.measured_range else None
        shown = f"{worst * 1e12:.3f} ps" if worst is not None else "none"
        print(f"skew {shown}, satisfied {d.satisfied}: {d.text}")
        if worst is None or worst > SKEW * (1 + 1e-9):
            L.fail(f"skew {shown} over the prompt's {SKEW * 1e12:.1f} ps: {d.text}")
    if len(skews) != 3:
        L.fail(f"{len(skews)} skew measurements, not the constraint's three (outputs 1 to 3 against output 0)")
L.finish()
