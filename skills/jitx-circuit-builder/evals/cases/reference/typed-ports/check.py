#!/usr/bin/env python3
"""Composition checks for the typed-ports reference. Offline: no runtime, no parts DB.

Exit 0 = every check passed. Exit 1 = a check failed.

Run:  python3 skills/jitx-circuit-builder/evals/cases/reference/typed-ports/check.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jitx.test
from design import Board, McuCircuit, MixedTypes, RegulatorCircuit, SensorCircuit
from jitx import Circuit
from jitx.common import Power
from jitx.inspect import decompose
from jitxlib.protocols.serial import I2C


class TypedPortChecks(jitx.test.TestCase):
    """A bundle net lists its bundles; each child then carries the members inward."""

    def setUp(self) -> None:
        self.b = Board()

    def test_hierarchy_holds_three_subcircuits(self) -> None:
        children = list(decompose(self.b, Circuit))
        self.assertEqual(len(children), 3)
        self.assertIsInstance(self.b.reg, RegulatorCircuit)
        self.assertIsInstance(self.b.mcu, McuCircuit)
        self.assertIsInstance(self.b.sensor, SensorCircuit)

    def test_boundaries_are_typed(self) -> None:
        for child in (self.b.reg, self.b.mcu, self.b.sensor):
            self.assertIsInstance(child.vin, Power)
        self.assertIsInstance(self.b.reg.vout, Power)
        self.assertIsInstance(self.b.mcu.i2c, I2C)
        self.assertIsInstance(self.b.sensor.i2c, I2C)

    def test_regulator_output_feeds_both_consumers(self) -> None:
        rail = list(self.b.rail)
        self.assertEqual(len(rail), 3)
        for port in (self.b.reg.vout, self.b.mcu.vin, self.b.sensor.vin):
            self.assertIn(port, rail)

    def test_regulator_input_is_not_on_the_output_rail(self) -> None:
        self.assertNotIn(self.b.reg.vin, list(self.b.rail))
        self.assertIn(self.b.reg.vin, list(self.b.input))

    def test_bus_joins_the_two_i2c_bundles(self) -> None:
        bus = list(self.b.i2c)
        self.assertEqual(len(bus), 2)
        self.assertIn(self.b.mcu.i2c, bus)
        self.assertIn(self.b.sensor.i2c, bus)

    def test_each_child_carries_its_boundary_to_the_pins(self) -> None:
        s = self.b.sensor
        self.assertIn(s.u1.VDD, list(s.VDD))
        self.assertIn(s.vin.Vp, list(s.VDD))
        self.assertIn(s.u1.SDA, list(s.SDA))
        self.assertIn(s.i2c.sda, list(s.SDA))
        r = self.b.reg
        self.assertIn(r.vout.Vp, list(r.VOUT))
        self.assertIn(r.u1.VOUT, list(r.VOUT))

    def test_mixed_bundle_types_refuse_to_net(self) -> None:
        """Guards the skill's rule that a port nets only to its own concrete type."""
        with self.assertRaises(ValueError):
            MixedTypes()


if __name__ == "__main__":
    result = unittest.main(argv=["check"], exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
