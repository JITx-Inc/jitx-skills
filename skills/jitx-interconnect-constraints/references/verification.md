# Proving SI Constraints with Design Issues

This reference owns the proof that a signal constraint applied, and the debug
path when it did not. `jitx-layout-constraints` checks rule effects on copper,
and `jitx-physical-layout` owns physical-layout verification. Observations
below are from jitx 4.6.0rc10 with runtime 4.6.0-rc.16.

## The check

Run this as a script from the project root while the project's runtime is
running (`jitx runtime start --background`, once per project):

```python
import jitx

from mypkg.main import MyDesign


def main() -> None:
    with jitx.runtime as rt:
        report = rt.submit(MyDesign).issues(satisfied=True, wait=30)
        if not report.complete:
            print("report incomplete: raise wait and run again")
        for group in report.groups():
            print("met" if group.satisfied else "NOT MET", group.text)
            if len(group.issues) > 1:
                for issue in group:
                    print("   ", issue.text)


if __name__ == "__main__":
    main()
```

`report.groups()` gives one group per check, for example per constraint
path or per skew comparison. `group.satisfied` is that check's verdict and
`group.text` its summary; a group of several issues shows only the first in
its text, so the loop prints each issue. Unresolved texts land in the
signal-constraint, topology and routing groups alike, so read every group
while debugging.

- `satisfied=True` is required: without it a met constraint is left out, and
  an empty report is the same report a never-applied constraint gives.
- `wait=30` gives the runtime's checks time to finish. A category still
  running when the wait ends comes back pending; `report.complete` is true
  only when every category finished, and the script says so when it is not.
- The body sits in `main()` behind the `__name__` guard. JITX design
  discovery (`jitx build` with no design named, `jitx design find`, the design
  picker) imports every `.py` under the project root whose name does not
  start with `_`, so code at module level would submit a design each time.
- `bool(report)` is true when any error-severity issue is present, and
  `report.errors` lists them, for a whole-design pass or fail.
- `report.of(cls)` filters issues by class (`jitx.issue`), but a measurement
  is typed by kind, `UnmetTime`, `UnmetTimeDiff` or `UnmetLoss`, not by
  verdict: `UnmetTime` and `UnmetTimeDiff` were seen on met checks. Take the
  verdict from `group.satisfied`.
- `jitx.run` and `jitx.issue` are marked experimental and may change.

`status: ok`, a clean type check, and the existence of a verification design
are not evidence that a constraint applied.

## What applied looks like

A constraint applied when its group carries a measurement naming the intended
ends. The taught script printed, for a routed differential pair:

```text
met Time: 105.311ps - Target: 500ps ± 500ps from drv.d.p to rcv.d.p
met Time: 105.311ps - Target: 500ps ± 500ps from drv.d.n to rcv.d.n
met Skew: 0s - Target: ± 1ps (longer from drv.d.p to rcv.d.p, shorter from drv.d.n to rcv.d.n)
met Satisfied
```

The last line is the Routing category's group with no issue in it: every
code route was made. It is not a constraint verdict.

- `timing` gives a `Time` measurement per path, `insertion_loss` a `Loss`
  measurement per path, `ConstrainDiffPair(...).timing_difference` a `Skew`
  per pair, and `ConstrainReferenceDifference` a `Skew` per compared signal
  (one per leg when a single-pin guide is compared against a pair).
- The target is a window, center and half-width: `timing(1e-9)` reads
  `500ps ± 500ps`, anything from 0 to 1 ns.
- Check the `from ... to ...` ends. A measurement between an intermediate pad
  and an end, or between pads inside a sub-circuit, covers a shorter span than
  intended.
- A `Constrain` that carries only `.structure(...)` never appears in the
  report, so the report cannot confirm it applied. The verification rule below exempts it and
  takes its code as the evidence.

Binding and compliance are separate claims. Binding: the measurement exists.
Compliance: `group.satisfied`. The text is the same for a met and an unmet
constraint, so never read compliance from it. `ConstrainReferenceDifference(guide,
target).timing_difference(window)` checks guide delay minus target delay
against the window as written, but the printed `Target` drops the sign: a
window of -1000 ps to 0 and one of 0 to 1000 ps both print
`Target: 500ps ± 500ps`. A group that also holds an unresolved text is not met
even when its measurement is in range:

```text
NOT MET 2 issues: Missing routing structure on Path: a.ser.a, b.ser.a
    Missing routing structure on Path: a.ser.a, b.ser.a
    Time: 211.039ps - Target: 500ps ± 500ps from a.chip.o to b.chip.o
```

## What unresolved looks like

Any of these in a constraint's group means the measurement is missing or is
not the design's number. Fix the cause and re-run; do not claim the constraint.

| Report text | Cause | Fix |
|---|---|---|
| `Unconnected Topology on Path: <a>, <b>` | The segment between `a` and `b` has no route. | Route it in the board view or with a code `Route`. |
| `Signal path from <a> to <b> is not routed yet` | The two pads share a net with no route joining them. | Same. |
| `No path for signal constraint from <a> to <b>: the ends are only connected through the part between <x> and <y>, which has no pin model.` | A pass-through part has no `BridgingPinModel`, or a flow-through package's two lands sit on separate nets. | If the part has a path through it between `x` and `y` (series resistor, AC cap, an ESD channel whose datasheet gives an in-to-out path), add a `BridgingPinModel` between them, with values from its datasheet or the user. If `y` is a pin that is not connected inside the package (a flow-through ESD part whose trace runs under it), add no model: put `x` and `y` on one net, joined by board copper; a model there would hide an open line. |
| `No path for signal constraint ...` with no part named | Seen when an unrouted net crosses a circuit's bundle port; when an assignment around fixed physical ends is unresolved or illegal; and, even on a routed path, when an end is a circuit port that reaches more than one pad, so no single pad stands in for it. | Route first, then read it again. If it stays on a routed path, check each end: rename a circuit-port end that reaches several pads to the chip pad you mean. For pin assignment see `jitx-pin-assignment`. |
| `Missing routing structure on Path: <a>, <b>` (beside a measurement) | Either the constraint has no `.structure(...)`, so the measured delay and loss are not the structure's; or the ends are chip pads behind series parts in sub-circuits and the segment named runs between those series parts on a net that also holds the sub-circuit ports, which the constraint's structure does not reach (jitx 4.6.0rc10, runtime 4.6.0-rc.16). | Add the routing structure. For the second cause, on a single-ended net, add a structure-only constraint across the sub-circuit ports, such as `Constrain(Topology(self.a.p, self.b.p)).structure(rs50)`; it cleared the line, and the chip-to-chip Time dropped from 211.039 ps to 182.253 or 184.468 ps across runs. Not tried on a diff pair. |
| `Structure model from [i] to [j] not found in "<Via>". Using placeholder model ...` | A via on the path has no `models` entry for that layer pair. The measurement uses a placeholder (20 ps and 0.15 dB on one observed run; not a documented default). | Give the via class a `models` entry from its data. |
| `Missing Connection on Path: <a>, <b>`, with `Unable to find path for requested route` under Routing | A code route the router cannot make. Observed causes: a part rotated so the routed pad faces away, a part with no `.at(...)` placement, and a via-structure ground cage that closes the via off. | Fix the route or the placement. |
| `Virtual connection without a pin model` | A `VirtualConnection` on the path has no `PinModel`. | Give it a `pin_model=PinModel(delay=..., loss=...)` (`jitx-physical-layout` covers `VirtualConnection`). |
| `Unassigned Pin on Path: <net>` | A `require()`d end whose assignment has not resolved. | Code routes on the provider's physical pins that match an offered mapping. |
| `Code route dropped: it conflicts with other connections` | A route that matches no offered pin mapping. | Route to a legal mapping. |
| `Overlapping routing structures along path from <a> to <b>` | Two constraints put a structure on a shared segment of a chain. | Apply the structure once, over the longest path. |
| `Ambiguous routing structures meet at <pad> (2 alternatives)` | Seen beside the overlap text on a code-routed `>>` chain, at the pad where the two structured segments meet. | Same. |

## Verification design and assembly

Proof routes fix one placement and, on a pin-assigned port, one pin mapping, so
they go in a code-routed verification design, one per constrained interface
(the constrained paths between the same modules, with every constraint on them), and
not in the shipping assembly. The verification design places
the parts and code-routes every constrained path between physical pads (on a
pin-assigned port, the provider's physical pins). It passes when every
constraint with a timing, loss or skew target shows a Time, Loss or Skew
measurement from its intended begin pad to its intended end pad, and no group
for it holds any of the unresolved texts above.

A constraint that carries only `.structure(...)`, with no timing, loss or skew
target, never appears in the report, satisfied or not. It is exempt from the
measured-line rule and from the absent-from-report rule; its evidence is the
constraint in code (class, Topology ends, structure), recorded in the parity
evidence.

Run the check on the assembly too, and sort each SI group by whether its
constraint's path has copper yet:

- No route on the path: `Unconnected Topology`, `not routed yet`, `No path for
  signal constraint` with no part named, and `Unassigned Pin` on a pin-assigned
  end are expected and recorded.
- Any route on the path: the constraint is held to the verification-design
  bar, a measurement between its intended ends with none of the unresolved
  texts above, `Missing routing structure` and a placeholder via model
  included. Those two appear only beside a measurement, so they are checked on
  the verification design and on routed paths.
- Blocking wherever it appears: `No path for signal constraint ... which has no
  pin model`, `Virtual connection without a pin model`, and a constraint with a
  timing, loss or skew target that is absent from the report.

Compliance is read from the routed assembly's own groups (`group.satisfied`).
A verification design's values are proof-route numbers, not the board's.

Parity compares constraint class, parameters, routing structure, Topology ends
and pin models between the verification design and the assembly. The
verification side's evidence is its measurements (for a structure-only
constraint, its code). The assembly side's is its constraint code, plus the
`Unconnected Topology on Path:` segment list where the report gives one; a
pin-assigned end reports `Unassigned Pin`, and an unrouted plain chain may
report `not routed yet` or a bare `No path`, and then the code comparison
stands alone. Topology ends compare by physical pad (the dotted prefix changes
with the hierarchy). A missing comparison or a mismatch returns the assembly
to rework.
