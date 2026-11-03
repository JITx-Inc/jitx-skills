"""Stitch-via measurement shared by the stitch cases.

The derived count follows the spike's S3 findings on jitx 4.6.0:

- sites sit on the square grid at multiples of the pitch from (0, 0), not
  from the pour;
- a site is kept when the via pad, grown by the pattern's inset, lies inside
  the pour's computed copper (whose outline already includes its pullback from
  other-net objects); the measured keep/drop windows matched this within 0.01.

A site within ``SLACK`` of a threshold is not required.
"""

from __future__ import annotations

import math
from typing import Any

import shapely
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep

from jitx.constraints import SquareViaStitchGrid, UnaryDesignConstraint

import lc_check as L

SLACK = 0.02


def stitch_rules(rd: Any) -> list[UnaryDesignConstraint]:
    return [
        c
        for c in L.rules(rd.root)
        if isinstance(c, UnaryDesignConstraint) and c.stitch_via_constraint is not None
    ]


def via_pad_radius(definition: Any) -> float:
    d = definition.diameter
    return float(getattr(d, "diameter", d)) / 2


def required_sites(
    pours: list[BaseGeometry],
    pads: list[BaseGeometry],
    pitch: float,
    inset: float,
    pad_r: float,
    pad_space: float,
    placed: list[tuple[float, float]],
    min_centre: float,
) -> list[tuple[float, float]]:
    """Grid sites a through-via stitch rule over pours must fill.

    A site is required when the via pad grown by the inset lies inside the
    computed copper of every pour (spike S3's inset rule, applied on each layer
    the through via crosses), and the via pad stays pad_space clear of every
    pad. The pad condition is this suite's own measurement, not the spike's: on
    the stitch-ground-pours solution (4 layers, pitch 2.0, inset 0.5,
    2026-11-03) the four sites over the U.FL ground pads and the inductor pads
    were dropped on every layer although the inner pours accepted them, and
    every other site that met the inset rule on all four layers was kept.
    A site within ``min_centre`` of a via the design places in code is not
    required either: on the stitch-pitch-too-small solution (pitch 0.5) the
    ten sites 0.5 or closer to the two feed anchors were dropped, and the fab
    sheet forbids drills closer than row 12 + row 15 = 0.500 centre to centre.
    """
    if not pours or any(p.is_empty for p in pours):
        return []
    inner = [prep(p.buffer(-(inset + pad_r + SLACK))) for p in pours]
    pad_zone = prep(shapely.union_all([p.buffer(pad_r + pad_space + SLACK) for p in pads])) if pads else None
    bounds = shapely.intersection_all(pours).bounds
    out = []
    for x, y in L.grid_sites(bounds, pitch):
        pt = Point(x, y)
        near_via = any(math.dist((x, y), v) < min_centre + SLACK for v in placed)
        if all(i.contains(pt) for i in inner) and not (pad_zone and pad_zone.contains(pt)) and not near_via:
            out.append((x, y))
    return out


def realized_in(pour: BaseGeometry, vias: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pp = prep(pour.buffer(1e-6))
    return [v for v in vias if pp.contains(Point(v))]


def on_grid(v: tuple[float, float], pitch: float) -> bool:
    return all(abs(c / pitch - round(c / pitch)) < 1e-3 for c in v)


def square_patterns(rules: list[UnaryDesignConstraint]) -> list[tuple[float, float, float]]:
    """(pitch, inset, pad radius) per stitch rule; a non-square pattern fails."""
    out = []
    for r in rules:
        sv = r.stitch_via_constraint
        assert sv is not None
        if not isinstance(sv.pattern, SquareViaStitchGrid):
            L.fail(f"stitch rule {r!r} uses {type(sv.pattern).__name__}; the prompt asks for a square grid")
            continue
        out.append((float(sv.pattern.pitch), float(sv.pattern.inset), via_pad_radius(sv.definition)))
    return out
