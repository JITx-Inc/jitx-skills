"""Grade a candidate substrate against the fab report it was built from.

Run it through ``grade_substrate.py``, or directly as
``pytest substrate_grader.py`` with these settings in the environment:

- ``SUBSTRATE_FILE``: the Python file that defines the candidate substrate.
  Required. Unset or blank is an error; there is no default substrate.
- ``FAB_CSV``: the fab report to grade it against. Required. Unset or blank
  is an error; there is no default report.
- ``SUBSTRATE_CLASS``: optional. Picks the ``Substrate`` subclass when the
  file defines several. Set but blank is an error.

Every expected value is read from the report at test time. Layer count, via
inventory, impedance targets, routing layers and fab-rule count all come from
the CSV; none is pinned here. The grader does assume the report is in the
JITX fab-report SECTION layout (DOCUMENT, MATERIALS_DIELECTRIC,
MATERIALS_COPPER, STACKUP, VIAS, IMPEDANCE, FAB_RULES, NOTES), with at least
the column headers it reads. Columns are read by name, so a report may carry
more; the case report adds Manufacturer and Product to MATERIALS_COPPER. It
also assumes the report holds these:

- FAB_RULES has exactly one capability row (no JITX field) for each of the
  mechanical drill minimum, the mechanical aspect-ratio maximum and the laser
  aspect-ratio maximum, found by their Rule text, and the mechanical drill
  minimum is above ``min_drill_diameter``, which holds the laser minimum.
- Every inner routing layer has two reference planes, one on each side, and
  an outer routing layer has one.
- A reference plane's height is the dielectric between line and plane, summed
  over the STACKUP Dielectric rows between them, as SKILL.md defines it; the
  copper of a layer in between is not counted.

What it checks, against the report:

- Stackup: one entry per STACKUP row in order, copper or dielectric as the
  row says, thickness, Dk and Df, copper roughness (matte and drum Rz in um
  in the copper class's docstring, and the ``roughness`` scalar, where it is
  set, equal to matte Rz in mm), both thickness totals in DOCUMENT, copper
  layer names that carry their layer id, distinct dielectric
  rows kept distinct, each dielectric's ``material_name`` carrying its
  MATERIALS_DIELECTRIC Product, and mirrored rows mirrored in the design.
- Vias: exactly the VIAS inventory, found by drill type and span rather than
  by name, each with its hole, pad, fill, tenting, via-in-pad and drill
  direction; depth on the convention each drill type uses; annular ring and
  aspect ratio within the stated capability; no invented SI models.
- Fab rules: every mapped FAB_RULES row on ``FabricationConstraints`` and in
  the translated rules; no impedance geometry below the engine minimums.
- Routing structures: one per controlled target, found by its target
  impedance; every geometry and layer the report lists, with width,
  clearance, pair gap, insertion loss and velocity from ``Eps_eff``;
  reference planes as ``Ref_layers`` names them, at the substrate-modeler
  skill's default width of 3x the dielectric height; ``-UNC`` rows folded
  into their pair; the uncontrolled default row not modelled.
- Neck regions: a controlled target whose rows quote ``Neck_*`` columns has
  a structure of its own beside its main one, single-ended or differential
  as the target is, carrying the neck width, gap and clearance on the layers
  of those rows, found by that geometry rather than by impedance. Its
  impedance, velocity and loss are not checked (the report quotes only a
  modelled impedance for a neck), and how a design applies it, by tag, is not
  graded here. No ``NeckDown`` may appear in the file or on any structure.

The substrate is wrapped in the grader's own design, on a board of the
report's DOCUMENT ``Board size``, and translated offline; that translation is
how the vias, materials and rules are read. The board itself is not graded.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
import re
import sys
import unittest
import warnings
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING
from unittest import mock

import fabcsv

# `instantiation` is private; it is the context jitx.test.TestCase enters, and
# the loader needs it once at import to see the candidate's stackup and rules.
from jitx._instantiation import instantiation

# `package_design` is private; jitx.test.TestCase supplies the instantiation
# context but exposes no public translate entry point.
from jitx._translate.design import package_design
from jitx.board import Board
from jitx.circuit import Circuit
from jitx.design import Design
from jitx.inspect import decompose
from jitx.proxy import typeof
from jitx.shapes import Shape
from jitx.shapes.composites import rectangle

# `_RefLayer` is private; `RoutingStructure.Layer` exposes no public accessor
# for the planes carried by `.reference()`.
from jitx.si import DifferentialRoutingStructure, RoutingStructure, _RefLayer
from jitx.stackup import Conductor, Dielectric, Material
from jitx.substrate import FabricationConstraints, Substrate
from jitx.test import TestCase
from jitx.units import ohm
from jitxlib.physics import phase_velocity
from parent_watch import watch_parent

if TYPE_CHECKING:
    # Annotation-only: the protobuf message types of the translated design.
    from jitxcore._proto.design_pb2 import DesignV1
    from jitxcore._proto.via_pb2 import Via as ViaProto

KIT_PACKAGE = "jitxexamples.jumpstart_kits"
"""A candidate may not subclass or reuse any class under this package."""

VELOCITY_RTOL = 1e-6
"""Relative tolerance on phase velocity. A one-digit change in the fourth
decimal of ``Eps_eff`` moves velocity by about 2e-5, so it still fails."""

_SIDE_TOP = 0
"""Proto ``Side`` enum value for TOP. Asserted against the descriptor by
:meth:`TestVias.test_side_enum_matches_descriptor` rather than trusted."""

TENT_MODES = {
    "Both": "TENT_BOTH",
    "Top": "TENT_TOP",
    "Bottom": "TENT_BOTTOM",
    "None": "TENT_NONE",
    "": "TENT_NONE",
}
"""VIAS ``Tented`` cell -> the translated ``TentMode`` name."""

UNFILLED = ("", "None", "No")
"""VIAS ``Fill`` cells that mean the via is not filled."""


def optional_setting(name: str) -> str | None:
    """A setting that may be unset (``None``). Set but blank is an error."""
    value = os.environ.get(name)
    if value is None:
        return None
    if not value.strip():
        raise ValueError(f"{name} is set but empty. Unset it, or give it a value.")
    return value.strip()


def required_setting(name: str) -> str:
    """A setting that must be given. Unset or blank is an error, never a default."""
    value = optional_setting(name)
    if value is None:
        raise ValueError(
            f"{name} is not set. The grader has no default; give it a value."
        )
    return value


def _load_module() -> ModuleType:
    """The module named by ``SUBSTRATE_FILE``."""
    path = required_setting("SUBSTRATE_FILE")
    file = Path(path).expanduser().resolve()
    if not file.is_file():
        raise FileNotFoundError(f"SUBSTRATE_FILE={path!r} is not a file.")
    # A unique name per path, so a candidate called board.py never collides
    # with another module of that name.
    name = "_candidate_" + hashlib.sha256(str(file).encode()).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, file)
    if spec is None or spec.loader is None:
        raise ImportError(f"SUBSTRATE_FILE={path!r} cannot be imported.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # The candidate's own directory is importable only while it loads.
    sys.path.insert(0, str(file.parent))
    try:
        # A candidate's own warning filters stay inside its import, so they
        # cannot hide the GradedTarget warning the wrapper reads.
        with warnings.catch_warnings():
            spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    finally:
        sys.path.remove(str(file.parent))
    return module


def _is_kit(klass: type) -> bool:
    return klass.__module__ == KIT_PACKAGE or klass.__module__.startswith(
        KIT_PACKAGE + "."
    )


def refuse_kit_classes(module: ModuleType, chosen: type[Substrate]) -> None:
    """Refuse a candidate that subclasses or reuses any kit class.

    Checked: every class in the module, every class nested in the substrate
    or its bases, and the classes of its instantiated ``stackup`` and
    ``constraints``, so neither a subclassed part nor an imported one is
    graded as the candidate's own work.
    """
    classes = [value for value in vars(module).values() if isinstance(value, type)]
    for klass in chosen.__mro__:
        classes += [value for value in vars(klass).values() if isinstance(value, type)]
    try:
        with instantiation.activate():
            instance = chosen()
            parts = [getattr(instance, "stackup", None)]
            parts.append(getattr(instance, "constraints", None))
    except (AttributeError, KeyError, TypeError, ValueError):
        # A substrate that cannot be instantiated is left for the tests to
        # report; nothing borrowed can be read from it here.
        parts = []
    classes += [type(part) for part in parts if part is not None]
    borrowed = sorted(
        {
            f"{klass.__module__}.{klass.__qualname__}"
            for cls in classes
            for klass in cls.__mro__
            if _is_kit(klass)
        }
    )
    if borrowed:
        raise TypeError(
            f"{chosen.__name__} in {module.__file__} uses the kit's own classes "
            f"({', '.join(borrowed)}). A candidate must define its substrate, "
            "stackup and rules itself."
        )


def load_substrate_class() -> type[Substrate]:
    """The ``Substrate`` subclass under test.

    Candidates are the ``Substrate`` subclasses defined in the module (not
    imported into it), less any that another candidate subclasses, so a shared
    base class does not count. ``SUBSTRATE_CLASS`` picks among all of them.
    Runs at import time, because JITX refuses to define new classes inside the
    instantiation context that every test runs in.
    """
    wanted = optional_setting("SUBSTRATE_CLASS")
    module = _load_module()
    defined = [
        value
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, Substrate)
        and value.__module__ == module.__name__
    ]
    leaves = {
        cls.__name__: cls
        for cls in defined
        if not any(other is not cls and issubclass(other, cls) for other in defined)
    }
    listed = ", ".join(sorted(cls.__name__ for cls in defined)) or "none"
    if wanted is not None:
        chosen = next((cls for cls in defined if cls.__name__ == wanted), None)
        if chosen is None:
            raise LookupError(
                f"SUBSTRATE_CLASS={wanted!r} is not a Substrate subclass defined "
                f"in {module.__file__}. Found: {listed}."
            )
    elif len(leaves) == 1:
        chosen = next(iter(leaves.values()))
    else:
        raise LookupError(
            f"{module.__file__} must define exactly one Substrate subclass that no "
            f"other subclasses, or SUBSTRATE_CLASS must name one. Found: {listed}."
        )
    refuse_kit_classes(module, chosen)
    return chosen


def fab_csv() -> Path:
    """The report named by ``FAB_CSV``."""
    value = required_setting("FAB_CSV")
    path = Path(value).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"FAB_CSV={value!r} is not a file.")
    return path


# Launched by grade_substrate.py: end with it, even if it is killed outright,
# before the candidate runs.
watch_parent()
SUBSTRATE = load_substrate_class()
FAB_CSV = fab_csv()


def candidate() -> Substrate:
    """A fresh instance of the substrate under test. Requires an instantiation
    context."""
    return SUBSTRATE()


class GradedTarget(UserWarning):
    """Names what this run grades. Issued once at import, so it shows in the
    warnings summary of every run, passing ones included, under ``pytest -q``."""


warnings.warn(
    GradedTarget(
        f"substrate {SUBSTRATE.__name__} from "
        f"{sys.modules[SUBSTRATE.__module__].__file__}; fab report {FAB_CSV}"
    ),
    stacklevel=1,
)


Rows = list[dict[str, str]]


@cache
def sections() -> dict[str, Rows]:
    """The report as ``{section name: [row dicts]}``."""
    return fabcsv.sections(FAB_CSV)


@cache
def document() -> dict[str, str]:
    return {row["Field"]: row["Value"] for row in sections()["DOCUMENT"]}


@cache
def materials() -> dict[str, dict[str, str]]:
    """Material_ID / Copper_ID -> its declaring row."""
    out = {r["Material_ID"]: r for r in sections()["MATERIALS_DIELECTRIC"]}
    out.update({r["Copper_ID"]: r for r in sections()["MATERIALS_COPPER"]})
    return out


@cache
def n_copper() -> int:
    """Copper layers, counted from the STACKUP rows."""
    return sum(1 for row in sections()["STACKUP"] if row["Type"] == "Copper")


@cache
def fab_rules() -> dict[str, float]:
    """JITX attribute name -> value in mm, for rows that map to a JITX field."""
    return {
        r["JITX_attribute"]: float(r["Value_mm"])
        for r in sections()["FAB_RULES"]
        if r["JITX_attribute"]
    }


def capability(pattern: str) -> str:
    """The one FAB_RULES row with no JITX field whose Rule matches ``pattern``
    (case-insensitive), returned as written."""
    found = [
        row
        for row in sections()["FAB_RULES"]
        if not row["JITX_attribute"] and re.search(pattern, row["Rule"], re.IGNORECASE)
    ]
    if len(found) != 1:
        raise AssertionError(
            f"FAB_RULES: expected one capability row matching {pattern!r}, "
            f"found {[row['Rule'] for row in found]}"
        )
    return found[0]["Value_mm"]


def ratio(value: str) -> float:
    """``'8.0:1'`` -> 8.0."""
    return float(value.split(":")[0])


@cache
def board_outline() -> tuple[float, float, float]:
    """Width, height and corner radius in mm, from DOCUMENT ``Board size``,
    for the grader's wrapping board only."""
    row = next((r for r in sections()["DOCUMENT"] if r["Field"] == "Board size"), None)
    if row is None or not row["Value"].strip():
        raise AssertionError(
            f"{FAB_CSV}: DOCUMENT has no 'Board size' value, so there is no board "
            "to wrap the substrate in. The grader does not invent one."
        )
    if row["Unit"].strip() != "mm":
        raise AssertionError(
            f"DOCUMENT Board size is in {row['Unit']!r}; the grader reads mm only."
        )
    try:
        width, height = (float(part) for part in row["Value"].split(" x "))
    except ValueError as error:
        raise AssertionError(
            f"DOCUMENT Board size {row['Value']!r} is not 'W x H'."
        ) from error
    radius = re.search(r"([0-9.]+)\s*mm corner radius", row["Notes"])
    return width, height, float(radius.group(1)) if radius else 0.0


def _outline(width: float, height: float, radius: float) -> Shape:
    if radius > 0:
        return rectangle(width, height, radius=radius)
    return rectangle(width, height)


class _EmptyCircuit(Circuit):
    """No components: only the substrate is graded."""


class _GradingBoard(Board):
    """The report's board size, with ``signal_area`` inset by the substrate's
    own ``min_copper_edge_space``."""

    def __init__(
        self, width: float, height: float, radius: float, inset: float
    ) -> None:
        self.shape = _outline(width, height, radius)
        self.signal_area = _outline(
            width - 2 * inset, height - 2 * inset, max(radius - inset, 0.0)
        )


class _GradingDesign(Design):
    """The substrate under test on the report's board. Any design the
    candidate file defines is ignored."""

    def __init__(self, substrate: type[Substrate]) -> None:
        width, height, radius = board_outline()
        self.substrate = substrate()
        self.board = _GradingBoard(
            width, height, radius, self.substrate.constraints.min_copper_edge_space
        )
        self.circuit = _EmptyCircuit()


def grading_design() -> Design:
    """The grader's design. Requires an instantiation context."""
    return _GradingDesign(SUBSTRATE)


@cache
def translated() -> DesignV1:
    """The design as JITX translates it. Requires an instantiation context."""
    return package_design(grading_design()).v1


def layer_number(index: int, side: int) -> int:
    """Proto (index, side) -> 1-based layer number."""
    return index + 1 if side == _SIDE_TOP else n_copper() - index


def signed_to_layer(index: int) -> int:
    """A signed conductor index as written in a substrate -> layer number."""
    return (index if index >= 0 else index + n_copper()) + 1


def stackup_span_mm(
    from_layer: str, to_layer: str, *, include_end_foils: bool
) -> float:
    """Thickness between two copper layers, summed from the STACKUP rows.

    ``include_end_foils`` picks between the report's two depth conventions:
    a mechanical drill's depth is the full drilled depth including the copper
    at both ends, a laser microvia's is the ablated dielectric alone.
    """
    rows = sections()["STACKUP"]
    position = {row["Layer"]: index for index, row in enumerate(rows) if row["Layer"]}
    first, last = sorted((position[from_layer], position[to_layer]))
    span = rows[first : last + 1] if include_end_foils else rows[first + 1 : last]
    return sum(float(row["Thickness_mm"]) for row in span)


@cache
def csv_reference_planes() -> dict[int, tuple[int, ...]]:
    """Routing layer number -> its plane numbers, per IMPEDANCE ``Ref_layers``.

    The column is written two ways. A group may name its routing layer inline
    (``L2 for L1``); otherwise it is positional against the row's own
    ``Layers`` column, so ``L2+L4; L11+L9`` pairs with ``L3;L10``.
    """
    out: dict[int, tuple[int, ...]] = {}
    for row in sections()["IMPEDANCE"]:
        if not row["Ref_layers"]:
            continue
        layers = [name.strip() for name in row["Layers"].split(";")]
        groups = row["Ref_layers"].split(";")
        if len(groups) != len(layers):
            raise AssertionError(
                f"IMPEDANCE {row['Structure_ID']} {row['Geometry']}: "
                f"{len(groups)} Ref_layers groups for {len(layers)} Layers"
            )
        for index, group in enumerate(groups):
            planes, separator, target = group.strip().partition(" for ")
            if not separator:
                target = layers[index]
            key = fabcsv.layer_number(target)
            numbers = tuple(fabcsv.layer_number(plane) for plane in planes.split("+"))
            if out.setdefault(key, numbers) != numbers:
                raise ValueError(
                    f"L{key} is given two different reference sets by the report: "
                    f"{out[key]} and {numbers}"
                )
    return out


def _drill_enum_number(via: ViaProto, row: dict[str, str]) -> int:
    """The translated ``type`` number for a VIAS row's ``Drill``, resolved
    through the descriptor rather than hard-coded."""
    drill = via.DESCRIPTOR.fields_by_name["type"].enum_type
    assert drill is not None
    expected = "LASER_DRILL" if row["Drill"] == "Laser" else "MECHANICAL_DRILL"
    return drill.values_by_name[expected].number


def via_start(via: ViaProto) -> int:
    return layer_number(via.start.index, via.start.side)


def via_stop(via: ViaProto) -> int:
    return layer_number(via.stop.index, via.stop.side)


def row_span(row: dict[str, str]) -> tuple[int, int]:
    return fabcsv.layer_number(row["From_layer"]), fabcsv.layer_number(row["To_layer"])


def via_matches_row(via: ViaProto, row: dict[str, str]) -> bool:
    """Same drill type and the same pair of end layers, in either order.

    Direction is left to :meth:`TestVias.test_geometry_matches_csv`, so a via
    declared in the wrong drill direction is reported there as a wrong span
    rather than here as a missing via.
    """
    span = {via_start(via), via_stop(via)}
    return via.type == _drill_enum_number(via, row) and span == set(row_span(row))


def registered_vias() -> list[ViaProto]:
    """The vias JITX registered on the board, each once.

    The board lists via ids, and a via reachable from the substrate by two
    routes is listed twice; the design's own via table holds each once.
    """
    on_board = set(translated().boards[0].vias)
    return [via for via in translated().vias if via.id in on_board]


def laser_drill_number(via: ViaProto) -> int:
    drill = via.DESCRIPTOR.fields_by_name["type"].enum_type
    assert drill is not None
    return drill.values_by_name["LASER_DRILL"].number


def via_for(row: dict[str, str]) -> ViaProto:
    """The one registered via that implements a VIAS row."""
    found = [via for via in registered_vias() if via_matches_row(via, row)]
    if len(found) != 1:
        names = ", ".join(via.name for via in found) or "none"
        raise AssertionError(
            f"VIAS {row['Via_ID']} ({row['Drill']}, {row['From_layer']} to "
            f"{row['To_layer']}): expected exactly one via with that drill type and "
            f"span, found {names}"
        )
    return found[0]


def impedance_rows(structure_id: str) -> Rows:
    return [r for r in sections()["IMPEDANCE"] if r["Structure_ID"] == structure_id]


@cache
def uncoupled_ids() -> dict[str, str]:
    """Differential Structure_ID -> the ``<id>-UNC`` row for its uncoupled region."""
    kinds = {r["Structure_ID"]: r["Type"] for r in sections()["IMPEDANCE"]}
    return {
        base: structure_id
        for structure_id in kinds
        if kinds.get(base := structure_id.removesuffix("-UNC")) == "Differential"
        and base != structure_id
    }


@cache
def controlled_ids() -> tuple[str, ...]:
    """Every controlled Structure_ID with a target, less the uncoupled regions,
    which live inside their differential structure rather than on the substrate."""
    nested = set(uncoupled_ids().values())
    return tuple(
        dict.fromkeys(
            r["Structure_ID"]
            for r in sections()["IMPEDANCE"]
            if r["Controlled"] == "Yes"
            and r["Target_Z_ohm"].strip()
            and r["Structure_ID"] not in nested
        )
    )


@cache
def uncontrolled_rows() -> Rows:
    """IMPEDANCE rows the report documents but does not control."""
    return [r for r in sections()["IMPEDANCE"] if r["Controlled"] != "Yes"]


def _lookup_failed(structure_id: str, kind: str, error: ValueError) -> AssertionError:
    target = impedance_rows(structure_id)[0]["Target_Z_ohm"]
    return AssertionError(
        f"IMPEDANCE {structure_id}: the substrate has no {kind} routing structure "
        f"at {target} ohm ({error})"
    )


def diff_structure_for(
    substrate: Substrate, structure_id: str
) -> DifferentialRoutingStructure:
    """Find a differential IMPEDANCE structure on the substrate by its target."""
    target = float(impedance_rows(structure_id)[0]["Target_Z_ohm"])
    try:
        return substrate.differential_routing_structure(target * ohm)
    except ValueError as error:
        raise _lookup_failed(structure_id, "differential", error) from error


AnyStructure = RoutingStructure | DifferentialRoutingStructure
AnyLayer = RoutingStructure.Layer | DifferentialRoutingStructure.Layer


def structure_for(substrate: Substrate, structure_id: str) -> AnyStructure:
    """Find an IMPEDANCE structure on the substrate by its target impedance."""
    if impedance_rows(structure_id)[0]["Type"] == "Differential":
        return diff_structure_for(substrate, structure_id)
    target = float(impedance_rows(structure_id)[0]["Target_Z_ohm"])
    try:
        return substrate.routing_structure(target * ohm)
    except ValueError as error:
        raise _lookup_failed(structure_id, "single-ended", error) from error


def layer_at(structure: AnyStructure, number: int) -> AnyLayer:
    """The structure's entry for layer ``L<number>``, however it is indexed."""
    for index, layer in structure.layers.items():
        if signed_to_layer(index) == number:
            return layer
    raise AssertionError(f"{structure.name!r} declares nothing on L{number}")


def _distinct(structures: list[AnyStructure]) -> list[AnyStructure]:
    out: list[AnyStructure] = []
    for structure in structures:
        if not any(structure is seen for seen in out):
            out.append(structure)
    return out


def uncoupled_regions(substrate: Substrate) -> list[RoutingStructure]:
    """The uncoupled region of every differential structure on the substrate."""
    return [
        d.uncoupled_region
        for d in decompose(substrate, DifferentialRoutingStructure)
        if d.uncoupled_region is not None
    ]


def single_ended_structures(substrate: Substrate) -> list[AnyStructure]:
    """Distinct single-ended structures declared on the substrate itself.

    An uncoupled region that is also held as an attribute of its own counts:
    it is then a standalone structure that ``routing_structure()`` returns,
    where the report means it to be part of its pair only.
    """
    return _distinct(list(decompose(substrate, RoutingStructure)))


def top_level_structures(substrate: Substrate) -> list[AnyStructure]:
    """Distinct structures declared on the substrate, single-ended and
    differential, not counting the uncoupled regions inside the pairs."""
    return _distinct(
        [
            *single_ended_structures(substrate),
            *decompose(substrate, DifferentialRoutingStructure),
        ]
    )


def controlled_lookups(substrate: Substrate) -> list[tuple[str, AnyStructure]]:
    """Each controlled Structure_ID with the structure its impedance finds;
    an ID that finds none is left out."""
    named: list[tuple[str, AnyStructure]] = []
    for structure_id in controlled_ids():
        try:
            named.append((structure_id, structure_for(substrate, structure_id)))
        except AssertionError:
            pass
    return named


def neck_rows(structure_id: str) -> Rows:
    """The IMPEDANCE rows of a target that quote a neck width."""
    return [
        row
        for row in impedance_rows(structure_id)
        if row.get("Neck_width_mm", "").strip()
    ]


@cache
def neck_regions() -> tuple[str, ...]:
    """Each controlled Structure_ID with a row that quotes a neck region. A
    neck region is modelled as a routing structure of its own, beside the
    target's main structure."""
    return tuple(sid for sid in controlled_ids() if neck_rows(sid))


def neck_label(structure_id: str) -> str:
    """Subtest ``structure=`` value for a neck region's structure."""
    return f"{structure_id} neck"


def neck_mismatches(structure: AnyStructure, structure_id: str) -> list[str]:
    """How ``structure`` differs from the neck region of ``structure_id``:
    its kind, its layers, then each layer's neck width, pair gap and
    clearance. Empty when it carries that neck region."""
    rows = neck_rows(structure_id)
    differential = rows[0]["Type"] == "Differential"
    if isinstance(structure, DifferentialRoutingStructure) != differential:
        return ["not differential" if differential else "differential"]
    expected = {
        fabcsv.layer_number(name): row
        for row in rows
        for name in row["Layers"].split(";")
    }
    covered = {
        signed_to_layer(index): layer for index, layer in structure.layers.items()
    }
    if set(covered) != set(expected):
        return [f"layers {sorted(covered)}, not {sorted(expected)}"]
    out: list[str] = []
    for number, row in sorted(expected.items()):
        layer = covered[number]
        checks = [
            ("width", layer.trace_width, row["Neck_width_mm"]),
            ("clearance", layer.clearance or 0.0, row.get("Neck_clearance_mm", "")),
            (
                "pair gap",
                getattr(layer, "pair_spacing", None) or 0.0,
                row.get("Neck_gap_mm", ""),
            ),
        ]
        out += [
            f"L{number} {what} {got:g}, not {cell}"
            for what, got, cell in checks
            if cell.strip() and round(got - float(cell), 6) != 0
        ]
    return out


def neck_lookups(substrate: Substrate) -> list[tuple[str, AnyStructure]]:
    """Each neck region with the structure that carries it: in report order,
    the first declared structure that no controlled target's impedance finds,
    that no earlier region took, and that carries the region's neck geometry.
    A region with none is left out."""
    taken = [structure for _, structure in controlled_lookups(substrate)]
    named: list[tuple[str, AnyStructure]] = []
    for structure_id in neck_regions():
        found = next(
            (
                structure
                for structure in top_level_structures(substrate)
                if not any(structure is seen for seen in taken)
                and not neck_mismatches(structure, structure_id)
            ),
            None,
        )
        if found is not None:
            taken.append(found)
            named.append((structure_id, found))
    return named


UNMATCHED = "(no IMPEDANCE row)"
"""Subtest ``structure=`` value for a structure no IMPEDANCE row finds."""


def all_structures(substrate: Substrate) -> list[tuple[str, AnyStructure]]:
    """Every distinct routing structure on the substrate, uncoupled regions
    included, each with the IMPEDANCE Structure_ID whose impedance finds it."""
    found = _distinct([*top_level_structures(substrate), *uncoupled_regions(substrate)])
    named = controlled_lookups(substrate)
    named += [(neck_label(sid), s) for sid, s in neck_lookups(substrate)]
    for structure_id, uncoupled_id in uncoupled_ids().items():
        try:
            region = diff_structure_for(substrate, structure_id).uncoupled_region
        except AssertionError:
            continue
        if region is not None:
            named.append((uncoupled_id, region))

    def label(structure: AnyStructure) -> str:
        return next((sid for sid, s in named if s is structure), UNMATCHED)

    return [(label(structure), structure) for structure in found]


def reference_planes(layer: AnyLayer) -> dict[int, float]:
    """Plane layer number -> desired width, as carried by ``.reference()``."""
    return {
        signed_to_layer(ref.layer): ref.desired_width
        for ref in decompose(layer, _RefLayer)
    }


class TestStackup(TestCase):
    def test_layer_count_and_order(self) -> None:
        layers = list(decompose(candidate().stackup, Material))
        rows = sections()["STACKUP"]
        self.assertTrue(rows, "the report has no STACKUP rows")
        self.assertEqual(len(layers), len(rows), "one stackup entry per CSV row")

        for row, layer in zip(rows, layers, strict=True):
            with self.subTest(
                seq=row["Seq"],
                layer=row["Layer"] or row["Function"],
                candidate=layer.name,
            ):
                expect_conductor = row["Type"] == "Copper"
                self.assertEqual(isinstance(layer, Conductor), expect_conductor)
                self.assertEqual(isinstance(layer, Dielectric), not expect_conductor)
                self.assertAlmostEqual(
                    layer.thickness or 0.0, float(row["Thickness_mm"]), places=6
                )

    def test_copper_layer_names_carry_the_layer_id(self) -> None:
        """Each conductor's name contains its STACKUP layer id anywhere, with no
        letter or digit just before it and no digit just after it, so
        "Top (L1)" and "L1Signal" name L1 while "TopL1" and "L12" do not. The
        rest of the name (a function word or anything else) is not checked
        here."""
        conductors = list(decompose(candidate().stackup, Conductor))
        self.assertEqual(int(document()["Layer count"]), n_copper())
        self.assertEqual(len(conductors), n_copper())

        copper_rows = [r for r in sections()["STACKUP"] if r["Type"] == "Copper"]
        for row, layer in zip(copper_rows, conductors, strict=True):
            with self.subTest(layer=row["Layer"]):
                # "L3-Signal", "Top (L1)", "GND L2", "L3_GND": the CSV layer id
                # is in the name, so the UI cross-section reads in the report's
                # own terms. No letter or digit may come before the id and no
                # digit after it, so "L10-Signal" and "L12" do not name L1.
                self.assertRegex(
                    layer.name or "",
                    rf"(?<![A-Za-z0-9]){re.escape(row['Layer'])}(?!\d)",
                    f"{layer.name!r} should contain {row['Layer']!r}, with no "
                    "letter or digit before it and no digit after it",
                )

    def test_thickness_totals_match_document(self) -> None:
        layers = list(decompose(candidate().stackup, Material))
        overall = sum(layer.thickness or 0.0 for layer in layers)
        mask = sum(
            layer.thickness or 0.0
            for layer, row in zip(layers, sections()["STACKUP"], strict=True)
            if row["Type"] == "Soldermask"
        )
        # Compare exactly rather than with a loose tolerance: a tolerance would
        # hide the transcription slip this test exists to catch.
        self.assertAlmostEqual(
            overall,
            float(document()["Overall thickness"]),
            places=6,
            msg="DOCUMENT Overall thickness against the sum of the stackup",
        )
        self.assertAlmostEqual(
            overall - mask,
            float(document()["Finished thickness"]),
            places=6,
            msg="DOCUMENT Finished thickness against the stackup less soldermask",
        )

    def test_material_properties_match_csv(self) -> None:
        """Dk, Df and roughness per layer, including the unit conversions."""
        proto_layers = translated().stackups[0].layers
        by_id = {m.id: m for m in translated().materials}
        rows = sections()["STACKUP"]
        self.assertEqual(len(proto_layers), len(rows))

        conductors = iter(decompose(candidate().stackup, Conductor))
        for row, proto in zip(rows, proto_layers, strict=True):
            material = by_id[proto.material]
            declared = materials()[row["Material_ID"]]
            with self.subTest(
                seq=row["Seq"], material=row["Material_ID"], candidate=proto.name
            ):
                if row["Type"] == "Copper":
                    conductor = next(conductors, None)
                    if conductor is None:
                        self.fail("fewer Conductor entries than STACKUP copper rows")
                    self.assert_roughness(conductor, material.roughness, row)
                    # oz is nominal; the electrical model uses finished thickness.
                    self.assertAlmostEqual(
                        proto.thickness,
                        float(declared["Finished_thickness_mm"]),
                        places=6,
                        msg=f"MATERIALS_COPPER {row['Material_ID']} "
                        "Finished_thickness_mm",
                    )
                else:
                    self.assertAlmostEqual(
                        material.dielectric_coefficient,
                        float(row["Dk"]),
                        places=6,
                        msg=f"STACKUP seq {row['Seq']} Dk",
                    )
                    self.assertAlmostEqual(
                        material.loss_tangent,
                        float(row["Df"]),
                        places=6,
                        msg=f"STACKUP seq {row['Seq']} Df",
                    )

    def assert_roughness(
        self, conductor: Conductor, translated_roughness: float, row: dict[str, str]
    ) -> None:
        """Copper roughness, on the convention SKILL.md sets.

        The class docstring, the durable record, must carry the matte and drum
        Rz in um as the report writes them, whether or not the ``roughness``
        scalar is set: the scalar holds one side only. Where the scalar is set,
        it is matte Rz in mm, and it reaches the translated material.
        """
        declared = materials()[row["Material_ID"]]
        where = f"MATERIALS_COPPER {row['Material_ID']}"
        if conductor.roughness is not None:
            # Rz is quoted in um on the matte side; the scalar is read as mm.
            expected = float(declared["Rz_matte_um"]) / 1000.0
            self.assertAlmostEqual(
                conductor.roughness, expected, places=6, msg=f"{where} Rz_matte_um"
            )
            self.assertAlmostEqual(
                translated_roughness, expected, places=6, msg=f"{where} Rz_matte_um"
            )
        # `decompose` hands back proxies; `typeof` is the class behind one.
        klass = typeof(conductor)
        # The candidate's own classes along the MRO, so Rz stated once on a
        # foil base class counts for every class built on it.
        docs = [
            vars(cls).get("__doc__") or ""
            for cls in klass.__mro__
            if cls.__module__.split(".")[0] not in ("jitx", "builtins")
        ]
        # Numbers standing on their own: the 5 in a product code like "WF-R5"
        # is not a roughness.
        numbers = re.findall(r"(?<![\w.])\d+(?:\.\d+)?", "\n".join(docs))
        stated = {float(number) for number in numbers}
        for column in ("Rz_matte_um", "Rz_drum_um"):
            self.assertIn(
                float(declared[column]),
                stated,
                f"{where} {column} {declared[column]} um: the docstring of "
                f"{klass.__name__}, or of a class it is built on, must state this "
                "value, since the roughness scalar holds at most the matte side",
            )

    def test_distinct_dielectrics_are_not_collapsed(self) -> None:
        """Every declared (Dk, Df) pair survives into the design, and there are
        exactly as many distinct ones as the report declares, so no two
        material rows were merged and none was invented."""
        declared = sections()["MATERIALS_DIELECTRIC"]
        material_type = translated().materials[0].DESCRIPTOR.fields_by_name["type"]
        assert material_type.enum_type is not None
        dielectric = material_type.enum_type.values_by_name["DIELECTRIC"].number
        built = {
            (round(m.dielectric_coefficient, 6), round(m.loss_tangent, 6))
            for m in translated().materials
            if m.type == dielectric
        }
        wanted = {
            (round(float(r["Dk"]), 6), round(float(r["Df"]), 6)) for r in declared
        }
        for row in declared:
            with self.subTest(material=row["Material_ID"]):
                self.assertIn(
                    (round(float(row["Dk"]), 6), round(float(row["Df"]), 6)), built
                )
        self.assertEqual(built, wanted)

    def test_material_names_carry_the_csv_product(self) -> None:
        """``material_name`` reaches the translated design; a docstring does not.
        Each dielectric's name carries the Product of its MATERIALS_DIELECTRIC row."""
        products = {
            row["Material_ID"]: row["Product"]
            for row in sections()["MATERIALS_DIELECTRIC"]
        }
        rows = [row for row in sections()["STACKUP"] if row["Type"] != "Copper"]
        layers = list(decompose(candidate().stackup, Dielectric))
        self.assertEqual(len(layers), len(rows), "dielectric entries against rows")
        for row, layer in zip(rows, layers, strict=True):
            product = products[row["Material_ID"]]
            name = layer.material_name or ""
            with self.subTest(seq=row["Seq"], material=row["Material_ID"]):
                self.assertIn(
                    product.casefold(),
                    name.casefold(),
                    f"STACKUP seq {row['Seq']}: material_name {name!r} does not "
                    f"carry the Product {product!r}",
                )

    def test_mirrored_rows_are_mirrored(self) -> None:
        """Where the report's STACKUP is mirror-symmetric row for row (same
        material and thickness), the translated layers are too: the same
        material type, thickness, Dk, Df and roughness."""
        rows = sections()["STACKUP"]
        layers = translated().stackups[0].layers
        self.assertEqual(len(layers), len(rows))
        by_id = {m.id: m for m in translated().materials}

        def signature(index: int) -> tuple[int, float, float, float, float]:
            layer = layers[index]
            material = by_id[layer.material]
            return (
                material.type,
                round(layer.thickness, 6),
                round(material.dielectric_coefficient, 6),
                round(material.loss_tangent, 6),
                round(material.roughness, 6),
            )

        def source(index: int) -> tuple[str, str]:
            return rows[index]["Material_ID"], rows[index]["Thickness_mm"]

        for index in range(len(rows) // 2):
            mirror = len(rows) - 1 - index
            if source(index) != source(mirror):
                continue
            with self.subTest(seq=rows[index]["Seq"], mirror=rows[mirror]["Seq"]):
                self.assertEqual(signature(index), signature(mirror))


class TestVias(TestCase):
    def vias_by_row(self) -> list[tuple[dict[str, str], ViaProto]]:
        """Each VIAS row with the via that implements it. A row with no single
        match is recorded as a failed subtest and left out."""
        out: list[tuple[dict[str, str], ViaProto]] = []
        for row in sections()["VIAS"]:
            try:
                out.append((row, via_for(row)))
            except AssertionError as error:
                with self.subTest(via=row["Via_ID"]):
                    self.fail(str(error))
        return out

    def test_side_enum_matches_descriptor(self) -> None:
        """`layer_number` reads `_SIDE_TOP` as an integer; check that holds."""
        self.assertTrue(translated().vias, "the design registers no vias")
        start = translated().vias[0].start
        side = start.DESCRIPTOR.fields_by_name["side"].enum_type
        assert side is not None
        self.assertEqual(side.values_by_name["TOP"].number, _SIDE_TOP)
        self.assertNotEqual(side.values_by_name["BOTTOM"].number, _SIDE_TOP)

    def test_inventory_is_exactly_the_csv_via_table(self) -> None:
        rows = sections()["VIAS"]
        self.assertTrue(rows, "the report has no VIAS rows")
        for row in rows:
            with self.subTest(via=row["Via_ID"]):
                via_for(row)
        unmatched = [
            via.name
            for via in registered_vias()
            if not any(via_matches_row(via, row) for row in rows)
        ]
        self.assertEqual(
            unmatched, [], "vias whose drill type and span match no VIAS row"
        )
        # Every Via on a substrate is auto-registered on the board, so the
        # count JITX registered must match the report exactly.
        on_board = set(translated().boards[0].vias)
        self.assertEqual(len(on_board), len(rows), "distinct vias on the board")
        self.assertEqual(
            on_board,
            {via.id for via in translated().vias},
            "every via in the design is on the board, and only those",
        )

    def test_geometry_matches_csv(self) -> None:
        tented = translated().vias[0].DESCRIPTOR.fields_by_name["tented"].enum_type
        assert tented is not None
        for row, via in self.vias_by_row():
            with self.subTest(via=row["Via_ID"], candidate=via.name):
                self.assertAlmostEqual(
                    via.hole_diameter,
                    float(row["Finished_hole_mm"]),
                    places=6,
                    msg=f"VIAS {row['Via_ID']} Finished_hole_mm, {via.name} hole",
                )
                self.assertAlmostEqual(
                    via.diameter,
                    float(row["Pad_mm"]),
                    places=6,
                    msg=f"VIAS {row['Via_ID']} Pad_mm, {via.name} pad",
                )
                self.assertEqual(via.type, _drill_enum_number(via, row))
                self.assertEqual(
                    via.filled,
                    row["Fill"] not in UNFILLED,
                    f"VIAS {row['Via_ID']} Fill {row['Fill']!r}",
                )
                self.assertEqual(
                    via.tented,
                    tented.values_by_name[TENT_MODES[row["Tented"]]].number,
                    f"VIAS {row['Via_ID']} Tented {row['Tented']!r}",
                )
                self.assertEqual(
                    via.via_in_pad,
                    row["Via_in_pad"] == "Yes",
                    f"VIAS {row['Via_ID']} Via_in_pad",
                )
                # Drill direction: the via starts on the layer it is drilled from.
                self.assertEqual(
                    (via_start(via), via_stop(via)),
                    row_span(row),
                    f"VIAS {row['Via_ID']} From_layer/To_layer, {via.name} start/stop",
                )

    def test_capped_vias_are_filled(self) -> None:
        """Capping has no JITX field, but a cap needs a fill under it, so a row
        the report caps must be a filled via."""
        for row, via in self.vias_by_row():
            if row["Capped"] != "Yes":
                continue
            with self.subTest(via=row["Via_ID"], candidate=via.name):
                self.assertNotIn(row["Fill"], UNFILLED)
                self.assertTrue(via.filled)

    def test_depth_matches_the_stackup_on_its_own_convention(self) -> None:
        """``Depth_mm`` against the depth each via's layer span implies:
        dielectric-only for laser microvias, full drilled depth for mechanical
        drills. Checks the report's own consistency, which the aspect-ratio
        test below relies on."""
        for row in sections()["VIAS"]:
            laser = row["Drill"] == "Laser"
            implied = stackup_span_mm(
                row["From_layer"], row["To_layer"], include_end_foils=not laser
            )
            with self.subTest(via=row["Via_ID"]):
                self.assertAlmostEqual(float(row["Depth_mm"]), implied, places=6)

    def test_annular_ring_and_aspect_ratio_within_capability(self) -> None:
        """Checks the built via geometry, not just the CSV's own cells. Depth
        has no JITX field, so it comes from the report; hole and pad come off
        the translated vias. Limits are inclusive."""
        min_ring = fab_rules()["min_annular_ring"]
        min_laser_drill = fab_rules()["min_drill_diameter"]
        min_mech_drill = float(capability(r"mechanical drill diameter"))
        max_laser_ar = ratio(capability(r"laser.*aspect ratio"))
        max_mech_ar = ratio(capability(r"mechanical.*aspect ratio"))
        self.assertGreater(
            min_mech_drill, min_laser_drill, "min_drill_diameter is the laser minimum"
        )
        for row, via in self.vias_by_row():
            laser = row["Drill"] == "Laser"
            aspect = float(row["Depth_mm"]) / via.hole_diameter
            with self.subTest(via=row["Via_ID"], candidate=via.name):
                self.assertGreaterEqual(
                    round((via.diameter - via.hole_diameter) / 2, 6), min_ring
                )
                self.assertGreaterEqual(
                    via.hole_diameter, min_laser_drill if laser else min_mech_drill
                )
                self.assertLessEqual(
                    round(aspect, 6), max_laser_ar if laser else max_mech_ar
                )

    def test_laser_vias_are_exactly_the_laser_rows(self) -> None:
        """As many laser vias as Laser rows, each drilled from the side its
        row's From_layer names, bottom-side vias included."""
        laser = [v for v in registered_vias() if v.type == laser_drill_number(v)]
        rows = [row for row in sections()["VIAS"] if row["Drill"] == "Laser"]
        self.assertEqual(len(laser), len(rows), "laser vias against Laser rows")
        self.assertEqual(
            sorted((via_start(via), via_stop(via)) for via in laser),
            sorted(row_span(row) for row in rows),
            "laser via (start, stop) pairs against VIAS (From_layer, To_layer)",
        )

    def test_no_si_models_declared(self) -> None:
        """A fab report has no electrical models; none may be invented here."""
        for via in registered_vias():
            with self.subTest(candidate=via.name):
                self.assertEqual(
                    len(via.structure_models),
                    0,
                    f"{via.name} carries via models the report does not give",
                )


class TestFabRules(TestCase):
    def test_all_required_constraints_present_and_match_csv(self) -> None:
        expected = fab_rules()
        # Every constraint JITX declares must be covered by the report.
        required = {
            name
            for name in FabricationConstraints.__annotations__
            if not name.startswith("_")
        }
        self.assertEqual(set(expected), required)

        constraints = candidate().constraints
        for attribute, value in expected.items():
            with self.subTest(
                constraint=attribute, candidate=type(constraints).__name__
            ):
                self.assertAlmostEqual(
                    getattr(constraints, attribute),
                    value,
                    places=6,
                    msg=f"FAB_RULES {attribute}",
                )

    def test_translated_rules_carry_every_constraint(self) -> None:
        self.assertEqual(len(translated().ruless[0].clearances), len(fab_rules()))

    def test_engine_enforced_rules_do_not_clamp_the_geometry(self) -> None:
        """min_copper_* override trace width and clearance, so nothing the
        report quotes may sit below them, the neck regions included."""
        min_width = fab_rules()["min_copper_width"]
        min_space = fab_rules()["min_copper_copper_space"]
        for row in sections()["IMPEDANCE"]:
            widths = [row["Line_width_mm"], row.get("Neck_width_mm", "")]
            spaces = [
                row["Pair_gap_mm"],
                row.get("Neck_gap_mm", ""),
                row["Clearance_mm"],
                row.get("Neck_clearance_mm", ""),
            ]
            with self.subTest(structure=row["Structure_ID"], geom=row["Geometry"]):
                for value in widths:
                    if value.strip():
                        self.assertGreaterEqual(float(value), min_width)
                for value in spaces:
                    if value.strip():
                        self.assertGreaterEqual(float(value), min_space)


class TestRoutingStructures(TestCase):
    # Structures are found by impedance (`structure_for`) and by enumerating
    # the substrate (`all_structures`), never by attribute name. Subtests key
    # `structure=` on the IMPEDANCE Structure_ID and `candidate=` on the
    # structure's own name.

    def structures_by_id(self, substrate: Substrate) -> list[tuple[str, AnyStructure]]:
        """Each controlled Structure_ID with the structure its impedance finds.
        An ID that finds none is recorded as a failed subtest and left out."""
        out: list[tuple[str, AnyStructure]] = []
        for structure_id in controlled_ids():
            try:
                out.append((structure_id, structure_for(substrate, structure_id)))
            except AssertionError as error:
                with self.subTest(structure=structure_id):
                    self.fail(str(error))
        return out

    def assert_ref_layers_covered(self, routed: set[int]) -> None:
        """The structures route on exactly the layers ``Ref_layers`` names, so
        a substrate with no structures cannot pass a per-layer loop vacuously."""
        self.assertEqual(
            routed,
            set(csv_reference_planes()),
            "layers the structures route on, against layers IMPEDANCE Ref_layers names",
        )

    def assert_layer_matches_row(self, layer: AnyLayer, row: dict[str, str]) -> None:
        """One IMPEDANCE row's geometry and electrical columns on one layer."""
        where = f"IMPEDANCE {row['Structure_ID']} {row['Geometry']}"
        self.assertAlmostEqual(
            layer.trace_width,
            float(row["Line_width_mm"]),
            places=6,
            msg=f"{where} Line_width_mm",
        )
        self.assertAlmostEqual(
            layer.clearance or 0.0,
            float(row["Clearance_mm"]),
            places=6,
            msg=f"{where} Clearance_mm",
        )
        self.assertAlmostEqual(
            layer.insertion_loss,
            float(row["Loss_dB_per_mm"]),
            places=6,
            msg=f"{where} Loss_dB_per_mm",
        )
        # eps_eff comes from the report, not from Dk. Relative tolerance, so any
        # correct formula for c passes while a change in the fourth decimal of
        # Eps_eff still fails.
        expected = phase_velocity(float(row["Eps_eff"]))
        self.assertAlmostEqual(
            layer.velocity,
            expected,
            delta=VELOCITY_RTOL * expected,
            msg=f"{where} Eps_eff, as phase velocity",
        )

    def test_lookup_by_impedance(self) -> None:
        substrate = candidate()
        declared = [
            *decompose(substrate, RoutingStructure),
            *decompose(substrate, DifferentialRoutingStructure),
        ]
        self.assertTrue(controlled_ids(), "IMPEDANCE has no controlled target")
        for structure_id in controlled_ids():
            target = float(impedance_rows(structure_id)[0]["Target_Z_ohm"])
            with self.subTest(structure=structure_id):
                found = structure_for(substrate, structure_id)
                self.assertTrue(
                    any(found is structure for structure in declared),
                    f"IMPEDANCE {structure_id}: lookup returned {found.name!r}, "
                    "which is not a routing structure declared on the substrate",
                )
                self.assertAlmostEqual(
                    ohm.m_from(found.impedance),
                    target,
                    places=6,
                    msg=f"IMPEDANCE {structure_id} Target_Z_ohm",
                )

    def test_every_declared_structure_has_a_controlled_target(self) -> None:
        """A structure no controlled IMPEDANCE row finds by its impedance, and
        that carries no neck region, is one the report does not ask for, such
        as an extra pair or a hoisted uncoupled region."""
        substrate = candidate()
        named = controlled_lookups(substrate)
        named += [(neck_label(sid), s) for sid, s in neck_lookups(substrate)]
        for structure in top_level_structures(substrate):
            label = next((sid for sid, s in named if s is structure), UNMATCHED)
            with self.subTest(structure=label, candidate=structure.name):
                if label == UNMATCHED:
                    self.fail(
                        f"{structure.name!r} at {ohm.m_from(structure.impedance)} "
                        "ohm is not the structure any controlled IMPEDANCE target "
                        "finds, and it carries no neck region"
                    )

    def test_layer_coverage(self) -> None:
        """Every controlled structure covers exactly the layers its rows list."""
        for structure_id, structure in self.structures_by_id(candidate()):
            with self.subTest(structure=structure_id, candidate=structure.name):
                covered = {signed_to_layer(i) for i in structure.layers}
                expected: set[int] = set()
                for row in impedance_rows(structure_id):
                    expected |= {
                        fabcsv.layer_number(name) for name in row["Layers"].split(";")
                    }
                self.assertEqual(
                    covered,
                    expected,
                    f"IMPEDANCE {structure_id} Layers, {structure.name!r} layers",
                )

    def test_geometry_matches_csv(self) -> None:
        for structure_id, structure in self.structures_by_id(candidate()):
            for row in impedance_rows(structure_id):
                for name in row["Layers"].split(";"):
                    with self.subTest(
                        structure=structure_id, candidate=structure.name, layer=name
                    ):
                        layer = layer_at(structure, fabcsv.layer_number(name))
                        if row["Pair_gap_mm"].strip():
                            if not isinstance(
                                layer, DifferentialRoutingStructure.Layer
                            ):
                                self.fail(
                                    f"IMPEDANCE {structure_id} states a Pair_gap_mm, "
                                    f"but {structure.name!r} is not differential"
                                )
                            self.assertAlmostEqual(
                                layer.pair_spacing,
                                float(row["Pair_gap_mm"]),
                                places=6,
                                msg=f"IMPEDANCE {structure_id} {row['Geometry']} "
                                "Pair_gap_mm",
                            )
                        self.assert_layer_matches_row(layer, row)

    def test_each_geometry_has_its_own_entry(self) -> None:
        """Where the report quotes one target on several geometries, each
        geometry's layers carry that geometry's own width and velocity."""
        for structure_id, structure in self.structures_by_id(candidate()):
            rows = impedance_rows(structure_id)
            firsts = [fabcsv.layer_number(r["Layers"].split(";")[0]) for r in rows]
            pairs = [(i, j) for i in range(len(rows)) for j in range(i)]
            for i, j in pairs:
                if rows[i]["Line_width_mm"] == rows[j]["Line_width_mm"]:
                    continue
                with self.subTest(
                    structure=structure_id,
                    geometries=f"{rows[j]['Geometry']} / {rows[i]['Geometry']}",
                ):
                    one = layer_at(structure, firsts[j])
                    two = layer_at(structure, firsts[i])
                    self.assertNotAlmostEqual(one.trace_width, two.trace_width)
                    if rows[i]["Eps_eff"] != rows[j]["Eps_eff"]:
                        self.assertNotAlmostEqual(one.velocity, two.velocity, places=0)

    def test_reference_planes_match_csv_ref_layers(self) -> None:
        """Each structure's planes against the IMPEDANCE ``Ref_layers`` column.
        Order within a layer's planes carries no meaning, so it is not compared."""
        named = csv_reference_planes()
        routed: set[int] = set()
        for structure_id, structure in all_structures(candidate()):
            for index, layer in structure.layers.items():
                number = signed_to_layer(index)
                routed.add(number)
                with self.subTest(
                    structure=structure_id, candidate=structure.name, layer=f"L{number}"
                ):
                    self.assertEqual(
                        sorted(reference_planes(layer)),
                        sorted(named.get(number, ())),
                        f"IMPEDANCE Ref_layers for L{number}",
                    )
        self.assert_ref_layers_covered(routed)

    def test_reference_planes_are_planes_on_the_right_sides(self) -> None:
        """Each carried plane is a STACKUP Plane layer; an outer layer has one
        plane, beneath it, and an inner layer one on each side."""
        plane_layers = {
            fabcsv.layer_number(r["Layer"])
            for r in sections()["STACKUP"]
            if r["Type"] == "Copper" and r["Function"].startswith("Plane")
        }
        routed: set[int] = set()
        for structure_id, structure in all_structures(candidate()):
            for index, layer in structure.layers.items():
                number = signed_to_layer(index)
                routed.add(number)
                planes = sorted(reference_planes(layer))
                with self.subTest(
                    structure=structure_id, candidate=structure.name, layer=f"L{number}"
                ):
                    for plane in planes:
                        self.assertIn(
                            plane, plane_layers, f"L{plane} is not a STACKUP Plane"
                        )
                    sides = {plane > number for plane in planes}
                    if number in (1, n_copper()):
                        self.assertEqual(len(planes), 1)
                    else:
                        self.assertEqual(len(planes), 2)
                        self.assertEqual(sides, {True, False})
        self.assert_ref_layers_covered(routed)

    def test_reference_plane_widths_are_the_skill_default(self) -> None:
        """Every carried plane width is the skill's 3x-dielectric-height default.

        The report's ``Ref_layers`` column names planes and never widths, and a
        ``None`` width is translation-fatal, so a substrate carries the
        substrate-modeler skill's labeled default. Asserted against the
        default's own formula over the dielectric the STACKUP rows put between
        line and plane, never against an impedance row.
        """
        named = csv_reference_planes()
        routed: set[int] = set()
        for structure_id, structure in all_structures(candidate()):
            for index, layer in structure.layers.items():
                number = signed_to_layer(index)
                routed.add(number)
                widths = reference_planes(layer)
                with self.subTest(
                    structure=structure_id, candidate=structure.name, layer=f"L{number}"
                ):
                    self.assertEqual(sorted(widths), sorted(named.get(number, ())))
                    for plane, width in widths.items():
                        height = fabcsv.dielectric_between_mm(
                            sections()["STACKUP"], f"L{number}", f"L{plane}"
                        )
                        self.assertAlmostEqual(
                            width,
                            3 * height,
                            places=6,
                            msg=f"L{number} to plane L{plane}: STACKUP Thickness_mm "
                            f"puts {height:.4f} mm of dielectric between them",
                        )
        self.assert_ref_layers_covered(routed)

    def test_uncoupled_region_matches_csv(self) -> None:
        pairs = uncoupled_ids()
        substrate = candidate()
        for structure_id, uncoupled_id in pairs.items():
            rows = impedance_rows(uncoupled_id)
            with self.subTest(structure=uncoupled_id):
                structure = diff_structure_for(substrate, structure_id)
                uncoupled = structure.uncoupled_region
                self.assertIsNotNone(
                    uncoupled,
                    f"IMPEDANCE {uncoupled_id}: {structure.name!r} declares no "
                    "uncoupled_region",
                )
                assert uncoupled is not None
                self.assertAlmostEqual(
                    ohm.m_from(uncoupled.impedance),
                    float(rows[0]["Target_Z_ohm"]),
                    places=6,
                    msg=f"IMPEDANCE {uncoupled_id} Target_Z_ohm",
                )
                for row in rows:
                    for name in row["Layers"].split(";"):
                        with self.subTest(
                            structure=uncoupled_id, candidate=uncoupled.name, layer=name
                        ):
                            layer = layer_at(uncoupled, fabcsv.layer_number(name))
                            self.assert_layer_matches_row(layer, row)

    def test_uncoupled_rows_are_not_standalone_structures(self) -> None:
        """One single-ended structure per controlled single-ended target, less
        the ``-UNC`` rows, which belong inside their differential structure,
        plus one per single-ended neck region."""
        nested = set(uncoupled_ids().values())
        single = {
            r["Structure_ID"]
            for r in sections()["IMPEDANCE"]
            if r["Controlled"] == "Yes"
            and r["Type"] == "Single-ended"
            and r["Structure_ID"] not in nested
        }
        necks = [sid for sid in neck_regions() if sid in single]
        found = single_ended_structures(candidate())
        self.assertEqual(
            len(found),
            len(single) + len(necks),
            "single-ended structures on the substrate, against controlled "
            f"single-ended targets {sorted(single)} and their neck regions "
            f"{necks}",
        )

    def test_uncontrolled_rows_are_not_modelled(self) -> None:
        """A row with ``Controlled`` other than Yes has no single impedance, so
        no structure may claim any impedance its Modelled_Z_ohm cell quotes."""
        substrate = candidate()
        for row in uncontrolled_rows():
            self.assertEqual(row["Target_Z_ohm"], "", f"{row['Structure_ID']} target")
            for value in re.findall(r"\d+(?:\.\d+)?", row["Modelled_Z_ohm"]):
                with (
                    self.subTest(structure=row["Structure_ID"], impedance=value),
                    self.assertRaises(ValueError),
                ):
                    substrate.routing_structure(float(value) * ohm)


class TestNeckRegions(TestCase):
    """A neck region is a routing structure of its own, applied by tag in the
    design; ``NeckDown`` is not used. How a design applies the structure is
    not graded here."""

    def test_no_neck_down_in_the_file(self) -> None:
        """No ``NeckDown`` name and no ``neck_down=`` other than None in the
        candidate file's code; comments and strings are not read."""
        path = Path(str(sys.modules[SUBSTRATE.__module__].__file__))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        lines = sorted(
            {
                node.lineno
                for node in ast.walk(tree)
                if (isinstance(node, ast.Name) and node.id == "NeckDown")
                or (isinstance(node, ast.Attribute) and node.attr == "NeckDown")
                or (isinstance(node, ast.alias) and node.name == "NeckDown")
                or (
                    isinstance(node, ast.keyword)
                    and node.arg == "neck_down"
                    and not (
                        isinstance(node.value, ast.Constant)
                        and node.value.value is None
                    )
                )
            }
        )
        self.assertEqual(
            lines,
            [],
            f"{path.name} uses NeckDown on these lines. A neck region is a "
            "routing structure of its own, applied by tag in the design.",
        )

    def test_no_structure_carries_a_neck_down(self) -> None:
        for label, structure in all_structures(candidate()):
            for index, layer in structure.layers.items():
                with self.subTest(
                    structure=label,
                    candidate=structure.name,
                    layer=f"L{signed_to_layer(index)}",
                ):
                    self.assertIsNone(
                        layer.neck_down,
                        "a neck region is a routing structure of its own, "
                        "applied by tag in the design, not a NeckDown",
                    )

    def test_each_neck_region_has_a_structure_of_its_own(self) -> None:
        """Each target whose rows quote ``Neck_*`` columns has a structure
        beside its main one, of the same kind, on the layers of those rows,
        with the neck width, pair gap and clearance."""
        substrate = candidate()
        matched = dict(neck_lookups(substrate))
        taken = [s for _, s in controlled_lookups(substrate)] + list(matched.values())
        spare = [
            s
            for s in top_level_structures(substrate)
            if not any(s is seen for seen in taken)
        ]
        for structure_id in neck_regions():
            if structure_id in matched:
                continue
            quoted = "; ".join(
                f"{row['Layers']} width {row['Neck_width_mm']}, gap "
                f"{row.get('Neck_gap_mm', '') or '-'}, clearance "
                f"{row.get('Neck_clearance_mm', '') or '-'}"
                for row in neck_rows(structure_id)
            )
            nearest = "; ".join(
                f"{s.name!r}: {', '.join(neck_mismatches(s, structure_id))}"
                for s in spare
            )
            with self.subTest(structure=neck_label(structure_id)):
                self.fail(
                    f"IMPEDANCE {structure_id} quotes a neck region ({quoted}), "
                    "and no structure carries it other than the one its target "
                    "impedance finds. Structures no target finds: "
                    f"{nearest or 'none'}"
                )


class TestSettings(unittest.TestCase):
    """A setting that is set but blank is an error, and the two required ones
    are errors when unset. A plain ``unittest.TestCase``: nothing here
    instantiates JITX objects."""

    def test_set_but_empty_is_refused(self) -> None:
        for name in ("SUBSTRATE_FILE", "SUBSTRATE_CLASS", "FAB_CSV"):
            with (
                self.subTest(variable=name),
                mock.patch.dict(os.environ, {name: " "}),
                self.assertRaisesRegex(ValueError, f"^{name} is set but empty"),
            ):
                optional_setting(name)

    def test_required_settings_unset_are_refused(self) -> None:
        for name, reader in (("SUBSTRATE_FILE", _load_module), ("FAB_CSV", fab_csv)):
            environment = {k: v for k, v in os.environ.items() if k != name}
            with (
                self.subTest(variable=name),
                mock.patch.dict(os.environ, environment, clear=True),
                self.assertRaisesRegex(ValueError, f"^{name} is not set"),
            ):
                reader()


class TestTranslation(TestCase):
    def test_design_translates(self) -> None:
        self.assertTrue(package_design(grading_design()))
