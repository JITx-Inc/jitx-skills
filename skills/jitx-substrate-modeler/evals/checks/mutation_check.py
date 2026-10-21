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
copy of the report in another scratch directory. It runs eight times:

- against an unchanged copy of the report: every test must pass, and at
  least one must run;
- against a copy at another path with the same values and one more NOTES
  line: every test must pass, so a suite that checks the report's bytes or
  path rather than its values is a red;
- with board.py replaced by a module that imports cleanly and answers every
  name with a stand-in that equals no number or string (``BROKEN_BOARD``):
  the tests must fail, so a suite that never tests board.py, or only imports
  it or a name from it, is a red;
- against the report, with one reference-plane width in board.py moved off
  3 x its dielectric height (see ``move_width``): the tests must fail (pytest
  exit 1, or 2), so a suite that never tests a default width against its
  formula is a red. A board.py with no width to move (no line that
  multiplies by 3, or by a name assigned 3, under a skill-default label)
  is a red;
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
import ast
import csv
import io
import re
import signal
import sys
import tempfile
import tokenize
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

BROKEN_BOARD = '''"""mutation_check.py replaced board.py with this module."""

STAND_IN = object()


def __getattr__(name: str) -> object:
    if name.startswith("__"):
        raise AttributeError(name)
    return STAND_IN
'''
"""board.py for the run whose tests must fail. It imports cleanly, and every
name read from it, ``from board import NAME`` included, is one stand-in: a
plain ``object()``, so it equals itself and nothing else, is truthy, takes no
arithmetic and no ordering comparison, and makes ``hasattr(board, NAME)``
true for any name that does not start with ``__``. What that guarantees: a
test that asserts a value read from board.py equals a number or string,
orders it, or does arithmetic with it, fails; a suite that only imports board.py, reads a
name from it, checks that a name exists or is truthy, or compares two names
it read, passes and is a red."""


LABEL = re.compile(r"\bskill[- ]defaults?\b", re.IGNORECASE)
NEGATED = re.compile(r"\b(?:no|not(?:\s+(?:a|the|any))?)\s+$", re.IGNORECASE)
"""A skill-default label, as ``scripts/check_labels.py`` reads one: a comment
naming the skill default other than directly after a word that denies it."""

MOVED_FACTOR = "3.5"
"""What ``move_width`` writes in place of the factor 3."""


def is_label(comment: str) -> bool:
    """The comment names the skill default, other than to deny it."""
    return any(
        not NEGATED.search(comment[: match.start()])
        for match in LABEL.finditer(comment)
    )


def is_three(node: ast.expr) -> bool:
    """The node is the number 3 (``3`` or ``3.0``), not a bool."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
        and node.value == 3
    )


def factor_assignments(body: list[ast.stmt]) -> list[tuple[str, ast.expr]]:
    """Each ``NAME = 3`` (or ``NAME: T = 3``) in a module or class body, and
    in the bodies of the classes it defines, as (name, the 3), in source
    order."""
    found: list[tuple[str, ast.expr]] = []
    for statement in body:
        if isinstance(statement, ast.ClassDef):
            found += factor_assignments(statement.body)
        elif (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and is_three(statement.value)
        ):
            found.append((statement.targets[0].id, statement.value))
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.value is not None
            and is_three(statement.value)
        ):
            found.append((statement.target.id, statement.value))
    return found


def replaced(text: str, row: int, start: int, end: int) -> str:
    """``text`` with characters ``start`` to ``end`` of line ``row`` (1-based)
    replaced by ``MOVED_FACTOR``."""
    lines = text.splitlines(keepends=True)
    line = lines[row - 1]
    lines[row - 1] = line[:start] + MOVED_FACTOR + line[end:]
    return "".join(lines)


def move_width(text: str) -> tuple[str, int] | None:
    """``text`` with one default width moved off its formula, and the line
    moved; None when there is no width to move.

    The width is the first line whose comment is a skill-default label and
    whose code multiplies by the number 3 (``2: 3 * H_L1_L3,  # skill
    default: ...``, ``H * 3.0`` too); that 3 becomes ``MOVED_FACTOR``. With no
    such line, the factor may be named: a labelled line multiplies by a name
    (``2: REF_FACTOR * H,  # skill default: ...``) that a module- or
    class-level assignment sets to 3 (``REF_FACTOR = 3``), and that
    assignment's 3 becomes ``MOVED_FACTOR``, the first such assignment in the
    file. Python's tokenizer finds the lines, so a 3, a name or a label inside
    a string is never one."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        tree = ast.parse(text)
    except (tokenize.TokenError, SyntaxError, ValueError):
        return None
    labelled = {
        token.start[0]
        for token in tokens
        if token.type == tokenize.COMMENT and is_label(token.string)
    }
    factors: set[str] = set()
    for index, token in enumerate(tokens):
        if token.type not in (tokenize.NUMBER, tokenize.NAME):
            continue
        if token.start[0] not in labelled:
            continue
        neighbours = tokens[index - 1 : index] + tokens[index + 1 : index + 2]
        if not any(
            other.type == tokenize.OP and other.string == "*" for other in neighbours
        ):
            continue
        if token.type == tokenize.NAME:
            factors.add(token.string)
            continue
        try:
            value = float(token.string.replace("_", ""))
        except ValueError:
            continue
        if value == 3:
            row, start = token.start
            return replaced(text, row, start, token.end[1]), row
    lines = text.splitlines(keepends=True)
    for name, three in factor_assignments(tree.body):
        if name not in factors or three.end_col_offset is None:
            continue
        # ast columns count UTF-8 bytes; the line is sliced in characters.
        raw = lines[three.lineno - 1].encode("utf-8")
        start = len(raw[: three.col_offset].decode("utf-8"))
        end = len(raw[: three.end_col_offset].decode("utf-8"))
        return replaced(text, three.lineno, start, end), three.lineno
    return None


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
    # First, before anything an older interpreter cannot run: a Python
    # without pytest or jitx (jitx needs 3.12) is the environment's problem.
    error = missing("mutation_check.py", ("pytest", "jitx"))
    if error is not None:
        verdict.errors.append(error)
        return verdict
    text = report_csv.read_text(encoding="utf-8")
    variants = [(mutation, mutate(text, mutation)) for mutation in MUTATIONS]
    relocated = relocate(text)
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
                "the tests pass with board.py replaced by a module whose every "
                "name is a stand-in that equals no number or string: they do not test "
                "board.py's values"
            )
        else:
            print("board.py replaced: the tests fail, as they should")
        site = move_width(real_board)
        if site is None:
            verdict.problems.append(
                "board.py has no line that multiplies by 3, or by a name assigned "
                "3, under a skill-default label, so the check has no "
                "reference-plane width to move off 3 x its dielectric height"
            )
        else:
            moved_board, line = site
            (project / "board.py").write_text(moved_board, encoding="utf-8")
            off = against("width-off-formula", text)
            (project / "board.py").write_text(real_board, encoding="utf-8")
            change = f"board.py line {line}: 3 -> {MOVED_FACTOR}"
            if off.code is None:
                verdict.problems.append(late("with a default width moved"))
            elif off.code in (1, 2):
                print(
                    f"a reference-plane width moved off its formula ({change}): "
                    "the tests fail, as they should"
                )
            elif off.code == 0:
                verdict.problems.append(
                    "the tests pass with a reference-plane width in board.py moved "
                    f"off 3 x its dielectric height ({change}): they do not test "
                    "default widths against their formula"
                )
            else:
                verdict.problems.append(
                    f"pytest exited {off.code} with a default width moved "
                    f"({change}):\n" + plain(tail(off.output))
                )
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
