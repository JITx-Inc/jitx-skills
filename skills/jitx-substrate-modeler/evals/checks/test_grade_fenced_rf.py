"""grade_fenced_rf.py fails a check exactly when the candidate breaks it.

The hand-written known-good board and design pass every check. Each table row
makes one edit to them and names the checks it must fail, through the
grader's CLI as the case runs it. The grader's fencing values are checked
against the case's spec, since the grader holds them as constants. Tests that
need jitx skip, with the reason, without it.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

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


def grade(tmp_path: Path, board: Edits, design: Edits) -> tuple[int, str]:
    run = subprocess.run(
        [
            sys.executable,
            str(GRADER),
            str(write(tmp_path, "board.py", board)),
            str(write(tmp_path, "design.py", design)),
            str(CSV),
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
POUR = "        self.cavity_pour = Pour(CAVITY, layer=0)\n"
KEEPOUT = "KeepOut(CAVITY, layers=LayerSet(0), pour=True, via=True)"
RULES_TAIL = "    min_pth_pin_solder_clearance = 0.200\n"
SUBSTRATE_TAIL = (
    "    cavity_fence = design_constraint(CavityFence(), priority=20).fence_via(\n"
)
L6_LAYER = (
    "            .reference({-2: 3 * 0.100})\n"
    "            .fence(UV2, PAIR_FENCE, reference_layer=-2),\n"
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
        [
            (POUR, POUR.replace("layer=0", "layer=2")),
            (KEEPOUT, KEEPOUT.replace("LayerSet(0)", "LayerSet(0, 2)")),
        ],
        {"cavity_pour"},
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
    assert stdout.startswith("FAIL  candidate does not load: ImportError"), stdout


@needs_jitx
def test_the_grader_holds_what_the_spec_states() -> None:
    import grade_fenced_rf as g

    spec = " ".join(SPEC.read_text(encoding="utf-8").split())
    stated = [
        f"pitch {g.FENCE_PITCH:.2f} mm",
        f"{g.CPW_OFFSET:.2f} mm out from the trace edge",
        f"on L{g.CPW_KEEPOUT_LAYER}, {g.CPW_KEEPOUT_WIDTH:.2f} mm wide",
        f"{g.PAIR_OFFSET:.2f} mm out from the outer trace edge",
        f"{g.CAVITY_OFFSET:.2f} mm outside the outline",
        f"{g.CAVITY_SIZE[0]:.1f} x {g.CAVITY_SIZE[1]:.1f} mm rectangle centred at "
        f"({g.CAVITY_CENTRE[0]:.1f}, {g.CAVITY_CENTRE[1]:.1f}) mm",
        f"{g.BOARD_SIZE[0]:.1f} x {g.BOARD_SIZE[1]:.1f} mm rectangle",
        f"UV-1 (L{g.CPW_LAYER} to L{g.CPW_FENCE_PLANE}), tied to the L{g.CPW_FENCE_PLANE}",
        *(f"to L{plane} on L{layer}" for layer, plane in g.PAIR_FENCES.items()),
        f"cavity on L{g.CAVITY_LAYER}",
        f"landing on L{g.CAVITY_FENCE_PLANE}",
    ]
    missing = [phrase for phrase in stated if phrase not in spec]
    assert not missing, missing
