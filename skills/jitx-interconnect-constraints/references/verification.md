# Proving SI Constraints with Design Issues

This reference owns the proof that a signal constraint applied, and the debug
path when it did not. `jitx-layout-constraints` checks rule effects on copper,
and `jitx-physical-layout` owns physical-layout verification. Observations
below are from jitx 4.6.0rc10 with runtime 4.6.0-rc.16.

## The command

```bash
jitx runtime start --background          # once per project, if none is running
jitx design issues <module.path.DesignClass> --satisfied --wait 30
```

`--satisfied` is required: without it the report lists only what is wrong, and
a met constraint does not appear, so `No design issues.` is the same report a
never-applied constraint gives. `--wait` gives background tasks time to finish
before the snapshot (default 5 s). `--category signal_constraint` narrows the
report. `jitx --format json design issues ...` gives each issue's class, text,
pins and, for a measurement, `detail.signal_integrity` with `measured_range`,
`acceptable_range` and `satisfied`, which a script can check. From Python, the
submitted design's `issues(satisfied=True)` returns the same report.

`status: ok`, a clean type check, and the existence of a harness are not
evidence that a constraint applied.

## What applied looks like

A constraint applied when a measured line appears for it, naming the intended
ends:

```text
Signal Constraint:
  - Time: 211.953ps - Target: 200ps ± 200ps from bga.tx0.p to conn.tx0.p
  - Loss: 0.907db ± 0db - Target: 1db ± 1db from bga.tx0.p to conn.tx0.p
  - Skew: 0fs - Target: ± 1ps (longer from bga.tx0.p to conn.tx0.p, shorter from bga.tx0.n to conn.tx0.n)
```

- `timing` gives a `Time` line per path, `insertion_loss` a `Loss` line per
  path, `ConstrainDiffPair(...).timing_difference` a `Skew` line per pair, and
  `ConstrainReferenceDifference` a `Skew` line per compared signal (one per leg
  when a single-pin guide is compared against a pair).
- The target is a window, center and half-width: `timing(400e-12)` reads
  `200ps ± 200ps`, anything from 0 to 400 ps.
- Check the `from ... to ...` ends. A measurement between an intermediate pad
  and an end, or between pads inside a sub-circuit, covers a shorter span than
  intended.
- A `Constrain` that carries only `.structure(...)` produces no line, so the
  report cannot confirm it applied.

Binding and compliance are separate claims. Binding: the measurement exists.
Compliance: the measured value lies inside its target. A violated constraint
prints the same kind of line, with or without `--satisfied`; report it as a
violation.

## What unresolved looks like

Any of these in a constraint's group means the measurement is missing or is
not the design's number. Fix the cause and re-run; do not claim the constraint.

| Report text | Cause | Fix |
|---|---|---|
| `Unconnected Topology on Path: <a>, <b>` | The segment between `a` and `b` has no route. | Route it in the board view or with a code `Route`. |
| `Signal path from <a> to <b> is not routed yet` | The two pads share a net with no route joining them. | Same. |
| `No path for signal constraint from <a> to <b>: the ends are only connected through the part between <x> and <y>, which has no pin model.` | A pass-through part has no `BridgingPinModel`. | Add one between `x` and `y`, with values from its datasheet or the user. |
| `No path for signal constraint ...` with no part named | Seen when an unrouted net crosses a circuit's bundle port, and when an assignment around fixed physical ends is unresolved or illegal. | Route first, then read it again; for pin assignment see `jitx-pin-assignment`. |
| `Missing routing structure on Path: <a>, <b>` (beside a measurement) | The constraint has no `.structure(...)`, so the measured delay and loss are not the structure's. | Add the routing structure. |
| `Structure model from [i] to [j] not found in "<Via>". Using placeholder model ...` | A via on the path has no `models` entry for that layer pair. The measurement uses a placeholder (20 ps and 0.15 dB on one observed run; not a documented default). | Give the via class a `models` entry from its data. |
| `Missing Connection on Path: <a>, <b>`, with `Unable to find path for requested route` under Routing | A code route the router cannot make, for example to a part rotated so the routed pad faces away, or to a part inside a sub-circuit that has no placement. | Fix the route or the placement. |
| `Unassigned Pin on Path: <net>` | A `require()`d end whose assignment has not resolved. | Code routes on the provider's physical pins that match an offered mapping. |
| `Code route dropped: it conflicts with other connections` | A route that matches no offered pin mapping. | Route to a legal mapping. |
| `Overlapping routing structures along path from <a> to <b>` | Two constraints put a structure on a shared segment of a chain. | Apply the structure once, over the longest path. |

## Harness and assembly parity

When a constraint is proved in a module harness and again in the assembled
board, run the command on both designs and compare the measured lines: the same
constraint must measure in both, between the same physical ends (the dotted
prefix changes with the hierarchy), through the same parts. A measurement in the
harness only, or ends that differ, returns the assembly for rework unless the
difference is named with its reason.
