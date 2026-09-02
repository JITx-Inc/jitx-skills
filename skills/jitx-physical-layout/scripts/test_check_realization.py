#!/usr/bin/env python3
"""Unit tests for physical-layout realization witness evaluation."""

from __future__ import annotations

import contextlib
import io
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_realization as realization
from check_realization import (
    CheckResult,
    KeepOutWitness,
    PourWitness,
    StitchTargetWitness,
    _normalized_layers,
    _normalized_pour_layer,
    _require_computed_pour,
    check_board_edge,
    check_keepouts,
    check_pours,
    check_stitch_targets,
    main,
    run_checks,
)


def pour(
    label: str = "circuit.ground",
    geometry: object | None = None,
    *,
    empty: bool = False,
) -> PourWitness:
    return PourWitness(
        label=label,
        net="GND",
        layer=1,
        geometry=shapely.box(1, 1, 9, 9)
        if geometry is None and not empty
        else geometry,
        empty=empty,
    )


class PourRealizationTests(unittest.TestCase):
    def test_nonempty_pour_passes(self) -> None:
        result = check_pours((pour(),))[0]
        self.assertTrue(result.passed)
        self.assertEqual(result.measured, 64.0)

    def test_empty_pour_fails_with_net_and_layer_instead_of_raising(self) -> None:
        result = check_pours((pour(empty=True),))[0]
        self.assertFalse(result.passed)
        self.assertIn("Empty()", result.detail)
        self.assertIn("net=GND", result.detail)
        self.assertIn("layer=1", result.detail)


class StitchRealizationTests(unittest.TestCase):
    def test_non_pour_target_fails(self) -> None:
        target = StitchTargetWitness("circuit.pad", "Pad", None, ())
        result = check_stitch_targets((target,), stitch_rule_count=1)[0]
        self.assertFalse(result.passed)
        self.assertIn("requires a Pour", result.detail)

    def test_stitched_pour_requires_via_inside(self) -> None:
        witness = pour()
        missing = StitchTargetWitness("circuit.ground", "Pour", witness, ((20, 20),))
        present = StitchTargetWitness("circuit.ground", "Pour", witness, ((2, 2),))
        self.assertFalse(check_stitch_targets((missing,), 1)[0].passed)
        self.assertTrue(check_stitch_targets((present,), 1)[0].passed)

    def test_stitch_rule_without_selected_pour_fails_coverage(self) -> None:
        result = check_stitch_targets((), stitch_rule_count=1)[0]
        self.assertFalse(result.passed)
        self.assertIn("selected-pour-targets=0", result.detail)


MIN_FEATURE = 0.09  # a JLCPCB-class minimum copper width, in mm


class KeepoutAndEdgeTests(unittest.TestCase):
    def test_realized_pour_inside_keepout_fails(self) -> None:
        keepout = KeepOutWitness(
            "circuit.keepout", frozenset({1}), shapely.box(4, 4, 6, 6)
        )
        result = check_keepouts((pour(),), (keepout,), MIN_FEATURE)[0]
        self.assertFalse(result.passed)
        self.assertGreater(result.measured, 0.0)  # type: ignore[operator]

    def test_voided_pour_clear_of_keepout_passes(self) -> None:
        geometry = shapely.box(1, 1, 9, 9).difference(shapely.box(4, 4, 6, 6))
        keepout = KeepOutWitness(
            "circuit.keepout", frozenset({1}), shapely.box(4, 4, 6, 6)
        )
        self.assertTrue(
            check_keepouts((pour(geometry=geometry),), (keepout,), MIN_FEATURE)[0].passed
        )

    def test_micron_corner_residue_does_not_fail_a_correct_void(self) -> None:
        # Regression for a gate that could not pass correct work. The runtime
        # rounds a void's inner corners, leaving micron-scale triangles inside the
        # keepout: measured at 9.46e-05 mm^2 over four ~9 um corners on a real
        # build, against an exact `overlap == 0.0` test. Residue this small is not
        # copper any process can make, so it must not fail the check.
        keepout = shapely.box(4, 4, 6, 6)
        void = keepout.buffer(-0.009, join_style=1)  # rounded inner corners
        geometry = shapely.box(1, 1, 9, 9).difference(void)
        result = check_keepouts(
            (pour(geometry=geometry),),
            (KeepOutWitness("circuit.keepout", frozenset({1}), keepout),),
            MIN_FEATURE,
        )[0]
        self.assertGreater(result.measured, 0.0)  # residue is genuinely present
        self.assertTrue(result.passed)  # and is below anything manufacturable

    def test_manufacturable_copper_in_keepout_still_fails(self) -> None:
        # The other side of the same predicate: residue wide enough to build is a
        # real violation however small its area looks next to the pour.
        keepout = shapely.box(4, 4, 6, 6)
        intruder = shapely.box(4.5, 4.5, 5.5, 5.5)
        result = check_keepouts(
            (pour(geometry=intruder),),
            (KeepOutWitness("circuit.keepout", frozenset({1}), keepout),),
            MIN_FEATURE,
        )[0]
        self.assertFalse(result.passed)

    def test_edge_spacing_tolerates_representation_error(self) -> None:
        # A pour buffered inward by exactly the floor captures back at 0.29999997
        # against a 0.3 floor. That is float representation, not a spacing
        # violation, and the previous 1e-9 slack was tighter than the error.
        board = shapely.box(0, 0, 10, 10)
        just_under = pour(geometry=shapely.box(0.29999997, 0.29999997, 9.7, 9.7))
        self.assertTrue(check_board_edge(board, (just_under,), 0.3)[0].passed)

    def test_edge_spacing_still_fails_a_real_violation(self) -> None:
        board = shapely.box(0, 0, 10, 10)
        too_close = pour(geometry=shapely.box(0.2, 0.2, 9.8, 9.8))
        self.assertFalse(check_board_edge(board, (too_close,), 0.3)[0].passed)

    def test_board_wide_pour_must_meet_fabrication_minimum(self) -> None:
        board = shapely.box(0, 0, 10, 10)
        too_close = pour(geometry=shapely.box(0.1, 0.1, 9.9, 9.9))
        correct = pour(geometry=shapely.box(0.2, 0.2, 9.8, 9.8))
        self.assertFalse(check_board_edge(board, (too_close,), 0.2)[0].passed)
        self.assertTrue(check_board_edge(board, (correct,), 0.2)[0].passed)


class VacuousPassTests(unittest.TestCase):
    """A green result has to be evidence. These pin the two rows that were not."""

    def test_keepout_with_no_same_layer_pour_is_a_finding_not_a_pass(self) -> None:
        # Previously reported PASS with same-layer-comparisons=0, which reads
        # identically whether the keepout is working or is on the wrong layer.
        keepout = KeepOutWitness(
            "circuit.keepout", frozenset({7}), shapely.box(4, 4, 6, 6)
        )
        results = check_keepouts((pour(),), (keepout,), MIN_FEATURE)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].passed)
        self.assertIn("same-layer-comparisons=0", results[0].detail)

    def test_no_keepouts_emits_no_row_at_all(self) -> None:
        # An absent check must not look like a passing one.
        self.assertEqual(check_keepouts((pour(),), (), MIN_FEATURE), [])

    def test_edge_check_names_the_board_wide_target(self) -> None:
        # The identity that board-wide-target used to carry now rides on the
        # check that actually proves something about the pour.
        board = shapely.box(0, 0, 10, 10)
        witness = pour(geometry=shapely.box(0.4, 0.4, 9.6, 9.6))
        result = check_board_edge(
            board, (witness,), 0.3, {witness.label: "circuit.ground"}
        )[0]
        self.assertTrue(result.passed)
        self.assertIn("board-wide-target=circuit.ground", result.detail)


class CaptureAdapterTests(unittest.TestCase):
    def test_bottom_side_normalizes_pour_and_keepout_layers(self) -> None:
        class BottomSide:
            def apply(self, layer: int) -> int:
                return -layer - 1

        class Layers:
            def normalize(self, layer: int) -> int:
                return layer + 4 if layer < 0 else layer

        rd = SimpleNamespace(layers=lambda: Layers())
        transform = SimpleNamespace(side=BottomSide())
        self.assertEqual(
            _normalized_pour_layer(rd, SimpleNamespace(layer=0), transform), 3
        )
        self.assertEqual(
            _normalized_layers(
                rd,
                SimpleNamespace(ranges=((0, 1),)),
                transform,
            ),
            frozenset({2, 3}),
        )

    def test_capture_inventory_reaches_every_required_check(self) -> None:
        class FakePour:
            pass

        class FakeKeepOut:
            pass

        class FakeComputedStitchVia:
            pass

        class FakeDesign:
            pass

        authored_shape = object()
        computed_shape = object()
        keepout_shape = object()
        board_shape = object()
        pour_object = FakePour()
        pour_object.shape = authored_shape
        keepout_object = FakeKeepOut()
        keepout_object.shape = keepout_shape
        keepout_object.pour = True
        keepout_object.layers = object()
        pour_trace = SimpleNamespace(path="circuit.ground", transform=object())
        keepout_trace = SimpleNamespace(path="circuit.moat", transform=object())
        runtime_net = SimpleNamespace(name="GND")
        group_net = object()
        stitch_group = SimpleNamespace(
            net=group_net,
            vias=[SimpleNamespace(position=(2.0, 2.0))],
        )
        root = SimpleNamespace(
            circuit=SimpleNamespace(ground=pour_object),
            board=SimpleNamespace(shape=board_shape),
            substrate=SimpleNamespace(
                constraints=SimpleNamespace(min_copper_edge_space=0.2)
            ),
        )

        class FakeNets:
            def find(self, target: object) -> object | None:
                if target is pour_object or target is group_net:
                    return runtime_net
                return None

        class FakeRuntimeDesign:
            def __init__(self) -> None:
                self.root = root
                self.capture_called = False

            def capture(self) -> None:
                self.capture_called = True
                pour_object.shape = computed_shape

            def nets(self) -> FakeNets:
                return FakeNets()

            def query(self, target: type):
                self.queried = target
                return [(SimpleNamespace(), stitch_group)]

        rd = FakeRuntimeDesign()

        class FakeRuntime:
            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def submit(self, design: type) -> FakeRuntimeDesign:
                self.submitted = design
                return rd

        jitx_module = types.ModuleType("jitx")
        jitx_module.runtime = FakeRuntime()  # type: ignore[attr-defined]
        copper_module = types.ModuleType("jitx.copper")
        copper_module.Pour = FakePour  # type: ignore[attr-defined]
        feature_module = types.ModuleType("jitx.feature")
        feature_module.KeepOut = FakeKeepOut  # type: ignore[attr-defined]
        applied_module = types.ModuleType("jitx._translate.reverse_flow.applied")
        applied_module.ComputedStitchVia = FakeComputedStitchVia  # type: ignore[attr-defined]
        transform_module = types.ModuleType("jitx.transform")
        transform_module.IDENTITY = object()  # type: ignore[attr-defined]
        modules = {
            "jitx": jitx_module,
            "jitx.copper": copper_module,
            "jitx.feature": feature_module,
            "jitx._translate.reverse_flow.applied": applied_module,
            "jitx.transform": transform_module,
        }

        def visits(_root: object, target: type):
            if target is FakePour:
                return [(pour_trace, pour_object)]
            if target is FakeKeepOut:
                return [(keepout_trace, keepout_object)]
            raise AssertionError(f"unexpected visit target {target}")

        def geometry(shape: object, _transform: object):
            geometries = {
                computed_shape: shapely.box(1, 1, 9, 9),
                keepout_shape: shapely.box(0.3, 0.3, 0.7, 0.7),
                board_shape: shapely.box(0, 0, 10, 10),
            }
            return geometries[shape], False

        with (
            patch.dict(sys.modules, modules),
            patch.object(realization, "_load_design", return_value=FakeDesign),
            patch.object(realization, "_unique_visits", side_effect=visits),
            patch.object(
                realization,
                "_stitch_rule_targets",
                return_value=([pour_object], 1),
            ),
            patch.object(realization, "_geometry", side_effect=geometry),
            patch.object(realization, "_normalized_pour_layer", return_value=1),
            patch.object(
                realization, "_normalized_layers", return_value=frozenset({1})
            ),
        ):
            checks = realization._capture_checks(
                "project.Design",
                ("circuit.ground",),
                ("circuit.ground",),
            )

        self.assertTrue(rd.capture_called)
        self.assertEqual(
            {result.name for result in checks},
            {
                "pour-realization",
                "stitch-realization",
                "pour-keepout",
                "copper-edge-spacing",
            },
            "board-wide-target is deliberately absent: it passed unconditionally "
            "once the path resolved to a Pour, so it inflated the passing count "
            "with a row that tested nothing. The board-wide pour's edge spacing is "
            "what the caller wants proved, and copper-edge-spacing proves it.",
        )
        self.assertTrue(all(result.passed for result in checks))


class CommandContractTests(unittest.TestCase):
    def test_unchanged_authored_shape_is_not_a_capture_witness(self) -> None:
        shape = object()
        captured = SimpleNamespace(shape=shape)
        with self.assertRaisesRegex(ValueError, "no computed-shape witness"):
            _require_computed_pour("circuit.ground", (object(), captured), id(shape))

    def test_distinct_computed_shape_is_a_capture_witness(self) -> None:
        captured = SimpleNamespace(shape=object())
        entry = (object(), captured)
        self.assertEqual(
            _require_computed_pour("circuit.ground", entry, id(object())),
            entry,
        )

    def test_unreadable_design_target_is_exit_two(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main(["not_a_real_module.RealDesign"])
        self.assertEqual(result, 2)
        self.assertIn("did not run", stderr.getvalue())

    def test_runtime_environment_failure_is_exit_two(self) -> None:
        stderr = io.StringIO()
        with (
            patch(
                "check_realization._capture_checks",
                side_effect=Exception("no active runtime"),
            ),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["project.Design"])
        self.assertEqual(result, 2)
        self.assertIn("no active runtime", stderr.getvalue())

    def test_empty_check_list_fails(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = run_checks([])
        self.assertEqual(result, 1)
        self.assertIn("nothing was verified", stdout.getvalue())

    def test_clean_result_exits_zero(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = run_checks([CheckResult("sample", True, 1, 1, "witness")])
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
