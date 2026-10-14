"""Import a candidate board file once, and say whose fault it is if that fails.

Usage:
  import_candidate.py BOARD_PY

grade_substrate.py runs this in a child interpreter before it grades. The
output is read by people and by eval harnesses, which treat Python's own
"No module named" and "ImportError: cannot import name" wording as an
environment problem rather than a skill failure. So the wording is chosen by
whose fault the failure is:

- The grader's own dependencies (jitx with jitx.proxy, jitxlib.physics,
  pytest) do not import, whatever they raise: an environment problem, exit 3,
  in Python's wording.
- An import fails inside a library rather than in the candidate's own files:
  an environment problem, exit 3, in Python's wording. The candidate's own
  files are those under the board's directory or under a directory the board
  adds to sys.path. A library is a file under a sys.path entry that was there
  before the board ran, or under the interpreter's stdlib, purelib or platlib,
  even where that sits under the board's directory: the deepest of these
  roots decides. importlib's own frames are machinery and are skipped, so a
  board's own ``importlib.import_module`` call is the board's.
- Anything else the candidate's import raises (a module or name that does not
  exist, an error at class definition, an error a library raises because of
  the candidate's call): a red, exit 1, as
  ``FAIL  candidate does not import: <what>``, without Python's wording.

Exit 0 when the candidate imports.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
import sysconfig
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
        except Exception as error:  # noqa: BLE001 - whatever it raises, not the candidate's
            return f"ERROR  the grader needs {name}: {type(error).__name__}: {error}"
    return None


IMPORTLIB = Path(importlib.__file__).resolve().parent
"""importlib's own directory: its frames are import machinery, not a library."""


def last_real_frame(error: BaseException) -> traceback.FrameSummary | None:
    """The innermost traceback frame in a real file, skipping the import
    machinery's frozen frames and importlib's own."""
    frames = [
        frame
        for frame in traceback.extract_tb(error.__traceback__)
        if not frame.filename.startswith("<")
        and not Path(frame.filename).resolve().is_relative_to(IMPORTLIB)
    ]
    return frames[-1] if frames else None


def resolved(entries: list[str]) -> set[Path]:
    return {Path(entry).resolve() for entry in entries if entry}


def library_roots(before: list[str]) -> set[Path]:
    """sys.path as it stood before the board ran, and the interpreter's own
    library directories."""
    paths = sysconfig.get_paths()
    return resolved(before) | resolved(
        [paths[key] for key in ("stdlib", "platstdlib", "purelib", "platlib")]
    )


def in_candidate(filename: str, own: set[Path], library: set[Path]) -> bool:
    """Whether a file is the candidate's own: the deepest root holding it is
    one of the candidate's, and a tie goes to the candidate."""
    path = Path(filename).resolve()
    holding = [root for root in own | library if path.is_relative_to(root)]
    if not holding:
        return False
    deepest = max(len(root.parts) for root in holding)
    return any(root in own for root in holding if len(root.parts) == deepest)


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
    before = list(sys.path)
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
        # The board's directory, and any directory the board put on sys.path.
        own = {board.parent} | (resolved(sys.path) - resolved(before))
        library = library_roots(before)
        theirs = frame is not None and not in_candidate(frame.filename, own, library)
        if isinstance(error, ImportError) and theirs:
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
