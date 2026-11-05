"""Check for the rf-from-switcher case.

Usage: check_rf_from_switcher.py <output-dir>

Builds <output>/fixture_rf_from_switcher.py, captures it, and checks:

- a two-condition clearance rule of at least the prompt's 2.5 exists with
  neither condition AnyObject (TrueExpr), so it relates the feed to the
  switcher rather than the feed to everything;
- the feed is still realized;
- the switch-node pour's computed copper sits 2.5 from the feed, within
  [2.5, 2.53] (measured on jitx 4.6, pour pullback sits at the rule's value
  plus 0.01);
- the feed's layer-0 GND pour is not pushed back past the clearance the
  output's own rules give it. The cap is the larger of fab row 4's 0.100 (the
  floor, where no rule matches) and the largest clearance rule in the output
  whose conditions match the feed and that pour
  (``lc_check.matching_clearances``), plus the runtime's 0.01, plus 0.03
  tolerance. So a board rule such as a copper-to-copper default raises the
  cap by its own value, and the switch-node keep-away, which does not match
  GND copper, does not raise it.

In this suite's own run (2026-11-03) a clearance(RF tag, AnyObject) of 2.5
made the feed unrealizable ("Unrealizable Route: Insufficient space"), which
fails the second item.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jitx.constraints import BinaryDesignConstraint, TrueExpr  # noqa: E402

import lc_check as L  # noqa: E402

KEEP = 2.5
FLOOR = 0.100  # fab sheet row 4

out = L.output_dir()
allowed: list[float] = []


def ground_cap(rd: Any) -> None:
    """The largest clearance the output's rules give the feed against its
    layer-0 GND pour, or the fab floor; read before capture."""
    c = rd.root.circuit
    feed_on = L.copper_facts(rd, L.TRACE, 0, c.feed, c.ANT, c)
    gnd_on = L.copper_facts(rd, L.POUR, 0, c.pours[0], c.GND, c)
    print(f"tags on the feed: {feed_on.tags}; on its GND pour: {gnd_on.tags}")
    matching = L.matching_clearances(rd, feed_on, gnd_on)
    print(f"clearance rules matching the feed and its GND pour: {matching}")
    allowed.append(max([FLOOR] + [r.clearance_constraint.clearance for r in matching if r.clearance_constraint]))


with L.built(out, "fixture_rf_from_switcher", "RfFromSwitcherDesign", before_capture=ground_cap) as rd:
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
            gnd_gap_max = allowed[0] + 0.01 + 0.03
            gap = L.gap(gnd_g, feed)
            print(f"layer-0 GND pour gap to the feed: {gap}, cap {gnd_gap_max:.3f}")
            if gap > gnd_gap_max:
                L.fail(f"the feed's own ground is pushed back to {gap}, past {allowed[0]} + 0.01")
            else:
                L.ok(f"the feed's ground stays at {gap}")
L.finish()
