"""Shared helpers for the jitx-layout-constraints eval checks.

Each check builds the runner's edited fixture in ``<output>`` with a runtime it
starts for that directory and stops at exit, captures the design, measures the
realized copper, prints what it measured, and exits nonzero on a failure.

The measurement surfaces are the ones the 2026-11-03 layout-constraints spike
(jitx 4.6.0, runtime 4.6.0) read headlessly:

- ``Pour.shape`` after ``rd.capture()`` holds the computed pour copper, holes
  included (spike S1);
- ``Route.traces[*].shapes`` holds the realized trace shapes (S8: a trace may
  come back as a ``Polygon`` with no width);
- ``ComputedStitchVia`` and ``ComputedFenceVia`` hold the generated vias (S3,
  S4, S9); fence vias from a ``fence_via`` rule on a pour come back as
  ``ComputedStitchVia`` (S4).
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
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from jitx._translate.reverse_flow.applied import ComputedFenceVia, ComputedStitchVia
from jitx.circuit import Route
from jitx.constraints import DesignConstraint
from jitx.copper import Pour
from jitx.design import Design
from jitx.inspect import visit
from jitx.landpattern import Pad
from jitx.run.runtime import Runtime
from jitx.shapes.primitive import Empty
from jitx.via import Via

FAILURES: list[str] = []


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
    design change otherwise aborts at "stabilization" (spike observation 6).
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


# ---------------------------------------------------------------- geometry


def geom(shape: Any) -> BaseGeometry:
    """Shapely geometry of a jitx shape, holes kept (4.6.0 keeps PolygonSet holes)."""
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
    shapes = [geom(s) for tr in route.traces or [] for s in tr.shapes]
    return shapely.union_all(shapes) if shapes else shapely.Polygon()


def trace_widths(route: Route) -> list[float | None]:
    """Width of every realized trace shape; None for a shape with no width
    (a ``Polygon``, spike S8), which a width check must not skip silently."""
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
            s = p.shape
            s = getattr(s, "shape", s)
            return geom((trace.transform * p.transform) * s)
    raise KeyError("pad not found")


def pads_of(rd: Any, root: Any) -> list[tuple[str, Pad, BaseGeometry]]:
    """Every pad under ``root`` (a component or landpattern instance), in world coordinates."""
    ids = {id(p) for _, p in visit(root, Pad)}
    out = []
    for trace, p in visit(rd.root, Pad):
        if id(p) in ids and trace.transform is not None and p.transform is not None:
            s = p.shape
            s = getattr(s, "shape", s)
            out.append((str(trace.path), p, geom((trace.transform * p.transform) * s)))
    return out


def placed_vias(rd: Any) -> list[tuple[float, float]]:
    """Centres of the vias the design places in code (not rule-generated ones)."""
    out = []
    for trace, v in visit(rd.root, Via):
        if trace.transform is None or v.transform is None:
            continue
        x, y = (trace.transform * v.transform).trs[0]
        out.append((float(x), float(y)))
    return out


def stitch_vias(rd: Any) -> list[tuple[float, float]]:
    return [
        (float(v.position[0]), float(v.position[1]))
        for _, s in visit(rd.root, ComputedStitchVia)
        for v in s.vias
    ]


def fence_vias(rd: Any) -> list[tuple[float, float]]:
    return [
        (float(v.position[0]), float(v.position[1]))
        for _, f in visit(rd.root, ComputedFenceVia)
        for v in f.vias
    ]


def rules(rd_or_design: Any) -> list[DesignConstraint]:
    return [c for _, c in visit(rd_or_design, DesignConstraint)]


def gap(a: BaseGeometry, b: BaseGeometry) -> float:
    return round(float(a.distance(b)), 4)


def relief(pour_g: BaseGeometry, pad_g: BaseGeometry, probe: float = 0.02) -> dict[str, Any]:
    """How a pour meets a pad (the spike's ``relief`` measure).

    voids: empty pieces of a 2 mm ring around the pad that touch the pad.
    gap_max: the largest distance from the pad to a void's outline.
    spoke_widths: lengths of pour copper crossing a ring ``probe`` mm outside the pad.
    full_contact: the pour meets the pad all round with no void.
    """
    ring = pad_g.buffer(2.0, join_style="mitre").difference(pad_g)
    voids = ring.difference(pour_g)
    vlist = [v for v in getattr(voids, "geoms", [voids]) if not v.is_empty and v.area > 1e-4]
    vlist = [v for v in vlist if v.distance(pad_g) < 1e-3]
    gaps = []
    for v in vlist:
        ext = getattr(v, "exterior", None)
        if ext is None:
            continue
        gaps.append(round(max(pad_g.distance(Point(xy)) for xy in ext.coords), 4))
    edge = pad_g.buffer(probe, join_style="mitre").exterior
    cross = edge.intersection(pour_g)
    pieces = [g for g in getattr(cross, "geoms", [cross]) if not g.is_empty and g.length > 1e-4]
    return {
        "touches": bool(pour_g.distance(pad_g) < 1e-3),
        "voids": len(vlist),
        "gap_max": max(gaps) if gaps else None,
        "spoke_widths": sorted(round(p.length, 4) for p in pieces),
        "full_contact": bool(pad_g.buffer(probe).difference(pad_g).difference(pour_g).area < 1e-4),
    }


def grid_sites(bounds: tuple[float, float, float, float], pitch: float) -> list[tuple[float, float]]:
    """Square-grid sites at multiples of ``pitch`` from (0, 0) inside ``bounds``
    (spike S3: stitch sites sit on the absolute grid, not the pour's)."""
    x0, y0, x1, y1 = bounds
    xs = [i * pitch for i in range(math.ceil(x0 / pitch - 1e-9), math.floor(x1 / pitch + 1e-9) + 1)]
    ys = [j * pitch for j in range(math.ceil(y0 / pitch - 1e-9), math.floor(y1 / pitch + 1e-9) + 1)]
    return [(x, y) for x in xs for y in ys]


def dump(obj: Any) -> None:
    print(json.dumps(obj, indent=1, default=str))
