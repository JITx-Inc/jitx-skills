# 01 — `pcb-component` → `Component`

A real 8-pin SOIC IC (NE555) shown side-by-side. Both halves of this example **compile and run** against their respective JITX install (verified on 3.36.1 and 4.1.0); the snippets below are extracted from working files.

## Stanza 3.x source

```stanza
#use-added-syntax(jitx)
defpackage demo/components :
  import core
  import jitx
  import jitx/commands
  import ocdb/utils/box-symbol

; Minimal landpattern stub — a real port would use an ocdb-provided SOIC
; landpattern from ocdb/landpatterns. This inline stub keeps the example
; compileable while staying focused on the pcb-component construct.
pcb-pad smd-pad-1mm :
  type = SMD
  shape = Rectangle(1.0, 0.5)

pcb-landpattern soic8-pkg :
  for i in 1 through 4 do :
    pad p[i] : smd-pad-1mm at loc(-2.5, 1.27 * (2.5 - to-double(i)))
  for i in 5 through 8 do :
    pad p[i] : smd-pad-1mm at loc( 2.5, 1.27 * (to-double(i) - 6.5))

; --- 8-pin SOIC IC ---
pcb-component NE555 :
  pin-properties :
    [pin:Ref | pads:Int ...]
    [GND     | 1]
    [TRIG    | 2]
    [OUT     | 3]
    [RESET   | 4]
    [CONT    | 5]
    [THRES   | 6]
    [DISCH   | 7]
    [VCC     | 8]
  make-box-symbol()
  assign-landpattern(soic8-pkg)
  name = "NE555"
  reference-prefix = "U"
```

## Python 4.x source

```python
import jitx
from jitx.net import Port
from jitxlib.landpatterns.generators.soic import SOIC, SOIC_DEFAULT_LEAD_PROFILE
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row


class NE555(jitx.Component):
    mpn = "NE555"
    manufacturer = "Texas Instruments"
    reference_designator_prefix = "U"

    GND = Port()
    TRIG = Port()
    OUT = Port()
    RESET = Port()
    CONT = Port()
    THRES = Port()
    DISCH = Port()
    VCC = Port()

    lp = (
        SOIC(num_leads=8)
        .lead_profile(SOIC_DEFAULT_LEAD_PROFILE)
        .narrow(jitx.Toleranced.min_max(4.81, 5.0))
    )

    symb = BoxSymbol(
        rows=Row(
            left=PinGroup(GND, TRIG, OUT, RESET),
            right=PinGroup(VCC, DISCH, THRES, CONT),
        ),
    )
```

## Notes

- `pcb-component Foo :` becomes `class Foo(jitx.Component):` — a Python class subclass, not a top-level form.
- `pin-properties` table is replaced by **declaring `Port()` attributes** on the class. Default port-to-pad mapping is by declaration order; for non-trivial mappings use `PadMapping({port: landpattern.p[n]})` (see `py-jitx/src/jitx/component.py`).
- `make-box-symbol()` → `BoxSymbol(rows=Row(left=PinGroup(...), right=PinGroup(...)))` (from `jitxlib.symbols.box`). Explicit `Row`/`PinGroup` give you control over schematic-symbol pin layout that `make-box-symbol()` infers from the pin-properties' `side:Dir` column.
- `assign-landpattern(pkg)` → assign the `Landpattern` (or a generator like `SOIC(...).lead_profile(...).narrow(...)`) to a class attribute (`lp` is conventional). Generators are chainable builders.
- `name = "NE555"` / `reference-prefix = "U"` → `mpn = "NE555"` / `reference_designator_prefix = "U"`. Python also exposes `manufacturer` and `datasheet` as first-class metadata.
- The Stanza side declares its landpattern inline (`pcb-pad smd-pad-1mm` + `pcb-landpattern soic8-pkg`) so the file compiles standalone; the Python side delegates landpattern construction to the `SOIC` generator from `jitxlib.landpatterns.generators.soic`.
