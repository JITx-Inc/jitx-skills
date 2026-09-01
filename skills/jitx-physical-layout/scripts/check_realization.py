#!/usr/bin/env python3
"""Capture a JITX design and fail on missing or invalid pour realization.

The command submits and captures a zero-argument ``Design`` target, checks every
authored ``Pour``, reconstructs stitch-rule targets, and verifies optional named
witness aliases. It uses the captured computed pour shape, not build status or
the authored outline.

Exit codes: 0 clean; 1 findings or no checks; 2 usage, import/runtime/capture
failure, or geometry that cannot be read safely.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass
from typing import Any

# Slack for float representation in captured geometry, well under any fab floor.
EDGE_EPSILON_MM = 1e-6


@dataclass(frozen=True)
class CheckResult:
    """One measured realization result with stable line-oriented output."""

    name: str
    passed: bool
    measured: float | int | None
    expected: float | int | None
    detail: str


@dataclass(frozen=True)
class PourWitness:
    """Captured, design-global evidence for one authored pour."""

    label: str
    net: str
    layer: int
    geometry: object | None
    empty: bool = False


@dataclass(frozen=True)
class KeepOutWitness:
    """Design-global geometry and normalized layers for one pour keepout."""

    label: str
    layers: frozenset[int]
    geometry: object


@dataclass(frozen=True)
class StitchTargetWitness:
    """One explicitly named stitch target and its solver-emitted via centers."""

    label: str
    target_type: str
    pour: PourWitness | None
    via_points: tuple[tuple[float, float], ...]


def check_pours(pours: tuple[PourWitness, ...]) -> list[CheckResult]:
    """Return one non-empty-copper result per authored pour."""

    results: list[CheckResult] = []
    for pour in pours:
        geometry = pour.geometry
        area = None if geometry is None else float(getattr(geometry, "area"))
        passed = not pour.empty and area is not None and area > 0.0
        state = (
            "Empty()" if pour.empty else "no readable copper" if area is None else ""
        )
        detail = f"pour={pour.label} net={pour.net} layer={pour.layer}"
        if state:
            detail += f" realized={state}"
        results.append(
            CheckResult(
                name="pour-realization",
                passed=passed,
                measured=area,
                expected=0.0,
                detail=detail,
            )
        )
    if not pours:
        results.append(
            CheckResult(
                name="pour-realization",
                passed=True,
                measured=0,
                expected=0,
                detail="authored-pours=0 (capture completed; no Pour objects authored)",
            )
        )
    return results


def check_stitch_targets(
    targets: tuple[StitchTargetWitness, ...], stitch_rule_count: int
) -> list[CheckResult]:
    """Require every selected Pour stitch target to contain a computed stitch via."""

    if stitch_rule_count and not targets:
        return [
            CheckResult(
                name="stitch-coverage",
                passed=False,
                measured=0,
                expected=stitch_rule_count,
                detail=(
                    f"stitch-rules={stitch_rule_count} selected-pour-targets=0; "
                    "the rules selected no authored Pour"
                ),
            )
        ]

    results: list[CheckResult] = []
    for target in targets:
        if target.pour is None:
            results.append(
                CheckResult(
                    name="stitch-realization",
                    passed=False,
                    measured=0,
                    expected=1,
                    detail=(
                        f"target={target.label} type={target.target_type}; "
                        "stitch_via requires a Pour"
                    ),
                )
            )
            continue
        geometry = target.pour.geometry
        count = 0
        if geometry is not None:
            import shapely

            count = sum(
                bool(geometry.covers(shapely.Point(point)))
                for point in target.via_points
            )
        results.append(
            CheckResult(
                name="stitch-realization",
                passed=count > 0,
                measured=count,
                expected=1,
                detail=(
                    f"target={target.label} net={target.pour.net} "
                    f"layer={target.pour.layer} computed-vias-inside={count}"
                ),
            )
        )
    return results


def _holds_circle(geometry: object, diameter: float) -> bool:
    """True when `geometry` contains a circle of `diameter`, i.e. real copper.

    Erosion by half the diameter leaves something only where the shape is at
    least that wide, which distinguishes a sliver the process cannot produce
    from a region it can.
    """
    if geometry is None or getattr(geometry, "is_empty", True):
        return False
    try:
        return not geometry.buffer(-diameter / 2.0).is_empty
    except Exception:
        return float(getattr(geometry, "area", 0.0)) > 0.0


def check_keepouts(
    pours: tuple[PourWitness, ...],
    keepouts: tuple[KeepOutWitness, ...],
    min_feature: float,
) -> list[CheckResult]:
    """Reject captured pour area inside every same-layer pour keepout."""

    results: list[CheckResult] = []
    comparisons = 0
    for keepout in keepouts:
        for pour in pours:
            if pour.layer not in keepout.layers or pour.geometry is None:
                continue
            comparisons += 1
            residue = pour.geometry.intersection(keepout.geometry)
            overlap = float(residue.area)
            # `overlap == 0.0` is not reachable on real output. The runtime rounds
            # the void's inner corners, leaving a few micron-scale triangles inside
            # the keepout on an otherwise correct design: measured at 9.46e-05 mm^2
            # across four ~9 um corners. A gate that cannot pass correct work gets
            # routed around, so ask the manufacturable question instead of the
            # arithmetic one: can what is left hold a feature the process can make?
            # Anything that can is real copper in the keepout and fails.
            holdable = _holds_circle(residue, min_feature)
            results.append(
                CheckResult(
                    name="pour-keepout",
                    passed=not holdable,
                    measured=overlap,
                    expected=f"no residue holding a {min_feature:g} mm feature",
                    detail=(
                        f"pour={pour.label} keepout={keepout.label} layer={pour.layer}"
                        + ("" if not holdable else "; residue is manufacturable copper")
                    ),
                )
            )
    if not comparisons:
        results.append(
            CheckResult(
                name="pour-keepout",
                passed=True,
                measured=0,
                expected=0,
                detail=f"same-layer-comparisons=0 keepouts={len(keepouts)}",
            )
        )
    return results


def check_board_edge(
    board_profile: object,
    pours: tuple[PourWitness, ...],
    minimum: float,
) -> list[CheckResult]:
    """Require realized pour copper to be inside and clear of the profile."""

    results: list[CheckResult] = []
    for pour in pours:
        geometry = pour.geometry
        inside = geometry is not None and bool(board_profile.covers(geometry))
        spacing = (
            None
            if geometry is None
            else float(geometry.distance(board_profile.boundary))
        )
        # A pour buffered inward by exactly the floor captures back at
        # 0.29999997 against a 0.3 floor: a representation artifact, not a
        # spacing violation, and 1e-9 is tighter than that error. Allow one
        # micron, which is far below any fabrication floor and far above the
        # noise, and say so rather than tuning a magic number.
        passed = inside and spacing is not None and spacing + EDGE_EPSILON_MM >= minimum
        results.append(
            CheckResult(
                name="copper-edge-spacing",
                passed=passed,
                measured=spacing,
                expected=minimum,
                detail=f"pour={pour.label} inside-profile={inside}",
            )
        )
    return results


def _format_measured(value: float | int | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def run_checks(checks: list[CheckResult]) -> int:
    """Print results and return 1 for any finding or an empty check list."""

    if not checks:
        print("summary: checks=0 failures=1 (no checks supplied; nothing was verified)")
        return 1
    failures = 0
    for result in checks:
        status = "PASS" if result.passed else "FAIL"
        failures += int(not result.passed)
        print(
            f"{status} {result.name}: measured={_format_measured(result.measured)} "
            f"expected={_format_measured(result.expected)} {result.detail}"
        )
    print(f"summary: checks={len(checks)} failures={failures}")
    return 1 if failures else 0


def _load_design(target: str) -> type:
    module_name, separator, object_name = target.replace(":", ".").rpartition(".")
    if not separator or not module_name or not object_name:
        raise ValueError("design target must be module.Design or module:Design")
    module = importlib.import_module(module_name)
    design = getattr(module, object_name)
    if not isinstance(design, type):
        raise TypeError(f"{target} is not a Design class")
    return design


def _resolve_path(root: object, path: str) -> object:
    """Resolve dotted attributes and numeric sequence indexes from a design root."""

    current = root
    for element in path.split("."):
        if not element:
            raise ValueError(f"empty element in witness path {path!r}")
        if element.isdecimal():
            current = current[int(element)]  # type: ignore[index]
        else:
            current = getattr(current, element)
    return current


def _unique_visits(root: object, target: type) -> list[tuple[Any, object]]:
    from jitx.inspect import visit

    seen: set[int] = set()
    found: list[tuple[Any, object]] = []
    for trace, obj in visit(root, target):
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        found.append((trace, obj))
    return found


def _require_computed_pour(
    label: object,
    captured_entry: tuple[Any, object] | None,
    authored_shape_id: int,
) -> tuple[Any, object]:
    """Reject an authored pour with no distinct post-capture shape witness."""

    if captured_entry is None:
        raise ValueError(f"authored pour {label} disappeared from capture")
    trace, captured = captured_entry
    if id(captured.shape) == authored_shape_id:
        raise ValueError(f"authored pour {label} has no computed-shape witness")
    return trace, captured


def _geometry(shape: object, transform: object) -> tuple[object | None, bool]:
    """Convert captured JITX geometry globally while preserving PolygonSet holes."""

    import shapely
    from jitx.shapes.primitive import Empty, PolygonSet
    from jitx.shapes.shapely import ShapelyGeometry

    primitive = getattr(shape, "geometry", shape)
    if isinstance(primitive, Empty):
        return None, True
    if transform is None:
        raise ValueError("unresolved capture transform")
    if isinstance(primitive, PolygonSet):
        polygons = [
            shapely.Polygon(polygon.elements, polygon.holes)
            for polygon in primitive.polygons
        ]
        local = ShapelyGeometry(shapely.MultiPolygon(polygons)).apply(
            getattr(shape, "transform")
        )
    else:
        local = shape.to_shapely()
    geometry = local.apply(transform).g
    if geometry.is_empty:
        return None, True
    if geometry.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError(f"captured geometry is {geometry.geom_type}, not polygonal")
    return geometry, False


def _normalized_layers(
    rd: object, layer_set: object, transform: object
) -> frozenset[int]:
    layers: set[int] = set()
    side = getattr(transform, "side", None)
    for begin, end in layer_set.ranges:
        if side is not None:
            begin = side.apply(begin)
            end = side.apply(end)
        begin = rd.layers().normalize(begin)
        end = rd.layers().normalize(end)
        low, high = sorted((begin, end))
        layers.update(range(low, high + 1))
    return frozenset(layers)


def _normalized_pour_layer(rd: object, pour: object, transform: object) -> int:
    """Return a pour layer after applying any placement-side transform."""

    layer = pour.layer
    side = getattr(transform, "side", None)
    if side is not None:
        layer = side.apply(layer)
    return rd.layers().normalize(layer)


def _stitch_rule_targets(
    rd: object,
    authored: list[tuple[Any, object]],
) -> tuple[list[object], int]:
    """Reconstruct which authored pours every stitch rule selects."""

    from jitx.constraints import (
        AndExpr,
        AtomExpr,
        BuiltinTag,
        NotExpr,
        OnLayer,
        OrExpr,
        TrueExpr,
        UnaryDesignConstraint,
        _ApplyTag,
    )

    pours = [obj for _, obj in authored]
    layers_by_pour = {
        id(pour): _normalized_pour_layer(rd, pour, trace.transform)
        for trace, pour in authored
    }
    pour_ids = {id(pour) for pour in pours}
    tags_by_pour: dict[int, list[object]] = {id(pour): [] for pour in pours}
    for _, assignment in _unique_visits(rd.root, _ApplyTag):
        if id(assignment.target) in pour_ids:
            tags_by_pour[id(assignment.target)].extend(assignment.tags.tags)

    def matches(expr: object, pour: object) -> bool:
        if isinstance(expr, TrueExpr):
            return True
        if isinstance(expr, AtomExpr):
            atom = expr.atom
            if isinstance(atom, BuiltinTag):
                return atom in (BuiltinTag.IsCopper, BuiltinTag.IsPour)
            if isinstance(atom, OnLayer):
                return rd.layers().normalize(atom.index) == layers_by_pour[id(pour)]
            return any(
                isinstance(assigned, type(atom)) for assigned in tags_by_pour[id(pour)]
            )
        if isinstance(expr, NotExpr):
            return not matches(expr.expr, pour)
        if isinstance(expr, OrExpr):
            return matches(expr.left, pour) or matches(expr.right, pour)
        if isinstance(expr, AndExpr):
            return matches(expr.left, pour) and matches(expr.right, pour)
        raise TypeError(f"unsupported stitch-rule selector {type(expr).__name__}")

    rules = [
        rule
        for _, rule in _unique_visits(rd.root, UnaryDesignConstraint)
        if rule.stitch_via_constraint is not None
    ]
    selected: list[object] = []
    selected_ids: set[int] = set()
    for rule in rules:
        for pour in pours:
            if matches(rule.condition, pour) and id(pour) not in selected_ids:
                selected.append(pour)
                selected_ids.add(id(pour))
    return selected, len(rules)


def _capture_checks(
    design_target: str,
    stitch_paths: tuple[str, ...],
    board_wide_paths: tuple[str, ...],
) -> list[CheckResult]:
    import jitx
    from jitx.copper import Pour
    from jitx.feature import KeepOut
    from jitx._translate.reverse_flow.applied import ComputedStitchVia
    from jitx.transform import IDENTITY

    design = _load_design(design_target)
    with jitx.runtime as runtime:
        rd = runtime.submit(design)
        authored = _unique_visits(rd.root, Pour)
        authored_shape_ids = {id(pour): id(pour.shape) for _, pour in authored}
        selected_stitch_pours, stitch_rule_count = _stitch_rule_targets(rd, authored)
        stitch_targets = [(path, _resolve_path(rd.root, path)) for path in stitch_paths]
        named_ids = {id(target) for _, target in stitch_targets}
        trace_by_id = {id(obj): trace for trace, obj in authored}
        stitch_targets.extend(
            (str(trace_by_id[id(target)].path), target)
            for target in selected_stitch_pours
            if id(target) not in named_ids
        )
        board_wide_targets = [
            (path, _resolve_path(rd.root, path)) for path in board_wide_paths
        ]
        rd.capture()

    captured_pours = {
        id(obj): (trace, obj) for trace, obj in _unique_visits(rd.root, Pour)
    }
    pour_samples: list[PourWitness] = []
    samples_by_id: dict[int, PourWitness] = {}
    for authored_trace, pour in authored:
        trace, captured = _require_computed_pour(
            authored_trace.path,
            captured_pours.get(id(pour)),
            authored_shape_ids[id(pour)],
        )
        geometry, empty = _geometry(captured.shape, trace.transform)
        runtime_net = rd.nets().find(captured)
        net_name = (
            "<unresolved>" if runtime_net is None else runtime_net.name or "<unnamed>"
        )
        sample = PourWitness(
            label=str(trace.path),
            net=net_name,
            layer=_normalized_pour_layer(rd, captured, trace.transform),
            geometry=geometry,
            empty=empty,
        )
        pour_samples.append(sample)
        samples_by_id[id(pour)] = sample

    stitch_groups = [group for _, group in rd.query(ComputedStitchVia)]
    stitch_samples: list[StitchTargetWitness] = []
    for label, target in stitch_targets:
        if not isinstance(target, Pour):
            stitch_samples.append(
                StitchTargetWitness(label, type(target).__name__, None, ())
            )
            continue
        sample = samples_by_id.get(id(target))
        if sample is None:
            raise ValueError(f"stitch target {label!r} is not an authored Pour")
        target_net = rd.nets().find(target)
        points: list[tuple[float, float]] = []
        for group in stitch_groups:
            group_net = rd.nets().find(group.net) if group.net is not None else None
            if target_net is not None and group_net is target_net:
                points.extend(tuple(via.position) for via in group.vias)
        stitch_samples.append(StitchTargetWitness(label, "Pour", sample, tuple(points)))

    keepout_samples: list[KeepOutWitness] = []
    for trace, keepout in _unique_visits(rd.root, KeepOut):
        if not keepout.pour:
            continue
        geometry, empty = _geometry(keepout.shape, trace.transform)
        if empty or geometry is None:
            raise ValueError(f"pour keepout {trace.path} has empty geometry")
        keepout_samples.append(
            KeepOutWitness(
                label=str(trace.path),
                layers=_normalized_layers(rd, keepout.layers, trace.transform),
                geometry=geometry,
            )
        )

    pours = tuple(pour_samples)
    checks = check_pours(pours)
    checks.extend(check_stitch_targets(tuple(stitch_samples), stitch_rule_count))
    # The smallest copper the process can make. Residue narrower than this inside a
    # keepout is a rounding artifact of the void, not copper anyone can fabricate.
    try:
        min_feature = float(rd.root.substrate.constraints.min_copper_width)
    except Exception:
        min_feature = 0.09  # JLCPCB-class floor; only used to size the predicate
    checks.extend(check_keepouts(pours, tuple(keepout_samples), min_feature))

    for label, target in board_wide_targets:
        if not isinstance(target, Pour):
            checks.append(
                CheckResult(
                    name="copper-edge-spacing",
                    passed=False,
                    measured=None,
                    expected=None,
                    detail=f"target={label} type={type(target).__name__}; expected Pour",
                )
            )
            continue
        sample = samples_by_id.get(id(target))
        if sample is None:
            raise ValueError(f"board-wide target {label!r} is not an authored Pour")
        checks.append(
            CheckResult(
                name="board-wide-target",
                passed=True,
                measured=1,
                expected=1,
                detail=f"target={label} pour={sample.label}",
            )
        )
    if pours:
        board_geometry, empty = _geometry(rd.root.board.shape, IDENTITY)
        if empty or board_geometry is None:
            raise ValueError("captured board profile is empty")
        minimum = float(rd.root.substrate.constraints.min_copper_edge_space)
        checks.extend(check_board_edge(board_geometry, pours, minimum))
    return checks


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design", help="zero-argument design target: module.Design")
    parser.add_argument(
        "--stitch-target",
        action="append",
        default=[],
        metavar="OBJECT_PATH",
        help="dotted path from the Design root to one stitch-rule target; repeatable",
    )
    parser.add_argument(
        "--board-wide-pour",
        action="append",
        default=[],
        metavar="OBJECT_PATH",
        help="dotted path from the Design root to one board-wide Pour; repeatable",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        checks = _capture_checks(
            args.design,
            tuple(args.stitch_target),
            tuple(args.board_wide_pour),
        )
    except Exception as error:
        print(f"ERROR realization check did not run: {error}", file=sys.stderr)
        return 2
    return run_checks(checks)


if __name__ == "__main__":
    raise SystemExit(main())
