"""Route-fence measurement shared by the feed-fence cases.

A route fence comes from ``RoutingStructure.Layer.fence`` on the structure
applied to the route (spike S9). A ``fence_via`` design rule fences no route
(S4), so a design that relies on one has no vias along the feed.

The vias are read with ``lc_check.generated_vias``, which returns every
generated via and does not say which rule made one. A row is the vias in a
narrow band at the row's distance from the trace edge (``ROW_TOL`` either
side), so a stitch or pour-fence via counts only if it lands in that band.
Measured on 2026-11-03 (jitx 4.6.0), splitting the vias by jitx's internal
records in a scratch script:

- each feed case's solution with a ``stitch_via`` rule (square, pitch 1.0,
  inset 0.2) added on every ground pour: vias-along-the-feed gave 606 stitch
  and 28 fence vias, the nearest stitch via 0.964 from the trace edge, none
  in its 0.45 to 0.50 row; fence-cpwg-two-rows gave 587 stitch and 61 fence
  vias, no stitch via within 1.6 of the trace edge. Both checks passed with
  the same rows as the fence vias alone;
- vias-along-the-feed with a ``fence_via`` rule (offset -0.25) on the layer-0
  pour and the unfenced CPWG_50 applied: 106 vias, none within 1.6 of the
  trace edge, so the rows come back empty and the check fails.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import shapely
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from jitx.circuit import Route

import lc_check as L

ROW_TOL = 0.02


@dataclass
class FenceVia:
    x: float
    y: float
    side: int
    edge: float
    t: float


@dataclass
class Feed:
    line: LineString
    width: float
    copper: BaseGeometry
    vias: list[FenceVia] = field(default_factory=list)

    @property
    def length(self) -> float:
        return float(self.line.length)


def centreline(route: Route) -> tuple[LineString, float] | None:
    """Centreline and width of a route realized as straight polyline pieces.

    Fails (returns None after recording a failure) on a shape with no width,
    such as a Polygon (spike S8), or on an arc."""
    pts: list[tuple[float, float]] = []
    widths: set[float] = set()
    shapes = [s for tr in route.traces or [] for s in tr.shapes]
    if not shapes:
        L.fail("the feed route has no realized traces")
        return None
    for s in shapes:
        g = getattr(s, "geometry", s)
        w = getattr(g, "width", None)
        elements = getattr(g, "elements", None)
        if w is None or elements is None:
            L.fail(f"feed trace shape {type(g).__name__} has no width; it cannot be checked as a line")
            return None
        widths.add(round(float(w), 4))
        for e in elements:
            if not (isinstance(e, tuple) and len(e) == 2):
                L.fail(f"feed trace has a non-point element {e!r}; this check measures straight runs")
                return None
            pts.append((float(e[0]), float(e[1])))
    if len(widths) != 1:
        L.fail(f"feed trace has several widths {sorted(widths)}")
        return None
    return LineString(pts), widths.pop()


def measure(rd: Any, route: Route) -> Feed | None:
    cl = centreline(route)
    if cl is None:
        return None
    line, width = cl
    feed = Feed(line=line, width=width, copper=L.route_geom(route))
    for x, y in L.generated_vias(rd):
        pt = Point(x, y)
        t = float(line.project(pt))
        a = line.interpolate(max(t - 0.01, 0.0))
        b = line.interpolate(min(t + 0.01, line.length))
        cross = (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x)
        feed.vias.append(
            FenceVia(x=x, y=y, side=1 if cross > 0 else -1, edge=float(line.distance(pt)) - width / 2, t=t)
        )
    return feed


def straight_row(feed: Feed, side: int, lo: float, hi: float) -> list[FenceVia]:
    """Vias on one side whose edge distance is in [lo, hi] and whose foot
    lies strictly inside the straight run."""
    return sorted(
        (v for v in feed.vias if v.side == side and lo <= v.edge <= hi and 0.0 < v.t < feed.length),
        key=lambda v: v.t,
    )


def full_count(feed: Feed, pitch: float) -> int:
    return math.floor(feed.length / pitch + 1e-9)


def check_pitch(row: list[FenceVia], pitch: float, label: str) -> None:
    steps = [b.t - a.t for a, b in zip(row, row[1:])]
    if not steps:
        return
    bad = [round(s, 3) for s in steps if abs(s - pitch) > 0.05 * pitch]
    if bad:
        L.fail(f"{label}: steps {bad} differ from the {pitch} pitch")
    else:
        L.ok(f"{label}: steps {min(steps):.3f} to {max(steps):.3f}")


def pour_both_sides(rd: Any, feed: Feed, layer: int, probe_edge: float) -> None:
    """The layer's pour copper is present on both sides of the feed, at
    ``probe_edge`` from the trace edge, at a quarter, half and three quarters
    of the run."""
    pours = [g for _, p, g in L.world_pours(rd) if p.layer == layer and not g.is_empty]
    if not pours:
        L.fail(f"no pour copper on layer {layer}")
        return
    copper = shapely.union_all(pours)
    gaps = [L.gap(copper, feed.copper)]
    print(f"layer {layer} pour gap to the feed: {gaps[0]}")
    for frac in (0.25, 0.5, 0.75):
        t = feed.length * frac
        a = feed.line.interpolate(t - 0.01)
        b = feed.line.interpolate(t + 0.01)
        dx, dy = b.x - a.x, b.y - a.y
        n = math.hypot(dx, dy)
        nx, ny = -dy / n, dx / n
        c = feed.line.interpolate(t)
        r = feed.width / 2 + probe_edge
        for side in (1, -1):
            pt = Point(c.x + side * r * nx, c.y + side * r * ny)
            if not copper.contains(pt):
                L.fail(f"no layer-{layer} pour copper at {probe_edge} from the trace edge, side {side}, {frac:.0%} along the feed")
                return
    L.ok(f"layer-{layer} pour present on both sides of the feed at {probe_edge} from the trace edge")


def layer_gap(rd: Any, feed: Feed, layer: int) -> float | None:
    pours = [g for _, p, g in L.world_pours(rd) if p.layer == layer and not g.is_empty]
    if not pours:
        return None
    return L.gap(shapely.union_all(pours), feed.copper)
