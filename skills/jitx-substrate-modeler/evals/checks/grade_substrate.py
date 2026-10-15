#!/usr/bin/env python3
"""Grade a candidate substrate against a fab report, and fail unless it graded it.

Usage:
  grade_substrate.py BOARD_PY CSV [-k SELECTION] [--timeout SECONDS]

First imports BOARD_PY on its own, with this interpreter, through
import_candidate.py. A candidate that does not import (a module or name that
does not exist, an error at class definition) is a red: "FAIL  candidate
does not import: <what>". A grader dependency that does not import, or an
import that fails inside a library rather than in the candidate's own files,
is an ``ERROR  `` line in Python's own wording: an environment problem, not
the candidate's. A pre-flight that crashes without a verdict is shown with
its stderr.

Then runs ``pytest -q -W always`` on substrate_grader.py, beside this script,
with this interpreter, SUBSTRATE_FILE=BOARD_PY and FAB_CSV=CSV, and passes
only when all of these hold:

- pytest exits 0, with at least one test selected;
- every selected test passed: a skipped, xfailed or xpassed test is not a
  graded one, so any of those is a red;
- the grader's ``GradedTarget`` warning names BOARD_PY as the substrate file
  and CSV as the fab report.

The last condition makes the case fail closed: a run that graded some other
file, or graded nothing, is not a pass. SUBSTRATE_CLASS and PYTEST_ADDOPTS
are removed from the environment, so a stray value cannot pick a class or
deselect tests.

Each child (the pre-flight, then pytest) runs in its own process group and
has --timeout seconds (default 300). A child that runs longer, such as a
board that hangs at import, is a red: the whole group is killed, so nothing
it started keeps running, and the FAIL line says which stage did not finish.
SIGTERM, SIGHUP and SIGINT to this process kill the child's group the same
way. If this process is killed outright, each child sees its parent gone and
kills its own group (parent_watch.py).

Exit codes: 0 graded and green / 1 red, or not graded / 2 usage error (a
missing or blank argument, or a CSV that is not a file).
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from types import FrameType

from parent_watch import PARENT

GRADER = Path(__file__).resolve().parent / "substrate_grader.py"
GRADED = re.compile(r"GradedTarget: substrate (\S+) from (.+); fab report (.+)$")
SUMMARY = re.compile(r"^=*\s*(\d+ [\w ]+?(?:, \d+ [\w ]+?)*) in [\d.]+s\b")
COUNT = re.compile(r"(\d+) ([\w ]+)")
GREEN_OUTCOMES = {"passed", "subtests passed", "warning", "warnings", "deselected"}
"""Summary outcomes a green run may report. Anything else (skipped, xfailed,
xpassed, subtests skipped, and the failures) means a test went ungraded."""

PREFLIGHT = Path(__file__).resolve().parent / "import_candidate.py"
"""Imports the candidate in a child interpreter first; see its docstring."""

TIMEOUT_S = 300.0
"""Seconds each child may run. Grading a correct board takes a few."""


def kill_group(child: subprocess.Popen[str]) -> None:
    """Kill the child's whole process group, then reap the child. Without a
    group of its own, the child alone is killed."""
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        child.kill()
    child.wait()
    for stream in (child.stdout, child.stderr):
        if stream is not None:
            stream.close()


def run_child(
    command: list[str],
    *,
    timeout: float,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str] | None:
    """Run a child in its own process group and capture its output. None when
    it outlives ``timeout``; the group is killed first, and also when this
    process is interrupted or terminated while it waits."""
    child = subprocess.Popen(
        command,
        env=env,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_group(child)
        return None
    except BaseException:
        kill_group(child)
        raise
    return subprocess.CompletedProcess(command, child.returncode, stdout, stderr)


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
    parser.add_argument("--timeout", type=float, default=TIMEOUT_S)
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as error:
        return 2 if error.code else 0
    if not args.board.strip() or not args.csv.strip():
        print("error: BOARD_PY and CSV must not be blank", file=sys.stderr)
        return 2
    if not args.timeout > 0:
        print("error: --timeout must be a positive number of seconds", file=sys.stderr)
        return 2
    board, csv_file = Path(args.board.strip()), Path(args.csv.strip())
    if not csv_file.is_file():
        print(f"error: no fab report at {csv_file}", file=sys.stderr)
        return 2
    if not board.is_file():
        print(f"FAIL  {board} does not exist")
        return 1
    # Each child ends itself if this process dies; see parent_watch.py.
    watched = {**os.environ, PARENT: str(os.getpid())}
    preflight = run_child(
        [sys.executable, str(PREFLIGHT), str(board)],
        timeout=args.timeout,
        env=watched,
    )
    if preflight is None:
        print(
            f"FAIL  the import pre-flight did not finish within {args.timeout:g} s: "
            f"importing {board} hangs or takes too long"
        )
        return 1
    if preflight.returncode != 0:
        verdict = preflight.stdout.strip()
        if not verdict:
            # The pre-flight crashed before judging the candidate: show why.
            verdict = (
                f"ERROR  the import pre-flight gave no verdict (exit "
                f"{preflight.returncode}):\n{preflight.stderr.strip()}"
            )
        print(verdict)
        return 1
    # Absolute, because the grader runs from its own directory.
    env = {
        **watched,
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
        "--color=no",
        str(GRADER),
    ]
    if args.selection:
        command += ["-k", args.selection]
    done = run_child(command, timeout=args.timeout, env=env, cwd=GRADER.parent)
    if done is None:
        print(
            f"FAIL  the grader did not finish within {args.timeout:g} s, so it "
            f"did not grade {board}"
        )
        return 1
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


def stop(signum: int, frame: FrameType | None) -> None:
    """SIGTERM or SIGHUP as an exception, so a child's process group is
    killed too."""
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    sys.exit(main(sys.argv))
