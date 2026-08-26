#!/usr/bin/env python3
"""Deterministic geometry solver for a bank of decoupling capacitors.

The module has no JITX dependency because it is copied into user projects. The
search is exhaustive over a finite square grid centered on each hint's IC-pad
centroid. Positions start at the centroid and expand in square rings, with
row-major order inside each ring. For every position it tests 0, 90, 180, and
270 degrees (skill default: four rotations). It rejects keepout overlap,
clearance violations against every IC pad, capacitor conflicts, degenerate or
self-intersecting loops, and insufficient separation between opposing power
and return paths. A branch-and-bound search minimizes summed loop area.

For a hint that contains more than one power or return pad, its capacitor loop
area is the arithmetic mean over every power-pad and return-pad pair in that
hint. Each loop follows capacitor power pad, IC power pad, IC return pad, and
capacitor return via. Equal totals are resolved lexicographically in hint order,
then by center-out grid position, then by rotation order. Nothing is random.

Run as ``python decoupling_solver.py spec.json``. The JSON form uses the same
field names as the public dataclasses. Exit 0 prints a JSON solution, exit 1
reports invalid or infeasible geometry, and exit 2 reports command usage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from math import ceil, hypot, inf, isfinite
from pathlib import Path
import sys
from typing import Any, Sequence

Point = tuple[float, float]
Polygon = tuple[Point, ...]

_EPSILON = 1e-9
_ROTATIONS = (0, 90, 180, 270)  # skill default: four orthogonal rotations


@dataclass(frozen=True)
class HintSpec:
    """IC pads served by one capacitor."""

    name: str
    power_pads: tuple[Point, ...]
    return_pads: tuple[Point, ...]


@dataclass(frozen=True)
class CapacitorGeometry:
    """Body and copper-pad dimensions in millimeters.

    ``pad_pitch`` is the center-to-center pitch. At zero degrees the power pad
    is on local negative X and the return pad is on local positive X.
    """

    body_length: float
    body_width: float
    pad_length: float
    pad_width: float
    pad_pitch: float


@dataclass(frozen=True)
class BankSpec:
    """Complete input for :func:`solve`. All distances are millimeters."""

    hints: tuple[HintSpec, ...]
    capacitor: CapacitorGeometry
    keepouts: tuple[Polygon, ...]
    via_pad_diameter: float
    clearance_floor: float
    capacitor_spacing: float
    grid_step: float = 0.25  # skill default: 0.25 mm candidate-grid step
    search_radius: float = 3.0  # skill default: 3.0 mm search radius per hint


@dataclass(frozen=True)
class CapacitorPlacement:
    """One placement and the via location for each capacitor net."""

    hint: str
    center: Point
    rotation: int
    power_via: Point
    return_via: Point
    loop_area: float


@dataclass(frozen=True)
class Solution:
    """Placements in input hint order and their summed loop-area proxy."""

    placements: tuple[CapacitorPlacement, ...]
    total_loop_area: float


@dataclass(frozen=True)
class _Rectangle:
    vertices: Polygon


@dataclass(frozen=True)
class _Circle:
    center: Point
    radius: float


type _Primitive = _Rectangle | _Circle


@dataclass(frozen=True)
class _Candidate:
    placement: CapacitorPlacement
    primitives: tuple[_Primitive, ...]
    loop_polygons: tuple[Polygon, ...]
    order: int


def _validate_point(point: Sequence[float], field: str) -> Point:
    if len(point) != 2:
        raise ValueError(f"{field} must contain exactly two coordinates")
    x, y = float(point[0]), float(point[1])
    if not (-inf < x < inf and -inf < y < inf):
        raise ValueError(f"{field} coordinates must be finite")
    return x, y


def _validate(spec: BankSpec) -> None:
    if not spec.hints:
        raise ValueError("hints must contain at least one hint group")
    names: set[str] = set()
    for index, hint in enumerate(spec.hints):
        if not hint.name:
            raise ValueError(f"hints[{index}].name must not be empty")
        if hint.name in names:
            raise ValueError(f"duplicate hint group name: {hint.name!r}")
        names.add(hint.name)
        if not hint.power_pads:
            raise ValueError(f"hint group {hint.name!r} has no IC power pads")
        if not hint.return_pads:
            raise ValueError(f"hint group {hint.name!r} has no IC return pads")
        for pad_index, point in enumerate(hint.power_pads):
            _validate_point(point, f"{hint.name}.power_pads[{pad_index}]")
        for pad_index, point in enumerate(hint.return_pads):
            _validate_point(point, f"{hint.name}.return_pads[{pad_index}]")

    dims = spec.capacitor
    scalar_values = {
        "body_length": dims.body_length,
        "body_width": dims.body_width,
        "pad_length": dims.pad_length,
        "pad_width": dims.pad_width,
        "pad_pitch": dims.pad_pitch,
        "via_pad_diameter": spec.via_pad_diameter,
        "clearance_floor": spec.clearance_floor,
        "capacitor_spacing": spec.capacitor_spacing,
        "grid_step": spec.grid_step,
        "search_radius": spec.search_radius,
    }
    for field, value in scalar_values.items():
        if not isfinite(value):
            raise ValueError(f"{field} must be finite")
    positive_dimensions = {
        field: scalar_values[field]
        for field in (
            "body_length",
            "body_width",
            "pad_length",
            "pad_width",
            "pad_pitch",
            "via_pad_diameter",
            "grid_step",
        )
    }
    for field, value in positive_dimensions.items():
        if value <= 0:
            raise ValueError(f"{field} must be greater than zero")
    if spec.clearance_floor < 0:
        raise ValueError("clearance_floor must not be negative")
    if spec.capacitor_spacing < 0:
        raise ValueError("capacitor_spacing must not be negative")
    if spec.search_radius < 0:
        raise ValueError("search_radius must not be negative")
    for index, keepout in enumerate(spec.keepouts):
        if len(keepout) < 3:
            raise ValueError(f"keepouts[{index}] must have at least three points")
        for point_index, point in enumerate(keepout):
            _validate_point(point, f"keepouts[{index}][{point_index}]")


def _rotate(point: Point, rotation: int) -> Point:
    x, y = point
    if rotation == 0:
        return x, y
    if rotation == 90:
        return -y, x
    if rotation == 180:
        return -x, -y
    if rotation == 270:
        return y, -x
    raise ValueError(f"unsupported rotation: {rotation}")


def _translate(point: Point, center: Point) -> Point:
    return point[0] + center[0], point[1] + center[1]


def _placed(point: Point, center: Point, rotation: int) -> Point:
    return _translate(_rotate(point, rotation), center)


def _rectangle(
    center: Point, length: float, width: float, rotation: int
) -> _Rectangle:
    half_l = length / 2.0
    half_w = width / 2.0
    local = (
        (-half_l, -half_w),
        (half_l, -half_w),
        (half_l, half_w),
        (-half_l, half_w),
    )
    return _Rectangle(tuple(_placed(point, center, rotation) for point in local))


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_on_segment(point: Point, a: Point, b: Point) -> bool:
    if abs(_orientation(a, b, point)) > _EPSILON:
        return False
    return (
        min(a[0], b[0]) - _EPSILON <= point[0] <= max(a[0], b[0]) + _EPSILON
        and min(a[1], b[1]) - _EPSILON
        <= point[1]
        <= max(a[1], b[1]) + _EPSILON
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if (o1 > _EPSILON and o2 < -_EPSILON or o1 < -_EPSILON and o2 > _EPSILON) and (
        o3 > _EPSILON and o4 < -_EPSILON
        or o3 < -_EPSILON and o4 > _EPSILON
    ):
        return True
    return (
        abs(o1) <= _EPSILON
        and _point_on_segment(c, a, b)
        or abs(o2) <= _EPSILON
        and _point_on_segment(d, a, b)
        or abs(o3) <= _EPSILON
        and _point_on_segment(a, c, d)
        or abs(o4) <= _EPSILON
        and _point_on_segment(b, c, d)
    )


def _segments(polygon: Polygon) -> tuple[tuple[Point, Point], ...]:
    return tuple(
        (polygon[index], polygon[(index + 1) % len(polygon)])
        for index in range(len(polygon))
    )


def _point_in_polygon(point: Point, polygon: Polygon) -> bool:
    inside = False
    x, y = point
    for a, b in _segments(polygon):
        if _point_on_segment(point, a, b):
            return True
        if (a[1] > y) != (b[1] > y):
            cross_x = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            if x < cross_x:
                inside = not inside
    return inside


def _point_segment_distance(point: Point, a: Point, b: Point) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= _EPSILON:
        return hypot(point[0] - a[0], point[1] - a[1])
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    closest = (a[0] + t * dx, a[1] + t * dy)
    return hypot(point[0] - closest[0], point[1] - closest[1])


def _segment_distance(a: Point, b: Point, c: Point, d: Point) -> float:
    if _segments_intersect(a, b, c, d):
        return 0.0
    return min(
        _point_segment_distance(a, c, d),
        _point_segment_distance(b, c, d),
        _point_segment_distance(c, a, b),
        _point_segment_distance(d, a, b),
    )


def _point_polygon_distance(point: Point, polygon: Polygon) -> float:
    if _point_in_polygon(point, polygon):
        return 0.0
    return min(_point_segment_distance(point, a, b) for a, b in _segments(polygon))


def _polygon_distance(first: Polygon, second: Polygon) -> float:
    if _point_in_polygon(first[0], second) or _point_in_polygon(second[0], first):
        return 0.0
    return min(
        _segment_distance(a, b, c, d)
        for a, b in _segments(first)
        for c, d in _segments(second)
    )


def _primitive_polygon_distance(primitive: _Primitive, polygon: Polygon) -> float:
    if isinstance(primitive, _Rectangle):
        return _polygon_distance(primitive.vertices, polygon)
    return max(0.0, _point_polygon_distance(primitive.center, polygon) - primitive.radius)


def _point_primitive_distance(point: Point, primitive: _Primitive) -> float:
    if isinstance(primitive, _Rectangle):
        return _point_polygon_distance(point, primitive.vertices)
    return max(0.0, hypot(point[0] - primitive.center[0], point[1] - primitive.center[1]) - primitive.radius)


def _primitive_distance(first: _Primitive, second: _Primitive) -> float:
    if isinstance(first, _Rectangle) and isinstance(second, _Rectangle):
        return _polygon_distance(first.vertices, second.vertices)
    if isinstance(first, _Circle) and isinstance(second, _Circle):
        return max(
            0.0,
            hypot(first.center[0] - second.center[0], first.center[1] - second.center[1])
            - first.radius
            - second.radius,
        )
    if isinstance(first, _Circle) and isinstance(second, _Rectangle):
        return max(
            0.0,
            _point_polygon_distance(first.center, second.vertices) - first.radius,
        )
    if isinstance(first, _Rectangle) and isinstance(second, _Circle):
        return max(
            0.0,
            _point_polygon_distance(second.center, first.vertices) - second.radius,
        )
    raise AssertionError("unhandled primitive pair")


def _polygon_area(points: Sequence[Point]) -> float:
    return abs(
        sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )
    ) / 2.0


def _loop_area(
    power_pad: Point, return_via: Point, hint: HintSpec
) -> float:
    areas = [
        _polygon_area((power_pad, ic_power, ic_return, return_via))
        for ic_power in hint.power_pads
        for ic_return in hint.return_pads
    ]
    return sum(areas) / len(areas)


def _loop_polygons(
    power_pad: Point, return_via: Point, hint: HintSpec
) -> tuple[Polygon, ...]:
    return tuple(
        (power_pad, ic_power, ic_return, return_via)
        for ic_power in hint.power_pads
        for ic_return in hint.return_pads
    )


def _is_simple_loop(polygon: Polygon) -> bool:
    if _polygon_area(polygon) <= _EPSILON:
        return False
    return not (
        _segments_intersect(polygon[0], polygon[1], polygon[2], polygon[3])
        or _segments_intersect(polygon[1], polygon[2], polygon[3], polygon[0])
    )


def _hint_centroid(hint: HintSpec) -> Point:
    points = (*hint.power_pads, *hint.return_pads)
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _candidate(
    hint: HintSpec,
    spec: BankSpec,
    center: Point,
    rotation: int,
    order: int,
) -> _Candidate:
    geometry = spec.capacitor
    power_pad = _placed((-geometry.pad_pitch / 2.0, 0.0), center, rotation)
    return_pad = _placed((geometry.pad_pitch / 2.0, 0.0), center, rotation)
    via_offset = (
        geometry.pad_pitch / 2.0
        + geometry.pad_length / 2.0
        + spec.via_pad_diameter / 2.0
    )
    power_via = _placed((-via_offset, 0.0), center, rotation)
    return_via = _placed((via_offset, 0.0), center, rotation)
    primitives: tuple[_Primitive, ...] = (
        _rectangle(center, geometry.body_length, geometry.body_width, rotation),
        _rectangle(
            power_pad, geometry.pad_length, geometry.pad_width, rotation
        ),
        _rectangle(
            return_pad, geometry.pad_length, geometry.pad_width, rotation
        ),
        _Circle(power_via, spec.via_pad_diameter / 2.0),
        _Circle(return_via, spec.via_pad_diameter / 2.0),
    )
    placement = CapacitorPlacement(
        hint=hint.name,
        center=center,
        rotation=rotation,
        power_via=power_via,
        return_via=return_via,
        loop_area=_loop_area(power_pad, return_via, hint),
    )
    return _Candidate(
        placement=placement,
        primitives=primitives,
        loop_polygons=_loop_polygons(power_pad, return_via, hint),
        order=order,
    )


def _positions(center: Point, spec: BankSpec) -> tuple[Point, ...]:
    steps = ceil(spec.search_radius / spec.grid_step)
    indexes: list[tuple[int, int]] = []
    for y_index in range(-steps, steps + 1):
        for x_index in range(-steps, steps + 1):
            x_offset = x_index * spec.grid_step
            y_offset = y_index * spec.grid_step
            if abs(x_offset) > spec.search_radius + _EPSILON:
                continue
            if abs(y_offset) > spec.search_radius + _EPSILON:
                continue
            indexes.append((x_index, y_index))
    indexes.sort(key=lambda item: (max(abs(item[0]), abs(item[1])), item[1], item[0]))
    return tuple(
        (
            round(center[0] + x_index * spec.grid_step, 12),
            round(center[1] + y_index * spec.grid_step, 12),
        )
        for x_index, y_index in indexes
    )


def _candidate_rejection(candidate: _Candidate, hint: HintSpec, spec: BankSpec) -> str | None:
    for keepout in spec.keepouts:
        if any(
            _primitive_polygon_distance(primitive, keepout) <= _EPSILON
            for primitive in candidate.primitives
        ):
            return "keepout overlap"
    ic_pads = tuple(
        pad
        for bank_hint in spec.hints
        for pad in (*bank_hint.power_pads, *bank_hint.return_pads)
    )
    if any(
        _point_primitive_distance(pad, primitive) + _EPSILON
        < spec.clearance_floor
        for pad in ic_pads
        for primitive in candidate.primitives
    ):
        return "IC-pad clearance floor"
    if not all(_is_simple_loop(polygon) for polygon in candidate.loop_polygons):
        return "nondegenerate loop geometry"
    path_clearance = (
        spec.capacitor.pad_width / 2.0
        + max(spec.capacitor.pad_width / 2.0, spec.via_pad_diameter / 2.0)
        + spec.clearance_floor
    )
    if any(
        _segment_distance(polygon[0], polygon[1], polygon[2], polygon[3])
        + _EPSILON
        < path_clearance
        for polygon in candidate.loop_polygons
    ):
        return "power-return path clearance floor"
    return None


def _compatible(first: _Candidate, second: _Candidate, spacing: float) -> bool:
    required = max(spacing, _EPSILON)
    return all(
        _primitive_distance(a, b) + _EPSILON >= required
        for a in first.primitives
        for b in second.primitives
    )


def _candidates_for_hint(hint: HintSpec, spec: BankSpec) -> tuple[_Candidate, ...]:
    candidates: list[_Candidate] = []
    rejection_counts: dict[str, int] = {}
    positions = _positions(_hint_centroid(hint), spec)
    for position_index, center in enumerate(positions):
        for rotation_index, rotation in enumerate(_ROTATIONS):
            order = position_index * len(_ROTATIONS) + rotation_index
            candidate = _candidate(hint, spec, center, rotation, order)
            if reason := _candidate_rejection(candidate, hint, spec):
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
            else:
                candidates.append(candidate)
    if not candidates:
        reason = max(
            rejection_counts,
            key=lambda key: rejection_counts[key],
            default="candidate grid",
        )
        raise ValueError(f"hint group {hint.name!r} infeasible: {reason}")
    return tuple(
        sorted(candidates, key=lambda item: (item.placement.loop_area, item.order))
    )


def solve(bank: BankSpec) -> Solution:
    """Solve ``bank`` and return the minimum-area feasible grid placement.

    Raises:
        ValueError: An input is invalid, a hint has no individually feasible
            candidate, or capacitor spacing prevents a complete bank.
    """

    _validate(bank)
    candidates = tuple(_candidates_for_hint(hint, bank) for hint in bank.hints)
    minimum_remaining = [0.0] * (len(bank.hints) + 1)
    for index in range(len(bank.hints) - 1, -1, -1):
        minimum_remaining[index] = (
            minimum_remaining[index + 1] + candidates[index][0].placement.loop_area
        )

    best_total = inf
    best_signature: tuple[int, ...] | None = None
    best_choice: tuple[_Candidate, ...] | None = None
    deepest_spacing_conflict = 0

    def search(
        depth: int,
        total: float,
        chosen: tuple[_Candidate, ...],
        signature: tuple[int, ...],
    ) -> None:
        nonlocal best_total, best_signature, best_choice, deepest_spacing_conflict
        if total + minimum_remaining[depth] > best_total + _EPSILON:
            return
        if depth == len(candidates):
            if total < best_total - _EPSILON or (
                abs(total - best_total) <= _EPSILON
                and (best_signature is None or signature < best_signature)
            ):
                best_total = total
                best_signature = signature
                best_choice = chosen
            return

        compatible_count = 0
        for candidate in candidates[depth]:
            if not all(
                _compatible(candidate, prior, bank.capacitor_spacing)
                for prior in chosen
            ):
                continue
            compatible_count += 1
            search(
                depth + 1,
                total + candidate.placement.loop_area,
                (*chosen, candidate),
                (*signature, candidate.order),
            )
        if compatible_count == 0:
            deepest_spacing_conflict = max(deepest_spacing_conflict, depth)

    search(0, 0.0, (), ())
    if best_choice is None:
        hint = bank.hints[deepest_spacing_conflict]
        raise ValueError(
            f"hint group {hint.name!r} infeasible: capacitor-to-capacitor spacing"
        )
    placements = tuple(candidate.placement for candidate in best_choice)
    return Solution(placements=placements, total_loop_area=sum(p.loop_area for p in placements))


def _point_tuple(raw: Any, field: str) -> Point:
    if not isinstance(raw, list | tuple):
        raise ValueError(f"{field} must be a coordinate pair")
    return _validate_point(raw, field)


def _from_json(raw: Any) -> BankSpec:
    if not isinstance(raw, dict):
        raise ValueError("the JSON root must be an object")
    try:
        hint_values = raw["hints"]
        capacitor_value = raw["capacitor"]
        keepout_values = raw.get("keepouts", [])
        if not isinstance(hint_values, list):
            raise ValueError("hints must be a list")
        if not isinstance(capacitor_value, dict):
            raise ValueError("capacitor must be an object")
        if not isinstance(keepout_values, list):
            raise ValueError("keepouts must be a list")
        hints = tuple(
            HintSpec(
                name=str(value["name"]),
                power_pads=tuple(
                    _point_tuple(point, f"hints[{index}].power_pads")
                    for point in value["power_pads"]
                ),
                return_pads=tuple(
                    _point_tuple(point, f"hints[{index}].return_pads")
                    for point in value["return_pads"]
                ),
            )
            for index, value in enumerate(hint_values)
        )
        capacitor = CapacitorGeometry(
            body_length=float(capacitor_value["body_length"]),
            body_width=float(capacitor_value["body_width"]),
            pad_length=float(capacitor_value["pad_length"]),
            pad_width=float(capacitor_value["pad_width"]),
            pad_pitch=float(capacitor_value["pad_pitch"]),
        )
        keepouts = tuple(
            tuple(
                _point_tuple(point, f"keepouts[{polygon_index}]")
                for point in polygon
            )
            for polygon_index, polygon in enumerate(keepout_values)
        )
        return BankSpec(
            hints=hints,
            capacitor=capacitor,
            keepouts=keepouts,
            via_pad_diameter=float(raw["via_pad_diameter"]),
            clearance_floor=float(raw["clearance_floor"]),
            capacitor_spacing=float(raw["capacitor_spacing"]),
            grid_step=float(raw.get("grid_step", 0.25)),  # skill default: 0.25 mm
            search_radius=float(raw.get("search_radius", 3.0)),  # skill default: 3.0 mm
        )
    except KeyError as exc:
        raise ValueError(f"missing required JSON field: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"invalid JSON field type: {exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. See the module docstring for exit codes."""

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: python decoupling_solver.py spec.json", file=sys.stderr)
        return 2
    try:
        raw = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        solution = solve(_from_json(raw))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(solution), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
