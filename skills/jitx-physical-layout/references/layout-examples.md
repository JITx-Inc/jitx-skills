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
solder cannot wick down the unfilled barrels. The mask and paste opening is
computed with shapely CSG: the exposed-pad rectangle minus a perimeter frame,
linear webs, and circular via dams. The vias use the same coordinates as the
CSG, so every via sits under a dam and every paste cell is enclosed by mask.

Copy `jitx-layout-constraints/scripts/thermal_via_stitch.py` into the project,
then use it at the landpattern and circuit call sites. The substrate supplies
the soldermask bridge, registration, and copper-edge values. The selected via
class supplies its pad diameter.

```python
from jitx import Pad
from jitx.query import query
from jitxlib.jlcpcb import JLC04161H_7628

from my_project.thermal_via_stitch import (
    StitchParams,
    ThermalViaField,
    grid_thermal_via_positions,
    soldermask_defined_thermal_pad_config,
)

# Landpattern side. Read the exposed-pad shape back from the generated
# landpattern, then replace its standard feature config with the CSG config.
via_class = JLC04161H_7628.StdViaPreferred
params = StitchParams.from_substrate(JLC04161H_7628.constraints, via_class)
ep_pad = next(pad for _, pad in query(landpattern, Pad) if pad in landpattern.thermal_pads)
min_x, min_y, max_x, max_y = ep_pad.shape.to_shapely().g.bounds
ep_size = (max_x - min_x, max_y - min_y)  # jitx.query landpattern Pad bounds
positions = grid_thermal_via_positions(
    ep_size=ep_size,
    via_grid=(4, 4),  # skill default: 4 columns by 4 rows.
    edge_margin=params.edge_margin,
    via_pad_diameter=params.via_pad_diameter,
)
config = soldermask_defined_thermal_pad_config(
    ep_size=ep_size,
    via_positions=positions,
    via_pad_diameter=params.via_pad_diameter,
    min_mask_bridge=params.min_mask_bridge,
    mask_expansion=params.mask_expansion,
    fillet_radius=params.fillet_radius,
)
landpattern.thermal_pad(shape=ep_pad.shape, config=config)

# Circuit side. Store the container structurally and use plain net membership.
self.amp = PowerAmp().at(thermal_anchor)
self.GND += self.amp.EP
self.thermal_vias = ThermalViaField(
    positions=positions,
    via_class=via_class,
    anchor=thermal_anchor,
)
for via in self.thermal_vias.vias:
    self.GND += via
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
from jitxlib.symbols.box import BoxSymbol


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
    symbol = BoxSymbol()             # components without a symbol fail translation

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
        self.ant = AntennaIFA().at(0, 0)
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
