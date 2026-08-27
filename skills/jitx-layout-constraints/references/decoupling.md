# Decoupling Banks

## Engineering basis

Eric Bogatin's guidance is to place each capacitor as close to the IC power pin
as practical and minimize the loop inductance between the IC power and ground
pins and the capacitor. That loop matters more than adding capacitance values.
Use the largest capacitance in the smallest package, rated at least twice the
rail, typically a 22 uF MLCC, with short, wide traces or a local power puddle.
Do not add a 10 uF, 1 uF, and 0.1 uF stack per power pin. Keep other power
routing explicit rather than using board-wide copper fill. See Eric Bogatin,
["Seven Habits of Successful 2-Layer Board Designers"](https://www.signalintegrityjournal.com/blogs/12-fundamentals/post/1207-seven-habits-of-successful-2-layer-board-designers), Signal Integrity Journal, 2019-04-23.
When the datasheet gives a value, package, placement side, pin grouping, or
layout figure, the datasheet wins.

## What the solver controls

Source citations (`jitx/constraints.py:910` and the like) point into the
installed py-jitx package, `4.4.0rc5.dev2` build; line numbers move between
builds, so confirm on another install before relying on one.

`scripts/decoupling_solver.py` is pure Python. Copy it into the design project
and import these frozen dataclasses. An infeasible bank raises `ValueError`
naming the hint group and the constraint that could not be met; that is a
stop, not a warning. Change the keepouts, spacing, or hints and solve again
rather than placing a capacitor by hand to get past it:

```python
from decoupling_solver import (
    BankSpec,
    CapacitorGeometry,
    HintSpec,
    Solution,
    solve,
)
```

One `HintSpec` describes the IC power-pad centers and IC return-pad centers
served by one capacitor. The solver places one capacitor per hint. At zero
degrees its power pad is on local negative X and its return pad is on local
positive X. It emits the capacitor center, one of the four orthogonal
rotations (skill default: four rotations), a via center for each pad, and the
loop area achieved for that hint.

The deterministic search walks a center-out grid around each hint centroid,
row-major inside each square ring. It tests four fixed rotations (skill default: four rotations), rejects
keepout, all-IC-pad clearance, capacitor-spacing, degenerate-loop, and
power-return path-clearance violations, then minimizes total loop area. Ties
use hint, position, and rotation order. Infeasibility names the hint and rule.

The loop polygon follows the capacitor power-pad center, IC power-pad center,
IC return-pad center, and capacitor return-via center in that order. The two
capacitor-side corners are of different kinds (a pad and a via), so the area
is not symmetric under a 180 degree flip of a symmetric part and the search
prefers orientations that keep the return via near the IC; the number is a
ranking proxy for loop inductance, not a symmetric geometric invariant.

For a hint containing more than one IC power pad or return pad, the reported
area is the arithmetic mean across every power-pad and return-pad pair. This is
a geometric proxy for the loop-inductance criterion. It is not an inductance
calculation and it does not replace a package or board simulation.

The capacitor envelope contains its body, pads, and via-pad circles. Keepouts
may be arbitrary simple polygons. IC-pad clearance uses their centers. For
large, asymmetric, or shaped pads, expand the keepouts to include their copper
outlines before solving.

Read every dimension before constructing `BankSpec`:

- capacitor body and pad bounds from the selected capacitor landpattern with
  `jitx.query`;
- capacitor pad pitch from the distance between the queried pad centers;
- IC power and return pad centers from the IC's `PadMapping` plus composed
  transforms;
- via pad diameter from the substrate's chosen via class;
- clearance floor from
  `current.design.substrate.constraints.min_copper_copper_space`;
- capacitor spacing from the component-placement rule or a value labeled
  `skill default` on the line where it is used;
- keepouts from the IC body, exposed pad, testpoints, and mechanical geometry.

`jitx.query.query(root, target, ...)` applies registered transformers, including
pad-to-copper and via-to-copper (`jitx/query.py:283`, `jitx/landpattern.py:173`,
`jitx/via.py:197`), and opens the design and substrate contexts, so its root
must be the design. To read a component's own landpattern before the design
exists (the capacitor geometry above), walk it with `jitx.inspect.visit` and
compose the same frames. Compose `trace.transform * element.transform` to read
a center (`jitx/inspect.py:174`, `jitx/landpattern.py:191`).

Do not use a nominal case-code table when the selected part already has a
landpattern. Parts queries can change the returned manufacturer part and its
landpattern. `CapacitorQuery` is the installed query type
(`jitxlib/parts/query_api.py:451`), and `Capacitor` builds its selected
landpattern from the returned database record
(`jitxlib/parts/query_api.py:1347`). Query the result that will be built.

## Structural hints

Hints carry real JITX ports. The key is the actual IC power-port object, not a
name assembled from a rail, pin number, or loop index.

```python
from dataclasses import dataclass
from collections.abc import Mapping

from jitx.net import Port


@dataclass(frozen=True)
class DecouplingHint:
    key: Port
    label: str
    power_ports: tuple[Port, ...]
    return_ports: tuple[Port, ...]
    power_pad_centers: tuple[tuple[float, float], ...]
    return_pad_centers: tuple[tuple[float, float], ...]
    power_pad_width: float
    return_pad_width: float


type HintMap = Mapping[Port, DecouplingHint]
```

Keep the mapping local while constructing the bank. Store the JITX objects it
creates, not a parallel string-keyed model. A `Circuit` requires every element
to remain reachable through an attribute, list, or mapping
(`jitx/circuit.py:50`).

The route endpoints and the hint ports must share a common owning circuit. The
simplest reusable shape is a bank that wraps the target IC, so the IC,
capacitors, vias, puddles, routes, and nets all sit below one
`DecouplingBank`. If an existing design cannot be wrapped, put the authored
routes on the common parent circuit and keep the geometry solver input in the
bank.

## DecouplingBank

The example below shows the structural pattern. `ic_type` builds the IC inside
the bank. `hint_factory` returns a `HintMap` keyed by that IC's real power
ports. `cap_geometry` and `package_rotation` come from the selected
landpattern query. `_power_puddle_shape` returns the puddle polygon for one
hint: the shipped reference uses a rectangular corridor between the served IC
pad and the capacitor pad (`_corridor` in its `design.py`); the pad-union
form is in `power-and-pours.md`, section 9, and has not been built yet.

```python
from collections.abc import Callable

from jitx import Circuit, Net, Pour, current
from jitx.circuit import Route
from jitx.component import Component
from jitx.constraints import AnyObject, Tag, Tags, design_constraint
from jitx.via import Via
from jitx.interval import AtLeast
from jitxlib.parts import Capacitor, CapacitorQuery, SortDir, SortKey

from decoupling_solver import BankSpec, CapacitorGeometry, HintSpec, Solution, solve


class EscapeTag(Tag):
    """Base tag for a specific escape segment."""


class DecouplingEscapeTag(EscapeTag):
    """Short routes between capacitor pads and the IC pads they serve."""


class DecouplingBank(Circuit):
    def __init__(
        self,
        ic_type: type[Component],
        hint_factory: Callable[[Component], HintMap],
        rail_voltage: float,
        cap_geometry: CapacitorGeometry,
        capacitance: float = 22e-6,  # Bogatin 2019: largest MLCC, 22 uF typical; pass the datasheet value when it gives one
        rated_voltage_factor: float = 2.0,  # Bogatin 2019: rated at least 2x the rail; the datasheet wins when it specifies
        keepouts: tuple[tuple[tuple[float, float], ...], ...],
        capacitor_spacing: float,
        package_rotation: int,
    ) -> None:
        self.ic = ic_type().at(0.0, 0.0)
        hints_by_key = hint_factory(self.ic)
        hints = tuple(hints_by_key.values())

        substrate = current.design.substrate
        fab = substrate.constraints
        via_cls: type[Via] = substrate.StdViaPreferred
        via_pad_diameter = via_cls.diameter  # substrate via-class field
        clearance_floor = fab.min_copper_copper_space  # FabricationConstraints field
        grid_step = 0.25  # skill default: 0.25 mm solver grid step
        search_radius = 3.0  # skill default: 3.0 mm solver search radius
        pad_limit = min(
            cap_geometry.pad_width,
            *(hint.power_pad_width for hint in hints),
            *(hint.return_pad_width for hint in hints),
        )  # queried pad widths
        if pad_limit < fab.min_copper_width:
            raise ValueError("a served pad is narrower than the fabrication copper floor")
        escape_width = pad_limit  # the route width the bank uses; the solver spaces the loop paths by it
        spec = BankSpec(
            hints=tuple(
                HintSpec(
                    name=hint.label,
                    power_pads=hint.power_pad_centers,
                    return_pads=hint.return_pad_centers,
                )
                for hint in hints
            ),
            capacitor=cap_geometry,
            keepouts=keepouts,
            via_pad_diameter=via_pad_diameter,
            clearance_floor=clearance_floor,
            capacitor_spacing=capacitor_spacing,
            grid_step=grid_step,
            search_radius=search_radius,
            escape_width=escape_width,
        )
        self.solution = solve(spec)

        cap_query = CapacitorQuery(
            capacitance=capacitance,
            rated_voltage=AtLeast(rated_voltage_factor * rail_voltage),  # a minimum, not an exact catalog value
            type="ceramic",
            mounting="smd",
            sort=SortKey("area", SortDir.INCREASING),
        )
        self.capacitors = [Capacitor(cap_query) for _ in hints]
        for capacitor, hint in zip(self.capacitors, hints, strict=True):
            capacitor.insert(
                hint.power_ports[0], hint.return_ports[0], short_trace=True
            )

        self._apply_solution(via_cls, package_rotation)
        self.escape_routes = []
        for capacitor, hint, power_via, return_via in zip(
            self.capacitors, hints, self.power_vias, self.return_vias, strict=True
        ):
            self.escape_routes.extend(
                (
                    Route(capacitor.p1, power_via, layer=0),  # substrate top layer
                    Route(power_via, hint.key, layer=0),  # substrate top layer
                    Route(capacitor.p2, return_via, layer=0),  # substrate top layer
                    Route(return_via, hint.return_ports[0], layer=0),  # substrate top layer
                )
            )
        Tags(DecouplingEscapeTag()).assign(self.escape_routes)

        puddle_width = cap_geometry.pad_width  # landpattern value read with jitx.query
        self.power_puddles = [
            Pour(
                _power_puddle_shape(hint, solved, puddle_width),
                layer=0,  # substrate top layer
            )
            for hint, solved in zip(hints, self.solution.placements, strict=True)
        ]

        self.rail_nets = [
            Net((*hint.power_ports, capacitor.p1, via, puddle))
            for hint, capacitor, via, puddle in zip(
                hints,
                self.capacitors,
                self.power_vias,
                self.power_puddles,
                strict=True,
            )
        ]
        self.return_net = Net(
            (
                *(port for hint in hints for port in hint.return_ports),
                *(capacitor.p2 for capacitor in self.capacitors),
                *self.return_vias,
            )
        )  # one shared return: the board ground is one net

        escape_clearance = fab.min_copper_copper_space  # FabricationConstraints field
        self.rules = [
            design_constraint(
                DecouplingEscapeTag(), priority=4  # skill priority ladder: 4, escape rules
            ).trace_width(escape_width),
            design_constraint(
                DecouplingEscapeTag(),
                AnyObject,
                priority=4,  # skill priority ladder: 4, escape rules
            ).clearance(escape_clearance),
        ]
        self.loop_areas = tuple(
            solved.loop_area for solved in self.solution.placements
        )
```

`Capacitor.insert(..., short_trace=True)` connects each capacitor port, and the
capacitor remains a structural component owned by the
bank (`jitxlib/parts/query_api.py:1461`). `Route` accepts ports, pads, vias, and
route endpoints, and captured copper is exposed through `route.traces`
(`jitx/circuit.py:466`, `jitx/circuit.py:569`).

The two vias per capacitor (skill default: two vias per capacitor) are
instances of the substrate's via class. A via
is positionable and carries its own pad diameter and layer span
(`jitxlib/jlcpcb/vias.py:24`, `jitx/via.py:37`, `jitx/placement.py:133`). Store every instance on the bank,
then include each power via in its rail net and every return via in the one
shared return net (the board ground is one net; separate return domains exist
only when the schematic has them, and then each gets its own net). `Net` accepts `Via` and `Copper` members directly
(`jitx/net.py:645`, `jitx/net.py:733`). `PortAttachment` is not needed for this
plain power-net membership. Two route segments on each side (skill default: two segments) use the via as an endpoint, so realized copper reaches its pad.

The local `Pour` is also a rail-net member. `Pour` takes a shape and one layer
index (`jitx/copper.py:46`); do not pass the deprecated `isolate=` parameter.
The puddle is local to this circuit so it moves with the IC and capacitors. It
does not authorize a board-wide power fill.

Tags are module-scope subclasses. `Tags(...).assign(...)` supports `Route`,
`Circuit`, `Component`, `Pad`, `Via`, `Copper`, and `Pour` targets
(`jitx/constraints.py:495`, `jitx/constraints.py:557`). The escape width is a
one-condition rule, while clearance is a two-condition rule. The conditions
are positional-only (`jitx/constraints.py:71`). Trace width exists on the
unary rule (`jitx/constraints.py:910`), and clearance exists only on the binary
rule (`jitx/constraints.py:1160`). Priority 4 is the escape rung of the ladder in `SKILL.md`, above the board
defaults at 0 and every class rule. Bound escape width by the queried capacitor and IC pad widths.

## Solution adapter

Keep the adapter small. It transfers solver coordinates into JITX placements
and stores the via lists structurally.

```python
def _apply_solution(self, via_cls: type[Via], package_rotation: int) -> None:
    for capacitor, solved in zip(
        self.capacitors, self.solution.placements, strict=True
    ):
        capacitor.at(
            solved.center[0], solved.center[1],
            rotate=solved.rotation + package_rotation,
        )
    self.power_vias = [
        via_cls().at(*solved.power_via) for solved in self.solution.placements
    ]
    self.return_vias = [
        via_cls().at(*solved.return_via) for solved in self.solution.placements
    ]
```

`Positionable.at()` writes the direct descendant's local placement
(`jitx/placement.py:133`). Give the bank an explicit position. `Circuit.at(floating=True)`
clears the fixed transform so a person can place the bank as one block in
the UI (`jitx/circuit.py:289`), but with no interactive placement stored the
runtime parks a floating circuit off the board and every route in it fails
with `Route targets not in router: ... is off the board` while `jitx build`
still reports `status: ok` (observed in the shipped reference). Instantiate it
at the top level like this:

```python
class MainCircuit(Circuit):
    def __init__(self) -> None:
        self.decoupling = DecouplingBank(
            ic_type=MyIc,
            hint_factory=make_hints,
            rail_voltage=my_rail_voltage,
            cap_geometry=queried_cap_geometry,
            keepouts=ic_keepouts,
            capacitor_spacing=placement_spacing,
            package_rotation=queried_package_rotation,
        ).at(bank_x, bank_y)  # explicit; floating only for interactive placement
```

Because the IC lives inside the bank, the capacitor placements, vias, routes,
and puddles all share its local frame. Moving the bank moves the whole
decoupling block without recomputing assembled names or absolute board
coordinates.

## What to check after build

Build status is not evidence that an authored route realized. Submit the
design, capture it, and inspect the bank. `RuntimeDesign.query` delegates to
the transformation query layer (`jitx/run/runtime.py:421`), and
`SyncRuntimeDesign.capture()` reads runtime geometry back into the design
objects (`jitx/run/runtime.py:602`).

```python
import math

from jitxlib.parts import Capacitor

rd.capture()
bank = rd.root.circuit.decoupling

for route in bank.escape_routes:
    assert route.traces, f"unrealized decoupling escape: {route}"

queried = [
    capacitor
    for _, capacitor in rd.query(Capacitor)
    if any(capacitor is owned for owned in bank.capacitors)
]
assert len(queried) == len(bank.capacitors)

tolerance = 1e-6  # skill default: 0.000001 mm placement readback tolerance
for capacitor in queried:
    index = next(
        index for index, owned in enumerate(bank.capacitors) if capacitor is owned
    )
    solved = bank.solution.placements[index]
    assert capacitor.transform is not None
    actual = capacitor.transform.translation
    error = math.hypot(
        actual[0] - solved.center[0], actual[1] - solved.center[1]
    )
    assert error <= tolerance, (actual, solved.center)
```

Also check that each via and puddle resolves to its intended net through
`rd.nets().find(...)`, the realized escape widths match the priority 4 rule,
and the selected capacitor landpattern still matches the geometry used by the
solver.

Record every per-capacitor `loop_area` and `solution.total_loop_area` in the
design's verification notes. They are solver outputs in square millimeters,
not measured inductances. Record the part numbers selected by the capacitor
query beside them so a later part substitution triggers a geometry review.

The shipped reference is in
`evals/cases/reference/decoupling-bank/`. Its check script prints the realized
route count, the queried placement count, and the recorded loop areas. If the
runtime cannot be reached, its `NOTES.md` must say so and retain the unrun
build, capture, and check steps as open items.
