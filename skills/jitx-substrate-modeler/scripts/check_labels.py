"""Fail when ``ruff format`` would split a labeled derivation from its label.

Usage: ``python scripts/check_labels.py <substrate.py>``

Run it with the project's own Python interpreter, the one its ``ruff`` is
installed in, on the file that holds the substrate. It formats a copy of the
file in memory, with the ruff configuration that applies to the file's own
directory, so a project that sets ``line-length`` is checked at that length.
It reports two shapes:

- a derivation split from its label: ``1: 3 * 0.080,  # skill default: ...``
  broken into ``1: 3`` and ``* 0.080,  # skill default: ...``;
- a detached label: a ``skill default`` comment after code holding no number,
  such as ``}),  # skill default: ...`` after a wrapped call.

A file that calls ``.reference(`` but carries no ``skill default`` label at
all is also reported, since its plane widths are unlabeled.

Exit 0 clean, with one summary line to quote: ``check_labels: <n> labeled
values, none split from their label``, or, for a file with no ``.reference(``
call and no label, a line saying there was nothing to check. Exit 1 found:
each finding is printed, then a summary line. Exit 2 could not run: ruff does
not import in this interpreter, or the file does not parse.
"""

import itertools
import re
import subprocess
import sys
from pathlib import Path

USAGE = "usage: python scripts/check_labels.py <substrate.py>"
LABEL = re.compile(r"skill default", re.IGNORECASE)
SPLIT_HEAD = re.compile(r"^\s*-?\d+:\s*[^#,]*[\w.)]\s*$")
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
        if LABEL.search(comment) and code.strip() and not re.search(r"\d", code):
            found.append((number, f"detached: {line.strip()!r}"))
    return sorted(found)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    text = formatted(Path(argv[1]))
    if text is None:
        return 2
    found = split_entries(text)
    labels = sum(1 for line in text.splitlines() if trailing_label(line))
    if labels == 0 and ".reference(" in text:
        print("check_labels: no skill-default label, though the file calls .reference(")
        return 1
    for number, description in found:
        print(f"line {number}: {description}")
    if found:
        print(f"check_labels: {labels} labeled lines, {len(found)} split or detached")
        return 1
    if labels == 0:
        print("check_labels: no .reference( call and no label, nothing to check")
        return 0
    print(f"check_labels: {labels} labeled values, none split from their label")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
