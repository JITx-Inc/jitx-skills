"""Check for the serpentine-four-sections case.

Usage: check_serpentine_four_sections.py <output-dir>

Builds <output>/fixture_serpentine_four_sections.py, captures it, and checks
each of the four pairs against the prompt:

- every route realized on layer 0, and on each row (y 15, 5, -5, -15) one
  coupled route (two traces) configured for length matching
  (``envelope_overhead`` above 0): the section;
- each section's copper spans no more than the pair's own copper (two 0.15
  traces 0.20 apart, from ``DIFF_100``) plus the prompt's 2.0 mm across its
  axis;
- row 15: the meander's pitch is at least 3.0 mm. Pitch is read where each
  trace's centre line crosses the row's axis: one trace sits on the inside of
  each turn, so neighbouring gaps alternate short and long, and each
  neighbouring two average to the pitch. Only the lower bound is scored;
- rows 5 and -5: the deskew bumps, read as the arc radii one trace has and
  the other does not, have exactly the prompt's radius (0.4 and 0.6 mm);
- row -15: the bumps (four arcs each, on one trace) sit exactly 2.0 mm
  apart, from the centre of a bump's last arc to the next bump's first, the
  ``min_bump_spacing`` the prompt asks for;
- the issue report names no signal constraint: delay and skew are met;
- no Copper or OverlappableCopper is drawn in code.

Rows 5 to -15 start at the staggered chips, 2.0 mm out of skew, so their
sections carry bumps. Other serpentine fields (``min_radius``,
``max_bump_length``, ``skew_tolerance``, ``long_lookahead``) are not scored:
spike C3 found the first two not held on jitx 4.6.0 and the others not
established.
"""

import sys
from itertools import pairwise
from pathlib import Path
from typing import Any

from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

ROWS = (15.0, 5.0, -5.0, -15.0)
PAIR = 2 * 0.15 + 0.20
ENVELOPE = 2.0
MIN_PITCH = 3.0
RADIUS = {5.0: 0.4, -5.0: 0.6}
SPACING = 2.0


def bump_arcs(traces: list[Any]) -> tuple[list[Any], list[float]]:
    """Arcs of the one trace whose radii the other trace lacks, and those radii."""
    radii = [{round(a.radius, 3) for a in L.arcs(t)} for t in traces]
    own = [radii[0] - radii[1], radii[1] - radii[0]]
    bumped = [k for k in (0, 1) if own[k]]
    if len(bumped) != 1:
        return [], []
    k = bumped[0]
    return [a for a in L.arcs(traces[k]) if round(a.radius, 3) in own[k]], sorted(own[k])


out = L.output_dir()
with L.built(out, "fixture_serpentine_four_sections", "SerpentineFourSectionsDesign") as rd:
    routes = L.realized_routes(rd, layer=0)
    sections = [
        (p, r)
        for p, r in routes
        if r.config is not None and (r.config.envelope_overhead or 0) > 0 and len(r.traces) == 2
    ]
    for y in ROWS:
        here = [(p, r) for p, r in sections if abs(L.route_geom(r).centroid.y - y) < 2.0]
        if len(here) != 1:
            L.fail(f"row {y}: {len(here)} coupled routes configured for length matching, not 1")
            continue
        path, sec = here[0]
        g = L.route_geom(sec)
        span = g.bounds[3] - g.bounds[1]
        print(f"row {y}: {path}, envelope {sec.config.envelope_overhead}, copper spans {span:.3f} across its axis")
        if span > PAIR + ENVELOPE + 1e-3:
            L.fail(f"row {y}: section copper spans {span:.3f}, over {PAIR + ENVELOPE:.3f}")
        if span <= PAIR + 1e-3:
            L.fail(f"row {y}: section did not meander (spans {span:.3f})")
        traces = list(sec.traces)
        if y == 15.0:
            for k, t in enumerate(traces):
                hits = L.centreline(t).intersection(LineString([(-100.0, y), (100.0, y)]))
                xs = sorted(p.x for p in getattr(hits, "geoms", [hits]) if not p.is_empty)
                gaps = [b - a for a, b in pairwise(xs)]
                pitches = [(a + b) / 2 for a, b in pairwise(gaps)]
                lo = min(pitches) if pitches else None
                print(f"row {y} trace {k}: {len(xs)} axis crossings, least pitch {lo}")
                if lo is None or lo < MIN_PITCH - 1e-3:
                    L.fail(f"row {y} trace {k}: meander pitch {lo}, under {MIN_PITCH}")
        else:
            bumps, radii = bump_arcs(traces)
            print(f"row {y}: bump radii {radii}, {len(bumps)} bump arcs")
            if not bumps:
                L.fail(f"row {y}: no deskew bumps on exactly one trace")
                continue
            if y in RADIUS and radii != [RADIUS[y]]:
                L.fail(f"row {y}: bump radii {radii}, not {RADIUS[y]}")
            if y == -15.0:
                groups = [bumps[i : i + 4] for i in range(0, len(bumps), 4)]
                gaps = [round(abs(n[0].center[0] - p[-1].center[0]), 4) for p, n in pairwise(groups)]
                print(f"row {y}: bump gaps {gaps}")
                if len(bumps) % 4 or not gaps or any(abs(gp - SPACING) > 0.01 for gp in gaps):
                    L.fail(f"row {y}: bumps {gaps} apart, not {SPACING}")
    text = L.issues_text(rd, wait=40)
    bad = L.issue_kinds(text, "signal constraint", "UnmetTime", "UnsquiggledRoute")
    print("issues:", text.strip().splitlines()[:4])
    if bad:
        L.fail(f"timing issues: {bad}")
    L.no_authored_copper(rd, "configured sections and rules were asked for")
L.finish()
