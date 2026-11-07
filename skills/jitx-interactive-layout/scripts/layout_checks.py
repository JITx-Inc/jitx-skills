"""Measure layout quality in a design held by `jitx design session`.

Run against a running session, from the project root:

    jitx design exec <module.path.DesignClass> <this file>

It reads ``.jitx/interactive-layout/checks-config.json`` (optional) in the
directory the session was started in, writes ``checks.json`` beside it and
returns a short summary. Millimetres and mm^2, board-absolute. Keys are the
ones ``layout_report.py`` writes: a pad (``reg.buck.landpattern.p.3``) or a
component (``reg.buck``). Every config key is optional:

    {
      "scope": ["reg", "j_pwr"],
      "ratio_limit": 1.5,
      "neck_down_mm": 1.0,
      "si_nets": ["MDI.*", "DDR_DQ0"],
      "power": {"VIN": 0.5, "GND": 0.5},
      "current_a": 2.0,
      "max_drop_mv": 50,
      "max_l_nh": 5.0,
      "power_paths": [{"net": "VIN", "from": "j_pwr.j", "to": "reg.buck",
                       "require_pour": true, "current_a": 1.5}],
      "grid_mm": 0.05,
      "window_mm": 3.0,
      "max_cells": 1000000,
      "plane_layers": [1, 4],
      "copper_mm": {"0": 0.035},
      "via_plating_mm": 0.020,
      "loop_target_mm2": 2.0,
      "loops": [{"cap": "reg.input_caps.0", "ic": "reg.buck",
                 "target_mm2": 2.0}],
      "decap_via_reach_mm": 2.0,
      "via_reach_mm": 2.0,
      "overhang": {"j_pwr.j": "edge connector, overhangs by design"}
    }

``si_nets`` names the nets under a skew or length-matching constraint, read
from the source (an entry ending in ``*`` is a name prefix). ``power`` maps
net names to the rule width read from the source (the script cannot read
rules or constraints). A path's ``net`` can be left out only when ``from``
has pads on one net. ``current_a``, ``max_drop_mv``, ``max_l_nh``,
``grid_mm`` and ``window_mm`` can also be set on one path.
``loop_target_mm2`` is the target for loops that give none.

Decoupling vias (``decap_vias``). For every capacitor (a component with a
``capacitance``) whose two pads each
have a plane via of their own net, in the pad or one route away (within
``decap_via_reach_mm``; a power or ground route that comes back as polygon
copper counts by its via's centre distance), where each via sits against its pad:
``in_pad``, ``side``, ``end`` (past the pad's outer end) or ``between``
(towards the other pad), and ``via_gap``, the distance between the nearest
via of each pad. A via past the end moves the two vias apart by the
capacitor's length and adds loop inductance. ``met`` is true when no via is
at an end or between and the nearest pair are on the same side.

``scope`` lists component keys. When it is set, circuitousness,
``narrower_than_rule``, ``loops``, ``decap_vias``, ``vias``,
``connectivity`` and ``sanity`` cover only what has an end on a component
in it (the component, or a pad whose key starts with it): a connection by
its two ends, a trace by the connection it is part of, a loop by its
``cap``, ``ic`` or ``pads``, a net by its pads, a courtyard by its
component (an overlap when either component is in scope), and a via by
the connection it is on or the pad it sits against. Power paths name
their own ends and are not scoped. The output gives the scope it used.

Circuitousness. A connection is a chain of routed traces on one net from a
pad to a pad, through vias, control points and trace joins that each have
exactly two links of that net. A link is a trace, or same-net copper that
overlaps with no trace between (a via against its pad), which counts its
centre-to-centre distance; a trace ending on a pad with a via in it ends
at the pad. A chain also ends at a via, control point or join with one
link or more than two (a plane via, a branch); one in a pad is named by
the pad, with end kind ``via_in_pad``, and measured from the via. Routed
length is the sum of the links on the board plane: a via or layer change
adds no length, and ``vias`` counts the vias passed. Distance is the
straight line between the centres of the two ends; ``ratio`` is length
over distance. A ratio a little under 1 means the traces end at pad
edges. Ends closer than 0.1 mm get no ratio. Every other connection over
``ratio_limit`` is listed in ``worst``, short ones included, except on
``si_nets``: those are listed under ``si_nets``, with no limit and out of
``max`` and ``median``. Each trace of a pair route counts on its own net,
through the pair insertions.
A chain that ends at a bare trace end (a ``join`` with one trace) and a
route whose copper comes back as a polygon are listed under
``unmeasured``. A chain that ends where bare trace ends branch (a ``join``
with three or more) is measured like any other.

Power width, per net named in ``power``: ``narrower_than_rule`` lists
every trace narrower than the rule, with its layer, and ``met`` is false
when any of them is not a step-down (``step_down``: no longer than
``neck_down_mm``, with an end in a pad whose narrow side is under the
rule, or in a via in such a pad). The list holds traces only, so a pour's
thermal spokes never enter it. Route copper that comes back as a polygon
is not width-checked; it is listed by net under ``cannot_measure``.

Power paths. Each ``power_paths`` entry finds the shortest copper path
from a source pad to a load pad, through traces, vias, overlapping copper
and pours. ``trace_hops`` and ``trace_length`` count its trace legs,
polygon route copper included (its length is the straight distance
between its ends). A step-down leg, as above, is not counted. With
``require_pour`` any counted leg fails the path.

IR drop and inductance, estimates. For each path, the DC resistance and
the inductance from all the ``from`` pads (held at one potential) to all
the ``to`` pads, solved on the net's copper inside a window ``window_mm``
around the path: trace copper at its width, pour fills, polygon route
copper, pads, vias and plated holes, on every layer the net uses. A
through-hole pad's copper on a layer is its ``shapes`` entry for that
layer, else its ``shape``. Each layer is a grid of ``grid_mm`` cells;
neighbour cells join through the copper in the cell-sized box centred on
the face between them, in proportion to how much of the box it covers.
Thermal spokes, necks, traces and pours all come out of the one solve,
and none is classified. Sheet resistance is resistivity (annealed copper
at 20 C, IEC 60028: 1/58 ohm mm^2/m) over the layer's copper thickness,
from the substrate or ``copper_mm``. A via or plated hole joins
consecutive layers through its wall, ``via_plating_mm`` thick (default
0.020 mm, the IPC-6012 Class 2 minimum average, so an estimate), over the
distance between the layers' middles. ``drop_mv`` is the resistance times
``current_a``, and ``within_budget`` compares it with ``max_drop_mv``.

``l_nh`` is the same network solved again with sheet inductance in place
of sheet resistance. A layer's sheet inductance is mu0 h per square, h
the dielectric between it and the nearest plane layer: the parallel-plate
inductance of a wide strip over a plane, L = mu0 h l / w. With a plane on
each side the two returns are in parallel, mu0 h1 h2 / (h1 + h2), as for
a wide stripline. Plane layers are the layers where pour fills, on any
net, cover at least half the board, or the layer indices in
``plane_layers`` (TOP is 0); ``power.planes`` gives the ones used and
``ir.sheet_nh`` each layer's value. A via or plated hole adds the partial
self-inductance of a thin tube its length, at the radius to the middle of
its wall: mu0/(2 pi) (l ln((l + sqrt(l^2 + r^2))/r) - sqrt(l^2 + r^2) +
r), the form for straight conductors in Inductance Calculations (1946). It
is spread along the hole by length, so a via that carries current only
part of its length reads somewhat high. ``l_within_budget`` compares
``l_nh`` with ``max_l_nh``. The estimate assumes the return current runs
in the nearest plane straight under the copper, and leaves out mutual
inductance between hops or nets, capacitor ESL and package inductance. It
is quasi-static: a rough figure for comparing layouts, not a sign-off
number. When a layer the net uses has no plane to return in, ``l_nh`` is
null with a reason.

Left out of both: temperature rise, frequency, contact resistance, pads
removed as non-functional on inner layers (an inner layer reads the full
pad), and copper outside the window (a plane spreading past it reads a
little high).

Accuracy, from closed-form checks (a straight trace, R = rho l / (w t);
four thermal spokes across a gap, each rho g / (w t); a wide strip over a
plane, L = mu0 h l / w). On the default 0.05 mm grid a trace or strip
along the grid reads exact, aligned spokes exact and off-grid spokes 3%
low. A diagonal trace reads high: by up to 10% for a 0.15 mm trace at 45
degrees, 4% for 0.125 mm at 30 degrees and 2% for 0.5 mm at 45 degrees;
a 0.5 mm strip at 30 degrees reads under 1% high in L. On a 0.1 mm grid
the same diagonals read up to 13% high, and thermal spokes or gaps under
two cells wide up to a third low.

``ir.solves`` gives each solve (``r``, ``l``) its ``iterations``,
``converged`` (the conjugate-gradient residual fell below 1e-9 of the
driving terms within 50,000 iterations) and ``balance``, the current into
the loads over the current out of the sources: 1 in a sound solve. When a
solve did not converge or its balance is off 1 by more than 0.01, its
budget comparison is null and ``ir.reasons`` says why.

Cost. Each solve runs in numpy, and its time grows faster than its cell
count. On an 80 by 80 mm, 18-layer board at 0.05 mm, a path through an
inner plane (530,000 cells) took 40 to 43 s for each of R and L over two
runs, and a path on TOP with a few vias (68,000 cells) under 0.1 s for
both. The plane path
on a 0.1 mm grid (134,000 cells) took 9 s for both and read R and L
within 4% of the 0.05 mm figures. A window over ``max_cells`` copper
cells (default 1,000,000) is refused with an error that says how to
change it.

``met`` is false when ``require_pour`` fails or a budget given
(``max_drop_mv``, ``max_l_nh``) is exceeded, true when every check asked
for passes, and null when none was asked or one is unknown.

Hot loop, for an input or decoupling capacitor straight across two pins of
one IC, the pins on the capacitor's two nets: the area enclosed by the
copper path from the capacitor's first pad to the IC pin on its net,
through the IC to its other pin, back to the second pad and through the
capacitor. Those two closing segments are straight lines through the parts
themselves. With ``ic`` the pins are the IC's pads on the capacitor's two
nets nearest each capacitor pad; ``pads`` names them instead, as
``[cap_a, ic_a, ic_b, cap_b]``, ``ic_a`` on the net of ``cap_a``. A loop
is refused with an error when the capacitor's pads are not on two nets
with an IC pin on each. That test cannot tell an input or decoupling
capacitor from an output capacitor on a regulator with a pin on its
output net (a sense or feedback pin such as VOUT or VOS): that loop is
measured through the pin, and is not the switching loop. The path is the
shortest through traces, vias, overlapping copper and pours; a hop
through a pour or plane, or across overlapping copper, is the straight
line between the two centres. The area is the projection on the board
plane: the via height down to a plane and back is not in it.

Via plan (``vias``). Every pad-to-pad connection, a circuitousness chain
whose two ends are pads or vias in pads, gets 0, 1 or 2 vias, each next to
an end pad. Its vias are those the chain passes, and a via in a pad at an
end. Per via: ``from_end``, its distance along the chain to the nearer end
(the sum of its links, 0 for a via in the end pad); ``far_from_end`` when
that is over ``via_reach_mm``; and ``redundant`` when the nearer end's pad
reaches the layer of the first trace on the via's far side, so the pad
could have made the layer change itself. A through-hole pad reaches every
layer, an SMD pad only its own side: a through-hole connector pad routed
on TOP to a via and then on an inner layer is redundant. A connection
fails with more than two vias or any via far from its end or redundant;
``met`` is true when none fails. ``failing`` lists those that do. A chain
that ends at a plane via, a branch, a control point or a bare trace end
is not pad-to-pad; it is counted under ``not_pad_to_pad`` and not judged.

Two faults are checked on every via in scope, on a pad-to-pad connection
or not. ``dangling`` lists vias whose copper (route traces, pour fills,
polygon route copper, pads they overlap) touches them on fewer than two
layers, with the layers it does touch: a via that changes no layer. A
stitch via between two pour layers counts as joined. ``via_in_pad`` lists
vias whose copper overlaps a pad's copper, of any net, on a layer both
are on, when the via's definition has ``via_in_pad`` false; a definition
without the attribute counts as false. With a scope, a via there counts
when it is in scope or the pad is. ``met`` is false when either list has
an entry.

Connectivity. For each net with two or more pads, the number of groups
its placed pads fall into when joined by realized copper: route traces,
overlapping copper, and each pour fill or polygon route piece, which joins
every pad and via it touches. A via or through-hole pad is one node on all
its layers, so pieces on different layers join through it. A split net
lists the pad keys of each group. Pads of unplaced components are left
out and listed under ``unchecked_pads``; a net with fewer than two placed
pads is ``unchecked``. A net with a pour whose fill has not come back is
``unknown``, with no verdict. ``met`` is true when every checked net is
one group.

Sanity. ``off_board`` lists components whose courtyard is not inside the
board outline, with the area outside; a component named in ``overhang``
(component key to the reason the user or the design gives) is listed with
its reason and does not fail. ``courtyard_overlaps`` lists placed
components on the same side whose courtyards overlap, with the area.
``vias_outside_board`` lists vias whose copper is not inside the outline.
``met`` is true when nothing fails.

Pours whose fill has not come back hold their requested outline, not
copper: they are left out of every path and listed under
``cannot_measure``. What the script cannot read is listed there or as a
reason on the entry, not guessed.
"""

from __future__ import annotations

import heapq
import itertools
import json
import math
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import shapely
from jitx.circuit import Route
from jitx.component import Component
from jitx.controlpoint import ControlPoint
from jitx.copper import Pour
from jitx.feature import Courtyard, Cutout
from jitx.inspect import decompose, extract
from jitx.landpattern import Pad, PadShape
from jitx.layerindex import Side
from jitx.proxy import typeof
from jitx.shapes.primitive import Arc, ArcPolyline, Polyline, discretize
from jitx.stackup import Conductor, Material
from jitx.via import Via
from shapely.geometry import LineString, MultiPolygon, box
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union
from shapely.prepared import prep

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout_report import (  # noqa: E402, RUF100
    LIST_LIMIT,
    OUT_DIR,
    _Keys,
    _owner,
    _pieces,
    _write,
)

CONFIG = "checks-config.json"
DEFAULTS: dict[str, Any] = {
    "ratio_limit": 1.5,
    "neck_down_mm": 1.0,
    "grid_mm": 0.05,
    "window_mm": 3.0,
    "max_cells": 1_000_000,
    # IPC-6012, Class 2: minimum average copper plating in holes, 20 um.
    "via_plating_mm": 0.020,
    "via_reach_mm": 2.0,
}
MIN_DISTANCE = 0.1
END_TOLERANCE = 0.02
END_SNAP = 0.5
CONTROL_RADIUS = 0.3
# Annealed copper at 20 C, IEC 60028: 1/58 ohm mm^2/m, in ohm mm.
RHO_CU = 1 / 58 * 1e-3
# Vacuum permeability, 4 pi 1e-7 H/m, in nH/mm.
MU0 = 4 * math.pi * 1e-4 * 1e3
SUPERSAMPLE = 4
CG_TOL = 1e-9
CG_MAX = 50_000
# A solve whose current out of the sources and into the loads differ by
# more than this fraction is not trusted.
BALANCE_TOL = 0.01
# A layer counts as a plane when pour fills cover this share of the board.
PLANE_SHARE = 0.5

XY = tuple[float, float]


@dataclass
class _Node:
    key: str
    kind: str
    pos: XY
    nets: set[int]
    layers: frozenset[int]
    shape: BaseGeometry
    narrow: float | None = None
    owner: str = ""
    hole: float | None = None
    per_layer: dict[int, BaseGeometry] = field(default_factory=dict)
    definition: str = ""
    via_in_pad: bool = False

    def on(self, layer: int) -> BaseGeometry:
        """The node's copper on ``layer``."""
        return self.per_layer.get(layer, self.shape)


@dataclass
class _Edge:
    a: int
    b: int
    net: int
    layer: int
    route: str
    length: float
    width: float
    points: list[XY]


@dataclass
class _Piece:
    net: int
    layer: int
    key: str
    geom: BaseGeometry
    nodes: list[int] = field(default_factory=list)
    route: str = ""


def _dist(p: XY, q: XY) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _arc_end(arc: Arc, angle: float) -> XY:
    cx, cy = arc.center
    a = math.radians(angle)
    return (cx + arc.radius * math.cos(a), cy + arc.radius * math.sin(a))


def _length(elements: Any) -> float:
    """Centreline length of a polyline of points and arcs, arcs exact."""
    total, prev = 0.0, None
    for e in elements:
        if isinstance(e, Arc):
            start, end = _arc_end(e, e.start), _arc_end(e, e.start + e.arc)
            total += (_dist(prev, start) if prev else 0.0) + e.radius * abs(
                math.radians(e.arc)
            )
            prev = end
        else:
            point = (float(e[0]), float(e[1]))
            total += _dist(prev, point) if prev else 0.0
            prev = point
    return total


def _polys(geom: BaseGeometry) -> list[ShapelyPolygon]:
    if isinstance(geom, ShapelyPolygon):
        return [] if geom.is_empty else [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, ShapelyPolygon)]


def _r(v: float) -> float:
    return round(v, 3)


class _Model:
    """Pads, vias and control points as nodes; route traces as edges; pour
    fills and polygon route copper as pieces."""

    def __init__(self, rd: Any) -> None:
        self.rd = rd
        self.key = _Keys(rd)
        self.count = len(rd.root.substrate.stackup.conductors)
        self.nodes: list[_Node] = []
        self.edges: list[_Edge] = []
        self.pieces: list[_Piece] = []
        self.labels: dict[int, str] = {}
        self.unmeasured: list[dict[str, Any]] = []
        self.fill_unknown: list[str] = []
        self.free: dict[tuple[int, int, float, float], int] = {}
        self.contacts: dict[int, list[int]] = {}
        self._nodes()
        self._contacts()
        self._pieces()
        self._edges()

    def net(self, obj: object) -> int | None:
        net = self.rd.nets.find(obj)
        if net is None:
            return None
        self.labels.setdefault(id(net), net.name or "")
        return id(net)

    def label(self, net: int) -> str:
        return self.labels.get(net) or f"unnamed net {net}"

    def _add(self, node: _Node) -> None:
        self.nodes.append(node)

    def _nodes(self) -> None:
        rd, key = self.rd, self.key
        comps: dict[str, Side | None] = {}
        for trace, comp in rd.query(Component):
            if comp.transform is None or trace.transform is None:
                comps[key(trace)] = None
                continue
            xf = trace.transform * comp.transform
            comps[key(trace)] = getattr(xf, "side", Side.Top)
        unplaced = [k for k, side in comps.items() if side is None]
        everything = frozenset(range(self.count))
        owners = sorted(comps, key=len, reverse=True)
        for trace, pad in rd.query(Pad):
            k = key(trace)
            owner = next((c for c in owners if k.startswith(c + ".")), None)
            side = comps.get(owner) if owner else None
            if side is None or trace.transform is None:
                continue
            xf = trace.transform * pad.transform if pad.transform else trace.transform
            base = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
            outline = (xf * base).to_shapely().g
            rect = outline.minimum_rotated_rectangle
            ring: list[XY] = (
                [(float(x), float(y)) for x, y in rect.exterior.coords]
                if isinstance(rect, ShapelyPolygon)
                else []
            )
            sides = [_dist(ring[i], ring[i + 1]) for i in range(min(2, len(ring) - 1))]
            cuts = list(extract(pad, Cutout))
            layers = (
                everything
                if cuts
                else frozenset({self.count - 1 if side == Side.Bottom else 0})
            )
            hole = None
            per_layer: dict[int, BaseGeometry] = {}
            if cuts:
                x0, y0, x1, y1 = cuts[0].shape.to_shapely().g.bounds
                hole = min(x1 - x0, y1 - y0)
                # A through-hole pad's own shape on given layers.
                for at, shp in (pad.shapes or {}).items():
                    geo = shp.shape if isinstance(shp, PadShape) else shp
                    for layer in at if isinstance(at, tuple) else (at,):
                        lay = rd.layers.normalize(layer)
                        per_layer[lay] = (xf * geo).to_shapely().g
            pos = xf.translation
            net = self.net(pad)
            self._add(
                _Node(
                    k,
                    "pad",
                    (float(pos[0]), float(pos[1])),
                    set() if net is None else {net},
                    layers,
                    outline,
                    min(sides) if sides else None,
                    owner or "",
                    hole,
                    per_layer,
                )
            )
        component_keys = list(comps)
        for trace, via in rd.query(Via):
            if trace.transform is None or via.transform is None:
                continue
            k = key(trace)
            owner = _owner(k, component_keys)
            if owner and any(c.startswith(owner) for c in unplaced):
                continue
            pos = (trace.transform * via.transform).translation
            diameter = via.diameter
            d = diameter if isinstance(diameter, float | int) else diameter.pad
            lo, hi = sorted(
                rd.layers.normalize(n) for n in (via.start_layer, via.stop_layer)
            )
            net = self.net(via)
            xy = (float(pos[0]), float(pos[1]))
            self._add(
                _Node(
                    k,
                    "via",
                    xy,
                    set() if net is None else {net},
                    frozenset(range(lo, hi + 1)),
                    ShapelyPoint(xy).buffer(d / 2),
                    hole=float(via.hole_diameter),
                    definition=typeof(via).name or typeof(via).__name__,
                    # A definition that does not say allows no via in a pad.
                    via_in_pad=bool(getattr(typeof(via), "via_in_pad", False)),
                )
            )
        for trace, cp in rd.query(ControlPoint):
            if trace.transform is None or cp.transform is None:
                continue
            xf = trace.transform * cp.transform
            pos = xf.translation
            xy = (float(pos[0]), float(pos[1]))
            nets = {self.net(cp)}
            shapes: list[BaseGeometry] = []
            for t in cp.traces or []:
                nets.add(self.net(t))
                shapes += [(xf * s).to_shapely().g for s in t.shapes]
            self._add(
                _Node(
                    self.key(trace),
                    "control",
                    xy,
                    {n for n in nets if n is not None},
                    frozenset({rd.layers.normalize(cp.layer)}),
                    unary_union(shapes)
                    if shapes
                    else ShapelyPoint(xy).buffer(CONTROL_RADIUS),
                )
            )

    def _contacts(self) -> None:
        """Same-net nodes whose copper overlaps on a shared layer, such as a
        via placed against its pad with no route."""
        for i, a in enumerate(self.nodes):
            for j in range(i + 1, len(self.nodes)):
                b = self.nodes[j]
                if (
                    a.nets & b.nets
                    and a.layers & b.layers
                    and a.shape.distance(b.shape) <= END_TOLERANCE
                ):
                    self.contacts.setdefault(i, []).append(j)
                    self.contacts.setdefault(j, []).append(i)

    def _pieces(self) -> None:
        """Pour fills. A pour whose fill has not come back holds its
        requested outline, not copper: it is left out and listed."""
        for trace, pour in self.rd.query(Pour):
            shape = pour.shape
            net = self.net(pour)
            if net is None or trace.transform is None:
                continue
            count = _pieces(shape)
            if count is None:
                self.fill_unknown.append(self.key(trace))
            if not count:
                continue
            fill = (trace.transform * shape).to_shapely().g
            layer = self.rd.layers.normalize(pour.layer)
            for poly in _polys(fill):
                self.pieces.append(_Piece(net, layer, self.key(trace), poly))
        self._touch()

    def _touch(self) -> None:
        for p in self.pieces:
            p.nodes.clear()
            area = prep(p.geom.buffer(END_TOLERANCE))
            p.nodes.extend(
                i
                for i, n in enumerate(self.nodes)
                if p.net in n.nets and p.layer in n.layers and area.intersects(n.shape)
            )

    def _end(self, point: XY, layer: int, net: int) -> int:
        """The node a trace end attaches to: one whose copper holds the point,
        else the nearest centre within END_SNAP, else a join of bare trace
        ends at that point. A control point takes an end of any net that lies
        on its copper: the runtime does not report a pair insertion's nets."""
        here = ShapelyPoint(point)
        inside: list[tuple[float, int]] = []
        near: list[tuple[float, int]] = []
        for i, n in enumerate(self.nodes):
            if layer not in n.layers:
                continue
            d = _dist(point, n.pos)
            on = n.shape.distance(here) <= END_TOLERANCE
            if on and (net in n.nets or n.kind == "control"):
                inside.append((d, i))
            elif net in n.nets and d <= END_SNAP:
                near.append((d, i))
        if inside or near:
            # On copper, a pad wins over a via in it: the end is the pad's.
            rank = {"pad": 0, "via": 1}
            i = (
                min(inside, key=lambda f: (rank.get(self.nodes[f[1]].kind, 2), f[0]))
                if inside
                else min(near)
            )[1]
            self.nodes[i].nets.add(net)
            return i
        slot = (net, layer, round(point[0], 2), round(point[1], 2))
        if slot not in self.free:
            self.free[slot] = len(self.nodes)
            self._add(
                _Node(
                    f"join@{slot[2]},{slot[3]}",
                    "join",
                    point,
                    {net},
                    frozenset({layer}),
                    here,
                )
            )
        return self.free[slot]

    def _edges(self) -> None:
        rd = self.rd
        added_pieces = False
        for trace, route in rd.query(Route):
            if trace.transform is None:
                continue
            rkey = self.key(trace)
            layer = rd.layers.normalize(route.layer)
            for rt in route.traces or []:
                net = (
                    self.net(rt)
                    or self.net(route.source)
                    or self.net(route.destination)
                )
                if net is None:
                    continue
                for s in rt.shapes:
                    placed = trace.transform * s
                    geom = placed.geometry
                    if not isinstance(geom, ArcPolyline | Polyline):
                        self.unmeasured.append(
                            {
                                "route": rkey,
                                "net": self.label(net),
                                "reason": "copper is a polygon",
                            }
                        )
                        for poly in _polys(placed.to_shapely().g):
                            self.pieces.append(
                                _Piece(net, layer, rkey, poly, route=rkey)
                            )
                        added_pieces = True
                        continue
                    t = placed.transform
                    points = [
                        (float(q[0]), float(q[1]))
                        for q in (
                            t * p for p in discretize(geom.elements, tolerance=1e-3)
                        )
                    ]
                    if len(points) < 2:
                        continue
                    a = self._end(points[0], layer, net)
                    b = self._end(points[-1], layer, net)
                    self.edges.append(
                        _Edge(
                            a,
                            b,
                            net,
                            layer,
                            rkey,
                            _length(geom.elements),
                            geom.width,
                            points,
                        )
                    )
        if added_pieces:
            self._touch()

    def adjacency(self) -> dict[int, dict[int, list[int]]]:
        """Per net, the edges at each node."""
        adj: dict[int, dict[int, list[int]]] = {}
        for i, e in enumerate(self.edges):
            per = adj.setdefault(e.net, {})
            per.setdefault(e.a, []).append(i)
            per.setdefault(e.b, []).append(i)
        return adj

    def path(
        self, net: int, sources: list[int], targets: set[int]
    ) -> list[tuple[int, int, str, int]]:
        """Shortest copper path on ``net``, as hops (from, to, kind, index):
        "trace" with an edge index, "pour" with a piece index, or "contact"
        (overlapping copper). Empty when no path joins them."""
        adj = self.adjacency().get(net, {})
        in_piece: dict[int, list[int]] = {}
        for pi, p in enumerate(self.pieces):
            if p.net == net:
                for n in p.nodes:
                    in_piece.setdefault(n, []).append(pi)
        best = {s: 0.0 for s in sources}
        back: dict[int, tuple[int, str, int]] = {}
        heap = [(0.0, s) for s in sources]
        while heap:
            d, n = heapq.heappop(heap)
            if d > best.get(n, math.inf):
                continue
            if n in targets:
                hops = []
                while n in back:
                    prev, kind, idx = back[n]
                    hops.append((prev, n, kind, idx))
                    n = prev
                return hops[::-1]
            steps: list[tuple[int, float, str, int]] = []
            for ei in adj.get(n, []):
                e = self.edges[ei]
                steps.append((e.b if e.a == n else e.a, e.length, "trace", ei))
            for c in self.contacts.get(n, []):
                if net in self.nodes[c].nets:
                    steps.append(
                        (c, _dist(self.nodes[n].pos, self.nodes[c].pos), "contact", -1)
                    )
            for pi in in_piece.get(n, []):
                for m in self.pieces[pi].nodes:
                    if m != n:
                        steps.append(
                            (m, _dist(self.nodes[n].pos, self.nodes[m].pos), "pour", pi)
                        )
            for m, cost, kind, idx in steps:
                if d + cost < best.get(m, math.inf):
                    best[m] = d + cost
                    back[m] = (n, kind, idx)
                    heapq.heappush(heap, (d + cost, m))
        return []

    def hop_points(self, hop: tuple[int, int, str, int]) -> list[XY]:
        a, b, kind, idx = hop
        if kind != "trace":
            return [self.nodes[a].pos, self.nodes[b].pos]
        pts = self.edges[idx].points
        return pts if self.edges[idx].a == a else pts[::-1]

    def find(self, key: str, net: int | None) -> list[int]:
        """Pad nodes with this key, or the pads of the component with this
        key, on ``net`` when given."""
        return [
            i
            for i, n in enumerate(self.nodes)
            if n.kind == "pad"
            and (n.key == key or n.key.startswith(key + "."))
            and (net is None or net in n.nets)
        ]

    def net_named(self, name: str) -> int | None:
        return next((n for n, label in self.labels.items() if label == name), None)


def _si(name: str, patterns: list[str]) -> bool:
    """A net named in ``si_nets``: exactly, or by a prefix ending in ``*``."""
    return any(
        name.startswith(p[:-1]) if p.endswith("*") else name == p for p in patterns
    )


def _in_scope(key: str, scope: list[str]) -> bool:
    """Whether ``key`` is a component in ``scope``, or a pad on one."""
    return any(key == p or key.startswith(p + ".") for p in scope)


@dataclass
class _Chain:
    """A run of links on one net between two terminal nodes: ``nodes`` from
    one end to the other, ``links`` between them in order, and ``edges`` the
    route traces among them, by index into the model's edges. ``ends`` and
    ``end_kinds`` name the two ends (a via in a pad by the pad);
    ``end_pads`` is the pad at each end, or None; ``bare`` is true when an
    end is a bare trace end."""

    net: int
    nodes: list[int]
    links: list[_Edge]
    edges: set[int]
    ends: tuple[str, str]
    end_kinds: tuple[str, str]
    end_pads: tuple[int | None, int | None]
    bare: bool


def _chains(m: _Model) -> list[_Chain]:
    """Every chain of links that holds at least one route trace. A link is a
    trace, or same-net copper that overlaps with no trace between, at its
    centre-to-centre distance (layer -1, no route)."""
    links = list(m.edges)
    for a, others in m.contacts.items():
        for b in others:
            if a < b:
                for net in m.nodes[a].nets & m.nodes[b].nets:
                    pa, pb = m.nodes[a].pos, m.nodes[b].pos
                    links.append(_Edge(a, b, net, -1, "", _dist(pa, pb), 0.0, [pa, pb]))
    adj: dict[int, dict[int, list[int]]] = {}
    for i, e in enumerate(links):
        adj.setdefault(e.net, {}).setdefault(e.a, []).append(i)
        adj[e.net].setdefault(e.b, []).append(i)
    out: list[_Chain] = []
    for net, per in adj.items():
        seen: set[int] = set()

        def terminal(n: int, per: dict[int, list[int]] = per) -> bool:
            return m.nodes[n].kind == "pad" or len(per[n]) != 2

        def other(e: _Edge, n: int) -> int:
            return e.b if e.a == n else e.a

        def named(n: int, net: int = net) -> tuple[str, str, int | None]:
            """A via in a pad is named by the pad."""
            node = m.nodes[n]
            if node.kind == "via":
                for c in m.contacts.get(n, []):
                    if m.nodes[c].kind == "pad" and net in m.nodes[c].nets:
                        return m.nodes[c].key, "via_in_pad", c
            return node.key, node.kind, n if node.kind == "pad" else None

        for start in (n for n in per if terminal(n)):
            for first in per[start]:
                if first in seen:
                    continue
                chain, ei = [first], first
                seen.add(first)
                nxt = other(links[ei], start)
                walked = [start, nxt]
                while not terminal(nxt):
                    ei = next(x for x in per[nxt] if x != ei)
                    if ei in seen:
                        break
                    seen.add(ei)
                    chain.append(ei)
                    nxt = other(links[ei], nxt)
                    walked.append(nxt)
                if not any(links[x].route for x in chain):
                    continue
                (ka, kind_a, pad_a), (kb, kind_b, pad_b) = named(start), named(nxt)
                out.append(
                    _Chain(
                        net,
                        walked,
                        [links[x] for x in chain],
                        {x for x in chain if x < len(m.edges)},
                        (ka, kb),
                        (kind_a, kind_b),
                        (pad_a, pad_b),
                        any(
                            m.nodes[n].kind == "join" and len(per[n]) == 1
                            for n in (start, nxt)
                        ),
                    )
                )
    return out


def _circuitousness(
    m: _Model, chains: list[_Chain], limit: float, si_nets: list[str], scope: list[str]
) -> dict[str, Any]:
    connections: list[dict[str, Any]] = []
    for ch in chains:
        routed = [e for e in ch.links if e.route]
        start, nxt = ch.nodes[0], ch.nodes[-1]
        length = sum(e.length for e in ch.links)
        distance = _dist(m.nodes[start].pos, m.nodes[nxt].pos)
        inner = {e.a for e in ch.links} | {e.b for e in ch.links}
        connections.append(
            {
                "net": m.label(ch.net),
                "ends": list(ch.ends),
                "end_kinds": list(ch.end_kinds),
                "length": _r(length),
                "distance": _r(distance),
                "ratio": _r(length / distance) if distance >= MIN_DISTANCE else None,
                "excess": _r(length - distance),
                "vias": sum(
                    1 for n in inner - {start, nxt} if m.nodes[n].kind == "via"
                ),
                "layers": sorted({e.layer for e in routed}),
                "routes": sorted({e.route for e in routed}),
                "bare_end": ch.bare,
                "edges": set(ch.edges),
            }
        )
    if scope:
        connections = [
            c for c in connections if any(_in_scope(k, scope) for k in c["ends"])
        ]
    edges: set[int] = set()
    for c in connections:
        edges |= c.pop("edges")
    joined = [c for c in connections if c.pop("bare_end")]
    si = [c for c in connections if c not in joined and _si(c["net"], si_nets)]
    checked = [c for c in connections if c not in joined and c not in si]
    ratios = [c["ratio"] for c in checked if c["ratio"] is not None]
    over = sorted(
        (c for c in checked if c["ratio"] is not None and c["ratio"] > limit),
        key=lambda c: -c["excess"],
    )
    unmeasured = m.unmeasured + [
        {"ends": c["ends"], "net": c["net"], "reason": "ends at a bare trace end"}
        for c in joined
    ]
    return {
        "scope": scope or None,
        "edges": edges,
        "limit": limit,
        "connections": len(checked),
        "with_ratio": len(ratios),
        "max": max(ratios) if ratios else None,
        "median": _r(statistics.median(ratios)) if ratios else None,
        "over_limit": len(over),
        "worst": over,
        "si_nets": si,
        "all": connections,
        "unmeasured": unmeasured,
    }


def _narrow_pad(m: _Model, n: int, rule: float) -> bool:
    """Node ``n`` is a pad narrower than ``rule``, or copper on one (a via in
    the pad)."""
    near = [n, *(c for c in m.contacts.get(n, []) if m.nodes[c].kind == "pad")]
    return any(
        m.nodes[i].kind == "pad"
        and m.nodes[i].narrow is not None
        and (m.nodes[i].narrow or 0.0) < rule
        for i in near
    )


@dataclass
class _Sheet:
    """A layer's copper on one net, its sheet conductance in siemens per
    square (thickness over resistivity), and its sheet inductance in nH per
    square over its return plane (None when there is no plane to return
    in)."""

    layer: int
    copper: BaseGeometry
    conductance: float
    inductance: float | None = None


@dataclass
class _Barrel:
    """A plated hole joining consecutive layers: its centre, drilled
    diameter, and each consecutive layer pair with the distance between
    the two layers' middles and that part's inductance in nH."""

    pos: XY
    hole: float
    spans: list[tuple[int, int, float, float]]


def _coverage(
    geom: BaseGeometry, origin: XY, shape: tuple[int, int], cell: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fraction inside ``geom`` of each grid cell, and of each face box: the
    cell-sized box centred on the face between two neighbours, through
    which they conduct (x faces, then y faces). From SUPERSAMPLE squared
    sample points per cell."""
    ny, nx = shape
    cov = np.zeros(shape)
    fx = np.zeros((ny, max(nx - 1, 0)))
    fy = np.zeros((max(ny - 1, 0), nx))
    if geom.is_empty:
        return cov, fx, fy
    s, half = SUPERSAMPLE, SUPERSAMPLE // 2
    # Polygon by polygon, each over its own bounds and one empty cell round
    # them: islands spread across the window cost only their own area.
    for poly in _polys(geom):
        gx0, gy0, gx1, gy1 = poly.bounds
        i0 = max(math.floor((gx0 - origin[0]) / cell) - 1, 0)
        i1 = min(math.ceil((gx1 - origin[0]) / cell) + 1, nx)
        j0 = max(math.floor((gy0 - origin[1]) / cell) - 1, 0)
        j1 = min(math.ceil((gy1 - origin[1]) / cell) + 1, ny)
        if i1 <= i0 or j1 <= j0:
            continue
        shapely.prepare(poly)
        xs = origin[0] + (np.arange(i0 * s, i1 * s) + 0.5) * cell / s
        step = max(1, 2_000_000 // (len(xs) * s))
        for r0 in range(j0, j1, step):
            r1 = min(r0 + step, j1)
            # Half a cell more below, for the y faces on this block's edge.
            f1 = min(r1 * s + half, ny * s)
            ys = origin[1] + (np.arange(r0 * s, f1) + 0.5) * cell / s
            gx, gy = np.meshgrid(xs, ys)
            fine = shapely.contains_xy(poly, gx, gy).astype(float)
            rows, cols = r1 - r0, i1 - i0
            body = fine[: rows * s]
            cov[r0:r1, i0:i1] += body.reshape(rows, s, cols, s).mean(axis=(1, 3))
            if cols > 1:
                mid = body[:, half : half + (cols - 1) * s]
                fx[r0:r1, i0 : i1 - 1] += mid.reshape(rows, s, cols - 1, s).mean(
                    axis=(1, 3)
                )
            faces = (len(fine) - half) // s
            if faces > 0:
                mid = fine[half : half + faces * s]
                fy[r0 : r0 + faces, i0:i1] += mid.reshape(faces, s, cols, s).mean(
                    axis=(1, 3)
                )
    return np.minimum(cov, 1.0), np.minimum(fx, 1.0), np.minimum(fy, 1.0)


def _pcg(
    diag: np.ndarray,
    fi: np.ndarray,
    fj: np.ndarray,
    gf: np.ndarray,
    b: np.ndarray,
    x0: np.ndarray | None = None,
) -> tuple[np.ndarray, int, bool]:
    """Jacobi-preconditioned conjugate gradient on the conductance matrix,
    from ``x0`` when given."""
    n = len(diag)

    def mul(x: np.ndarray) -> np.ndarray:
        return (
            diag * x
            - np.bincount(fi, gf * x[fj], minlength=n)
            - np.bincount(fj, gf * x[fi], minlength=n)
        )

    x = np.zeros(n) if x0 is None else x0.copy()
    r = b - mul(x) if x0 is not None else b.copy()
    z = r / diag
    p = z.copy()
    rz = float(r @ z)
    limit = CG_TOL * float(np.linalg.norm(b))
    for k in range(CG_MAX):
        if float(np.linalg.norm(r)) <= limit:
            return x, k, True
        q = mul(p)
        alpha = rz / float(p @ q)
        x += alpha * p
        r -= alpha * q
        z = r / diag
        rz_next = float(r @ z)
        p = z + (rz_next / rz) * p
        rz = rz_next
    return x, CG_MAX, False


def _solve(
    sheets: list[_Sheet],
    barrels: list[_Barrel],
    terminals: list[tuple[int, BaseGeometry, float]],
    window: tuple[float, float, float, float],
    cell: float,
    plating: float,
    max_cells: int,
) -> dict[str, Any]:
    """DC resistance, and inductance, between the terminals at 1 V and
    those at 0 V.

    Each layer's copper is a grid of cells. Neighbour cells join through
    the copper in the cell-sized box centred on the face between them, in
    proportion to how much of that box is covered; a terminal cell (at
    least half covered by a terminal) joins its free neighbour over half a
    cell, so the potential sits at the terminal's edge. Each barrel joins
    the cells inside its hole on consecutive layers, sharing the plated
    wall's conductance. The inductance is the same network solved again
    with each layer's sheet inductance in place of its sheet resistance and
    each barrel part's inductance in place of its resistance."""
    x0, y0, x1, y1 = window
    nx, ny = math.ceil((x1 - x0) / cell), math.ceil((y1 - y0) / cell)
    origin = (x0, y0)
    grids = {s.layer: _coverage(s.copper, origin, (ny, nx), cell) for s in sheets}
    covs = {k: v[0] for k, v in grids.items()}
    count = sum(int((c > 0).sum()) for c in covs.values())
    if count > max_cells:
        raise ValueError(
            f"{count} copper cells over max_cells {max_cells}: raise grid_mm "
            "(0.1 cuts the cells about four times), lower window_mm, or raise "
            "max_cells in checks-config.json (the solve takes longer)"
        )
    ids: dict[int, np.ndarray] = {}
    start = 0
    for layer, cov in covs.items():
        idx = np.full(cov.shape, -1)
        mask = cov > 0
        idx[mask] = np.arange(start, start + int(mask.sum()))
        start += int(mask.sum())
        ids[layer] = idx
    n = start
    with_l = all(s.inductance for s in sheets)
    ea: list[np.ndarray] = []
    eb: list[np.ndarray] = []
    eg: list[np.ndarray] = []
    el: list[np.ndarray] = []
    halves: list[np.ndarray] = []
    for s in sheets:
        cov, fx, fy = grids[s.layer]
        idx = ids[s.layer]
        for ca, cb, face, ia, ib in (
            (cov[:, :-1], cov[:, 1:], fx, idx[:, :-1], idx[:, 1:]),
            (cov[:-1, :], cov[1:, :], fy, idx[:-1, :], idx[1:, :]),
        ):
            both = (ca > 0) & (cb > 0) & (face > 0)
            ea.append(ia[both])
            eb.append(ib[both])
            eg.append(s.conductance * face[both])
            el.append(face[both] / (s.inductance or 1.0))
            # A free cell next to a terminal joins over half a cell.
            halves.append(np.full(int(both.sum()), 2.0))

    def cells_at(layer: int, pos: XY, radius: float) -> np.ndarray:
        idx = ids[layer]
        cx, cy = (pos[0] - x0) / cell, (pos[1] - y0) / cell
        r = radius / cell
        i0, i1 = max(int(cx - r) - 1, 0), min(int(cx + r) + 2, nx)
        j0, j1 = max(int(cy - r) - 1, 0), min(int(cy + r) + 2, ny)
        jj, ii = np.mgrid[j0:j1, i0:i1]
        near = (ii + 0.5 - cx) ** 2 + (jj + 0.5 - cy) ** 2 <= r * r
        found = idx[jj[near], ii[near]]
        if not len(found) and 0 <= int(cx) < nx and 0 <= int(cy) < ny:
            found = np.array([idx[int(cy), int(cx)]])
        return found

    for bar in barrels:
        wall = math.pi * plating * max(bar.hole - plating, plating)
        for la, lb, span, nh in bar.spans:
            if la not in ids or lb not in ids:
                continue
            ca = cells_at(la, bar.pos, bar.hole / 2)
            cb = cells_at(lb, bar.pos, bar.hole / 2)
            if len(ca) != len(cb):
                continue
            keep = (ca >= 0) & (cb >= 0)
            if not keep.any():
                continue
            k = int(keep.sum())
            ea.append(ca[keep])
            eb.append(cb[keep])
            eg.append(np.full(k, wall / (RHO_CU * span) / k))
            el.append(np.full(k, 1 / nh / k if nh > 0 else 0.0))
            halves.append(np.ones(k))
    a_all = np.concatenate(ea).astype(np.int64)
    b_all = np.concatenate(eb).astype(np.int64)
    half = np.concatenate(halves)
    volts = np.full(n, np.nan)
    for layer, geom, v in terminals:
        if layer not in ids:
            continue
        cov = _coverage(geom, origin, (ny, nx), cell)[0]
        hit = ids[layer][(cov >= 0.5) & (ids[layer] >= 0)]
        if not len(hit):
            p = geom.representative_point()
            hit = cells_at(layer, (p.x, p.y), 0.0)
            hit = hit[hit >= 0]
        clash = hit[~np.isnan(volts[hit]) & (volts[hit] != v)]
        if len(clash):
            raise ValueError("a source and a load share copper cells")
        volts[hit] = v
    fixed = ~np.isnan(volts)
    if not (volts == 1).any() or not (volts == 0).any():
        raise ValueError("a terminal has no copper cell in the window")
    fa, fb = fixed[a_all], fixed[b_all]
    free = ~fixed
    order = np.cumsum(free) - 1
    nf = int(free.sum())
    inner = ~fa & ~fb
    fi, fj = order[a_all[inner]], order[b_all[inner]]
    src_a, src_b = volts[a_all] == 1, volts[b_all] == 1
    load_a, load_b = volts[a_all] == 0, volts[b_all] == 0

    def one(g_all: np.ndarray, x0: np.ndarray | None) -> dict[str, Any]:
        """Solve the network for one set of edge weights."""
        g_eff = np.where(fa != fb, half * g_all, g_all)
        gf = g_all[inner]
        diag = np.bincount(fi, gf, minlength=nf) + np.bincount(fj, gf, minlength=nf)
        rhs = np.zeros(nf)
        for side, other in ((a_all, b_all), (b_all, a_all)):
            sel = ~fixed[side] & fixed[other]
            diag += np.bincount(order[side[sel]], g_eff[sel], minlength=nf)
            rhs += np.bincount(
                order[side[sel]], g_eff[sel] * volts[other[sel]], minlength=nf
            )
        diag[diag == 0] = 1.0
        began = time.perf_counter()
        xf, iterations, converged = _pcg(diag, fi, fj, gf, rhs, x0)
        v = volts.copy()
        v[free] = xf
        flow = g_eff * (v[a_all] - v[b_all])
        out_src = float(flow[src_a].sum() - flow[src_b].sum())
        into_load = float(flow[load_b].sum() - flow[load_a].sum())
        current = (out_src + into_load) / 2
        return {
            "value": 1 / current if current > 0 else None,
            "iterations": iterations,
            "converged": converged,
            "balance": _r(into_load / out_src) if out_src else None,
            "seconds": round(time.perf_counter() - began, 2),
            "x": xf,
        }

    r_solve = one(np.concatenate(eg), None)
    # The inductance solve starts from the resistance solution.
    l_solve = one(np.concatenate(el), r_solve["x"]) if with_l else None
    stats = {
        name: {k: v for k, v in res.items() if k not in ("x", "value")}
        for name, res in (("r", r_solve), ("l", l_solve))
        if res is not None
    }
    return {
        "ohm": r_solve["value"],
        "nh": None if l_solve is None else l_solve["value"],
        "cells": n,
        "grid": [nx, ny],
        "solves": stats,
    }


def _stackup(rd: Any, config: dict[str, Any]) -> tuple[list[float], list[float]]:
    """Each conductor's copper thickness and the depth of its middle, top
    first, in mm. ``copper_mm`` (one value, or per layer index) overrides
    the substrate."""
    mats = list(decompose(rd.root.substrate.stackup, Material))
    thick: list[float] = []
    depth: list[float] = []
    z = 0.0
    for mat in mats:
        t = float(mat.thickness or 0.0)
        if isinstance(mat, Conductor):
            thick.append(t)
            depth.append(z + t / 2)
        z += t
    over = config.get("copper_mm")
    if isinstance(over, int | float):
        thick = [float(over)] * len(thick)
    elif isinstance(over, dict):
        for k, val in over.items():
            thick[int(k)] = float(val)
    return thick, depth


def _tube_nh(length: float, radius: float) -> float:
    """Partial self-inductance in nH of a straight thin tube, ``length`` and
    ``radius`` in mm: the mutual inductance of two parallel filaments
    ``length`` long, ``radius`` apart, since a thin tube's geometric mean
    distance from itself is its radius (Inductance Calculations, 1946:
    straight filaments, geometric mean distances)."""
    root = math.hypot(length, radius)
    return (
        MU0
        / (2 * math.pi)
        * (length * math.log((length + root) / radius) - root + radius)
    )


def _planes(m: _Model, config: dict[str, Any]) -> list[int]:
    """Layers that count as return planes: ``plane_layers`` from the
    config, or else each layer whose pour fills, on any net, cover at least
    PLANE_SHARE of the board."""
    if "plane_layers" in config:
        return sorted(int(k) for k in config["plane_layers"])
    board = m.rd.root.board.shape.to_shapely().g.area
    per: dict[int, list[BaseGeometry]] = {}
    for p in m.pieces:
        if not p.route:
            per.setdefault(p.layer, []).append(p.geom)
    return sorted(
        k for k, geoms in per.items() if unary_union(geoms).area >= PLANE_SHARE * board
    )


def _sheet_nh(
    layer: int, planes: list[int], thick: list[float], depth: list[float]
) -> float | None:
    """Sheet inductance in nH per square of copper on ``layer`` over its
    return: mu0 times the dielectric distance to the nearest plane layer,
    the parallel-plate inductance of a wide strip over a plane (L = mu0 h
    l / w). With a plane on each side the two returns are in parallel,
    mu0 h1 h2 / (h1 + h2), as for a wide stripline. None with no plane."""

    def gap(j: int) -> float:
        return abs(depth[j] - depth[layer]) - (thick[j] + thick[layer]) / 2

    above = [gap(j) for j in planes if j < layer]
    below = [gap(j) for j in planes if j > layer]
    hs = [min(side) for side in (above, below) if side]
    if not hs or min(hs) <= 0:
        return None
    return MU0 / sum(1 / h for h in hs)


def _trust(stats: dict[str, Any] | None, what: str) -> str | None:
    """Why a solve's value is not trusted, or None."""
    if stats is None:
        return None
    if not stats["converged"]:
        return f"the {what} solve did not converge in {CG_MAX} iterations"
    bal = stats["balance"]
    if bal is None or abs(bal - 1) > BALANCE_TOL:
        return f"the {what} solve's balance {bal} is off 1 by more than {BALANCE_TOL}"
    return None


def _ir(
    m: _Model,
    net: int,
    src: list[int],
    dst: list[int],
    hops: list[tuple[int, int, str, int]],
    config: dict[str, Any],
    spec: dict[str, Any],
    planes: list[int],
) -> dict[str, Any]:
    """Estimated DC resistance, drop and inductance from the ``src`` pads to
    the ``dst`` pads on ``net``, solved on the copper in a window around
    the path."""
    cell = float(spec.get("grid_mm", config["grid_mm"]))
    margin = float(spec.get("window_mm", config["window_mm"]))
    plating = float(config["via_plating_mm"])
    thick, depth = _stackup(m.rd, config)
    pts = [p for hop in hops for p in m.hop_points(hop)]
    shapes = [m.nodes[i].shape for i in src + dst]
    bx0, by0, bx1, by1 = unary_union([*shapes, *(ShapelyPoint(p) for p in pts)]).bounds
    window = (bx0 - margin, by0 - margin, bx1 + margin, by1 + margin)
    frame = box(*window)
    per: dict[int, list[BaseGeometry]] = {}
    for e in m.edges:
        if e.net == net:
            per.setdefault(e.layer, []).append(LineString(e.points).buffer(e.width / 2))
    for p in m.pieces:
        if p.net == net:
            per.setdefault(p.layer, []).append(p.geom)
    barrels = []
    for n in m.nodes:
        if net not in n.nets:
            continue
        for layer in n.layers:
            per.setdefault(layer, []).append(n.on(layer))
        span = sorted(n.layers)
        if n.hole and len(span) > 1 and frame.contains(ShapelyPoint(n.pos)):
            # The barrel's inductance per mm over its whole length, shared
            # by each part in proportion to its length.
            full = depth[span[-1]] - depth[span[0]]
            per_mm = _tube_nh(full, max(n.hole - plating, plating) / 2) / full
            barrels.append(
                _Barrel(
                    n.pos,
                    n.hole,
                    [
                        (a, b, depth[b] - depth[a], per_mm * (depth[b] - depth[a]))
                        for a, b in itertools.pairwise(span)
                    ],
                )
            )
    sheets = []
    for layer, geoms in sorted(per.items()):
        copper = unary_union(geoms).intersection(frame)
        if copper.is_empty:
            continue
        if not thick[layer]:
            raise ValueError(f"layer {layer} has no copper thickness: set copper_mm")
        sheets.append(
            _Sheet(
                layer,
                copper,
                thick[layer] / RHO_CU,
                _sheet_nh(layer, planes, thick, depth),
            )
        )
    terminals = [
        (layer, m.nodes[i].on(layer), v)
        for group, v in ((src, 1.0), (dst, 0.0))
        for i in group
        for layer in m.nodes[i].layers
    ]
    solved = _solve(
        sheets, barrels, terminals, window, cell, plating, int(config["max_cells"])
    )
    ohm, nh = solved.pop("ohm"), solved.pop("nh")
    current = spec.get("current_a", config.get("current_a"))
    budget = spec.get("max_drop_mv", config.get("max_drop_mv"))
    l_budget = spec.get("max_l_nh", config.get("max_l_nh"))
    drop = None if ohm is None or current is None else ohm * float(current) * 1e3
    r_why = _trust(solved["solves"].get("r"), "resistance")
    l_why = _trust(solved["solves"].get("l"), "inductance")
    if not all(s.inductance for s in sheets):
        missing = [s.layer for s in sheets if not s.inductance]
        l_why = f"no return plane for layers {missing}: set plane_layers"
    reasons = [w for w in (r_why, l_why) if w]
    return (
        {
            "r_mohm": None if ohm is None else _r(ohm * 1e3),
            "l_nh": None if nh is None else _r(nh),
            "current_a": current,
            "drop_mv": None if drop is None else _r(drop),
            "max_drop_mv": budget,
            "within_budget": (
                None if drop is None or budget is None or r_why else drop <= budget
            ),
            "max_l_nh": l_budget,
            "l_within_budget": (
                None if nh is None or l_budget is None or l_why else nh <= l_budget
            ),
            "grid_mm": cell,
            "window_mm": margin,
            "layers": [s.layer for s in sheets],
            "sheet_nh": {
                s.layer: None if s.inductance is None else _r(s.inductance)
                for s in sheets
            },
        }
        | ({"reasons": reasons} if reasons else {})
        | solved
    )


def _path_net(m: _Model, spec: dict[str, Any]) -> tuple[int | None, str]:
    """The path's net: the one named, or, with none named, the only net
    ``from`` has pads on. The string says why there is none."""
    name = spec.get("net")
    if name:
        net = m.net_named(name)
        return net, "" if net is not None else f"no net named {name}"
    nets = {n for i in m.find(spec["from"], None) for n in m.nodes[i].nets}
    if len(nets) == 1:
        return nets.pop(), ""
    return None, f"from has pads on {len(nets)} nets: name the net"


def _power(
    m: _Model, config: dict[str, Any], ring: float, scoped: set[int] | None
) -> dict[str, Any]:
    rules: dict[str, float] = config.get("power", {})
    planes = _planes(m, config) if config.get("power_paths") else []
    out: dict[str, Any] = {"nets": {}, "paths": [], "errors": [], "planes": planes}
    for name, rule in rules.items():
        net = m.net_named(name)
        if net is None:
            out["errors"].append(f"no net named {name}")
            continue
        traces = [e for e in m.edges if e.net == net]
        # With a scope, only the traces of connections in it are listed.
        listed = [
            e
            for i, e in enumerate(m.edges)
            if e.net == net and (scoped is None or i in scoped)
        ]
        narrow = [
            {
                "route": e.route,
                "layer": e.layer,
                "width": _r(e.width),
                "length": _r(e.length),
                "ends": [m.nodes[e.a].key, m.nodes[e.b].key],
                "step_down": e.length <= ring
                and any(_narrow_pad(m, n, rule) for n in (e.a, e.b)),
            }
            for e in listed
            if e.width < rule - 1e-6
        ]
        out["nets"][name] = {
            "rule": rule,
            "traces": len(traces),
            "narrowest": _r(min(e.width for e in traces)) if traces else None,
            "met": all(t["step_down"] for t in narrow),
            "narrower_than_rule": narrow,
            "polygon_routes": sorted(
                {p.route for p in m.pieces if p.net == net and p.route}
            ),
            "pours": len({p.key for p in m.pieces if p.net == net and not p.route}),
        }
    for spec in config.get("power_paths", []):
        entry: dict[str, Any] = {k: spec.get(k) for k in ("net", "from", "to")}
        net, why = _path_net(m, spec)
        if net is None:
            entry["error"] = why
            out["paths"].append(entry)
            continue
        name = m.label(net)
        entry["net"] = name
        rule = rules.get(name)
        src, dst = m.find(spec["from"], net), m.find(spec["to"], net)
        if not src or not dst:
            entry["error"] = f"from or to has no pad on {name}"
            out["paths"].append(entry)
            continue
        hops = m.path(net, src, set(dst))
        if not hops:
            entry["error"] = "no copper path joins them"
            out["paths"].append(entry)
            continue
        rows = []
        for a, b, kind, idx in hops:
            row: dict[str, Any] = {
                "from": m.nodes[a].key,
                "to": m.nodes[b].key,
                "kind": kind,
            }
            if kind == "trace":
                e = m.edges[idx]
                step = (
                    rule is not None
                    and e.length <= ring
                    and any(_narrow_pad(m, n, rule) for n in (e.a, e.b))
                )
                row |= {
                    "route": e.route,
                    "layer": e.layer,
                    "width": _r(e.width),
                    "length": _r(e.length),
                    "step_down": step,
                }
            elif kind == "pour" and m.pieces[idx].route:
                # Route copper that came back as a polygon is still a trace.
                row |= {
                    "kind": "trace",
                    "route": m.pieces[idx].route,
                    "layer": m.pieces[idx].layer,
                    "copper": "polygon",
                    "length": _r(_dist(m.nodes[a].pos, m.nodes[b].pos)),
                    "step_down": False,
                }
            elif kind == "pour":
                row |= {"pour": m.pieces[idx].key, "layer": m.pieces[idx].layer}
            rows.append(row)
        traced = [r for r in rows if r["kind"] == "trace" and not r["step_down"]]
        entry |= {
            "hops": rows,
            "trace_hops": len(traced),
            "trace_length": _r(sum(r["length"] for r in traced)),
        }
        try:
            entry["ir"] = _ir(m, net, src, dst, hops, config, spec, planes)
        except ValueError as err:
            entry["ir"] = {"error": str(err)}
        checks = []
        if spec.get("require_pour"):
            checks.append(not traced)
        for key, budget in (
            ("within_budget", "max_drop_mv"),
            ("l_within_budget", "max_l_nh"),
        ):
            if spec.get(budget, config.get(budget)) is not None:
                checks.append(entry["ir"].get(key))
        met: bool | None = None
        if False in checks:
            met = False
        elif checks and None not in checks:
            met = True
        entry["met"] = met
        out["paths"].append(entry)
    return out


def _loops(m: _Model, config: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    scope = config.get("scope") or []
    for spec in config.get("loops", []):
        named = [spec.get("cap", ""), spec.get("ic", ""), *spec.get("pads", [])]
        if scope and not any(_in_scope(k, scope) for k in named):
            continue
        entry: dict[str, Any] = {k: spec[k] for k in ("cap", "ic", "pads") if k in spec}
        target = spec.get("target_mm2", config.get("loop_target_mm2"))
        if "pads" in spec:
            found = [m.find(k, None) for k in spec["pads"]]
            if len(found) != 4 or not all(len(f) == 1 for f in found):
                entry["error"] = "pads must name four pads"
                out.append(entry)
                continue
            ca, ia, ib, cb = (f[0] for f in found)
        else:
            caps = m.find(spec["cap"], None)
            if len(caps) != 2:
                entry["error"] = f"capacitor has {len(caps)} placed pads, not 2"
                out.append(entry)
                continue
            ca, cb = caps
            pins = []
            for c in caps:
                net = next(iter(m.nodes[c].nets), None)
                cand = m.find(spec["ic"], net) if net is not None else []
                pins.append(
                    min(cand, key=lambda i: _dist(m.nodes[i].pos, m.nodes[c].pos))
                    if cand
                    else None
                )
            ia, ib = pins
            if ia is None or ib is None:
                entry["error"] = "the IC has no pad on one of the capacitor's nets"
                out.append(entry)
                continue
        na, nb = (next(iter(m.nodes[n].nets), None) for n in (ca, cb))
        # Only a capacitor straight across two pins of one IC: the segments
        # that close the loop then run through the two parts themselves.
        owners = [m.nodes[n].owner for n in (ca, cb, ia, ib)]
        if (
            na is None
            or nb is None
            or na == nb
            or na not in m.nodes[ia].nets
            or nb not in m.nodes[ib].nets
            or owners[0] != owners[1]
            or owners[2] != owners[3]
            or owners[0] == owners[2]
        ):
            entry["error"] = (
                "not a capacitor across two pins of one IC on the same two nets"
            )
            out.append(entry)
            continue
        go, ret = m.path(na, [ca], {ia}), m.path(nb, [ib], {cb})
        if not go or not ret:
            entry["error"] = "no copper path from a capacitor pad to its IC pin"
            out.append(entry)
            continue
        ring: list[XY] = []
        for hop in go + ret:
            ring += m.hop_points(hop)
        ring.append(ring[0])
        faces = list(polygonize(unary_union(LineString(ring)))) if len(ring) > 3 else []
        area = sum(f.area for f in faces)
        entry |= {
            "pins": [m.nodes[n].key for n in (ca, ia, ib, cb)],
            "area_mm2": _r(area),
            "target_mm2": target,
            "met": None if target is None else area <= target,
            "path": [
                f"{m.nodes[a].key} -{kind}-> {m.nodes[b].key}"
                for a, b, kind, _ in go + ret
            ],
        }
        out.append(entry)
    return out


def _capacitors(m: _Model) -> set[str]:
    """Keys of components with a `capacitance`, as the standard library's
    capacitors carry. A live session hands components back behind a proxy,
    so their class is not visible to `type()`; their attributes are."""
    out = set()
    for trace, comp in m.rd.query(Component):
        if getattr(comp, "capacitance", None) is not None:
            out.add(m.key(trace))
    return out


def _decap_vias(
    m: _Model, config: dict[str, Any], scope: list[str]
) -> list[dict[str, Any]]:
    """Where each capacitor's plane vias sit against its pads.

    A capacitor counts when each of its two pads, on two nets, has a via of
    its own net in it, or joined to it by one route (a trace no longer than
    ``decap_via_reach_mm``, or route copper that came back as a polygon,
    with the via centre within that distance of the pad centre). Per via: ``along`` is how far it lies past the
    pad's centre away from the other pad, ``lateral`` how far to one side,
    both in mm. ``placement`` is ``in_pad``, ``end`` (further past the pad's
    outer edge than past its side), ``side`` or ``between`` (towards the
    other pad). ``met`` is true when every via is in its pad or beside it
    and the nearest power and ground vias are on the same side."""
    reach = float(config.get("decap_via_reach_mm", 2.0))
    caps = _capacitors(m)
    pads: dict[str, list[int]] = {}
    for i, n in enumerate(m.nodes):
        if n.kind == "pad" and n.owner in caps:
            pads.setdefault(n.owner, []).append(i)
    links: dict[int, list[tuple[int, float]]] = {}
    for e in m.edges:
        for a, b in ((e.a, e.b), (e.b, e.a)):
            if m.nodes[a].kind == "pad" and m.nodes[b].kind == "via":
                links.setdefault(a, []).append((b, e.length))
    # A route on a power or ground net often comes back as polygon copper:
    # a pad and a via it touches count as joined, by their centre distance.
    for piece in m.pieces:
        if not piece.route:
            continue
        for a in piece.nodes:
            if m.nodes[a].kind != "pad":
                continue
            for b in piece.nodes:
                if m.nodes[b].kind == "via":
                    links.setdefault(a, []).append(
                        (b, _dist(m.nodes[a].pos, m.nodes[b].pos))
                    )
    out = []
    for owner, idx in sorted(pads.items()):
        if len(idx) != 2 or (scope and not _in_scope(owner, scope)):
            continue
        a, b = idx
        if m.nodes[a].nets == m.nodes[b].nets:
            continue
        found: dict[int, list[tuple[int, str]]] = {}
        for p in (a, b):
            got = [
                (v, "in_pad") for v in m.contacts.get(p, []) if m.nodes[v].kind == "via"
            ]
            got += [(v, "") for v, length in links.get(p, []) if length <= reach]
            seen: set[int] = set()
            found[p] = [(v, k) for v, k in got if not (v in seen or seen.add(v))]
        if not found[a] or not found[b]:
            continue
        pa, pb = m.nodes[a].pos, m.nodes[b].pos
        pitch = _dist(pa, pb)
        if pitch == 0:
            continue
        entry: dict[str, Any] = {"cap": owner, "pad_pitch": _r(pitch), "pads": []}
        sides: dict[int, list[tuple[float, int]]] = {}
        ok = True
        for p, q in ((a, b), (b, a)):
            c, o = m.nodes[p].pos, m.nodes[q].pos
            ux, uy = (c[0] - o[0]) / pitch, (c[1] - o[1]) / pitch
            ring = list(_polys(m.nodes[p].shape)[0].exterior.coords)
            half_along = max((x - c[0]) * ux + (y - c[1]) * uy for x, y in ring)
            half_lat = max(abs(-(x - c[0]) * uy + (y - c[1]) * ux) for x, y in ring)
            vias = []
            for v, kind in found[p]:
                vx, vy = m.nodes[v].pos
                along = (vx - c[0]) * ux + (vy - c[1]) * uy
                lateral = -(vx - c[0]) * uy + (vy - c[1]) * ux
                if not kind:
                    if along < -half_along:
                        kind = "between"
                    elif along - half_along > abs(lateral) - half_lat:
                        kind = "end"
                    else:
                        kind = "side"
                if kind in ("end", "between"):
                    ok = False
                if kind == "side":
                    # Lateral sign in pad a's frame, so both pads compare.
                    sign = 1 if (lateral if p == a else -lateral) > 0 else -1
                    sides.setdefault(p, []).append((sign, v))
                vias.append(
                    {
                        "via": m.nodes[v].key,
                        "placement": kind,
                        "along": _r(along),
                        "lateral": _r(lateral),
                    }
                )
            entry["pads"].append(
                {
                    "pad": m.nodes[p].key,
                    "net": m.label(next(iter(m.nodes[p].nets))),
                    "vias": vias,
                }
            )
        pairs = [
            (_dist(m.nodes[v].pos, m.nodes[w].pos), v, w)
            for v, _ in found[a]
            for w, _ in found[b]
        ]
        gap, v, w = min(pairs)
        entry["via_gap"] = _r(gap)
        sa = {x: s_ for s_, x in sides.get(a, [])}
        sb = {x: s_ for s_, x in sides.get(b, [])}
        if v in sa and w in sb and sa[v] != sb[w]:
            entry["opposite_sides"] = True
            ok = False
        entry["met"] = ok
        out.append(entry)
    return out


def _scoped_vias(m: _Model, chains: list[_Chain], scope: list[str]) -> set[int] | None:
    """The vias a scope covers: those on a connection with an end on a
    component in it, or against one of its pads. None with no scope."""
    if not scope:
        return None
    scoped: set[int] = set()
    for ch in chains:
        if any(_in_scope(k, scope) for k in ch.ends):
            scoped |= {n for n in ch.nodes if m.nodes[n].kind == "via"}
    for i, n in enumerate(m.nodes):
        if n.kind == "pad" and _in_scope(n.key, scope):
            scoped |= {c for c in m.contacts.get(i, []) if m.nodes[c].kind == "via"}
    return scoped


def _dangling(m: _Model, scoped: set[int] | None) -> list[dict[str, Any]]:
    """Vias whose copper (route traces, pour fills, polygon route copper,
    pads they overlap) touches them on fewer than two layers."""
    layers: dict[int, set[int]] = {
        i: set() for i, n in enumerate(m.nodes) if n.kind == "via"
    }
    for e in m.edges:
        for n in (e.a, e.b):
            if n in layers:
                layers[n].add(e.layer)
    for pc in m.pieces:
        for n in pc.nodes:
            if n in layers:
                layers[n].add(pc.layer)
    for v, found in layers.items():
        for c in m.contacts.get(v, []):
            if m.nodes[c].kind == "pad":
                found |= m.nodes[v].layers & m.nodes[c].layers
    return [
        {
            "via": m.nodes[v].key,
            "net": m.label(next(iter(m.nodes[v].nets))) if m.nodes[v].nets else None,
            "layers": sorted(found),
        }
        for v, found in layers.items()
        if len(found) < 2 and (scoped is None or v in scoped)
    ]


def _in_pad(
    m: _Model, scoped: set[int] | None, scope: list[str]
) -> list[dict[str, Any]]:
    """Vias whose definition allows no via in a pad and whose copper
    overlaps a pad's copper, of any net, on a layer both are on. With a
    scope, a via counts when it is in scope or the pad is."""
    pads = [(i, n, n.shape.bounds) for i, n in enumerate(m.nodes) if n.kind == "pad"]
    out = []
    for v, via in enumerate(m.nodes):
        if via.kind != "via" or via.via_in_pad:
            continue
        x0, y0, x1, y1 = via.shape.bounds
        for _, pad, (px0, py0, px1, py1) in pads:
            if px0 > x1 or px1 < x0 or py0 > y1 or py1 < y0:
                continue
            if scoped is not None and v not in scoped and not _in_scope(pad.key, scope):
                continue
            shared = sorted(
                layer
                for layer in via.layers & pad.layers
                if via.shape.intersection(pad.on(layer)).area > 1e-6
            )
            if shared:
                out.append(
                    {
                        "via": via.key,
                        "definition": via.definition,
                        "pad": pad.key,
                        "via_net": m.label(next(iter(via.nets))) if via.nets else None,
                        "pad_net": m.label(next(iter(pad.nets))) if pad.nets else None,
                        "layers": shared,
                    }
                )
    return out


def _via_plan(
    m: _Model, chains: list[_Chain], reach: float, scope: list[str]
) -> dict[str, Any]:
    """The via plan of every pad-to-pad connection.

    A connection is a chain (as for circuitousness) whose two ends are pads,
    or vias in pads. Its vias are the vias it passes and a via in a pad at
    an end. Per via: ``from_end``, its distance along the chain to the
    nearer end (0 for a via in the end pad), ``far_from_end`` when that is
    over ``reach``, and ``redundant`` when the nearer end's pad reaches the
    layer of the first trace on the via's far side, so the pad could have
    made the layer change itself. A connection fails with more than two
    vias, or any via far from its end or redundant."""
    rows: list[dict[str, Any]] = []
    left_out = 0
    for ch in chains:
        if scope and not any(_in_scope(k, scope) for k in ch.ends):
            continue
        pad_a, pad_b = ch.end_pads
        if pad_a is None or pad_b is None or ch.bare:
            left_out += 1
            continue
        lengths = [e.length for e in ch.links]
        total = sum(lengths)
        along = list(itertools.accumulate(lengths, initial=0.0))
        last = len(ch.nodes) - 1
        vias = []
        for i, n in enumerate(ch.nodes):
            if m.nodes[n].kind != "via":
                continue
            if i == 0 or i == last:
                # A via in the end pad: it sits at that end.
                near_start, distance = i == 0, 0.0
            else:
                near_start = along[i] <= total - along[i]
                distance = min(along[i], total - along[i])
            pad = pad_a if near_start else pad_b
            # The first trace moving away from the nearer end.
            onward = ch.links[i:] if near_start else ch.links[:i][::-1]
            far = next((e.layer for e in onward if e.route), None)
            vias.append(
                {
                    "via": m.nodes[n].key,
                    "from_end": _r(distance),
                    "end": m.nodes[pad].key,
                    "far_layer": far,
                    "far_from_end": distance > reach,
                    "redundant": far is not None and far in m.nodes[pad].layers,
                }
            )
        met = len(vias) <= 2 and not any(
            v["far_from_end"] or v["redundant"] for v in vias
        )
        rows.append(
            {
                "net": m.label(ch.net),
                "ends": list(ch.ends),
                "end_kinds": list(ch.end_kinds),
                "length": _r(total),
                "vias": len(vias),
                "placement": vias,
                "met": met,
            }
        )
    failing = [r for r in rows if not r["met"]]
    scoped = _scoped_vias(m, chains, scope)
    dangling = _dangling(m, scoped)
    in_pad = _in_pad(m, scoped, scope)
    return {
        "via_reach_mm": reach,
        "connections": len(rows),
        "by_count": dict(sorted(Counter(r["vias"] for r in rows).items())),
        "over_two": sum(1 for r in rows if r["vias"] > 2),
        "far_from_end": sum(
            1 for r in rows for v in r["placement"] if v["far_from_end"]
        ),
        "redundant": sum(1 for r in rows for v in r["placement"] if v["redundant"]),
        "not_pad_to_pad": left_out,
        "met": not (failing or dangling or in_pad),
        "failing": failing,
        "dangling": dangling,
        "via_in_pad": in_pad,
    }


def _unplaced_pads(m: _Model) -> dict[int, list[str]]:
    """Per net, the keys of pads on components that are not placed, which
    the model leaves out."""
    placed = {n.owner for n in m.nodes if n.kind == "pad"}
    comps: list[str] = []
    for trace, comp in m.rd.query(Component):
        if comp.transform is None or trace.transform is None:
            comps.append(m.key(trace))
    comps.sort(key=len, reverse=True)
    out: dict[int, list[str]] = {}
    if not comps:
        return out
    for trace, pad in m.rd.query(Pad):
        k = m.key(trace)
        owner = next((c for c in comps if k.startswith(c + ".")), None)
        if owner is None or owner in placed:
            continue
        net = m.net(pad)
        if net is not None:
            out.setdefault(net, []).append(k)
    return out


def _connectivity(m: _Model, scope: list[str]) -> dict[str, Any]:
    """Per net with two or more pads, how many groups its placed pads fall
    into when joined by realized copper: route traces, overlapping copper,
    and pour fills and polygon route copper, each piece joining every pad
    and via it touches. A via or through-hole pad is one node on all its
    layers, so pieces on different layers join through it."""
    pads: dict[int, list[int]] = {}
    for i, n in enumerate(m.nodes):
        if n.kind == "pad":
            for net in n.nets:
                pads.setdefault(net, []).append(i)
    unplaced = _unplaced_pads(m)
    unknown: set[int] = set()
    for _, pour in m.rd.query(Pour):
        net = m.net(pour)
        if net is not None and _pieces(pour.shape) is None:
            unknown.add(net)
    by_net: dict[int, list[_Edge]] = {}
    for e in m.edges:
        by_net.setdefault(e.net, []).append(e)
    touching = [(a, b) for a, others in m.contacts.items() for b in others if a < b]
    nets: dict[str, Any] = {}
    for net in sorted(set(pads) | set(unplaced), key=m.label):
        mine = pads.get(net, [])
        missing = unplaced.get(net, [])
        if len(mine) + len(missing) < 2:
            continue
        keys = [m.nodes[i].key for i in mine]
        if scope and not any(_in_scope(k, scope) for k in keys + missing):
            continue
        entry: dict[str, Any] = {"pads": len(mine)}
        if missing:
            entry["unchecked"] = missing[:LIST_LIMIT]
        if net in unknown:
            entry["status"] = "unknown"
            entry["reason"] = "a pour on this net has no fill yet: sync and rerun"
        elif len(mine) < 2:
            entry["status"] = "unchecked"
        else:
            links = [(e.a, e.b) for e in by_net.get(net, [])]
            links += [
                (a, b) for a, b in touching if net in m.nodes[a].nets & m.nodes[b].nets
            ]
            for pc in m.pieces:
                if pc.net == net:
                    links += [(pc.nodes[0], b) for b in pc.nodes[1:]]
            parent: dict[int, int] = {}

            def find(i: int, parent: dict[int, int] = parent) -> int:
                while parent.get(i, i) != i:
                    parent[i] = parent.get(parent[i], parent[i])
                    i = parent[i]
                return i

            for a, b in links:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra
            groups: dict[int, list[str]] = {}
            for i in mine:
                groups.setdefault(find(i), []).append(m.nodes[i].key)
            parts = sorted(groups.values(), key=len, reverse=True)
            entry["groups"] = len(parts)
            entry["status"] = "joined" if len(parts) == 1 else "split"
            if len(parts) > 1:
                entry["group_pads"] = [g[:LIST_LIMIT] for g in parts[:LIST_LIMIT]]
        nets[m.label(net)] = entry
    split = [n for n, v in nets.items() if v["status"] == "split"]
    return {
        "nets": nets,
        "checked": sum(1 for v in nets.values() if v["status"] in ("joined", "split")),
        "split": split,
        "unknown": [n for n, v in nets.items() if v["status"] == "unknown"],
        "unchecked_pads": sorted(
            k for v in nets.values() for k in v.get("unchecked", [])
        ),
        "met": not split,
    }


def _courtyards(m: _Model) -> tuple[dict[str, BaseGeometry], dict[str, str]]:
    """Each placed component's courtyard on the board, and its side."""
    side_of: dict[str, str] = {}
    keys: list[str] = []
    for trace, comp in m.rd.query(Component):
        k = m.key(trace)
        keys.append(k)
        if comp.transform is not None and trace.transform is not None:
            xf = trace.transform * comp.transform
            bottom = getattr(xf, "side", Side.Top) == Side.Bottom
            side_of[k] = "bottom" if bottom else "top"
    owners = sorted(keys, key=len, reverse=True)
    out: dict[str, BaseGeometry] = {}
    for trace, court in m.rd.query(Courtyard):
        k = m.key(trace)
        owner = next((c for c in owners if k.startswith(c + ".")), None)
        if owner is None or owner not in side_of or trace.transform is None:
            continue
        geom = (trace.transform * court.shape).to_shapely().g
        out[owner] = geom if owner not in out else out[owner].union(geom)
    return out, side_of


def _sanity(
    m: _Model, chains: list[_Chain], overhang: dict[str, str], scope: list[str]
) -> dict[str, Any]:
    """Components whose courtyard leaves the board, courtyards that overlap
    on one side, and vias whose copper leaves the board. An off-board
    component named in ``overhang`` is listed with its reason and passes."""
    board = m.rd.root.board.shape.to_shapely().g
    inside = board.buffer(1e-6)
    courts, side_of = _courtyards(m)
    placed = sorted(k for k in courts if not scope or _in_scope(k, scope))
    off = []
    for k in placed:
        if inside.contains(courts[k]):
            continue
        outside = courts[k].difference(board).area
        entry: dict[str, Any] = {"component": k, "outside_mm2": _r(outside)}
        if k in overhang:
            entry["overhang"] = overhang[k]
        off.append(entry)
    overlaps = []
    every = sorted(courts)
    for i, a in enumerate(every):
        for b in every[i + 1 :]:
            if scope and not (_in_scope(a, scope) or _in_scope(b, scope)):
                continue
            if side_of[a] == side_of[b]:
                area = courts[a].intersection(courts[b]).area
                if area > 1e-6:
                    overlaps.append({"components": [a, b], "area_mm2": _r(area)})
    scoped = _scoped_vias(m, chains, scope)
    vias = [
        {"via": n.key, "pos": [_r(n.pos[0]), _r(n.pos[1])]}
        for i, n in enumerate(m.nodes)
        if n.kind == "via"
        and (scoped is None or i in scoped)
        and not inside.contains(n.shape)
    ]
    failing_off = [o for o in off if "overhang" not in o]
    return {
        "off_board": off,
        "courtyard_overlaps": overlaps,
        "vias_outside_board": vias,
        "met": not (failing_off or overlaps or vias),
    }


def run(rd: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Write checks.json for ``config`` and return its summary."""
    config = {**DEFAULTS, **config}
    m = _Model(rd)
    ring = float(config["neck_down_mm"])  # step-down legs, for require_pour
    scope = list(config.get("scope") or [])
    chains = _chains(m)
    circ = _circuitousness(
        m, chains, float(config["ratio_limit"]), config.get("si_nets", []), scope
    )
    edges = circ.pop("edges")
    power = _power(m, config, ring, edges if scope else None)
    loops = _loops(m, config)
    decaps = _decap_vias(m, config, scope)
    vias = _via_plan(m, chains, float(config["via_reach_mm"]), scope)
    connectivity = _connectivity(m, scope)
    sanity = _sanity(m, chains, dict(config.get("overhang") or {}), scope)
    cannot = [
        (
            "decoupling vias joined to their pad through a pour or a control "
            "point, not a single trace"
        ),
        (
            "via plan: connections that end at a plane via, a branch, a control "
            "point or a bare trace end, and vias joined to a pad through a pour; "
            "a via joined only through a pour whose fill has not come back "
            "reads as dangling"
        ),
        (
            "connectivity: copper joined only through a part (a net tie or a "
            "jumper), and pads of unplaced components (listed as unchecked)"
        ),
        (
            "sanity: keep-outs, copper-to-edge clearance, and anything off the "
            "outline other than courtyards and vias"
        ),
        "via barrel height in loop areas",
        (
            "IR drop and inductance: temperature rise, frequency (both are "
            "quasi-static), contact resistance, mutual inductance between "
            "hops or nets, capacitor ESL, package inductance, removed "
            "non-functional pads, and copper outside each path's window"
        ),
    ]
    if m.fill_unknown:
        cannot.append(
            "pours whose fill has not come back (sync and rerun): "
            + ", ".join(sorted(set(m.fill_unknown))[:LIST_LIMIT])
        )
    polygons = {
        n: v["polygon_routes"] for n, v in power["nets"].items() if v["polygon_routes"]
    }
    if polygons:
        cannot.append(
            "route copper that came back as a polygon, not width-checked "
            "(the IR estimate includes it): "
            + "; ".join(f"{n}: {', '.join(r)}" for n, r in polygons.items())
        )
    if not config.get("power"):
        cannot.append("power width: no nets named in power")
    if not config.get("power_paths"):
        cannot.append("IR drop: no power_paths named")
    if not config.get("loops"):
        cannot.append("hot loops: none named in loops")
    written = _write(
        "checks.json",
        {
            "config": config,
            "circuitousness": circ,
            "power": power,
            "loops": loops,
            "decap_vias": decaps,
            "vias": vias,
            "connectivity": connectivity,
            "sanity": sanity,
        },
    )
    return {
        "written": written,
        "scope": scope or None,
        "circuitousness": {
            k: circ[k]
            for k in (
                "limit",
                "connections",
                "with_ratio",
                "max",
                "median",
                "over_limit",
            )
        }
        | {
            "worst": [
                {
                    k: c[k]
                    for k in (
                        "net",
                        "ends",
                        "end_kinds",
                        "length",
                        "distance",
                        "ratio",
                        "vias",
                    )
                }
                for c in circ["worst"][:LIST_LIMIT]
            ],
            "si_nets": [
                {k: c[k] for k in ("net", "ends", "ratio")}
                for c in circ["si_nets"][:LIST_LIMIT]
            ],
            "unmeasured": circ["unmeasured"][:LIST_LIMIT],
        },
        "power": {
            "nets": {
                n: {
                    "rule": v["rule"],
                    "narrowest": v["narrowest"],
                    "met": v["met"],
                    "narrower_than_rule": v["narrower_than_rule"][:LIST_LIMIT],
                }
                for n, v in power["nets"].items()
            },
            "paths": [
                {
                    k: p[k]
                    for k in (
                        "net",
                        "from",
                        "to",
                        "met",
                        "trace_hops",
                        "trace_length",
                        "ir",
                        "error",
                    )
                    if k in p
                }
                | {
                    "trace_legs": [
                        h for h in p.get("hops", []) if h["kind"] == "trace"
                    ][:LIST_LIMIT]
                }
                for p in power["paths"]
            ],
            "errors": power["errors"],
        },
        "loops": [
            {
                k: lp[k]
                for k in ("cap", "pads", "area_mm2", "target_mm2", "met", "error")
                if k in lp
            }
            for lp in loops
        ],
        "decap_vias": {
            "capacitors": len(decaps),
            "met": sum(1 for d in decaps if d["met"]),
            "not_met": [
                {
                    "cap": d["cap"],
                    "via_gap": d["via_gap"],
                    "pad_pitch": d["pad_pitch"],
                    "placements": [
                        v["placement"] for p in d["pads"] for v in p["vias"]
                    ],
                    "opposite_sides": d.get("opposite_sides", False),
                }
                for d in decaps
                if not d["met"]
            ][:LIST_LIMIT],
        },
        "vias": {
            k: v
            for k, v in vias.items()
            if k not in ("failing", "dangling", "via_in_pad")
        }
        | {
            "dangling_count": len(vias["dangling"]),
            "dangling": vias["dangling"][:LIST_LIMIT],
            "via_in_pad_count": len(vias["via_in_pad"]),
            "via_in_pad": vias["via_in_pad"][:LIST_LIMIT],
        }
        | {
            "failing": [
                {
                    "net": c["net"],
                    "ends": c["ends"],
                    "vias": c["vias"],
                    "placement": [
                        {k: v[k] for k in ("via", "from_end", "far_layer")}
                        | {k: True for k in ("far_from_end", "redundant") if v[k]}
                        for v in c["placement"]
                    ],
                }
                for c in vias["failing"][:LIST_LIMIT]
            ]
        },
        "connectivity": {
            "met": connectivity["met"],
            "checked": connectivity["checked"],
            "split": [
                {
                    "net": n,
                    "groups": connectivity["nets"][n]["groups"],
                    "group_pads": connectivity["nets"][n]["group_pads"],
                }
                for n in connectivity["split"][:LIST_LIMIT]
            ],
            "unknown": connectivity["unknown"][:LIST_LIMIT],
            "unchecked_pad_count": len(connectivity["unchecked_pads"]),
            "unchecked_pads": connectivity["unchecked_pads"][:LIST_LIMIT],
        },
        "sanity": {
            "met": sanity["met"],
            **{
                k: sanity[k][:LIST_LIMIT]
                for k in ("off_board", "courtyard_overlaps", "vias_outside_board")
            },
        },
        "cannot_measure": cannot,
        "lists_truncated_at": LIST_LIMIT,
    }


def main(rd: Any) -> dict[str, Any]:
    """Run the checks with checks-config.json, or the defaults without it."""
    path = Path.cwd() / OUT_DIR / CONFIG
    config = json.loads(path.read_text()) if path.exists() else {}
    return run(rd, config)
