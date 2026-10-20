"""Fail when ``ruff format`` would split a labeled derivation from its label.

Usage: ``python <this skill's directory>/scripts/check_labels.py <substrate.py>``

Run it with the project's own Python interpreter, the one its ``ruff`` is
installed in, on the file that holds the substrate, from any directory. It
formats a copy of the file in memory, with the ruff configuration that applies
to the file's own directory, so a project that sets ``line-length`` is checked
at that length. A label is a comment that says ``skill default``,
``skill-default`` or ``skill defaults`` (any case) anywhere but directly after
``no``, ``not``, ``not a``, ``not the`` or ``not any``. It reports two shapes:

- a derivation split from its label: ``1: 3 * 0.080,  # skill default: ...``
  broken into ``1: 3`` and ``* 0.080,  # skill default: ...``, or a named key
  (``L2_IDX: 3``), keyword (``loss=3``) or list element (``3``) broken the
  same way, over two lines or more;
- a detached label: a label after code that is nothing but closing brackets
  and commas, such as ``}),  # skill default: ...`` after a wrapped call, or
  after code that ends in an opening bracket, such as
  ``.reference(  # skill default: ...``, where the values follow on other lines.
  A label the author put on such a line in the source is reported only when no
  line inside that bracket pair carries a label of its own; a label ruff moves
  there from an entry, such as ``3: 3 * 0.127}),  # skill default: ...``
  becoming ``),  # skill default: ...``, is always reported.

A split whose comment is not a label, such as a unit or source note, is not
reported.

Exit 0 clean, with one summary line to quote: ``check_labels: <n> labeled
lines, none split from their label``, or, for a file with no ``skill default``
label, a line saying there was nothing to check (a width taken from a source
row needs no label; a value no source row backs still does). Exit 1 found: each
finding is printed, then a summary line. Exit 2 could not run: no file at the
path, the file is not UTF-8, ruff neither imports in this interpreter nor is on
``PATH``, or the file does not parse.
"""

import importlib.util
import io
import itertools
import re
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

USAGE = "usage: python <this skill's directory>/scripts/check_labels.py <substrate.py>"
LABEL = re.compile(r"\bskill[- ]defaults?\b", re.IGNORECASE)
NEGATED = re.compile(r"\b(?:no|not(?:\s+(?:a|the|any))?)\s+$", re.IGNORECASE)
CLOSERS = re.compile(r"[\s)\]},]+")
OPENS = re.compile(r"[(\[{]\s*$")
# A line of code whose value goes on to the next: it ends in a value, not in a
# comma or an opening bracket. Outside a string, ruff starts a line with a
# binary operator only when it breaks an expression, so CONTINUATION on the
# next line is what marks a split. String contents are masked before either
# pattern sees a line.
HEAD_END = re.compile(r"[^\s,(\[{]\s*$")
CONTINUATION = re.compile(r"^\s*(?:\*\*|//|[*/+-])\s")
# One line as (code, comment): the code before any comment, with every string
# literal's characters, docstrings and f-strings included, replaced by "_";
# and the comment token with its "#", or "" when the line has none.
Line = tuple[str, str]


def is_label(comment: str) -> bool:
    """The comment names the skill default, other than to deny it."""
    return any(
        not NEGATED.search(comment[: match.start()])
        for match in LABEL.finditer(comment)
    )


def scan(text: str) -> list[Line]:
    """Each line of ``text`` as (code, comment), from Python's tokenizer, so a
    ``#`` or an operator inside a string is never a comment or code. Lines are
    tokenized with their indentation removed, which the tokenizer would
    otherwise check, so a fragment of a file reads the same as the whole file;
    one that leaves a string open is read up to where the tokenizer stops."""
    lines = text.splitlines()
    indent = [len(line) - len(line.lstrip()) for line in lines]
    rows = [list(line) for line in lines]
    comments = [""] * len(rows)

    def mask(start: tuple[int, int], end: tuple[int, int]) -> None:
        for row in range(start[0], min(end[0], len(rows)) + 1):
            chars = rows[row - 1]
            first = start[1] + indent[row - 1] if row == start[0] else 0
            last = end[1] + indent[row - 1] if row == end[0] else len(chars)
            chars[first:last] = "_" * len(chars[first:last])

    dedented = io.StringIO("".join(line.lstrip() + "\n" for line in lines))
    opened: list[tuple[int, int]] = []
    try:
        for token in tokenize.generate_tokens(dedented.readline):
            name = tokenize.tok_name[token.type]
            row, column = token.start
            if name == "COMMENT":
                comments[row - 1] = token.string
                del rows[row - 1][column + indent[row - 1] :]
            elif name == "STRING" and not opened:
                mask(token.start, token.end)
            elif name.endswith("STRING_START"):
                opened.append(token.start)
            elif name.endswith("STRING_END") and opened:
                begun = opened.pop()
                if not opened:
                    mask(begun, token.end)
    except (tokenize.TokenError, SyntaxError):
        pass
    return [("".join(chars), comment) for chars, comment in zip(rows, comments)]


def ruff_command() -> list[str] | None:
    """This interpreter's ruff, else the one on PATH, else None."""
    if importlib.util.find_spec("ruff") is not None:
        return [sys.executable, "-m", "ruff"]
    found = shutil.which("ruff")
    return [found] if found else None


def formatted(path: Path) -> tuple[str, str] | None:
    """(source, the file as `ruff format` would leave it), or None when ruff
    cannot run."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"check_labels: could not read {path}: {exc}", file=sys.stderr)
        return None
    ruff = ruff_command()
    if ruff is None:
        print(
            "check_labels: ruff neither imports in this interpreter nor is on PATH",
            file=sys.stderr,
        )
        return None
    try:
        proc = subprocess.run(
            [*ruff, "format", "--stdin-filename", str(path.resolve()), "-"],
            check=False,
            input=source,
            cwd=path.resolve().parent,
            capture_output=True,
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"could not run ruff: {exc}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(proc.stderr.strip() or "ruff format failed", file=sys.stderr)
        return None
    return source, proc.stdout


def trailing_label(line: Line) -> bool:
    """A ``skill default`` label trailing code, not a docstring or comment line."""
    code, comment = line
    return bool(code.strip()) and is_label(comment)


def bracket_label(line: Line) -> bool:
    """A label after code that only closes brackets or ends in an opening one."""
    code, comment = line
    return (
        is_label(comment)
        and bool(code.strip())
        and bool(CLOSERS.fullmatch(code) or OPENS.search(code))
    )


def moved_labels(text: list[Line], source: list[Line]) -> set[int]:
    """Line numbers in ``text`` of bracket-line labels that were not on a
    bracket line in ``source``: labels ruff moved there. ruff keeps comments
    in order, so the k-th copy of a comment in ``text`` is its k-th copy in
    ``source``."""
    placed: dict[str, list[bool]] = {}
    for line in source:
        comment = line[1]
        if is_label(comment):
            placed.setdefault(comment.strip(), []).append(bracket_label(line))
    seen: dict[str, int] = {}
    moved: set[int] = set()
    for number, line in enumerate(text, start=1):
        comment = line[1].strip()
        if not is_label(comment):
            continue
        k = seen.get(comment, 0)
        seen[comment] = k + 1
        before = placed.get(comment, [])
        if bracket_label(line) and not (k < len(before) and before[k]):
            moved.add(number)
    return moved


def brackets(code: str) -> tuple[int, int]:
    """(closed, opened): brackets this code closes from earlier lines, and
    leaves open for later ones. The code has its strings masked already."""
    closed = opened = 0
    for char in code:
        if char in "([{":
            opened += 1
        elif char in ")]}":
            if opened:
                opened -= 1
            else:
                closed += 1
    return closed, opened


def inside(lines: list[Line], index: int) -> list[Line]:
    """The lines inside the bracket pair the line at ``index`` opens (when its
    code ends in an opening bracket) or closes (when it is only closers)."""
    closed, opened = brackets(lines[index][0])
    found: list[Line] = []
    if opened:
        depth = opened
        for line in lines[index + 1 :]:
            line_closed, line_opened = brackets(line[0])
            depth -= line_closed
            if depth <= 0:
                break
            depth += line_opened
            found.append(line)
    else:
        depth = closed
        for line in reversed(lines[:index]):
            line_closed, line_opened = brackets(line[0])
            depth -= line_opened
            if depth <= 0:
                break
            depth += line_closed
            found.append(line)
    return found


def split_entries(text: str, source: str | None = None) -> list[tuple[int, str]]:
    """Each (line number, description) where a label in the formatted ``text``
    is split or detached; with ``source``, a label ruff moved onto a bracket
    line is detached whatever the bracket holds."""
    raw = text.splitlines()
    lines = scan(text)
    moved = set() if source is None else moved_labels(lines, scan(source))
    found: list[tuple[int, str]] = []
    for number, (code, comment) in enumerate(lines, start=1):
        if (
            comment
            or not code.strip()
            or CONTINUATION.match(code)
            or not HEAD_END.search(code)
        ):
            continue
        # ruff breaks a long derivation before each operator, so the label sits
        # on the last of one or more continuation lines.
        tail = list(
            itertools.takewhile(
                lambda line: CONTINUATION.match(line[0]),
                itertools.islice(lines, number, None),
            )
        )
        if tail and is_label(tail[-1][1]):
            last = raw[number + len(tail) - 1].strip()
            found.append((number, f"split: {raw[number - 1].strip()!r} / {last!r}"))
    for number, line in enumerate(lines, start=1):
        if bracket_label(line) and (
            number in moved
            or not any(trailing_label(entry) for entry in inside(lines, number - 1))
        ):
            found.append((number, f"detached: {raw[number - 1].strip()!r}"))
    return sorted(found)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"check_labels: no file at {path}", file=sys.stderr)
        return 2
    read = formatted(path)
    if read is None:
        return 2
    source, text = read
    labels = sum(1 for line in scan(text) if trailing_label(line))
    if labels == 0:
        print(
            "check_labels: no skill-default label, nothing to check "
            "(a value no source row backs needs one)"
        )
        return 0
    found = split_entries(text, source)
    for number, description in found:
        print(f"line {number}: {description}")
    if found:
        print(f"check_labels: {labels} labeled lines, {len(found)} split or detached")
        return 1
    print(f"check_labels: {labels} labeled lines, none split from their label")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
