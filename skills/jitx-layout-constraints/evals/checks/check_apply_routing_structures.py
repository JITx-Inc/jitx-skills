"""Check for the apply-routing-structures case.

Usage: check_apply_routing_structures.py <output-dir>

Builds <output>/fixture_apply_routing_structures.py, captures it, and checks
the two feed segments against the substrate's structures (lc_substrate.py):

- ``feed_escape`` (connector pad to the via): NECK_50, width 0.12, the layer-0
  pour 0.12 away;
- ``feed`` (via to the inductor): CPWG_50, width 0.30, the pour 0.20 away;
- the issue report has no "Missing routing structure" line (with a
  structure applied by rule the line goes away, measured on jitx 4.6).

Measured on jitx 4.6: a priority-1 structure rule on a tag on the escape Route object
gives that segment its own structure and leaves the rest at the net's. Pour
gaps were measured at the structure clearance plus 0.01, so each gap
must lie in [value, value + 0.03].
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402

SEGMENTS = {
    "feed_escape": (0.12, 0.12),
    "feed": (0.30, 0.20),
}

out = L.output_dir()
with L.built(out, "fixture_apply_routing_structures", "ApplyRoutingStructuresDesign") as rd:
    c = rd.root.circuit
    pours = {p.layer: g for _, p, g in L.world_pours(rd) if not g.is_empty}
    for name, (width, space) in SEGMENTS.items():
        route = getattr(c, name)
        widths = L.trace_widths(route)
        print(f"{name}: widths {widths}")
        if not widths:
            L.fail(f"{name} has no realized traces")
            continue
        if any(w is None or abs(w - width) > 1e-3 for w in widths):
            L.fail(f"{name} widths {widths}, expected {width}")
        else:
            L.ok(f"{name} realized at {width}")
        if 0 not in pours:
            L.fail("no layer-0 pour copper")
            continue
        gap = L.gap(pours[0], L.route_geom(route))
        if space - 1e-3 <= gap <= space + 0.03:
            L.ok(f"{name}: pour gap {gap}")
        else:
            L.fail(f"{name}: pour gap {gap}, expected {space} (+0.01)")
    text = rd.issues(wait=20, satisfied=True).text()
    print(text)
    if "Missing routing structure" in text:
        L.fail("the issue report still has a missing routing structure")
    else:
        L.ok("no missing routing structure reported")
L.finish()
