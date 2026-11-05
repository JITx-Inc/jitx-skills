"""Check for the apply-routing-structures case.

Usage: check_apply_routing_structures.py <output-dir>

Builds <output>/fixture_apply_routing_structures.py, captures it, and checks
the two feed segments against the substrate's structures (lc_substrate.py):

- ``feed_escape`` (connector pad to the via): NECK_50, width 0.12, the layer-0
  pour at least 0.12 away. Its cap is the largest of NECK_50's 0.12, fab row
  4's 0.100 and the largest clearance rule in the output whose conditions match the escape
  and that pour (``lc_check.matching_clearances``), plus 0.01 and 0.02
  tolerance: measured on jitx 4.6, a matching clearance rule larger than a
  structure's clearance sets the gap, so a board rule such as a
  copper-to-copper default above 0.12 moves the escape's pour out;
- ``feed`` (via to the inductor): CPWG_50, width 0.30, the pour 0.20 away,
  within [0.20, 0.23]: a matching clearance rule above 0.20 would move
  the coplanar ground off CPWG_50's gap;
- the issue report has no "Missing routing structure" line (with a
  structure applied by rule the line goes away, measured on jitx 4.6).

Measured on jitx 4.6: a priority-1 structure rule on a tag on the escape Route object
gives that segment its own structure and leaves the rest at the net's. Pour
gaps were measured at the structure clearance plus 0.01.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402

SEGMENTS = {
    "feed_escape": (0.12, 0.12),
    "feed": (0.30, 0.20),
}
FLOOR = 0.100  # fab sheet row 4
caps: dict[str, float] = {}


def escape_cap(rd: Any) -> None:
    """The largest of NECK_50's clearance, the fab floor and every clearance
    rule matching the escape and the layer-0 pour; read before capture."""
    c = rd.root.circuit
    space = SEGMENTS["feed_escape"][1]
    on_route = L.copper_facts(rd, L.TRACE, 0, c.feed_escape, c.ANT, c)
    on_pour = L.copper_facts(rd, L.POUR, 0, c.pours[0], c.GND, c)
    matching = L.matching_clearances(rd, on_route, on_pour)
    print(f"feed_escape: tags {on_route.tags}; clearance rules matching it and the pour: {matching}")
    caps["feed_escape"] = max([space, FLOOR] + [r.clearance_constraint.clearance for r in matching if r.clearance_constraint])


out = L.output_dir()
with L.built(out, "fixture_apply_routing_structures", "ApplyRoutingStructuresDesign", before_capture=escape_cap) as rd:
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
        top = caps.get(name, space)
        gap = L.gap(pours[0], L.route_geom(route))
        if space - 1e-3 <= gap <= top + 0.03:
            L.ok(f"{name}: pour gap {gap}")
        else:
            L.fail(f"{name}: pour gap {gap}, expected {space} to {top} (+0.01)")
    text = rd.issues(wait=20, satisfied=True).text()
    print(text)
    if "Missing routing structure" in text:
        L.fail("the issue report still has a missing routing structure")
    else:
        L.ok("no missing routing structure reported")
L.finish()
