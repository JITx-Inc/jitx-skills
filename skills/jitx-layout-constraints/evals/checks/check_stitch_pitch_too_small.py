"""Check for the stitch-pitch-too-small case.

Usage: check_stitch_pitch_too_small.py <output-dir>

The prompt asks for 0.4 mm and, if the fab cannot build it, the closest pitch
it can. The floor is 0.500 mm centre to centre, from both terms of
``min_stitch_pitch`` in jitxexamples.patterns.layout_stitched_pour: drill
0.250 (row 12) plus hole-to-hole 0.250 (row 15), and one via pad, 0.500
(row 11). Clearance is not enforced between copper of the same net (the
sheet's header: "same-net copper may touch"), and every stitch via is on GND,
so the pad-to-pad row 4 does not bind.

So 0.4 cannot be built; at 0.4 the runtime thins the grid silently
and places no via short of the floor (measured on jitx 4.6: pitch 0.4 under a
0.45 pad kept 231 of 650 sites, a checkerboard, with no issue).

Builds <output>/fixture_stitch_pitch_too_small.py, captures it, and checks:
- at least one stitch_via rule, on a square grid;
- every rule's pitch is at or above the 0.500 floor and no more than 0.550
  ("closest": the floor plus a 0.05 rounding margin);
- every rule's inset is the prompt's 0.5 (the via pad edge 0.5 in from the
  pour edge; the inset is measured from the via pad edge to the computed
  pour boundary);
- the ground pours on all four layers came back with copper;
- every grid site a rule with the prompt's inset must fill
  (stitch_common.required_sites, at the rule's pitch and inset 0.5) holds a
  generated via (``lc_check.generated_vias``). The generated vias include any
  pour or route fence as well; the fixture has neither and the prompt asks
  for neither, and a fence via fills a site only if it lands within 0.0005 of
  it (the 3-decimal match), so the fixture needs no split.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402
import stitch_common as SC  # noqa: E402

PAD_SPACE = 0.100  # fab sheet row 4; only for the sites required_sites leaves out
MIN_PITCH = max(0.500, 0.250 + 0.250)  # pad, row 11; drill plus hole-to-hole, rows 12 and 15
MAX_PITCH = MIN_PITCH + 0.05
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
    vias = L.generated_vias(rd)
    got = {(round(x, 3), round(y, 3)) for x, y in vias}
    print(f"generated vias realized: {len(vias)}")
    for pitch, inset, pad_r in patterns:
        print(f"pattern pitch {pitch} inset {inset} via pad radius {pad_r}")
        if pitch > MAX_PITCH + 1e-9:
            L.fail(f"pitch {pitch} is not the closest buildable pitch ({MIN_PITCH:.3f} to {MAX_PITCH:.3f})")
        if pitch < MIN_PITCH - 1e-9:
            L.fail(f"pitch {pitch} is under the floor {MIN_PITCH:.3f} (rows 11, 12, 15)")
        if abs(inset - PROMPT_INSET) > 1e-6:
            L.fail(f"inset {inset}, the prompt fixes {PROMPT_INSET}")
        need = SC.required_sites(geoms, pads, pitch, PROMPT_INSET, pad_r, PAD_SPACE, placed, 2 * pad_r + PAD_SPACE)
        missing = [s for s in need if (round(s[0], 3), round(s[1], 3)) not in got]
        print(f"derived sites {len(need)}, realized on them {len(need) - len(missing)}")
        if not need:
            L.fail("the rule derives no sites on these pours")
        elif missing:
            L.fail(f"{len(missing)} derived sites have no via, e.g. {missing[:5]}")
        else:
            L.ok(f"all {len(need)} derived sites stitched")
L.finish()
