---
name: jitx-code-layout
description: "Use when the user asks to write a fixed PCB layout in Python: place vias, and parts relative to another instance (Circuit.place), code routes through control points (RoutePoint, PairPoint, PairInsertion), Route.Sketch, Route.Config, a Route.Target taper, narrowing a route in a BGA field or a fine-pitch pad, escape or fanout geometry fixed by a stated number or pad geometry, a connector launch on its pad axis, serpentine or deskew settings on a matched section, thermal vias in an exposed pad, pours, keepouts, cutouts, Copper or OverlappableCopper (antennas, net ties), or reading the realized layout back (capture, Empty pours, 'Unable to find path'). Sorts control points between code and jitx-interactive-layout. Tag rules, escape width rules, stitching and fencing go to jitx-layout-constraints; stackups, vias and structure definitions to jitx-substrate-modeler; land-pattern mask, paste and thermal pads to jitx-component-modeler; nets and passives to jitx-circuit-builder; timing to jitx-interconnect-constraints."
---

# JITX Code Layout

A layout in code is fixed: every build puts its control points and vias where the code says, so first decide which a designer will move ([Code or designer](#code-or-designer)). Read the result back from the capture: `status: ok` does not mean the copper exists. Explanation: [Layouts from code](https://docs.jitx.com/en/latest/essentials/physical_design/creating-layouts-from-code.html), [Pours](https://docs.jitx.com/en/latest/essentials/physical_design/pours.html).

## Environment

Invoke the base `jitx` skill first. Worked patterns are `jitxexamples` modules, which the base skill's Step 1 installs. If a named module is missing, the installed copy predates it: say so, and work from the rules here.

## Code or designer

First sort every control point, via and turn:

| Kind | Examples | Where |
|---|---|---|
| Fixed by geometry or a stated number | a connector exit on the pad axis, the split at a ball-field edge, thermal vias in a pad | code |
| A designer's choice | fanout via positions, escape bends, sketch turns | the interactive layout (`jitx-interactive-layout`), or code in a function named and documented as designer-placed (`designer_placed_fanout_points` in `qfn_thermal_and_power_fanout`) |

See [Interactive edits](#interactive-edits). Keep width, structure, net and layer in code even where positions go to the designer, and name the routes that end on each designer-owned point: they go with it.

## Placement and vias

- Fixed `.at` placement is [`jitx-circuit-builder`](../jitx-circuit-builder/SKILL.md#placement). Place parts and the copper that depends on them in one circuit, so they move together.
- `self.place(child, (x, y), relative_to=other)` records a placement request without changing the child's transform, and sets a child circuit floating: use it only to place relative to another instance.
- A circuit at `.at(floating=True)` with no stored placement sits off the board: its routes do not realize and its pours come back `Empty()`. A headless check gives every circuit a position.
- Via classes come from the substrate (`jitx-substrate-modeler`); code places instances. Join a power or ground via with `net += via`; `PortAttachment` binds a signal port to a control point or signal via.
- Store every via, copper, keepout, control point and route on `self`: geometry reachable only through a net drops out of exports.
- Stitch and fence vias come from rules (`jitx-layout-constraints`), never a hand-placed grid.

## Code routes

`Route(source, destination, layer, sketch=None, config=None)` joins two ports, pads, vias or control points on one layer. Worked pattern: `jitxexamples.patterns.code_route_basics`.

- Width, spacing and structure come from rules or a structure on the net (`jitx-layout-constraints`), or from `Route.Config`.
- A route ending on a control point in a sibling circuit fails to translate ("not an ancestor"): declare it in the common ancestor. A control point's `.port` cannot be a `Topology` end either: constrain between part ports.
- Every control point joins its net (`net += point.port`, or a `PortAttachment`), or the design fails to load ("INVALID-STATE").
- `RoutePoint.pad` routes and `.port` nets; `PairInsertion` joins `.uncoupled.p`/`.n` legs to `.coupled`; `PairPoint` joins coupled sections at `.front` and `.back`. Attach a pair in `[p, n]` order and set handedness with `invert=` (which ends join: the `PairInsertion` docstring). A reversed attachment order builds and makes no copper. "Code route dropped: its ends can never be joined" means a wrong `invert=` or end.
- A route heads for its destination, so it leaves a pad on the pad's axis only when the destination lies on that axis. Where the line must (an RF launch, a tangent exit), put a `RoutePoint` on the axis at the stated length: the route to it is straight. For a tangent bend after it, tag a GND `Copper` square inside the turn, running from the `RoutePoint` with its near side the clearance off the line's copper (nearer leaves the route unrealized); its tag's clearance rule to the line's tag is at least the structure's and outranks any rule between the line's tag and a tag reaching the square ([priority](../jitx-layout-constraints/SKILL.md#priority)): the line bends about the square's corner at half its width plus the clearance. One square, inside only; a route `KeepOut`'s edge gets no clearance. Worked pattern: `jitxexamples.patterns.rf_connector_launch`.
- A control point whose copper overlaps a via's pad gives "Unrealizable Route: Overlapping target shapes": keep the point's copper, half the route width around it, off the via pad.

### Route.Sketch

`Route.Sketch(Route.Sketch.Terminal(start), turns, Route.Sketch.Terminal(end))` tells the router which side of an obstacle to pass. A turn is a side hint, not the waypoint its `Route.Sketch.turns` docstring describes: the route bends only as far as the obstacle needs, so moving a turn further out buys no margin (a tag clearance to the obstacle does). Turns are read in the declaring circuit's frame. Report where the copper passed from the captured trace, not the turns.

### Route.Config and Route.Target

`Route.Config` overrides the rules for one route. `trace_space` is also the pour's pullback. Leave `Route.Config.pour` unset: fill around a route with a `Pour`.

A `Route.Target` that differs from the trace width tapers the whole route it is on: `Route.Target.rectangle` realizes as one polygon widening linearly to the target's extent across the trace, with no drawn trace width. To taper only at the pad, split at a `RoutePoint` and put the target on the short last route (`code_route_basics`). A taper suits widening into a wider pad but cannot hold a width over one: for copper narrower than the pad, split at a `RoutePoint` at least half the wide width past the pad edge and give the short route its own width.

## Narrowing a route

Where the full structure does not fit (a BGA ball field, a fine-pitch pad row), split the route at a `RoutePoint` or `PairPoint` and tag the narrow route. The tag's `routing_structure` rule must outrank the net's ([priority](../jitx-layout-constraints/SKILL.md#priority)). Split just outside the field or row, so the full section clears the last pads. Worked patterns: `jitxexamples.patterns.hex_bga_escape`, `jitxexamples.patterns.layout_routing_structure_by_tag`.

An impedance lookup (`substrate.differential_routing_structure(100 * ohm)`, or a protocol constraint given no `structure`) returns a structure whose `impedance` fits; two structures sharing an `impedance` make the result depend on declaration order. Give a narrow structure an `impedance` no lookup window admits (`hex_bga_escape` gives its neck 0 ohm).

## Length matching

Matched length is a timing constraint (`jitx-interconnect-constraints`), never a meander drawn in code. A section with `Route.Config(envelope_overhead=w)` may meander within `w` beyond its own copper, half each side, until the route meets its timing constraint; zero turns matching off, as does no `Config` without an interactive envelope. Worked patterns: `jitxexamples.patterns.serpentine_sections`, `jitxexamples.patterns.wilkinson_tree`.

- End a matched section on `RoutePoint`s or `PairPoint`s, which resize to fit the envelope. A small pad leaves no room (`UnsquiggledRoute`); a matched coupled section between two `PairInsertion`s does not route.
- Size each envelope for the delay its section adds: too little room leaves the route short, reported only as unmet time (`UnmetTime`, `UnmetTimeDiff`) with routing "Satisfied": widen the envelope, or put the delay in another section. The router stops at the low edge of the timing window.
- Per-section settings are rules on a tag only that section's `Route` carries: `serpentine_params(min_pitch=...)`, `coupled_pair_params(deskew_bump_radius=..., min_bump_spacing=...)`. `min_pitch` and `deskew_bump_radius` are lower bounds on the router's choice (their docstrings). The router does not hold `min_radius` or `max_bump_length`: never claim either without reading the arcs.
- An envelope section ignores keepouts and tag clearances, unreported: end it at control points clear of obstacles, with plain routes around them.
- Read back each section's span across its axis against its envelope, pitch and bump radii from the captured arcs, and the timing lines from `rd.issues()`.

## Copper, pours and keepouts

| Construct | Net | For |
|---|---|---|
| `Pour(shape, layer=, rank=)` | `net += pour` | a plane or shaped fill, cut around other copper |
| `Copper(shape, layer=)` | `net += copper` | a fixed shape on one net |
| `OverlappableCopper(shape, layer=)` | none | copper over other nets' pads: a net tie, an antenna; the router and overlap checks ignore it |
| `KeepOut(shape, layers=, pour=, via=, route=)` | never | keeps pours, generated vias or traces out; set a flag |
| `Cutout(shape)` | none | a routed slot |

- A pour keeps copper only where its net has a pad or via with copper on that layer inside it; otherwise it comes back `Empty()` with `status: ok`, and stitch or fence vias do not hold it. Anchor each layer's pour, for example with one through via on the net. Worked pattern: `jitxexamples.patterns.board_ground_pours`.
- A pour larger than the board is pulled back by `min_copper_edge_space` or a larger `IsBoardEdge` rule (`jitx-layout-constraints`).
- `KeepOut(pour=True)` removes pour copper at every rank. `KeepOut(via=True)` blocks generated vias, fence vias included, not code-placed ones: hold other-net copper off a fenced line with a tag clearance rule instead ([fencing](../jitx-layout-constraints/SKILL.md#fencing)). A pour does not avoid `OverlappableCopper`: add a coincident `KeepOut(pour=True)`.
- Fence non-route copper (a divider body) with a fence-tagged GND `Pour` equal to it on its layer or the next ([fencing](../jitx-layout-constraints/SKILL.md#fencing)); where the body's pour keepout empties it, its fence stands.
- Declare a pour in the circuit that owns its net. One declared in a parent on a child's net can be captured off that net, and a fence-tagged child pour joined to a parent's net fails at submit ("Key N does not exist in table").
- `OverlappableCopper` connects only through the pads it overlaps; for the router to count two same-net pads joined by it, declare a [`VirtualConnection`](https://docs.jitx.com/en/latest/essentials/physical_design/creating-layouts-from-code.html#virtual-connections) (`jitx.virtual`); on a constrained path give it a `PinModel` with the leg's electrical delay, not one from its drawn length.
- Shapes: `jitx.shapes.composites` first; `ShapelyGeometry(g)` wraps shapely, `.to_shapely()` converts back. Use only a non-empty `Polygon` or `MultiPolygon`. `.at(scale=(1, -1))` does not mirror: transform the geometry.

## Thermal vias

Vias in one exposed pad at a stated pitch are placed in code, not by a `stitch_via` rule (`jitx-layout-constraints`). Worked pattern: `jitxexamples.patterns.qfn_thermal_and_power_fanout`; its `thermal_via_grid` spreads the vias over the span, so for a stated pitch place the centres at the pitch.

- Derive the count from the land pattern's pad size, the pitch, the rim margin and the via pad.
- JITX raises no issue for a via in a pad whose via class disallows it: read `via_in_pad` yourself and refuse a false one.
- Join each via to the pad's net and show from the capture that its copper reaches the plane's layer.
- Mask dams and paste windows belong to the land pattern (`jitx-component-modeler`); worked pattern: `qfn_thermal_and_power_fanout.thermal_pad_opening`.

## Fab floors the build does not hold

JITX raises no issue for these; keep the design's copper at or above its fabricator's limits:

- Spacing is not enforced between copper of one net, such as neighbouring meander segments: keep `min_pitch` at or above one segment's copper plus `min_copper_copper_space`.
- A structure's width and pair gap override the `min_copper_*` floors.
- Land-pattern pads are placed as drawn, even inside `min_copper_edge_space`.

Compare structures and realized copper with `rd.root.substrate.constraints`. A structure below the floors that the substrate or user states is an open item naming who must accept it; any other miss fails.

## Verification

A check proves every requested property from the capture: `with jitx.runtime as r: rd = r.submit(MyDesign)`, `rd.capture()`, read, assert, exit nonzero on failure. Take expected values from the request, documents and geometry, never from your own code's constants.

| Claim | Read and assert |
|---|---|
| A route exists | `route.status.routed` and non-empty `route.traces` (two for a coupled section) |
| Width, layer | each captured trace's `shapes`: width equal to the structure's, or the larger of the `Config`'s and `min_copper_width`, on the named layer, not read from the authored `Route` |
| A pour fills | `Pour.shape`: `Empty()` means removed (test before `.to_shapely()`, which raises on it); otherwise the computed copper with holes, and the realized edge gap |
| Generated vias | `rd.query(Via)` less the code-placed ones `visit(rd.root, Via)` lists, by identity; assert counts per row or region |
| Net | `rd.nets.find(obj).name` on pours, vias and each trace of a pair |
| Issues | `rd.issues()`: routing ("Unable to find path for requested route"), timing (`UnmetTime`), `UnsquiggledRoute` |
| A distance | between captured shapes; arcs via `ShapelyGeometry.from_shape(shape, tolerance=1e-4)` |

When a route, pour or via did not realize, report it as not done with that evidence, and give the engineer the options (open the obstacle, change layer, move a part) instead of choosing one.

### Coordinate frames

`Route.Trace.shapes` are in the frame of the circuit that declares the route: apply `trace.transform` from `visit(rd.root, Route)`. A placed element from `visit` sits at `trace.transform * elem.transform`. `Copper` from `rd.query` and a pour's `shape` have no transform of their own: apply `trace.transform` to the shape (`trace.transform * pour.shape`; the `jitx.query` docstring). Never read `pad.transform` alone: a component with several land patterns nests its pads a level deeper.

## Interactive edits

`rd.layout`, `jitx design session` and `jitx design exec` edit the layout the runtime holds: `jitx-interactive-layout` ([what an edit cannot change](../jitx-interactive-layout/references/api.md#changing-and-removing)).

- A via placed in code cannot be dragged relative to anything else placed in its circuit; it moves only when a floating circuit containing it is moved. A via made through the interactive layout can be dragged. A designer would take over a placeholder via by deleting it and its routes from code and re-creating them in the interactive layout; untested.

Dragging a control point, turn or width in the board view is untested: never report one as working unless you did it.

## Completion

The completion gives:

- Each piece of layout with one sentence on what goes wrong on this board without it, not what it does. Example: "GND via on L3: without a GND object on that layer the L3 pour comes back empty and the line loses its reference plane."
- The source of every width, gap, length, envelope and count (prompt, fab-sheet row, structure, datasheet, or a derivation with its arithmetic), and each structure below a fab floor.
- The control-point sort: each point, via and turn marked fixed by geometry or designer-placed (a placeholder in code), with the routes that go with it.
- Each check with its command, exit code and what it read from the capture; and anything open.
