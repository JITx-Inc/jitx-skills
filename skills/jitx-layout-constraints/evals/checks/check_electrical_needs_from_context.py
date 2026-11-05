"""Check for the electrical-needs-from-context case.

Usage: check_electrical_needs_from_context.py <output-dir>

Builds <output>/fixture_electrical_needs_from_context.py, captures it, and
checks:

- nothing but tags and rules changed (``lc_check.built``), and every pour is
  drawn as in the fixture, layer and shape (``check_drawn_pours``);
- both routes are realized and every pour has computed copper (a pour pushed
  to ``Empty`` would pass the distance checks with nothing to measure);
- on every layer, every piece of primary-side copper (``VIN48`` and ``GND_P``:
  pads, routes, pours and code-placed vias) sits at least 2.0 from every
  piece of secondary-side copper (``V3V3`` and ``GND_S``). The 2.0 is the
  barrier clearance in the fixture's ``corrow_cpi4833_excerpt.md``;
- on every layer the 48 V route has copper on, the route sits at least 0.6
  from every piece of ``GND_P`` copper on that layer. The 0.6 is row S2 of the
  fixture's ``house_spacing_rules.md`` (conductors above 30 V, external
  layers), and ``requirements.md`` puts the input at 48 V nominal, 57 V
  maximum. The route is the only ``VIN48`` copper this item
  measures. A rule keyed on a tag on the route alone also passes it; the
  case's judge assertion that the rule is keyed on the net is the guard.

A via the runtime generates (a stitch or fence via from a rule the runner
adds) is not classified by side: ``rd.query(Via)`` does not say which net a
generated via is on. The fixture places no generated via.

Measured on the bare fixture (2026-11-05): see the case notes.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shapely  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from shapely.geometry.base import BaseGeometry  # noqa: E402

from jitx.inspect import visit  # noqa: E402
from jitx.via import Via  # noqa: E402

import lc_check as L  # noqa: E402

MODULE = "fixture_electrical_needs_from_context"
DESIGN = "ElectricalNeedsFromContextDesign"
BARRIER = 2.0
HOUSE_48V = 0.6
LAYERS = range(4)
VIA_PAD = 0.5  # fab row 11, the ThVia pad diameter
TOL = 1e-3

# The drawn shape of every pour, by layer, in board coordinates, read from the
# instantiated design before any build, in a fresh interpreter (the output and
# the bare fixture share module names).
_DRAWN_POURS = """
import importlib, json, sys
sys.path.insert(0, sys.argv[1])
from jitx.copper import Pour
from jitx.inspect import visit
from jitx.run.runtime import _instantiate_design
d = _instantiate_design(getattr(importlib.import_module(sys.argv[2]), sys.argv[3]))
out = []
for t, p in visit(d, Pour):
    s = p.shape if t.transform is None else t.transform * p.shape
    out.append([p.layer, s.to_shapely().g.wkt])
print(json.dumps(out))
"""


def drawn_pours(project: Path) -> list[tuple[int, BaseGeometry]]:
    run = subprocess.run(
        [sys.executable, "-c", _DRAWN_POURS, str(project), MODULE, DESIGN],
        cwd=project,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        print(run.stdout + run.stderr, file=sys.stderr)
        print(f"error: could not read the drawn pours in {project}", file=sys.stderr)
        sys.exit(2)
    return [(layer, shapely.from_wkt(w)) for layer, w in json.loads(run.stdout.strip().splitlines()[-1])]


def check_drawn_pours(out: Path) -> None:
    """Fail when a pour's drawn shape differs from the fixture's: moving a
    pour edge would meet the barrier by redrawing the board, not by a rule."""
    got = drawn_pours(out)
    with tempfile.TemporaryDirectory() as tmp:
        want = drawn_pours(L.bare_fixture(MODULE, Path(tmp) / "bare"))
    unmatched = list(want)
    for layer, g in got:
        match = next((w for w in unmatched if w[0] == layer and w[1].symmetric_difference(g).area < 1e-6), None)
        if match is None:
            L.fail(f"a layer-{layer} pour is drawn as {g.bounds}, which no fixture pour on that layer matches")
        else:
            unmatched.remove(match)
    for layer, g in unmatched:
        L.fail(f"the fixture's layer-{layer} pour drawn as {g.bounds} is missing or redrawn")
    print(f"drawn pours: {len(got)} in the output, {len(want)} in the fixture, {len(unmatched)} unmatched")


out = L.output_dir()
check_drawn_pours(out)
with L.built(out, MODULE, DESIGN) as rd:
    c = rd.root.circuit

    def empty() -> dict[int, list[BaseGeometry]]:
        return {layer: [] for layer in LAYERS}

    primary, secondary, gnd_p = empty(), empty(), empty()

    for name, route, side in (("VIN48", c.vin_route, primary), ("V3V3", c.v3_route, secondary)):
        widths = L.trace_widths(route)
        print(f"{name} route widths: {widths}")
        if not widths:
            L.fail(f"the {name} route has no realized traces")
        else:
            side[route.layer].append(L.route_geom(route))

    pours = {id(p): g for _, p, g in L.world_pours(rd)}
    for label, group, side in (
        ("GND_P", c.primary_pours, (primary, gnd_p)),
        ("GND_S", c.secondary_pours, (secondary,)),
    ):
        for p in group:
            g = pours.get(id(p))
            if g is None or g.is_empty:
                L.fail(f"the layer-{p.layer} {label} pour has no computed copper")
                continue
            for s in side:
                s[p.layer].append(g)

    # Every pad in the fixture is an SMD pad on layer 0.
    for label, pad, side in (
        ("J1 pad 1 (VIN48)", c.j1.landpattern.p1, (primary,)),
        ("J1 pad 2 (GND_P)", c.j1.landpattern.p2, (primary, gnd_p)),
        ("U1 pad 1 (VIN48)", c.u1.landpattern.p1, (primary,)),
        ("U1 pad 2 (GND_P)", c.u1.landpattern.p2, (primary, gnd_p)),
        ("U1 pad 3 (V3V3)", c.u1.landpattern.p3, (secondary,)),
        ("U1 pad 4 (GND_S)", c.u1.landpattern.p4, (secondary,)),
        ("J2 pad 1 (V3V3)", c.j2.landpattern.p1, (secondary,)),
        ("J2 pad 2 (GND_S)", c.j2.landpattern.p2, (secondary,)),
    ):
        g = L.pad_world(rd, pad)
        for s in side:
            s[0].append(g)

    # The fixture's through vias have copper on every layer.
    vias = {id(v): (t, v) for t, v in visit(rd.root, Via)}
    for group, side in ((c.primary_anchors, (primary, gnd_p)), (c.secondary_anchors, (secondary,))):
        for v in group:
            t, cv = vias[id(v)]
            if t.transform is None or cv.transform is None:
                raise ValueError(f"unresolved frame for the via at {t.path}")
            x, y = (t.transform * cv.transform).translation
            g = Point(float(x), float(y)).buffer(VIA_PAD / 2)
            for s in side:
                for layer in LAYERS:
                    s[layer].append(g)

    for layer in LAYERS:
        if not primary[layer] or not secondary[layer]:
            continue
        gap = L.gap(shapely.union_all(primary[layer]), shapely.union_all(secondary[layer]))
        print(f"layer {layer}: primary to secondary copper {gap}")
        if gap < BARRIER - TOL:
            L.fail(f"layer {layer}: primary copper {gap} from secondary copper, below the {BARRIER} barrier clearance")
        else:
            L.ok(f"layer {layer}: barrier {gap}")

    if c.vin_route.traces:
        layer = c.vin_route.layer
        gap = L.gap(L.route_geom(c.vin_route), shapely.union_all(gnd_p[layer]))
        print(f"layer {layer}: VIN48 route to GND_P copper {gap}")
        if gap < HOUSE_48V - TOL:
            L.fail(f"layer {layer}: the 48 V route is {gap} from GND_P copper, below the house {HOUSE_48V}")
        else:
            L.ok(f"layer {layer}: 48 V spacing {gap}")
L.finish()
