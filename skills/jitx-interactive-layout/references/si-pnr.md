# Place and route under SI constraints

For DDR, LPDDR, wide parallel buses and high-speed differential links.
`general-pnr.md` still applies. Constraints are owned by
`jitx-interconnect-constraints`, swap rules by `jitx-pin-assignment`; read
both from the source.

Timing, skew, delay and loss bounds are constraints on the signals in the
design's code, and their results come from `rd.issues()`
(`layout_report.py -f issues_all`, every result with its `margin`). Your own
delay estimates guide the routing; the issue margins decide pass or fail.
A bound the design states nowhere in code is not checked: say so, hand it
to `jitx-interconnect-constraints`, and route to it meanwhile. A group with
no measurement is unmeasured, not passing.

## What good looks like

- Power first. The decoupling of the balls the interface escapes past is
  placed (often tied to its ball by a `ShortTrace` and parked off the board
  for you), and those power and ground balls and capacitors are fanned out
  to their planes, before any signal fanout: they take via sites and
  channels the signals would otherwise use. A plane is a pour: when the
  plane layers have none, make them with the power fanout (ground on each
  ground layer, a region per rail on the power layers, each covering its
  balls' and capacitors' vias); a pour with no via of its net reads empty
  until one lands. Check each is one piece.
- One pin assignment for the whole interface, even when the task is one
  lane: solve every group's assignment together, from the eligible pool
  in `provide`/`require` and its swap rules
  ([protocol-pin-flexibility.md](../../jitx-pin-assignment/references/protocol-pin-flexibility.md)),
  so no group takes pins or channels another group needs, then route the
  groups in scope. Prefer the assignment that equalizes delay in each group
  and keeps routes from crossing. Say what the assignment leaves for the
  groups not routed yet. Solve it after both ends are placed, and solve it
  again as the layout firms up: when fanout vias, decoupling or a routed
  group leave another group short of pins or channels, re-solve rather
  than route around it. Where the far end is not placed yet, place it
  for the assignment: its position and rotation decide which balls face
  each other.
- Fewest layers. Every layer a signal uses brings its own velocity, loss
  and via transitions into the matching, and every via down to it blocks
  channels on the layers it passes. So the interface goes on as few signal
  layers as it can be routed on, and a split across layers is the last
  resort, not the first plan.
  - Search before you split. Try routings that reach the density one
    layer needs: re-solve the pin assignment, rotate or move the far part,
    move fanout vias, change the escape pattern, route neighbours
    differently. Keep trying while an attempt still improves.
  - Score attempts with fast surrogates, not full routes: the signals
    crossing each cut line between two obstacles against the traces of
    the routing structure that fit through it (after fanout vias and
    decoupling take their share); crossings in the pin ordering, since an
    ordering with no crossings routes on one layer; a coarse grid router
    over the layer's free area. Check a surrogate against the real router
    on a few routes before trusting it, and write each attempt with its
    score to the plan file.
  - Split only when the best attempt still overflows, and then along group
    boundaries, never inside a group: a group is the signals matched to
    each other (a byte lane with its strobe, a command bus with its clock,
    the pairs of an Ethernet PHY), and every signal in it takes the same
    layer and the same via transitions.
  - Say how many layers you used, the attempts you scored before
    splitting, and the overflow that forced each split. Check: every
    route of a group in `state.json` is on its layer between its end vias.
- Differential pairs coupled. A signal the design gives a differential
  routing structure (a clock, a strobe, a lane) is routed as a coupled
  pair: `pair_insertion` near the pads, `pair_point`s along the path, an
  insertion near the far pads, on the pair's structure. Two single routes
  that meet the skew bound are not a coupled pair: if coupling fails, say
  so as a failure with what blocked it. Matching corrects P/N skew before
  group skew, so keep the pad-to-insertion legs equal. An assignment
  re-solve does not track insertion invert state: read the pair back and
  `update_control(..., invert=True)` if the legs cross.
- Vias by the via plan (`general-pnr.md`): each signal's vias next to its
  end pads, the same transitions for every signal of a group.
- Each group within about 5 ps of its bound from the route paths alone
  (layer and `turns` from a path solver), then length matching only where
  margins need it. `envelope_overhead` on `route` or `modify` sets the
  serpentine width (`0` disables matching, None takes the constraints);
  plan where each serpentine goes before routing neighbours into it.
  `UnsquiggledRoute` means no room for it.

Expect to write solvers as project scripts, each writing its decisions to
a file: pin assignment, via breakout, route paths. `UnassignedPin` lists
constrained pins with no assignment yet. `force=True` only on spots the
solver checked.

## Done for an SI group

Its decoupling placed and fanned out before its signals; every path routed
and measured; every skew, delay and loss check met with margins reported;
each differential pair coupled on its structure; no `UnsquiggledRoute` or
blocked route; length matching only where margins needed it.
