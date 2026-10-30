#!/usr/bin/env python3
"""Self-test of the typed-ports reference: its composition checks, and pyright over
this file and design.py. Offline: no runtime, no parts DB.

Exit 0 = every check passed. Exit 1 = a check failed.

Run:  python3 skills/jitx-circuit-builder/evals/cases/reference/typed-ports/check.py
"""

import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import jitx.test
from design import Board, McuCircuit, MixedTypes, RegulatorCircuit, SensorCircuit
from jitx import Circuit, Net
from jitx.common import Power
from jitx.inspect import decompose
from jitx.net import Port
from jitxlib.protocols.serial import I2C


def joined(circuit: Circuit, a: Port, b: Port) -> bool:
    """Whether some net the circuit holds, under any attribute name, carries both ports."""
    return any(
        a in members and b in members
        for members in (list(n) for n in decompose(circuit, Net))
    )


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
        rail = list(self.b.VSYS)
        self.assertEqual(len(rail), 3)
        for port in (self.b.reg.vout, self.b.mcu.vin, self.b.sensor.vin):
            self.assertIn(port, rail)

    def test_regulator_input_is_not_on_the_output_rail(self) -> None:
        self.assertNotIn(self.b.reg.vin, list(self.b.VSYS))
        self.assertIn(self.b.reg.vin, list(self.b.VIN))

    def test_bus_joins_the_two_i2c_bundles(self) -> None:
        bus = list(self.b.I2C)
        self.assertEqual(len(bus), 2)
        self.assertIn(self.b.mcu.i2c, bus)
        self.assertIn(self.b.sensor.i2c, bus)

    def test_each_child_carries_its_boundary_to_the_pins(self) -> None:
        s = self.b.sensor
        self.assertTrue(joined(s, s.vin.Vp, s.u1.VDD))
        self.assertTrue(joined(s, s.i2c.sda, s.u1.SDA))
        self.assertTrue(joined(s, s.i2c.scl, s.u1.SCL))
        r = self.b.reg
        self.assertTrue(joined(r, r.vout.Vp, r.u1.VOUT))
        m = self.b.mcu
        self.assertTrue(joined(m, m.vin.Vp, m.u1.VDD))
        self.assertTrue(joined(m, m.i2c, m.u1.i2c))

    def test_mixed_bundle_types_refuse_to_net(self) -> None:
        """Guards the skill's rule that a port nets only to its own concrete type."""
        with self.assertRaises(ValueError):
            MixedTypes()

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
