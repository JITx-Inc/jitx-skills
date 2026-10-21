"""The PDF-report, no-report and fenced-RF cases' deterministic commands pass
on the known-good test data, run exactly as each case JSON writes them.

Each command runs from the repository root through the shell, with
``<output>`` replaced by a directory holding the known-good files under the
names the case asks the runner for, and with this interpreter's directory
first on ``PATH`` so ``python3`` is the one running the tests. This is the
seam between the case files and the graders: a grader flag a case relies on
(such as the ``-k`` selections passed to grade_substrate.py), a renamed test
or a stricter grader shows up here rather than in an eval run. A command
whose tool is not installed (pyright, or ruff for check_labels.py) skips with
the reason; a command that needs jitx skips without it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from import_candidate import ENVIRONMENT_WORDING

CHECKS = Path(__file__).resolve().parent
SKILL = CHECKS.parents[1]
REPO = SKILL.parents[1]
CASES = SKILL / "evals" / "cases"
TESTDATA = CHECKS / "testdata"

STAGED: dict[str, dict[str, Path]] = {
    "stackup-from-pdf-report.json": {"board.py": TESTDATA / "case_b" / "board.py"},
    "symmetric-4-layer-no-report.json": {
        "board.py": TESTDATA / "case_b" / "symmetric_board.py"
    },
    "fenced-rf-substrate.json": {
        "board.py": TESTDATA / "case_c" / "board.py",
        "design.py": TESTDATA / "case_c" / "design.py",
    },
    "substrate-api-retrieval.json": {
        "transcript.jsonl": TESTDATA / "case_e" / "transcript_reads_all.jsonl"
    },
}
"""Case file -> the known-good file to stage under each name the case uses."""


def commands() -> list[object]:
    params: list[object] = []
    for case in STAGED:
        data = json.loads((CASES / case).read_text(encoding="utf-8"))
        found = [
            (index, assertion["cmd"])
            for index, assertion in enumerate(data["assertions"])
            if assertion["check"] == "deterministic"
        ]
        assert found, f"{case} has no deterministic command"
        params += [
            pytest.param(case, cmd, id=f"{case.removesuffix('.json')}-{index}")
            for index, cmd in found
        ]
    return params


def missing_tool(cmd: str) -> str | None:
    """Why ``cmd`` cannot run here, or None when it can."""
    if importlib.util.find_spec("jitx") is None:
        return "jitx is not importable; install jitx to run this test"
    if "-m pyright" in cmd and importlib.util.find_spec("pyright") is None:
        return "pyright is not installed in this interpreter"
    ruff = importlib.util.find_spec("ruff") is not None or shutil.which("ruff")
    if "check_labels.py" in cmd and not ruff:
        return "ruff neither imports here nor is on PATH; check_labels.py needs it"
    return None


@pytest.mark.parametrize(("case", "cmd"), commands())
def test_case_command_passes_on_the_known_good_files(
    tmp_path: Path, case: str, cmd: str
) -> None:
    for name, source in STAGED[case].items():
        shutil.copyfile(source, tmp_path / name)
    run_in_repo(cmd, tmp_path)


def run_in_repo(cmd: str, output: Path, code: int = 0) -> str:
    """Run ``cmd`` as the case writes it, with ``<output>`` as ``output`` and
    ``<transcript>`` as ``output/transcript.jsonl``;
    its output, after failing unless it exits ``code``."""
    why = missing_tool(cmd)
    if why is not None:
        pytest.skip(why)
    command = cmd.replace("<output>", shlex.quote(str(output))).replace(
        "<transcript>", shlex.quote(str(output / "transcript.jsonl"))
    )
    env = {
        **os.environ,
        "PATH": os.pathsep.join([str(Path(sys.executable).parent), os.environ["PATH"]]),
    }
    run = subprocess.run(
        command,
        shell=True,
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == code, f"{command}\n{run.stdout}{run.stderr}"
    return run.stdout + run.stderr


CASE_B_DERIVED_CORE = """THICK_CORE = FINISHED - (
    2 * 0.0381 + 6 * INNER_CU + 2 * 0.0762 + 2 * 0.1270 + 2 * 0.1016
)"""
"""The known-good case B board's core, solved from the finished total exactly."""

CASE_B_ROUNDED = (
    ("INNER_CU = 0.0350", "INNER_CU = 1.38 * 0.0254"),
    (CASE_B_DERIVED_CORE, "THICK_CORE = 1.1359"),
)
"""1 oz inner copper as 1.38 mil, and the core solved from the total and
written to the report's 4 decimal places: correct, though its stack sums to
the stated totals only at the report's precision."""


def case_b_graders() -> list[object]:
    """Case B's grader commands, as its JSON writes them."""
    assertions = json.loads(
        (CASES / "stackup-from-pdf-report.json").read_text(encoding="utf-8")
    )["assertions"]
    return [
        pytest.param(assertion["cmd"], id=f"stackup-from-pdf-report-{index}")
        for index, assertion in enumerate(assertions)
        if assertion["check"] == "deterministic" and "grade_" in assertion["cmd"]
    ]


@pytest.mark.parametrize("cmd", case_b_graders())
def test_case_b_grades_a_core_written_at_the_report_precision(
    tmp_path: Path, cmd: str
) -> None:
    """Case B grades the stack's totals at the report's precision, so its
    graders pass a board whose core is the 4-place literal 1.1359 mm."""
    source = STAGED["stackup-from-pdf-report.json"]["board.py"].read_text(
        encoding="utf-8"
    )
    for old, new in CASE_B_ROUNDED:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    (tmp_path / "board.py").write_text(source, encoding="utf-8")
    run_in_repo(cmd, tmp_path)


RED_AT_IMPORT = {
    "exits 3 in environment wording": (
        "\nimport os as _os\n\n"
        'if __name__ == "_candidate_preflight":\n'
        "    print(\"No module named 'jitx_rf_helpers'\", flush=True)\n"
        "    _os._exit(3)\n"
    ),
    "prints environment wording, then fails": (
        "\nprint(\"note: No module named 'jitx_rf_helpers'; using built-in defaults\")\n"
        "EXTRA = UNDEFINED_NAME  # noqa: F821\n"
    ),
}
"""Tails that stop the case B board importing, each the candidate's fault."""


@pytest.mark.parametrize("tail", RED_AT_IMPORT.values(), ids=RED_AT_IMPORT.keys())
@pytest.mark.parametrize("cmd", case_b_graders())
def test_case_b_graders_read_a_board_that_does_not_import_as_red(
    tmp_path: Path, cmd: str, tail: str
) -> None:
    """Run as the case writes them, both graders call it a red, in no wording
    an eval harness reads as a missing environment."""
    source = STAGED["stackup-from-pdf-report.json"]["board.py"].read_text(
        encoding="utf-8"
    )
    (tmp_path / "board.py").write_text(source + tail, encoding="utf-8")
    output = run_in_repo(cmd, tmp_path, code=1)
    assert "FAIL  " in output, output
    for wording in ENVIRONMENT_WORDING:
        assert not re.search(wording, output, re.IGNORECASE), (wording, output)
