# 02 — `pcb-module` → `Circuit`

A two-instance module (R + C placeholder) with three named nets, alongside its Python `Circuit` form using `+` to build nets. Both halves **compile** against their respective JITX install (verified on 3.36.1 and 4.1.0).

(For brevity the second instance is also a resistor — in a real port it would be a capacitor; the construct mapping is what's being demonstrated.)

## Stanza 3.x source

```stanza
#use-added-syntax(jitx)
defpackage demo/rc-filter :
  import core
  import jitx
  import jitx/commands
  import ocdb/utils/defaults
  import ocdb/utils/generic-components

pcb-module rc-filter :
  ; External ports
  port vin
  port vout
  port gnd

  ; Two child instances — using the ocdb chip-resistor generator so the
  ; example stands alone without needing a sibling components package.
  inst R1 : chip-resistor(1.0e3)
  inst C1 : chip-resistor(10.0e-9)

  ; Named nets joining vin → R1 → vout → C1 → gnd
  net SIG (vin, R1.p[1])
  net OUT (R1.p[2], vout, C1.p[1])
  net GND (gnd, C1.p[2])
```

## Python 4.x source

```python
from jitx.circuit import Circuit
from jitx.net import Port
from jitxlib.parts import Resistor
from jitx.units import kohm


class RCFilter(Circuit):
    # External ports
    vin = Port()
    vout = Port()
    gnd = Port()

    # Two child instances (same simplification as the Stanza side — both are
    # Resistor in this example; a real port substitutes a Capacitor).
    R1 = Resistor(resistance=1 * kohm)
    C1 = Resistor(resistance=1 * kohm)

    def __init__(self):
        # Nets built with the `+` operator (unordered electrical connection).
        self.nets = [
            self.vin  + self.R1.p1,
            self.vout + self.R1.p2 + self.C1.p1,
            self.gnd  + self.C1.p2,
        ]
```

## Notes

- `pcb-module Foo :` becomes `class Foo(Circuit):` — same shape as a `Component` but no landpattern/symbol.
- `port name` declarations become `name = Port()` class attributes. Use bundle types (e.g. `Power()`, `DiffPair()`) where Stanza uses `port x : bundle-name`.
- `inst R1 : chip-resistor(1.0e3)` becomes `R1 = Resistor(resistance=1 * kohm)` at class scope; instantiation is implicit per-circuit-instance, mediated by `jitx._structural.instantiation`.
- `net NAME (a, b, c)` becomes `a + b + c` — the `+` operator returns a `Net`. Assign nets either to a named attribute (`self.sig = ...`) or, more commonly, into a `self.nets = [...]` list inside `__init__`.
- For high-speed signals where order matters (USB, DDR, Ethernet), use `>>` instead of `+` — that yields a `TopologyNet` rather than a plain `Net`.
- Pad indexing: ocdb generators expose pads as `R1.p[1]` (1-indexed) on the Stanza side; the Python `Resistor` exposes `R1.p1` and `R1.p2` (named attributes on the `Component`'s `Port`s).
