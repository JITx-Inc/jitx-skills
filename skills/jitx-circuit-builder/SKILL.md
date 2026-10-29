---
name: jitx-circuit-builder
description: "Use when the user asks to \"wire up\", \"connect\", \"build a circuit\", create an \"application circuit\", declare a circuit's typed ports or bundles (Power, I2C, RGMII), compose sub-circuits into a hierarchy and connect them port to port, \"place components\" or sub-circuits (fixed or floating), add passives (resistors, capacitors, inductors) or decoupling, or set up power connections. Covers the Circuit class, nets, the + and >> operators, typed ports, hierarchy, placement, and jitxlib-parts passives. Drawing a pour or copper is jitx-physical-layout; pour rules are jitx-layout-constraints; provide/require pin assignment is jitx-pin-assignment."
---

# JITX Circuit Builder

A `Circuit` composes components and sub-circuits behind typed boundary ports. Verify every import with pyright, test each circuit with `jitx.test.TestCase` and build it as the base `jitx` skill describes (Writing good code, Running designs). For a self-critique pass, invoke `jitx-code-review`.

## Circuit skeleton

```python
from jitx import Circuit, Net
from jitx.common import Power
from jitx.net import ShortTrace
from jitx.units import V, kohm, nF
from jitxlib.parts import AtLeast, AtMost, Capacitor, Resistor
from jitxlib.protocols.serial import I2C

from .sensor import Sensor  # a jitx.Component


class SensorCircuit(Circuit):
    vin = Power()  # boundary ports: typed class attributes
    i2c = I2C()

    def __init__(self) -> None:
        self.u1 = Sensor()
        self.GND = Net([self.vin.Vn, self.u1.GND], name="GND")
        self.VDD = Net([self.vin.Vp, self.u1.VDD], name="VDD")
        self.c_vdd = Capacitor(
            capacitance=100 * nF,
            rated_voltage_dc=AtLeast(10 * V),
            temperature_coefficient_code="X7R",
        )
        self.c_vdd_st = ShortTrace(self.c_vdd.p1, self.u1.VDD)
        self.GND += self.c_vdd.p2
        self.r_pu = [Resistor(resistance=4.7 * kohm, tolerance=AtMost(0.01)) for _ in range(2)]
        self.bus = [
            self.i2c.sda + self.u1.SDA + self.r_pu[0].p1,
            self.i2c.scl + self.u1.SCL + self.r_pu[1].p1,
        ]
        self.VDD += Net([r.p2 for r in self.r_pu])
```

## Key rules

1. Store every component and every net expression on `self`, singly or in a list attribute. An unstored `a + b` is a lost connection; a component no attribute holds earns only a logged warning, `Reference to structural object ... lost during instantiation`.
2. Boundary ports are class attributes. Components, nets and wiring go in `__init__`, with no `build()` or `circuit()` methods.
3. Subclass `Circuit` for a circuit and `jitx.Component` for a part.
4. Never alias a component's port (`self.x = self.r1.p2`): the build fails with `Child object ... has multiple parents`. To expose a pin, net it to a boundary port.
5. A named net and a public port share one namespace, so name them differently (port `pwr_vccint`, net `VCCINT`).

## Anti-string-hacking

Construct JITX objects directly. Do not build a `list[dict[str, Any]]` spec and walk it to emit JITX calls (batch parameters in a frozen dataclass), and do not add to a circuit from a free function (compose a `Container` member). Worked examples: the base skill's Don'ts and `jitx/references/architectural-patterns.md`.

## Typed ports and composition

A circuit's boundary is typed ports: `Power` from `jitx.common` (members `Vp`, `Vn`), and protocol bundles such as `I2C` and `SPI` (`jitxlib.protocols.serial`), `RGMII` and `MIIM` (`jitxlib.protocols.ethernet.mii.rgmii`, `.miim`) and `MDI1000BaseT` (`jitxlib.protocols.ethernet.mdi.mdi1000base_t`). Bundle classes live in `jitxlib.protocols` and `jitx.common`; find one with the base skill's Introspection and read its class for the members. Never write member names from memory, and check constructor options (`SPI(cs=True)` adds `cs`).

A port nets only to a port of the same concrete type and parameters: `+` between two `Power` ports joins them member for member, and `Power + I2C` raises `ValueError: Incompatible ports on Net`. Use `>>` where order matters or an SI constraint will apply; a constraint needs a topology even between two ports (`jitx-interconnect-constraints`).

```python
class EthernetPort(Circuit):
    vin = Power()
    rgmii = RGMII()
    miim = MIIM()

    def __init__(self) -> None:
        self.reg = RegulatorCircuit()  # each sub-circuit declares its own ports
        self.phy = PhyCircuit()
        self.jack = RJ45Circuit()
        self.rails = [self.vin + self.reg.vin, self.reg.vout + self.phy.vin]
        self.mac_side = [self.rgmii + self.phy.rgmii, self.miim + self.phy.miim]
        self.mdi = self.phy.mdi >> self.jack.mdi
```

A parent wires its children's boundary ports to each other and to its own. It never reaches into a child's components, and a child never reaches up: a pin the parent needs is a boundary port of the child. Pin assignment through `provide`/`require` is `jitx-pin-assignment`.

## Placement

```python
self.reg = RegulatorCircuit().at(10, 5, rotate=90)  # fixed, in this circuit's frame
self.jack = RJ45().at(0, 0, on=Side.Bottom)  # Side from jitx.layerindex
self.phy = PhyCircuit().at(floating=True)  # Circuit only: placed interactively
```

`.at(...)` sets the instance's own transform in its parent's frame. A sub-circuit without `.at` sits at its parent's origin on top, so one meant for interactive placement takes `.at(floating=True)`. Placement relative to another instance (`Circuit.place`), code-placed vias and copper are `jitx-physical-layout`.

## Nets

`Net(...)` takes one iterable of ports, so a whole rail goes on in one call; a bare port raises `TypeError`. Name power and ground nets. Net symbols (`PowerSymbol()`, `GroundSymbol()` from `jitxlib.symbols.net_symbols`, as `symbol=` or `net.symbol = ...`) join a rail across schematic pages without drawn wires, and belong in the top-level design only: the base skill's grep gates fail them outside `TOP_LEVEL_PATH` (default `designs/`).

`+=` takes a port or a `Net`, never a bare list, so wrap a rail list in `Net(...)`:

```python
self.GND = Net([*self.u1.GND, *self.u1.RSVDGND], name="GND")
self.GND += [*self.u1.AGND]  # WRONG
self.GND += Net([*self.u1.AGND])  # RIGHT
```

pyright reports the wrong form (`Operator "+=" not supported for types "Net[Port]" and "list[Port]"`). Onto an empty net the list is stored as one member: a `TestCase` passes and the build fails with `TypeError: unhashable type: 'list'`. Onto a net that holds ports it raises at instantiation, `InstantiationException` wrapping `ValueError: Incompatible ports on Net: Port and list`.

### Asserting connectivity in tests

Assert membership over `list(net)`, never with `in`: `Net.__contains__` stops at the first nested net, so a port after it reports `False` while iteration finds it. Count as well as contain, since `len(list(net))` against the expected count catches a rail that lost half its balls:

```python
self.assertIn(self.u1.VCCINT[0], list(circuit.V1V0))
self.assertEqual(len(list(circuit.GND)), 30)
```

A bundle net lists its bundles (both `Power` ports, say). Assert that, then assert inside each child that its boundary member reaches the component pin.

## Passives

`Resistor`, `Capacitor` and `Inductor` from `jitxlib.parts` take `jitx.units` quantities (`10 * kohm`, `100 * nF`, `4.7 * uH`; a bare number is ohms, farads or henries). Bounds are `AtLeast` and `AtMost` from `jitxlib.parts`; a bare value is an exact match. The project's provider chain resolves them: base skill Install Step 2 and [Parts and Providers](https://docs.jitx.com/en/latest/essentials/design/parts.html).

Filter only on keys the approved CSV has a column for; read its header. On a key with no column the CSV declines the query, which falls through to `ideal`, and `ideal` ignores the key: the constraint is silently dropped until `ideal` leaves the chain. Where the CSV lacks a column the design needs (a resistor's temperature coefficient, say), ask for the column rather than writing the key.

State what the circuit depends on:

- `tolerance=AtMost(0.01)` on every passive whose value matters.
- `temperature_coefficient_code="X7R"` (or `"X5R"`, `"C0G"`) on every ceramic. Unconstrained, a query can return Y5V or Z5U, which lose most of their capacitance across temperature and DC bias.
- `rated_voltage_dc=AtLeast(...)` with DC-bias derating: 10 V or 16 V on a 3.3 V rail, not 6.3 V.

For a divider, pick the bottom resistor from the current budget and snap it to a named series (E96 unless the request says otherwise), compute the top from the datasheet equation and snap it, then recompute the output. Its worst-case error is the rounding error, plus each resistor's tolerance times (1 - Vref/Vout), plus the reference's datasheet accuracy; state it against the rail's tolerance.

## Decouple against the pins

A power-rail capacitor is its own attribute on `self`, its supply-side pad joins the pin it serves through `ShortTrace(self.c_x.p1, <the IC power pin port>)` and its other pad joins the return net. `jitx.net.ShortTrace(p1, p2)` takes two ports, never a net: a net has no position, only the pin does, and pyright rejects a net argument. Bootstrap capacitors follow the same rule.

Scale with the pin count. Two caps on a 96-ball core net are two caps for ninety-six balls:

```python
self.c_vccint = [
    Capacitor(capacitance=100 * nF, rated_voltage_dc=AtLeast(10 * V), temperature_coefficient_code="X7R")
    for _ in fpga.VCCINT
]
self.c_vccint_st = [
    ShortTrace(c.p1, ball) for c, ball in zip(self.c_vccint, fpga.VCCINT, strict=True)
]
self.GND += Net([c.p2 for c in self.c_vccint])
```

One HF cap per one or two core balls, plus bulk per rail, is the starting point. Fewer is a decision to state, with the count the design really wants.

## Extract the repeated block at the second instance

Three regulator stages that differ only in output voltage are one `Circuit` subclass instantiated three times, not three copies. The same holds for per-rail decoupling banks. If two blocks differ only in their arguments, they are one subcircuit with a parameter, and a difference the copies have drifted apart on is the bug this rule prevents.
