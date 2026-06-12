# Physical Layout — Worked Examples

Real, build-tested patterns. Verify imports with `pyright` against the installed
package before reusing — JITX moves and APIs get renamed across releases.

## Table of Contents

- [Soldermask-defined thermal pad (shapely CSG + attached vias)](#soldermask-defined-thermal-pad)
- [OverlappableCopper antenna + local ground island](#overlappablecopper-antenna)
- [Custom-pad soldermask / paste helpers](#custom-pad-soldermask--paste-helpers)

## Soldermask-defined thermal pad

A cheap-fab alternative to filled via-in-pad: tented vias inside the chip's
exposed-pad copper, with a thin soldermask "dam" only around each via so reflowed
solder can't wick down the unfilled barrels. The mask/paste opening is computed with
shapely CSG (`EP_rect − (perimeter frame ∪ linear webs ∪ circular via dams)`), and
the vias are placed at the **same** coordinates the CSG used (so the dams land on
the vias) and joined to the ground net by **net membership** — not
`PortAttachment`, which is scoped to signal topologies.

```python
from collections.abc import Iterable, Sequence
import shapely
import jitx
from jitx import Container
from jitx.shapes import Shape
from jitx.shapes.shapely import ShapelyGeometry
from jitx.via import Via, ViaType
from jitxlib.landpatterns.pads import SMDPadConfig

# Module-scope via class. A custom via is justified here: JLCPCB charges nothing for
# a *tented* unfilled via inside a pad, and the design-rule resolver does not walk
# via classes inherited from a mixin — so it must be defined at module scope, not on
# the substrate. (Normally, source vias from the substrate / JLCPCB library.)
class ThermalStitchVia(Via):
    name = "Soldermask-Defined Thermal Via"
    start_layer = 0
    stop_layer = -1
    diameter = 0.45          # JLCPCB "Preferred Standard Via" pad
    hole_diameter = 0.30
    type = ViaType.MechanicalDrill
    tented = True            # tented both sides → no solder wicking, no upcharge
    via_in_pad = True


def grid_thermal_via_positions(
    *, ep_size: tuple[float, float], via_grid: tuple[int, int],
    edge_margin: float = 0.3, via_pad_diameter: float = 0.45,
) -> list[tuple[float, float]]:
    """Evenly-spaced cols×rows via grid in the EP-local frame (origin = EP center),
    inset so the outermost pad rim stays `edge_margin` from the EP edge."""
    nx, ny = via_grid
    ep_w, ep_h = ep_size
    inset = edge_margin + via_pad_diameter / 2.0

    def axis(extent: float, n: int) -> list[float]:
        if n <= 0:
            return []
        avail = extent - 2.0 * inset
        if avail < 0:
            raise ValueError(f"EP extent {extent} too small for {n} vias")
        if n == 1:
            return [0.0]
        step = avail / (n - 1)
        return [-avail / 2.0 + k * step for k in range(n)]

    xs, ys = axis(ep_w, nx), axis(ep_h, ny)
    return [(x, y) for y in ys for x in xs]


def soldermask_thermal_pad_opening(
    *, ep_size: tuple[float, float], via_positions: Iterable[tuple[float, float]],
    via_pad_diameter: float = 0.45, min_mask_bridge: float = 0.08,
    fillet_radius: float = 0.05,
) -> Shape:
    """Paste/soldermask opening = EP rectangle minus (frame ∪ web stripes ∪ via dams).
    `min_mask_bridge` (JLCPCB min soldermask bridge, 0.08 mm) is both the web width
    and the radial mask margin around each via pad."""
    ep_w, ep_h = ep_size
    ep_rect = shapely.box(-ep_w / 2, -ep_h / 2, ep_w / 2, ep_h / 2)

    positions = list(via_positions)
    if not positions:
        return ShapelyGeometry(ep_rect)

    half_stripe = min_mask_bridge / 2.0
    unique_xs = sorted({round(x, 6) for x, _ in positions})
    unique_ys = sorted({round(y, 6) for _, y in positions})
    parts: list[shapely.geometry.base.BaseGeometry] = []

    # Perimeter frame ring (closes the ends of the web stripes).
    inner_w, inner_h = ep_w - 2 * min_mask_bridge, ep_h - 2 * min_mask_bridge
    if inner_w > 0 and inner_h > 0:
        inner = shapely.box(-inner_w / 2, -inner_h / 2, inner_w / 2, inner_h / 2)
        parts.append(ep_rect.difference(inner))
    # Linear web stripes through each unique via X and Y.
    for x in unique_xs:
        parts.append(shapely.box(x - half_stripe, -ep_h / 2, x + half_stripe, ep_h / 2))
    for y in unique_ys:
        parts.append(shapely.box(-ep_w / 2, y - half_stripe, ep_w / 2, y + half_stripe))
    # Circular dam over each via (pad + bridge ring on every side).
    dam_radius = via_pad_diameter / 2.0 + min_mask_bridge
    for x, y in positions:
        parts.append(shapely.Point(x, y).buffer(dam_radius, resolution=24))

    opening = ep_rect.difference(shapely.unary_union(parts))
    if fillet_radius > 0:
        # Morphological open: round sharp inside corners of the paste cells.
        opening = opening.buffer(-fillet_radius, resolution=24).buffer(fillet_radius, resolution=24)
    # Guard before handing to a fab feature — only non-empty Polygon/MultiPolygon serialize.
    assert not opening.is_empty and opening.geom_type in ("Polygon", "MultiPolygon"), opening.geom_type
    return ShapelyGeometry(opening)


def soldermask_defined_thermal_pad_config(**kw) -> SMDPadConfig:
    """Both paste and soldermask use the CSG opening shape."""
    opening = soldermask_thermal_pad_opening(**kw)
    return SMDPadConfig(soldermask=opening, paste=opening)   # each field takes a Shape


class ThermalViaField(Container):
    """Placed thermal vias as a composed member. A `Container` subclass is the
    composition unit — its members are traversed by the structural walk. Do NOT
    write this as a free function that mutates the circuit
    (`def attach_thermal_vias(circuit, ...): circuit.xyz = ...` is an
    anti-pattern — see the base `jitx` skill's Don'ts)."""

    def __init__(
        self, *, positions: Sequence[tuple[float, float]],
        anchor: tuple[float, float] = (0.0, 0.0),
        via_class: type[Via] = ThermalStitchVia,
    ):
        ax, ay = anchor
        self.vias = [via_class().at(ax + dx, ay + dy) for dx, dy in positions]
```

Usage — component side builds the pad, circuit side places the chip at the same
anchor, composes the via field as a member, and joins the vias to the ground net
(thermal/ground vias are plain net membership — `Net` accepts `Via` members;
`PortAttachment` is reserved for signal topologies):

```python
# In the landpattern definition:
positions = grid_thermal_via_positions(ep_size=(3.45, 3.45), via_grid=(4, 4))
config = soldermask_defined_thermal_pad_config(ep_size=(3.45, 3.45), via_positions=positions)
landpattern.thermal_pad(shape=rectangle(3.45, 3.45), config=config)

# In the circuit where the chip is placed:
self.place(self.amp, (0, 0))
self.GND += self.amp.EP                     # the exposed pad is on ground
self.thermal_vias = ThermalViaField(positions=positions, anchor=(0.0, 0.0))
for via in self.thermal_vias.vias:
    self.GND += via                         # vias join the net — no PortAttachment
```

## OverlappableCopper antenna

A PCB inverted-F antenna. The structure is a small `Component` with two **anchor
pads** (feed + short) that carry the nets — so the router has explicit points to land
on — plus the radiating shape drawn as **netless `OverlappableCopper`** that overlaps
those pads. A local ground island (keepout + higher-rank pour) lives **inside** the
circuit so it tracks the antenna wherever it is placed.

```python
import jitx
from jitx import OverlappableCopper, PadMapping, Pour, Tag
from jitx.circuit import Circuit
from jitx.feature import KeepOut
from jitx.landpattern import Landpattern, Pad
from jitx.layerindex import LayerSet
from jitx.net import Net, Port
from jitx.shapes.composites import rectangle


# Define Tag subclasses at MODULE scope — never inside a method (subclassing a JITX
# class in a function breaks instantiation tracking; see base skill conventions).
class AntennaGroundTag(Tag):
    """Marks the antenna's local GND pour for the substrate's fence-via rule."""


class _AnchorPad(Pad):
    shape = rectangle(0.6, 0.6)


class _AnchorLandpattern(Landpattern):
    # 1-based pad collection — matches the lp.p[1]/lp.p[2] mapping below.
    p = {1: _AnchorPad().at(3.25, -4.8), 2: _AnchorPad().at(0.25, -4.8)}


class AntennaIFA(jitx.Component):
    """Two anchor pads (feed + short). The radiator copper is added by the enclosing
    circuit as OverlappableCopper — keeping the tunable shape out of the component."""
    mpn = "PCB_IFA_16x6_v1"
    manufacturer = "JITX (PCB structure)"
    reference_designator_prefix = "ANT"
    feed = Port()
    short = Port()
    landpattern = _AnchorLandpattern()

    def __init__(self) -> None:
        lp = self.landpattern
        self.mappings = [PadMapping({self.feed: [lp.p[1]], self.short: [lp.p[2]]})]


class AntennaMatching(Circuit):
    rfio_in = Port()
    gnd = Port()

    def __init__(self) -> None:
        self.GND = Net(name="GND"); self.GND += self.gnd
        self.ANT_FEED = Net(name="ANT_FEED")
        # ... π-network matching components (elided) land RFIO → ANT_FEED ...

        # Anchor component at the circuit origin; the radiator copper shares this frame.
        self.ant = AntennaIFA()
        self.place(self.ant, (0, 0))
        self.ANT_FEED += self.ant.feed     # pads carry the nets
        self.GND      += self.ant.short

        # Radiator / legs are NETLESS OverlappableCopper overlapping the pads — the
        # electrical path is through the pads, so these overlaps don't trip DRC.
        self.copper_radiator  = OverlappableCopper(rectangle(26.0, 1.0).at(13.0, 5.5), layer=0)
        self.copper_feed_leg  = OverlappableCopper(rectangle(0.5, 10.0).at(3.25, 0.0), layer=0)
        self.copper_short_stub = OverlappableCopper(rectangle(0.5, 10.0).at(0.25, 0.0), layer=0)

        # Local ground island that tracks the antenna. KeepOut clears the board's
        # default pour/vias/traces from the antenna region; a higher-rank GND Pour of
        # the same shape fills GND back on the radiator's layer.
        # NOTE on flags (per the KeepOut API): route=True DISALLOWS autorouter traces,
        # via=True blocks auto-vias, pour=True keeps pours out. Set the flags to the
        # behavior you actually want — here we want no stray traces/vias/pours under
        # the antenna, so all three are True.
        island = rectangle(35.0, 9.5).at(13.0, 4.75)
        self.keepouts = [
            KeepOut(shape=island, layers=LayerSet(layer), pour=True, via=True, route=True)
            for layer in (0, 1, 2, -1)
        ]
        self.gnd_pour = Pour(island, layer=0, rank=1)   # rank=1 overrides the keepout for GND
        self.GND += self.gnd_pour

        # Tag the pour so the substrate's fence-via rule selects it. This skill owns the
        # tagged-pour GEOMETRY; the design_constraint(AntennaGroundTag()).fence_via(...)
        # RULE that rings it with vias is declared in the substrate / top-level design —
        # see jitx-substrate-modeler "Fenced Pour Outlines".
        AntennaGroundTag().assign(self.gnd_pour)
```

> The original project file commented `route=False` as "so signal traces can't cross
> the antenna region" — that comment is backwards: with the JITX `KeepOut` API,
> `route=True` is what disallows autorouter traces. The example above uses the correct
> flag. Always read the `route`/`via`/`pour` semantics from `jitx/feature.py`.

`AntennaGroundTag` is defined at **module scope** above — subclassing a JITX class
inside a method breaks instantiation tracking (see the base skill conventions). The
fence-via *rule* that consumes the tag lives in `jitx-substrate-modeler`; this example
owns only the tagged-pour geometry.

## Custom-pad soldermask / paste helpers

Custom `Pad` subclasses emit no default mask/paste. These helpers add them, preserving
a `Circle` exactly (so a round pad doesn't become a 16-gon) and expanding everything
else as a shapely polygon. Mask expansion defaults to JLCPCB's
`solder_mask_registration` (0.05 mm); paste matches the copper exactly.

```python
from jitx.feature import Paste, Soldermask
from jitx.shapes import Shape
from jitx.shapes.primitive import Circle

DEFAULT_MASK_EXPANSION_MM = 0.05

def _expand_shape(shape: Shape, amount: float) -> Shape:
    if amount == 0:
        return shape
    if isinstance(shape, Circle):
        return Circle(diameter=shape.diameter + 2.0 * amount)   # keep true circle
    return shape.to_shapely().buffer(amount, cap_style="square", join_style="mitre")

def smt_soldermask(shape: Shape, *, mask_expansion: float = DEFAULT_MASK_EXPANSION_MM) -> Soldermask:
    return Soldermask(_expand_shape(shape, mask_expansion))

def smt_paste(shape: Shape) -> Paste:
    return Paste(shape)                       # paste matches copper exactly

def th_soldermask(shape: Shape, *, mask_expansion: float = DEFAULT_MASK_EXPANSION_MM) -> Soldermask:
    return Soldermask(_expand_shape(shape, mask_expansion))   # TH pads: mask, no paste
```
