---
name: jitx-layout-constraints
description: "Use when the user asks to set default trace width or clearance, write design rules, set net-to-net, trace-to-pour, trace-to-hole, or per-layer clearance, size power trace width by net class or current, keep one net's copper away from another, tag nets into classes with their own width and spacing, place and route decoupling capacitors, set pour rules (inner or outer layer, heavy copper, sliver removal, thermal relief, direct connect), express pour stitching as a rule or build an explicit thermal-pad via field, step a wide power trace down to fit a QFN, BGA, or passive pad (fanout or escape width), verify widths and clearances after build, or find out why a design rule did not apply. Covers Tag, design_constraint, UnaryDesignConstraint, BinaryDesignConstraint, builtin tags, OnLayer, AnyObject, priority, all rule effects, FabricationConstraints floors, the Bogatin power and decoupling habits, and after-build checks. Fab minimums, stackups, vias, and routing-structure definitions belong to jitx-substrate-modeler ('set fabrication rules' means the fab floor; design rules above the floor live here). Drawing copper, diagnosing realized pours or stitch vias, control-point mechanics, and the geometry-verification loop belong to jitx-physical-layout. Topology and timing constraints belong to jitx-interconnect-constraints."
---

# JITX Layout Constraints

Turn a board's physical requirements into the rule set the router and DRC
obey: board-wide defaults, one tag per net class with its width and clearance
rules, the step-down ladder where a class rule cannot reach a package pad, the
pour and decoupling rules, and the checks that read the built design back.

A rule that builds is not a rule that applied. The engine picks the highest
priority matching rule per object, silently; the only evidence is the copper
after capture. Every section below ends in something you can measure.

## Scope, what this skill owns vs neighbors

| You want to... | Skill |
|---|---|
| Board-wide default trace width, clearance, thermal relief | this skill |
| Net classes: a tag per class with width and clearance rules | this skill |
| Net-to-net, trace-to-pour, trace-to-hole, per-layer clearance | this skill |
| Power routing width, sense lines, pad-to-via rules | this skill |
| Pour rules: inner vs outer, heavy copper, sliver removal, stitching, direct connect | this skill |
| Step a class width down to fit a QFN, BGA, or passive pad (escape rules) | this skill (route and control-point mechanics: `jitx-physical-layout`) |
| Decoupling capacitor placement and routing as a module | this skill |
| Verify widths, clearances, and route realization after build | this skill (the capture loop itself: `jitx-physical-layout`) |
| Why a rule did not fire | this skill |
| Fab minimums (`FabricationConstraints`), stackup, via definitions, routing structures, fenced pour outlines | `jitx-substrate-modeler` |
| Draw copper, custom shapes, pad features, place vias and components, `Route` and control points | `jitx-physical-layout` |
| Topology (`>>`), timing, skew, insertion loss, diff-pair constraints | `jitx-interconnect-constraints` |
| Wire nets, passives, basic top-level pours | `jitx-circuit-builder` |
| Component landpatterns (including the pad geometry escape rules read) | `jitx-component-modeler` |

## Environment

Environment setup is the base `jitx` skill's job; invoke it first — it owns the
supported version line, and this skill does not restate it. This page is written
against and verified on the `jitx.constraints` module as shipped in 4.4.0. Before
writing rules on an unfamiliar install, open the installed
`jitx/constraints.py` and confirm the class and method names in
`references/rule-reference.md` still exist. Verify every import with `pyright`
against the installed package.

## The rule system

### Vocabulary

A rule is a condition (or two) plus an effect, with a priority.

```python
from jitx.constraints import (
    AnyObject, BinaryDesignConstraint, IsCopper, IsPad, IsPour, IsTrace,
    OnLayer, Tag, Tags, UnaryDesignConstraint, design_constraint,
)
```

Conditions:

- A `Tag` subclass you declare at module scope. Tags form a hierarchy by
  class inheritance: a rule on `PowerTag` also matches every `PowerTag`
  subclass. Which objects can carry a tag and how to assign one is
  `jitx-physical-layout`, "Layout-intent tags".
- The nine builtin tags: `IsCopper`, `IsTrace`, `IsPour`, `IsVia`, `IsPad`,
  `IsBoardEdge`, `IsThroughHole`, `IsNeckdown`, `IsHole`. Conditions only;
  `assign()` on a builtin raises `TypeError`. `IsNeckdown` matches copper the
  engine has classified as a neckdown region; nothing in code creates one.
- `OnLayer(index)`, with `OnLayer.external()` for layers 0 and -1 and
  `OnLayer.internal()` for everything else. Not re-exported from top-level
  `jitx`; import it from `jitx.constraints`.
- `AnyObject`, which matches everything and is the usual second condition of
  a binary rule.
- Expressions: `&`, `|`, `~`, and `Tag.any(...)` / `Tag.all(...)`.

Effects, and the arity rule that trips everyone: a one-condition rule
(`UnaryDesignConstraint`) may chain any effect except clearance; a
two-condition rule (`BinaryDesignConstraint`) has exactly one effect,
`.clearance(mm)`. `design_constraint(c1)` and `design_constraint(c1, c2)` are
a factory returning the right class; the conditions are positional-only.

| Effect | Rule shape | Signature |
|---|---|---|
| Trace width | unary | `.trace_width(width)` |
| Clearance | binary only | `.clearance(clearance)` |
| Via stitching | unary | `.stitch_via(ViaClass, SquareViaStitchGrid(pitch=, inset=))` or `TriangularViaStitchGrid` |
| Via fencing | unary | `.fence_via(ViaClass, ViaFencePattern(...))` |
| Thermal relief | unary | `.thermal_relief(gap_distance, spoke_width, num_spokes)` |
| Pour sliver removal | unary | `.pour_feature_size(min_width)` |
| Serpentine parameters | unary | `.serpentine_params(min_radius=, min_pitch=)` |
| Coupled-pair parameters | unary | `.coupled_pair_params(...)` (`skew_tolerance` is a distance) |
| Routing structure | unary | `.routing_structure(rs, ref_net=)` or `ref_layer_nets={layer: net}` |

That is the whole surface: eight unary effects and one binary effect. There
is no per-route width, no neckdown effect, no pour-isolation effect, and no
"direct connect" effect; those intents are expressed with the rules above
(see Pours and Fanout). Full signatures with source citations:
`references/rule-reference.md`.

### What rules act on

Width rules set the width of every trace they match, including code-authored
`Route`s (verified: escape segments realize at their rule's width on the same
net as a wider trunk). Clearance rules and the fab floors act on copper the
router places and on pour voiding; they do not move a code-authored route.
Two tagged routes authored 0.100 mm apart under a 0.25 mm rule realized at
0.1001 mm, and authored 0.020 mm apart they realized below the 0.09 mm fab
floor, both with `status: ok` (`references/rule-reference.md`, "Verified
behaviors"). A code-authored escape must therefore be placed with its
clearance already satisfied, and checked after capture; the rule documents
the intent for the router and DRC, it does not repair authored geometry. A
rule declared on a child circuit applies board-wide (verified), so put it
where its objects live for readability, not for scope.

### Priority

Higher `priority=` wins when more than one rule matches an object. The
default rules below sit at priority 0, so every override needs `priority=1`
or more, and a rule that must beat another override needs a higher number
still. Equal priority between two matching rules is not defined in the
Python source; do not rely on it. Give each override a distinct priority and
write the ladder down in a comment where the rules are declared.

Rung order matters as much as distinctness. A rule that is general across a
layer (a heavy-copper spacing for every copper on layer 2) belongs one rung
above the defaults and below the class rules, or it silently overrides every
class clearance that lands on that layer; a class rule scoped to a layer (the
12 V rail's clearance on layer 2) sits above its own class rule. A working
ladder: 0 defaults, 1 power and ground width and any layer-wide rule, 2 net
classes, 3 layer-scoped class overrides, 4 escape rules.

An override below a rule the object already matches can realize zero traces
while the build still reports `status: ok`. This is not a harmless losing
rule. Before the task reaches the Verification completion gate, the check
script enumerates the expected routes for every override, passes them to
`check_routes`, and fails if any expected route has no realized traces. Width
comparisons run only after that count passes, so an empty result cannot satisfy
them vacuously.

### Where rules live

Rules are collected by walking the design tree for `DesignConstraint`
objects. Any structural attribute reachable from the `Design` counts; a
module-level rule, or one built in a function and dropped, does not exist.
Convention:

- Board-wide rules go on the `Design`, in `__init__`, as `self.rules = [...]`
  (the name is a convention, not a framework field; a list is fine because the
  structural walk enters lists).
- Rules about objects one circuit owns (its escape routes, its decoupling
  puddle, its fence pour) go on that circuit as attributes, next to the
  `Tags(...).assign(...)` calls that mark the objects.
- Tag classes are declared at module scope. A `Tag` subclass inside a
  function or method breaks instantiation tracking.

### Fab floors vs design rules

The substrate's `FabricationConstraints` has four fields the engine enforces
on generated copper and that take precedence over any rule:
`min_copper_width`, `min_copper_copper_space`, `min_copper_hole_space`,
`min_copper_edge_space`. The other fifteen fields (annular ring, drill,
soldermask bridge and registration, silkscreen, and so on) are documentation
that your code can read. A design rule tighter than the floor is what you
normally write; a rule looser than the floor is overridden by the floor and
never takes effect. Read the floors from the substrate rather than retyping
them:

```python
from jitx import current
fab = current.design.substrate.constraints
floor_space = fab.min_copper_copper_space
```

### Sharp edges (verified on real boards)

- A binary clearance between two tags must out-rank the board's default
  `IsCopper x IsCopper` (or `AnyObject x AnyObject`) clearance: pass
  `priority=1` or higher.
- A same-tag binary clearance is safe for differential pairs: a coupled span
  is one trace object whose internal gap is the structure's `pair_spacing`,
  so `design_constraint(HsTag(), HsTag(), priority=1).clearance(0.5)` only
  separates different pairs. Reported from a shipped board, not reproduced as
  a reference case here; treat it as pending and verify the pair gap after
  capture before relying on it.
- A `RoutingStructure` declared at module level is not part of the design
  tree and cannot be applied by a rule; build it as a substrate attribute or
  inside the consuming circuit.
- `.routing_structure()` takes `ref_net=` or `ref_layer_nets=` (not
  `reference_*`); passing both raises `ValueError`, passing neither requires
  an active `jitx.si.ReferencePlanes` context.
- Flat tag proliferation is a smell: a row of sibling tags that differ only
  by name, each with a rule that restates the others, wants one base tag with
  the shared rule and subtags only where behavior differs.

## Board-wide defaults

Every `Design` declares four rules so the router and DRC have
production-friendly defaults above the fab floor. Without them the router
uses the fab minimums, which are too narrow for power and put no thermal
relief on pads.

```python
from jitx import Circuit, Net
from jitx.constraints import (
    BinaryDesignConstraint, IsCopper, IsPad, IsTrace, Tag, UnaryDesignConstraint,
)
from jitxlib.symbols.net_symbols import GroundSymbol, PowerSymbol


class PowerTag(Tag):
    """Power rails. Subclass per tier or per rail when widths differ."""


class GroundTag(Tag):
    """Ground nets."""


class TopCircuit(Circuit):
    def __init__(self):
        self.GND = Net(name="GND", symbol=GroundSymbol())
        self.VBUS = Net(name="VBUS", symbol=PowerSymbol())
        GroundTag().assign(self.GND)
        PowerTag().assign(self.VBUS)


class Design(...):
    substrate = ...
    board = ...
    circuit = TopCircuit()

    def __init__(self):
        # Priority ladder: 0 defaults, 1 power/ground width and layer-wide
        # rules, 2 class rules, 3 layer-scoped class overrides, 4 escape rules.
        # Written here so the next reader sees the whole ladder.
        self.rules = [
            # Default trace width for any trace not otherwise tagged.
            UnaryDesignConstraint(IsTrace).trace_width(0.125),  # skill default: JLC04161H-class, above the 0.09 floor
            # Default copper-to-copper clearance: traces, pours, pads.
            BinaryDesignConstraint(IsCopper, IsCopper).clearance(0.125),  # skill default: JLC04161H-class
            # Thermal relief on pads: gap, spoke width, spoke count.
            UnaryDesignConstraint(IsPad).thermal_relief(0.125, 0.2, 4),  # skill default: gap = default clearance, 0.2 mm spokes, 4 spokes
            # Power and ground get wider traces; priority=1 beats IsTrace.
            UnaryDesignConstraint(PowerTag() | GroundTag(), priority=1).trace_width(0.4),  # skill default: between the Bogatin 0.15 and 0.5 tiers
        ]
```

The 0.125 mm width and clearance and the 0.4 mm power width are typical
JLC04161H-class defaults (JLCPCB's 1 oz floor is 0.09 mm). Calibrate to the
actual substrate's floors and label the source of each number on its line.
`IsTrace`, `IsCopper`, and `IsPad` match every trace, copper, and pad, so
these four rules cover the board without tagging every net. Non-default
classes get higher-priority rules in the same list (next section).

The complete-board workflow's Phase 3 gate checks that these four rules are
present on the `Design`; see the base `jitx` skill's `completion-blocks.md`.

## Net classes: tag, derive, express

Some nets need non-default physical rules. The class catalog is per design:
enumerate the classes that apply, derive each class's width and clearance
from a stated source, and express each as a tag plus rules. If no net needs a
non-default rule, record "no non-default net classes" with a one-line reason.

| Net class | Why it matters | Width source | Clearance source | Rule shape |
|---|---|---|---|---|
| Power rail (tiered) | I x R drop, heating | Bogatin tier (Routed power below) or fab current table | default | `UnaryDesignConstraint(RailTag(), priority=1).trace_width(w)` |
| High current (over 3 A) | heating, connector limits | Bogatin 100 mil tier or fab table | default or wider to ground | width rule plus `BinaryDesignConstraint(HiCurrentTag(), GroundTag(), priority=2).clearance(c)` |
| Switch node (buck, boost) | dV/dt, EMI | as its rail | pour pulled back: value from EMI budget, labeled | `BinaryDesignConstraint(SwTag(), IsPour, priority=2).clearance(c)` |
| RF / antenna feed | impedance, return path | routing structure | structure's clearance | `design_constraint(RFTag()).routing_structure(rs, ref_net=gnd)` |
| High-speed differential | impedance, skew | differential structure | structure's clearance; pair-to-pair via same-tag binary rule | `jitx-interconnect-constraints` for timing; structure via tag rule |
| Sensitive analog | coupling | default | wider to digital and power, value labeled | `BinaryDesignConstraint(AnalogTag(), DigitalTag(), priority=2).clearance(c)` |
| High voltage / mains | creepage | default | creepage per the applicable standard, cited | binary clearance to `AnyObject`, layer scoped if needed |
| Kelvin sense | accuracy | default (narrow) | wider to the power path it measures | `BinaryDesignConstraint(SenseTag(), PowerTag(), priority=2).clearance(c)` |
| Gate drive | ringing | as its driver datasheet | default | width rule, placement handled in the circuit |
| Isolated domain | galvanic isolation | default | barrier clearance, cited | binary clearance to `AnyObject`; keepout for the barrier |

Extend the table as a design demands. Each row's numbers need a source on
the line where they appear in code: a `FabricationConstraints` field, a
datasheet or standard named with its revision or date and the page, table,
or figure the number comes from, the Bogatin tier, or `skill default` with
the value.

When no source exists for a clearance (a keep-away for a sensitive net, a
switch-node pullback, a sense-to-power gap), do not write an assumption. Two
legal moves: derive it from a value that has a source and label the
derivation on the line (`2 * DEFAULT_CLEARANCE  # skill default: twice the
board default`), or leave it as an open item that the check script fails
loudly on until the user supplies the number. The label must contain the
words `skill default` (or name the fab field or the citation); `derived`,
`assumed`, or `my assumption` on its own is not a source, and a multiplier
with no label is an invented number even when the base value is sourced. An
assumption dressed as a constant passes every check and ships.

Tag hierarchy does the bookkeeping: `class RailTag(PowerTag)` picks up the
power width rule automatically, and a `Rail12VTag(RailTag)` with its own
`priority=2` width rule overrides it where that rail differs.

## Routed power

Basis: Eric Bogatin, "Seven Habits of Successful 2-Layer Board Designers",
Signal Integrity Journal, 2019. The habits are engineering defaults for 1 oz
copper, not a current-capacity model, and this skill does not use IPC
current-carrying charts or formulas at all.

- Width tiers (Bogatin, 1 oz): 6 mil (0.15 mm) signal traces carry 1 A DC
  with no measurable temperature rise; 20 mil (0.5 mm) power traces carry
  3 A; 100 mil (2.5 mm) carries 10 A. Express them as `PowerTag` subtags
  (`PowerTag` at 0.5 mm, `HighCurrentTag(PowerTag)` at 2.5 mm with a higher
  priority) and label each width `Bogatin 2019 tier`. Adjust only when the
  fab's capability table or a measured temperature rise says otherwise, and
  say which.
- Route power as traces by default, not as copper fill (Bogatin's habit 7: a
  routed trace keeps the current path explicit and its width visible; a fill
  hides both). A `Pour` on a rail net is a net member and its connectivity is
  checkable in JITX, so this is a legibility and current-path decision, not a
  tool limit. The one exception is the local power puddle under a decoupling
  bank (Decoupling below); a wider power pour needs its reason (a datasheet or
  a current requirement) on the line that creates it.
- Pad-to-via: a power pad that changes layers needs vias sized and counted
  for the tier (one via per tier step is the default; label it). Set
  `via_in_pad = True` on the via class only when the fab's via-in-pad row
  allows it, and read the fab's `min_annular_ring`.
- Sense (Kelvin) lines ride a power net but are not power: tag the sense
  route segments with their own `SenseTag` (the net itself is the power net,
  so those routes carry both tags), give the sense width rule a rung above
  the power width, and add a binary clearance to the power path they measure
  so the router keeps them off the current path.

Detail and worked derivations: `references/power-and-pours.md`.

## Pours

This section owns pour rules. Pour materialization, empty output, stitch-via
realization, edge pullback, and captured-shape semantics are owned by
[Pour realization semantics](../jitx-physical-layout/SKILL.md#pour-realization-semantics).

- Ground gets one board-wide pour on its own return layer (Bogatin: a
  continuous return under every signal). Do not rely on a top-side copper
  fill for ground, and do not fill between signal traces to reduce
  crosstalk; it does not reliably help and can hurt.
- Power is not poured (Routed power above), except a local puddle inside a
  decoupling bank's circuit, built from the pads it serves.
- Clearance to pours is a binary rule with `IsPour` on one side:
  `BinaryDesignConstraint(IsTrace, IsPour, priority=1).clearance(c)`,
  `BinaryDesignConstraint(IsPour, IsHole, priority=1).clearance(c)` (or
  `IsThroughHole`). Layer-scope with `OnLayer(n)`.
- Heavy copper on an inner layer raises the fab's minimum spacing (etch
  factor). Find the layers by walking the stackup's `Conductor.thickness`,
  then write a per-index rule with the fab's heavy-copper spacing row:
  `BinaryDesignConstraint(IsCopper & OnLayer(2), IsCopper, priority=1).clearance(c)`.
  `OnLayer.internal()` matches every inner layer, so it is the wrong selector
  for one heavy layer. Walk the substrate instance inside the design
  (`current.design.substrate.stackup.conductors`); the same attribute read
  off the substrate class hangs in a lazy proxy. The walk only finds what the
  substrate models: the
  predefined JLCPCB substrates carry 1 oz outer and half-ounce inner copper,
  so a quoted 2 oz layer that is not in the stackup is a substrate task first
  (`jitx-substrate-modeler`, from the fab's report), and until then the
  heavy-copper rule is an open item, not a guess at a layer index.
- An inner-layer pour with no via tying it to copper that carries its net is
  orphan copper, and the engine drops it silently; give inner pours stitch vias
  or anchor vias.
- Sliver removal: `design_constraint(IsPour).pour_feature_size(min_width)`.
- Stitching a pour: `design_constraint(GndPourTag()).stitch_via(ViaClass,
  SquareViaStitchGrid(pitch=, inset=))`; the via class may be reached
  through the substrate's mixin, re-declared on the substrate, or declared at
  module scope (verified). The target and inset realization semantics are in
  [Pour realization semantics](../jitx-physical-layout/SKILL.md#pour-realization-semantics).
  For an exposed thermal pad, the soldermask-defined
  via field with its mask dams is `scripts/thermal_via_stitch.py`, which reads
  its constants from `FabricationConstraints` and the via class and raises
  `ValueError` on a pad too small for the grid or an opening that is not a
  polygon (a raise means stop and change the grid, never bypass it); usage is
  in `jitx-physical-layout` `references/layout-examples.md`. The module is
  unit-tested; no reference design has built a pad with it yet, so verify the
  mask and paste openings in the fab output the first time.
- Thermal relief is the `IsPad` default above. A solid connection for a
  high-current pad (direct connect) has no dedicated effect; the verified
  pattern is a higher-priority `thermal_relief` on the tagged pads with
  the fab floor as the gap and a spoke width equal to the pad diameter, which
  collapses the relief into solid copper. A higher-priority rule with no
  effect does not suppress the default. Test and numbers:
  `references/power-and-pours.md`, section 8.
- `Pour(..., isolate=)` is deprecated; express pour clearance with the
  binary rules above.

## Fanout: stepping a class rule down to a pad

A 0.5 mm power trace does not fit a 0.25 mm QFN pad at 0.5 mm pitch. The
class rule stays; a specific escape rule takes over for the last segment.
Compute first, for every pad a tagged class width reaches (walk the tagged
nets' pad mappings, do not hand-pick the pads you noticed): if the class
width fits the pad and keeps the fab floor to the neighboring pads, there is
no step-down and no escape rule (a 0.5 mm trace into a 0.6 mm pad at 0.95 mm
pitch is such a case); where it does not fit, emit the escape pair or raise,
so a ground pin on a 0.5 mm ground width cannot sit silently in a 0.25 mm pad.
Neckdown is not used for this: `RoutingStructure.NeckDown` parameters take
effect only through the UI, and a specific tag carries the intent in a way a
reader and a rule can see.

The ladder, always with tags. Every escape subtag gets both rules, a width
and a two-condition clearance, and every transition from class width to
escape width is a `RoutePoint`, including one that sits next to a via or a
layer change. The escape rules live on the circuit that owns the route, not
in the Design's list.

```python
from jitx import RoutePoint
from jitx.circuit import Route
from jitx.constraints import AnyObject, Tag, Tags, design_constraint


class EscapeTag(Tag):
    """Base for escape segments; shared rules go here."""


class QfnEscapeTag(EscapeTag):
    """Escape into a 0.5 mm pitch QFN pad."""


# In the circuit that owns the source j1, the QFN u1, and the escape route.
# w_escape and c_escape are computed from the QFN landpattern and the fab
# floor (references/fanout.md), never typed in.
rp = RoutePoint(layer=0).at(x_transition, y_transition)
self.v5 += rp.port                                # net the control point, or the build fails
trunk = Route(self.j1.VOUT, rp, layer=0)          # class-width trunk ends here
esc = Route(rp, self.u1.VIN, layer=0)             # escape segment into the pad;
                                                  # intermediate sketch points are
                                                  # dropped on 4.4.0-rc.9, so a turn
                                                  # needs another RoutePoint
self.escape = [rp, trunk, esc]                    # store each object once: a list OR
                                                  # named attributes, never both
Tags(QfnEscapeTag()).assign(esc)

# Escape rules out-rank every class rule and override (rung 4 in the ladder):
self.qfn_escape_width = design_constraint(QfnEscapeTag(), priority=4).trace_width(w_escape)
self.qfn_escape_space = design_constraint(QfnEscapeTag(), AnyObject, priority=4).clearance(c_escape)
```

A single-ended `RoutePoint` must be a member of the net (`rp.port`) or the
build fails with an opaque key error; a `Route` stored both as a named
attribute and in a list fails translation with `Child object Route
encountered multiple times`; prefer a pad-to-point trunk, since a
via-to-`RoutePoint` trunk has been seen to realize alone and not inside a
full design. `w_escape` and `c_escape` are derived, not typed: read the
landpattern's pad geometry with `jitx.query` and subtract the fab floor.
The escape width is strictly less than the narrowest pad selected by its rule.
The derivation rounds that measured pad width to a fixed precision and
subtracts one quantum unconditionally; equality with any selected pad is a
failure because it can silently change a centered trace into polygon copper.
`c_escape` starts from the board default clearance and only tightens where
the pad geometry cannot hold the default, never below the floor; a rule at
the escape rung against `AnyObject` set to the floor would loosen the default
around every escape. That clearance acts on router copper and pour voiding
near the segment, not on the authored segment itself (What rules act on). The governing gap
differs by package family (QFN: the gap between adjacent pads in a row; BGA:
the diagonal channel between balls and the row depth; two-terminal passive:
the pad-to-pad gap and courtyard). Derivations, the QFN worked example, and
BGA channel planning: `references/fanout.md`. `Route`, `RoutePoint`, and the
control-point binding rules: `jitx-physical-layout`
`references/control-points.md`, which also owns the rule for where the tag
goes on single-ended versus differential routes.

## Decoupling

Basis: Bogatin's habits 5 and 7. Loop inductance between the IC's power and
return pins and the capacitor matters more than how many capacitors there
are or their values.

- Fewest, largest MLCCs in the smallest package, rated at least 2x the rail
  (22 uF is typical). One per group of pins it serves, not a
  10 uF / 1 uF / 0.1 uF stack per pin ("there is no problem this solves").
  Where a datasheet specifies decoupling, the datasheet wins.
- Place each capacitor as close to its power pin as the package allows,
  with a via at each capacitor pad to the return layer, and connect with
  short, wide segments or a local power puddle.
- As code: a `DecouplingBank(Circuit)` that owns the IC, the capacitors,
  their vias, the puddle on the rail, and the tagged escape routes to the IC
  pads, so the whole block shares one frame. Give the bank an explicit
  position; `at(floating=True)` is for interactive placement in the UI, and
  a floating circuit with no stored placement is parked off the board
  headlessly, where every route fails to realize while the build says ok. Each capacitor carries a hint naming the IC
  pads it serves (finer than the net), which the solver in
  `scripts/decoupling_solver.py` turns into placements and via positions by
  minimizing loop area. Module, solver usage, and the recorded loop areas:
  `references/decoupling.md`.

## Verification

Build success proves nothing about rules. After every build, capture the
design and read it back (the loop, `query` semantics, and coordinate frames
are in `jitx-physical-layout` `references/geometry-verification.md`). The
constraint-specific checks, packaged in `scripts/layout_checks.py`:

- Width by net and layer, and per route: every realized trace shape
  (`route.traces[i].shapes[j].geometry`, an `ArcPolyline` or `Polyline` whose
  `.width` is the trace width) on a tagged net has the width its winning rule
  asked for, equal within a
  labeled tolerance; wider fails as well as narrower, since wider means a
  different rule won. A net that carries a class trunk and a narrower escape
  on the same layer is checked per route (`check_route_width`), not per net.
- Clearance between two nets: the minimum shapely distance between their
  copper on a layer is at or above the binary rule.
- Route realization: the project check explicitly lists the routes governed by
  each override and passes that list to `check_routes`, then requires
  `route.traces` to be non-empty for every escape route authored. A silently
  unrealized route is the common failure, including the case where an override
  sits below another matching priority rung.
- Primitive shape: a realized escape must expose a polyline width. A `Polygon`
  with no width field is a failed width realization, not a missing attribute to
  skip and not evidence that the route is absent.

Capture limits and traps (runtime-mutated pours, transform composition, sketch
points, floating circuits) are owned by `jitx-physical-layout`
`references/geometry-verification.md` and its
[Pour realization semantics](../jitx-physical-layout/SKILL.md#pour-realization-semantics).
The consequence for rules: trace-to-pour clearance, thermal relief and sliver
removal are not measurable from `rd.query`. Report those rules
as not verified from capture and move on. Do not reach for the fabrication
export to close them: parsing an ODB++ tree to confirm a rule costs an export,
a directory walk and a feature-file parse per rule, and it answers a question
the design already knows the answer to. An unverifiable rule is an open item
with one line against it, not a research project.

A measured width below the winning rule is a failure, never a note: a route
that realizes at the via pad diameter because it runs via to via has not met
its rule (route pad to point, or use a via whose pad matches the width). A
rule with no copper to witness it is not verified; the check output must
count those separately and never print zero failures while any declared rule
went unexercised.

Checks read the rules, they do not restate them: pass each rule object's own
value to the check (`rule_width(rule)` and `rule_clearance(rule)` in
`scripts/layout_checks.py` read the effect the rule carries), never a literal
typed beside the rule list, and end with `rule_coverage(rules, witnessed)`,
which fails for every declared rule no check named. A hand-typed table of expected values is a
parallel model that drifts the first time a rule is added (see the base
skill's `references/architectural-patterns.md`).

`layout_checks.py` is a library; the project's check script is the gate. It
ends with `raise SystemExit(run_checks([...]))`, which exits 1 on any failed
check and on an empty check list, and the completion block records that
script's command and exit code. A rule set is done when that script exits 0
on the built design, or when the missing runtime is named as an open item in
the completion block. Never report a rule as applied from `status: ok`.

## Why a rule did not fire

Check in this order:

1. Not reachable: the rule is a module-level object or a local variable, not
   a structural attribute under the `Design`.
2. Out-ranked: a binary clearance at priority 0 loses to the default
   `IsCopper x IsCopper` rule. A route-width override below an already
   matching rule can emit zero traces rather than merely lose. Raise the
   priority, then let the Verification gate refuse completion unless the
   expected trace count is nonzero and the measured widths match.
3. Wrong arity: `.clearance()` on a one-condition rule, or any other effect
   on a two-condition rule.
4. Builtin assigned: `IsTrace.assign(obj)` raises `TypeError`; builtins are
   conditions, and `IsTrace` is an enum member, not a class to instantiate.
5. Tag class declared inside a function: instantiation tracking breaks.
6. Routing structure at module level: an `Instantiable` proxy a rule cannot
   apply.
7. Below the floor: a rule looser than a `FabricationConstraints` minimum is
   overridden by the floor.
8. Via class not found: `stitch_via` and `fence_via` take the via class
   object. A class reached through the substrate's mixin, one
   re-declared as a substrate attribute, and one at module scope all
   generate vias (verified in `evals/cases/reference/stitch-via/`). If vias are
   missing, check the tag assignment and the rule's reachability before
   suspecting the via class.
9. The object is not taggable: `OverlappableCopper` cannot carry a tag.
10. The object is a code-authored `Route`: clearance rules and fab floors do
    not move authored geometry (What rules act on, above). Measure it after
    capture with the project's check script built on
    `scripts/layout_checks.py`; its non-zero exit is a failed task, and the
    completion block is not written until it exits 0 or the unmeasurable
    rules are named as open items.
11. Stitch-target type or materialization: diagnose it with the owning
    [Pour realization semantics](../jitx-physical-layout/SKILL.md#pour-realization-semantics)
    and its executable realization check.

Behaviors settled by a built design are recorded, with the design that
settled them, in `references/rule-reference.md`, "Verified behaviors"; a row
marked pending has not been run and must not be relied on.

## Anti-string-hacking and completion

Construct tags and rules as structural objects on `self`; batch parameters in
a `@dataclass(frozen=True)` or a plain list; key nothing by an assembled
string. See the base `jitx` skill's `references/architectural-patterns.md`
and run `jitx-code-review` as the self-critique pass.

The task acceptance block (base `jitx` skill, `references/completion-blocks.md`)
fields this skill fills: the four default rules present on the `Design`; the
net-class table or the explicit "no non-default net classes" line; the
after-build width, clearance, and realization checks with their commands and
results; open items for anything a missing runtime left unverified.

## API reference

`references/rule-reference.md` (conditions, effects, signatures with source
citations, verified behaviors), `references/power-and-pours.md`,
`references/fanout.md`, `references/decoupling.md`, and the JITX
documentation at https://docs.jitx.com.
