"""Check for the wilkinson-tree case.

Usage: check_wilkinson_tree.py <output-dir>

Builds <output>/fixture_wilkinson_tree.py, captures it, and checks the tree
against the prompt. Every number below is the prompt's or the fixture's, or
worked from them:

- hierarchy: three ``WilkinsonCell`` instances, each under the one
  ``WilkinsonTree``, and each holding exactly one ``OverlappableCopper`` body
  on L1; no other ``Copper`` or ``OverlappableCopper`` in the design (a
  meander drawn by hand, or a body drawn in the tree, fails here);
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
- region fence: around each body, at least 8 generated vias within 2.0 mm of
  its outline that stand more than 2.0 mm from every route's centre line, so
  they are not the route fence (its outer row stands 1.35 off the centre
  line, and a 0.500 via pad reaches 1.6);
- fenced routes: every route realized on L1 at 0.30 (``CPWG_50_FENCED``; a
  route ending on a pad can realize as a polygon trace with no width, read
  as the short side of its minimum rotated rectangle), and the generated
  vias read by distance to the routes' centre lines stand in two rows of at
  least four, 0.75 and 1.35 off it;
- tangency: routed copper meets each body (within 0.05 mm) in exactly three
  places, its three ports. A port's axis runs from the centroid of the body
  copper within 0.6 mm of the contact to the contact. Routed copper covers
  that axis for the first 2.0 mm, and none of it (over 0.0001 mm2) stands
  outside a strip half the trace and 0.01 wide about the axis over that
  length, so the route leaves straight along the axis;
- matching: the routed copper falls into seven connected pieces (the input
  feed, two joins, four output feeds). Each piece but the one touching the
  input jack has exactly one route with ``Route.Config(envelope_overhead=E)``,
  0 < E <= 3.0, at most three routes, and every other route in it straight
  (its copper's minimum rotated rectangle no wider than the trace and 0.02)
  and no more than 4.0 mm long; a zigzag of control points fails here. The
  input feed's routes are straight. In the issue report with satisfied
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
FENCE_MIN = 8
FENCE_ROWS = (WIDTH / 2 + 0.6, WIDTH / 2 + 1.2)
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

    drawn = L.authored_copper(rd)
    bodies = []
    for path, g, layer in drawn:
        owner = [cp for cp, _ in cells if path.startswith(cp + ".")]
        if not owner:
            L.fail(f"copper drawn outside a cell: {path}")
            continue
        bodies.append((owner[0], path, g, layer))
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
    for owner, _, g, _ in bodies:
        ring = [(x, y) for x, y in gen if g.distance(Point(x, y)) <= 2.0 and centre.distance(Point(x, y)) > 2.0]
        print(f"{owner}: {len(ring)} region fence vias")
        if len(ring) < FENCE_MIN:
            L.fail(f"{owner}: {len(ring)} fence vias around the body away from the routes, under {FENCE_MIN}")

    geoms = {wr.path: L.route_geom(wr) for wr in routes}
    copper = shapely.union_all(list(geoms.values())) if geoms else shapely.Polygon()
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

            def slab(s0: float, s1: float, half: float) -> shapely.Polygon:
                return shapely.Polygon(
                    [
                        (cx + ux * s0 - uy * half, cy + uy * s0 + ux * half),
                        (cx + ux * s1 - uy * half, cy + uy * s1 + ux * half),
                        (cx + ux * s1 + uy * half, cy + uy * s1 - ux * half),
                        (cx + ux * s0 + uy * half, cy + uy * s0 - ux * half),
                    ]
                )

            wide = copper.intersection(slab(0.0, TANGENT - WIDTH / 2, 2.0)).difference(g.buffer(0.05))
            stray = wide.difference(slab(0.0, TANGENT, WIDTH / 2 + DRIFT)).area
            axis = LineString([(cx, cy), (cx + ux * TANGENT, cy + uy * TANGENT)])
            held = axis.intersection(copper).length
            heading = math.degrees(math.atan2(uy, ux))
            print(f"{owner}: port at ({cx:.3f}, {cy:.3f}) heading {heading:.1f}: copper on the axis {held:.3f} of {TANGENT}, off it {stray:.5f} mm2")
            if held < TANGENT - 1e-3 or stray > 1e-4:
                L.fail(f"{owner}: the route at ({cx:.3f}, {cy:.3f}) does not leave straight on the port axis for {TANGENT} mm")

    pieces = list(getattr(copper, "geoms", [copper]))
    jin = L.sma_centre_pads(rd)[0] if L.sma_centre_pads(rd) else None
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
                if env > MAX_ENVELOPE + 1e-9:
                    L.fail(f"{wr.path}: envelope {env}, over {MAX_ENVELOPE}")
                continue
            ok, length = straight(geoms[wr.path])
            if not ok:
                L.fail(f"{wr.path}: not straight between its ends, with no envelope: length drawn by hand")
            elif not is_input and length > EXIT_MAX:
                L.fail(f"{wr.path}: a {length:.3f} mm route with no envelope on a matched section, over {EXIT_MAX}")
        name = "input feed" if is_input else f"piece {i}"
        print(f"{name}: {len(members)} routes, configured {configured}")
        if not is_input:
            if len(configured) != 1:
                L.fail(f"{name}: {len(configured)} routes with an envelope, not one")
            if len(members) > 3:
                L.fail(f"{name}: {len(members)} routes, more than the exit, section and entry")

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
