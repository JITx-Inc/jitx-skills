"""Check for the rule-did-not-fire case.

Usage: check_rule_did_not_fire.py <output-dir>

Builds <output>/fixture_rule_did_not_fire.py, captures it, and checks:

- the VIN route between the two input capacitors is realized, every trace
  shape has a width (a Polygon would mean the width did not fit, spike S8),
  and every width is the prompt's 0.5;
- the board's 0.15 default trace width rule is still in the design, so the
  fix did not remove the default to let the rail rule through.

On the bare fixture (2026-11-03, this suite's own run) the route came back at
0.15 with every rule at priority 0.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jitx.constraints import UnaryDesignConstraint  # noqa: E402

import lc_check as L  # noqa: E402

WIDTH = 0.5
DEFAULT = 0.15

out = L.output_dir()
with L.built(out, "fixture_rule_did_not_fire", "RuleDidNotFireDesign") as rd:
    widths = L.trace_widths(rd.root.circuit.vin_route)
    print(f"VIN route widths: {widths}")
    if not widths:
        L.fail("the VIN route has no realized traces")
    elif any(w is None for w in widths):
        L.fail("a VIN trace came back as a shape with no width")
    elif any(abs(w - WIDTH) > 1e-3 for w in widths if w is not None):
        L.fail(f"VIN route widths {widths}, not {WIDTH}")
    else:
        L.ok(f"VIN route realized at {WIDTH}")
    defaults = [
        c
        for c in L.rules(rd.root)
        if isinstance(c, UnaryDesignConstraint)
        and c.trace_width_constraint is not None
        and abs(c.trace_width_constraint.width - DEFAULT) < 1e-9
    ]
    if not defaults:
        L.fail(f"the board's {DEFAULT} default trace width rule is gone")
    else:
        L.ok(f"the {DEFAULT} default trace width rule is still there")
L.finish()
