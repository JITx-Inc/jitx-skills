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
from jitx.interval import AtLeast, AtMost
from jitxlib.parts import (
    CapacitorQuery,
    InductorQuery,
    ResistorQuery,
    SortDir,
    SortKey,
)

class MyDesign(SampleDesign):
    resistor_query = ResistorQuery(
        mounting="smd",
        case=("0402", "0603", "0805"),
        tolerance_min=AtLeast(-0.01),
        tolerance_max=AtMost(0.01),
    )
    capacitor_query = CapacitorQuery(
        mounting="smd",
        case=("0402", "0603", "0805", "1206"),
        sort=SortKey('area', SortDir.INCREASING)
    )
    # Power inductors do not use the chip-passive case ceiling. Each instance
    # carries any current and saturation bounds required by its datasheet.
    inductor_query = InductorQuery(mounting="smd")
    circuit = MyCircuit()
    board = MyBoard()
    substrate = MySubstrate()
```

These design-context attributes are singular `*_query` names. Attributes named
`resistor_defaults`, `capacitor_defaults`, or `inductor_defaults` are ignored and do
not constrain the selected parts. The verification process in the main skill refuses
to proceed until the resolved package, ratings, MPN, and price are inspected.

### Circuit-level context manager

```python
from jitx.interval import AtLeast
from jitxlib.parts import Capacitor, CapacitorQuery

with CapacitorQuery.refine(type="ceramic", case="0805"):
    self.c_bulk_0 = Capacitor(capacitance=10e-6, rated_voltage=AtLeast(50.0))
    self.c_bulk_0.insert(self.buck.VIN, self.buck.GND, short_trace=True)

    self.c_bulk_1 = Capacitor(capacitance=10e-6, rated_voltage=AtLeast(50.0))
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

`GroundSymbol()` / `PowerSymbol()` are **top-level only** — `scripts/grep_gates.py` hard-fails them outside `TOP_LEVEL_PATH` (default `designs/`). The example below shows the pattern in a top-level design.

```python
# Top-level design (in <ns>/designs/...) only.
from jitx import Net
from jitxlib.symbols.net_symbols import GroundSymbol, PowerSymbol

self.gnd = Net(name="GND")
self.gnd.symbol = GroundSymbol()    # attribute assignment, NOT + operator

self.vcc = Net(name="VCC")
self.vcc.symbol = PowerSymbol()
```

## Provider / Require Pattern

For all provide/require patterns (`@provide`, `@provide.one_of`, `@provide.subset_of`, programmatic `Provide`, `require()`, hierarchical composition, and protocol-specific pin flexibility), see the **jitx-pin-assignment** skill. Invoke it with the `jitx-pin-assignment` skill.

## Pours

The simple circuit-level pattern is:

```python
from jitx import Pour, current

fab = current.design.substrate.constraints
ground_shape = current.design.board.shape.to_shapely().buffer(
    -fab.min_copper_edge_space
)
if ground_shape.g.is_empty or ground_shape.g.geom_type not in (
    "Polygon",
    "MultiPolygon",
):
    raise ValueError("board edge pullback removed or invalidated the pour outline")
self.ground_pour = Pour(shape=ground_shape, layer=-1)
self.gnd += self.ground_pour
```

Every other pour question, including layer reachability, keepouts, rank,
stitch-via output, captured shapes, and empty results, belongs to
[Pour realization semantics](../../jitx-physical-layout/SKILL.md#pour-realization-semantics).
Layer selection, clearances, thermal relief, sliver removal, direct connect, and
stitching expressed as rules belong to `jitx-layout-constraints`. Stackups, via
definitions, and fenced pour outlines belong to `jitx-substrate-modeler`.

## Copper Geometry

Custom `Copper`, netless overlapping copper, and shapely-built shapes belong to
`jitx-physical-layout`, which carries the `Pour` vs `Copper` vs
`OverlappableCopper` decision table and the realized-geometry checks.

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

Prefer `.at()` for **direct descendants** — it mutates the instance's own `transform`, so the
placement is readable on the instance (visible to introspection before the design is built). That
transform is in its **immediate container's** frame, not the board's — to get a position for
anything nested (a pad inside a landpattern, a component inside a subcircuit) compose down from the
frame you want with `visit` (see `jitx-physical-layout/references/geometry-verification.md`
§ "Coordinate frames").
`Circuit.place(child, pos)` instead records a deferred placement request on the parent — reserve it
for placing relative to **another** instance (`relative_to=`); see **jitx-physical-layout**.

Placed `Via` (and `Copper`) instances can join a net directly — `self.GND +=
via_cls().at(x, y)` — which is the preferred form for ground/power stitching and
thermal vias. **As of JITX 4.3.0-rc.3+ a bare `Via` may also appear directly in a
`>>` topology chain** (e.g. `self += driver.out >> via_cls().at(x, y) >> rx.inp`),
so a signal via can enter a constrained topology without a `PortAttachment`.
`PortAttachment` is scoped to **signal topologies** (control points, signal escape
vias) and is expected to be deprecated. For both — and for code-based routes /
control points — see the **jitx-physical-layout** subskill.

## Complete Application Circuit

```python
"""Buck converter application circuit."""

from jitx import Circuit, Net
from jitx.common import Power
from jitx.constraints import Tag, design_constraint
from jitx.interval import AtLeast
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
            self.c_in1 = Capacitor(capacitance=10e-6, rated_voltage=AtLeast(50.0))
            self.c_in1.insert(self.buck.VIN, self.buck.GND, short_trace=True)

            self.c_in2 = Capacitor(capacitance=10e-6, rated_voltage=AtLeast(50.0))
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
        self.L = Inductor(
            inductance=4.7e-6,
            current_rating=AtLeast(output_current * 1.3),
        )
        self.SW_NODE += self.buck.SW + self.L.p1
        self.VOUT += self.L.p2

        # Output caps
        with CapacitorQuery.refine(type="ceramic", case="1206"):
            self.c_out1 = Capacitor(capacitance=22e-6, rated_voltage=AtLeast(10.0))
            self.c_out1.insert(self.vout.Vp, self.vout.Vn, short_trace=True)

            self.c_out2 = Capacitor(capacitance=22e-6, rated_voltage=AtLeast(10.0))
            self.c_out2.insert(self.vout.Vp, self.vout.Vn, short_trace=True)

        # Design constraint for switch node clearance
        SwTag().assign(self.SW_NODE)
        self.sw_rule = design_constraint(SwTag(), priority=5).clearance(0.25)
```
