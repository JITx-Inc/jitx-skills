#!/usr/bin/env python3
"""Check that the runner's design binds its own substrate and translates.

Usage:
  design_check.py OUTPUT_DIR [--timeout SECONDS]

OUTPUT_DIR holds the runner's ``board.py`` (the substrate) and ``design.py``
(a JITX ``Design`` that binds it). The check copies OUTPUT_DIR into a scratch
project with a ``pyproject.toml`` of its own, then:

1. imports ``board.py`` and ``design.py`` there, each in a child interpreter,
   through ``import_candidate.py``, so a file that does not import is a red
   and a library that does not import is an environment problem;
2. lists, in another child, each ``Design`` subclass in ``design.py``'s
   namespace that ``design.py`` or ``board.py`` defines, instantiates it, and
   reads the substrate it binds. A design matches when it is not a
   ``SampleDesign`` subclass and binds the substrate the grader grades: the
   one ``Substrate`` subclass board.py defines that no other subclasses. A
   design that binds ``SampleSubstrate``, or subclasses ``SampleDesign``, is a
   red: it would build the sample substrate, not the runner's;
3. runs ``jitx build --dry --no-dependency-check design.<Name>`` in the
   scratch project for every matching design, through this interpreter's
   jitx. ``--dry`` translates without connecting to a JITX runtime.

It passes only when at least one design matches, no design builds the sample
substrate, and every matching design translates. A design that does not
instantiate is noted, and fails the check only by leaving no design that
matches. POSIX only, like ``grade_substrate.py``, whose child runner and
signal handling it uses: SIGTERM or SIGHUP ends every child and removes the
scratch project.

Exit codes: 0 pass / 1 red, with a ``FAIL  `` line per reason / 2 usage
error (no such directory) / 3 an environment problem, as an ``ERROR  `` line
in Python's own wording (this interpreter lacks jitx, or a library the
runner's files import does not import).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import signal
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from grade_substrate import run_child, stop
from parent_watch import PARENT

TIMEOUT_S = 300.0
"""Seconds each child may run."""

PYPROJECT = """[project]
name = "substrate-eval-design"
version = "0"
dependencies = ["jitx"]
"""
"""The scratch project's own pyproject.toml. ``jitx build`` needs a project
root that lists jitx as a dependency; the dependency check is skipped."""

IGNORED = shutil.ignore_patterns(
    "__pycache__", ".pytest_cache", "*.pyc", ".venv", "venv", ".git"
)
"""Left out of the scratch copy: caches, a virtualenv and version control."""

PREFLIGHT = Path(__file__).resolve().parent / "import_candidate.py"
"""Imports one file in a child and says whose fault a failure is."""


@dataclass
class Verdict:
    """What a check found: environment problems, then reds."""

    errors: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def plain(text: str) -> str:
    """``text`` without Python's own words for a failed import. Eval
    harnesses read those words as an environment problem, so a red that
    quotes a runner's failed import must not carry them."""
    for pattern, words in (
        (r"cannot import name ('[^']*') from ('[^']*')", r"\2 has no name \1"),
        (r"cannot import name\b", "no importable name"),
        (r"No module named ('[^']*')", r"module \1 not found"),
        (r"No module named\b", "module not found"),
    ):
        text = re.sub(pattern, words, text, flags=re.IGNORECASE)
    return text


def tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def missing(script: str, names: tuple[str, ...]) -> str | None:
    """An ``ERROR  `` line for the first of ``names`` this interpreter, which
    every child also runs under, cannot import; None when all import."""
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as error:  # noqa: BLE001 - whatever it raises, not the runner's
            return f"{script} needs {name}: {type(error).__name__}: {error}"
    return None


def copy_output(output: Path, project: Path) -> None:
    """Copy the runner's directory, less ``IGNORED``; a symlink to nothing is
    skipped rather than copied."""
    shutil.copytree(output, project, ignore=IGNORED, ignore_dangling_symlinks=True)


def child_env(project: Path) -> dict[str, str]:
    """This environment with the scratch project first on PYTHONPATH, and
    this process named as the parent import_candidate.py watches."""
    env = {**os.environ, PARENT: str(os.getpid())}
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(project), env.get("PYTHONPATH", "")) if part
    )
    return env


def import_file(
    path: Path, env: dict[str, str], timeout: float, verdict: Verdict
) -> bool:
    """Import ``path`` in a child through import_candidate.py. A failure is
    added to ``verdict``, as a red or an environment problem; True when it
    imports."""
    done = run_child(
        [sys.executable, str(PREFLIGHT), str(path)],
        timeout=timeout,
        env=env,
        cwd=path.parent,
    )
    if done is None:
        verdict.problems.append(
            f"importing {path.name} did not finish within {timeout:g} s"
        )
        return False
    if done.returncode == 0:
        return True
    said = done.stdout.strip()
    if done.returncode == 3 and said.startswith("ERROR  "):
        verdict.errors.append(said.removeprefix("ERROR  "))
    elif done.returncode == 1 and said.startswith("FAIL  candidate does not import: "):
        what = said.removeprefix("FAIL  candidate does not import: ")
        verdict.problems.append(f"{path.name} does not import: {plain(what)}")
    else:
        verdict.errors.append(
            f"the import check on {path.name} gave no verdict (exit "
            f"{done.returncode}):\n{tail(done.stdout + done.stderr)}"
        )
    return False


def find_designs() -> dict[str, object]:
    """Run in the child, with the scratch project first on ``sys.path``: the
    substrates board.py defines, and each design with what it binds."""
    from jitx._instantiation import instantiation
    from jitx.design import Design
    from jitx.proxy import typeof
    from jitx.sample import SampleDesign, SampleSubstrate
    from jitx.substrate import Substrate

    board = importlib.import_module("board")
    design = importlib.import_module("design")
    defined = [
        value
        for value in vars(board).values()
        if isinstance(value, type)
        and issubclass(value, Substrate)
        and value.__module__ == board.__name__
    ]
    # As the grader picks its substrate: a shared base class does not count.
    leaves = [
        cls
        for cls in defined
        if not any(other is not cls and issubclass(other, cls) for other in defined)
    ]
    graded = leaves[0] if len(leaves) == 1 else None
    designs: dict[str, str] = {}
    for name, value in vars(design).items():
        if not (
            isinstance(value, type)
            and issubclass(value, Design)
            and value.__module__ in (design.__name__, board.__name__)
        ):
            continue
        if issubclass(value, SampleDesign):
            designs[name] = "sample design"
            continue
        try:
            with instantiation.activate(), instantiation.frame():
                bound = typeof(value().substrate)
        except Exception as error:  # noqa: BLE001 - reported as a note
            designs[name] = f"error: {type(error).__name__}: {error}"
            continue
        if issubclass(bound, SampleSubstrate):
            designs[name] = "sample substrate"
        elif bound is graded:
            designs[name] = "match"
        else:
            designs[name] = f"binds {bound.__module__}.{bound.__qualname__}"
    return {
        "substrates": sorted(cls.__name__ for cls in defined),
        "leaves": sorted(cls.__name__ for cls in leaves),
        "designs": designs,
    }


def list_designs(
    project: Path, env: dict[str, str], timeout: float, verdict: Verdict
) -> tuple[dict[str, str], list[str]] | None:
    """find_designs' designs and substrate leaves, from a child that writes
    them to a file, so nothing a runner's file prints can change them."""
    result = project.parent / "designs.json"
    done = run_child(
        [sys.executable, str(Path(__file__).resolve()), "--find", str(result)],
        timeout=timeout,
        env=env,
        cwd=project,
    )
    if done is None:
        verdict.problems.append(
            f"listing the designs did not finish within {timeout:g} s"
        )
        return None
    try:
        found = json.loads(result.read_text(encoding="utf-8"))
        designs = {str(k): str(v) for k, v in found["designs"].items()}
        leaves = [str(name) for name in found["leaves"]]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        designs, leaves = None, None
    if done.returncode != 0 or designs is None or leaves is None:
        verdict.problems.append(
            f"listing the designs in design.py failed (exit {done.returncode}):\n"
            + plain(tail(done.stdout + done.stderr))
        )
        return None
    return designs, leaves


def check(output: Path, timeout: float) -> Verdict:
    """Every environment problem and red; both empty when the output passes."""
    verdict = Verdict()
    error = missing("design_check.py", ("jitx", "jitx.proxy"))
    if error is not None:
        verdict.errors.append(error)
        return verdict
    for name in ("board.py", "design.py"):
        if not (output / name).is_file():
            verdict.problems.append(f"{output / name} does not exist")
            return verdict
    with tempfile.TemporaryDirectory(prefix="design-check-") as tmp:
        project = Path(tmp) / "project"
        copy_output(output, project)
        (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
        env = child_env(project)
        for name in ("board.py", "design.py"):
            if not import_file(project / name, env, timeout, verdict):
                return verdict
        found = list_designs(project, env, timeout, verdict)
        if found is None:
            return verdict
        designs, leaves = found
        verdict.problems += [
            f"design.{name} builds the {said}, not the substrate in board.py"
            for name, said in designs.items()
            if said in ("sample design", "sample substrate")
        ]
        for name, said in designs.items():
            if said.startswith("error: "):
                print(f"note: design.{name} does not instantiate: {plain(said[7:])}")
        matched = [name for name, said in designs.items() if said == "match"]
        if len(leaves) != 1:
            listed = ", ".join(leaves) or "none"
            verdict.problems.append(
                "board.py must define exactly one Substrate subclass that no other "
                f"subclasses, the one the grader grades. Found: {listed}"
            )
        elif not matched:
            listed = ", ".join(f"{n} ({v})" for n, v in designs.items()) or "none"
            verdict.problems.append(
                f"no Design in design.py binds {leaves[0]}, the Substrate board.py "
                f"defines for the grader; designs: {plain(listed)}"
            )
        for name in matched:
            build = run_child(
                [
                    sys.executable,
                    "-m",
                    "jitx",
                    "build",
                    "--dry",
                    "--no-dependency-check",
                    f"design.{name}",
                ],
                timeout=timeout,
                env=env,
                cwd=project,
            )
            if build is None:
                verdict.problems.append(
                    f"design.{name} did not translate within {timeout:g} s"
                )
            elif build.returncode != 0 or "status: ok" not in build.stdout:
                text = plain((build.stdout + build.stderr).strip())
                verdict.problems.append(
                    f"design.{name} does not translate (jitx build exit "
                    f"{build.returncode}):\n{text[-2000:]}"
                )
            else:
                print(f"design.{name} binds the board.py substrate and translates")
    return verdict


def report(verdict: Verdict, passed: str) -> int:
    """Print the verdict's lines; its exit code."""
    for error in verdict.errors:
        print(f"ERROR  {error}")
    if verdict.errors:
        return 3
    for problem in verdict.problems:
        print(f"FAIL  {problem}")
    if verdict.problems:
        return 1
    print(f"PASS  {passed}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--find":
        sys.path.insert(0, os.getcwd())
        Path(argv[2]).write_text(json.dumps(find_designs()), encoding="utf-8")
        return 0
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("output")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_S)
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as error:
        return 2 if error.code else 0
    output = Path(args.output)
    if not output.is_dir():
        print(f"error: no output directory at {output}", file=sys.stderr)
        return 2
    return report(
        check(output, args.timeout),
        f"design.py in {output} binds its substrate and translates",
    )


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    sys.exit(main(sys.argv))
