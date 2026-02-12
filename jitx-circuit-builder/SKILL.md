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

There are no `jitx.passives`, `jitx.symbols`, `jitx.providers`, or `jitx.bundle` modules.
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

        # 5. Named component — assign to self, then insert
        self.r1 = Resistor(resistance=10e3)
        self.r1.insert(self.power.Vp, self.signal)

        # 6. Anonymous bypass cap — chaining insert() is fine
        Capacitor(capacitance=100e-9).insert(self.power.Vp, self.power.Vn)

Device = MyCircuit
```

## Key Rules

1. **`insert()` belongs to the component** — `self.r1.insert(portA, portB)`. No `self.insert()` or `self.add()` on Circuit
2. **All wiring in `__init__`** — no `circuit()`, `execute()`, or `build()` methods
3. **`jitx.Component`** — `import jitx` then `class MyIC(jitx.Component):`
4. **Never alias component ports** — `self.x = self.r1.p2` creates multiple parents and fails. To expose a connection point, wire to a class-level Port: `self.r1.insert(gpio, self.output_port)`

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

# Named — assign to self, then insert between any two Ports or Nets
self.r_sense = Resistor(resistance=0.1)
self.r_sense.insert(self.power.Vp, self.sense_out)

# Anonymous — chain insert() directly
Capacitor(capacitance=100e-9).insert(self.ic.VCC, self.ic.GND)

# With extra parameters
Capacitor(capacitance=10e-6, rated_voltage=10.0, temperature_coefficient_code="X7R").insert(
    self.ic.VCC, self.ic.GND
)

self.inductor = Inductor(inductance=4.7e-6, current_rating=3.0)
```

## Advanced Patterns

For query refinement, voltage divider, providers, pours, copper geometry,
placement, and a complete application circuit example, see
[references/advanced-patterns.md](references/advanced-patterns.md).

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
