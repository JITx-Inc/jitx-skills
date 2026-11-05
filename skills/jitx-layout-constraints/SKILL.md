---
name: jitx-layout-constraints
description: "Use when the user asks for design rules on a placed and routed design: default trace width, clearance and thermal relief; net classes by tag (power, RF, sense) with their own width and spacing; net-to-net, trace-to-pour, hole, board-edge, per-layer and heavy-copper clearance; pour rules (thermal relief, direct connect, sliver removal); via stitching as a rule; via fencing of a pour outline, an antipad or a grounded coplanar line; applying routing structures to nets and escapes by tag; escape width to fit a QFN, BGA or fine-pitch pad; checking after build that a rule applied, or why it did not. Fab minimums, stackups, vias and routing-structure definitions belong to jitx-substrate-modeler ('set fabrication rules' means the fab floor); drawing copper and pours, code-placed vias and realized-pour diagnosis to jitx-physical-layout; decoupling and net wiring to jitx-circuit-builder; topology and timing to jitx-interconnect-constraints."
---

# JITX Layout Constraints

Tags, `design_constraint` rules keyed on them, and the reads after capture that show each applied. Explanation: the Essentials page [Layout Constraints](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html). The functions named here, in `jitxexamples.patterns`, do the arithmetic; their docstrings hold the measurements.

## Environment

Invoke the base `jitx` skill first. Add `jitxexamples` to the project's `dependencies`: the design calls its functions at build time. An `ImportError`, or a `TypeError` from a named function (an older `derive_escape` takes no `escape_clearance`), means the installed copy predates them: upgrade it. If the upgrade does not bring them in, stop and list each value the function would derive as an open item. Never drop a keyword to make a call work, and never derive the value by hand instead.

## The rule system

`design_constraint(c)` is a one-condition rule; `design_constraint(c1, c2)` a two-condition rule, matched in either order ([Design Constraints](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html)).

### Conditions

A `Tag` subclass declared at module scope matches what it reaches ([What a tag reaches](#what-a-tag-reaches)), its subclasses included. `IsTrace`, `IsPour`, `IsVia`, `IsPad` and `IsCopper` are conditions only (`Tags(IsTrace)` raises `TypeError`). `IsHole` is a hole in the outline, a `Cutout` and every via drill; `IsBoardEdge` the outer edge only. `OnLayer(i)` is layer `i`, 0 top, -1 bottom. `AnyObject`, `&`, `|` and `~` complete them.

### Effects

A two-condition rule takes only `.clearance(mm)`. A one-condition rule takes `.trace_width`, `.thermal_relief(gap_distance, spoke_width, num_spokes)`, `.pour_feature_size`, `.stitch_via`, `.fence_via`, `.routing_structure`, `.serpentine_params` or `.coupled_pair_params`. There is no neckdown, pour-isolation or direct-connect effect.

### Priority

Higher `priority=` wins first; at equal priority the more specific condition wins, object type tags first, so a `PowerTag()` width at 0 loses to the `IsTrace` default at 0 ([Always use object type tags!](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html#always-use-object-type-tags)). Use one ladder, written in a comment beside the rules:

| Priority | Rules |
|---|---|
| 0 | board defaults |
| 1 | a layer's floors; the trace-to-pour rule |
| 2 | net-tag and pour-tag rules |
| 3 | pad, landpattern and component tag rules; a rule that must beat a rung-2 rule (a high-current or sense width, `PowerTag() & OnLayer(1)`, a heavy-layer copy) |
| 4 | escape segments; a direct connect |
| 5 or above | protections (keep-away, creepage, edge, hole), one rung each, the larger clearance higher |

Traps ([Priority is a ladder](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html#priority-is-a-ladder-so-put-what-must-win-at-the-top)):

- The losing rule is not applied at all. Raise a protection above every permissive rule that can match its copper, at no less than the class value it replaces, and narrow the permissive rule: `(IsTrace & EscapeTag(), IsPad & PartPadTag())`, not `(EscapeTag(), AnyObject)`.
- An exclusion (`~SomeTag()`) must hold on either side, and excluding a whole tag withdraws the rule everywhere.
- A width override under a rule the object already matches can leave a route with zero traces and a clean build: count traces before comparing widths.

### Where rules live

Rules are found by walking the design tree: one at module scope, or built and dropped, does not exist. Board-wide rules go in the `Design`'s `self.rules = [...]`; a circuit's rules go on that circuit and still apply board-wide. Stay at or above the substrate's `FabricationConstraints` (`current.substrate.constraints`), which `jitx-substrate-modeler` defines.

## What a tag reaches

A tag on a `Net` reaches its traces, pours, pads and code-placed vias, so a clearance or relief rule on it acts on the pads and vias too. On a `Pad`, `Landpattern` or `Component` it reaches those pads, the way to pick out some of a net's pads; on a `Route`, that route's segments only; on a `Pour` or `Via`, that object. Tags on a `TopologyNet`, `Copper`, `Circuit` or `ControlPoint` are also accepted; tags assigned outside a design context, or to anything else, warn and do nothing.

## Board defaults

Unruled copper comes out at the fab floor (measured on jitx 4.6: a route at `min_copper_width`), and a pad no relief rule matches joins its pour solid. Write what the board needs ([Defaults above the fab floor](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#defaults-above-the-fab-floor); `layout_default_rules`): `design_constraint(IsTrace).trace_width(w)`, `design_constraint(IsCopper, IsCopper).clearance(c)` and `design_constraint(IsPad).thermal_relief(gap, spoke, n)`.

The coplanar cap: board-wide clearances (the copper default and the trace-to-pour rule) stay at or below the smallest coplanar structure's clearance on the board, since a wider board rule widens the gap of a coplanar line with no pair rule. Lower a fab-sheet value to the cap, cited as such; write a wider prompt value and list it as an open item naming the clearance it exceeds.

Every value traces to a fab-sheet row cited by number, the prompt, a cited datasheet or standard, or a derivation with its arithmetic shown; for a function's value, the call, its inputs, what it returns (QFN `Escape.pad_width`, `.pad_gap`, `.centreline_clearance`, `.escape_clearance`, `.width`; `BgaEscape.channel_clearance`, `.escape_clearance`, `.width`; the `coplanar_gap` value), and the relation the function checks, from its docstring, with the numbers (for `checked_fence_pattern`, `initial_offset - pad/2 >= pour_gap`). Anything else is an open item. No chart or formula of your choosing sets a width from a current: ask for the width, or the copper weight, temperature rise and sizing standard.

## Classes of nets

A class of nets is a tag on nets with its rules written once; a subclass (`HighCurrentTag(PowerTag)`) takes its own width at 3. `p` is a protection rung.

| Nets | Rule |
|---|---|
| Power | `PowerTag()` width and `(PowerTag(), AnyObject)` clearance, at 2 |
| RF, coplanar | `RFLineTag` with a `routing_structure` rule, and the pair rule `design_constraint(RFLineTag(), GroundTag(), priority=2).clearance(c_s)`, `c_s` the structure's clearance |
| Kelvin sense | a `SenseTag` on the sense `Route`s, not the net (it shares the power net), its width at 3, a clearance to `PowerTag` at `p` |
| Sensitive against noisy | `(RFLineTag(), NoisyTag())` clearance at `p` (`layout_sensitive_net_clearance`) |

- The coplanar gap, trace edge to pour, is `coplanar_gap(structure_clearance, winning_rule_clearance)` (`layout_cpwg_two_row_fence`): the structure's clearance is a floor, and a wider winning rule between line and ground widens it. At 2 the pair rule beats a wider rule lower on the ladder (a board rule at 0, an `AnyObject` keep-away at the default priority) and loses to one above (measured on jitx 4.6). With several coplanar structures on a net, set the pair rule to the smallest structure's clearance.
- A class-to-class clearance keeps a line from a noisy net and leaves ground alone. A keep-away `(RFLineTag(), AnyObject)` at a protection rung outranks the pair rule and, wider than the structure's clearance, pushes the coplanar ground out.

## Pours and relief

Pour realization belongs to `jitx-physical-layout` ([Pour realization semantics](../jitx-physical-layout/SKILL.md#pour-realization-semantics)).

| Intent | Rule |
|---|---|
| Trace to pour | `(IsTrace, IsPour)` clearance at 1, under the coplanar cap |
| All of a net's pads and vias | the net tag's `thermal_relief` at 2 |
| Some pads | a tag on the pads, landpattern or component, its relief at 3 (`layout_thermal_classes`) |
| Direct connect | `DirectConnectTag` on the pad, `thermal_relief(gap, pad_diagonal, 4)` at 4; or no relief rule matching the pad |
| Sliver removal | `pour_feature_size(min_width)` on a pour tag; a coplanar strip narrower than `min_width` goes whole |
| Edge; slots, cutouts, drills | `(IsBoardEdge, AnyObject)`; `(IsHole, AnyObject)`, each at `p` (`layout_edge_and_cutout`) |

- `IsHole` matches via drills: a hole rule wider than a via's pad pulls pours back from every other-net via.
- A pour stops the clearance plus 0.01 from traces and the board edge (measured on jitx 4.6); compare pullback with the rule, not an exact value.
- A pour with no pad or via of its own net inside comes back `Empty`; stitch and fence vias do not anchor it.

Heavy copper on one layer (`layout_heavy_copper_layer`):

- `heavy_layer_index(current.substrate)` finds the layer by conductor thickness and raises when no one layer is heaviest (a substrate task first; with two heavy layers, pass each index). Select it with `OnLayer(i)`; `OnLayer.internal()` matches every inner layer.
- A floor at 1 loses, unreported, to every rule at 2 or above on the layer. `heavy_layer_rules(layer, min_width, min_clearance, trace_to_pour, class_rules, exclude=...)` returns the floors and the trace-to-pour rule's layer form at 1, and a layer copy at 3, at the floor, of each rule in `class_rules` below it. Pass every `trace_width` and two-condition `clearance` rule at 2 or 3 whose (first) condition is one tag and that can match the layer; write any other shape's layer form by hand (`PowerTag() & OnLayer(1)` raises). A class that wants more than the floor there writes its own `& OnLayer(i)` rule at 3 and stays out of `class_rules`.
- `exclude` (such as `SenseTag`) narrows the width copies only; the docstring gives the cost. An escape, a protection or a pad-side rule at 3 that can match the layer meets the floor itself, or is an open item.

## Stitching

`design_constraint(StitchedPourTag()).stitch_via(ViaClass, checked_stitch_grid(ViaClass, fab, pitch, inset))`, the tag on each `Pour` (`layout_stitched_pour`; [Stitching a pour](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#stitching-a-pour)). The vias take the pour's net.

- Sites sit on multiples of the pitch from the board origin. `inset` runs from the via pad's edge to the computed pour boundary; a failing site is dropped, never moved, with no issue.
- Below the via pad the grid thins to a checkerboard, and JITX checks no pitch against the fab. `checked_stitch_grid` refuses a pitch below `min_stitch_pitch`, the larger of one via pad and drill plus `min_hole_to_hole`; same-net pads need no copper spacing.
- A fence on the same pour displaces nearby sites (measured on jitx 4.6: an inward fence 0.6 in removed the ring 1.0 in); pass that band as `leave_out`.
- To check, call `expected_stitch_sites(pours, via, grid, fab, pads=..., placed_vias=..., leave_out=...)` once per group of pours stacked over one area (a through via crosses them all), with each captured `Pour.shape` in board frame ([Coordinate frames](../jitx-physical-layout/references/geometry-verification.md#coordinate-frames)). Every returned site holds a generated via; a via outside the set is not a failure, and an empty set is a failure, not a pass.

## Fencing

Explanation: [Fencing](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#fencing), [A grounded coplanar line](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#a-grounded-coplanar-line).

| Target | How | Offsets from |
|---|---|---|
| A pour outline | `fence_via(ViaClass, ViaFencePattern(...))` on a tag on the `Pour` (`fenced_pour_outline`) | the drawn outline, positive outward |
| A routed line | `RoutingStructure.Layer(...).fence(ViaClass, ViaFencePattern(...), reference_layer=i)`, applied by a `routing_structure` rule; a copy with the same layer values when the substrate is not yours (`layout_cpwg_two_row_fence`) | the trace edge to the via centres |

- A `fence_via` rule fences no route, with no issue; on a net's tag it fences that net's pours. Route fences come only from `Layer.fence`, on the reference plane's net.
- Row k sits `initial_offset + (k-1)·offset` out; an unset `initial_offset` takes `offset`. A pitch below the via pad is thinned.
- `checked_fence_pattern(pattern, via, pour_gap)`, with `pour_gap` from `coplanar_gap`, refuses a first row whose pads sit in the gap, which JITX does not check; `rows_in_coplanar_pour` lists the rows that reach the coplanar pour.
- A coplanar pour needs a same-net via in each region the line separates.
- Counts: `fence_count_range(outline, row_offset, pitch, via, fab)` per outline row, `row_offset` that row's offset from the line above (an outward offset keeps each corner square, one via on its diagonal); `straight_run_fence_sites(run_length, pitch, row)` per side per row of a route's straight run, its round ends checked by position only. A distance band does not separate fence vias from a stitch grid; position on the derived row does.

## Routing structures by tag

The substrate defines structures; rules apply them ([Routing structures by tag](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#routing-structures-by-tag); `layout_routing_structure_by_tag`).

- A net: `design_constraint(SignalTag(), priority=2).routing_structure(rs, ref_net=self.GND)`, the tag on the net; it satisfies a `Constrain`'s need for a structure.
- One segment: a tag on its `Route` (on the net's tag it necks the whole net), with its structure at 4.
- A rule and a `Constrain(...).structure(...)` on one net: the rule wins with no issue. Use one.
- Build a `RoutingStructure` in the circuit's `__init__` or on the substrate; at module level the rule raises `TypeError: 'Instantiable' object is not iterable`.

## Fanout

When a class width does not fit its pads, keep the class rule and make the last segment its own `Route` with an escape tag, its width at 4 ([Fanout from fine-pitch parts](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#fanout-from-fine-pitch-parts); `layout_qfn_escape`, `layout_bga_escape`, `layout_diff_pair_escape`).

- Walk every pad the class reaches: one needs an escape when the width does not fit it or cannot keep the net's clearance to the pads it passes. Trunk and escape meet at a `RoutePoint` on the net (`jitx-physical-layout`).
- Add an escape clearance only where the pads cannot hold the net's; a floor-valued clearance to `AnyObject` at 4 loosens the default around every escape.
- Choose the escape clearance `s_e` first: the net's governing clearance, or a lower one at or above `min_copper_copper_space`. Where the pads sit closer than the class clearance, say what the escape relaxes.
- Never type the width. `layout_qfn_escape.derive_escape(landpattern, pad, fab, escape_clearance=s_e)` or `layout_bga_escape.derive_escape(landpattern, ball, outward, fab, escape_clearance=s_e)` returns it as `.width`; other geometry takes `escape_width(pad_width, c, s_e, fab)`, `c` the least distance from the escape's centreline to another pad. One tag over several pads takes the smallest width.

## Verification

A rule that builds is not a rule that applied. Submit, `rd.capture()`, then read the captured tree (`jitx-physical-layout` [`references/geometry-verification.md`](../jitx-physical-layout/references/geometry-verification.md); [Checking that a rule applied](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html#checking-that-a-rule-applied)).

| Rule | Read | Pass |
|---|---|---|
| Width | every shape in `route.traces[i].shapes` | traces exist and every `.geometry.width` equals the winning rule's; a `Polygon` with no width fails |
| Clearance | `Pour.shape` (or `Empty`) or the other route's traces, in board frame | shapely distance at or above the rule |
| Relief | voids and spokes of `Pour.shape` at each matched pad | gap and spoke count match |
| Stitch, fence | `rd.query(Via)` less the code-placed vias from `visit(rd.root, Via)`, at `(trace.transform * via.transform).translation` | pour not `Empty`; sites and counts as derived above |
| Routing structure | widths per segment; `rd.issues(satisfied=True).text()` | structure widths; no `Missing routing structure` |

- Derive each expected value from the prompt or fab sheet; a value read from the rule alone checks a wrong rule against itself.
- Capture does not show which rule won. For a route's width, select it in the board view and press B.
- Every rule has witnessing copper or is reported unwitnessed. `Copper` placed from code reaches the layout as written, whatever the rules say: check it.
- The check script exits nonzero on any failure; the completion block records its command and exit code. Never report a rule applied from `status: ok`.

## Why a rule did not fire

1. Not reachable ([Where rules live](#where-rules-live)).
2. Out-ranked ([Priority](#priority)), a heavy layer's floor included.
3. Wrong arity ([Effects](#effects)), or a builtin in `Tags(...)`.
4. Wrong target: a `fence_via` rule meant for a route, or a module-level `RoutingStructure`.
5. Below a `min_copper_*` floor.
6. No generated vias: the tag is not on the `Pour`, or no site passes. An `Empty` pour still gets stitch vias, so read its `Pour.shape`.
7. Not taggable or outside a design context; `Copper` placed from code; pour realization (`jitx-physical-layout`).

## Completion

Tags and rules are structural objects on `self`; nothing is keyed by an assembled string (base skill `references/architectural-patterns.md`; `jitx-code-review`). The acceptance block (`jitx-project-builder` `references/completion-blocks.md`) takes the defaults and classes with each value's source, or "none" with a reason; the checks with command and exit code; and open items for anything unwitnessed. API: the docstrings of `jitx.constraints` and `jitx.si`.
