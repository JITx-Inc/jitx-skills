"""grade_pdf_report.py fails a check exactly when the candidate breaks it.

The hand-written known-good boards pass every check. Each table row makes one
edit to a known-good board and names the checks it must fail, through the
grader's CLI as the case runs it, so the exit code and the ``PASS``/``FAIL``
lines are what is asserted. The case's PDF is checked against its CSV twin
with pdftotext: the twin is what the grader reads, the PDF is what the runner
reads, and the two must state the same values except where the case sets a
trap. Tests that need jitx or pdftotext skip, with the reason, without them.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import fabcsv
import pytest

CHECKS = Path(__file__).resolve().parent
GRADER = CHECKS / "grade_pdf_report.py"
CASE_B = CHECKS / "testdata" / "case_b"
BOARD = CASE_B / "board.py"
SYMMETRIC = CASE_B / "symmetric_board.py"
TWIN = CASE_B / "TIC-8L_Stackup-Report_RevC.csv"
PDF = CHECKS.parent / "cases" / "fixtures" / "pdf_TIC-8L_Stackup-Report_RevC.pdf"

REPORT_CHECKS = {
    "backdrill",
    "stacked",
    "nfp",
    "skip_layer_reference",
    "capability_not_attributes",
    "capability_documented",
}
SYMMETRIC_CHECKS = {
    "symmetric",
    "middle_is_dielectric",
    "four_copper_layers",
    "translates",
}

needs_jitx = pytest.mark.skipif(
    importlib.util.find_spec("jitx") is None,
    reason="jitx is not importable; install jitx to run this test",
)


def grade(*args: str | Path) -> tuple[int, str]:
    run = subprocess.run(
        [sys.executable, str(GRADER), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )
    return run.returncode, run.stdout


def outcomes(stdout: str) -> dict[str, str]:
    """Check name -> ``PASS`` or ``FAIL``, from the grader's per-check lines."""
    return dict(
        (name, status)
        for status, name in re.findall(
            r"^(PASS|FAIL)  (\w+)(?::|$)", stdout, re.MULTILINE
        )
    )


def edited(tmp_path: Path, source: Path, edits: list[tuple[str, str]]) -> Path:
    text = source.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, f"edit target not found once: {old!r}"
        text = text.replace(old, new)
    out = tmp_path / source.name
    out.write_text(text, encoding="utf-8")
    return out


SV1_SPAN = "        start_layer = 0\n        stop_layer = 2\n        diameter = 0.3048"
RULES_DOC = (
    '    """Capability limits: mechanical drill 6.0 mil, mechanical aspect ratio\n'
    '    10:1, laser aspect ratio 1.25:1, 2 stacked levels, dielectric 2.5 mil."""\n'
)
TH1_DIAMETERS = (
    "        diameters = {(1, 2, 3, 4, 5, 6): ViaDiameter(0.4064, nfp=0.2794)}\n"
)
SUBSTRATE_HEAD = "    stackup = EightLayer()\n"
RULES_TAIL = "    min_pth_pin_solder_clearance = 0.2032\n"

REPORT_ROWS = [
    ("known_good", [], set(), False),
    (
        "backdrilled_from_the_top",
        [("            bottom=Backdrill(", "            top=Backdrill(")],
        {"backdrill"},
        False,
    ),
    (
        "backdrill_clearance_wrong",
        [("copper_clearance=0.7112", "copper_clearance=0.6604")],
        {"backdrill"},
        False,
    ),
    (
        "stack_coded_as_l2_to_l3_only",
        [(SV1_SPAN, SV1_SPAN.replace("start_layer = 0", "start_layer = 1"))],
        {"stacked"},
        False,
    ),
    (
        "unlisted_level_beside_the_stack",
        [
            (
                SUBSTRATE_HEAD,
                SUBSTRATE_HEAD + "\n    class UV23(Via):\n"
                "        type = ViaType.LaserDrill\n"
                "        start_layer = 1\n"
                "        stop_layer = 2\n"
                "        diameter = 0.3048\n"
                "        hole_diameter = 0.1524\n",
            )
        ],
        {"stacked"},
        False,
    ),
    ("no_nfp", [(TH1_DIAMETERS, "")], {"nfp"}, False),
    (
        "via_wide_nfp_reaches_the_outer_layers",
        [
            (TH1_DIAMETERS, ""),
            (
                "        diameter = 0.4064\n        hole_diameter = 0.2032",
                "        diameter = ViaDiameter(0.4064, nfp=0.2794)\n        hole_diameter = 0.2032",
            ),
        ],
        {"nfp"},
        False,
    ),
    (
        "l1_references_the_voided_l2",
        [
            (
                "            ).reference({2: 3 * H_L1_L3}),",
                "            ).reference({1: 3 * 0.0762}),",
            )
        ],
        {"skip_layer_reference"},
        False,
    ),
    (
        "skip_width_from_one_ply",
        [
            (
                "            ).reference({2: 3 * H_L1_L3}),",
                "            ).reference({2: 3 * 0.0762}),",
            )
        ],
        {"skip_layer_reference"},
        False,
    ),
    (
        "aspect_ratio_as_a_rules_attribute",
        [(RULES_TAIL, RULES_TAIL + "    max_laser_aspect_ratio = 1.25\n")],
        {"capability_not_attributes"},
        False,
    ),
    (
        "stack_count_on_the_substrate",
        [(SUBSTRATE_HEAD, SUBSTRATE_HEAD + "    MAX_STACKED_LEVELS = 2\n")],
        {"capability_not_attributes"},
        False,
    ),
    (
        "laser_ratio_undocumented",
        [(RULES_DOC, RULES_DOC.replace("laser aspect ratio 1.25:1, ", ""))],
        {"capability_documented"},
        False,
    ),
    (
        "mechanical_drill_as_a_custom_mm_attribute",
        [
            (RULES_DOC, RULES_DOC.replace("mechanical drill 6.0 mil, ", "")),
            (RULES_TAIL, RULES_TAIL + "    min_mechanical_drill_diameter = 0.1524\n"),
        ],
        set(),
        False,
    ),
    (
        "annular_ring_called_enforced",
        [
            (
                "    min_annular_ring = 0.0635\n",
                "    min_annular_ring = 0.0635  # enforced by the engine\n",
            )
        ],
        set(),
        True,
    ),
]


@needs_jitx
@pytest.mark.parametrize(
    ("edits", "failing", "noted"),
    [
        pytest.param(edits, failing, noted, id=name)
        for name, edits, failing, noted in REPORT_ROWS
    ],
)
def test_report_checks_fail_only_on_their_own_defect(
    tmp_path: Path, edits: list[tuple[str, str]], failing: set[str], noted: bool
) -> None:
    code, stdout = grade("report", edited(tmp_path, BOARD, edits), TWIN)
    assert outcomes(stdout) == {
        name: "FAIL" if name in failing else "PASS" for name in REPORT_CHECKS
    }, stdout
    assert code == (1 if failing else 0), stdout
    assert ("NOTE  only the four min_copper_* fields" in stdout) == noted, stdout


SYMMETRIC_CORE = "    core = FR4(thickness=1.065)\n"
SYMMETRIC_STACKUP = (
    "class FourLayer(Symmetric):\n"
    "    top_mask = Mask(thickness=0.0127)\n"
    '    top = Foil(name="L1")\n'
    "    prepreg = FR4(thickness=0.2)\n"
    '    inner = Foil(name="L2")\n' + SYMMETRIC_CORE
)
EXPLICIT_STACKUP = (
    "class FourLayer(Stackup):\n"
    "    top_mask = Mask(thickness=0.0127)\n"
    '    l1 = Foil(name="L1")\n'
    "    pp1 = FR4(thickness=0.2)\n"
    '    l2 = Foil(name="L2")\n'
    "    core = FR4(thickness=1.065)\n"
    '    l3 = Foil(name="L3")\n'
    "    pp2 = FR4(thickness=0.2)\n"
    '    l4 = Foil(name="L4")\n'
    "    bottom_mask = Mask(thickness=0.0127)\n"
)
COPPER_LAST = "Last layer must be dielectric"
"""What jitx raises for a Symmetric stackup listed down to a copper layer."""

SYMMETRIC_ROWS = [
    ("known_good", [], set()),
    (
        "explicit_stackup",
        [
            (SYMMETRIC_STACKUP, EXPLICIT_STACKUP),
            (
                "import Conductor, Dielectric, Symmetric",
                "import Conductor, Dielectric, Stackup",
            ),
        ],
        {"symmetric"},
    ),
    (
        "six_layers",
        [
            (
                SYMMETRIC_CORE,
                '    pp2 = FR4(thickness=0.5)\n    l3 = Foil(name="L3")\n'
                + SYMMETRIC_CORE,
            )
        ],
        {"four_copper_layers"},
    ),
    ("does_not_translate", [("    min_hole_to_hole = 0.25\n", "")], {"translates"}),
    ("listed_down_to_copper", [(SYMMETRIC_CORE, "")], SYMMETRIC_CHECKS),
]


@needs_jitx
@pytest.mark.parametrize(
    ("edits", "failing"),
    [pytest.param(edits, failing, id=name) for name, edits, failing in SYMMETRIC_ROWS],
)
def test_symmetric_checks_fail_only_on_their_own_defect(
    tmp_path: Path, edits: list[tuple[str, str]], failing: set[str]
) -> None:
    code, stdout = grade("symmetric", edited(tmp_path, SYMMETRIC, edits))
    assert outcomes(stdout) == {
        name: "FAIL" if name in failing else "PASS" for name in SYMMETRIC_CHECKS
    }, stdout
    assert code == (1 if failing else 0), stdout
    if failing == SYMMETRIC_CHECKS:
        assert re.search(
            rf"^FAIL  middle_is_dielectric: .*{COPPER_LAST}", stdout, re.M
        ), stdout


@needs_jitx
@pytest.mark.parametrize(
    ("argv", "code", "line"),
    [
        pytest.param(
            ["report", BOARD, "missing.csv"], 2, "ERROR  missing.csv", id="no_csv"
        ),
        pytest.param(
            ["report", "missing.py", TWIN], 1, "FAIL  candidate", id="no_board"
        ),
        pytest.param(["symmetric"], 2, "", id="no_board_argument"),
    ],
)
def test_usage_errors_and_a_missing_board(
    argv: list[str | Path], code: int, line: str
) -> None:
    got, stdout = grade(*argv)
    assert got == code
    assert stdout.startswith(line)


@needs_jitx
@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ("    min_annular_ring = 0.0635  # enforced by the engine", True),
        ("    # min_hole_to_hole and min_pitch_bga are engine-enforced", True),
        ("    min_copper_width = 0.0762  # enforced by the engine", False),
        (
            "    min_annular_ring = 0.0635  # not enforced; documents the fab's rule",
            False,
        ),
        ("    min_hole_to_hole = 0.2540  # unenforced", False),
        ("    min_annular_ring = 0.0635", False),
    ],
)
def test_enforced_claims_are_noted_for_fields_beyond_min_copper(
    line: str, flagged: bool
) -> None:
    import grade_pdf_report

    assert bool(grade_pdf_report.enforced_claims(line)) == flagged


# The PDF against its twin. Each twin cell the grader reads must appear in the
# PDF in mm or in mil, except the cells the case hides; hidden cells must not.

HIDDEN = {
    "1.1362": "the L5-L6 core thickness, which the PDF leaves unstated",
    "44.73": "the same thickness in mil",
    "0.0350": "the inner copper thickness, which the PDF gives as 1 oz only",
    "1.38": "the same thickness in mil",
    "0.4225": "BD-1's depth to the layer it keeps; the PDF gives the full drilled depth",
}
SHOWN_TRAPS = {
    "0.1000": "the L4-L5 prepreg's mm cell, which disagrees with its 4.00 mil",
    "2.50": "UV-1's annular ring as Rev B stated it",
    "80.00 (2.0320)": "BD-1's full drilled depth",
}


def pdf_text() -> str:
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        pytest.skip("pdftotext is not installed; install poppler to run this test")
    return subprocess.run(
        [pdftotext, "-layout", str(PDF), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def forms(mm: str) -> set[str]:
    """A twin mm cell as the PDF may print it: as written, or in mil."""
    return {mm, f"{float(mm) / 0.0254:.2f}"}


def graded_cells() -> list[tuple[str, str]]:
    """(where, mm value) for each twin cell a grader compares a candidate to."""
    twin = fabcsv.sections(TWIN)
    cells: list[tuple[str, str]] = []
    for row in twin["STACKUP"]:
        where = f"STACKUP {row['Seq']}"
        cells += [(where, row["Dk"]), (where, row["Df"])] if row["Dk"] else []
        cells.append((where, row["Thickness_mm"]))
    for row in twin["MATERIALS_COPPER"]:
        cells += [
            (row["Copper_ID"], row["Rz_matte_um"]),
            (row["Copper_ID"], row["Rz_drum_um"]),
        ]
    columns = [
        "Finished_hole_mm",
        "Pad_mm",
        "Depth_mm",
        "Backdrill_diameter_mm",
        "Backdrill_startpad_mm",
        "Backdrill_mask_opening_mm",
        "Backdrill_copper_clearance_mm",
        "NFP_pad_mm",
    ]
    for row in twin["VIAS"]:
        cells += [(f"VIAS {row['Via_ID']} {c}", row[c]) for c in columns if row[c]]
    for row in twin["IMPEDANCE"]:
        if row["Controlled"] == "Yes":
            where = f"IMPEDANCE {row['Structure_ID']} {row['Layers']}"
            for column in ("Line_width_mm", "Pair_gap_mm", "Clearance_mm"):
                cells += [(where, row[column])] if row[column] else []
            cells += [(where, row["Eps_eff"]), (where, row["Loss_dB_per_mm"])]
    for row in twin["FAB_RULES"]:
        value = row["Value_mm"]
        if ":" in value or not row["Value_mil"]:
            continue
        cells.append((f"FAB_RULES {row['Rule']}", value))
    return cells


def test_pdf_states_every_graded_value_and_hides_the_trap_values() -> None:
    text = pdf_text()
    tokens = set(re.findall(r"\d+(?:\.\d+)?", text))
    missing = [
        f"{where}: {mm}"
        for where, mm in graded_cells()
        if mm not in HIDDEN and not (forms(mm) & tokens)
    ]
    assert not missing, missing
    twin = fabcsv.sections(TWIN)
    for row in twin["FAB_RULES"]:
        if not row["JITX_attribute"]:
            stated = (
                row["Value_mm"]
                if ":" in row["Value_mm"]
                else row["Value_mil"] or row["Value_mm"]
            )
            assert stated in text, row["Rule"]
        elif not row["Value_mil"]:
            inches = re.search(r"\(([\d.]+ in)\)", row["Notes"])
            assert inches and inches.group(1) in text, row["Rule"]
    leaked = {value: why for value, why in HIDDEN.items() if value in tokens}
    assert not leaked, leaked
    absent = {value: why for value, why in SHOWN_TRAPS.items() if value not in text}
    assert not absent, absent
