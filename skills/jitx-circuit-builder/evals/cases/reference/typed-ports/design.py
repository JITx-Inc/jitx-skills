"""Reference: three sub-circuits composed through typed boundary ports.

A regulator's `Power` output feeds an MCU and a sensor, and the MCU's `I2C`
bundle reaches the sensor's, all port to port at the top level. The parts are
stand-ins with bare ports: the shape of the composition is under test, not the
parts. Everything here instantiates offline: no runtime, no parts database.
"""

import jitx
from jitx import Circuit, Net
from jitx.common import Power
from jitx.net import Port
from jitxlib.protocols.serial import I2C


class Ldo(jitx.Component):
    VIN = Port()
    VOUT = Port()
    GND = Port()


class Mcu(jitx.Component):
    VDD = Port()
    VSS = Port()
    i2c = I2C()


class Sensor(jitx.Component):
    VDD = Port()
    GND = Port()
    SDA = Port()
    SCL = Port()


class RegulatorCircuit(Circuit):
    vin = Power()
    vout = Power()

    def __init__(self) -> None:
        self.u1 = Ldo()
        self.VIN = Net([self.vin.Vp, self.u1.VIN], name="VIN")
        self.VOUT = Net([self.vout.Vp, self.u1.VOUT], name="VOUT")
        self.GND = Net([self.vin.Vn, self.vout.Vn, self.u1.GND], name="GND")


class McuCircuit(Circuit):
    vin = Power()
    i2c = I2C()

    def __init__(self) -> None:
        self.u1 = Mcu()
        self.VDD = Net([self.vin.Vp, self.u1.VDD], name="VDD")
        self.GND = Net([self.vin.Vn, self.u1.VSS], name="GND")
        self.I2C = self.i2c + self.u1.i2c  # a bundle nets to the same bundle type


class SensorCircuit(Circuit):
    vin = Power()
    i2c = I2C()

    def __init__(self) -> None:
        self.u1 = Sensor()
        self.VDD = Net([self.vin.Vp, self.u1.VDD], name="VDD")
        self.GND = Net([self.vin.Vn, self.u1.GND], name="GND")
        self.SDA = Net([self.i2c.sda, self.u1.SDA], name="SDA")
        self.SCL = Net([self.i2c.scl, self.u1.SCL], name="SCL")


class Board(Circuit):
    """The parent wires its children's boundary ports and never their components."""

    vin = Power()

    def __init__(self) -> None:
        self.reg = RegulatorCircuit()
        self.mcu = McuCircuit()
        self.sensor = SensorCircuit()
        self.input = self.vin + self.reg.vin
        self.rail = self.reg.vout + self.mcu.vin + self.sensor.vin
        self.i2c = self.mcu.i2c + self.sensor.i2c


class MixedTypes(Circuit):
    """Support for the type guard in check.py: a Power port netted to an I2C bundle."""

    vin = Power()
    i2c = I2C()

    def __init__(self) -> None:
        self.bad = Net([self.vin, self.i2c])
