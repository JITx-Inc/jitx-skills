#!/usr/bin/env python3
"""Check captured JITX trace width, net clearance, and route realization.

The pure helpers at the top of this module do not import JITX. The capture
adapter imports JITX only when a captured ``RuntimeDesign`` is checked.

Capture traps and limits handled here:

* Query-returned pad and via copper is in the source object's local frame.
  The adapter composes ``trace.transform`` before measuring it. Omitting that
  composition makes unrelated copper commonly read as 0.0000 mm apart.
* ``PolygonSet.to_shapely()`` fills each computed-pour cutout ring. The adapter
  rebuilds polygon sets ring by ring before conversion.
* A captured ``Pour`` on the JITX 4.4 line is its input outline before voiding.
  Pours are excluded from capture clearance checks. Use the runtime-side
  legacy ODB++ export for trace-to-pour measurements.

The capture/query procedure and the reason to assert concrete geometry are in
``jitx-physical-layout/references/geometry-verification.md``. Installed API
locations used by the adapter: ``jitx/run/runtime.py:404`` for
``RuntimeDesign``, ``jitx/query.py:187`` for transformed queries,
``jitx/inspect.py:174`` for inspection traces, ``jitx/circuit.py:546`` for
route traces, and ``jitx/shapes/shapely.py:76`` for shape conversion.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any


def trace_widths(shapes: Iterable[object]) -> set[float]:
    """Return the widths exposed by polyline-like objects."""
    return {
        float(width)
        for shape in shapes
        if (width := getattr(shape, "width", None)) is not None
    }


def min_clearance(
    shapes_a: Iterable[object], shapes_b: Iterable[object]
) -> float | None:
    """Return the smallest shapely distance, or ``None`` for an empty side."""
    try:
        from shapely.geometry.base import BaseGeometry
    except ImportError as exc:
        raise ImportError(
            "min_clearance requires shapely; install shapely in the check environment"
        ) from exc

    first = tuple(shapes_a)
    second = tuple(shapes_b)
    if not first or not second:
        return None
    if not all(isinstance(shape, BaseGeometry) for shape in (*first, *second)):
        raise TypeError("min_clearance expects shapely geometry objects")
    return min(a.distance(b) for a in first for b in second)  # type: ignore[union-attr]


def unrealized(routes: Iterable[object]) -> list[object]:
    """Return routes whose ``traces`` attribute is missing or empty."""
    return [route for route in routes if not getattr(route, "traces", None)]


@dataclass(frozen=True)
class CheckResult:
    """One measured check result suitable for stable line-oriented output."""

    name: str
    passed: bool
    measured: float | int | tuple[float, ...] | None
    expected: float | int | None
    detail: str


@dataclass(frozen=True)
class _CopperSample:
    geometry: object
    width: float | None


def _shape_geometry(shape: Any, transform: Any, polygon_set_type: type) -> object:
    """Convert a JITX shape to global-frame shapely geometry."""
    try:
        import shapely
    except ImportError as exc:
        raise ImportError(
            "captured layout checks require shapely; install shapely in the check environment"
        ) from exc

    from jitx.shapes.shapely import ShapelyGeometry

    primitive = shape.geometry
    if isinstance(primitive, polygon_set_type):
        polygons = [
            shapely.Polygon(polygon.elements, polygon.holes)
            for polygon in primitive.polygons
        ]
        local = ShapelyGeometry(shapely.MultiPolygon(polygons)).apply(shape.transform)
    else:
        local = shape.to_shapely()
    if transform is None:
        raise ValueError("unresolved query transform; copper cannot be measured safely")
    return local.apply(transform).g


def _collect_copper(rd: Any, net: str, layer: int) -> list[_CopperSample]:
    """Collect non-pour copper for one named net on one normalized layer."""
    try:
        from jitx import Copper, Pour
        from jitx.circuit import Route
        from jitx.shapes.primitive import PolygonSet
    except ImportError as exc:
        raise ImportError(
            "captured layout checks require the jitx package used to build the design"
        ) from exc

    normalized_layer = rd.layers().normalize(layer)
    net_index = rd.nets()
    samples: list[_CopperSample] = []
    for trace, copper in rd.query(Copper):
        if isinstance(copper, Pour):
            continue
        if rd.layers().normalize(copper.layer) != normalized_layer:
            continue
        runtime_net = net_index.find(copper)
        if runtime_net is None or runtime_net.name != net:
            continue

        source = trace.path.access(rd.root)
        route_source = isinstance(source, Route)
        transform = None if route_source else trace.transform
        if route_source:
            geometry = _shape_geometry(copper.shape, _identity_transform(), PolygonSet)
        else:
            geometry = _shape_geometry(copper.shape, transform, PolygonSet)
        primitive = copper.shape.geometry
        width = getattr(primitive, "width", None)
        samples.append(
            _CopperSample(
                geometry=geometry,
                width=float(width) if width is not None and route_source else None,
            )
        )
    return samples


def _identity_transform() -> Any:
    """Return the JITX identity transform without importing JITX at module load."""
    try:
        from jitx.transform import IDENTITY
    except ImportError as exc:
        raise ImportError(
            "captured layout checks require the jitx package used to build the design"
        ) from exc
    return IDENTITY


def check_width(
    rd: Any, net: str, layer: int, expected: float, tol: float
) -> CheckResult:
    """Check every realized route width on a named net and layer."""
    samples = _collect_copper(rd, net, layer)
    widths = tuple(sorted(trace_widths(s for s in samples if s.width is not None)))
    passed = bool(widths) and all(abs(width - expected) <= tol for width in widths)
    detail = (
        f"net={net} layer={layer} tol={tol:.4f} mm"
        if widths
        else f"net={net} layer={layer} has no realized trace width witness"
    )
    return CheckResult(
        name="width",
        passed=passed,
        measured=widths if widths else None,
        expected=expected,
        detail=detail,
    )


def check_clearance(
    rd: Any, net_a: str, net_b: str, layer: int, minimum: float
) -> CheckResult:
    """Check minimum non-pour copper clearance between two named nets."""
    first = _collect_copper(rd, net_a, layer)
    second = _collect_copper(rd, net_b, layer)
    measured = min_clearance(
        (sample.geometry for sample in first),
        (sample.geometry for sample in second),
    )
    passed = measured is not None and measured >= minimum
    detail = f"nets={net_a},{net_b} layer={layer}"
    if measured is None:
        detail += " has no copper witness on one or both sides"
    return CheckResult(
        name="clearance",
        passed=passed,
        measured=measured,
        expected=minimum,
        detail=detail,
    )


def check_routes(routes: Iterable[object]) -> CheckResult:
    """Check that every supplied authored route has realized traces."""
    route_list = tuple(routes)
    missing = unrealized(route_list)
    return CheckResult(
        name="routes",
        passed=not missing,
        measured=len(missing),
        expected=0,
        detail=f"checked={len(route_list)} unrealized={len(missing)}",
    )


def check_route_width(route: object, expected: float, tol: float) -> CheckResult:
    """Check every realized shape width of one authored route.

    Use this where one net carries a class-width trunk and a narrower tagged
    escape on the same layer: ``check_width`` is keyed by net and layer and
    would see both widths, while the step-down ladder expects them to differ.
    """
    shapes: list[object] = []
    for trace in getattr(route, "traces", None) or ():
        for shape in getattr(trace, "shapes", ()):
            shapes.append(getattr(shape, "geometry", shape))
    widths = tuple(sorted(trace_widths(shapes)))
    passed = bool(widths) and all(abs(width - expected) <= tol for width in widths)
    detail = (
        f"route={route!r} tol={tol:.4f} mm"
        if widths
        else f"route={route!r} has no realized trace width witness"
    )
    return CheckResult(
        name="route-width",
        passed=passed,
        measured=widths if widths else None,
        expected=expected,
        detail=detail,
    )


def _format_measured(value: float | tuple[float, ...] | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, tuple):
        return ",".join(f"{item:.4f}" for item in value)
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def rule_width(rule: object) -> float:
    """Return the trace width a unary rule carries, so checks read the rule, not a copy."""
    effect = getattr(rule, "trace_width_constraint", None)
    if effect is None:
        raise ValueError(f"rule {rule!r} carries no trace_width effect")
    return float(effect.width)


def rule_clearance(rule: object) -> float:
    """Return the clearance a binary rule carries, so checks read the rule, not a copy."""
    effect = getattr(rule, "clearance_constraint", None)
    if effect is None:
        raise ValueError(f"rule {rule!r} carries no clearance effect")
    return float(effect.clearance)


def run_checks(checks: Sequence[CheckResult]) -> int:
    """Print one line per check and return 1 when any check fails or none were supplied."""
    if not checks:
        print("summary: checks=0 failures=1 (no checks supplied; nothing was verified)")
        return 1
    failures = 0
    for result in checks:
        status = "PASS" if result.passed else "FAIL"
        if not result.passed:
            failures += 1
        print(
            f"{status} {result.name}: measured={_format_measured(result.measured)} "
            f"expected={_format_measured(result.expected)} {result.detail}"
        )
    print(f"summary: checks={len(checks)} failures={failures}")
    return 1 if failures else 0
