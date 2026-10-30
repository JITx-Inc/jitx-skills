---
name: jitx-interconnect-constraints
description: "Use when the user asks about timing constraints, skew matching, insertion loss limits, pin models (bridging, terminating, via models), proving that an SI constraint applied, or debugging a constraint that does not measure in the design issues report. Also covers differential pairs, DiffPair bundles, skew across a bundle or against a clock, protocol constraints for PCIe, USB, DisplayPort, RGMII, Ethernet, DDR, reference planes, length matching, impedance-controlled routing, SignalConstraint definitions, and daisy-chain or flyby topologies built with the double-greater-than operator. Covers Topology, Constrain, ConstrainDiffPair, ConstrainReferenceDifference, DiffPairConstraint, BridgingPinModel, TerminatingPinModel, via models, ReferencePlanes, design issues, and protocol-specific constraint patterns. Trace width and clearance design rules belong to jitx-layout-constraints. Pin muxing and lane or polarity swappability belong to jitx-pin-assignment. Stackups and routing-structure definitions belong to jitx-substrate-modeler."
---

# JITX Interconnect Constraints

SI constraints (timing, insertion loss, intra-pair skew, skew to a reference) on jitx 4.6: `Topology(begin, end)` names a path's ends, routes and pin models let the runtime follow it, and the design issues report proves it measured.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

The worked patterns this skill points at are modules in the `jitxexamples` package. Install it into the project venv once with `pip install --no-deps --upgrade jitxexamples` (`--no-deps` keeps its pins off the project's `jitx`); it is not a project dependency. If importing a pointed-at module raises `ModuleNotFoundError`, the installed `jitxexamples` predates these patterns: say so, and work from the rules here.

## Package Architecture

```python
import jitx
from jitx.si import Constrain, ConstrainDiffPair, ConstrainReferenceDifference
from jitx.si import DiffPairConstraint, SignalConstraint, ReferencePlanes
from jitx.si import PinModel, BridgingPinModel, TerminatingPinModel
from jitx.net import DiffPair, Net, Port, PortAttachment, Topology
from jitx.circuit import Circuit, Route
from jitx.toleranced import Toleranced
from jitx import current
```

**These DO NOT EXIST — never import:**
`jitx.topology`, `jitx.constraints.si`, `jitx.diffpair`, `jitx.signal`,
`jitxlib.si`, `jitxlib.constraints`

`TopologyNet` is in `jitx.net`, routing structures in `jitx.si`; `Topology` is also re-exported from `jitx.si`.

## Anti-string-hacking

Apply per-lane or per-pair constraints by iterating a typed collection (`self.lanes: list[DiffPair]`), never a string-keyed dict or sibling attributes read with `getattr`, and hold constraints in a typed list or dataclass, never `dict[str, Any]` (`jitx/references/architectural-patterns.md`). `jitx-code-review` is the optional self-critique pass.

## Plain nets by default

Join the path with ordinary nets (`+` or `Net([...])`) and name its two ends with `Topology(begin, end)`. The runtime infers the path between them from the routes, crossing parts that carry pin models, so `>>` (`TopologyNet`) is not needed for timing, loss or skew. It is dispreferred, fixing the connection order before routing. Use it only for a daisy chain whose order is part of the design ([Daisy chains](#daisy-chains-)).

Store every net, constraint, helper, pin model and route on `self`; one left unstored logs `... lost during instantiation` and never reaches the report.

## Basic Constraints

`Topology(begin, end)` names the path and connects nothing. Delay is in seconds, loss in dB; `rs50 = current.substrate.routing_structure(50.0)`:

```python
self.cst = Constrain(Topology(self.drv.o, self.rcv.i)).timing(500e-12).insertion_loss(1.0).structure(rs50)
```

Worked pattern: `jitxexamples.patterns.si_point_to_point`. `.timing(high=..., low=...)` sets a window; `Constrain([topo_a, topo_b])` takes several paths.

Cover every timed path with one routing structure, on its own constraint or, in a daisy chain, the longest path's. Without one the measurement is not the structure's, and `Missing routing structure on Path: ...` is a defect to fix. `Constrain.structure()` takes only a single-ended `RoutingStructure`; differential work uses `ConstrainDiffPair` or `DiffPairConstraint`.

### Choosing the ends

Name the true end-to-end pads and check each measured line reads `from <begin> to <end>` with them; an intermediate pad measures a shorter span silently. A circuit port resolves to the first pad behind it, so behind a series part in a sub-circuit, constrain the chip's pad (`self.phy.chip.tx`, not `self.phy.tx`).

With a series part in each of two sub-circuits, the segment between them, on the net holding the ports, reports `Missing routing structure` despite `.structure(...)`. On a single-ended net, a structure-only constraint across the ports clears it: `self.mid = Constrain(Topology(self.a.p, self.b.p)).structure(rs50)`. Untried on a diff pair. Measured case: [Ends Inside Sub-Circuits](https://docs.jitx.com/en/latest/essentials/SI/constraints.html#ends-inside-sub-circuits).

## Pin Models

Pin model delay and loss are SI inputs the measurement adds: take them from the datasheet, IBIS or vendor model, or the user, never placeholders, and label a fictional part's values illustrative.

### BridgingPinModel: parts the signal passes through

A path stops at a part with no `BridgingPinModel`, reporting `No path for signal constraint ... the part between <x> and <y>, which has no pin model.` Give one to every part with a path through it between two pins (AC coupling cap, series resistor, common-mode choke, an ESD channel whose datasheet gives an in-to-out path), on the component class or in the circuit: `self.bridge = BridgingPinModel(self.cap.a, self.cap.b, delay=6e-12, loss=0.5)` (s, dB). A flow-through package whose opposite pin is not connected inside gets none: its two lands are one net joined by board copper, and a model would hide an open line. Worked pattern: `jitxexamples.patterns.si_series_part`.

A bare `No path`, naming no part, can come from an unrouted net crossing a circuit's bundle port (route it), a circuit-port end reaching several pads (name the pad), or an unresolved assignment ([pin-assigned ports](#constraints-on-pin-assigned-ports)).

### TerminatingPinModel: package delay at an end

Adds a chip or connector pin's package delay and loss, one per pin, whenever package or connector data is supplied: `pkg = [TerminatingPinModel(p, delay=15e-12, loss=0.2) for p in (tx.p, tx.n)]`. Worked pattern: `jitxexamples.patterns.si_point_to_point`.

### Via models

A via adds the delay and loss in its `models`, keyed by layer pair. The substrate declares the via class (`jitx-substrate-modeler`); a design-local subclass adds the models, and `PortAttachment(port, via)` nets it:

```python
class EscapeVia(MySubstrate.THVia):
    models = {(0, 1): PinModel(delay=6e-12, loss=0.04)}  # layer 0 to layer 1
```

Give every via on a constrained path a `models` entry for the layers it spans; without one it measures on a placeholder (`Structure model from [0] to [1] not found ...`), which is unresolved. Worked pattern: `jitxexamples.patterns.si_via_model`.

## Closing the path

The runtime infers the path between the `Topology` ends from routed copper, so no `>>` is needed: a path crosses a via, or a part with a pin model, where routes land on both sides. Unrouted, nothing measures; the report carries `Unconnected Topology on Path: <a>, <b>` per segment or `Signal path from <a> to <b> is not routed yet`. Route in the board view or with code routes between physical pads, vias and control points, one segment per hop (`Route(self.drv.o, self.via, layer=0)`; mechanics in `jitx-physical-layout`). A route the router cannot make reports `Unable to find path for requested route`, and the constraint `Missing Connection on Path`.

## Differential Pairs

A bundle net (`self.src.tx + self.dst.rx`) joins each leg; `drs100 = current.substrate.differential_routing_structure(100.0)`:

```python
self.dp_cst = (
    ConstrainDiffPair(Topology(self.src.tx, self.dst.rx))
    .timing_difference(3e-12).timing(600e-12).insertion_loss(3.0).structure(drs100)
)
```

`timing_difference` is the P-to-N skew window, one `Skew` line per pair; timing and loss apply per leg. `ConstrainDiffPair` also takes a list of topologies. `DiffPairConstraint(skew=Toleranced(...), loss=..., structure=...)` is a reusable helper with no delay limit: store it on `self`, then call `.constrain(src, dst)` per pair. Worked pattern: `jitxexamples.patterns.si_diff_pair` (both forms). `LanePair` (`jitx.common`) bundles a TX and an RX `DiffPair`.

## Skew Across a Bundle (ConstrainReferenceDifference)

Matches data to a clock or strobe (RGMII, DDR DQ to DQS) or lane to lane (PCIe, SFP):

```python
self.bus_skew = ConstrainReferenceDifference(
    guide=Topology(self.src.clk, self.dst.clk),
    topologies=[Topology(s, d) for s, d in zip(self.src.data, self.dst.data)],
).timing_difference(Toleranced(0, 11e-12))
```

The guide must run between single pins (`Guide must be a single pin type`), so across diff pairs one leg is the guide; each compared leg prints a `Skew` line. The window is guide delay minus target delay; the printed `Target` drops the sign. Worked pattern: `jitxexamples.patterns.si_bundle_skew`.

## Reference Planes

Reference planes name the return-path `Net` per routing layer: `with ReferencePlanes(self.GND):` (every layer), `with ReferencePlanes({0: self.GND, 1: self.GND, 2: self.PWR}):`, or `.structure(rs50, ref_layers={0: self.GND})`. A bare `Port` raises `'Port' object has no attribute 'connected'`. A structure with `.reference()` layers errors at build without them; for one with none the context is inert, so check the structure definition.

## Tag-based routing structures

For nets that share one structure and carry no timing, loss or skew limits, tag them and attach the structure as a design rule:

```python
from jitx.constraints import Tag, design_constraint  # class HighSpeedTag(Tag): pass
HighSpeedTag().assign(self.clk_net)
self.hs_rule = design_constraint(HighSpeedTag()).routing_structure(rs50, ref_net=self.GND)
```

Its reference planes come from `ref_net=`, `ref_layer_nets={layer: net}` or an active `ReferencePlanes`, not `ref_layers=` (`jitx-layout-constraints` `references/rule-reference.md`).

## Building Protocol Constraints (SignalConstraint)

Subclass `SignalConstraint[T]` (`T` the bundle `Port`), override `constrain(self, src: T, dst: T)`, and keep the standard's cited numbers in a parameter class. An `__init__` calls `super().__init__()` first (the base creates what `self.add(...)` extends). Store helpers and the instance on `self`, and call `constrain(src, dst)` on the true ends. For a transmit and a receive pair, `constrain` applies `src.tx` to `dst.rx` and `dst.tx` to `src.rx` (the crossover), never `tx` to `tx`. `constrain_topology` adds nothing on plain nets. Worked pattern: `jitxexamples.patterns.si_signal_constraint`.

For several signal groups, compose one constraint per group, called from `constrain`, as `jitxexamples.protocols.memory` does for DDR4 and LPDDR4, every number cited.

## Working with Built-in Protocols

`jitxlib.protocols` holds protocol constraints with their port bundles: `usb` (`USB2`, `USBSuperSpeed`, `USB_C`), `displayport` (`DisplayPort`), `ethernet.mii.rgmii` (`RGMII`), `ethernet.mdi.mdi100base_tx` (`MDI100BaseTX`), `ethernet.mdi.mdi1000base_t` (`MDI1000BaseT`). Find what your installed version has with your **Grep** tool (pattern `class.*Constraint.*SignalConstraint`, path `.venv`, glob `*.py`). Per-standard parameters: [references/protocol-standards.md](references/protocol-standards.md).

## Via Structures

`SingleViaStructure(via, ground_cages=[PolarViaGroundCage(...)], antipads=[])` (`jitxlib.via_structures`; `via` a class with `models`; the keyword-only `ground_cages` and `antipads` required) is a `Circuit` with `sig_in`, `sig_out` and `COMMON` ports around `signal_via`. Net it in like a part, join `COMMON` to ground, route to `signal_via` on each layer, and name the outer pads; it binds on plain nets and counts the via's `models` (single-ended and differential, measured on jitx 4.6.0rc10). A cage that closes the via off fails the routes (`Missing Connection on Path`): size it, turn it with `theta=`, or gap it with `skips=`. Worked pattern: `jitxexamples.patterns.si_via_structure`.

`DifferentialViaStructure(vias, pitch, ground_cages=..., antipads=...)` has `DiffPair` ports and vias `via_p` and `via_n`; `enterOn` / `exitOn` add pair insertions. Neither takes `insertion_points`.

**These DO NOT EXIST; never import:**
`jitx.via_structures`, `jitx.si.ViaStructure`, `jitxlib.vias`

## Constraints on pin-assigned ports

A constraint on a `require()`d port measures only once the assignment resolves (until then `Unassigned Pin on Path`, or `No path` between fixed physical ends). Code routes on the provider's physical pins resolve it, P/N inversion included; a route matching no offered mapping is dropped (`Code route dropped: it conflicts with other connections`) and the pin reported unassigned. A route cannot end on a `require()`d port, and a `require()`d port cannot be stored on `self`. Proof routes fix one mapping, so they belong in a verification design. Full rules: [jitx-pin-assignment](../jitx-pin-assignment/SKILL.md#constraints-on-pin-assigned-ports).

## Daisy chains (`>>`)

A daisy chain feeds loads in a fixed order, such as a DDR flyby clock. `self.a0 = self.ctrl.a0 >> self.dram0.a0 >> self.dram1.a0` builds a `TopologyNet` recording that order before routing. Apply the structure once, over the longest path; a second structure on a shared segment adds `Overlapping routing structures along path from ...` and, routed, `Ambiguous routing structures meet at <pad>`. A plain `Net` chain also measures once code-routed in order. How the autorouter treats a chain, with or without `>>`, is unverified: claim neither. Worked pattern: `jitxexamples.patterns.si_daisy_chain`.

## Common Mistakes

- Declaring `>>` on a point-to-point signal, or telling the user `>>` is required for a constraint to apply. Plain nets plus `Topology(begin, end)` are enough.
- `self.src.data = self.dst.data` is Python assignment, not a connection.
- Expecting a constraint to create copper: it measures routed paths only.

## Verification

Proving each SI constraint applied (width and clearance: `jitx-layout-constraints`; geometry: `jitx-physical-layout`).

Prove binding on a verification design per constrained interface: parts placed, every path code-routed between physical pads (on a pin-assigned port, the provider's pins), passing when each constraint with a timing, loss or skew target measures between its intended ends with no unresolved text; a structure-only constraint never appears, and its code is the evidence. The shipping assembly carries no proof routes: there the unrouted texts (`Unconnected Topology`, `not routed yet`, a bare `No path`, `Unassigned Pin`) are expected only where a path has no route, and a routed path meets the same bar. Details: [references/verification.md](references/verification.md).

1. Type check: `pyright path/to/circuit.py`.
2. Read the design issues from Python, as a script run from the project root while the project's runtime is running (`jitx runtime start --background`):

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

   Without `satisfied=True` a met constraint is left out. `group.text` shows only a group's first issue. Keep the code in `main()`: design discovery imports the project's `.py` files. `jitx.run` is experimental. Builds against one project run in sequence ([Build safety](../jitx/SKILL.md#build-safety-dont-parallelize-same-design-work)).

3. Count a constraint applied only when its group carries a `Time`, `Loss` or `Skew` measurement naming the intended ends (`met Time: <delay> - Target: 500ps ± 500ps from <begin> to <end>`); `status: ok` or a clean type check is not evidence. Compliance is `group.satisfied`, the only verdict: the text reads the same met or unmet, and a skew `Target` drops its sign. A group also holding an unresolved text ([table](references/verification.md#what-unresolved-looks-like)) is neither proven nor met. Report binding and compliance separately, and an unmet measurement as a violation.

## API Reference

- [jitx.si module](https://docs.jitx.com/en/latest/api/jitx.si.html)
- [SI Topology concepts](https://docs.jitx.com/en/latest/essentials/SI/topology.html)
- [SI Constraints guide](https://docs.jitx.com/en/latest/essentials/SI/constraints.html)

## Formatting

```bash
ruff format path/to/circuit.py
```
