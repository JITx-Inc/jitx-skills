"""design_check.py passes a design that binds board.py's substrate and
translates, and fails each way a design can miss that.

testdata/case_a/good_design and testdata/case_a/sample_substrate_design are
the two directories a reader can run the check on by hand. The other rows edit
a copy of the good one. Every row runs the script as the eval runs it, so the
imports, the instantiation and the ``jitx build --dry`` child are real.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import design_check
import pytest
from import_candidate import ENVIRONMENT_WORDING

CHECKS = Path(__file__).resolve().parent
SCRIPT = CHECKS / "design_check.py"
CASE_A = CHECKS / "testdata" / "case_a"

OPTIONAL_IMPORT = (
    "try:\n"
    "    import jitx_rf_helpers  # noqa: F401\n"
    "except ImportError as missing_helper:\n"
    '    print(f"note: {missing_helper}; using built-in defaults")\n'
    "EXTRA = UNDEFINED_NAME  # noqa: F821\n\n\n"
)
"""An optional import whose failure the board prints, in Python's wording,
before an error of the board's own stops it importing."""


def exits_at_import(line: str, code: int) -> str:
    """Code that ends the import pre-flight with ``line`` and exit ``code``."""
    return (
        "import os\n\n"
        'if __name__ == "_candidate_preflight":\n'
        f"    print({line!r}, flush=True)\n"
        f"    os._exit({code})\n\n\n"
    )


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("jitx") is None,
    reason="jitx is not importable; install jitx to run this test",
)


def run(output: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *flags, str(SCRIPT), str(output)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def good_copy(tmp_path: Path) -> Path:
    output = tmp_path / "output"
    shutil.copytree(CASE_A / "good_design", output)
    return output


Change = Callable[[Path], None]


def edit(name: str, old: str, new: str) -> Change:
    def apply(output: Path) -> None:
        path = output / name
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, old
        path.write_text(text.replace(old, new), encoding="utf-8")

    return apply


def both(*changes: Change) -> Change:
    def apply(output: Path) -> None:
        for change in changes:
            change(output)

    return apply


def remove(name: str) -> Change:
    def apply(output: Path) -> None:
        (output / name).unlink()

    return apply


def design_in_board(output: Path) -> None:
    """The design's classes moved into board.py; design.py re-exports it."""
    design = (output / "design.py").read_text(encoding="utf-8")
    body = design.replace("from board import TwoLayerSubstrate\n", "")
    with (output / "board.py").open("a", encoding="utf-8") as board:
        board.write("\n\n" + body)
    (output / "design.py").write_text("from board import SmokeTest\n", encoding="utf-8")


def clutter(output: Path) -> None:
    """What a runner's directory may also hold: a virtualenv, a git directory
    and a symlink to nothing."""
    (output / ".venv" / "bin").mkdir(parents=True)
    os.symlink("/nonexistent/python", output / ".venv" / "bin" / "python")
    (output / ".git").mkdir()
    (output / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    os.symlink("missing.py", output / "stale.py")


def test_good_design_passes() -> None:
    done = run(CASE_A / "good_design")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS  design.py in" in done.stdout


def test_design_binding_the_sample_substrate_fails() -> None:
    done = run(CASE_A / "sample_substrate_design")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "FAIL  design.SmokeTest builds the sample substrate" in done.stdout


@pytest.mark.parametrize(
    "change",
    [
        design_in_board,
        edit(
            "design.py",
            "class SmokeTest(Design):",
            'import atexit\n\nprint("at import", end="")\n'
            'atexit.register(print, "at exit")\n\n\nclass SmokeTest(Design):',
        ),
        clutter,
    ],
    ids=[
        "a Design defined in board.py",
        "a design.py that prints at import and at exit",
        "a virtualenv, a git directory and a broken symlink",
    ],
)
def test_each_way_of_writing_a_good_design_passes(
    tmp_path: Path, change: Change
) -> None:
    output = good_copy(tmp_path)
    change(output)
    done = run(output)
    assert done.returncode == 0, done.stdout + done.stderr


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
            "no Design in design.py binds TwoLayerSubstrate",
        ),
        (
            edit(
                "design.py",
                "class SmokeTest(Design):\n    substrate = TwoLayerSubstrate()",
                "class Swapped(TwoLayerSubstrate):\n    pass\n\n\n"
                "class SmokeTest(Design):\n    substrate = Swapped()",
            ),
            "SmokeTest (binds design.Swapped)",
        ),
        (
            both(
                edit(
                    "board.py",
                    "class TwoLayerSubstrate(Substrate):",
                    "class Base(Substrate):\n    stackup = TwoLayer()\n"
                    "    constraints = Rules()\n\n\nclass TwoLayerSubstrate(Base):",
                ),
                edit(
                    "design.py",
                    "from board import TwoLayerSubstrate",
                    "from board import Base as TwoLayerSubstrate",
                ),
            ),
            "SmokeTest (binds board.Base)",
        ),
        (
            edit("board.py", "    constraints = Rules()\n", ""),
            "design.SmokeTest does not translate (jitx build exit 1)",
        ),
        (
            edit("board.py", "class Core(", "raise SystemExit(0)\n\n\nclass Core("),
            "FAIL  board.py does not import: SystemExit: 0",
        ),
        (
            edit(
                "design.py",
                "from board import TwoLayerSubstrate",
                "from board import Two",
            ),
            "FAIL  design.py does not import: ",
        ),
        (
            edit("design.py", "from board import", "from boards import"),
            "FAIL  design.py does not import: boards",
        ),
        (remove("design.py"), "design.py does not exist"),
        (
            edit("board.py", "class Core(", OPTIONAL_IMPORT + "class Core("),
            "FAIL  board.py does not import: NameError: name 'UNDEFINED_NAME'",
        ),
        (
            edit(
                "board.py",
                "class Core(",
                exits_at_import("ERROR  No module named 'jitx_rf_helpers'", 3)
                + "class Core(",
            ),
            "FAIL  the import pre-flight exited 3 on board.py without one of its own",
        ),
        (
            edit(
                "board.py",
                "class Core(",
                exits_at_import("No module named 'jitx_rf_helpers'", 7) + "class Core(",
            ),
            "FAIL  the import pre-flight gave no verdict on board.py (exit 7)",
        ),
    ],
    ids=[
        "a SampleDesign subclass",
        "no Design at all",
        "a substrate of its own",
        "a base class of the board's substrate",
        "a substrate that does not translate",
        "a board.py that exits at import",
        "a design.py importing a name board.py lacks",
        "a design.py importing a module that does not exist",
        "no design.py",
        "a board.py that prints environment wording, then fails",
        "a board.py that exits 3 with an ERROR line of its own",
        "a board.py that exits 7 in environment wording",
    ],
)
def test_each_way_a_design_misses_is_red(
    tmp_path: Path, change: Change, reason: str
) -> None:
    output = good_copy(tmp_path)
    change(output)
    done = run(output)
    assert done.returncode == 1, done.stdout + done.stderr
    assert reason in done.stdout
    for wording in ENVIRONMENT_WORDING:
        assert not re.search(wording, done.stdout + done.stderr, re.IGNORECASE), (
            wording,
            done.stdout,
        )


def test_an_interpreter_without_jitx_is_an_environment_error() -> None:
    """``-S`` leaves site-packages, and with it jitx, off the path."""
    done = run(CASE_A / "good_design", "-S")
    assert done.returncode == 3, done.stdout + done.stderr
    assert done.stdout.startswith("ERROR  design_check.py needs jitx"), done.stdout


def test_an_interpreter_without_jitx_sample_is_an_environment_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The listing child imports jitx.sample; without it nothing is graded."""
    monkeypatch.setitem(sys.modules, "jitx.sample", None)
    verdict = design_check.check(good_copy(tmp_path), design_check.TIMEOUT_S)
    assert verdict.problems == []
    assert [error.split(":")[0] for error in verdict.errors] == [
        "design_check.py needs jitx.sample"
    ], verdict.errors


def test_a_dependency_that_exits_at_import_is_an_environment_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A dependency that calls sys.exit while it imports is still the
    environment's, not a way out of the check."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "exits_at_import.py").write_text(
        'import sys\n\nsys.exit("exits_at_import: reinstall it")\n', encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(site))
    monkeypatch.delitem(sys.modules, "exits_at_import", raising=False)
    assert design_check.missing("design_check.py", ("exits_at_import",)) == (
        "design_check.py needs exits_at_import: SystemExit: "
        "exits_at_import: reinstall it"
    )
