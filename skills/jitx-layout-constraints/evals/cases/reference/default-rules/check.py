#!/usr/bin/env python3
"""Build, capture, and check the child-Circuit rule-scope reference.

The runtime adapter and capture entry point are in
``jitx/run/runtime.py:404`` and ``jitx/run/runtime.py:593``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import jitx


def _load_layout_checks() -> None:
    for parent in Path(__file__).resolve().parents:
        candidates = (
            parent / "scripts" / "layout_checks.py",
            parent / "layout_checks.py",
        )
        for candidate in candidates:
            if candidate.is_file():
                sys.path.insert(0, str(candidate.parent))
                return
    raise RuntimeError("could not locate layout_checks.py from the reference tree")


_load_layout_checks()

from layout_checks import (  # pyright: ignore[reportMissingImports]
    CheckResult,
    check_routes,
    run_checks,
    trace_widths,
)

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


def _route_widths(route: object) -> tuple[float, ...]:
    shapes = []
    for trace in route.traces or ():  # type: ignore[attr-defined]
        for shape in trace.shapes:
            shapes.append(getattr(shape, "geometry", shape))
    return tuple(sorted(trace_widths(shapes)))


def _route_width_result(label: str, route: object, expected: float) -> CheckResult:
    widths = _route_widths(route)
    passed = bool(widths) and all(
        abs(width - expected) <= WIDTH_TOLERANCE for width in widths
    )
    return CheckResult(
        name=f"width-{label}",
        passed=passed,
        measured=widths if widths else None,
        expected=expected,
        detail=f"tol={WIDTH_TOLERANCE:.4f} mm",
    )


def main() -> int:
    with jitx.runtime as runtime:
        rd = runtime.submit(DefaultRulesDesign)
        rd.capture()
        circuit = rd.root.circuit
        routes = [*circuit.rule_owner.routes, *circuit.sibling.routes]
        sibling_widths = _route_widths(circuit.sibling.routes[0])
        board_wide = bool(sibling_widths) and all(
            abs(width - CHILD_RULE_WIDTH) <= WIDTH_TOLERANCE for width in sibling_widths
        )
        child_local = bool(sibling_widths) and all(
            abs(width - DEFAULT_TRACE_WIDTH) <= WIDTH_TOLERANCE
            for width in sibling_widths
        )
        if board_wide:
            outcome = "board-wide"
        elif child_local:
            outcome = "child-local"
        else:
            outcome = "ambiguous"
        checks = [
            check_routes(routes),
            _route_width_result(
                "rule-owner", circuit.rule_owner.routes[0], CHILD_RULE_WIDTH
            ),
            CheckResult(
                name="child-rule-scope",
                passed=board_wide or child_local,
                measured=sibling_widths if sibling_widths else None,
                expected=None,
                detail=f"observed={outcome}",
            ),
        ]
        print("child-rule scope probe, result classified from captured copper")
        return run_checks(checks)


if __name__ == "__main__":
    raise SystemExit(main())
