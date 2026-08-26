#!/usr/bin/env python3
"""Unit tests for the pure helpers in layout_checks.py.

The capture adapter is exercised by the built reference designs under
``evals/cases/reference`` because a realistic ``RuntimeDesign`` exists only
after submit and capture (``jitx/run/runtime.py:404``,
``jitx/run/runtime.py:593``). Run directly with
``python test_layout_checks.py``.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))

from layout_checks import check_route_width, min_clearance, trace_widths, unrealized


@dataclass
class ShapeWithWidth:
    width: float


@dataclass
class RouteStandIn:
    traces: object


class TraceWidthsTests(unittest.TestCase):
    def test_collects_unique_widths(self) -> None:
        shapes = [
            ShapeWithWidth(0.2),
            object(),
            ShapeWithWidth(0.4),
            ShapeWithWidth(0.2),
        ]
        self.assertEqual(trace_widths(shapes), {0.2, 0.4})

    def test_empty_input_returns_empty_set(self) -> None:
        self.assertEqual(trace_widths([]), set())


class MinClearanceTests(unittest.TestCase):
    def test_measures_known_box_gap(self) -> None:
        left = shapely.box(0.0, 0.0, 1.0, 1.0)
        right = shapely.box(1.35, 0.0, 2.0, 1.0)
        measured = min_clearance([left], [right])
        assert measured is not None
        self.assertAlmostEqual(measured, 0.35)

    def test_empty_left_returns_none(self) -> None:
        self.assertIsNone(min_clearance([], [shapely.box(0.0, 0.0, 1.0, 1.0)]))

    def test_empty_right_returns_none(self) -> None:
        self.assertIsNone(min_clearance([shapely.box(0.0, 0.0, 1.0, 1.0)], []))

    def test_rejects_non_shapely_objects(self) -> None:
        with self.assertRaises(TypeError):
            min_clearance([object()], [shapely.box(0.0, 0.0, 1.0, 1.0)])


class UnrealizedTests(unittest.TestCase):
    def test_detects_none_and_empty_traces(self) -> None:
        missing = RouteStandIn(None)
        empty = RouteStandIn([])
        realized = RouteStandIn([object()])
        self.assertEqual(unrealized([missing, empty, realized]), [missing, empty])

    def test_empty_route_input_returns_empty_list(self) -> None:
        self.assertEqual(unrealized([]), [])


@dataclass
class TraceStandIn:
    shapes: list[object]


class CheckRouteWidthTests(unittest.TestCase):
    def test_passes_when_every_shape_matches(self) -> None:
        route = RouteStandIn([TraceStandIn([ShapeWithWidth(0.25), ShapeWithWidth(0.25)])])
        result = check_route_width(route, 0.25, 1e-6)
        self.assertTrue(result.passed)
        self.assertEqual(result.measured, (0.25,))

    def test_fails_on_wider_and_narrower(self) -> None:
        wider = RouteStandIn([TraceStandIn([ShapeWithWidth(0.5)])])
        narrower = RouteStandIn([TraceStandIn([ShapeWithWidth(0.15)])])
        self.assertFalse(check_route_width(wider, 0.25, 1e-6).passed)
        self.assertFalse(check_route_width(narrower, 0.25, 1e-6).passed)

    def test_unrealized_route_fails_with_no_witness(self) -> None:
        result = check_route_width(RouteStandIn(None), 0.25, 1e-6)
        self.assertFalse(result.passed)
        self.assertIsNone(result.measured)
        self.assertIn("no realized trace width witness", result.detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
