"""Build, capture, and check the QFN power-fanout reference.

The script copies the reference into a temporary JITX project so build output
never lands in the shipped skill tree. It exits nonzero on setup, build,
capture, route-realization, or width failures.
"""

from __future__ import annotations

import importlib
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import jitx


DESIGN_TARGET = "qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign"
WIDTH_TOLERANCE_MM = 1e-6  # skill default: 1e-6 mm width comparison
PYPROJECT = """\
[build-system]
requires = ["hatchling>=1.27.0,<2.0"]
build-backend = "hatchling.build"

[project]
name = "qfn-power-fanout-reference"
version = "0.1"
dependencies = ["jitx>=4.4.0rc2,<5", "jitxlib-standard>=4.4.0rc2,<5"]
requires-python = ">=3.12"
"""


def run_cli(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run one JITX CLI command and print output with the temp root normalized."""

    command = [sys.executable, "-m", "jitx", *arguments]
    display_command = ["python", "-m", "jitx", *arguments]
    print(f"$ {' '.join(display_command)}")
    result = subprocess.run(
        command,
        cwd=project,
        env={**os.environ, "PYTHONPATH": str(project)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.stdout:
        output = result.stdout.replace(
            str(project.resolve()), "<temporary-project>"
        ).replace(str(project), "<temporary-project>")
        print(output, end="" if output.endswith("\n") else "\n")
    if result.returncode:
        runtime_log = project.resolve() / ".jitx" / "logs" / "runtime.log"
        if runtime_log.exists():
            lines = [
                line
                for line in runtime_log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            socket_lines = [line for line in lines if "lws_socket_bind" in line]
            if lines:
                detail = (socket_lines or lines)[0]
                detail = detail.split(" E: ", maxsplit=1)[-1]
                detail = detail.replace(str(Path.home()), "$HOME")
                print(f"[runtime.log] {detail}")
        raise RuntimeError(
            f"command exited {result.returncode}: {' '.join(display_command)}"
        )
    return result


def prepare_project(project: Path) -> None:
    """Copy the reference module into a temporary importable project."""

    source = Path(__file__).with_name("qfn_power_fanout.py")
    package = project / "qfn_power_fanout"
    package.mkdir()
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(source, package / source.name)


def assert_widths(
    name: str, actual: tuple[float, ...], expected: float
) -> None:
    if not actual:
        raise AssertionError(f"{name} has no realized polyline widths")
    wrong = [
        width
        for width in actual
        if not math.isclose(width, expected, abs_tol=WIDTH_TOLERANCE_MM)
    ]
    if wrong:
        raise AssertionError(
            f"{name} expected {expected:.6f} mm, got {actual!r}"
        )


def capture_and_check(project: Path) -> None:
    """Capture the design and assert realization plus both winning widths."""

    old_cwd = Path.cwd()
    old_path = list(sys.path)
    os.chdir(project)
    sys.path.insert(0, str(project))
    try:
        reference = importlib.import_module("qfn_power_fanout.qfn_power_fanout")
        with jitx.runtime as runtime:
            runtime_design = runtime.submit(reference.QfnPowerFanoutDesign)
            runtime_design.capture()

        circuit = runtime_design.root.circuit
        if not circuit.trunk_route.traces:
            raise AssertionError("trunk route has empty traces after capture")
        if not circuit.escape_route.traces:
            raise AssertionError("escape route has empty traces after capture")

        trunk_widths = reference.realized_route_widths(circuit.trunk_route)
        escape_widths = reference.realized_route_widths(circuit.escape_route)
        expected_escape = circuit.escape_geometry.escape_width
        assert_widths("trunk", trunk_widths, reference.POWER_CLASS_WIDTH_MM)
        assert_widths("escape", escape_widths, expected_escape)

        print(
            "[PASS] trunk route realized at "
            f"{trunk_widths} mm, expected {reference.POWER_CLASS_WIDTH_MM:.6f} mm"
        )
        print(
            "[PASS] escape route realized at "
            f"{escape_widths} mm, expected {expected_escape:.6f} mm"
        )
        print("[PASS] trunk and escape routes have non-empty traces")
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="qfn-power-fanout-") as temporary:
            project = Path(temporary)
            prepare_project(project)
            started = False
            try:
                run_cli(project, "runtime", "start", "--background")
                started = True
                run_cli(project, "build", DESIGN_TARGET)
                print("$ python check_fanout.py  # submit, capture, and assertions")
                capture_and_check(project)
            finally:
                if started:
                    try:
                        run_cli(project, "runtime", "stop")
                    except RuntimeError as error:
                        print(f"[WARN] runtime stop failed: {error}")
    except Exception as error:
        print(f"[FAIL] {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
