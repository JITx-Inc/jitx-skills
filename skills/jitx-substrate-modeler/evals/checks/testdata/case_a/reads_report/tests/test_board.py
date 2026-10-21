"""Each value in board.py against the report that FAB_CSV names."""

import csv
import os
from pathlib import Path

import board


def rows(section: str) -> list[dict[str, str]]:
    lines = Path(os.environ["FAB_CSV"]).read_text(encoding="utf-8").splitlines()
    start = lines.index(f"SECTION,{section}") + 1
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("SECTION,")),
        len(lines),
    )
    return list(csv.DictReader(line for line in lines[start:end] if line.strip()))


def row(section: str, column: str, key: str) -> dict[str, str]:
    return next(r for r in rows(section) if r[column] == key)


def test_core_thickness() -> None:
    cell = row("STACKUP", "Seq", "7")["Thickness_mm"]
    assert board.CORE_L3_L4_THICKNESS == float(cell)


def test_via_pad() -> None:
    assert board.UV1_PAD == float(row("VIAS", "Via_ID", "UV-1")["Pad_mm"])


def test_fab_rule() -> None:
    cell = row("FAB_RULES", "JITX_attribute", "min_copper_width")["Value_mm"]
    assert board.MIN_COPPER_WIDTH == float(cell)


def test_impedance_width() -> None:
    cell = row("IMPEDANCE", "Structure_ID", "SE-50")["Line_width_mm"]
    assert board.SE50_L1_WIDTH == float(cell)
