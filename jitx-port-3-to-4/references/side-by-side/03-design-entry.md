# 03 — Design entry: `main.stanza` → `Design` class

The form invoked from `nightly_design_tests/config/designs.yaml` (Stanza) versus its `Design` subclass form discovered by `python -m jitx find` (driven from `jitx-test/.github/workflows/integration-testing.yml`). Both halves **compile and produce export artifacts** against their respective JITX install (verified on 3.36.1 and 4.1.0 — the Stanza side writes a real KiCad project under `designs/jitx-design/kicad/`; the Python side returns `status: ok`).

## Stanza 3.x source — `main.stanza`

```stanza
#use-added-syntax(jitx)
defpackage demo/main :
  import core
  import jitx
  import jitx/commands
  import ocdb/utils/defaults
  import ocdb/utils/generic-components

; Inline circuit (in a real port the rc-filter would live in its own package
; — see 02-circuit.md for that form).
pcb-module rc-filter :
  port vin
  port vout
  port gnd
  inst R1 : chip-resistor(1.0e3)
  inst C1 : chip-resistor(10.0e-9)
  net (vin,  R1.p[1])
  net (vout, R1.p[2], C1.p[1])
  net (gnd,  C1.p[2])

; Top-level design module that owns the rc-filter instance.
public pcb-module jitx-design :
  inst flt : rc-filter

set-current-design("jitx-design")
make-default-board(jitx-design, 2, RoundedRectangle(30.0, 18.5, 0.25))
set-export-backend(`kicad)
export-cad()
view-board()
view-schematic()
```

Invoked from `nightly_design_tests/config/designs.yaml`:

```yaml
- id: demo
  repo: "git@github.com:JITx-Inc/demo.git"
  branch: main
  targets:
    - project_dir: "."
      stanza_file: "main.stanza"
      design_name: "jitx-design"
```

## Python 4.x source — `main.py`

```python
from jitx.circuit import Circuit
from jitx.net import Port
from jitx.sample import SampleDesign
from jitxlib.parts import Resistor
from jitx.units import kohm


class RCFilter(Circuit):
    R1 = Resistor(resistance=1 * kohm)
    C1 = Resistor(resistance=1 * kohm)
    def __init__(self):
        self.nets = [self.R1.p2 + self.C1.p1]


class jitx_design(SampleDesign):
    circuit = RCFilter()
```

Discovery / build:

```bash
python -m jitx find
# designs:
#   example.main.jitx_design

python -m jitx build example.main.jitx_design
```

Matrix row in `jitx-test/.github/workflows/integration-testing.yml`:

```yaml
- example-repo-name: demo
  use-prerelease: true
  example-repo-url: "https://github.com/JITx-Inc/demo.git"
  jitx-env-var: JITX_ENV_PROD
  jitx-user-email-var: JITX_USER_EMAIL_PROD
  jitx-user-pass-secret: JITX_USER_PASS_PROD
```

## Notes

- The Stanza pattern (`set-current-design` + `make-default-board` + `export-cad` + `view-*` at top level) collapses into a single `Design` subclass. `SampleDesign` (from `jitx.sample`) supplies a default `Board`, `Substrate`, and fab constraints — for a real port substitute a real `Substrate` / `Stackup` / `Board` (see `jitx-substrate-modeler`).
- `set-board(default-board(stack, shape))` and `make-default-board(module, layers, shape)` (Stanza) both split into Python class attributes: `Board.shape`, `Substrate.stackup`, `Design.circuit`. There is no `set-main-module` analog — the `Circuit` instance assigned to `Design.circuit` *is* the entrypoint.
- The YAML-side identifier flips: `design_name: "jitx-design"` (the Stanza module name) becomes a fully-qualified Python class path like `example.main.jitx_design`, discovered by `python -m jitx find` rather than declared in YAML.
- The driver moves from `nightly_design_tests/config/designs.yaml` to a GitHub Actions matrix in `jitx-test/.github/workflows/integration-testing.yml`. Each row points at a repo URL; the design is auto-discovered by `python -m jitx`. There is no per-target `stanza_file`/`design_name` pair to set.
- `view-board()` / `view-schematic()` calls are dropped entirely on the Python side — view dispatch happens automatically when an interactive session is connected (the `jitx interactive` server).
- `export-cad()` is the explicit CAD-export trigger on the Stanza side; the Python build pipeline writes the same artifacts as part of `python -m jitx build` without a separate call.

## Board outline — `RoundedRectangle(...)` → `rectangle(..., radius=...)`

Stanza:

```stanza
make-default-board(jitx-design, 2, RoundedRectangle(80.9, 50.0, 3.0))
```

Python:

```python
from jitx.sample import SampleDesign
from jitx.shapes.composites import rectangle

class jitx_design(SampleDesign):
    circuit = MyCircuit()

    def __init__(self):
        super().__init__()
        self.board.shape = rectangle(80.9, 50.0, radius=3.0)
```

Key facts:

- **There is no `RoundedRectangle` class.** Use the function `rectangle(width, height, *, radius=None, chamfer=None, anchor=Anchor.C)` from `jitx.shapes.composites`. `radius=` rounds all four corners; pass a 4-tuple `(r1, r2, r3, r4)` to round per-corner.
- `Design.board: Board` and `Board.shape: Shape` are plain attributes — assign the shape, no setter.
- `SampleDesign` ships a default `SampleBoard(shape=rectangle(50, 50, radius=5))`. For any board with a different outline, override `self.board.shape` in `__init__` (as above), or subclass `Board` and assign `board = MyBoard()` on the design.
- The board shape is independent of `substrate` / `stackup` — those govern the layer composition, not the outline.
