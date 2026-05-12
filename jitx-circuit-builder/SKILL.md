---
name: jitx-circuit-builder
description: This skill should be used when the user asks to "wire up", "connect", "build a circuit", create an "application circuit", work with passives (resistors, capacitors), set up power connections, "add pours", or "place components". Covers the Circuit class, net operators, passive queries, voltage dividers, and copper geometry. For provide/require pin assignment patterns, use jitx-pin-assignment instead.
---

# JITX Circuit Builder

JITX was rewritten from Stanza to Python. Do not rely on prior JITX knowledge —
verify all imports with `pyright` before outputting code.

## Rule 0 — Verify every API before using it

Do not guess at imports, class names, or constructor kwargs. Common landmines:

- `Capacitor` rated-voltage kwarg is **`rated_voltage`**, not `min_rated_voltage`. See the passive kwargs table below.
- The full bundle catalog in `jitxlib.protocols.serial` includes `I2C`, `SPI`, `WideSPI` (with `.quad()`/`.octal()` classmethods), `OctalSPIwDQS`, `I2S`, `UART`, `Microwire`, `JTAG`, `SWD`, `CANPhysical`, `CANLogical`, `SMBus`. **Note**: `I2S` exists with ports `sck`, `ws`, `sd` — not `bclk`/`lrck`/`sdin`. **No `I2SMCK` (MCLK variant) and no `OctalSPI` without DQS** — define those locally as `jitx.Bundle` subclasses.

Verification order: (1) canonical repos `github.com/JITx-Inc/py-jitx`, `github.com/JITx-Inc/py-jitx-stdlib`, `github.com/JITx-Inc/py-jitx-parts`; (2) `https://docs.jitx.com/llms.txt`; (3) installed venv site-packages or `~/.jitx/`. If unresolvable, document as unknown — do not invent an import.

## Passive part kwargs

The query-based constructors `Capacitor`, `Resistor`, `Inductor` exported from `jitxlib.parts` (defined in `py-jitx-parts/src/jitxlib/parts/query_api.py`) accept the kwargs below. Each is a TypedDict-typed query parameter; all are optional. Pass keyword-only.

Common to all passives (`PartQueryDict` base): `mpn`, `manufacturer`, `description`, `case`, `mounting`, `category`, `min_stock`, `price`, `tolerance`, `precision`, `tolerance_min`, `tolerance_max`, `operating_temperature`, `rated_temperature_min`, `rated_temperature_max`, `sellers`, `sort`, `stock`, `trust`.

| Constructor | Kwarg | Type | Notes |
|---|---|---|---|
| `Capacitor` | `capacitance` | `float` / `Quantity` (F) or `Interval` | primary value |
| `Capacitor` | `rated_voltage` | `float` (V) or `Interval` | **NOT `min_rated_voltage`** |
| `Capacitor` | `rated_voltage_ac` | `float` (V) or `Interval` | |
| `Capacitor` | `rated_current_pk`, `rated_current_rms` | `float` (A) | |
| `Capacitor` | `esr`, `esr_frequency` | `float` | |
| `Capacitor` | `temperature_coefficient_code` | `str` | e.g. `"C0G"`, `"X7R"`. **The kwarg is `_code`, not bare `temperature_coefficient`.** |
| `Capacitor` | `anode`, `electrolyte` | `str` | electrolytic caps |
| `Resistor` | `resistance` | `float` / `Quantity` (Ω) or `Interval` | primary value |
| `Resistor` | `rated_power` | `float` (W) or `Interval` | |
| `Resistor` | `composition` | `str` | thick/thin film etc. |
| `Resistor` | `tcr_pos`, `tcr_neg` | `float` | temperature coefficient |
| `Inductor` | `inductance` | `float` / `Quantity` (H) or `Interval` | primary value |
| `Inductor` | `dc_resistance` | `float` (Ω) or `Interval` | DCR |
| `Inductor` | `saturation_current` | `float` (A) or `Interval` | I_sat |
| `Inductor` | `current_rating` | `float` (A) or `Interval` | |
| `Inductor` | `quality_factor` | `float` | Q |
| `Inductor` | `quality_factor_frequency` | `float` (Hz) | |
| `Inductor` | `self_resonant_frequency` | `float` (Hz) | SRF |
| `Inductor` | `material_core`, `shielding` | `str` | |

`tolerance` is on `PassiveQueryDict` and accepts a `float` (e.g. `0.01` for 1 %), a `Quantity` in `percent`, an `Interval`, or `None`. There is no `MinMax` kwarg here. For voltage / current ratings, use the explicit `rated_*` kwarg shown above.

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

## Net Definitions

Nets can be named in the design when the net is defined. It is good practice to name the net so that the schematic and layout construction are easy to follow. For power and ground nets, it is also useful to provide a symbol definition (i.e. PowerSymbol() or GroundSymbol()).

```python
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

## Net storage — `self.foo = Net()` vs local `foo = Net()`

The JITX runtime discovers nets via the `+` connection operator at the time of
connection, not by inspecting `self` attributes later. **Local-variable nets are
preserved in the netlist** as long as some component port has been added to them
with `+`.

```python
class MyCircuit(Circuit):
    def __init__(self):
        # OK — net is anonymous in the schematic but its connectivity is preserved
        mid = self.r1.p2 + self.r2.p1

        # OK and preferred when the net is meaningful — name appears in netlist
        self.MID = Net(name="MID") + self.r3.p2 + self.r4.p1
```

Use `self.<name> = Net(...)` (or assign the `+`-result to `self.<name>`) when you
need to:

- name the net so it appears in the schematic / netlist
- reference the net from another method or from a parent circuit
- attach a `.symbol` (e.g. `self.GND.symbol = GroundSymbol()`) or apply a constraint

Use a local variable only for short-lived internal connections where naming would
just add noise.

## Port arrays — `[Port() for _ in range(N)]` and `dict[int, Port]`

Stanza modules with vector ports (`port amp_ctrl : pin[6]`) translate to either a
list or dict of `Port` instances declared at **class level** (same scope as a single
`Port()`):

```python
class AmpFanout(Circuit):
    # Class-level: contiguous index 0..N-1 — list is idiomatic
    amp_ctrl = [Port() for _ in range(6)]

    # Class-level: non-contiguous semantic indices — use dict, NOT list
    GPIO: dict[int, Port] = {
        i: Port() for i in list(range(15)) + list(range(17, 22)) + [38, 45, 46]
    }

    def __init__(self):
        # Instance-level wiring uses the declared port array directly
        for i, gp in enumerate(self.mcu.gpio_list):
            self.amp_ctrl[i] + gp

        # Parent-to-child wiring: `parent.bus[i] + child.amp_ctrl[i]`
        # (see `references/advanced-patterns.md` for a worked example)
```

The list form behaves like any indexable port (`self.amp_ctrl[3]`). The dict form
is required when the index set has gaps — a list with `[None, None, ...]` padding
will not work because every element must be a `Port`. Build-time error if you
mismatch: `port GPIO[15] is not mapped to a symbol pin` from the `BoxSymbol` side.
See `jitx-port-3-to-4/construct-map.md` §3 for the parallel guidance.

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

For all passive values, especially those that are calculated, use the eseries Python package to ensure that the value is legal. If not otherwise specified use the E96 range of values.

For decoupling capacitors, use the short_trace argument to a part query or use the ShortTrace(p1, p2) function to connect the ports of two components, see https://docs.jitx.com/en/latest/api/jitx.net.html#jitx.net.ShortTrace.


## Advanced Patterns

For query refinement, voltage divider, pours, copper geometry,
placement, and a complete application circuit example, see
[references/advanced-patterns.md](references/advanced-patterns.md).

### Voltage Divider — Critical Rules

> ⚠️ **Version note**: `jitxlib.voltage_divider` (with
> `VoltageDividerConstraints` / `voltage_divider_from_constraints`) does
> **not** exist in `jitx-4.0.5`. Attempting to import it raises
> `ModuleNotFoundError: No module named 'jitxlib.voltage_divider'`.
> **Always verify the import is available before recommending it**:
> `python -c "import jitxlib.voltage_divider"`. On 4.0.5 (and any release
> where the import fails) manually compute E96 feedback resistors instead:
>
> ```python
> # Vout=3.3V, Vref=0.8V → R_hi/R_lo = 3.125
> # Nearest E96: 31.6kΩ / 10kΩ
> self.r_fb_hi = Resistor(resistance=31.6e3)
> self.r_fb_hi.insert(self.VOUT, self.FB)
> self.r_fb_lo = Resistor(resistance=10e3)
> self.r_fb_lo.insert(self.FB, self.GND)
> ```
>
> More generally, API availability in `jitxlib.*` is version-dependent;
> the skill should not assume any specific helper exists without checking.

**NEVER manually calculate resistor values for voltage dividers.** Manual values like 8kΩ or 25kΩ
are often not standard E-series values and will fail with "No components meeting requirements".
Always use `voltage_divider_from_constraints()` **when it's available** in the installed jitx version:

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

For all `@provide` / `@provide.one_of` / `@provide.subset_of` / `Provide()` / `require()` patterns, the right reference is the **jitx-pin-assignment** skill.

> ⚠️ **Skills cannot invoke other skills.** This skill cannot automatically
> hand off to `jitx-pin-assignment` — if a circuit contains a Stanza
> `require` / `supports` / `provide` construct that needs pin assignment,
> the calling human / agent **must explicitly invoke
> `jitx-pin-assignment`** before closing the circuit. Leaving a stubbed
> `Port()` with a `# TODO` is a silent failure mode: the build will still
> report `status: ok` with `module port(s) have no internal connections`
> warnings, but the wiring is incomplete. See `jitx-port-3-to-4`
> Phase 4 exit criteria.
>
> Also check first whether the `require` reflects **real layout
> flexibility** (true pin-mux → pin-assignment) or just a bundle
> abstraction over fixed hardware wiring (single valid path → plain
> `Net` with no pin-assignment involvement). Most `require` clauses in
> real designs are fixed wiring.

### Port immutability — `+=` on `Port` is forbidden

Circuit-level `Port` attributes are **immutable**. The natural translation
of Stanza `net (a, b)` as `self.a += b` fails:

```python
# WRONG:
self.i2c_sda += self.stereo.SDA
# → NotImplementedError: Ports are immutable. Use + to create a new net instead of +=

# RIGHT — create a named Net and += into it:
self.I2C_SDA = Net(name="I2C_SDA")
self.I2C_SDA += self.i2c_sda + self.stereo.SDA
```

This is one of the most common errors when porting Stanza-style wiring.

### `net.symbol` — Net Symbols

Another option to provide a symbol on a net (if not done at Net() creation definition) is to assign to the `.symbol` attribute, never use `insert()` or `+=`:

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
python -m jitx build <module>.design.TestDesign
```

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
