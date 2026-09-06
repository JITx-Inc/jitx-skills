# Component Code Patterns

The agent opens this file when writing the component class, symbol, package-generator call, multi-unit partition, or explicit pad mapping. It carries the generic component template and API-specific patterns that apply after the source and package are known.

## Anti-string-hacking — read before building arrays of pins / lanes / bundles

For any component with N parallel siblings (BGAs, multi-channel ICs, banked diff-pairs), reach for `self.pins: list[Port]` or `self.lanes: list[DiffPair]` — **never** `self.TX_b0, self.TX_b1, ...` plus `getattr(self, f"TX_b{i}")` to iterate. See `jitx/references/architectural-patterns.md` § "Sibling attributes → array attributes" before writing the constructor. Also: do not assign `refdes=`, net names, or other JITX-assigned values yourself (§ "Don't assign what JITX assigns").

For a same-model self-critique pass on the component after writing (catches what these rules don't), invoke `jitx-code-review`. Optional for single-task use.

## A `Port` has exactly one home

**Never store a collection of the component's own ports as a second attribute.** A `Port` belongs to
exactly one place in the object tree, and stashing the same ports under a second name — `self.bank_groups = [...]`, `self.rails = {...}` — fails translation with:

```
Child object encountered multiple times
```

The grouping itself is usually a legitimate thing to want: a bank roster, a lane grouping, a list of
supply rails to tie. Expose it as a **method returning fresh records**, not as stored state:

```python
def bank_pins(self) -> dict[int, list[Port]]:      # computed per call
    return {700: [self.IO_0_700, self.IO_1_700, ...], ...}
```

The distinction is ownership, not syntax. `self.symbols = [BoxSymbol(...), ...]` is fine — the
component owns those symbols and nothing else does. `self.bank_groups = [[self.IO_0_700, ...]]` is
not — those ports already have a home.

Design the groupings as methods from the start. Retrofitting this after the fact means unpicking
every consumer, and the error message names the symptom rather than the attribute that caused it.

### Step 3: Generate Component Code

Use this template structure:

```python
"""
{Manufacturer} {MPN} - {Description}

Component definition for the {full description}.
"""

import jitx
from jitx import PadMapping
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column
# Import appropriate landpattern generator:
# from jitxlib.landpatterns.generators.soic import SOIC, SOIC_DEFAULT_LEAD_PROFILE
# from jitxlib.landpatterns.generators.sot import SOT23_3, SOT23_5, SOT23_6, SOTLead, SOTLeadProfile
# from jitxlib.landpatterns.generators.qfn import QFN, QFNLead
# from jitxlib.landpatterns.generators.son import SON, SONLead
# from jitxlib.landpatterns.generators.bga import BGA
from jitxlib.landpatterns.leads import LeadProfile
from jitxlib.landpatterns.package import RectanglePackage


class {ComponentClassName}(jitx.Component):
    """Brief description of the component."""

    mpn = "{MPN}"
    manufacturer = "{Manufacturer}"
    reference_designator_prefix = "U"  # or "Q" for transistors, etc.
    datasheet = "{datasheet_url}"

    # Define ports for each pin
    # Single pins:
    VCC = Port()
    GND = Port()

    # Pin arrays (for many similar pins):
    GPIO = [Port() for _ in range(N)]

    # Landpattern definition
    landpattern = (
        {Generator}(num_leads=N)
        .lead_profile(...)
        .package_body(...)
        # Optional: .thermal_pad(...)
    )

    # Symbol definition — use BARE attribute names (GND, VCC), NEVER self.GND
    # (self does not exist at class scope)
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(...),
            right=PinGroup(...),
        ),
        columns=Column(
            up=PinGroup(...),    # Power pins typically go up
            down=PinGroup(...),  # Ground pins typically go down
        ),
    )

    # For non-standard pin ordering, add explicit mapping in __init__:
    def __init__(self):
        lp = self.landpattern
        self.mappings = [PadMapping({
            self.PIN1: [lp.p[1]],
            self.PIN2: [lp.p[2]],
            # ...
        })]


Device: type[{ComponentClassName}] = {ComponentClassName}
```

## Package-Specific Examples

For complete examples of each package type (SOIC, SOT, SON, QFN, QFP, BGA), including thermal pads,
port arrays, inactive positions, and non-uniform BGA grids, see
[package-examples.md](package-examples.md).

Read its **BGA-Specific Notes** before any BGA, not just an unusual one — in particular what
`ball_diameter` actually sets, and the public `get_pad` adapter for reaching pads from test and
verification code. Both are places where the obvious reading is the wrong one.

## Dimension Mapping Reference

| Datasheet Symbol | Description | JITX Parameter |
|-----------------|-------------|----------------|
| D | Package length | `RectanglePackage.length` |
| E | Package width | `RectanglePackage.width` |
| A | Package height | `RectanglePackage.height` |
| E1 / D1 | Lead span | `LeadProfile.span` |
| e | Lead pitch | `LeadProfile.pitch` |
| b | Lead width | `SMDLead.width` / `QFNLead.width` |
| L | Lead length | `SMDLead.length` / `QFNLead.length` |
| D2 / E2 | Thermal pad size | `.thermal_pad(rectangle(E2, D2))` — **E2 is width (X), D2 is height (Y)**. D=along pins, E=across. Do NOT write rectangle(D2, E2). |

**Two-terminal chips use L / W / T instead, and the two symbol sets do not correspond row for row** — do not translate one into the other by position.

| Chip datasheet symbol | Description | JITX Parameter |
|-----------------|-------------|----------------|
| L | Body length, termination end face to end face | `LeadProfile.span`, `RectanglePackage.length` |
| W | Body width (= termination width) | `SMDLead.width`, `RectanglePackage.width` |
| H / T | Body height / thickness | `RectanglePackage.height` |
| *(seating-plane band; symbol varies by vendor)* | Solderable termination length | `SMDLead.length` — **not** the end-face wrap-up band. See [parameterized-families.md](parameterized-families.md#the-two-termination-bands--which-one-is-the-solderable-land). |

## Common Patterns

### Class-Level vs Instance-Level

Ports, landpattern, and symbol defined at **class level** (no `self`). The exception to this is if a parameter is needed at the class initialization time then the definition can be done in the initialization function:

```python
class MyIC(jitx.Component):
    GND = Port()          # class-level: no self
    VCC = Port()

    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(GND),    # bare name, NEVER self.GND
            right=PinGroup(VCC),   # bare name, NEVER self.VCC
        ),
    )
```

Only use `self` inside `__init__` (for PadMapping, multi-unit symbols).

### Toleranced Values

```python
Toleranced.min_max(3.8, 4.0)           # Min-max range (most common)
Toleranced(5.0, 0.1)                    # Nominal ± tolerance
Toleranced.min_typ_max(0.13, 0.18, 0.23)  # Asymmetric
Toleranced.exact(7.0)                   # BSC = Basic
```

### Thermal Pad with Paste Subdivision

```python
from jitx.shapes.composites import rectangle
from jitxlib.landpatterns.pads import SMDPadConfig, WindowSubdivide

.thermal_pad(
    shape=rectangle(3.0, 3.0),
    config=SMDPadConfig(paste=WindowSubdivide(padding=0.25)),
)
```

### Reference Designator Prefixes

- `U` - Integrated circuits
- `Q` - Transistors (typically BJTs)
- `D` - Diodes (LEDs)
- `R` - Resistors
- `C` - Capacitors
- `L` - Inductors
- `J` - Connectors
- `Y` or `X`- Crystals/oscillators
- `FB` - Ferrite beads
- `T` - Transformers

## Multi-Unit Symbols

`BoxSymbol` accepts `BoxConfig` field overrides as keyword arguments — e.g.
`BoxSymbol(rows=..., orientation=90)` rotates the box symbol (an int multiple
of 90 degrees; other values raise `ValueError`; jitxlib 4.2+).

**Prefer partitioning large symbols into several smaller boxes.** A single box
with dozens of pins is unreadable; as a rule of thumb, **once a part exceeds
~40 pins, split it into multiple symbols.** A component may carry more than one
`BoxSymbol` — each becomes a separate visual box, and the boxes can be placed on
different schematic pages (see "Splitting across schematic pages" below).

**At four figures' worth of pins the partition becomes the schematic.** Past a
few hundred pins there is no "the symbol" left to split — the partition *is* the
part's readable form, and it needs stating as a property rather than a habit:

- **Every port in exactly one partition**, and the partition count reconciles
  against the total pin count. Same property the pin inventory owes (see
  `pin-file-generation.md`), asserted the same way. A port in two boxes and a
  port in none both draw without complaint.
- **One box per structural group the source itself defines.** Take the grouping
  from the datasheet's own organizing axis and do not invent one — on an FPGA
  that is typically the IO bank, transceiver quad or power domain; on other
  parts it is whatever the pin table is organized by. If you cannot name the
  document that defines your grouping, it is invented.
- **A per-box ceiling for the groups that have no natural size** — the large
  rails, where one box per net would mean a single box of several hundred pins.
  Chunk them at a stated ceiling and say what it is. The right number is
  whatever keeps a box readable at your schematic's page size; state it, enforce
  it in a test, and revisit it by looking at the rendered sheet rather than
  trusting the number.
- Pins belonging to no group get their own box rather than being distributed by
  convenience.

Build the boxes from a **method returning fresh partitions**, never a stored
attribute holding the ports a second time; see "A `Port` has exactly one home".

**By functional group** (the usual case — split where the datasheet does: each
op-amp unit, the power unit, each peripheral block):

```python
def __init__(self):
    self.symbol_a = BoxSymbol(rows=Row(
        left=PinGroup(self.INp[0], self.INn[0]),
        right=PinGroup(self.OUT[0]),
    ))
    self.symbol_b = BoxSymbol(rows=Row(
        left=PinGroup(self.INp[1], self.INn[1]),
        right=PinGroup(self.OUT[1]),
    ))
    # Power unit: use horizontal layout (left=supplies, right=grounds)
    self.symbol_power = BoxSymbol(
        rows=Row(
            left=PinGroup(self.VCC, self.VBAT),
            right=PinGroup(self.VSS, self.GND),
        ),
    )
```

**By regular slices** — only when the part has **no** natural functional
grouping (generic connectors, board-to-board headers, pin arrays). For FPGAs,
MCUs, and memory, partition by the structure the datasheet already gives you —
IO bank, power domain, byte lane, peripheral block — *before* falling back to
arbitrary slices. When slicing is the right call, store the boxes as a **list**
and slice a `p = [Port() for _ in range(N)]` pin array into fixed-size groups:

```python
# 100-pin part → ten 10-pin boxes (5 left / 5 right each):
self.symbols = [
    BoxSymbol(
        rows=Row(
            left=PinGroup(*self.p[i * 10:i * 10 + 5]),
            right=PinGroup(*self.p[i * 10 + 5:i * 10 + 10]),
        ),
    )
    for i in range(10)
]
```

`self.symbols` (a list of `BoxSymbol`) is a recognized structural collection —
no string-keyed dict, no `getattr` (see `jitx/references/architectural-patterns.md`).

### Splitting across schematic pages

Each symbol can be assigned to its own schematic page by wrapping it in a
`SchematicGroup`. In the **enclosing circuit/design**, pull the component's
symbols out with `extract(..., Symbol)` and give each its own group:

```python
from jitx import extract, Symbol
from jitx.circuit import SchematicGroup

# In the circuit that instantiates the part:
self.banks = [SchematicGroup(symbol) for symbol in extract(self.u1, Symbol)]
```

`extract(self.u1, Symbol)` yields every `Symbol` in `self.u1` (the partitioned
boxes); each `SchematicGroup` becomes a separately placeable schematic group, so
a 100-pin part's ten banks can land on ten pages. Rails connect across those
pages through `PowerSymbol` / `GroundSymbol` net symbols, not drawn wires — see
`jitx-circuit-builder` "Net Definitions". (`SchematicGroup` is in `jitx.circuit`;
`extract` and `Symbol` are top-level `jitx` exports.)

## Pin Naming Best Practices

**Every physical pin/ball MUST have a Port().** Never use "representative samples" — a 142-ball
BGA needs exactly 142 Port() declarations. Enumerate every pin from the datasheet pin table or
ball map row by row. NC (no-connect) pins with physical pads also need ports. 

**One Port per physical pin** — if a ball has a primary name and alternate functions
(SPI_CLK, UART_TX, etc.), create ONE port using the datasheet's primary pin name. Do not create
separate ports for each alternate function of the same physical ball.
Also for Ports that have incrementing numbers in the name, use an indexed Port name instead (GND1, GND2, GND3 -> GND[1 through 3])

**Use real functional names from the datasheet**, not generic placeholders:

```python
# GOOD - from datasheet
OQSPIF_D0 = Port()   # Octal QSPI Flash data bit 0
eMMC_CMD = Port()    # eMMC command line
V18F = Port()        # 1.8V flash supply

# BAD - generic
P0 = Port()          # What does P0 do?
VDD1 = Port()        # Which power domain?
```

## Landpattern Constructor Signatures

Do NOT invent constructor parameters — use only these documented signatures:

```python
# SOT — SOTLeadProfile takes ONLY span, nothing else
SOTLeadProfile(span=Toleranced.min_max(2.3, 2.5))

# LeadProfile — used for SOIC, SON, QFN
LeadProfile(
    span=Toleranced.min_max(5.8, 6.2),   # terminal-to-terminal
    pitch=1.27,                            # center-to-center lead spacing
    type=SONLead(length=..., width=...),   # or SMDLead, QFNLead
)

# SON — use .lead_profile() method chain, NOT .lead()
SON(num_leads=8).lead_profile(LeadProfile(span=..., pitch=..., type=SONLead(...)))

# QFP — uses LeadProfile with QFPLead (BigGullWingLeads)
QFP(num_leads=48).lead_profile(LeadProfile(span=..., pitch=0.5, type=QFPLead(...)))
# For asymmetric pin counts: QFP(num_rows=(left, bottom, right, top))
# For asymmetric lead spans: .lead_profile(x_profile, y_profile)

# BGA — constructor takes these 4 args
BGA(num_rows=12, num_cols=12, pitch=0.45, ball_diameter=0.25)
# then chain: .grid_planner(...).pad_config(SMDPadConfig()).package_body(...)
```

### `.narrow()` vs `.package_body()` for SOIC

SOIC provides a convenience method `.narrow(length)` that sets the package body to the standard SOIC narrow width (3.9mm) with a given length:

```python
# .narrow() — shorthand for narrow-body SOIC (3.9mm width)
SOIC(num_leads=8).lead_profile(SOIC_DEFAULT_LEAD_PROFILE).narrow(Toleranced.min_max(4.81, 5.0))

# Equivalent explicit form using .package_body()
SOIC(num_leads=8).lead_profile(SOIC_DEFAULT_LEAD_PROFILE).package_body(
    RectanglePackage(width=Toleranced.exact(3.9), length=Toleranced.min_max(4.81, 5.0))
)
```

Use `.narrow()` for standard narrow-body SOICs. Use `.package_body()` for wide-body SOICs or when specifying all three dimensions (width, length, height).

## PadMapping Requirements

- **Automatic mapping (no PadMapping needed):** Ports mapped to pads in declaration order.
- **Explicit PadMapping required when:**
  - Thermal pad exists (map to `lp.thermal_pads[0]`)
  - Ports declared out of pin order
  - Multiple ports map to same pad
  - Pin 1 is not the first declared port

A `PadMapping` resolves port → pad, and nothing more. It carries **no coordinate** — and a component
declaring more than one landpattern is combined into a single *composite* landpattern, so each
`Pad.transform` is local to its own sub-landpattern rather than to the component. Pad coordinates
must be composed from a `visit` (`trace.transform * pad.transform`), never read off `Pad.transform`
alone; see `jitx-physical-layout/references/geometry-verification.md` § "Coordinate frames".

**Both of these need narrowing before a type checker will accept them**, which matters because a
"pyright clean" gate and an un-narrowed lookup contradict each other:

- `PadMapping.__getitem__` returns `Pad | Sequence[Pad]` — a port may map to several pads — so
  `mapping[port][0]` is a `reportIndexIssue`, and `len(mapping[port])` fails on the `Pad` arm.
- `Pad.transform` is `Placement | None`, so `pad.transform.translation` is a
  `reportOptionalMemberAccess`.

Each is a small helper once you know — write both; they narrow different unions:

```python
from jitx.landpattern import Pad, PadMapping
from jitx.placement import Placement


def one_pad(mapping: PadMapping, port: Port) -> Pad:
    """The single pad for a port. Raises if the port maps to several."""
    pads = mapping[port]
    if isinstance(pads, Pad):
        return pads
    if len(pads) != 1:
        raise AssertionError(f"expected one pad for {port}, got {len(pads)}")
    return pads[0]


def placement_of(pad: Pad) -> Placement:
    """A pad's own placement. Raises rather than returning a silent default."""
    if pad.transform is None:
        raise AssertionError(f"pad {pad} has no placement")
    return pad.transform
```

Write the helpers rather than suppressing the errors. A `pyright: ignore` on the first hides the
composite-landpattern case the union exists to flag; one on the second turns a missing placement into
an `AttributeError` at some later line instead of a named failure here. And note `placement_of` gives
you the pad's *local* transform — for a coordinate in the component's frame, compose it from a
`visit`, per the paragraph above.
