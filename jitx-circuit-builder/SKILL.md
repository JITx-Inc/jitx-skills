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
- The full bundle catalog in `jitxlib.protocols.serial` includes `I2C`, `SPI`, `WideSPI` (with `.quad()`/`.octal()` classmethods), `OctalSPIwDQS`, `I2S`, `UART`, `Microwire`, `JTAG`, `SWD`, `CANPhysical`, `CANLogical`, `SMBus`. **Note**: `I2S` exists with ports `sck`, `ws`, `sd` — not `bclk`/`lrck`/`sdin`. **No `I2SMCK` (MCLK variant) and no `OctalSPI` without DQS** — define those locally as `Port` subclasses (there is no `jitx.Bundle` class; a bundle is just a `Port` subclass with sub-`Port` attributes — see `jitx-pin-assignment` §"Bundles missing from jitxlib — define locally").

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

Nets can be named in the design when the net is defined. It is good practice to name the net so that the schematic and layout construction are easy to follow. For power and ground nets, it is also useful to provide a symbol definition (i.e. PowerSymbol() or GroundSymbol()) — **at the top-level design only**. `PowerSymbol()` / `GroundSymbol()` outside `TOP_LEVEL_PATH` (default `designs/`) is a hard-fail under `scripts/grep_gates.sh`; the example below shows the *top-level* pattern.

```python
# Top-level design (in src/<ns>/designs/...): symbols are legal here.
self.my_net = Net([self.a], name="my_net")
self.VCC = Net([self.power.Vp], name="VCC", symbol=PowerSymbol())
```

> ⚠️ **Name nets at the top level only.** A `Net(..., name="GND")` declared
> in every sub-`Circuit` builds cleanly through translation, then fails
> with `status: error / message: Public name GND already in use`. The
> message names the colliding name but not the source locations. Leave
> sub-circuit nets that will be unified by the parent **anonymous**
> (`Net([...])` with no `name=`); apply `name="GND"` only on the unified
> net at the top level:
>
> ```python
> class PowerSupplies(Circuit):
>     def __init__(self):
>         self.GND = Net([...])                     # no name=
>
> class Top(Circuit):
>     def __init__(self):
>         self.power = PowerSupplies()
>         self.GND = Net([self.power.GND, ...], name="GND")   # name= only here
> ```

> ⚠️ **`Net()` takes a single iterable of ports, not varargs.** A natural
> translation of "net VDD (a, b, c)" to `Net(self.a, self.b, self.c,
> name="VDD")` raises `TypeError: Net.__init__() takes from 1 to 2
> positional arguments…`. The signature is `Net(ports: Iterable = (), *,
> name=None, symbol=None)` — wrap the ports in a list:
> `Net([self.a, self.b, self.c], name="VDD")`.

### Power-rail naming — VCC vs VDD

JITX has no built-in voltage-domain consistency check, and rail-naming
inversions produce **clean builds with the wrong voltage on PVDD / I²C
pullups / copper pours**. Pick the names with discipline:

- `VCC` (or `V_BAT`, `V_IN`, etc.) — the **raw external supply** (from
  the connector or input header).
- `VDD` (or `V3P3`, `V1P8`, etc.) — the **regulated output** (from a
  buck/LDO).

The natural Python instinct is to use `VCC` for the most prominent rail
in the design — which is often the regulated 3.3 V, not the raw input.
That inversion is the most-inverted check in real designs. Write down
the mapping explicitly before naming nets:

| Net | Source | Type | Wired to (example) |
|---|---|---|---|
| `VCC` | `conn.p[1]` | raw input | regulator VIN, amp PVDD, motor driver VBAT |
| `VDD` | `vreg.VOUT` | regulated | MCU DVDD, sensor VCC, I²C pullups |

High-current / output-stage components (class-D amps, motor drivers,
high-side LED drivers) typically connect their power supply to the **raw
external** rail. MCU / sensor / digital-side DVDD / AVDD connects to the
**regulated** rail. The `jitx/references/export-verification.md` §C
("Power topology") checklist is the audit pass that catches inversions.

### Net construction — canonical recipes

The four-row table below covers every legitimate net-construction shape
in 4.x. The footguns it averts (Net GC after `__init__`, `Port += Port`
errors, name collisions across subcircuits, missing schematic symbols)
are scattered through this skill's other subsections; this table is the
quick-reference index.

| Goal | Recipe | Why |
|---|---|---|
| Top-level rail (named, schematic symbol) | `self.X = Net(name="X")` then `self.X += a + b`. Symbol attach: `self.X.symbol = PowerSymbol()` (or `GroundSymbol()`). | `name=` and `symbol=` only legal in `designs/`; `self.X` keeps the Net alive across `__init__`. |
| Intra-circuit net (anonymous) | `self.x = a + b` | `+`-chain returns a Net; `self.` assignment prevents GC. The name doesn't reach the schematic, which is fine inside a subcircuit. |
| Adding a port to an existing net | `self.X += new_port` | `+=` mutates the Net in place. The result of `Port + Port` is a Net, so `self.X += a + b` also works. |
| ❌ Don't | `a + b` (no `self.`) | The Net is GC'd after `__init__` returns. Build logs `WARNING:jitx._structural: Reference to structural object Net() lost during instantiation` — the symbol and name are lost even if the connectivity survives. |
| ❌ Don't | `self.a += b` where `a` is a `Port`, not a `Net` | Ports are immutable. See §"Port immutability" below. Wrap the LHS in `Net(...)` first. |
| ❌ Don't | `Net(self.a, self.b, self.c, name=...)` (varargs) | Signature is `Net(ports: Iterable = (), *, name=None, symbol=None)`. Wrap the ports in a list: `Net([self.a, self.b, self.c], name=...)`. |

## Top-level / aggregator-only constructs — what doesn't belong in a leaf subcircuit

Four JITX 4.x constructs are placed **only** in the `Design` class (or
`designs/<board>.py` per project convention); a fifth — shared-bus
pull-ups — lives one level lower, at the **bus-aggregation circuit**
that owns the multi-consumer bus (which is the Design class on many
boards, but is a dedicated subcircuit when the bus is reused across
designs). Putting any of these in a leaf subcircuit produces a build-
clean design with hidden wiring or silent rule conflicts.

| Construct | Why top-level only |
|---|---|
| `GroundSymbol()` / `PowerSymbol()` on `Net.symbol` | Schematic symbols on rails are a property of the unified board-wide net. A subcircuit's local "GND" gets merged into the top-level GND; if both carry a symbol, you get duplicate symbols on the schematic. |
| `Pour(shape, layer=...)` copper pours | Pours bind to the **whole board** geometry, not a subcircuit's frame. Subcircuit pours land at the wrong absolute coordinates if the parent is placed off-origin. |
| `ReferencePlanes({0: GND, ...})` | Reference planes are board-level routing rules. A subcircuit-local declaration doesn't propagate up. |
| `Constrain(...)`, `ConstrainDiffPair(...)`, `ConstrainReferenceDifference(...)` | These need the merged-net view from the top level. The subcircuit's local DP / DN ports are not yet joined to their consumer-side endpoints. |
| **Shared-bus pull-ups** (I²C SDA/SCL, FAULT open-drain, PG open-drain) | The pull-up's "other end" is the top-level rail (`+3V3`, etc.). The pull-up logically belongs at the bus aggregation level — usually the design layer — because it serves every consumer on the bus equally, not the one consumer whose subcircuit instantiates it. |

Projects that enforce this discipline ship a `scripts/grep_gates.sh`
(or equivalent) that hard-fails the build when the tokens above appear
outside `designs/`. Even without the script, follow the convention:
keep every consumer subcircuit free of these tokens, and place them
explicitly in the top-level `Design`'s `Circuit`.

Worked example: the `pd-audio/encore` reference puts all five of these
in `encore/designs/board.py`; the consumer circuits
(`encore/circuits/audio/amp.py`, `encore/circuits/mcu/esp32_subsystem.py`)
contain none of them. The grep gate at
`encore/scripts/grep_gates.sh` enforces the rule on every commit.

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

## Net storage — always root `+`-chain results on `self`

A `+` chain between `Port`s returns a `Net`. The connectivity it expresses is
discovered when the operator runs, but the `Net` object itself is a structural
object that JITX expects to find rooted on the `Circuit`. If you bind the
result to a Python local, the `Net` is GC'd after `__init__` returns and the
build logs:

```
WARNING:jitx._structural:Reference to structural object Net() at <file>:<line>
lost during instantiation, it likely needs to be assigned to an object.
```

Connectivity may still appear in the netlist via the merge that the operator
performed, but the `Net`'s metadata (its name, its symbol, any constraint
attached to it) is lost — silently. **Always assign every `+`-chain result to
`self.<name>` or accumulate it in a list / `self.nets`.**

```python
class MyCircuit(Circuit):
    def __init__(self):
        # ✅ Anonymous-but-rooted — no schematic name, but the Net survives.
        self.mid = self.r1.p2 + self.r2.p1

        # ✅ Named, preferred when the net is meaningful (appears in netlist).
        self.MID = Net(name="MID") + self.r3.p2 + self.r4.p1

        # ✅ Accumulated in a list also roots them.
        self.nets = [
            self.r5.p2 + self.r6.p1,
            self.r7.p2 + self.r8.p1,
        ]

        # ❌ Bare local — Net is GC'd, WARNING logged, name/symbol lost.
        mid = self.r1.p2 + self.r2.p1
```

Use `self.<name> = Net(...)` (or assign the `+`-result to `self.<name>`) when
you need to:

- name the net so it appears in the schematic / netlist
- reference the net from another method or from a parent circuit
- attach a `.symbol` (e.g. `self.GND.symbol = GroundSymbol()`) or apply a constraint

For short-lived internal connections that don't need a name, root them on
`self` anyway — pick a descriptive attribute name (`self.mid`,
`self.fb_div_out`) or accumulate in `self.nets`. The "bare local" form is
never the right shape; see `jitx-port-3-to-4/references/pitfalls.md`
§"Don't bind a Net to a Python local" for the porter-side rule.

### `Circuit.__dict__` is read-only

The `Circuit` / `Component` metaclass exposes attributes through
`types.MappingProxyType`, so `self.__dict__[name] = value` and
`self.__dict__.setdefault(name, default)` both raise (pyright also
flags them — `Cannot access attribute "setdefault" for class
"MappingProxyType[str, Any]"`).

```python
# ❌ Pythonic on plain classes, fails on Circuit / Component:
self.__dict__.setdefault("_pullups", []).append(r)

# ✅ Declare the accumulator on self in __init__, then mutate the list:
def __init__(self) -> None:
    self._pullups: list[Resistor] = []
    ...
```

For helper functions that need to accumulate sub-instances, **pass
the accumulator list as an argument** rather than reaching into
`self.__dict__`:

```python
def _i2c_pullups(container: list, bus: I2C, vdd: Port | Net) -> None:
    container.append(Resistor(resistance=10e3).insert(bus.scl, vdd))
    container.append(Resistor(resistance=10e3).insert(bus.sda, vdd))

class MyCircuit(Circuit):
    def __init__(self) -> None:
        self._pullups: list = []
        self.esp = ESP32_S3()
        _i2c_pullups(self._pullups, self.esp.i2c, self.VDD3V3)
```

The general rule: always set instance attributes via `self.<name> = …`.
Never use `setattr` / `self.__dict__[...] = ...` / `self.__dict__.setdefault(...)`
(see `jitx-skills:jitx/SKILL.md` §"Don'ts" for the broader rule and the
cryptic translation-time failure that violation produces).

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
        # Instance-level wiring uses the declared port array directly.
        # Root each net on `self` so it survives `__init__` — the bare
        # `port + port` chain returns a Net that's GC'd after __init__
        # if not stored.
        self.amp_ctrl_nets = [
            self.amp_ctrl[i] + gp
            for i, gp in enumerate(self.mcu.gpio_list)
        ]

        # Parent-to-child wiring: `parent.bus[i] + child.amp_ctrl[i]`
        # (see `references/advanced-patterns.md` for a worked example)
```

The list form behaves like any indexable port (`self.amp_ctrl[3]`). The dict form
is required when the index set has gaps — a list with `[None, None, ...]` padding
will not work because every element must be a `Port`. Build-time error if you
mismatch: `port GPIO[15] is not mapped to a symbol pin` from the `BoxSymbol` side.
See `jitx-port-3-to-4/references/construct-map.md` §3 for the parallel guidance.

## Board outline / shapes

The board outline is set as the `shape` attribute of the design's `Board`,
**not** via a `RoundedRectangle` class (there is no such class):

```python
from jitx.shapes.composites import rectangle

class MyDesign(Design):
    def __init__(self):
        super().__init__()
        self.board.shape = rectangle(80.9, 50.0, radius=3.0)
```

`rectangle(w, h, *, radius=None)` is a **function** in
`jitx.shapes.composites`, not a class — the `radius=` kwarg rounds the
corners. `SampleDesign` ships a default `SampleBoard(shape=rectangle(50,
50, radius=5))`; override `self.board.shape` to change it, or subclass
`Board`.

For arbitrary curved outlines (notched boards, mixed-curve perimeters),
use `ArcPolygon` from `jitx.shapes.primitive` (**singular** —
`jitx.shapes.primitives` does not exist, nor does `from jitx.shapes
import Arc`):

```python
from jitx.shapes.primitive import Arc, ArcPolygon, Polygon, Circle
```

Use `ArcPolygon` only when `rectangle(w, h, radius=...)` can't express
the shape.

## Pour import path

`Pour` is in `jitx` (top-level) or `jitx.copper` — **NOT** in
`jitx.feature` (despite living alongside `Silkscreen` / `Soldermask` /
`Cutout` in the surface-feature family):

```python
from jitx import Pour              # preferred
# OR
from jitx.copper import Pour       # also fine
```

`from jitx.feature import Pour` raises `ImportError`. See the copper pour
layer-indices section below for the `Pour(shape, layer=..., ...)`
signature.

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

### Snap computed values to a standard E-series

There is no JITX-side helper that snaps a computed passive value to the
nearest E12/E24 standard value. The JITX parts DB only stocks standard
values, and an off-series request raises
`ValueError: No components meeting requirements: {'category': 'capacitor',
'capacitance': 1.375e-08}` — the error names the requested value but does
not suggest snapping. Snap **before** constructing the part. The `eseries`
Python package handles this; a tiny inline helper also works for one-off
use:

```python
import math

_E12 = (10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82)

def _round_e12(value: float) -> float:
    if value <= 0:
        return value
    decade = 10 ** math.floor(math.log10(value))
    norm = value / decade
    for v in _E12:
        if v / 10 >= norm:
            return v / 10 * decade
    return _E12[0] * decade * 10

# Soft-start cap for a TPS62933 — formula yields 1.375e-8, not a stocked value:
css = _round_e12(2.0e-3 * 5.5e-6 / 0.8)        # 1.5e-8, in DB
self.c_ss = Capacitor(capacitance=css)
self.c_ss.insert(self.buck.SS, self.GND)
```

### Strap-helper expansion

JITX 4.x has no `bypass-cap-strap`, `cap-strap`, or `res-strap` helper.
Expand inline — instantiate the passive on `self.*` and wire both ports:

```python
# Equivalent of Stanza bypass-cap-strap(VDD, GND, 100e-9):
self.c_bypass = Capacitor(capacitance=100e-9, case="0402")
self.c_bypass.insert(self.VDD, self.GND)

# Equivalent of res-strap(net_a, net_b, value):
self.r_pullup = Resistor(resistance=10e3, case="0402")
self.r_pullup.insert(self.net_a, self.net_b)
```

The `self.` prefix is **mandatory** — local-variable passives get
garbage-collected at the end of `__init__` and the component drops out
of the netlist (see Key Rule 1 above).

For circuits that need many straps, **write them out explicitly** —
one `self.<name> = Capacitor(...)` line per cap. The natural Python
shortcut of stamping caps in a loop with `setattr(self, f"_bypass_{i}", c)`
**violates the No-setattr rule** in `jitx-skills:jitx/SKILL.md`
§"Don'ts" and triggers a cryptic translation-time failure
(`Unable to map local reference N, parent <Circuit> is not an
ancestor of child <Port>`, with the misleading "child" pointer at
`jitx/__init__.py:32`). Three real pd_audio sessions hit this same
trap on bypass-cap loops; the only working pattern is explicit
assignment:

```python
# ✅ One self.<name> = ... per cap. Boring is correct.
self.c_pwr_10u = Capacitor(capacitance=10e-6, case="0805")
self.c_pwr_10u.insert(self.mcu_power_p, self.mcu_power_n)
self.c_pwr_1u = Capacitor(capacitance=1e-6, case="0402")
self.c_pwr_1u.insert(self.mcu_power_p, self.mcu_power_n)
self.c_vdda = Capacitor(capacitance=1e-6, case="0402")
self.c_vdda.insert(self.vdda_p, self.vdda_n)
```

If the explicit list is long enough to itch (≥ 5 caps between the
same two rails), the right factoring is a small helper `Circuit`
subclass with named attributes — **not** a loop that stamps
`self.*` via `setattr`:

```python
class _PowerDecoupling(Circuit):
    """N caps between the same two rails. Add caps as named attrs."""
    p = Port()
    n = Port()
    def __init__(self) -> None:
        self.c_10u = Capacitor(capacitance=10e-6, case="0805")
        self.c_10u.insert(self.p, self.n)
        self.c_1u  = Capacitor(capacitance=1e-6, case="0402")
        self.c_1u.insert(self.p, self.n)
        self.c_100n = Capacitor(capacitance=100e-9, case="0402")
        self.c_100n.insert(self.p, self.n)
```

then `self.decoupling = _PowerDecoupling(); self.decoupling.p + ...`.

### Mounting holes — no jitxlib helper

`add-mounting-holes` from Stanza has **no Python equivalent** —
`jitxlib.mechanical` does not exist. Define a PTH mounting-hole
`Component` manually and instantiate it at explicit board-relative
coordinates. **Silent omission**: the design builds without it and the
fabbed board has no mounting points. Common dimensions:

| Screw | Drill | Annular ring (pad) | Notes |
|---|---|---|---|
| M2 | 2.2 mm | 4.0 mm | clearance fit |
| M2.5 | 2.7 mm | 4.5 mm | clearance fit |
| M3 | 3.2 mm | 5.5 mm | clearance fit |
| M4 | 4.3 mm | 7.0 mm | clearance fit |
| #4-40 | 2.95 mm | 5.0 mm | imperial |

Model the hole as a `Component` with a single `Port()`, a custom
`Landpattern` containing a `THPad` of the right size and a hole, then
instantiate at corners of the board outline.

### Relaxing query defaults for outsize parts — `with <Query>.refine(...)`

`Design.capacitor_defaults` / `resistor_defaults` / `inductor_defaults` set **global** query constraints that apply to every `Capacitor()` / `Resistor()` / `Inductor()` call in the design. A common default is `CapacitorQuery(case=["0402","0603","0805"])`. Large bulk parts — 100µF+ ceramics, 330µF electrolytics for class-D amp PVDD, large film caps — are not manufactured in those case sizes, and the query returns no match. The build then fails with `no component satisfying CapacitorQuery(...)`.

Use the `refine()` context manager to relax a constraint **only for the duration of a `with` block**. `PassiveQuery` inherits `jitx.context.Context` so the returned query is a real context manager; outside the block, the original `Design` defaults are restored:

```python
from jitxlib.parts import Capacitor, CapacitorQuery

# Design has CapacitorQuery(case=["0402","0603","0805"]) as default.
# 330µF electrolytic doesn't exist in those case codes — relax it:
with CapacitorQuery.refine(case=None):
    self.c_pvdd_a = Capacitor(capacitance=330e-6, rated_voltage=35.0)
    self.c_pvdd_a.insert(self.PVDD, self.GND)
    self.c_pvdd_b = Capacitor(capacitance=330e-6, rated_voltage=35.0)
    self.c_pvdd_b.insert(self.PVDD, self.GND)

# After the `with` block, c_bypass uses the original 0402/0603/0805 default:
self.c_bypass = Capacitor(capacitance=100e-9)
```

`refine(case=None)` removes the case constraint entirely; `refine(case=["1210","2220"])` overrides it with different cases. The same pattern applies to `ResistorQuery.refine(...)` and `InductorQuery.refine(...)` for high-power resistors and large-current inductors. Verified: `py-jitx-parts/src/jitxlib/parts/query_api.py:522`; live use at `TEC-example/tec_example/circuits/amplifiers.py:117`.

⚠ **Inductor query defaults over-constrain RF / sub-nH values.** A
top-level `inductor_defaults = InductorQuery(mounting="smd")` is fine
for most designs, but small RF inductors (≤ 10 nH 0402 / 0201) often
don't satisfy the implicit case constraint that comes with the
default query. When `Inductor(inductance=…)` fails with "No
components meeting requirements" on a sub-10-nH value, the first
probe is `Inductor(inductance=2.0e-9, case="0402")` (explicit case)
or — for one-shot relaxation — `with InductorQuery.refine(case=None):`.
The error message names the requested inductance but does **not**
name the implicit case set, so the cause is opaque without this hint.

> ⚠️ **Polymer/electrolytic cap crash on `C ≳ 100µF` + `V ≥ 25V`.** A
> `Capacitor(capacitance=C, rated_voltage=V)` query in that range may
> resolve to a part whose symbol is a `PolarizedCapacitorSymbol`, and the
> jitxlib build pipeline then crashes during `build_two_pin_mappings`:
>
> ```
> File ".../jitxlib/parts/_build.py", line 434, in build_two_pin_mappings
>     sym_map = {component.p1: symbol.p[1], component.p2: symbol.p[2]}
>                              ^^^^^^^^
> AttributeError: 'PolarizedCapacitorSymbol' object has no attribute 'p'
> ```
>
> This is an upstream jitxlib bug (`jitxlib-parts 1.1.0a0`, jitx 4.1.0a7),
> not a user error — `build_two_pin_mappings` assumes `symbol.p[i]` is
> always present. Same crash with `Capacitor(mpn="UCD1V331MNL1GS")`
> (Nichicon 330µF/35V polymer) and similar.
>
> Workaround until upstream lands a fix: derate to MLCC territory, or pin
> a specific non-polarized MPN.
>
> ```python
> # Stays in MLCC territory (≤22µF), avoids the polarized symbol path:
> self.c_bulk = Capacitor(capacitance=22e-6, rated_voltage=35.0)
> ```


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

A `Net` symbol can be attached two equivalent ways. Prefer the
constructor kwarg when the symbol is known at net-creation time —
it keeps the symbol declaration adjacent to the net definition.
Same top-level restriction as Net naming above — `PowerSymbol()` /
`GroundSymbol()` only in `TOP_LEVEL_PATH` (default `designs/`); under
`scripts/grep_gates.sh` this is a hard-fail outside the top-level
design path.

```python
# Top-level design only.

# Pattern A — constructor kwarg (preferred):
self.GND = Net(
    [self.power.GND_out, self.amps.gnd, self.controller.gnd],
    name="GND",
    symbol=GroundSymbol(),
)

# Pattern B — attribute assignment (use when ports are added later):
self.GND = Net(name="GND")
self.GND.symbol = GroundSymbol()    # attribute assignment, NOT insert()
```

Full signature: `Net(ports: Iterable = (), *, name=None, symbol=None)`.
Both `name` and `symbol` are keyword-only.

`+=` on a `Net` that already has a `symbol` attached **preserves the
symbol** while attaching new geometry / ports — the two forms
compose:

```python
self.GND = Net([...], name="GND", symbol=GroundSymbol())
self.GND += Pour(shape, layer=0, rank=1)   # symbol survives
self.GND += Pour(shape, layer=1, rank=1)
```

⚠ `+=` is forbidden on bare `Port` attributes (see §"Port
immutability" above); the rule above is `+=` on a `Net`, which is fine.

## Copper pour layer indices

`Pour(shape, layer=…, rank=…)` from `jitx.copper` takes an integer
`layer`. The integer is interpreted by the design's `Substrate` / `Stackup`, with a
consistent convention across stackups. (`Pour(..., isolate=…)` is legacy —
see `references/advanced-patterns.md` §"`isolate=` is legacy"; express
non-default clearance via `design_constraint(...)` with Tags instead.)

| Layer | Index (top-down) | Index (negative / bottom-up) | Notes |
|---|---|---|---|
| Top copper | `0` | (same) | `Side.Top == 0` |
| Inner 1 (from top) | `1` | `-(N-1)` | only on 4+ layer boards |
| Inner 2 (from top) | `2` | `-(N-2)` | only on 6+ layer boards |
| Bottom copper | `N - 1` | `-1` | `Side.Bottom == -1` |

Both conventions reach the same physical layers — pick one and stay consistent
within a design. The negative form pairs naturally with `symmetric_routing_layers`
(which maps `k → -k - 1` internally; `py-jitx/src/jitx/si.py:984-1004`).

**Examples by stackup**:

```python
# 2-layer board:
self.GND += Pour(shape, layer=0,  rank=1)  # top
self.GND += Pour(shape, layer=-1, rank=1)  # bottom (or layer=1)

# 4-layer board (e.g. JLC04161H_1080) — all-positive form:
self.GND += Pour(shape, layer=0, rank=1)   # top
self.GND += Pour(shape, layer=1, rank=1)   # inner 1
self.VCC += Pour(shape, layer=2, rank=1)   # inner 2 (power plane)
self.GND += Pour(shape, layer=3, rank=1)   # bottom

# 4-layer board — symmetric form (equivalent):
self.GND += Pour(shape, layer=0,  rank=1)
self.GND += Pour(shape, layer=1,  rank=1)
self.VCC += Pour(shape, layer=-2, rank=1)
self.GND += Pour(shape, layer=-1, rank=1)
```

Reference: `~/jitx/TEC-example/tec_example/main.py:145-148` uses the all-positive
form on a JLCPCB 4-layer board.

## DNP / do-not-populate

There is no `dnp=True` kwarg on `Resistor` / `Capacitor` / `Component`. The
authoritative fields are `in_bom: bool | None` and `soldered: bool | None` on
`jitx.Component` (`py-jitx/src/jitx/component.py:93,98`). Three patterns are
supported — see the construct-map's §"Do-not-populate (DNP)" entry for the full
write-up. Quick summary:

```python
# Pattern A — built-in subclass (preferred when DNP is part of the design intent):
# Import from `jitx.component` — `NonPopulatedComponent` is NOT re-exported from
# `jitx/__init__.py` in 4.0.5, so `from jitx import NonPopulatedComponent` raises
# ImportError. The class itself lives at jitx/component.py:150.
from jitx.component import NonPopulatedComponent
class CFG1Pulldown(NonPopulatedComponent):
    ...

# Pattern B — class-level override on any Component subclass:
class MyOptionalIC(jitx.Component):
    in_bom = False
    soldered = False

# Pattern C — instance-level override (one-off DNP on a query-API passive):
self.c_filter = Capacitor(capacitance=10.0e-12, case="0402")
self.c_filter.in_bom   = False
self.c_filter.soldered = False
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

### Step 4: Audit for silent wiring errors

A `status: ok` build does not catch wiring errors where every port is in
*some* net but the wrong net. After the build passes, walk the six-section
checklist in `jitx-skills:jitx/references/export-verification.md`:

- A. Net inventory — every named net you intended exists
- B. Connector pin assignment — connector port order matches datasheet
- C. Power topology — VCC = raw input, VDD = regulated; rail inversion
  is silent and produces wrong voltages on PVDD / I²C pullups
- D. Component output pins — no floating `OUT_*` / `BST_*` / `SW`
- E. Passive count sanity — counts roughly match datasheet's "Typical
  Application" schematic; large discrepancies indicate a missing
  application-circuit wrapper
- F. Control-signal completeness — distinguish MCU-driven from tie-off
  nets; forgotten GPIO wiring looks identical to intentional tie-off

## Formatting

Format all generated circuit code with ruff:

```bash
ruff format path/to/file.py
```
