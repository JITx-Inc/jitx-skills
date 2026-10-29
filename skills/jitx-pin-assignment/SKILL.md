---
name: jitx-pin-assignment
description: "Use when the user asks about provide/require patterns, provide.one_of or provide.subset_of decorators, programmatic Provide, pin muxing, MCU peripherals on shared pins, DiffPair polarity swapping, PCIe lane swapping or width variants, DDR byte or bit swapping, LPDDR5 channel swapping, hierarchical provider composition, SI constraints on pin-assigned ports, constraints with provide/require, or flexible pin mapping for FPGAs and MCUs. Covers provide, Provide, require, all_of, one_of, subset_of, and protocol-specific pin flexibility with SI constraints."
---

# JITX Pin Assignment

Model flexible pin mappings between circuit-level interfaces and component-level pins. JITX's provide/require system lets a provider offer every mapping the part allows and leaves the choice open; routes on the provider's physical pins resolve it to one mapping.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

## Package Architecture

```python
# Pin assignment imports
from jitx.net import Port, DiffPair, provide, Provide

# Common bundles
from jitx.common import Power, GPIO

# Protocol bundles (for peripheral muxing)
from jitxlib.protocols.serial import I2C, SPI, UART

# SI constraint imports (for constraints on pin-assigned paths)
from jitx.si import (
    BridgingPinModel,
    Constrain,
    ConstrainDiffPair,
    ConstrainReferenceDifference,
    DiffPairConstraint,
    ReferencePlanes,
)
from jitx.net import Topology
from jitx.circuit import Route
from jitx.toleranced import Toleranced

# Core framework
from jitx import Circuit, Net
```

**These DO NOT EXIST — never import:**
`jitx.provide`, `jitx.providers`, `jitx.pin_assignment`, `jitx.assign`,
`jitx.net.provide_one_of`, `jitxlib.pin_assignment`, `jitx.pin_assign`

**Key locations:**
- `provide` (lowercase, decorator) is in `jitx.net`
- `Provide` (uppercase, constructor class) is in `jitx.net` (also re-exported from `jitx`)
- `GPIO` is in `jitx.common`
- `I2C`, `SPI`, `UART` are in `jitxlib.protocols.serial`
- All constraint classes are in `jitx.si`

## When to Use Pin Assignment

Use pin assignment when a component's physical pins can validly serve more than one logical role, and the choice should stay open until routing instead of being fixed in code.

**Use pin assignment for:**
- MCU GPIO — any of N pins can drive an LED, sensor, etc.
- Peripheral muxing — I2C/SPI/UART available on alternate pin groups
- DiffPair polarity: some protocols allow P/N swap (PCIe, where the controller supports polarity inversion)
- Lane ordering — PCIe lane reversal, width variants (x1/x2/x4)
- Byte/bit swapping — DDR controllers that support data bus reordering

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
from jitx.net import Port, DiffPair

class TXLink(Port):
    """Single TX differential pair."""
    tx = DiffPair()

class PCIeLane(Port):
    """Single PCIe lane: TX + RX diff pairs."""
    TX = DiffPair()
    RX = DiffPair()

class PCIeLink(Port):
    """Multi-lane PCIe link."""
    lane = [PCIeLane() for _ in range(4)]

class DDR4ByteLane(Port):
    """One DDR4 byte lane: DQ bits + strobe + mask."""
    DQ = [Port() for _ in range(8)]
    DQS = DiffPair()
    DM = Port()
```

**Rules for custom bundles:**
- Subclass `Port`, not `Circuit` or `Component`
- Sub-ports are class attributes (Port, DiffPair, or lists of them)
- Use lists for indexed groups: `DQ = [Port() for _ in range(8)]`
- Nest bundles for hierarchical interfaces: `lane = [PCIeLane() for _ in range(4)]`

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
 (physical)          (declares flexibility)    (consumes interface)
```

1. **Component** — defines physical pins (`Port()` class attributes)
2. **Circuit wrapper** — wraps the component, declares what interfaces it can provide and which pins map to each
3. **Application circuit** — calls `.require()` to acquire an interface, then wires its sub-ports

### The Mapping Return Type

Every `@provide` method returns a list of dictionaries. Each dictionary maps **bundle sub-ports → component pins**:

```python
@provide(GPIO)
def provide_gpio(self, g: GPIO):
    # g is a GPIO bundle instance — it has a .gpio sub-port
    # Each dict maps {bundle_sub_port: component_pin}
    return [
        {g.gpio: self.mcu.GPIO[0]},   # Option 1: GPIO[0] fulfills this GPIO
        {g.gpio: self.mcu.GPIO[1]},   # Option 2: GPIO[1] fulfills this GPIO
    ]

@provide.one_of(I2C)
def provide_i2c(self, i2c: I2C):
    # i2c has .sda and .scl — map BOTH in each option
    return [
        {i2c.sda: self.mcu.GPIO[0], i2c.scl: self.mcu.GPIO[1]},  # Option A
        {i2c.sda: self.mcu.GPIO[2], i2c.scl: self.mcu.GPIO[3]},  # Option B
    ]
```

**The keys** are always sub-ports of the bundle parameter (`g.gpio`, `i2c.sda`, etc.).
**The values** are always component pins from `self.<component>.<port>`.

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
from jitx.net import Provide

class MCUCircuit(Circuit):
    def __init__(self, num_gpio: int = 8):
        self.mcu = MCU()
        gpio_pins = self.mcu.GPIO[:num_gpio]
        self.gpios = Provide(GPIO).all_of(
            lambda g: [{g.gpio: pin} for pin in gpio_pins]
        )
```

**When to use which:**
- **Decorator**: Port count is known at class definition time
- **Constructor**: Port count depends on `__init__` parameters or runtime values

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
# all_of (same as @provide)
self.gpios = Provide(GPIO).all_of(lambda g: [{g.gpio: p} for p in pins])

# one_of (same as @provide.one_of)
self.i2c = Provide(I2C).one_of(lambda i2c: [
    {i2c.sda: self.mcu.GPIO[0], i2c.scl: self.mcu.GPIO[1]},
    {i2c.sda: self.mcu.GPIO[2], i2c.scl: self.mcu.GPIO[3]},
])

# subset_of (same as @provide.subset_of)
self.gpios = Provide(GPIO).subset_of(4, lambda g: [{g.gpio: p} for p in pins])
```

## Consuming Providers with `require()`

The consumer circuit calls `.require(BundleType)` on the provider circuit instance. This returns a bundle instance whose sub-ports are wired with `+`, like any other port. Keep the returned bundle in a local variable and store the nets: a `require()`d port stored on `self` fails the build with `Port <circuit>.<name> is a required port from <Provider> and should not be a member field of a circuit`. SI constraints on these nets need no `>>`; see [Constraints on Pin-Assigned Ports](#constraints-on-pin-assigned-ports).

```python
class AppCircuit(Circuit):
    def __init__(self):
        self.mcu_circuit = MCUCircuit()

        # Request a GPIO — returns a GPIO bundle instance
        gpio = self.mcu_circuit.require(GPIO)

        # Wire using the bundle's sub-ports with + (net) operator
        self.led_net = gpio.gpio + self.led.anode

        # Request an I2C — returns an I2C bundle instance
        i2c = self.mcu_circuit.require(I2C)

        # Wire both sub-ports
        self.sda_net = i2c.sda + self.sensor.SDA
        self.scl_net = i2c.scl + self.sensor.SCL
```

## Complete End-to-End Example

```python
"""MCU with GPIO pin assignment driving 2 LEDs."""

import jitx
from jitx import Circuit, Net
from jitx.common import GPIO, Power
from jitx.net import Port, provide
from jitxlib.parts import Resistor, Capacitor


class MCUComponent(jitx.Component):
    """8-pin MCU — physical component with pins."""
    VCC = Port()
    GND = Port()
    GPIO = [Port() for _ in range(4)]
    RESET = Port()
    NC = Port()
    # ... landpattern, symbol, mapping ...


class MCUCircuit(Circuit):
    """Wrapper that declares pin flexibility via @provide."""

    power = Power()

    @provide(GPIO)
    def provide_gpio(self, g: GPIO):
        """Any of 4 GPIO pins can independently serve as GPIO."""
        return [{g.gpio: pin} for pin in self.mcu.GPIO]

    def __init__(self):
        self.mcu = MCUComponent()
        self.VCC = Net(name="VCC")
        self.GND = Net(name="GND")
        self.VCC += self.power.Vp + self.mcu.VCC
        self.GND += self.power.Vn + self.mcu.GND

        self.c_bypass = Capacitor(capacitance=100e-9)
        self.c_bypass.insert(self.mcu.VCC, self.mcu.GND, short_trace=True)

        self.r_reset = Resistor(resistance=10e3)
        self.r_reset.insert(self.mcu.VCC, self.mcu.RESET)


class LEDDriverApp(Circuit):
    """Application that consumes GPIOs to drive LEDs."""

    vin = Power()

    def __init__(self):
        self.GND = Net(name="GND")
        self.VCC = Net(name="VCC")
        self.GND += self.vin.Vn
        self.VCC += self.vin.Vp

        # Instantiate the provider circuit
        self.mcu = MCUCircuit()
        self.VCC += self.mcu.power.Vp
        self.GND += self.mcu.power.Vn

        # Consume GPIOs; which physical pin each gets is resolved from routing
        self.r_leds = []
        for i in range(2):
            gpio = self.mcu.require(GPIO)
            r = Resistor(resistance=330.0)
            self.r_leds.append(r)
            r.insert(gpio.gpio, ...)  # wire to LED anode

Device = LEDDriverApp
```

## Hierarchical Provider Composition

Providers that internally require from sub-providers. Use for peripheral muxing where signals (SDA, SCL) can be independently selected from different pin options.

```python
class MCUCircuit(Circuit):
    power = Power()

    # Step 1: Define inner bundle types for each muxed signal
    class I2C_SDA(Port):
        p = Port()

    class I2C_SCL(Port):
        p = Port()

    # Step 2: Provide each signal independently with one_of
    @provide.one_of(I2C_SDA)
    def provide_sda(self, sda: I2C_SDA):
        return [{sda.p: self.mcu.GPIO[0]}, {sda.p: self.mcu.GPIO[2]}]

    @provide.one_of(I2C_SCL)
    def provide_scl(self, scl: I2C_SCL):
        return [{scl.p: self.mcu.GPIO[1]}, {scl.p: self.mcu.GPIO[3]}]

    # Step 3: Compose into the real I2C bundle
    @provide(I2C)
    def provide_i2c(self, i2c: I2C):
        sda = self.require(self.I2C_SDA)  # self.require() consumes own providers
        scl = self.require(self.I2C_SCL)
        return [{i2c.sda: sda.p, i2c.scl: scl.p}]

    def __init__(self):
        self.mcu = MCUComponent()
        # ... power wiring ...
```

This creates 4 possible I2C configurations (2 SDA options x 2 SCL options); routing resolves the assignment to one of them.

**Key rules:**
- Inner Port classes are defined as nested classes on the Circuit
- `self.require()` inside `@provide` consumes the circuit's own providers
- The composed options stay open until the assignment is resolved

## DiffPair P/N Polarity Swapping

**Only model P/N swap when the part or protocol explicitly supports it.** See [references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md) for per-protocol rules.

When the component has individual P/N pins (not a DiffPair bundle), the Provide mapping can offer both polarities:

```python
class TXLink(Port):
    tx = DiffPair()

class FlexTXCircuit(Circuit):
    @provide.one_of(TXLink)
    def provide_tx(self, link: TXLink):
        return [
            {link.tx.p: self.ic.TXP, link.tx.n: self.ic.TXN},  # Normal
            {link.tx.p: self.ic.TXN, link.tx.n: self.ic.TXP},  # Swapped
        ]
```

## Constraints on Pin-Assigned Ports

On jitx 4.6 an SI constraint (timing, insertion loss, intra-pair skew, skew against a reference) on a path through assigned pins is written on plain `+` nets. No `>>` is needed. `Topology(begin, end)` names the two ends, the runtime infers the path between them from the routes, and the constraint measures only once the pin assignment resolves. The rules:

1. Net the required bundle with `+` and keep it local. Store the nets on `self`, never the required port (see [Consuming Providers with `require()`](#consuming-providers-with-require)).
2. Give every pass-through part on the path a `BridgingPinModel` between its two ports (an ESD channel's in and out pins, an AC-coupling cap's two pins). Without one the path stops at that part, and the report names it: `No path for signal constraint from drv.o to rcv.o: the ends are only connected through the part between cap.a and cap.b, which has no pin model.`
3. Close the path in a verification design: a separate Design that instantiates the circuit, places its parts, and closes the path with code `Route`s that end on the provider's physical pins. Proof routes fix one mapping, so they never go in the product design, where they would remove the freedom the provider offers. A route cannot end on a required port: the build fails with `Using require ports as route ends at circuit.r[0] is not implemented`. The routes are what resolve the assignment. A route set that matches one offered mapping resolves to it, P/N inversion included. When the routes match no offered mapping, the conflicting routes are dropped (`Code route dropped: it conflicts with other connections`) and their leg has no path; a leg whose routes fit an offered mapping can still measure. With no routes, nothing resolves and nothing measures.
4. Pick the Topology ends by where the assigned part sits.
   - The assigned part is mid-path (an ESD array): put the ends on fixed physical pins on either side, such as `Topology(self.host.usb, self.conn.usb)`. While the assignment is unresolved or illegal, the report says `No path for signal constraint from host.usb.p to conn.usb.p`.
   - The provider is itself an end (a PCIe switch's lanes, a DDR controller's byte lanes): the Topology begins on the required port. While the assignment is unresolved, the report says `Unassigned Pin on Path: nets[0].p`. Once routes resolve it, the measured line names the physical pin, such as `from src.u.a.p to conn.tx.p`.
5. Prove it with design issues ([Step 3](#step-3-prove-constraints-with-design-issues)). A constraint counts as applied only when its group carries a Time, Loss or Skew measurement; whether it is met is `group.satisfied`.

### Worked example: USB 2.0 through a channel-swappable ESD array

A USB 2.0 pair runs from a host to a connector through a 4-channel flow-through ESD array (each channel an in pin and an out pin on opposite sides). The routing freedom is which ESD channels carry D+ and D-: pair (1, 2) or (3, 4), either way round. USB 2.0 polarity is fixed end to end, so host D+ always reaches connector D+; only the channel choice is free.

One choice fixes pins on both sides of the part, so the provider offers a custom bundle that covers both sides. A plain `DiffPair` provide cannot say "the connector side uses the same channel as the host side".

```python
from jitx.circuit import Circuit, Route
from jitx.component import Component
from jitx.net import DiffPair, Net, Port, Topology, provide
from jitx.si import BridgingPinModel, ConstrainDiffPair
from jitxlib.protocols.usb import USB

OFFERED = ((0, 1), (1, 0), (2, 3), (3, 2))  # (D+ channel, D- channel), 0-based


class FlowThroughEsd4(Component):
    """4-channel flow-through ESD array: ch_in[i] passes straight to ch_out[i]."""

    ch_in = [Port() for _ in range(4)]
    ch_out = [Port() for _ in range(4)]
    gnd = Port()

    def __init__(self) -> None:
        # ... landpattern and symbol ...
        # Each channel is a pass-through: without a pin model the path stops here.
        # Delay and loss come from the part's datasheet. A fixture or
        # placeholder part says it is fictional in its docstring, and its
        # values are labelled as given.
        self.channel_models = [
            BridgingPinModel(self.ch_in[i], self.ch_out[i], delay=ESD_DELAY, loss=ESD_LOSS)
            for i in range(4)
        ]


class ProtectedPair(Port):
    """A D+/D- pair through one ESD channel pair: host side and connector side."""

    host = DiffPair()
    conn = DiffPair()


class EsdProtection(Circuit):
    gnd = Port()

    def __init__(self) -> None:
        self.esd = FlowThroughEsd4()  # unplaced: placement is the board's choice
        self.gnd_net = self.gnd + self.esd.gnd

    @provide.one_of(ProtectedPair)
    def protected_pair(self, pair: ProtectedPair) -> list[dict[Port, Port]]:
        # One mapping moves both sides of the channel together.
        return [
            {
                pair.host.p: self.esd.ch_in[p],
                pair.host.n: self.esd.ch_in[n],
                pair.conn.p: self.esd.ch_out[p],
                pair.conn.n: self.esd.ch_out[n],
            }
            for p, n in OFFERED
        ]


class UsbThroughEsd(Circuit):
    """The product module: unplaced and route-free, so the assignment stays open."""

    def __init__(self) -> None:
        self.host = UsbHost()
        self.conn = UsbConnector()
        self.prot = EsdProtection()

        pair = self.prot.require(ProtectedPair)  # local, never self.pair
        self.nets = [
            self.host.usb.p + pair.host.p,
            self.host.usb.n + pair.host.n,
            pair.conn.p + self.conn.usb.p,
            pair.conn.n + self.conn.usb.n,
        ]
        self.gnd = Net([self.host.gnd, self.prot.gnd, self.conn.gnd], name="GND")

        # Fixed physical ends either side of the assigned pins.
        self.usb_constraint = (
            ConstrainDiffPair(Topology(self.host.usb, self.conn.usb))
            .timing_difference(USB.v2.skew)
            .timing(TIMING_BUDGET)
            .structure(substrate.DRS_90)
        )


# Verification design: everything below is proof scaffolding and never goes in
# the product. It places the module's parts and routes one mapping.
ChannelPair = tuple[int, int]  # (D+ channel, D- channel), 0-based


class UsbThroughEsdProof(Circuit):
    """The module, placed, with code routes landing on chosen ESD channels."""

    def __init__(self, host_channels: ChannelPair, conn_channels: ChannelPair) -> None:
        self.dut = UsbThroughEsd()
        dut, esd = self.dut, self.dut.prot.esd
        # Unplaced parts give Missing Connection instead of a measurement.
        dut.host.at(-12, 0)
        esd.at(0, 0)
        dut.conn.at(12, 0)

        # Proof routes end on the ESD part's physical pins and fix one mapping.
        hp, hn = host_channels
        cp, cn = conn_channels
        self.routes = [
            Route(dut.host.usb.p, esd.ch_in[hp], layer=0),
            Route(dut.host.usb.n, esd.ch_in[hn], layer=0),
            Route(esd.ch_out[cp], dut.conn.usb.p, layer=0),
            Route(esd.ch_out[cn], dut.conn.usb.n, layer=0),
        ]


class VerifyUsbThroughEsd(ProjectDesign):  # your project's Design subclass
    """D+ on channel 1, D- on channel 2, both sides."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsdProof(host_channels=(0, 1), conn_channels=(0, 1))
```

`USB.v2.skew` is jitxlib-standard's USB 2.0 intra-pair skew limit, `Toleranced(0, 3.75e-12)`. `ESD_DELAY`, `ESD_LOSS` and `TIMING_BUDGET` come from the part's datasheet and the design's budget; for a fixture or placeholder part, label the part fictional and its values as given. `substrate.DRS_90` comes from your substrate (USB 2.0 asks for 90 ohm differential).

The verification design with five routings (each row sets `host_channels` and `conn_channels`; the last row leaves the routes out), run on jitx 4.6.0rc10 against runtime 4.6.0-rc.16 with a fictional ESD part (3 ps and 0.05 dB per channel) on `jitx.sample.SampleSubstrate`. The runnable version is this repository's `evals/cases/reference/usb-through-esd-swap/` case.

| Routes (D+, D- channel; host side / connector side) | What the design issues report holds |
|---|---|
| (1, 2) / (1, 2), offered | `Time: 112.879ps` on each leg, `Skew: 0s - Target: ± 3.75ps` |
| (4, 3) / (4, 3), offered, inverted | `Time: 115.823ps` and `137.724ps`, `Skew: 21.9ps - Target: ± 3.75ps` |
| (1, 3) / (1, 3), splits the pairs | `Code route dropped: it conflicts with other connections`; D- measures alone; `No path for signal constraint from host.usb.p to conn.usb.p`; no skew |
| (1, 2) / (3, 4), sides disagree | `Code route dropped`; `No path for signal constraint` on both legs; nothing measured |
| none | `No path for signal constraint` on both legs; nothing measured |

Binding is not compliance. The inverted routing measures 21.9 ps of skew against a 3.75 ps limit, from its crossed D+/D- routes on one layer. The constraint applied, and the routing violates it. A measurement means the constraint bound; whether it passed is `group.satisfied`, not the printed text.

### PCIe pattern: lane providers + per-lane constraints

The switch is the provider and one end of each lane, so each Topology begins on the required lane. This pattern has not been run on the 4.6 runtime; the USB example's reference case has.

```python
link = self.switch.require(PCIeLink)  # local, never self.link
self.lane_nets = [link.lane[i].TX + self.endpoints[i].INP for i in range(num_lanes)]

# Illustrative limits: take skew and loss from the PCIe generation's specification.
self.lane_cst = DiffPairConstraint(skew=Toleranced(0, 5e-12), loss=3.0)
with ReferencePlanes(self.GND):
    for i in range(num_lanes):
        self.lane_cst.constrain(link.lane[i].TX, self.endpoints[i].INP)

# Routes from the switch's physical lane pins (self.switch.sw.PTXP[k], PTXN[k])
# to each endpoint resolve the lane mapping; until then each lane reports
# Unassigned Pin.
```

### DDR4 pattern: byte swap + DQ-to-DQS matching

`ConstrainReferenceDifference` needs a single-pin guide (`Guide must be a single pin type`), so the guide is the strobe's `p` leg, not the `DQS` pair. This pattern has not been run on the 4.6 runtime, in particular a guide that begins on a required sub-port; prove it in a verification design before relying on it.

```python
data = self.controller.require(DDR4Data)  # local, never self.data
self.data_nets = []
self.dq_to_dqs = []

with ReferencePlanes(self.GND):
    for bl in range(2):
        lane = data.byte_lane[bl]
        offset = bl * bits_per_lane

        self.data_nets += [
            lane.DQS.p + self.mem.DQS_P[bl],
            lane.DQS.n + self.mem.DQS_N[bl],
        ]
        self.data_nets += [
            lane.DQ[i] + self.mem.DQ[offset + i] for i in range(bits_per_lane)
        ]

        # Match each DQ to its strobe (illustrative 20 ps; take the window
        # from the controller and memory datasheets).
        self.dq_to_dqs.append(
            ConstrainReferenceDifference(
                guide=Topology(lane.DQS.p, self.mem.DQS_P[bl]),
                topologies=[
                    Topology(lane.DQ[i], self.mem.DQ[offset + i])
                    for i in range(bits_per_lane)
                ],
            ).timing_difference(Toleranced(0, 20e-12))
        )
```

Routes on the controller's physical `DQ`, `DQS_P` and `DQS_N` pins resolve which byte mapping is used.

### Daisy chains

`>>` (`TopologyNet`) is for a daisy chain whose order the autorouter must follow, such as a flyby clock. It is not part of constraining a pin-assigned path, and the timing, loss and skew constraints above bind without it.

## PCIe Lane Flexibility

Model PCIe width variants and lane flexibility using the constructor `Provide` API. The component has individual P/N pins per lane; the Provide mapping connects them to DiffPair bundle sub-ports.

```python
class PCIeSwitchCircuit(Circuit):
    def __init__(self):
        self.sw = PCIeSwitchComponent()

        # x4 link using all 4 lanes
        self.pcie_x4 = Provide(PCIeLink4).one_of(
            lambda b: [self._create_mapping(b, lane_offset=0)]
        )

        # x2 links: lanes 0-1 or lanes 2-3
        self.pcie_x2 = Provide(PCIeLink2).one_of(
            lambda b: [
                self._create_mapping(b, lane_offset=0),
                self._create_mapping(b, lane_offset=2),
            ]
        )

    def _create_mapping(self, b, lane_offset: int) -> dict:
        mapping = {}
        for i in range(len(b.lane)):
            mapping[b.lane[i].TX.p] = self.sw.PTXP[i + lane_offset]
            mapping[b.lane[i].TX.n] = self.sw.PTXN[i + lane_offset]
            mapping[b.lane[i].RX.p] = self.sw.PRXP[i + lane_offset]
            mapping[b.lane[i].RX.n] = self.sw.PRXN[i + lane_offset]
        return mapping
```

## DDR4 Byte/Bit Swapping

DDR4 controllers often support byte lane reordering and bit swapping within a byte lane. Model with `Provide().one_of()`:

```python
class DDR4ControllerCircuit(Circuit):
    def __init__(self):
        self.ctrl = DDR4ControllerComponent()

        self.data_provide = Provide(DDR4Data).one_of(
            lambda b: [
                self._create_mapping(b, byte_swap=False),
                self._create_mapping(b, byte_swap=True),
            ]
        )

    def _create_mapping(self, b: DDR4Data, byte_swap: bool) -> dict:
        mapping = {}
        phys = [1, 0] if byte_swap else [0, 1]
        for logical in range(2):
            p = phys[logical]
            for i in range(8):
                mapping[b.byte_lane[logical].DQ[i]] = self.ctrl.DQ[p * 8 + i]
            mapping[b.byte_lane[logical].DQS.p] = self.ctrl.DQS_P[p]
            mapping[b.byte_lane[logical].DQS.n] = self.ctrl.DQS_N[p]
            mapping[b.byte_lane[logical].DM] = self.ctrl.DM[p]
        return mapping
```

**Important rules:**
- DQS must stay with its byte lane (DQS0 always with byte lane 0's DQ bits)
- Address and command signals are NOT swappable — use fixed wiring
- CK polarity is NOT swappable — use fixed wiring

For protocol-specific swap rules and constraint parameters, see [references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md).

## Common Mistakes

```python
# WRONG: Returning the port directly instead of a mapping list
@provide(GPIO)
def provide_gpio(self, g: GPIO):
    return self.mcu.GPIO[0]  # WRONG: must return list of dicts

# CORRECT: Return list of {bundle_port: component_port} dicts
@provide(GPIO)
def provide_gpio(self, g: GPIO):
    return [{g.gpio: self.mcu.GPIO[0]}]

# WRONG: Using = to connect required ports (Python assignment)
gpio = self.mcu.require(GPIO)
self.led_pin = gpio.gpio  # WRONG: assignment, not connection

# CORRECT: Use + to create a net
self.led_net = gpio.gpio + self.led.anode

# WRONG: Using @provide.one_of when you want multiple instances
@provide.one_of(GPIO)  # Only gives ONE GPIO total
def provide_gpio(self, g: GPIO):
    return [{g.gpio: p} for p in self.mcu.GPIO]

# CORRECT: Use @provide (all_of) for multiple independent instances
@provide(GPIO)
def provide_gpio(self, g: GPIO):
    return [{g.gpio: p} for p in self.mcu.GPIO]

# WRONG: Net not stored (silently dropped)
tx = self.src.require(TXLink)
tx.tx.p + self.dst.INP.p  # BAD: the net is built and discarded

# CORRECT: Store the net on self
self.tx_net = tx.tx + self.dst.INP

# WRONG: Storing the required port on self (build error: "... is a required
# port from ... and should not be a member field of a circuit")
self.tx = self.src.require(TXLink)

# CORRECT: Keep the required port local; store the nets and constraints
tx = self.src.require(TXLink)
self.tx_net = tx.tx + self.dst.INP

# WRONG: Routing to the required port (build error: "Using require ports as
# route ends ... is not implemented")
self.routes = [Route(tx.tx.p, self.dst.INP.p, layer=0)]

# CORRECT: Route the provider's physical pin; the route resolves the assignment
self.routes = [Route(self.src.ic.TXP, self.dst.INP.p, layer=0)]

# WRONG: Adding >> to make a constraint bind. On 4.6 the constraint binds on
# plain nets once routes close the path; >> is for an ordered daisy chain.
self += tx.tx.p >> self.dst.INP.p

# WRONG: Modeling P/N swap for a protocol that doesn't support it
# DDR4 DQS polarity is FIXED — never swap
@provide.one_of(DDR4DQS)
def provide_dqs(self, dqs: DDR4DQS):
    return [
        {dqs.p: self.ctrl.DQS_P, dqs.n: self.ctrl.DQS_N},
        {dqs.p: self.ctrl.DQS_N, dqs.n: self.ctrl.DQS_P},  # WRONG: not swappable
    ]
```

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

`satisfied=True` is required: without it, satisfied constraints are left out. `group.satisfied` is each check's verdict; the text reads the same met or unmet. A group of several issues shows only the first in `group.text`. The body stays in `main()` because design discovery imports every `.py` in the project. `jitx-interconnect-constraints` `references/verification.md` covers the rest of the report API.

| Report text | Meaning |
|---|---|
| `Time: 112.879ps - Target: ...`, `Skew: 0s - Target: ...`, `Loss: ...` | The assignment resolved and the constraint applied. Whether it is met is `group.satisfied`. |
| `No path for signal constraint from host.usb.p to conn.usb.p` | Ends on fixed pins around the assigned part, and the assignment did not resolve: no routes, or routes that match no offered mapping. |
| `Unassigned Pin on Path: nets[0].p` | The Topology ends on the required port, and the assignment did not resolve. |
| `Code route dropped: it conflicts with other connections` | The routes matched no offered mapping; the conflicting routes were dropped. A leg whose routes fit an offered mapping can still measure. |
| `Missing Connection on Path: ...`, `Unable to find path for requested route` | A code route could not be made, for example because the parts are not placed. Place every part with `.at(...)` in the verification design. |
| `No path for signal constraint ... which has no pin model` | A pass-through part on the path needs a `BridgingPinModel`. |

To show the offered mappings are enforced, also run one routing that matches none of them: it must report a dropped route and no measurement for that leg.

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
