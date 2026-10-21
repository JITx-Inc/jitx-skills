"""Binds the board.py substrate on a design of its own."""

from jitx.board import Board
from jitx.circuit import Circuit
from jitx.design import Design
from jitx.shapes.composites import rectangle

from board import TwoLayerSubstrate


class Outline(Board):
    shape = rectangle(20, 10)


class Empty(Circuit):
    pass


class SmokeTest(Design):
    substrate = TwoLayerSubstrate()
    board = Outline()
    circuit = Empty()
