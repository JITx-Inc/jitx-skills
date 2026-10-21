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
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
    why = missing_tool(cmd)
    if why is not None:
        pytest.skip(why)
    for name, source in STAGED[case].items():
        shutil.copyfile(source, tmp_path / name)
    command = cmd.replace("<output>", shlex.quote(str(tmp_path)))
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
    assert run.returncode == 0, f"{command}\n{run.stdout}{run.stderr}"
