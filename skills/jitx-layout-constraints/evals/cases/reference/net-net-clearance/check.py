#!/usr/bin/env python3
"""Build, capture, and check the net-to-net clearance reference designs.

What this reference establishes: a two-condition clearance rule between two
tagged nets does not move code-authored routes. The realized copper sits where
the code put it, even below the fabrication floor, and the build reports
``status: ok``. Width rules on the same nets do apply. The checks below assert
that observed behavior, so a runtime that enforces clearance on authored routes
fails this case and the skill text needs revisiting.

The runtime adapter and capture entry point are ``jitx.runtime`` and
``jitx.run.runtime.SyncRuntimeDesign.capture``. Clearance is measured between
the two routes' captured trace copper; pads and pours are not part of it. Each
check prints one PASS or FAIL line; the exit status is 1 when any check fails
or none ran.
"""

from __future__ import annotations

from typing import Any

import jitx
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

try:  # Package import in a scratch project, direct import when run beside design.py.
    from .design import (
        BELOW_FLOOR_CLEARANCE,
        DEFAULT_TAGGED_WIDTH,
        EXAMPLE_CLEARANCE,
        TOP_LAYER,
        WIDTH_TOLERANCE,
        BelowFloorClearanceDesign,
        NetNetClearanceDesign,
    )
except ImportError:
    from design import (  # type: ignore[no-redef]
        BELOW_FLOOR_CLEARANCE,
        DEFAULT_TAGGED_WIDTH,
        EXAMPLE_CLEARANCE,
        TOP_LAYER,
        WIDTH_TOLERANCE,
        BelowFloorClearanceDesign,
        NetNetClearanceDesign,
    )

# Stroked ArcPolyline ends are polygonized; measured gaps run about 0.0002 mm
# over the authored gap. 0.005 mm absorbs that and nothing else.
GAP_TOLERANCE = 0.005  # skill test tolerance: 0.005 mm arc polygonization allowance


def _capture(runtime: Any, design: type) -> Any:
    rd = runtime.submit(design)
    rd.capture()
    return rd


def _fmt(value: float | int | None) -> str:
    if value is None:
        return "none"
    return str(value) if isinstance(value, int) else f"{value:.4f}"


def _check(
    name: str,
    passed: bool,
    measured: float | int | None,
    expected: float | int,
    detail: str,
) -> bool:
    """Print one result line and return whether the check passed."""
    status = "PASS" if passed else "FAIL"
    print(
        f"{status} {name}: measured={_fmt(measured)} expected={_fmt(expected)} {detail}"
    )
    return passed


def _summary(results: list[bool]) -> int:
    """Print the totals; 1 when any check failed or none ran."""
    failures = results.count(False)
    print(f"summary: checks={len(results)} failures={failures}")
    return 1 if failures or not results else 0


def _shapes(route: Any) -> list[Any]:
    """Every captured shape of a route; empty for a route with no traces."""
    return [shape for trace in route.traces or () for shape in trace.shapes]


def _copper(route: Any) -> BaseGeometry:
    """The union of a route's captured trace shapes as shapely geometry."""
    return unary_union([shape.to_shapely().g for shape in _shapes(route)])


def _clearance(rd: Any) -> float | None:
    """Smallest distance between the power and ground route copper, in mm."""
    routes = list(rd.root.circuit.routes)
    if len(routes) != 2:
        return None
    power, ground = routes  # design.py stores the power route first
    first, second = _copper(power), _copper(ground)
    if first.is_empty or second.is_empty:
        return None
    return float(first.distance(second))


def _common_checks(rd: Any) -> list[bool]:
    """Both routes realized, and every shape on each at the tagged width."""
    routes = list(rd.root.circuit.routes)
    unrealized = [
        route
        for route in routes
        if not route.traces or not all(trace.shapes for trace in route.traces)
    ]
    results = [
        _check(
            "routes",
            len(routes) == 2 and not unrealized,
            len(unrealized),
            0,
            f"checked={len(routes)} unrealized={len(unrealized)}",
        )
    ]
    for net, route in zip(("POWER", "GROUND"), routes):
        widths = [getattr(shape.geometry, "width", None) for shape in _shapes(route)]
        known = [w for w in widths if w is not None]
        worst = max(known, key=lambda w: abs(w - DEFAULT_TAGGED_WIDTH), default=None)
        results.append(
            _check(
                f"width {net}",
                route.layer == TOP_LAYER
                and bool(widths)
                and len(known) == len(widths)
                and all(
                    abs(w - DEFAULT_TAGGED_WIDTH) <= WIDTH_TOLERANCE for w in known
                ),
                worst,
                DEFAULT_TAGGED_WIDTH,
                f"layer={route.layer} shapes={len(widths)} tol={WIDTH_TOLERANCE} mm",
            )
        )
    return results


def _clearance_observation(rd: Any, requested: float, label: str) -> list[bool]:
    """Assert the observed behavior: realized clearance follows authored geometry."""
    measured = _clearance(rd)
    authored = float(rd.root.circuit.authored_gap)
    equals_authored = measured is not None and abs(measured - authored) <= GAP_TOLERANCE
    rule_reached = measured is not None and measured + GAP_TOLERANCE >= requested
    return [
        _check(
            f"{label}: realized clearance equals authored gap",
            equals_authored,
            measured,
            authored,
            f"rule asked {requested:.4f} mm; code authored {authored:.4f} mm",
        ),
        _check(
            f"{label}: clearance rule not applied to authored routes",
            measured is not None and not rule_reached,
            measured,
            requested,
            "a pass here means the rule moved nothing",
        ),
    ]


def main() -> int:
    with jitx.runtime as runtime:
        example = _capture(runtime, NetNetClearanceDesign)
        print("example rule, source: skill example above the fabrication floor")
        example_exit = _summary(
            _common_checks(example)
            + _clearance_observation(example, EXAMPLE_CLEARANCE, "example")
        )

        below = _capture(runtime, BelowFloorClearanceDesign)
        floor = float(below.root.substrate.constraints.min_copper_copper_space)
        print(
            "below-floor request, source: "
            f"skill test value {BELOW_FLOOR_CLEARANCE:.4f} mm; "
            f"fabrication floor {floor:.4f} mm"
        )
        below_results = _common_checks(below) + _clearance_observation(
            below, BELOW_FLOOR_CLEARANCE, "below-floor"
        )
        measured = _clearance(below)
        below_results.append(
            _check(
                "below-floor: fabrication floor not enforced on authored routes",
                measured is not None and measured + GAP_TOLERANCE < floor,
                measured,
                floor,
                "floor read from FabricationConstraints.min_copper_copper_space; "
                "a pass means authored copper sits below it with status ok",
            )
        )
        below_exit = _summary(below_results)
    return 1 if example_exit or below_exit else 0


if __name__ == "__main__":
    raise SystemExit(main())
