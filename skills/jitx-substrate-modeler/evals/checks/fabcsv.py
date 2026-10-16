"""Read a fab stackup report CSV in the JITX SECTION layout.

Shared by the substrate eval checks. Stdlib only, so a check that needs no
JITX install can use it too.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

Rows = list[dict[str, str]]


def raw_sections(path: Path) -> dict[str, list[str]]:
    """{section name: its raw text lines}, the SECTION line and header included.

    Lines before the first SECTION go under the empty name. Blank lines between
    sections are dropped, so two files compare equal section by section when
    only the spacing between sections differs.
    """
    out: dict[str, list[str]] = {"": []}
    name = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SECTION,"):
            name = next(csv.reader([line]))[1]
            out[name] = []
        if line.strip():
            out[name].append(line)
    return out


def cells(lines: list[str]) -> list[list[str]]:
    """One section's raw lines as parsed cells, stripped, blank rows dropped.

    Two files that differ only in CSV quoting (a writer that drops quotes a
    field does not need) or in spaces around a cell (after a comma, or after
    a closing quote) give the same cells.
    """
    return [
        [cell.strip() for cell in row]
        for row in csv.reader(lines)
        if any(cell.strip() for cell in row)
    ]


def parse_lines(lines: list[str]) -> Rows:
    """The data rows of one section's raw lines, keyed by its header."""
    rows = list(csv.reader(io.StringIO("\n".join(lines[1:]))))
    if not rows:
        return []
    header, data = [cell.strip() for cell in rows[0]], rows[1:]
    return [
        dict(zip(header, (cell.strip() for cell in row), strict=True))
        for row in data
        if any(cell.strip() for cell in row)
    ]


def sections(path: Path) -> dict[str, Rows]:
    """{section name: its rows as dicts keyed by the section's header}."""
    return {
        name: parse_lines(lines) for name, lines in raw_sections(path).items() if name
    }


def layer_number(name: str) -> int:
    """'L7' -> 7."""
    return int(name.strip().removeprefix("L"))


def dielectric_between_mm(stackup: Rows, from_layer: str, to_layer: str) -> float:
    """Dielectric thickness between two copper layers, from the STACKUP rows.

    The copper of any layer in between is not counted.
    """
    position = {
        row["Layer"]: index for index, row in enumerate(stackup) if row["Layer"]
    }
    first, last = sorted((position[from_layer], position[to_layer]))
    return sum(
        float(row["Thickness_mm"])
        for row in stackup[first + 1 : last]
        if row["Type"] == "Dielectric"
    )
