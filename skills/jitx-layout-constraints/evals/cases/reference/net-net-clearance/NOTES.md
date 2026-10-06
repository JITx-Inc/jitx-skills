# Net-to-net clearance reference notes

## Result

The 0.25 mm request is not honored and not reported: with the two tagged nets
authored 0.100 mm apart edge to edge, the realized top-layer copper measures
0.1001 mm, and `jitx build` returns `status: ok`.

For the below-floor request neither side wins. Authored 0.020 mm apart, the
realized copper measures 0.0202 mm, under both the 0.05 mm rule and the 0.09 mm
JLCPCB floor (`JLCPCBRules.min_copper_copper_space`), and that build is also
`status: ok`.

The tags themselves resolve: the priority-1 tagged width rule reaches the same
copper (0.2000 mm measured on both nets against a 0.20 mm request). It is the
`BinaryDesignConstraint(PowerTag(), GroundTag()).clearance(...)` rule that moves
nothing. Realized clearance equals whatever the code authored.

## What the probe measures

Two pad-to-point routes on `POWER` and `GROUND`, tagged `PowerTag` and
`GroundTag`, converging at their right-hand ends on the top conductor. The
convergence is authored into the `RoutePoint` coordinates: for a requested edge
gap `g` between two 0.20 mm traces the two points sit at `y = +/-(g + 0.20)/2`,
so the authored copper is deliberately tighter than the rule. If the engine
enforced the rule the realized copper would have to be at least the requested
clearance apart. It is not.

Each measurement runs under 0.001 mm above what was authored (0.1001 mm reported
for an authored 0.100 mm, 0.0202 mm for an authored 0.020 mm). That is consistent
with the polygon approximation of the stroked `ArcPolyline`, the same class of
artifact `geometry-verification.md` records for circle bounding boxes. It is far
too small to be a rule effect: the rules asked for 0.25 mm and 0.05 mm.

## Discovery

`_ClearanceRules` shares the rule set and is not a `Design` subclass, so
`jitx find` lists only the two concrete designs:

```text
$ jitx find
designs:
  <project>.default_rules.design.DefaultRulesDesign
  <project>.net_net_clearance.design.BelowFloorClearanceDesign
  <project>.net_net_clearance.design.NetNetClearanceDesign
```

## Route sketch turns are inert

The runtime returns a straight two-point polyline between the route endpoints
and discards the intermediate turns of a `Route(..., sketch=[...])` turn list.
Four side-probe cases in the same project, one net, one route, no obstacle
between the endpoints:

```text
S_none: authored_sketch=None
    realized=[[(-8.0, 0.0), (8.0, 0.0)]]
S_direct: authored_sketch=[(-8.0, 0.0), (8.0, 0.0)]
    realized=[[(-8.0, 0.0), (8.0, 0.0)]]
S_orthogonal_detour: authored_sketch=[(-8.0, 0.0), (-8.0, 4.0), (8.0, 4.0), (8.0, 0.0)]
    realized=[[(-8.0, 0.0), (8.0, 0.0)]]
S_single_diagonal_turn: authored_sketch=[(-8.0, 0.0), (0.0, 4.0), (8.0, 0.0)]
    realized=[[(-8.0, 0.0), (8.0, 0.0)]]
```

The turns are serialized and sent, so the drop happens runtime-side. The claim
is scoped to what was observed: a two-endpoint route with nothing in the way. A
sketch may still matter where the direct path is blocked.

A probe that puts the convergence in sketch turns passes vacuously. With a
sketch start point of `(-8.0, 1.50)`, which is not the pad center (the
`SMT("0402")` landpattern stacks its two pads along Y, so `route_pad` (pad 1)
sits at `(-8.0, 2.0099)`), both routes realized as straight diagonals to
`(8.0, +/-1.50)`, and the smallest `POWER` to `GROUND` distance was the 2.5197 mm
between the two route pads, not trace to trace. Every clearance check passed
without the two nets ever coming near the rule.

## Pour limit

A captured `Pour` returned its input outline before voiding, so the capture
clearance check uses trace-to-trace copper and excludes pours. That also means
there is no engine-computed copper in this probe on which a clearance rule could
have been caught being enforced. The legacy ODB++ cross-check was not run.
