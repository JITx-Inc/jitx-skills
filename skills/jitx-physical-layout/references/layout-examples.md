# Physical Layout — Worked Examples

Real, build-tested patterns. Verify imports with `pyright` against the installed
package before reusing — JITX moves and APIs get renamed across releases.

## Table of Contents

- [Soldermask-defined thermal pad (shapely CSG + attached vias)](#soldermask-defined-thermal-pad)
- [OverlappableCopper antenna + local keepout and ground island](#overlappablecopper-antenna)
- [Custom-pad soldermask / paste helpers](#custom-pad-soldermask--paste-helpers)

## Soldermask-defined thermal pad

A cheap-fab alternative to filled via-in-pad: tented vias inside the chip's
exposed-pad copper, with a thin soldermask "dam" only around each via so reflowed
solder cannot wick down the unfilled barrels. The mask and paste opening is
computed with shapely CSG: the exposed-pad rectangle minus a perimeter frame,
linear webs, and circular via dams. The vias use the same coordinates as the
CSG, so every via sits under a dam and every paste cell is enclosed by mask.

Copy `jitx-layout-constraints/scripts/thermal_via_stitch.py` into the project,
then use it at the landpattern and circuit call sites. It raises `ValueError`
when the exposed pad cannot hold the grid or the opening is not a polygon; a
raise means change the grid, not skip the check. The substrate supplies
the soldermask bridge, registration, and copper-edge values. The selected via
class supplies its pad diameter.

```python
from jitx import Pad, current
from jitx.inspect import visit

from my_project.thermal_via_stitch import (
    StitchParams,
    ThermalViaField,
    grid_thermal_via_positions,
    soldermask_defined_thermal_pad_config,
)


class ThermalStitchVia(current.design.substrate.StdViaPreferred):
    """The substrate's preferred via, declared for use inside a pad.

    The library class carries via_in_pad = False; a via inside an exposed pad
    needs a class that says otherwise, declared here rather than by mutating
    the library class. Confirm with the fab that tented, unfilled vias inside
    a pad are accepted before using it.
    """

    via_in_pad = True

# Landpattern side. Read the exposed-pad shape back from the generated
# landpattern, then replace its standard feature config with the CSG config.
via_class = ThermalStitchVia
params = StitchParams.from_substrate(current.design.substrate.constraints, via_class)
# visit, not query: query opens the substrate context and needs a design root
ep_pad = next(
    (pad for _, pad in visit(landpattern, Pad) if pad in landpattern.thermal_pads),
    None,
)
if ep_pad is None:
    raise ValueError("landpattern has no thermal pad to stitch")
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
pads** (feed + short) that carry the nets, plus the radiating shape drawn as
**netless `OverlappableCopper`** that overlaps those pads. A local keepout lives
inside the circuit so it tracks the antenna wherever it is placed.

```python
import jitx
from jitx import Board, Design, OverlappableCopper, PadMapping, Pour, Tag
from jitx.circuit import Circuit
from jitx.constraints import ViaFencePattern, design_constraint
from jitx.feature import KeepOut
from jitx.landpattern import Landpattern, Pad
from jitx.layerindex import LayerSet
from jitx.net import Net, Port
from jitx.shapes.composites import rectangle
from jitxlib.jlcpcb import JLC04161H_7628
from jitxlib.symbols.box import BoxSymbol


class AntennaGroundTag(Tag):
    """Marks the local RF ground island for the design's fence-via rule."""


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

        # Local keepout that tracks the antenna. KeepOut clears the board's
        # pours, automatic vias, and autorouted traces from the antenna region.
        # NOTE on flags (per the KeepOut API): route=True DISALLOWS autorouter traces,
        # via=True blocks auto-vias, pour=True keeps pours out. Set the flags to the
        # behavior you actually want — here we want no stray traces/vias/pours under
        # the antenna, so all three are True.
        island = rectangle(35.0, 9.5).at(13.0, 4.75)
        self.keepouts = [
            KeepOut(shape=island, layers=LayerSet(layer), pour=True, via=True, route=True)
            for layer in (0, 1, 2, -1)
        ]

        # Correct local-ground-island pattern: a pour in the HOLE of a pour
        # keepout ring, never under the keepout itself. This island surrounds the
        # short anchor below the antenna region; the GND pad anchors its net on L1.
        local_island = rectangle(3.0, 2.0).at(0.25, -4.8)
        local_moat = (
            local_island.to_shapely().buffer(0.8)
            - local_island.to_shapely().buffer(0.2)
        )
        self.keepouts.append(
            KeepOut(
                shape=local_moat,
                layers=LayerSet(0),
                pour=True,
                via=False,   # allow the fence-via rule to ring the island
                route=False,
            )
        )
        self.gnd_island = Pour(local_island, layer=0)
        self.GND += self.gnd_island
        AntennaGroundTag().assign(self.gnd_island)


class AntennaBoard(Board):
    shape = rectangle(50.0, 30.0)


class AntennaDesign(Design):
    board = AntennaBoard()
    substrate = JLC04161H_7628()
    circuit = AntennaMatching()
    antenna_ground_fence = design_constraint(AntennaGroundTag()).fence_via(
        JLC04161H_7628.StdViaPreferred,
        ViaFencePattern(pitch=1.0, offset=0.5, num_rows=1),
    )
```

> The original project file commented `route=False` as "so signal traces can't cross
> the antenna region" — that comment is backwards: with the JITX `KeepOut` API,
> `route=True` is what disallows autorouter traces. The example above uses the correct
> flag. Always read the `route`/`via`/`pour` semantics from `jitx/feature.py`.

`KeepOut(pour=True)` excludes pours at every rank. It does not provide a local
ground-island exception. The replacement above uses disjoint geometry: the moat
keepout surrounds but does not overlap `gnd_island`, the short pad anchors that
island to GND, and `AntennaGroundTag` feeds the top-level `fence_via(...)` rule a
concrete `Pour` target. The realization command names `circuit.gnd_island` when a
stitch rule also selects it; a fence-via project check queries the computed
fence-via group separately. See the main skill's
[Pour realization semantics](../SKILL.md#pour-realization-semantics).

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
