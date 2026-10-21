"""Import a candidate board file once, and say whose fault it is if that fails.

Usage:
  import_candidate.py BOARD_PY

grade_substrate.py runs this in a child interpreter before it grades, so a
board that does not import is graded as the candidate's red or reported as an
environment problem, and the grader never runs on it. POSIX only when
grade_substrate.py starts it: it then ends itself through parent_watch.py,
which uses process groups. Run by hand, with GRADE_SUBSTRATE_PID unset, it
makes no POSIX call.

Exit codes:
  0  the candidate imports
  1  a red, the candidate's own import failed:
     ``FAIL  candidate does not import: <what>``, without Python's wording
  2  usage error
  3  an environment problem, as an ``ERROR  `` line in Python's own wording:
     a module or name the grader imports (``NEEDED``) does not import, or an
     import fails inside a library rather than in the candidate's own files

A red goes through ``scrub``, so a candidate's own message cannot carry the
wording an eval harness reads as an environment problem. Each verdict is one
line, printed last; ``verdict`` is how every grader reads this script's exit
code and that line. Once the candidate has run, the verdict goes to a copy of
stdout taken before it ran, after both streams are flushed, and the process
then ends at once, so a replaced ``sys.stdout``, an exit handler or a thread
the candidate started cannot hide the line or print after it. That guards
against a candidate's accidents only: a candidate that prints one of the
``ERROR  `` lines itself and exits 3 reads as an environment problem.
``scrub`` and the
wording it rewords live here, with no jitx import, so that every grader and
check that quotes a candidate can use them, including the ones that must
report a missing jitx themselves.
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

ENVIRONMENT_WORDING = [
    r"No module named",
    r'Import "[^"]+" could not be resolved \(reportMissingImports\)',
    r"ImportError: cannot import name",
    r'"[^"]+" is unknown import symbol',
    r"command not found|: not found\b",
    r"No such file or directory: '(?:[^']*/)?(?:python[0-9.]*|pyright|jitx)'",
    r"coroutine '.*' was never awaited",
    r"launcher exited .* before announcing itself",
    r"Error occurred when attempting to open the user statistics file",
    r"Connection refused|WebSocket|ws://.*refused",
]
"""Wording an eval harness reads, case-insensitively, as "the environment
could not run this" rather than as a red: a copy of the patterns in the
harness's ENV_PATTERNS (run_cases.py), which a test compares when it can
import run_cases. A red must match none of it."""

PARAPHRASES = [
    (r"No module named", "no module called"),
    (
        r"could not be resolved \(reportMissingImports\)",
        "is unresolved (reportMissingImports)",
    ),
    (r"ImportError: cannot import name", "ImportError, cannot import name"),
    (r"is unknown import symbol", "is an unknown symbol to import"),
    (r"command not found", "command missing"),
    (r": not found\b", ": missing"),
    (r"No such file or directory: '", "no such file or folder: '"),
    (r"was never awaited", "was not awaited"),
    (r"before announcing itself", "before it announced itself"),
    (
        r"Error occurred when attempting to open the user statistics file",
        "the user statistics file did not open",
    ),
    (r"Connection refused", "connection turned away"),
    (r"WebSocket", "web socket"),
    (r"ws://", "ws: //"),
]
"""Each phrase in ENVIRONMENT_WORDING, and a rewording that keeps its sense."""


def scrub(text: str) -> str:
    """``text`` with every phrase an eval harness would read as an
    environment problem reworded, so a candidate's red stays a red."""
    for pattern, paraphrase in PARAPHRASES:
        text = re.sub(pattern, paraphrase, text, flags=re.IGNORECASE)
    return text


NEEDED: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("jitx", ()),
    ("jitx.proxy", ("typeof",)),
    ("jitxlib.physics", ("phase_velocity",)),
    ("pytest", ()),
    ("jitx._instantiation", ("instantiation",)),
    ("jitx._translate.design", ("package_design",)),
    ("jitx.board", ("Board",)),
    ("jitx.circuit", ("Circuit",)),
    ("jitx.design", ("Design",)),
    ("jitx.inspect", ("decompose",)),
    ("jitx.shapes", ("Shape",)),
    ("jitx.shapes.composites", ("rectangle",)),
    ("jitx.si", ("DifferentialRoutingStructure", "RoutingStructure", "_RefLayer")),
    ("jitx.stackup", ("Conductor", "Dielectric", "Material")),
    ("jitx.substrate", ("FabricationConstraints", "Substrate")),
    ("jitx.test", ("TestCase",)),
    ("jitx.units", ("ohm",)),
)
"""(module, names) the grader itself imports: pytest, and every jitx and
jitxlib import of substrate_grader.py, which a test keeps in step. No
candidate can fix these, and checking them here, before any candidate code
runs, reports a missing one in Python's own wording, where a failure inside
the grader's pytest run would be printed scrubbed, as a red. Older jitx
releases have no ``jitx.proxy``, and private modules such as
``jitx._translate.design`` can move between releases; either is reported
here, not as a red."""

NEEDS = "ERROR  the grader needs"
LIBRARY = "ERROR  a library the candidate imports does not import:"
"""How this script's two environment lines start (exit 3). A caller that
reads exit 3 can tell them from a candidate that exits 3 on its own."""

DOES_NOT_IMPORT = "FAIL  candidate does not import:"
"""How this script's red line starts (exit 1)."""


def one_line(text: str) -> str:
    """``text`` with its whitespace, newlines included, collapsed, so a
    multi-line error message stays on the line that carries it."""
    return " ".join(text.split())


def verdict(code: int, stdout: str, stderr: str, name: str) -> tuple[bool, str]:
    """What a run of this script on the file ``name`` that did not exit 0
    means, as every grader reads it: ``(True, line)`` for an environment
    problem, only when it exited 3 and its last stdout line is one of its two
    environment lines, kept as it is; otherwise ``(False, line)``, the
    candidate's red, a ``FAIL  `` line with everything quoted from the
    candidate scrubbed. A candidate that exits 3 itself, exits with another
    code, or crashes the import is a red."""
    said = stdout.strip().splitlines()
    last = said[-1] if said else ""
    if code == 3 and last.startswith((NEEDS, LIBRARY)):
        return True, last
    if code == 1 and last.startswith(DOES_NOT_IMPORT):
        return False, scrub(last)
    if code == 3:
        head = (
            f"FAIL  the import pre-flight exited 3 on {name} without one of its "
            "own environment lines; a candidate that exits 3 is a red:"
        )
    else:
        head = f"FAIL  the import pre-flight gave no verdict on {name} (exit {code}):"
    tail = [*said[-3:], *stderr.strip().splitlines()[-3:]]
    return False, head + "".join(f"\n      {scrub(line)}" for line in tail)


def missing_dependency() -> str | None:
    """Python's own report for the first grader dependency that does not
    import, or None when all of them do."""
    for module, names in NEEDED:
        try:
            imported = importlib.import_module(module)
        except BaseException as error:  # noqa: BLE001 - SystemExit too, not the candidate's
            return f"{NEEDS} {module}: {type(error).__name__}: {one_line(str(error))}"
        for name in names:
            if not hasattr(imported, name):
                return (
                    f"{NEEDS} {module}.{name}: ImportError: cannot import name "
                    f"{name!r} from {module!r}"
                )
    return None


IMPORTLIB = Path(importlib.__file__).resolve().parent
"""importlib's own directory: its frames are import machinery, not a library."""


def last_real_frame(error: BaseException) -> traceback.FrameSummary | None:
    """The innermost traceback frame in a real file: one with an absolute
    filename, so pseudo-filenames such as ``<frozen ...>`` and ``<string>``
    and relative build-time names such as ``pkg/_mod.pyx`` are skipped, and
    so are importlib's own frames."""
    # This frame decides whose fault a failure is. Skipping importlib's frames
    # as machinery makes a board's own ``importlib.import_module`` call the
    # board's.
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
    # Testing the resolved form too keeps a symlink inside a library root a
    # library file. A library root wins even where it sits under the board's
    # directory, as an editable project can. Known misreads: a library
    # installed some other way (a custom import hook with no direct_url.json,
    # a zip outside sys.path) reads as the candidate's, and a file the board
    # loads by path from inside an editable project's directory, but outside
    # the board's own directory, grades as the environment's.
    paths = forms(filename)
    holding = [
        root
        for root in own | library
        if any(path.is_relative_to(root) for path in paths)
    ]
    if not holding:
        # No library root holds it. The roots cover how an installed library
        # is normally found, so it was most likely loaded by the board from a
        # path of its own choosing.
        return True

    def depth(root: Path) -> int:
        return len(root.resolve().parts)

    deepest = max(depth(root) for root in holding)
    return any(root in own for root in holding if depth(root) == deepest)


def describe(error: BaseException) -> str:
    """What failed, in words that do not repeat Python's own import wording."""
    # People and eval harnesses read this output, and the harnesses treat
    # Python's "No module named" and "ImportError: cannot import name" wording
    # as an environment problem rather than a skill failure. So a red never
    # carries that wording, and an environment problem (exit 3) keeps it.
    if isinstance(error, ModuleNotFoundError) and error.name:
        return error.name
    if isinstance(error, ImportError) and error.msg:
        # "cannot import name 'x' from 'm' (/path/to/m.py)": drop the path.
        return re.sub(r"\s*\([^()]*\)$", "", error.msg)
    return f"{type(error).__name__}: {error}"


GRADER_ENVIRONMENT = "GRADE_SUBSTRATE_ENVIRONMENT"
"""The setting that names a file for substrate_grader.py's own environment
line. grade_substrate.py sets it, and prints the line it finds there raw."""


def grader_cannot_import(error: BaseException) -> None:
    """Record, for grade_substrate.py, that substrate_grader.py's own imports
    failed in its pytest process. They run before any candidate code there,
    so the failure is the environment's: the line names the first grader
    dependency that does not import, in Python's own wording, or the error
    itself when each of them imports on a second try. It is written to the
    file ``GRADER_ENVIRONMENT`` names, when that is set, because grade_substrate.py
    prints the pytest output scrubbed and reads an environment problem only
    from there. The caller re-raises ``error``."""
    line = missing_dependency() or (
        f"{NEEDS} {type(error).__name__}: {one_line(str(error))}"
    )
    target = os.environ.get(GRADER_ENVIRONMENT, "").strip()
    if target:
        Path(target).write_text(f"{line}\n", encoding="utf-8")


_verdict_channel: list[int] = []
"""A copy of stdout, taken before the candidate runs, for the verdict line."""


def flush_all() -> None:
    """Flush stdout and stderr, as the candidate may have replaced them and as
    Python started them, so what the candidate printed comes before the
    verdict line."""
    for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
        try:
            if stream is not None:
                stream.flush()
        except Exception:  # noqa: BLE001 - a replaced stream may not flush
            pass


def say(line: str) -> None:
    """Write the verdict line, after whatever the candidate printed and on a
    line of its own, to the copy of stdout taken before the candidate ran, so
    a candidate that replaces ``sys.stdout`` cannot swallow it."""
    flush_all()
    data = f"\n{line}\n".encode()
    channel = _verdict_channel[0] if _verdict_channel else sys.stdout.fileno()
    while data:
        data = data[os.write(channel, data) :]


def finish(code: int) -> None:
    """End this process with ``code`` at once, once the verdict is written,
    so no exit handler or thread the candidate started runs after it."""
    flush_all()
    os._exit(code)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    watch_parent()
    problem = missing_dependency()
    if problem is not None:
        print(problem)
        return 3
    _verdict_channel.append(os.dup(sys.stdout.fileno()))
    board = Path(argv[1]).resolve()
    before = list(sys.path)
    editable = editable_projects()
    sys.path.insert(0, str(board.parent))
    spec = importlib.util.spec_from_file_location("_candidate_preflight", board)
    if spec is None or spec.loader is None:
        print(f"{DOES_NOT_IMPORT} {board.name} is not a Python file")
        return 1
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs, as a normal import would be: dataclasses
    # under string annotations look the module up in sys.modules.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as error:  # noqa: BLE001 - any failure is reported
        # An ImportError whose innermost real frame is in a library is the
        # environment's. Anything else is a red: a module or name that does not
        # exist, an error at class definition, or an error a library raises
        # because of the candidate's call.
        frame = last_real_frame(error)
        # The board's directory, and any directory the board put on sys.path.
        own = {board.parent} | (roots(sys.path) - roots(before))
        library = library_roots(before, editable)
        theirs = frame is not None and not in_candidate(frame.filename, own, library)
        if isinstance(error, ImportError) and theirs:
            where = f" (in {frame.filename}:{frame.lineno})" if frame else ""
            say(f"{LIBRARY} {type(error).__name__}: {one_line(str(error))}{where}")
            return 3
        own = [
            line.lineno
            for line in traceback.extract_tb(error.__traceback__)
            if not line.filename.startswith("<")
            and Path(line.filename).resolve() == board
        ]
        where = f" (at {board.name}:{own[-1]})" if own else ""
        say(f"{DOES_NOT_IMPORT} {scrub(one_line(describe(error)))}{where}")
        return 1
    return 0


if __name__ == "__main__":
    finish(main(sys.argv))
