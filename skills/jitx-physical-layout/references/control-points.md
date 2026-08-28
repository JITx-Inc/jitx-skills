# Control Points & Code-Based Routes

> **Surface reshaped in JITX 4.3.0-rc.3+ (py-jitx ≥ 4.3.0a17).** `Route` lives in
> `jitx.circuit`; the control-point classes live in `jitx.controlpoint`
> (`RoutePoint`, `PairInsertion`, `PairPoint` — also re-exported from top-level
> `jitx`). `SingleControl` / `InsertionControl` / `PairControl` are old alpha-era
> names for the same classes and no longer import. **On the routing vs.
> netting split:** control points separate the port used
> for *netting* (`.port`) from the endpoint(s) used for *routing* (`RoutePoint.pad`;
> `PairPoint.front`/`.back`; `PairInsertion.coupled`/`.uncoupled`). `PairPoint.pair`
> was **removed** and `RoutePoint.connection_point` was **renamed `.pad`**. On an
> unfamiliar runtime, confirm the surface by Reading the first ~200 lines of the
> installed `jitx/controlpoint.py`.

## When to use

Use code-based routes and control points when you need to author the **physical
route path** from code rather than leaving it to the autorouter or the interactive
UI — escape lanes out of a dense package, differential-pair deskew, or forcing a pair
to a specific insertion geometry. For ordinary connectivity, wire nets with `+`
(`jitx-circuit-builder`); for timing/skew/impedance *constraints*, use
`jitx-interconnect-constraints`.

**The iron rule (4.3): a `Route` that builds is not a route that exists.** Routes
realize (or silently don't) inside the runtime; `status: ok` says nothing about
copper. After every build, capture the design and assert `route.traces` on every
route you authored — the full recipe is in `references/geometry-verification.md`.
A production board on this exact pattern shipped 48 silently-unrealized fan legs
that netlist checks and visual inspection both missed; the traces assert catches
it in seconds.

## `Route` — code-based route between two endpoints

```python
from jitx.circuit import Route

# Route(source, destination, layer, sketch=None)
#   source / destination : Port | Pad | Via | RouteConnectionEndpoint | RoutePoint
#                          (not directional — order verified irrelevant. A RoutePoint
#                          is unwrapped to its .pad automatically.)
#   layer                : int
#   sketch               : optional routing-engine hint — a plain list of (x, y) points
#                          (verified: still accepted) or a Route.Sketch (start/turns/end)
r = Route(self.driver.OUT_p, self.rx.IN_p, layer=0)
self.routes = [r]                      # store on self so the structural walk sees it
```

- **`Via` endpoints** — a placed via instance is a valid route end, so you can route
  from a pad into a code-placed via.
- **No per-route width/clearance overrides.** `Route` carries no configuration —
  width/clearance/structure come from `design_constraint(...)` rules keyed on tags
  (rule mechanics in `jitx-layout-constraints`). **Where the tag goes matters:**
  - single-ended fanout: tag the *route* (`Tags(PinFanoutTag()).assign(r)`);
  - **differential structures: tag the NET, never the individual routes.** Tagging a
    pair's routes separately lets the two sides of one control point carry different
    routing structures, deforming the pair-point transition geometry. A net-level tag
    gives coupled spans the differential structure and the fanned legs automatically
    pick up its `uncoupled_region`.
- **`require`-provided ports cannot be route ends.** A port obtained through a
  `require(...)` pin-assignment raises
  `NotImplementedError: Using require ports as route ends ... is not implemented`
  at build time — route the component-side port or the pad instead.
- **A code `Route` is also a connectivity path.** Combining it with a `>>` topology
  segment on the same net double-connects the net → invalid physical state. When
  code-routing a net fully, drop the parallel topology and rely on nets +
  tag-applied structures. (Conversely, `topology + ConstrainDiffPair` alone routes
  NO copper — constraints bind auto-routed topologies, they never synthesize
  geometry for code topologies.)
- **After capture** (`rd.capture()` — see geometry-verification.md), `route.traces`
  holds the realized copper (`Route.Trace.shapes`, **design-global coordinates**)
  and `route.derived` any structure-driven extras (soldermask openings, keepouts).
  `None`/empty = the route did not realize.

## Control points — `RoutePoint` / `PairInsertion` / `PairPoint`

All three subclass `ControlPoint` (don't use the base directly), take a keyword-only
`layer=`, and are placed with `.at(point, rotate=)`:

- **`RoutePoint(layer=..., shape=None, bundle=Port)`** — the single-ended control
  point. **`.pad`** is the routing endpoint (`Route(some_port, rp.pad, layer)`); you
  may also pass the `RoutePoint` itself and `Route` unwraps it to `.pad`. **`.port`**
  is the (separate) netting port. (4.3.0-rc.3+: the old single `.port` that served
  both roles was split; the routing field was called `.connection_point` before the
  rename to `.pad`.)
- **`PairInsertion(layer=..., bundle=DiffPair, invert=False)`** — a differential-pair
  *insertion* point: transitions two individual, uncoupled traces into a coupled pair.
  For routing, `.coupled` is a `CoupledRouteConnectionEndpoint` (routes as a pair) and
  `.uncoupled` is an `UncoupledConnectionEndpoint` whose `.p`/`.n` are the two
  single-leg routing endpoints; `.port` is the netting `DiffPair`. It can also be
  netted directly (via `Net`/`TopologyNet`) now, in addition to `PortAttachment` +
  `Route`. `invert=True` mirrors the chirality (see below).
- **`PairPoint(layer=..., bundle=DiffPair, invert=False)`** — connects two segments of
  a differential pair *while still paired*, so each segment can be configured
  independently. **4.3.0-rc.3+: the old single `.pair` field is gone.** For routing use
  `.front` and `.back` (each a `CoupledRouteConnectionEndpoint`); for netting use
  `.port` (the `DiffPair`). `invert=True` mirrors the chirality (see below).

Attach ports with `PortAttachment`, passing the pair as an **ordered list**:

```python
from jitx.net import PortAttachment
self.pa = PortAttachment([tx.p, tx.n], insertion)
```

**Every pair a control point touches needs an explicit design `Net`.** If the only
thing connecting a component-internal `DiffPair` to the design is a
`PortAttachment`, capture crashes with
`Expected Net for LayoutControlPoint.copper[*].net_id 0, got '<Component>'` —
declare `self.dsig = Net([comp.sig])` (or unify it with the far end:
`self.dsig = a.sig + b.sig`). Related: `port + port` needs ≥ 2 members; a
single-member net is `Net([port])`, not a bare port (a bare `Port` has no
`.connected` and fails instantiation).

### The PairInsertion binding map (verified empirically on 4.3)

This is the part everyone gets wrong, because the `n`/`p` names on `uncoupled`
are **positional labels, not net polarity**:

1. **Binding**: `PortAttachment([first, second], ins)` binds `first → ins.uncoupled.n`
   and `second → ins.uncoupled.p`. (`uncoupled.n` = the "left" position looking from
   the coupled side toward the uncoupled side; at `rotate=0` it is the **+Y** side.
   The whole map rotates rigidly with `rotate=`.)
2. **Leg routes must target the port each signal is BOUND to**:
   `Route(first, ins.uncoupled.n, layer)` and `Route(second, ins.uncoupled.p, layer)`.
   Routing a signal to the port it is *not* bound to does not error — the leg is
   **silently unrealized** (empty `traces`). This — not geometric crossing — is the
   usual leg-failure mechanism.
3. **A coupled trunk between two facing insertions (0°/180°) realizes only with
   MIRRORED attachment orders** — `[p, n]` on one side, `[n, p]` on the other. Same
   order on both sides puts the pair's polarity lines on opposite physical sides →
   the trunk silently doesn't realize. Pad geometry does not change this.
4. **Pick the mirror sense so each signal's bound side matches its pad side.** Both
   mirror senses realize; the wrong one realizes with legs wrapped around the
   insertion (geometrically awful). Realized ≠ sensible — check the trace bounds.
5. The `coupled` side always routes as a pair (`Route(ins1.coupled, ins2.coupled,
   layer)`); never access `coupled.p`/`coupled.n` individually. Route coupled ends
   control-point-to-control-point (insertion `.coupled` ↔ pair-point `.front`/`.back`,
   or `.coupled` ↔ `.coupled`), never onto a feed/bundle port.

> **4.3.0-rc.3+ — reach for `invert=` before the attachment-order hack.** Chirality is
> now a first-class constructor argument: `PairInsertion(...)`/`PairPoint(...)` take
> `invert: bool`, which mirrors the p/n handedness of the control point directly.
> This is the intended mechanism for the "mirrored attachment orders" trunk fix in
> point 3 and the "which physical side each leg lands on" problem — flip `invert=`
> instead of hand-swapping the `PortAttachment` order. `invert=` mirrors handedness
> only (it does **not** rotate the point; a facing insertion still needs
> `rotate=180`). The positional-label mechanics above still describe what happens per
> attachment order; `invert=` is the cleaner lever. Verify realization either way
> with the `route.traces` assert.

**Coupled-connection rules (4.3.0-rc.3+, from the `controlpoint.py` docstrings).** With
the routing endpoints now explicit (`PairPoint.front`/`.back`, `PairInsertion.coupled`)
and chirality carried by `invert=`, the legal coupled connections are:

- **Pair-point → pair-point chain** routes `.front → .back` when *neither or both*
  endpoints are inverted; to connect an inverted point to a non-inverted one, join
  `.front ↔ .front` or `.back ↔ .back`.
- **Insertion → pair-point:** a *non-inverted* insertion's `.coupled` connects to the
  pair point's `.back`; an *inverted* insertion connects to the `.front`. The two
  relationships swap if the pair point itself is inverted.
- **Insertion → insertion** requires exactly *one* of the two insertions inverted.

`invert=` mirrors the control point's chirality (its p/n handedness) *without*
rotating it — the ASCII diagram in `PairInsertion`'s docstring shows why an
insertion facing another must be both inverted **and** rotated 180°. `PairPoint`
also has an orientation dependence: its rotation selects which side a coupled route
may exit from; a wrong-facing point silently doesn't realize. Flip by adding 180° to
`rotate=` (position unchanged), or set `invert=True` to mirror handedness, and
re-verify.

**`invert=` is the ONLY way to express chirality. Reversing attachment order is now a
dead route, not a mirror.** The linker enforces per-conductor net consistency (p↔p,
n↔n), so `PortAttachment([pair.n, pair.p], cvg)` — the pre-4.3 idiom for flipping a
pair — no longer crosses the geometry; it asks for a conductor path that does not
exist, and the route silently produces nothing while the build still reports
`status: ok`. The rule to write, and to review against:

```python
# ALWAYS this, on every lane, whatever the geometry is doing:
PortAttachment([pair.p, pair.n], cvg)      # canonical, ELECTRICAL order
cvg = PairInsertion(layer=0, invert=flip)  # chirality lives HERE
```

Measured on one migration to 4.3.0-rc.3: **109 of 128 routes dead**, all of them
passing `jitx build`, found only by asserting `route.traces` afterwards. When a design
predates this rule, crossed attachments are the first thing to look for — and each one
needs its chirality re-expressed as `invert=`, not merely re-ordered, because which
endpoint a trunk may exit from (`.front` vs `.back`) is keyed to `invert` per the table
above.

6. **A `PairPoint` → `PairInsertion` trunk additionally requires the two
   endpoints' control points to be attached to DIFFERENT port pairs of the net**
   (e.g. the pair point on the source component's pair, the insertion on the
   destination component's pair — the net is unified either way). With both
   attached to the same pair, the trunk silently never realizes under any
   order/rotation combination. Insertion↔insertion trunks tolerate same-pair
   attachments (mirrored orders still required). When a trunk resists every
   order/flip lever, swap one endpoint's attachment to the far pair.

### Circuit ownership — the common-ancestor rule

A code route may reference control points **anywhere in its owning circuit's
subtree**: a parent-owned trunk between two child-circuit insertions works, and a
parent-owned `PortAttachment` onto a child component's internal `DiffPair` works.
What still fails (translate-time
`Unable to map local reference N, parent X is not an ancestor of child <DiffPair>`)
is referencing a **sibling** circuit's control point — the route must be hoisted to
the common ancestor. Store `PortAttachment` objects on `self`, not raw foreign
component ports (a raw port stored on `self` acquires a second structural parent
and breaks the ancestor walk).

> **Known bug (4.3.0-develop.25 / py-jitx develop):** fan legs authored *inside a
> child circuit* (component + insertion + bound-correct legs all local) may silently
> fail to realize even though the identical geometry realizes at root level, and
> even though the insertion's own transition copper is placed correctly. Board-scale
> designs showed one leg per pair dropping. Until fixed: author fans at the circuit
> level where they verifiably realize, and **always assert `route.traces` on every
> route after capture** — it is the only reliable detector.

## Worked example — deskew fan

Attachments and routes accumulate in plain **lists** (not string-keyed dicts);
vias come from the substrate; legs are routed to their *bound* ports.

The per-lane pad coordinates (`lane.p_pad` / `lane.n_pad` below) are **composed**, not read
off `pad.transform` — `PadMapping` resolves port → pad, then `visit` plus
`trace.transform * pad.transform` gives the coordinate in the frame you want. Raise on an
unresolved frame rather than skipping, since these lists are consumed positionally. Recipe
and the composite-landpattern trap: `references/geometry-verification.md`
§ "Coordinate frames".

```python
from jitx.controlpoint import PairInsertion, PairPoint
from jitx.circuit import Route
from jitx.net import PortAttachment

self.attachments = []
self.routes = []
for index, lane in enumerate(self.escape_lanes):          # a list, iterated
    via_cls = substrate.signal_via[lane.spec.signal_layer]
    self.attachments.append(PortAttachment(lane.tx_pair.p, via_cls().at(*lane.p_pad)))
    self.attachments.append(PortAttachment(lane.tx_pair.n, via_cls().at(*lane.n_pad)))

    pair_point = PairPoint(layer=lane.spec.deskew_layer).at(lane.exit_xy, rotate=90)
    insertion = PairInsertion(layer=lane.spec.deskew_layer).at(lane.fan_xy, rotate=90)

    order = [lane.tx_pair.n, lane.tx_pair.p]              # first -> uncoupled.n
    self.attachments.extend([
        PortAttachment([lane.tx_pair.n, lane.tx_pair.p], pair_point),
        PortAttachment(order, insertion),
    ])
    self.routes.extend([
        # 4.3.0-rc.3+: pair point exposes .front/.back (not .pair). A non-inverted
        # insertion's .coupled joins the pair point's .back (see connection rules above);
        # if a coupled trunk won't realize, try .front or flip a point's invert=.
        Route(pair_point.back, insertion.coupled, lane.spec.deskew_layer),
        Route(order[0], insertion.uncoupled.n, lane.spec.deskew_layer),   # bound port!
        Route(order[1], insertion.uncoupled.p, lane.spec.deskew_layer),
    ])
```

To replicate a verified cell across N lanes, author it in a local frame and place
each instance with `.at(pivot, rotate=)` — a rigid rotation preserves internal
clearances by construction; re-derive the attachment order per placement from the
binding map (mirroring/rotating flips which physical side each index lands on),
then verify all N with the traces assert.

## Verification

`pyright` catches a wrong accessor or constructor immediately. Then verify
**realized geometry, not build success**: submit + capture through the runtime and
assert, for every route: (1) `traces` is non-empty (and `== 2` traces for a coupled
trunk), (2) the net riding each trunk line (`rd.nets().find(trace)`) matches the
intended polarity, (3) the shapely bounds of the trace shapes are where you meant
(`shape.to_shapely().g.bounds`). Full recipe, query-vs-visit semantics, and
coordinate-frame rules: `references/geometry-verification.md`.
