"""grade_fenced_rf.py fails a check exactly when the candidate breaks it.

The hand-written known-good board and design pass every check. Each table row
makes one edit to them and names the checks it must fail, through the
grader's CLI as the case runs it; a row that names none is a valid variant
the grader must accept. A candidate that ends the grading early must be a
red. The grader's fencing values are checked against the case's spec, since
the grader holds them as constants. Tests that need jitx skip, with the
reason, without it.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import import_candidate
import pytest

CHECKS = Path(__file__).resolve().parent
GRADER = CHECKS / "grade_fenced_rf.py"
CASE_C = CHECKS / "testdata" / "case_c"
FIXTURES = CHECKS.parent / "cases" / "fixtures"
CSV = FIXTURES / "rf_PC-6L_Fab-Stackup_RevA.csv"
SPEC = FIXTURES / "rf_fence_spec.txt"

ALL_CHECKS = [
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

needs_jitx = pytest.mark.skipif(
    importlib.util.find_spec("jitx") is None,
    reason="jitx is not importable; install jitx to run this test",
)

Edits = list[tuple[str, str]]


def outcomes(stdout: str) -> dict[str, str]:
    """Check name -> ``PASS`` or ``FAIL``, from the grader's per-check lines."""
    return dict(
        (name, status)
        for status, name in re.findall(
            r"^(PASS|FAIL)  (\w+)(?::|$)", stdout, re.MULTILINE
        )
    )


def write(tmp_path: Path, name: str, edits: Edits) -> Path:
    text = (CASE_C / name).read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, f"edit target not found once in {name}: {old!r}"
        text = text.replace(old, new)
    out = tmp_path / name
    out.write_text(text, encoding="utf-8")
    return out


def grade(tmp_path: Path, board: Edits, design: Edits, *extra: str) -> tuple[int, str]:
    run = subprocess.run(
        [
            sys.executable,
            str(GRADER),
            str(write(tmp_path, "board.py", board)),
            str(write(tmp_path, "design.py", design)),
            str(CSV),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return run.returncode, run.stdout


CPW_FENCE = "    CPW_FENCE = ViaFencePattern(pitch=0.50, offset=0.40, num_rows=1)\n"
PAIR_FENCE = "    PAIR_FENCE = ViaFencePattern(pitch=0.50, offset=0.60, num_rows=1)\n"
CPW_GEOMETRY = "            .geometry(KeepOut, 0.60, layers=LayerSet(1), pour=True)\n"
CAVITY_RULE = "        UV1, ViaFencePattern(pitch=0.50, offset=0.30, num_rows=1)\n"
CAVITY_RULE_HEAD = "design_constraint(CavityFence(), priority=20)"
CAVITY_RULE_LINES = (
    "    cavity_fence = design_constraint(CavityFence(), priority=20).fence_via(\n"
    + CAVITY_RULE
    + "    )\n"
)
POUR = "        self.cavity_pour = Pour(CAVITY, layer=0)\n"
KEEPOUT = "KeepOut(CAVITY, layers=LayerSet(0), pour=True, via=True)"
SUBSTRATE_TAIL = (
    "    cavity_fence = design_constraint(CavityFence(), priority=20).fence_via(\n"
)
TAG_CLASS = "class CavityFence(Tag):\n"
UV2_SPAN = "        start_layer = -1\n        stop_layer = -2\n"
L6_LAYER = (
    "            .reference({-2: 3 * 0.100})\n"
    "            .fence(UV2, PAIR_FENCE, reference_layer=-2),\n"
)
L4_PAIR_LAYER = (
    "            3: DifferentialRoutingStructure.Layer(\n"
    "                trace_width=0.16,\n"
    "                pair_spacing=0.20,\n"
    "                clearance=0.40,\n"
    "                velocity=phase_velocity(2.68),\n"
    "                insertion_loss=0.007,\n"
    "            ).reference({2: 3 * 0.200, 4: 3 * 0.200}),\n"
)
DESIGN_RULE = (
    "        self.cavity_fence = design_constraint(CavityFence(), priority=20).fence_via(\n"
    "            RFSubstrate.UV1, ViaFencePattern(pitch=0.50, offset=0.30, num_rows=1)\n"
    "        )\n"
)

# (id, board.py edits, design.py edits, checks that must fail)
ROWS: list[tuple[str, Edits, Edits, set[str]]] = [
    ("known_good", [], [], set()),
    (
        "missing_mandatory_fab_rule",
        [("    min_hole_to_hole = 0.250\n", "")],
        [],
        {"design_translates", "structures_translate"},
    ),
    (
        "cpw_pitch",
        [(CPW_FENCE, CPW_FENCE.replace("pitch=0.50", "pitch=0.45"))],
        [],
        {"cpw_fence"},
    ),
    (
        "cpw_offset_centre_to_centre",
        [(CPW_FENCE, CPW_FENCE.replace("offset=0.40", "offset=0.54"))],
        [],
        {"cpw_fence"},
    ),
    (
        "cpw_initial_offset_as_spec",
        [
            (
                CPW_FENCE,
                CPW_FENCE.replace("offset=0.40", "offset=0.25, initial_offset=0.40"),
            )
        ],
        [],
        set(),
    ),
    (
        "cpw_two_rows",
        [(CPW_FENCE, CPW_FENCE.replace("num_rows=1", "num_rows=2"))],
        [],
        {"cpw_fence"},
    ),
    (
        "cpw_fenced_with_the_through_via",
        [(".fence(UV1, CPW_FENCE", ".fence(TH1, CPW_FENCE")],
        [],
        {"cpw_fence"},
    ),
    (
        "cpw_fence_tied_to_l3",
        [("CPW_FENCE, reference_layer=1)", "CPW_FENCE, reference_layer=2)")],
        [],
        {"cpw_fence"},
    ),
    (
        "cpw_keepout_on_l2_and_l3",
        [(CPW_GEOMETRY, CPW_GEOMETRY.replace("LayerSet(1)", "LayerSet(1, 2)"))],
        [],
        {"cpw_keepout"},
    ),
    (
        "cpw_keepout_width",
        [(CPW_GEOMETRY, CPW_GEOMETRY.replace("0.60", "0.80"))],
        [],
        {"cpw_keepout"},
    ),
    (
        "cpw_keepout_not_for_pours",
        [(CPW_GEOMETRY, CPW_GEOMETRY.replace("pour=True", "pour=False, route=True"))],
        [],
        {"cpw_keepout"},
    ),
    (
        "pair_offset",
        [(PAIR_FENCE, PAIR_FENCE.replace("offset=0.60", "offset=0.40"))],
        [],
        {"pair_fences"},
    ),
    (
        "pair_l6_fenced_with_the_top_via",
        [(".fence(UV2, PAIR_FENCE", ".fence(UV1, PAIR_FENCE")],
        [],
        {"pair_fences"},
    ),
    (
        "pair_l6_unfenced",
        [(L6_LAYER, "            .reference({-2: 3 * 0.100}),\n")],
        [],
        {"pair_fences"},
    ),
    ("pair_adds_l4", [(L6_LAYER, L6_LAYER + L4_PAIR_LAYER)], [], {"pair_fences"}),
    (
        "uv2_coded_from_l5_to_l6",
        [(UV2_SPAN, "        start_layer = -2\n        stop_layer = -1\n")],
        [],
        set(),
    ),
    (
        "cpw_references_the_voided_l2",
        [
            (
                "            .reference({2: 3 * 0.300})\n",
                "            .reference({1: 3 * 0.100})\n",
            )
        ],
        [],
        {"references"},
    ),
    (
        "cavity_fence_inset",
        [(CAVITY_RULE, CAVITY_RULE.replace("offset=0.30", "offset=-0.30"))],
        [],
        {"cavity_rule"},
    ),
    (
        "cavity_fenced_with_the_through_via",
        [(CAVITY_RULE, CAVITY_RULE.replace("UV1,", "TH1,"))],
        [],
        {"cavity_rule"},
    ),
    (
        "cavity_rule_on_two_tags",
        [
            (TAG_CLASS, "class Shielded(Tag):\n    pass\n\n\n" + TAG_CLASS),
            (
                CAVITY_RULE_HEAD,
                "design_constraint(CavityFence() & Shielded(), priority=20)",
            ),
        ],
        [],
        {"cavity_rule"},
    ),
    (
        "fence_rule_in_the_design",
        [(CAVITY_RULE_LINES, "")],
        [
            (
                "from jitx import Pour\n",
                "from jitx import Pour\n"
                "from jitx.constraints import ViaFencePattern, design_constraint\n",
            ),
            (KEEPOUT + "\n", KEEPOUT + "\n" + DESIGN_RULE),
        ],
        {"cavity_rule"},
    ),
    (
        "cavity_pour_untagged",
        [],
        [("        CavityFence().assign(self.cavity_pour)\n", "")],
        {"cavity_pour"},
    ),
    (
        "cavity_pour_outline",
        [],
        [
            (
                POUR,
                "        self.cavity_pour = Pour(rectangle(4.0, 3.5).at(5.0, 3.0), layer=0)\n",
            )
        ],
        {"cavity_pour"},
    ),
    (
        "cavity_pour_out_of_the_vias_reach",
        [],
        [(POUR, POUR.replace("layer=0", "layer=2"))],
        {"cavity_pour"},
    ),
    (
        "cavity_pour_on_l2_keepout_on_l1",
        [],
        [(POUR, POUR.replace("layer=0", "layer=1"))],
        set(),
    ),
    (
        "cavity_keepouts_on_l1_and_l2",
        [],
        [
            (POUR, POUR.replace("layer=0", "layer=1")),
            (
                KEEPOUT + "\n",
                KEEPOUT
                + "\n        self.l2_keepout = "
                + KEEPOUT.replace("LayerSet(0)", "LayerSet(1)")
                + "\n",
            ),
        ],
        set(),
    ),
    (
        "cavity_keepout_on_l2_only",
        [],
        [(KEEPOUT, KEEPOUT.replace("LayerSet(0)", "LayerSet(1)"))],
        {"cavity_keepout"},
    ),
    (
        "cavity_keepout_not_for_pours",
        [],
        [(KEEPOUT, KEEPOUT.replace("pour=True", "pour=False"))],
        {"cavity_keepout"},
    ),
    (
        "pour_isolate",
        [],
        [(POUR, POUR.replace("layer=0)", "layer=0, isolate=0.2)"))],
        {"no_isolate"},
    ),
    (
        "pour_isolate_set_by_setattr",
        [],
        [(POUR, POUR + '        setattr(self.cavity_pour, "isolate", 0.2)\n')],
        {"no_isolate"},
    ),
    (
        "trace_width_rule_in_the_substrate",
        [
            (
                SUBSTRATE_TAIL,
                "    width_rule = design_constraint(CavityFence()).trace_width(0.2)\n"
                + SUBSTRATE_TAIL,
            )
        ],
        [],
        {"substrate_rules"},
    ),
    (
        "clearance_rule_in_the_substrate",
        [
            (
                SUBSTRATE_TAIL,
                "    gap_rule = design_constraint(CavityFence(), CavityFence()).clearance(0.2)\n"
                + SUBSTRATE_TAIL,
            )
        ],
        [],
        {"substrate_rules"},
    ),
]


@needs_jitx
@pytest.mark.parametrize(
    ("board", "design", "failing"),
    [
        pytest.param(board, design, failing, id=name)
        for name, board, design, failing in ROWS
    ],
)
def test_checks_fail_only_on_their_own_defect(
    tmp_path: Path, board: Edits, design: Edits, failing: set[str]
) -> None:
    code, stdout = grade(tmp_path, board, design)
    assert outcomes(stdout) == {
        name: "FAIL" if name in failing else "PASS" for name in ALL_CHECKS
    }, stdout
    assert code == (1 if failing else 0), stdout


@needs_jitx
def test_a_design_that_does_not_import_is_red(tmp_path: Path) -> None:
    code, stdout = grade(
        tmp_path,
        [],
        [("from board import CavityFence, RFSubstrate", "from board import Missing")],
    )
    assert code == 1
    assert stdout.startswith(
        "FAIL  candidate does not import: cannot import name 'Missing' from 'board'"
    ), stdout
    # Eval harnesses read Python's own import wording as an environment error.
    assert "ImportError: cannot import name" not in stdout, stdout
    assert "No module named" not in stdout, stdout


DESIGN_TAIL = "    circuit = RFCircuit()\n"


def ends_in_init(body: str) -> Edits:
    """RFDesign gets an __init__ with ``body``: it runs only while grading."""
    return [(DESIGN_TAIL, DESIGN_TAIL + "\n    def __init__(self) -> None:\n" + body)]


@needs_jitx
@pytest.mark.parametrize(
    ("design", "line"),
    [
        pytest.param(
            [
                (
                    "class RFDesign(Design):\n",
                    "sys.exit(0)\n\n\nclass RFDesign(Design):\n",
                )
            ]
            + [("from board import", "import sys\n\nfrom board import")],
            "candidate does not import",
            id="sys_exit_at_import",
        ),
        pytest.param(
            ends_in_init("        import sys\n\n        sys.exit(0)\n"),
            "grading stopped before every check ran",
            id="sys_exit_while_grading",
        ),
        pytest.param(
            ends_in_init("        import os\n\n        os._exit(0)\n"),
            "grading stopped before every check ran",
            id="os_exit_while_grading",
        ),
        pytest.param(
            ends_in_init("        while True:\n            pass\n"),
            "grading ran past 10 s",
            id="hang_while_grading",
        ),
    ],
)
def test_a_candidate_that_ends_the_grading_early_is_red(
    tmp_path: Path, design: Edits, line: str
) -> None:
    code, stdout = grade(tmp_path, [], design, "--timeout", "10")
    assert code == 1, stdout
    assert f"FAIL  {line}" in stdout, stdout
    assert "PASS  all" not in stdout, stdout


ENVIRONMENT_MESSAGE = (
    "sh: 1: pyright: not found; bash: jitx: command not found; "
    "No module named 'jitx.unitz'; Connection refused by ws://127.0.0.1 refused; "
    "WebSocket closed; coroutine 'run' was never awaited; "
    "No such file or directory: '/usr/bin/python3'"
)
"""A candidate's own message carrying wording an eval harness reads as an
environment problem."""


@needs_jitx
@pytest.mark.parametrize(
    ("design", "line"),
    [
        pytest.param(
            ends_in_init(f"        raise RuntimeError({ENVIRONMENT_MESSAGE!r})\n"),
            "FAIL  design_translates: RuntimeError: sh: 1: pyright: missing;",
            id="raised_while_grading",
        ),
        pytest.param(
            [
                (
                    "class RFDesign(Design):\n",
                    f"print({ENVIRONMENT_MESSAGE!r}, flush=True)\n\n\n"
                    "class RFDesign(Design):\n",
                )
            ]
            + ends_in_init("        import os\n\n        os._exit(0)\n"),
            "sh: 1: pyright: missing;",
            id="printed_at_import",
        ),
        pytest.param(
            [
                (
                    "class RFDesign(Design):\n",
                    "raise RuntimeError('pyright: not found')\n\n\n"
                    "class RFDesign(Design):\n",
                )
            ],
            "FAIL  candidate does not import: RuntimeError: pyright: missing",
            id="preflight_red",
        ),
        pytest.param(
            ends_in_init(
                "        import os, sys\n\n"
                f"        sys.stderr.write({ENVIRONMENT_MESSAGE!r})\n"
                "        sys.stderr.flush()\n"
                "        os._exit(0)\n"
            ),
            "sh: 1: pyright: missing;",
            id="written_to_stderr_while_grading",
        ),
    ],
)
def test_a_red_never_reads_as_an_environment_problem(
    tmp_path: Path, design: Edits, line: str
) -> None:
    code, stdout = grade(tmp_path, [], design)
    assert code == 1, stdout
    assert line in stdout, stdout
    for wording in import_candidate.ENVIRONMENT_WORDING:
        assert not re.search(wording, stdout, re.IGNORECASE), (wording, stdout)


@needs_jitx
def test_a_candidate_that_prints_an_error_line_and_exits_2_is_red(
    tmp_path: Path,
) -> None:
    design = ends_in_init(
        "        import sys\n\n"
        "        print('ERROR  the grader needs jitx', flush=True)\n"
        "        sys.exit(2)\n"
    )
    code, stdout = grade(tmp_path, [], design)
    assert code == 1, stdout
    assert "FAIL  grading stopped before every check ran" in stdout, stdout


@pytest.mark.parametrize(
    "text",
    [
        "python3: No module named pyright",
        'board.py:1 - error: Import "jitx.unitz" could not be resolved '
        "(reportMissingImports)",
        "ImportError: cannot import name 'Foo' from 'jitx'",
        '"Foo" is unknown import symbol (reportAttributeAccessIssue)',
        "bash: jitx: command not found",
        "sh: 1: pyright: not found",
        "[Errno 2] No such file or directory: '/opt/venv/bin/python3.12'",
        "RuntimeWarning: coroutine 'connect' was never awaited",
        "the launcher exited with 1 before announcing itself",
        "Error occurred when attempting to open the user statistics file",
        "ConnectionRefusedError: [Errno 61] Connection refused",
        "WebSocket handshake failed",
        "ws://127.0.0.1:9000 refused",
    ],
)
def test_scrub_rewords_every_environment_phrase(text: str) -> None:
    assert any(
        re.search(wording, text, re.IGNORECASE)
        for wording in import_candidate.ENVIRONMENT_WORDING
    ), text
    scrubbed = import_candidate.scrub(text)
    for wording in import_candidate.ENVIRONMENT_WORDING:
        assert not re.search(wording, scrubbed, re.IGNORECASE), (wording, scrubbed)


RUN_CASES = "RUN_CASES_PY"
"""The environment variable naming the eval harness's run_cases.py, for the
test that compares its ENV_PATTERNS with ENVIRONMENT_WORDING."""


def harness() -> ModuleType:
    """The eval harness's run_cases module: from the file RUN_CASES_PY names,
    or importable as run_cases. Skips, with the reason, when it is neither."""
    named = os.environ.get(RUN_CASES, "").strip()
    if named:
        spec = importlib.util.spec_from_file_location("run_cases", named)
    elif importlib.util.find_spec("run_cases") is not None:
        spec = importlib.util.find_spec("run_cases")
    else:
        spec = None
    if spec is None or spec.loader is None:
        pytest.skip(
            "run_cases.py, the eval harness, is not importable; set "
            f"{RUN_CASES} to its path to compare its ENV_PATTERNS"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_environment_wording_is_the_harness_list() -> None:
    """scrub rewords what ENVIRONMENT_WORDING lists, so the list must be the
    harness's: a pattern added there and not here would let a red through
    as an environment problem."""
    patterns = [pattern for pattern, _ in harness().ENV_PATTERNS]
    assert import_candidate.ENVIRONMENT_WORDING == patterns


@needs_jitx
def test_the_grader_holds_what_the_spec_states() -> None:
    import grade_fenced_rf as g

    spec = " ".join(SPEC.read_text(encoding="utf-8").split())
    # Each value with its unit or the layers it names, not the spec's prose.
    stated = [
        f"pitch {g.FENCE_PITCH:.2f} mm",
        f"{g.CPW_OFFSET:.2f} mm out from the trace edge",
        f"L{g.CPW_KEEPOUT_LAYER} copper under the line, {g.CPW_KEEPOUT_WIDTH:.2f} mm wide",
        f"{g.PAIR_OFFSET:.2f} mm out from the outer trace edge",
        f"{g.CAVITY_OFFSET:.2f} mm outside the outline",
        f"{g.CAVITY_SIZE[0]:.1f} x {g.CAVITY_SIZE[1]:.1f} mm",
        f"({g.CAVITY_CENTRE[0]:.1f}, {g.CAVITY_CENTRE[1]:.1f}) mm",
        f"{g.BOARD_SIZE[0]:.1f} x {g.BOARD_SIZE[1]:.1f} mm",
        f"UV-1 (L{g.CPW_LAYER} to L{g.CPW_FENCE_PLANE})",
        *(f"to L{plane} on L{layer}" for layer, plane in g.PAIR_FENCES.items()),
        f"cavity on L{g.CAVITY_LAYER}",
        f"landing on L{g.CAVITY_FENCE_PLANE}",
    ]
    missing = [phrase for phrase in stated if phrase not in spec]
    assert not missing, missing
