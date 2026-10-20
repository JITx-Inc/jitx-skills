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
  (``L2_IDX: 3``) or keyword (``loss=3``) broken the same way, over two lines
  or more;
- a detached label: a label after code that is nothing but closing brackets
  and commas, such as ``}),  # skill default: ...`` after a wrapped call, or
  after code that ends in an opening bracket, such as
  ``.reference(  # skill default: ...``, where the values follow on other lines,
  when no line inside that bracket pair carries a label of its own.

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
import itertools
import re
import shutil
import subprocess
import sys
from pathlib import Path

USAGE = "usage: python <this skill's directory>/scripts/check_labels.py <substrate.py>"
LABEL = re.compile(r"\bskill[- ]defaults?\b", re.IGNORECASE)
NEGATED = re.compile(r"\b(?:no|not(?:\s+(?:a|the|any))?)\s+$", re.IGNORECASE)
CLOSERS = re.compile(r"[\s)\]},]+")
OPENS = re.compile(r"[(\[{]\s*$")
# A dict entry (any key) or a keyword argument whose value goes on: the head
# ends in a value, not in a comma or an opening bracket.
SPLIT_HEAD = re.compile(r"^\s*(?:[^#=\s][^#=]*?:|\w+=)\s*[^#]*[^\s#,(\[{]\s*$")
CONTINUATION = re.compile(r"^\s*(?:\*\*|//|[*/+-])\s")
STRING = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'")


def is_label(comment: str) -> bool:
    """The comment names the skill default, other than to deny it."""
    return any(
        not NEGATED.search(comment[: match.start()])
        for match in LABEL.finditer(comment)
    )


def ruff_command() -> list[str] | None:
    """This interpreter's ruff, else the one on PATH, else None."""
    if importlib.util.find_spec("ruff") is not None:
        return [sys.executable, "-m", "ruff"]
    found = shutil.which("ruff")
    return [found] if found else None


def formatted(path: Path) -> str | None:
    """The file as `ruff format` would leave it, or None when ruff cannot run."""
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
    return proc.stdout


def trailing_label(line: str) -> bool:
    """A ``skill default`` label trailing code, not a docstring or comment line."""
    code, _, comment = line.partition("#")
    return bool(code.strip()) and is_label(comment)


def brackets(code: str) -> tuple[int, int]:
    """(closed, opened): brackets this code closes from earlier lines, and
    leaves open for later ones. Brackets inside string literals do not count."""
    closed = opened = 0
    for char in STRING.sub("", code):
        if char in "([{":
            opened += 1
        elif char in ")]}":
            if opened:
                opened -= 1
            else:
                closed += 1
    return closed, opened


def inside(lines: list[str], index: int) -> list[str]:
    """The lines inside the bracket pair the line at ``index`` opens (when its
    code ends in an opening bracket) or closes (when it is only closers)."""
    code = lines[index].partition("#")[0]
    closed, opened = brackets(code)
    found: list[str] = []
    if opened:
        depth = opened
        for line in lines[index + 1 :]:
            line_closed, line_opened = brackets(line.partition("#")[0])
            depth -= line_closed
            if depth <= 0:
                break
            depth += line_opened
            found.append(line)
    else:
        depth = closed
        for line in reversed(lines[:index]):
            line_closed, line_opened = brackets(line.partition("#")[0])
            depth -= line_opened
            if depth <= 0:
                break
            depth += line_closed
            found.append(line)
    return found


def split_entries(text: str) -> list[tuple[int, str]]:
    """Each (line number, description) where a label is split or detached."""
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    for number, head in enumerate(lines, start=1):
        if not SPLIT_HEAD.match(head):
            continue
        # ruff breaks a long derivation before each operator, so the label sits
        # on the last of one or more continuation lines.
        tail = list(
            itertools.takewhile(
                CONTINUATION.match, itertools.islice(lines, number, None)
            )
        )
        if tail and is_label(tail[-1].partition("#")[2]):
            found.append((number, f"split: {head.strip()!r} / {tail[-1].strip()!r}"))
    for number, line in enumerate(lines, start=1):
        code, _, comment = line.partition("#")
        if (
            is_label(comment)
            and code.strip()
            and (CLOSERS.fullmatch(code) or OPENS.search(code))
            and not any(trailing_label(entry) for entry in inside(lines, number - 1))
        ):
            found.append((number, f"detached: {line.strip()!r}"))
    return sorted(found)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"check_labels: no file at {path}", file=sys.stderr)
        return 2
    text = formatted(path)
    if text is None:
        return 2
    labels = sum(1 for line in text.splitlines() if trailing_label(line))
    if labels == 0:
        print(
            "check_labels: no skill-default label, nothing to check "
            "(a value no source row backs needs one)"
        )
        return 0
    found = split_entries(text)
    for number, description in found:
        print(f"line {number}: {description}")
    if found:
        print(f"check_labels: {labels} labeled lines, {len(found)} split or detached")
        return 1
    print(f"check_labels: {labels} labeled lines, none split from their label")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
