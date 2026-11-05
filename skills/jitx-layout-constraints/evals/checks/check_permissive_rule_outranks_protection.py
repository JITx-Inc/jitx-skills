"""Check for the permissive-rule-outranks-protection case.

Usage: check_permissive_rule_outranks_protection.py <output-dir>

Builds <output>/fixture_permissive_rule_outranks_protection.py, captures it,
and checks:

- the layer-0 GND pour sits the fixture's 0.6 keep-away plus the runtime's
  0.01 (measured on jitx 4.6: a clearance to AnyObject sets the pour gap at
  the rule's value plus 0.01) from the VIN route, within [0.60, 0.63];
- the VIN route is still realized at its 0.5 width;
- a 0.1 clearance rule is still in the design: the escape spacing the TPS62933
  pads need was kept, not deleted to make room for the keep-away.

On the bare fixture (2026-11-03, this suite's own run) the pour gap was 0.11:
the priority-4 escape rule on every L1 trace beat the priority-2 keep-away.
"""

import sys
from pathlib import Path

import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jitx.constraints import BinaryDesignConstraint  # noqa: E402

import lc_check as L  # noqa: E402

KEEPAWAY = 0.6
WIDTH = 0.5
ESCAPE = 0.1

out = L.output_dir()
with L.built(out, "fixture_permissive_rule_outranks_protection", "PermissiveRuleOutranksProtectionDesign") as rd:
    route = rd.root.circuit.vin_route
    widths = L.trace_widths(route)
    print(f"VIN route widths: {widths}")
    if not widths or any(w is None or abs(w - WIDTH) > 1e-3 for w in widths):
        L.fail(f"VIN route widths {widths}, not {WIDTH}")
    l0 = [g for _, p, g in L.world_pours(rd) if p.layer == 0 and not g.is_empty]
    if not l0:
        L.fail("no layer-0 pour copper")
    else:
        gap = L.gap(shapely.union_all(l0), L.route_geom(route))
        print(f"layer-0 pour gap to the VIN route: {gap}")
        if not (KEEPAWAY - 1e-3 <= gap <= KEEPAWAY + 0.03):
            L.fail(f"pour gap {gap}, not the {KEEPAWAY} keep-away (+0.01)")
        else:
            L.ok(f"keep-away realized at {gap}")
    escapes = [
        c
        for c in L.rules(rd.root)
        if isinstance(c, BinaryDesignConstraint)
        and c.clearance_constraint is not None
        and abs(c.clearance_constraint.clearance - ESCAPE) < 1e-9
    ]
    if not escapes:
        L.fail(f"the {ESCAPE} escape clearance rule is gone")
    else:
        L.ok(f"the {ESCAPE} escape clearance rule is kept")
L.finish()
