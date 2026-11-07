"""Check for the qfn-thermal-vias case.

Usage: check_qfn_thermal_vias.py <output-dir>

Builds <output>/fixture_qfn_thermal_vias.py, captures it, and checks the
vias in the KSZ9031RNX exposed pad against the prompt, the part's land
pattern and the fab sheet:

- the grid count is worked out here from the exposed pad's copper as
  captured (its side, 3.60 in land pattern figure 13-3), the prompt's 1.0
  pitch and 0.25 rim margin, and row 16's 0.450 via pad: centres may sit
  within side / 2 - 0.25 - 0.225 of the pad centre, so a grid centred on the
  pad holds floor(2 x that / 1.0) + 1 per axis, squared;
- exactly that many code-placed vias sit inside the exposed pad, on a 1.0
  grid centred on it, each via pad's rim at least 0.25 inside the pad edge;
- every via in the pad is one the fab accepts in a pad: ``via_in_pad`` is
  True (row 16; row 12's open via is not accepted in a pad). The runtime
  raises no issue for a via in a pad that does not allow one, so the
  check reads the flag;
- each via centre lies inside the realized L2 ground pour (``Pour.shape``
  after capture), so it joins the plane the heat goes to;
- the exposed pad keeps its mask and paste: the paste windows total
  4 x 1.425^2 = 8.1225 mm2 inside the pad copper (four windows, 0.25 in from
  the copper and 0.25 apart: (3.60 - 3 x 0.25) / 2 = 1.425, the part's
  docstring), and a mask opening covers the whole pad.
"""

import math
import sys
from pathlib import Path

import shapely
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

PITCH = 1.0
RIM = 0.25
VIA_PAD = 0.450
PASTE_AREA = 4 * ((3.60 - 3 * 0.25) / 2) ** 2

out = L.output_dir()
with L.built(out, "fixture_qfn_thermal_vias", "QfnThermalViasDesign") as rd:
    from jitx.feature import Paste, Soldermask
    from jitx.inspect import visit
    from jitxexamples.components.ethernet_phys.microchip_KSZ9031RNX import KSZ9031RNX

    phys = [c for _, c in visit(rd.root, KSZ9031RNX)]
    ep = phys[0].landpattern.thermal_pads[0]
    pad = L.pad_world(rd, ep)
    x0, y0, x1, y1 = pad.bounds
    side = round(x1 - x0, 4)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = side / 2 - RIM - VIA_PAD / 2
    n = math.floor(2 * half / PITCH + 1e-9) + 1
    want = n * n
    print(f"exposed pad {side} square at ({cx:.3f}, {cy:.3f}); {n} per axis, {want} vias expected")
    inside = [(x, y, v) for x, y, v in L.placed_vias(rd) if pad.contains(Point(x, y))]
    print(f"code-placed vias in the pad: {len(inside)}")
    if len(inside) != want:
        L.fail(f"{len(inside)} vias in the exposed pad, {want} expected")
    for x, y, v in inside:
        d = float(v.diameter)
        rim = min(x - d / 2 - x0, x1 - x - d / 2, y - d / 2 - y0, y1 - y - d / 2)
        if rim < RIM - 1e-3:
            L.fail(f"via at ({x:.3f}, {y:.3f}): pad rim {rim:.3f} from the pad edge, under {RIM}")
        if not getattr(v, "via_in_pad", False):
            L.fail(
                f"via at ({x:.3f}, {y:.3f}) is {type(v).__name__} with via_in_pad False (row 12), not row 16's VipVia"
            )
        for c, label in ((x - cx, "x"), (y - cy, "y")):
            k = c / PITCH - (n - 1) / 2
            if abs(k - round(k)) > 1e-3:
                L.fail(f"via at ({x:.3f}, {y:.3f}) is off the {PITCH} grid centred on the pad in {label}")
    if inside:
        L.ok(
            f"via pads {sorted({round(float(v.diameter), 3) for _, _, v in inside})}, all checked against the rim and grid"
        )
    planes = [g for _, p, g in L.world_pours(rd) if int(p.layer) == 1]
    plane = shapely.union_all(planes) if planes else shapely.Polygon()
    outside = [(round(x, 3), round(y, 3)) for x, y, _ in inside if not plane.contains(Point(x, y))]
    if plane.is_empty:
        L.fail("the L2 ground pour did not realize")
    elif outside:
        L.fail(f"vias not inside the realized L2 ground pour: {outside}")
    elif inside:
        L.ok("every via in the pad sits in the realized L2 ground pour")
    paste = [L.geom(L.placed(t.transform) * f.shape) for t, f in visit(ep, Paste)]
    mask = [L.geom(L.placed(t.transform) * f.shape) for t, f in visit(ep, Soldermask)]
    local = L.geom(ep.shape)
    pa = shapely.union_all(paste) if paste else shapely.Polygon()
    ma = shapely.union_all(mask) if mask else shapely.Polygon()
    print(f"paste {pa.area:.4f} mm2 (expected {PASTE_AREA:.4f}), mask covers pad: {ma.covers(local)}")
    if abs(pa.area - PASTE_AREA) > 1e-3 or not local.covers(pa):
        L.fail(f"exposed-pad paste {pa.area:.4f} mm2, not the part's {PASTE_AREA:.4f} inside the pad")
    if not ma.covers(local):
        L.fail("the exposed pad's mask opening no longer covers the pad")
L.finish()
