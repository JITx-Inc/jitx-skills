"""Check for the route-config-length case.

Usage: check_route_config_length.py <output-dir>

Builds <output>/fixture_route_config_length.py, captures it, and checks the
two lines against the prompt:

- every route realized on layer 0;
- CLK: one connected piece of routed copper joins its two pads (the
  ``PadChip`` pads at y 10), every trace in it 0.25 wide (the prompt's
  width), and the L1 pour stands 0.35 to 0.37 from the trace away from the
  pads (the prompt's spacing; a ``Route.Config`` trace space sets the pour's
  pullback from the trace, measured 0.402 for 0.4 in spike C4);
- DATA: one connected piece joins its two pads (y -8). At least one of its
  routes carries ``Route.Config(envelope_overhead=3.0)`` (the prompt's
  3 mm), and that section's copper stays within half the envelope plus half
  the trace (1.5 + 0.15) of the chord between its two ends (spike C2: the
  envelope is the total extra width, half on each side). Every other DATA
  route lies within half its trace width of its own chord: no length is
  drawn by hand with control points;
- the issue report has no ``UnmetTime``, ``UnmetTimeDiff`` or
  ``UnsquiggledRoute``: the 300 ps constraint the fixture carries is met;
- no Copper or OverlappableCopper is drawn in code.
"""

import sys
from pathlib import Path

import shapely
from shapely.geometry import LineString, box

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cl_check as L  # noqa: E402

CLK_WIDTH = 0.25
CLK_SPACE = 0.35
ENVELOPE = 3.0
TOL = 0.01

out = L.output_dir()
with L.built(out, "fixture_route_config_length", "RouteConfigLengthDesign") as rd:
    from cl_parts import PadChip

    pads = L.chip_pads(rd, PadChip)
    clk_pads = sorted([p for p in pads if abs(p.centroid.y - 10.0) < 0.5], key=lambda g: g.centroid.x)
    data_pads = sorted([p for p in pads if abs(p.centroid.y + 8.0) < 0.5], key=lambda g: g.centroid.x)
    routes = L.realized_routes(rd, layer=0)
    geoms = {path: L.route_geom(r) for path, r in routes}
    copper = shapely.union_all(list(geoms.values())) if geoms else shapely.Polygon()

    clk = L.piece_touching(copper, *clk_pads) if len(clk_pads) == 2 else None
    if clk is None:
        L.fail("no connected piece of routed copper joins the two CLK pads")
    else:
        widths = sorted({w for path, r in routes if geoms[path].intersects(clk) for w in L.trace_widths(r)}, key=str)
        print(f"CLK trace widths {widths}")
        if any(w is None or abs(w - CLK_WIDTH) > 1e-3 for w in widths):
            L.fail(f"CLK trace widths {widths}, not {CLK_WIDTH}")
        pour = shapely.union_all([g for _, p, g in L.world_pours(rd) if int(p.layer) == 0])
        mid = clk.intersection(box(-19.0, 0.0, 19.0, 20.0))
        g = L.gap(pour, mid) if not pour.is_empty and not mid.is_empty else None
        print(f"CLK pour gap {g}")
        if g is None or not (CLK_SPACE - 1e-3 <= g <= CLK_SPACE + 0.02):
            L.fail(f"L1 pour {g} from the CLK trace, not {CLK_SPACE}")

    data = L.piece_touching(copper, *data_pads) if len(data_pads) == 2 else None
    if data is None:
        L.fail("no connected piece of routed copper joins the two DATA pads")
    else:
        sections = 0
        chords = 0.0
        for path, r in routes:
            if not geoms[path].intersects(data):
                continue
            env = getattr(r.config, "envelope_overhead", None) if r.config is not None else None
            ends = L.trace_ends(r)
            w = max((x for x in L.trace_widths(r) if x is not None), default=0.0)
            if not ends:
                L.fail(f"{path}: no trace ends read")
                continue
            chord = LineString(ends[0])
            chords += chord.length
            if env:
                if abs(env - ENVELOPE) < 1e-6:
                    sections += 1
                reach = env / 2 + w / 2
                off = geoms[path].difference(chord.buffer(reach + TOL)).area
                lateral = max(chord.distance(shapely.Point(c)) for c in shapely.get_coordinates(geoms[path]))
                print(
                    f"{path}: envelope {env}, chord {chord.length:.3f}, copper reaches {lateral:.4f} from it (limit {reach:.4f})"
                )
                if off > 1e-4:
                    L.fail(f"{path}: copper leaves the {env} envelope ({off:.4f} mm2 outside {reach:.3f} of the chord)")
            else:
                off = geoms[path].difference(chord.buffer(w / 2 + TOL)).area
                if off > 1e-4:
                    L.fail(
                        f"{path}: not straight between its ends ({off:.4f} mm2 off the chord) with no length-matching Config"
                    )
        span = data_pads[0].centroid.distance(data_pads[1].centroid)
        print(f"DATA chords add to {chords:.3f} over {span:.3f} between the pads")
        if chords > 1.05 * span:
            L.fail(
                f"DATA chords add to {chords:.3f}, over 5% more than the {span:.3f} between its pads: length added by hand"
            )
        if sections == 0:
            L.fail(f"no DATA route carries Route.Config(envelope_overhead={ENVELOPE})")
    text = L.issues_text(rd)
    bad = L.issue_kinds(text, "signal constraint", "UnmetTime", "UnsquiggledRoute")
    print("issues:", text.strip().splitlines()[:6])
    if bad:
        L.fail(f"timing issues: {bad}")
    L.no_authored_copper(rd, "a code route and a configured section were asked for")
L.finish()
