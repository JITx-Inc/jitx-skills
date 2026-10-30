---
name: jitx-pin-assignment
description: "Use when the user asks about provide/require patterns, provide.one_of or provide.subset_of decorators, programmatic Provide, pin muxing, MCU peripherals on shared pins, DiffPair polarity swapping, PCIe lane swapping or width variants, DDR byte or bit swapping, LPDDR5 channel swapping, hierarchical provider composition, SI constraints on pin-assigned ports, constraints with provide/require, or flexible pin mapping for FPGAs and MCUs. Covers provide, Provide, require, all_of, one_of, subset_of, and protocol-specific pin flexibility with SI constraints."
---

# JITX Pin Assignment

Model flexible pin mappings between circuit-level interfaces and component pins. A provider offers every mapping the part allows and leaves the choice open; routes on the provider's physical pins resolve it to one mapping.

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

`Provide` is also re-exported from `jitx`. Every constraint class, `DiffPairConstraint` and `ReferencePlanes` included, is in `jitx.si`.

## When to Use Pin Assignment

Use it when a part's pins can serve more than one role and the choice should stay open until routing: MCU GPIO and peripheral muxing, DiffPair P/N polarity where protocol and controller allow it, PCIe lane order and width, DDR byte and bit swapping, channel choice on a pass-through part with identical channels. Use fixed wiring when the mapping is 1:1 (DDR address pins, CK polarity), or the datasheet gives one valid pin function. For a self-critique pass after writing, invoke `jitx-code-review` (optional for single-task use).

## Bundles

A bundle is a `Port` subclass that groups related signals; it is the type parameter of `provide` and `require()`. Read an unlisted bundle's sub-ports from its class source (Grep `class BundleName` under `.venv`).

| Bundle | Import | Sub-ports |
|--------|--------|-----------|
| `GPIO` | `jitx.common` | `.gpio` |
| `Power` | `jitx.common` | `.Vp`, `.Vn` |
| `DiffPair` | `jitx.net` | `.p`, `.n` |
| `I2C` | `jitxlib.protocols.serial` | `.sda`, `.scl` |
| `SPI` | `jitxlib.protocols.serial` | `.sck`, `.copi`, `.cipo`, `.cs`; the last three optional: `SPI(cs=True)` |
| `UART` | `jitxlib.protocols.serial` | `.tx`, `.rx` on by default; flow control optional: `UART(cts=True, rts=True)` |

For a custom bundle, subclass `Port` (never `Circuit` or `Component`). Sub-ports are class attributes; use lists for indexed groups and nest bundles for hierarchy:

```python
class PCIeLane(Port):
    TX = DiffPair()
    RX = DiffPair()

class PCIeLink(Port):
    lane = [PCIeLane() for _ in range(4)]
```

When one choice fixes pins on two sides of a part (both ends of a pass-through channel), put both sides in one bundle so one mapping sets both; separate offers per side can pick different channels for the two ends.

## The Provide/Require Architecture

A component defines the pins; a circuit wrapping it declares with `provide` the bundles it offers and the pins each option maps to; an application circuit calls `.require()` on the wrapper and wires what it gets back.

### The Mapping Return Type

Every provide method returns `list[dict[Port, Port]]`: one dict per option. The keys are the bundle parameter's sub-ports, every one of them in every option. The values are component pins (`self.<component>.<port>`) or sub-ports of a bundle the provider requires from itself ([Hierarchical Provider Composition](#hierarchical-provider-composition)).

```python
@provide.one_of(I2C)
def provide_i2c(self, i2c: I2C) -> list[dict[Port, Port]]:
    return [
        {i2c.sda: self.mcu.GPIO[0], i2c.scl: self.mcu.GPIO[1]},  # Option A
        {i2c.sda: self.mcu.GPIO[2], i2c.scl: self.mcu.GPIO[3]},  # Option B
    ]
```

### Carve-out from the anti-string-hacking rule

`jitx/SKILL.md` bans string-keyed design state and `list[dict[str, Any]]` spec models. The provide return value alone is exempt: its keys are the bundle's Port objects, and the list is the framework's pin-mapping contract, not a parallel model. Use that shape exactly, with no string key anywhere in it (the discriminator is the key type: `jitx/references/architectural-patterns.md` § "String-keyed dicts → structural objects").

## Provider Patterns

| Variant | Decorator | Constructor | Offers |
|---|---|---|---|
| all_of | `@provide(B)` | `Provide(B).all_of(fn)` | One provider per option, all assignable at once (GPIO). |
| one_of | `@provide.one_of(B)` | `Provide(B).one_of(fn)` | One provider, filled by exactly one option (a bus on one pin group or another). |
| subset_of | `@provide.subset_of(B, n)` | `Provide(B).subset_of(n, fn)` | At most `n` options assigned (a current budget across GPIO). |

`fn` takes the bundle and returns the mapping list. Use the constructor when the options depend on `__init__` arguments (here `n`), and store its result on `self`:

```python
self.gpios = Provide(GPIO).all_of(lambda g: [{g.gpio: p} for p in self.mcu.GPIO[:n]])
```

## Consuming Providers with `require()`

`provider.require(B)` returns a bundle whose sub-ports are netted with `+` like any port; `require(B, count=n)` returns a sequence of `n`. Keep the result in a local variable and store the nets. A `require()`d port stored on `self` fails the build with `Port <circuit>.<name> is a required port from <Provider> and should not be a member field of a circuit`.

```python
gpio = self.mcu_circuit.require(GPIO)  # local, never self.gpio
self.led_net = gpio.gpio + self.led.anode
```

Worked example, end to end (RP2040 SPI and I2C muxing, a shipping design with no routes, legal and illegal verification designs): `jitxexamples.jumpstart_kits.js3_pin_assignment.mcu_muxing`.

## Hierarchical Provider Composition

Inside a provide method a provider can call `self.require(...)` on its own providers and map the outer bundle onto what it gets back. Use it when parts of an interface are chosen independently, such as SDA and SCL from their own pin lists. Inner bundle types are nested classes on the circuit or live in their own module.

```python
@provide(I2C)
def provide_i2c(self, i2c: I2C) -> list[dict[Port, Port]]:
    sda = self.require(self.I2C_SDA)  # single-pin bundle, @provide.one_of over SDA pins
    scl = self.require(self.I2C_SCL)
    return [{i2c.sda: sda.p, i2c.scl: scl.p}]
```

Concept: [I2C Example](https://docs.jitx.com/en/latest/essentials/design/pin_assignment.html#i2c-example). Worked pattern: `jitxexamples.components.mcus.raspberry_pi_RP2040` (I2C, SPI and UART composed from per-signal `one_of` pin lists).

## DiffPair P/N Polarity Swapping

Offer a P/N swap only when the part or protocol explicitly supports it at both ends ([references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md)). The inversion is its own option with the legs crossed:

```python
{link.p: self.ic.TXP, link.n: self.ic.TXN},  # straight
{link.p: self.ic.TXN, link.n: self.ic.TXP},  # inverted
```

A code route from `TXN` to the far end's `p` pin resolves the inverted option. Worked pattern: `jitxexamples.patterns.pin_lane_polarity` (lane choice and P/N inversion, proven straight, inverted and illegal).

## Constraints on Pin-Assigned Ports

On jitx 4.6, write the constraint as `jitx-interconnect-constraints` teaches: plain `+` nets and `Topology(begin, end)`, no `>>`. The path between the ends is inferred from the routes; it crosses a via, or a part with a pin model, where routes land on both sides. `>>` (`TopologyNet`) is only for a daisy chain whose order the autorouter must follow, such as a flyby clock. What pin assignment adds:

1. Give every part with a path through it a `BridgingPinModel` between the two pins that path joins (a series resistor, an AC-coupling capacitor, an ESD channel whose datasheet gives an in-to-out path); without one the path stops there (`No path for signal constraint ... which has no pin model`). A flow-through package whose pin opposite the channel is n.c. has no path through it: no pin model, and the channel pin and the n.c. pin are one net joined by board copper. A pin model's delay and loss come from the part's datasheet; a fixture or placeholder part says it is fictional in its docstring and labels its values as given.
2. Prove it on a verification design: a separate Design that places every part with `.at(...)` and closes the path with code `Route`s ending on the provider's physical pins. A route cannot end on a required port (`Using require ports as route ends ... is not implemented`). Proof routes fix one mapping, so they never go in the product design.
3. Routes that match one offered mapping resolve the assignment to it. Routes that match none are dropped (`Code route dropped`) and their leg has no path; a leg whose routes fit an offered mapping still measures. A constraint on a required port measures only once its assignment resolves, so with no routes nothing measures.
4. Pick the Topology ends by where the assigned part sits.
   - Mid-path (a pass-through part with interchangeable channels): ends on fixed physical pins either side, such as `Topology(self.drv.d[0], self.rcv.d[0])`. Worked pattern: `jitxexamples.patterns.pin_series_array`.
   - The provider is an end (a serializer's lanes, a DDR controller's byte lanes): the Topology begins on the required port. Resolved, the measured line names the physical pin, such as `from src.u.a.n to conn.tx.p` for an inverted pair. Worked pattern: `jitxexamples.patterns.pin_lane_polarity`.
5. Skew across a bundle uses `ConstrainReferenceDifference`, whose guide must be a single pin (`Guide must be a single pin type`): one leg, such as a strobe's `p`, never the `DiffPair`.
6. A constraint counts as applied only when its group carries a Time, Loss or Skew measurement; whether it is met is `group.satisfied` ([Step 3](#step-3-prove-constraints-with-design-issues)).

## PCIe Lane Flexibility

Offer PCIe lane reversal, polarity inversion or a narrower link width only where the controller datasheet confirms it; the per-feature rules are in [references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md#pcie-lane-flexibility). A lane constraint begins on the required lane (rule 4 above); worked pattern: `jitxexamples.patterns.pin_lane_polarity`.

## DDR Byte/Bit Swapping

Where the controller allows bytes to move between byte slots and bits within a byte, model both as two levels of `provide`, never `one_of` over bit permutations (8! = 40,320 options per byte):

- Bit swap: per byte slot, a single-pin bundle type of its own (`Slot0Bit`, `Slot1Bit`, ...), offered `all_of` over the slot's eight DQ pins. Per slot because `require()` matches an offer by bundle type: one shared type would let a byte's bits resolve onto another slot's pins.
- Byte swap: the bus bundle offered `one_of`, one option per allowed byte-to-slot order. In the options callback, `self.require(SlotBit, count=8)` once per slot; each option maps the fixed pins, the slot's DQS and DM, and the byte's eight DQ ports to that slot's eight bits.

DQS and DM move with their byte; address, command and CK (polarity included) are fixed wiring. Match each DQ to its strobe with `ConstrainReferenceDifference` (rule 5). Worked example: `jitxexamples.jumpstart_kits.js4_fpga_lpddr4x` (LPDDR4X on a Versal VP1002: pin rules in `pinout`, the two-level offer in `fpga`, constraints in `constraint`, legal and illegal proof routes in `proof`).

## Common Mistakes

- Returning a port instead of a mapping list: `return self.mcu.GPIO[0]`. Return `[{g.gpio: self.mcu.GPIO[0]}]`.
- Assigning a required port instead of netting it: `self.led_pin = gpio.gpio` makes no connection. Use `self.led_net = gpio.gpio + self.led.anode`.
- Building a net without storing it: `tx.p + self.dst.INP.p` alone is built and discarded. Store it: `self.tx_net = tx + self.dst.INP`.
- `@provide.one_of(GPIO)` when several GPIOs are wanted: it gives one GPIO in total. Use `@provide` (all_of).

## Verification

Step 1: `ruff format path/to/circuit.py` and `pyright path/to/circuit.py`.

Step 2: `jitx build <module.path.DesignClass>`. Don't run parallel JITX builds against the same project; sequence them ([Build safety](../jitx/SKILL.md#build-safety-dont-parallelize-same-design-work)).

### Step 3: Prove constraints with design issues

Run the check on the verification design (rule 2); the product design reports these constraints unresolved until the board is routed. Run this as a script from the project root while the project's runtime is running:

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

The report API, and the report texts and their causes: `jitx-interconnect-constraints` [references/verification.md](../jitx-interconnect-constraints/references/verification.md). The texts specific to pin assignment:

| Report text | Cause |
|---|---|
| `Unassigned Pin on Path: nets[0].p` | Topology begins on the required port; the assignment did not resolve. |
| `No path for signal constraint from drv.d[0] to rcv.d[0]` | Fixed ends around the assigned part; no routes, or routes matching no offered mapping. |
| `Code route dropped: it conflicts with other connections` | The routes matched no offered mapping (rule 3). On a net with no SI constraint it can read `Code route dropped: its ends are on different nets`. |

To show the offered mappings are enforced, also prove one routing that matches none: it must report a dropped route and no measurement for that leg.

## API Reference

- [Pin assignment concepts](https://docs.jitx.com/en/latest/essentials/design/pin_assignment.html)
- [jitx.net module (provide, Provide)](https://docs.jitx.com/en/latest/api/jitx.net.html)
- [jitx.si module (constraints)](https://docs.jitx.com/en/latest/api/jitx.si.html)
- Protocol-specific pin flexibility: [references/protocol-pin-flexibility.md](references/protocol-pin-flexibility.md)
