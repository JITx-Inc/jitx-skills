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
report, but do not narrow it while debugging: unresolved texts also land under
`Topology:` (`No path ... no pin model`, `not routed yet`) and `Routing:`
(`Unable to find path for requested route`). The command exits 0 whatever it finds unless `--error <severity>` is
given. `jitx --format json design issues ...` gives each issue's class, text,
pins and, for a measurement, `detail.signal_integrity` with `measured_range`,
`acceptable_range` and `satisfied`, which a script can check. From Python, the
submitted design returns the same report:
`with jitx.runtime as r:` then `r.submit(MyDesign).issues(satisfied=True, wait=30).text()`.

A second query of a design already submitted, unchanged, has hung on this
runtime for minutes. Restart the project's runtime (`jitx runtime stop`, then
`jitx runtime start --background`) before querying it again.

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
| `Missing Connection on Path: <a>, <b>`, with `Unable to find path for requested route` under Routing | A code route the router cannot make. Observed causes: a part rotated so the routed pad faces away, a part with no `.at(...)` placement, and a via-structure ground cage that closes the via off. | Fix the route or the placement. |
| `Virtual connection without a pin model` | A `VirtualConnection` on the path has no `PinModel`. | Give it a `pin_model=PinModel(delay=..., loss=...)` (`jitx-physical-layout` covers `VirtualConnection`). |
| `Unassigned Pin on Path: <net>` | A `require()`d end whose assignment has not resolved. | Code routes on the provider's physical pins that match an offered mapping. |
| `Code route dropped: it conflicts with other connections` | A route that matches no offered pin mapping. | Route to a legal mapping. |
| `Overlapping routing structures along path from <a> to <b>` | Two constraints put a structure on a shared segment of a chain. | Apply the structure once, over the longest path. |

## Verification design and assembly

Proof routes fix one placement and, on a pin-assigned port, one pin mapping, so
they go in a code-routed verification design, one per module that carries SI
constraints, and not in the shipping assembly. The verification design places
the parts, code-routes every constrained path between physical pads (on a
pin-assigned port, the provider's physical pins), and passes when each
constraint has a measured line with the intended ends and none of the
unresolved texts above.

Run the command on the assembly too, and disposition each SI line. While the
assembly is unrouted, these are expected and recorded: `Unconnected Topology`,
`not routed yet`, `No path for signal constraint` with no part named, and
`Unassigned Pin` on pin-assigned ends. These block even unrouted: `No path ...
which has no pin model`, `Virtual connection without a pin model`, and a
constraint that is absent from the report. `Missing routing structure` and the
placeholder via model appear only beside a measurement, so an unrouted
assembly cannot show them; check them on the verification design and on the
routed assembly. Once the assembly is routed, it is held to the
verification-design bar: every constraint measures between its intended ends,
with none of the unresolved texts above.

Parity: the assembly applies the same constraint class and parameters as its
verification design, routing structure included, through the same pin models.
The evidence on the verification side is its measured lines; on the assembly
side it is the same Topology ends and pin models in code, plus, while unrouted,
the `Unconnected Topology on Path:` segment list, which names each segment
between bridged parts. The physical ends must match (the dotted prefix
changes with the hierarchy); any other difference returns the assembly for
rework unless it is named with its reason.
