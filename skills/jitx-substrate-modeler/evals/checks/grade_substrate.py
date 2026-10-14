#!/usr/bin/env python3
"""Grade a candidate substrate against a fab report, and fail unless it graded it.

Usage:
  grade_substrate.py BOARD_PY CSV [-k SELECTION]

Runs ``pytest -q -W always`` on substrate_grader.py, beside this script, with
this interpreter, SUBSTRATE_FILE=BOARD_PY and FAB_CSV=CSV, and passes only
when both hold:

- pytest exits 0, with at least one test selected;
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
PASSED = re.compile(r"\b(\d+) passed\b")


def same_file(reported: str, given: Path) -> bool:
    return Path(reported.strip()).expanduser().resolve() == given.resolve()


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
    if done.returncode != 0:
        problems.append(f"the grader exited {done.returncode}")
    elif not PASSED.search(output):
        problems.append("the grader selected no tests")
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
