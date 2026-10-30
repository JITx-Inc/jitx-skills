# Proving SI Constraints with Design Issues

The proof that a signal constraint applied, and the debug path when it did
not. Observed on jitx 4.6.0rc10 with runtime 4.6.0-rc.16.

## The check

The script is in the skill's [Verification](../SKILL.md#verification), step 2:
`rt.submit(MyDesign).issues(satisfied=True, wait=30)`, run from the project
root while the project's runtime is running.

- `report.groups()` gives one group per check (a constraint path, a skew
  comparison). `group.satisfied` is its verdict; `group.text` shows only the
  first issue of a group of several, so iterate the group (`for issue in
  group: issue.text`). Unresolved texts land in signal-constraint, topology
  and routing groups alike: read every group.
- `satisfied=True` is required: without it a met constraint is left out, and
  the empty report matches a never-applied constraint's.
- `wait=30` lets the checks finish; a category still running comes back
  pending, and `report.complete` is true only when every category finished.
- The body sits in `main()` behind the `__name__` guard: design discovery
  imports every `.py` under the project root not starting with `_`.
- `bool(report)` is true when any error-severity issue is present;
  `report.errors` lists them.
- `report.of(cls)` filters by issue class (`jitx.issue`), which names the
  kind (`UnmetTime`, `UnmetLoss`), not the verdict.
- `jitx.run` and `jitx.issue` are marked experimental and may change.

## What applied looks like

A group carries a measurement naming the intended ends, such as
`met Time: 105.311ps - Target: 500ps ± 500ps from drv.d.p to rcv.d.p`. A
trailing `met Satisfied` is the Routing category's empty group (every code
route was made), not a constraint verdict. `timing` gives a `Time` per path,
`insertion_loss` a `Loss` per path, `ConstrainDiffPair(...).timing_difference`
a `Skew` per pair, and `ConstrainReferenceDifference` a `Skew` per compared
signal (per leg against a pair). The target is a window, center and
half-width: `timing(1e-9)` reads `500ps ± 500ps`.

Binding (the measurement exists) and compliance (`group.satisfied`) are
separate; the text reads the same met or unmet, and a reference-difference
`Target` drops the window's sign. A group that also holds an unresolved text
is not met even with its measurement in range:

```text
NOT MET 2 issues: Missing routing structure on Path: a.ser.a, b.ser.a
    Missing routing structure on Path: a.ser.a, b.ser.a
    Time: 211.039ps - Target: 500ps ± 500ps from a.chip.o to b.chip.o
```

## What unresolved looks like

Each means the measurement is missing or not the design's: fix the cause and
re-run.

| Report text | Cause and fix |
|---|---|
| `Unconnected Topology on Path: <a>, <b>` | The segment has no route (board view or code `Route`). |
| `Signal path from <a> to <b> is not routed yet` | The pads share a net with no route joining them. Route it. |
| `No path for signal constraint ... the part between <x> and <y>, which has no pin model.` | A part with a path through it: a `BridgingPinModel` from its datasheet or the user. A flow-through package whose `y` is not connected inside: no model; `x` and `y` on one net, joined by board copper. |
| `No path for signal constraint ...`, no part named | An unrouted net crossing a circuit's bundle port (route, then reread); an unresolved or illegal assignment around fixed physical ends; or, even routed, a circuit-port end reaching several pads (name the chip pad). |
| `Missing routing structure on Path: <a>, <b>` (beside a measurement) | No `.structure(...)`: add it. Or, behind series parts in sub-circuits, the segment's net holds the sub-circuit ports: on a single-ended net, add a structure-only constraint across the ports (untried on a diff pair; [measured case](https://docs.jitx.com/en/latest/essentials/SI/constraints.html#ends-inside-sub-circuits)). |
| `Structure model from [i] to [j] not found in "<Via>". Using placeholder model ...` | The via has no `models` entry for that layer pair. Add one from its data. |
| `Missing Connection on Path: <a>, <b>`, with `Unable to find path for requested route` | A code route the router cannot make: a pad facing away after rotation, a part with no `.at(...)`, a via-structure cage closing the via off. Fix the route or placement. |
| `Virtual connection without a pin model` | Give the `VirtualConnection` `pin_model=PinModel(delay=..., loss=...)` (`jitx-physical-layout`). |
| `Unassigned Pin on Path: <net>` | A `require()`d end not yet resolved. Code-route the provider's physical pins to an offered mapping. |
| `Code route dropped: it conflicts with other connections` | The route matches no offered pin mapping. Route a legal one. |
| `Overlapping routing structures along path from <a> to <b>`; on a routed chain also `Ambiguous routing structures meet at <pad>` | Two structures on a shared chain segment. Apply one, over the longest path. |

## Verification design and assembly

Proof routes fix one placement and, on a pin-assigned port, one mapping, so
they go in a verification design per constrained interface, never the
shipping assembly. It code-routes every constrained path between physical
pads (the provider's pins on a pin-assigned port) and passes when every
constraint with a timing, loss or skew target measures between its intended
pads with no unresolved text in its groups. A structure-only constraint never
appears; it is exempt, and its code (class, Topology ends, structure) is its
evidence.

On the assembly, sort each SI group by whether its path has copper:

- No route: `Unconnected Topology`, `not routed yet`, a bare `No path`, and
  `Unassigned Pin` on a pin-assigned end are expected and recorded.
- Any route: the verification-design bar, `Missing routing structure` and a
  placeholder via model included.
- Blocking wherever it appears: `No path ... which has no pin model`,
  `Virtual connection without a pin model`, and a constraint with a timing,
  loss or skew target absent from the report.

Compliance is read from the routed assembly's own groups; a verification
design's values are proof-route numbers.

Parity compares constraint class, parameters, routing structure, Topology ends
(by physical pad) and pin models: the verification design's measurements (or,
structure-only, code) against the assembly's constraint code plus any
`Unconnected Topology on Path:` segment list. A missing comparison or a
mismatch returns the assembly to rework.
