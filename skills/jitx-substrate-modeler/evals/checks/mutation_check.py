#!/usr/bin/env python3
"""Check that the runner's tests read the report and test board.py against
it: they pass on the report and fail on copies of it with one value changed.

Usage:
  mutation_check.py OUTPUT_DIR REPORT_CSV [--timeout SECONDS]

OUTPUT_DIR holds the runner's ``board.py`` and its ``tests/`` directory.
REPORT_CSV is the case report, ``QCW-HDI12_Fab-Stackup_RevB.csv``. The check
copies OUTPUT_DIR into a scratch directory, imports ``board.py`` there in a
child through ``import_candidate.py``, and runs ``python -m pytest -q tests``
from the copy, with this interpreter, the copy first on PYTHONPATH (so the
tests ``import board``), and the environment variable ``FAB_CSV`` naming a
copy of the report in another scratch directory. It runs seven times:

- against an unchanged copy of the report: every test must pass, and at
  least one must run;
- against a copy at another path with the same values and one more NOTES
  line: every test must pass, so a suite that checks the report's bytes or
  path rather than its values is a red;
- with board.py replaced by a module that raises at import: the tests must
  fail, so a suite that never tests board.py is a red;
- against four copies, each with one value changed (see ``MUTATIONS``): a
  dielectric thickness, a via pad, a fab rule and an impedance width. Each
  run must fail (pytest exit 1, or 2 for errors at collection).

A suite that compares board.py with numbers typed into the tests, or reads
the report from a path of its own instead of ``FAB_CSV``, passes a changed
copy and is a red. So is a suite that cannot run at all. Each changed value
is written in both its mm and its mil cell, so a test that reads either
column sees the change. Outcomes are counted from a JUnit XML report written
outside the copy, so a runner's own pytest options cannot hide them. POSIX
only, like ``grade_substrate.py``, whose child runner and signal handling it
uses: SIGTERM or SIGHUP ends every child and removes the scratch directories.

Exit codes: 0 pass / 1 red, with a ``FAIL  `` line per reason / 2 usage error
(no such directory or report, or a report that no longer holds a row or value
``MUTATIONS`` expects) / 3 an environment problem, as an ``ERROR  `` line in
Python's own wording (this interpreter lacks pytest or jitx, or a library
board.py imports does not import).
"""

from __future__ import annotations

import argparse
import csv
import io
import signal
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path

from design_check import (
    Verdict,
    child_env,
    copy_output,
    import_file,
    missing,
    plain,
    report,
    tail,
)
from grade_substrate import run_child, stop

TIMEOUT_S = 300.0
"""Seconds each pytest run may take."""

RELOCATED_NOTE = (
    '"This copy of the report has the values of the original; the check reads '
    'it from another path."\n'
)
"""The line added to the report's last section, NOTES, for the relocated
copy."""

BROKEN_BOARD = 'raise RuntimeError("mutation_check.py replaced board.py")\n'
"""board.py for the run whose tests must fail."""


@dataclass(frozen=True)
class Mutation:
    """One value changed in one row of the report."""

    label: str
    section: str
    key_column: str
    key: str
    cells: tuple[tuple[str, str, str], ...]
    """(column, value the report holds, value written in its place)."""


MUTATIONS = (
    Mutation(
        "a dielectric thickness (STACKUP seq 7, the L3 to L4 core)",
        "STACKUP",
        "Seq",
        "7",
        (("Thickness_mm", "0.1270", "0.1370"), ("Thickness_mil", "5.00", "5.39")),
    ),
    Mutation(
        "a via pad (VIAS UV-1)",
        "VIAS",
        "Via_ID",
        "UV-1",
        (("Pad_mm", "0.240", "0.260"), ("Pad_mil", "9.45", "10.24")),
    ),
    Mutation(
        "a fab rule (FAB_RULES min_copper_width)",
        "FAB_RULES",
        "JITX_attribute",
        "min_copper_width",
        (("Value_mm", "0.045", "0.050"), ("Value_mil", "1.77", "1.97")),
    ),
    Mutation(
        "an impedance width (IMPEDANCE SE-50 on L1;L12)",
        "IMPEDANCE",
        "Structure_ID",
        "SE-50",
        (("Line_width_mm", "0.1470", "0.1570"), ("Line_width_mil", "5.79", "6.18")),
    ),
)
"""Rows and values of the case report. The key picks the first row whose key
column holds it, so the SE-50 change lands on its L1;L12 row."""


class ReportChanged(Exception):
    """The report does not hold a row or value a mutation expects."""


def mutate(text: str, mutation: Mutation) -> str:
    """``text`` with the mutation's cells changed, every other line as it was."""
    lines = text.splitlines(keepends=True)
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith(f"SECTION,{mutation.section}")
        ),
        None,
    )
    if start is None:
        raise ReportChanged(f"no SECTION,{mutation.section}")
    header = next(csv.reader([lines[start + 1]]))
    for index in range(start + 2, len(lines)):
        if lines[index].startswith("SECTION,"):
            break
        row = next(csv.reader([lines[index]]), [])
        cells = dict(zip(header, row, strict=False))
        if cells.get(mutation.key_column) != mutation.key:
            continue
        for column, old, new in mutation.cells:
            if cells.get(column) != old:
                raise ReportChanged(
                    f"{mutation.section} {mutation.key} {column} is "
                    f"{cells.get(column)!r}, not {old!r}"
                )
            row[header.index(column)] = new
        out = io.StringIO()
        csv.writer(out, lineterminator="").writerow(row)
        ending = lines[index][len(lines[index].rstrip("\r\n")) :]
        lines[index] = out.getvalue() + ending
        return "".join(lines)
    raise ReportChanged(
        f"no {mutation.section} row with {mutation.key_column} {mutation.key}"
    )


def relocate(text: str) -> str:
    """``text`` with one more NOTES line; every value as it was."""
    sections = [line for line in text.splitlines() if line.startswith("SECTION,")]
    if not sections or sections[-1].strip() != "SECTION,NOTES":
        raise ReportChanged("the last section is not NOTES")
    return text + ("" if text.endswith("\n") else "\n") + RELOCATED_NOTE


@dataclass(frozen=True)
class Outcome:
    """One pytest run: its exit code (None on timeout), the tests that
    passed, and the tail of its output."""

    code: int | None
    passed: int
    output: str


def passed_count(junit: Path) -> int:
    """Tests that passed, from a JUnit XML report; 0 when there is none."""
    try:
        root = ElementTree.parse(junit).getroot()
    except (OSError, ElementTree.ParseError):
        return 0
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    return sum(
        int(suite.get("tests", 0))
        - int(suite.get("failures", 0))
        - int(suite.get("errors", 0))
        - int(suite.get("skipped", 0))
        for suite in suites
    )


def run_tests(project: Path, report_copy: Path, timeout: float) -> Outcome:
    """The tests in ``project`` against ``report_copy``. The JUnit report
    goes beside the report copy, outside ``project``."""
    env = {k: v for k, v in child_env(project).items() if k != "PYTEST_ADDOPTS"}
    env["FAB_CSV"] = str(report_copy)
    # board.py is swapped out between runs: no bytecode cache may outlive it.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    junit = report_copy.parent / "junit.xml"
    done = run_child(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--color=no",
            f"--junitxml={junit}",
            "tests",
        ],
        timeout=timeout,
        env=env,
        cwd=project,
    )
    if done is None:
        return Outcome(None, 0, "")
    return Outcome(done.returncode, passed_count(junit), done.stdout + done.stderr)


def check(output: Path, report_csv: Path, timeout: float) -> Verdict:
    """Every environment problem and red; both empty when the tests pass."""
    verdict = Verdict()
    text = report_csv.read_text(encoding="utf-8")
    variants = [(mutation, mutate(text, mutation)) for mutation in MUTATIONS]
    relocated = relocate(text)
    error = missing("mutation_check.py", ("pytest", "jitx"))
    if error is not None:
        verdict.errors.append(error)
        return verdict
    if not (output / "tests").is_dir():
        verdict.problems.append(
            f"{output / 'tests'} does not exist, so there are no tests to run"
        )
        return verdict
    if not (output / "board.py").is_file():
        verdict.problems.append(f"{output / 'board.py'} does not exist")
        return verdict
    with tempfile.TemporaryDirectory(prefix="mutation-check-") as tmp:
        root = Path(tmp)
        project = root / "project"
        copy_output(output, project)
        if not import_file(project / "board.py", child_env(project), timeout, verdict):
            return verdict

        def against(name: str, content: str) -> Outcome:
            copy = root / "reports" / name / report_csv.name
            copy.parent.mkdir(parents=True)
            copy.write_text(content, encoding="utf-8")
            return run_tests(project, copy, timeout)

        def late(what: str) -> str:
            return f"the tests did not finish within {timeout:g} s {what}"

        original = against("original", text)
        if original.code is None:
            verdict.problems.append(late("on the report"))
            return verdict
        if original.code != 0 or not original.passed:
            verdict.problems.append(
                "the tests do not pass against the report as given (pytest exit "
                f"{original.code}), so they cannot show that a changed value fails "
                f"them:\n{plain(tail(original.output))}"
            )
            return verdict
        print(f"report as given: {original.passed} passed")
        moved = against("relocated", relocated)
        if moved.code is None:
            verdict.problems.append(late("on the relocated copy of the report"))
        elif moved.code != 0 or not moved.passed:
            verdict.problems.append(
                "the tests fail on a copy of the report with the same values at "
                "another path and one more NOTES line (pytest exit "
                f"{moved.code}): they check the file, not its values:\n"
                + plain(tail(moved.output))
            )
        else:
            print("relocated copy of the report: the tests pass, as they should")
        real_board = (project / "board.py").read_text(encoding="utf-8")
        (project / "board.py").write_text(BROKEN_BOARD, encoding="utf-8")
        broken = against("board-replaced", text)
        (project / "board.py").write_text(real_board, encoding="utf-8")
        if broken.code is None:
            verdict.problems.append(late("with board.py replaced"))
        elif broken.code == 0:
            verdict.problems.append(
                "the tests pass with board.py replaced by a module that raises at "
                "import: they do not test board.py"
            )
        else:
            print("board.py replaced: the tests fail, as they should")
        for number, (mutation, changed) in enumerate(variants, start=1):
            outcome = against(f"mutation-{number}", changed)
            values = ", ".join(
                f"{column} {old} -> {new}" for column, old, new in mutation.cells
            )
            if outcome.code is None:
                verdict.problems.append(late(f"on {mutation.label}"))
            elif outcome.code in (1, 2):
                print(f"{mutation.label} ({values}): the tests fail, as they should")
            elif outcome.code == 0:
                verdict.problems.append(
                    f"the tests pass with {mutation.label} changed ({values}): they "
                    "do not check that value against the report FAB_CSV names"
                )
            else:
                verdict.problems.append(
                    f"pytest exited {outcome.code} with {mutation.label} changed:\n"
                    + plain(tail(outcome.output))
                )
    return verdict


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("output")
    parser.add_argument("report")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_S)
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as error:
        return 2 if error.code else 0
    output, report_csv = Path(args.output), Path(args.report)
    if not output.is_dir():
        print(f"error: no output directory at {output}", file=sys.stderr)
        return 2
    if not report_csv.is_file():
        print(f"error: no report at {report_csv}", file=sys.stderr)
        return 2
    try:
        verdict = check(output, report_csv, args.timeout)
    except ReportChanged as error:
        print(
            f"error: the report has changed ({error}); update MUTATIONS",
            file=sys.stderr,
        )
        return 2
    return report(
        verdict, f"the tests in {output} fail on every changed copy of the report"
    )


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    sys.exit(main(sys.argv))
