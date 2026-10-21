#!/usr/bin/env python3
"""Grade what the stackup-from-pdf-report cases add to the substrate grader.

Usage:
  grade_pdf_report.py report BOARD_PY CSV [--timeout SECONDS]
  grade_pdf_report.py symmetric BOARD_PY [--timeout SECONDS]

``report`` grades a substrate against the CSV twin of the case's PDF report,
on the points substrate_grader.py does not cover. Every expected value is read
from the CSV:

- backdrill: each VIAS row with a ``Backdrill_side`` is one mechanical via
  coded from ``From_layer`` to the layer the backdrill keeps, backdrilled from
  that side only, with the four backdrill dimensions;
- stacked: each VIAS row with ``Stacked_levels`` above 1 is one laser via over
  its whole span, not a stack of unlisted single-level vias;
- nfp: each VIAS row with ``NFP_layers`` has its pad on every layer it spans
  and its reduced pad on exactly the listed layers, through ``diameters`` and
  ``ViaDiameter(nfp=...)`` or the via-wide ``nfp``;
- skip_layer_reference: a routing layer whose IMPEDANCE ``Ref_layers`` names a
  plane beyond the next copper layer references that plane alone, at 3x the
  dielectric summed between them;
- capability_not_attributes: no capability limit that is not a length (an
  ``N:1`` ratio or a count) is a class attribute of the rules or substrate
  class;
- capability_documented: the rules class docstring states every capability
  limit, the length limits in mm or mil, unless the limit is a custom mm
  attribute of the rules class.

``report`` also prints a ``NOTE`` line for each source line that seems to
call a fabrication-constraint field other than the four ``min_copper_*``
fields engine-enforced. Only those four are enforced; the rest document the
fab's rules. The scan is a pattern match, so a NOTE never fails the run: it
points a reader at the line.

``symmetric`` grades the no-report variant: the substrate's stackup is a
``Symmetric`` subclass, its last listed layer is a dielectric, it has four
copper layers, and the substrate translates on a 50 x 50 mm board.

Exit codes: 0 graded and every check passed / 1 a check failed, the candidate
does not import, or the run went past --timeout seconds (default 120) / 2 a
usage error or a grader dependency that does not import.
"""

from __future__ import annotations

import argparse
import inspect
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import check_runner
    import fabcsv

    # `instantiation` and `package_design` are private; jitx exposes no public
    # entry point that instantiates and translates a design offline.
    from jitx._instantiation import instantiation
    from jitx._translate.design import package_design
    from jitx.inspect import decompose
    from jitx.si import DifferentialRoutingStructure, RoutingStructure, _RefLayer
    from jitx.stackup import Conductor, Dielectric, Material, Symmetric
    from jitx.substrate import FabricationConstraints, Substrate
except ImportError as missing:
    print(f"ERROR  the grader needs {missing.name}: {missing}")
    sys.exit(2)

if TYPE_CHECKING:
    # Annotation-only: the protobuf message types of the translated design.
    from jitxcore._proto.design_pb2 import DesignV1
    from jitxcore._proto.via_pb2 import Via as ViaProto

Rows = list[dict[str, str]]
TOLERANCE_MM = 1e-4
"""Values in the twin are stated to 0.1 um."""

SIDE_TOP = 0
"""``LayerIndex.side`` for an index counted from the top."""

ENFORCED = frozenset(
    name
    for name in FabricationConstraints.__annotations__
    if name.startswith("min_copper_")
)
"""The fields the engine enforces, per jitx.substrate.FabricationConstraints."""

SYMMETRIC_BOARD = (50.0, 50.0, 0.0)
"""The variant has no report, so no board size: a 50 x 50 mm square."""


def close(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= TOLERANCE_MM


class Report:
    """The CSV twin and the candidate substrate graded against it."""

    def __init__(self, substrate: type[Substrate], csv: Path, source: str) -> None:
        self.substrate = substrate
        self.source = source
        self.sections = fabcsv.sections(csv)
        self.stackup: Rows = self.sections["STACKUP"]
        self.vias: Rows = self.sections["VIAS"]
        self.n_copper = sum(1 for row in self.stackup if row["Type"] == "Copper")
        self._design: check_runner.SubstrateDesign | None = None
        self._translated: DesignV1 | None = None

    def board_size(self) -> tuple[float, float, float]:
        row = next(r for r in self.sections["DOCUMENT"] if r["Field"] == "Board size")
        width, height = (float(part) for part in row["Value"].split(" x "))
        radius = re.search(r"([0-9.]+)\s*mm corner radius", row["Notes"])
        return width, height, float(radius.group(1)) if radius else 0.0

    def design(self) -> check_runner.SubstrateDesign:
        """The substrate on the report's board, instantiated once."""
        if self._design is None:
            self._design = check_runner.SubstrateDesign(
                self.substrate, self.board_size()
            )
        return self._design

    def translated(self) -> DesignV1:
        """The design, translated once."""
        if self._translated is None:
            self._translated = package_design(self.design()).v1
        return self._translated

    def layer_number(self, index: int, side: int) -> int:
        return index + 1 if side == SIDE_TOP else self.n_copper - index

    def signed_to_layer(self, index: int) -> int:
        return (index if index >= 0 else index + self.n_copper) + 1

    def registered_vias(self) -> list[ViaProto]:
        design = self.translated()
        on_board = set(design.boards[0].vias)
        return [via for via in design.vias if via.id in on_board]

    def span(self, via: ViaProto) -> tuple[int, int]:
        return (
            self.layer_number(via.start.index, via.start.side),
            self.layer_number(via.stop.index, via.stop.side),
        )

    @staticmethod
    def is_laser(via: ViaProto) -> bool:
        drill = via.DESCRIPTOR.fields_by_name["type"].enum_type
        assert drill is not None
        return via.type == drill.values_by_name["LASER_DRILL"].number

    def via_for(self, row: dict[str, str]) -> ViaProto:
        laser = row["Drill"] == "Laser"
        ends = {
            fabcsv.layer_number(row["From_layer"]),
            fabcsv.layer_number(row["To_layer"]),
        }
        found = [
            via
            for via in self.registered_vias()
            if self.is_laser(via) == laser and set(self.span(via)) == ends
        ]
        if len(found) != 1:
            kind = "laser" if laser else "mechanical"
            names = ", ".join(via.name for via in found) or "none"
            raise AssertionError(
                f"{row['Via_ID']}: expected one {kind} via from {row['From_layer']} to "
                f"{row['To_layer']}, found {names}"
            )
        return found[0]

    def rows_with(self, column: str) -> Rows:
        rows = [row for row in self.vias if row.get(column, "").strip()]
        if not rows:
            raise AssertionError(f"the report has no VIAS row with {column}")
        return rows


def check_backdrill(report: Report) -> None:
    for row in report.rows_with("Backdrill_side"):
        via = report.via_for(row)
        start, _ = report.span(via)
        if start != fabcsv.layer_number(row["From_layer"]):
            raise AssertionError(
                f"{row['Via_ID']}: {via.name} starts at L{start}; it is drilled from "
                f"{row['From_layer']}"
            )
        side = row["Backdrill_side"].strip().lower()
        other = "top" if side == "bottom" else "bottom"
        if not via.backdrill.HasField(side):
            raise AssertionError(f"{row['Via_ID']}: {via.name} has no {side} backdrill")
        if via.backdrill.HasField(other):
            raise AssertionError(
                f"{row['Via_ID']}: {via.name} is backdrilled from the {other}; the report "
                f"backdrills it from the {side} only"
            )
        drill = getattr(via.backdrill, side)
        for field, column in (
            ("diameter", "Backdrill_diameter_mm"),
            ("startpad_diameter", "Backdrill_startpad_mm"),
            ("solder_mask_opening", "Backdrill_mask_opening_mm"),
            ("copper_clearance", "Backdrill_copper_clearance_mm"),
        ):
            if not close(getattr(drill, field), float(row[column])):
                raise AssertionError(
                    f"{row['Via_ID']}: backdrill {field} {getattr(drill, field)} != "
                    f"{row[column]}"
                )


def check_stacked(report: Report) -> None:
    listed = {
        frozenset(
            (fabcsv.layer_number(r["From_layer"]), fabcsv.layer_number(r["To_layer"]))
        )
        for r in report.vias
        if r["Drill"] == "Laser"
    }
    for row in report.vias:
        if int(row.get("Stacked_levels") or 1) < 2:
            continue
        report.via_for(row)
        low, high = sorted(
            (
                fabcsv.layer_number(row["From_layer"]),
                fabcsv.layer_number(row["To_layer"]),
            )
        )
        for via in report.registered_vias():
            ends = frozenset(report.span(via))
            if (
                report.is_laser(via)
                and ends not in listed
                and low <= min(ends) <= max(ends) <= high
            ):
                raise AssertionError(
                    f"{row['Via_ID']}: {via.name} is a laser via the report does not list, "
                    f"inside the stacked span {row['From_layer']} to {row['To_layer']}; "
                    "the stack is one via over the whole span"
                )


def check_nfp(report: Report) -> None:
    for row in report.rows_with("NFP_layers"):
        via = report.via_for(row)
        pad, nfp = float(row["Pad_mm"]), float(row["NFP_pad_mm"])
        reduced = {fabcsv.layer_number(name) for name in row["NFP_layers"].split(";")}
        per_layer: dict[int, tuple[float, float]] = {}
        for entry in via.diameters:
            for layer in entry.layers:
                per_layer[report.layer_number(layer.index, layer.side)] = (
                    entry.pad,
                    entry.nfp,
                )
        low, high = sorted(report.span(via))
        for number in range(low, high + 1):
            layer_pad, layer_nfp = per_layer.get(
                number, (via.diameter, via.nfp_diameter)
            )
            if not close(layer_pad, pad):
                raise AssertionError(
                    f"{row['Via_ID']}: pad on L{number} is {layer_pad}, not {pad}"
                )
            if number in reduced and not close(layer_nfp, nfp):
                raise AssertionError(
                    f"{row['Via_ID']}: non-functional pad on L{number} is "
                    f"{layer_nfp or 'not set'}, not {nfp}"
                )
            if number not in reduced and layer_nfp:
                raise AssertionError(
                    f"{row['Via_ID']}: L{number} has a non-functional pad of {layer_nfp}; "
                    f"the report reduces pads on {row['NFP_layers']} only"
                )


def reference_groups(report: Report) -> list[tuple[int, tuple[int, ...]]]:
    """(routing layer, its planes) for each IMPEDANCE ``Ref_layers`` group."""
    out: list[tuple[int, tuple[int, ...]]] = []
    for row in report.sections["IMPEDANCE"]:
        if not row["Ref_layers"]:
            continue
        layers = [name.strip() for name in row["Layers"].split(";")]
        for index, group in enumerate(row["Ref_layers"].split(";")):
            planes, separator, target = group.strip().partition(" for ")
            if not separator:
                target = layers[index]
            numbers = tuple(fabcsv.layer_number(plane) for plane in planes.split("+"))
            out.append((fabcsv.layer_number(target), numbers))
    return out


AnyLayer = RoutingStructure.Layer | DifferentialRoutingStructure.Layer


def structure_layers(report: Report, number: int) -> list[tuple[str, AnyLayer]]:
    """Every routing-structure layer on the substrate that routes ``L<number>``."""
    substrate = report.design().substrate
    structures = [
        *decompose(substrate, RoutingStructure),
        *decompose(substrate, DifferentialRoutingStructure),
    ]
    return [
        (structure.name or type(structure).__name__, layer)
        for structure in structures
        for index, layer in structure.layers.items()
        if report.signed_to_layer(index) == number
    ]


def check_skip_layer_reference(report: Report) -> None:
    skips = [
        (target, planes)
        for target, planes in reference_groups(report)
        if any(abs(plane - target) > 1 for plane in planes)
    ]
    if not skips:
        raise AssertionError(
            "the report has no routing layer that skips a copper layer"
        )
    for target, planes in skips:
        expected = {
            plane: 3
            * fabcsv.dielectric_between_mm(report.stackup, f"L{target}", f"L{plane}")
            for plane in planes
        }
        found = structure_layers(report, target)
        if not found:
            raise AssertionError(f"no routing structure routes L{target}")
        for name, layer in found:
            refs = {
                report.signed_to_layer(ref.layer): ref.desired_width
                for ref in decompose(layer, _RefLayer)
            }
            if set(refs) != set(expected) or not all(
                close(refs[plane], width) for plane, width in expected.items()
            ):
                want = ", ".join(f"L{p} at {w:.4f}" for p, w in expected.items())
                got = (
                    ", ".join(f"L{p} at {w:.4f}" for p, w in refs.items()) or "nothing"
                )
                raise AssertionError(
                    f"{name} L{target} references {got}; the report wants {want} "
                    "(3x the dielectric summed between them)"
                )


def capability_rows(report: Report) -> list[tuple[str, str, float, float | None]]:
    """(rule, kind, value, mil value) for each FAB_RULES row with no JITX field.

    kind is ``ratio`` for ``N:1``, ``count`` for a rule about levels or a
    count, and ``length`` (in mm, with its mil value when stated) otherwise.
    """
    out: list[tuple[str, str, float, float | None]] = []
    for row in report.sections["FAB_RULES"]:
        if row["JITX_attribute"]:
            continue
        value = row["Value_mm"].strip()
        if ":" in value:
            out.append((row["Rule"], "ratio", float(value.split(":")[0]), None))
        elif re.search(r"levels|count", row["Rule"], re.IGNORECASE):
            out.append((row["Rule"], "count", float(value), None))
        else:
            mil = float(row["Value_mil"]) if row["Value_mil"].strip() else None
            out.append((row["Rule"], "length", float(value), mil))
    return out


NOT_A_LENGTH = re.compile(r"aspect|ratio|stack|level|count", re.IGNORECASE)


def custom_attributes(klass: type, base: type) -> dict[str, float]:
    """Numeric class attributes the candidate's own classes add above ``base``."""
    known = set(base.__annotations__) if base is FabricationConstraints else set()
    out: dict[str, float] = {}
    for cls in klass.__mro__:
        if (
            cls is base
            or not issubclass(cls, base)
            or cls.__module__.startswith("jitx")
        ):
            continue
        for name, value in vars(cls).items():
            if name.startswith("_") or name in known or isinstance(value, bool):
                continue
            if isinstance(value, int | float):
                out.setdefault(name, float(value))
    return out


def check_capability_not_attributes(report: Report) -> None:
    rules = report.substrate.constraints
    values = {
        value for _, kind, value, _ in capability_rows(report) if kind != "length"
    }
    for klass, base in (
        (type(rules), FabricationConstraints),
        (report.substrate, Substrate),
    ):
        for name, value in custom_attributes(klass, base).items():
            if NOT_A_LENGTH.search(name) or value in values:
                raise AssertionError(
                    f"{klass.__name__}.{name} = {value:g} holds a capability limit that is "
                    "not a length; it belongs in the rules class docstring"
                )


def numbers_in(text: str) -> set[float]:
    return {float(token) for token in re.findall(r"\d+(?:\.\d+)?", text)}


def check_capability_documented(report: Report) -> None:
    rules = type(report.substrate.constraints)
    stated = numbers_in(inspect.getdoc(rules) or "")
    custom = custom_attributes(rules, FabricationConstraints)
    missing: list[str] = []
    for rule, kind, value, mil in capability_rows(report):
        if any(close(number, value) for number in stated):
            continue
        if mil is not None and any(close(number, mil) for number in stated):
            continue
        if kind == "length" and any(close(number, value) for number in custom.values()):
            continue
        missing.append(rule)
    if missing:
        raise AssertionError(
            f"the {rules.__name__} docstring does not state: {'; '.join(missing)}"
        )


ENFORCED_CLAIM = re.compile(r"\benforc", re.IGNORECASE)
NEGATED = re.compile(
    r"\b(?:not|never|no|isn't|aren't|without)\b[^.;]*\benforc|\bunenforc", re.IGNORECASE
)


def enforced_claims(source: str) -> list[str]:
    """Source lines that call a non-``min_copper_*`` field enforced, as
    ``line N: text``. A pattern match for a reader, not a verdict."""
    others = [
        name for name in FabricationConstraints.__annotations__ if name not in ENFORCED
    ]
    found: list[str] = []
    for number, line in enumerate(source.splitlines(), start=1):
        if not ENFORCED_CLAIM.search(line) or NEGATED.search(line):
            continue
        if any(re.search(rf"\b{name}\b", line) for name in others):
            found.append(f"line {number}: {line.strip()}")
    return found


def report_checks(report: Report) -> list[check_runner.Check]:
    def bind(check: Callable[[Report], None]) -> Callable[[], None]:
        return lambda: check(report)

    return [
        ("backdrill", bind(check_backdrill)),
        ("stacked", bind(check_stacked)),
        ("nfp", bind(check_nfp)),
        ("skip_layer_reference", bind(check_skip_layer_reference)),
        ("capability_not_attributes", bind(check_capability_not_attributes)),
        ("capability_documented", bind(check_capability_documented)),
    ]


def symmetric_checks(substrate: type[Substrate]) -> list[check_runner.Check]:
    """The variant's checks. A stackup that cannot be instantiated, as a
    Symmetric one whose last listed layer is copper cannot, fails each of
    them with the reason."""
    made: list[check_runner.SubstrateDesign] = []

    def design() -> check_runner.SubstrateDesign:
        if not made:
            made.append(check_runner.SubstrateDesign(substrate, SYMMETRIC_BOARD))
        return made[0]

    def is_symmetric() -> None:
        stackup = type(design().substrate.stackup)
        if not issubclass(stackup, Symmetric):
            raise AssertionError(f"{stackup.__name__} is not a Symmetric stackup")

    def middle_is_dielectric() -> None:
        layers = list(decompose(design().substrate.stackup, Material))
        middle = layers[len(layers) // 2]
        if len(layers) % 2 == 0 or not isinstance(middle, Dielectric):
            raise AssertionError(
                f"the last listed layer is a {type(middle).__name__}; a Symmetric "
                "stackup lists down to its centre dielectric"
            )

    def four_copper_layers() -> None:
        count = len(list(decompose(design().substrate.stackup, Conductor)))
        if count != 4:
            raise AssertionError(f"{count} copper layers, not 4")

    def translates() -> None:
        package_design(design())

    return [
        ("symmetric", is_symmetric),
        ("middle_is_dielectric", middle_is_dielectric),
        ("four_copper_layers", four_copper_layers),
        ("translates", translates),
    ]


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Grade what the stackup-from-pdf-report cases add to the substrate grader."
    )
    parser.add_argument("--timeout", type=int, default=120)
    modes = parser.add_subparsers(dest="mode", required=True)
    report = modes.add_parser("report")
    report.add_argument("board", type=Path)
    report.add_argument("csv", type=Path)
    symmetric = modes.add_parser("symmetric")
    symmetric.add_argument("board", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse(argv)
    csv: Path | None = getattr(args, "csv", None)
    if csv is not None and not csv.is_file():
        print(f"ERROR  {csv} is not a file")
        return 2
    board: Path = args.board.expanduser().resolve()
    if not board.is_file():
        print(f"FAIL  candidate {board} is not a file")
        return 1
    try:
        with check_runner.time_limit(args.timeout):
            try:
                module = check_runner.load_module(board)
                substrate = check_runner.one_leaf(module, Substrate)
            except Exception as error:  # noqa: BLE001 - the candidate's red
                print(f"FAIL  candidate does not load: {check_runner.reason(error)}")
                return 1
            with instantiation.activate():
                if csv is None:
                    checks = symmetric_checks(substrate)
                else:
                    report = Report(substrate, csv, board.read_text(encoding="utf-8"))
                    checks = report_checks(report)
                    for claim in enforced_claims(report.source):
                        print(
                            "NOTE  only the four min_copper_* fields are engine-enforced; "
                            f"{claim}"
                        )
                return check_runner.run(checks, str(board))
    except check_runner.TimeLimit:
        print(f"FAIL  grading {board} ran past {args.timeout} s")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
