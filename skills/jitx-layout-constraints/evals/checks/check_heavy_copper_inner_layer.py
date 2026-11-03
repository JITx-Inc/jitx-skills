"""Check for the heavy-copper-inner-layer case.

Usage: check_heavy_copper_inner_layer.py <output-dir>

Builds <output>/fixture_heavy_copper_inner_layer.py, captures it, and measures
the two inner-layer routes against the fab sheet:

- ``vin_l2`` on layer 1 (L2, 2 oz, row 2): width 0.200 (row 5), and the
  layer-1 GND pour 0.250 (row 6) away;
- ``sense_l3`` on layer 2 (L3, 0.5 oz): unchanged at the board defaults,
  0.15 wide with the layer-2 pour 0.15 away (rows 3 and 4 plus 0.05; the
  sheet's note keeps rows 3 and 4 on a non-2 oz layer).

Spike S8: OnLayer.internal() matched both inner layers, so a rule written on
it moves ``sense_l3`` too and fails here. Pour gaps were measured at the
winning clearance plus 0.01 (S8, S9), so each gap must lie in [value,
value + 0.03]. Every trace shape must have a width (S8: Polygon traces).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lc_check as L  # noqa: E402

ROUTES = {
    "vin_l2": (1, 0.200, 0.250),
    "sense_l3": (2, round(0.100 + 0.05, 3), round(0.100 + 0.05, 3)),
}

out = L.output_dir()
with L.built(out, "fixture_heavy_copper_inner_layer", "HeavyCopperInnerLayerDesign") as rd:
    c = rd.root.circuit
    pours = {p.layer: g for _, p, g in L.world_pours(rd) if not g.is_empty}
    for name, (layer, width, space) in ROUTES.items():
        route = getattr(c, name)
        widths = L.trace_widths(route)
        print(f"{name} (layer {layer}): widths {widths}")
        if not widths:
            L.fail(f"{name} has no realized traces")
            continue
        if any(w is None or abs(w - width) > 1e-3 for w in widths):
            L.fail(f"{name} widths {widths}, expected {width}")
        else:
            L.ok(f"{name} realized at {width}")
        if layer not in pours:
            L.fail(f"no pour copper on layer {layer}")
            continue
        gap = L.gap(pours[layer], L.route_geom(route))
        if space - 1e-3 <= gap <= space + 0.03:
            L.ok(f"{name}: layer-{layer} pour gap {gap}")
        else:
            L.fail(f"{name}: layer-{layer} pour gap {gap}, expected {space} (+0.01)")
L.finish()
