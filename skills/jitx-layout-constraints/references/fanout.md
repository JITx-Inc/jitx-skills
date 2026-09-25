# Fanout and package escape owners

- Rule ladder: [skill workflow](../SKILL.md#workflow) and
  `jitxexamples.patterns.complete_rules`.
- QFN pad measurement, adjacent-gap derivation, and worked escape:
  `jitxexamples.patterns.qfn_power_fanout`. Apply the
  [manufacturable width derivation](../SKILL.md#workflow) in place of its
  historical 1 nm subtraction; that receipt does not verify the new width.
- Route and control-point APIs: installed `jitx.circuit` and `jitx.controlpoint`;
  [physical-layout verification](../../jitx-physical-layout/SKILL.md#verification)
  owns capture. Width checks belong to `jitxlib.verify` and the
  [constraint verification gate](../SKILL.md#verification).
- `RoutingStructure.NeckDown`: installed `jitx.si` owns the substrate
  definition; use tagged route segments for code-side escapes.

BGA and passive derivations have no worked owner and remain below, with their
shared pad-query helper. Source line citations refer to a 4.4.0 install;
confirm them against installed source. Neither derivation has a captured
reference result.

## Shared support for the unowned derivations

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
composition rule are in [geometry evidence](../../jitx-physical-layout/references/geometry-verification.md#coordinate-frames).

A generated landpattern (`SMT("0805")`, the QFN generator) is built lazily.
If nothing has touched its pads before the `query(design, Copper)` walk runs
inside a `Design.Initialized` hook, the build fires inside the walk and fails
with `ContextMissingException: CurrentPad is not active`. Declare an explicit
`PadMapping` in the component's `__init__` (or otherwise touch
`landpattern.p` there) so the landpattern is built inside the component's own
context before any query reads it.

The fabrication floor comes from the selected substrate:

```python
fab = design.substrate.constraints
floor_width = fab.min_copper_width
floor_space = fab.min_copper_copper_space
```

Use the same manufacturable width policy for every pad/channel limit:

```python
from collections.abc import Sequence
from decimal import Decimal, ROUND_FLOOR
from jitx.substrate import FabricationConstraints

GEOMETRY_TOLERANCE = 1e-6  # skill default: 1e-6 mm comparison tolerance
ESCAPE_PAD_INSET = Decimal("0.02")  # complete_rules guideline default, mm
FANOUT_WIDTH_GRID = Decimal("0.01")  # complete_rules guideline default, mm

# No source on this machine establishes an escape spacing margin, and none is
# invented here. Bind it from the design's own spacing budget before calling
# the helpers below; there is no skill default.
CLEARANCE_MARGIN: float

def strictly_inside_width(limit: float, floor: float) -> float:
    """Subtract the pad margin, round down to the grid, then check the fab floor."""
    steps = (Decimal(str(limit)) - ESCAPE_PAD_INSET) / FANOUT_WIDTH_GRID
    width = float(steps.to_integral_value(rounding=ROUND_FLOOR) * FANOUT_WIDTH_GRID)
    if not width < limit:
        raise ValueError("escape is not strictly below its measured limit")
    if width < floor:
        raise ValueError("escape is below the fabrication copper floor")
    return width
```

## BGA, diagonal channel and row depth

Unverified: no built reference case exercises this helper yet. Treat it as the
intended shape and verify the realized width after capture before relying on
it; the QFN pattern is the one with a captured reference.

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
    rule_pads: Sequence[Pad],
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
    rule_pad_widths = []
    for pad in rule_pads:
        minx, miny, maxx, maxy = pad_copper[pad].bounds
        rule_pad_widths.append(min(maxx - minx, maxy - miny))
    pad_width = min(rule_pad_widths)
    channel_width = diagonal_gap - 2.0 * fab.min_copper_copper_space
    escape_width = strictly_inside_width(
        min(pad_width, channel_width),
        fab.min_copper_width,
    )
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
mechanics in [control points](../../jitx-physical-layout/references/control-points.md); the package plan does not
change them.

## Two-terminal passive, terminal gap and courtyard

Unverified: no built reference case exercises this helper yet; verify the
realized width after capture before relying on it.

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
    rule_pads: Sequence[Pad],
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
    rule_pad_widths = []
    for pad in rule_pads:
        bounds = pads[pad].bounds
        rule_pad_widths.append(
            min(bounds[2] - bounds[0], bounds[3] - bounds[1])
        )
    narrowest_rule_pad_width = min(rule_pad_widths)
    between_pad_limit = min(
        narrowest_rule_pad_width,
        pad_gap - 2.0 * fab.min_copper_copper_space,
    )
    between_pad_width = strictly_inside_width(
        between_pad_limit,
        fab.min_copper_width,
    )
    outward_escape_width = strictly_inside_width(
        narrowest_rule_pad_width,
        fab.min_copper_width,
    )
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
