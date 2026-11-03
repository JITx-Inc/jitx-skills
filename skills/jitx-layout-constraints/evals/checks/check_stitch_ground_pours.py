"""Check for the stitch-ground-pours case.

Usage: check_stitch_ground_pours.py <output-dir>

Builds <output>/fixture_stitch_ground_pours.py, captures it, and checks:
- at least one stitch_via rule, on a square grid;
- its pitch is no more than one twentieth of the wavelength in the board at
  2.4 GHz with er 4.2 (the prompt's criterion: 299.792458 / 2.4 / sqrt(4.2) / 20
  = 3.048 mm) and no less than the drill-to-drill floor of the fab sheet
  (row 12 drill 0.250 + row 15 hole-to-hole 0.250 = 0.500 mm centre to centre);
- the ground pours on all four layers came back with copper;
- every grid site the rule must fill (stitch_common.required_sites) holds a via.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402
import stitch_common as SC  # noqa: E402

MAX_PITCH = 299.792458 / 2.4 / math.sqrt(4.2) / 20
MIN_PITCH = 0.250 + 0.250
PAD_SPACE = 0.100  # fab sheet row 4

out = L.output_dir()
with L.built(out, "fixture_stitch_ground_pours", "StitchGroundPoursDesign") as rd:
    rules = SC.stitch_rules(rd)
    print(f"stitch rules: {len(rules)}")
    if not rules:
        L.fail("no stitch_via rule in the design")
    patterns = SC.square_patterns(rules)
    pours = L.world_pours(rd)
    geoms = [g for _, _, g in pours]
    for path, p, g in pours:
        print(f"{path} layer {p.layer}: computed area {g.area:.3f}")
    if sorted(p.layer for _, p, g in pours if not g.is_empty) != [0, 1, 2, 3]:
        L.fail("expected one ground pour with copper on each of layers 0 to 3")
    pads = [g for _, _, g in L.pads_of(rd, rd.root)]
    placed = L.placed_vias(rd)
    vias = L.stitch_vias(rd)
    got = {(round(x, 3), round(y, 3)) for x, y in vias}
    print(f"stitch vias realized: {len(vias)}")
    for pitch, inset, pad_r in patterns:
        print(f"pattern pitch {pitch} inset {inset} via pad radius {pad_r}")
        if pitch > MAX_PITCH + 1e-9:
            L.fail(f"pitch {pitch} exceeds lambda/20 at 2.4 GHz, er 4.2 ({MAX_PITCH:.3f})")
        if pitch < MIN_PITCH - 1e-9:
            L.fail(f"pitch {pitch} is under the fab drill-to-drill floor {MIN_PITCH:.3f} (rows 12, 15)")
        need = SC.required_sites(geoms, pads, pitch, inset, pad_r, PAD_SPACE, placed, MIN_PITCH)
        missing = [s for s in need if (round(s[0], 3), round(s[1], 3)) not in got]
        print(f"derived sites {len(need)}, realized on them {len(need) - len(missing)}")
        if not need:
            L.fail("the rule derives no sites on these pours")
        elif missing:
            L.fail(f"{len(missing)} derived sites have no via, e.g. {missing[:5]}")
        else:
            L.ok(f"all {len(need)} derived sites stitched")
L.finish()
