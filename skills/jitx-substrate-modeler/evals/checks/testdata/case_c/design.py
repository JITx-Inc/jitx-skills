"""Known-good test design for case C: the case's board, ground net and fenced
cavity. Test data for test_grade_fenced_rf.py."""

from board import CavityFence, RFSubstrate
from jitx import Pour
from jitx.board import Board
from jitx.circuit import Circuit
from jitx.design import Design
from jitx.feature import KeepOut
from jitx.layerindex import LayerSet
from jitx.net import Net
from jitx.shapes.composites import rectangle

CAVITY = rectangle(4.0, 3.0).at(5.0, 3.0)


class RFBoard(Board):
    shape = rectangle(30.0, 20.0)
    signal_area = rectangle(29.4, 19.4)


class RFCircuit(Circuit):
    def __init__(self) -> None:
        self.GND = Net(name="GND")
        self.cavity_pour = Pour(CAVITY, layer=0)
        CavityFence().assign(self.cavity_pour)
        self.GND += self.cavity_pour
        self.cavity_keepout = KeepOut(CAVITY, layers=LayerSet(0), pour=True, via=True)


class RFDesign(Design):
    board = RFBoard()
    substrate = RFSubstrate()
    circuit = RFCircuit()
