#!/usr/bin/env python3
"""Grade a candidate substrate against a fab report, and fail unless it graded it.

Usage:
  grade_substrate.py BOARD_PY CSV [-k SELECTION]

First imports BOARD_PY on its own, with this interpreter. A candidate that
does not import (a module or name that does not exist, an error at class
definition) is a red: "FAIL  candidate does not import: <module>". Only a
missing jitx or pytest, which no candidate can fix, is reported in Python's
own "No module named" wording.

Then runs ``pytest -q -W always`` on substrate_grader.py, beside this script,
with this interpreter, SUBSTRATE_FILE=BOARD_PY and FAB_CSV=CSV, and passes
only when all of these hold:

- pytest exits 0, with at least one test selected;
- every selected test passed: a skipped, xfailed or xpassed test is not a
  graded one, so any of those is a red;
- the grader's ``GradedTarget`` warning names BOARD_PY as the substrate file
  and CSV as the fab report.

The second condition makes the case fail closed: a run that graded some other
file, or graded nothing, is not a pass. SUBSTRATE_CLASS and PYTEST_ADDOPTS
are removed from the environment, so a stray value cannot pick a class or
deselect tests.

Exit codes: 0 graded and green / 1 red, or not graded / 2 usage error (a
missing or blank argument, or a CSV that is not a file).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

GRADER = Path(__file__).resolve().parent / "substrate_grader.py"
GRADED = re.compile(r"GradedTarget: substrate (\S+) from (.+); fab report (.+)$")
SUMMARY = re.compile(r"^=*\s*(\d+ [\w ]+?(?:, \d+ [\w ]+?)*) in [\d.]+s\b")
COUNT = re.compile(r"(\d+) ([\w ]+)")
GREEN_OUTCOMES = {"passed", "subtests passed", "warning", "warnings", "deselected"}
"""Summary outcomes a green run may report. Anything else (skipped, xfailed,
xpassed, subtests skipped, and the failures) means a test went ungraded."""

PREFLIGHT = """
import importlib.util, sys, traceback
from pathlib import Path
for needed in ("jitx", "pytest"):
    if importlib.util.find_spec(needed) is None:
        print(f"No module named {needed!r}")
        sys.exit(3)
board = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(board.parent))
spec = importlib.util.spec_from_file_location("_candidate_preflight", board)
module = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(module)
except BaseException as error:
    if isinstance(error, ImportError) and error.name:
        what = error.name
    else:
        what = f"{type(error).__name__}: {error}"
    lines = [
        f"{Path(frame.filename).name}:{frame.lineno}"
        for frame in traceback.extract_tb(error.__traceback__)
        if Path(frame.filename).resolve() == board
    ]
    where = f" (at {lines[-1]})" if lines else ""
    print(f"FAIL  candidate does not import: {what}{where}")
    sys.exit(1)
"""
"""Imports the candidate in a child interpreter. Exit 3 names a missing jitx
or pytest; exit 1 is a candidate that does not import, reported without
Python's own wording so a harness does not read it as an environment error."""


def same_file(reported: str, given: Path) -> bool:
    return Path(reported.strip()).expanduser().resolve() == given.resolve()


def summary_counts(output: str) -> dict[str, int]:
    """Outcome -> count, from the last pytest summary line in ``output``."""
    found = [m for line in output.splitlines() if (m := SUMMARY.match(line.strip()))]
    if not found:
        return {}
    return {
        outcome.strip(): int(number)
        for number, outcome in COUNT.findall(found[-1].group(1))
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("board")
    parser.add_argument("csv")
    parser.add_argument("-k", dest="selection")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as error:
        return 2 if error.code else 0
    if not args.board.strip() or not args.csv.strip():
        print("error: BOARD_PY and CSV must not be blank", file=sys.stderr)
        return 2
    board, csv_file = Path(args.board.strip()), Path(args.csv.strip())
    if not csv_file.is_file():
        print(f"error: no fab report at {csv_file}", file=sys.stderr)
        return 2
    if not board.is_file():
        print(f"FAIL  {board} does not exist")
        return 1
    preflight = subprocess.run(
        [sys.executable, "-c", PREFLIGHT, str(board)],
        capture_output=True,
        text=True,
        check=False,
    )
    if preflight.returncode != 0:
        print(preflight.stdout.strip() or f"FAIL  {board} does not import")
        return 1
    # Absolute, because the grader runs from its own directory.
    env = {
        **os.environ,
        "SUBSTRATE_FILE": str(board.resolve()),
        "FAB_CSV": str(csv_file.resolve()),
    }
    env.pop("SUBSTRATE_CLASS", None)
    env.pop("PYTEST_ADDOPTS", None)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-W",
        "always",
        "-p",
        "no:cacheprovider",
        str(GRADER),
    ]
    if args.selection:
        command += ["-k", args.selection]
    done = subprocess.run(
        command,
        env=env,
        cwd=GRADER.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    output = done.stdout + done.stderr
    print(output, end="" if output.endswith("\n") else "\n")
    problems: list[str] = []
    counts = summary_counts(output)
    if done.returncode != 0:
        problems.append(f"the grader exited {done.returncode}")
    elif not counts.get("passed"):
        problems.append("the grader selected no tests")
    ungraded = {k: v for k, v in counts.items() if k not in GREEN_OUTCOMES}
    if done.returncode == 0 and ungraded:
        listed = ", ".join(f"{v} {k}" for k, v in ungraded.items())
        problems.append(f"the grader reported {listed}; only a passed test is graded")
    graded = [match for line in output.splitlines() if (match := GRADED.search(line))]
    if not graded:
        problems.append(
            f"the grader printed no GradedTarget line, so it did not grade {board}"
        )
    for match in graded:
        if not same_file(match.group(2), board):
            problems.append(f"the grader graded {match.group(2)}, not {board}")
        if not same_file(match.group(3), csv_file):
            problems.append(
                f"the grader read the fab report {match.group(3)}, not {csv_file}"
            )
    for problem in problems:
        print(f"FAIL  {problem}")
    if not problems:
        print(f"PASS  the grader graded {board} against {csv_file}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
