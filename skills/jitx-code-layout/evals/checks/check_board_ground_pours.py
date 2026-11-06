"""Check for the board-ground-pours case.

Usage: check_board_ground_pours.py <output-dir>

Builds <output>/fixture_board_ground_pours.py, captures it, and checks the
pours against the prompt and the fab sheet:

- each of the four layers has a pour whose computed copper (``Pour.shape``
  after capture) is not empty. A pour with no same-net object on its layer
  comes back ``Empty()`` with no issue raised and the build at status ok;
  in this fixture nothing on GND touches L2 or L3;
- each layer's realized pour covers at least 90 % of the board inside the
  edge pullback, (60 - 2 x 0.300) x (40 - 2 x 0.300) mm (cl_substrate.py
  board, row 8): the prompt asks for ground over the whole board;
- the realized L1 and L4 pours touch the SMA ground pads, so they are on
  GND (same-net copper joins; another net's pour would keep clear of them).
"""

import sys
from pathlib import Path

import shapely
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

EDGE = 0.300
W, H = 60.0, 40.0
INNER_AREA = (W - 2 * EDGE) * (H - 2 * EDGE)
OUTLINE = box(-W / 2, -H / 2, W / 2, H / 2).exterior

out = L.output_dir()
with L.built(out, "fixture_board_ground_pours", "BoardGroundPoursDesign") as rd:
    from jitxexamples.components.connectors.wurth_elektronik_60312202114514 import (
        Wurth60312202114514,
    )
    from jitx.inspect import visit
    from jitx.landpattern import Pad

    gnd_pads = []
    for _, comp in visit(rd.root, Wurth60312202114514):
        for _, pad in visit(comp.landpattern.gnd, Pad):
            gnd_pads.append(L.pad_world(rd, pad))
    pours = L.world_pours(rd)
    by_layer: dict[int, list] = {}
    for path, p, g in pours:
        by_layer.setdefault(int(p.layer), []).append((path, g))
    for layer in range(4):
        got = by_layer.get(layer, [])
        g = shapely.union_all([x for _, x in got]) if got else shapely.Polygon()
        if not got:
            L.fail(f"layer {layer}: no pour")
            continue
        if g.is_empty:
            L.fail(f"layer {layer}: pour realized as Empty ({[p for p, _ in got]})")
            continue
        edge = L.gap(OUTLINE, g)
        print(f"layer {layer}: area {g.area:.1f} of {INNER_AREA:.1f}, edge gap {edge}")
        if g.area < 0.9 * INNER_AREA:
            L.fail(f"layer {layer}: realized pour covers {g.area:.1f} mm2, under 90 % of {INNER_AREA:.1f}")
        if layer in (0, 3):
            touching = sum(1 for pad in gnd_pads if g.distance(pad) < 1e-3)
            if touching == 0:
                L.fail(f"layer {layer}: the pour touches no SMA ground pad, so it is not on GND")
L.finish()
