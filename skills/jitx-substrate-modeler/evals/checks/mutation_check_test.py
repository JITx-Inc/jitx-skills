"""mutation_check.py passes a test suite that reads the report FAB_CSV names,
and fails a suite that does not, or that cannot show it.

testdata/case_a/reads_report and testdata/case_a/constants_copy are the two
directories a reader can run the check on by hand. The other rows edit a copy
of the first. Every row runs the script as the eval runs it, so the pytest
children are real.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import fabcsv
import mutation_check
import pytest

CHECKS = Path(__file__).resolve().parent
SCRIPT = CHECKS / "mutation_check.py"
CASE_A = CHECKS / "testdata" / "case_a"
CASE_CSV = CHECKS.parent / "cases" / "fixtures" / "QCW-HDI12_Fab-Stackup_RevB.csv"
SUITE = Path("tests") / "test_board.py"


PYTHON_IMPORT_WORDING = ("No module named", "cannot import name")
"""Python's own words for a failed import. Eval harnesses read them as an
environment problem, so a red must not carry them."""


def run(output: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *flags, str(SCRIPT), str(output), str(CASE_CSV)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def edit(name: Path, old: str, new: str) -> Callable[[Path], None]:
    def apply(output: Path) -> None:
        path = output / name
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, old
        path.write_text(text.replace(old, new), encoding="utf-8")

    return apply


Change = Callable[[Path], None]


def suite(text: str) -> Change:
    """The suite replaced by one test file holding ``text``."""

    def apply(output: Path) -> None:
        (output / SUITE).write_text(text, encoding="utf-8")

    return apply


def write(name: str, text: str) -> Change:
    def apply(output: Path) -> None:
        (output / name).write_text(text, encoding="utf-8")

    return apply


def clutter(output: Path) -> None:
    """What a runner's directory may also hold: a virtualenv, a git directory
    and a symlink to nothing."""
    (output / ".venv" / "bin").mkdir(parents=True)
    os.symlink("/nonexistent/python", output / ".venv" / "bin" / "python")
    (output / ".git").mkdir()
    (output / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    os.symlink("missing.py", output / "stale.py")


REPORT_HASH = hashlib.sha256(CASE_CSV.read_bytes()).hexdigest()

HASH_SUITE = f"""import hashlib
import os
from pathlib import Path


def test_the_report_is_the_one_modelled() -> None:
    text = Path(os.environ["FAB_CSV"]).read_bytes()
    assert hashlib.sha256(text).hexdigest() == "{REPORT_HASH}"
"""
"""Passes on the report and fails on every changed copy, without board.py."""

PATH_SUITE = """import os


def test_the_report_path() -> None:
    assert "/original/" in os.environ["FAB_CSV"]
"""
"""Passes or fails by where the check puts the report."""

REPORT_ONLY_SUITE = """import os
from pathlib import Path


def test_the_report_holds_the_modelled_values() -> None:
    text = Path(os.environ["FAB_CSV"]).read_text(encoding="utf-8")
    for cells in ("5.00,0.1270", "9.45,0.240", "width,1.77,0.045", "5.79,0.1470"):
        assert cells in text
"""
"""Reads each changed value from the report, and never tests board.py."""


def test_a_suite_that_reads_the_report_passes() -> None:
    done = run(CASE_A / "reads_report")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS  the tests in" in done.stdout


def test_a_suite_of_copied_constants_fails_every_mutation() -> None:
    done = run(CASE_A / "constants_copy")
    assert done.returncode == 1, done.stdout + done.stderr
    assert done.stdout.count("FAIL  the tests pass with") == len(
        mutation_check.MUTATIONS
    )


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            edit(SUITE, 'os.environ["FAB_CSV"]', repr(str(CASE_CSV))),
            "FAIL  the tests pass with",
        ),
        (
            edit(Path("board.py"), "UV1_PAD = 0.240", "UV1_PAD = 0.250"),
            "FAIL  the tests do not pass against the report as given (pytest exit 1)",
        ),
        (
            lambda output: (output / SUITE).unlink(),
            "FAIL  the tests do not pass against the report as given (pytest exit 5)",
        ),
        (
            lambda output: shutil.rmtree(output / "tests"),
            "tests does not exist, so there are no tests to run",
        ),
        (
            suite(HASH_SUITE),
            "FAIL  the tests fail on a copy of the report with the same values",
        ),
        (
            suite(PATH_SUITE),
            "FAIL  the tests fail on a copy of the report with the same values",
        ),
        (
            suite(REPORT_ONLY_SUITE),
            "FAIL  the tests pass with board.py replaced by a module that raises",
        ),
        (
            write("board.py", "import substrate_helpers\n"),
            "FAIL  board.py does not import: substrate_helpers",
        ),
        (
            edit(SUITE, "import board\n", "import board\nimport fixtures_helper\n"),
            "FAIL  the tests do not pass against the report as given (pytest exit 2)",
        ),
    ],
    ids=[
        "a suite that reads its own copy of the report",
        "a suite that fails on the report",
        "a tests directory with no tests",
        "no tests directory",
        "a suite that checks the report's hash",
        "a suite that checks the report's path",
        "a suite that never tests board.py",
        "a board.py that does not import",
        "a suite that imports a module that does not exist",
    ],
)
def test_each_way_a_suite_cannot_show_it_reads_the_report_is_red(
    tmp_path: Path, change: Change, reason: str
) -> None:
    output = tmp_path / "output"
    shutil.copytree(CASE_A / "reads_report", output)
    change(output)
    done = run(output)
    assert done.returncode == 1, done.stdout + done.stderr
    assert reason in done.stdout
    for words in PYTHON_IMPORT_WORDING:
        assert words.lower() not in done.stdout.lower(), done.stdout


@pytest.mark.parametrize(
    "change",
    [write("pytest.ini", "[pytest]\naddopts = -q\n"), clutter],
    ids=[
        "a pytest.ini that adds -q",
        "a virtualenv, a git directory and a broken symlink",
    ],
)
def test_each_way_of_writing_a_good_suite_passes(
    tmp_path: Path, change: Change
) -> None:
    output = tmp_path / "output"
    shutil.copytree(CASE_A / "reads_report", output)
    change(output)
    done = run(output)
    assert done.returncode == 0, done.stdout + done.stderr


def test_an_interpreter_without_pytest_is_an_environment_error() -> None:
    """``-S`` leaves site-packages, and with it pytest, off the path."""
    done = run(CASE_A / "reads_report", "-S")
    assert done.returncode == 3, done.stdout + done.stderr
    assert done.stdout.startswith("ERROR  mutation_check.py needs pytest"), done.stdout


@pytest.mark.parametrize("mutation", mutation_check.MUTATIONS, ids=lambda m: m.section)
def test_each_mutation_changes_only_its_own_cells(
    tmp_path: Path, mutation: mutation_check.Mutation
) -> None:
    """Read back as the report reader reads it, a changed copy differs from
    the case report in the named cells of one row and nowhere else, so a
    suite fails it for that value and not for a damaged file."""
    changed = tmp_path / CASE_CSV.name
    changed.write_text(
        mutation_check.mutate(CASE_CSV.read_text(encoding="utf-8"), mutation),
        encoding="utf-8",
    )
    before, after = fabcsv.sections(CASE_CSV), fabcsv.sections(changed)
    assert before.keys() == after.keys()
    differences = [
        (name, index, column, row[column], after[name][index][column])
        for name, rows in before.items()
        for index, row in enumerate(rows)
        for column in row
        if row[column] != after[name][index][column]
    ]
    expected_row = next(
        index
        for index, row in enumerate(before[mutation.section])
        if row[mutation.key_column] == mutation.key
    )
    assert sorted(differences) == sorted(
        (mutation.section, expected_row, column, old, new)
        for column, old, new in mutation.cells
    )
