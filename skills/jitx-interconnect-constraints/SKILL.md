---
name: jitx-interconnect-constraints
description: "Use when the user asks about topology using the double-greater-than operator, timing constraints, skew matching, insertion loss limits, differential pairs, DiffPair bundles, protocol constraints for PCIe, USB, DisplayPort, RGMII, Ethernet, DDR, pin models, reference planes, length matching, impedance-controlled routing, SignalConstraint definitions, or proving after build that an SI constraint bound to its intended end-to-end path. Covers TopologyNet, Constrain, ConstrainDiffPair, ConstrainReferenceDifference, DiffPairConstraint, ReferencePlanes, emitted topology-span verification, and protocol-specific constraint patterns. Trace width and clearance design rules belong to jitx-layout-constraints. Pin muxing and lane or polarity swappability belong to jitx-pin-assignment. Stackups and routing-structure definitions belong to jitx-substrate-modeler."
---

# JITX Interconnect Constraints

Apply signal integrity constraints to signal topologies in JITX Python designs. This skill bridges `jitx-circuit-builder` (wiring with `+`) and `jitx-substrate-modeler` (routing structures) by teaching how to create SI-aware topologies with `>>` and constrain them.

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
    symmetric_routing_layers,
)

# Topology and ports
from jitx.net import DiffPair, Port, TopologyNet, Topology

# Common bundles
from jitx.common import LanePair

# Core framework
from jitx import Circuit, Net, current
from jitx.toleranced import Toleranced
from jitx.units import ohm
```

**These DO NOT EXIST — never import:**
`jitx.topology`, `jitx.constraints.si`, `jitx.diffpair`, `jitx.signal`,
`jitx.si.TopologyNet` (it is in `jitx.net`), `jitxlib.si`, `jitxlib.constraints`

**Key locations:**
- `DiffPair` and `TopologyNet` are in `jitx.net`
- `Topology` is in `jitx.net` (re-exported from `jitx.si`)
- All constraint classes are in `jitx.si`
- Routing structures are in `jitx.si` (also used in substrate definitions)

For complete API signatures, see [jitx.si API docs](https://docs.jitx.com/en/latest/api/jitx.si.html).

## Anti-string-hacking — read before applying per-lane / per-pair constraint metadata

When applying constraints across N parallel diff-pairs or N parallel lanes, iterate over a typed collection (`self.lanes: list[DiffPair]`), not a string-keyed dict (`self.pairs["TX_b0"]`) or sibling attributes plus `getattr`. The constraints themselves are objects; assemble them inside a typed dataclass or list, never `dict[str, Any]`. See `jitx/references/architectural-patterns.md` §§ "String-keyed dicts → structural objects" and "Sibling attributes → array attributes" before writing per-lane constraint application code.

For a same-model self-critique pass on the constraint code after writing (catches what these rules don't), invoke `jitx-code-review`. Optional for single-task use.

## The Critical Distinction: `+` vs `>>`

The most important concept for SI-constrained designs:

```python
# + creates a Net — electrical connection only, NO SI awareness
# The routing engine can route this any way it wants
self.power_net = self.ic.VCC + self.cap.p1

# >> creates a TopologyNet — ordered signal path WITH SI awareness
# The routing engine knows the signal order and can apply constraints
self += self.driver.out >> self.receiver.inp
```

**Storage rules** (same as for `+` nets):

```python
# CORRECT — store on self with +=
self += self.src >> self.dst

# CORRECT — store as named attribute
self.my_topo = self.src >> self.dst

# CORRECT — store in a list on self
self.topos = [self.src >> self.dst]

# WRONG — topology created but not stored, silently dropped!
self.src >> self.dst  # BAD — lost!
```

**When to use which:**
- `+` — Power rails, ground connections, control signals without SI requirements
- `>>` — Any signal with timing, skew, loss, or impedance constraints (clocks, data buses, differential pairs, RF signals)

## Basic Topology and Constraints

### Step 1: Create topology with `>>`

```python
# >> defines the ordered signal path
self += self.driver.out >> self.receiver.inp
```

### Step 2: Identify topology for constraint application

```python
# Topology(begin, end) is a DESCRIPTOR — it identifies the path, does not create it
topo = Topology(self.driver.out, self.receiver.inp)
```

Both descriptor endpoints must be elements of the stored `>>` chain, not
ports that are merely netted to it. A reachable endpoint can still stop short
and silently constrain only part of the intended path. A subcircuit that
carries an SI chain therefore exposes both ends, and the outer constraint uses
the true end-to-end ports. The post-build gate in `references/verification.md`
refuses completion when an endpoint is absent or when the connected chain has
an uncovered segment.

### Step 3: Apply constraints

```python
# Get routing structure from substrate (defined in jitx-substrate-modeler)
rs50 = current.substrate.routing_structure(50.0)

# Apply with ReferencePlanes context
self.GND = Net(name="GND")
with ReferencePlanes(self.GND):
    self.cst = Constrain(topo).insertion_loss(1.0).structure(rs50)
```

### Constraint methods on `Constrain`

```python
# Insertion loss — max dB
Constrain(topo).insertion_loss(3.0)

# Timing — max propagation delay (seconds)
Constrain(topo).timing(500e-12)

# Timing — min and max delay window
Constrain(topo).timing(high=500e-12, low=100e-12)

# Routing structure assignment
Constrain(topo).structure(rs50)

# Chaining (all constraints applied together)
self.cst = (
    Constrain(topo)
    .insertion_loss(1.0)
    .timing(500e-12)
    .structure(rs50)
)
```

`Constrain.structure()` accepts a single-ended `RoutingStructure`.
`DifferentialRoutingStructure` is not a `RoutingStructure` subclass and does
not go through this method. Differential work uses `ConstrainDiffPair` or
`DiffPairConstraint`; the constraint-authoring step refuses to proceed to the
build with a differential structure attached through `Constrain`.

### Multiple signals with same constraint

```python
# Constrain accepts a sequence of Topology objects
topos = [Topology(s, d) for s, d in zip(src_pins, dst_pins)]
self.cst = Constrain(topos).insertion_loss(3.0).structure(rs50)
```

## Differential Pairs

### The DiffPair bundle

```python
import jitx
from jitx.net import DiffPair

class MyComponent(jitx.Component):
    data = DiffPair()  # has .p (positive) and .n (negative) sub-ports
```

### Constraining differential pairs

```python
# Create diff pair topology — >> connects both .p and .n
self += self.src.data >> self.dst.data

# Identify and constrain
topo = Topology(self.src.data, self.dst.data)

drs100 = current.substrate.differential_routing_structure(100.0)

self.dp_cst = (
    ConstrainDiffPair(topo)
    .timing_difference(5e-12)   # max 5ps intra-pair skew (P-to-N)
    .insertion_loss(3.0)         # max loss per line
    .structure(drs100)           # 100 ohm differential routing structure
)
```

### DiffPairConstraint — reusable helper

For applying the same constraint to multiple differential pairs:

```python
from jitx.si import DiffPairConstraint

# Create once, use many times
dp_cst = DiffPairConstraint(
    skew=Toleranced(0, 5e-12),    # max 5ps intra-pair skew
    loss=3.0,                      # max 3dB insertion loss
    structure=drs100,              # routing structure
)

# Apply to each diff pair
self += self.src.tx >> self.dst.rx
dp_cst.constrain(self.src.tx, self.dst.rx)

self += self.src.clk >> self.dst.clk
dp_cst.constrain(self.src.clk, self.dst.clk)
```

### LanePair — TX + RX bundle

```python
from jitx.common import LanePair

class MySerialPort(Port):
    lane = LanePair()  # has .TX (DiffPair) and .RX (DiffPair)
```

## Bus-Level Matching (ConstrainReferenceDifference)

Match multiple data signals to a reference clock or strobe:

```python
# Create topologies for clock and data
self += self.src.clk >> self.dst.clk
clk_topo = Topology(self.src.clk, self.dst.clk)

data_topos = []
for i in range(8):
    self += self.src.data[i] >> self.dst.data[i]
    data_topos.append(Topology(self.src.data[i], self.dst.data[i]))

# Constrain all data signals relative to clock
# "All data signals must arrive within +/- 11ps of the clock"
self.bus_skew = (
    ConstrainReferenceDifference(
        guide=clk_topo,             # reference signal
        topologies=data_topos,      # signals to match
    ).timing_difference(Toleranced(0, 11e-12))
)
```

**Key concept:** The `guide` is the reference signal. All `topologies` are constrained to arrive within the specified timing window relative to the guide.

This pattern is used for:
- RGMII: data-to-clock matching
- DDR: DQ-to-DQS matching, CMD/ADDR-to-CK matching
- PCIe/SFP: inter-lane skew (first lane as reference)

## Pin Models

Pin-model declarations participate in construction of the signal path across
components. In particular, a `BridgingPinModel` joins the topology between its
two ports. Without that edge, stored `>>` chains on the two sides of a passive
remain disconnected, and the build can still report `status: ok`.

### TerminatingPinModel — IC endpoints

Applied to active component pins where the signal terminates:

```python
class MyIC(jitx.Component):
    TX_P = Port()
    TX_N = Port()

    # Silicon-to-pad delay and loss
    pm_txp = TerminatingPinModel(TX_P, delay=15e-12, loss=0.2)
    pm_txn = TerminatingPinModel(TX_N, delay=15e-12, loss=0.2)
```

### BridgingPinModel — pass-through components

Applied to passive components that a signal passes through (AC coupling caps, series resistors, common-mode chokes):

```python
class BlockingCapacitor(jitx.Component):
    p1 = Port()
    p2 = Port()

    # This declaration joins the signal path across the two component ports.
    pin_model = BridgingPinModel(p1, p2, delay=6e-12, loss=0.5)
```

### Using BridgingPinModel in a subcircuit

Define a subcircuit with ports that a topology chains through:

```python
class ACCoupler(Circuit):
    """Single-ended AC coupling subcircuit."""
    A = Port()
    B = Port()

    def __init__(self):
        self.cap = BlockingCapacitor()  # has BridgingPinModel
        self += self.A >> self.cap.p1
        self += self.cap.p2 >> self.B
```

Differential pair version:

```python
class DiffPairCoupler(Circuit):
    """AC coupling for a differential pair."""
    A = DiffPair()
    B = DiffPair()

    def __init__(self, capacitance=100e-9):
        self.cap_p = BlockingCapacitor(capacitance)
        self.cap_n = BlockingCapacitor(capacitance)

        # Topology chains through the caps
        self.topo_p1 = self.A.p >> self.cap_p.p1
        self.topo_p2 = self.cap_p.p2 >> self.B.p
        self.topo_n1 = self.A.n >> self.cap_n.p1
        self.topo_n2 = self.cap_n.p2 >> self.B.n
```

### Chaining topology through a subcircuit

The outer circuit connects to the subcircuit's ports with `>>`. The topology chains through the subcircuit's internal `>>` connections automatically:

```python
class MyDesign(Circuit):
    def __init__(self):
        self.driver = MyDriver()
        self.recv = MyReceiver()
        self.coupler = ACCoupler()

        # Topology chains: driver -> coupler.A -> [internal] -> coupler.B -> recv
        self += self.driver.out >> self.coupler.A
        self += self.coupler.B >> self.recv.inp

        # Constrain the full end-to-end path
        topo = Topology(self.driver.out, self.recv.inp)
        with ReferencePlanes(self.GND):
            self.cst = Constrain(topo).insertion_loss(3.0)
```

### Topology with bridging components (no subcircuit)

When a topology passes through a component that does **not** have an embedded BridgingPinModel, define one at the circuit level:

```python
# Signal path: driver → cap → receiver
self += self.driver.out >> self.cap.p1
self += self.cap.p2 >> self.receiver.inp

# Add BridgingPinModel so the emitted topology has a path across the cap.
self.bridge = BridgingPinModel(self.cap.p1, self.cap.p2, delay=6e-12, loss=0.5)

# The post-build span check must now walk from driver to receiver.
topo = Topology(self.driver.out, self.receiver.inp)
self.cst = Constrain(topo).insertion_loss(3.0)
```

The constructor accepts delay and loss values, but this skill does not treat
their presence as binding evidence. `references/verification.md` proves the
path edge from the emitted `pinModels` record; numeric loss satisfaction needs
its own SI evidence.

## Reference Planes

Reference planes specify which net serves as the return path for each routing layer.

### Context manager form (most common)

```python
self.GND = Net(name="GND")

# All reference layers use GND
with ReferencePlanes(self.GND):
    self.cst = Constrain(topo).structure(rs50)
```

### Per-layer form

```python
# Different reference nets per layer
with ReferencePlanes({0: self.GND, 1: self.GND, 2: self.PWR}):
    self.cst = Constrain(topo).structure(rs50)
```

### On Constrain directly (via structure ref_layers)

```python
self.cst = Constrain(topo).structure(rs50, ref_layers={0: self.GND})
```

**Important:** If a routing structure has `.reference()` definitions (from
substrate-modeler), it needs `ReferencePlanes`; without them, the constraint
errors at build time. The converse matters too: a `ReferencePlanes` context is
inert when the routing structure declares no reference layers. Before the
constraint-authoring step proceeds to the build, it opens the selected
structure definition and confirms that the expected `.reference()` layers are
present. The presence of the context manager alone is not evidence.

## Tag-based routing structures (alternative to Constrain)

Since 4.2, a routing structure can also be applied through the **design-rule
system**: tag the nets/routes, then attach the structure as a rule effect.

```python
from jitx.constraints import Tag, design_constraint

class HighSpeedTag(Tag):
    "Nets that route on the 50-ohm structure."

# in the circuit — tag the nets (see jitx-physical-layout "Layout-intent tags"):
HighSpeedTag().assign(self.clk_net)

# in the rules — attach the structure:
self.hs_rule = design_constraint(HighSpeedTag()).routing_structure(rs50, ref_net=self.GND)
```

When to choose which:

- **Topology `Constrain(...).structure(...)`** — an ordered `>>` path exists and
  SI constraints (timing, skew, insertion loss) travel with the structure. The
  structure applies to the topology paths you enumerate (`Constrain` takes one
  topology or a list — see "Multiple signals with same constraint").
- **Tag-based `design_constraint(...).routing_structure(...)`** — class-of-net
  rules: every net or code-based `Route` carrying the tag gets the structure,
  with no per-signal topology authoring. This is also the only way to put a
  structure on a plain `Net` or a code-based `Route`, neither of which has a
  `>>` topology.

Reference planes for the rule effect resolve through `ref_net=` (one net for all
reference layers), `ref_layer_nets={layer: net}`, or an active `ReferencePlanes`
context — note the kwarg names differ from `Constrain.structure(...,
ref_layers=)`. Full signature and the three resolution modes:
`jitx-layout-constraints` `references/rule-reference.md`.

## Building Protocol Constraints (SignalConstraint)

For reusable protocol-specific constraint bundles, subclass `SignalConstraint[T]`:

### Pattern: Port bundle + Standard + Constraint

```python
from dataclasses import dataclass
from jitx.si import SignalConstraint, DiffPairConstraint
from jitx.net import DiffPair, Port
from jitx.toleranced import Toleranced
from jitx import current

# 1. Define port bundle
class MySerialLink(Port):
    tx = DiffPair()
    rx = DiffPair()

# 2. Define standard parameters
@dataclass(frozen=True)
class MyStandard:
    skew: Toleranced = Toleranced(0, 1e-12)
    loss: float = 12.0
    impedance: Toleranced = Toleranced(100, 10)

# 3. Define constraint class
class MyConstraint(SignalConstraint["MySerialLink"]):
    def __init__(self, standard: MyStandard,
                 structure: DifferentialRoutingStructure | None = None):
        super().__init__()
        if structure is None:
            structure = current.substrate.differential_routing_structure(
                standard.impedance
            )
        self._dp_cst = DiffPairConstraint(
            skew=standard.skew, loss=standard.loss, structure=structure
        )

    def constrain(self, src: MySerialLink, dst: MySerialLink):
        # Crossover: TX→RX, RX→TX
        self._dp_cst.constrain(src.tx, dst.rx)
        self._dp_cst.constrain(dst.tx, src.rx)
```

Every `SignalConstraint` subclass that defines `__init__` calls
`super().__init__()` before it adds or delegates constraints. The base
initializer creates the collection that `self.add(...)` extends. The
constraint-authoring step refuses to proceed to the build when a subclass
initializer omits that call, even if one delegated example happens not to use
`self.add(...)` yet.

### Using constrain_topology (context manager)

The `constrain_topology` method handles topology creation and constraint application together. Use it when inserting components (like AC coupling caps) into the topology:

```python
class MyDesignCircuit(Circuit):
    def __init__(self):
        self.fpga = FPGA()
        self.phy = PHY()

        std = MyStandard()
        cst = MyConstraint(std)

        # constrain_topology creates proxies and applies constraints
        with cst.constrain_topology(
            self.fpga.serial, self.phy.serial
        ) as (src, dst):
            # Insert AC coupling caps in the TX path
            self.coupler = DiffPairCoupler()
            self.topos = [
                src.tx >> self.coupler.A,
                self.coupler.B >> dst.rx,
                dst.tx >> src.rx,  # RX path direct
            ]
```

### Hierarchical constraints (DDR4 pattern)

For complex protocols with multiple signal groups, compose constraints:

```python
class DDR4Constraint(SignalConstraint["DDR4"]):
    def __init__(self, standard):
        super().__init__()
        self._data_cst = DDR4DataConstraint(standard)
        self._acc_cst = DDR4AccConstraint(standard)

    def constrain(self, src: DDR4, dst: DDR4):
        self._data_cst.constrain(src.data, dst.data)
        self._acc_cst.constrain(src.acc, dst.acc)
        # Cross-group: CK-to-DQS timing
        ...
```

See [jitx_protocols_ext](https://github.com/JITx-Inc/jitx-protocols-ext) for complete protocol implementations including PCIe, SATA, SFP, DDR4, LPDDR4, LPDDR5, and GDDR7.

## Working with Built-in Protocols

JITX provides built-in protocol constraints in `jitxlib`. Check your installed version for available protocols with your **Grep** tool (pattern `class.*Constraint.*SignalConstraint`, path `.venv`, glob `*.py`); it recurses and is OS-agnostic. Shell fallback: bash `grep -rn "class.*Constraint.*SignalConstraint" .venv/lib/python*/site-packages/jitxlib/protocols/` (macOS/Linux); on Windows use the Grep tool, or `Select-String` over `.venv\Lib\site-packages\jitxlib\protocols`.

Common built-in protocols:

| Protocol | Import Path | Port Bundle |
|----------|-------------|-------------|
| USB | `jitxlib.protocols.usb` | `USB2`, `USBSuperSpeed`, `USB_C` |
| DisplayPort | `jitxlib.protocols.displayport` | `DisplayPort` |
| RGMII | `jitxlib.protocols.ethernet.mii.rgmii` | `RGMII` |
| 100Base-TX | `jitxlib.protocols.ethernet.mdi.mdi100base_tx` | `MDI100BaseTX` |
| 1000Base-T | `jitxlib.protocols.ethernet.mdi.mdi1000base_t` | `MDI1000BaseT` |

For protocol-specific timing parameters (skew, loss, impedance per standard version), see [references/protocol-standards.md](references/protocol-standards.md).

## Via Structures in Topologies

Via structures let the constraint engine track signal transitions between layers. They are `Circuit` subclasses with `sig_in`, `sig_out`, and `COMMON` ports.

```python
from jitxlib.via_structures import SingleViaStructure, PolarViaGroundCage, SimpleAntiPad
```

**These DO NOT EXIST — never import:**
`jitx.via_structures`, `jitx.si.ViaStructure`, `jitxlib.vias`

### Simple via (bare signal transition)

```python
from jitxlib.via_structures import SingleViaStructure

# Bare via — no ground cage or antipads
self.via = SingleViaStructure(
    MySubstrate.MicroVia,
    ground_cages=[],
    antipads=[],
    insertion_points=[],
)
self.GND += self.via.COMMON

# Chain topology through via
self += self.driver.out >> self.via.sig_in
self += self.via.sig_out >> self.receiver.inp

# Constrain full path (via is transparent to the constraint)
topo = Topology(self.driver.out, self.receiver.inp)
rs50 = current.substrate.routing_structure(50.0)
with ReferencePlanes(self.GND):
    self.cst = Constrain(topo).structure(rs50).insertion_loss(3.0)
```

### RF via with ground cage

For controlled-impedance via transitions, add a `PolarViaGroundCage` and optional `SimpleAntiPad`:

```python
from jitxlib.via_structures import SingleViaStructure, PolarViaGroundCage, SimpleAntiPad

self.rf_via = SingleViaStructure(
    MySubstrate.MicroviaL1L2,
    ground_cages=[
        PolarViaGroundCage(
            MySubstrate.BlindViaL1L4,  # Via type for cage
            count=12,                   # Number of ground vias
            radius=0.6,                 # Distance from signal via (mm)
        )
    ],
    antipads=[SimpleAntiPad(shape, layers)],
    insertion_points=[],
)
self.GND += self.rf_via.COMMON

# Same topology pattern as bare via
self += self.driver.out >> self.rf_via.sig_in
self += self.rf_via.sig_out >> self.receiver.inp

topo = Topology(self.driver.out, self.receiver.inp)
rs50 = current.substrate.routing_structure(50.0)
with ReferencePlanes(self.GND):
    self.cst = Constrain(topo).insertion_loss(1.0).structure(rs50)
```

### Key points

- **`sig_in` / `sig_out`** — Signal enters and exits the via structure. Chain these with `>>` into your topology.
- **`COMMON`** — Ground connection for the cage vias. Always connect to your GND net with `+=`.
- **`insertion_points=[]`** — Required parameter. Pass empty list unless using custom insertion point geometry.
- **Positioning** — Via structures support `.at(x, y, rotate=angle)` for placement.
- **`DifferentialViaStructure`** — Same pattern but with `DiffPair` ports (`sig_in.p`, `sig_in.n`, etc.) and a `pitch` parameter for P/N spacing.

For `RoutingStructure`, `DifferentialRoutingStructure`, and substrate via definitions, see the `jitx-substrate-modeler` skill.

## Common Mistakes

```python
# WRONG: Using + for SI-constrained signals (no topology created)
self.data_net = self.src.data + self.dst.data

# CORRECT: Use >> for topology
self += self.src.data >> self.dst.data

# WRONG: Topology not stored (silently dropped)
self.src.data >> self.dst.data

# CORRECT: Store with += or named attribute
self += self.src.data >> self.dst.data

# WRONG: Using = for connections (Python assignment, no electrical connection)
self.src.data = self.dst.data

# WRONG: Constrain without ReferencePlanes when routing structure needs it
Constrain(topo).structure(rs50_with_reference)

# CORRECT: Wrap in ReferencePlanes
with ReferencePlanes(self.GND):
    Constrain(topo).structure(rs50_with_reference)

# WRONG: Creating Topology before creating the >> connection
topo = Topology(self.src, self.dst)  # Path doesn't exist yet!
self += self.src >> self.dst

# CORRECT: Create >> first, then identify with Topology
self += self.src >> self.dst
topo = Topology(self.src, self.dst)
```

Three more traps that build `status: ok` and fail silently or cryptically:

- **`>>` + `ConstrainDiffPair(...).structure(DRS)` routes NO copper by itself.**
  Constraints *bind* routed topologies (auto-router or interactive); they never
  synthesize geometry. A topology-only diff pair yields an empty layout that only
  fails downstream (e.g. "No trace on layer" at SI export). Route it — interactive,
  auto, or code `Route`s (see `jitx-physical-layout`).
- **A code `Route` and a `>>` segment on the same net double-connect** → invalid
  physical state. Full code-routing means dropping the parallel topology and
  applying structures via net tags: `design_constraint(Tag()).routing_structure(DRS,
  ref_net=GND)` with the tag assigned to the **net** (never per-route for
  differential — mismatched structures deform control-point transitions; a net tag
  also gives uncoupled legs the DRS `uncoupled_region` automatically).
- **`ReferencePlanes(...)` needs a `Net`, not a bare `Port`** — a Port raises the
  unhelpful `'Port' object has no attribute 'connected'`. Hoist the constraint to
  the scope where the reference is a `Net` (usually the parent circuit's GND).

## Verification

The detailed post-build procedure has one owner:
`references/verification.md`. It covers the emitted `load-cache.json` fields,
the executable span checker, its limits, and its negative controls. Layout
width and clearance checks remain with `jitx-layout-constraints`;
physical-layout checks remain with `jitx-physical-layout`.

### Step 1: Type check

```bash
pyright path/to/circuit.py
```

### Step 2: Build

```bash
jitx build <module.path.DesignClass>
```

JITX builds against the same project run in sequence. See `jitx/SKILL.md`
"Build Safety".

### Step 3: Prove emitted binding

The project copies `scripts/check_si_spans.py` and runs it against the built
design's `cache/load-cache.json`:

```bash
python scripts/check_si_spans.py path/to/Design/cache/load-cache.json
```

The task completion block is refused unless the command exits 0 and names the
expected constrained spans. `status: ok`, a zero-exit type check, or the
existence of a test harness cannot replace this result. An unavailable artifact
or exit 2 records binding as an open item, and the task may claim only that the
constraint translated.

When both a module harness and an assembly integration apply the constraint,
this step runs the checker on both artifacts and records the begin endpoint,
end endpoint, and intended path from each. The completion block is refused if
they differ without a named, intentional reason.

### Step 4: Record numeric SI evidence

SI constraint violations appear in the Issues List under "Unsatisfied Signal
Constraints" in the JITX UI. This UI evidence can support timing, skew, or loss
compliance when it is actually inspected. The CLI build does not expose that
panel, and the emitted-span checker proves binding rather than numeric
compliance. Claims without the corresponding evidence stay open.

## API Reference

For complete class definitions, all parameters, and method signatures:
- [jitx.si module](https://docs.jitx.com/en/latest/api/jitx.si.html)
- [SI Topology concepts](https://docs.jitx.com/en/latest/essentials/SI/topology.html)
- [SI Constraints guide](https://docs.jitx.com/en/latest/essentials/SI/constraints.html)

## Formatting

```bash
ruff format path/to/circuit.py
```
