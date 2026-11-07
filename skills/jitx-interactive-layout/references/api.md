# Interactive layout API reference

Signatures from `jitx.run.layout` and `jitx.issue`. The module is marked
experimental; when a call is refused with an argument error, read
the installed source (`python -c "import jitx.run.layout, inspect;
print(inspect.getsource(jitx.run.layout.SyncBatch))"`).

## Imports

```python
from jitx.run.layout import RequestRejected, RouteSetting
from jitx.copper import Pour
from jitx.feature import KeepOut, Cutout
from jitx.shapes.hull import ConvexHull
from jitx.layerindex import Side, LayerSet
from jitx.placement import Placement
from jitx.landpattern import Pad
from jitx.circuit import Route
from jitx.via import Via
from jitx.controlpoint import ControlPoint
from jitx.component import Component
from jitx.proxy import typeof
from jitx.issue import (
    IssueCategory, Severity, CategoryStatus,
    BlockedPath, DroppedRoute, MissingRoute, UnroutedTopology, UnassignedPin,
    TimingIssue, UnmetTime, UnmetTimeDiff, UnmetLoss, UnrealizedRoute,
    UnsquiggledRoute,
    GeometricOverlap,
)
```

## Script shape

```python
def main(rd) -> dict:
    reg = rd.root.circuit.reg_3v3          # the design tree, as in the source
    L = rd.layout
    with L.batch() as b:
        b.place(reg.buck, (-15.0, -15.0), 0, on=Side.Top)
        b.place(reg.c_in, (-13.2, -14.75), 90, on=Side.Top)
    r = L.route(reg.buck.landpattern.p[3], reg.c_in.landpattern.p[1], 0)
    L.sync(timeout=20)
    route = r.route
    return {"routed": route is not None and route.status is not None and route.status.routed}
```

`exec` prints the return value as JSON. Keep it small; write bulk data to a
file under `.jitx/`.

## Requests

Every request exists on `rd.layout` (sent at once) and on a batch from
`rd.layout.batch()` (sent together at the end of the `with` block). Direct
`rd.layout.route` and `rd.layout.via` take `wait=True` by default and return
after the runtime has routed them. Points
are `(x, y)` board-absolute millimetres. `layer` counts copper layers from
the top; negative counts from the bottom.

### place

```python
place(component, (x, y) | Placement | None, rotation=None, *, on=Side | None)
```

Board-absolute; rotation in degrees, counter-clockwise. Omitted aspects keep
their current value. Placing the same component again in one batch applies to
its earlier placement in that batch. `rd.layout.place` returns the
`Placement`; a batch's `place` returns a `PendingPlacement` whose
`.placement` is set after the batch is sent.

### route

```python
route(start, end, layer, *, turns=None, width=None, space=None,
      pair_space=None, envelope_overhead=None, pour=None)
```

- `turns=None` autoroutes, like a UI autoroute. A list of points guides the
  route past them, autorouting where it cannot follow; `[]` is a straight
  sketch. The list holds only the points between the endpoints. A turn picks
  which side of an obstacle the route passes; the router then pulls the
  route tight, so do not expect it to pass exactly through the point. To
  hold a route to a path where no obstacle forces a side (around a part's
  body rather than under it), end the first leg at a `route_point` on the
  path and route on from it.
- `width`, `space`, `pair_space`: None takes the design's constraints. Set
  them only with a reason: the design's rules, or a fine-pitch pad
  narrower than the rule's width (see `general-pnr.md`, Route order). A
  `space` wider than the gap a pin allows leaves the route blocked.
- `envelope_overhead`: extra width of the region the trace may meander in
  for length matching; `0` disables length matching for this route; None
  takes the constraints.
- `pour=True` grows the route's copper into a pour filling the free space
  around it.
- A route with no path is kept, blocked, and may route later. The net comes
  from the endpoints.
- Endpoints: a pad, a port mapped to one pad, a via, a control point. Only
  points that are neighbours in a topology chain can be joined directly; a
  request between non-adjacent points can be refused as not connectable.
  Plan routes along the chain.

Returns `PendingRoute`: `.key` once sent, `.route` (the `Route`) once the
runtime reports it; follow with `sync` to wait for that.

### via

```python
via(definition, origin_pad, (x, y), layer, *, turns=None, force=False,
    width=None, space=None)
```

- `definition`: a `Via` subclass from the substrate, an instance, or its
  name. Find the definitions with `typeof(rd.root.substrate).__mro__` and the
  nested `Via` subclasses in each class's `__dict__`; `layout_report.py`
  lists them in `state.json`.
- Joined to `origin_pad` by a route on `layer`; `width` and `space` apply
  to that route, as for `route`. Set `width` at a fine-pitch pad (see
  `general-pnr.md`, Route order).
- Without `force` the via moves to the nearest free spot. That search reaches
  only a short distance; compute a clear
  spot yourself rather than relying on it.
- With `force=True` the via goes exactly at the point, clear or not. A
  forced via on a pad whose definition has no via-in-pad is placed and its
  route comes out blocked, reported as `BlockedPath`; no `GeometricOverlap`
  is reported for it.

Returns `PendingVia`: `.key`, `.position` (after any move) once sent; `.route`
(the origin route, or None if via and pad coincide); `.via` once reported.
Inside a batch the handle is pending until the batch is sent (`.key` raises
"via is pending until the batch is sent"), so use the via as an endpoint, a
`net=` or a hull anchor in a later batch or call. The same holds for a
`PendingControlPoint`.

### route_point

```python
route_point(origin, (x, y), layer, *, radius=None, size=None, turns=None,
            width=None, space=None)
```

A single-ended control point routed from `origin`. Routes continue from it.
`radius` makes it circular, `size=(w, h)` rectangular; both must be
positive. Use it to bend a route around something, to give a hull pour an
extra anchor, or as the end of a pin escape.

### Differential pairs

```python
pair_insertion((p, n), (x, y), rotation, layer, *, invert=False,
               width=None, space=None, pair_space=None)
drop_pair_insertion((p, n), layer, *, pull=None, width=None, space=None,
                    pair_space=None)
pair_point(origin_control, (x, y), rotation, layer, *, turns=None,
           width=None, space=None, pair_space=None)
```

- `pair_insertion` is where the p and n traces from their pads merge into a
  coupled pair; at rotation 0 the coupled side points along +x. `invert`
  swaps the sides when the traces would otherwise cross.
- `drop_pair_insertion` places it next to the pads, between them and pointing
  away from the component, at the nearest clear spot, with sides chosen so
  the traces do not cross. Refused if there is no room.
- `pair_point` continues the coupled route from an insertion or another pair
  point. End a pair route at a second insertion near the far pads.
- The invert state of insertions on pin-assigned pairs is not tracked when
  the assignment re-solves, so P and N can swap. Re-read after a re-solve.

### region

```python
region(feature, *, origin=None, net=None)
```

- `feature`: `Pour(shape, layer, rank=)`, `KeepOut(shape, LayerSet(...),
  pour=, via=, route=)`, `Cutout(shape)`, or a surface feature. The shape is
  a board-absolute shape or a `ConvexHull(anchors, expand=)`.
- `ConvexHull` anchors are pads, vias, control points, ports (all their
  pads) or components (all their pads). The runtime keeps the hull around
  them as they move. `expand` grows it; give it enough that thermal spokes
  reach the pads.
- `net` is required for a pour (a net, or a pad, port or via on it) and
  refused for anything else.
- `origin` makes the region move and flip with a component or one of its
  pads, vias or control points.

Returns `PendingRegion`: `.key`, `.region` once reported.

### Changing and removing

```python
modify(route, *, turns=None, width=None, space=None, pair_space=None,
       envelope_overhead=None, pour=None, reset=[RouteSetting.Width, ...])
update_via(via, *, position=None, definition=None, force=False)
update_control(control, *, position=None, rotation=None, invert=False,
               radius=None, size=None)
update_region(region, *, shape=None, layers=None, side=None, rank=None,
              pour=None, via=None, route=None, name=None, origin=None, net=None)
delete(*objects)
sync(timeout=None) -> bool
```

- `modify` reroutes as needed. `reset` returns settings to the constraints.
  A route created in code can be modified except for what its code sets.
- `update_via`, `update_control` and `update_region` act only on objects the
  runtime made (by a request or in the editor), not ones placed in code.
  Attached routes follow.
- A region's kind cannot change; delete it and create another.
- `delete` removes runtime-made routes, vias, control points and regions.
  Routes attached to a deleted via or control point are removed or joined.
  Sync before reading the tree after a delete.
- Each update refuses a call that would change nothing.
- `sync` waits until background routing and checks settle; False means it
  timed out.

## Batches

```python
try:
    with rd.layout.batch() as b:
        vias = [b.via(THVia, pad, spot, 0) for pad, spot in plane_spots]
        b.sync(20)                      # only first or last in a batch
    with rd.layout.batch() as b:        # the vias exist now
        b.route(vias[0], other_gnd_pad, 0)  # a sent PendingVia is an endpoint
        b.region(Pour(ConvexHull([sw_a, sw_b, vias[1]], expand=0.3), 0,
                      rank=5), net=sw_a)
except RequestRejected as e:
    print(e.kind, e.message, e.operation)
```

The batch is applied in order and all-or-nothing, as one undo step in the
editor. Handles resolve when the block exits, not before. `operation` is an
index into the batch's operations, which are not its calls: consecutive
placements merge into one operation, a `delete` splits into one operation per
kind of object, and `sync` counts as one. Read `message` to identify the
refused request.

## Reading the tree

- Runtime-made objects live in link containers. What existed when the
  session captured sits in `_Capture__link` on its circuit
  (`reg._Capture__link.vias.0`); what this session created sits in
  `_Links__session` at the top of the design, whichever circuit it belongs
  to (`_Links__session.vias.3`). So selecting by a circuit's key prefix
  misses everything made since the session started: select by net, by the
  pads a route ends at, or by the handles your script kept. A tree path
  through either container marks an object a request can modify or delete.
- Captured objects are proxies; `type(x)` is the proxy class. Use
  `typeof(x)` for the real class and its name.
- `rd.query(T)` yields `(trace, obj)`; `trace.path` is the tree path and
  `trace.transform * obj.transform` the board-absolute transform of a placed
  object.
- `Route`: `.source`, `.destination`, `.layer`, `.traces`, and `.status`
  (None until the runtime reports it; then `.routed` or `.blocked`). A
  blocked route has no traces. A trace's shape comes back either as arc
  elements or as a wrapped polygon `Shape`; handle both. Polygonized arcs sit
  slightly inside the true arc, so geometric measurements on them read a
  little short.
- A trace's `ArcPolyline` has `width` and `elements` (points and `Arc`s).
  `rd.nets.find(trace)` gives that trace's net; a pair route's two traces
  each carry their own, so match them by net, not by order. In a run on a
  board with pair insertions, `rd.nets.find` returned None for each
  insertion and its copper; the copper can also carry a net when the
  runtime computes one, so handle both.
  `scripts/layout_checks.py` measures lengths, widths, loops and estimates
  of DC drop and inductance from these.
- After a session restart, components inside a circuit with no placement of
  its own (`.at(floating=True)`) have `transform` None, and the vias
  captured in that circuit read in their owning component's frame. Place
  the circuit in the source (SKILL.md, Session) so this does not happen.
- `rd.nets.find(pad)`: the pad's `Net` or None.
- `rd.root.board.shape`, `rd.root.substrate.stackup.conductors`.

`scripts/layout_report.py` reads all of this into `state.json`: each route
with `source_key` and `destination_key` (the key of the pad, via or control
point each end attaches to), each pad, via and control point with `placed`,
each pour with its `fill_pieces` (0 for no copper, null while the fill has
not come back).

The link containers and their names are jitx internals and can change
between releases. Read them through `layout_report.py` or `rd.query` rather
than by attribute in your own scripts.

## Issues

```python
report = rd.issues(categories=None, satisfied=False, wait=5.0)
report.complete                      # every category finished computing
report.status(IssueCategory.ROUTING) # CategoryStatus.PENDING or COMPLETE
report.errors                        # error-severity issues
report.of(UnmetTimeDiff)             # by class, subclasses included
report.referencing(obj)              # issues naming obj, by identity
for issue in report: issue.text, issue.severity, issue.objects
```

- `satisfied=True` also returns signal-integrity measurements that pass,
  which is how to read remaining margin.
- `wait` is how long to wait for pending categories. A report with a pending
  category is partial.
- `issue.objects` is a list of `IssueObject(role, ref, instance)`. `ref` is
  often empty; `instance` is the Python object, matched by identity against
  `rd.query` results.
- `DroppedRoute`, `UnrealizedRoute`, `UnsquiggledRoute` and
  `MissingStructureModel` carry a `cause` string; `layout_report.py` copies
  it, and the timing issues' path refs when the runtime names them, into
  each issue entry.

| Class | Family | Means |
|---|---|---|
| `MissingRoute` | connectivity | A topology segment has no route |
| `UnroutedTopology` | topology | A signal path needs two points no route joins yet |
| `DuplicateRoute` | connectivity | Two routes join the same points |
| `UnconnectedTopology` | connectivity | A topology is not connected end to end |
| `UnassignedPin` | connectivity | A pin on a constrained path has no assignment |
| `BlockedPath` | connectivity | No path found for a requested route |
| `DroppedRoute` | connectivity | A route in the design code was dropped; `cause` is `not-on-layer`, `not-in-topology`, `different-nets`, `never-connectable` or `conflicting` |
| `UnmodelledVirtualConnection` | connectivity | A virtual connection on a topology segment has no pin model, so its step cannot be timed |
| `UnmetTime` | timing | Delay along one path; ranges in seconds |
| `UnmetTimeDiff` | timing | Skew between `longer_path` and `shorter_path`; seconds |
| `UnmetLoss` | loss | Insertion loss; dB |
| `UnrealizedRoute` | realization | A route could not be realized; geometry in `shapes` |
| `UnsquiggledRoute` | realization | Length tuning could not fit a serpentine |
| `GeometricOverlap` | geometry | Copper overlaps where it must not |
| `OverlappingStructure`, `MissingStructureModel` | routing structure | Routing-structure problems |
| `AmbiguousTouchingStructure` | routing structure | Several routing structures meet at a point |
| `MissingRoutingStructure` | routing structure | A route segment on a constrained path has no routing structure |
| `AmbiguousTopology`, `MissingPinModel`, `EquivalentPaths` | topology | Topology definition problems |

The family is the issue's base class (`report.of(TimingIssue)` gets both
timing types). The report's categories (`IssueCategory`) partition it for
completion status and do not classify issues.

Signal-integrity issues carry `measured_range`, `acceptable_range` (low,
high) and `satisfied`. `layout_report.py` converts them to picoseconds or dB
and adds `margin`: the distance from the measured range to the nearest
acceptable bound, negative when outside.

No issue type reports a plain net, outside any topology, that has no route.
Check those yourself.
