"""grade_substrate.py and substrate_grader.py grade what they are given, and nothing else.

The JS1 kit board, read from an installed jitxexamples and brought to this
case's rules (each neck region a routing structure of its own, no
``NeckDown``, drum-side Rz in the foil docstrings; see ``kit_source``),
passes against a verbatim copy of the kit's own report, and so does a copy
with every class and structure renamed, so nothing is found by name. The kit
board as it ships, with its neck-downs, fails. Copies with one wrong value
fail in the test that owns that value. Temporary copies of the kit report and
the kit board, edited together, pass, so the grader reads what a report says
rather than what the JS1 report happens to say. The same kit board fails
against the case's report, and the case's report is checked for its own
internal consistency without any board. Unset or blank settings are errors,
never defaults. Tests that need the kit board or jitx skip, with the reason,
when they are not installed.

testdata/JS1_Part1_Fab-Stackup.csv is a verbatim copy of the fab stackup
report that ships with the JS1 Jumpstart kit
(part1-stackup/JS1_Part1_Fab-Stackup.csv in the kit). The copy and the
installed kit board must be updated together: the kit board is graded against
the copy, so a change to one without the other turns these tests red.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import sysconfig
import time
from collections.abc import Callable
from pathlib import Path

import fabcsv
import grade_substrate
import import_candidate
import pytest

CHECKS = Path(__file__).resolve().parent
GRADER = CHECKS / "substrate_grader.py"
GRADE = CHECKS / "grade_substrate.py"
KIT_CSV = CHECKS / "testdata" / "JS1_Part1_Fab-Stackup.csv"
CASE_CSV = CHECKS.parent / "cases" / "fixtures" / "QCW-HDI12_Fab-Stackup_RevB.csv"
KIT_MODULE = "jitxexamples.jumpstart_kits.js1_stackup_components.hdi_stackup.board"


def kit_board() -> Path | None:
    """The installed kit board's source file, or None when it is absent."""
    try:
        spec = importlib.util.find_spec(KIT_MODULE)
    except ModuleNotFoundError:
        return None
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin)


KIT_BOARD = kit_board()
needs_kit = pytest.mark.skipif(
    KIT_BOARD is None,
    reason=f"{KIT_MODULE} is not importable; install jitxexamples to run this test",
)
needs_jitx = pytest.mark.skipif(
    importlib.util.find_spec("jitx") is None,
    reason="jitx is not importable; install jitx to run this test",
)


KIT_NECK_DOWNS = (
    (
        "    neck = (\n"
        "        RoutingStructure.NeckDown(\n"
        "            trace_width=neck_width,\n"
        "            clearance=neck_clearance,\n"
        "        )\n"
        "        if neck_width is not None or neck_clearance is not None\n"
        "        else None\n"
        "    )\n",
        "",
    ),
    ("            neck_down=neck,\n", ""),
    (
        "            neck_down=DifferentialRoutingStructure.NeckDown(\n"
        "                trace_width=neck_width,\n"
        "                pair_spacing=neck_gap,\n"
        "                clearance=neck_clearance,\n"
        "            ),\n",
        "",
    ),
    (
        "    neck_width: float,\n    neck_gap: float,\n    neck_clearance: float,\n",
        "    neck_width: float | None = None,\n"
        "    neck_gap: float | None = None,\n"
        "    neck_clearance: float | None = None,\n",
    ),
)
"""Edits that take every ``NeckDown`` out of the kit's two layer helpers."""


def kit_neck_structure(attribute: str, name: str) -> str:
    """A single-ended structure carrying the JS1 single-ended neck geometry:
    the report's Neck_* width and clearance on the microstrip and stripline
    layers. SE-DEFAULT, SE-40 and SE-50 quote the same neck geometry, so one
    such structure can serve all three. The report quotes no single impedance,
    velocity or loss for a neck: the impedance is the stripline rows'
    Neck_modelled_Z_ohm, and velocity and loss are SE-DEFAULT's, as a runner
    would label them. The grader checks none of the three."""
    return f"""    {attribute} = RoutingStructure(
        name="{name}",
        impedance=58.35 * ohm,
        layers={{
            **_se_layers(
                MICROSTRIP_LAYERS,
                width=0.1500,
                clearance=0.1500,
                eps_eff=2.4316,
                insertion_loss=0.00907,
            ),
            **_se_layers(
                STRIPLINE_LAYERS,
                width=0.0762,
                clearance=0.0762,
                eps_eff=2.9600,
                insertion_loss=0.01367,
            ),
        }},
    )
"""


KIT_DIFF_NECK = """    Neck_DIFF_100 = DifferentialRoutingStructure(
        name="neck region (DIFF-100)",
        impedance=106.54 * ohm,
        layers={
            **_diff_layers(
                MICROSTRIP_LAYERS,
                width=0.1000,
                pair_gap=0.0750,
                clearance=0.2000,
                eps_eff=2.4010,
                insertion_loss=0.01082,
            ),
            **_diff_layers(
                STRIPLINE_LAYERS,
                width=0.0635,
                pair_gap=0.0635,
                clearance=0.1270,
                eps_eff=2.9600,
                insertion_loss=0.01579,
            ),
        },
    )
"""
"""The JS1 DIFF-100 neck region as a differential structure of its own."""

KIT_SHARED_NECK = kit_neck_structure(
    "Neck_SE", "neck region (SE-DEFAULT, SE-40, SE-50)"
)
"""One structure for the three single-ended neck regions, whose geometry is
the same."""

KIT_NECK_STRUCTURES = KIT_SHARED_NECK + KIT_DIFF_NECK
"""The JS1 neck regions as structures of their own: one shared single-ended
structure and one differential. The DIFF-100 impedance is its stripline
row's Neck_modelled_Z_ohm."""

KIT_NECK_PER_REGION = (
    "".join(
        kit_neck_structure(f"Neck_{sid.replace('-', '_')}", f"neck region ({sid})")
        for sid in ("SE-DEFAULT", "SE-40", "SE-50")
    )
    + KIT_DIFF_NECK
)
"""The same neck regions with a single-ended structure for each region."""

KIT_DRUM_RZ = (
    (
        "Rz matte 2.0 um -> roughness 0.0020 mm.",
        "Rz matte 2.0 um, drum 0.7 um -> roughness 0.0020 mm.",
    ),
    (
        "Rz matte 6.0 um -> roughness 0.0060 mm.",
        "Rz matte 6.0 um, drum 3.5 um -> roughness 0.0060 mm.",
    ),
)
"""Docstring edits that add the report's drum-side Rz to each kit foil class."""


def kit_source(necks: str = KIT_NECK_STRUCTURES) -> str:
    """The kit board brought to this case's rules: each neck region on a
    routing structure of its own (``necks``), no ``NeckDown`` anywhere, and
    the drum-side Rz in each foil class's docstring. Each edit applies only
    where the installed kit board still has the text it edits, so a kit board
    already brought to these rules is taken as it is; the neck structures are
    added only when ``NeckDown`` entries were taken out. A test that asks for
    other ``necks`` than the default skips on a kit board with no
    ``NeckDown`` entries, since its structures could not take their place and
    the test would grade the kit's own."""
    assert KIT_BOARD is not None
    source = KIT_BOARD.read_text(encoding="utf-8")
    had_neck_downs = "NeckDown" in source
    if not had_neck_downs and necks != KIT_NECK_STRUCTURES:
        pytest.skip(
            "the installed kit board has no NeckDown entries for these neck "
            "structures to replace, so this test would grade the kit's own"
        )
    for old, new in (*KIT_NECK_DOWNS, *KIT_DRUM_RZ):
        source = source.replace(old, new)
    assert "NeckDown" not in source, "the kit's NeckDown code has changed shape"
    return add_to_substrate(necks)(source) if had_neck_downs else source


@needs_kit
def test_kit_source_skips_other_necks_on_a_kit_board_without_neck_downs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Once the kit board ships without ``NeckDown``, a test that asks for
    neck structures of its own skips rather than grading the kit's."""
    retargeted = tmp_path / "board.py"
    retargeted.write_text(kit_source(), encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "KIT_BOARD", retargeted)
    assert kit_source() == retargeted.read_text(encoding="utf-8")
    with pytest.raises(pytest.skip.Exception, match="no NeckDown entries"):
        kit_source(KIT_NECK_PER_REGION)


def renamed_kit_source() -> str:
    """:func:`kit_source` with every class, routing-structure attribute and
    structure ``name=`` replaced by a meaningless one."""
    source = kit_source()
    names = re.findall(r"^\s*class (\w+)\(", source, re.MULTILINE)
    names += re.findall(
        r"^    (\w+) = (?:Differential)?RoutingStructure\(", source, re.MULTILINE
    )
    for number, name in enumerate(names):
        source = re.sub(rf"\b{name}\b", f"Renamed{number}", source)
    counter = iter(range(len(source)))
    return re.sub(
        r'name="\d+ ohm[^"]*"', lambda _: f'name="structure {next(counter)}"', source
    )


@pytest.fixture(autouse=True)
def no_grader_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The grader's own settings, exported in the shell that runs these tests,
    must not change what they see."""
    for name in (
        "SUBSTRATE_FILE",
        "SUBSTRATE_CLASS",
        "FAB_CSV",
        "PYTEST_ADDOPTS",
        "GRADE_SUBSTRATE_PID",
        import_candidate.GRADER_ENVIRONMENT,
    ):
        monkeypatch.delenv(name, raising=False)


def grade(
    capsys: pytest.CaptureFixture[str], board: Path, report: Path
) -> tuple[int, str]:
    """grade_substrate's exit code and printed output for one board and report."""
    code = grade_substrate.main(["grade_substrate.py", str(board), str(report)])
    return code, capsys.readouterr().out


def write(tmp_path: Path, source: str) -> Path:
    board = tmp_path / "board.py"
    board.write_text(source, encoding="utf-8")
    return board


@needs_kit
def test_kit_board_passes_its_own_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, out = grade(capsys, write(tmp_path, kit_source()), KIT_CSV)
    assert code == 0, out[-3000:]
    assert "PASS  the grader graded" in out


@needs_kit
def test_kit_board_with_its_neck_downs_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The kit board as it ships models its neck regions as ``NeckDown``
    entries on the controlled structures, which the grader refuses."""
    assert KIT_BOARD is not None
    if "NeckDown" not in KIT_BOARD.read_text(encoding="utf-8"):
        pytest.skip("the installed kit board no longer uses NeckDown")
    code, out = grade(capsys, KIT_BOARD, KIT_CSV)
    assert code == 1, out[-3000:]
    for owner in (
        "TestNeckRegions::test_no_neck_down_in_the_file",
        "TestNeckRegions::test_no_structure_carries_a_neck_down",
        "TestNeckRegions::test_each_neck_region_has_a_structure_of_its_own",
    ):
        assert re.search(rf"FAILED.*{owner}", out), owner


@needs_kit
def test_kit_board_with_a_neck_structure_per_region_passes(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Regions with the same neck geometry may share a structure or each
    have one of their own."""
    code, out = grade(capsys, write(tmp_path, kit_source(KIT_NECK_PER_REGION)), KIT_CSV)
    assert code == 0, out[-3000:]


@needs_kit
def test_renamed_kit_board_passes(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    source = renamed_kit_source()
    assert source.count("(Via):") >= 12
    assert not re.search(r"\bHDISubstrate\b|\bDRS_100\b|MicroVia_L", source)
    code, out = grade(capsys, write(tmp_path, source), KIT_CSV)
    assert code == 0, out[-3000:]


def differential_name(source: str) -> str:
    """The (renamed) attribute that holds the kit's differential structure."""
    found = re.search(
        r"^    (\w+) = DifferentialRoutingStructure\(", source, re.MULTILINE
    )
    assert found is not None
    return found.group(1)


# Mutations are written against the kit board's code and values, never its
# comments or docstrings, so rewording the kit's prose does not break them.

Mutation = Callable[[str], str]


def replace_once(old: str, new: str) -> Mutation:
    def mutate(source: str) -> str:
        assert old in source, old
        return source.replace(old, new, 1)

    return mutate


def sub_once(pattern: str, replacement: str) -> Mutation:
    def mutate(source: str) -> str:
        assert re.search(pattern, source), pattern
        return re.sub(pattern, replacement, source, count=1)

    return mutate


def add_to_substrate(statement: str) -> Mutation:
    """Append a class-body statement to the kit's ``Substrate`` subclass.
    ``{diff}`` names its differential structure attribute."""

    def mutate(source: str) -> str:
        header = re.search(r"^class \w+\(Substrate\):\n", source, re.MULTILINE)
        assert header is not None
        after = re.search(r"^\S", source[header.end() :], re.MULTILINE)
        assert after is not None
        at = header.end() + after.start()
        text = statement.replace("{diff}", differential_name(source))
        return source[:at] + text + "\n\n" + source[at:]

    return mutate


STANDARD_STRUCTURE = """    standard = RoutingStructure(
        name="standard",
        impedance=60.99 * ohm,
        layers=_se_layers(
            MICROSTRIP_LAYERS,
            width=0.1500,
            clearance=0.1500,
            eps_eff=2.4316,
            insertion_loss=0.00907,
        ),
    )
"""
"""A structure for the JS1 STANDARD row, at its microstrip Modelled_Z_ohm."""


@needs_kit
@pytest.mark.parametrize(
    ("mutate", "owner"),
    [
        (
            replace_once("hole_diameter = 0.125", "hole_diameter = 0.130"),
            "TestVias::test_geometry_matches_csv",
        ),
        (
            replace_once("thickness = 0.8000", "thickness = 0.8100"),
            "TestStackup::test_thickness_totals_match_document",
        ),
        (
            replace_once(
                "REF_PLANE_WIDTH = 3 * 0.1000", "REF_PLANE_WIDTH = 3 * 0.1100"
            ),
            "TestRoutingStructures::test_reference_plane_widths_are_the_skill_default",
        ),
        (
            replace_once("min_copper_width = 0.050", "min_copper_width = 0.060"),
            "TestFabRules::test_all_required_constraints_present_and_match_csv",
        ),
        (
            # D-BU's Dk in place of the report's Eps_eff on SE-DEFAULT L1/L20.
            replace_once("eps_eff=2.4316,", "eps_eff=2.96,"),
            "TestRoutingStructures::test_geometry_matches_csv",
        ),
        (
            # UV-6 is drilled from L20; this one starts on L19.
            replace_once(
                "start_layer = -1\n        stop_layer = -2\n",
                "start_layer = -2\n        stop_layer = -1\n",
            ),
            "TestVias::test_geometry_matches_csv",
        ),
        (
            add_to_substrate("    hoisted = {diff}.uncoupled_region\n"),
            "TestRoutingStructures::test_uncoupled_rows_are_not_standalone_structures",
        ),
        (
            sub_once(r'(material_name = "[^"]*?)Astra MT77 ', r"\1"),
            "TestStackup::test_material_names_carry_the_csv_product",
        ),
        (
            add_to_substrate(STANDARD_STRUCTURE),
            "TestRoutingStructures::test_uncontrolled_rows_are_not_modelled",
        ),
        (
            sub_once(r'name="L1(?!\d)', 'name="L10'),
            "TestStackup::test_copper_layer_names_carry_the_layer_id",
        ),
        (
            replace_once('name="L1-Signal"', 'name="L12"'),
            "TestStackup::test_copper_layer_names_carry_the_layer_id",
        ),
        (
            replace_once('name="L1-Signal"', 'name="Top Signal"'),
            "TestStackup::test_copper_layer_names_carry_the_layer_id",
        ),
        (
            replace_once('name="L1-Signal"', 'name="TopL1"'),
            "TestStackup::test_copper_layer_names_carry_the_layer_id",
        ),
        (
            # No roughness scalar, and a docstring that states no Rz.
            replace_once(
                "    roughness = 0.0060\n", '    __doc__ = "No roughness stated."\n'
            ),
            "TestStackup::test_material_properties_match_csv",
        ),
        (
            # The scalar holds matte Rz only; the drum side is then lost.
            replace_once(", drum 3.5 um -> roughness", " -> roughness"),
            "TestStackup::test_material_properties_match_csv",
        ),
        (
            # The shared single-ended neck structure at the line width.
            sub_once(
                r'(?s)(name="neck region \(SE[^"]*\)".*?MICROSTRIP_LAYERS,'
                r"\n\s+width=)0\.1500",
                r"\g<1>0.3179",
            ),
            "TestNeckRegions::test_each_neck_region_has_a_structure_of_its_own",
        ),
        (
            # The shared single-ended neck structure with the stripline neck
            # clearance of the line.
            sub_once(
                r'(?s)(name="neck region \(SE[^"]*\)".*?STRIPLINE_LAYERS,'
                r"\n\s+width=0\.0762,\n\s+clearance=)0\.0762",
                r"\g<1>0.1752",
            ),
            "TestNeckRegions::test_each_neck_region_has_a_structure_of_its_own",
        ),
        (
            # The shared single-ended neck structure on the microstrip layers only.
            sub_once(
                r'(?s)(name="neck region \(SE[^"]*\)".*?\),\n)'
                r"            \*\*_se_layers\(\n                STRIPLINE_LAYERS,.*?\),\n",
                r"\g<1>",
            ),
            "TestNeckRegions::test_each_neck_region_has_a_structure_of_its_own",
        ),
        (
            # DIFF-100's neck region with the stripline neck gap of the pair.
            replace_once(
                "width=0.0635,\n                pair_gap=0.0635,",
                "width=0.0635,\n                pair_gap=0.0762,",
            ),
            "TestNeckRegions::test_each_neck_region_has_a_structure_of_its_own",
        ),
        (
            # The single-ended neck structure left out.
            sub_once(
                r"(?ms)^    \w+ = RoutingStructure\(\n        "
                r'name="neck region \(SE[^"]*\)".*?^    \)\n',
                "",
            ),
            "TestNeckRegions::test_each_neck_region_has_a_structure_of_its_own",
        ),
        (
            # A NeckDown built and never attached is still a NeckDown.
            add_to_substrate(
                "    spare = RoutingStructure.NeckDown(trace_width=0.1500)\n"
            ),
            "TestNeckRegions::test_no_neck_down_in_the_file",
        ),
    ],
    ids=[
        "one wrong hole",
        "a wrong core",
        "a wrong plane width",
        "a wrong fab rule",
        "velocity from Dk",
        "a bottom-side laser via started on the wrong layer",
        "a hoisted uncoupled structure",
        "a material name without its Product",
        "the STANDARD row modelled",
        "L1 named as L10",
        "L1 named as L12",
        "L1 named with no layer id",
        "L1 named with a letter before its id",
        "roughness in neither scalar nor docstring",
        "the roughness scalar set and drum Rz dropped",
        "a neck region at the line width",
        "a neck region with the line clearance",
        "a neck structure missing a geometry's layers",
        "a differential neck region with the wrong gap",
        "the single-ended neck regions with no structure",
        "an unattached NeckDown",
    ],
)
def test_renamed_kit_board_with_one_wrong_value_fails(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, mutate: Mutation, owner: str
) -> None:
    source = mutate(renamed_kit_source())
    code, out = grade(capsys, write(tmp_path, source), KIT_CSV)
    assert code == 1, out[-3000:]
    assert owner in out


def rz_on_a_foil_base_class(source: str) -> str:
    """The CU-PLN class built on a foil base class that states its Rz, with no
    roughness scalar anywhere."""
    pattern = re.compile(
        r"^class (\w+)\(Conductor\):\n(?=(?:(?:    .*)?\n)*?    roughness = 0\.0060\n)",
        re.MULTILINE,
    )
    assert len(pattern.findall(source)) == 1
    base = 'class RoughFoil(Conductor):\n    """Rz matte 6.0 um, drum 3.5 um."""\n\n\n'
    source = pattern.sub(lambda m: base + f"class {m.group(1)}(RoughFoil):\n", source)
    return source.replace("    roughness = 0.0060\n", "", 1)


@needs_kit
@pytest.mark.parametrize(
    "mutate",
    [
        sub_once(r'name="L(\d+)-', r'name="L\1 '),
        sub_once(r'name="L(\d+)-', r'name="L\1_'),
        # The layer id anywhere in the name, with no letter or digit before it.
        replace_once('name="L1-Signal"', 'name="Top (L1)"'),
        replace_once('name="L2-GND"', 'name="GND L2"'),
        replace_once('name="L3-Signal"', 'name="L3_GND"'),
        # The CU-PLN Rz values from testdata, stated in the docstring in place
        # of the roughness scalar.
        replace_once(
            "    roughness = 0.0060\n",
            '    __doc__ = "Rz matte 6.0 um, drum 3.5 um."\n',
        ),
        rz_on_a_foil_base_class,
    ],
    ids=[
        "layer names with a space",
        "layer names with an underscore",
        "the layer id in brackets after a function word",
        "the layer id after a function word",
        "the layer id before an underscore",
        "Rz in the docstring and no roughness scalar",
        "Rz on a foil base class and no roughness scalar",
    ],
)
def test_renamed_kit_board_written_another_way_passes(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, mutate: Mutation
) -> None:
    code, out = grade(capsys, write(tmp_path, mutate(renamed_kit_source())), KIT_CSV)
    assert code == 0, out[-3000:]


def via_class_blocks(source: str) -> list[re.Match[str]]:
    """Each nested ``Via`` class in the kit substrate, header to last body line."""
    return list(
        re.finditer(
            r"^    class \w+\(Via\):\n(?:(?:        .*)?\n)*", source, re.MULTILINE
        )
    )


KIT_TH_VIA = """        start_layer = Side.Top
        stop_layer = Side.Bottom
        diameter = 0.650
        hole_diameter = 0.350
        filled = True
        tented = True
"""
"""The kit's through via, whose report row is ``Resin,Yes,Both``."""


def edit_report(lines: list[str], via_id: str, row: str | None) -> list[str]:
    """``lines`` with the VIAS row for ``via_id`` replaced by ``row``, or
    dropped when ``row`` is None."""
    out: list[str] = []
    found = 0
    for line in lines:
        if line.startswith(via_id + ","):
            found += 1
            if row is not None:
                out.append(row)
            continue
        out.append(line)
    assert found == 1, via_id
    return out


@needs_kit
@pytest.mark.parametrize(
    "edit",
    ["through via unfilled and tented on top only", "one laser via dropped"],
)
def test_kit_report_and_board_edited_together_pass(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, edit: str
) -> None:
    """The grader follows the report it is given: change a report and its
    board the same way, and they still agree."""
    source = renamed_kit_source()
    lines = KIT_CSV.read_text(encoding="utf-8").splitlines()
    if edit == "one laser via dropped":
        row = next(line for line in lines if line.startswith("UV-5,"))
        assert ",Laser,L5,L6," in row
        lines = edit_report(lines, "UV-5", None)
        # UV-5 is the laser via from L5 to L6: signed indices 4 and 5.
        blocks = [
            block
            for block in via_class_blocks(source)
            if "LaserDrill\n" in block.group()
            and "start_layer = 4\n" in block.group()
            and "stop_layer = 5\n" in block.group()
        ]
        assert len(blocks) == 1
        source = source[: blocks[0].start()] + source[blocks[0].end() :]
    else:
        th_row = next(line for line in lines if line.startswith("TH-1,"))
        assert ",Resin,Yes,Both," in th_row
        lines = edit_report(
            lines, "TH-1", th_row.replace(",Resin,Yes,Both,", ",None,No,Top,")
        )
        assert source.count(KIT_TH_VIA) == 1
        source = source.replace(
            KIT_TH_VIA,
            KIT_TH_VIA.replace("filled = True", "filled = False").replace(
                "tented = True", "tented = Side.Top"
            ),
        )
    report = tmp_path / "report.csv"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, out = grade(capsys, write(tmp_path, source), report)
    assert code == 0, out[-3000:]


@needs_kit
def test_kit_board_fails_the_case_report(capsys: pytest.CaptureFixture[str]) -> None:
    """Copying the kit board does not pass the case: it fails in the stackup,
    via, fab-rule and routing tests."""
    assert KIT_BOARD is not None
    code, out = grade(capsys, KIT_BOARD, CASE_CSV)
    assert code == 1, out[-3000:]
    for owner in (
        "TestStackup::",
        "TestVias::",
        "TestFabRules::",
        "TestRoutingStructures::",
    ):
        assert re.search(rf"FAILED.*{owner}", out), owner


@pytest.mark.parametrize(
    "argv",
    [
        ["grade_substrate.py"],
        ["grade_substrate.py", "board.py"],
        ["grade_substrate.py", "", str(CASE_CSV)],
        ["grade_substrate.py", "board.py", " "],
        ["grade_substrate.py", "board.py", "no-such-report.csv"],
    ],
    ids=["no arguments", "no CSV", "blank board", "blank CSV", "CSV not a file"],
)
def test_usage_errors_exit_2(argv: list[str]) -> None:
    assert grade_substrate.main(argv) == 2


def test_missing_board_is_red(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, out = grade(capsys, tmp_path / "board.py", CASE_CSV)
    assert code == 1
    assert "does not exist" in out


MINIMAL_SUBSTRATE = """
from jitx.substrate import Substrate


class Minimal(Substrate):
    pass
"""


@needs_jitx
@pytest.mark.parametrize(
    ("unset", "blank", "message"),
    [
        ("SUBSTRATE_FILE", None, "SUBSTRATE_FILE is not set"),
        ("FAB_CSV", None, "FAB_CSV is not set"),
        (None, "SUBSTRATE_FILE", "SUBSTRATE_FILE is set but empty"),
        (None, "FAB_CSV", "FAB_CSV is set but empty"),
        (None, "SUBSTRATE_CLASS", "SUBSTRATE_CLASS is set but empty"),
    ],
    ids=[
        "SUBSTRATE_FILE unset",
        "FAB_CSV unset",
        "SUBSTRATE_FILE blank",
        "FAB_CSV blank",
        "SUBSTRATE_CLASS blank",
    ],
)
def test_grader_refuses_unset_or_blank_settings(
    tmp_path: Path, unset: str | None, blank: str | None, message: str
) -> None:
    """Run directly, the grader stops at collection rather than grading a
    default; it has none."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("SUBSTRATE_FILE", "SUBSTRATE_CLASS", "FAB_CSV", "PYTEST_ADDOPTS")
    }
    environment["SUBSTRATE_FILE"] = str(write(tmp_path, MINIMAL_SUBSTRATE))
    environment["FAB_CSV"] = str(CASE_CSV)
    if unset is not None:
        del environment[unset]
    if blank is not None:
        environment[blank] = " "
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(GRADER)],
        cwd=CHECKS,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 2, done.stdout[-3000:]
    assert message in done.stdout + done.stderr


# A two-layer report and board, small enough to read at a glance. Graded on
# the stackup, via and reference-plane tests, they show that the grader takes
# the layer count from the report: a 20-layer count from the JS1 report, in
# the stackup tests or in the layer arithmetic that numbers a bottom-side via
# end or a plane written as a negative index, turns them red.

TOY_REPORT = """SECTION,DOCUMENT
Field,Value,Unit,Notes
Layer count,2,copper layers,
Board size,20.0 x 10.0,mm,1.0 mm corner radius
Overall thickness,1.070,mm,
Finished thickness,1.070,mm,

SECTION,STACKUP
Seq,Type,Layer,Function,Material_ID,Thickness_mil,Thickness_mm,Dk,Df
1,Copper,L1,Signal,CU,1.38,0.0350,,
2,Dielectric,,Core,D-CORE,39.37,1.0000,4.00,0.0200
3,Copper,L2,Plane - GND,CU,1.38,0.0350,,

SECTION,VIAS
Via_ID,Structure,Drill,From_layer,To_layer,Finished_hole_mil,Finished_hole_mm,Pad_mil,Pad_mm,Depth_mm,Aspect_ratio,Annular_ring_mm,Fill,Capped,Tented,Via_in_pad,Notes
TH-1,Through,Mechanical,L1,L2,11.81,0.300,23.62,0.600,1.070,3.57,0.150,None,No,Both,No,

SECTION,IMPEDANCE
Structure_ID,Controlled,Type,Target_Z_ohm,Tolerance_pct,Layers,Geometry,Line_width_mil,Line_width_mm,Pair_gap_mm,Clearance_mm,Ref_layers,Modelled_Z_ohm,Eps_eff,Delay_ps_per_mm,Loss_dB_per_mm,Neck_width_mm,Neck_gap_mm,Neck_clearance_mm,Neck_modelled_Z_ohm
SE-50,Yes,Single-ended,50,10,L1,Microstrip,7.87,0.2000,,0.4000,L2 for L1,50.00,3.0000,5.7775,0.01000,,,,
"""

TOY_BOARD = """
from jitx.layerindex import Side
from jitx.si import RoutingStructure
from jitx.stackup import Conductor, Dielectric, Stackup
from jitx.substrate import FabricationConstraints, Substrate
from jitx.units import ohm
from jitx.via import Via, ViaType
from jitxlib.physics import phase_velocity


class Core(Dielectric):
    dielectric_coefficient = 4.00
    loss_tangent = 0.0200
    thickness = 1.0000


class Foil(Conductor):
    thickness = 0.0350


class ToyStackup(Stackup):
    top = Foil(name="L1-Signal")
    core = Core(name="Core")
    bottom = Foil(name="L2-GND")


class ToyRules(FabricationConstraints):
    min_copper_width = 0.100
    min_copper_copper_space = 0.100
    min_copper_hole_space = 0.200
    min_copper_edge_space = 0.300
    min_annular_ring = 0.100
    min_drill_diameter = 0.200
    min_pitch_leaded = 0.500
    min_pitch_bga = 0.500
    max_board_width = 400.0
    max_board_height = 400.0
    min_silkscreen_width = 0.150
    min_silk_solder_mask_space = 0.150
    min_silkscreen_text_height = 0.800
    solder_mask_registration = 0.050
    min_soldermask_opening = 0.100
    min_soldermask_bridge = 0.100
    min_th_pad_expand_outer = 0.100
    min_hole_to_hole = 0.300
    min_pth_pin_solder_clearance = 0.200


class Toy(Substrate):
    stackup = ToyStackup()
    constraints = ToyRules()

    class Through(Via):
        type = ViaType.MechanicalDrill
        start_layer = Side.Top
        stop_layer = Side.Bottom
        diameter = 0.600
        hole_diameter = 0.300
        filled = False
        tented = True

    # The plane is written as -1, which only the report's layer count makes L2.
    fifty = RoutingStructure(
        name="50 ohm",
        impedance=50 * ohm,
        layers={
            0: RoutingStructure.Layer(
                trace_width=0.2000,
                clearance=0.4000,
                velocity=phase_velocity(3.0000),
                insertion_loss=0.01000,
            ).reference({-1: 3.0})
        },
    )
"""

TOY_DATACLASS = (
    """from __future__ import annotations

from dataclasses import dataclass
"""
    + TOY_BOARD
    + """

@dataclass(frozen=True)
class Note:
    text: str
"""
)
"""The toy board with string annotations and a dataclass, which is how a
correct board imports differently from a plain module."""

TOY_TESTS = (
    "test_layer_count_and_order or test_copper_layer_names_carry_the_layer_id"
    " or test_thickness_totals_match_document"
    " or test_inventory_is_exactly_the_csv_via_table"
    " or test_laser_vias_are_exactly_the_laser_rows"
    " or test_geometry_matches_csv or test_layer_coverage"
    " or test_reference_planes_match_csv_ref_layers"
)


def grade_toy(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    board_source: str,
    *,
    report_source: str = TOY_REPORT,
    tests: str = TOY_TESTS,
) -> tuple[int, str]:
    report = tmp_path / "toy.csv"
    report.write_text(report_source, encoding="utf-8")
    board = write(tmp_path, board_source)
    argv = ["grade_substrate.py", str(board), str(report), "-k", tests]
    code = grade_substrate.main(argv)
    return code, capsys.readouterr().out


@needs_jitx
def test_grader_reads_the_layer_count_from_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, out = grade_toy(capsys, tmp_path, TOY_BOARD)
    assert code == 0, out[-3000:]
    assert "9 passed" in out


SKIP_LAYER_REPORT_EDITS = [
    ("Layer count,2,", "Layer count,3,"),
    ("Overall thickness,1.070,", "Overall thickness,1.205,"),
    ("Finished thickness,1.070,", "Finished thickness,1.205,"),
    (
        (
            "2,Dielectric,,Core,D-CORE,39.37,1.0000,4.00,0.0200\n"
            "3,Copper,L2,Plane - GND,CU,1.38,0.0350,,\n"
        ),
        (
            "2,Dielectric,,Prepreg,D-PP,3.94,0.1000,4.00,0.0200\n"
            "3,Copper,L2,Signal,CU,1.38,0.0350,,\n"
            "4,Dielectric,,Core,D-CORE,39.37,1.0000,4.00,0.0200\n"
            "5,Copper,L3,Plane - GND,CU,1.38,0.0350,,\n"
        ),
    ),
    (
        ",L1,L2,11.81,0.300,23.62,0.600,1.070,3.57,",
        ",L1,L3,11.81,0.300,23.62,0.600,1.205,4.02,",
    ),
    (",L2 for L1,", ",L3 for L1,"),
]
"""Edits that move the toy report's L1 reference plane to L3: a 0.1000 mm
prepreg, L2's 0.0350 mm copper, then the 1.0000 mm core."""


@needs_jitx
@pytest.mark.parametrize(
    ("height", "code"),
    [(0.1000 + 1.0000, 0), (0.1000 + 0.0350 + 1.0000, 1)],
    ids=["the two dielectrics", "the copper between counted too"],
)
def test_a_plane_two_dielectrics_away_is_3x_the_dielectric_alone(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, height: float, code: int
) -> None:
    """The skill sums the dielectric rows between a line and a plane further
    than one away; the grader holds the board to that sum, not to the full
    distance with the copper between."""
    board_edits = [
        (
            "class Foil(Conductor):",
            (
                "class Prepreg(Dielectric):\n"
                "    dielectric_coefficient = 4.00\n"
                "    loss_tangent = 0.0200\n"
                "    thickness = 0.1000\n\n\n"
                "class Foil(Conductor):"
            ),
        ),
        (
            '    core = Core(name="Core")\n    bottom = Foil(name="L2-GND")\n',
            (
                '    prepreg = Prepreg(name="Prepreg")\n'
                '    middle = Foil(name="L2-Signal")\n'
                '    core = Core(name="Core")\n'
                '    bottom = Foil(name="L3-GND")\n'
            ),
        ),
        (
            "    # The plane is written as -1, which only the report's layer count makes L2.\n",
            "    # L3 is two dielectrics below L1, with L2's copper between.\n",
        ),
        (".reference({-1: 3.0})", f".reference({{2: {3 * height:.4f}}})"),
    ]
    report, board = TOY_REPORT, TOY_BOARD
    for old, new in SKIP_LAYER_REPORT_EDITS:
        report = replace_once(old, new)(report)
    for old, new in board_edits:
        board = replace_once(old, new)(board)
    result, out = grade_toy(
        capsys,
        tmp_path,
        board,
        report_source=report,
        tests="test_reference_plane_widths_are_the_skill_default",
    )
    assert result == code, out[-3000:]
    if code == 0:
        assert "1 passed" in out
    else:
        assert "L1 to plane L3: STACKUP Thickness_mm puts 1.1000 mm" in out


@needs_jitx
def test_coloured_pytest_output_still_grades(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PY_COLORS", "1")
    code, out = grade_toy(capsys, tmp_path, TOY_BOARD)
    assert code == 0, out[-3000:]


@needs_jitx
def test_board_with_string_annotations_and_a_dataclass_imports(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Dataclasses under ``from __future__ import annotations`` look their
    module up in ``sys.modules``; the pre-flight must register it."""
    code, out = grade_toy(capsys, tmp_path, TOY_DATACLASS)
    assert code == 0, out[-3000:]
    assert "does not import" not in out


@needs_jitx
def test_a_board_that_silences_warnings_still_grades(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The grader reports what it graded through a warning; a board that
    filters warnings at import must not hide it."""
    source = 'import warnings\nwarnings.filterwarnings("ignore")\n' + TOY_BOARD
    code, out = grade_toy(capsys, tmp_path, source)
    assert code == 0, out[-3000:]


HANG = """
import os, subprocess, sys
from pathlib import Path

if {when}:
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    Path(__file__).with_name("pids.txt").write_text(f"{{os.getpid()}} {{sleeper.pid}}")
{board}
if {when}:
    # Iterating a stackup outside an instantiation context never returns.
    assert len(list(ToyStackup().conductors)) == 2
"""


def gone(pid: int) -> bool:
    """Whether no process has this id, allowing a moment for reaping."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def recorded_pids(directory: Path) -> list[int]:
    """The board's process and its sleeper, as the board wrote them."""
    record = directory / "pids.txt"
    if not record.is_file():
        return []
    return [int(pid) for pid in record.read_text(encoding="utf-8").split()]


def survivors(pids: list[int]) -> list[int]:
    """The recorded processes still running, each killed so none outlives the
    test; the caller asserts on the list."""
    alive = [pid for pid in pids if not gone(pid)]
    for pid in alive:
        os.kill(pid, 9)
    return alive


@needs_jitx
@pytest.mark.parametrize(
    ("when", "stage"),
    [("True", "the import pre-flight"), ('os.environ.get("FAB_CSV")', "the grader")],
    ids=["hangs at import", "hangs under the grader"],
)
def test_a_board_that_hangs_is_red_and_leaves_nothing_running(
    tmp_path: Path, when: str, stage: str
) -> None:
    """Run in its own interpreter under a bound of its own, so a broken
    timeout fails this test instead of hanging the suite."""
    report = tmp_path / "toy.csv"
    report.write_text(TOY_REPORT, encoding="utf-8")
    board = write(tmp_path, HANG.format(when=when, board=TOY_BOARD))
    command = [sys.executable, str(GRADE), str(board), str(report), "--timeout", "10"]
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=60, check=False
        )
    except subprocess.TimeoutExpired:
        done = None
    left = survivors(recorded_pids(tmp_path))
    assert done is not None, "grade_substrate.py did not stop within 60 s"
    assert done.returncode == 1, done.stdout[-3000:]
    assert f"FAIL  {stage} did not finish within 10 s" in done.stdout
    assert len(recorded_pids(tmp_path)) == 2
    assert left == [], f"processes {left} were still running"


ESCAPES_THE_GROUP = """
import os, sys, time

if os.fork() == 0:
    os.setsid()
    with open(sys.argv[1], "w") as record:
        record.write(str(os.getpid()))
    time.sleep(60)
    os._exit(0)
os._exit(0)
"""
"""Exits at once, leaving a process in a session of its own that holds the
child's output open."""


def test_a_child_whose_group_cannot_be_signalled_is_timed_out(
    tmp_path: Path,
) -> None:
    """The wait runs to the timeout, since the escaped process holds the
    output open, and the child's group then holds only the unreaped child,
    which macOS refuses to signal (PermissionError). run_child kills what it
    can and reports the timeout rather than raising."""
    script = tmp_path / "escape.py"
    script.write_text(ESCAPES_THE_GROUP, encoding="utf-8")
    record = tmp_path / "escaped.pid"
    try:
        done = grade_substrate.run_child(
            [sys.executable, str(script), str(record)], timeout=2
        )
    finally:
        if record.is_file():
            survivors([int(record.read_text(encoding="utf-8"))])
    assert done is None
    assert record.is_file(), "the escaping process never started"


SIGNALLED = """
import os, subprocess, sys, time
from pathlib import Path

if {when}:
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    Path(__file__).with_name("pids.txt").write_text(f"{{os.getpid()}} {{sleeper.pid}}")
    time.sleep(120)
"""


@needs_jitx
@pytest.mark.parametrize(
    "when",
    ["True", 'os.environ.get("FAB_CSV")'],
    ids=["hanging at import", "hanging under the grader"],
)
@pytest.mark.parametrize(
    ("signum", "to_group"),
    [(15, False), (1, False), (9, False), (9, True)],
    ids=["SIGTERM", "SIGHUP", "SIGKILL", "SIGKILL to its group"],
)
def test_no_child_outlives_a_signalled_grader(
    tmp_path: Path, when: str, signum: int, to_group: bool
) -> None:
    """However grade_substrate.py is stopped, what it started stops too."""
    board = write(tmp_path, SIGNALLED.format(when=when))
    grader = subprocess.Popen(
        [sys.executable, str(GRADE), str(board), str(CASE_CSV)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 60
        while len(recorded_pids(tmp_path)) < 2 and time.monotonic() < deadline:
            time.sleep(0.1)
        assert len(recorded_pids(tmp_path)) == 2, "the board never started"
        if to_group:
            os.killpg(grader.pid, signum)
        else:
            os.kill(grader.pid, signum)
        grader.wait(timeout=30)
    finally:
        if grader.poll() is None:
            grader.kill()
            grader.wait()
        left = survivors(recorded_pids(tmp_path))
    assert left == [], f"processes {left} outlived grade_substrate.py"
    # A signal it can catch, it handles: it cleans up and exits 128 + signum,
    # rather than dying and leaving the cleanup to its children.
    assert grader.returncode == (-signum if signum == 9 else 128 + signum)


EXITS_AT_IMPORT = """import os

if __name__ == "_candidate_preflight":
    print({line!r}, flush=True)
    os._exit({code})
"""
"""A board that ends the import pre-flight itself, with a line of its own."""

FORGED = (
    "ERROR  a library the candidate imports does not import: "
    "ModuleNotFoundError: No module named 'jitx_rf'"
)
"""An environment line a board writes itself, from code that runs late."""

FORGED_AT_EXIT = f"""import atexit
import os


def _forge() -> None:
    os.write(1, b"\\n{FORGED}\\n")
    os._exit(3)


atexit.register(_forge)
EXTRA = UNDEFINED_NAME
"""
"""A board that fails to import, with an exit handler that would end the
pre-flight on a forged environment line."""

FORGED_FROM_A_THREAD = f"""import os
import threading
import time


def _forge() -> None:
    time.sleep(2)
    os.write(1, b"\\n{FORGED}\\n")
    os._exit(3)


threading.Thread(target=_forge).start()
EXTRA = UNDEFINED_NAME
"""
"""The same from a thread, which the interpreter waits for at exit."""

UNDEFINED = "FAIL  candidate does not import: NameError: name 'UNDEFINED_NAME' is not"

RED_AT_IMPORT = [
    pytest.param(
        "from jitx.dielectric import Laminate\n",
        "FAIL  candidate does not import: jitx.dielectric (at board.py:1)",
        id="a module that does not exist",
    ),
    pytest.param(
        "from jitx.units import kiloohm_typo\n",
        "FAIL  candidate does not import: cannot import name 'kiloohm_typo' "
        "from 'jitx.units' (at board.py:1)",
        id="a name that does not exist",
    ),
    pytest.param(
        "raise RuntimeError(\"sh: 1: pyright: not found; No module named 'jitx.unitz'\")\n",
        "FAIL  candidate does not import: RuntimeError: sh: 1: pyright: missing",
        id="a message in environment wording",
    ),
    pytest.param(
        "print(\"note: No module named 'jitx_rf_helpers'; using built-in defaults\")\n"
        "EXTRA = UNDEFINED_NAME\n",
        "FAIL  candidate does not import: NameError: name 'UNDEFINED_NAME' is not "
        "defined (at board.py:2)",
        id="environment wording printed before its own error",
    ),
    pytest.param(
        EXITS_AT_IMPORT.format(line="ERROR  No module named 'jitx_rf_helpers'", code=3),
        "FAIL  the import pre-flight exited 3 on board.py without one of its own "
        "environment lines",
        id="an exit 3 with an ERROR line of its own",
    ),
    pytest.param(
        EXITS_AT_IMPORT.format(line="No module named 'jitx_rf_helpers'", code=7),
        "FAIL  the import pre-flight gave no verdict on board.py (exit 7)",
        id="another exit code in environment wording",
    ),
    pytest.param(FORGED_AT_EXIT, UNDEFINED, id="an exit handler that forges an ERROR"),
    pytest.param(FORGED_FROM_A_THREAD, UNDEFINED, id="a thread that forges an ERROR"),
]
"""(what the board starts with, the line grade_substrate.py prints for it)."""


@needs_jitx
@pytest.mark.parametrize(("start", "line"), RED_AT_IMPORT)
def test_a_board_that_does_not_import_is_red(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, start: str, line: str
) -> None:
    """Whatever stops the board importing in its own code is the candidate's
    fault: a red, with nothing in it an eval harness reads as a missing
    environment, whatever the board printed or exited with."""
    code, out = grade(capsys, write(tmp_path, start + MINIMAL_SUBSTRATE), CASE_CSV)
    assert code == 1
    assert line in out, out
    for wording in import_candidate.ENVIRONMENT_WORDING:
        assert not re.search(wording, out, re.IGNORECASE), (wording, out)


@needs_jitx
def test_what_the_board_prints_while_graded_is_scrubbed(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A board that imports, then prints environment wording while the
    grader's tests run, is a red the eval harness still reads as one: the
    pytest output that quotes it is scrubbed."""
    board = write(
        tmp_path,
        MINIMAL_SUBSTRATE
        + "\n    def __init__(self) -> None:\n"
        + "        print(\"No module named 'jitx_rf_helpers'\")\n"
        + "        super().__init__()\n",
    )
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "no module called 'jitx_rf_helpers'" in out, out
    for wording in import_candidate.ENVIRONMENT_WORDING:
        assert not re.search(wording, out, re.IGNORECASE), (wording, out)


WRITES_THROUGH = """import sys


class _Through:
    def __init__(self):
        self.pending = []

    def write(self, text):
        self.pending.append(text)
        return len(text)

    def flush(self):
        sys.__stdout__.write("".join(self.pending))
        self.pending.clear()

    def __getattr__(self, name):
        return getattr(sys.__stdout__, name)


sys.stdout = _Through()
print("loading brokenlib")
"""
"""A replacement sys.stdout that holds what is printed until it is flushed,
then hands it to sys.__stdout__, which holds it until that is flushed."""

STDOUT_BEFORE_A_LIBRARY = [
    pytest.param("", id="nothing else"),
    pytest.param(
        "import io\nimport sys\n\nsys.stdout = io.StringIO()\n",
        id="sys.stdout replaced",
    ),
    pytest.param(
        'import atexit\n\natexit.register(print, "board: done")\n',
        id="an exit handler that prints",
    ),
    pytest.param(WRITES_THROUGH, id="sys.stdout replaced by one that writes through"),
    pytest.param(
        "import os\n\nos.dup2(os.open(os.devnull, os.O_WRONLY), 1)\n",
        id="file descriptor 1 pointed at the null device",
    ),
    pytest.param("import os\n\nos.close(1)\n", id="file descriptor 1 closed"),
    pytest.param(
        "import threading\n\n\n"
        "def _spin():\n"
        "    while True:\n"
        '        print("tick", flush=True)\n\n\n'
        "threading.Thread(target=_spin, daemon=True).start()\n",
        id="a thread that prints and flushes in a tight loop",
    ),
]
"""What a board does before it imports a library that does not import."""


@needs_jitx
@pytest.mark.parametrize("head", STDOUT_BEFORE_A_LIBRARY)
def test_an_import_that_fails_inside_a_library_is_the_environment(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    head: str,
) -> None:
    """Nothing in the candidate's own files is wrong, so it is not a red. The
    pre-flight's environment line reaches the grader, last, whatever the
    board did to stdout before the library failed, and nothing the board set
    up to run at exit runs after it."""
    library = tmp_path / "library"
    library.mkdir()
    (library / "brokenlib.py").write_text(
        "import a_dependency_that_is_not_installed\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(library))
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    board = write(candidate, head + "import brokenlib\n" + MINIMAL_SUBSTRATE)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1, out
    assert (
        out.strip()
        .splitlines()[-1]
        .startswith(
            "ERROR  a library the candidate imports does not import: ModuleNotFoundError: "
            "No module named 'a_dependency_that_is_not_installed'"
        )
    ), out
    assert "candidate does not import" not in out


@needs_jitx
def test_a_helper_beside_the_board_with_a_wrong_import_is_red(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A file beside the board is the candidate's own, wherever the import
    fails inside it."""
    (tmp_path / "helpers.py").write_text(
        "from jitx.dielectric import Laminate\n", encoding="utf-8"
    )
    board = write(tmp_path, "import helpers\n" + MINIMAL_SUBSTRATE)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "FAIL  candidate does not import: jitx.dielectric (at board.py:1)" in out


@needs_jitx
def test_a_helper_the_board_puts_on_the_path_is_the_candidates(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A directory the board adds to sys.path holds the candidate's own files,
    even outside the board's directory."""
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "shared_materials.py").write_text(
        "from jitx.dielectric import Laminate\n", encoding="utf-8"
    )
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    board = write(
        candidate,
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'shared'))\n"
        "import shared_materials\n" + MINIMAL_SUBSTRATE,
    )
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "FAIL  candidate does not import: jitx.dielectric (at board.py:3)" in out


def outside_root_board(tmp_path: Path) -> Path:
    """A board in tmp_path/candidate that loads, by path, a module in
    tmp_path/outside whose import fails. Returns the board."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "loose_materials.py").write_text(
        "from jitx.dielectric import Laminate\n", encoding="utf-8"
    )
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    return write(
        candidate,
        "import importlib.util, pathlib\n"
        "path = pathlib.Path(__file__).parent.parent / 'outside' / 'loose_materials.py'\n"
        "spec = importlib.util.spec_from_file_location('loose_materials', path)\n"
        "assert spec is not None and spec.loader is not None\n"
        "spec.loader.exec_module(importlib.util.module_from_spec(spec))\n"
        + MINIMAL_SUBSTRATE,
    )


@needs_jitx
def test_a_file_outside_every_root_is_the_candidates(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A file under none of the roots the pre-flight knows (the board's
    directory, a directory the board added to sys.path, sys.path before the
    board ran, the interpreter's library directories, an editable install's
    project directory) is counted as the candidate's: here the board loaded it
    by path, so an import that fails in it is a red."""
    board = outside_root_board(tmp_path)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "FAIL  candidate does not import: jitx.dielectric (at board.py:5)" in out
    assert "ERROR" not in out
    preflight = subprocess.run(
        [sys.executable, str(grade_substrate.PREFLIGHT), str(board)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert preflight.returncode == 1, preflight.stdout + preflight.stderr


EDITABLE_FINDER = """import sys
from importlib.util import spec_from_file_location

MAPPING = {mapping!r}


class _EditableFinder:
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        if fullname not in MAPPING:
            return None
        package = MAPPING[fullname]
        return spec_from_file_location(
            fullname, package + "/__init__.py", submodule_search_locations=[package]
        )


def install():
    sys.meta_path.append(_EditableFinder)
"""
"""The import hook setuptools writes for an editable install: the project
directory is never put on sys.path, so only this finder knows where it is."""


def editable_install(tmp_path: Path) -> Path:
    """A virtual environment holding an editable install of ``brokenlib``,
    laid out as pip and setuptools write one (a dist-info with
    direct_url.json, a .pth that installs a meta-path finder), whose package
    imports a dependency that is not installed. It also sees this
    interpreter's site-packages, for jitx and pytest. Returns its python.

    The files are written here rather than by ``pip install -e``, which needs
    setuptools and a network this test may not have."""
    project = tmp_path / "brokenproj"
    (project / "brokenlib").mkdir(parents=True)
    (project / "brokenlib" / "__init__.py").write_text(
        "import a_dependency_that_is_not_installed\n", encoding="utf-8"
    )
    venv = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv)],
        check=True,
        timeout=120,
    )
    python = venv / "bin" / "python"
    found = subprocess.run(
        [
            str(python),
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    site = Path(found.stdout.strip())
    ours = sysconfig.get_paths()["purelib"]
    (site / "inherit.pth").write_text(
        f"import site; site.addsitedir({ours!r})\n", encoding="utf-8"
    )
    mapping = {"brokenlib": str(project / "brokenlib")}
    (site / "__editable___brokenlib_0_0_1_finder.py").write_text(
        EDITABLE_FINDER.format(mapping=mapping), encoding="utf-8"
    )
    (site / "__editable__.brokenlib-0.0.1.pth").write_text(
        "import __editable___brokenlib_0_0_1_finder; "
        "__editable___brokenlib_0_0_1_finder.install()\n",
        encoding="utf-8",
    )
    info = site / "brokenlib-0.0.1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: brokenlib\nVersion: 0.0.1\n", encoding="utf-8"
    )
    (info / "direct_url.json").write_text(
        json.dumps({"url": project.as_uri(), "dir_info": {"editable": True}}),
        encoding="utf-8",
    )
    return python


@needs_jitx
def test_an_editable_library_outside_every_sys_path_entry_is_the_environment(
    tmp_path: Path,
) -> None:
    """An editable install reached through an import hook keeps its files in
    its project directory, which is on no sys.path entry; it is still a
    library, so its broken import is the environment's."""
    python = editable_install(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    board = write(candidate, "import brokenlib\n" + MINIMAL_SUBSTRATE)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONHOME")
    }
    preflight = subprocess.run(
        [str(python), str(grade_substrate.PREFLIGHT), str(board)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=environment,
    )
    assert preflight.returncode == 3, preflight.stdout + preflight.stderr
    assert "ERROR  a library the candidate imports does not import" in preflight.stdout
    graded = subprocess.run(
        [str(python), str(GRADE), str(board), str(CASE_CSV)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env=environment,
    )
    assert graded.returncode == 1, graded.stdout + graded.stderr
    assert "ERROR  a library the candidate imports does not import" in graded.stdout
    assert "candidate does not import" not in graded.stdout


def library_on_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, source: str
) -> Path:
    """A module ``name`` with this source in a directory on PYTHONPATH, and a
    board in its own directory that imports it. Returns the board."""
    site = tmp_path / "site"
    site.mkdir(exist_ok=True)
    (site / f"{name}.py").write_text(source, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(site))
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    return write(candidate, f"import {name}\n" + MINIMAL_SUBSTRATE)


def preflight_code(board: Path) -> int:
    """import_candidate.py's own exit code for a board, in this environment."""
    return subprocess.run(
        [sys.executable, str(grade_substrate.PREFLIGHT), str(board)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    ).returncode


@needs_jitx
def test_a_symlinked_library_file_is_the_environment(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A library file that is a symlink to somewhere outside its sys.path
    entry, as some installers lay out site-packages, is still a library."""
    target = tmp_path / "elsewhere" / "brokensym.py"
    target.parent.mkdir()
    target.write_text("import a_dependency_that_is_not_installed\n", encoding="utf-8")
    board = library_on_the_path(tmp_path, monkeypatch, "placeholder", "")
    (tmp_path / "site" / "brokensym.py").symlink_to(target)
    board.write_text("import brokensym\n" + MINIMAL_SUBSTRATE, encoding="utf-8")
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "ERROR  a library the candidate imports does not import" in out
    assert "candidate does not import" not in out
    assert preflight_code(board) == 3


@needs_jitx
@pytest.mark.parametrize(
    "source",
    [
        'exec("import a_dependency_that_is_not_installed")\n',
        (
            'exec(compile("import a_dependency_that_is_not_installed", '
            '"compiledlib/_speedups.pyx", "exec"))\n'
        ),
    ],
    ids=["a pseudo-filename frame", "a relative build-time filename frame"],
)
def test_a_frame_that_is_not_a_file_does_not_decide(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    """Code a library runs under a name that is not an absolute file path
    (exec's "<string>", or a compiled module's relative source name such as a
    Cython .pyx) is skipped, so the library's own file decides and its broken
    import is the environment's."""
    monkeypatch.chdir(tmp_path)
    board = library_on_the_path(tmp_path, monkeypatch, "compiledlib", source)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "ERROR  a library the candidate imports does not import" in out
    assert "candidate does not import" not in out
    assert preflight_code(board) == 3


def distribution_record(site: Path, name: str, record: bytes) -> None:
    """A dist-info for ``name`` in ``site`` whose direct_url.json holds these
    bytes."""
    info = site / f"{name}-0.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: 0\n", encoding="utf-8"
    )
    (info / "direct_url.json").write_bytes(record)


@needs_kit
@pytest.mark.parametrize(
    "record",
    [
        b'\xff\xfe{"url": "file:///x"}',
        b'{"url": "file:///a\\u0000b", "dir_info": {"editable": true}}',
        b'{"url": "file:outside", "dir_info": {"editable": true}}',
        b'{"url": "file:///", "dir_info": {"editable": true}}',
    ],
    ids=[
        "not UTF-8",
        "a NUL in the path",
        "a relative path",
        "the filesystem root",
    ],
)
def test_a_broken_install_record_does_not_change_a_grade(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record: bytes,
) -> None:
    """A corrupt or hand-made direct_url.json anywhere on sys.path is
    ignored: a correct board still grades green, and a board whose own file
    fails to import still grades red."""
    site = tmp_path / "site"
    distribution_record(site, "brokenrecord", record)
    monkeypatch.setenv("PYTHONPATH", str(site))
    # "file:outside" would name tmp_path/outside, where the red board's file is.
    monkeypatch.chdir(tmp_path)
    kit = tmp_path / "kit"
    kit.mkdir()
    code, out = grade(capsys, write(kit, kit_source()), KIT_CSV)
    assert code == 0, out[-3000:]
    board = outside_root_board(tmp_path)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "FAIL  candidate does not import: jitx.dielectric (at board.py:5)" in out
    assert preflight_code(board) == 1


@needs_jitx
@pytest.mark.parametrize("how", ["editable record", "PYTHONPATH entry"])
def test_a_library_root_holding_the_boards_directory_leaves_its_files_red(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    how: str,
) -> None:
    """A board usually sits inside its own project, which may be an editable
    install or on sys.path. The board's directory is the deeper root, so a
    broken helper beside the board is still the candidate's."""
    project = tmp_path / "project"
    candidate = project / "candidate"
    candidate.mkdir(parents=True)
    (candidate / "helpers.py").write_text(
        "from jitx.dielectric import Laminate\n", encoding="utf-8"
    )
    board = write(candidate, "import helpers\n" + MINIMAL_SUBSTRATE)
    if how == "editable record":
        site = tmp_path / "site"
        url = project.as_uri()
        distribution_record(
            site,
            "userproject",
            json.dumps({"url": url, "dir_info": {"editable": True}}).encode(),
        )
        monkeypatch.setenv("PYTHONPATH", str(site))
    else:
        monkeypatch.setenv("PYTHONPATH", str(project))
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "FAIL  candidate does not import: jitx.dielectric (at board.py:1)" in out
    assert preflight_code(board) == 1


@needs_jitx
def test_the_boards_own_import_module_call_is_red(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """importlib's own frames are machinery, not a library at fault."""
    board = write(
        tmp_path,
        "import importlib\nimportlib.import_module('jitx.dielectric')\n"
        + MINIMAL_SUBSTRATE,
    )
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "FAIL  candidate does not import: jitx.dielectric (at board.py:2)" in out


@needs_jitx
def test_a_library_on_the_path_under_the_boards_directory_is_the_environment(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A virtual environment that happens to sit beside the board is still a
    library, not the candidate's own files."""
    site = tmp_path / ".venv" / "lib" / "python3" / "site-packages"
    site.mkdir(parents=True)
    (site / "brokenlib.py").write_text(
        "import a_dependency_that_is_not_installed\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(site))
    board = write(tmp_path, "import brokenlib\n" + MINIMAL_SUBSTRATE)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "ERROR  a library the candidate imports does not import" in out
    assert "candidate does not import" not in out


@needs_jitx
def test_an_error_the_board_causes_inside_a_library_is_red(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Only an import that fails inside a library is the environment's; any
    other error a library raises was caused by the candidate's call."""
    board = write(tmp_path, "import json\njson.loads('not json')\n" + MINIMAL_SUBSTRATE)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "FAIL  candidate does not import: JSONDecodeError:" in out
    assert "(at board.py:2)" in out


SIBLINGS = {path.stem for path in CHECKS.glob("*.py")}
"""Modules beside the grader, which it imports from its own directory."""


def type_checking(test: ast.expr) -> bool:
    """Whether an ``if`` tests ``TYPE_CHECKING``, so its body never runs."""
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def reports(handler: ast.ExceptHandler) -> bool:
    """Whether an ``except`` clause hands its error to grader_cannot_import."""
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "grader_cannot_import"
        for node in ast.walk(handler)
    )


GraderImport = tuple[str, str, int, bool, bool]
"""(module, name or "" for a plain import, line, at module level, inside a
try whose handler reports to grader_cannot_import)."""


def grader_imports() -> list[GraderImport]:
    """Every import in substrate_grader.py of a module that is neither in the
    standard library nor beside the grader, at any depth: module level,
    nested blocks, class bodies and function bodies. Imports under
    ``if TYPE_CHECKING:`` never run, so they are left out."""
    found: list[GraderImport] = []

    def visit(statements: list[ast.stmt], module_level: bool, guarded: bool) -> None:
        for statement in statements:
            if isinstance(statement, ast.Import | ast.ImportFrom):
                if isinstance(statement, ast.Import):
                    pairs = [(alias.name, "") for alias in statement.names]
                else:
                    module = "." * statement.level + (statement.module or "")
                    pairs = [(module, alias.name) for alias in statement.names]
                for module, name in pairs:
                    top = module.split(".")[0]
                    if top and top not in sys.stdlib_module_names | SIBLINGS:
                        found.append(
                            (module, name, statement.lineno, module_level, guarded)
                        )
            elif isinstance(statement, ast.If) and type_checking(statement.test):
                visit(statement.orelse, module_level, guarded)
            elif isinstance(statement, ast.Try | ast.TryStar):
                inside = guarded or any(reports(h) for h in statement.handlers)
                visit(statement.body, module_level, inside)
                for handler in statement.handlers:
                    visit(handler.body, module_level, guarded)
                visit(statement.orelse, module_level, guarded)
                visit(statement.finalbody, module_level, guarded)
            elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                visit(statement.body, False, False)
            else:
                children = ast.iter_child_nodes(statement)
                visit(
                    [c for c in children if isinstance(c, ast.stmt)],
                    module_level,
                    guarded,
                )
                if isinstance(statement, ast.Match):
                    for case in statement.cases:
                        visit(case.body, module_level, guarded)

    visit(ast.parse(GRADER.read_text(encoding="utf-8")).body, True, False)
    return found


def test_the_preflight_checks_every_third_party_import_of_the_grader() -> None:
    """Every import of the grader's that is not the standard library's or a
    sibling's is in import_candidate.NEEDED, so the pre-flight checks it
    before any candidate code runs, and each that runs at module level sits
    in the try that reports a failed one. One left out would fail inside
    pytest, where its output is printed scrubbed, as a red. An import inside
    a function runs only once a test calls it, so it must be in NEEDED too."""
    found = grader_imports()
    needed = {(module, "") for module, _ in import_candidate.NEEDED} | {
        (module, name) for module, names in import_candidate.NEEDED for name in names
    }
    assert any(m == "jitx.si" and n == "_RefLayer" for m, n, *_ in found)
    unlisted = sorted(
        (line, module, name)
        for module, name, line, _, _ in found
        if (module, name) not in needed
    )
    assert not unlisted, f"imports missing from NEEDED: {unlisted}"
    unguarded = sorted(
        line for _, _, line, top, guarded in found if top and not guarded
    )
    assert not unguarded, f"imports outside the guarded try, at lines {unguarded}"


HIDE_MODULE = """    class _Hide:
        def find_spec(self, name, path=None, target=None):
            if name == {target!r}:
                raise ModuleNotFoundError(f"No module named {{name!r}}", name=name)
            return None

    sys.meta_path.insert(0, _Hide())
"""
DROP_NAME = """    import jitx._translate.design
    import {module}

    del {module}.{name}
"""
"""jitx._translate.design imports jitx.si's ``_RefLayer`` itself, so it is
imported first: the name is then gone for the grader alone."""
RAISE_IN = """    class _Raise:
        def find_spec(self, name, path=None, target=None):
            if name == {target!r}:
                {statement}
            return None

    sys.meta_path.insert(0, _Raise())
"""
"""A dependency that raises, or exits, as it is imported."""
ONLY_IN = """import sys

if any(arg.endswith({script!r}) for arg in getattr(sys, "orig_argv", [])):
"""
"""A sitecustomize.py that breaks the environment in one script's process."""

GRADER_ENVIRONMENT_FAULTS = [
    pytest.param(
        "import_candidate.py",
        HIDE_MODULE.format(target="jitxlib"),
        "ERROR  the grader needs jitxlib.physics: ModuleNotFoundError: "
        "No module named 'jitxlib'",
        id="jitxlib, the grader's dependency and not jitx's, gone",
    ),
    pytest.param(
        "import_candidate.py",
        HIDE_MODULE.format(target="jitx._translate.design"),
        "ERROR  the grader needs jitx._translate.design: ModuleNotFoundError: "
        "No module named 'jitx._translate.design'",
        id="a private module the grader imports, gone",
    ),
    pytest.param(
        "substrate_grader.py",
        HIDE_MODULE.format(target="jitx._translate.design"),
        "ERROR  the grader needs jitx._translate.design: ModuleNotFoundError: "
        "No module named 'jitx._translate.design'",
        id="a private module, gone only where the grader runs",
    ),
    pytest.param(
        "import_candidate.py",
        DROP_NAME.format(module="jitx.si", name="_RefLayer"),
        "ERROR  the grader needs jitx.si._RefLayer: ImportError: cannot import "
        "name '_RefLayer' from 'jitx.si'",
        id="a private name the grader imports, gone",
    ),
    pytest.param(
        "substrate_grader.py",
        DROP_NAME.format(module="jitx.si", name="_RefLayer"),
        "ERROR  the grader needs jitx.si._RefLayer: ImportError: cannot import "
        "name '_RefLayer' from 'jitx.si'",
        id="a private name, gone only where the grader runs",
    ),
    pytest.param(
        "import_candidate.py",
        RAISE_IN.format(
            target="jitxlib.physics",
            statement='sys.exit("jitxlib.physics: No module named '
            "'jitxlib._native'; reinstall jitxlib\")",
        ),
        "ERROR  the grader needs jitxlib.physics: SystemExit: jitxlib.physics: "
        "No module named 'jitxlib._native'; reinstall jitxlib",
        id="a grader dependency that exits at import",
    ),
    pytest.param(
        "import_candidate.py",
        RAISE_IN.format(
            target="jitxlib.physics",
            statement="raise RuntimeError('jitxlib built for another jitx')",
        ),
        "ERROR  the grader needs jitxlib.physics: RuntimeError: "
        "jitxlib built for another jitx",
        id="a grader dependency that raises at import",
    ),
]
"""(the script whose process breaks, how, the line grade_substrate.py ends
with). A fault only where the grader runs is one the pre-flight cannot see."""


@needs_jitx
@pytest.mark.parametrize(("script", "fault", "line"), GRADER_ENVIRONMENT_FAULTS)
def test_a_grader_import_that_fails_is_the_environment(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    script: str,
    fault: str,
    line: str,
) -> None:
    """Whatever stops the grader's own imports, in the pre-flight or in the
    grader's pytest run, is reported raw, last, in Python's wording."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(
        ONLY_IN.format(script=script) + fault, encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(site))
    code, out = grade(capsys, write(tmp_path, MINIMAL_SUBSTRATE), CASE_CSV)
    assert code == 1, out
    assert out.strip().splitlines()[-1] == line, out


def test_a_preflight_that_prints_no_verdict_shows_its_stderr(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-flight that crashes has judged nothing, so the board is not
    blamed and the reason is shown."""
    board = write(tmp_path, MINIMAL_SUBSTRATE)

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        assert str(grade_substrate.PREFLIGHT) in command
        crash = "Traceback (most recent call last):\nRuntimeError: pre-flight broke\n"
        return subprocess.CompletedProcess(command, 1, "", crash)

    monkeypatch.setattr(grade_substrate, "run_child", fake_run)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "RuntimeError: pre-flight broke" in out
    assert "does not import" not in out


def test_a_skipped_grader_test_is_red(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pytest exits 0 with a skip; the run is still not fully graded."""
    board = write(tmp_path, MINIMAL_SUBSTRATE)
    graded = f"GradedTarget: substrate Minimal from {board}; fab report {CASE_CSV}"

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        summary = "31 passed, 1 skipped, 1 warning, 260 subtests passed in 0.40s"
        return subprocess.CompletedProcess(command, 0, f"{graded}\n{summary}\n", "")

    monkeypatch.setattr(grade_substrate, "run_child", fake_run)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1, out
    assert "FAIL  the grader reported 1 skipped" in out


GREEN_SUMMARY = "32 passed, 1 warning, 260 subtests passed in 0.40s"


@pytest.mark.parametrize(
    ("graded", "verdict"),
    [
        (
            "GradedTarget: substrate Minimal from {board}; fab report {csv}",
            "PASS  the grader graded {board} against {csv}",
        ),
        (
            "GradedTarget: substrate Minimal from {other}; fab report {csv}",
            "FAIL  the grader graded {other}, not {board}",
        ),
        (
            "GradedTarget: substrate Minimal from {board}; fab report {other}",
            "FAIL  the grader read the fab report {other}, not {csv}",
        ),
        ("", "FAIL  the grader printed no GradedTarget line"),
    ],
    ids=["the right files", "another board", "another report", "no GradedTarget"],
)
def test_a_green_run_passes_only_if_it_graded_the_given_files(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    graded: str,
    verdict: str,
) -> None:
    """The fail-closed guard: an all-green summary is not a pass unless the
    grader says it graded this board against this report."""
    board = write(tmp_path, MINIMAL_SUBSTRATE)
    other = tmp_path / "other.py"
    names = {"board": board, "csv": CASE_CSV, "other": other}

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        output = f"{graded.format(**names)}\n{GREEN_SUMMARY}\n"
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(grade_substrate, "run_child", fake_run)
    code, out = grade(capsys, board, CASE_CSV)
    assert verdict.format(**names) in out
    assert code == (0 if verdict.startswith("PASS") else 1), out


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        (
            "32 passed, 1 warning, 260 subtests passed in 0.37s",
            {"passed": 32, "warning": 1, "subtests passed": 260},
        ),
        (
            "== 1 failed, 31 passed, 2 skipped in 0.9s ==",
            {"failed": 1, "passed": 31, "skipped": 2},
        ),
        ("no tests ran in 0.01s", {}),
    ],
)
def test_summary_counts(summary: str, expected: dict[str, int]) -> None:
    assert grade_substrate.summary_counts(f"noise\n{summary}\n") == expected


# The case report, checked on its own: these hold of any report the grader is
# meant to read, so a fixture edit that breaks one is caught without a board.

MIL = 0.0254


def report_sections(report: Path) -> dict[str, list[dict[str, str]]]:
    return fabcsv.sections(report)


def copper_positions(rows: list[dict[str, str]]) -> dict[str, int]:
    return {row["Layer"]: index for index, row in enumerate(rows) if row["Layer"]}


REPORTS = pytest.mark.parametrize(
    "report", [CASE_CSV, KIT_CSV], ids=["case report", "kit report"]
)


@REPORTS
def test_report_rows_sum_to_both_totals(report: Path) -> None:
    sections = report_sections(report)
    document = {row["Field"]: row["Value"] for row in sections["DOCUMENT"]}
    rows = sections["STACKUP"]
    overall = sum(float(row["Thickness_mm"]) for row in rows)
    finished = sum(
        float(row["Thickness_mm"]) for row in rows if row["Type"] != "Soldermask"
    )
    assert round(overall, 6) == float(document["Overall thickness"])
    assert round(finished, 6) == float(document["Finished thickness"])


@REPORTS
def test_report_via_depths_follow_each_drills_convention(report: Path) -> None:
    """Laser: the dielectric between the two copper layers. Mechanical: the
    full drilled depth, both end foils included."""
    sections = report_sections(report)
    rows = sections["STACKUP"]
    position = copper_positions(rows)
    for via in sections["VIAS"]:
        first, last = sorted((position[via["From_layer"]], position[via["To_layer"]]))
        span = (
            rows[first + 1 : last]
            if via["Drill"] == "Laser"
            else rows[first : last + 1]
        )
        depth = sum(float(row["Thickness_mm"]) for row in span)
        assert round(depth, 6) == float(via["Depth_mm"]), via["Via_ID"]


@REPORTS
def test_report_vias_are_within_its_capability(report: Path) -> None:
    sections = report_sections(report)
    rules = {row["Rule"]: row["Value_mm"] for row in sections["FAB_RULES"]}
    min_ring = float(rules["Minimum annular ring"])
    max_ar = {
        "Laser": float(rules["Maximum laser microvia aspect ratio"].split(":")[0]),
        "Mechanical": float(
            rules["Maximum mechanical drill aspect ratio"].split(":")[0]
        ),
    }
    for via in sections["VIAS"]:
        hole, pad = float(via["Finished_hole_mm"]), float(via["Pad_mm"])
        ring = (pad - hole) / 2
        aspect = float(via["Depth_mm"]) / hole
        assert round(ring, 6) == float(via["Annular_ring_mm"]), via["Via_ID"]
        assert round(aspect, 2) == float(via["Aspect_ratio"]), via["Via_ID"]
        assert ring >= min_ring, via["Via_ID"]
        assert round(aspect, 6) <= max_ar[via["Drill"]], via["Via_ID"]


@REPORTS
def test_report_reference_planes_are_adjacent_plane_rows(report: Path) -> None:
    sections = report_sections(report)
    rows = sections["STACKUP"]
    position = copper_positions(rows)
    for row in sections["IMPEDANCE"]:
        if not row["Ref_layers"]:
            continue
        layers = [name.strip() for name in row["Layers"].split(";")]
        groups = [group.strip() for group in row["Ref_layers"].split(";")]
        assert len(groups) == len(layers), row["Structure_ID"]
        for index, group in enumerate(groups):
            planes, separator, line = group.partition(" for ")
            line = line if separator else layers[index]
            for plane in planes.split("+"):
                plane_row = rows[position[plane]]
                assert plane_row["Function"].startswith("Plane"), plane
                first, last = sorted((position[plane], position[line]))
                between = [r for r in rows[first + 1 : last] if r["Type"] == "Copper"]
                assert between == [], f"{plane} is not adjacent to {line}"


def test_dielectric_between_skips_the_copper_between() -> None:
    """A skip-layer plane's height is the dielectric alone, as SKILL.md sums it."""
    stackup = report_sections(CASE_CSV)["STACKUP"]
    assert fabcsv.dielectric_between_mm(stackup, "L1", "L3") == pytest.approx(0.160)
    assert fabcsv.dielectric_between_mm(stackup, "L3", "L1") == pytest.approx(0.160)
    assert fabcsv.dielectric_between_mm(stackup, "L3", "L4") == pytest.approx(0.127)


@REPORTS
def test_report_uncoupled_widths_equal_the_pair_widths(report: Path) -> None:
    rows = report_sections(report)["IMPEDANCE"]
    uncoupled = [row for row in rows if row["Structure_ID"].endswith("-UNC")]
    assert uncoupled
    for row in uncoupled:
        pair = next(
            r
            for r in rows
            if r["Structure_ID"] == row["Structure_ID"].removesuffix("-UNC")
            and r["Layers"] == row["Layers"]
        )
        assert row["Line_width_mm"] == pair["Line_width_mm"], row["Layers"]
        assert row["Clearance_mm"] == pair["Clearance_mm"], row["Layers"]


@REPORTS
def test_report_mil_and_mm_columns_agree(report: Path) -> None:
    """Every mil cell is its mm cell in mil, to the two decimals mil is written to."""
    checked = 0
    for name, rows in report_sections(report).items():
        for row in rows:
            for column, mil in row.items():
                if not column.endswith("_mil") or not mil.strip():
                    continue
                mm = row[column.removesuffix("_mil") + "_mm"]
                if not re.fullmatch(r"[0-9.]+", mm.strip()):
                    continue
                checked += 1
                assert abs(float(mm) / MIL - float(mil)) <= 0.005 + 1e-9, (
                    f"{name} {row} {column}"
                )
    assert checked > 50
