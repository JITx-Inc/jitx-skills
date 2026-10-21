#!/usr/bin/env python3
"""Check that the runner's design binds its own substrate and translates.

Usage:
  design_check.py OUTPUT_DIR [--timeout SECONDS]

OUTPUT_DIR holds the runner's ``board.py`` (the substrate) and ``design.py``
(a JITX ``Design`` that binds it). The check copies OUTPUT_DIR into a scratch
project with a ``pyproject.toml`` of its own, then:

1. imports ``design`` there, in a child interpreter, and instantiates each
   ``Design`` subclass that ``design.py`` itself defines. A design matches when
   it is not a ``SampleDesign`` subclass and its ``substrate`` is an instance
   of a ``Substrate`` subclass defined in ``board.py``. A design that binds
   ``SampleSubstrate``, or subclasses ``SampleDesign``, is a red: it would
   build the sample substrate, not the runner's.
2. runs ``jitx build --dry --no-dependency-check design.<Name>`` in the
   scratch project for every matching design, through this interpreter's
   jitx. ``--dry`` translates without connecting to a JITX runtime.

It passes only when at least one design matches, no design binds the sample
substrate, and every matching design translates. A design that does not
instantiate is noted, and fails the check only by leaving no design that
matches. POSIX only, like
``grade_substrate.py``, whose child runner it uses.

Exit codes: 0 pass / 1 red, with a ``FAIL  `` line per reason / 2 usage
error (no such directory).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from grade_substrate import run_child

TIMEOUT_S = 300.0
"""Seconds each child may run."""

PYPROJECT = """[project]
name = "substrate-eval-design"
version = "0"
dependencies = ["jitx"]
"""
"""The scratch project's own pyproject.toml. ``jitx build`` needs a project
root that lists jitx as a dependency; the dependency check is skipped."""

IGNORED = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")


def find_designs() -> dict[str, object]:
    """Run in the child, with the scratch project first on ``sys.path``: each
    ``Design`` subclass ``design.py`` defines, with what it binds."""
    from jitx._instantiation import instantiation
    from jitx.design import Design
    from jitx.proxy import typeof
    from jitx.sample import SampleDesign, SampleSubstrate
    from jitx.substrate import Substrate

    board = importlib.import_module("board")
    design = importlib.import_module("design")
    substrates = tuple(
        value
        for value in vars(board).values()
        if isinstance(value, type)
        and issubclass(value, Substrate)
        and value.__module__ == board.__name__
    )
    found: dict[str, object] = {
        "substrates": sorted(cls.__name__ for cls in substrates),
        "designs": {},
    }
    designs: dict[str, str] = {}
    for value in vars(design).values():
        if not (
            isinstance(value, type)
            and issubclass(value, Design)
            and value.__module__ == design.__name__
        ):
            continue
        if issubclass(value, SampleDesign):
            designs[value.__name__] = "sample design"
            continue
        try:
            with instantiation.activate(), instantiation.frame():
                bound = typeof(value().substrate)
        except Exception as error:  # noqa: BLE001 - reported as the design's red
            designs[value.__name__] = f"error: {type(error).__name__}: {error}"
            continue
        if issubclass(bound, SampleSubstrate):
            designs[value.__name__] = "sample substrate"
        elif substrates and issubclass(bound, substrates):
            designs[value.__name__] = "match"
        else:
            designs[value.__name__] = f"binds {bound.__module__}.{bound.__qualname__}"
    found["designs"] = designs
    return found


def scratch_project(output: Path, root: Path) -> Path:
    """A copy of ``output`` under ``root``, with its own pyproject.toml."""
    project = root / "project"
    shutil.copytree(output, project, ignore=IGNORED)
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return project


def child_env(project: Path) -> dict[str, str]:
    """This environment with the scratch project first on PYTHONPATH."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(project), env.get("PYTHONPATH", "")) if part
    )
    return env


def check(output: Path, timeout: float) -> list[str]:
    """Every reason the output fails; empty when it passes."""
    for name in ("board.py", "design.py"):
        if not (output / name).is_file():
            return [f"{output / name} does not exist"]
    with tempfile.TemporaryDirectory(prefix="design-check-") as tmp:
        project = scratch_project(output, Path(tmp))
        env = child_env(project)
        done = run_child(
            [sys.executable, str(Path(__file__).resolve()), "--find"],
            timeout=timeout,
            env=env,
            cwd=project,
        )
        if done is None:
            return [f"importing design.py did not finish within {timeout:g} s"]
        if done.returncode != 0:
            tail = (done.stderr.strip() or done.stdout.strip()).splitlines()[-1:]
            return [f"design.py does not import: {' '.join(tail) or 'no output'}"]
        found = json.loads(done.stdout.strip().splitlines()[-1])
        designs: dict[str, str] = found["designs"]
        problems = [
            f"design.{name} builds the {verdict}, not the substrate in board.py"
            for name, verdict in designs.items()
            if verdict in ("sample design", "sample substrate")
        ]
        for name, verdict in designs.items():
            if verdict.startswith("error: "):
                print(f"note: design.{name} does not instantiate: {verdict[7:]}")
        matched = [name for name, verdict in designs.items() if verdict == "match"]
        if not matched:
            listed = ", ".join(f"{n} ({v})" for n, v in designs.items()) or "none"
            problems.append(
                "no Design in design.py binds a Substrate defined in board.py "
                f"({', '.join(found['substrates']) or 'none defined'}); designs: "
                f"{listed}"
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
                problems.append(f"design.{name} did not translate within {timeout:g} s")
            elif build.returncode != 0 or "status: ok" not in build.stdout:
                text = (build.stdout + build.stderr).strip()
                problems.append(
                    f"design.{name} does not translate (jitx build exit "
                    f"{build.returncode}):\n{text[-2000:]}"
                )
            else:
                print(f"design.{name} binds the board.py substrate and translates")
    return problems


def main(argv: list[str]) -> int:
    if argv[1:] == ["--find"]:
        sys.path.insert(0, os.getcwd())
        print(json.dumps(find_designs()))
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
    problems = check(output, args.timeout)
    for problem in problems:
        print(f"FAIL  {problem}")
    if not problems:
        print(f"PASS  design.py in {output} binds its substrate and translates")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
