#!/usr/bin/env python3
"""Build, capture, and check the net-to-net clearance reference designs.

What this reference establishes (runtime 4.4.0-rc.9, py-jitx 4.4.0rc5.dev2):
a two-condition clearance rule between two tagged nets does not move
code-authored routes. The realized copper sits where the code put it, even
below the fabrication floor, and the build reports ``status: ok``. Width rules
on the same nets do apply. The checks below assert that observed behavior, so
a runtime that starts enforcing clearance on authored routes fails this case
and the skill text gets revisited.

The runtime adapter and capture entry point are in
``jitx/run/runtime.py:404`` and ``jitx/run/runtime.py:593``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

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
    check_clearance,
    check_routes,
    check_width,
    run_checks,
)

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


def _common_checks(rd: Any) -> list[CheckResult]:
    return [
        check_routes(rd.root.circuit.routes),
        check_width(rd, "POWER", TOP_LAYER, DEFAULT_TAGGED_WIDTH, WIDTH_TOLERANCE),
        check_width(rd, "GROUND", TOP_LAYER, DEFAULT_TAGGED_WIDTH, WIDTH_TOLERANCE),
    ]


def _clearance_observation(rd: Any, requested: float, label: str) -> list[CheckResult]:
    """Assert the observed behavior: realized clearance follows authored geometry."""
    measured = check_clearance(rd, "POWER", "GROUND", TOP_LAYER, requested).measured
    authored = float(rd.root.circuit.authored_gap)
    is_number = isinstance(measured, float)
    equals_authored = is_number and abs(measured - authored) <= GAP_TOLERANCE
    rule_reached = is_number and measured + GAP_TOLERANCE >= requested
    return [
        CheckResult(
            name=f"{label}: realized clearance equals authored gap",
            passed=equals_authored,
            measured=measured,
            expected=authored,
            detail=f"rule asked {requested:.4f} mm; code authored {authored:.4f} mm",
        ),
        CheckResult(
            name=f"{label}: clearance rule not applied to authored routes",
            passed=is_number and not rule_reached,
            measured=measured,
            expected=requested,
            detail="verified behavior on the 4.4 line; a pass here means the rule moved nothing",
        ),
    ]


def main() -> int:
    with jitx.runtime as runtime:
        example = _capture(runtime, NetNetClearanceDesign)
        print("example rule, source: skill example above the fabrication floor")
        example_exit = run_checks(
            _common_checks(example)
            + _clearance_observation(example, EXAMPLE_CLEARANCE, "example")
        )

        below = _capture(runtime, BelowFloorClearanceDesign)
        floor = float(below.root.substrate.constraints.min_copper_copper_space)
        below_checks = _common_checks(below) + _clearance_observation(
            below, BELOW_FLOOR_CLEARANCE, "below-floor"
        )
        measured = check_clearance(
            below, "POWER", "GROUND", TOP_LAYER, BELOW_FLOOR_CLEARANCE
        ).measured
        below_checks.append(
            CheckResult(
                name="below-floor: fabrication floor not enforced on authored routes",
                passed=isinstance(measured, float) and measured + GAP_TOLERANCE < floor,
                measured=measured,
                expected=floor,
                detail=(
                    "floor read from FabricationConstraints.min_copper_copper_space; "
                    "a pass means authored copper sits below it with status ok"
                ),
            )
        )
        print(
            "below-floor request, source: "
            f"skill test value {BELOW_FLOOR_CLEARANCE:.4f} mm; "
            f"fabrication floor {floor:.4f} mm"
        )
        below_exit = run_checks(below_checks)
    return 1 if example_exit or below_exit else 0


if __name__ == "__main__":
    raise SystemExit(main())
