#!/usr/bin/env python3
"""Build, capture, and check the net-to-net clearance reference designs.

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


def _capture(runtime: Any, design: type) -> Any:
    rd = runtime.submit(design)
    rd.capture()
    return rd


def main() -> int:
    with jitx.runtime as runtime:
        example = _capture(runtime, NetNetClearanceDesign)
        example_checks = [
            check_routes(example.root.circuit.routes),
            check_width(
                example,
                "POWER",
                TOP_LAYER,
                DEFAULT_TAGGED_WIDTH,
                WIDTH_TOLERANCE,
            ),
            check_width(
                example,
                "GROUND",
                TOP_LAYER,
                DEFAULT_TAGGED_WIDTH,
                WIDTH_TOLERANCE,
            ),
            check_clearance(
                example,
                "POWER",
                "GROUND",
                TOP_LAYER,
                EXAMPLE_CLEARANCE,
            ),
        ]
        print("example clearance, source: skill example above fabrication floor")
        example_exit = run_checks(example_checks)

        below_floor = _capture(runtime, BelowFloorClearanceDesign)
        floor = below_floor.root.substrate.constraints.min_copper_copper_space
        below_floor_clearance = check_clearance(
            below_floor,
            "POWER",
            "GROUND",
            TOP_LAYER,
            BELOW_FLOOR_CLEARANCE,
        )
        measured = below_floor_clearance.measured
        if isinstance(measured, float):
            floor_observed = measured + WIDTH_TOLERANCE >= floor
            outcome = (
                "fabrication floor or greater" if floor_observed else "below-floor rule"
            )
            classification_passed = measured + WIDTH_TOLERANCE >= BELOW_FLOOR_CLEARANCE
        else:
            outcome = "no measurable copper witness"
            classification_passed = False
        floor_checks = [
            check_routes(below_floor.root.circuit.routes),
            check_width(
                below_floor,
                "POWER",
                TOP_LAYER,
                DEFAULT_TAGGED_WIDTH,
                WIDTH_TOLERANCE,
            ),
            check_width(
                below_floor,
                "GROUND",
                TOP_LAYER,
                DEFAULT_TAGGED_WIDTH,
                WIDTH_TOLERANCE,
            ),
            below_floor_clearance,
            CheckResult(
                name="below-floor-classification",
                passed=classification_passed,
                measured=measured,
                expected=BELOW_FLOOR_CLEARANCE,
                detail=(f"observed={outcome}; fabrication floor={floor:.4f} mm"),
            ),
        ]
        print(
            "below-floor request, source: "
            f"skill test value {BELOW_FLOOR_CLEARANCE:.4f} mm; "
            "fabrication floor read from FabricationConstraints.min_copper_copper_space"
        )
        floor_exit = run_checks(floor_checks)
    return 1 if example_exit or floor_exit else 0


if __name__ == "__main__":
    raise SystemExit(main())
