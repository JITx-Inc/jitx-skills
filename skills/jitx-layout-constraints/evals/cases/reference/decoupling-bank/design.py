"""Reference DecouplingBank on the JLC04161H_7628 substrate.

The IC is a four-pad placeholder QFN (skill default: four pads) used only to
expose two power pins and two ground pins (skill default: two of each). The
capacitors, via locations, and route endpoints come from the geometry solver.
The pure solver is copied beside this module before build.
"""

from dataclasses import dataclass
from math import hypot

from decoupling_solver import (  # pyright: ignore[reportMissingImports]
    BankSpec,
    CapacitorGeometry,
    HintSpec,
    Solution,
    solve,
)
import jitx
from jitx import Board, Circuit, Design, Net, Polygon, Pour, current
from jitx.circuit import Route
from jitx.constraints import AnyObject, IsCopper, IsTrace, Tag, Tags, design_constraint
from jitx.feature import Courtyard, Paste, Soldermask
from jitx.inspect import visit
from jitx.landpattern import Landpattern, Pad, PadMapping, PadShape
from jitx.net import Port
from jitx.shapes import Shape
from jitx.shapes.composites import rectangle
from jitxlib.jlcpcb import JLC04161H_7628  # pyright: ignore[reportMissingImports]
from jitxlib.parts import Capacitor, CapacitorQuery, SortDir, SortKey
from jitxlib.symbols.box import BoxSymbol


class EscapeTag(Tag):
    """Base tag for specific, short escape route segments."""


class DecouplingEscapeTag(EscapeTag):
    """Routes between decoupling capacitor pads and the served IC pads."""


class PlaceholderIcPad(Pad):
    """Solderable pad for the placeholder QFN."""

    pad_shape: Shape = rectangle(
        0.45, 0.30  # skill default: 0.45 mm by 0.30 mm IC pad
    )
    shape = pad_shape

    def __init__(self) -> None:
        self.soldermask = Soldermask(self.pad_shape)
        self.paste = Paste(self.pad_shape)


class PlaceholderQfnLandpattern(Landpattern):
    """Placeholder QFN with four pads (skill default: four pads)."""

    p1 = PlaceholderIcPad().at(-0.85, -0.50)  # skill default: IC pad center in mm
    p2 = PlaceholderIcPad().at(-0.85, 0.50)  # skill default: IC pad center in mm
    p3 = PlaceholderIcPad().at(0.85, -0.50)  # skill default: IC pad center in mm
    p4 = PlaceholderIcPad().at(0.85, 0.50)  # skill default: IC pad center in mm
    courtyard = Courtyard(
        rectangle(2.20, 1.80)  # skill default: 2.20 mm by 1.80 mm courtyard
    )


class PlaceholderQfn(jitx.Component):
    """Reference-only IC with two power and two ground pins (skill default)."""

    reference_designator_prefix = "U"
    mpn = "PLACEHOLDER-QFN-4"
    manufacturer = "Reference only"

    VCORE = Port()
    GND_CORE = Port()
    VIO = Port()
    GND_IO = Port()

    landpattern = PlaceholderQfnLandpattern()
    symbol = BoxSymbol()
    mappings = [
        PadMapping(
            {
                VCORE: landpattern.p1,
                GND_CORE: landpattern.p3,
                VIO: landpattern.p2,
                GND_IO: landpattern.p4,
            }
        )
    ]


@dataclass(frozen=True)
class DecouplingHint:
    """One capacitor request keyed by an actual IC power-port object."""

    key: Port
    label: str
    power_ports: tuple[Port, ...]
    return_ports: tuple[Port, ...]
    power_pad_centers: tuple[tuple[float, float], ...]
    return_pad_centers: tuple[tuple[float, float], ...]
    power_pad_width: float
    return_pad_width: float


def query_capacitor_geometry(
    capacitor: Capacitor,
) -> tuple[CapacitorGeometry, int]:
    """Read the selected capacitor's solver envelope and pad orientation."""

    # `jitx.query.query` needs a design-rooted object: it opens
    # `SubstrateContext(root.substrate)` (jitx/query.py:247). A `Capacitor` root
    # raises `'Capacitor' object has no attribute 'substrate'`. `Pad` and
    # `Courtyard` are authored objects, so the transformer graph would collapse
    # to identity anyway (jitx/query.py:209) and `visit` reads the same frames.
    pad_rows: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for trace, pad in visit(capacitor, Pad):
        if trace.transform is None or pad.transform is None:
            raise ValueError("selected capacitor pad has an unresolved frame")
        pad_shape = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
        bounds = pad_shape.at(trace.transform * pad.transform).to_shapely().g.bounds
        pad_rows.append(
            (
                ((bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0),
                (bounds[2] - bounds[0], bounds[3] - bounds[1]),
            )
        )
    if len(pad_rows) != 2:  # jitxlib/parts/query_api.py:1434
        raise ValueError("selected capacitor must query to exactly two pads")

    (p1_center, _), (p2_center, _) = pad_rows
    dx = p2_center[0] - p1_center[0]
    dy = p2_center[1] - p1_center[1]
    pad_pitch = hypot(dx, dy)
    axis_tolerance = 1e-6  # skill default: 0.000001 mm axis-alignment tolerance
    if pad_pitch <= axis_tolerance or min(abs(dx), abs(dy)) > axis_tolerance:
        raise ValueError("selected capacitor pads must lie on one orthogonal axis")
    horizontal = abs(dx) > abs(dy)
    # The rotation that lands p1 (the solver's power pad) on local negative X.
    # Rotation is counter-clockwise, so (x, y) -> (-y, x) at 90 degrees: p1 at
    # local +Y needs 90, p1 at local -Y needs 270.
    package_rotation = (
        0 if horizontal and dx > 0 else 180 if horizontal else 270 if dy > 0 else 90
    )

    courtyard_bounds = []
    for trace, courtyard in visit(capacitor, Courtyard):
        if trace.transform is None:
            raise ValueError("selected capacitor courtyard has an unresolved frame")
        courtyard_bounds.append(
            courtyard.shape.at(trace.transform).to_shapely().g.bounds
        )
    if not courtyard_bounds:
        raise ValueError("selected capacitor landpattern has no courtyard")
    bounds = (
        min(row[0] for row in courtyard_bounds),
        min(row[1] for row in courtyard_bounds),
        max(row[2] for row in courtyard_bounds),
        max(row[3] for row in courtyard_bounds),
    )
    body_x = bounds[2] - bounds[0]
    body_y = bounds[3] - bounds[1]
    pad_x = max(row[1][0] for row in pad_rows)
    pad_y = max(row[1][1] for row in pad_rows)
    geometry = CapacitorGeometry(
        body_length=body_x if horizontal else body_y,
        body_width=body_y if horizontal else body_x,
        pad_length=pad_x if horizontal else pad_y,
        pad_width=pad_y if horizontal else pad_x,
        pad_pitch=pad_pitch,
    )
    return geometry, package_rotation


def _rotate(point: tuple[float, float], rotation: int) -> tuple[float, float]:
    x, y = point
    if rotation == 0:
        return x, y
    if rotation == 90:
        return -y, x
    if rotation == 180:
        return -x, -y
    if rotation == 270:
        return y, -x
    raise ValueError(f"unsupported solver rotation: {rotation}")


def _placed(
    point: tuple[float, float], center: tuple[float, float], rotation: int
) -> tuple[float, float]:
    x, y = _rotate(point, rotation)
    return x + center[0], y + center[1]


def _corridor(
    start: tuple[float, float], end: tuple[float, float], width: float
) -> Polygon:
    """Return a rectangular local puddle joining two pad centers."""

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = hypot(dx, dy)
    if length == 0:
        raise ValueError("local puddle endpoints must differ")
    nx = -dy * width / (2.0 * length)
    ny = dx * width / (2.0 * length)
    return Polygon(
        (
            (start[0] + nx, start[1] + ny),
            (end[0] + nx, end[1] + ny),
            (end[0] - nx, end[1] - ny),
            (start[0] - nx, start[1] - ny),
        )
    )


class DecouplingBank(Circuit):
    """Placeholder IC plus one solved capacitor for each structural hint."""

    def __init__(self) -> None:
        self.ic = PlaceholderQfn().at(0.0, 0.0)
        hints_by_key = {
            self.ic.VCORE: DecouplingHint(
                key=self.ic.VCORE,
                label="core",
                power_ports=(self.ic.VCORE,),
                return_ports=(self.ic.GND_CORE,),
                power_pad_centers=((-0.85, -0.50),),  # skill default: placeholder IC pad center in mm
                return_pad_centers=((0.85, -0.50),),  # skill default: placeholder IC pad center in mm
                power_pad_width=0.30,  # skill default: 0.30 mm placeholder IC pad width
                return_pad_width=0.30,  # skill default: 0.30 mm placeholder IC pad width
            ),
            self.ic.VIO: DecouplingHint(
                key=self.ic.VIO,
                label="io",
                power_ports=(self.ic.VIO,),
                return_ports=(self.ic.GND_IO,),
                power_pad_centers=((-0.85, 0.50),),  # skill default: placeholder IC pad center in mm
                return_pad_centers=((0.85, 0.50),),  # skill default: placeholder IC pad center in mm
                power_pad_width=0.30,  # skill default: 0.30 mm placeholder IC pad width
                return_pad_width=0.30,  # skill default: 0.30 mm placeholder IC pad width
            ),
        }
        hints = tuple(hints_by_key.values())
        cap_query = CapacitorQuery(
            capacitance=22e-6,  # Bogatin basis: typical 22 uF MLCC
            rated_voltage=10.0,  # skill default: 10.0 V is 2x a 5.0 V rail
            type="ceramic",
            mounting="smd",
            case=["0402", "0603", "0805", "1206"],
            sort=SortKey("area", SortDir.INCREASING),
        )
        self.capacitors = [Capacitor(cap_query) for _ in hints]
        queried_geometry = tuple(
            query_capacitor_geometry(capacitor) for capacitor in self.capacitors
        )
        self.cap_geometry, self.package_rotation = queried_geometry[0]
        if any(item != queried_geometry[0] for item in queried_geometry[1:]):
            raise ValueError("capacitor query returned inconsistent landpatterns")

        via_cls = JLC04161H_7628.StdViaPreferred  # pyright: ignore[reportAttributeAccessIssue]
        via_pad_diameter = float(
            via_cls.diameter  # JLC04161H_7628 substrate via field
        )  # Via.diameter is float | ViaDiameter (jitx/via.py:60); ViaDiameter defines __float__ (jitx/via.py:328)
        fab = current.design.substrate.constraints
        clearance_floor = fab.min_copper_copper_space  # FabricationConstraints field
        capacitor_spacing = 0.25  # skill default: 0.25 mm component spacing
        keepout = (
            (-0.70, -0.35),
            (0.70, -0.35),
            (0.70, 0.35),
            (-0.70, 0.35),
        )  # skill default: placeholder IC-body keepout in mm
        spec = BankSpec(
            hints=tuple(
                HintSpec(
                    name=hint.label,
                    power_pads=hint.power_pad_centers,
                    return_pads=hint.return_pad_centers,
                )
                for hint in hints
            ),
            capacitor=self.cap_geometry,
            keepouts=(keepout,),
            via_pad_diameter=via_pad_diameter,
            clearance_floor=clearance_floor,
            capacitor_spacing=capacitor_spacing,
            grid_step=0.25,  # skill default: 0.25 mm solver grid step
            search_radius=3.0,  # skill default: 3.0 mm solver search radius
        )
        self.solution: Solution = solve(spec)

        for cap, hint, placement in zip(
            self.capacitors, hints, self.solution.placements, strict=True
        ):
            cap.insert(hint.power_ports[0], hint.return_ports[0], short_trace=True)
            cap.at(
                placement.center[0],
                placement.center[1],
                rotate=placement.rotation + self.package_rotation,
            )

        self.power_vias = [
            via_cls().at(*placement.power_via)
            for placement in self.solution.placements
        ]
        self.return_vias = [
            via_cls().at(*placement.return_via)
            for placement in self.solution.placements
        ]
        self.escape_routes = []
        for cap, hint, power_via, return_via in zip(
            self.capacitors,
            hints,
            self.power_vias,
            self.return_vias,
            strict=True,
        ):
            self.escape_routes.extend(
                (
                    Route(cap.p1, power_via, layer=0),  # substrate top layer
                    Route(power_via, hint.power_ports[0], layer=0),  # substrate top layer
                    Route(cap.p2, return_via, layer=0),  # substrate top layer
                    Route(return_via, hint.return_ports[0], layer=0),  # substrate top layer
                )
            )
        Tags(DecouplingEscapeTag()).assign(self.escape_routes)

        pad_limit = min(
            self.cap_geometry.pad_width,
            *(hint.power_pad_width for hint in hints),
            *(hint.return_pad_width for hint in hints),
        )  # queried capacitor pad width and placeholder IC pad widths
        if pad_limit < fab.min_copper_width:
            raise ValueError("a served pad is narrower than the fabrication copper floor")
        escape_width = pad_limit
        self.escape_width = escape_width
        puddle_width = escape_width  # queried pad widths and FabricationConstraints field
        self.power_puddles = []
        for hint, placement in zip(hints, self.solution.placements, strict=True):
            cap_power_pad = _placed(
                (-self.cap_geometry.pad_pitch / 2.0, 0.0),
                placement.center,
                placement.rotation,
            )
            self.power_puddles.append(
                Pour(
                    _corridor(hint.power_pad_centers[0], cap_power_pad, puddle_width),
                    layer=0,
                )
            )

        self.rail_nets = [
            Net(
                (
                    hint.power_ports[0],
                    cap.p1,
                    power_via,
                    puddle,
                ),
            )
            for hint, cap, power_via, puddle in zip(
                hints,
                self.capacitors,
                self.power_vias,
                self.power_puddles,
                strict=True,
            )
        ]
        self.ground_net = Net(
            (
                *(hint.return_ports[0] for hint in hints),
                *(cap.p2 for cap in self.capacitors),
                *self.return_vias,
            ),
            name="GND",
        )

        escape_clearance = fab.min_copper_copper_space  # FabricationConstraints field
        self.rules = [
            design_constraint(
                DecouplingEscapeTag(), priority=4  # skill priority ladder: 4, escape rules
            ).trace_width(escape_width),
            design_constraint(
                DecouplingEscapeTag(), AnyObject, priority=4  # skill priority ladder: 4, escape rules
            ).clearance(escape_clearance),
        ]
        self.loop_areas = tuple(
            placement.loop_area for placement in self.solution.placements
        )


class ReferenceBoard(Board):
    shape = rectangle(16.0, 12.0)  # skill default: 16.0 mm by 12.0 mm board


class ReferenceCircuit(Circuit):
    def __init__(self) -> None:
        # `at(floating=True)` leaves the bank "subject to interactive placement"
        # (jitx/circuit.py:314). With no interactive placement on disk the
        # runtime parks it beside the board, and every escape route then fails
        # with "Route targets not in router: ... is off the board on layer 0".
        # A headless reference has to place the bank on the board.
        self.decoupling = DecouplingBank().at(0.0, 0.0)  # bank origin on the board


class DecouplingReference(Design):
    substrate = JLC04161H_7628()
    board = ReferenceBoard()
    circuit = ReferenceCircuit()

    def __init__(self) -> None:
        fab = self.substrate.constraints
        default_width = fab.min_copper_width  # FabricationConstraints field
        default_clearance = fab.min_copper_copper_space  # FabricationConstraints field
        self.rules = [
            design_constraint(IsTrace).trace_width(default_width),
            design_constraint(IsCopper, IsCopper).clearance(default_clearance),
        ]


Device: type[DecouplingReference] = DecouplingReference
