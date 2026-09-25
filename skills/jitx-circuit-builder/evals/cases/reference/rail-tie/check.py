#!/usr/bin/env python3
"""Connectivity checks for the rail-tie reference. Offline: no runtime, no parts DB.

Exit 0 = every check passed. Exit 1 = a check failed. Exit 2 = usage error.

Run:  python3 skills/jitx-circuit-builder/evals/cases/reference/rail-tie/check.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jitx.test  # noqa: E402
from design import (  # noqa: E402
    CORE_BALLS,
    GND_BALLS,
    RSVD_GND_BALLS,
    NestedNetFirst,
    RailTie,
)


class RailTieChecks(jitx.test.TestCase):
    """Connectivity is the one property neither pyright nor a build reliably catches."""

    def setUp(self) -> None:
        self.c = RailTie()

    def test_ground_rail_carries_every_ball(self) -> None:
        """Count, don't just contain: a membership check cannot see a lost half-rail."""
        members = list(self.c.GND)
        self.assertEqual(len(members), GND_BALLS + RSVD_GND_BALLS)

    def test_core_rail_carries_every_ball_and_the_aux_pin(self) -> None:
        members = list(self.c.V1V0)
        self.assertEqual(len(members), CORE_BALLS + 1)

    def test_every_named_port_is_reachable_by_iteration(self) -> None:
        """Assert over list(net) — `in` can false-negative, see test_in_is_unreliable."""
        gnd = list(self.c.GND)
        for ball in [*self.c.u1.GND, *self.c.u1.RSVDGND]:
            self.assertIn(ball, gnd)
        core = list(self.c.V1V0)
        for ball in self.c.u1.VCCINT:
            self.assertIn(ball, core)
        self.assertIn(self.c.u1.VCCAUX, core)

    def test_rails_are_not_shorted(self) -> None:
        gnd = list(self.c.GND)
        for ball in self.c.u1.VCCINT:
            self.assertNotIn(ball, gnd)

    def test_in_is_unreliable_so_the_iterate_rule_is_load_bearing(self) -> None:
        """`Net.__contains__` stops at the first nested net, so members after it vanish.

        This guards the rule rather than the design: if a jitx release ever makes
        `in` agree with iteration, this test fails and the skill's advice can be
        revisited. Until then it documents why every assertion above uses list().
        """
        c = NestedNetFirst()
        self.assertIn(c.t, list(c.top), "iteration must find the port")
        self.assertFalse(
            bool(c.t in c.top),
            "`in` agreed with iteration — the upstream defect may be fixed; "
            "re-check the skill's iterate-don't-use-`in` rule against this release",
        )


if __name__ == "__main__":
    result = unittest.main(argv=["check"], exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
