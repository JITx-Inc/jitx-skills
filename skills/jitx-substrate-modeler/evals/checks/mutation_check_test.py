"""mutation_check.py passes a test suite that reads the report FAB_CSV names,
and fails a suite that does not, or that cannot show it.

testdata/case_a/reads_report and testdata/case_a/constants_copy are the two
directories a reader can run the check on by hand. The other rows edit a copy
of the first. Every row runs the script as the eval runs it, so the pytest
children are real.
"""

from __future__ import annotations

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


def run(output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(output), str(CASE_CSV)],
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
    ],
    ids=[
        "a suite that reads its own copy of the report",
        "a suite that fails on the report",
        "a tests directory with no tests",
        "no tests directory",
    ],
)
def test_each_way_a_suite_cannot_show_it_reads_the_report_is_red(
    tmp_path: Path, change: Callable[[Path], None], reason: str
) -> None:
    output = tmp_path / "output"
    shutil.copytree(CASE_A / "reads_report", output)
    change(output)
    done = run(output)
    assert done.returncode == 1, done.stdout + done.stderr
    assert reason in done.stdout


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
