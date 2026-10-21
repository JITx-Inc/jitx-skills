#!/usr/bin/env python3
"""Check that the runner's tests read the report: they pass on it and fail on
copies of it with one value changed.

Usage:
  mutation_check.py OUTPUT_DIR REPORT_CSV [--timeout SECONDS]

OUTPUT_DIR holds the runner's ``board.py`` and its ``tests/`` directory.
REPORT_CSV is the case report, ``QCW-HDI12_Fab-Stackup_RevB.csv``. The check
copies OUTPUT_DIR into a scratch directory and runs ``python -m pytest -q
tests`` there, with this interpreter, the copy first on PYTHONPATH (so the
tests ``import board``), and the environment variable ``FAB_CSV`` naming a
copy of the report. It runs five times:

- against an unchanged copy of the report: every test must pass, and at
  least one must run;
- against four copies, each with one value changed (see ``MUTATIONS``): a
  dielectric thickness, a via pad, a fab rule and an impedance width. Each
  run must fail (pytest exit 1, or 2 for errors at collection).

A suite that compares board.py with numbers typed into the tests, or reads
the report from a path of its own instead of ``FAB_CSV``, passes a changed
copy and is a red. So is a suite that cannot run at all. Each changed value
is written in both its mm and its mil cell, so a test that reads either
column sees the change. POSIX only, like ``grade_substrate.py``, whose child
runner it uses.

Exit codes: 0 pass / 1 red, with a ``FAIL  `` line per reason / 2 usage error
(no such directory or report, or a report that no longer holds a row or value
``MUTATIONS`` expects).
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from grade_substrate import run_child, summary_counts

TIMEOUT_S = 300.0
"""Seconds each pytest run may take."""

IGNORED = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")


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


def run_tests(project: Path, report: Path, timeout: float) -> tuple[int | None, str]:
    """pytest's exit code (None on timeout) and its output, for the tests in
    ``project`` against ``report``."""
    env = {key: value for key, value in os.environ.items() if key != "PYTEST_ADDOPTS"}
    env["FAB_CSV"] = str(report)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(project), env.get("PYTHONPATH", "")) if part
    )
    done = run_child(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--color=no",
            "tests",
        ],
        timeout=timeout,
        env=env,
        cwd=project,
    )
    if done is None:
        return None, ""
    return done.returncode, done.stdout + done.stderr


def last_lines(output: str) -> str:
    return "\n".join(output.strip().splitlines()[-15:])


def check(output: Path, report: Path, timeout: float) -> list[str]:
    """Every reason the output's tests fail the check; empty when they pass."""
    text = report.read_text(encoding="utf-8")
    variants = [(mutation, mutate(text, mutation)) for mutation in MUTATIONS]
    if not (output / "tests").is_dir():
        return [f"{output / 'tests'} does not exist, so there are no tests to run"]
    with tempfile.TemporaryDirectory(prefix="mutation-check-") as tmp:
        root = Path(tmp)
        project = root / "project"
        shutil.copytree(output, project, ignore=IGNORED)
        original = root / "reports" / "original" / report.name
        original.parent.mkdir(parents=True)
        original.write_text(text, encoding="utf-8")
        code, out = run_tests(project, original, timeout)
        if code is None:
            return [f"the tests did not finish within {timeout:g} s on the report"]
        counts = summary_counts(out)
        if code != 0 or not counts.get("passed"):
            return [
                "the tests do not pass against the report as given (pytest exit "
                f"{code}), so they cannot show that a changed value fails them:\n"
                + last_lines(out)
            ]
        print(f"report as given: {counts['passed']} passed")
        problems: list[str] = []
        for number, (mutation, changed) in enumerate(variants, start=1):
            copy = root / "reports" / f"mutation-{number}" / report.name
            copy.parent.mkdir(parents=True)
            copy.write_text(changed, encoding="utf-8")
            code, out = run_tests(project, copy, timeout)
            values = ", ".join(
                f"{column} {old} -> {new}" for column, old, new in mutation.cells
            )
            if code is None:
                problems.append(
                    f"the tests did not finish within {timeout:g} s on {mutation.label}"
                )
            elif code in (1, 2):
                print(f"{mutation.label} ({values}): the tests fail, as they should")
            elif code == 0:
                problems.append(
                    f"the tests pass with {mutation.label} changed ({values}): they "
                    "do not check that value against the report FAB_CSV names"
                )
            else:
                problems.append(
                    f"pytest exited {code} with {mutation.label} changed:\n"
                    + last_lines(out)
                )
    return problems


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
    output, report = Path(args.output), Path(args.report)
    if not output.is_dir():
        print(f"error: no output directory at {output}", file=sys.stderr)
        return 2
    if not report.is_file():
        print(f"error: no report at {report}", file=sys.stderr)
        return 2
    try:
        problems = check(output, report, args.timeout)
    except ReportChanged as error:
        print(
            f"error: the report has changed ({error}); update MUTATIONS",
            file=sys.stderr,
        )
        return 2
    for problem in problems:
        print(f"FAIL  {problem}")
    if not problems:
        print(f"PASS  the tests in {output} fail on every changed copy of the report")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
