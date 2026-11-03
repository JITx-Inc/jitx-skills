"""Check for the default-net-classes case.

Usage: check_default_net_classes.py <output-dir>

Builds <output>/fixture_default_net_classes.py, captures it, and measures the
two code routes against the prompt's classes:

- the default class (the soft-start route): width 0.100 (fab row 3) + 0.05 =
  0.15, and the layer-0 GND pour 0.100 (fab row 4) + 0.05 = 0.15 away;
- the power class (the VIN route): width 0.5, the pour 0.3 away.

Every realized trace shape must have a width (spike S8: a width that does not
fit comes back as a Polygon). Spike S9 measured pour gaps at the winning
clearance plus 0.01, so each gap must lie in [value, value + 0.03].
"""

import sys
from pathlib import Path

import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402

CLASSES = {
    "ss_route": (round(0.100 + 0.05, 3), round(0.100 + 0.05, 3)),
    "vin_route": (0.5, 0.3),
}

out = L.output_dir()
with L.built(out, "fixture_default_net_classes", "DefaultNetClassesDesign") as rd:
    c = rd.root.circuit
    l0 = [g for _, p, g in L.world_pours(rd) if p.layer == 0 and not g.is_empty]
    pour = shapely.union_all(l0) if l0 else None
    if pour is None:
        L.fail("no layer-0 pour copper")
    for name, (width, space) in CLASSES.items():
        route = getattr(c, name)
        widths = L.trace_widths(route)
        print(f"{name}: widths {widths}")
        if not widths:
            L.fail(f"{name} has no realized traces")
        elif any(w is None or abs(w - width) > 1e-3 for w in widths):
            L.fail(f"{name} widths {widths}, expected {width}")
        else:
            L.ok(f"{name} realized at {width}")
        if pour is not None and widths:
            gap = L.gap(pour, L.route_geom(route))
            if space - 1e-3 <= gap <= space + 0.03:
                L.ok(f"{name}: pour gap {gap}")
            else:
                L.fail(f"{name}: pour gap {gap}, expected {space} (+0.01)")
L.finish()
