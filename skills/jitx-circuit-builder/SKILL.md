---
name: jitx-circuit-builder
description: "Use when the user asks to \"wire up\", \"connect\", \"build a circuit\", create an \"application circuit\", declare a circuit's typed ports or bundles (Power, I2C, RGMII), compose sub-circuits into a hierarchy and connect them port to port, \"place components\" or sub-circuits (fixed or floating), add passives (resistors, capacitors, inductors) or decoupling, or set up power connections. Covers the Circuit class, nets and the + operator, typed ports, hierarchy, placement, and jitxlib-parts passives. Drawing a pour or copper is jitx-physical-layout; pour rules are jitx-layout-constraints; provide/require pin assignment is jitx-pin-assignment."
---

# JITX Circuit Builder

A `Circuit` composes components and sub-circuits behind typed boundary ports. Verify, test and build each circuit as the base `jitx` skill describes (Writing good code, Running designs).

## Circuit skeleton

```python
from jitx import Circuit, Net
from jitx.common import Power
from jitx.net import ShortTrace
from jitx.units import V, nF
from jitxlib.parts import AtLeast, Capacitor
from jitxlib.protocols.serial import I2C

from .sensor import Sensor  # a jitx.Component


class SensorCircuit(Circuit):
    vin = Power()
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
        self.SDA = self.i2c.sda + self.u1.SDA
        self.SCL = self.i2c.scl + self.u1.SCL
```

A shared open-drain bus's pull-ups (I2C, MDIO's `MIIM.mdio`) belong to the circuit that composes the bus (usually the top-level design), never inside one participant; the base skill's grep gates flag `r_sda` and `r_scl` outside `TOP_LEVEL_PATH`.

## Key rules

1. Store every component and net expression on `self` once, singly or in a list. A component stored twice (two attributes, an attribute and a list, or a helper's `jitx.current.circuit +=` plus an attribute) fails translation: `Child object ... encountered multiple times`. An unstored `a + b` is a lost connection. An unstored component fails the build once its ports join a net (`Unable to map local reference`), which a `TestCase` that only instantiates the design misses; unjoined, it only logs `lost during instantiation`.
2. Boundary ports are class attributes. Components, nets and wiring go in `__init__`, with no `build()` or `circuit()` methods.
3. Subclass `Circuit` for a circuit and `jitx.Component` for a part.
4. Never alias a component's port (`self.x = self.r1.p2`): the build fails with `Child object ... has multiple parents`. To expose a pin, net it to a boundary port.
5. Mark an unused component pin `no_connect()` in the component or the circuit holding it. Leave an unused circuit port off every net: `no_connect()` on one passes translation and a `TestCase`, then fails the build: `Cannot set a module pin as no-connect`.

## Anti-string-hacking

Construct JITX objects directly. Never walk a `list[dict[str, Any]]` spec to emit JITX calls (batch parameters in a frozen dataclass), and do not add to a circuit from a free function (compose a `Container` member). Worked examples: the base skill's Don'ts and `jitx/references/architectural-patterns.md`.

## Typed ports and composition

A circuit's boundary is typed ports: `Power` from `jitx.common` (members `Vp`, `Vn`) and protocol bundles from `jitxlib.protocols` (`I2C`, `SPI`, `RGMII`, `MIIM`, `MDI1000BaseT`). Find one with `grep -rn "class RGMII"` under the venv's `jitxlib/protocols` and read its module path, members and constructor options (`SPI(cs=True)` adds `cs`); never write them from memory.

A port nets only to a port of the same concrete type and parameters: `+` between two `Power` ports joins them member for member, and `Power + I2C` raises `ValueError: Incompatible ports on Net`. `+` pairs members by name, so cross members named per device: `UART` `tx` to `rx`, `LanePair` `TX` to `RX`. `RGMII` connects by name: `RGMII.Standard.Constraint` pairs `src.TX` with `dst.TX`. SI constraints and topology are `jitx-interconnect-constraints`.

```python
class EthernetPort(Circuit):
    vin = Power()
    rgmii = RGMII()
    miim = MIIM()

    def __init__(self) -> None:
        self.reg = RegulatorCircuit()
        self.phy = PhyCircuit()
        self.jack = RJ45Circuit()
        self.VIN = self.vin + self.reg.vin
        self.VPHY = self.reg.vout + self.phy.vin
        self.RGMII = self.rgmii + self.phy.rgmii
        self.MIIM = self.miim + self.phy.miim
        self.MDI = self.phy.mdi + self.jack.mdi
```

A parent wires its children's boundary ports to each other and to its own. It never nets into a child's components, and a child never reaches up: a pin the parent needs is a boundary port of the child. SI constraint ends, a verification design's placement and its proof routes may still name a child's pads (`jitx-interconnect-constraints`, "Choosing the ends").

## Placement

```python
self.reg = RegulatorCircuit().at(10, 5, rotate=90)  # fixed, in this circuit's frame
self.jack = RJ45().at(0, 0, on=Side.Bottom)  # Side from jitx.layerindex
self.phy = PhyCircuit().at(floating=True)  # Circuit only: placed interactively
```

A sub-circuit without `.at` sits at its parent's origin on top. Until a placement is stored, a floating circuit sits off the board: routes stay unrealized and pours `Empty()` while the build reports `status: ok`. That trap, relative placement (`Circuit.place`) and code-placed vias are `jitx-physical-layout`.

## Nets

`Net(...)` takes one iterable of ports, so a whole rail goes on in one call; a bare port raises `TypeError`.

A net's exported name comes from the highest circuit that joins it. Without `name=`, it is the name of the field that stores the net: `self.RESET_n = a + b` is `RESET_n`, a list in `self.CA` gives `CA[0]`, `CA[1]` and so on, and a list of lists in `self.DQ` gives `DQ[0][1]`. A bundle net exports one net per member: `self.CK` on a diff pair gives `CK_p` and `CK_n`, `self.VSYS` on a `Power` gives `VSYS_Vp` and `VSYS_Vn`. The highest circuit's name wins even over a child's `name=`, so a catch-all field in the joining circuit (`self.nets = [...]`) renames every net it touches `nets[0]`, `nets[1]`, whatever the children called them. A sub-circuit's net that no parent joins keeps its own name when no other instance exports that name; two sibling instances `x` and `y` of a circuit with net `E` give `x_E` and `y_E`. A net added with `self += a + b` is stored in no field and exports under an internal name (`_Circuit__iliad[0]`). A net's name may match a public port's name. Store each signal, or each group of like signals, in its own field named for it, in the highest circuit that joins it; in a loop, keep one list per signal role (`self.TX_P`, `self.TX_N`).

Power and ground get net symbols in the top-level design (the circuit a `Design` builds, in a file under `TOP_LEVEL_PATH`, default `designs/`): `GroundSymbol()` on each ground domain and `PowerSymbol()` on each power rail that crosses circuits, both from `jitxlib.symbols.net_symbols`. The base skill's grep gates fail a symbol anywhere else, so a sub-circuit's rails, including one made and used inside it (an LDO's local 1V8), carry no symbol and are named by their field. A symbol on a bundle net raises `ValueError: Cannot set symbol on bundle net`, so keep the rail a bundle net and put the symbol on a net of one member, stored after the bundle in the field that names the rail:

```python
self.VSYS = self.reg.vout + self.mcu.vin + self.sensor.vin
self.P3V3 = Net([self.reg.vout.Vp], symbol=PowerSymbol())
self.GND = Net([self.reg.vout.Vn], symbol=GroundSymbol())
```

The rail exports as `P3V3` and `GND`, with a symbol at each part on it. The symbol net's field names the whole rail, so a bundle in `self.P3V3` with its symbol net in `self.P3V3_SYM` exports `P3V3_SYM`.

Measured on jitx 4.6.0rc10 by full build and KiCad export.

`+=` takes a port or a `Net`, never a bare list:

```python
self.GND = Net([*self.u1.GND, *self.u1.RSVDGND], name="GND")
self.GND += [*self.u1.AGND]  # WRONG
self.GND += Net([*self.u1.AGND])  # RIGHT
```

Pyright reports `Operator "+=" not supported` and instantiation raises `InstantiationException` wrapping `ValueError: Incompatible ports on Net: Port and list`. Onto an empty `Net(name="GND")` pyright is silent, a `TestCase` passes, and the build fails with `TypeError: unhashable type: 'list'`.

### Asserting connectivity in tests

Assert membership over `list(net)`, never with `in`: `Net.__contains__` stops at the first nested net, so a port after it reports `False`. Count too: `len(list(net))` catches a rail that lost balls:

```python
self.assertIn(self.u1.VCCINT[0], list(circuit.V1V0))
self.assertEqual(len(list(circuit.GND)), 30)
```

A bundle net lists its bundles. Assert that, then assert inside each child that its boundary member reaches the component pin.

## Passives

`Resistor`, `Capacitor` and `Inductor` from `jitxlib.parts` take `jitx.units` quantities (a bare number is ohms, farads or henries). Bounds are `AtLeast` and `AtMost` from `jitxlib.parts`; a bare value is an exact match. The project's provider chain resolves them: base skill Install Step 2 and [Parts and Providers](https://docs.jitx.com/en/latest/essentials/design/parts.html).

Filter only on columns the approved CSV has, with bounds its rows meet: read it first. A query the CSV cannot meet (`tolerance=AtMost(0.01)` on an X7R whose rows are 10 to 20 percent) falls through to `ideal`, which returns an `IDEAL-` part honoring only value, case, tolerance and polarization: dielectric and ratings are silently dropped. Where the CSV lacks a column or row the design needs, ask for it rather than writing the key.

State what the circuit depends on:

- `tolerance=AtMost(0.01)` on every resistor whose value matters; a capacitor tolerance only where the circuit needs one.
- `temperature_coefficient_code="X7R"` (or `"X5R"`, `"C0G"`) on every ceramic. Unconstrained, Y5V or Z5U can come back.
- `rated_voltage_dc=AtLeast(...)` derated for DC bias: 10 V or 16 V on a 3.3 V rail.
- `max_power=AtLeast(...)` on a resistor that dissipates.

Leave `case=` off each passive, never a proxy for a power or voltage rating. Where the assembler sets a minimum package, state it once as a default query on the `Design` (`ResistorQuery` and `CapacitorQuery` from `jitxlib.parts`) listing every package it accepts, smallest up; one left off is excluded:

```python
class Board(Design):
    resistor_defaults = ResistorQuery(case=["0402", "0603", "0805", "1206", "1210"])
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805", "1206", "1210"])
```

A part's `query=` object or a `with` block replaces the whole default; its keywords add to it.

## Decouple against the pins

A power-rail capacitor is its own attribute on `self`, its supply-side pad joins the pin it serves through `ShortTrace(self.c_x.p1, <the IC power pin port>)` and its other pad joins the return net. `jitx.net.ShortTrace(p1, p2)` takes two ports, each a component pin or a boundary port: never a net (pyright rejects one) or a net's `.port` (pyright passes; translation fails).

This covers decoupling, bulk (to the supply pin it serves nearest) and output-filter capacitors (to the regulator output pin); a `PolarizedCapacitor` uses `.a`. A bootstrap capacitor takes a `ShortTrace` to its BOOT pin, other pad to SW per the datasheet; a crystal load capacitor takes one to its crystal pin, other pad to the return net. AC-coupling, RC timing, compensation and RF matching capacitors are not power-rail; say so for each.

Scale with the pin count, never two caps for a 96-ball core net:

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

Start at one HF cap per one or two core balls plus bulk per rail; fewer is a decision to state, with the count the design wants.

## Extract the repeated block at the second instance

Blocks that differ only in their arguments are one subcircuit with a parameter: three regulator stages differing in output voltage are one `Circuit` subclass instantiated three times.
