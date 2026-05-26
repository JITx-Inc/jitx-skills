---
name: jitx-circuit-builder
description: This skill should be used when the user asks to "wire up", "connect", "build a circuit", create an "application circuit", work with passives (resistors, capacitors), set up power connections, "add pours", or "place components". Covers the Circuit class, net operators, passive queries, voltage dividers, and copper geometry. For provide/require pin assignment patterns, use jitx-pin-assignment instead.
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
        #    bare `a + b` without storing on self silently drops the connection
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

1. **EVERY component must be stored as `self.<name>`** — `self.c1 = Capacitor(...)` then `self.c1.insert(...)`. Anonymous `Capacitor().insert()` passes pyright but **fails at build time** with `"Reference to structural object lost during instantiation"`. Component instantiation should not be done at the class level.
2. **`insert()` belongs to the component** — `self.r1.insert(portA, portB)`. No `self.insert()` or `self.add()` on Circuit.
3. **Always `class X(Circuit):`** — never `Device`, `JITXDevice`, or any other base class. There is no `Device` class in JITX but `Device` can be used as an alias.
4. **All wiring in `__init__`** — no `circuit()`, `execute()`, or `build()` methods.
5. **`jitx.Component`** — `import jitx` then `class MyIC(jitx.Component):`.
6. **Never alias component ports** — `self.x = self.r1.p2` creates multiple parents and fails. To expose a connection point, wire to a class-level Port: `self.r1.insert(gpio, self.output_port)`.

## Anti-string-hacking — read before writing parametric / generator circuits

For circuits that emit N parallel instances (per-lane fanout, per-row ballout, per-channel filter), construct the JITX objects directly inside the Circuit — do not build an intermediate `list[dict[str, Any]]` "spec" model and then walk it to emit JITX calls. If you need to batch parameters, use a frozen dataclass with named fields, not bare `dict[str, Any]`. See `jitx/references/architectural-patterns.md` §§ "Build the scene graph directly" and "Typed records over `dict[str, Any]`" before writing record-then-iterate code.

For a same-model self-critique pass on the circuit after writing (catches what these rules don't), invoke `jitx-skills:jitx-code-review`. Optional for single-task use.

## Net Definitions

Nets can be named in the design when the net is defined. It is good practice to name the net so that the schematic and layout construction are easy to follow. For power and ground nets, it is also useful to provide a symbol definition (i.e. PowerSymbol() or GroundSymbol()) — **at the top-level design only**. `PowerSymbol()` / `GroundSymbol()` outside `TOP_LEVEL_PATH` (default `designs/`) is a hard-fail under `scripts/grep_gates.sh`; the example below shows the *top-level* pattern.

```python
# Top-level design (in src/<ns>/designs/...): symbols are legal here.
self.my_net = Net(self.a, name = "my_net")
self.VCC = Net(self.power.Vp, name = "VCC", symbol = PowerSymbol())
```
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

# >> topology operator for ordered routing (intermediate nodes are RoutingStructure instances)
self.topology = self.driver.out >> self.trace >> self.receiver.inp
```

## Passives

```python
from jitxlib.parts import Resistor, Capacitor, Inductor

# ALWAYS assign to self — anonymous Component().insert() fails at build time
self.r_sense = Resistor(resistance=0.1)
self.r_sense.insert(self.power.Vp, self.sense_out)

# Power-rail caps use short_trace=True (see "short_trace=True is the default
# for power-rail capacitors" below).
self.c_bypass = Capacitor(capacitance=100e-9)
self.c_bypass.insert(self.ic.VCC, self.ic.GND, short_trace=True)

# With extra parameters
self.c_bulk = Capacitor(capacitance=10e-6, rated_voltage=10.0, temperature_coefficient_code="X7R")
self.c_bulk.insert(self.ic.VCC, self.ic.GND, short_trace=True)

self.inductor = Inductor(inductance=4.7e-6, current_rating=3.0)
```

For all passive values, especially those that are calculated, use the eseries Python package to ensure that the value is legal. If not otherwise specified use the E96 range of values.

### `short_trace=True` is the default for power-rail capacitors

Every capacitor `.insert(...)` call on a power rail — decoupling, bypass, bulk, output filter — **must** pass `short_trace=True`. The router uses this to minimize the trace length between the cap and its connected ports, which is what makes the cap actually decouple. Without it, the router may place a 0402 100 nF cap 20 mm from the IC and route through vias, defeating the purpose.

```python
# DEFAULT — every power-rail cap
self.c_bulk = Capacitor(capacitance=10e-6, rated_voltage=10.0)
self.c_bulk.insert(self.ic.VCC, self.GND, short_trace=True)

self.c_hf = Capacitor(capacitance=100e-9, rated_voltage=10.0)
self.c_hf.insert(self.ic.VCC, self.GND, short_trace=True)
```

**Exceptions** (caps where `short_trace=True` is NOT used — placement is part of the design):

- AC coupling caps in signal paths (e.g., audio out, USB SS data) — placement is symmetric to the trace topology
- RC time-constant caps (reset RC, soft-start, debounce) — value determines behavior, placement isn't the constraint
- Compensation network caps in switching regulator feedback loops — datasheet defines layout near the FB pin
- RF matching, coupling, or shunt caps (LNA input network, antenna feed) — placement is bookend-specific per the impedance budget
- Crystal load caps — placed per the crystal datasheet, not as decoupling

The `short_trace=True` rule is gated at the Phase 2 → Phase 3 exit. `bash scripts/grep_gates.sh src/<ns>/` flags every `.insert(...)` call missing `short_trace=` as review-required; the agent dispositions each: fix (add `short_trace=True`) for power-rail caps, accept-with-rationale (`exception: AC coupling`, `exception: RC time constant`, etc.) for non-power-rail caps, or N/A (`not a capacitor — resistor insert`).

The skill also documents `ShortTrace(p1, p2)` as an alternative connect-with-short-trace primitive — see https://docs.jitx.com/en/latest/api/jitx.net.html#jitx.net.ShortTrace.


## Advanced Patterns

For query refinement, voltage divider, pours, copper geometry,
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

### Provider / Require Patterns

For all `@provide` / `@provide.one_of` / `@provide.subset_of` / `Provide()` / `require()` patterns, see the **jitx-pin-assignment** skill. Invoke with `skill: "jitx-skills:jitx-pin-assignment"`.

### `net.symbol` — Net Symbols

Another option to provide a symbol on a net (if not done at Net() creation definition) is to assign to the `.symbol` attribute, never use `insert()` or `+=`. Same top-level restriction as above — only in `TOP_LEVEL_PATH` (default `designs/`):

```python
# Top-level design only.
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

Create a test harness to verify the circuit builds with the JITX backend (utilizing the required virtual environment):

```python
# design.py
from jitx.container import inline
from jitx.sample import SampleDesign
from jitxlib.parts import ResistorQuery, CapacitorQuery, InductorQuery

from .circuit import Device

class TestDesign(SampleDesign):
    resistor_defaults = ResistorQuery(case=["0402", "0603", "0805"])
    capacitor_defaults = CapacitorQuery(case=["0402", "0603", "0805", "1206"])
    inductor_defaults = InductorQuery(mounting="smd")

    @inline
    class circuit(Device):
        pass
```

```bash
jitx build <module>.design.TestDesign
```

Don't run parallel JITX builds against the same project — sequence them. See `jitx/SKILL.md` "Build Safety".

**If a `build_test` helper is available** (e.g., in the skill_eval package), use it instead:
```bash
python -m skill_eval.build_test path/to/circuit.py
```

### Step 3: Fix Build Errors

If the build fails:
1. Read the traceback — the error message and the line number in the code indicate what went wrong
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
