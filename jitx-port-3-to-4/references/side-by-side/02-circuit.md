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

## Parametric modules — `pcb-module foo (flag:True|False) : ...`

Stanza 3.x lets a single `pcb-module` take a parameter (often a `True|False` flag or an enumerated type) and branch on it internally:

```stanza
public pcb-module amp-module (PBTL?:True|False) :
  if PBTL? :
    port out : diff-pair
    ; PBTL wiring
  else :
    port out : diff-pair[2]
    ; BTL stereo wiring
```

Callers instantiate two distinct variants: `inst stereo : amp-module(false)`, `inst sub : amp-module(true)`. Python `Circuit` class bodies cannot branch port declarations on `__init__` kwargs, so there is no single mechanical mapping. Pick by what the parameter controls:

### (a) Parameter affects wiring only — single `Circuit` with a variant kwarg

When the ports stay the same and only the internal wiring changes (e.g. a configuration register write, a different gain resistor), use one class and branch inside `__init__`:

```python
class AmpModule(Circuit):
    out = DiffPair()    # same port shape for every variant

    def __init__(self, *, pbtl: bool = False):
        # ... build child instances ...
        if pbtl:
            self.nets = [...]     # PBTL wiring
        else:
            self.nets = [...]     # BTL wiring
```

### (b) Parameter changes the port interface — two separate `Circuit` subclasses

When the parameter changes the *number* or *type* of external ports, write two subclasses. Python class-level `Port` declarations are evaluated once at class creation and cannot vary by instance kwarg:

```python
class AmpModuleStereo(Circuit):
    out = [DiffPair(), DiffPair()]
    # ... stereo wiring

class AmpModuleSub(Circuit):
    out = DiffPair()
    # ... PBTL wiring
```

This is the safest port for any Stanza module whose `if flag : port out : diff-pair else : port out : diff-pair[2]` shape changes the external interface. Most TAS5825M-class amplifier ports use this pattern.

### (c) Variants share most wiring — `@classmethod` factory

When two variants share most of their child instances and nets and you don't want to duplicate them, expose `@classmethod` constructors on a single base class:

```python
class AmpModule(Circuit):
    @classmethod
    def stereo(cls) -> "AmpModule":
        inst = cls()
        inst._configure(pbtl=False)
        return inst

    @classmethod
    def pbtl(cls) -> "AmpModule":
        inst = cls()
        inst._configure(pbtl=True)
        return inst
```

Combine with pattern (a) for the internal `_configure` call. Use this when the port interface is identical but the variant-selection sites read better as `AmpModule.stereo()` / `AmpModule.pbtl()` than `AmpModule(pbtl=True)`.

> Rule of thumb: if the Stanza `if PBTL? :` block contains a `port` declaration, you need pattern (b). Otherwise (a) is almost always simpler than (c).
