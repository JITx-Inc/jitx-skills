"""grade_substrate.py and substrate_grader.py grade what they are given, and nothing else.

The JS1 kit board, imported from an installed jitxexamples, passes against a
verbatim copy of the kit's own report, and so does a copy with every class and
structure renamed, so nothing is found by name. Copies with one wrong value
fail in the test that owns that value. Temporary copies of the kit report and
the kit board, edited together, pass, so the grader reads what a report says
rather than what the JS1 report happens to say. The same kit board fails
against the case's report, and the case's report is checked for its own
internal consistency without any board. Unset or blank settings are errors,
never defaults. Tests that need the kit board or jitx skip, with the reason,
when they are not installed.

testdata/JS1_Part1_Fab-Stackup.csv is a verbatim copy of the JS1 Jumpstart
kit's part1-stackup/JS1_Part1_Fab-Stackup.csv in <py-components>
(jumpstart-kits/js1-stackup-components/part1-stackup/). The copy and the
installed kit board must be updated together: the kit board is graded against
the copy, so a change to one without the other turns these tests red.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import fabcsv
import grade_substrate
import pytest

CHECKS = Path(__file__).resolve().parent
GRADER = CHECKS / "substrate_grader.py"
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


def renamed_kit_source() -> str:
    """The kit substrate's source with every class, routing-structure attribute
    and structure ``name=`` replaced by a meaningless one."""
    assert KIT_BOARD is not None
    source = KIT_BOARD.read_text(encoding="utf-8")
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
def test_kit_board_passes_its_own_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert KIT_BOARD is not None
    code, out = grade(capsys, KIT_BOARD, KIT_CSV)
    assert code == 0, out[-3000:]
    assert "PASS  the grader graded" in out


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
            "TestStackup::test_copper_layers_named_by_function",
        ),
        (
            # No roughness scalar, and a docstring that states no Rz.
            replace_once(
                "    roughness = 0.0060\n", '    __doc__ = "No roughness stated."\n'
            ),
            "TestStackup::test_material_properties_match_csv",
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
        "roughness in neither scalar nor docstring",
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
# the stackup tests alone, they show that the grader takes the layer count
# from the report: a 20-layer pin from the JS1 report turns them red.

TOY_REPORT = """SECTION,DOCUMENT
Field,Value,Unit,Notes
Layer count,2,copper layers,
Overall thickness,1.070,mm,
Finished thickness,1.070,mm,

SECTION,STACKUP
Seq,Type,Layer,Function,Material_ID,Thickness_mil,Thickness_mm,Dk,Df
1,Copper,L1,Signal,CU,1.38,0.0350,,
2,Dielectric,,Core,D-CORE,39.37,1.0000,4.00,0.0200
3,Copper,L2,Plane - GND,CU,1.38,0.0350,,
"""

TOY_BOARD = """
from jitx.stackup import Conductor, Dielectric, Stackup
from jitx.substrate import Substrate


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


class Toy(Substrate):
    stackup = ToyStackup()
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
    "test_layer_count_and_order or test_copper_layers_named_by_function"
    " or test_thickness_totals_match_document"
)


def grade_toy(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, board_source: str
) -> tuple[int, str]:
    report = tmp_path / "toy.csv"
    report.write_text(TOY_REPORT, encoding="utf-8")
    board = write(tmp_path, board_source)
    argv = ["grade_substrate.py", str(board), str(report), "-k", TOY_TESTS]
    code = grade_substrate.main(argv)
    return code, capsys.readouterr().out


@needs_jitx
def test_grader_reads_the_layer_count_from_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, out = grade_toy(capsys, tmp_path, TOY_BOARD)
    assert code == 0, out[-3000:]
    assert "3 passed" in out


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
def test_candidate_that_does_not_import_is_red(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A wrong import is the candidate's fault, so it reads as a red and not in
    the wording a harness takes for a missing environment."""
    board = write(
        tmp_path, "from jitx.dielectric import Laminate\n" + MINIMAL_SUBSTRATE
    )
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "FAIL  candidate does not import: jitx.dielectric (at board.py:1)" in out
    assert "No module named" not in out


@needs_jitx
def test_a_name_that_does_not_exist_is_red(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    board = write(tmp_path, "from jitx.units import kiloohm_typo\n" + MINIMAL_SUBSTRATE)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert (
        "FAIL  candidate does not import: cannot import name 'kiloohm_typo' "
        "from 'jitx.units' (at board.py:1)"
    ) in out
    assert "ImportError: cannot import name" not in out


@needs_jitx
def test_an_import_that_fails_inside_a_library_is_the_environment(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing in the candidate's own files is wrong, so it is not a red."""
    library = tmp_path / "library"
    library.mkdir()
    (library / "brokenlib.py").write_text(
        "import a_dependency_that_is_not_installed\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(library))
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    board = write(candidate, "import brokenlib\n" + MINIMAL_SUBSTRATE)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1
    assert "ERROR  a library the candidate imports does not import" in out
    assert "No module named 'a_dependency_that_is_not_installed'" in out
    assert "candidate does not import" not in out


@needs_jitx
def test_a_missing_grader_dependency_is_the_environment(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """jitxlib is the grader's dependency, not jitx's, so it is checked too."""
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "jitxlib.py").write_text(
        "raise ModuleNotFoundError(\"No module named 'jitxlib'\", name='jitxlib')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(shadow))
    code, out = grade(capsys, write(tmp_path, MINIMAL_SUBSTRATE), CASE_CSV)
    assert code == 1
    assert "ERROR  the grader needs jitxlib.physics" in out
    assert "No module named 'jitxlib'" in out


def test_a_skipped_grader_test_is_red(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pytest exits 0 with a skip; the run is still not fully graded."""
    board = write(tmp_path, MINIMAL_SUBSTRATE)
    graded = f"GradedTarget: substrate Minimal from {board}; fab report {CASE_CSV}"

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if "-c" in command:
            return subprocess.CompletedProcess(command, 0, "", "")
        summary = "31 passed, 1 skipped, 1 warning, 260 subtests passed in 0.40s"
        return subprocess.CompletedProcess(command, 0, f"{graded}\n{summary}\n", "")

    monkeypatch.setattr(grade_substrate.subprocess, "run", fake_run)
    code, out = grade(capsys, board, CASE_CSV)
    assert code == 1, out
    assert "FAIL  the grader reported 1 skipped" in out


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
