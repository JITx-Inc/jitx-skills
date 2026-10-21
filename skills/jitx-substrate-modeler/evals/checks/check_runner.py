"""What grade_pdf_report.py and grade_fenced_rf.py share: loading a
candidate's files, wrapping a substrate in a design, and running named checks.

Each check is a function that returns when the candidate passes it and raises
when it does not; the message it raises with is the reason printed.

A grader runs in two processes, so it fails closed. The parent imports each
candidate file in a child first (import_candidate.py, as grade_substrate.py
does), then runs the grader script again as a child, which loads the
candidate, prints ``PASS  <check>`` or ``FAIL  <check>: <reason>`` per check
and, last, a ``DONE`` line carrying a token the parent passed it. The parent
prints the child's lines and one summary line, and passes only when the
token line came last, every check printed exactly one line, every check
passed and the child exited 0.

What this guards against is a candidate's accident, not its malice: a
candidate that exits the child early (``sys.exit``, ``os._exit``, a crash or
an exit handler), hangs it past the time limit, prints lines of its own or
replaces ``sys.stdout`` is a red, since the child writes its check lines to
a copy of its stdout taken before any candidate code runs. Code written to
defeat the grader from inside the child (writing to that copy, or reading
the token, which ``ps -E`` shows in the child's environment) is not covered.
POSIX only: it uses process groups and POSIX signals.

Everything the parent prints from the candidate's side (the child's lines, the
tail of its stderr, the pre-flight's red) goes through ``scrub`` first. An
eval harness reads some wording, such as Python's "No module named" or a
shell's ": not found", as an environment problem and leaves the assertion out
of scoring, so a candidate's own message carrying it would hide a red.

Exit codes of the parent: 0 every check passed / 1 a red / 2 an environment
problem, which only the pre-flight reports, in its own ``ERROR  `` line and
Python's wording (a grader dependency or a library the candidate imports does
not import).

The Design and Board subclasses live here rather than in the grader scripts,
because JITX treats a Design subclass defined in ``__main__`` as a design file
to run when the interpreter exits.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import secrets
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TypeVar

from grade_substrate import run_child
from import_candidate import LIBRARY, NEEDS, describe, scrub
from parent_watch import PARENT, watch_parent

from jitx.board import Board
from jitx.circuit import Circuit
from jitx.design import Design
from jitx.shapes import Shape
from jitx.shapes.composites import rectangle
from jitx.substrate import Substrate

Check = tuple[str, Callable[[], None]]
T = TypeVar("T")

PREFLIGHT = Path(__file__).resolve().parent / "import_candidate.py"
"""Imports a candidate file in a child interpreter; see its docstring."""

NONCE = "GRADE_CHECKS_NONCE"
"""The environment variable through which a parent hands its child a token."""

ENVIRONMENT_EXIT = 2
"""The parent's exit code for an environment problem."""

_check_lines: list[int] = []
"""In a grading child: the copy of stdout's descriptor that check lines go
to, taken by ``child_nonce`` before any candidate code runs."""

DONE = "DONE"
"""The child's last line, with the token: every check ran."""

CHECK_LINE = re.compile(r"^(PASS|FAIL)  (\w+)(?::|$)")


def load_module(file: Path) -> ModuleType:
    """Import one candidate file under a name unique to its path, with its
    own directory importable while it loads."""
    name = "_candidate_" + hashlib.sha256(str(file).encode()).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, file)
    if spec is None or spec.loader is None:
        raise ImportError(f"{file} cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(file.parent))
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    finally:
        sys.path.remove(str(file.parent))
    return module


def defined_leaves(module: ModuleType, base: type[T]) -> list[type[T]]:
    """Subclasses of ``base`` defined in ``module`` (not imported into it)
    that no other of them subclasses."""
    defined: list[type[T]] = [
        value
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, base)
        and value is not base
        and value.__module__ == module.__name__
    ]
    return [
        cls
        for cls in defined
        if not any(other is not cls and issubclass(other, cls) for other in defined)
    ]


def one_leaf(module: ModuleType, base: type[T]) -> type[T]:
    """The one leaf subclass of ``base`` that ``module`` defines."""
    found = defined_leaves(module, base)
    if len(found) != 1:
        names = ", ".join(sorted(cls.__name__ for cls in found)) or "none"
        raise LookupError(
            f"{module.__file__} must define exactly one {base.__name__} subclass "
            f"that no other subclasses; found {names}"
        )
    return found[0]


def outline(width: float, height: float, radius: float) -> Shape:
    if radius > 0:
        return rectangle(width, height, radius=radius)
    return rectangle(width, height)


class EmptyCircuit(Circuit):
    """No components: only the substrate is graded."""


class GraderBoard(Board):
    """A board of the given size, with ``signal_area`` inset by ``inset``."""

    def __init__(
        self, width: float, height: float, radius: float, inset: float
    ) -> None:
        self.shape = outline(width, height, radius)
        self.signal_area = outline(
            width - 2 * inset, height - 2 * inset, max(radius - inset, 0.0)
        )


class SubstrateDesign(Design):
    """A substrate on a board, inset by its own ``min_copper_edge_space``, with
    no components, or with the circuit ``circuit_for`` builds for the
    substrate. Requires an instantiation context."""

    def __init__(
        self,
        substrate: type[Substrate],
        size: tuple[float, float, float],
        circuit_for: Callable[[Substrate], Circuit] | None = None,
    ) -> None:
        width, height, radius = size
        self.substrate = substrate()
        self.board = GraderBoard(
            width, height, radius, self.substrate.constraints.min_copper_edge_space
        )
        self.circuit = (
            circuit_for(self.substrate) if circuit_for is not None else EmptyCircuit()
        )


def _one(error: BaseException) -> str:
    text = " ".join(str(error).split())
    if isinstance(error, AssertionError) and text:
        return text
    return f"{type(error).__name__}: {text}" if text else type(error).__name__


def reason(error: BaseException) -> str:
    """One line for a failed check: an assertion's own message, or the
    exception's type and message for anything else the candidate raised,
    followed by the error that caused it, since JITX wraps a failure inside a
    class it instantiates in one that names only the class."""
    root = error
    while root.__cause__ is not None:
        root = root.__cause__
    if root is error:
        return _one(error)
    return f"{_one(error)}, caused by {_one(root)}"


def load_failure(error: BaseException) -> str:
    """The line for a candidate that imports but cannot be graded, worded as
    import_candidate.py words a red, so an eval harness does not read
    Python's own import wording in it as an environment problem."""
    return f"FAIL  candidate does not load: {describe(error)}"


def child_nonce() -> str | None:
    """In a grading child: the token its parent passed, taken out of the
    environment before any candidate code runs, the parent watch started and
    a copy of stdout kept for the check lines. None in the parent."""
    token = os.environ.pop(NONCE, None)
    if token is not None:
        watch_parent()
        _check_lines.append(os.dup(sys.stdout.fileno()))
    return token


def say(line: str) -> None:
    """In the grading child: write one check line to the stdout copy, after
    whatever the candidate has printed so far, so a candidate that replaces
    ``sys.stdout`` cannot rewrite it."""
    for stream in (sys.__stdout__, sys.stdout):
        if stream is not None:
            stream.flush()
    data = (line + "\n").encode()
    while data:
        data = data[os.write(_check_lines[0], data) :]


def run(checks: list[Check], token: str) -> int:
    """In the grading child: run every check, print one line each, then the
    line that tells the parent every check ran. Returns 0 when all passed."""
    failed = 0
    for name, check in checks:
        try:
            check()
        except Exception as error:  # noqa: BLE001 - any error is the candidate's red
            failed += 1
            say(f"FAIL  {name}: {reason(error)}")
        else:
            say(f"PASS  {name}")
    say(f"{DONE} {token}")
    return 1 if failed else 0


def outcomes(lines: list[str]) -> dict[str, list[str]]:
    """Check name -> each ``PASS`` or ``FAIL`` printed for it, in order."""
    found: dict[str, list[str]] = {}
    for line in lines:
        match = CHECK_LINE.match(line)
        if match:
            found.setdefault(match.group(2), []).append(match.group(1))
    return found


def preflight(files: list[Path], timeout: float, env: dict[str, str]) -> int | None:
    """Import each candidate file in a child, as grade_substrate.py does.
    None when every file imports; else the exit code, after printing why."""
    for file in files:
        done = run_child(
            [sys.executable, str(PREFLIGHT), str(file)], timeout=timeout, env=env
        )
        if done is None:
            print(
                f"FAIL  the import pre-flight did not finish within {timeout:g} s: "
                f"importing {file.name} hangs or takes too long"
            )
            return 1
        said = done.stdout.strip().splitlines()
        if done.returncode == 3 and said and said[-1].startswith((NEEDS, LIBRARY)):
            # An environment problem, kept in Python's own wording.
            print(said[-1])
            return ENVIRONMENT_EXIT
        if done.returncode == 3:
            print(
                f"FAIL  the import pre-flight exited 3 on {file.name} without one "
                "of its own environment lines; a candidate that exits 3 is a red:\n"
                + scrub("\n".join(said[-3:]))
            )
            return 1
        if done.returncode != 0:
            verdict = done.stdout.strip() or (
                f"FAIL  the import pre-flight gave no verdict on {file.name} (exit "
                f"{done.returncode}):\n{done.stderr.strip()}"
            )
            print(scrub(verdict))
            return 1
    return None


def grade_in_child(
    script: Path,
    argv: list[str],
    names: list[str],
    files: list[Path],
    graded: str,
    timeout: float,
) -> int:
    """In the parent: pre-flight the candidate's files, then run ``script``
    with ``argv`` as the grading child, and pass only when the child printed
    one ``PASS`` line for each of ``names``, then the line that says every
    check ran and nothing after it, and exited 0. A child that exits early,
    by ``sys.exit`` or ``os._exit`` from the candidate's code or by a crash,
    or that runs past ``timeout`` seconds, is a red, and nothing it started
    in its process group keeps running."""
    watched = {**os.environ, PARENT: str(os.getpid())}
    stopped = preflight(files, timeout, watched)
    if stopped is not None:
        return stopped
    token = secrets.token_hex(16)
    done = run_child(
        [sys.executable, str(script), *argv],
        timeout=timeout,
        env={**watched, NONCE: token},
    )
    if done is None:
        print(f"FAIL  grading ran past {timeout:g} s on {graded}")
        return 1
    finished = f"{DONE} {token}"
    printed = done.stdout.splitlines()
    lines = [scrub(line) for line in printed if line != finished]
    if lines:
        print("\n".join(lines))
    if finished not in printed:
        tail = [scrub(line) for line in done.stderr.strip().splitlines()[-3:]]
        print(
            f"FAIL  grading stopped before every check ran on {graded} (the "
            f"grader exited {done.returncode})"
            + "".join(f"\n      {line}" for line in tail)
        )
        return 1
    after = len(printed) - 1 - printed.index(finished)
    results = outcomes(lines)
    repeated = sorted(name for name, said in results.items() if len(said) > 1)
    failed = [name for name in names if set(results.get(name, [])) != {"PASS"}]
    problems = [f"{len(failed)} of {len(names)} checks failed"] if failed else []
    if repeated:
        problems.append(f"more than one line for {', '.join(repeated)}")
    if after:
        problems.append(f"{after} line(s) after the line that ends the grading")
    if done.returncode != 0 and not failed:
        # A child whose checks all passed exits 0; anything else ended it.
        problems.append(f"every check passed, but the grader exited {done.returncode}")
    if problems:
        print(f"FAIL  {'; '.join(problems)} on {graded}")
        return 1
    print(f"PASS  all {len(names)} checks passed on {graded}")
    return 0
