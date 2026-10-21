"""design_check.py passes a design that binds board.py's substrate and
translates, and fails each way a design can miss that.

testdata/case_a/good_design and testdata/case_a/sample_substrate_design are
the two directories a reader can run the check on by hand. The other rows edit
a copy of the good one. Every row runs the script as the eval runs it, so the
import, the instantiation and the ``jitx build --dry`` child are real.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

CHECKS = Path(__file__).resolve().parent
SCRIPT = CHECKS / "design_check.py"
CASE_A = CHECKS / "testdata" / "case_a"

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("jitx") is None,
    reason="jitx is not importable; install jitx to run this test",
)


def run(output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(output)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def good_copy(tmp_path: Path) -> Path:
    output = tmp_path / "output"
    shutil.copytree(CASE_A / "good_design", output)
    return output


def edit(name: str, old: str, new: str) -> Callable[[Path], None]:
    def apply(output: Path) -> None:
        path = output / name
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, old
        path.write_text(text.replace(old, new), encoding="utf-8")

    return apply


def remove(name: str) -> Callable[[Path], None]:
    def apply(output: Path) -> None:
        (output / name).unlink()

    return apply


def test_good_design_passes() -> None:
    done = run(CASE_A / "good_design")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS  design.py in" in done.stdout


def test_design_binding_the_sample_substrate_fails() -> None:
    done = run(CASE_A / "sample_substrate_design")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "FAIL  design.SmokeTest builds the sample substrate" in done.stdout


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            edit(
                "design.py",
                "class SmokeTest(Design):",
                "from jitx.sample import SampleDesign\n\n\n"
                "class SmokeTest(SampleDesign):",
            ),
            "builds the sample design",
        ),
        (
            edit("design.py", "class SmokeTest(Design):", "class SmokeTest(Circuit):"),
            "no Design in design.py binds a Substrate defined in board.py",
        ),
        (
            edit("board.py", "    constraints = Rules()\n", ""),
            "design.SmokeTest does not translate (jitx build exit 1)",
        ),
        (remove("design.py"), "design.py does not exist"),
    ],
    ids=[
        "a SampleDesign subclass",
        "no Design at all",
        "a substrate that does not translate",
        "no design.py",
    ],
)
def test_each_way_a_design_misses_is_red(
    tmp_path: Path, change: Callable[[Path], None], reason: str
) -> None:
    output = good_copy(tmp_path)
    change(output)
    done = run(output)
    assert done.returncode == 1, done.stdout + done.stderr
    assert reason in done.stdout
