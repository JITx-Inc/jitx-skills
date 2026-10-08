#!/usr/bin/env python3
"""Build, capture, and check the child-Circuit rule-scope reference.

The runtime adapter and capture entry point are ``jitx.runtime`` and
``jitx.run.runtime.SyncRuntimeDesign.capture``. Each check prints one PASS or
FAIL line; the exit status is 1 when any check fails or none ran.
"""

from __future__ import annotations

from typing import Any

import jitx
from jitx.shapes.primitive import Empty

try:  # Package import in a scratch project, direct import when run beside design.py.
    from .design import (
        CHILD_RULE_WIDTH,
        DEFAULT_TRACE_WIDTH,
        WIDTH_TOLERANCE,
        DefaultRulesDesign,
    )
except ImportError:
    from design import (  # type: ignore[no-redef]
        CHILD_RULE_WIDTH,
        DEFAULT_TRACE_WIDTH,
        WIDTH_TOLERANCE,
        DefaultRulesDesign,
    )


def _realized(route: Any) -> bool:
    """True when the route has traces and every trace has a non-empty shape."""
    traces = route.traces or ()
    return bool(traces) and all(
        any(not isinstance(shape.geometry, Empty) for shape in trace.shapes)
        for trace in traces
    )


def _widths(route: Any) -> list[float | None]:
    """The width of every captured shape in a route; None where a shape has none."""
    return [
        getattr(shape.geometry, "width", None)
        for trace in route.traces or ()
        for shape in trace.shapes
    ]


def _width_is(route: Any, expected: float) -> bool:
    """Every captured shape has a width within tolerance of expected."""
    widths = _widths(route)
    return (
        _realized(route)
        and bool(widths)
        and all(w is not None and abs(w - expected) <= WIDTH_TOLERANCE for w in widths)
    )


def _show(widths: list[float | None]) -> str:
    """Distinct widths at fixed precision, for the printed line."""
    shown = ("none" if w is None else f"{w:.4f}" for w in widths)
    return ",".join(dict.fromkeys(shown)) or "none"


def _check(name: str, passed: bool, measured: str, expected: str, detail: str) -> bool:
    """Print one result line and return whether the check passed."""
    status = "PASS" if passed else "FAIL"
    print(f"{status} {name}: measured={measured} expected={expected} {detail}")
    return passed


def _routes_check(routes: list[Any]) -> bool:
    """At least one route, each realized; an empty selection fails."""
    unrealized = [route for route in routes if not _realized(route)]
    return _check(
        "routes",
        bool(routes) and not unrealized,
        str(len(unrealized)),
        "0",
        f"checked={len(routes)} unrealized={len(unrealized)}",
    )


def _summary(results: list[bool]) -> int:
    """Print the totals; 1 when any check failed or none ran."""
    failures = results.count(False)
    print(f"summary: checks={len(results)} failures={failures}")
    return 1 if failures or not results else 0


def main() -> int:
    with jitx.runtime as runtime:
        rd = runtime.submit(DefaultRulesDesign)
        rd.capture()
        circuit = rd.root.circuit
        routes = [*circuit.rule_owner.routes, *circuit.sibling.routes]
        owner = circuit.rule_owner.routes[0]
        sibling = circuit.sibling.routes[0]
        board_wide = _width_is(sibling, CHILD_RULE_WIDTH)
        child_local = _width_is(sibling, DEFAULT_TRACE_WIDTH)
        if board_wide:
            outcome = "board-wide"
        elif child_local:
            outcome = "child-local"
        else:
            outcome = "ambiguous"
        print("child-rule scope probe, result classified from captured copper")
        results = [
            _routes_check(routes),
            _check(
                "width-rule-owner",
                _width_is(owner, CHILD_RULE_WIDTH),
                _show(_widths(owner)),
                f"{CHILD_RULE_WIDTH:.4f}",
                f"tol={WIDTH_TOLERANCE:.4f} mm",
            ),
            _check(
                "child-rule-scope",
                board_wide or child_local,
                _show(_widths(sibling)),
                "none",
                f"observed={outcome}",
            ),
        ]
        return _summary(results)


if __name__ == "__main__":
    raise SystemExit(main())
