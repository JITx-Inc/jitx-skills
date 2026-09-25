# Power and pour owners

- Width tiers and tag/rule implementations: `jitxexamples.patterns.complete_rules`;
  current-to-tier selection: [skill workflow](../SKILL.md#where-a-net-class-gets-its-number).
- Pours, layer selection, sliver removal, and fill geometry:
  [Pours](https://docs.jitx.com/en/latest/essentials/physical_design/pours.html).
  Pour rule effects: installed `jitx.constraints`; capture limits:
  [pour realization semantics](../../jitx-physical-layout/SKILL.md#pour-realization-semantics).
- Direct connect: `jitxexamples.patterns.direct_connect`, including its versioned receipt.
- Fill between signal traces and the engineering basis for routed power:
  Eric Bogatin, [Seven Habits of Successful 2-Layer Board Designers](https://www.signalintegrityjournal.com/blogs/12-fundamentals/post/1207-seven-habits-of-successful-2-layer-board-designers),
  Signal Integrity Journal, 2019-04-23.

Power-as-traces policy (including local puddles), pad-to-via sizing, Kelvin
lines, and heavy-copper rules have no worked owner and remain below. Snippets
use the project's power tag, sourced signal width, class priority, and protection
priority from the [rule ladder](../SKILL.md#workflow).
Source line citations and library dimensions were read on a 4.4.0 install;
confirm them against the selected substrate and installed source.

## Power as traces

Bogatin's reason for routing power as traces is inspectable connectivity. A
trace exposes its path and width, while a fill hides the intended current path.
The policy is therefore: no board-wide power pours. The one exception is the
local pad-derived puddle under [local power puddles](#power-puddle-from-a-pad-list).

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
        PowerTag(), IsPour, priority=PROTECTION_PRIORITY
    ).clearance(power_to_ground_pour)
)
```

`RuntimeDesign.query` and `RuntimeDesign.nets().find` are capture-side surfaces
(`jitx/run/runtime.py:421`, `jitx/run/runtime.py:565`). The clearance starts
with `min_copper_copper_space`, one of the enforced fabrication floors
(`jitx/substrate.py:165`). The added margin is a skill default, so change it
only when the design's coupling or voltage requirement supplies another
source.

## Pad-to-via for power

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
        PowerTag(), IsVia, priority=PROTECTION_PRIORITY
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

## Sense (Kelvin) lines

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
        SenseTag(), PowerTag(), priority=PROTECTION_PRIORITY
    ).clearance(sense_power_clearance)
)
```

`SenseTag` and its circuit rule must remain structural attributes. Tag
assignment supports nets, copper, pads, vias, routes, components, and circuits
(`jitx/constraints.py:495`, `jitx/constraints.py:565`).

## Heavy copper

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
            priority=PROTECTION_PRIORITY,
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

## Power puddle from a pad list

A local puddle serving a group of pins is built by the circuit that owns those
pads. It is copper on the rail, given an explicit position, and needs its reason
on the line that creates it.
