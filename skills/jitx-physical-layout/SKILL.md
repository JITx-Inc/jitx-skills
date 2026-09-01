---
name: jitx-physical-layout
description: "Use when the user asks to author PCB physical layout from code: draw copper, antennas, filters, net ties, custom shapes, board outlines, custom pads, soldermask or paste openings, thermal pads with vias, code-placed vias, fanout or escape tags, direct-connect or thermal-relief tags, control points, code-based routes, diff-pair fans/trunks, escape routing, or deskew, or to inspect or verify realized geometry from Python (jitx.query, RuntimeDesign capture, missing or Empty pours, missing stitch vias, route realization checks). Covers shapely geometry, Copper, OverlappableCopper, Pour realization semantics, pad features, PortAttachment, explicit placement, layout-intent tags, Route/control-point APIs, and the 4.3 reverse-flow geometry-verification workflow. Use jitx-layout-constraints to author pour and via-stitching rules, jitx-substrate-modeler for stackups, via definitions, routing structures, fence-via rules, and fenced pours, and jitx-circuit-builder for net wiring, passives, and basic pours."
---

# JITX Physical Layout

Author physical layout geometry — copper, custom shapes, pad features, explicit
placement, code-driven vias/routes, and layout-intent tags — directly in Python.
This is the layer **between** schematic-level wiring (`jitx-circuit-builder`) and
stackup/fab definition (`jitx-substrate-modeler`).

JITX is a moving target — APIs on this page have been renamed across releases
(the control-point classes in 4.2.0; the reverse-flow inspection surface is new in
4.3). Do not rely on prior JITX knowledge — **verify every import and signature
with `pyright` against the installed package**, and verify control-point/route
geometry by **capturing and asserting the realized copper**
(`references/geometry-verification.md`), never by build success alone.

## Scope — what this skill owns vs neighbors

| You want to… | Skill |
|---|---|
| Draw copper shapes, antennas, filters, net-ties, custom board/pad geometry | **this skill** |
| Build a shape with shapely and feed it to any feature | **this skill** |
| Add soldermask/paste/thermal-pad features, place vias/components from code | **this skill** |
| Tag layout objects (fanout, escape, direct-connect) for selection | **this skill** (rule *mechanics* → `jitx-layout-constraints`) |
| Code-based routes & control points (escape lanes, deskew) | **this skill** (advanced — see reference) |
| Diagnose whether pours or stitch vias materialized and inspect captured pour geometry | **this skill** |
| Design rules: clearances, widths, net classes, escape rule ladders, after-build width/clearance checks | `jitx-layout-constraints` |
| Wire nets, add passives, voltage dividers, basic pours | `jitx-circuit-builder` |
| Define the stackup, vias, routing structures, fence-via rules, fenced pour outlines | `jitx-substrate-modeler` |
| Author a component's package/landpattern from a datasheet | `jitx-component-modeler` |
| Topology (`>>`), timing/skew/impedance constraints | `jitx-interconnect-constraints` |

This skill covers the design-side *geometry and placement*; `jitx-layout-constraints`
owns the `design_constraint(...)` rules that act on it, and the substrate owns the via
classes and routing structures those rules reference. Where they meet, this skill
cross-references rather than restating.

## Environment

Environment setup is handled by the base `jitx` skill — invoke it first.

## Imports

```python
# Copper & pours
from jitx import Copper, Pour, current
from jitx.feature import OverlappableCopper          # netless overlap copper
# Features (pad / surface / keepout)
from jitx.feature import Soldermask, Paste, Silkscreen, Courtyard, Custom, Cutout, KeepOut
# Shapes
from jitx.shapes import Shape
from jitx.shapes.shapely import ShapelyGeometry       # wrap a shapely geometry
from jitx.shapes.composites import rectangle, capsule, notch_rectangle, chipped_circle
from jitx.shapes.primitive import Circle, Polygon, Text
from jitx.anchor import Anchor
from jitx.layerindex import Side, LayerSet
import shapely                                          # the upstream library
# Placement & attachment
from jitx.net import Port, PortAttachment
# Tags
from jitx.constraints import Tag, Tags
# Pad config (landpattern feature generation)
from jitxlib.landpatterns.pads import SMDPadConfig
# Code-based routes / control points (stable as of 4.2; also re-exported from top-level jitx)
from jitx.circuit import Route
from jitx.controlpoint import RoutePoint, PairInsertion, PairPoint
```

**Do NOT import** (these do not exist): `jitx.copper.OverlappableCopper`
(it lives in `jitx.feature`), `jitx.shapes.Shapely`, `jitx.geometry`,
`jitx.layout`, `jitx.routes`. When unsure, search the installed source with your **Grep** tool (pattern `class OverlappableCopper|class Route|class PortAttachment`, path `.venv`, glob `*.py`); it recurses and is OS-agnostic. Shell fallback: bash `grep -rn "class OverlappableCopper\|class Route\|class PortAttachment" .venv/lib/python*/site-packages/jitx/` (macOS/Linux); on Windows use the Grep tool, or `Select-String` over `.venv\Lib\site-packages\jitx`.

## Custom shapes with shapely (general)

Shapely is general shape creation for **any** JITX feature that takes a `Shape` —
copper, pours, keepouts, the board outline, courtyards, and pad soldermask/paste.
It is not pad-specific.

Reach for a **built-in composite first** for common shapes — they stay exact
(`rectangle`, `capsule`, `Circle`, `notch_rectangle`, `chipped_circle`, `bullseye`,
`equilateral_triangle`, …). Use **shapely** when you need CSG (union / difference /
intersection), buffering, fillets, or arbitrary polygons.

Two shape-API gotchas: `jitx.Point` is a bare `tuple[float, float]` alias, not a
constructor — waypoints/vertices are plain `(x, y)` tuples. And there is no
per-axis reflection: `.at(scale=(1, -1))` crashes (`can't multiply sequence …`) —
mirror by transforming the geometry itself (shapely `scale`/affine, or negate arc
math), not via `.at(scale=)`.

```python
import shapely
from jitx.shapes.shapely import ShapelyGeometry

# Build geometry with shapely, then wrap the result for JITX:
ring = shapely.box(-5, -5, 5, 5).difference(shapely.box(-4, -4, 4, 4))
shape = ShapelyGeometry(ring)          # a jitx Shape — feed it to ANY feature

# Round-trip an existing JITX shape into shapely for an operation:
from jitx.shapes.composites import rectangle
expanded = rectangle(2, 1).to_shapely().buffer(0.1, cap_style="square", join_style="mitre")
# `.to_shapely()` and `.buffer(...)` return ShapelyGeometry; pass straight to a feature.
```

`ShapelyGeometry` supports set operators `&` (intersection) `|` (union) `-`
(difference) `^` (symmetric difference) and `.buffer()`. A **morphological open**
(`buffer(-r).buffer(r)`) rounds sharp inside corners — useful for paste cells.

**Validity caveat — guard before feeding a fab feature.** JITX serializes only
**non-empty `Polygon` / `MultiPolygon`** geometries. Shapely operations can produce
empty geometries, `LineString`s, or `GeometryCollection`s — those raise at build
time. After CSG, confirm the result is a non-empty polygon:

```python
g = ring  # a raw shapely geometry
assert not g.is_empty and g.geom_type in ("Polygon", "MultiPolygon"), g.geom_type
```

Arcs are polygonized at a tolerance when converted to/from shapely; keep an eye on
vertex counts for large numbers of circular features.

## Copper: Pour vs Copper vs OverlappableCopper

Three ways to put copper on a layer — pick by **net membership** and whether the
copper is allowed to **overlap** other copper:

| Construct | On a net? | Overlap-exempt? | Use for |
|---|---|---|---|
| `Pour(shape, layer, *, rank=0)` | yes (`net += Pour(...)`) | no | filled planes / shaped fills |
| `Copper(shape, layer)` | yes (`net += Copper(...)` or `a + Copper(...)`) | no | an explicit copper shape on one net |
| `OverlappableCopper(shape, layer)` | **no** (netless) | **yes** | net-tie copper bridging two nets' pads, antenna radiators, filter copper — ignored by the router and overlap checks |

`Copper(..., exempt=True)` was **removed in 4.2.0** — there is no on-net,
overlap-exempt copper anymore. Overlap-tolerant copper is `OverlappableCopper`,
which is netless: its connectivity comes from the pads it overlaps.

`Copper` lives in `jitx` (top-level / `jitx.copper`); `OverlappableCopper` lives in
`jitx.feature`.

```python
from jitx import Copper, Pour
from jitx.feature import OverlappableCopper

self.GND += Pour(rectangle(10, 10), layer=0)              # local filled region
self.SIG += Copper(rectangle(10, 0.5).at(0, 5), layer=0)  # copper shape on a net
```

## Pour realization semantics

A `Pour` is an authored fill request. The runtime decides whether copper
materializes, replaces the captured shape with runtime output, and may return a
successful build with no realized copper or stitch vias. The realization gate
therefore runs `scripts/check_realization.py`; the Physical realization rows in
the task and Phase 4 completion blocks refuse a missing command or nonzero exit.

### Construction and placement prerequisites

`Pour(...)` constructed outside an active design context is a deferred
`Instantiable` proxy. Its `.layer` and `.shape` attributes are accessors, not the
values passed to the constructor. A unit probe must submit a `Design` and call
`capture()` before it asserts per-pour layer, shape, or identity. Unit tests may
check plain-data helpers and outline factories outside the runtime, but they are
not structural realization evidence. `check_realization.py` performs submit and
capture before reading those fields.

Placement is also a realization prerequisite. Top-level subsystem circuits use
`.at(floating=True)` when a person will place them interactively; otherwise they
pile up at the parent origin. A headless geometry harness gives them explicit
positions. A floating circuit with no stored interactive placement is parked off
the board, which leaves routes unrealized and board-wide pours `Empty()` while the
build still reports `status: ok`. Record either explicit positions or completed
interactive placements stored in `design-info/` before interpreting a realization
failure. Capture cannot report which objects lacked authored placement because
auto-placement and stored state give every captured component a position; this is
a stated limitation, not a placement gate the shipped checker claims to enforce.

### Conditions for realized copper

A pour survives only when its net has a pad or via reaching the pour's layer. If
nothing on the net reaches that layer, the runtime silently deletes the pour and
capture returns `Empty()`. Calling `.to_shapely()` on that value raises
`ValueError: Unhandled primitive geometry type: Empty()`. The realization command
checks for `Empty()` before conversion, reports the pour's net and layer, and exits
1 on every required empty pour. The
`orphans` constructor field is documented as currently not respected, so it is
not a keep-or-drop control and never substitutes for the captured-shape check.

`KeepOut(..., pour=True)` always forbids realized pour copper in its shape. A
`KeepOut` has no rank field, and the translated forbid-copper feature receives no
rank input. Raising `Pour.rank` does not fill over the keepout at any rank; rank
only prioritizes competing pours. `KeepOut(via=True)` blocks automatically placed
vias, not vias explicitly placed in code. `check_realization.py` intersects the
captured computed pour copper with every same-layer `KeepOut(pour=True)` and exits
1 if forbidden area is present.

A pour authored directly from `current.design.board.shape` receives no automatic
copper-to-edge pullback and lands flush with the board profile. A board-wide pour
must use an outline buffered inward by at least the active fabrication floor:

```python
fab = current.design.substrate.constraints
pour_outline = current.design.board.shape.to_shapely().buffer(
    -fab.min_copper_edge_space
)
if pour_outline.g.is_empty or pour_outline.g.geom_type not in (
    "Polygon",
    "MultiPolygon",
):
    raise ValueError("board edge pullback removed or invalidated the pour outline")
self.ground_return = Pour(pour_outline, layer=return_layer)
self.GND += self.ground_return
```

Name every board-wide pour with repeatable `--board-wide-pour`. The realization
command measures its captured copper against the profile and exits 1 when it is
outside the board or the spacing is below `min_copper_edge_space`; using the board
profile unchanged therefore cannot pass.

### Stitch-via realization

`design_constraint(...).stitch_via(...)` materializes vias only when its selected
object is a `Pour`. In a controlled test, the same 3.10 by 4.05 mm shape produced
9 vias as a `Pour` and zero as a `Pad`, as `Copper`, and through a board-wide
`IsPad` rule. Every zero-via case reported `status: ok`. To stitch a thermal-pad
region with this rule, the circuit creates a `Pour` from the landpattern thermal
pad's shape, joins it to the net, and tags that pour. A pad-specific explicit via
field remains a separate physical-layout pattern.

`SquareViaStitchGrid.inset` is observed from the region boundary to the via pad
edge, not to the via center. Away from an exact boundary, the observed count per
axis follows:

```python
2 * floor((size / 2 - inset - via_pad_diameter / 2) / pitch) + 1
```

The exact boundary is not fully characterized. On a 3.10 mm axis with 1.2 mm
pitch, `inset=0.125` produced one via where both tested count formulas predicted
three. Treat a count formula as a planning estimate. The shipped checker proves
that each named stitch target is a `Pour` and that at least one solver-emitted
stitch-via center lies inside it. The capture record does not bind a stitch group
back to its rule or expose a direct "requested inset satisfied" flag, so exact pad-
edge inset compliance remains a stated limitation requiring a project-specific
geometry check.

### Captured pour geometry

`capture()` overwrites each authored `pour.shape` in place with reverse-flow
runtime output. `rd.query(Pour)` therefore does not preserve the authored outline:
an authored `rectangle(20, 20)` was observed after capture as a `MultiPolygon`
with area `399.9976`, not a `Rectangle` with area `400.0`. Code that needs the
authored geometry records its expected bounds or reconstructs its outline before
capture rather than reusing `pour.shape` afterwards.

The supported reverse-flow adapter applies `LayoutOutput.computed_shape` to the
captured `Pour`. `check_realization.py` preserves `PolygonSet` holes while
converting that shape and uses it for presence, keepout voiding, and final edge
spacing. If the installed package cannot import that reverse-flow surface or the
geometry cannot be read safely, the command exits 2; it never converts missing
evidence into a pass. What the command cannot witness it names as
unwitnessed; it does not accept build status as evidence, and it does not send
the reader to the fabrication export to close the gap.

**Reverse flow is the realization surface.** After `capture()`, the reverse-flow
linker assigns the runtime's output back onto the objects the design authored:
`LayoutOutput.computed_shape` onto the pour, and `ComputedStitchVia` /
`ComputedFenceVia` (in `jitx._translate.reverse_flow.applied`, applied through
registered transformers) onto the copper their rules produced. Read realization
there.

It is the better surface, not merely the cheaper one. A fabrication export
carries geometry stripped of meaning: features on a layer, with no net and no
owning instance, so proving a pour reached the right net means reconstructing
connectivity the design already knows. Reverse flow carries the realized shape
together with its net and its owner, which is what a question like "did this
pour connect to the rail it was drawn for" actually needs. The export can only
answer a shape question; reverse flow answers the electrical one.

What it does not witness on the 4.4 line: trace-to-pour clearance, thermal
relief spoke geometry, and sliver removal. Those are reported unwitnessed, with
one line each. Do not open an export to chase them. The export is a handoff
artifact for a fab, not a verification loop for an agent: an agent that starts
parsing exported geometry to confirm its own rules spends heavily and learns
little that the runtime could not have told it.

**OverlappableCopper is netless.** Its electrical connection comes from the **pads it
overlaps**, not from the copper itself. A net-tie is the minimal case: the bridging
shape is `OverlappableCopper` drawn across pads on the two nets it ties. The
antenna pattern is the same idea at full size: give the structure a
small `Component` with anchor pads that *are* on the nets (so the router has
something to land on), then draw the radiating shape as `OverlappableCopper`
overlapping those pads:

```python
self.ant = AntennaIFA().at(0, 0)        # component with feed + short anchor pads, pinned at origin
self.ANT_FEED += self.ant.feed          # pads carry the nets
self.GND      += self.ant.short
# radiator shape is netless copper overlapping the pads — no DRC overlap error:
self.copper_radiator = OverlappableCopper(radiator_shape, layer=0)
```

Note `OverlappableCopper` is **not** in the set of tag-able objects (see Tags below).
The full antenna example is in `references/layout-examples.md`.

### Declaring the connection: `VirtualConnection` (4.3.0-rc.3+)

Overlap alone is a *physical* connection the tools can't reason about: the
topology walker doesn't see it, so ratsnest/unrouted warnings fire and no SI
constraint can span the authored copper. `jitx.virtual.VirtualConnection`
closes that gap — a user-declared assertion that two endpoints are
electrically connected, **with known electrical properties**:

```python
from jitx.si import PinModel
from jitx.toleranced import Toleranced
from jitx.virtual import VirtualConnection

# deskew-fan leg: authored OverlappableCopper from a BGA ball pad to a
# PairPoint's front-side leg — declare it, with its electrical model:
self.leg_vc = VirtualConnection(
    self.bcm.mtx[0].p,          # single-pin Port (or Pad, or Via)
    self.cvg.front.p,           # a control point's per-leg endpoint
    source_layer=0,
    destination_layer=0,
    pin_model=PinModel(delay=Toleranced(10.9e-12, 35e-15), loss=0.06),
)
```

Rules learned in production (saturn-ethernet, 4.3.0-rc.3):

- **Endpoints are single electrical targets**: a single-pin `Port`, `Pad`,
  `Via`, or a non-coupled `ConnectionEndpoint` (e.g. `pair_point.front.p`).
  Bundle ports — including a combined `DiffPair` — are rejected; name the
  leg (`pair.p` / `pair.n`).
- **A pin model is what completes a CONSTRAINED topology.** A model-less
  VirtualConnection suppresses ratsnest/unrouted warnings but cannot satisfy
  skew / timing / insertion-loss constraints routed through it. With
  `PinModel(delay=, loss=)` declared per leg, a `ConstrainDiffPair` /
  `DiffPairConstraint` topology spans the authored copper end to end — this
  is how an authored deskew fan participates in intra-pair skew matching.
- **The topology itself must be `>>` TopologyNets, never `+` Nets.** A
  constrained path is valid only when every pad-to-pad segment is declared
  with `>>` (docs: essentials/SI/topology): one plain `+` tie anywhere in
  the chain is an "invalid segment" and the walker reports NO PATH for the
  whole topology — the VC/pin-model machinery never even gets asked.
  Series components (AC caps) are crossed by their `BridgingPinModel`;
  `TopologyNet` sequences also accept `Via` and `ControlPoint` elements,
  and TopologyNets are tag-able (routing-structure rules carry over).
- **Model MEASURED delay, not drawn length.** On curved/wrapped legs the
  drawn centreline over-states delay (a verified deskew hook measured
  ~0.07 ps of real skew where drawn lengths implied ~2 ps). Encode the
  electrical truth: equal mean delays with the measured residual as a
  `Toleranced` spread; use drawn length for loss and for the mean only.
- **Constraint endpoints must be COMPONENT ports.** Control-point `.port`
  bundles do not id-map as `Topology` begin/end at translation
  ("parent ... is not an ancestor of child <<Port>>") — constrain from
  component port to component port (e.g. BGA pair -> connector pair) and
  let control points sit mid-topology.
- The API is marked experimental in `jitx.virtual` — expect change.

## Pad features (soldermask / paste / thermal pad)

Custom `Pad` subclasses (KiCad-converted footprints, mechanical pads) get **no
default soldermask or paste** — the pad is unsolderable until you add them. Two
mechanisms, kept distinct:

**(a) Feature objects added to a Pad.** Surface features take `(shape, side=Side.Top)`:

```python
from jitx.feature import Soldermask, Paste
# JLCPCB convention: mask = copper expanded by solder_mask_registration (~0.05 mm);
# paste = copper exactly. See pad_features.py helpers in references for Circle-exact expansion.
mask  = Soldermask(expanded_copper_shape, side=Side.Top)
paste = Paste(copper_shape)
```

**(b) `SMDPadConfig` driving a landpattern generator.** Each of `copper` /
`soldermask` / `paste` takes a **`Shape`** (or a `float` expansion, `None` to skip,
or a `ShapeAdjustment` like paste subdivision). Omit a field (default `...`) for
standard behavior. Pass the config to `landpattern.thermal_pad(shape, config=)`:

```python
from jitxlib.landpatterns.pads import SMDPadConfig
config = SMDPadConfig(soldermask=opening_shape, paste=opening_shape)   # both are Shapes
landpattern.thermal_pad(shape=rectangle(3.45, 3.45), config=config)
```

A **soldermask-defined thermal pad** (shapely CSG webs + via dams, a cheap-fab
alternative to filled via-in-pad) is a complete worked example in
`references/layout-examples.md`. Authoring the package/landpattern itself from a
datasheet belongs to `jitx-component-modeler`; this skill is the feature mechanics.

## Explicit placement & via attachment

**Structural-membership rule (CRITICAL for export):** every placed via (or
copper) must be **assigned to a circuit as a structural attribute** — stored on
`self`, directly or in a list. Geometry reachable ONLY through a `Net` or a
`PortAttachment` builds with the warning
`N object(s) appear in nets or port attachments but are not assigned to a
circuit … deprecated` — and on the 4.3 EDB/HFSS export path that geometry is
**silently DROPPED from the export** (verified: 485 flagged vias absent from
the EDB; 0 flagged and all present after storing the instances on `self`).
Treat that warning as a hard error: store the instance, then attach/net it.

**Scope rule — `PortAttachment` is for signal topologies only**: binding a signal
port to a control point, or to a signal via in an escape/deskew path. For
ground/power stitching vias, thermal vias, and anything else that just joins a
net, add the placed via (or copper) to the **net** — `Net` accepts `Copper | Via`
members directly. PortAttachment use is deliberately being limited and is
expected to be deprecated; default to the net form whenever the connection is
plain net membership.

```python
# Ground / thermal vias: structural list on self + net membership.
# Source the via class from the substrate / JLCPCB library — do NOT redefine vias here:
via_cls = substrate.signal_via[layer]          # or: from jitxlib.jlcpcb.vias import JLCPCBVias
self.thermal_vias = [via_cls().at(x, y) for (x, y) in via_positions]   # structural: stored on self
for via in self.thermal_vias:
    self.GND += via

# Signal vias (escape/deskew): ALSO store the instances, then PortAttachment.
# ball_positions: compose each pad's frame — visit() + trace.transform * pad.transform
# (references/geometry-verification.md § Coordinate frames). NEVER pad.transform alone.
self.sig_vias = [via_cls().at(*pad_xy) for pad_xy in ball_positions]
self.sig_via_attach = [
    PortAttachment(port, via) for port, via in zip(ports, self.sig_vias)
]
```

For the signal-topology cases, `PortAttachment(port_or_ports, attachment)` connects
a port (or a sequence of ports) to a placed **`Copper` | `Via` | `ControlPoint`**
at a fixed location:

```python
from jitx.net import PortAttachment
# Signal escape via at a fixed location, bound to its signal port:
self.attachments = [PortAttachment(self.serdes.TX.p, via_cls().at(x, y))]
```

**Vias are defined in the substrate**, not here (see `jitx-substrate-modeler`). This
skill *places* instances of them. Define a custom module-scope `Via`
subclass only with a fab-verified reason — e.g. the tented-unfilled thermal via in
the thermal-pad example, where JLCPCB charges nothing for tented vias inside a pad.

**Placement — place a direct descendant with `.at()`; use `Circuit.place()` sparingly.**

```python
self.led = LED().at(10.0, 5.0, rotate=90)          # x, y, rotate (deg), on=Side — default form
self.led_b = LED().at(10.0, 5.0, on=Side.Bottom)
self.subckt = MySub().at(floating=True)            # interactive placement; store it before capture checks
# Circuit.place() — sparingly: records a DEFERRED placement request on the parent (the child's own
# transform won't reflect it until placement resolves) and force-floats a placed subcircuit. Reserve
# it for the one thing .at() can't express — placing relative to ANOTHER instance (for a
# layout-engine-chosen position, use .at(floating=True) as above):
self.x = MyChip()
self.place(self.x, (1.0, 0.0), relative_to=self.led)
```

`.at()` mutates the instance's own `transform`, so the placement is readable on the instance —
visible to introspection before the design is built — in the **immediate container's** frame, which
for a direct descendant is exactly the parent frame you placed it in. Reading that transform as a
**board/global** position is the frame bug, and a pad nests deeper still (landpattern, and one more
level for a composite): compose down instead — see `references/geometry-verification.md`
§ Coordinate frames. For a **direct descendant** placed in the
parent's frame, set the position with `.at()` (chained when you create it, `self.x = Comp().at(x,
y)`, or `self.x.at(x, y)` if it already exists) — **not** `self.place(self.x, (x, y))`.

When a placed component and the geometry attached to it share the **same local
frame** (pin the anchor with `.at(0, 0)`, give attachments offsets in that frame), they
move together under interactive placement. Use `.at(0, 0)` here, not `place()`: `place()` records a
deferred placement request (and force-floats a placed *subcircuit*), so the anchor is not pinned in
the parent frame alongside its copper. Store attachments/vias/lanes as **list or
dataclass attributes** — never `getattr(self, f"via_{i}")` (see Anti-string-hacking).

Within a reusable circuit, code places only the anchor component whose frame local
geometry depends on. It leaves the other components to a placement solver or the
interactive layout instead of deriving offsets from nominal package sizes.
Captured pad extents can be measured for collisions and out-of-board bounds, but
capture cannot prove whether those positions were authored or auto-placed. Record
the placement plan separately instead of presenting that blind spot as an
enforced gate.

## Keepouts that shape pours

`KeepOut(shape, layers=LayerSet(...), pour=, via=, route=)` — **at least one** of
`pour` / `via` / `route` must be `True` or it is a no-op (the constructor warns):

- `pour=True` — keep pours out of this area
- `via=True` — block the auto-router from dropping vias here
- `route=True` — disallow auto-router traces here

`pour=True` is a hard boundary for pours at every rank. The
[Pour realization semantics](#pour-realization-semantics) section owns the
realization and verification rules.

**Local vs global pours.** Board-wide return-path pours belong in the **top-level**
design (the convention in `jitx-circuit-builder`). The exception: a local pour or
keepout that must **track a placed sub-circuit** lives **inside that circuit** so it
follows the circuit wherever it is placed. To ring an arbitrary shape with fence
vias (antipads, RF cavities, BGA
breakouts), see `jitx-substrate-modeler` "Fenced Pour Outlines".

## Layout-intent tags (object selection)

Use tags to **mark which physical objects** get special layout treatment; the
**rule** that defines the treatment (width, clearance, thermal relief, fence vias,
routing structure) is declared on the design or the owning circuit via
`design_constraint(...)`; see `jitx-layout-constraints`.

Apply with `MyLayoutTag().assign(obj)` or `Tags(tag_a, tag_b).assign(obj1, obj2)` —
always a `Tag` *subclass you define*, never the bare `Tag` base — inside a
design/circuit context. Supported object types: **`Net`, `TopologyNet`, `Copper`,
`Pour`, `Route`, `Component`, `Circuit`, `Landpattern`, `Pad`, `Via`,
`ControlPoint`** — note `OverlappableCopper` is *not* taggable.

Tagging a **container tags the copper objects inside it** — tag a `Landpattern`
and every pad in it inherits the tag; same for a `Component` or `Circuit`. Tag
`self` in a class `__init__` to tag *all instances* of that class. Assignment
outside a design-relevant context emits a `RuntimeWarning` and has no effect, and
assigning a `BuiltinTag` raises `TypeError` (builtins are rule conditions only;
see `jitx-layout-constraints`).

Common layout-intent tag roles (define the `Tag` subclasses in your design):

- **Fanout / escape** (`PinFanoutTag`, `PowerPinFanoutTag`, `BootstrapFanoutTag`) —
  local neckdown/escape for fine-pitch package pins, applied to short route segments
  or individual pads, overriding the board-wide width/clearance for the escape.
- **`FanoutPourKeepoutTag`** — ask pours to stay back from dense local fanout copper.
- **`DirectConnectTag`** — solid pour connection (no thermal-relief spokes) for
  high-current/high-dissipation pads; tag the component to tag all its pads.

The **"route two pads, then tag the route"** workflow — create a code-based route and
mark it for the escape rule:

```python
# Route a pin to its escape destination (both ports on the SAME net), then tag the segment:
r = Route(self.u1.SCL, self.header.SCL, layer=0)
self.routes = [r]                          # store on self so the structural walk sees it
Tags(PinFanoutTag()).assign(r)             # Route is a supported tag target
```

`Route` and the control-point types are detailed in
`references/control-points.md`.

## Control points & code-based routes

Surface reshaped in **JITX 4.3.0-rc.3+** (control points split netting from routing;
`PairPoint.pair` removed). The module is **`jitx.controlpoint`** (the three classes
are also re-exported from top-level `jitx`; pre-4.2 alphas used `SingleControl` /
`InsertionControl` / `PairControl` — those names no longer import).

- `Route(source, destination, layer, sketch=None)` — a code-based route (not
  directional) between two endpoints, each a `Port` / `Pad` / `Via` /
  `RouteConnectionEndpoint` / `RoutePoint` (a `RoutePoint` is unwrapped to its
  `.pad`); `sketch` is an optional routing hint — a plain list of `(x, y)` points
  (still accepted) or a `Route.Sketch`. No per-route width/clearance overrides —
  single-ended fanout: tag the route; **differential: tag the net** (per-route tags
  deform pair-point transitions).
- `RoutePoint(layer=..., shape=None, bundle=Port)` — the **single-ended** control
  point; **`.pad`** is the routing endpoint (`.port` is the separate netting port).
- `PairInsertion(layer=..., bundle=DiffPair, invert=False)` — differential-pair
  **insertion** point (uncoupled legs on one side via `.uncoupled.{n,p}`, coupled
  pair on the other via `.coupled`; `.port` nets the pair); `PairPoint(layer=...,
  bundle=DiffPair, invert=False)` — joins two coupled segments via **`.front`/`.back`**
  (routing) with `.port` for netting (the old `.pair` field is gone). Both are placed
  with `.at(point, rotate=)` and wired to ports via
  `PortAttachment([first, second], control)` — the order is a **positional binding**
  (`first → uncoupled.n`), and leg routes must target the bound port or they silently
  don't realize.

**Attachment order is ELECTRICAL, not geometric — chirality is `invert=`, never a
swapped attachment (4.3.0-rc.3+).** Always attach in the canonical order for the
bundle (`[p, n]`) and express p/n handedness with `invert=True` on the control point.
This is not a style preference: the linker enforces **per-conductor net consistency**
(p↔p, n↔n), so an attachment written in the reverse order to "flip" a pair no longer
produces crossed geometry — it produces a route with no consistent conductor path,
which **silently does not realize**. Older code that crossed the order to get the
geometry it wanted still builds `status: ok` and emits nothing. Measured on a real
migration: **109 of 128 routes dead**, every one of them passing every build gate,
found only by an external `route.traces` check. If you inherit a design that swaps
attachment order for chirality, treat every such site as a dead route until proven
otherwise.

Routes realize **silently or not at all** — `status: ok` proves nothing. After
every build, capture and assert `route.traces` on every route (see
`references/geometry-verification.md`). Full binding map, circuit-ownership
(common-ancestor) rule, explicit-Net requirement, known nested-circuit
realization bug + the deskew example: `references/control-points.md`.

**A `KeepOut` is not copper.** Like a via it must be a **structural** member (stored
on `self`) to reach the export, but unlike a via it must **never** be added to a net —
it carries no conductor. Adding one to a `Net` is a category error the build does not
reject.

## Anti-string-hacking

Geometry-heavy layout code tempts you into building a parallel string-keyed model
(`vias[f"r{r}c{c}"] = ...`) and walking it to emit JITX calls. Don't. Construct the
JITX objects directly; batch parameters with a `@dataclass(frozen=True)` or a plain
`list`; key dicts by `Port`/structural objects, never by an assembled string. If the
only key you have is a runtime-built string, the structural object you need is
missing. See the base `jitx` skill's `references/architectural-patterns.md`, and run
`jitx-code-review` as a self-critique pass on layout code.

## Verification

```bash
pyright path/to/layout.py        # verify imports/signatures against the installed package
ruff format path/to/layout.py
```

Then verify **realized geometry, not build success** (4.3 reverse flow): submit +
`capture()` the design through the runtime and assert against the concrete result —
`route.traces` non-empty for every route, `rd.query(Copper)` bounds where you meant
them, `rd.nets().find(...)` on every net-bearing feature. The full loop, the
`query`-vs-`visit` semantics, and the coordinate-frame rules are in
`references/geometry-verification.md` — this replaces screenshot/viewer checking
for code-authored layout. Validate shapely outputs (non-empty
`Polygon`/`MultiPolygon`) before they reach a fab feature. Sequence builds — don't
parallelize against the same design.

For pours, keepouts, stitching, and board-edge spacing, copy and run the shipped
checker. It submits and captures the zero-argument design target itself, checks
every authored `Pour`, reconstructs each stitching rule's selected pours, and
prints the witness paths. Use explicit names for stitching selections and
board-wide pours when the completion record needs stable human-facing aliases:

```bash
python scripts/check_realization.py my_project.designs.Design \
  --stitch-target circuit.thermal_ground \
  --board-wide-pour circuit.ground_return
```

Repeat either option as needed. The task and Phase 4 Physical realization rows
are blocked unless this exact command exits 0 and carry the authored-pour,
stitch-target, and board-wide-pour names it checked. Exit 2 means the capture or
geometry read did not run, not that the layout passed.

A `SampleDesign` harness is a smoke test, not a geometry acceptance environment.
Before the realization gate runs, the harness must carry the production substrate,
passive-query defaults, and board rule set. `check_realization.py` cannot compare a
harness configuration with production; record any mismatch as a limitation and do
not use a clean harness build to claim the shipping board's copper was checked.

## API Reference

Complete class definitions and parameters: [JITX Documentation](https://docs.jitx.com).
Worked examples: `references/layout-examples.md` (thermal-pad CSG, antenna),
`references/control-points.md` (Route / control points), and
`references/geometry-verification.md` (reverse-flow inspection & geometry checks).
