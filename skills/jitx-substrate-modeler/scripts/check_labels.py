"""Fail when ``ruff format`` would split a labeled derivation from its label.

Usage: ``python <this skill's directory>/scripts/check_labels.py <substrate.py>``

Run it with the project's own Python interpreter, the one its ``ruff`` is
installed in, on the file that holds the substrate, from any directory. It
formats a copy of the file in memory, with the ruff configuration that applies
to the file's own directory, so a project that sets ``line-length`` is checked
at that length. It reports two shapes:

- a derivation split from its label: ``1: 3 * 0.080,  # skill default: ...``
  or ``loss=3 * 0.006,  # skill default: ...`` broken into ``1: 3`` and
  ``* 0.080,  # skill default: ...``;
- a detached label: a ``skill default`` comment after code that is nothing
  but closing brackets and commas, such as ``}),  # skill default: ...``
  after a wrapped call, or after code that ends in an opening bracket, such as
  ``.reference(  # skill default: ...``, where the values follow on other lines.

Exit 0 clean, with one summary line to quote: ``check_labels: <n> labeled
lines, none split from their label``, or, for a file with no ``skill default``
label, a line saying there was nothing to check (a width taken from a source
row needs no label; a value no source row backs still does). Exit 1 found: each finding is printed, then a summary
line. Exit 2 could not run: no file at the path, ruff does not import in this
interpreter, or the file does not parse.
"""

import itertools
import re
import subprocess
import sys
from pathlib import Path

USAGE = "usage: python <this skill's directory>/scripts/check_labels.py <substrate.py>"
LABEL = re.compile(r"skill default", re.IGNORECASE)
CLOSERS = re.compile(r"[\s)\]},]+")
OPENS = re.compile(r"[(\[{]\s*$")
SPLIT_HEAD = re.compile(r"^\s*(?:-?\d+:|\w+=)\s*[^#,]*[\w.)]\s*$")
CONTINUATION = re.compile(r"^\s*[*/+-]\s")


def formatted(path: Path) -> str | None:
    """The file as `ruff format` would leave it, or None when ruff cannot run."""
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--stdin-filename",
                str(path.resolve()),
                "-",
            ],
            check=False,
            input=path.read_text(),
            cwd=path.resolve().parent,
            capture_output=True,
            text=True,
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
    return bool(code.strip()) and bool(LABEL.search(comment))


def split_entries(text: str) -> list[tuple[int, str]]:
    """Each (line number, description) where a label is split or detached."""
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    for number, (head, tail) in enumerate(itertools.pairwise(lines), start=1):
        if SPLIT_HEAD.match(head) and CONTINUATION.match(tail) and "#" in tail:
            found.append((number, f"split: {head.strip()!r} / {tail.strip()!r}"))
    for number, line in enumerate(lines, start=1):
        code, _, comment = line.partition("#")
        if (
            LABEL.search(comment)
            and code.strip()
            and (CLOSERS.fullmatch(code) or OPENS.search(code))
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
