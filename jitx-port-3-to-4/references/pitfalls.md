# Pitfalls & Non-Obvious Differences

Things that bite during a port and aren't covered by the construct map.

## Object construction model

- **Stanza modules return values** (a `pcb-module` body produces the module). **Python `Circuit` subclasses build via attribute assignment in `__init__`** — there is no "return" of the circuit. Don't try to write `return self` or paraphrase the Stanza expression-style body as a Python expression.
- **Instance declarations** in Stanza (`inst foo : my-component`) become `self.foo = MyComponent()` in Python `__init__`. Order in `__init__` matters when later code references earlier instances.

## Component lifecycle (GC trap) ⚠️ most common port failure

Every `Resistor(...)`, `Capacitor(...)`, and `Inductor(...)` **must be assigned to a `self.*` attribute**. If you create a component and call `.insert()` without assigning it, Python's garbage collector destroys the component object before translation runs. The component's ports remain in nets (`.insert()` saves them via an `InsertContainer`), but the component itself is unreachable from the circuit's attribute tree — so `idmap.set_parent` is never called for it. Translation then fails with:

```
Unable to map local reference N, parent <Circuit> is not an ancestor of child <Port>
```

This error is cryptic — it names an internal reference number, not the passive you forgot to assign.

**Always use the two-step form:**

```python
# WRONG — component is GCd before translation:
Capacitor(capacitance=10e-6).insert(self.VDD, self.GND)

# RIGHT — component survives until translation:
self.c_bypass = Capacitor(capacitance=10e-6)
self.c_bypass.insert(self.VDD, self.GND)
```

The same rule applies to `Resistor` and `Inductor`. The Stanza 3.x idiom of creating passives inline has no safe equivalent in Python 4.x.

**Anonymous `port + port` expressions trigger the same error.** The `+` operator creates a `Net` object. If that object is not assigned to `self.*`, it is GCd and its ports lose their parent registration:

```python
# WRONG — Net is GCd:
self.esp.XTAL_P + self.xtal.OSC1

# RIGHT — Net survives:
self.xtal_p_net = self.esp.XTAL_P + self.xtal.OSC1
```

When a port is already a member of a named `Net`, use `+=` instead of `+`:

```python
self.VDD = Net(name="VDD")
self.VDD += self.buck.VIN      # safe: VDD is already on self
self.VDD += self.esp.VDD3P3
```

## Connectivity

- **Stanza connects by name (string-typed nets)** when you write `net pwr (a.vcc, b.vcc)`. **Python connects by Port object identity** with the `+` operator: `self.nets = [a.vcc + b.vcc]`. There is no global string namespace for nets in Python.
- **`+` is the net operator**, not topology. **`>>` is the topology (routed-graph) operator.** Mixing them produces type errors that pyright will catch — trust pyright here.
- **Named nets** (e.g., labeling `gnd` so it shows up in the schematic with that name) require explicit Python helpers; do not assume the Python form picks up names automatically.
- **`Net()` takes a single iterable of ports, not varargs.** A natural Stanza-style
  translation of `net VDD (a b c d)` to `Net(self.a, self.b, self.c, self.d, name="VDD")`
  raises `TypeError: Net.__init__() takes from 1 to 2 positional arguments but
  N positional arguments (and 1 keyword-only argument) were given`. The signature
  (`py-jitx/src/jitx/net.py:662-668`) is
  `Net(ports: Iterable = (), *, name=None, symbol=None)` — wrap the ports in a list:
  `Net([self.a, self.b, self.c, self.d], name="VDD")`.
- **Circuit-level `Port` attributes are immutable** — `self.port += self.other` raises
  `NotImplementedError: Ports are immutable. Use + to create a new net instead of +=`.
  This trips up the natural Stanza-style translation of `net (a, b)` into
  `self.a += b`. The correct pattern is to create a `Net` first, then `+=` into the net:

  ```python
  # WRONG — Port += Port:
  self.i2c_sda += self.stereo.SDA   # NotImplementedError

  # RIGHT — named net:
  self.I2C_SDA = Net(name="I2C_SDA")
  self.I2C_SDA += self.i2c_sda + self.stereo.SDA
  ```

## Naming

- ❌ **Do not name the ported design class `SampleDesign`** when subclassing
  `jitx.sample.SampleDesign`. Python rebinding makes
  `class SampleDesign(SampleDesign): ...` technically legal but confuses readers
  and static analysis tools. Pick something distinctive (`TecDesign`, `MyBoard`,
  `EthernetIODesign`).

### Net naming across hierarchy

A Stanza design happily declares `net GND (...)` in every `pcb-module`, and the
merger collapses them all into the same top-level `GND` net. The natural Python
port — `Net([...], name="GND")` in every nested `Circuit` — builds cleanly
through instantiation and translation, then fails at the build step with:

```
status: error
message: Public name GND already in use
```

The message names the colliding name but not the source locations. Multiple
sibling circuits each declaring `Net(..., name="GND")` is the typical cause;
the same applies to any rail name reused across modules (`VDD`, `P3V3`, …).

**Rule: name nets at the top level only.** Sub-circuit nets that will be
unified by the parent should be left anonymous (`Net([...])` with no `name=`);
the top-level `name="GND"` carries through after unification.

```python
class PowerSupplies(Circuit):
    def __init__(self):
        self.GND = Net([...])                         # no name=

class Amplifiers(Circuit):
    def __init__(self):
        self.GND = Net([...])                         # no name=

class PdAudio(Circuit):
    def __init__(self):
        self.power = PowerSupplies()
        self.amps = Amplifiers()
        self.GND = Net([
            self.power.GND, self.amps.GND, ...
        ], name="GND")                                # name= only here
```

Cross-reference: construct-map.md §5 row "named net".

## Pins, ports, and direction

- Stanza `pin.up` / `pin.down` (schematic placement direction) maps to **Python `Pin.up()` / `Pin.down()` / `Pin.right()` — these are method calls returning configured pin objects**, not enum values. Easy to mistype.
- Stanza `pin-properties` declarations cover pin number + name + direction in one block. The Python form splits this across `Pin` (logical), `Pad` (physical), and the symbol/landpattern mapping objects.
- **Stanza port arrays with non-contiguous valid indices must use a `dict`,
  not a `list`, in Python.** Many MCU packages with depopulated pins (e.g.
  ESP32-S3 FN8 has GPIOs 0–14, 17–21, 33–38, 45, 46 but not 15, 16, 22–32,
  39–44) cannot be modeled as a dense `[Port() for _ in range(N)]` — the
  resulting non-physical entries fail at build time with
  `port GPIO[15] is not mapped to a symbol pin`.

  ```python
  # WRONG — dense list includes non-physical GPIO indices:
  GPIO = [Port() for _ in range(47)]

  # RIGHT — sparse dict, only physically-present indices:
  _gpio_indices = list(range(15)) + list(range(17, 22)) + list(range(33, 39)) + [45, 46]
  GPIO = {i: Port() for i in _gpio_indices}

  # Symbol unpacking from a dict-port-array uses .values():
  symbol = BoxSymbol(rows=Row(right=PinGroup(*GPIO.values(), ...)))
  ```

- **Do not use protocol bundle objects (e.g. `USB2()`, `I2C()`, `I2S()`) as class-level interface ports on `Circuit` subclasses.** Protocol bundles have nested sub-ports (e.g. `usb.data.p`, `usb.data.n`). These nested sub-ports do not function correctly as hierarchy boundary ports — wiring the parent-side bundle port to a child's internal net via `+=` silently fails or raises `NotImplementedError`. Use plain `Port()` instances instead:

  ```python
  # WRONG — USB2() nested sub-ports break at hierarchy boundary:
  class PowerSupplies(Circuit):
      usb = USB2()
  # ... then in top-level:
  self.power.usb.data.p += self.usb_conn.DP1  # fails

  # RIGHT — plain Port() works at any boundary:
  class PowerSupplies(Circuit):
      usb_dp = Port()
      usb_dn = Port()
  # ... then in top-level:
  self.dp_net = self.power.usb_dp + self.usb_conn.DP1
  ```

  Protocol bundles (`I2C`, `I2S`, `USB2`, etc.) are for **intra-circuit** wiring — connecting two ports within the same `Circuit.__init__`. They are not designed for cross-circuit hierarchy exposure.

## Provide / require

- Stanza `supports` / `require` and Python `@provide` / `@require` are *similar* but **not identical** in hierarchical composition. Cases that "just worked" in Stanza via implicit propagation may need an explicit `Provide(...)` declaration in Python.
- `@provide.one_of`, `@provide.subset_of`, `@provide.all_of` are the Python idioms for the patterns Stanza expressed via free-form `supports` clauses with conditions. See `jitx-pin-assignment` for which to use.
- **Silent failure — provide stub returning `[]`**: A `@provide.all_of(Bundle)` method
  that returns `[]` (an unfinished stub) silently satisfies every `require(Bundle)`
  call against it. The build prints `status: ok` even though the resulting bundle's
  ports are all unconnected. The only signal is a *"module port(s) have no internal
  connections"* warning in the build log. During a port, leave unimplemented
  providers as `raise NotImplementedError("PORT-DEFERRED: …")` so the build fails
  loudly until the stub is filled in. See `jitx-pin-assignment` §"Provide stub
  danger" for the canonical pattern.

## Power topology / net naming (mandatory Phase 4 check)

Stanza power-net naming is conventional: `VCC` is typically the **raw external
supply** (from the connector or input header), and `VDD` is typically the
**regulated output** (from a buck/LDO). The natural Python instinct is to use
`VCC` for the most prominent rail in the design — which is often the regulated
3.3 V, not the raw input. **This inversion produces a clean build with the
wrong voltage on PVDD / I²C pullups / copper pours.** The build will not
catch it; only Phase 7's power-topology check will.

Before naming any net in the Python port, read every Stanza `net` definition
that touches the input connector AND the regulator, and write down the
mapping explicitly:

```stanza
net VCC (conn.p[1])                     ; VCC = external input from connector
net VDD (vreg.vout)                     ; VDD = regulated output
net (VCC amps.pvdd.vdd)                 ; speaker supply = raw external
net (VDD amps.dvdd.vdd mcu.mcu-power.vdd)  ; digital supply = regulated
```

| Stanza net | Voltage | Python name |
|---|---|---|
| Connected to input connector AND regulator VIN | raw input | `VCC` |
| Connected to regulator VOUT | regulated | `VDD` |

If any amp PVDD / high-voltage speaker supply / motor-driver VBAT port
connects to the raw supply in Stanza, it **must** connect to the same net
as the regulator input in Python — not to a separate connector pin and not
to the regulated rail.

## Thermal vias

Stanza `add-thermal-vias(net, shape)` places a grid of through-hole vias
under a thermal pad and connects them to the given net. **There is no
direct equivalent function in JITX 4.x.** The closest API is a
`design_constraint(tag).stitch_via(...)` rule that the router applies
inside an existing copper pour:

```python
from jitx.constraints import design_constraint, Tag
from jitx.constraints import SquareViaStitchGrid

self.thermal_via_rule = design_constraint(
    self.GND_tag,
).stitch_via(
    MySubstrate.THVia,
    SquareViaStitchGrid(pitch=1.2, inset=0.3),
)
```

Prerequisites that aren't obvious from the API shape:

- The target net needs a `Tag` so the constraint can reference it.
- A copper **`Pour`** must already cover the thermal pad area — without
  the pour, `stitch_via` has nothing to fill and the constraint silently
  does nothing.
- This is a layout-quality concern (thermal performance), not a
  connectivity concern. A Phase 7 build will pass without thermal vias;
  flag them as a deferred task with a `PORT-DEFERRED.md` entry.

## Topology and constraints

- 4.x has first-class `RoutingStructure`, `DifferentialRoutingStructure`, `NeckDown`, `ReferencePlanes`, `InsertionLossConstraint`, `TimingDifferenceConstraint` — many of these had no first-class Stanza equivalent in 3.x and were expressed ad-hoc. Don't search the Stanza source for an exact match; reformulate from the design intent.
- `BridgingPinModel` / `TerminatingPinModel` attach to topology nodes. In Stanza these were often modeled as parametric components; in Python they are pin-model objects on the topology graph itself.
- **Differential routing structure on two single-ended `Constrain` calls is a silent error.** When the Stanza source applies a differential routing structure (e.g. USB D+/D−, LVDS, MIPI) to a pair of nets, do **not** translate it as two `Constrain(Topology(p_path)).structure(drs)` and `Constrain(Topology(n_path)).structure(drs)` calls. `Constrain.structure()` is typed to take `RoutingStructure` only, but at runtime nothing stops you from passing a `DifferentialRoutingStructure` — the build accepts it and the router treats P and N as independent single-ended signals. Coupling and skew are not enforced. The correct form is `ConstrainDiffPair(Topology(dp_begin, dp_end)).structure(drs).timing_difference(lo, hi)` where `dp_begin` / `dp_end` are `DiffPair()` bundles whose `.p` / `.n` sub-ports are joined to the actual signal nets with `+=`. See `construct-map.md` §9. Observed in the pd-audio port — the build was clean but the USB diff pair was wired without differential constraints.
- **`TimingDifferenceConstraint` has no chained form on plain `Constrain`.** `.timing_difference(lo, hi)` only exists on `BaseConstrainPairwise` (i.e. `ConstrainDiffPair`, `ConstrainReferenceDifference`). Silently omitting the timing constraint from a ported diff pair compiles cleanly — when porting, search the Stanza source for `TimingDifferenceConstraint` and ensure each occurrence has a matching `.timing_difference()` on the Python side.

## Passive queries

- **Global passive defaults silently break large parts.** `Design.capacitor_defaults = CapacitorQuery(case=["0402","0603","0805"])` is a typical setting and applies to every `Capacitor()` call in the design. Bulk electrolytics (≥47µF), large film caps, and high-current inductors are not stocked in those cases — the build fails with `no component satisfying CapacitorQuery(...)`. The fix is `with CapacitorQuery.refine(case=None):` (a context manager — `PassiveQuery` extends `jitx.context.Context`) around just the outsize part, leaving the global default intact for everything else. Same pattern for `ResistorQuery.refine` / `InductorQuery.refine`. Documented under `jitx-circuit-builder/SKILL.md` §"Relaxing query defaults".

## Board utilities

- **`add-mounting-holes` has no Python equivalent** as of `jitxlib-standard` 4.0.1. No `jitxlib.mechanical` module exists; no top-level helper exists. A porter who searches for "mounting hole" finds nothing, drops the call, and the build succeeds with no warning — the resulting board has no mounting points. When the Stanza source calls `add-mounting-holes`, define a PTH mounting-hole `Component` by hand, place it at explicit coordinates, and add a `PORT-DEFERRED.md` entry tracking the upstream gap.

## Build invocation gotchas

- **`python -m jitx build --port <PORT>`** — `--port` is the **TCP port for the JITX UI server**, not a PCB port. Easy to confuse mid-design.
- The Python build target is `<module>.<DesignClass>` (e.g., `mydesign.boards.MainBoard`), not a file path. Get this wrong and the build fails with "no design found", not a Python import error.
- Two installs in the same shell will cross-contaminate `PATH` and Conan envs. Use absolute paths or subshells. See `verification.md`.

## Stanza language idioms that trip up porters

- **`defmulti` dispatch** in Stanza often becomes a plain Python method, not `functools.singledispatch`. Python's `Circuit`/`Component` class hierarchy is rich enough that you rarely need open multimethod dispatch.
- **Stanza generators / `Seq` pipelines** map to Python list/generator comprehensions, not to a port of the Stanza sequence library.
- **`with-syntax` / parametric helpers** in Stanza often emitted families of designs at compile time. The Python equivalent is a plain factory function or a parameterized `Circuit` subclass; resist transcribing the macro structure.

## Package layout

- **Stanza `defpackage` paths are not Python module paths.** A file at `src/foo/bar.stanza` with `defpackage foo/bar` is unrelated to where Python will put `foo/bar.py`. Python module layout follows `pyproject.toml` conventions; design from the Python side.
- **Stanza `import` is package-granular.** Python `from jitx import Circuit, Component, Port` is symbol-granular. Listing the imports in the Python file is more verbose but more navigable.

## Verification gotchas

- A 3.x design that builds with warnings may produce a 4.x port that builds clean — the warnings often map to issues the 4.x type system catches at construction time. Don't treat "fewer warnings" as proof of correctness.
- Conversely, a 3.x design that builds *cleanly* and a 4.x port that builds *cleanly* still need export comparison — equivalent component placement and routing isn't guaranteed by passing builds alone.
- **`~/.jitx/current` symlink mismatch silently corrupts the build.** JITX reads runtime/config/plugin state via `~/.jitx/current/...` regardless of which versioned binary you launched. Repoint it to match the version you're invoking before each build (verified: a 4.x-pointing symlink while invoking a 3.x binary breaks Stanza export with `write-stable-id (False)` on every release tested 3.25.0 → 4.0.5).

## Invented API names — the recurring failure mode

These are real wrong guesses observed during porting passes. Every one of them follows the same anti-pattern: invent an import "by analogy" with another package, write a plausible-looking constructor, and don't verify against the source. Always confirm via the Rule 0 fallback chain in `../SKILL.md` before committing such code.

| ❌ Wrong guess | ✅ Actual API | Where |
|---|---|---|
| `from jitxlib.landpatterns.core import Landpattern` | `from jitx.landpattern import Landpattern, PadMapping` | `py-jitx/src/jitx/landpattern.py` |
| `BGADepop([(0,0)])` kwarg on `BGA(...)` | `.grid_planner(<GridPlanner subclass>)` — see `package-examples.md` Example 6 | `py-jitx-stdlib/src/jitxlib/landpatterns/grid_planner.py` |
| `BGA(rows=5, cols=5, ...)` | `BGA(num_rows=5, num_cols=5, ball_diameter=..., pitch=...)` | `py-jitx-stdlib/src/jitxlib/landpatterns/generators/bga.py` |
| `QFN_DEFAULT_LEAD_PROFILE` exported symbol | Build a `LeadProfile(span=..., pitch=..., type=QFNLead(...))` explicitly | `py-jitx-stdlib/src/jitxlib/landpatterns/generators/qfn.py` |
| `LeadProfile(..., SMDLead(length, width))` for QFN | `LeadProfile(..., QFNLead(length, width))` — base `SMDLead` requires `lead_type` and raises `TypeError: SMDLead.__init__() missing 1 required positional argument: 'lead_type'`. `QFNLead` defaults `lead_type = QuadFlatNoLeads`. | `py-jitx-stdlib/src/jitxlib/landpatterns/generators/qfn.py:102` |
| `from jitx.feature import Pour` (by analogy with `Silkscreen` / `Soldermask` / `Cutout`) | `from jitx import Pour` (re-exported from `jitx/__init__.py:54`) or `from jitx.copper import Pour`. **Not in `jitx.feature`.** | `py-jitx/src/jitx/copper.py:45` |
| `Net(self.a, self.b, self.c, name="VDD")` (varargs) | `Net([self.a, self.b, self.c], name="VDD")` — `Net()` takes a single iterable. | `py-jitx/src/jitx/net.py:662-668` |
| `from jitx import NonPopulatedComponent` | `from jitx.component import NonPopulatedComponent` — defined at `jitx/component.py:150` but NOT re-exported from `jitx/__init__.py` in 4.0.5. | `py-jitx/src/jitx/component.py:150` |
| `Pad.at(x, y, theta)` (positional rotation) | `Pad.at(x, y, rotate=theta)` — rotation is keyword-only. | `py-jitx/src/jitx/placement.py:104-106` |
| `.thermal_pad(width=4.0, height=4.0)` | `.thermal_pad(rectangle(4.0, 4.0))` — takes a `Shape`, not w/h kwargs | `py-jitx-stdlib/src/jitxlib/landpatterns/pads.py` (`thermal_pad`) |
| `.body(...)` chain method on a generator | `.package_body(RectanglePackage(width=..., length=..., height=...))` | `py-jitx-stdlib/src/jitxlib/landpatterns/pads.py` (`PackageBodyMixin`) |
| `SOT89_3()`, `SOT223_3()`, `SOT583_8()` generators | Only `SOT23_3`, `SOT23_5`, `SOT23_6` exist. Build a custom `Landpattern` subclass for SOT-89 / SOT-223 / SOT-583. | `py-jitx-stdlib/src/jitxlib/landpatterns/generators/sot.py` |
| `landpattern.add_pad(SMDPad(index=1, shape=Rectangle(...), center=(0,0)))` | Declare `p1 = SMDPad(copper=rectangle(...)).at(x, y)` as a class attribute on the `Landpattern` subclass. No `add_pad()`, no `index=`, no `center=`. | `py-jitx-stdlib/src/jitxlib/landpatterns/pads.py` |
| `Rectangle` as a class import | `Rectangle` is **not** a class. Use the function `rectangle(w, h, *, radius=None)` from `jitx.shapes.composites`. `Circle` *is* a class. | `py-jitx/src/jitx/shapes/composites.py` |
| `PadMapping({"PVDD": [3, 4], "EP": "thermal_pad"})` (string keys, int / string values) | `PadMapping({self.PVDD: [lp.p[3], lp.p[4]], self.EP: [lp.thermal_pads[0]]})` — keys are `Port` objects, values are `Pad` or `Sequence[Pad]` | `py-jitx/src/jitx/landpattern.py:99-198` |
| `Capacitor(min_rated_voltage=35.0)` | `Capacitor(rated_voltage=35.0)` | `py-jitx-parts/src/jitxlib/parts/query_api.py` (`CapacitorQueryDict`) |
| `Capacitor(temperature_coefficient="C0G")` | `Capacitor(temperature_coefficient_code="C0G")` — kwarg is `_code` | same |
| `RoundedRectangle(80.9, 50.0, 3.0)` | `rectangle(80.9, 50.0, radius=3.0)` from `jitx.shapes.composites`, assigned to `design.board.shape` | `py-jitx/src/jitx/board.py`, `shapes/composites.py` |
| `from jitxlib.protocols.serial import I2S` with ports `bclk`/`lrck`/`sdin` | `I2S` exists but its ports are `sck`/`ws`/`sd` — rename when porting from Stanza `bclk`/`lrck`/`sdmo` | `py-jitx-stdlib/src/jitxlib/protocols/serial.py:227` |
| `from jitxlib.protocols.serial import OctalSPI` | No bare `OctalSPI`. Use `OctalSPIwDQS` if your part has a DQS pin; otherwise define a local `jitx.Bundle` subclass. | `py-jitx-stdlib/src/jitxlib/protocols/serial.py:119` |
| `from jitxlib.protocols.serial import I2SMCK` | No `I2SMCK`. Define a local `jitx.Bundle` subclass with `sck`, `ws`, `sd`, `mclk`. | n/a |

> Every entry above was caught after the wrong code was already written, sometimes after it had silently compiled. **Verify before writing**, not after.

## Don't

- ❌ Describe Stanza as JVM-compiled — it is natively compiled via C.
- ❌ Mass-rename Stanza identifiers to Python style without re-running the build at each step. Identifier-rename mistakes cascade through the wiring.
- ❌ Skip `pyright` because "the build worked." Type errors mask wiring bugs.
- ❌ Invent an import path "by analogy" with another package. See "Invented API names" above.
