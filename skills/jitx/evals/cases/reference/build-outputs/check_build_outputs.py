"""Check what ``jitx build`` writes, against the base skill's "Running designs".

Stages a throwaway project (``pyproject.toml`` plus a package holding a copy of
``build_outputs_design.py``) under the system temp directory, starts that
project's runtime in the background, runs
``jitx build build_outputs_ref.build_outputs_design.BuildOutputsDesign``, stops
the runtime, and checks the design's ``designs/<module.path.DesignClass>/``
folder:

- the build printed ``status: ok``;
- ``cache/design-explorer.json`` exists and ``cache/netlist.json`` does not;
- the file is a module tree: the top ``module`` holds its own ``nets`` (the
  ``LINK`` net, on ``load.a``) and its ``module-instances``, and the ``stage``
  child holds its own ``nets`` (``MID``, on ``stage.first.b`` and
  ``stage.second.a``), which the top module's ``nets`` do not repeat, so the
  file is no flat netlist;
- each part in ``component-instances`` carries its ``mpn``.

Prints one PASS or FAIL line per check and exits 1 on any FAIL. Run it with the
interpreter of a venv that has jitx installed; the ``jitx`` entry point beside
that interpreter is used.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DESIGN_FILE = HERE / "build_outputs_design.py"
PACKAGE = "build_outputs_ref"
DESIGN = f"{PACKAGE}.build_outputs_design.BuildOutputsDesign"
FIXTURE_MPN = "FIXTURE-2P-0001"

PYPROJECT = """\
[project]
name = "build-outputs-ref"
version = "0.1"
dependencies = ["jitx"]
requires-python = ">=3.12"
"""


def jitx_cli() -> str:
    beside = Path(sys.executable).parent / "jitx"
    if beside.exists():
        return str(beside)
    found = shutil.which("jitx")
    if found is None:
        raise SystemExit("jitx entry point not found beside the interpreter or on PATH")
    return found


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


def net_refs(module: dict[str, Any]) -> dict[str, set[str]]:
    """Each of ``module``'s own nets, by name, to the pin refs it lists."""
    nets: dict[str, set[str]] = {}
    stack = list(module.get("nets", []))
    while stack:
        net = stack.pop()
        if net.get("__object_type__") == "TreeNetBundle":
            stack += net.get("nets", [])
            continue
        nets[net["name"]] = {p["ref"] for p in net.get("pins", [])}
    return nets


def has_net(module: dict[str, Any], refs: set[str]) -> bool:
    return any(refs <= pins for pins in net_refs(module).values())


def components(module: dict[str, Any]) -> list[dict[str, Any]]:
    found = list(module.get("component-instances", []))
    for child in module.get("module-instances", []):
        found += components(child)
    return found


def checks(
    build: subprocess.CompletedProcess[str], folder: Path
) -> list[tuple[str, bool]]:
    cache = folder / "cache"
    explorer = cache / "design-explorer.json"
    results = [
        ("build printed status: ok", "status: ok" in build.stdout + build.stderr),
        ("cache/design-explorer.json exists", explorer.is_file()),
        ("cache/netlist.json does not exist", not (cache / "netlist.json").exists()),
    ]
    if not explorer.is_file():
        return results
    tree = json.loads(explorer.read_text())
    top = tree.get("module", {})
    stages = [m for m in top.get("module-instances", []) if m.get("name") == "stage"]
    parts = components(top)
    results += [
        ("top module lists its own nets: LINK on load.a", has_net(top, {"load.a"})),
        ("top module lists the stage child under module-instances", len(stages) == 1),
        (
            "stage child lists its own nets: MID on stage.first.b and stage.second.a",
            bool(stages) and has_net(stages[0], {"stage.first.b", "stage.second.a"}),
        ),
        (
            "top module's own nets leave out the stage's MID",
            not has_net(top, {"stage.first.b", "stage.second.a"}),
        ),
        (
            "every component instance carries its mpn",
            len(parts) == 3 and all(p.get("mpn") == FIXTURE_MPN for p in parts),
        ),
    ]
    return results


def main() -> int:
    jitx = jitx_cli()
    root = Path(tempfile.mkdtemp(prefix="build-outputs-"))
    (root / "pyproject.toml").write_text(PYPROJECT)
    package = root / PACKAGE
    package.mkdir()
    (package / "__init__.py").write_text("")
    shutil.copyfile(DESIGN_FILE, package / DESIGN_FILE.name)
    env = {**os.environ, "PYTHONPATH": str(root)}
    project = ["--project", str(root)]
    try:
        started = run([jitx, "runtime", "start", "--background", *project], root, env)
        if started.returncode != 0:
            print(started.stdout + started.stderr)
            print("FAIL runtime did not start")
            return 1
        build = run([jitx, "build", DESIGN, *project], root, env)
        print(f"--- jitx build {DESIGN} (exit {build.returncode})")
        print((build.stdout + build.stderr).rstrip())
    finally:
        stopped = run([jitx, "runtime", "stop", *project], root, env)
        if stopped.returncode != 0:
            print(stopped.stdout + stopped.stderr)
            print(f"WARNING runtime stop exited {stopped.returncode}; project {root}")
    folder = root / "designs" / DESIGN
    results = checks(build, folder)
    for label, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} {label}")
    ok = all(passed for _, passed in results)
    if ok:
        shutil.rmtree(root, ignore_errors=True)
    else:
        print(f"staged project kept for inspection: {root}")
        if folder.is_dir():
            print(
                "design folder:",
                sorted(str(p.relative_to(folder)) for p in folder.rglob("*"))[:40],
            )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
