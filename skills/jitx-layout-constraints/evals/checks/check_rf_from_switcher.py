"""Check for the rf-from-switcher case.

Usage: check_rf_from_switcher.py <output-dir>

Builds <output>/fixture_rf_from_switcher.py, captures it, and checks:

- a two-condition clearance rule of at least the prompt's 2.5 exists with
  one condition naming a tag that sits on the feed (the RF_ANT net, the feed
  route, the U.FL circuit or its part, or the series inductor) and the other a tag that sits
  on the switch node (its net, its pour or the regulator circuit), so it
  relates the feed to the switcher rather than either one to everything;
- the feed is still realized;
- the switch-node pour's computed copper sits at least 2.5 from the feed
  trace (the reference solution measured 2.5028). Only the trace is
  measured, not the feed's pads. There is no upper bound: a pour held
  farther back, for instance by also keeping 2.5 from the inductor's pads,
  still meets the prompt;
- the feed's layer-0 GND pour stays at the board's default gap, fab row 4's
  0.100 plus the runtime's 0.01, at most 0.14: a clearance from the feed to
  AnyObject would push its own ground back.

In this suite's own run (2026-11-03) a clearance(RF tag, AnyObject) of 2.5
made the feed unrealizable ("Unrealizable Route: Insufficient space"), which
fails the second item.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Any  # noqa: E402

from jitx.constraints import (  # noqa: E402
    AndExpr,
    AtomExpr,
    BinaryDesignConstraint,
    BoolExpr,
    BuiltinTag,
    OrExpr,
    _ApplyTag,
)
from jitx.inspect import extract  # noqa: E402

import lc_check as L  # noqa: E402

KEEP = 2.5
GND_GAP_MAX = 0.100 + 0.01 + 0.03


def named_tags(expr: BoolExpr) -> set[type]:
    """User tag types every object the expression matches must carry one of.

    An AND narrows, so it keeps what either side names. An OR names nothing
    unless both sides do: ``RfFeed() | IsCopper`` matches all copper. A
    negation, a builtin or AnyObject names nothing.
    """
    if isinstance(expr, AtomExpr):
        atom = expr.atom
        return set() if isinstance(atom, BuiltinTag) else {type(atom)}
    if isinstance(expr, AndExpr):
        return named_tags(expr.left) | named_tags(expr.right)
    if isinstance(expr, OrExpr):
        left, right = named_tags(expr.left), named_tags(expr.right)
        return left | right if left and right else set()
    return set()


def covers(named: set[type], assigned: set[type]) -> bool:
    """A rule on a tag also matches its subclasses (jitx ``Tag`` docstring)."""
    return any(issubclass(a, n) for a in assigned for n in named)


def tags_on(root: Any, objs: list[Any]) -> set[type]:
    """User tag types assigned anywhere under root to one of objs."""
    targets = [o for o in objs if o is not None]
    found: set[type] = set()
    for rec in extract(root, _ApplyTag):
        if any(rec.target is o for o in targets):
            found |= {type(x) for x in rec.tags.tags if not isinstance(x, BuiltinTag)}
    return found


out = L.output_dir()
with L.built(out, "fixture_rf_from_switcher", "RfFromSwitcherDesign") as rd:
    c = rd.root.circuit
    feed_tags = tags_on(
        rd.root,
        [
            c.ANT,
            c.feed,
            getattr(c, "feed_escape", None),
            c.ufl,
            c.ufl.component,
            c.ufl.L,
        ],
    )
    sw_tags = tags_on(rd.root, [c.reg.SW_NODE, c.reg.sw_pour, c.reg])
    print(f"tags on the feed: {sorted(t.__name__ for t in feed_tags)}")
    print(f"tags on the switch node: {sorted(t.__name__ for t in sw_tags)}")

    def relates(r: BinaryDesignConstraint) -> bool:
        a, b = named_tags(r.first), named_tags(r.second)
        return (covers(a, feed_tags) and covers(b, sw_tags)) or (
            covers(b, feed_tags) and covers(a, sw_tags)
        )

    pair_rules = [
        r
        for r in L.rules(rd.root)
        if isinstance(r, BinaryDesignConstraint)
        and r.clearance_constraint is not None
        and r.clearance_constraint.clearance >= KEEP - 1e-9
        and relates(r)
    ]
    print(f"feed-to-switcher clearance rules of at least {KEEP}: {len(pair_rules)}")
    if not pair_rules:
        L.fail(
            f"no clearance of at least {KEEP} between a feed tag and a switch-node tag"
        )
    widths = L.trace_widths(c.feed)
    print(f"feed widths: {widths}")
    if not widths:
        L.fail("the feed has no realized traces")
    else:
        feed = L.route_geom(c.feed)
        found = {
            p is c.reg.sw_pour: g
            for _, p, g in L.world_pours(rd)
            if p is c.reg.sw_pour or p is c.pours[0]
        }
        sw_g, gnd_g = found.get(True), found.get(False)
        if sw_g is None or sw_g.is_empty:
            L.fail("the switch-node pour's computed copper was not found")
        else:
            gap = L.gap(sw_g, feed)
            print(f"switch-node pour gap to the feed: {gap}")
            if gap >= KEEP - 1e-3:
                L.ok(f"switch-node copper {gap} from the feed")
            else:
                L.fail(
                    f"switch-node copper {gap} from the feed, expected at least {KEEP}"
                )
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
