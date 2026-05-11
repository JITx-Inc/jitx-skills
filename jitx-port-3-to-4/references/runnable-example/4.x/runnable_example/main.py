from jitx.circuit import Circuit
from jitx.sample import SampleDesign
from jitxlib.parts import Resistor
from jitx.units import ohm


class SimpleCircuit(Circuit):
    def __init__(self):
        self.r1 = Resistor(resistance=1000 * ohm)
        self.r2 = Resistor(resistance=1000 * ohm)
        self.SIG = self.r1.p2 + self.r2.p1


class runnable_example(SampleDesign):
    circuit = SimpleCircuit()
