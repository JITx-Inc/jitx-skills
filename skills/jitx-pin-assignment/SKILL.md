---
name: jitx-pin-assignment
description: "Use when the user asks about provide/require patterns, provide.one_of or provide.subset_of decorators, programmatic Provide, pin muxing, MCU peripherals on shared pins, DiffPair polarity swapping, PCIe lane swapping or width variants, DDR byte or bit swapping, LPDDR5 channel swapping, hierarchical provider composition, SI constraints on pin-assigned ports, constraints with provide/require, or flexible pin mapping for FPGAs and MCUs. Covers provide, Provide, require, all_of, one_of, subset_of, and protocol-specific pin flexibility with SI constraints."
---

# JITX Pin Assignment

Model flexible pin mappings between circuit-level interfaces and component-level pins. JITX's provide/require system lets a provider offer every mapping the part allows and leaves the choice open; routes on the provider's physical pins resolve it to one mapping.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

The worked patterns this skill points at are modules in the `jitxexamples` package. Install it into the project venv once with `pip install --no-deps --upgrade jitxexamples` (`--no-deps` keeps its pins off the project's `jitx`); it is not a project dependency. If importing a pointed-at module raises `ModuleNotFoundError`, the installed `jitxexamples` predates these patterns: say so, and work from the rules here.

## Package Architecture

```python
from jitx import Circuit, Net
from jitx.net import Port, DiffPair, Topology, provide, Provide
from jitx.common import Power, GPIO
from jitxlib.protocols.serial import I2C, SPI, UART
from jitx.si import BridgingPinModel, Constrain, ConstrainDiffPair, ConstrainReferenceDifference
from jitx.circuit import Route
from jitx.toleranced import Toleranced
```

**These DO NOT EXIST — never import:**
`jitx.provide`, `jitx.providers`, `jitx.pin_assignment`, `jitx.assign`,
`jitx.net.provide_one_of`, `jitxlib.pin_assignment`, `jitx.pin_assign`

**Key locations:**
- `provide` (lowercase, decorator) is in `jitx.net`
- `Provide` (uppercase, constructor class) is in `jitx.net` (also re-exported from `jitx`)
- `GPIO` is in `jitx.common`
- `I2C`, `SPI`, `UART` are in `jitxlib.protocols.serial`
- All constraint classes (`DiffPairConstraint`, `ReferencePlanes` too) are in `jitx.si`

## When to Use Pin Assignment

Use pin assignment when a component's physical pins can validly serve more than one logical role, and the choice should stay open until routing instead of being fixed in code.

**Use pin assignment for:**
- MCU GPIO — any of N pins can drive an LED, sensor, etc.
- Peripheral muxing — I2C/SPI/UART available on alternate pin groups
- DiffPair polarity: some protocols allow P/N swap (PCIe, where the controller supports polarity inversion)
- Lane ordering — PCIe lane reversal, width variants (x1/x2/x4)
- Byte/bit swapping — DDR controllers that support data bus reordering
- Channel choice on a pass-through part whose channels are identical

**Use fixed wiring instead when:**
- The mapping is 1:1 with no flexibility (e.g., DDR address pins, CK polarity)
- The component datasheet specifies a single valid pin function
- A deterministic connection is needed regardless of layout

## Bundles: The Language of Provide/Require

A **bundle** is a Port subclass that groups related signals. Bundles are the type parameter for `@provide` and `require()` — they define what interface is being offered and consumed.

### Built-in Bundles and Their Sub-Ports

Discover sub-ports by reading the class source — use your **Grep** tool (pattern `class BundleName`, path `.venv`, glob `*.py`, ~10 context lines); it recurses and is OS-agnostic. Shell fallback: bash `grep -rn -A 10 "class BundleName" .venv/lib/python*/site-packages/jitx*/` (macOS/Linux); on Windows use the Grep tool, or `Select-String` over `.venv\Lib\site-packages\jitx*`.

| Bundle | Import | Sub-ports | Notes |
|--------|--------|-----------|-------|
| `GPIO` | `jitx.common` | `.gpio` | Single pin |
| `Power` | `jitx.common` | `.Vp`, `.Vn` | Power/ground pair |
| `DiffPair` | `jitx.net` | `.p`, `.n` | Positive/negative pair |
| `I2C` | `jitxlib.protocols.serial` | `.sda`, `.scl` | Always present |
| `SPI` | `jitxlib.protocols.serial` | `.sck`, `.copi`, `.cipo`, `.cs` | `cs`, `copi`, `cipo` are optional: `SPI(cs=True)` |
| `UART` | `jitxlib.protocols.serial` | `.tx`, `.rx`, `.cts`, `.rts`, ... | `tx`/`rx` default on; flow control optional: `UART(cts=True, rts=True)` |

### Defining Custom Bundles

When no built-in bundle matches your interface, subclass `Port`:

```python
class PCIeLane(Port):
    TX = DiffPair()
    RX = DiffPair()

class PCIeLink(Port):
    lane = [PCIeLane() for _ in range(4)]
```

**Rules for custom bundles:**
- Subclass `Port`, not `Circuit` or `Component`
- Sub-ports are class attributes (Port, DiffPair, or lists of them)
- Use lists for indexed groups: `DQ = [Port() for _ in range(8)]`
- Nest bundles for hierarchical interfaces: `lane = [PCIeLane() for _ in range(4)]`
- When one choice fixes pins on two sides of a part (both ends of a pass-through channel), put both sides in one bundle, so one mapping sets both. Two separate offers, one per side, can pick different channels for the two ends.

## The Provide/Require Architecture

Pin assignment uses a three-tier architecture:

```
Component            Circuit Wrapper          Application Circuit
┌──────────┐        ┌──────────────────┐      ┌───────────────────┐
│ GPIO[0]  │←──────→│ @provide(GPIO)   │      │                   │
│ GPIO[1]  │   maps │  maps bundle     │◄─────│ .require(GPIO)    │
│ GPIO[2]  │  pins  │  ports to pins   │      │  gets a bundle    │
│ GPIO[3]  │        │                  │      │  instance to wire │
└──────────┘        └──────────────────┘      └───────────────────┘
```

1. **Component** — defines physical pins (`Port()` class attributes)
2. **Circuit wrapper** — wraps the component, declares what interfaces it can provide and which pins map to each
3. **Application circuit** — calls `.require()` to acquire an interface, then wires its sub-ports

### The Mapping Return Type

Every `@provide` method returns a list of dictionaries. Each dictionary is one option and maps **bundle sub-ports → component pins**, every sub-port of the bundle in every option:

```python
@provide.one_of(I2C)
def provide_i2c(self, i2c: I2C) -> list[dict[Port, Port]]:
    return [
        {i2c.sda: self.mcu.GPIO[0], i2c.scl: self.mcu.GPIO[1]},  # Option A
        {i2c.sda: self.mcu.GPIO[2], i2c.scl: self.mcu.GPIO[3]},  # Option B
    ]
```

**The keys** are always sub-ports of the bundle parameter (`g.gpio`, `i2c.sda`, etc.).
**The values** are always component pins from `self.<component>.<port>`, or sub-ports of a bundle the provider requires from itself (see [Hierarchical Provider Composition](#hierarchical-provider-composition)).

### Carve-out from the anti-string-hacking rule

`jitx/SKILL.md` Don'ts say "don't key design state by hand-built strings" and "don't build intermediate `list[dict[str, Any]]` spec models." The `@provide` return type — `list[dict[Port, Port]]` — is the **carve-out**: the dict is keyed by Port objects (not strings), and the list is the framework's pin-mapping contract (not a parallel data model). Use this shape exactly when implementing `@provide` methods. Do **not** introduce string keys anywhere in the return value — keys are always Port objects from the bundle parameter. See `jitx/references/architectural-patterns.md` § "String-keyed dicts → structural objects" for the discriminator (key type), and § "Build the scene graph directly" for the general rule the carve-out exempts you from.

For a same-model self-critique pass on the pin-assignment code after writing, invoke `jitx-code-review`. Optional for single-task use.

## The Two APIs

### Decorator API (preferred for static configurations)

```python
from jitx.net import provide

class MCUCircuit(Circuit):
    @provide(GPIO)
    def provide_gpio(self, g: GPIO):
        return [{g.gpio: pin} for pin in self.mcu.GPIO]
```

### Constructor API (preferred for dynamic/computed port counts)

```python
class MCUCircuit(Circuit):
    def __init__(self, num_gpio: int = 8):
        self.mcu = MCU()
        pins = self.mcu.GPIO[:num_gpio]
        self.gpios = Provide(GPIO).all_of(lambda g: [{g.gpio: p} for p in pins])
```

**When to use which:**
- **Decorator**: Port count is known at class definition time
- **Constructor**: Port count depends on `__init__` parameters or runtime values. Store the result on `self`.

## Provider Patterns

### `@provide(Bundle)` — Multiple independent offers (all_of)

Creates one provider per mapping. Each can be independently assigned. Use for GPIO, where any pin can independently serve as a GPIO.

```python
@provide(GPIO)
def provide_gpio(self, g: GPIO):
    return [{g.gpio: pin} for pin in self.mcu.GPIO]
```

### `@provide.one_of(Bundle)` — Single selection from alternatives

Only ONE option from the returned list is selected. Use for peripheral pin muxing where an entire bus can appear on one pin group OR another, but not both.

```python
@provide.one_of(I2C)
def provide_i2c(self, i2c: I2C):
    return [
        {i2c.sda: self.mcu.GPIO[0], i2c.scl: self.mcu.GPIO[1]},  # Option A
        {i2c.sda: self.mcu.GPIO[2], i2c.scl: self.mcu.GPIO[3]},  # Option B
    ]
```

### `@provide.subset_of(Bundle, count)` — N from M

From the full set of mappings, at most `count` may be assigned. Use for resource-constrained scenarios (e.g., limited current budget across GPIO).

```python
@provide.subset_of(GPIO, 4)
def provide_gpio(self, g: GPIO):
    """8 GPIO pins available, but only 4 may be assigned."""
    return [{g.gpio: pin} for pin in self.mcu.GPIO]
```

### Constructor equivalents

```python
self.gpios = Provide(GPIO).all_of(lambda g: [{g.gpio: p} for p in pins])
self.i2c = Provide(I2C).one_of(lambda i2c: [
    {i2c.sda: self.mcu.GPIO[0], i2c.scl: self.mcu.GPIO[1]},
    {i2c.sda: self.mcu.GPIO[2], i2c.scl: self.mcu.GPIO[3]},
])
self.gpios = Provide(GPIO).subset_of(4, lambda g: [{g.gpio: p} for p in pins])
```

## Consuming Providers with `require()`

The consumer circuit calls `.require(BundleType)` on the provider circuit instance. This returns a bundle instance whose sub-ports are wired with `+`, like any other port. `require(BundleType, count=n)` returns a sequence of `n`. Keep the returned bundle in a local variable and store the nets: a `require()`d port stored on `self` fails the build with `Port <circuit>.<name> is a required port from <Provider> and should not be a member field of a circuit`. SI constraints on these nets need no `>>`; see [Constraints on Pin-Assigned Ports](#constraints-on-pin-assigned-ports).

```python
gpio = self.mcu_circuit.require(GPIO)  # local, never self.gpio
self.led_net = gpio.gpio + self.led.anode
i2c = self.mcu_circuit.require(I2C)
self.i2c_nets = [i2c.sda + self.sensor.SDA, i2c.scl + self.sensor.SCL]
```

Worked example, end to end (an RP2040 offering SPI and I2C from its datasheet's pin table, a circuit that requires both from it and nets them to a flash and an accelerometer, a shipping design with no routes, and verification designs with legal and illegal routes): `jitxexamples.jumpstart_kits.js3_pin_assignment.mcu_muxing`.

## Hierarchical Provider Composition

A provider can require from its own providers inside a `@provide` method (`self.require(...)`) and map the outer bundle onto what it gets back. Use it when parts of an interface are chosen independently: an MCU whose SDA and SCL each come from their own pin list, or a memory controller whose DQ bits move freely within a byte while the byte moves as a unit.

```python
@provide(I2C)
def provide_i2c(self, i2c: I2C) -> list[dict[Port, Port]]:
    sda = self.require(self.I2C_SDA)  # single-pin bundle, @provide.one_of over SDA pins
    scl = self.require(self.I2C_SCL)
    return [{i2c.sda: sda.p, i2c.scl: scl.p}]
```

Two SDA options and two SCL options give 4 I2C configurations; routing resolves the assignment to one of them.

**Key rules:**
- Inner Port classes are defined as nested classes on the Circuit, or in a module of their own
- `self.require()` inside `@provide` consumes the circuit's own providers
- The composed options stay open until the assignment is resolved

Worked pattern: `jitxexamples.components.mcus.raspberry_pi_RP2040` (I2C, SPI and UART composed from per-signal `one_of` pin lists).

## DiffPair P/N Polarity Swapping

**Only model P/N swap when the part or protocol explicitly supports it.** See [references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md) for per-protocol rules.

When the component has individual P/N pins, the Provide mapping can offer both polarities, one option each:

```python
{link.p: self.ic.TXP, link.n: self.ic.TXN},  # straight
{link.p: self.ic.TXN, link.n: self.ic.TXP},  # inverted
```

Worked pattern: `jitxexamples.patterns.pin_lane_polarity` (lane choice and P/N inversion on a provider that is one end of a constrained link, proven straight, inverted and illegal).

## Constraints on Pin-Assigned Ports

On jitx 4.6 an SI constraint (timing, insertion loss, intra-pair skew, skew against a reference) on a path through assigned pins is written on plain `+` nets. No `>>` is needed. `Topology(begin, end)` names the two ends, the runtime infers the path between them from the routes, and the constraint measures only once the pin assignment resolves. The rules:

1. Net the required bundle with `+` and keep it local. Store the nets on `self`, never the required port (see [Consuming Providers with `require()`](#consuming-providers-with-require)).
2. Give every part on the path with a path through it a `BridgingPinModel` between the two pins that path joins: a series resistor, an AC-coupling capacitor, an ESD channel whose datasheet gives an in-to-out path. Without one the path stops at that part, and the report names it: `No path for signal constraint from drv.o to rcv.o: the ends are only connected through the part between cap.a and cap.b, which has no pin model.` A flow-through package whose pin opposite the channel is n.c. (the trace runs under the package) is different: it has no path through it, so it gets no pin model, and the channel pin and the pin opposite it are one net, joined by board copper. A `BridgingPinModel` there passes every check while the board has an open line. A pin model's delay and loss come from the part's datasheet. A fixture or placeholder part says it is fictional in its docstring, and its values are labelled as given.
3. When one choice fixes pins on both sides of a pass-through part, offer a custom bundle that covers both sides, so one mapping moves both ends of the channel together.
4. Close the path in a verification design: a separate Design that instantiates the circuit, places its parts, and closes the path with code `Route`s that end on the provider's physical pins. Proof routes fix one mapping, so they never go in the product design, where they would remove the freedom the provider offers. A route cannot end on a required port: the build fails with `Using require ports as route ends at circuit.r[0] is not implemented`. The routes are what resolve the assignment. A route set that matches one offered mapping resolves to it, P/N inversion included. When the routes match no offered mapping, the conflicting routes are dropped (`Code route dropped: it conflicts with other connections`) and their leg has no path; a leg whose routes fit an offered mapping can still measure. With no routes, nothing resolves and nothing measures.
5. Pick the Topology ends by where the assigned part sits.
   - The assigned part is mid-path (a pass-through part whose channels are interchangeable): put the ends on fixed physical pins on either side, such as `Topology(self.drv.d[0], self.rcv.d[0])`. While the assignment is unresolved or illegal, the report says `No path for signal constraint from drv.d[0] to rcv.d[0]`. Worked pattern: `jitxexamples.patterns.pin_series_array`.
   - The provider is itself an end (a serializer's or PCIe switch's lanes, a DDR controller's byte lanes): the Topology begins on the required port. While the assignment is unresolved, the report says `Unassigned Pin on Path: nets[0].p`. Once routes resolve it, the measured line names the physical pin, such as `from src.u.a.n to conn.tx.p` for an inverted pair. Worked pattern: `jitxexamples.patterns.pin_lane_polarity`.
6. Skew across a bundle uses `ConstrainReferenceDifference`, whose guide must be a single pin (`Guide must be a single pin type`): guide on one leg, such as a strobe's `p` leg, never the `DiffPair`.
7. Prove it with design issues ([Step 3](#step-3-prove-constraints-with-design-issues)). A constraint counts as applied only when its group carries a Time, Loss or Skew measurement; whether it is met is `group.satisfied`.

### Daisy chains

`>>` (`TopologyNet`) is for a daisy chain whose order the autorouter must follow, such as a flyby clock. It is not part of constraining a pin-assigned path, and the timing, loss and skew constraints above bind without it.

## PCIe Lane Flexibility

Offer PCIe lane reversal, polarity inversion or a narrower link width only where the controller datasheet confirms it; the per-feature rules are in [references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md#pcie-lane-flexibility). A lane constraint begins on the required lane (rule 5 above); worked pattern: `jitxexamples.patterns.pin_lane_polarity`.

## DDR Byte/Bit Swapping

DDR controllers often allow bytes to move between byte slots and DQ bits to move within a byte. Model both as two levels of `provide`, not as `one_of` over bit permutations (8! = 40,320 options per byte):

- Bit swap: per byte slot, a single-pin bundle type of its own (`Slot0Bit`, `Slot1Bit`, ...), offered with `all_of` over the slot's eight DQ pins. Each slot needs its own type because `require()` matches an offer by bundle type: with one bit type shared by every slot, a byte's eight bits could resolve onto another slot's DQ pins, a cross-byte move the controller's rules forbid (PG313 for the Versal DDRMC).
- Byte swap: the bus bundle offered with `one_of`, one option per allowed byte-to-slot order. Inside the options callback, `self.require(SlotBit, count=8)` once per slot; each option maps the fixed pins, the slot's DQS and DM, and the byte's eight DQ ports to that slot's eight required bits.

```python
bits = [[b.p for b in self.require(bit, count=8)] for bit in SLOT_BITS]
for order in byte_orders:  # one option per allowed byte-to-slot order
    option = dict(fixed)
    for lane, slot in zip(lanes, order):
        option.update(zip(lane.dq, bits[slot]))  # DQS and DM map separately
    options.append(option)
```

Worked example: `jitxexamples.jumpstart_kits.js4_fpga_lpddr4x` (LPDDR4X on a Versal VP1002: the pin rules as data in `pinout`, the two-level offer in `fpga`, the timing constraints in `constraint`, legal and illegal proof routes in `proof`).

**Important rules:**
- DQS must stay with its byte lane (DQS0 always with byte lane 0's DQ bits)
- Address and command signals are NOT swappable — use fixed wiring
- CK polarity is NOT swappable — use fixed wiring
- Match each DQ to its strobe with `ConstrainReferenceDifference`, the strobe's `p` leg as the guide

For protocol-specific swap rules and constraint parameters, see [references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md).

## Common Mistakes

- Returning a port instead of a mapping list: `return self.mcu.GPIO[0]`. Return a list of `{bundle_port: component_pin}` dicts: `return [{g.gpio: self.mcu.GPIO[0]}]`.
- Assigning a required port instead of netting it: `self.led_pin = gpio.gpio` makes no connection. Use `+`: `self.led_net = gpio.gpio + self.led.anode`.
- `@provide.one_of(GPIO)` when several instances are wanted: it gives ONE GPIO in total. Use `@provide` (all_of) for independent instances.
- Building a net and not storing it: `tx.p + self.dst.INP.p` alone is built and discarded. Store it: `self.tx_net = tx + self.dst.INP`.
- Storing the required port on `self` (`self.tx = self.src.require(DiffPair)`): build error `... is a required port from ... and should not be a member field of a circuit`. Keep it local; store the nets and constraints.
- Routing to the required port (`Route(tx.p, self.dst.INP.p, layer=0)`): build error `Using require ports as route ends ... is not implemented`. Route the provider's physical pin (`Route(self.src.ic.TXP, self.dst.INP.p, layer=0)`); the route resolves the assignment.
- Adding `>>` to make a constraint bind (`self += tx.p >> self.dst.INP.p`). On 4.6 the constraint binds on plain nets once routes close the path; `>>` is for an ordered daisy chain.
- Offering a P/N swap the protocol does not allow, such as DDR4 DQS (`{dqs.p: self.ctrl.DQS_N, dqs.n: self.ctrl.DQS_P}`). DQS polarity is fixed; offer only the straight mapping.
- Offering a bit swap as `one_of` over every permutation of a byte's DQ bits. Use the two-level offer in [DDR Byte/Bit Swapping](#ddr-bytebit-swapping).
- Offering each side of a pass-through channel separately. One mapping must set both sides (a bundle over both).
- A `BridgingPinModel` across a flow-through package whose opposite pin is n.c. Net the two pins; there is no path through the part.
- Inventing a pin model's delay or loss. Take them from the part's datasheet; a fixture part says it is fictional in its docstring and labels its values as given.

## Verification

### Step 1: Type Check
```bash
pyright path/to/circuit.py
```

### Step 2: Build Test
```bash
jitx build <module.path.DesignClass>
```

Don't run parallel JITX builds against the same project — sequence them. See [Build safety: don't parallelize same-design work](../jitx/SKILL.md#build-safety-dont-parallelize-same-design-work).

The design-issue report (Step 3) groups its issues by category, such as signal constraint, topology and routing.

### Step 3: Prove constraints with design issues

A clean build says nothing about whether an SI constraint on a pin-assigned path applied. Run the check on a verification design: a separate Design whose parts are placed and whose code routes land on the provider's physical pins, fixing one mapping (see [Constraints on Pin-Assigned Ports](#constraints-on-pin-assigned-ports)). The product design keeps no proof routes, so its assignment stays open and its report shows `No path for signal constraint` or `Unassigned Pin` for these constraints until the board is routed.

Run this as a script from the project root while the project's runtime is running:

```python
import jitx

from mypkg.verify import VerifyDesign


def main() -> None:
    with jitx.runtime as rt:
        report = rt.submit(VerifyDesign).issues(satisfied=True, wait=30)
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

`satisfied=True` is required: without it, satisfied constraints are left out. `group.satisfied` is each check's verdict; the text reads the same met or unmet. A group of several issues shows only the first in `group.text`. The body stays in `main()` because design discovery imports the project's `.py` files. `jitx-interconnect-constraints` `references/verification.md` covers the rest of the report API.

| Report text | Meaning |
|---|---|
| `Time: 70.937ps - Target: ...`, `Skew: 0s - Target: ...`, `Loss: ...` | The assignment resolved and the constraint applied. Whether it is met is `group.satisfied`. |
| `No path for signal constraint from drv.d[0] to rcv.d[0]` | Ends on fixed pins around the assigned part, and the assignment did not resolve: no routes, or routes that match no offered mapping. |
| `Unassigned Pin on Path: nets[0].p` | The Topology ends on the required port, and the assignment did not resolve. |
| `Unconnected Topology on Path: choke.a_out, conn.rx.p` | A segment between the ends has no route yet. |
| `Code route dropped: it conflicts with other connections` | The routes matched no offered mapping; the conflicting routes were dropped. A leg whose routes fit an offered mapping can still measure. On a net with no SI constraint the text can read `Code route dropped: its ends are on different nets`. |
| `Missing Connection on Path: ...`, `Unable to find path for requested route` | A code route could not be made, for example because the parts are not placed. Place every part with `.at(...)` in the verification design. |
| `No path for signal constraint ... which has no pin model` | A part with a path through it needs a `BridgingPinModel`. |

Binding is not compliance: crossed routes on one layer can measure a skew outside its window. The constraint applied, and that routing fails it. To show the offered mappings are enforced, also run one routing that matches none of them: it must report a dropped route and no measurement for that leg.

## API Reference

For complete class definitions, all parameters, and method signatures:
- [Pin assignment concepts](https://docs.jitx.com/en/latest/essentials/design/pin_assignment.html)
- [jitx.net module (provide, Provide)](https://docs.jitx.com/en/latest/api/jitx.net.html)
- [jitx.si module (constraints)](https://docs.jitx.com/en/latest/api/jitx.si.html)

For protocol-specific pin flexibility rules, see [references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md).

## Formatting

```bash
ruff format path/to/circuit.py
```
