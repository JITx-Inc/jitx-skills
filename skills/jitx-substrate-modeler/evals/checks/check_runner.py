"""What grade_pdf_report.py and grade_fenced_rf.py share: loading a
candidate's files, wrapping a substrate in a design, and running named checks.

Each check is a function that returns when the candidate passes it and raises
when it does not; the message it raises with is the reason printed. The
runner prints ``PASS  <check>`` or ``FAIL  <check>: <reason>`` per check and
then one summary line, and returns the exit code: 0 when every check passed,
1 when any failed. A run that goes past its time limit fails as a whole.

The Design and Board subclasses live here rather than in the grader scripts,
because JITX treats a Design subclass defined in ``__main__`` as a design file
to run when the interpreter exits.
"""

from __future__ import annotations

import hashlib
import importlib.util
import signal
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType, ModuleType
from typing import TypeVar

from jitx.board import Board
from jitx.circuit import Circuit
from jitx.design import Design
from jitx.shapes import Shape
from jitx.shapes.composites import rectangle
from jitx.substrate import Substrate

Check = tuple[str, Callable[[], None]]
T = TypeVar("T")


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


class TimeLimit(Exception):
    """The run went past its time limit."""


def _expire(signum: int, frame: FrameType | None) -> None:
    raise TimeLimit


@contextmanager
def time_limit(seconds: int) -> Iterator[None]:
    """Raise ``TimeLimit`` in the main thread after ``seconds``. POSIX only."""
    previous = signal.signal(signal.SIGALRM, _expire)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


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


def run(checks: list[Check], graded: str) -> int:
    """Run every check, print one line each and a summary, and return the
    exit code: 0 when all passed, 1 otherwise."""
    failed = 0
    for name, check in checks:
        try:
            check()
        except TimeLimit:
            raise
        except Exception as error:  # noqa: BLE001 - any error is the candidate's red
            failed += 1
            print(f"FAIL  {name}: {reason(error)}")
        else:
            print(f"PASS  {name}")
    if failed:
        print(f"FAIL  {failed} of {len(checks)} checks failed on {graded}")
        return 1
    print(f"PASS  all {len(checks)} checks passed on {graded}")
    return 0
