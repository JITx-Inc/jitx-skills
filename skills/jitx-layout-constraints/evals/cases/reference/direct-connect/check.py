"""Capture and report each available computed-pour surface for this case."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import jitx
from design import (
    DEFAULT_THERMAL_GAP,
    TEST_PAD_DIAMETER,
    DirectConnectNoEffectDesign,
    DirectConnectWideSpokeDesign,
)
from jitx import Copper, Pad, Pour
from jitx.inspect import visit
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

PAD_INSPECTION_RADIUS = 1.2  # skill default: 1.2 mm inspection radius
GAP_INSPECTION_FRACTION = 0.5  # skill default: inspect halfway through the gap


def _pad_centers(root: Any) -> dict[str, tuple[float, float]]:
    wanted = {
        root.circuit.test.landpattern.thermal_pad: "default-thermal",
        root.circuit.test.landpattern.tagged_pad: "tagged-candidate",
    }
    centers: dict[str, tuple[float, float]] = {}
    for trace, pad in visit(root, Pad):
        label = wanted.get(pad)
        if label is None:
            continue
        if trace.transform is None or pad.transform is None:
            raise ValueError(f"unresolved coordinate frame for {label}")
        x, y = (trace.transform * pad.transform).translation
        centers[label] = (float(x), float(y))
    if centers.keys() != {"default-thermal", "tagged-candidate"}:
        raise AssertionError(f"missing test pads: {centers}")
    return centers


def _shape_geometry(shape: Any, transform: Any) -> BaseGeometry:
    if transform is None:
        raise ValueError("unresolved query transform")
    return cast(BaseGeometry, (transform * shape).to_shapely().g)


def _gap_band(center: tuple[float, float]) -> BaseGeometry:
    pad_radius = TEST_PAD_DIAMETER / 2  # test-pad diameter from the landpattern
    sample_radius = pad_radius + DEFAULT_THERMAL_GAP * GAP_INSPECTION_FRACTION
    return (
        Point(center).buffer(sample_radius).difference(Point(center).buffer(pad_radius))
    )


def _report_gap_coverage(
    source: str,
    geometry: BaseGeometry,
    centers: dict[str, tuple[float, float]],
) -> None:
    for label, center in centers.items():
        band = _gap_band(center)
        coverage = geometry.intersection(band).area / band.area
        print(f"{source} gap-band coverage at {label}: {coverage:.6f}")


def _proto_polygon_set(proto: Any) -> BaseGeometry:
    polygons = []
    for component in proto.components:
        outer = [(point.x, point.y) for point in component.outer.points]
        holes = [
            [(point.x, point.y) for point in inner.points] for inner in component.inners
        ]
        polygons.append(Polygon(outer, holes=holes))
    return unary_union(polygons)


def _capture_summary(rd: Any, raw_layout: Any) -> None:
    centers = _pad_centers(rd.root)
    pours = list(rd.query(Pour))
    coppers = list(rd.query(Copper))
    print(f"capture Pour count: {len(pours)}")
    print(f"capture Copper count: {len(coppers)}")

    pour_geometries: list[BaseGeometry] = []
    for index, (trace, pour) in enumerate(pours):
        g = _shape_geometry(pour.shape, trace.transform)
        pour_geometries.append(g)
        print(
            f"capture pour[{index}]: area={g.area:.6f} "
            f"holes={sum(len(p.interiors) for p in getattr(g, 'geoms', [g]))} "
            f"bounds={g.bounds}"
        )
    _report_gap_coverage("capture pour", unary_union(pour_geometries), centers)

    for label, center in centers.items():
        nearby: list[BaseGeometry] = []
        for trace, copper in coppers:
            g = _shape_geometry(copper.shape, trace.transform)
            if g.distance(Point(center)) <= PAD_INSPECTION_RADIUS:
                nearby.append(g)
        print(f"capture copper near {label} at {center}: {len(nearby)} shape(s)")

    if raw_layout is None:
        print("raw LayoutOutput: unavailable")
    else:
        print(f"raw LayoutOutput pours: {len(raw_layout.pours)}")
        raw_pour_geometries: list[BaseGeometry] = []
        for index, pour in enumerate(raw_layout.pours):
            raw_pour_geometries.append(_proto_polygon_set(pour.computed_shape))
            print(
                f"raw pour[{index}]: input={pour.input_shape.WhichOneof('shape')} "
                f"computed-components={len(pour.computed_shape.components)} "
                f"computed-holes={sum(len(c.inners) for c in pour.computed_shape.components)}"
            )
        _report_gap_coverage(
            "raw computed pour", unary_union(raw_pour_geometries), centers
        )

    derived = [
        cast(Any, route).derived
        for _, route in visit(rd.root, jitx.circuit.Route)
        if cast(Any, route).derived
    ]
    print(f"Route.derived pour/feature groups: {len(derived)}")


def _nearby_odb_records(
    paths: Iterable[Path], centers: dict[str, tuple[float, float]]
) -> None:
    found = False
    for path in paths:
        text = path.read_text(errors="replace")
        if "UNITS=MM" not in text:
            continue
        lines = text.splitlines()
        nearby: dict[str, list[str]] = {label: [] for label in centers}
        for line in lines:
            values: list[float] = []
            for token in line.replace(",", " ").split():
                try:
                    values.append(float(token))
                except ValueError:
                    continue
            for label, (x, y) in centers.items():
                if any(
                    abs(values[i] - x) <= PAD_INSPECTION_RADIUS
                    and abs(values[i + 1] - y) <= PAD_INSPECTION_RADIUS
                    for i in range(len(values) - 1)
                ):
                    nearby[label].append(line)
        if any(nearby.values()):
            found = True
            print(f"ODB features: {path}")
            for label, records in nearby.items():
                print(f"  {label}: {len(records)} nearby record(s)")
                for record in records:
                    print(f"    {record}")
    if not found:
        print("ODB features: no millimeter feature records found near the pads")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate", choices=("no-effect", "wide-spoke"), default="no-effect"
    )
    parser.add_argument("--odb-root", type=Path)
    args = parser.parse_args()
    design = (
        DirectConnectNoEffectDesign
        if args.candidate == "no-effect"
        else DirectConnectWideSpokeDesign
    )

    raw: dict[str, Any] = {}
    Capture = cast(Any, import_module("jitx._translate.reverse_flow.linker")).Capture

    original_run = Capture.run

    def recording_run(self: Any) -> None:
        raw["layout"] = self._layout
        original_run(self)

    Capture.run = recording_run
    try:
        with cast(Any, jitx).runtime as runtime:
            rd = runtime.submit(design)
            rd.capture()
    finally:
        Capture.run = original_run

    _capture_summary(rd, raw.get("layout"))
    if args.odb_root is not None:
        centers = _pad_centers(rd.root)
        _nearby_odb_records(args.odb_root.rglob("features"), centers)


if __name__ == "__main__":
    main()
