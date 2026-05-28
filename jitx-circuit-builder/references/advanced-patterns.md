# Advanced Circuit Patterns

## Table of Contents

- [Query Refinement](#query-refinement)
- [Voltage Divider Solver](#voltage-divider-solver)
- [Net Symbols](#net-symbols)
- [Provider / Require Pattern](#provider--require-pattern) (→ jitx-pin-assignment skill)
- [Pours](#pours)
- [Copper Geometry](#copper-geometry)
- [Placement](#placement)
- [Complete Application Circuit](#complete-application-circuit)

## Query Refinement

### Design-level defaults

```python
from jitxlib.parts import ResistorQuery, CapacitorQuery, SortDir, SortKey

class MyDesign(SampleDesign):
    resistor_defaults = ResistorQuery(case=["0402"], tolerance=0.01)
    capacitor_defaults = CapacitorQuery(
        case=["0402", "0603", "0805", "1206"],
        sort=SortKey('area', SortDir.INCREASING)
    )
    circuit = MyCircuit()
    board = MyBoard()
    substrate = MySubstrate()
```

### Circuit-level context manager

```python
from jitxlib.parts import Capacitor, CapacitorQuery

with CapacitorQuery.refine(type="ceramic", case="0805"):
    self.c_bulk_0 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
    self.c_bulk_0.insert(self.buck.VIN, self.buck.GND, short_trace=True)

    self.c_bulk_1 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
    self.c_bulk_1.insert(self.buck.VIN, self.buck.GND, short_trace=True)

    self.c_hf = Capacitor(capacitance=100e-9)
    self.c_hf.insert(self.buck.VIN, self.buck.GND, short_trace=True)
```

## Voltage Divider Solver

**NEVER manually pick resistor values for voltage dividers** — use this solver instead. It finds real, purchasable E-series resistor pairs automatically.

Two critical requirements:
- **`v_out` MUST use `Toleranced.percent()`** — e.g., `Toleranced.percent(0.8, 3.0)` gives ±3%. Using `Toleranced.exact(0.8)` or bare `0.8` gives zero tolerance and the solver WILL fail with `NoPrecisionSatisfiesConstraintsError`.
- **`prec_series` is required** — e.g., `[1.00, 0.10]`. Tells the solver which resistor precision grades to search.

```python
from jitxlib.voltage_divider import VoltageDividerConstraints, voltage_divider_from_constraints
from jitxlib.parts import ResistorQuery
from jitx.toleranced import Toleranced

cons = VoltageDividerConstraints(
    v_in=Toleranced.exact(3.3),
    v_out=Toleranced.percent(0.8, 3.0),     # ±3% tolerance window
    current=0.8 / 10e3,
    prec_series=[1.00, 0.10],               # resistor precision grades
    base_query=ResistorQuery(case=["0402"]),
)
self.fb_div = voltage_divider_from_constraints(cons, name="feedback")

# Wire: hi=input, lo=ground, out=feedback tap
self.VOUT += self.fb_div.hi
self.GND += self.fb_div.lo
self.nets.append(self.fb_div.out + self.buck.FB)
```

## Net Symbols

`GroundSymbol()` / `PowerSymbol()` are **top-level only** — `scripts/grep_gates.sh` hard-fails them outside `TOP_LEVEL_PATH` (default `designs/`). The example below shows the pattern in a top-level design.

```python
# Top-level design (in src/<ns>/designs/...) only.
from jitx import Net
from jitxlib.symbols.net_symbols import GroundSymbol, PowerSymbol

self.gnd = Net(name="GND")
self.gnd.symbol = GroundSymbol()    # attribute assignment, NOT + operator

self.vcc = Net(name="VCC")
self.vcc.symbol = PowerSymbol()
```

## Provider / Require Pattern

For all provide/require patterns (`@provide`, `@provide.one_of`, `@provide.subset_of`, programmatic `Provide`, `require()`, hierarchical composition, and protocol-specific pin flexibility), see the **jitx-pin-assignment** skill. Invoke it with `skill: "jitx-skills:jitx-pin-assignment"`.

## Pours

Pours belong in the **top-level circuit**, not subcircuits. Pour every plane intended as a return path; the reference plane for an outer-layer signal can be an adjacent inner-layer pour (microstrip over an inner ground pour is fine) — what matters is continuity, not which layer the pour sits on. Split or interrupted reference planes underneath high-speed signals are the SI failure, not whether the pour is outer or inner.

```python
from jitx import Pour, current

board_shape = current.design.board.shape

# Pour(shape, layer, *, rank=0, orphans=True)
# layer is an int: 0=top, -1=bottom, 1/2/...=inner layers
self.gnd += Pour(layer=0, shape=board_shape)             # Top layer
self.gnd += Pour(layer=-1, shape=board_shape)            # Bottom layer
self.gnd += Pour(layer=2, shape=board_shape, rank=1)     # Inner layer
```

> **`orphans=True` is the API default.** Leaving it produces orphan copper regions (islands of pour not electrically connected to the named net) that the agent must consciously handle — either set `orphans=False` to drop them, or accept them with rationale (e.g. intentional thermal mass, antenna ground plane). Don't ship a design with orphans left over by default.

### `isolate=` is legacy — do not use it

The `Pour(..., isolate=...)` parameter is being removed. Pour clearance is governed by the substrate's `FabricationConstraints` (the default copper-to-edge and copper-to-net spacing) and by per-net-class `design_constraint(...)` rules with Tags. Express non-default clearance there, not on the pour:

- For a net class that needs wider keepout (HV creepage, switch-node spacing, RF clearance under an antenna), declare a Tag and apply `design_constraint(<MyTag>(), priority=N).clearance(...)` against tagged nets.
- For substrate-wide changes, edit the `FabricationConstraints` on the substrate.

New skill examples must not introduce `isolate=`. Existing user code that has it should migrate to `design_constraint(...)` when convenient — `grep_gates.sh` flags it as review-required, dispositioned `fixed (migrated)` or `deferred (legacy file)`.

### Fenced pour outlines (Pour as fence-via trigger)

To ring an arbitrary closed shape with fence vias (antipad outlines around signal-via pairs, RF cavities, BGA breakout boundaries, deskew arc cutouts), pair a tagged Pour with an optional same-shape KeepOut. The pour goes on a conductor layer the fence via reaches — typically the via's termination layer.

```python
from jitx import Pour
from jitx.feature import KeepOut
from jitx.layerindex import LayerSet

# `shape` is the outline; `FenceOutlineTag` and the fence_via rule live in the substrate.
fence_pour = Pour(shape, layer=6)
FenceOutlineTag().assign(fence_pour)
self.GND += fence_pour

# Optional — add a same-shape KeepOut ONLY when the pour copper itself is unwanted.
self.fence_outline_keepout = KeepOut(shape, layers=LayerSet(6), pour=True, via=True)
```

The Tag + `design_constraint(...).fence_via(...)` rule must already be declared on the substrate — see [jitx-substrate-modeler/SKILL.md](../../jitx-substrate-modeler/SKILL.md) "Fenced Pour Outlines".

## Copper Geometry

```python
from jitx import Copper
from jitx.shapes.composites import rectangle
from jitx.anchor import Anchor

self.nets = [
    self.A + self.e.A + Copper(
        rectangle(width=10.0, height=0.5, anchor=Anchor.W).at(0.0, 5.0),
        0  # layer
    ),
]
```

## Placement

```python
from jitx.layerindex import Side

# Fixed placement
self.led1 = LED().at(10.0, 5.0)
self.led2 = LED().at(10.0, 5.0, rotate=90)
self.led3 = LED().at(10.0, 5.0, on=Side.Bottom)

# Floating (layout engine decides) — Circuit.at() only
self.subckt = MySubCircuit().at(floating=True)
```

## Complete Application Circuit

```python
"""Buck converter application circuit."""

from jitx import Circuit, Net
from jitx.common import Power
from jitx.constraints import Tag, design_constraint
from jitxlib.parts import Capacitor, CapacitorQuery, Resistor, Inductor, ResistorQuery
from jitxlib.voltage_divider import VoltageDividerConstraints, voltage_divider_from_constraints
from jitx.toleranced import Toleranced

from .my_buck_ic import MyBuckIC


class SwTag(Tag):
    """Switch node - high dV/dt, needs clearance."""
    pass


class BuckConverterCircuit(Circuit):
    vin = Power()
    vout = Power()

    def __init__(self, output_voltage=3.3, output_current=3.0):
        self.GND = Net(name="GND")
        self.VOUT = Net(name="VOUT")
        self.VIN = Net(name="VIN")
        self.SW_NODE = Net(name="SW_NODE")

        self.buck = MyBuckIC()

        # Power connections
        self.VIN += self.vin.Vp + self.buck.VIN
        self.GND += self.buck.GND + self.vin.Vn + self.vout.Vn

        # Input caps — ALWAYS assign to self
        with CapacitorQuery.refine(type="ceramic", case="0805"):
            self.c_in1 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
            self.c_in1.insert(self.buck.VIN, self.buck.GND, short_trace=True)

            self.c_in2 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
            self.c_in2.insert(self.buck.VIN, self.buck.GND, short_trace=True)

            self.c_in_hf = Capacitor(capacitance=100e-9)
            self.c_in_hf.insert(self.buck.VIN, self.buck.GND, short_trace=True)

        # Feedback voltage divider
        vdiv_cons = VoltageDividerConstraints(
            v_in=Toleranced.exact(output_voltage),
            v_out=Toleranced.percent(0.8, 3.0),
            current=0.8 / 10e3,
            prec_series=[1.00, 0.10],
            base_query=ResistorQuery(case=["0402"]),
        )
        self.fb_div = voltage_divider_from_constraints(vdiv_cons)
        self.VOUT += self.fb_div.hi + self.vout.Vp
        self.GND += self.fb_div.lo
        self.feedback_nets = [self.fb_div.out + self.buck.FB]

        # Output inductor
        self.L = Inductor(inductance=4.7e-6, current_rating=output_current * 1.3)
        self.SW_NODE += self.buck.SW + self.L.p1
        self.VOUT += self.L.p2

        # Output caps
        with CapacitorQuery.refine(type="ceramic", case="1206"):
            self.c_out1 = Capacitor(capacitance=22e-6, rated_voltage=10.0)
            self.c_out1.insert(self.vout.Vp, self.vout.Vn, short_trace=True)

            self.c_out2 = Capacitor(capacitance=22e-6, rated_voltage=10.0)
            self.c_out2.insert(self.vout.Vp, self.vout.Vn, short_trace=True)

        # Design constraint for switch node clearance
        SwTag().assign(self.SW_NODE)
        self.sw_rule = design_constraint(SwTag(), priority=5).clearance(0.25)
```
