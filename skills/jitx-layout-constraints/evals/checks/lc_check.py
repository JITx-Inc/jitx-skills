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
import tempfile
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


# Counts the fixture's objects in a fresh interpreter: the runner's fixture and
# the bare one share module names, so they cannot share one process.
# ``_instantiate_design`` is what ``Runtime.submit`` uses to build a Design.
#
# A structure's signature is, per layer index, its trace width and clearance
# (and a differential layer's pair spacing, and a neck-down's width and
# clearance): the values that set copper. A fence, reference layers and the
# name are left out, so a fenced copy of a substrate structure has the
# substrate structure's signature.
_COUNT_SCRIPT = """
import json, importlib, sys
sys.path.insert(0, sys.argv[1])
from jitx.circuit import Route
from jitx.constraints import UnaryDesignConstraint
from jitx.copper import Pour
from jitx.inspect import visit
from jitx.run.runtime import _instantiate_design
from jitx.si import BaseConstrain, Constraint, DifferentialRoutingStructure, RoutingStructure
from jitx.via import Via

def rnd(x):
    return None if x is None else round(float(x), 6)

def sig(s):
    out = {}
    for i, l in s.layers.items():
        nd = l.neck_down
        out[str(i)] = [
            rnd(l.trace_width),
            rnd(l.clearance),
            rnd(getattr(l, "pair_spacing", None)),
            None if nd is None else [rnd(nd.trace_width), rnd(nd.clearance), rnd(getattr(nd, "pair_spacing", None))],
        ]
    return out

def entries(where, s):
    yield {"where": where, "name": s.name, "layers": sig(s)}
    u = getattr(s, "uncoupled_region", None)
    if u is not None:
        yield from entries(f"{where} (uncoupled region)", u)

d = _instantiate_design(getattr(importlib.import_module(sys.argv[2]), sys.argv[3]))
applied = []
constrain_structures = 0
for t, c in visit(d, BaseConstrain):
    rsc = getattr(c, "_structure", None)
    if rsc is not None:
        constrain_structures += 1
        applied.extend(entries(f"Constrain at {t.path}", rsc.structure))
for t, c in visit(d, UnaryDesignConstraint):
    if c.routing_structure_constraint is not None:
        applied.extend(entries(f"routing_structure rule at {t.path}", c.routing_structure_constraint.routing_structure))
# The substrate's class attributes are wrapped until instantiated; visit
# reads them from the instance, as for any structural object.
substrate = []
for t, s in visit(d.substrate, (RoutingStructure, DifferentialRoutingStructure)):
    substrate.extend(entries(f"{type(d.substrate).__name__}.{t.path}", s))
print(json.dumps({
    "routes": len(list(visit(d, Route))),
    "vias": len(list(visit(d, Via))),
    "pours": len(list(visit(d, Pour))),
    "si_constraints": len(list(visit(d, Constraint))),
    "constrain_structures": constrain_structures,
    "configured": [str(t.path) for t, r in visit(d, Route) if r.config is not None],
    "applied_structures": applied,
    "substrate_structures": substrate,
}))
"""

SKILL = Path(__file__).resolve().parents[2]


def object_counts(project: Path, module: str, cls: str) -> dict[str, Any]:
    """Routes, code-placed vias, pours, ``jitx.si.Constraint`` objects (timing
    and loss) and structure-applying ``Constrain`` and ``ConstrainDiffPair``
    objects in ``module.cls``;
    the routes that carry a ``Route.Config``; the routing structures the
    design applies; and the routing structures its substrate class defines."""
    run = subprocess.run(
        [sys.executable, "-c", _COUNT_SCRIPT, str(project), module, cls],
        cwd=project,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        print(run.stdout + run.stderr, file=sys.stderr)
        print(f"error: could not instantiate {module}.{cls} in {project}", file=sys.stderr)
        sys.exit(2)
    return json.loads(run.stdout.strip().splitlines()[-1])


def bare_fixture(module: str, into: Path) -> Path:
    """Copy the case's own inputs (the fixture as shipped) into ``into``."""
    for case in sorted((SKILL / "evals" / "cases").glob("*.json")):
        inputs = json.loads(case.read_text())["inputs"]
        if f"{module}.py" in inputs:
            into.mkdir(parents=True, exist_ok=True)
            for dst, src in inputs.items():
                shutil.copy(SKILL / src, into / dst)
            return into
    raise FileNotFoundError(f"no case lists {module}.py")


def _layer_text(idx: str, v: list[Any]) -> str:
    text = f"layer {idx} width {v[0]} clearance {v[1]}"
    if v[2] is not None:
        text += f" pair spacing {v[2]}"
    if v[3] is not None:
        text += f" neck-down {v[3]}"
    return text


def check_structures(applied: list[dict[str, Any]], defined: list[dict[str, Any]]) -> None:
    """Fail on an applied routing structure with a layer whose width or
    clearance no structure in the fixture's substrate has on that layer.

    The contract allows applying the substrate's structures, and a fenced copy
    of one when its width and clearance are unchanged; defining new widths or
    clearances belongs to jitx-substrate-modeler. Layers compare by value, so
    a copy made with ``RoutingStructure.Layer.fence`` passes."""
    allowed: dict[str, list[tuple[str, list[Any]]]] = {}
    for s in defined:
        for idx, v in s["layers"].items():
            allowed.setdefault(idx, []).append((s["where"], v))
    for s in applied:
        for idx, v in sorted(s["layers"].items()):
            if any(v == w for _, w in allowed.get(idx, [])):
                continue
            have = "; ".join(f"{where} {_layer_text(idx, w)}" for where, w in allowed.get(idx, [])) or "none"
            fail(
                f"routing structure {s['name']} ({s['where']}): {_layer_text(idx, v)} matches no "
                f"substrate structure on layer {idx} (substrate has: {have}); a new width or "
                "clearance is a substrate-modeler change, not a rule"
            )


def check_unedited(out: Path, module: str, cls: str) -> None:
    """Fail when the runner changed what the contract says to leave alone.

    Spike S5: a ``Route.Config`` overrides design rules, so a width set on a
    route passes every width check without a rule. No fixture sets one. The
    route, via and pour counts must match the fixture as shipped. Neither the
    ``jitx.si.Constraint`` count (timing and loss) nor the count of
    ``Constrain`` and ``ConstrainDiffPair`` objects that apply a structure
    may drop below the fixture's. Every routing structure the output applies, through
    ``Constrain(...).structure(...)``, ``ConstrainDiffPair(...).structure(...)``
    or a ``routing_structure`` rule, must match one the fixture's substrate
    defines (``check_structures``).

    ``_instantiate_design`` is private: if a jitx upgrade renames it, the
    count script exits with an import error, which run_cases reports as
    "could not run", not FAIL."""
    got = object_counts(out, module, cls)
    with tempfile.TemporaryDirectory() as tmp:
        want = object_counts(bare_fixture(module, Path(tmp) / "bare"), module, cls)
    if got["configured"]:
        fail(f"Route.Config set on {got['configured']}: a route edit, not a rule")
    for key in ("routes", "vias", "pours"):
        if got[key] != want[key]:
            fail(f"{key}: {got[key]} in the output, {want[key]} in the fixture")
    for key, label in (("si_constraints", "SI constraints"), ("constrain_structures", "structure-applying Constrain objects")):
        if got[key] < want[key]:
            fail(f"{label}: {got[key]} in the output, {want[key]} in the fixture")
    check_structures(got["applied_structures"], want["substrate_structures"])
    summary = {k: got[k] for k in ("routes", "vias", "pours", "si_constraints", "constrain_structures", "configured")}
    print(f"objects: {summary}, fixture: { {k: want[k] for k in summary} }")
    print(f"applied structures: {[(s['name'], s['layers']) for s in got['applied_structures']]}")


@contextmanager
def built(out: Path, module: str, cls: str, wait: float = 60.0) -> Iterator[Any]:
    """Check the output against the fixture as shipped (``check_unedited``),
    then submit and capture the design; yields the RuntimeDesign.

    The stored design state is removed first: a headless submit after a
    design change otherwise aborts at "stabilization" (spike observation 6).
    """
    check_unedited(out, module, cls)
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
