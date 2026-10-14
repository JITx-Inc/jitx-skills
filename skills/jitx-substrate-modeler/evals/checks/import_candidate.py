"""Import a candidate board file once, and say whose fault it is if that fails.

Usage:
  import_candidate.py BOARD_PY

grade_substrate.py runs this in a child interpreter before it grades. The
output is read by people and by eval harnesses, which treat Python's own
"No module named" and "ImportError: cannot import name" wording as an
environment problem rather than a skill failure. So the wording is chosen by
whose fault the failure is:

- The grader's own dependencies (jitx with jitx.proxy, jitxlib.physics,
  pytest) do not import: an environment problem, exit 3, in Python's wording.
- An import fails inside a library rather than in the candidate's own files
  (the board and the files beside it): an environment problem, exit 3, in
  Python's wording.
- Anything else the candidate's import raises (a module or name that does not
  exist, an error at class definition): a red, exit 1, as
  ``FAIL  candidate does not import: <what>``, without Python's wording.

Exit 0 when the candidate imports.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
import traceback
from pathlib import Path

NEEDED = ("jitx", "jitx.proxy", "jitxlib.physics", "pytest")
"""What the grader itself imports. No candidate can fix these. Older jitx
releases have no ``jitx.proxy``; one of those is reported here, not as a red."""


def missing_dependency() -> str | None:
    """Python's own report for the first grader dependency that does not
    import, or None when all of them do."""
    for name in NEEDED:
        try:
            importlib.import_module(name)
        except ImportError as error:
            return f"ERROR  the grader needs {name}: {type(error).__name__}: {error}"
    return None


def last_real_frame(error: BaseException) -> traceback.FrameSummary | None:
    """The innermost traceback frame in a real file, skipping the import
    machinery's frozen frames."""
    frames = [
        frame
        for frame in traceback.extract_tb(error.__traceback__)
        if not frame.filename.startswith("<")
    ]
    return frames[-1] if frames else None


def describe(error: BaseException) -> str:
    """What failed, in words that do not repeat Python's own import wording."""
    if isinstance(error, ModuleNotFoundError) and error.name:
        return error.name
    if isinstance(error, ImportError) and error.msg:
        # "cannot import name 'x' from 'm' (/path/to/m.py)": drop the path.
        return re.sub(r"\s*\([^()]*\)$", "", error.msg)
    return f"{type(error).__name__}: {error}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    problem = missing_dependency()
    if problem is not None:
        print(problem)
        return 3
    board = Path(argv[1]).resolve()
    sys.path.insert(0, str(board.parent))
    spec = importlib.util.spec_from_file_location("_candidate_preflight", board)
    if spec is None or spec.loader is None:
        print(f"FAIL  candidate does not import: {board.name} is not a Python file")
        return 1
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs, as a normal import would be: dataclasses
    # under string annotations look the module up in sys.modules.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as error:  # noqa: BLE001 - any failure is reported
        frame = last_real_frame(error)
        # The candidate's own files: the board and anything beside it.
        in_candidate = frame is not None and Path(
            frame.filename
        ).resolve().is_relative_to(board.parent)
        if isinstance(error, ImportError) and not in_candidate:
            where = f" (in {frame.filename}:{frame.lineno})" if frame else ""
            print(
                "ERROR  a library the candidate imports does not import: "
                f"{type(error).__name__}: {error}{where}"
            )
            return 3
        own = [
            line.lineno
            for line in traceback.extract_tb(error.__traceback__)
            if not line.filename.startswith("<")
            and Path(line.filename).resolve() == board
        ]
        where = f" (at {board.name}:{own[-1]})" if own else ""
        print(f"FAIL  candidate does not import: {describe(error)}{where}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
