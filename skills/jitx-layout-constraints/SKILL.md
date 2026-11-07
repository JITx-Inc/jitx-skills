---
name: jitx-layout-constraints
description: "Use when the user asks for design rules, or for the layout to meet an electrical requirement: isolation between domains, voltage clearance, current capacity, noise coupling, return paths. Covers default width, clearance and relief; net classes by tag (power, RF, sense, high voltage); net-to-net, trace-to-pour, hole, board-edge, per-layer and heavy-copper clearance; pour rules (relief, direct connect, sliver removal); via stitching as a rule; via fencing of a pour outline, an antipad or a coplanar line; applying routing structures by tag; escape width to fit a QFN, BGA or fine-pitch pad; verifying a rule applied, or why it did not. Fab minimums, stackups, vias and routing-structure definitions belong to jitx-substrate-modeler ('set fabrication rules' means the fab floor); drawing copper and pours, slots, code-placed vias and realized-pour diagnosis to jitx-code-layout; decoupling and net wiring to jitx-circuit-builder; topology and timing to jitx-interconnect-constraints."
---

# JITX Layout Constraints

This skill adds the constraints that make a layout perform electrically. JITX routes to the rules it is given: a board that builds clean can still arc across an isolation gap, overheat a power trace or couple a switch node into a receiver. Explanation: [Layout Constraints](https://docs.jitx.com/en/latest/essentials/physical_design/layout-constraints.html).

## Environment

Invoke the base `jitx` skill first. Add `jitxexamples` to the project's `dependencies`: the design calls its `jitxexamples.patterns` functions. An `ImportError`, or a `TypeError` from a named function, means an older copy: upgrade it, and if that does not bring the function in, list each value it would derive as an open item. Never drop a keyword, and never derive the value by hand instead.

## Start from what the board needs

Before writing a rule, read the schematic, the prompt and every document given (requirements, fab sheet, datasheets), and list what the layout must hold electrically. The user may name values, or only the board.

| Need | Why | Rule |
|---|---|---|
| Fab floor | copper under the fab's minimums is not built as drawn | the substrate holds it; board defaults at 0 sit at or above it |
| Current | a narrow trace drops voltage and heats | a class width on the net's tag |
| Working voltage | conductors too close at voltage arc or track | a clearance from the voltage class's tag to `AnyObject` at a protection rung |
| Isolation | a barrier part is only as good as the copper spacing across it | a clearance between the two domains' tags, each on every net of its domain, grounds included, at a protection rung |
| Impedance | a line off its impedance reflects and loses signal | a routing structure on the net's tag |
| Return path | return current follows the nearest reference; a gap in it radiates | stitching, fencing, a coplanar ground |
| Coupling | a noisy net beside a sensitive one couples into it | a clearance between the two classes' tags |
| Assembly | a pad tied solid into a plane sinks heat and solders poorly; a relieved one carries less current | relief per pad class, direct connect where current needs it |

Every value traces to the prompt, a rule the design already carries, a fab-sheet row by number, a datasheet or standard quoted from a document you were given, or a derivation with its arithmetic shown; for a function's value, the call, its inputs, the dataclass fields it returns (`BgaEscape.channel_clearance`, `Escape.centreline_clearance`, `Escape.pad_gap`) and the relation its docstring checks, with the numbers. Where nothing given settles a value (a 48 V or mains net with no spacing stated, an isolation rating with no barrier distance), name what would (the isolating part's datasheet, IPC-2221B's conductor spacing table, the product's safety standard such as IEC 62368-1, 61010-1 or 60601-1) and list an open item: never pick a number. No chart or formula of your choosing sets a width from a current: ask for the width, or the copper weight, temperature rise and sizing standard. A clearance rule holds distance across a layer's surface (copper to copper, hole or edge), so for copper on one surface with no slot between, where a source gives clearance and creepage, it takes the larger; distance through insulation between layers is an open item. A slot that lengthens a creepage path is a `Cutout` (`jitx-code-layout`) or a hole in the board outline (`jitx-mechanical`), held from copper by an `IsHole` rule.

In the completion, give each rule one line on what fails on this board without it (an arc, a short, a hot trace, a reflection, a cold joint, a trace that etches open at the fab's limit), not what the rule does.

## The rule system

`design_constraint(c)` is a one-condition rule; `design_constraint(c1, c2)` a two-condition rule, matched in either order ([Design Constraints](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html)).

A condition is a `Tag` subclass declared at module scope (matching its subclasses too), a builtin (`IsTrace`, `IsPour`, `IsVia`, `IsPad`, `IsCopper`; conditions only, `Tags(IsTrace)` raises `TypeError`), `IsHole` (outline holes, cutouts and every via drill), `IsBoardEdge`, `OnLayer(i)` (0 top, -1 bottom), `AnyObject`, or a combination with `&`, `|` and `~`.

A two-condition rule takes only `.clearance(mm)`; the rest (`.trace_width`, `.thermal_relief(gap_distance, spoke_width, num_spokes)`, stitching, fencing, routing structures) take one condition.

### Priority

Higher `priority=` wins; at equal priority the more specific condition wins, object type tags first, so a `PowerTag()` width at 0 loses to the `IsTrace` default at 0. The loser is not applied, and nothing reports it. One ladder, commented beside the rules:

| Priority | Rules |
|---|---|
| 0 | board defaults |
| 1 | a layer's floors; the trace-to-pour rule |
| 2 | net-tag and pour-tag rules |
| 3 | pad, landpattern and component tag rules; a rule that must beat a rung-2 rule (a high-current or sense width, a heavy-layer copy) |
| 4 | escape segments; a direct connect |
| 5 or above | protections (isolation, voltage, keep-away, edge, hole), one rung each, the larger clearance higher |

- A protection goes above every permissive rule that can match its copper, at no less than the class value it replaces; narrow the permissive rule too: `(IsTrace & EscapeTag(), IsPad & PartPadTag())`, not `(EscapeTag(), AnyObject)`, with both tags assigned to the copper they mean.
- An exclusion (`~SomeTag()`) must hold on either side; excluding a whole tag withdraws the rule everywhere.

### Where rules live, what a tag reaches

Rules are found by walking the design tree: one at module scope, or built and dropped, does not exist. Board-wide rules go in the `Design`'s `self.rules = [...]`; a circuit's rules still apply board-wide.

A tag on a `Net` reaches its traces, pours, pads, code-placed vias and `Copper`; on a `Pad`, `Landpattern` or `Component`, those pads; on a `Route`, its segments; on a `Pour` or `Via`, that object. `TopologyNet`, `Copper`, `Circuit` and `ControlPoint` also take tags; anything else, or a tag assigned outside a design context, warns and does nothing.

## Defaults and classes

Unruled copper comes out at the fab floor, and a pad no relief rule matches joins its pour solid. Write only the defaults the board needs above the floor, each with its margin's source: `design_constraint(IsTrace).trace_width(w)`, `design_constraint(IsCopper, IsCopper).clearance(c)`, `design_constraint(IsPad).thermal_relief(...)`, which matches every pad, so only a higher-priority direct connect joins one solid (`layout_default_rules`).

A class is a tag on its nets with its rules written once: `PowerTag()` width and `(PowerTag(), AnyObject)` clearance at 2; a subclass (`HighCurrentTag(PowerTag)`) takes its own width at 3. A Kelvin sense line shares the power net, so its `SenseTag` goes on the sense `Route`s, its width at 3. A class-to-class clearance, `(RFLineTag(), NoisyTag())` or `(PrimaryTag(), SecondaryTag())`, keeps one class from another and leaves each one's own ground alone (`layout_sensitive_net_clearance`).

The coplanar cap: a board-wide clearance wider than a coplanar line's gap widens the gap of any line without a pair rule to its ground, unreported. Keep board clearances at or below the smallest coplanar structure's clearance: lower a fab-sheet value to it, cited as such; a wider prompt value is written as given and listed open, naming the clearance it exceeds. Set each gap with a pair rule (Fencing).

## Pours and relief

| Intent | Rule |
|---|---|
| Trace to pour | `(IsTrace, IsPour)` clearance at 1 |
| A net's pads and vias | the net tag's `thermal_relief` at 2 |
| Some pads | a tag on the pads, landpattern or component, relief at 3 (`layout_thermal_classes`) |
| Direct connect | no relief rule matching the pad; or `DirectConnectTag` on the pad, `thermal_relief(gap, pad_diagonal, 4)` at 4; measure the join, and give a pad that voids no relief rule |
| Sliver removal | `pour_feature_size(min_width)` on a pour tag |
| Edge; slots, cutouts, drills | `(IsBoardEdge, AnyObject)`; `(IsHole, AnyObject)`, at protection rungs (`layout_edge_and_cutout`) |

- `IsHole` matches via drills: a hole rule wider than a via's pad pulls pours back from every other-net via. A plated through-hole pad's drill is untested (`layout_edge_and_cutout`): measure it or list it open.
- Why a pour comes back `Empty`: [`jitx-code-layout`, pours](../jitx-code-layout/SKILL.md#copper-pours-and-keepouts).

A heavy copper layer needs wider traces and gaps (`layout_heavy_copper_layer`). Cite the stackup row whose copper makes it heavy; `heavy_layer_index(current.substrate)` finds it, `OnLayer(i)` selects it, `OnLayer.internal()` matches every inner layer. A floor at 1 loses, unreported, to every rule at 2 or above, so `heavy_layer_rules(layer, min_width, min_clearance, trace_to_pour, class_rules, exclude=...)` returns the floors plus a copy at 3, at the floor, of each rule passed whose value is below it: every `trace_width` and two-condition `clearance` at 2 or 3 whose first condition is one tag. An escape, protection or pad-side rule at 3 or above on that layer meets the floor itself, or is an open item.

## Stitching

`design_constraint(StitchedPourTag()).stitch_via(ViaClass, checked_stitch_grid(ViaClass, fab, pitch, inset))`, the tag on each `Pour` (`layout_stitched_pour`); the vias take the pour's net.

- Sites sit on multiples of the pitch from the board origin; `inset` runs from the via pad's edge to the computed pour boundary, and a site that fails it is dropped, never moved, unreported.
- Below the via pad the grid thins to a checkerboard, and JITX checks no pitch against the fab: `checked_stitch_grid` refuses a pitch below `min_stitch_pitch`. Clearance is not enforced between copper of the same net, so stitch via pads need no copper spacing between them.
- To check: `expected_stitch_sites(pours, via, grid, fab, pads=..., placed_vias=..., leave_out=...)` once per group of pours stacked over one area, with captured `Pour.shape` in board frame, and `leave_out` for the band a fence displaces. A via outside the set is not a failure; an empty set is.

## Fencing

A via fence keeps fields in and gives a line's ground a short return.

| Target | How |
|---|---|
| A pour outline | `fence_via(ViaClass, ViaFencePattern(...))` on a tag on the `Pour` (`fenced_pour_outline`); offsets from the drawn outline, positive outward |
| A routed line | `RoutingStructure.Layer(...).fence(ViaClass, ViaFencePattern(...), reference_layer=i)`, applied by a `routing_structure` rule; a copy with the same layer values when the substrate is not yours (`layout_cpwg_two_row_fence`); offsets from the trace edge |

- A `fence_via` rule fences no route, unreported.
- Grounded coplanar: board clearances under the cap, the gap set by `design_constraint(RFLineTag(), GroundTag(), priority=2).clearance(c_s)` at the structure's clearance; with several coplanar structures on a net, at the smallest one's. The gap is `coplanar_gap(structure_clearance, winning_rule_clearance)`; a keep-away from the line to `AnyObject` above 2, wider than the gap, pushes the ground out. Measure the realized gap.
- Row k sits `initial_offset + (k-1)·offset` out; an unset `initial_offset` takes `offset`. JITX puts fence pads inside the gap unreported: `checked_fence_pattern(pattern, via, pour_gap)` refuses that.
- A coplanar pour needs a same-net via in each region the line separates; an unanchored region vanishes unreported.
- A via `KeepOut` over a fence removes its vias, unreported: space other copper with a tag clearance.
- A fence pitch below one via pad thins unreported, and below `min_stitch_pitch` the fab cannot drill it: check the pitch.
- Count with `fence_count_range` per outline row and `straight_run_fence_sites` per side per row of a straight run, and assert that count, not that vias exist; identify fence vias by position on the derived row, not a distance band.

## Routing structures by tag

The substrate defines structures; rules apply them (`layout_routing_structure_by_tag`): `design_constraint(SignalTag(), priority=2).routing_structure(rs, ref_net=self.GND)` with the tag on the net, or a tag on one segment's `Route` at 4. A rule beats a `Constrain(...).structure(...)` on the same net, unreported: use one.

## Fanout

When a class width does not fit its pads, keep the class rule and give the last segment its own `Route` and escape tag, width at 4, meeting the trunk at a `RoutePoint` (`layout_qfn_escape`, `layout_bga_escape`, `layout_diff_pair_escape`). Walk every pad the class reaches: one needs an escape when the width does not fit it or cannot keep the net's clearance to the pads it passes; where pads sit closer than the class clearance, say which, by how much, and what the escape relaxes. The escape clearance `s_e` is the net's governing clearance, or a lower one at or above `min_copper_copper_space` stated as relaxed for the escape only, with its reason; where the governing clearance leaves only the fab-minimum width, lower `s_e` to widen the escape, and say so. Never type the width: `layout_qfn_escape.derive_escape` or `layout_bga_escape.derive_escape(..., escape_clearance=s_e)` returns it, or `escape_width(pad_width, c, s_e, fab)` for other geometry; one tag over several pads takes the smallest. If it raises with `s_e` at `min_copper_copper_space`, no legal escape fits: list it open. A floor-valued clearance to `AnyObject` at 4 loosens every escape's surroundings.

## Verification

A rule that builds is not a rule that applied. Build, `rd.capture()`, and read the captured copper ([verification](../jitx-code-layout/SKILL.md#verification)): widths, distances between the copper each clearance relates (pads included), relief voids and spokes, generated vias against expected sites and counts, `rd.issues(satisfied=True)`.

- Derive expected values from the prompt, documents or geometry, never from the rule.
- A route can realize as a widthless `Polygon`, or with no traces (a width override under a rule it already matches can do this): a width check fails on either, never skips it.
- Every rule has witnessing copper or is reported unwitnessed. `Copper` placed from code is drawn as written whatever the rules say (routes other than an envelope section keep their clearance to it): check it.
- Capture does not show which rule won; the board view does (select the route, press B).
- The check exits nonzero on failure; `status: ok` is not proof.
- A rule that did not apply is usually unreachable, out-ranked (a heavy layer's floor too), the wrong arity, aimed at the wrong target, below a `min_copper_*` floor (not a `routing_structure` rule, whose width and pair gap override the floors), or keyed on a tag not on the `Pour`.

## Completion

Tags and rules are structural objects on `self`, never keyed by an assembled string (`jitx-code-review`). The completion block (`jitx-project-builder` `references/completion-blocks.md`) lists each rule with its value's source and the need it holds, the checks with command and exit code, and open items.
