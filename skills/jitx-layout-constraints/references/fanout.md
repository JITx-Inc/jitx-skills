# Fanout and Package Escape Rules

Use this reference when a net-class width reaches a package whose pad or
channel cannot accept it. Keep the class rule. Split the physical path at a
control point, tag only the short escape segment, and let a higher-priority
package rule set that segment's width and clearance.

This page owns the package geometry derivation. The complete rule surface is
in `rule-reference.md`. Route and control-point mechanics are in
`jitx-physical-layout/references/control-points.md`. Coordinate composition and
capture are in
`jitx-physical-layout/references/geometry-verification.md`.

## The rule ladder

The default board rules are priority zero. A class rule is priority two in
this example, rung three is reserved for layer-scoped class overrides, and
each concrete escape tag gets one unary width rule and one binary clearance
rule at priority four (the ladder in `SKILL.md`, "Priority"). The factory chooses the rule class
from the positional condition count (`jitx/constraints.py:70-111`), unary
rules expose `trace_width` (`jitx/constraints.py:910-922`), and binary rules
expose `clearance` (`jitx/constraints.py:1135-1172`).

```python
from jitx.constraints import AnyObject, Tag, design_constraint

POWER_WIDTH = 0.5  # skill default: 0.5 mm power-class width

class PowerTag(Tag): ...
class EscapeTag(Tag): ...
class QfnEscapeTag(EscapeTag): ...
class BgaEscapeTag(EscapeTag): ...
class PassiveEscapeTag(EscapeTag): ...
class Qfn1v8EscapeTag(EscapeTag): ...

# Every width and clearance below comes from the geometry helpers.
self.rules = [
    design_constraint(PowerTag(), priority=2).trace_width(POWER_WIDTH),
    design_constraint(QfnEscapeTag(), priority=4).trace_width(qfn_width),
    design_constraint(QfnEscapeTag(), AnyObject, priority=4).clearance(
        qfn_clearance
    ),
    design_constraint(BgaEscapeTag(), priority=4).trace_width(bga_width),
    design_constraint(BgaEscapeTag(), AnyObject, priority=4).clearance(
        bga_clearance
    ),
    design_constraint(PassiveEscapeTag(), priority=4).trace_width(
        passive_width
    ),
    design_constraint(
        PassiveEscapeTag(), AnyObject, priority=4
    ).clearance(passive_clearance),
    design_constraint(Qfn1v8EscapeTag(), priority=4).trace_width(
        qfn_1v8_width
    ),
    design_constraint(
        Qfn1v8EscapeTag(), AnyObject, priority=4
    ).clearance(qfn_1v8_clearance),
]
```

Use a package-family tag when every escape in that family has the same derived
values. If one rail differs, use a concrete rail tag such as
`Qfn1v8EscapeTag` and its own rule pair. Do not also tag that segment with
`QfnEscapeTag`, so there is one winning pair of effects.

One generic `EscapeTag` rule hides why a value changed and assumes QFN rows,
BGA channels, and passive courtyards produce the same result. They do not.
Specific tags make the package and rail intent readable at the route.

Tag subclasses belong at module scope. Tag assignments and rule objects must
be structural attributes under the `Design`; lists are traversed. See
`rule-reference.md`, "Rule classes", for the source-backed mechanics.

## Read placed pad copper once

The installed query engine converts pads to copper. A query result stays in
the source's local frame, so compose the query trace with the copper shape
before measuring (`jitx/query.py:187-263`,
`jitx/landpattern.py:173-206`). The query must start at the design because it
opens the design and substrate contexts.

```python
from collections import defaultdict
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from jitx import Design
from jitx.copper import Copper
from jitx.inspect import visit
from jitx.landpattern import Landpattern, Pad
from jitx.query import query

def placed_pad_polygons(
    design: Design,
    landpattern: Landpattern,
    layer: int,
) -> dict[Pad, BaseGeometry]:
    """Pad copper in the design frame, keyed by the structural Pad."""
    pads = [pad for _, pad in visit(landpattern, Pad)]
    by_identity = {id(pad): pad for pad in pads}
    shapes: dict[int, list[BaseGeometry]] = defaultdict(list)
    for trace, copper in query(design, Copper):
        parent_id = id(trace.parent)
        if parent_id not in by_identity or copper.layer != layer:
            continue
        if trace.transform is None:
            raise ValueError(f"unresolved pad frame at {trace.path}")
        placed = copper.shape.at(trace.transform).to_shapely().g
        shapes[parent_id].append(placed)
    result: dict[Pad, BaseGeometry] = {}
    for pad_id, pad in by_identity.items():
        if not shapes[pad_id]:
            raise ValueError(f"pad query returned no copper for {pad}")
        result[pad] = unary_union(shapes[pad_id])
    return result
```

Do not read `pad.transform` alone. A composite landpattern adds frames above
the pad, and bottom-side placement adds mirroring. The full failure mode and
composition rule are in `geometry-verification.md`, "Coordinate frames".

The fabrication floor comes from the selected substrate:

```python
fab = design.substrate.constraints
floor_width = fab.min_copper_width
floor_space = fab.min_copper_copper_space
```

The four enforced fabrication fields and their precedence over design rules
are summarized in `rule-reference.md`, "What the rules sit on". Do not copy a
fabricator value into an escape helper.

## QFN, adjacent-pad gap and pad width

The `jitxlib` QFN generator places four rows from a lead profile, and the
profile carries the row pitch (`jitxlib/landpatterns/generators/qfn.py:115-134`,
`jitxlib/landpatterns/quad.py:123-145`). `DensityLevel` selects the
IPC-7351 land-protrusion goal. IPC-7351 is the standard implemented by the
generator, not an escape-width table.

Measure the emitted copper. For a pad on a left or right row, pad width is its
Y extent. For a pad on a top or bottom row, pad width is its X extent. The
nearest pad with the same radial coordinate is the adjacent pad in that row.
Its center distance is the realized pitch, and polygon distance is the
realized edge gap.

```python
from dataclasses import dataclass
from math import isclose
from shapely.geometry.base import BaseGeometry

from jitx.landpattern import Pad
from jitx.substrate import FabricationConstraints

GEOMETRY_TOLERANCE = 1e-6  # skill default: 1e-6 mm comparison tolerance
CLEARANCE_MARGIN = 0.01  # skill default: 0.01 mm above the fab floor

@dataclass(frozen=True)
class QfnEscapeGeometry:
    pad_width: float
    adjacent_gap: float
    row_pitch: float
    pad_depth: float
    escape_width: float
    escape_clearance: float

def qfn_escape_geometry(
    pad_copper: dict[Pad, BaseGeometry],
    target_pad: Pad,
    package_center: tuple[float, float],
    fab: FabricationConstraints,
) -> QfnEscapeGeometry:
    target = pad_copper[target_pad]
    minx, miny, maxx, maxy = target.bounds
    center = ((minx + maxx) / 2.0, (miny + maxy) / 2.0)
    delta = (center[0] - package_center[0], center[1] - package_center[1])
    radial_is_x = abs(delta[0]) >= abs(delta[1])
    radial_index = 0 if radial_is_x else 1
    tangent_index = 1 - radial_index
    neighbors: list[tuple[float, BaseGeometry]] = []
    for pad, geometry in pad_copper.items():
        if pad is target_pad:
            continue
        gx0, gy0, gx1, gy1 = geometry.bounds
        other_center = ((gx0 + gx1) / 2.0, (gy0 + gy1) / 2.0)
        if not isclose(
            other_center[radial_index],
            center[radial_index],
            abs_tol=GEOMETRY_TOLERANCE,
        ):
            continue
        row_delta = abs(other_center[tangent_index] - center[tangent_index])
        neighbors.append((row_delta, geometry))
    if not neighbors:
        raise ValueError("target QFN pad has no neighbor in its row")
    row_pitch, neighbor = min(neighbors, key=lambda item: item[0])
    pad_width = maxy - miny if radial_is_x else maxx - minx
    pad_depth = maxx - minx if radial_is_x else maxy - miny
    adjacent_gap = row_pitch - pad_width
    if not isclose(adjacent_gap, target.distance(neighbor), abs_tol=GEOMETRY_TOLERANCE):
        raise ValueError("QFN row pads are not a uniform pitch-minus-width channel")
    floor_space = fab.min_copper_copper_space
    channel_limit = pad_width + 2.0 * (adjacent_gap - floor_space)
    escape_width = min(pad_width, channel_limit)
    if escape_width < fab.min_copper_width:
        raise ValueError("no QFN escape meets the fabrication copper floor")
    escape_clearance = floor_space + CLEARANCE_MARGIN
    return QfnEscapeGeometry(
        pad_width,
        adjacent_gap,
        row_pitch,
        pad_depth,
        escape_width,
        escape_clearance,
    )
```

The centered-channel limit asks how far a trace may extend from the target
pad center before it violates the floor at the neighboring pad. The result is
capped at the target pad width. When the adjacent gap already exceeds the fab
floor, the pad width is the governing limit. If the result falls below
`min_copper_width`, the package and process have no legal routed escape under
this model. Stop instead of typing a narrower value.

### Worked power escape

The class trunk in this example is `0.5 mm` (skill default: `0.5 mm` power
class width). The QFN pitch and pad size are read from the generated
landpattern. `Route` accepts a `RoutePoint`, converts it to `.pad`, and accepts
`sketch=` as a point sequence (`jitx/circuit.py:569-599`). `RoutePoint.pad` is
the routing endpoint (`jitx/controlpoint.py:61-76`).

```python
from jitx import RoutePoint
from jitx.circuit import Route
from jitx.constraints import AnyObject, Tags, design_constraint

POWER_WIDTH = 0.5  # skill default: 0.5 mm power-class width
ESCAPE_RUN = 1.0  # skill default: 1.0 mm from pad edge to transition

# pad_copper came from placed_pad_polygons(...).
geometry = qfn_escape_geometry(
    pad_copper,
    qfn_power_pad,
    package_center=qfn_center,
    fab=design.substrate.constraints,
)
pad_center = qfn_power_pad_geometry.centroid.coords[0]
outward = qfn_outward_unit_vector
transition = (
    pad_center[0] + outward[0] * (geometry.pad_depth / 2.0 + ESCAPE_RUN),
    pad_center[1] + outward[1] * (geometry.pad_depth / 2.0 + ESCAPE_RUN),
)
self.rp = RoutePoint(layer=top_copper_layer).at(transition)
self.power_net += self.rp.port
self.trunk_route = Route(trunk_port, self.rp, top_copper_layer)
self.escape_route = Route(
    self.rp,
    qfn_power_pad,
    top_copper_layer,
    sketch=[transition, pad_center],
)
Tags(QfnEscapeTag()).assign(self.escape_route)
self.escape_rules = [
    design_constraint(QfnEscapeTag(), priority=4).trace_width(
        geometry.escape_width
    ),
    design_constraint(
        QfnEscapeTag(), AnyObject, priority=4
    ).clearance(geometry.escape_clearance),
]
```

`sketch=` is the code-side handle on the escape path. It does not set width or
clearance. The tag selects the two rules. Both routes, the control point, and
the rule list stay on `self`, so the design-tree walk can reach them.

For a single-ended escape, tag the route segment. For a differential
structure, tag the net. Per-route differential tags can deform the control
point transition. See `control-points.md`, "Route", for that rule. Place a
route at the common ancestor required by `control-points.md`, "Circuit
ownership". Do not restate the ownership tree in local helpers.

## BGA, diagonal channel and row depth

The BGA generator places circular pad lands on a grid. Its `ball_diameter`
argument becomes the PCB pad-circle diameter, and its pitch becomes the X and
Y center spacing (`jitxlib/landpatterns/generators/bga.py:63-103`). Read the
placed pad polygons anyway, since depopulated and nonuniform arrays change the
available channels.

For a diagonal channel, select the nearest candidate whose X and Y center
deltas are both nonzero. The polygon distance is the diagonal edge gap. A
trace centered in that channel may be no wider than the diagonal gap minus a
fab clearance on each side, and it is still capped at the target pad width.
The row depth is the radial center distance from the target row to the
outermost populated row. Both values come from emitted copper.

```python
def bga_channel_geometry(
    pad_copper: dict[Pad, BaseGeometry],
    target_pad: Pad,
    package_center: tuple[float, float],
    fab: FabricationConstraints,
):
    target = pad_copper[target_pad]
    tx, ty = target.centroid.coords[0]
    candidates: list[tuple[float, BaseGeometry]] = []
    centers: list[tuple[float, float]] = []
    for pad, geometry in pad_copper.items():
        cx, cy = geometry.centroid.coords[0]
        centers.append((cx, cy))
        if pad is target_pad:
            continue
        dx, dy = abs(cx - tx), abs(cy - ty)
        if dx <= GEOMETRY_TOLERANCE or dy <= GEOMETRY_TOLERANCE:
            continue
        candidates.append((dx * dx + dy * dy, geometry))
    if not candidates:
        raise ValueError("target BGA pad has no diagonal channel")
    _, diagonal_neighbor = min(candidates, key=lambda item: item[0])
    diagonal_gap = target.distance(diagonal_neighbor)
    minx, miny, maxx, maxy = target.bounds
    pad_width = min(maxx - minx, maxy - miny)
    channel_width = diagonal_gap - 2.0 * fab.min_copper_copper_space
    escape_width = min(pad_width, channel_width)
    if escape_width < fab.min_copper_width:
        raise ValueError("no BGA channel meets the fabrication copper floor")
    radial_is_x = abs(tx - package_center[0]) >= abs(ty - package_center[1])
    axis = 0 if radial_is_x else 1
    outer = max(abs(center[axis] - package_center[axis]) for center in centers)
    target_radius = abs((tx, ty)[axis] - package_center[axis])
    row_depth = outer - target_radius
    clearance = fab.min_copper_copper_space + CLEARANCE_MARGIN
    return diagonal_gap, row_depth, pad_width, escape_width, clearance
```

Plan row-to-layer assignment before drawing routes. The outer populated row
escapes on the first available signal layer. The next inward row uses the next
available signal layer, and the plan continues inward only while the derived
channel and via geometry remain legal. Build the row order from pad centers
and the layer order from the selected substrate. Store the resulting mapping
beside the routes. For differential lanes, use the net-tag and control-point
mechanics already documented in `control-points.md`; the package plan does not
change them.

## Two-terminal passive, terminal gap and courtyard

A two-terminal passive has two separate questions. The pad-to-pad gap governs
a path or via placed between the terminals. The courtyard bounds govern how
far an outward escape may run before it enters neighboring component space.
Read both from the generated landpattern.

```python
from jitx.feature import Courtyard

def passive_geometry(
    design: Design,
    landpattern: Landpattern,
    layer: int,
    fab: FabricationConstraints,
):
    pads = placed_pad_polygons(design, landpattern, layer)
    if len(pads) != 2:  # landpattern query source: two terminal pads
        raise ValueError("expected a two-terminal passive landpattern")
    pad_items = list(pads.items())
    first = pad_items[0][1]
    second = pad_items[1][1]
    pad_gap = first.distance(second)
    courtyard_shapes: list[BaseGeometry] = []
    for trace, courtyard in visit(landpattern, Courtyard):
        if trace.transform is None:
            raise ValueError(f"unresolved courtyard frame at {trace.path}")
        courtyard_shapes.append(
            courtyard.shape.at(trace.transform).to_shapely().g
        )
    if not courtyard_shapes:
        raise ValueError("passive landpattern has no courtyard")
    courtyard = unary_union(courtyard_shapes)
    first_bounds = first.bounds
    first_pad_width = min(
        first_bounds[2] - first_bounds[0],
        first_bounds[3] - first_bounds[1],
    )
    between_pad_limit = pad_gap - 2.0 * fab.min_copper_copper_space
    between_pad_width = min(first_pad_width, between_pad_limit)
    outward_escape_width = first_pad_width
    escape_clearance = fab.min_copper_copper_space + CLEARANCE_MARGIN
    return (
        pad_gap,
        courtyard.bounds,
        between_pad_width,
        outward_escape_width,
        escape_clearance,
    )
```

Use `between_pad_width` only when the authored path actually passes between
the terminals. Use `outward_escape_width` for a route leaving a terminal away
from the other pad. In either case, cap at the pad width and fail if the result
is below `min_copper_width`. The courtyard is a placement envelope, not an
escape-width source (`jitx/feature.py:177-194`).

## Not NeckDown

`RoutingStructure.NeckDown` only supplies parameters for a neckdown region;
the installed code surface provides no route-side region activator
(`jitx/si.py:553-575`). Those parameters take effect when a region is
activated in the UI. A specific escape tag keeps the code-side intent visible
to readers and rules, so this skill does not use it for package escapes.

## What to check after build

Follow `SKILL.md`, "Verification", after capture. A clean build is not width
evidence. Both authored routes must have non-empty `route.traces`, and every
realized polyline on each route must carry the winning width. Captured route
shapes and their width fields are defined in `jitx/circuit.py:545-562` and
`jitx/shapes/primitive.py:285-317`.

```python
from jitx.shapes.primitive import ArcPolyline, Polyline

def realized_widths(route: Route) -> tuple[float, ...]:
    assert route.traces, f"unrealized route: {route}"
    widths: list[float] = []
    for trace in route.traces:
        for shape in trace.shapes:
            primitive = shape.to_primitive().geometry
            if isinstance(primitive, ArcPolyline | Polyline):
                widths.append(primitive.width)
    assert widths, f"route has no realized polyline width: {route}"
    return tuple(widths)

assert all(width == POWER_WIDTH for width in realized_widths(circuit.trunk_route))
assert all(
    width == circuit.escape_geometry.escape_width
    for width in realized_widths(circuit.escape_route)
)
```

Use a small numeric tolerance in an executable check to absorb serialization
noise. Label that tolerance as a skill default on the line that defines it.
Print the derived pad width, governing gap, clearance, and both measured route
widths so a reviewer can compare the requested rule values with captured
copper.
