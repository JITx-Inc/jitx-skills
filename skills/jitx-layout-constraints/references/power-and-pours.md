# Power Routing and Pours

This is the worked detail for `SKILL.md`, "Routed power" and "Pours". Use
[Rule Reference](rule-reference.md) for the complete condition and effect
surface. Rules remain structural (`jitx/_translate/design.py:187`). Higher priorities win when several rules match (`jitx/constraints.py:802`, `jitx/constraints.py:860`).

Source citations (`jitx/constraints.py:910` and the like) point into the
installed py-jitx package, `4.4.0rc5.dev2` build; line numbers move between
builds, so confirm on another install before relying on one.

Engineering basis: Eric Bogatin, ["Seven Habits of Successful 2-Layer Board Designers"](https://www.signalintegrityjournal.com/blogs/12-fundamentals/post/1207-seven-habits-of-successful-2-layer-board-designers),
Signal Integrity Journal, 2019-04-23. Only claims that article makes are attributed to it.

## 1. Width tiers as tags

For 1 oz copper, Bogatin 2019 gives these engineering tiers:

- 6 mil, 0.15 mm, and about 1 A DC (Bogatin 2019 tier).
- 20 mil, 0.5 mm, and about 3 A (Bogatin 2019 tier).
- 100 mil, 2.5 mm, and about 10 A (Bogatin 2019 tier).

The rules use `trace_width` (`jitx/constraints.py:910`). Tag inheritance lets a base-tag rule match subtags (`jitx/constraints.py:344`).

```python
from jitx.constraints import IsTrace, Tag, UnaryDesignConstraint
DEFAULT_PRIORITY = 0  # skill default: board-default priority 0
POWER_PRIORITY = 1  # skill default: shared power priority 1
CLASS_PRIORITY = 2  # skill default: rail and class priority 2
ESCAPE_PRIORITY = 4  # skill default: tagged escape priority 4, above every class rule and override

SIGNAL_WIDTH = 0.15  # Bogatin 2019 tier: 0.15 mm signal width, 1 oz copper
POWER_WIDTH = 0.5  # Bogatin 2019 tier: 0.5 mm power width, 1 oz copper
HIGH_CURRENT_WIDTH = 2.5  # Bogatin 2019 tier: 2.5 mm high-current width, 1 oz copper
RAIL_12V_WIDTH = 2.5  # Bogatin 2019 tier: 2.5 mm for this rail, 1 oz copper
class PowerTag(Tag):
    """Power routed at the shared power tier."""
class HighCurrentTag(PowerTag):
    """Power routed at the high-current tier."""
class Rail12VTag(PowerTag):
    """One rail whose width differs from the shared power tier."""
class EscapeTag(Tag):
    """A specific, short pad escape segment."""
# Store this list on the Design. The rule collector walks structural lists.
self.rules = [
    UnaryDesignConstraint(IsTrace, priority=DEFAULT_PRIORITY).trace_width(
        SIGNAL_WIDTH
    ),
    UnaryDesignConstraint(PowerTag(), priority=POWER_PRIORITY).trace_width(
        POWER_WIDTH
    ),
    UnaryDesignConstraint(HighCurrentTag(), priority=CLASS_PRIORITY).trace_width(
        HIGH_CURRENT_WIDTH
    ),
    UnaryDesignConstraint(Rail12VTag(), priority=CLASS_PRIORITY).trace_width(
        RAIL_12V_WIDTH
    ),
]
```

Assign the narrowest tag that states the rail's real requirement:

```python
PowerTag().assign(self.VDD_3V3)
HighCurrentTag().assign(self.MOTOR_SUPPLY)
Rail12VTag().assign(self.VIN_12V)
```

These are 1 oz engineering defaults, not a current-capacity calculation. The
fab's capability table or a measured temperature rise is the only reason to
change them. Record that replacement source on the same line as the new width.
Do not use an IPC current-carrying chart, formula, or coefficient here.

The class width stays on the trunk. A short tagged escape takes `ESCAPE_PRIORITY`
when the landpattern requires it (see `fanout.md`; when the class width fits the
pad there is no escape rule). Use a tag on a `Route` segment, never
`RoutingStructure.NeckDown`.

## 2. Power as traces

Bogatin's reason for routing power as traces is inspectable connectivity. A
trace exposes its path and width, while a fill hides the intended current path.
The policy is therefore: no board-wide power pours. The one exception is the
local pad-derived puddle in section 9.

The listed unary effects do not prevent Python from constructing a `Pour` (`jitx/constraints.py:871`). Enforce the
policy with a capture check, and use a binary clearance so the board-wide
ground pour stays away from power copper. Binary rules own clearance
(`jitx/constraints.py:1135`, `jitx/constraints.py:1160`).

```python
from collections.abc import Collection
from jitx import Net, Pour
from jitx.constraints import BinaryDesignConstraint, IsPour
def assert_only_local_power_puddles(
    rd,
    power_nets: Collection[Net],
    allowed_local_puddles: Collection[Pour],
) -> None:
    allowed = set(allowed_local_puddles)
    power_groups = {rd.nets().find(net) for net in power_nets}
    for _, pour in rd.query(Pour):
        net = rd.nets().find(pour)
        if net in power_groups and pour not in allowed:
            raise AssertionError(f"board-wide power pour: {pour}")
fab = self.substrate.constraints
POUR_PULLBACK_MARGIN = 0.11  # skill default: 0.11 mm beyond the fab floor
power_to_ground_pour = fab.min_copper_copper_space + POUR_PULLBACK_MARGIN  # FabricationConstraints floor plus skill default margin
self.rules.append(
    BinaryDesignConstraint(
        PowerTag(), IsPour, priority=CLASS_PRIORITY
    ).clearance(power_to_ground_pour)
)
```

`RuntimeDesign.query` and `RuntimeDesign.nets().find` are capture-side surfaces
(`jitx/run/runtime.py:421`, `jitx/run/runtime.py:565`). The clearance starts
with `min_copper_copper_space`, one of the enforced fabrication floors
(`jitx/substrate.py:165`). The added margin is a skill default, so change it
only when the design's coupling or voltage requirement supplies another
source.

## 3. Pad-to-via for power

Read the via class from the substrate. A via exposes its pad `diameter`, drill
`hole_diameter`, and `via_in_pad` capability (`jitx/via.py:60`,
`jitx/via.py:64`, `jitx/via.py:70`). Read `min_annular_ring` from the active
fabrication constraints (`jitx/substrate.py:178`).
`current.design` reads the active design context (`jitx/__init__.py:116`, `jitx/__init__.py:132`).

```python
from jitx import current
from jitx.constraints import BinaryDesignConstraint, IsVia
fab = current.design.substrate.constraints
via_cls = current.design.substrate.StdViaPreferred
via_pad_diameter = via_cls.diameter  # substrate via-class pad diameter
via_hole_diameter = via_cls.hole_diameter  # substrate via-class drill diameter
min_annular_ring = fab.min_annular_ring  # FabricationConstraints field
# FabricationConstraints.min_annular_ring is the total pad-minus-hole difference, not a
# per-side ring: JLCPCB's preferred via is 0.45 pad / 0.30 hole against a 0.13 field.
if via_pad_diameter - via_hole_diameter < min_annular_ring:
    raise ValueError("via pad minus hole is below the documented annular-ring floor")
VIAS_PER_TIER_STEP = 1  # skill default: 1 via per tier step; not a current derivation
def power_via_count(tier_step_count: int) -> int:
    """tier_step_count comes from the selected source and destination tiers.

    This skill carries no per-via current model. When the rail current or a
    thermal requirement matters, take the per-via figure from the fab's or the
    via manufacturer's data and record its source; without one, the via count
    is an open item, not this default.
    """
    return tier_step_count * VIAS_PER_TIER_STEP
VIA_CLEARANCE_MARGIN = 0.11  # skill default: 0.11 mm beyond the fab floor
power_via_clearance = fab.min_copper_copper_space + VIA_CLEARANCE_MARGIN  # FabricationConstraints floor plus skill default margin
self.rules.append(
    BinaryDesignConstraint(
        PowerTag(), IsVia, priority=CLASS_PRIORITY
    ).clearance(power_via_clearance)
)
```

The JLCPCB example substrate exposes `StdViaPreferred.diameter = 0.45 mm` from its via class (`jitxlib/jlcpcb/vias.py:24`, `jitxlib/jlcpcb/vias.py:34`).
That value is an example read from the substrate, not a portable default.

Set `via_in_pad` only on a via class whose fab process allows via-in-pad. The
example substrate's filled class sets `via_in_pad = True` and its ordinary
classes set it to false (`jitxlib/jlcpcb/vias.py:141`,
`jitxlib/jlcpcb/vias.py:157`). Do not mutate an ordinary via class to bypass
that capability decision.

## 4. Sense (Kelvin) lines

A Kelvin sense connection belongs to the circuit that owns the shunt. A sense
trace is usually on the power net it measures, so tag the sense route
segments (they then carry both tags, and the sense width rule needs a rung
above the power width); tag separate sense nets only when the schematic has
them, as in the example below. Give them the default signal width and a
two-condition clearance to power copper.

```python
from jitx.constraints import BinaryDesignConstraint, Tag, UnaryDesignConstraint
class SenseTag(Tag):
    """Kelvin sense nets kept off the measured current path."""
class ShuntMonitor(Circuit):
    def __init__(self) -> None:
        SenseTag().assign(self.SENSE_P, self.SENSE_N)
        self.rules = [
            UnaryDesignConstraint(
                SenseTag(), priority=CLASS_PRIORITY
            ).trace_width(SIGNAL_WIDTH),
        ]
fab = self.substrate.constraints
SENSE_CLEARANCE_MARGIN = 0.11  # skill default: 0.11 mm beyond the fab floor
sense_power_clearance = fab.min_copper_copper_space + SENSE_CLEARANCE_MARGIN  # FabricationConstraints floor plus skill default margin
self.rules.append(
    BinaryDesignConstraint(
        SenseTag(), PowerTag(), priority=CLASS_PRIORITY
    ).clearance(sense_power_clearance)
)
```

`SenseTag` and its circuit rule must remain structural attributes. Tag
assignment supports nets, copper, pads, vias, routes, components, and circuits
(`jitx/constraints.py:495`, `jitx/constraints.py:565`).

## 5. Pours

Put one board-wide ground pour on the return layer below the routed signal
layer. The top-level circuit owns it. See the circuit builder's
`references/advanced-patterns.md`, "Pours", for net attachment and placement.
Bogatin recommends top-layer components, signals, and power traces over a
continuous ground return. Do not rely on a top-layer ground fill as the return.
Pour materialization, placement prerequisites, edge pullback, empty output, and
capture semantics are owned by
[Pour realization semantics](../../jitx-physical-layout/SKILL.md#pour-realization-semantics).

```python
from jitx import current
from jitx.constraints import (
    BinaryDesignConstraint,
    IsHole,
    IsPour,
    IsThroughHole,
    IsTrace,
    OnLayer,
)
# Inside the top-level circuit's __init__. Creation of self.ground_return uses
# the edge-pullback pattern owned by jitx-physical-layout at the link above.
fab = current.design.substrate.constraints
TRACE_POUR_MARGIN = 0.11  # skill default: 0.11 mm beyond the fab floor
trace_pour_clearance = fab.min_copper_copper_space + TRACE_POUR_MARGIN  # FabricationConstraints floor plus skill default margin
pour_hole_clearance = fab.min_copper_hole_space  # FabricationConstraints field
self.rules.extend(
    [
        BinaryDesignConstraint(
            IsTrace & OnLayer(return_layer),
            IsPour & OnLayer(return_layer),
            priority=POWER_PRIORITY,
        ).clearance(trace_pour_clearance),
        BinaryDesignConstraint(
            IsPour & OnLayer(return_layer),
            IsHole,
            priority=POWER_PRIORITY,
        ).clearance(pour_hole_clearance),
        BinaryDesignConstraint(
            IsPour & OnLayer(return_layer),
            IsThroughHole,
            priority=CLASS_PRIORITY,
        ).clearance(pour_hole_clearance),
    ]
)
```

`OnLayer(index)` is a rule condition, and negative indices count from the
bottom (`jitx/constraints.py:471`). `Pour` takes one integer layer and joins a
net through membership (`jitx/copper.py:46`, `jitx/copper.py:71`). The
`isolate=` argument is deprecated in 4.4. Use clearance rules instead
(`jitx/copper.py:54`).

## 6. Heavy copper

`Stackup.conductors` returns the ordered conducting layers, and each
`Conductor` carries `thickness` in millimeters (`jitx/stackup.py:54`,
`jitx/stackup.py:112`). Find heavy layers from the modeled stackup. Do not type
a guessed layer index.

```python
from jitx import current
from jitx.constraints import BinaryDesignConstraint, IsCopper, OnLayer
def layers_over_thickness(threshold_mm: float) -> list[int]:
    """threshold_mm comes from the fab's copper-weight row."""
    conductors = current.design.substrate.stackup.conductors
    return [
        index
        for index, conductor in enumerate(conductors)
        if conductor.thickness is not None
        and conductor.thickness > threshold_mm
    ]
def heavy_copper_spacing_rules(
    threshold_mm: float,
    c_heavy: float,
) -> list[BinaryDesignConstraint]:
    """c_heavy comes from the fab's heavy-copper spacing row."""
    return [
        BinaryDesignConstraint(
            IsCopper & OnLayer(index),
            IsCopper,
            priority=POWER_PRIORITY,
        ).clearance(c_heavy)
        for index in layers_over_thickness(threshold_mm)
    ]
# Both arguments are user-supplied values copied from the selected fab row.
self.heavy_copper_rules = heavy_copper_spacing_rules(
    fab_heavy_threshold_mm,
    fab_heavy_spacing_mm,
)
```

There is no heavy-copper spacing field in `FabricationConstraints`; its full
field list contains the four enforced copper floors and documentation fields
only (`jitx/substrate.py:154`, `jitx/substrate.py:161`). Keep `c_heavy` as a
required user parameter.

`OnLayer.internal()` is wrong for this job because it matches every conductor
that is not an external layer (`jitx/constraints.py:486`). A per-index
`OnLayer(index)` rule changes only the conductor whose modeled thickness
crossed the threshold.

The substrate class does not expose every field the same way. A fabrication
floor such as `JLC04161H_7628.constraints.min_copper_edge_space` is readable at
class scope, while `JLC04161H_7628.stackup.conductors` is a deferred
`InstantiableAttribute`; calling `len()` on it raises `TypeError`. Instantiating
the substrate outside a design context also does not make the stackup readable.
The heavy-copper rule builder runs inside the design context through
`current.design.substrate.stackup.conductors` and stops if that value has not
resolved to the conductor sequence.

The predefined example stackup models 0.035 mm outer copper (`jitxlib/jlcpcb/JLC04161H_7628.py:16`) and 0.0152 mm inner copper (`jitxlib/jlcpcb/JLC04161H_7628.py:17`). If a fab quote calls for a thicker
layer, update the substrate before generating the rules.

## 7. Sliver removal

`pour_feature_size` clips pour regions that cannot contain a circle of the
given minimum width, excluding thermal spokes (`jitx/constraints.py:309`,
`jitx/constraints.py:1038`). Start with the selected fab's copper-width floor.

```python
from jitx.constraints import IsPour, design_constraint
from jitxlib.jlcpcb.rules import JLCPCBRules
min_pour_feature = JLCPCBRules.min_copper_width  # JLCPCBRules floor: 0.09 mm copper width
self.rules.append(
    design_constraint(IsPour, priority=DEFAULT_PRIORITY).pour_feature_size(
        min_pour_feature
    )
)
```

The JLCPCB example floors are:

- 0.09 mm minimum copper width (`jitxlib/jlcpcb/rules.py:8`).
- 0.09 mm copper-to-copper clearance (`jitxlib/jlcpcb/rules.py:9`).
- 0.254 mm copper-to-hole clearance (`jitxlib/jlcpcb/rules.py:10`).
- 0.3 mm copper-to-edge clearance (`jitxlib/jlcpcb/rules.py:11`).

Read these fields from the selected substrate. The class values are examples, not constants to copy to another fab.

## 8. Direct connect

Result, observed on 4.4.0rc5.dev2 on one pad shape (a 1.6 mm round pad):
candidate 2 below produces a direct connect and candidate 1 does not. Before
reusing the pattern on another pad shape, size, or runtime, confirm with the
ODB++ export that the tagged pad's void is gone. A higher-priority `thermal_relief` whose spoke width
equals the pad diameter leaves the runtime's computed pour copper with no gap
and no spokes at the tagged pad, while a default-relief pad on the same net
keeps its four 0.2 mm spokes; the higher-priority rule carrying no effect leaves
both pads identical. Only two surfaces show that copper, the raw
`LayoutOutput.computed_shape` and the legacy ODB++ `features` file for the
pour's layer. Captured-query interpretation is owned by
[Pour realization semantics](../../jitx-physical-layout/SKILL.md#pour-realization-semantics);
`rd.query(Pour)` is not a valid witness for these voids on the tested 4.4 line
(numbers in `evals/cases/reference/direct-connect/NOTES.md`).

The installed Python surface has no direct-connect effect. A unary rule can
carry thermal relief, but the translator emits a thermal effect only when
`thermal_relief` was set (`jitx/_translate/rules.py:37`,
`jitx/_translate/rules.py:62`). That source fact does not establish whether a
higher-priority rule with no effect suppresses a lower-priority thermal.

The tested candidates, in order, are:

```python
class DirectConnectTag(Tag):
    """Pad selected for the direct-connect experiment."""
# Candidate 1, tested: higher-priority unary rule with no effect. No effect on the pour.
candidate_no_effect = design_constraint(
    DirectConnectTag(), priority=POWER_PRIORITY
)
# Candidate 2, tested: fab-floor gap with pad-wide overlapping spokes. Direct connect.
candidate_wide_spokes = design_constraint(
    DirectConnectTag(), priority=POWER_PRIORITY
).thermal_relief(
    JLCPCBRules.min_copper_copper_space,  # JLCPCBRules floor: 0.09 mm thermal gap
    TEST_PAD_DIAMETER,  # skill default: 1.6 mm spoke width equals test-pad diameter
    4,  # skill default: 4 overlapping spokes
)
```

Candidate 2 is the pattern; candidate 1 is recorded so nobody tries it again.
When reusing candidate 2, read the result on a surface that shows computed
pour copper. The reference case checked these surfaces:

1. `rd.query(Copper)` and `rd.query(Pour)` after capture
   (`jitx/run/runtime.py:421`), neither a voiding witness on the tested line.
2. The raw `LayoutOutput.computed_shape`, which reverse flow assigns back to
   an authored pour (`jitx/_translate/reverse_flow/linker.py:1313`,
   `jitx/_translate/reverse_flow/linker.py:1329`).
3. `Route.derived` for route-derived pours and features (`jitx/circuit.py:564`,
   `jitx/circuit.py:613`).
4. The legacy ODB++ `features` files, parsed around both test pads.

Surfaces 2 and 4 show the voided pour; surfaces 1 and 3 do not on the 4.4 line.
A successful build alone is not evidence of direct connection.

## 9. Power puddle from a pad list

This pad-union puddle has not yet been exercised against a runtime in a
reference design; treat it as the intended shape and verify the puddle's
copper after capture before relying on it. The shipped decoupling reference
uses a simpler rectangular corridor between the two pads it joins
(`_corridor` in its `design.py`), which has been built and captured.

Make a local puddle from pads in the circuit that owns them. `query` runs the
Pad-to-Copper transformer, and that transformer composes the accumulated frame
with `pad.transform` before yielding copper (`jitx/landpattern.py:173`,
`jitx/landpattern.py:187`). Convert the result back into the owner's local
frame before constructing the `Pour`.

```python
from collections.abc import Sequence
from shapely.ops import unary_union
from jitx import Circuit, Copper, Design, Net, Pad, Pour, current, query, visit
from jitx.shapes.shapely import ShapelyGeometry
def _owner_to_design(design: Design, owner: Circuit):
    for trace, circuit in visit(design, Circuit):
        if circuit is not owner:
            continue
        if trace.transform is None:
            raise ValueError("unresolved owner coordinate frame")
        if owner is design.circuit:
            return trace.transform
        if owner.transform is None:
            raise ValueError("nested puddle owner must be placed")
        return trace.transform * owner.transform
    raise ValueError("puddle owner is not reachable from the Design")
def add_power_puddle(
    design: Design,
    owner: Circuit,
    rail: Net,
    pads: Sequence[Pad],
    layer: int,
    buffer_mm: float,
) -> Pour:
    """Return the puddle Pour; the caller stores it and adds it to ``rail``.

    buffer_mm is supplied by the design and labeled at the call site.
    """
    wanted = set(pads)
    owner_from_design = ~_owner_to_design(design, owner)
    pad_geometries = []
    for trace, copper in query(design, Copper):
        if trace.parent not in wanted or copper.layer != layer:
            continue
        if trace.transform is None:
            raise ValueError("unresolved pad coordinate frame")
        local_shape = owner_from_design * trace.transform * copper.shape
        pad_geometries.append(local_shape.to_shapely().g)
    if len(pad_geometries) != len(wanted):
        raise ValueError("each selected pad must yield copper on the puddle layer")
    geometry = unary_union(pad_geometries).buffer(
        buffer_mm,
        cap_style="square",
        join_style="mitre",
    )
    if geometry.is_empty or geometry.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError(f"invalid puddle geometry: {geometry.geom_type}")
    return Pour(ShapelyGeometry(geometry), layer=layer)
PUDDLE_BUFFER = 0.5  # skill default: 0.5 mm pad-union buffer
# The owning circuit stores the pour and adds it to the rail; the helper only
# computes geometry (a free function must not mutate a circuit).
self.power_puddle = add_power_puddle(
    current.design,
    self,
    self.VDD,
    [self.c1.landpattern.vdd_pad, self.u1.landpattern.vdd_pad],
    self.power_layer,
    PUDDLE_BUFFER,
)
self.VDD += self.power_puddle
```

`query` yields transformed targets while preserving `trace.transform`
(`jitx/query.py:187`, `jitx/query.py:216`). `ShapelyGeometry` accepts a Shapely
geometry and converts polygon or multipolygon data into JITX primitives
(`jitx/shapes/shapely.py:21`, `jitx/shapes/shapely.py:64`). The pour remains an attribute of its positionable owner (`jitx/circuit.py:50`).

Do not pass `isolate=`. It is deprecated, and clearance belongs in the binary
rules from sections 2 and 5 (`jitx/copper.py:54`, `jitx/copper.py:71`).

## 10. Fill between signal traces

Do not add copper fill between signal traces as a crosstalk treatment. [Bogatin 2019](https://www.signalintegrityjournal.com/blogs/12-fundamentals/post/1207-seven-habits-of-successful-2-layer-board-designers)
states that such fill does not reliably reduce crosstalk and can increase it.
Keep the continuous return on the layer below, route signals on top, and solve
crosstalk with the trace geometry and spacing that the design requires. A top
fill is not a substitute for the return layer or for a sourced signal spacing.
