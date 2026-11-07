# General place and route

What a good layout looks like, and the check for each. Router behaviour
noted here depends on the design: confirm it with a read-back.

## Plan from the source

- Read topology chains (`TopologyNet`, `>>`), `ShortTrace` pairs, power
  nets and widths, high-speed nets and local circuits from the source.
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
- Place, route and check one block at a time (`layout_checks.py` with
  `scope` set to the block). A later block does not move an earlier
  block's parts; resize the floorplan and rerun instead.

## Via plan

Before routing, give every connection a layer and its vias, and write the
plan to a file the routing scripts read.

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

- Dense, top layer first; no courtyard overlaps; nothing past the board
  edge unless the user or the design says so.
- Leave escape room for every signal leaving a circuit.
- Each passive goes where every connection it has can route close to its
  pad-to-pad distance, pads facing the pins they serve: an LED's resistor
  between the LED and its driver, a decoupling capacitor against its pins.
- Check: `circuitousness`, nothing over 1.5 outside `si_nets`. For each
  connection over, in order: a stale detour (delete, sync, reroute); a
  part turned so a pad faces away (rotate or mirror it); the part in the
  wrong place (move it).

## Decoupling

- The loop from the IC's power pin through the capacitor to its ground pin
  is as small as you can make it: same side as the IC, against the pin
  pair, pads facing their pins, short wide connections. On a switching
  regulator the hot-loop capacitors (a buck's input, a boost's output) are
  the decoupling; join them to the IC with pours where they can be built.
- Each capacitor has a plane via of its own at each pad (bulk capacitors
  more than one), beside the pads, both on the same side of the part, not
  past the ends: a via past the end lengthens the loop for nothing.
- Checks: `loops` area per input or decoupling capacitor at or under a
  target the user states or you state with your reason (output loops
  through an inductor are not measured; leave output capacitors out of
  `loops`); `decap_vias` `met`.

## Pours

- A pour joins nearby same-net pads with less resistance and inductance
  than traces. Use one where that matters (a switching loop, a regulator's
  current path) and its fill stays one piece.
- Hull pours: `region(Pour(ConvexHull([pads, vias, route_points],
  expand=0.3), layer, rank=), net=)`. Send anchor vias in an earlier
  batch.
- Same-rank overlaps subtract; a higher rank cuts lower pours away from
  nearby pads (stitch those pads).
- Other nets' copper inside a hull can split it: a crossing trace always,
  pads and vias when their clearance holes meet. Keep the hull to what it
  joins; keep traces out with a route-only keepout
  (`KeepOut(shape, LayerSet(layer), route=True, via=False, pour=False)`)
  or route them first through known gaps.
- A design `thermal_relief` rule joins pads through spokes; a region
  request has no setting for the joint. A solid joint is a rule change in
  the source (`jitx-layout-constraints`).
- Check: `fill_pieces` 1 for each pour, every batch.

## Power paths

- A regulator's input path, connector through input capacitors to the IC,
  is a pour. Power or ground that leaves TOP reaches its load through a
  plane or an inner pour, by vias at the pads, not a thin inner trace.
- Route a power device's current-carrying pins at the power rule's width,
  the direct way, or by vias straight to the plane.
- Checks: a `power_paths` entry per source-to-load path with its current
  and drop and inductance budgets (from the user, or stated with your
  reason), `met`, reporting `ir.r_mohm`, `ir.drop_mv` and `ir.l_nh`; and
  `power.nets.<net>.met` for each power net (a step-down leg into a pad
  narrower than the rule, within `neck_down_mm`, is allowed; thermal
  spokes never count).
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
3. The rest, in batches, to the via plan.

- Send each via before long routes pass its spot.
- Sketch short constrained routes with `turns`; the autorouter may detour.
- A blocked route is a placement or plan signal: move, reorder or sketch.
- Leave `width` and `space` to the rules, except at a fine-pitch pad
  narrower than the rule's width across the entry direction: a rule-width
  route there can come back with less than the clearance, unreported by
  `rd.issues()`. Narrow the leg that ends at the pad to the pad's width
  (`width=` on that `route`, on a `via` request's pad stub, or on the last
  leg after a `route_point`), and on a power net keep it within
  `neck_down_mm`.
- A route can keep a stale detour after its parts move: delete, sync,
  reroute. A via moves with the pad it was routed from.
