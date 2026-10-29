"""Prove the usb-through-esd-swap variants against a live JITX runtime.

Stages a throwaway project (``pyproject.toml`` plus a package holding a copy of
``usb_esd_swap_design.py``) under the system temp directory, starts that
project's runtime in the background, runs
``jitx design issues <pkg.module.Variant> --satisfied --wait 60`` for each
variant named on the command line (all of them by default), stops the runtime,
and checks each report:

- ``straight``, ``swapped_inverted``: the time from ``host.usb.p`` to
  ``conn.usb.p`` and from ``host.usb.n`` to ``conn.usb.n`` and the intra-pair
  skew are measured, with no missing path, dropped route or unassigned pin. The
  routes of these two variants land on different channels, so a measurement
  with no dropped route means the assignment resolved to the mapping the routes
  name.
- ``illegal`` (D+ and D- on different channel pairs): a code route is dropped,
  at least one leg has no path, and no skew is measured.
- ``sides_disagree`` (host side and connector side on different channel
  pairs): a code route is dropped and neither leg has a path or a measurement.
- ``unrouted``: neither leg has a path, nothing is measured, nothing dropped.

The check asserts binding (a measured line), not compliance: a measured skew
outside the USB limit still passes.

Prints each report and one PASS or FAIL line per variant, and exits 1 on any
FAIL. Run it with the interpreter of a venv that has jitx installed; the
``jitx`` entry point beside that interpreter is used.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESIGN_FILE = HERE / "usb_esd_swap_design.py"
PACKAGE = "usb_esd_ref"
MODULE = f"{PACKAGE}.usb_esd_swap_design"
WAIT_SECONDS = "60"

PYPROJECT = """\
[project]
name = "usb-esd-ref"
version = "0.1"
dependencies = ["jitx>=4.6.0rc1,<5", "jitxlib-standard>=4.6.0rc1,<5"]
requires-python = ">=3.12"
"""

TIME_P = re.compile(r"Time: \S+ .*from host\.usb\.p to conn\.usb\.p")
TIME_N = re.compile(r"Time: \S+ .*from host\.usb\.n to conn\.usb\.n")
ANY_TIME = re.compile(r"\bTime: ")
SKEW = re.compile(r"Skew: \S+ .*from host\.usb\.[pn] to conn\.usb\.[pn]")
ANY_SKEW = re.compile(r"\bSkew: ")
NO_PATH_P = re.compile(
    r"No path for signal constraint from host\.usb\.p to conn\.usb\.p"
)
NO_PATH_N = re.compile(
    r"No path for signal constraint from host\.usb\.n to conn\.usb\.n"
)
NO_PATH = re.compile(r"No path for signal constraint")
UNASSIGNED = re.compile(r"Unassigned Pin")
DROPPED = re.compile(r"Code route dropped")
ERROR = re.compile(r"^Error:", re.MULTILINE)


def has(pattern: re.Pattern[str]) -> Callable[[str], bool]:
    return lambda report: pattern.search(report) is not None


def lacks(pattern: re.Pattern[str]) -> Callable[[str], bool]:
    return lambda report: pattern.search(report) is None


Expectation = tuple[str, Callable[[str], bool]]

# The constraint's ends are the fixed host and connector pins, and the assigned
# ESD pins sit between them. While the assignment is unresolved, the 4.6.0-rc.16
# runtime reports that span as "No path for signal constraint", not as
# "Unassigned Pin" (which it reports when a Topology ends on the required port).
MEASURES: list[Expectation] = [
    ("time host.usb.p -> conn.usb.p measured", has(TIME_P)),
    ("time host.usb.n -> conn.usb.n measured", has(TIME_N)),
    ("intra-pair skew measured", has(SKEW)),
    ("no missing path", lacks(NO_PATH)),
    ("no unassigned pin", lacks(UNASSIGNED)),
    ("no dropped code route", lacks(DROPPED)),
]
# Which leg the solver keeps is its choice, so only one missing leg is required.
SPLIT_PAIR: list[Expectation] = [
    ("code route dropped", has(DROPPED)),
    ("at least one leg has no path", has(NO_PATH)),
    ("no skew measured", lacks(ANY_SKEW)),
]
SIDES_DISAGREE: list[Expectation] = [
    ("code route dropped", has(DROPPED)),
    ("no path host.usb.p -> conn.usb.p", has(NO_PATH_P)),
    ("no path host.usb.n -> conn.usb.n", has(NO_PATH_N)),
    ("no time measured", lacks(ANY_TIME)),
    ("no skew measured", lacks(ANY_SKEW)),
]
UNROUTED: list[Expectation] = [
    ("no path host.usb.p -> conn.usb.p", has(NO_PATH_P)),
    ("no path host.usb.n -> conn.usb.n", has(NO_PATH_N)),
    ("no time measured", lacks(ANY_TIME)),
    ("no skew measured", lacks(ANY_SKEW)),
    ("no dropped code route", lacks(DROPPED)),
]

VARIANTS: dict[str, tuple[str, list[Expectation]]] = {
    "straight": ("Straight", MEASURES),
    "swapped_inverted": ("SwappedInverted", MEASURES),
    "illegal": ("Illegal", SPLIT_PAIR),
    "sides_disagree": ("SidesDisagree", SIDES_DISAGREE),
    "unrouted": ("Unrouted", UNROUTED),
}


def jitx_cli() -> str:
    beside = Path(sys.executable).parent / "jitx"
    if beside.exists():
        return str(beside)
    found = shutil.which("jitx")
    if found is None:
        raise SystemExit("jitx entry point not found beside the interpreter or on PATH")
    return found


def stage(root: Path) -> None:
    (root / "pyproject.toml").write_text(PYPROJECT)
    package = root / PACKAGE
    package.mkdir()
    (package / "__init__.py").write_text("")
    shutil.copyfile(DESIGN_FILE, package / DESIGN_FILE.name)


def run(
    cmd: list[str], root: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
    )


def check(name: str, report: str, expectations: list[Expectation]) -> bool:
    if ERROR.search(report):
        print(f"FAIL variant={name}: the command reported an error")
        return False
    misses = [label for label, test in expectations if not test(report)]
    if misses:
        print(f"FAIL variant={name}: " + "; ".join(misses))
        return False
    print(f"PASS variant={name}: " + "; ".join(label for label, _ in expectations))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "variants", nargs="*", metavar="variant", help=", ".join(VARIANTS)
    )
    args = parser.parse_args()
    names: list[str] = args.variants or list(VARIANTS)
    unknown = [name for name in names if name not in VARIANTS]
    if unknown:
        parser.error(
            f"unknown variant(s) {', '.join(unknown)}; choose from {', '.join(VARIANTS)}"
        )

    jitx = jitx_cli()
    root = Path(tempfile.mkdtemp(prefix="usb-esd-swap-"))
    stage(root)
    env = {**os.environ, "PYTHONPATH": str(root)}
    project = ["--project", str(root)]
    ok = True
    try:
        started = run([jitx, "runtime", "start", "--background", *project], root, env)
        if started.returncode != 0:
            print(started.stdout + started.stderr)
            print("FAIL runtime did not start")
            return 1
        for name in names:
            design, expectations = VARIANTS[name]
            cmd = [
                jitx,
                "design",
                "issues",
                f"{MODULE}.{design}",
                "--satisfied",
                "--wait",
                WAIT_SECONDS,
                *project,
            ]
            result = run(cmd, root, env)
            report = result.stdout + result.stderr
            print(f"--- {MODULE}.{design} (exit {result.returncode})")
            print(report.rstrip())
            ok = check(name, report, expectations) and ok
    finally:
        stopped = run([jitx, "runtime", "stop", *project], root, env)
        if stopped.returncode != 0:
            print(stopped.stdout + stopped.stderr)
            print(f"WARNING runtime stop exited {stopped.returncode}; project {root}")
    if ok:
        shutil.rmtree(root, ignore_errors=True)
    else:
        print(f"staged project kept for inspection: {root}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
