---
name: jitx-physical-layout
description: This skill should be used when the user asks to author PCB physical layout from code — "draw copper from code", "create an antenna" / "filter copper" / "net tie" / "overlapping copper", build a "custom shape" or board outline with shapely, add a "custom pad shape", "soldermask/paste opening", or "thermal pad with vias", "place vias from code" / "attach a via to a pad", apply "fanout / escape tags" or "direct-connect / thermal-relief" to layout objects, or (advanced) add "control points" and "code-based routes" for escape routing or deskew. Covers shapely shape creation feeding ANY feature, Copper vs OverlappableCopper vs Pour, pad features (Soldermask/Paste/SMDPadConfig/thermal_pad), PortAttachment + explicit placement, layout-intent tags, and the Route / control-point API (RoutePoint / PairInsertion / PairPoint, stable as of JITX 4.2). For stackup, via definitions, routing structures, fence-via rules, and fenced pour outlines use jitx-substrate-modeler; for net wiring, passives, and basic pours use jitx-circuit-builder.
---

# JITX Physical Layout

Author physical layout geometry — copper, custom shapes, pad features, explicit
placement, code-driven vias/routes, and layout-intent tags — directly in Python.
This is the layer **between** schematic-level wiring (`jitx-circuit-builder`) and
stackup/fab definition (`jitx-substrate-modeler`).

JITX is a moving target — APIs on this page have been renamed across releases
(most recently the control-point classes in 4.2.0). Do not rely on prior JITX
knowledge — **verify every import and signature with `pyright` against the
installed package**, and build-test control-point/route geometry before
trusting it.

## Scope — what this skill owns vs neighbors

| You want to… | Skill |
|---|---|
| Draw copper shapes, antennas, filters, net-ties, custom board/pad geometry | **this skill** |
| Build a shape with shapely and feed it to any feature | **this skill** |
| Add soldermask/paste/thermal-pad features, place vias/components from code | **this skill** |
| Tag layout objects (fanout, escape, direct-connect) for selection | **this skill** (rule *mechanics* → substrate-modeler) |
| Code-based routes & control points (escape lanes, deskew) | **this skill** (advanced — see reference) |
| Wire nets, add passives, voltage dividers, basic pours | `jitx-circuit-builder` |
| Define the stackup, vias, routing structures, fence-via rules, fenced pour outlines | `jitx-substrate-modeler` |
| Author a component's package/landpattern from a datasheet | `jitx-component-modeler` |
| Topology (`>>`), timing/skew/impedance constraints | `jitx-interconnect-constraints` |

This skill covers the design-side *geometry and placement*; the substrate owns the
*rule definitions* (`design_constraint(...)`, via classes, routing structures) that
act on it. Where they meet, this skill cross-references rather than restating.

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
`jitx.layout`, `jitx.routes`. When unsure, search the installed source:

```bash
grep -rn "class OverlappableCopper\|class Route\|class PortAttachment" .venv/lib/python*/site-packages/jitx/
```

## Custom shapes with shapely (general)

Shapely is general shape creation for **any** JITX feature that takes a `Shape` —
copper, pours, keepouts, the board outline, courtyards, and pad soldermask/paste.
It is not pad-specific.

Reach for a **built-in composite first** for common shapes — they stay exact
(`rectangle`, `capsule`, `Circle`, `notch_rectangle`, `chipped_circle`, `bullseye`,
`equilateral_triangle`, …). Use **shapely** when you need CSG (union / difference /
intersection), buffering, fillets, or arbitrary polygons.

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

Four ways to put copper on a layer — pick by **net membership** and whether the
copper is allowed to **overlap** other copper:

| Construct | On a net? | Overlap-exempt? | Use for |
|---|---|---|---|
| `Pour(shape, layer, *, rank=0, orphans=True)` | yes (`net += Pour(...)`) | no | filled planes / shaped fills |
| `Copper(shape, layer)` | yes (`net += Copper(...)` or `a + Copper(...)`) | no | an explicit copper shape on one net |
| `Copper(shape, layer, exempt=True)` | yes | **yes** | net-tie copper that intentionally bridges/overlaps two nets' copper |
| `OverlappableCopper(shape, layer)` | **no** (netless) | **yes** | antenna radiators, filter copper, decorative/RF fill that overlaps pads — ignored by the router and overlap checks |

`Copper` lives in `jitx` (top-level / `jitx.copper`); `OverlappableCopper` lives in
`jitx.feature`.

```python
from jitx import Copper, Pour
from jitx.feature import OverlappableCopper

self.GND += Pour(current.design.board.shape, layer=0)     # board-wide top pour
self.SIG += Copper(rectangle(10, 0.5).at(0, 5), layer=0)  # copper shape on a net
```

**OverlappableCopper is netless.** Its electrical connection comes from the **pads it
overlaps**, not from the copper itself. The antenna pattern: give the structure a
small `Component` with anchor pads that *are* on the nets (so the router has
something to land on), then draw the radiating shape as `OverlappableCopper`
overlapping those pads:

```python
self.ant = AntennaIFA()                 # component with feed + short anchor pads
self.place(self.ant, (0, 0))
self.ANT_FEED += self.ant.feed          # pads carry the nets
self.GND      += self.ant.short
# radiator shape is netless copper overlapping the pads — no DRC overlap error:
self.copper_radiator = OverlappableCopper(radiator_shape, layer=0)
```

Note `OverlappableCopper` is **not** in the set of tag-able objects (see Tags below).
The full antenna example is in `references/layout-examples.md`.

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

`PortAttachment(port_or_ports, attachment)` connects a port (or a sequence of ports)
to a placed **`Copper` | `Via` | `ControlPoint`** at a fixed location:

```python
from jitx.net import PortAttachment
# Source the via class from the substrate / JLCPCB library — do NOT redefine vias here:
via_cls = substrate.signal_via[layer]          # or: from jitxlib.jlcpcb.vias import JLCPCBVias
self.attachments = [
    PortAttachment(self.amp.EP, via_cls().at(x, y))
    for (x, y) in via_positions                 # list, not a string-keyed dict
]
```

**Vias are defined in the substrate**, not here (see `jitx-substrate-modeler`). This
skill *attaches* placed instances of them. Define a custom module-scope `Via`
subclass only with a fab-verified reason — e.g. the tented-unfilled thermal via in
the thermal-pad example, where JLCPCB charges nothing for tented vias inside a pad.

Placement:

```python
self.led = LED().at(10.0, 5.0, rotate=90)          # x, y, rotate (deg), on=Side
self.led_b = LED().at(10.0, 5.0, on=Side.Bottom)
self.place(self.amp, (0, 0))                       # Circuit.place — anchor in local frame
self.subckt = MySub().at(floating=True)            # layout engine decides position
```

When a placed component and the geometry attached to it share the **same local
frame** (place the anchor at `(0, 0)`, give attachments offsets in that frame), they
move together under interactive placement. Store attachments/vias/lanes as **list or
dataclass attributes** — never `getattr(self, f"via_{i}")` (see Anti-string-hacking).

## Keepouts that shape pours

`KeepOut(shape, layers=LayerSet(...), pour=, via=, route=)` — **at least one** of
`pour` / `via` / `route` must be `True` or it is a no-op (the constructor warns):

- `pour=True` — keep pours out of this area
- `via=True` — block the auto-router from dropping vias here
- `route=True` — disallow auto-router traces here

A higher-`rank` `Pour` of the same shape fills back **over** a keepout — the pattern
for a deliberately-shaped local ground island (e.g. around an antenna) that the
board-wide pour is otherwise cleared from.

**Local vs global pours.** Board-wide return-path pours belong in the **top-level**
design (the convention in `jitx-circuit-builder`). The exception: a local
pour/keepout that must **track a placed sub-circuit** — like an antenna's ground
island — lives **inside that circuit** so it follows the circuit wherever it is
placed. To ring an arbitrary shape with fence vias (antipads, RF cavities, BGA
breakouts), see `jitx-substrate-modeler` "Fenced Pour Outlines".

## Layout-intent tags (object selection)

Use tags to **mark which physical objects** get special layout treatment; the
**rule** that defines the treatment (width, clearance, thermal relief, fence vias,
routing structure) is declared in the substrate or top-level design via
`design_constraint(...)` — see `jitx-substrate-modeler`.

Apply with `MyLayoutTag().assign(obj)` or `Tags(tag_a, tag_b).assign(obj1, obj2)` —
always a `Tag` *subclass you define*, never the bare `Tag` base — inside a
design/circuit context. Supported object types: **`Net`, `TopologyNet`, `Copper`,
`Pour`, `Route`, `Component`, `Circuit`, `Landpattern`, `Pad`, `Via`,
`ControlPoint`** — note `OverlappableCopper` is *not* taggable.

Tagging a **container tags the copper objects inside it** — tag a `Landpattern`
and every pad in it inherits the tag; same for a `Component` or `Circuit`. Tag
`self` in a class `__init__` to tag *all instances* of that class. Assignment
outside a design-relevant context emits a `RuntimeWarning` and has no effect, and
assigning a `BuiltinTag` raises `TypeError` (builtins are rule conditions only —
see `jitx-substrate-modeler`).

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

## Control points & code-based routes (ADVANCED)

Stable as of **JITX 4.2.0**. The module is **`jitx.controlpoint`** (the three
classes are also re-exported from top-level `jitx`). The classes were **renamed in
4.2.0** — pre-release alphas called them `SingleControl` / `InsertionControl` /
`PairControl`; those names no longer import.

- `Route(source, destination, layer, sketch=None)` — a code-based route between two
  `Port`/`Pad`/`Via` endpoints (not directional); `sketch` is an optional list of
  points hinting the routing engine. No per-route width/clearance overrides — tag
  the route and write a `design_constraint(...)` rule instead.
- `RoutePoint(layer=..., shape=None, bundle=Port)` — the **single-ended** control
  point; its `.port` is the routable endpoint.
- `PairInsertion(layer=..., bundle=DiffPair)` — differential-pair **insertion**
  point (uncoupled legs on one side via `.uncoupled.{n,p}`, coupled pair on the
  other via `.coupled`); `PairPoint(layer=..., bundle=DiffPair)` — joins two
  coupled segments via `.pair`. Both are placed with `.at(point, rotate=)` and
  wired to ports via `PortAttachment([n, p], control)` — port **order sets
  chirality** for `PairInsertion`.

Full pattern, chirality rules + the real BGA escape/deskew example:
`references/control-points.md`.

## Anti-string-hacking

Geometry-heavy layout code tempts you into building a parallel string-keyed model
(`vias[f"r{r}c{c}"] = ...`) and walking it to emit JITX calls. Don't. Construct the
JITX objects directly; batch parameters with a `@dataclass(frozen=True)` or a plain
`list`; key dicts by `Port`/structural objects, never by an assembled string. If the
only key you have is a runtime-built string, the structural object you need is
missing. See the base `jitx` skill's `references/architectural-patterns.md`, and run
`jitx-skills:jitx-code-review` as a self-critique pass on layout code.

## Verification

```bash
pyright path/to/layout.py        # verify imports/signatures against the installed package
ruff format path/to/layout.py
```

Then build-test with a `SampleDesign` harness (see `jitx-circuit-builder`
"Verification Process"); sequence builds — don't parallelize against the same
design. Validate shapely outputs (non-empty `Polygon`/`MultiPolygon`) before they
reach a fab feature.

## API Reference

Complete class definitions and parameters: [JITX Documentation](https://docs.jitx.com).
Worked examples: `references/layout-examples.md` (thermal-pad CSG, antenna) and
`references/control-points.md` (Route / control points).
