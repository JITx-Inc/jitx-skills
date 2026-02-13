---
name: jitx-circuit-builder
description: Build JITX circuits with wiring, passives, providers, and geometry. Use when user asks to "wire up", "connect", "build a circuit", create an "application circuit", work with passives (resistors, capacitors), set up power connections, add pours, or place components. Covers the Circuit class, net operators, passive queries, provider/require patterns, and copper geometry.
---

# JITX Circuit Builder

JITX was rewritten from Stanza to Python. Do not rely on prior JITX knowledge —
verify all imports with `pyright` before outputting code.

## Package Architecture

JITX uses two packages — know which one to import from:

- **`jitx`** — Core framework. Circuit infrastructure, nets, ports, bundles, geometry.
  - `jitx` (top-level): `Circuit`, `Net`, `Pour`, `Copper`, `current`
  - `jitx.common`: Bundles — `Power`, `GPIO`
  - `jitx.net`: Port system — `Port`, `DiffPair`, `provide`, `Provide`
  - `jitx.toleranced`: `Toleranced`
  - `jitx.constraints`: `Tag`, `design_constraint`
  - `jitx.layerindex`: `Side`
- **`jitxlib`** — Parts library. Components, queries, protocols, symbols, solvers.
  - `jitxlib.parts`: `Resistor`, `Capacitor`, `Inductor`, `ResistorQuery`, `CapacitorQuery`, `InductorQuery`
  - `jitxlib.protocols.serial`: `I2C`, `SPI`, `UART`
  - `jitxlib.symbols.net_symbols`: `GroundSymbol`, `PowerSymbol`
  - `jitxlib.voltage_divider`: `VoltageDividerConstraints`, `voltage_divider_from_constraints`

**These modules DO NOT EXIST — NEVER import from them:**
`jitx.passives`, `jitx.passive`, `jitx.bundles`, `jitx.bundle`, `jitx.provide`,
`jitx.providers`, `jitx.symbols`, `jitx.si_units`. There is no `Device` class in jitx
(use `Circuit`). Passives live in `jitxlib.parts`, bundles in `jitx.common`, protocols in
`jitxlib.protocols.serial`, `provide` in `jitx.net`.

When unsure, search:

```bash
grep -r "class ClassName" .venv/lib/python*/site-packages/jitx*/
grep -r "def function_name" .venv/lib/python*/site-packages/jitxlib*/
```

### Finding bundle pins

Read the class definition to discover what pins a bundle has:

```bash
grep -A 10 "class Power" .venv/lib/python*/site-packages/jitx/common.py
grep -A 20 "class SPI" .venv/lib/python*/site-packages/jitxlib/protocols/serial.py
```

Do not hardcode pin names from memory — verify from source. Bundle constructors
may have optional pins (e.g., `SPI(cs=True)` to enable chip select).

## Circuit Structure

```python
from jitx import Circuit, Net
from jitx.common import Power
from jitx.net import Port
from jitxlib.parts import Resistor, Capacitor

class MyCircuit(Circuit):
    """Circuit subclass — follow this skeleton exactly."""

    # 1. Ports are class-level attributes, NEVER assigned in __init__
    power = Power()
    signal = Port()

    # 2. __init__ takes no super() call — Circuit handles setup internally
    def __init__(self):
        # 3. Named nets — name= is keyword-only (first positional arg is ports)
        self.GND = Net(name="GND")
        self.VCC = Net(name="VCC")

        # 4. += stores the connection (net on LEFT, ports on right)
        #    bare `a + b` without += silently drops the connection
        self.VCC += self.power.Vp
        self.GND += self.power.Vn

        # 5. Components — ALWAYS assign to self, then insert
        self.r1 = Resistor(resistance=10e3)
        self.r1.insert(self.power.Vp, self.signal)

        # 6. Bypass cap — must also be assigned to self
        self.c_bypass = Capacitor(capacitance=100e-9)
        self.c_bypass.insert(self.power.Vp, self.power.Vn)

Device = MyCircuit
```

## Key Rules

1. **EVERY component must be stored as `self.<name>`** — `self.c1 = Capacitor(...)` then `self.c1.insert(...)`. Anonymous `Capacitor().insert()` passes pyright but **fails at build time** with `"Reference to structural object lost during instantiation"`.
2. **`insert()` belongs to the component** — `self.r1.insert(portA, portB)`. No `self.insert()` or `self.add()` on Circuit.
3. **Always `class X(Circuit):`** — never `Device`, `JITXDevice`, or any other base class. There is no `Device` class in jitx.
4. **All wiring in `__init__`** — no `circuit()`, `execute()`, or `build()` methods.
5. **`jitx.Component`** — `import jitx` then `class MyIC(jitx.Component):`.
6. **Never alias component ports** — `self.x = self.r1.p2` creates multiple parents and fails. To expose a connection point, wire to a class-level Port: `self.r1.insert(gpio, self.output_port)`.

## Net Wiring

Every `a + b` expression creates a Net — it **must** be stored or the connection is lost.

```python
# Named nets for power rails — use +=
self.VCC += self.power.Vp + self.ic.VIN
self.GND += self.ic.GND + self.power.Vn

# Group anonymous nets by function
self.feedback_nets = [self.fb_div.out + self.buck.FB]
self.i2c_nets = [
    i2c.sda + self.sensor.SDA,
    i2c.scl + self.sensor.SCL,
]

# >> topology operator for ordered routing
self.topology = self.driver.out >> self.trace >> self.receiver.inp
```

## Passives

```python
from jitxlib.parts import Resistor, Capacitor, Inductor

# ALWAYS assign to self — anonymous Component().insert() fails at build time
self.r_sense = Resistor(resistance=0.1)
self.r_sense.insert(self.power.Vp, self.sense_out)

self.c_bypass = Capacitor(capacitance=100e-9)
self.c_bypass.insert(self.ic.VCC, self.ic.GND)

# With extra parameters
self.c_bulk = Capacitor(capacitance=10e-6, rated_voltage=10.0, temperature_coefficient_code="X7R")
self.c_bulk.insert(self.ic.VCC, self.ic.GND)

self.inductor = Inductor(inductance=4.7e-6, current_rating=3.0)
```

## Advanced Patterns

For query refinement, voltage divider, providers, pours, copper geometry,
placement, and a complete application circuit example, see
[references/advanced-patterns.md](references/advanced-patterns.md).

### Voltage Divider — Critical Rules

**NEVER manually calculate resistor values for voltage dividers.** Manual values like 8kΩ or 25kΩ
are often not standard E-series values and will fail with "No components meeting requirements".
Always use `voltage_divider_from_constraints()`:

```python
# WRONG — manual resistor values, 8k is not a standard E-series value
self.r_hi = Resistor(resistance=25e3)
self.r_lo = Resistor(resistance=8e3)  # FAILS: not a real resistor value

# WRONG — Toleranced.exact() on v_out gives zero tolerance, solver WILL fail
VoltageDividerConstraints(v_out=Toleranced.exact(0.6), ...)

# CORRECT — always use Toleranced.percent() for v_out, always include prec_series
VoltageDividerConstraints(
    v_in=Toleranced.exact(3.3),
    v_out=Toleranced.percent(0.6, 2.0),  # ±2% tolerance window (REQUIRED)
    current=0.6 / 10e3,
    prec_series=[1.00, 0.10],            # precision grades (REQUIRED)
    base_query=ResistorQuery(case=["0402"]),
)
```

### `@provide` — Critical Return Type

`@provide` methods must return `Iterable[Mapping[Port, Port]]`, NOT the bundle itself:

```python
# WRONG — returns a Port, not a mapping:
@provide(GPIO)
def provide_gpio(self, g: GPIO):
    return self.mcu.GPIO0

# CORRECT — returns list of {bundle_port: component_port} dicts:
@provide(GPIO)
def provide_gpio(self, g: GPIO):
    return [{g.gpio: self.mcu.GPIO0}, {g.gpio: self.mcu.GPIO1}]
```

### `net.symbol` — Net Symbols

Assign to the `.symbol` attribute, never use `insert()` or `+=`:

```python
self.GND = Net(name="GND")
self.GND.symbol = GroundSymbol()  # attribute assignment, NOT insert()
```

## Verification Process

### Step 1: Type Check
```bash
pyright path/to/circuit.py
```
Fix all import and type errors before proceeding. Ignore errors about `.prebuilt_components` relative imports — but always use the relative form (`from .prebuilt_components import ...`) since absolute imports fail at build time.

### Step 2: Build Test

Create a test harness to verify the circuit builds with the JITX backend:

```python
# design.py
from jitx.container import inline
from jitx.sample import SampleDesign
from jitxlib.parts import ResistorQuery, CapacitorQuery, InductorQuery

from .circuit import Device

class TestDesign(SampleDesign):
    _resistor_defaults = ResistorQuery(case=["0402", "0603", "0805"])
    _capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805", "1206"])
    _inductor_defaults = InductorQuery(mounting="smd")

    @inline
    class circuit(Device):
        pass
```

```bash
python -m jitx build <module>.design.TestDesign
```

**If a `build_test` helper is available** (e.g., in the skill_eval package), use it instead:
```bash
python -m skill_eval.build_test path/to/circuit.py
```

### Step 3: Fix Build Errors

If the build fails:
1. Read the traceback — the error message and the line number in your code tell you what went wrong
2. Look up the class or method that failed in source:
   ```bash
   grep -n "def method_name\|class ClassName" .venv/lib/python*/site-packages/jitx*/**/*.py
   ```
3. Fix the code, re-run pyright, then re-run the build. Repeat until it passes.

## Formatting

Format all generated circuit code with ruff:

```bash
ruff format path/to/file.py
```
