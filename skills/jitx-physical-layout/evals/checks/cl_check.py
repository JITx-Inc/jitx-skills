"""Shared helpers for the code-layout eval checks.

Each check builds the runner's design in ``<output>`` with a runtime it starts
for that directory and stops at exit, captures it, measures the realized
copper, prints what it measured, and exits nonzero on a failure.

What a headless build reads back after ``rd.capture()``:

- ``Pour.shape`` holds the computed pour copper, holes included, or
  ``Empty()`` when the pour did not realize;
- ``Route.traces[*].shapes`` holds the realized trace shapes (a trace can
  come back as a ``Polygon`` with no width); a route with no traces did not
  realize;
- ``rd.query(Via)`` returns the vias the runtime generated (route fences,
  stitching) together with the vias the design places in code, which
  ``generated_vias`` leaves out;
- ``rd.issues(...)`` returns the design issues, timing among them.
"""

from __future__ import annotations

import importlib
import json
import math
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import shapely
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from jitx.circuit import Route
from jitx.copper import Copper, Pour
from jitx.design import Design
from jitx.feature import OverlappableCopper
from jitx.inspect import visit
from jitx.landpattern import Pad, PadShape
from jitx.run.runtime import Runtime
from jitx.shapes import Shape
from jitx.shapes.primitive import Empty
from jitx.via import Via

FAILURES: list[str] = []

SKILL = Path(__file__).resolve().parents[2]


def fail(msg: str) -> None:
    """Record a failed expectation; the check exits nonzero at the end."""
    FAILURES.append(msg)
    print(f"FAIL: {msg}")


def ok(msg: str) -> None:
    print(f"ok: {msg}")


def finish() -> None:
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        sys.exit(1)
    print("all checks passed")
    sys.exit(0)


def output_dir() -> Path:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <output-dir>", file=sys.stderr)
        sys.exit(2)
    out = Path(sys.argv[1]).resolve()
    if not (out / "pyproject.toml").is_file():
        print(f"error: {out} has no pyproject.toml; copy the fixture there first", file=sys.stderr)
        sys.exit(2)
    return out


def load_design(out: Path, module: str, cls: str) -> type[Design]:
    """Import ``module.cls`` from the runner's output directory."""
    sys.path.insert(0, str(out))
    mod = importlib.import_module(module)
    design = getattr(mod, cls)
    if not (isinstance(design, type) and issubclass(design, Design)):
        print(f"error: {module}.{cls} is not a Design subclass", file=sys.stderr)
        sys.exit(2)
    return design


@contextmanager
def runtime_for(out: Path) -> Iterator[None]:
    """Start a runtime for ``out`` and stop it on exit, whatever happens."""
    start = subprocess.run(
        ["jitx", "runtime", "start", "--background", "--project", str(out)],
        capture_output=True,
        text=True,
    )
    if start.returncode != 0:
        print(start.stdout + start.stderr, file=sys.stderr)
        print("error: could not start a JITX runtime for the output directory", file=sys.stderr)
        sys.exit(2)
    try:
        yield
    finally:
        subprocess.run(
            ["jitx", "runtime", "stop", "--project", str(out)],
            capture_output=True,
            text=True,
        )


@contextmanager
def built(out: Path, module: str, cls: str, wait: float = 60.0) -> Iterator[Any]:
    """Submit and capture the design; yields the RuntimeDesign.

    The stored design state is removed first: a headless submit after a
    design change otherwise aborts at "stabilization".
    """
    design = load_design(out, module, cls)
    stored = out / "designs" / f"{module}.{cls}"
    if stored.exists():
        shutil.rmtree(stored)
    with runtime_for(out):
        with Runtime(project=out) as r:
            rd = r.submit(design)
            rd.capture(wait=wait)
            yield rd


def bare_fixture(module: str, into: Path) -> Path:
    """Copy the inputs of the case whose fixture module is ``module`` into ``into``."""
    for case in sorted((SKILL / "evals" / "cases").glob("*.json")):
        inputs = json.loads(case.read_text())["inputs"]
        if f"{module}.py" in inputs:
            into.mkdir(parents=True, exist_ok=True)
            for dst, src in inputs.items():
                shutil.copy(SKILL / src, into / dst)
            return into
    raise FileNotFoundError(f"no case lists {module}.py")


# ---------------------------------------------------------------- reading


def issues_text(rd: Any, wait: float = 15.0) -> str:
    """The runtime's design issue report, as text."""
    return rd.issues(satisfied=False, wait=wait).text()


def geom(shape: Any) -> BaseGeometry:
    """Shapely geometry of a jitx shape, holes kept."""
    if isinstance(shape, Empty) or isinstance(getattr(shape, "geometry", None), Empty):
        return shapely.Polygon()
    return shape.to_shapely().g


def world_pours(rd: Any) -> list[tuple[str, Pour, BaseGeometry]]:
    """Every pour in the design, with its computed copper in board coordinates."""
    out: list[tuple[str, Pour, BaseGeometry]] = []
    for trace, p in visit(rd.root, Pour):
        s = p.shape
        if trace.transform is not None and not isinstance(s, Empty):
            s = trace.transform * s
        out.append((str(trace.path), p, geom(s)))
    return out


def world_routes(rd: Any) -> list[tuple[str, Route]]:
    return [(str(trace.path), r) for trace, r in visit(rd.root, Route)]


def route_geom(route: Route) -> BaseGeometry:
    """Union of a route's realized trace shapes (empty when it did not realize)."""
    shapes = [geom(s) for tr in route.traces or [] for s in tr.shapes]
    return shapely.union_all(shapes) if shapes else shapely.Polygon()


def trace_widths(route: Route) -> list[float | None]:
    """Width of every realized trace shape; None for a shape with no width
    (a ``Polygon``), which a width check must not skip silently."""
    ws: list[float | None] = []
    for tr in route.traces or []:
        for s in tr.shapes:
            w = getattr(getattr(s, "geometry", s), "width", None)
            ws.append(None if w is None else round(float(w), 4))
    return ws


def pad_world(rd: Any, pad: Pad) -> BaseGeometry:
    """World geometry of one pad's copper."""
    for trace, p in visit(rd.root, Pad):
        if p is pad:
            if trace.transform is None or p.transform is None:
                raise ValueError(f"unresolved frame for {trace.path}")
            s: Shape = p.shape.shape if isinstance(p.shape, PadShape) else p.shape
            return geom((trace.transform * p.transform) * s)
    raise KeyError("pad not found")


def placed_vias(rd: Any) -> list[tuple[float, float, Via]]:
    """Centres of the vias the design places in code, with the via object."""
    out = []
    for trace, v in visit(rd.root, Via):
        if trace.transform is None or v.transform is None:
            continue
        x, y = (trace.transform * v.transform).trs[0]
        out.append((float(x), float(y), v))
    return out


def generated_vias(rd: Any) -> list[tuple[float, float]]:
    """Centres of the vias the runtime generated (route fences, stitching).

    ``rd.query(Via)`` yields them together with the vias placed in code;
    those are the ``Via`` objects ``visit`` lists in the captured tree, and
    they are left out by identity."""
    placed = {id(v) for _, v in visit(rd.root, Via)}
    out = []
    for trace, v in rd.query(Via):
        if id(v) in placed:
            continue
        if trace.transform is None or v.transform is None:
            raise ValueError(f"unresolved frame for a generated via at {trace.path}")
        x, y = (trace.transform * v.transform).translation
        out.append((float(x), float(y)))
    return out


def authored_copper(rd: Any) -> list[tuple[str, BaseGeometry, int]]:
    """``Copper`` and ``OverlappableCopper`` shapes the design draws in code,
    in board coordinates, with their layer. Pads are not included."""
    out = []
    for trace, c in visit(rd.root, (Copper, OverlappableCopper)):
        if isinstance(c, Pour):
            continue
        s = c.shape
        if trace.transform is not None:
            s = trace.transform * s
        out.append((str(trace.path), geom(s), int(c.layer)))
    return out


def gap(a: BaseGeometry, b: BaseGeometry) -> float:
    return round(float(a.distance(b)), 4)


def segments(route: Route) -> list[tuple[tuple[float, float], tuple[float, float], float]]:
    """The straight pieces of every realized ``Polyline`` trace: (start, end, width)."""
    out = []
    for tr in route.traces or []:
        for s in tr.shapes:
            g = getattr(s, "geometry", s)
            pts = getattr(g, "elements", None)
            w = getattr(g, "width", None)
            if pts is None or w is None:
                continue
            xf = getattr(s, "transform", None)
            coords = []
            for p in pts:
                if not (isinstance(p, tuple) and len(p) == 2):
                    break
                coords.append((float(p[0]), float(p[1])))
            else:
                if xf is not None:
                    coords = [tuple(map(float, xf * c)) for c in coords]
                out += [(a, b, float(w)) for a, b in zip(coords, coords[1:])]
    return out


def seg_len(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def dump(obj: Any) -> None:
    print(json.dumps(obj, indent=1, default=str))


# ---------------------------------------------------------------- shared checks


def sma_centre_pads(rd: Any) -> list[BaseGeometry]:
    """World geometry of each Würth SMA's centre pad, left to right."""
    from jitxexamples.components.connectors.wurth_elektronik_60312202114514 import (
        Wurth60312202114514,
    )

    pads = []
    for _, comp in visit(rd.root, Wurth60312202114514):
        pads.append(pad_world(rd, comp.landpattern.sig))
    return sorted(pads, key=lambda g: g.centroid.x)


def realized_routes(rd: Any, layer: int | None = None) -> list[tuple[str, Route]]:
    """Every route in the design, failing each one that did not realize (no
    traces, or a blocked status) and, with ``layer``, each one on another
    layer. Returns the realized ones."""
    good = []
    routes = world_routes(rd)
    if not routes:
        fail("the design has no Route")
    for path, r in routes:
        status = getattr(r, "status", None)
        if not r.traces or (status is not None and not status.routed):
            fail(f"{path}: route did not realize (status {status}, {len(r.traces or [])} traces)")
            continue
        if layer is not None and r.layer != layer:
            fail(f"{path}: on layer {r.layer}, not layer {layer}")
        good.append((path, r))
    return good


def no_authored_copper(rd: Any, why: str) -> None:
    """Fail on any ``Copper`` or ``OverlappableCopper`` drawn in code."""
    drawn = authored_copper(rd)
    if drawn:
        fail(f"copper drawn in code where {why}: {[p for p, _, _ in drawn]}")
    else:
        ok("no copper drawn in code")


def joins(copper: BaseGeometry, a: BaseGeometry, b: BaseGeometry) -> bool:
    """True when one connected piece of ``copper`` touches both ``a`` and ``b``."""
    for piece in getattr(copper, "geoms", [copper]):
        if piece.distance(a) < 1e-3 and piece.distance(b) < 1e-3:
            return True
    return False


def _end_point(el: Any, last: bool) -> tuple[float, float] | None:
    """First (or last) point of one ArcPolyline element: a point or an Arc."""
    if isinstance(el, tuple) and len(el) == 2:
        return (float(el[0]), float(el[1]))
    centre = getattr(el, "center", None)
    if centre is None:
        return None
    a = math.radians(float(el.start) + (float(el.arc) if last else 0.0))
    r = float(el.radius)
    return (float(centre[0]) + r * math.cos(a), float(centre[1]) + r * math.sin(a))


def trace_ends(route: Route) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """First and last point of each realized trace shape, in board
    coordinates. Elements may be points or arcs."""
    out = []
    for tr in route.traces or []:
        for s in tr.shapes:
            g = getattr(s, "geometry", s)
            els = list(getattr(g, "elements", []))
            if not els:
                continue
            a, b = _end_point(els[0], False), _end_point(els[-1], True)
            if a is None or b is None:
                continue
            xf = getattr(s, "transform", None)
            if xf is not None:
                a, b = tuple(map(float, xf * a)), tuple(map(float, xf * b))
            out.append((a, b))
    return out


def chip_pads(rd: Any, cls: type) -> list[BaseGeometry]:
    """World geometry of every pad of every component of type ``cls``."""
    out = []
    for _, comp in visit(rd.root, cls):
        for _, pad in visit(comp.landpattern, Pad):
            out.append(pad_world(rd, pad))
    return out


def piece_touching(copper: BaseGeometry, *targets: BaseGeometry) -> BaseGeometry | None:
    """The connected piece of ``copper`` that touches every one of ``targets``."""
    for piece in getattr(copper, "geoms", [copper]):
        if all(piece.distance(t) < 1e-3 for t in targets):
            return piece
    return None


def issue_kinds(text: str, *kinds: str) -> list[str]:
    """Lines of an issue report that name any of kinds (any case), each
    joined with the line after it, which carries the detail."""
    lines = text.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if any(k.lower() in ln.lower() for k in kinds):
            out.append(" ".join(x.strip() for x in lines[i : i + 2]))
    return out


def arcs(trace: Any) -> list[Any]:
    """The arcs of one realized trace, in order."""
    return [e for s in trace.shapes for e in getattr(getattr(s, "geometry", s), "elements", []) if hasattr(e, "radius")]


def centreline(trace: Any, step_deg: float = 5.0) -> LineString:
    """A realized trace's centre line, arcs sampled every ``step_deg``."""
    pts: list[tuple[float, float]] = []
    for s in trace.shapes:
        for el in getattr(getattr(s, "geometry", s), "elements", []):
            if hasattr(el, "radius"):
                cx, cy = el.center
                n = max(2, math.ceil(abs(el.arc) / step_deg))
                for i in range(n + 1):
                    t = math.radians(el.start + el.arc * i / n)
                    pts.append((cx + el.radius * math.cos(t), cy + el.radius * math.sin(t)))
            else:
                pts.append((float(el[0]), float(el[1])))
    return LineString(pts)
