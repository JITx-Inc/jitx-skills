"""Fail when `ruff format` would split a labeled derivation from its label.

Usage: python3 check_labels_formatted.py <board.py>

Formats a copy of the file in memory and looks for two shapes:
- a derivation split from its label: `1: 3 * 0.080,  # skill default: ...`
  broken into `1: 3` and `* 0.080,  # skill default: ...`, leaving the factor
  on a line with no label;
- a detached label: a `skill default` comment after code holding no number,
  such as `}),  # skill default: ...` after a wrapped call.
Exit 0 clean, 1 found (each printed), 2 could not run (ruff missing or the
file does not parse).
"""

import itertools
import re
import subprocess
import sys
from pathlib import Path

USAGE = "usage: python3 check_labels_formatted.py <board.py>"
LABEL = "skill default"
SPLIT_HEAD = re.compile(r"^\s*-?\d+:\s*[\d.]+\s*$")
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
                path.name,
                "-",
            ],
            check=False,
            input=path.read_text(),
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


def split_entries(text: str) -> list[tuple[int, str]]:
    """Each (line number, description) where a label is split or detached."""
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    for number, (head, tail) in enumerate(itertools.pairwise(lines), start=1):
        if SPLIT_HEAD.match(head) and CONTINUATION.match(tail) and "#" in tail:
            found.append((number, f"split: {head.strip()!r} / {tail.strip()!r}"))
    for number, line in enumerate(lines, start=1):
        code, _, comment = line.partition("#")
        if LABEL in comment and code.strip() and not re.search(r"\d", code):
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
    for number, description in found:
        print(f"line {number}: {description}")
    print(f"{len(found)} labels split or detached by ruff format")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
