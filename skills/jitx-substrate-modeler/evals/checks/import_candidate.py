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
  an environment problem, exit 3, in Python's wording. A library is a file
  under a library root: a sys.path entry that was there before the board ran,
  the interpreter's stdlib, purelib or platlib, or the project directory of
  an editable install (pip's direct_url.json), even where that sits under the
  board's directory. The candidate's own roots are the board's directory and
  any directory the board adds to sys.path. The deepest root holding the file
  decides, a tie going to the candidate. A file is tested both as named and
  with symlinks resolved, so a symlink inside a library root stays library.
  A file under none of these roots counts as the candidate's: those roots
  cover how an installed library is normally found, so a file outside them
  is most likely one the board loaded by path. A library installed some
  other way (a custom import hook with no direct_url.json, a zip outside
  sys.path) would be misread as the candidate's, and a file the board loads
  by path from inside an editable project's directory, but outside the
  board's own directory, grades as the environment's.
  The innermost frame in a real file decides. A real file has an absolute
  filename: pseudo-filenames (starting with "<", such as a frozen module or
  exec's "<string>") and relative build-time names (such as a Cython module's
  ``pkg/_mod.pyx``) are skipped. importlib's own frames are machinery and are
  skipped too, so a board's own ``importlib.import_module`` call is the
  board's.
- Anything else the candidate's import raises (a module or name that does not
  exist, an error at class definition, an error a library raises because of
  the candidate's call): a red, exit 1, as
  ``FAIL  candidate does not import: <what>``, without Python's wording.

Exit 0 when the candidate imports.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import json
import os
import re
import sys
import sysconfig
import traceback
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from parent_watch import watch_parent

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
    """The innermost traceback frame in a real file: one with an absolute
    filename, so pseudo-filenames such as ``<frozen ...>`` and ``<string>``
    and relative build-time names such as ``pkg/_mod.pyx`` are skipped, and
    so are importlib's own frames."""
    frames = [
        frame
        for frame in traceback.extract_tb(error.__traceback__)
        if os.path.isabs(frame.filename)
        and not Path(frame.filename).resolve().is_relative_to(IMPORTLIB)
    ]
    return frames[-1] if frames else None


def forms(entry: str) -> set[Path]:
    """A path as named (made absolute) and with its symlinks resolved."""
    return {Path(os.path.abspath(entry)), Path(entry).resolve()}


def roots(entries: list[str]) -> set[Path]:
    return {form for entry in entries if entry for form in forms(entry)}


def editable_projects() -> list[str]:
    """The project directory of each installed editable distribution, from
    the direct_url.json pip records. An editable install reached through an
    import hook keeps its files there, on no sys.path entry.

    A record that cannot be read or parsed, or whose path is not absolute,
    cannot be resolved, or is the filesystem root, is skipped: a broken
    install record must never stop a board from being graded."""
    found: list[str] = []
    try:
        distributions = list(importlib.metadata.distributions())
    except (ValueError, OSError):
        return found
    for distribution in distributions:
        try:
            text = distribution.read_text("direct_url.json")
            if not text:
                continue
            record: object = json.loads(text)
        except (ValueError, OSError):
            # UnicodeDecodeError and json's errors are ValueErrors.
            continue
        if not isinstance(record, dict):
            continue
        url = record.get("url")
        info = record.get("dir_info")
        if not (
            isinstance(url, str)
            and url.startswith("file:")
            and isinstance(info, dict)
            and info.get("editable") is True
        ):
            continue
        path = url2pathname(urlparse(url).path)
        if not os.path.isabs(path):
            continue
        try:
            project = Path(path).resolve()
        except (ValueError, OSError):
            continue
        if project.parent == project:
            continue
        found.append(path)
    return found


def library_roots(before: list[str], editable: list[str]) -> set[Path]:
    """sys.path as it stood before the board ran, the interpreter's own
    library directories, and the editable installs' project directories."""
    paths = sysconfig.get_paths()
    return (
        roots(before)
        | roots([paths[key] for key in ("stdlib", "platstdlib", "purelib", "platlib")])
        | roots(editable)
    )


def in_candidate(filename: str, own: set[Path], library: set[Path]) -> bool:
    """Whether a file is the candidate's own: the deepest root holding it, as
    named or resolved, is one of the candidate's (a tie goes to the
    candidate), or no root holds it at all."""
    paths = forms(filename)
    holding = [
        root
        for root in own | library
        if any(path.is_relative_to(root) for path in paths)
    ]
    if not holding:
        # No library root holds it, so it was most likely loaded by the board
        # from a path of its own choosing.
        return True

    def depth(root: Path) -> int:
        return len(root.resolve().parts)

    deepest = max(depth(root) for root in holding)
    return any(root in own for root in holding if depth(root) == deepest)


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
    watch_parent()
    problem = missing_dependency()
    if problem is not None:
        print(problem)
        return 3
    board = Path(argv[1]).resolve()
    before = list(sys.path)
    editable = editable_projects()
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
        own = {board.parent} | (roots(sys.path) - roots(before))
        library = library_roots(before, editable)
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
