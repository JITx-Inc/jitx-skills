# 04 — `supports` / `require` → `@provide` / `require()`

The Stanza `supports` clause encodes either flexibility or a fixed mapping. The Python `@provide` decorator family expresses the same. **Both halves of the pair matter**: a `supports` declaration on the component side is half the construct; the `require` call site on the consumer side is the other half. Porting only one half loses the bind.

Before reading the four shapes below, run the **hardware-analysis gate** from `jitx-skills:jitx-pin-assignment` §"Hardware-analysis gate". Most Stanza `require` clauses are **fixed wiring**, not pin-mux. But the inverse trap is also real: if you skip `supports` entirely and hardcode specific pins, the layout engine loses every degree of freedom the component author granted. A Stanza-source-to-Python audit must check both directions.

## Shape A — single fixed mapping

The component exposes one peripheral on one specific pin group. There is no flexibility, but the `supports` form lets consumers ask for the interface by **bundle type** instead of by pin name.

### Stanza 3.x

```stanza
public pcb-component ESP32-S3 :
  pin-properties :
    [pin:Ref      | pads:Int ... | side:Dir]
    [GPIO[19]     | 25            | Right]
    [GPIO[20]     | 26            | Right]
    ; ... other pins ...

  supports usb-2-data :
    usb-2-data.N => self.GPIO[19]
    usb-2-data.P => self.GPIO[20]
```

Consumer:

```stanza
pcb-module my-board :
  inst mcu : ESP32-S3
  require usb : usb-2-data from mcu
  net (usb.N power.usb.N)
  net (usb.P power.usb.P)
```

### Python 4.x

```python
from jitx.common import GPIO
from jitx.net import provide
from jitxlib.protocols.usb import USB2

class ESP32_S3_Wrapper(jitx.Circuit):
    @provide.one_of(USB2)
    def provide_usb(self, usb: USB2):
        return [
            {usb.data.n: self.mcu.GPIO[19], usb.data.p: self.mcu.GPIO[20]},
        ]
```

Consumer:

```python
class MyBoard(Circuit):
    def __init__(self):
        self.mcu = ESP32_S3_Wrapper()
        usb = self.mcu.require(USB2)
        self.usb_n = usb.data.n + self.power.usb_n
        self.usb_p = usb.data.p + self.power.usb_p
```

**Why `one_of` with a single-element list and not plain `@provide`?** A `@provide.one_of(USB2)` with one mapping is still the right form when there are zero alternatives — it keeps the consumer interface uniform (always `require(USB2)`) so a later author can add alternative mappings without rewiring callers.

## Shape B — multiple polarity / lane options on one provider

The component (or its wrapper) advertises N mappings for the same interface; the layout engine picks one. The Stanza idiom is multiple `option :` blocks inside one `supports`.

### Stanza 3.x

```stanza
pcb-module speaker-terminal :
  inst c : database-part(["mpn" => "DB128L-5.08-2P-BK-S", "manufacturer" => "DIBO"])
  supports diff-pair :
    option :
      diff-pair.N => c.p[1]
      diff-pair.P => c.p[2]
    option :
      diff-pair.N => c.p[2]
      diff-pair.P => c.p[1]
```

Consumer:

```stanza
pcb-module amp :
  inst spk : speaker-terminal
  require dp : diff-pair from spk
  net (dp.P amp-out.P)
  net (dp.N amp-out.N)
```

### Python 4.x

```python
from jitx.net import DiffPair, provide

class SpeakerTerminal(jitx.Circuit):
    @provide.one_of(DiffPair)
    def provide_diff_pair(self, dp: DiffPair):
        return [
            {dp.n: self.c.p[1], dp.p: self.c.p[2]},   # default polarity
            {dp.n: self.c.p[2], dp.p: self.c.p[1]},   # swapped polarity
        ]
```

Consumer:

```python
class Amp(Circuit):
    def __init__(self):
        self.spk = SpeakerTerminal()
        dp = self.spk.require(DiffPair)
        self.dp_p = dp.p + self.amp_out_p
        self.dp_n = dp.n + self.amp_out_n
```

The layout engine picks whichever option produces cleaner routing. Hardcoding `self.spk.c.p[1] + amp_out_p` loses this — the layout engine cannot swap.

## Shape C — `for p in pins(...) do : supports gpio : ...` (one provider per pin)

The component advertises one independent provider per pin. Each `require(GPIO)` on the consumer side claims one of the offers.

### Stanza 3.x

```stanza
public pcb-component ESP32-S3 :
  ; GPIO[0..14, 17..21, 33..38, 45, 46] declared in pin-properties
  val reserved-io = [self.GPIO[0] self.GPIO[45] self.GPIO[46] self.GPIO[33]
                     self.GPIO[34] self.GPIO[35] self.GPIO[36] self.GPIO[37]]
  for p in pins(self.GPIO) do :
    if not contains?(reserved-io, p) :
      supports gpio :
        gpio.gpio => p
```

Consumer:

```stanza
pcb-module my-board :
  inst mcu : ESP32-S3
  require led : gpio from mcu
  require btn : gpio from mcu
  net (led.gpio my-led.anode)
  net (btn.gpio my-button.p[1])
```

### Python 4.x

```python
from jitx.common import GPIO
from jitx.net import provide

class ESP32_S3_Wrapper(jitx.Circuit):
    def _free_iomux_gpios(self) -> list[Port]:
        return [
            self.mcu.GPIO[1], self.mcu.GPIO[2], self.mcu.GPIO[4],
            # ... all non-reserved GPIOs ...
        ]

    @provide(GPIO)
    def provide_gpio(self, g: GPIO):
        return [{g.gpio: pin} for pin in self._free_iomux_gpios()]
```

Consumer:

```python
class MyBoard(Circuit):
    def __init__(self):
        self.mcu = ESP32_S3_Wrapper()
        led_gpio = self.mcu.require(GPIO)
        btn_gpio = self.mcu.require(GPIO)
        self.led_net = led_gpio.gpio + self.my_led.anode
        self.btn_net = btn_gpio.gpio + self.my_button.p[1]
```

Note `@provide(GPIO)` (no `.one_of`) — Stanza's `supports gpio` repeated N times maps to a single Python `@provide(GPIO)` returning N mappings, **each a separate offer**. Use `@provide.one_of` only when at most one of the offers is taken.

## Shape D — `for i in 0 to N do : supports proto : option ... option ...` (per-instance flexibility)

A wrapper has N independent instances, each with its own multi-option provider. Each `require(Proto)` on the consumer side claims one instance.

### Stanza 3.x

```stanza
pcb-module speaker-terminal-3ch :
  inst c : database-part(["mpn" => "DB128L-5.08-2P-BK-S", "manufacturer" => "DIBO"])[3]
  for i in 0 to 3 do :
    supports diff-pair :
      option :
        diff-pair.N => c[i].p[1]
        diff-pair.P => c[i].p[2]
      option :
        diff-pair.N => c[i].p[2]
        diff-pair.P => c[i].p[1]
```

Consumer:

```stanza
pcb-module amps :
  inst speaks : speaker-terminal-3ch
  require speaker : diff-pair[3] from speaks
  net (speaker[0] stereo.out[0])
  net (speaker[1] stereo.out[1])
  net (speaker[2] sub.out)
```

### Python 4.x

```python
from jitx.net import DiffPair, provide

class SpeakerTerminal3Ch(jitx.Circuit):
    def __init__(self):
        self.c = [Part(mpn="DB128L-5.08-2P-BK-S", manufacturer="DIBO")
                  for _ in range(3)]

    @provide(DiffPair)
    def provide_diff_pair(self, dp: DiffPair):
        # One offer per connector, each with two polarity options.
        # @provide (not .one_of) means each connector is independently
        # claimable by a separate require(DiffPair) call.
        return [
            *[{dp.n: c.p[1], dp.p: c.p[2]} for c in self.c],   # default
            *[{dp.n: c.p[2], dp.p: c.p[1]} for c in self.c],   # swapped
        ]
```

> ⚠️ Shape D is the **only one of the four** where the cardinality of the consumer's `require` call has to match the cardinality the component declares. If `speaks` exposes 3 connector instances and the consumer calls `require(DiffPair)` four times, the build fails. Mirror the Stanza `[3]` count in the Python list-of-Resistor / list-of-Part literal and in the consumer's `require()` count.

Consumer:

```python
class Amps(Circuit):
    def __init__(self):
        self.speaks = SpeakerTerminal3Ch()
        self.stereo = TAS5825Stereo()
        self.sub = TAS5825PBTL()

        spk0 = self.speaks.require(DiffPair)
        spk1 = self.speaks.require(DiffPair)
        spk2 = self.speaks.require(DiffPair)

        self.net0_p = spk0.p + self.stereo.out_a_p
        self.net0_n = spk0.n + self.stereo.out_a_n
        self.net1_p = spk1.p + self.stereo.out_b_p
        self.net1_n = spk1.n + self.stereo.out_b_n
        self.net2_p = spk2.p + self.sub.out_p
        self.net2_n = spk2.n + self.sub.out_n
```

## The `differential-constraint` helper recipe

A common Stanza idiom is to define a reusable helper that bundles `net + topology-segment + structure + timing-difference`:

```stanza
public defn differential-constraint (in1, out1, in2, out2) :
  inside pcb-module :
    net (in1 out1)
    net (in2 out2)
    topology-segment(in1 out1)
    topology-segment(in2 out2)
    structure(in1 => out1, in2 => out2) = differential
    timing-difference(in1 => out1, in2 => out2) = TimingDifferenceConstraint(-1.e-12, 1.e-12)
```

Don't transcribe this inline at every call site. Port it as a Python **function** that returns a `ConstrainDiffPair`:

```python
from jitx import Toleranced
from jitx.si import ConstrainDiffPair, Topology

def differential_constraint(in1, out1, in2, out2, structure):
    topo_a = in1 >> out1
    topo_b = in2 >> out2
    return (
        ConstrainDiffPair(Topology(in1, out1), Topology(in2, out2))
        .structure(structure)
        .timing_difference(Toleranced.min_max(-1e-12, 1e-12))
    )
```

The caller side is then a single line per pair, not a six-line inline block. Functions composed of `>>` / `Constrain*` operators run at `__init__` time and produce live constraint objects in the JITX object graph.

## Audit checklist for a port

For every Stanza `supports` clause, locate the corresponding Python `@provide`:

- [ ] Each `supports <bundle>` in a `pcb-component` has a matching `@provide` or `@provide.one_of` in the corresponding `Circuit` wrapper. **Put `@provide` on the wrapper `Circuit`, not directly on the `Component`** — see §"Where to put `@provide`: wrapper `Circuit`, not `Component`" below for the rationale.
- [ ] Each `option :` block inside a `supports` clause becomes a separate mapping in the `@provide.one_of` return list.
- [ ] Each `for ... do : supports ...` loop becomes either `@provide` (independent providers) or a flattened-options `@provide.one_of` list — choose by whether consumers will `require` the provider multiple independent times (Shape C / D) or only once with N options (Shape B).
- [ ] Each `require X : <bundle> from <inst>` in Stanza has a matching `self.<inst>.require(<Bundle>)` on the Python side.
- [ ] The cardinality of consumer `require()` calls matches the cardinality offered by the wrapper (Shape D constraint).

Audit each Stanza file in the design; check the boxes; surface any unmatched `supports` / `require` pair as a Phase 4 blocker, not a TODO.

## Where to put `@provide`: wrapper `Circuit`, not `Component`

Stanza `pcb-component` blocks can host `supports` clauses directly on
the component, so the naive Python translation is to put `@provide` on
a `jitx.Component` subclass:

```python
class MyMCU(jitx.Component):
    GPIO: dict[int, Port] = {i: Port() for i in range(16)}

    @provide(I2C)
    def provide_i2c(self, i2c: I2C):
        return [{i2c.sda: self.GPIO[1], i2c.scl: self.GPIO[2]}]
```

The framework handles `@provide` on `Component` and `@provide` on
`Circuit` similarly at the implementation level, so the build often
works. The reason to **not** do this is **architectural**, not
technical:

- A `Component` models a **physical part** — its pins, symbol,
  landpattern, MPN. That description is the same in every design that
  uses the part.
- A `@provide` clause is a **policy decision** about which of the
  part's pins are eligible to serve which logical interface. Different
  designs may want different policies (e.g. one design pins I²C to
  GPIO[1..2], another to GPIO[8..9], a third forbids I²C on any GPIO
  that's already routed to a high-speed signal).

Mixing the two concerns on the `Component` makes the component
non-reusable across designs that want different pin-mapping policies.
Keeping `@provide` on a wrapper `Circuit` cleanly separates the
physical-part description from the design-time pin-assignment policy:

> ❌ Don't put `@provide` / `@provide.one_of` / `@provide.subset_of`
> on a `jitx.Component` subclass.
> ✅ Put it on a `Circuit` that wraps the component, exposing the
> component's pins via attribute access from inside the `@provide`
> method.

### Wrapper-Circuit pattern

```python
class MyMCU(jitx.Component):
    GPIO: dict[int, Port] = {i: Port() for i in range(16)}
    # (no @provide here — Component is a pure pin/symbol/landpattern carrier)

class MyMCUWrapper(jitx.Circuit):
    """Adds layout-flexibility advertisements over MyMCU's pins."""

    def __init__(self):
        self.mcu = MyMCU()

    @provide(I2C)
    def provide_i2c(self, i2c: I2C):
        return [{i2c.sda: self.mcu.GPIO[1], i2c.scl: self.mcu.GPIO[2]}]
```

Consumers then write `self.mcu_wrapper = MyMCUWrapper()` and
`i2c = self.mcu_wrapper.require(I2C)` exactly as before.

### Hardwire fallback (when flexibility doesn't matter)

If the layout flexibility a Stanza `supports` clause expressed isn't
load-bearing for the port (e.g. you're just trying to get a baseline
build), it's also fine to skip the wrapper entirely and assign specific
pins inline:

```python
class MyCircuit(Circuit):
    def __init__(self):
        self.mcu = MyMCU()
        # Hardwired — no pin-mux solver involvement:
        self.SDA = self.i2c.sda + self.mcu.GPIO[1]
        self.SCL = self.i2c.scl + self.mcu.GPIO[2]
```

This loses the router degrees of freedom but is a perfectly valid Phase
4 exit if the wrapper-`Circuit` route is more refactoring than the port
warrants. Document the choice in `PORT-DEFERRED.md` so a future pass
can re-introduce the wrapper.
