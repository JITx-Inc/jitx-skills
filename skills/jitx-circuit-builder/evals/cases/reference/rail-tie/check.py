#!/usr/bin/env python3
"""Self-test of the rail-tie reference: its connectivity checks, and pyright over
this file and design.py. Offline: no runtime, no parts DB.

Exit 0 = every check passed. Exit 1 = a check failed. Exit 2 = usage error.

Run:  python3 skills/jitx-circuit-builder/evals/cases/reference/rail-tie/check.py
"""

import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import jitx.test
from design import (
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

    def test_reference_type_checks(self) -> None:
        """The reference and this file type-check against the installed JITX package."""
        files = [str(HERE / "design.py"), str(HERE / "check.py")]
        proc = subprocess.run(
            [sys.executable, "-m", "pyright", "--pythonpath", sys.executable, *files],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    result = unittest.main(argv=["check"], exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
