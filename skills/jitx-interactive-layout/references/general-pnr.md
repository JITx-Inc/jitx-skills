# General place and route

What a good layout looks like, and the check for each. Router behaviour
noted here depends on the design: confirm it with a read-back.

## Plan from the source

- Read topology chains (`TopologyNet`, `>>`), `ShortTrace` pairs, power
  nets and widths, high-speed nets and local circuits from the source.
- Default width and clearance at the fab's minimum (no default rule in the
  source means the minimum) is a rule to raise before routing, unless the
  user asked for the minimum: defaults above it are a fix in the source
  (`jitx-layout-constraints`), and the minimum stays for the pads that
  need it.
- A power net with no width rule in the source is a rule to raise before
  routing: its width is a fix in the source (`jitx-layout-constraints`),
  from the user's figure, not one you pick. Never list it in the checks'
  `power` at the default width: that passes a thin trace.
- Only chain neighbours can be routed to each other; anything else is
  refused (`RequestRejected`, or `DroppedRoute` with `not-in-topology` for
  a code route).
- Pin-assigned ports: the capture's assignment follows placement and is
  often poor. Pick pins from the `provide`/`require` pool and route to them.

## Floorplan by blocks

A whole board placed in one batch and fixed afterwards loses quality in
every circuit. Work block by block inside a floorplan.

- Blocks are the design's subcircuits: a regulator, a PHY with its crystal
  and decoupling, a connector with its parts.
- Size each block from the sum of its courtyards times a routing allowance
  (near 2 for dense passives, 1.2 for a connector alone; adjust from the
  first blocks you finish).
- Draw the flows before the blocks: each signal bundle and each power path
  from source to load. A bundle takes area: its channel is the bundle's
  width (signals times trace width plus space, over the layers it may use)
  for its whole length, and a wide bus can need as much area as a
  regulator. Give every flow its channel in the floorplan, then fit the
  blocks around the channels. A block in a bundle's path (a regulator, a
  crystal, a connector) moves out of it; the bundle does not route through
  or around it.
- Vias block area on every layer they pass through, not only where they
  land. A fanout field or a row of plane vias closes channels on the inner
  and bottom layers under it; count that blockage when sizing the channels
  on those layers.
- Give each block a region of whatever shape it needs, connectors on their
  edges, with the channels between blocks. Write the regions and channels
  to a file the placement scripts read.
- An outline the user or the caller gives as a limit, or leaves to place
  and route, is yours to size: the smallest board that holds the regions and
  channels, changed in the source, with what binds it stated. Any other
  outline stays as the source has it.
- Place, route and check one block at a time (`layout_checks.py` with
  `scope` set to the block). A later block does not move an earlier
  block's parts; resize the floorplan and rerun instead.

## Pin selection

For signals taken with `require`, choose the whole pool's pins at once,
after both ends are placed, before routing any of it. A route's detour
ratio (`circuitousness`) cannot see a wrong pin (a straight route to
a far pin has a ratio of 1), and a pin one signal takes is gone for the
rest.

1. Name each pool in the checks config `pin_selection`: `starts`, each
   signal's load-end pad, and `ends`, the component or pad keys
   whose pins are the pool: `route_ends` also answers the net's other
   pads (a pull-up).
2. Run `layout_checks.py -f pin_ends`. It saves each signal's possible
   ends (`pin-ends.json`) and returns the least-total selection.
3. Check it against what a straight line ignores (courtyards, via sites,
   the layer plan, crossings): each costs a via or a detour.
4. Route each signal to its chosen pad, then read `pin_selection`. A
   selection other than the least-total one needs its reason in `accept`.
   If the summary lists `stale_labels`, restart the session and rerun the
   checks before reading `connectivity`.

A bundle's pins (an SPI bus) can be tied to one peripheral instance:
routing one signal narrows what the rest answer, so the least
total over the unrouted reading may mix instances and is a lower bound.
List one instance's pads (the component's `provide` in the source) in
`ends` to read its own least total (no new reading), route the instance
with the least, and leave its list in `ends` as the declared pool; or
keep the wider `ends` and name the instance in `accept`. An `ends`
narrowed to one bundle still lists the pads the group's other bundles may
take, or their starts have no candidate.

On a routed board, delete the whole pool's routes and `sync` before
reading again: a signal lifted alone gets back only pads no other route
holds. On an Edit, do that only when the user asked to reconsider the
pins.

Without `route_ends`, derive the pool from the source and choose the same
way; the check reports `pin_selection` as not measurable.

## Via plan

Before routing, give every connection a layer and its vias, and write the
plan to a file the routing scripts read.

- Layers first. Where the stackup, the source and the user leave it
  open, a four-layer board defaults to both inner layers as ground planes
  with no routing, signals and power on the outer layers, and power that
  leaves TOP crossing to a pour on BOTTOM. State the plan, and the reason
  wherever it departs from this.
- A connection gets 0, 1 or 2 vias: 0 when both ends reach its layer, 1
  when one end does not, 2 when neither does. A through-hole pad reaches
  every layer; a surface pad reaches its own side.
- Each via sits at the end pad it serves, as that pad's escape: beside
  it, or in it at its centre where the via definition allows via-in-pad.
  Never mid-route. A power or ground pad's via to its plane is its escape the
  same way.
- A signal leaving a through-hole pad on an inner layer starts on that
  layer at the pad: no stub on TOP to a via.
- Pads may share a plane via when they are on the same net, the shared
  route is short, and the current is within what one via carries by the
  design's rules (ask; do not guess a figure). Every ground island gets a
  plane via.
- When a route will not fit its plan, change the plan (another layer, a
  moved part, a moved via spot), not the route.
- Spots: clear of other pads by the rules' clearance, of large courtyards and of
  neighbouring escapes and pair insertions, reachable without crossing
  another net. The nudger moves a via only a little; compute the spot.
  `force=True` on a pad whose via definition has no via-in-pad gives a
  blocked route.

Check: `layout_checks.py` `vias` is `met`.

## Placement

- Dense, top layer first; no overlapping courtyards or pads; nothing past
  the board edge unless the user or the design says so.
- Order. Board-wide: mechanically fixed parts first (connectors,
  mounting, anything the user placed). Then, within each block, its IC:
  compare the four rotations from pad coordinates and keep the one that
  faces its pins toward what they connect to, with room on each side for
  that side's parts. Then the block's other parts by how little distance
  each connection tolerates: a switching loop, `ShortTrace` pairs and
  vendor-fixed positions; decoupling and filter capacitors, each at its
  own pin; crystals and their load capacitors; bulk capacitors, series
  resistors and pull-ups; then whatever tolerates distance.
- When two parts want the same spot at a pin, the one later in that
  order moves. When a part and an escaping trace want it, the trace
  gives way: it can bend, change layer or leave by another edge.
- Leave escape room for every signal leaving a circuit.
- Each passive goes where every connection it has can route close to its
  pad-to-pad distance, pads facing the pins they serve: an LED's resistor
  between the LED and its driver, a decoupling capacitor against its pins.
- Check: `circuitousness`, nothing over 1.5 outside `si_nets`. For each
  connection over, in order: a stale detour (delete, sync, reroute); a
  part turned so a pad faces away (rotate or mirror it); the part in the
  wrong place (move it).

`scripts/layout_placement.py` works these out from `state.json` before
anything is routed. It runs with the project's Python, needs no session
and sends nothing: it prints spots and gaps, you send `rd.layout.place`.
Run `layout_report.py` again after a batch of placements, since it reads
the last report. Name the ground nets with `--ground` when they are not
`GND`: every gap is measured between signal pads, and it stops on a
name no pad carries. Its docstring has every option.

- `sides <ic>`: the IC's pads by package side, the four rotations with
  how many pins face the larger parts on their nets, and on each side
  the room against the courtyards of the small parts that side's nets
  need. Use it for the rotation, before the block's other parts.
- `search --part <part> --pin <ic>:<pad>`: the legal spots nearest a pin
  (courtyard and pads inside the board, overlapping no other part's, pad
  copper `--clear` from other parts' pads), at four rotations, as x, y
  and rotation. `--conflicts` adds spots that
  overlap other parts and names them, so you know what to move;
  `--track` and `--clear` rank last the spots that close a pin's last
  escape channel.
- `group --assign <part>=<ic>:<pad> ...`: parts that compete for the same
  pins, tried in up to six orders (one led by each part when there are
  more), each part taking its best spot given the ones before it; pass `--clear`
  as for `search`.
- `audit --ic <the block's ICs>`: for each IC, the gap from each pin to
  the nearest small part on its net, parts turned away from the pin they
  serve, and, with
  `--track` and `--clear`, pins with no escape; for each block, the box
  around its courtyards over their sum, to hold against the floorplan's
  allowance; for the board, each pair of parts whose courtyards or pads
  overlap. Run it on each block before `layout_checks.py`.

Courtyards are boxes here, so a turned part can be listed against a
neighbour it clears: `sanity` in `layout_checks.py` compares the real
shapes and still decides overlaps.

## Decoupling

- The loop from the IC's power pin through the capacitor to its ground pin
  is as small as you can make it: same side as the IC, against the pin
  pair, pads facing their pins, short wide connections. On a switching
  regulator the hot-loop capacitors (a buck's input, a boost's output) are
  the decoupling; join them to the IC with pours where they can be built.
- Each capacitor pad whose net has a plane has a plane via of its own
  (bulk capacitors more than one), beside the pad, the two pads' vias on
  the same side of the part, not past the ends: a via past the end
  lengthens the loop for nothing. A pad whose net has no plane reaches its
  pin through a pour or the shortest trace on its own layer.
- Checks: `loops` area per input or decoupling capacitor at or under a
  target the user states or you state with your reason (output loops
  through an inductor are not measured; leave output capacitors out of
  `loops`); `decap_vias` `met`. It lists every two-pad capacitor with a
  surface pad over a plane of its net, and fails a pad with no via to
  that plane. A capacitor modelled as its own component (no
  `capacitance`), or with more than two pads, is not listed: read those
  off the board.

## Pours

- A pour joins nearby same-net pads with less resistance and inductance
  than traces. Use one where that matters (a switching loop, a supply
  rail, a high-current path) and its fill stays one piece.
- Build a pour from the pads it joins, not a drawn outline:
  `region(Pour(ConvexHull([pads, vias, route_points], expand=0.3), layer,
  rank=), net=)`. The hull follows its anchors when a part moves. Send
  anchor vias in an earlier batch. Draw an outline only for a plane, or
  for a shape no hull gives.
- Hulls of different nets overlap where their parts interleave, so set
  each pour's `rank` before sending: same-rank overlaps subtract; a
  higher rank cuts lower pours away from nearby pads (stitch those pads).
  Rank highest the pour that must keep its pads, such as a supply at an
  IC's pins over the switch node beside them.
- Other nets' copper inside a hull can split it: a crossing trace always,
  pads and vias when their clearance holes meet. Keep the hull to what it
  joins; keep traces out with a route-only keepout
  (`KeepOut(shape, LayerSet(layer), route=True, via=False, pour=False)`)
  or route them first through known gaps.
- A design `thermal_relief` rule joins pads through spokes; a region
  request has no setting for the joint. A solid joint is a rule change in
  the source (`jitx-layout-constraints`).
- Check: `fill_pieces` 1 for each pour, every batch, and after a new
  pour or a rank change, that each pour it overlaps still reaches its
  pads (`connectivity`, `power_paths`).

## Power paths

- Supply rails and high-current paths are pours or planes for their whole
  length: a regulator's input path (connector through input capacitors to
  the IC), each rail from its source to every load, a power stage's supply
  and its output to the load. A trace carries power only as a pad's entry
  or on a low-current branch (a sense line, a pull-up, a bias, an
  indicator). A branch needs no pour: route it as a trace.
- Power or ground that leaves TOP reaches its load through a
  plane or a pour on another layer, by vias at the pads, not a thin inner
  trace.
- Route a power device's current-carrying pins at the power rule's width,
  the direct way, or by vias straight to the plane.
- Checks: a `power_paths` entry per source-to-load path with its current
  and drop and inductance budgets (from the user, or stated with your
  reason), `met`, reporting `ir.r_mohm`, `ir.drop_mv` and `ir.l_nh`; and
  `power.nets.<net>.met` for each power net (a step-down leg into a pad
  narrower than the rule, within `neck_down_mm`, is allowed; thermal
  spokes never count). A path with a trace leg is not `met`. A
  low-current branch is not a power path: name the part it serves in
  `power_branches`, as `{"<net>": {"<component or pad key>": "<reason>"}}`,
  and its thin traces stop failing `power.nets`. A thin trace that also
  feeds an unnamed part still fails, and so does one between two pads a
  pour already joins (delete it); a bad name is listed in `power.errors`
  and excuses nothing. Report each branch with its reason.
  `"require_pour": false` is only for
  a branch listed as a path because it has a drop budget. A step-down leg
  on a path is excused only when the path's net is in `power`. With no
  budget, `met` says only that the path has no trace leg.
- These are estimates (DC at 20 C; return in the nearest plane; no mutual
  inductance, capacitor ESL or package inductance): compare layouts with
  them and say so. A plane path costs about 40 s per solve on an 18-layer
  board, two solves per path: run them at milestones, and between them use
  `"grid_mm": 0.1` (about nine times faster, within 4%, but diagonal traces
  up to 13% high and spokes or gaps under 0.2 mm up to a third low). When
  `ir.reasons` is present, that budget has no verdict.

## Routing

1. Tight connections: decoupling, bootstrap, switch node, pair escapes.
2. Plane vias, then the pours they anchor.
3. Placement review. With every part placed and every block checked, and
   before any route between blocks, report the layer plan, the board's
   size with the share of it the courtyards cover (`audit`), and what the
   checks say, so the user can look at the board. Stop for an answer only
   if the user, or the caller that delegated the layout, asked to review
   the placement; otherwise go on. A caller delegating a whole board asks
   for that stop and shows the user the placement: routing between blocks
   on a placement the user then rejects is wasted. The run after a review
   keeps the placement on the board, follows `SKILL.md` Edit if the user
   changed it, and goes on from item 4.
4. Between blocks, then the rest, in batches, to the via plan.

- Send each via before long routes pass its spot.
- Sketch short constrained routes with `turns`; the autorouter may detour.
- A blocked route is a placement or plan signal: move, reorder or sketch.
  Never resend it unchanged.
- The router picks each route's angles. Never redraw routes or add control
  points to make them 45/90 unless the user asks.
- Leave `width` and `space` to the rules, except at a fine-pitch pad
  narrower than the rule's width across the entry direction: a rule-width
  route there can come back with less than the clearance, unreported by
  `rd.issues()`. Narrow the leg that ends at the pad to the pad's width
  (`width=` on that `route`, on a `via` request's pad stub, or on the last
  leg after a `route_point`), and on a power net keep it within
  `neck_down_mm`.
- A route can keep a stale detour after its parts move: delete, sync,
  reroute. A via moves with the pad it was routed from.
