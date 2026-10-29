---
name: jitx-interconnect-constraints
description: "Use when the user asks about timing constraints, skew matching, insertion loss limits, pin models (bridging, terminating, via models), proving that an SI constraint applied, or debugging a constraint that does not measure in the design issues report. Also covers differential pairs, DiffPair bundles, skew across a bundle or against a clock, protocol constraints for PCIe, USB, DisplayPort, RGMII, Ethernet, DDR, reference planes, length matching, impedance-controlled routing, SignalConstraint definitions, and daisy-chain or flyby topologies built with the double-greater-than operator. Covers Topology, Constrain, ConstrainDiffPair, ConstrainReferenceDifference, DiffPairConstraint, BridgingPinModel, TerminatingPinModel, via models, ReferencePlanes, design issues, and protocol-specific constraint patterns. Trace width and clearance design rules belong to jitx-layout-constraints. Pin muxing and lane or polarity swappability belong to jitx-pin-assignment. Stackups and routing-structure definitions belong to jitx-substrate-modeler."
---

# JITX Interconnect Constraints

Apply signal integrity constraints (timing, insertion loss, intra-pair skew, skew against a reference) to signal paths in JITX Python designs, on jitx 4.6. A constraint names a path's two ends with `Topology(begin, end)`; the ports along the path are joined by the ordinary nets `jitx-circuit-builder` teaches; routes and pin models let the runtime follow the path; the design issues report proves it measured. Routing structures come from `jitx-substrate-modeler`.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

## Package Architecture

```python
# Core SI imports
from jitx.si import (
    Constrain,
    ConstrainDiffPair,
    ConstrainReferenceDifference,
    DiffPairConstraint,
    SignalConstraint,
    PinModel,
    BridgingPinModel,
    TerminatingPinModel,
    ReferencePlanes,
    RoutingStructure,
    DifferentialRoutingStructure,
)

# Path ends and ports
from jitx.net import DiffPair, Net, Port, PortAttachment, Topology

# Code routes that close a path
from jitx.circuit import Circuit, Route

# Common bundles
from jitx.common import LanePair

from jitx import current
from jitx.toleranced import Toleranced
```

**These DO NOT EXIST — never import:**
`jitx.topology`, `jitx.constraints.si`, `jitx.diffpair`, `jitx.signal`,
`jitx.si.TopologyNet` (it is in `jitx.net`), `jitxlib.si`, `jitxlib.constraints`

`DiffPair`, `Topology` and `TopologyNet` are in `jitx.net` (`Topology` is re-exported from `jitx.si`); every constraint class and routing structure is in `jitx.si`. For complete API signatures, see [jitx.si API docs](https://docs.jitx.com/en/latest/api/jitx.si.html).

## Anti-string-hacking — read before applying per-lane / per-pair constraint metadata

When applying constraints across N parallel diff-pairs or N parallel lanes, iterate over a typed collection (`self.lanes: list[DiffPair]`), not a string-keyed dict (`self.pairs["TX_b0"]`) or sibling attributes plus `getattr`. The constraints themselves are objects; assemble them inside a typed dataclass or list, never `dict[str, Any]`. See `jitx/references/architectural-patterns.md` §§ "String-keyed dicts → structural objects" and "Sibling attributes → array attributes" before writing per-lane constraint application code.

For a same-model self-critique pass on the constraint code after writing (catches what these rules don't), invoke `jitx-code-review`. Optional for single-task use.

## Plain nets by default

On jitx 4.6 an SI constraint needs only the path's two ends. Connect the path with ordinary nets (`+` or `Net([...])`) and name the ends with `Topology(begin, end)`. The runtime infers the path between them from the routes, crossing parts that carry pin models.

The `>>` operator (`TopologyNet`) is not needed for timing, loss or skew, and it is dispreferred: a topology is complex and rigid, fixing the connection order before anything is routed. Use it only for a daisy chain whose order is part of the design, such as a flyby clock ([Daisy chains](#daisy-chains-)).

Nets, constraints, constraint helpers, pin models and routes join the design only when the circuit stores them. A dropped constraint or helper logs `Reference to structural object <Class> ... lost during instantiation, it likely needs to be assigned to an object.` and never reaches the report:

```python
self.n1 = self.drv.o + self.cap.a           # CORRECT
self.nets = [self.cap.b + self.rcv.i]       # CORRECT
self.drv.o + self.cap.a                     # WRONG: built, never stored
Constrain(Topology(self.drv.o, self.rcv.i)).timing(500e-12)  # WRONG: lost during instantiation
```

## Basic Constraints

```python
self.n1 = self.drv.o + self.cap.a
self.n2 = self.cap.b + self.rcv.i

# Topology(begin, end) names the path; it connects nothing.
topo = Topology(self.drv.o, self.rcv.i)

rs50 = current.substrate.routing_structure(50.0)
self.cst = (
    Constrain(topo)
    .timing(500e-12)          # max propagation delay, seconds
    .insertion_loss(1.0)      # max loss, dB
    .structure(rs50)          # single-ended RoutingStructure
)
```

Other forms: `.timing(high=500e-12, low=100e-12)` for a delay window, and `Constrain([topo_a, topo_b])` to give several paths the same constraints individually.

Cover every timed path with one routing structure: on its own constraint, or, for a daisy chain, on the single constraint over the longest path ([Daisy chains](#daisy-chains-)). Without one the constraint still measures, but with a delay and loss that are not the structure's, and the report adds `Missing routing structure on Path: ...` per segment: treat that line as a defect to fix.

`Constrain.structure()` accepts a single-ended `RoutingStructure`. `DifferentialRoutingStructure` is not a `RoutingStructure` subclass; differential work uses `ConstrainDiffPair` or `DiffPairConstraint`.

### Choosing the ends

Name the true end-to-end pads. A constraint that ends on an intermediate pad measures a shorter span silently; check that each measured line reads `from <begin> to <end>` with your intended ends. A circuit port as an end resolves to the first pad behind it, so when a sub-circuit holds a series part between its port and the chip, a constraint on the sub-circuit port leaves that part out of the measurement. Constrain to the chip's pad instead (`self.phy.chip.tx`, not `self.phy.tx`).

With a series part in each sub-circuit, the segment between the series parts, whose net holds the sub-circuit ports, reports `Missing routing structure on Path: a.ser.a, b.ser.a` beside the chip-to-chip measurement, though the constraint has `.structure(...)`. On that single-ended net, a structure-only constraint across the ports, `self.mid = Constrain(Topology(self.a.p, self.b.p)).structure(rs50)`, cleared the line, and the Time dropped from 211.039 ps to 182.253 or 184.468 ps across runs (jitx 4.6.0rc10, runtime 4.6.0-rc.16). A diff pair was not tried. With no series part, nothing was missing.

## Pin Models

Each pin model carries delay and loss that the measurement adds. They are SI inputs: take them from the datasheet, IBIS or vendor model, or values the user supplied, never placeholders.

### BridgingPinModel: parts the signal passes through

A path stops at any part between its ends that has no `BridgingPinModel`. AC coupling caps, series resistors and common-mode chokes each need one:

```python
class BlockingCapacitor(jitx.Component):
    a = Port()
    b = Port()
    # delay (s) and loss (dB) across the part, from its datasheet or the user
    through = BridgingPinModel(a, b, delay=6e-12, loss=0.5)
```

When the component does not carry one, add it in the circuit: `self.bridge = BridgingPinModel(self.cap.a, self.cap.b, delay=6e-12, loss=0.5)`. Without it the report says `No path for signal constraint from drv.o to rcv.i: the ends are only connected through the part between cap.a and cap.b, which has no pin model.` A bare `No path` before routing can also come from an unrouted net that crosses a circuit's bundle port, so route first, then read it.

### TerminatingPinModel: package delay at an end

Adds a chip or connector pin's package delay and loss, one per pin. Add one whenever package or connector data is supplied:

```python
class MyIC(jitx.Component):
    tx = DiffPair()
    pkg = [TerminatingPinModel(p, delay=15e-12, loss=0.2) for p in (tx.p, tx.n)]
```

### Via models

A via adds the delay and loss in its `models`, keyed by the layer pair the signal crosses. The substrate declares the via class (`jitx-substrate-modeler`); when a constrained path goes through a via, a design-local subclass adds the models:

```python
class EscapeVia(MySubstrate.THVia):
    models = {(0, 1): PinModel(delay=8e-12, loss=0.05)}  # layer 0 to layer 1

self.via = EscapeVia().at(x, y)
self.escape = PortAttachment(self.bga.tx.p, self.via)
```

Give every via on a constrained path a `models` entry for the layers it spans. A via without one still measures, but with a placeholder model, and the report says `Structure model from [0] to [1] not found in "<Via>". Using placeholder model ...`: treat that as unresolved, not as a result.

## Closing the path

Path inference follows routed copper. Before routing there is nothing to measure: the report carries `Unconnected Topology on Path: <a>, <b>` per segment, or `Signal path from <a> to <b> is not routed yet`. Route in the board view, or close the path from code so the proof runs headless:

```python
self.routes = [
    Route(self.bga.tx.p, self.via, layer=0),
    Route(self.via, self.cap.a, layer=1),
    Route(self.cap.b, self.conn.tx.p, layer=1),
]
```

Route between physical pads, vias and control points, one segment per hop. A route the router cannot make reports `Unable to find path for requested route` under Routing, and the constraint reports `Missing Connection on Path: <a>, <b>`. Control points and route mechanics belong to `jitx-physical-layout`.

## Differential Pairs

```python
self.nets = [self.src.tx + self.dst.rx]       # bundle + nets each leg

drs100 = current.substrate.differential_routing_structure(100.0)
self.dp_cst = (
    ConstrainDiffPair(Topology(self.src.tx, self.dst.rx))
    .timing_difference(5e-12)   # max P-to-N skew
    .timing(400e-12)            # max delay per leg
    .insertion_loss(3.0)        # max loss per leg
    .structure(drs100)
)
```

Timing and loss apply to each leg, so each leg gets its own `Time` and `Loss` line; the skew gives one `Skew` line per pair.

`ConstrainDiffPair` also takes a list of pair topologies. For the same constraint on many pairs, `DiffPairConstraint` is a reusable helper:

```python
self.dp_helper = DiffPairConstraint(skew=Toleranced(0, 5e-12), loss=3.0, structure=drs100)
self.dp_helper.constrain(self.src.tx, self.dst.rx)
self.dp_helper.constrain(self.src.clk, self.dst.clk)
```

`LanePair` (`jitx.common`) bundles a TX and an RX `DiffPair`.

## Skew Across a Bundle (ConstrainReferenceDifference)

Match signals to a reference: data to a clock or strobe, or pairs to each other.

```python
self.bus_skew = ConstrainReferenceDifference(
    guide=Topology(self.src.clk, self.dst.clk),
    topologies=[Topology(s, d) for s, d in zip(self.src.data, self.dst.data)],
).timing_difference(Toleranced(0, 11e-12))
```

The guide must run between single pins (`Guide must be a single pin type` otherwise). For skew across diff pairs, one leg of one pair is the guide, and the report prints one `Skew` line per compared leg:

```python
self.bundle = ConstrainReferenceDifference(
    Topology(self.bga.tx0.p, self.conn.tx0.p),
    [Topology(self.bga.tx1.p, self.conn.tx1.p), Topology(self.bga.tx1.n, self.conn.tx1.n)],
).timing_difference(5e-12)
```

Used for RGMII data to clock, DDR DQ to DQS and CMD/ADDR to CK, and PCIe or SFP lane-to-lane skew.

## Reference Planes

Reference planes name the return-path net per routing layer. They take a `Net`, not a bare `Port`:

```python
with ReferencePlanes(self.GND):                       # one net for every reference layer
    self.cst = Constrain(topo).structure(rs50)
with ReferencePlanes({0: self.GND, 1: self.GND, 2: self.PWR}):   # per layer
    self.cst2 = Constrain(topo2).structure(rs50)
self.cst3 = Constrain(topo3).structure(rs50, ref_layers={0: self.GND})
```

A routing structure with `.reference()` definitions (from `jitx-substrate-modeler`) needs reference planes; without them the constraint errors at build time. A `ReferencePlanes` context is inert when the structure declares no reference layers, so open the structure definition and confirm its `.reference()` layers rather than trusting the context manager.

## Tag-based routing structures

A routing structure can also be applied through the design-rule system: tag the nets, then attach the structure as a rule effect.

```python
from jitx.constraints import Tag, design_constraint

class HighSpeedTag(Tag):
    "Nets that route on the 50-ohm structure."

HighSpeedTag().assign(self.clk_net)
self.hs_rule = design_constraint(HighSpeedTag()).routing_structure(rs50, ref_net=self.GND)
```

Use `Constrain(...).structure(...)` when the path also carries timing, loss or skew limits. Use the tag rule for a class of nets that all get one structure with no per-signal limits. Reference planes for the rule resolve through `ref_net=`, `ref_layer_nets={layer: net}`, or an active `ReferencePlanes` context (the kwarg names differ from `Constrain.structure(..., ref_layers=)`); full signature in `jitx-layout-constraints` `references/rule-reference.md`.

## Building Protocol Constraints (SignalConstraint)

For reusable protocol bundles, subclass `SignalConstraint[T]`:

```python
@dataclass(frozen=True)
class MyStandard:
    skew: Toleranced = Toleranced(0, 1e-12)
    loss: float = 12.0
    impedance: Toleranced = Toleranced(100, 10)

class MySerialLink(Port):
    tx = DiffPair()
    rx = DiffPair()

class MyConstraint(SignalConstraint[MySerialLink]):
    def __init__(self, standard: MyStandard,
                 structure: DifferentialRoutingStructure | None = None) -> None:
        super().__init__()
        if structure is None:
            structure = current.substrate.differential_routing_structure(standard.impedance)
        self._dp_cst = DiffPairConstraint(skew=standard.skew, loss=standard.loss, structure=structure)

    def constrain(self, src: MySerialLink, dst: MySerialLink) -> None:
        self._dp_cst.constrain(src.tx, dst.rx)   # crossover: TX to RX
        self._dp_cst.constrain(dst.tx, src.rx)
```

Every subclass that defines `__init__` calls `super().__init__()` first; the base initializer creates the collection that `self.add(...)` extends.

Apply it on plain nets with `constrain(src, dst)`, naming the true ends, and wire the parts between them as usual. Here `coupler` is an AC coupling part with `DiffPair` ports `a` and `b` and a `BridgingPinModel` on each leg:

```python
self.link_cst = MyConstraint(MyStandard())
self.link_cst.constrain(self.fpga.serial, self.phy.serial)
self.tx_nets = [self.fpga.serial.tx + self.coupler.a, self.coupler.b + self.phy.serial.rx]
self.rx_nets = [self.phy.serial.tx + self.fpga.serial.rx]
```

`constrain_topology(src, dst)` calls `constrain(src, dst)` immediately and returns a context manager that yields `(src, dst)`; it only moves an end along a `>>` chain already in the circuit. On plain nets it adds nothing over `constrain`.

For protocols with several signal groups, compose: a `DDR4Constraint` holds a data constraint and an address/command constraint and calls each from its own `constrain`. `jitxexamples.protocols.memory` (the `jitxexamples` distribution) implements DDR4 and LPDDR4 this way, with every number cited to its source.

## Working with Built-in Protocols

JITX provides built-in protocol constraints in `jitxlib`. Check your installed version for available protocols with your **Grep** tool (pattern `class.*Constraint.*SignalConstraint`, path `.venv`, glob `*.py`); it recurses and is OS-agnostic.

| Protocol | Import Path | Port Bundle |
|----------|-------------|-------------|
| USB | `jitxlib.protocols.usb` | `USB2`, `USBSuperSpeed`, `USB_C` |
| DisplayPort | `jitxlib.protocols.displayport` | `DisplayPort` |
| RGMII | `jitxlib.protocols.ethernet.mii.rgmii` | `RGMII` |
| 100Base-TX | `jitxlib.protocols.ethernet.mdi.mdi100base_tx` | `MDI100BaseTX` |
| 1000Base-T | `jitxlib.protocols.ethernet.mdi.mdi1000base_t` | `MDI1000BaseT` |

For protocol-specific timing parameters (skew, loss, impedance per standard version), see [references/protocol-standards.md](references/protocol-standards.md).

## Via Structures

Via structures (`jitxlib.via_structures`) are `Circuit`s with `sig_in`, `sig_out` and `COMMON` ports around a signal via, with optional ground cage and antipads. Net them in like a part and route to the signal via; the constraint names the outer pads. Measured on jitx 4.6.0rc10 with runtime 4.6.0-rc.16, single-ended and differential, the constraint binds on plain nets and counts the via's `models`.

```python
from jitxlib.via_structures import SingleViaStructure, PolarViaGroundCage

self.vs = SingleViaStructure(
    EscapeVia,                       # a via class with models
    ground_cages=[PolarViaGroundCage(MySubstrate.THVia, count=4, radius=1.5)],
    antipads=[],
).at(0, 0)
self.GND += self.vs.COMMON
self.nets = [self.drv.o + self.vs.sig_in, self.vs.sig_out + self.rcv.i]
self.routes = [
    Route(self.drv.o, self.vs.signal_via, layer=0),
    Route(self.vs.signal_via, self.rcv.i, layer=1),
]
self.cst = Constrain(Topology(self.drv.o, self.rcv.i)).timing(1e-9).structure(rs50)
```

The cage must leave the routes a way in. On the two-layer `jitx.sample.SampleSubstrate` this four-via cage at 1.5 mm measured `Time: 112.495ps`; an eight-via cage at 0.6 mm closed the via off, and the report gave `Missing Connection on Path` with `Unable to find path for requested route`. Size the cage for your trace and clearance, or leave a gap with `skips=`.

`DifferentialViaStructure(vias, pitch, ground_cages=..., antipads=...)` has `DiffPair` ports and signal vias `via_p` and `via_n`; optional `enterOn` / `exitOn` add pair insertions. Neither class takes an `insertion_points` argument.

**These DO NOT EXIST; never import:**
`jitx.via_structures`, `jitx.si.ViaStructure`, `jitxlib.vias`

## Constraints on pin-assigned ports

A constraint on a `require()`d port measures only once the assignment resolves. Code routes on the provider's physical pins resolve it, including P/N inversion; routes that match no offered mapping are dropped (`Code route dropped: it conflicts with other connections`). A route cannot end on a `require()`d port, and a `require()`d port cannot be stored on `self`. With the Topology ending on the `require()`d port, an unresolved assignment reports `Unassigned Pin on Path: ...`; with fixed physical ends around the assigned pins, an unresolved or illegal assignment reports `No path for signal constraint`. Proof routes fix one mapping, so they belong in a verification design (see Verification). The full rules and patterns are in [jitx-pin-assignment](../jitx-pin-assignment/SKILL.md#constraints-on-pin-assigned-ports).

## Daisy chains (`>>`)

A daisy chain feeds several loads in a fixed order, such as a DDR flyby clock or address bus. `>>` builds a `TopologyNet` that records that order before anything is routed:

```python
self.a0 = self.ctrl.a0 >> self.dram0.a0 >> self.dram1.a0     # the chain is the connection
self.a0_timing = Constrain(
    [Topology(self.ctrl.a0, self.dram0.a0), Topology(self.ctrl.a0, self.dram1.a0)]
).timing(1e-9)
self.a0_rs = Constrain(Topology(self.ctrl.a0, self.dram1.a0)).structure(rs50)
```

Store the chain like any net. Unrouted, it reports `Unconnected Topology` per segment. Apply the structure once, over the longest path: when two constraints both put a structure on the shared `ctrl.a0` to `dram0.a0` segment, the report adds `Overlapping routing structures along path from ...`.

The same chain on a plain `Net([ctrl.a0, dram0.a0, dram1.a0])` also measures once it is code-routed in order (78.396 ps to the first load and 156.793 ps to the second on a two-layer sample board): the routes fix the order. How the autorouter treats a chain with or without `>>` has not been verified; do not claim either way.

## Common Mistakes

- Declaring `>>` on a point-to-point signal, or telling the user `>>` is required for a constraint to apply. Plain nets plus `Topology(begin, end)` are enough.
- Claiming a timed constraint applies from `status: ok`, a clean type check, or an issue report read without `satisfied=True`. Only a measurement counts.
- A part on the path with no `BridgingPinModel`, or a via with no `models`. Add the model; do not accept the placeholder.
- A timed path covered by no routing structure (neither its own constraint nor, for a chain, the longest-path constraint). The measurement is not the structure's; the `Missing routing structure` line is a defect.
- Ending a constraint on a sub-circuit port or an intermediate pad, so the measurement skips part of the path.
- Expecting constraints to create copper. They measure routed paths; route in the board view, or with code `Route`s.
- `DifferentialRoutingStructure` passed to `Constrain.structure`; use `ConstrainDiffPair`.
- A pair (`DiffPair`) as the guide of `ConstrainReferenceDifference`; use one leg.
- `self.src.data = self.dst.data` is Python assignment, not a connection.
- `ReferencePlanes(port)` with a bare `Port` raises `'Port' object has no attribute 'connected'`; pass the parent circuit's `Net`.

## Verification

Layout width and clearance checks belong to `jitx-layout-constraints`; physical-layout checks to `jitx-physical-layout`. This section proves that each SI constraint applied.

Prove binding on a code-routed verification design, one per constrained interface. It places the parts, code-routes each path between physical pads (on a pin-assigned port, the provider's physical pins), and passes when each constraint with a timing, loss or skew target has a measurement with the intended ends and no unresolved text. A structure-only constraint never appears; its code is the evidence. The shipping assembly carries no proof routes. On it, the unrouted texts (`Unconnected Topology`, `not routed yet`, a bare `No path`, `Unassigned Pin`) are expected only on a constraint whose path has no route; a routed constraint is held to the verification-design bar. [references/verification.md](references/verification.md) has the full rule, the blocking texts and parity evidence.

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

   Without `satisfied=True` a met constraint is left out. A group of several issues shows only the first in `group.text`. Keep the code in `main()`: design discovery imports the project's `.py` files. `jitx.run` is marked experimental. Builds against one project run in sequence ([Build safety](../jitx/SKILL.md#build-safety-dont-parallelize-same-design-work)).

3. A constraint bound to its path when its group carries a Time, Loss or Skew measurement naming the intended ends:

   ```text
   met Time: 105.311ps - Target: 500ps ± 500ps from drv.d.p to rcv.d.p
   met Time: 105.311ps - Target: 500ps ± 500ps from drv.d.n to rcv.d.n
   met Skew: 0s - Target: ± 1ps (longer from drv.d.p to rcv.d.p, shorter from drv.d.n to rcv.d.n)
   ```

   A group that also holds a text [references/verification.md](references/verification.md) lists as unresolved is not proven; that page gives each cause and fix.

4. Keep binding apart from compliance. Binding: the measurement exists. Compliance: `group.satisfied`, the verdict to read; the text reads the same met or unmet, and a skew window's printed `Target` drops its sign. A group that also holds an unresolved text is not met. Report both, and an unmet measurement as a violation.

## API Reference

- [jitx.si module](https://docs.jitx.com/en/latest/api/jitx.si.html)
- [SI Topology concepts](https://docs.jitx.com/en/latest/essentials/SI/topology.html)
- [SI Constraints guide](https://docs.jitx.com/en/latest/essentials/SI/constraints.html)

## Formatting

```bash
ruff format path/to/circuit.py
```
