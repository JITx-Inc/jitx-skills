"""Check for the rf-from-switcher case.

Usage: check_rf_from_switcher.py <output-dir>

Builds <output>/fixture_rf_from_switcher.py, captures it, and checks:

- a two-condition clearance rule of at least the prompt's 2.5 exists with
  neither condition AnyObject (TrueExpr), so it relates the feed to the
  switcher rather than the feed to everything;
- the feed is still realized;
- the switch-node pour's computed copper sits 2.5 from the feed, within
  [2.5, 2.53] (pour pullback is the one headless witness of a clearance rule
  between nets, spike S6, at the rule's value plus 0.01, S9);
- the feed's layer-0 GND pour stays at the board's default gap, fab row 4's
  0.100 plus the runtime's 0.01, at most 0.14: a clearance from the feed to
  AnyObject would push its own ground back (S9).

In this suite's own run (2026-11-03) a clearance(RF tag, AnyObject) of 2.5
made the feed unrealizable ("Unrealizable Route: Insufficient space"), which
fails the second item.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jitx.constraints import BinaryDesignConstraint, TrueExpr  # noqa: E402

import lc_check as L  # noqa: E402

KEEP = 2.5
GND_GAP_MAX = 0.100 + 0.01 + 0.03

out = L.output_dir()
with L.built(out, "fixture_rf_from_switcher", "RfFromSwitcherDesign") as rd:
    c = rd.root.circuit
    pair_rules = [
        r
        for r in L.rules(rd.root)
        if isinstance(r, BinaryDesignConstraint)
        and r.clearance_constraint is not None
        and r.clearance_constraint.clearance >= KEEP - 1e-9
        and not isinstance(r.first, TrueExpr)
        and not isinstance(r.second, TrueExpr)
    ]
    print(f"two-condition clearance rules of at least {KEEP}: {len(pair_rules)}")
    if not pair_rules:
        L.fail(f"no two-condition clearance of at least {KEEP} between named classes")
    widths = L.trace_widths(c.feed)
    print(f"feed widths: {widths}")
    if not widths:
        L.fail("the feed has no realized traces")
    else:
        feed = L.route_geom(c.feed)
        found = {p is c.reg.sw_pour: g for _, p, g in L.world_pours(rd) if p is c.reg.sw_pour or p is c.pours[0]}
        sw_g, gnd_g = found.get(True), found.get(False)
        if sw_g is None or sw_g.is_empty:
            L.fail("the switch-node pour's computed copper was not found")
        else:
            gap = L.gap(sw_g, feed)
            print(f"switch-node pour gap to the feed: {gap}")
            if KEEP - 1e-3 <= gap <= KEEP + 0.03:
                L.ok(f"switch-node copper {gap} from the feed")
            else:
                L.fail(f"switch-node copper {gap} from the feed, expected {KEEP} (+0.01)")
        if gnd_g is None or gnd_g.is_empty:
            L.fail("the layer-0 GND pour's computed copper was not found")
        else:
            gap = L.gap(gnd_g, feed)
            print(f"layer-0 GND pour gap to the feed: {gap}")
            if gap > GND_GAP_MAX:
                L.fail(f"the feed's own ground is pushed back to {gap}")
            else:
                L.ok(f"the feed's ground stays at {gap}")
L.finish()
