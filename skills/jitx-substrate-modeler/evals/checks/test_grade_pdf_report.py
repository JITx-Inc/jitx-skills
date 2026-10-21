"""grade_pdf_report.py fails a check exactly when the candidate breaks it.

The hand-written known-good boards pass every check. Each table row makes one
edit to a known-good board and names the checks it must fail, through the
grader's CLI as the case runs it, so the exit code and the ``PASS``/``FAIL``
lines are what is asserted; a row that names none is a valid variant the
grader must accept. A candidate that ends the grading early must be a red.
The case's PDF is checked against its CSV twin with pdftotext: the twin is
what the grader reads, the PDF is what the runner reads, and the two must
state the same values except where the case sets a trap. Tests that need
jitx or pdftotext skip, with the reason, without them.
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
from import_candidate import ENVIRONMENT_WORDING

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
    "stackup_rows",
    "inner_copper",
    "core_from_total",
    "thickness_totals",
    "materials",
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

Edits = list[tuple[str, str]]


def run_grader(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GRADER), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def grade(*args: str | Path) -> tuple[int, str]:
    run = run_grader(*args)
    return run.returncode, run.stdout


def outcomes(stdout: str) -> dict[str, str]:
    """Check name -> ``PASS`` or ``FAIL``, from the grader's per-check lines."""
    return dict(
        (name, status)
        for status, name in re.findall(
            r"^(PASS|FAIL)  (\w+)(?::|$)", stdout, re.MULTILINE
        )
    )


def edited(tmp_path: Path, source: Path, edits: Edits) -> Path:
    text = source.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, f"edit target not found once: {old!r}"
        text = text.replace(old, new)
    out = tmp_path / source.name
    out.write_text(text, encoding="utf-8")
    return out


SV1_SPAN = "        start_layer = 0\n        stop_layer = 2\n        diameter = 0.3048"
BD1_SPAN = "        start_layer = Side.Top\n        stop_layer = 3\n"
BD1_BACKDRILL = "        backdrill = BackdrillSet(\n            bottom=Backdrill(\n"
RULES_DOC = (
    '    """Capability limits: mechanical drill 6.0 mil, mechanical aspect ratio\n'
    '    10:1, laser aspect ratio 1.25:1, 2 stacked levels, dielectric 2.5 mil."""\n'
)
TH1_DIAMETERS = (
    "        diameters = {(1, 2, 3, 4, 5, 6): ViaDiameter(0.4064, nfp=0.2794)}\n"
)
TH1_TAIL = "        hole_diameter = 0.2032\n"
SUBSTRATE_HEAD = "    stackup = EightLayer()\n"
RULES_TAIL = "    min_pth_pin_solder_clearance = 0.2032\n"
INNER_CU = "INNER_CU = 0.0350"
THICK = "    thick = ThickCore(thickness=THICK_CORE)\n"
H_L1_L3 = "            ).reference({2: 3 * H_L1_L3}),"


def backdrill(side: str) -> str:
    return (
        f"            {side}=Backdrill(\n"
        "                diameter=0.4064,\n"
        "                startpad_diameter=0.6096,\n"
        "                solder_mask_opening=0.6604,\n"
        "                copper_clearance=0.7112,\n"
        "            ),\n"
    )


def th1_backdrill(side: str) -> str:
    return (
        TH1_TAIL
        + "        backdrill = BackdrillSet(\n"
        + backdrill(side)
        + "        )\n"
    )


def th1_nfp_on(layers: str) -> Edits:
    return [(TH1_DIAMETERS, TH1_DIAMETERS.replace("(1, 2, 3, 4, 5, 6)", layers))]


# (id, board.py edits, checks that must fail, whether a NOTE line is printed)
REPORT_ROWS: list[tuple[str, Edits, set[str], bool]] = [
    ("known_good", [], set(), False),
    (
        "backdrilled_from_the_top",
        [("            bottom=Backdrill(", "            top=Backdrill(")],
        {"backdrill"},
        False,
    ),
    (
        "backdrilled_from_both_sides",
        [
            (
                BD1_BACKDRILL,
                "        backdrill = BackdrillSet(\n"
                + backdrill("top")
                + "            bottom=Backdrill(\n",
            )
        ],
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
        "bd1_coded_from_l4",
        [(BD1_SPAN, "        start_layer = 3\n        stop_layer = Side.Top\n")],
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
        "via_wide_nfp_keeps_both_end_pads",
        [
            (TH1_DIAMETERS, ""),
            (
                "        diameter = 0.4064\n        hole_diameter = 0.2032",
                "        diameter = ViaDiameter(0.4064, nfp=0.2794)\n        hole_diameter = 0.2032",
            ),
        ],
        set(),
        False,
    ),
    (
        "nfp_declared_on_l1_without_a_top_backdrill",
        th1_nfp_on("(0, 1, 2, 3, 4, 5, 6)"),
        set(),
        False,
    ),
    (
        "nfp_declared_on_l8_without_a_bottom_backdrill",
        th1_nfp_on("(1, 2, 3, 4, 5, 6, 7)"),
        set(),
        False,
    ),
    (
        "nfp_on_l1_under_a_top_backdrill",
        [*th1_nfp_on("(0, 1, 2, 3, 4, 5, 6)"), (TH1_TAIL, th1_backdrill("top"))],
        {"nfp"},
        False,
    ),
    (
        "nfp_on_l8_under_a_bottom_backdrill",
        [*th1_nfp_on("(1, 2, 3, 4, 5, 6, 7)"), (TH1_TAIL, th1_backdrill("bottom"))],
        {"nfp"},
        False,
    ),
    (
        "l1_references_the_voided_l2",
        [(H_L1_L3, "            ).reference({1: 3 * 0.0762}),")],
        {"skip_layer_reference"},
        False,
    ),
    (
        "l1_references_l2_and_l3",
        [(H_L1_L3, "            ).reference({1: 3 * 0.0762, 2: 3 * H_L1_L3}),")],
        {"skip_layer_reference"},
        False,
    ),
    (
        "skip_width_from_one_ply",
        [(H_L1_L3, "            ).reference({2: 3 * 0.0762}),")],
        {"skip_layer_reference"},
        False,
    ),
    (
        "prepreg_from_the_mm_cell",
        [
            (
                "    pp1 = Prepreg(thickness=0.1016)\n",
                "    pp1 = Prepreg(thickness=0.1000)\n",
            )
        ],
        {"stackup_rows", "core_from_total", "thickness_totals"},
        False,
    ),
    (
        "inner_copper_from_the_mil_column",
        [
            (INNER_CU, "INNER_CU = 1.38 * 0.0254"),
            (THICK, "    thick = ThickCore(thickness=44.72 * 0.0254)\n"),
        ],
        set(),
        False,
    ),
    (
        "inner_copper_read_as_half_ounce",
        [(INNER_CU, "INNER_CU = 0.0175")],
        {"inner_copper"},
        False,
    ),
    (
        "inner_copper_read_as_two_ounce",
        [(INNER_CU, "INNER_CU = 0.0700")],
        {"inner_copper"},
        False,
    ),
    (
        "core_not_from_the_total",
        [(THICK, "    thick = ThickCore(thickness=1.1000)\n")],
        {"core_from_total", "thickness_totals"},
        False,
    ),
    (
        "core_from_the_total_at_the_report_precision",
        [
            (INNER_CU, "INNER_CU = 1.38 * 0.0254"),
            (THICK, "    thick = ThickCore(thickness=1.1359)\n"),
        ],
        set(),
        False,
    ),
    (
        "core_rounded_past_the_report_precision",
        [(THICK, "    thick = ThickCore(thickness=1.136)\n")],
        {"core_from_total", "thickness_totals"},
        False,
    ),
    (
        "core_dk_wrong",
        [
            (
                "    dielectric_coefficient = 3.60\n    loss_tangent = 0.0080",
                "    dielectric_coefficient = 3.70\n    loss_tangent = 0.0080",
            )
        ],
        {"materials"},
        False,
    ),
    (
        "drum_rz_undocumented",
        [
            (
                '    """1 oz. Rz matte 4.0 um, drum 2.0 um."""',
                '    """1 oz. Rz matte 4.0 um."""',
            )
        ],
        {"materials"},
        False,
    ),
    (
        "roughness_scalar_from_matte_rz",
        [
            (
                "    thickness = 0.0381\n",
                "    thickness = 0.0381\n    roughness = 0.0025\n",
            )
        ],
        set(),
        False,
    ),
    (
        "roughness_scalar_from_drum_rz",
        [
            (
                "    thickness = 0.0381\n",
                "    thickness = 0.0381\n    roughness = 0.0008\n",
            )
        ],
        {"materials"},
        False,
    ),
    (
        "aspect_ratio_as_a_rules_attribute",
        [(RULES_TAIL, RULES_TAIL + "    max_laser_aspect_ratio = 1.25\n")],
        {"capability_not_attributes"},
        False,
    ),
    (
        "mechanical_ratio_as_a_rules_attribute",
        [(RULES_TAIL, RULES_TAIL + "    max_mechanical_aspect_ratio = 10.0\n")],
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
        "via_aspect_ratio_on_the_substrate",
        [(SUBSTRATE_HEAD, SUBSTRATE_HEAD + "    UV1_ASPECT = 0.75\n")],
        set(),
        False,
    ),
    (
        "tolerance_of_ten_percent_on_the_rules",
        [(RULES_TAIL, RULES_TAIL + "    thickness_tolerance_pct = 10\n")],
        set(),
        False,
    ),
    (
        "laser_ratio_undocumented",
        [(RULES_DOC, RULES_DOC.replace("laser aspect ratio 1.25:1, ", ""))],
        {"capability_documented"},
        False,
    ),
    (
        "mechanical_ratio_undocumented",
        [
            (
                RULES_DOC,
                RULES_DOC.replace("mechanical aspect ratio\n    10:1, ", "\n    "),
            )
        ],
        {"capability_documented"},
        False,
    ),
    (
        "stacked_levels_undocumented",
        [(RULES_DOC, RULES_DOC.replace("2 stacked levels, ", ""))],
        {"capability_documented"},
        False,
    ),
    (
        "stacked_levels_only_as_a_layer_name",
        [
            (
                RULES_DOC,
                RULES_DOC.replace("2 stacked levels", "stacked microvias L1 to L2"),
            )
        ],
        {"capability_documented"},
        False,
    ),
    (
        "dielectric_minimum_undocumented",
        [(RULES_DOC, RULES_DOC.replace(", dielectric 2.5 mil", ""))],
        {"capability_documented"},
        False,
    ),
    (
        "dielectric_minimum_without_its_unit",
        [(RULES_DOC, RULES_DOC.replace("dielectric 2.5 mil", "dielectric 2.5"))],
        {"capability_documented"},
        False,
    ),
    (
        "mechanical_drill_in_mm",
        [
            (
                RULES_DOC,
                RULES_DOC.replace(
                    "mechanical drill 6.0 mil", "mechanical drill 0.1524 mm"
                ),
            )
        ],
        set(),
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
    tmp_path: Path, edits: Edits, failing: set[str], noted: bool
) -> None:
    code, stdout = grade("report", edited(tmp_path, BOARD, edits), TWIN)
    assert outcomes(stdout) == {
        name: "FAIL" if name in failing else "PASS" for name in REPORT_CHECKS
    }, stdout
    assert code == (1 if failing else 0), stdout
    assert ("NOTE  only the four min_copper_* fields" in stdout) == noted, stdout


def in_substrate(body: str) -> Edits:
    """TICSubstrate gets an __init__ with ``body``: it runs only while grading."""
    return [
        (SUBSTRATE_HEAD, SUBSTRATE_HEAD + "\n    def __init__(self) -> None:\n" + body)
    ]


@needs_jitx
@pytest.mark.parametrize(
    ("edits", "line"),
    [
        pytest.param(
            [(SUBSTRATE_HEAD, SUBSTRATE_HEAD + "    import sys\n\n    sys.exit(0)\n")],
            "candidate does not import",
            id="sys_exit_at_import",
        ),
        pytest.param(
            [(SUBSTRATE_HEAD, SUBSTRATE_HEAD + "    import os\n\n    os._exit(0)\n")],
            "grading stopped before every check ran",
            id="os_exit_at_import",
        ),
        pytest.param(
            in_substrate("        import sys\n\n        sys.exit(0)\n"),
            "grading stopped before every check ran",
            id="sys_exit_while_grading",
        ),
        pytest.param(
            in_substrate("        import os\n\n        os._exit(0)\n"),
            "grading stopped before every check ran",
            id="os_exit_while_grading",
        ),
        pytest.param(
            [(SUBSTRATE_HEAD, SUBSTRATE_HEAD + "    while True:\n        pass\n")],
            "the import pre-flight did not finish within 10 s",
            id="hang_at_import",
        ),
    ],
)
def test_a_candidate_that_ends_the_grading_early_is_red(
    tmp_path: Path, edits: Edits, line: str
) -> None:
    code, stdout = grade(
        "report", edited(tmp_path, BOARD, edits), TWIN, "--timeout", "10"
    )
    assert code == 1, stdout
    assert f"FAIL  {line}" in stdout, stdout
    assert "PASS  all" not in stdout, stdout


IN_GRADING = 'if __name__ != "_candidate_preflight":\n'
"""Guards a tail so it runs in the grading child only, not the pre-flight."""

FAKED_PASSES = (
    "    for _name in "
    + repr(sorted(REPORT_CHECKS))
    + ':\n        print(f"PASS  {_name}", flush=True)\n'
)
EXIT_0_AT_EXIT = "    _atexit.register(lambda: (_sys.stdout.flush(), _os._exit(0)))\n"
CORE_DK = "    dielectric_coefficient = 3.60\n    loss_tangent = 0.0080"
CORE_DK_WRONG = [(CORE_DK, CORE_DK.replace("3.60", "3.70"))]
"""Fails materials, so a tail that hides a red has one to hide."""
HEADER = "import atexit as _atexit, os as _os, re as _re, sys as _sys\n"
FORGE = (
    "def _forge():\n"
    '    _os.write(1, b"\\nERROR  a library the candidate imports does not import: '
    "ModuleNotFoundError: No module named 'jitx_rf'\\n\")\n"
    "    _os._exit(3)\n"
)
"""Ends the process on an environment line the board wrote itself."""

# (id, board.py edits, tail appended to board.py, line the parent prints)
TAMPER_ROWS: list[tuple[str, Edits, str, str]] = [
    (
        "passes_printed_before_the_checks_then_exit_0",
        CORE_DK_WRONG,
        HEADER + IN_GRADING + FAKED_PASSES + EXIT_0_AT_EXIT,
        "more than one line for",
    ),
    (
        "stdout_rewritten_fail_to_pass_then_exit_0",
        CORE_DK_WRONG,
        HEADER
        + IN_GRADING
        + "    class _Rewrite:\n"
        + "        def __init__(self, inner):\n"
        + "            self.inner = inner\n"
        + "        def write(self, text):\n"
        + '            return self.inner.write(_re.sub(r"^FAIL  (\\w+):.*$", '
        + 'r"PASS  \\1", text, flags=_re.M))\n'
        + "        def flush(self):\n"
        + "            self.inner.flush()\n"
        + "        def __getattr__(self, name):\n"
        + "            return getattr(self.inner, name)\n"
        + "    _sys.stdout = _Rewrite(_sys.stdout)\n"
        + EXIT_0_AT_EXIT,
        "FAIL  1 of 11 checks failed",
    ),
    (
        "token_read_from_the_environment",
        [],
        HEADER
        + IN_GRADING
        + FAKED_PASSES
        + "    print(f\"DONE {_os.environ.get('GRADE_CHECKS_NONCE')}\", flush=True)\n"
        + "    _os._exit(0)\n",
        "FAIL  grading stopped before every check ran",
    ),
    (
        "exits_1_after_every_check_passed",
        [],
        HEADER + IN_GRADING + "    _atexit.register(_os._exit, 1)\n",
        "every check passed, but the grader exited 1",
    ),
    (
        "prints_after_the_last_line",
        [],
        HEADER + IN_GRADING + '    _atexit.register(print, "at exit")\n',
        "1 line(s) after the line that ends the grading",
    ),
    (
        "preflight_exits_3_in_environment_wording",
        [],
        HEADER
        + 'if __name__ == "_candidate_preflight":\n'
        + "    print(\"No module named 'jitx_rf_helpers'\", flush=True)\n"
        + "    _os._exit(3)\n",
        "FAIL  the import pre-flight exited 3 on board.py without one of its own",
    ),
    (
        "preflight_exits_3_with_an_error_line_of_its_own",
        [],
        HEADER
        + 'if __name__ == "_candidate_preflight":\n'
        + "    print(\"ERROR  No module named 'jitx_rf_helpers'\", flush=True)\n"
        + "    _os._exit(3)\n",
        "FAIL  the import pre-flight exited 3 on board.py without one of its own",
    ),
    (
        "environment_wording_printed_before_its_own_error",
        [],
        "print(\"note: No module named 'jitx_rf_helpers'; using built-in defaults\")\n"
        + "EXTRA = UNDEFINED_NAME\n",
        "FAIL  candidate does not import: NameError: name 'UNDEFINED_NAME'",
    ),
    (
        "error_line_forged_by_an_exit_handler",
        [],
        HEADER + FORGE + "_atexit.register(_forge)\nEXTRA = UNDEFINED_NAME\n",
        "FAIL  candidate does not import: NameError: name 'UNDEFINED_NAME'",
    ),
    (
        "error_line_forged_by_a_thread",
        [],
        HEADER
        + "import threading as _threading, time as _time\n"
        + FORGE.replace("def _forge():\n", "def _forge():\n    _time.sleep(2)\n")
        + "_threading.Thread(target=_forge).start()\nEXTRA = UNDEFINED_NAME\n",
        "FAIL  candidate does not import: NameError: name 'UNDEFINED_NAME'",
    ),
]
"""Candidates that try to end the grading looking green, or looking like an
environment problem. Several are the kind of code the grader does not claim
to stop (see check_runner.py); each of these is a red all the same."""


@needs_jitx
@pytest.mark.parametrize(
    ("edits", "tail", "line"),
    [
        pytest.param(edits, tail, line, id=name)
        for name, edits, tail, line in TAMPER_ROWS
    ],
)
def test_a_candidate_that_tampers_with_the_grading_is_red(
    tmp_path: Path, edits: Edits, tail: str, line: str
) -> None:
    board = edited(tmp_path, BOARD, edits)
    with board.open("a", encoding="utf-8") as file:
        file.write("\n\n" + tail)
    code, stdout = grade("report", board, TWIN)
    assert code == 1, stdout
    assert line in stdout, stdout
    assert "PASS  all" not in stdout, stdout
    for wording in ENVIRONMENT_WORDING:
        assert not re.search(wording, stdout, re.IGNORECASE), (wording, stdout)


@needs_jitx
@pytest.mark.parametrize(
    "head",
    [
        'print("building the TIC-8L substrate")\n',
        'import sys\n\nsys.stdout.write("progress: 1/1")\n',
        'import atexit\n\natexit.register(print, "")\n',
        'import atexit\n\natexit.register(print, "   ")\n',
    ],
    ids=[
        "a line printed at import",
        "a partial line written at import",
        "an empty line printed at exit",
        "a line of spaces printed at exit",
    ],
)
def test_a_correct_board_that_prints_passes(tmp_path: Path, head: str) -> None:
    """What a board prints is not a check line, even a line with no end, and
    a blank line after the last one is not a line after it."""
    board = tmp_path / BOARD.name
    board.write_text(head + BOARD.read_text(encoding="utf-8"), encoding="utf-8")
    code, stdout = grade("report", board, TWIN)
    assert code == 0, stdout
    assert f"PASS  all {len(REPORT_CHECKS)} checks passed" in stdout, stdout


MULTI_LINE_IMPORT_ERROR = """raise ImportError(
    "\\n\\nIMPORTANT: PLEASE READ THIS FOR ADVICE ON HOW TO SOLVE THIS ISSUE!\\n\\n"
    "Importing the fastmath C-extensions failed.\\n\\n"
    "Original error was: No module named 'fastmath._core'\\n"
)
"""
"""A library that fails to import with a message over several lines, as
compiled extensions do."""


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
print("loading fastmath")
"""
"""A replacement sys.stdout that holds what is printed until it is flushed,
then hands it to sys.__stdout__, which holds it until that is flushed: what
the board printed reaches the pipe before the verdict line only when the
replacement is flushed first."""


@needs_jitx
@pytest.mark.parametrize(
    "head",
    [
        "",
        "import io\nimport sys\n\nsys.stdout = io.StringIO()\n",
        'import atexit\n\natexit.register(print, "board: done")\n',
        WRITES_THROUGH,
    ],
    ids=[
        "nothing else",
        "sys.stdout replaced",
        "an exit handler that prints",
        "sys.stdout replaced by one that writes through",
    ],
)
def test_a_library_import_error_over_several_lines_is_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, head: str
) -> None:
    """The pre-flight's environment line holds the whole message on one line,
    so it is still the last line and still reads as an environment problem,
    whatever the board did to stdout before it imported the library."""
    site = tmp_path / "site" / "fastmath"
    site.mkdir(parents=True)
    (site / "__init__.py").write_text(MULTI_LINE_IMPORT_ERROR, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(site.parent))
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    board = candidate / BOARD.name
    board.write_text(
        head + "import fastmath  # noqa: F401\n" + BOARD.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    code, stdout = grade("report", board, TWIN)
    assert code == 2, stdout
    last = stdout.strip().splitlines()[-1]
    assert last.startswith(
        "ERROR  a library the candidate imports does not import: ImportError: "
        "IMPORTANT: PLEASE READ"
    ), stdout
    assert "No module named 'fastmath._core'" in last, stdout


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
    ("argv", "code", "stream", "line"),
    [
        pytest.param(
            ["report", BOARD, "missing.csv"],
            2,
            "out",
            "ERROR  missing.csv",
            id="no_csv",
        ),
        pytest.param(
            ["report", "missing.py", TWIN], 1, "out", "FAIL  candidate", id="no_board"
        ),
        pytest.param(["symmetric"], 2, "err", "usage:", id="no_board_argument"),
        pytest.param(
            ["report", BOARD, TWIN, "--timeout", "60"],
            0,
            "out",
            "PASS  all 11 checks passed",
            id="timeout_after_the_arguments",
        ),
        pytest.param(
            ["symmetric", SYMMETRIC, "--timeout", "0"],
            2,
            "out",
            "ERROR  --timeout",
            id="timeout_not_positive",
        ),
    ],
)
def test_usage_as_the_usage_line_documents_it(
    argv: list[str | Path], code: int, stream: str, line: str
) -> None:
    run = run_grader(*argv)
    assert run.returncode == code, run.stdout + run.stderr
    assert line in (run.stdout if stream == "out" else run.stderr), (
        run.stdout + run.stderr
    )


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
SHOWN_TRAPS = [
    (
        r"9\s+Dielectric\s",
        "0.1000",
        "the L4-L5 prepreg's mm cell, against its 4.00 mil",
    ),
    (r"UV-1\s+Microvia\s", "2.50", "UV-1's annular ring as Rev B stated it"),
    (r"BD-1\s+Backdrilled\s", "80.00 (2.0320)", "BD-1's full drilled depth"),
]
"""(start of the PDF table row, value, why): each trap value is looked for on
its own row, since the same figure appears elsewhere in the PDF."""

STATED_PROSE = [
    (
        "the mil value controls.",
        "the Units row declaring mil controlling over the mm cells",
    ),
    (
        "C 2026-10-06 UV-1 capture pad enlarged from 9.0 mil to 10.0 mil",
        "the Rev C row enlarging UV-1's pad",
    ),
    (
        "* Aspect ratio = depth / finished hole.",
        "the footnote that gives the aspect-ratio depth basis",
    ),
]
"""(words, why): prose traps the PDF states in a sentence, not a table cell,
looked for with whitespace collapsed and ligatures spelled out."""

LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl"})
"""pdftotext writes the ff, fi and fl ligatures the PDF's font uses as one
character each."""


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
    absent: list[str] = []
    for row, value, why in SHOWN_TRAPS:
        lines = [line for line in text.splitlines() if re.match(rf"\s*{row}", line)]
        token = rf"(?<![\d.]){re.escape(value)}(?![\d])"
        if len(lines) != 1 or not re.search(token, lines[0]):
            absent.append(f"{value}: {why}")
    assert not absent, absent
    prose = " ".join(text.translate(LIGATURES).split())
    unstated = [why for words, why in STATED_PROSE if words not in prose]
    assert not unstated, unstated
