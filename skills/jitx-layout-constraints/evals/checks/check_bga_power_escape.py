"""Check for the bga-power-escape case.

Usage: check_bga_power_escape.py <output-dir>

Builds <output>/fixture_bga_power_escape.py, captures it, and measures the two
VCORE segments:

- ``vcore_escape`` (the VCORE ball to the first via) is realized and every
  trace shape has a width of at least 0.100 (fab row 3) and at most the ball
  channel less 0.100 of space on each side (fab row 4). The channel is the
  land pattern's nearest-ball pitch less its ball pad: ``BGA_HPITCH`` 1.0 -
  ``BGA_BALL_DIAMETER`` 0.5 = 0.5, so the escape is at most 0.3 wide;
- the escape copper is at least 0.100 (fab row 4) from every other ball pad,
  measured from the captured geometry;
- ``vcore_trunk`` (via to via) keeps the prompt's 0.5 class width on every
  shape.

With the fixture as given the escape is not realized ("Unable to find path for
requested route", this suite's own run, 2026-11-03). A rule on the VCORE net
or on ``VcoreTag & IsTrace`` narrows the trunk too (spike S10's control case)
and fails the third item.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jitxexamples.demos.si_bga_optimization.generic_bga import (  # noqa: E402
    BGA_BALL_DIAMETER,
    BGA_HPITCH,
)

import lc_check as L  # noqa: E402

FAB_MIN_WIDTH = 0.100
FAB_MIN_SPACE = 0.100
CHANNEL = BGA_HPITCH - BGA_BALL_DIAMETER
MAX_ESCAPE = CHANNEL - 2 * FAB_MIN_SPACE
TRUNK_WIDTH = 0.5
VCORE_BALL = (4, 2)

out = L.output_dir()
with L.built(out, "fixture_bga_power_escape", "BgaPowerEscapeDesign") as rd:
    c = rd.root.circuit
    esc = L.trace_widths(c.vcore_escape)
    print(f"vcore_escape widths: {esc} (allowed {FAB_MIN_WIDTH}..{MAX_ESCAPE:.3f})")
    if not esc:
        L.fail("vcore_escape has no realized traces")
    elif any(w is None or not (FAB_MIN_WIDTH - 1e-9 <= w <= MAX_ESCAPE + 1e-9) for w in esc):
        L.fail(f"vcore_escape widths {esc}, expected each in [{FAB_MIN_WIDTH}, {MAX_ESCAPE:.3f}]")
    else:
        L.ok(f"escape widths {esc} fit the {CHANNEL:.3f} channel")
    if esc:
        vpad = c.bga.landpattern.get_pad(*VCORE_BALL)
        geom = L.route_geom(c.vcore_escape)
        others = [(path, g) for path, p, g in L.pads_of(rd, c.bga) if p is not vpad]
        if len(others) == len(L.pads_of(rd, c.bga)):
            L.fail("could not find the VCORE ball pad")
        else:
            path, g = min(others, key=lambda t: t[1].distance(geom))
            d = round(g.distance(geom), 4)
            print(f"nearest other ball: {path} at {d}")
            if d >= FAB_MIN_SPACE - 1e-3:
                L.ok(f"escape {d} from the nearest other ball")
            else:
                L.fail(f"escape {d} from {path}, under fab row 4's {FAB_MIN_SPACE}")
    trunk = L.trace_widths(c.vcore_trunk)
    print(f"vcore_trunk widths: {trunk}")
    if not trunk:
        L.fail("vcore_trunk has no realized traces")
    elif any(w is None or abs(w - TRUNK_WIDTH) > 1e-3 for w in trunk):
        L.fail(f"vcore_trunk widths {trunk}, expected {TRUNK_WIDTH}")
    else:
        L.ok(f"trunk realized at {TRUNK_WIDTH}")
L.finish()
