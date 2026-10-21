"""Binds SampleSubstrate on a design of its own, not board.py's substrate."""

from jitx.board import Board
from jitx.circuit import Circuit
from jitx.design import Design
from jitx.sample import SampleSubstrate
from jitx.shapes.composites import rectangle


class Outline(Board):
    shape = rectangle(20, 10)


class Empty(Circuit):
    pass


class SmokeTest(Design):
    substrate = SampleSubstrate()
    board = Outline()
    circuit = Empty()
