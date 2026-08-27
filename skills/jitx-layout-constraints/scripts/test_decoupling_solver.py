#!/usr/bin/env python3
"""Tests for decoupling_solver.py.

Stdlib only. Run directly: python3 test_decoupling_solver.py
"""

import sys
import unittest
from pathlib import Path
from math import nan

sys.path.insert(0, str(Path(__file__).resolve().parent))

from decoupling_solver import (  # noqa: E402
    BankSpec,
    CapacitorGeometry,
    HintSpec,
    solve,
)


CAPACITOR = CapacitorGeometry(
    body_length=1.0,  # skill default: 1.0 mm test body length
    body_width=0.5,  # skill default: 0.5 mm test body width
    pad_length=0.5,  # skill default: 0.5 mm test pad length
    pad_width=0.35,  # skill default: 0.35 mm test pad width
    pad_pitch=0.8,  # skill default: 0.8 mm test pad pitch
)


def two_hint_spec() -> BankSpec:
    """A small bank with separated hints and one central keepout."""

    return BankSpec(
        hints=(
            HintSpec("core", ((-2.3, 0.0),), ((-1.7, 0.0),)),
            HintSpec("io", ((1.7, 0.0),), ((2.3, 0.0),)),
        ),
        capacitor=CAPACITOR,
        keepouts=(((-0.4, -0.4), (0.4, -0.4), (0.4, 0.4), (-0.4, 0.4)),),
        via_pad_diameter=0.4,  # skill default: 0.4 mm test via pad diameter
        clearance_floor=0.1,  # skill default: 0.1 mm test clearance floor
        capacitor_spacing=0.3,  # skill default: 0.3 mm test spacing
        grid_step=0.4,  # skill default: 0.4 mm test grid step
        search_radius=0.8,  # skill default: 0.8 mm test search radius
    )


class DecouplingSolverTests(unittest.TestCase):
    def test_happy_path_solves_two_hints_around_one_keepout(self) -> None:
        solution = solve(two_hint_spec())
        self.assertEqual(["core", "io"], [p.hint for p in solution.placements])
        self.assertEqual(2, len(solution.placements))
        self.assertAlmostEqual(
            sum(p.loop_area for p in solution.placements), solution.total_loop_area
        )
        for placement in solution.placements:
            self.assertFalse(
                -0.4 <= placement.center[0] <= 0.4
                and -0.4 <= placement.center[1] <= 0.4
            )

    def test_infeasible_keepout_names_hint_and_constraint(self) -> None:
        blocked = BankSpec(
            hints=(HintSpec("blocked_rail", ((-0.3, 0.0),), ((0.3, 0.0),)),),
            capacitor=CAPACITOR,
            keepouts=(((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),),
            via_pad_diameter=0.4,  # skill default: 0.4 mm test via pad diameter
            clearance_floor=0.1,  # skill default: 0.1 mm test clearance floor
            capacitor_spacing=0.3,  # skill default: 0.3 mm test spacing
            grid_step=0.5,  # skill default: 0.5 mm test grid step
            search_radius=0.5,  # skill default: 0.5 mm test search radius
        )
        with self.assertRaisesRegex(
            ValueError, "blocked_rail.*keepout overlap"
        ):
            solve(blocked)

    def test_same_input_is_deterministic(self) -> None:
        spec = two_hint_spec()
        self.assertEqual(solve(spec), solve(spec))

    def test_clearance_applies_to_pads_in_other_hints(self) -> None:
        blocking_centers = tuple(
            (x, y) for y in (-0.5, 0.0, 0.5) for x in (-0.5, 0.0, 0.5)
        )
        spec = BankSpec(
            hints=(
                HintSpec("served", ((-1.0, -1.0),), ((1.0, 1.0),)),
                HintSpec("other", blocking_centers, ((2.0, 2.0),)),
            ),
            capacitor=CAPACITOR,
            keepouts=(),
            via_pad_diameter=0.4,  # skill default: 0.4 mm test via pad diameter
            clearance_floor=0.1,  # skill default: 0.1 mm test clearance floor
            capacitor_spacing=0.3,  # skill default: 0.3 mm test spacing
            grid_step=0.5,  # skill default: 0.5 mm test grid step
            search_radius=0.5,  # skill default: 0.5 mm test search radius
        )
        with self.assertRaisesRegex(ValueError, "served.*IC-pad clearance floor"):
            solve(spec)

    def test_degenerate_loop_is_infeasible(self) -> None:
        spec = BankSpec(
            hints=(HintSpec("flat", ((-0.5, 0.0),), ((0.5, 0.0),)),),
            capacitor=CAPACITOR,
            keepouts=(),
            via_pad_diameter=0.4,  # skill default: 0.4 mm test via pad diameter
            clearance_floor=0.0,  # skill default: 0.0 mm test clearance floor
            capacitor_spacing=0.0,  # skill default: 0.0 mm test spacing
            grid_step=0.5,  # skill default: 0.5 mm test grid step
            search_radius=0.0,  # skill default: fixed test position
        )
        with self.assertRaisesRegex(ValueError, "flat.*nondegenerate loop geometry"):
            solve(spec)

    def test_non_finite_geometry_is_rejected(self) -> None:
        spec = two_hint_spec()
        invalid = BankSpec(
            hints=spec.hints,
            capacitor=CapacitorGeometry(
                body_length=nan,
                body_width=spec.capacitor.body_width,
                pad_length=spec.capacitor.pad_length,
                pad_width=spec.capacitor.pad_width,
                pad_pitch=spec.capacitor.pad_pitch,
            ),
            keepouts=spec.keepouts,
            via_pad_diameter=spec.via_pad_diameter,
            clearance_floor=spec.clearance_floor,
            capacitor_spacing=spec.capacitor_spacing,
            grid_step=spec.grid_step,
            search_radius=spec.search_radius,
        )
        with self.assertRaisesRegex(ValueError, "body_length must be finite"):
            solve(invalid)

    def test_two_capacitors_competing_for_one_best_spot_both_place(self) -> None:
        competing = BankSpec(
            hints=(
                HintSpec("first", ((-0.4, 0.0),), ((0.4, 0.0),)),
                HintSpec("second", ((-0.4, 0.0),), ((0.4, 0.0),)),
            ),
            capacitor=CapacitorGeometry(
                body_length=0.5,  # skill default: 0.5 mm test body length
                body_width=0.3,  # skill default: 0.3 mm test body width
                pad_length=0.2,  # skill default: 0.2 mm test pad length
                pad_width=0.2,  # skill default: 0.2 mm test pad width
                pad_pitch=0.3,  # skill default: 0.3 mm test pad pitch
            ),
            keepouts=(),
            via_pad_diameter=0.2,  # skill default: 0.2 mm test via pad diameter
            clearance_floor=0.0,  # skill default: 0.0 mm test clearance floor
            capacitor_spacing=0.2,  # skill default: 0.2 mm test spacing
            grid_step=0.5,  # skill default: 0.5 mm test grid step
            search_radius=1.0,  # skill default: 1.0 mm test search radius
        )
        solution = solve(competing)
        first, second = solution.placements
        self.assertNotEqual(first.center, second.center)
        self.assertEqual(("first", "second"), (first.hint, second.hint))

    def test_loop_area_decreases_when_ic_pads_move_closer(self) -> None:
        geometry = CapacitorGeometry(
            body_length=0.4,  # skill default: 0.4 mm test body length
            body_width=0.2,  # skill default: 0.2 mm test body width
            pad_length=0.2,  # skill default: 0.2 mm test pad length
            pad_width=0.15,  # skill default: 0.15 mm test pad width
            pad_pitch=0.3,  # skill default: 0.3 mm test pad pitch
        )

        def solve_distance(distance: float) -> float:
            spec = BankSpec(
                hints=(
                    HintSpec(
                        "rail",
                        ((-distance, -distance),),
                        ((distance, distance),),
                    ),
                ),
                capacitor=geometry,
                keepouts=(),
                via_pad_diameter=0.2,  # skill default: 0.2 mm test via pad diameter
                clearance_floor=0.0,  # skill default: 0.0 mm test clearance floor
                capacitor_spacing=0.0,  # skill default: 0.0 mm test spacing
                grid_step=0.25,  # skill default: 0.25 mm test grid step
                search_radius=0.25,  # skill default: 0.25 mm test search radius
            )
            return solve(spec).total_loop_area

        self.assertLess(solve_distance(0.5), solve_distance(1.0))


class ScaleAndPitchTests(unittest.TestCase):
    def _cap(self) -> CapacitorGeometry:
        return CapacitorGeometry(
            body_length=1.6, body_width=0.8, pad_length=0.9, pad_width=0.8, pad_pitch=1.5
        )

    def test_fine_pitch_ic_is_feasible_with_escape_width(self) -> None:
        # Power and return pads 0.5 mm apart, as on a 0.5 mm pitch QFN row.
        spec = BankSpec(
            hints=(HintSpec("core", ((0.0, 0.0),), ((0.5, 0.0),)),),
            capacitor=self._cap(),
            keepouts=(),
            via_pad_diameter=0.45,
            clearance_floor=0.09,
            capacitor_spacing=0.2,
            escape_width=0.25,
        )
        solution = solve(spec)
        self.assertEqual(len(solution.placements), 1)

    def test_four_hints_solve_under_the_node_budget(self) -> None:
        hints = tuple(
            HintSpec(f"h{i}", ((x, 0.0),), ((x + 0.5, 0.0),))
            for i, x in enumerate((0.0, 2.0, 4.0, 6.0))
        )
        spec = BankSpec(
            hints=hints,
            capacitor=self._cap(),
            keepouts=(),
            via_pad_diameter=0.45,
            clearance_floor=0.09,
            capacitor_spacing=0.2,
            escape_width=0.25,
        )
        solution = solve(spec)
        self.assertEqual(len(solution.placements), 4)

    def test_node_budget_raises_with_hint_count(self) -> None:
        spec = BankSpec(
            hints=(HintSpec("a", ((0.0, 0.0),), ((0.5, 0.0),)), HintSpec("b", ((3.0, 0.0),), ((3.5, 0.0),))),
            capacitor=self._cap(),
            keepouts=(),
            via_pad_diameter=0.45,
            clearance_floor=0.09,
            capacitor_spacing=0.2,
            escape_width=0.25,
            max_nodes=3,
        )
        with self.assertRaisesRegex(ValueError, "2 hints"):
            solve(spec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
