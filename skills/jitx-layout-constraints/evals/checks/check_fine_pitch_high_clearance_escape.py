"""Check for the fine-pitch-high-clearance-escape case.

Usage: check_fine_pitch_high_clearance_escape.py <output-dir>

Builds <output>/fixture_fine_pitch_high_clearance_escape.py, captures it, and
measures the two switch-node segments:

- ``sw_escape`` (SW pad to the via): every trace shape has a width, each
  strictly under 0.28, the narrow side of the SOT-583 pad
  (``rectangle(0.28, 0.68)`` in the TPS62933 land pattern), and at least
  0.100, fab row 3's minimum width;
- ``sw_trunk`` (via to the inductor): every trace shape 0.6 wide, the
  prompt's switch-node class width;
- the layer-0 GND pour sits 0.25 from the trunk, the fixture's
  ``SwTag`` class clearance, within [0.25, 0.28] (measured on jitx 4.6: pour pullback
  at the winning clearance plus 0.01).

The escape rule must reach the escape only: a rule on the switch-node net or
on ``SwTag & IsTrace`` narrows the trunk too (measured on jitx 4.6) and
fails the second item. With the fixture as given, the escape comes back as a
Polygon with no width (this suite's own run, 2026-11-03), which fails the
first.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402

PAD_NARROW = 0.28
FAB_MIN_WIDTH = 0.100
TRUNK_WIDTH = 0.6
SW_CLEARANCE = 0.25

out = L.output_dir()
with L.built(out, "fixture_fine_pitch_high_clearance_escape", "FinePitchHighClearanceEscapeDesign") as rd:
    c = rd.root.circuit
    esc = L.trace_widths(c.sw_escape)
    print(f"sw_escape widths: {esc}")
    if not esc:
        L.fail("sw_escape has no realized traces")
    elif any(w is None or not (FAB_MIN_WIDTH - 1e-9 <= w < PAD_NARROW) for w in esc):
        L.fail(f"sw_escape widths {esc}, expected each in [{FAB_MIN_WIDTH}, {PAD_NARROW})")
    else:
        L.ok(f"escape widths {esc} fit inside the {PAD_NARROW} pad")
    trunk = L.trace_widths(c.sw_trunk)
    print(f"sw_trunk widths: {trunk}")
    if not trunk:
        L.fail("sw_trunk has no realized traces")
    elif any(w is None or abs(w - TRUNK_WIDTH) > 1e-3 for w in trunk):
        L.fail(f"sw_trunk widths {trunk}, expected {TRUNK_WIDTH}")
    else:
        L.ok(f"trunk realized at {TRUNK_WIDTH}")
        l0 = [g for _, p, g in L.world_pours(rd) if p.layer == 0 and not g.is_empty]
        if not l0:
            L.fail("no layer-0 pour copper")
        else:
            gap = min(L.gap(g, L.route_geom(c.sw_trunk)) for g in l0)
            if SW_CLEARANCE - 1e-3 <= gap <= SW_CLEARANCE + 0.03:
                L.ok(f"trunk to pour {gap}")
            else:
                L.fail(f"trunk to pour {gap}, expected {SW_CLEARANCE} (+0.01)")
L.finish()
