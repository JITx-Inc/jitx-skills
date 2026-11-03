"""Check for the thermal-by-pad-class case.

Usage: check_thermal_by_pad_class.py <output-dir>

Builds <output>/fixture_thermal_by_pad_class.py, captures it, and measures how
the layer-0 GND pour meets each GND pad (lc_check.relief, the spike's S2
measure: the void gap, and the width of each copper spoke crossing a ring just
outside the pad). The expected values are the prompt's:

- each 10 uF input capacitor's ground pad: 0.25 gap, four 0.30 spokes;
- the 100 nF input capacitor's ground pad: 0.20 gap, two 0.15 spokes;
- the terminal block's ground pads: solid, no void.

A GND pad is one the pour reaches; the other-net pads on these parts stand
off the pour and are skipped.
"""

import sys
from pathlib import Path

import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402

TOL = 0.02
BULK = (0.25, 0.30, 4)
SMALL = (0.20, 0.15, 2)


def relieved(label: str, rel: dict, gap: float, spoke: float, n: int) -> None:
    spokes = rel["spoke_widths"]
    good = (
        rel["gap_max"] is not None
        and abs(rel["gap_max"] - gap) <= TOL
        and len(spokes) == n
        and all(abs(s - spoke) <= TOL for s in spokes)
    )
    if good:
        L.ok(f"{label}: gap {rel['gap_max']}, spokes {spokes}")
    else:
        L.fail(f"{label}: gap {rel['gap_max']}, spokes {spokes}; expected gap {gap}, {n} spokes of {spoke}")


out = L.output_dir()
with L.built(out, "fixture_thermal_by_pad_class", "ThermalByPadClassDesign") as rd:
    c = rd.root.circuit
    l0 = [g for _, p, g in L.world_pours(rd) if p.layer == 0 and not g.is_empty]
    if not l0:
        L.fail("no layer-0 pour copper")
        L.finish()
    pour = shapely.union_all(l0)
    groups = [
        ("10 uF cap", c.reg.input_caps, BULK),
        ("100 nF cap", [c.reg.c_inp_sm], SMALL),
        ("terminal", [c.term], None),
    ]
    for name, parts, want in groups:
        gnd = 0
        for part in parts:
            for path, _, g in L.pads_of(rd, part):
                rel = L.relief(pour, g)
                if not rel["touches"]:
                    continue
                gnd += 1
                label = f"{name} {path}"
                if want is None:
                    if rel["full_contact"] and rel["voids"] == 0:
                        L.ok(f"{label}: solid")
                    else:
                        L.fail(f"{label}: not solid, {rel}")
                else:
                    relieved(label, rel, *want)
        expected = {"10 uF cap": 2, "100 nF cap": 1, "terminal": 2}[name]
        if gnd != expected:
            L.fail(f"{name}: {gnd} ground pads reached by the pour, expected {expected}")
L.finish()
