---
name: jitx-layout-constraints
description: "Use when the user asks to add design rules to a placed and routed design: default trace width, clearance and thermal relief, tags for classes of nets (power, ground, RF, switch node, sense) with their own width and clearance, net-to-net, trace-to-pour, hole and board-edge clearance, per-layer and heavy-copper rules, pour rules (thermal relief per pad class, direct connect, sliver removal), via stitching as a rule, via fencing (a fenced pour outline or antipad by a fence_via rule, a fenced or grounded coplanar line by RoutingStructure.Layer.fence), applying the substrate's routing structures to nets and escape segments by tag, stepping a wide trace down to fit a QFN, BGA or fine-pitch pad (fanout or escape width), checking after build that each rule applied, or finding out why a rule did not apply. Covers Tag, design_constraint, builtin tags, OnLayer, AnyObject, priority, every rule effect, SquareViaStitchGrid, ViaFencePattern, and the capture reads that witness them. It does not wire, place, route or draw copper. Fab minimums, stackups, vias and routing-structure definitions belong to jitx-substrate-modeler ('set fabrication rules' means the fab floor). Drawing copper and pours, code-placed vias, control points and diagnosing realized pours belong to jitx-physical-layout. Decoupling and net wiring belong to jitx-circuit-builder. Topology and timing constraints belong to jitx-interconnect-constraints."
---

# JITX Layout Constraints

Rules for a design that already has its parts, circuits, placement, routes and pours: tags that say what an object is, `design_constraint` rules keyed on those tags, and the reads after capture that show each rule applied. The explanation and figures are on the Essentials page [Layout Constraints](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html); this skill is the working reference.

A rule that builds is not a rule that applied. Headless capture does not report which rule won for an object, so the evidence is the captured copper. In the board view, select a route and press B to open its Constraints panel.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

The worked patterns this skill points at are modules in the `jitxexamples` package. Install it into the project venv once with `pip install --no-deps --upgrade jitxexamples` (`--no-deps` keeps its pins off the project's `jitx`); it is not a project dependency. If importing a pointed-at module raises `ModuleNotFoundError`, the installed `jitxexamples` predates these patterns: say so, and work from the rules here.

## The rule system

```python
from jitx.constraints import (
    AnyObject, IsBoardEdge, IsCopper, IsHole, IsPad, IsPour, IsTrace, IsVia,
    OnLayer, SquareViaStitchGrid, Tag, Tags, ViaFencePattern, design_constraint,
)
```

`design_constraint(c)` returns a one-condition rule and `design_constraint(c1, c2)` a two-condition rule; conditions are positional, `priority=` and `name=` are keywords. Explanation: [Tags say what an object is](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#tags-say-what-an-object-is) and [Design Constraints](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html).

### Conditions

| Condition | Matches |
|---|---|
| `MyTag()`, a `Tag` subclass declared at module scope | what the tag reaches ([What a tag reaches](#what-a-tag-reaches)); a rule on a base tag also matches its subclasses |
| `IsTrace`, `IsPour`, `IsVia`, `IsPad`, `IsCopper`, `IsThroughHole`, `IsNeckdown` | objects of that type; builtins are conditions only, and `Tags(IsTrace)` raises `TypeError` |
| `IsHole` | a hole in the board outline, a `Cutout`, and every via drill |
| `IsBoardEdge` | the outer edge of the board outline only |
| `OnLayer(i)`, `OnLayer.external()`, `OnLayer.internal()` | layer `i` (0 top, -1 bottom); layers 0 and -1; every inner layer |
| `AnyObject` | everything; the usual second condition of a clearance |
| `a & b`, `a \| b`, `~a`, `Tag.any(...)`, `Tag.all(...)` | combinations |

### Effects

A two-condition rule takes only `.clearance(mm)`. A one-condition rule takes any other effect: `.trace_width(width)`, `.thermal_relief(gap_distance, spoke_width, num_spokes)`, `.pour_feature_size(min_width)`, `.stitch_via(ViaClass, SquareViaStitchGrid(pitch=, inset=))` (or `TriangularViaStitchGrid`), `.fence_via(ViaClass, ViaFencePattern(pitch=, offset=, ...))`, `.routing_structure(rs, ref_net=net)` (or `ref_layer_nets={layer: net}`), `.serpentine_params(...)`, `.coupled_pair_params(...)`.

There is no neckdown effect, no pour-isolation effect (`Pour(isolate=)` is deprecated) and no direct-connect effect; [Pours and relief](#pours-and-relief) and [Fanout](#fanout) express those intents.

### Priority

A higher `priority=` wins, and priority is applied before specificity. At equal priority the more specific condition wins ([Always use object type tags!](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html#always-use-object-type-tags)): `design_constraint(PowerTag()).trace_width(...)` at 0 loses to an `IsTrace` default at 0. Give every override its own rung from one ladder, and write the ladder in a comment where the rules are declared:

| Priority | Rules |
|---|---|
| 0 | board defaults (`IsTrace`, `IsCopper`, `IsPad`) |
| 1 | layer-wide rules, such as a heavy layer's floors (`IsTrace & OnLayer(i)`, `IsCopper & OnLayer(i)`); the trace-to-pour clearance, below every class rule so a class's clearance to pours wins, and its `& OnLayer(i)` form on a layer with a floor |
| 2 | rules on your own tags: on nets, on pads, on pours |
| 3 | a rule that must beat a rung-2 rule on the same copper: a high-current or sense width, a tag rule narrowed to one layer (`PowerTag() & OnLayer(1)`), relief per pad class, a rung-2 class rule's heavy-layer copy |
| 4 | escape segments; a direct connect |
| 5 or above | protecting clearances (a keep-away, a creepage gap, edge and hole rules): a distinct rung per protection, the larger clearance higher |

A protection goes above every permissive rule that can match the same copper, because the losing rule is not applied at all. Raise the protection, and narrow the permissive rule to the copper it is for: `(IsTrace & EscapeTag(), IsPad & PartPadTag())`, not `(EscapeTag(), AnyObject)`. A two-condition rule matches in either order, so an exclusion (`~SomeTag()`) must hold on either side, and excluding a whole tag withdraws the permissive rule everywhere ([Priority is a ladder](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html#priority-is-a-ladder-so-put-what-must-win-at-the-top)).

Two protections that can match one pair of objects, such as `(HvTag(), AnyObject)` and `(IsBoardEdge, AnyObject)` on high-voltage copper by the edge, need distinct rungs: at one rung specificity decides, and it need not pick the larger.

A width override under a rule the object already matches can leave the route with zero traces and a clean build, so count traces before comparing widths.

### Where rules live

- Rules are collected by walking the design tree for `DesignConstraint` objects. A rule at module scope, or built in a function and dropped, does not exist.
- Board-wide rules go on the `Design` in `__init__` (`self.rules = [...]`; a list is walked). Rules about one circuit's objects go on that circuit, beside its `Tags(...).assign(...)` calls; they still apply board-wide.
- Fab floors are the substrate's `FabricationConstraints`; read them as `current.substrate.constraints.min_copper_copper_space` and stay at or above them. Defining them is `jitx-substrate-modeler`'s.

## What a tag reaches

| Tag on | Reaches |
|---|---|
| a `Net` | the net's traces, pours, pads and code-placed vias; a clearance or relief rule on a net tag acts on its pads and vias too |
| a `Pad`, `Landpattern` or `Component` | those pads: the way to pick out some of a net's pads |
| a `Route` | that route's segments only (an escape) |
| a `Pour` | that pour (stitching, fencing, sliver removal) |
| a `Via` | that via |

Assign tags only to `Net`, `TopologyNet`, `Copper`, `Pour`, `Route`, `Component`, `Circuit`, `Landpattern`, `Pad`, `Via` or `ControlPoint`, inside a design context (a circuit, component, landpattern or the design). Anything else warns `tag will have no effect` (`OverlappableCopper` is a feature, not copper), and an assignment outside a design context warns and does nothing.

## Board defaults

Where no rule matches, copper comes out at the fab floor (measured on jitx 4.6: an unruled route at the sample substrate's 0.127 mm `min_copper_width`), and a pad no relief rule matches joins its pour solid. Defaults lift the board off those two outcomes; write only the ones the board needs. Explanation: [Defaults above the fab floor](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#defaults-above-the-fab-floor). Worked pattern: `jitxexamples.patterns.layout_default_rules`.

| Default | Rule shape | Value from |
|---|---|---|
| Trace width | `design_constraint(IsTrace).trace_width(w)` | the fab sheet's standard (not minimum) width row, or the prompt |
| Copper clearance | `design_constraint(IsCopper, IsCopper).clearance(c)` | the fab sheet's standard spacing row, or the prompt |
| Pad relief | `design_constraint(IsPad).thermal_relief(gap, spoke, n)` | the fab sheet, the assembler's guidance, or the prompt |

Every width, clearance and gap in this skill's rules traces to a fab-sheet row, a value in the prompt, a cited datasheet or standard, or a derivation from a sourced value with its arithmetic on the line. A value with none of those is an open item that the check fails on until the user supplies it. No current-carrying chart or formula sets a trace width.

## Classes of nets

A class of nets is a tag assigned to nets: the power nets are the nets carrying `PowerTag`, and the class's rules are written once against the tag. Below, `p` is a protection rung ([Priority](#priority)).

| Nets | Rule shape | Number from |
|---|---|---|
| Power | `design_constraint(PowerTag(), priority=2).trace_width(w)` | the prompt or the fab sheet |
| High current | `class HighCurrentTag(PowerTag)`, its width at priority 3 | the prompt |
| RF, impedance controlled | a `routing_structure` rule ([Routing structures by tag](#routing-structures-by-tag)) | the substrate's structure |
| Switch node, noisy | `design_constraint(RFLineTag(), NoisyTag(), priority=p).clearance(c)` | the prompt or an EMI budget |
| Kelvin sense | a `SenseTag` on the sense `Route`s, its width a rung above power, a clearance to `PowerTag` at `p` | the prompt or the part's datasheet |
| High voltage, isolated | `design_constraint(HvTag(), AnyObject, priority=p).clearance(c)` | the standard the prompt names, cited |

- Power is routed as traces under its tag's width; a pour on a rail needs its reason on the line that creates it. A power pad that changes layers needs vias sized and counted for its current from the prompt or the fab sheet; set `via_in_pad = True` on the via class only where the fab sheet allows via-in-pad.
- A two-tag clearance keeps one class from another without moving ground: `(RFLineTag(), AnyObject)` also pushes the coplanar ground away. Worked pattern: `jitxexamples.patterns.layout_sensitive_net_clearance`.
- A row of sibling tags that differ only by name, each restating the others' rule, wants one base tag with the shared rule and subtags only where behavior differs.

## Pours and relief

Pour drawing and realization belong to `jitx-physical-layout` ([Pour realization semantics](../jitx-physical-layout/SKILL.md#pour-realization-semantics)); the rules that act on pours are here. Explanation: [Thermal relief](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#thermal-relief), [Heavy copper on one layer](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#heavy-copper-on-one-layer), [Board edge and cutouts](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#board-edge-and-cutouts).

| Intent | Rule shape |
|---|---|
| Trace-to-pour clearance | `design_constraint(IsTrace, IsPour, priority=1).clearance(c)`, below every class rule: at 2 it would beat `(PowerTag(), AnyObject)` at 2, because specificity in object types outweighs most other kinds ([Introduction to constraint selection](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html#introduction-to-constraint-selection)), and the class's clearance to pours would be lost with no issue |
| Relief for all of a net's pads and code-placed vias | `design_constraint(GroundTag(), priority=2).thermal_relief(gap, spoke, n)` |
| Relief per pad size | tag the pads by measured size, one relief rule per class at priority 3, above the net's relief (`jitxexamples.patterns.layout_thermal_classes`) |
| Direct connect | a `DirectConnectTag` on the pad, `thermal_relief(gap, pad_diagonal, 4)` a rung above every relief that matches the pad (priority 4) |
| Sliver removal | `design_constraint(MyPourTag()).pour_feature_size(min_width)`; it judges a pour region's full width, so a coplanar ground strip narrower than `min_width` goes whole |
| Heavy copper on one layer | the layer's floors at priority 1, `design_constraint(IsTrace & OnLayer(i), priority=1).trace_width(w)` and `design_constraint(IsCopper & OnLayer(i), AnyObject, priority=1).clearance(c)`, plus the copies below |
| Board edge | `design_constraint(IsBoardEdge, AnyObject, priority=p).clearance(c)` |
| Slots, cutouts, drills | `design_constraint(IsHole, AnyObject, priority=p).clearance(c)` (`jitxexamples.patterns.layout_edge_and_cutout`) |

- A floor at 1 loses to every rule at 2 or above that matches the layer's copper, with nothing reported. Hold it this way:
  - The trace-to-pour rule gets its own form on that layer at rung 1, `design_constraint(IsTrace & OnLayer(i), IsPour, priority=1).clearance(c_l)`, with `c_l` the larger of its value and the floor. Its condition implies both `(IsTrace, IsPour)` and the floor's, so it beats both at that rung ([Global logical specificity](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html#global-logical-specificity)).
  - Each rung-2 class rule whose width or clearance is below the floor, and which can match that layer's copper, gets a copy narrowed with `& OnLayer(i)` at 3, at the floor or the class's own larger value for that layer: `design_constraint(PowerTag() & OnLayer(i), AnyObject, priority=3).clearance(c_floor)`.
  - A rung-3 rule below the floor (a high-current or sense width) is raised on that layer by its own `& OnLayer(i)` form at the floor, on rung 3, which beats it by the same specificity. A subclass's rule at 3, such as `HighCurrentTag()`, beats its base class's copy there, as a child tag beats its parent tag narrowed to a layer ([Local logical specificity: extended example](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html#local-logical-specificity-extended-example)).
  - An escape or a protection that can match that layer's copper is already at or above the floor; an escape that cannot meet it is an open item for the user.
- Find the heavy layer's index by walking `current.substrate.stackup.conductors` (index 0 is the top) and reading each conductor's `thickness`; a layer the substrate does not model as heavy is a substrate task first. `OnLayer.internal()` matches every inner layer, so it is the wrong selector for one heavy layer.
- `IsHole` matches via drills, so a hole rule wider than a via's pad pulls pours back from every other-net via.
- Measured on jitx 4.6, a pour stops the clearance plus 0.01 from traces and the board edge, and 0.1323 from a pad and 0.1312 from a via pad against a 0.127 floor; compare pullback with the rule, not with an exact value.
- A pour with no pad or via of its own net on its layer comes back `Empty`; stitch vias and fence vias do not anchor it.

## Stitching

`design_constraint(StitchedPourTag()).stitch_via(ViaClass, SquareViaStitchGrid(pitch=p, inset=s))`, the tag on the `Pour`. The vias take the pour's net. Explanation: [Stitching a pour](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#stitching-a-pour). Worked pattern: `jitxexamples.patterns.layout_stitched_pour`.

- Sites sit on multiples of the pitch from the board origin, not from the pour, so moving the pour changes which sites fit.
- `inset` runs from the via pad's edge to the computed pour boundary, after pullback from other-net copper: a site is kept when its centre is at least `inset + pad/2` inside `Pour.shape`. A site that fails is dropped, never moved or shrunk, and the count falls with no issue.
- A pitch below the via pad thins the grid to a checkerboard, so a smaller pitch can give fewer vias. Nothing checks pitch against the fab's spacing: refuse `pitch < pad` and `pitch < drill + min_hole_to_hole` before you write the rule.
- A fence on the same pour displaces the stitch sites near it, whatever the priorities (measured on jitx 4.6: an inward fence 0.6 in removed the stitch ring 1.0 in); leave those sites out of the derived set.

Expected count before you check, with the pitch at or above the pad: the origin-lattice points that pass each condition below, from what was measured on jitx 4.6. Compare the generated vias with that set, by position.

- The via pad, grown by `inset`, lies inside every pour the rule stitches (each captured `Pour.shape` in board frame, `trace.transform * pour.shape` from `visit(rd.root, Pour)`; [Coordinate frames](../jitx-physical-layout/references/geometry-verification.md#coordinate-frames)).
- Sites over pads were dropped on every layer. Where a site near a pad starts to drop was not measured, so leave out sites whose via pad comes within `min_copper_copper_space` of a pad.
- Sites 0.5 or closer to a code-placed via were dropped, with 0.5 via pads; the threshold between that and the next lattice site was not measured, so leave out sites within `pad + min_copper_copper_space` of a code-placed via.

## Fencing

Explanation: [Fencing](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#fencing) and [A grounded coplanar line](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#a-grounded-coplanar-line).

| Target | How | `initial_offset` measured from | Worked pattern |
|---|---|---|---|
| A pour outline: antipad, RF cavity, BGA breakout ring | `design_constraint(FencedPourTag()).fence_via(ViaClass, ViaFencePattern(...))`, tag on the `Pour` | the pour's drawn outline (`input_shape_only` defaults to true); positive outward, negative inward | `jitxexamples.patterns.fenced_pour_outline` |
| A routed line | a fenced copy of the substrate's structure, built in the circuit's `__init__`: the same layer values (the structure's width, clearance, velocity, loss) plus `.fence(ViaClass, ViaFencePattern(...), reference_layer=i)`, applied by a `routing_structure` rule; never edit the substrate file | the trace edge to the first row's via centres; must be positive | `jitxexamples.patterns.layout_cpwg_two_row_fence` |

- A `fence_via` rule keyed on a route's tag or a net's tag places no vias and raises no issue. Route fences come only from `Layer.fence`.
- `offset` is the spacing between rows and the default `initial_offset`. `Layer.fence` gives the vias the net of the structure's reference plane on that layer.
- Row k of a route fence sits `w/2 + initial_offset + (k-1)·offset` from the centreline. Keep the first row out of the gap, `initial_offset - pad/2 >= clearance`; nothing checks it.
- Row k's pad lands in the coplanar pour when `initial_offset + (k-1)·offset + pad/2 > C + 0.01`, where C is the larger of the structure's clearance and a clearance rule on the line's tag.
- The line cuts the coplanar pour in two, and each half needs its own same-net via: fence vias do not anchor a pour.
- A pitch below the via pad is thinned; `min_pitch` and `max_pitch` bound the pitch.

Expected counts before you check, with `L` the length of the outline offset by `initial_offset`, or of a straight run:

- Outward offset of a square outline: `floor(L / pitch)`. The offset keeps each corner square, with one via on its diagonal (measured on jitx 4.6: an 8 x 8 outline at +0.5 and pitch 1.0 gave 36, `L` 36, with the corner vias 0.707 out on the diagonals).
- Inward offsets and curves: the measured spacing changes to close the ring, so accept from `floor(L / pitch) - 1` to `ceil(L / pitch)` (measured on jitx 4.6 with a rule pitch of 1.0: an 8 x 8 outline at -0.6 gave 26 for `L` 27.2, a measured spacing of 1.014; a circle of radius 2.5 at +0.5 gave 19 for `L` 18.85).
- Route fence: `L / pitch` sites per side per row along a straight run (measured on jitx 4.6: 24 per side for `L` 24 at pitch 1.0). The round ends are partly filled, and a site beside an end pad can drop; check the straight run by count and position, and the ends by position only.

A generated fence via is identified by position against the derived pattern (on the offset outline or row, at the pitch), or by building the design so only one rule generates vias in that region. A distance band does not separate a fence from a stitch grid.

## Routing structures by tag

The substrate defines structures; this skill applies them. Explanation: [Routing structures by tag](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#routing-structures-by-tag). Worked pattern: `jitxexamples.patterns.layout_routing_structure_by_tag`.

| Intent | Rule |
|---|---|
| Every route of a net, pair included | `design_constraint(SignalTag(), priority=2).routing_structure(rs, ref_net=self.GND)`, the tag on the net |
| A neck on one segment | a tag on that segment's `Route` (keyed on a net tag `& IsTrace` it necks the whole net), `design_constraint(EscapeNeckTag(), priority=4).routing_structure(neck_rs, ref_net=self.GND)` |
| Different reference per layer | `ref_layer_nets={0: self.GND, 1: self.PWR}` |

- The rule applies the structure to code routes and satisfies a `Constrain`'s need for one: no `Missing routing structure` issue.
- If a `Constrain(...).structure(...)` and a rule both give one net a structure, the rule wins with no issue. Use one or the other.
- `.routing_structure()` takes `ref_net=` or `ref_layer_nets=` (not `reference_*`); passing both raises `ValueError`, and passing neither requires an active `jitx.si.ReferencePlanes` context.
- A `RoutingStructure` declared at module level is not part of the design tree and cannot be applied by a rule (`TypeError: 'Instantiable' object is not iterable`); build it as a substrate attribute or inside the consuming circuit.

Timing, loss and skew on the same nets: `jitx-interconnect-constraints`.

## Fanout

When a class width does not fit the pads it reaches, the class rule stays and the last segment becomes its own `Route` with an escape tag and a higher rung. Explanation: [Fanout from fine-pitch parts](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#fanout-from-fine-pitch-parts). Worked patterns: `jitxexamples.patterns.layout_qfn_escape`, `jitxexamples.patterns.layout_bga_escape`, `jitxexamples.patterns.layout_diff_pair_escape`.

- Walk every pad a tagged class width reaches through the tagged nets, not the pads you noticed. A pad needs an escape when the class width does not fit it, or when a trace at that width cannot keep the net's clearance to the pads it passes.
- The escape tag goes on the escape `Route`, and the trunk and escape meet at a `RoutePoint` that is a member of the net. Route and control-point mechanics: `jitx-physical-layout`.
- Escape rules sit at priority 4: `design_constraint(QfnEscapeTag(), priority=4).trace_width(w_escape)`, plus a two-condition clearance only where the pad geometry cannot hold the net's.
- Choose the escape clearance `s_e` first: the clearance that governs the net (the board default, or its class's), or a lower escape clearance at or above `min_copper_copper_space`.
- On a layer with a heavy floor, `s_e` and `w_escape` are at or above that layer's floors; an escape that cannot meet them is an open item for the user.
- Then derive `w_escape` from the placed pads read with `jitx.query`; never type it. It is:
  - strictly below the narrowest pad the escape rule selects;
  - at most `2·(c - s_e)`, where `c` is the smallest distance from the escape's centreline (pad centre to transition) to any other pad. On a QFN the escape leaves along the pad's long axis, so `c` is half the pad width plus the gap to the adjacent pad, and the pad bound decides wherever that gap is at or above `s_e`. On a BGA, `c` is half the channel between the balls the escape runs past: at 1.0 pitch with 0.5 balls the channel is 0.5 and `c` 0.25, so the escape is at most 0.3 at `s_e` 0.1 and 0.26 at `s_e` 0.12;
  - at or above `min_copper_width`, rounded down to a grid you state.
- A floor-valued clearance against `AnyObject` at the escape rung loosens the board default around every escape.
- `RoutingStructure.NeckDown` is not the escape mechanism; a tag on the `Route` is.

## Verification

Build success proves nothing about rules. Submit, `rd.capture()`, then read the captured tree (the loop, frames and `query` semantics: `jitx-physical-layout` [`references/geometry-verification.md`](../jitx-physical-layout/references/geometry-verification.md)). Explanation: [Checking that a rule applied](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#checking-that-a-rule-applied).

| Rule | Read after capture | Pass |
|---|---|---|
| Width | every shape of `route.traces[i].shapes` on each governed route | the trace count is nonzero, and every shape has a `.geometry.width` equal to the winning rule's; a `Polygon` with no width is a failure, never skipped |
| Clearance, pour pullback | `Pour.shape` in board frame (the computed copper, holes included, or `Empty`) against trace and pad geometry | the shapely distance is at or above the rule |
| Relief | the voids and spokes of `Pour.shape` around each pad and via the rule matches | gap and spoke count match the rule; a pad with full contact had no relief |
| Stitch, fence | `rd.query(Via)`, less the vias `visit(rd.root, Via)` lists (the code-placed ones, matched by identity); each position is `(trace.transform * via.transform).translation` | count and positions match the derived pattern |
| Routing structure | trace widths per segment, and `rd.issues(satisfied=True).text()` | each segment at its structure's width; no `Missing routing structure` |

- Read each expected value from the rule object (`rule.trace_width_constraint.width`, `rule.clearance_constraint.clearance`, `rule.thermal_relief_constraint.gap_distance`), not from a constant typed beside the rule list.
- Every declared rule has copper that witnesses it, or it is reported as unwitnessed. A check that prints no failures while a rule went unexercised has not passed.
- `Copper` shapes placed from code reach the layout as written, whatever the rules say: check them against the rules after capture.
- Before `rd.capture()`, in the submit path, `Pour.shape` is the drawn outline.
- The project's check script exits nonzero on any failure; the completion block records its command and exit code. Never report a rule as applied from `status: ok`.

## Why a rule did not fire

Check in this order:

1. Not reachable ([Where rules live](#where-rules-live)).
2. Out-ranked ([Priority](#priority)), a heavy layer's floor included.
3. Wrong arity ([Effects](#effects)), or a builtin passed to `Tags(...)`.
4. Wrong target: `fence_via` on a route or net tag ([Fencing](#fencing)), or a module-level `RoutingStructure`.
5. Below a `FabricationConstraints` `min_copper_*` floor.
6. No generated vias: the tag is not on the `Pour`, the pour is `Empty`, or no site passes ([Stitching](#stitching)). The via class is not the cause: one reached through the substrate, re-declared on it, or declared at module scope works for `stitch_via`.
7. Not taggable, or assigned outside a design context ([What a tag reaches](#what-a-tag-reaches)).
8. `Copper` placed from code, which no rule reshapes.
9. Pour or stitch realization: `jitx-physical-layout` [Pour realization semantics](../jitx-physical-layout/SKILL.md#pour-realization-semantics).

## Anti-string-hacking and completion

Construct tags and rules as structural objects on `self`; batch parameters in a `@dataclass(frozen=True)` or a list; key nothing by an assembled string (base skill `references/architectural-patterns.md`; self-critique with `jitx-code-review`).

The task acceptance block (`jitx-project-builder` `references/completion-blocks.md`) takes from this skill: the board defaults and the classes of nets with each value's source, or "no board defaults" or "no classes of nets" with a reason; the after-build checks with their command and exit code; open items for anything unwitnessed.

API: the docstrings of `jitx.constraints` and `jitx.si`.
