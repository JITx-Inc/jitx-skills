"""Build a soldermask-defined thermal pad and its explicit via field.

Copy this module into the JITX project that owns the component. The landpattern
call site uses :func:`grid_thermal_via_positions` and
:func:`soldermask_defined_thermal_pad_config`. The circuit call site stores a
:class:`ThermalViaField` as a structural attribute and adds each via to the pad's
net. Containers participate in structural traversal at ``jitx/container.py:27``.

The module deliberately ships no via definition. Pass a class supplied by the
substrate or the fabrication library. If the same class is used with
``design_constraint(...).stitch_via(...)``, it must be declared where the rule
resolver can find it. See ``jitx-layout-constraints/SKILL.md``, "Why a rule did
not fire", item 8. The rule API accepts a via class at
``jitx/constraints.py:924``, and substrate via classes are collected at
``jitx/_translate/board.py:215``.

Fabrication values come from :class:`FabricationConstraints`, whose relevant
fields are declared at ``jitx/substrate.py:173``, ``jitx/substrate.py:198``, and
``jitx/substrate.py:202``. A via's pad diameter is its ``diameter`` field at
``jitx/via.py:60``. The geometry functions take plain numbers so they can be
tested without a JITX runtime.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Self

from jitx import Container
from jitx.shapes import Shape
from jitx.substrate import FabricationConstraints
from jitx.via import Via, ViaDiameter
from jitxlib.landpatterns.pads import SMDPadConfig

_COORDINATE_DIGITS = 6  # skill default: 6 decimal places when grouping grid axes.
_CIRCLE_RESOLUTION = 24  # skill default: 24 segments per quadrant for mask dams.


@dataclass(frozen=True)
class StitchParams:
    """Plain-number inputs derived from a substrate and a via class."""

    min_mask_bridge: float
    mask_expansion: float
    edge_margin: float
    via_pad_diameter: float
    fillet_radius: float = 0.0  # skill default: 0.0 mm disables cell filleting.

    @classmethod
    def from_substrate(
        cls,
        constraints: FabricationConstraints,
        via_cls: type[Via],
        *,
        fillet_radius: float = 0.0,  # skill default: 0.0 mm disables filleting.
    ) -> Self:
        """Read stitch geometry from fabrication constraints and ``via_cls``.

        ``min_soldermask_bridge`` supplies web width,
        ``solder_mask_registration`` supplies radial mask overlap around each
        tented via, and ``min_copper_edge_space`` supplies the via-pad rim inset.
        These fields are documented at ``jitx/substrate.py:173``,
        ``jitx/substrate.py:198``, and ``jitx/substrate.py:202``.
        ``Via.diameter`` may be a float or a :class:`ViaDiameter`; the latter
        exposes its pad size as ``pad`` at ``jitx/via.py:309``.
        """

        diameter = via_cls.diameter
        if isinstance(diameter, ViaDiameter):
            diameter = diameter.pad
        return cls(
            min_mask_bridge=float(constraints.min_soldermask_bridge),
            mask_expansion=float(constraints.solder_mask_registration),
            edge_margin=float(constraints.min_copper_edge_space),
            via_pad_diameter=float(diameter),
            fillet_radius=float(fillet_radius),
        )


def grid_thermal_via_positions(
    *,
    ep_size: tuple[float, float],
    via_grid: tuple[int, int],
    edge_margin: float,
    via_pad_diameter: float,
) -> list[tuple[float, float]]:
    """Return an evenly spaced columns-by-rows grid in the EP-local frame.

    The outermost via pad rim stays ``edge_margin`` from each exposed-pad edge.
    ``edge_margin`` normally comes from
    ``FabricationConstraints.min_copper_edge_space`` and ``via_pad_diameter``
    from the selected via class through :meth:`StitchParams.from_substrate`.
    """

    nx, ny = via_grid
    ep_w, ep_h = ep_size
    inset = edge_margin + via_pad_diameter / 2.0

    def axis_positions(extent: float, count: int) -> list[float]:
        if count <= 0:
            return []
        available = extent - 2.0 * inset
        if available < 0:
            raise ValueError(
                f"EP extent {extent} mm is too small for {count} vias with "
                f"a {inset} mm center inset on each side"
            )
        if count == 1:
            return [0.0]
        step = available / (count - 1)
        return [-available / 2.0 + index * step for index in range(count)]

    xs = axis_positions(ep_w, nx)
    ys = axis_positions(ep_h, ny)
    return [(x, y) for y in ys for x in xs]


def soldermask_thermal_pad_opening(
    *,
    ep_size: tuple[float, float],
    via_positions: Iterable[tuple[float, float]],
    via_pad_diameter: float,
    min_mask_bridge: float,
    mask_expansion: float,
    fillet_radius: float = 0.0,  # skill default: 0.0 mm disables cell filleting.
) -> Shape:
    """Return the paste and soldermask opening around tented thermal vias.

    The removed mask region is the union of a perimeter frame, linear webs, and
    circular via dams. Webs use ``min_mask_bridge``. Each dam extends
    ``mask_expansion`` beyond the via pad rim. Pass values built by
    :meth:`StitchParams.from_substrate`.

    Shapely is optional in the JITX package, so it is imported only here. The
    result is checked before it reaches a fabrication feature because
    ``ShapelyGeometry`` serializes only polygonal geometry
    (``jitx/shapes/shapely.py:64``).
    """

    try:
        import shapely
        import shapely.geometry.base
        from jitx.shapes.shapely import ShapelyGeometry
    except ImportError as exc:
        raise ImportError(
            "thermal_via_stitch requires the optional 'shapely' package to "
            "build soldermask and paste openings"
        ) from exc

    ep_w, ep_h = ep_size
    ep_rect = shapely.box(-ep_w / 2.0, -ep_h / 2.0, ep_w / 2.0, ep_h / 2.0)
    positions = list(via_positions)
    mask_parts: list[shapely.geometry.base.BaseGeometry] = []

    if positions:
        half_web = min_mask_bridge / 2.0
        unique_xs = sorted({round(x, _COORDINATE_DIGITS) for x, _ in positions})
        unique_ys = sorted({round(y, _COORDINATE_DIGITS) for _, y in positions})

        inner_w = ep_w - 2.0 * min_mask_bridge
        inner_h = ep_h - 2.0 * min_mask_bridge
        if inner_w > 0 and inner_h > 0:
            inner = shapely.box(
                -inner_w / 2.0,
                -inner_h / 2.0,
                inner_w / 2.0,
                inner_h / 2.0,
            )
            mask_parts.append(ep_rect.difference(inner))

        for x in unique_xs:
            mask_parts.append(
                shapely.box(
                    x - half_web,
                    -ep_h / 2.0,
                    x + half_web,
                    ep_h / 2.0,
                )
            )
        for y in unique_ys:
            mask_parts.append(
                shapely.box(
                    -ep_w / 2.0,
                    y - half_web,
                    ep_w / 2.0,
                    y + half_web,
                )
            )

        dam_radius = via_pad_diameter / 2.0 + mask_expansion
        for x, y in positions:
            mask_parts.append(
                shapely.Point(x, y).buffer(
                    dam_radius,
                    quad_segs=_CIRCLE_RESOLUTION,
                )
            )

    opening = (
        ep_rect.difference(shapely.unary_union(mask_parts)) if mask_parts else ep_rect
    )
    if fillet_radius > 0:
        opening = opening.buffer(
            -fillet_radius,
            quad_segs=_CIRCLE_RESOLUTION,
        ).buffer(
            fillet_radius,
            quad_segs=_CIRCLE_RESOLUTION,
        )

    if opening.is_empty or opening.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError(
            "thermal-pad opening must be a non-empty Polygon or MultiPolygon; "
            f"got {opening.geom_type}"
        )
    return ShapelyGeometry(opening)


def soldermask_defined_thermal_pad_config(
    *,
    ep_size: tuple[float, float],
    via_positions: Iterable[tuple[float, float]],
    via_pad_diameter: float,
    min_mask_bridge: float,
    mask_expansion: float,
    fillet_radius: float = 0.0,  # skill default: 0.0 mm disables cell filleting.
) -> SMDPadConfig:
    """Use one validated CSG opening for both paste and soldermask.

    Both fields accept a ``Shape`` at ``jitxlib/landpatterns/pads.py:372``.
    """

    opening = soldermask_thermal_pad_opening(
        ep_size=ep_size,
        via_positions=via_positions,
        via_pad_diameter=via_pad_diameter,
        min_mask_bridge=min_mask_bridge,
        mask_expansion=mask_expansion,
        fillet_radius=fillet_radius,
    )
    return SMDPadConfig(soldermask=opening, paste=opening)


class ThermalViaField(Container):
    """Structural collection of placed thermal vias.

    Store this container on the circuit and add every member of ``vias`` to the
    thermal-pad net. Plain power and ground membership uses ``Net += via``
    (``jitx/net.py:748``), not ``PortAttachment``.
    """

    def __init__(
        self,
        *,
        positions: Sequence[tuple[float, float]],
        via_class: type[Via],
        anchor: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        ax, ay = anchor
        self.vias = [via_class().at(ax + dx, ay + dy) for dx, dy in positions]
