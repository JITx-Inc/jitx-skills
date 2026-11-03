"""Check for the stitch-pitch-too-small case.

Usage: check_stitch_pitch_too_small.py <output-dir>

The prompt asks for 0.4 mm and, if the fab cannot build it, the closest pitch
it can. The fab floor is drill 0.250 (row 12) plus hole-to-hole 0.250 (row 15)
= 0.500 mm centre to centre, so 0.4 cannot be built; at 0.4 the runtime thins
the grid silently and places no via short of the floor (spike S3: pitch 0.4
under a 0.45 pad kept 231 of 650 sites, a checkerboard, with no issue).

Builds <output>/fixture_stitch_pitch_too_small.py, captures it, and checks:
- at least one stitch_via rule, on a square grid;
- every rule's pitch is at or above the 0.500 floor and no more than 0.650
  ("closest": the floor plus the 0.100 copper space of row 4, plus margin);
- every rule's inset is the prompt's 0.5 (the via pad edge 0.5 in from the
  pour edge; spike S3 measured inset from the via pad edge to the computed
  pour boundary);
- the ground pours on all four layers came back with copper;
- every grid site a rule with the prompt's inset must fill
  (stitch_common.required_sites, at the rule's pitch and inset 0.5) holds a
  via.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402
import stitch_common as SC  # noqa: E402

MAX_PITCH = 0.650
MIN_PITCH = 0.250 + 0.250
PAD_SPACE = 0.100  # fab sheet row 4
PROMPT_INSET = 0.5

out = L.output_dir()
with L.built(out, "fixture_stitch_pitch_too_small", "StitchPitchTooSmallDesign") as rd:
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
            L.fail(f"pitch {pitch} is not the closest buildable pitch (0.500 to {MAX_PITCH:.3f})")
        if pitch < MIN_PITCH - 1e-9:
            L.fail(f"pitch {pitch} is under the fab drill-to-drill floor {MIN_PITCH:.3f} (rows 12, 15)")
        if abs(inset - PROMPT_INSET) > 1e-6:
            L.fail(f"inset {inset}, the prompt fixes {PROMPT_INSET}")
        need = SC.required_sites(geoms, pads, pitch, PROMPT_INSET, pad_r, PAD_SPACE, placed, MIN_PITCH)
        missing = [s for s in need if (round(s[0], 3), round(s[1], 3)) not in got]
        print(f"derived sites {len(need)}, realized on them {len(need) - len(missing)}")
        if not need:
            L.fail("the rule derives no sites on these pours")
        elif missing:
            L.fail(f"{len(missing)} derived sites have no via, e.g. {missing[:5]}")
        else:
            L.ok(f"all {len(need)} derived sites stitched")
L.finish()
