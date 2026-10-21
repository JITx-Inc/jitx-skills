#!/usr/bin/env python3
"""Grade the fencing in the fenced-rf-substrate case: a substrate and the design
that uses it, against the case's report and fencing spec.

Usage:
  grade_fenced_rf.py BOARD_PY DESIGN_PY CSV [--timeout SECONDS]

DESIGN_PY is imported with its own directory importable, so it may import
BOARD_PY by its module name. BOARD_PY must define one leaf Substrate subclass
and DESIGN_PY one leaf Design subclass whose substrate is an instance of it.
The layer count and the laser vias come from CSV; the fencing values come
from the spec (evals/cases/fixtures/rf_fence_spec.txt) and are held below,
with a self-test that each appears in the spec. The fence is graded on the
parameters declared, not on where the engine would place the vias.

Checks:

- design_translates: the candidate design translates offline;
- structures_translate: every routing structure on the substrate translates
  when a design rule applies it with a GND reference net;
- cpw_fence: the 50 ohm structure's L1 layer is fenced with the L1-L2 laser
  via, referenced to L2, at the spec's pitch, one row, first-row offset;
- cpw_keepout: that layer adds a pour KeepOut on L2 alone, of the spec's width;
- pair_fences: the 100 ohm pair declares exactly L1 and L6, each fenced with
  the laser via landing on its adjacent plane and referenced to that plane
  (``symmetric_routing_layers`` refuses to mirror these fences, since the
  laser vias are not symmetric, so the layers must be enumerated);
- references: each structure's layers reference the planes their IMPEDANCE
  row names, at 3x the dielectric between (substrate_grader.py cannot check
  this report, since it gives L1 two reference sets);
- cavity_rule: the substrate declares a tag-conditioned ``fence_via`` rule
  with the L1-L2 laser via, the spec's pitch and an outward offset;
- cavity_pour: the design has a Pour carrying that tag, on a layer the fence
  via reaches, in the cavity's outline (when cavity_rule finds no such rule,
  any tag will do here, so one defect is one red);
- cavity_keepout: a pour KeepOut of the same outline covers L1, where the spec
  voids the copper; the pour itself may sit on L1 or L2;
- no_isolate: no Pour in the design sets the deprecated ``isolate``;
- substrate_rules: the substrate declares no design rule but fence rules.

A via's ends are compared as a pair, so UV-2 may be coded from L6 to L5 or
from L5 to L6. The grading runs in a child process; see check_runner.py.

Exit codes: 0 graded and every check passed / 1 a check failed, a candidate
file does not import, the grading stopped before every check ran, or a stage
ran past --timeout seconds (default 120) / 2 a usage error, a grader
dependency that does not import, or an import that fails inside a library.
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path
from types import ModuleType

try:
    import check_runner
    import fabcsv
    from grade_substrate import stop

    # `instantiation` and `package_design` are private; jitx exposes no public
    # entry point that instantiates and translates a design offline.
    from jitx._instantiation import instantiation
    from jitx._translate.design import package_design
    from jitx.circuit import Circuit
    from jitx.constraints import (
        AtomExpr,
        DesignConstraint,
        FenceVia,
        Tag,
        UnaryDesignConstraint,
        ViaFencePattern,
        _ApplyTag,
        design_constraint,
    )
    from jitx.copper import Pour
    from jitx.design import Design
    from jitx.feature import KeepOut
    from jitx.inspect import decompose, extract
    from jitx.layerindex import LayerSet
    from jitx.net import Net
    from jitx.shapes import Shape
    from jitx.shapes.composites import rectangle
    from jitx.si import (
        DifferentialRoutingStructure,
        RoutingStructure,
        _AddGeom,
        _RefLayer,
        _StructureViaFence,
    )
    from jitx.substrate import Substrate
    from jitx.units import ohm
    from jitx.via import Via, ViaType
except ImportError as missing:
    print(f"ERROR  the grader needs {missing.name}: {missing}")
    sys.exit(2)

TOLERANCE_MM = 1e-6

# What the spec states. test_grade_fenced_rf.py checks each against the spec.
FENCE_PITCH = 0.50
CPW_OFFSET = 0.40
"""First-row via centres out from the trace edge."""
CPW_KEEPOUT_WIDTH = 0.60
PAIR_OFFSET = 0.60
"""First-row via centres out from the outer trace edge."""
CAVITY_OFFSET = 0.30
"""Via centres outside the cavity outline: outward, so positive."""
CAVITY_SIZE = (4.0, 3.0)
CAVITY_CENTRE = (5.0, 3.0)
BOARD_SIZE = (30.0, 20.0, 0.0)
CPW_LAYER = 1
CPW_FENCE_PLANE = 2
CPW_KEEPOUT_LAYER = 2
PAIR_FENCES = {1: 2, 6: 5}
"""Pair layer -> the plane its fence via lands on and references."""
CAVITY_LAYER = 1
CAVITY_FENCE_PLANE = 2


AnyStructure = RoutingStructure | DifferentialRoutingStructure
AnyLayer = RoutingStructure.Layer | DifferentialRoutingStructure.Layer


def close(actual: float | None, expected: float) -> bool:
    return actual is not None and abs(actual - expected) <= TOLERANCE_MM


class _ApplyStructures(Tag):
    """The grader's own tag for applying every routing structure."""


class _StructureCircuit(Circuit):
    """Applies each routing structure through a design rule, with GND as the
    reference net, so that it is translated."""

    def __init__(self, structures: list[AnyStructure]) -> None:
        self.GND = Net(name="GND")
        self.rules = [
            design_constraint(_ApplyStructures()).routing_structure(
                structure, ref_net=self.GND
            )
            for structure in structures
        ]


class Candidate:
    """The candidate's two files, the report, and the design instance."""

    def __init__(self, board: Path, design: Path, csv: Path) -> None:
        self.files = (board, design)
        self.design_module = check_runner.load_module(design)
        self.board_module = self._board_module(board)
        self.substrate_class = check_runner.one_leaf(self.board_module, Substrate)
        self.design_class = check_runner.one_leaf(self.design_module, Design)
        self.report = fabcsv.sections(csv)
        self.n_copper = sum(
            1 for row in self.report["STACKUP"] if row["Type"] == "Copper"
        )
        self._design: Design | None = None

    def _board_module(self, board: Path) -> ModuleType:
        """The module DESIGN_PY imported BOARD_PY as, or BOARD_PY itself."""
        for module in list(sys.modules.values()):
            file = getattr(module, "__file__", None)
            if file and Path(file).resolve() == board:
                return module
        return check_runner.load_module(board)

    def design(self) -> Design:
        """The candidate design, instantiated once."""
        if self._design is None:
            self._design = self.design_class()
        return self._design

    def substrate(self) -> Substrate:
        substrate = self.design().substrate
        if not isinstance(substrate, self.substrate_class):
            raise AssertionError(
                f"{self.design_class.__name__}.substrate is a "
                f"{type(substrate).__name__}, not the {self.substrate_class.__name__} "
                "board.py defines"
            )
        return substrate

    def layer(self, index: int) -> int:
        """A signed conductor index -> its 1-based layer number."""
        return (index if index >= 0 else index + self.n_copper) + 1

    def layers(self, layer_set: LayerSet) -> set[int]:
        out: set[int] = set()
        for start, end in layer_set.ranges:
            low, high = sorted((self.layer(start), self.layer(end)))
            out.update(range(low, high + 1))
        return out

    def via_span(self, definition: type[Via] | Via) -> tuple[bool, int, int]:
        """(laser, start layer, stop layer) of a via definition."""
        via = definition if isinstance(definition, type) else type(definition)
        return (
            via.type == ViaType.LaserDrill,
            self.layer(int(via.start_layer)),
            self.layer(int(via.stop_layer)),
        )

    def has_laser_via(self, start: int, stop: int) -> bool:
        """Whether the report lists a laser via between L<start> and L<stop>,
        coded either way round."""
        return any(
            row["Drill"] == "Laser"
            and {
                fabcsv.layer_number(row["From_layer"]),
                fabcsv.layer_number(row["To_layer"]),
            }
            == {start, stop}
            for row in self.report["VIAS"]
        )


def first_offset(pattern: ViaFencePattern) -> float:
    """The first row's offset as declared: ``initial_offset``, which defaults
    to ``offset``."""
    return (
        pattern.initial_offset if pattern.initial_offset is not None else pattern.offset
    )


def check_fence(
    candidate: Candidate,
    where: str,
    fence: FenceVia,
    start: int,
    plane: int,
    offset: float,
) -> None:
    if not candidate.has_laser_via(start, plane):
        raise AssertionError(f"the report lists no laser via from L{start} to L{plane}")
    laser, first, last = candidate.via_span(fence.definition)
    if not laser or {first, last} != {start, plane}:
        kind = "laser" if laser else "mechanical"
        raise AssertionError(
            f"{where}: the fence via is a {kind} via L{first}-L{last}; the spec "
            f"wants the laser via L{start}-L{plane}"
        )
    pattern = fence.pattern
    if not close(pattern.pitch, FENCE_PITCH):
        raise AssertionError(f"{where}: pitch {pattern.pitch}, not {FENCE_PITCH}")
    if not close(first_offset(pattern), offset):
        raise AssertionError(
            f"{where}: first-row offset {first_offset(pattern)}, not {offset} "
            "(the spec's distance from the edge to the via centres)"
        )
    if pattern.num_rows not in (None, 1):
        raise AssertionError(f"{where}: {pattern.num_rows} rows, not 1")
    if isinstance(fence, _StructureViaFence):
        if (
            fence.reference_layer is None
            or candidate.layer(fence.reference_layer) != plane
        ):
            raise AssertionError(
                f"{where}: reference_layer is {fence.reference_layer}; the fence ties to L{plane}"
            )


def layer_of(
    candidate: Candidate, structure: AnyStructure, number: int, name: str
) -> AnyLayer:
    for index, layer in structure.layers.items():
        if candidate.layer(index) == number:
            return layer
    raise AssertionError(f"the {name} declares nothing on L{number}")


def one_fence(layer: AnyLayer, where: str) -> _StructureViaFence:
    fences = list(extract(layer, _StructureViaFence))
    if len(fences) != 1:
        raise AssertionError(f"{where}: {len(fences)} fences, not 1")
    return fences[0]


def cpw(candidate: Candidate) -> RoutingStructure:
    try:
        return candidate.substrate().routing_structure(50 * ohm)
    except ValueError as error:
        raise AssertionError(f"no 50 ohm routing structure: {error}") from error


def pair(candidate: Candidate) -> DifferentialRoutingStructure:
    try:
        return candidate.substrate().differential_routing_structure(100 * ohm)
    except ValueError as error:
        raise AssertionError(
            f"no 100 ohm differential routing structure: {error}"
        ) from error


def check_design_translates(candidate: Candidate) -> None:
    package_design(candidate.design())


def structures_of(substrate: Substrate) -> list[AnyStructure]:
    return [
        *decompose(substrate, RoutingStructure),
        *decompose(substrate, DifferentialRoutingStructure),
    ]


def check_structures_translate(candidate: Candidate) -> None:
    design = check_runner.SubstrateDesign(
        candidate.substrate_class,
        BOARD_SIZE,
        lambda substrate: _StructureCircuit(structures_of(substrate)),
    )
    structures = structures_of(design.substrate)
    if not structures:
        raise AssertionError("the substrate declares no routing structure")
    translated = package_design(design).v1
    found = len(translated.routings) + len(translated.differential_routings)
    if found < len(structures):
        raise AssertionError(f"{len(structures)} structures, {found} translated")


def check_cpw_fence(candidate: Candidate) -> None:
    layer = layer_of(candidate, cpw(candidate), CPW_LAYER, "50 ohm structure")
    fence = one_fence(layer, f"50 ohm L{CPW_LAYER}")
    check_fence(
        candidate,
        f"50 ohm L{CPW_LAYER} fence",
        fence,
        CPW_LAYER,
        CPW_FENCE_PLANE,
        CPW_OFFSET,
    )


def check_cpw_keepout(candidate: Candidate) -> None:
    layer = layer_of(candidate, cpw(candidate), CPW_LAYER, "50 ohm structure")
    keepouts = [
        geom for geom in extract(layer, _AddGeom) if isinstance(geom.feature, KeepOut)
    ]
    if len(keepouts) != 1:
        raise AssertionError(
            f"50 ohm L{CPW_LAYER}: {len(keepouts)} KeepOut geometries, not 1"
        )
    geom = keepouts[0]
    feature = geom.feature
    assert isinstance(feature, KeepOut)
    layers = candidate.layers(feature.layers)
    if layers != {CPW_KEEPOUT_LAYER}:
        named = ", ".join(f"L{n}" for n in sorted(layers))
        raise AssertionError(
            f"the KeepOut is on {named}, not L{CPW_KEEPOUT_LAYER} alone"
        )
    if not feature.pour:
        raise AssertionError("the KeepOut does not keep out pours (pour=True)")
    if not close(geom.width, CPW_KEEPOUT_WIDTH):
        raise AssertionError(
            f"the KeepOut is {geom.width} wide, not {CPW_KEEPOUT_WIDTH}"
        )


def check_pair_fences(candidate: Candidate) -> None:
    structure = pair(candidate)
    declared = {candidate.layer(index) for index in structure.layers}
    if declared != set(PAIR_FENCES):
        named = ", ".join(f"L{n}" for n in sorted(declared))
        raise AssertionError(f"the 100 ohm pair declares {named}, not L1 and L6")
    for number, plane in PAIR_FENCES.items():
        layer = layer_of(candidate, structure, number, "100 ohm pair")
        fence = one_fence(layer, f"100 ohm L{number}")
        check_fence(
            candidate, f"100 ohm L{number} fence", fence, number, plane, PAIR_OFFSET
        )


def reference_rows(
    candidate: Candidate,
) -> list[tuple[dict[str, str], int, tuple[int, ...]]]:
    """(IMPEDANCE row, routing layer, its planes) per controlled layer."""
    out: list[tuple[dict[str, str], int, tuple[int, ...]]] = []
    for row in candidate.report["IMPEDANCE"]:
        if row["Controlled"] != "Yes":
            continue
        layers = [name.strip() for name in row["Layers"].split(";")]
        for index, group in enumerate(row["Ref_layers"].split(";")):
            planes, separator, target = group.strip().partition(" for ")
            if not separator:
                target = layers[index]
            numbers = tuple(fabcsv.layer_number(plane) for plane in planes.split("+"))
            out.append((row, fabcsv.layer_number(target), numbers))
    return out


def check_references(candidate: Candidate) -> None:
    for row, number, planes in reference_rows(candidate):
        structure: AnyStructure = (
            cpw(candidate) if row["Type"] != "Differential" else pair(candidate)
        )
        name = f"{row['Structure_ID']} L{number}"
        layer = layer_of(candidate, structure, number, row["Structure_ID"])
        refs = {
            candidate.layer(ref.layer): ref.desired_width
            for ref in decompose(layer, _RefLayer)
        }
        want = {
            plane: 3
            * fabcsv.dielectric_between_mm(
                candidate.report["STACKUP"], f"L{number}", f"L{plane}"
            )
            for plane in planes
        }
        if set(refs) != set(want) or not all(
            close(refs[p], w) for p, w in want.items()
        ):
            got = ", ".join(f"L{p} at {w:.4f}" for p, w in refs.items()) or "nothing"
            wanted = ", ".join(f"L{p} at {w:.4f}" for p, w in want.items())
            raise AssertionError(f"{name} references {got}; the report wants {wanted}")


def fence_rules(candidate: Candidate) -> list[UnaryDesignConstraint]:
    return [
        rule
        for rule in decompose(candidate.substrate(), DesignConstraint)
        if isinstance(rule, UnaryDesignConstraint)
        and getattr(rule, "fence_via_constraint", None) is not None
    ]


def cavity_rule(candidate: Candidate) -> tuple[type[Tag], FenceVia]:
    """The substrate's one tag-conditioned fence rule: its tag class and fence."""
    rules = fence_rules(candidate)
    tagged = [rule for rule in rules if isinstance(rule.condition, AtomExpr)]
    if len(tagged) != 1:
        raise AssertionError(
            f"the substrate declares {len(tagged)} fence_via rules conditioned on a "
            "single tag, not 1"
        )
    rule = tagged[0]
    condition = rule.condition
    assert isinstance(condition, AtomExpr)
    fence = rule.fence_via_constraint
    assert fence is not None
    return type(condition.atom), fence


def check_cavity_rule(candidate: Candidate) -> None:
    _, fence = cavity_rule(candidate)
    check_fence(
        candidate,
        "cavity fence rule",
        fence,
        CAVITY_LAYER,
        CAVITY_FENCE_PLANE,
        CAVITY_OFFSET,
    )


def cavity_shape() -> Shape:
    return rectangle(*CAVITY_SIZE).at(*CAVITY_CENTRE)


def same_outline(shape: Shape, expected: Shape) -> bool:
    """Whether two shapes cover the same area. A shape shapely cannot read,
    such as a routing structure's ``Empty()``, matches nothing."""
    try:
        actual = shape.to_shapely().g
    except Exception:  # noqa: BLE001 - an unreadable shape is not the outline
        return False
    return actual.symmetric_difference(expected.to_shapely().g).area <= TOLERANCE_MM


def tagged_pours(candidate: Candidate, tag: type[Tag] | None) -> list[Pour]:
    """The design's Pours carrying ``tag``, or any tag when it is None."""
    out: list[Pour] = []
    for record in extract(candidate.design(), _ApplyTag):
        if isinstance(record.target, Pour) and any(
            tag is None or type(each) is tag for each in record.tags.tags
        ):
            out.append(record.target)
    return out


def check_cavity_pour(candidate: Candidate) -> None:
    try:
        tag, fence = cavity_rule(candidate)
    except AssertionError:
        # cavity_rule reports a missing rule; grade the pour on its own.
        tag, start, stop = None, CAVITY_LAYER, CAVITY_FENCE_PLANE
    else:
        _, start, stop = candidate.via_span(fence.definition)
    pours = tagged_pours(candidate, tag)
    if not pours:
        wanted = f"the {tag.__name__} tag" if tag is not None else "a tag"
        raise AssertionError(f"no Pour in the design carries {wanted}")
    reach = set(range(min(start, stop), max(start, stop) + 1))
    for pour in pours:
        layer = candidate.layer(pour.layer)
        if layer not in reach:
            raise AssertionError(
                f"the tagged Pour is on L{layer}, which the fence via (L{start}-L{stop}) "
                "does not reach"
            )
        if not same_outline(pour.shape, cavity_shape()):
            raise AssertionError("the tagged Pour is not the cavity outline")


def check_cavity_keepout(candidate: Candidate) -> None:
    for keepout in extract(candidate.design(), KeepOut):
        if (
            keepout.pour
            and CAVITY_LAYER in candidate.layers(keepout.layers)
            and same_outline(keepout.shape, cavity_shape())
        ):
            return
    raise AssertionError(
        f"no pour KeepOut (pour=True) in the cavity outline covers L{CAVITY_LAYER}"
    )


def check_no_isolate(candidate: Candidate) -> None:
    for pour in extract(candidate.design(), Pour):
        if pour.isolate:
            raise AssertionError(
                f"a Pour on L{candidate.layer(pour.layer)} sets the deprecated "
                f"isolate={pour.isolate:g}"
            )


EFFECTS = [
    name
    for name in UnaryDesignConstraint.__annotations__
    if name.endswith("_constraint")
]


def check_substrate_rules(candidate: Candidate) -> None:
    for rule in decompose(candidate.substrate(), DesignConstraint):
        if not isinstance(rule, UnaryDesignConstraint):
            raise AssertionError(
                f"the substrate declares a {type(rule).__name__}; design rules beyond "
                "the fence rule belong in the design"
            )
        others = [
            name
            for name in EFFECTS
            if name != "fence_via_constraint" and getattr(rule, name, None) is not None
        ]
        if others or getattr(rule, "fence_via_constraint", None) is None:
            effects = ", ".join(others) or "no fence_via"
            raise AssertionError(
                f"the substrate declares a rule with {effects}; design rules beyond the "
                "fence rule belong in the design"
            )


NAMES = [
    "design_translates",
    "structures_translate",
    "cpw_fence",
    "cpw_keepout",
    "pair_fences",
    "references",
    "cavity_rule",
    "cavity_pour",
    "cavity_keepout",
    "no_isolate",
    "substrate_rules",
]


def checks(candidate: Candidate) -> list[check_runner.Check]:
    named = [
        ("design_translates", check_design_translates),
        ("structures_translate", check_structures_translate),
        ("cpw_fence", check_cpw_fence),
        ("cpw_keepout", check_cpw_keepout),
        ("pair_fences", check_pair_fences),
        ("references", check_references),
        ("cavity_rule", check_cavity_rule),
        ("cavity_pour", check_cavity_pour),
        ("cavity_keepout", check_cavity_keepout),
        ("no_isolate", check_no_isolate),
        ("substrate_rules", check_substrate_rules),
    ]
    assert [name for name, _ in named] == NAMES
    return [(name, lambda check=check: check(candidate)) for name, check in named]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Grade the fencing in the fenced-rf-substrate case."
    )
    parser.add_argument("board", type=Path)
    parser.add_argument("design", type=Path)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    if not args.timeout > 0:
        print("ERROR  --timeout must be a positive number of seconds")
        return 2
    if not args.csv.is_file():
        print(f"ERROR  {args.csv} is not a file")
        return 2
    board: Path = args.board.expanduser().resolve()
    design: Path = args.design.expanduser().resolve()
    for file in (board, design):
        if not file.is_file():
            print(f"FAIL  candidate {file} is not a file")
            return 1
    token = check_runner.child_nonce()
    if token is None:
        return check_runner.grade_in_child(
            Path(__file__).resolve(),
            argv,
            NAMES,
            [board, design],
            f"{board} and {design}",
            args.timeout,
        )
    sys.path.insert(0, str(design.parent))
    try:
        candidate = Candidate(board, design, args.csv)
    except Exception as error:  # noqa: BLE001 - the candidate's red
        print(check_runner.load_failure(error))
        return 1
    with instantiation.activate():
        return check_runner.run(checks(candidate), token)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    sys.exit(main(sys.argv[1:]))
