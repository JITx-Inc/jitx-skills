# Net-to-net clearance reference notes

## Result

The 0.25 mm request is not honored and not reported: with the two tagged nets
authored 0.100 mm apart edge to edge, the realized top-layer copper measures
0.1001 mm, and `jitx build` returns `status: ok`.

For the below-floor request neither side wins. Authored 0.020 mm apart, the
realized copper measures 0.0202 mm, under both the 0.05 mm rule and the 0.09 mm
JLCPCB floor (`jitxlib/jlcpcb/rules.py:9`), and that build is also `status: ok`.

The tags themselves resolve: the priority-1 tagged width rule reaches the same
copper (0.2000 mm measured on both nets against a 0.20 mm request). It is the
`BinaryDesignConstraint(PowerTag(), GroundTag()).clearance(...)` rule that moves
nothing. On this runtime realized clearance equals whatever the code authored.

Measured with py-jitx 4.4.0rc5.dev2, runtime 4.4.0-rc.9, substrate
`JLC04161H_7628`.

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

## Commands and real output

Run from the project root. The project holds the two reference directories as
packages plus `scripts/layout_checks.py`; the interpreter is the project venv.
The websocket port and session id in the runtime line are normalized, since
customer-shipped files cannot carry machine-specific values.

```text
$ jitx runtime start --background
Runtime: reachable at ws://localhost:<port>/<session>

$ jitx find
designs:
  layout_constraints_wp5.default_rules.design.DefaultRulesDesign
  layout_constraints_wp5.net_net_clearance.design.BelowFloorClearanceDesign
  layout_constraints_wp5.net_net_clearance.design.NetNetClearanceDesign
  layout_constraints_wp5.net_net_clearance.design._ClearanceDesign

$ jitx build layout_constraints_wp5.net_net_clearance.design.NetNetClearanceDesign
Running design layout_constraints_wp5.net_net_clearance.design.NetNetClearanceDesign...
Saving stable design and reference designator table
layout_constraints_wp5.net_net_clearance.design.NetNetClearanceDesign:
  design: layout_constraints_wp5.net_net_clearance.design.NetNetClearanceDesign
  status: ok

$ jitx build layout_constraints_wp5.net_net_clearance.design.BelowFloorClearanceDesign
Running design layout_constraints_wp5.net_net_clearance.design.BelowFloorClearanceDesign...
Saving stable design and reference designator table
layout_constraints_wp5.net_net_clearance.design.BelowFloorClearanceDesign:
  design: layout_constraints_wp5.net_net_clearance.design.BelowFloorClearanceDesign
  status: ok

$ python3 -m layout_constraints_wp5.net_net_clearance.check
no computed net for port in component circuit.power_pad: unused
no computed net for port in component circuit.ground_pad: unused
no computed net for port in component circuit.power_pad: unused
no computed net for port in component circuit.ground_pad: unused
example clearance, source: skill example above fabrication floor
PASS routes: measured=0 expected=0 checked=2 unrealized=0
PASS width: measured=0.2000 expected=0.2000 net=POWER layer=0 tol=0.0010 mm
PASS width: measured=0.2000 expected=0.2000 net=GROUND layer=0 tol=0.0010 mm
FAIL clearance: measured=0.1001 expected=0.2500 nets=POWER,GROUND layer=0
summary: checks=4 failures=1
below-floor request, source: skill test value 0.0500 mm; fabrication floor read from FabricationConstraints.min_copper_copper_space
PASS routes: measured=0 expected=0 checked=2 unrealized=0
PASS width: measured=0.2000 expected=0.2000 net=POWER layer=0 tol=0.0010 mm
PASS width: measured=0.2000 expected=0.2000 net=GROUND layer=0 tol=0.0010 mm
FAIL clearance: measured=0.0202 expected=0.0500 nets=POWER,GROUND layer=0
FAIL below-floor-classification: measured=0.0202 expected=0.0500 observed=neither the rule nor the floor; authored geometry; fabrication floor=0.0900 mm
summary: checks=5 failures=2
exit=1
```

The two `clearance` FAIL lines and the classification FAIL are the finding, not a
defect in the probe. The script exits 1 because the realized copper does not meet
the requested clearance, which is exactly what the question asked.

The `no computed net for port` lines come from the `unused` port on each
`ProbeTerminal`, which is `no_connect()`ed. They are informational.

## Route sketch turns are inert on this runtime

The original probe put the convergence in a `Route(..., sketch=[...])` turn list.
That does not work here: the runtime returns a straight two-point polyline
between the route endpoints and discards the intermediate turns. Four side-probe
cases in the same project, one net, one route, no obstacle between the endpoints:

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

The turns are serialized and sent (`jitx/_translate/circuit.py:842`), so the drop
happens runtime-side. The claim is scoped to what was observed: a two-endpoint
route with nothing in the way. A sketch may still matter where the direct path is
blocked.

The consequence for the original probe was a silent vacuous pass. Its sketch
start point `(-8.0, 1.50)` was also not the pad center: the `SMT("0402")`
landpattern stacks its two pads along Y, so `route_pad` (pad 1) sits at
`(-8.0, 2.0099)`. Both routes therefore realized as straight diagonals to
`(8.0, +/-1.50)`, and the smallest `POWER` to `GROUND` distance was the 2.5197 mm
between the two route pads, not trace to trace. Every clearance check passed
without the two nets ever coming near the rule.

## Fixes made

1. `net-net-clearance/design.py`, `ParallelRoutes`: convergence moved out of the
   sketch and into the endpoints. The class attribute `middle_offset` (0.10 mm,
   overridden to 0.03 mm) became `authored_gap` (0.10 mm, overridden to 0.02 mm)
   and now means the authored edge-to-edge gap; the two `RoutePoint`s moved from
   `(right_x, +/-endpoint_offset)` to `(right_x, +/-(authored_gap + 0.20)/2)`;
   both `sketch=` arguments and the now-unused `turn_x` local were removed. The
   pads, nets, tags, board, substrate, and the five rules are unchanged.

2. `net-net-clearance/check.py`: the below-floor classification had only two
   branches, so a measurement below both the rule and the floor was labelled
   `observed=below-floor rule`, a claim the copper does not support. Added a
   third branch, `neither the rule nor the floor; authored geometry`. The
   `CheckResult` fields, the check name, and the exit convention are unchanged.

No change was needed in `scripts/layout_checks.py`. Its pad-transform
composition was verified against hand arithmetic on the original geometry: pad
centers at y = 2.0099 and y = -0.9901 with 0.4803 mm tall pads give a 2.5197 mm
gap, which is what the adapter reported. Its own unit tests pass:

```text
$ python3 -m pytest scripts/test_layout_checks.py -q
8 passed in 0.04s
```

## Limits found and not fixed

`_ClearanceDesign`, the private base class, is discovered by `jitx find` and
cannot be instantiated, so `jitx build-all` in a project holding this case
reports an error:

```text
$ jitx build layout_constraints_wp5.net_net_clearance.design._ClearanceDesign
layout_constraints_wp5.net_net_clearance.design._ClearanceDesign:
  design: layout_constraints_wp5.net_net_clearance.design._ClearanceDesign
  errors:
    instantiation failed:
      '_ClearanceDesign' object has no attribute 'requested_clearance' at net_net_clearance/design.py:136
```

Fixing that means changing how the two variants share a base, which is a design
decision rather than a minimal repair, so it was left alone.

## Pour limit

A captured `Pour` on this JITX line returns its input outline before voiding, so
the capture clearance check uses trace-to-trace copper and excludes pours. That
also means there is no engine-computed copper in this probe on which a clearance
rule could have been caught being enforced. The legacy ODB++ cross-check was not
run.

## Rerun after check rewrite

The `check.py` above now asserts the observed behavior rather than the request,
so it exits 0 while the runtime leaves code-authored routes where the code put
them. Rerun on py-jitx 4.4.0rc5.dev2, runtime 4.4.0-rc.9, substrate
`JLC04161H_7628`, from the project root with the project venv interpreter. The
"Commands and real output" block above records the pre-rewrite script, which
exited 1 on the same measurements.

```text
$ python3 -m layout_constraints_wp5.net_net_clearance.check
example rule, source: skill example above the fabrication floor
PASS routes: measured=0 expected=0 checked=2 unrealized=0
PASS width: measured=0.2000 expected=0.2000 net=POWER layer=0 tol=0.0010 mm
PASS width: measured=0.2000 expected=0.2000 net=GROUND layer=0 tol=0.0010 mm
PASS example: realized clearance equals authored gap: measured=0.1001 expected=0.1000 rule asked 0.2500 mm; code authored 0.1000 mm
PASS example: clearance rule not applied to authored routes: measured=0.1001 expected=0.2500 verified behavior on the 4.4 line; a pass here means the rule moved nothing
summary: checks=5 failures=0
below-floor request, source: skill test value 0.0500 mm; fabrication floor 0.0900 mm
PASS routes: measured=0 expected=0 checked=2 unrealized=0
PASS width: measured=0.2000 expected=0.2000 net=POWER layer=0 tol=0.0010 mm
PASS width: measured=0.2000 expected=0.2000 net=GROUND layer=0 tol=0.0010 mm
PASS below-floor: realized clearance equals authored gap: measured=0.0202 expected=0.0200 rule asked 0.0500 mm; code authored 0.0200 mm
PASS below-floor: clearance rule not applied to authored routes: measured=0.0202 expected=0.0500 verified behavior on the 4.4 line; a pass here means the rule moved nothing
PASS below-floor: fabrication floor not enforced on authored routes: measured=0.0202 expected=0.0900 floor read from FabricationConstraints.min_copper_copper_space; a pass means authored copper sits below it with status ok
summary: checks=6 failures=0
```

Exit code: 0.

Trimmed from the verbatim output: four leading `no computed net for port in
component circuit.{power,ground}_pad: unused` lines, the same informational
`no_connect()` noise described above. Nothing else was cut.

The measurements are unchanged from the original run: 0.1001 mm against a
0.25 mm rule on an authored 0.100 mm gap, and 0.0202 mm against a 0.05 mm rule
and a 0.09 mm floor on an authored 0.020 mm gap.

One discovery-side change came with the rewrite: `design.py` now shares the rule
set through `_ClearanceRules`, which is not a `Design` subclass, so `jitx find`
lists only the two concrete designs and the `_ClearanceDesign` build error in
"Limits found and not fixed" no longer occurs.

```text
$ jitx find
designs:
  layout_constraints_wp5.default_rules.design.DefaultRulesDesign
  layout_constraints_wp5.net_net_clearance.design.BelowFloorClearanceDesign
  layout_constraints_wp5.net_net_clearance.design.NetNetClearanceDesign
```
