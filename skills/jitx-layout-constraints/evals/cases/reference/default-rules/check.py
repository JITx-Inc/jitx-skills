#!/usr/bin/env python3
"""Build, capture, and check the child-Circuit rule-scope reference.

The runtime adapter and capture entry point are in
``jitx/run/runtime.py:404`` and ``jitx/run/runtime.py:593``.
"""

from __future__ import annotations

import jitx
from jitxlib.verify import (
    CheckResult,
    check_route_width,
    check_routes,
    report,
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


def main() -> int:
    with jitx.runtime as runtime:
        rd = runtime.submit(DefaultRulesDesign)
        rd.capture()
        circuit = rd.root.circuit
        routes = [*circuit.rule_owner.routes, *circuit.sibling.routes]
        board_wide = check_route_width(
            circuit.sibling.routes[0], CHILD_RULE_WIDTH, WIDTH_TOLERANCE
        )
        child_local = check_route_width(
            circuit.sibling.routes[0], DEFAULT_TRACE_WIDTH, WIDTH_TOLERANCE
        )
        if board_wide.passed:
            outcome = "board-wide"
        elif child_local.passed:
            outcome = "child-local"
        else:
            outcome = "ambiguous"
        checks = [
            check_routes(routes),
            check_route_width(
                circuit.rule_owner.routes[0], CHILD_RULE_WIDTH, WIDTH_TOLERANCE
            ),
            CheckResult(
                name="child-rule-scope",
                passed=board_wide.passed or child_local.passed,
                measured=board_wide.measured,
                expected=None,
                detail=f"observed={outcome}; {board_wide.detail}",
            ),
        ]
        print("child-rule scope probe, result classified from captured copper")
        return report(checks)


if __name__ == "__main__":
    raise SystemExit(main())
