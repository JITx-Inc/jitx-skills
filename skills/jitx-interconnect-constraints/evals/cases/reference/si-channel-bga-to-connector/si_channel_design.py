"""Reference for the si-channel-bga-to-connector eval case.

Two TX differential pairs leave a BGA ball on the top layer, drop through an
escape via to the bottom layer, pass through an AC coupling capacitor, and end
at a connector. Every connection is a plain net; no ``>>`` topology is
declared. ``Topology(begin, end)`` names the two ends of each constrained path,
the runtime infers the path between them from the code routes, and the pin
models carry the delay and loss of the BGA package, the via, the capacitor and
the connector.

All three parts are fictional fixtures, not real products. Their pin-model
values are the fixture values the case prompt supplies; the timing and loss
limits are fixture values chosen so this reference passes with margin.

The board is ``jitx.sample.SampleSubstrate``: two copper layers, ``DRS_100``
on both, and ``THVia`` (layer 0 to layer 1). Its bottom layer is the routing
layer the prompt names.

Variants, one Design class each:

- ``SiChannelDesign``: the reference. Every constraint measures and passes.
- ``CapNoModelDesign``: the capacitor on ``tx0.p`` has no bridging pin model,
  so that path stops at the capacitor.
- ``NoRoutesDesign``: no code routes, so no path can be inferred.
- ``NoTerminationDesign``: the BGA and connector carry no terminating pin
  models. Same routes, so each path's delay and loss drop by exactly the two
  terminations.
- ``IdealViaDesign``: the escape via's model is zero delay and zero loss.
  Same routes, so each path's delay and loss drop by exactly the via model.
- ``NoViaModelDesign``: the escape via carries no model. The runtime measures
  with a placeholder model and reports that it did.

``SiChannelDesign`` is the reference; ``NoTerminationDesign`` and
``IdealViaDesign`` are probes that prove the models move the numbers; the
other three are mutations the check must reject.
"""

from jitx.circuit import Circuit, Route
from jitx.component import Component
from jitx.feature import Courtyard, Soldermask
from jitx.landpattern import Landpattern, Pad, PadMapping
from jitx.layerindex import Side
from jitx.net import DiffPair, Net, Port, PortAttachment, Topology
from jitx.sample import SampleDesign, SampleSubstrate
from jitx.shapes.composites import rectangle
from jitx.shapes.primitive import Circle
from jitx.si import (
    BridgingPinModel,
    ConstrainDiffPair,
    ConstrainReferenceDifference,
    PinModel,
    TerminatingPinModel,
)
from jitx.symbol import Direction, Pin, Symbol
from jitx.via import Via

# Fixture pin-model values, as the case prompt supplies them (seconds, dB).
BGA_TX_DELAY = 30e-12
BGA_TX_LOSS = 0.1
VIA_DELAY = 8e-12
VIA_LOSS = 0.05
CAP_DELAY = 5e-12
CAP_LOSS = 0.1
CONN_TX_DELAY = 20e-12
CONN_TX_LOSS = 0.15

# Fixture constraint values (seconds, dB).
INTRA_PAIR_SKEW = 1e-12
BUNDLE_SKEW = 5e-12
TIMING_LIMIT = 400e-12
LOSS_LIMIT = 2.0

# Row pitch shared by the BGA TX column, the vias, the capacitors and the
# connector. Every leg is then the same shape shifted in y, so the four legs
# have equal routed length and the skew limits pass by construction.
PITCH = 1.0
ROWS = (1.5, 0.5, -0.5, -1.5)  # tx0.p, tx0.n, tx1.p, tx1.n

BGA_X = -15.0
VIA_X = BGA_X + 1.5  # one pitch outboard of the TX ball column at BGA_X + 0.5
CAP_X = 0.0
CONN_X = 15.0


class BallPad(Pad):
    shape = Circle(diameter=0.45)
    soldermask = Soldermask(Circle(diameter=0.55))


class SmdPad(Pad):
    shape = rectangle(0.6, 0.6)
    soldermask = Soldermask(rectangle(0.7, 0.7))


class BoxSymbol(Symbol):
    def __init__(self, pin_count: int) -> None:
        self.pins = [
            Pin(at=(-1, i - pin_count // 2), length=1, direction=Direction.Left)
            for i in range(pin_count)
        ]
        self.draw = rectangle(2, pin_count + 1)


class BgaLandpattern(Landpattern):
    """Two columns of four balls at 1.0 mm pitch: TX on the right, GND on the left."""

    def __init__(self) -> None:
        self.tx_balls = [BallPad().at(0.5, y) for y in ROWS]
        self.gnd_balls = [BallPad().at(-0.5, y) for y in ROWS]
        self.court = Courtyard(rectangle(2.5, 4.5))


class FixtureFpgaBga(Component):
    """Fictional FPGA-like BGA fragment: two TX diff pairs and four ground balls.

    Not a real product. Each TX pin carries a terminating pin model for the
    package path from die to ball (fixture values from the case prompt).
    """

    tx0 = DiffPair()
    tx1 = DiffPair()
    gnd = [Port() for _ in range(4)]

    def __init__(self, terminate: bool = True) -> None:
        self.landpattern = BgaLandpattern()
        self.symbol = BoxSymbol(8)
        tx_pins = [self.tx0.p, self.tx0.n, self.tx1.p, self.tx1.n]
        self.mapping = PadMapping(
            list(zip(tx_pins, self.landpattern.tx_balls, strict=True))
            + list(zip(self.gnd, self.landpattern.gnd_balls, strict=True))
        )
        if terminate:
            self.package = [
                TerminatingPinModel(p, delay=BGA_TX_DELAY, loss=BGA_TX_LOSS)
                for p in tx_pins
            ]


class CapLandpattern(Landpattern):
    """Two pads 1.0 mm apart along x: pad 0 at -0.5, pad 1 at +0.5."""

    def __init__(self) -> None:
        self.pads = [SmdPad().at(-0.5, 0), SmdPad().at(0.5, 0)]
        self.court = Courtyard(rectangle(1.8, 1.0))


class FixtureAcCap(Component):
    """Fictional AC coupling capacitor, two ports.

    Not a real product. Carries a bridging pin model from ``a`` to ``b``
    (fixture values from the case prompt) unless ``model`` is False.
    """

    a = Port()
    b = Port()

    def __init__(self, model: bool = True) -> None:
        self.landpattern = CapLandpattern()
        self.symbol = BoxSymbol(2)
        if model:
            self.through = BridgingPinModel(
                self.a, self.b, delay=CAP_DELAY, loss=CAP_LOSS
            )


class ConnLandpattern(Landpattern):
    """One column of four pads at 1.0 mm pitch."""

    def __init__(self) -> None:
        self.pads = [SmdPad().at(0, y) for y in ROWS]
        self.court = Courtyard(rectangle(1.5, 4.5))


class FixtureConnector(Component):
    """Fictional connector with two TX diff pairs.

    Not a real product. Each TX pin carries a terminating pin model for the
    connector body (fixture values from the case prompt).
    """

    tx0 = DiffPair()
    tx1 = DiffPair()

    def __init__(self, terminate: bool = True) -> None:
        self.landpattern = ConnLandpattern()
        self.symbol = BoxSymbol(4)
        tx_pins = [self.tx0.p, self.tx0.n, self.tx1.p, self.tx1.n]
        self.mapping = PadMapping(
            list(zip(tx_pins, self.landpattern.pads, strict=True))
        )
        if terminate:
            self.body = [
                TerminatingPinModel(p, delay=CONN_TX_DELAY, loss=CONN_TX_LOSS)
                for p in tx_pins
            ]


class EscapeVia(SampleSubstrate.THVia):
    """The sample through via with a delay and loss model from layer 0 to layer 1."""

    models = {(0, 1): PinModel(delay=VIA_DELAY, loss=VIA_LOSS)}


class IdealEscapeVia(SampleSubstrate.THVia):
    """The sample through via with a zero-delay, zero-loss model, for the probe."""

    models = {(0, 1): PinModel(delay=0.0, loss=0.0)}


class BareEscapeVia(SampleSubstrate.THVia):
    """The sample through via with no model, for the no-via-model mutation."""


class SiChannel(Circuit):
    """BGA ball, escape via, bottom-layer trace, AC cap, connector; two pairs."""

    routed: bool = True
    terminated: bool = True
    via_class: type[Via] = EscapeVia
    cap_without_model: int | None = None  # index into ROWS order

    def __init__(self) -> None:
        self.bga = FixtureFpgaBga(terminate=self.terminated).at(BGA_X, 0)
        self.conn = FixtureConnector(terminate=self.terminated).at(
            CONN_X, 0, on=Side.Bottom
        )
        bga_pins = [self.bga.tx0.p, self.bga.tx0.n, self.bga.tx1.p, self.bga.tx1.n]
        conn_pins = [
            self.conn.tx0.p,
            self.conn.tx0.n,
            self.conn.tx1.p,
            self.conn.tx1.n,
        ]
        self.caps: list[FixtureAcCap] = []
        self.vias: list[Via] = []
        # One list per leg, indexed by pair: TX_FPGA_P[1] is pair 1's p leg.
        self.TX_FPGA_P: list[Net] = []
        self.TX_FPGA_N: list[Net] = []
        self.TX_CONN_P: list[Net] = []
        self.TX_CONN_N: list[Net] = []
        self.escapes: list[PortAttachment] = []
        self.routes: list[Route] = []
        for i, (src, dst, y) in enumerate(zip(bga_pins, conn_pins, ROWS, strict=True)):
            # On the bottom side the cap's x axis is mirrored; rotating by 180
            # puts pad ``a`` back on the BGA side.
            cap = FixtureAcCap(model=i != self.cap_without_model).at(
                CAP_X, y, on=Side.Bottom, rotate=180
            )
            via = self.via_class().at(VIA_X, y)
            self.caps.append(cap)
            self.vias.append(via)
            n_leg = i % 2 == 1  # the pin lists alternate p, n
            (self.TX_FPGA_N if n_leg else self.TX_FPGA_P).append(Net([src, cap.a]))
            (self.TX_CONN_N if n_leg else self.TX_CONN_P).append(Net([cap.b, dst]))
            self.escapes.append(PortAttachment(src, via))
            if self.routed:
                self.routes += [
                    Route(src, via, layer=0),
                    Route(via, cap.a, layer=1),
                    Route(cap.b, dst, layer=1),
                ]

        pair0 = Topology(self.bga.tx0, self.conn.tx0)
        pair1 = Topology(self.bga.tx1, self.conn.tx1)
        self.pairs = (
            ConstrainDiffPair([pair0, pair1])
            .timing_difference(INTRA_PAIR_SKEW)
            .timing(TIMING_LIMIT)
            .insertion_loss(LOSS_LIMIT)
            .structure(SampleSubstrate.DRS_100)
        )
        # The guide must be a single pin, so one leg of pair 0 stands for it.
        self.bundle = ConstrainReferenceDifference(
            Topology(self.bga.tx0.p, self.conn.tx0.p),
            [
                Topology(self.bga.tx1.p, self.conn.tx1.p),
                Topology(self.bga.tx1.n, self.conn.tx1.n),
            ],
        ).timing_difference(BUNDLE_SKEW)


class CapNoModel(SiChannel):
    cap_without_model = 0


class NoRoutes(SiChannel):
    routed = False


class NoTermination(SiChannel):
    terminated = False


class IdealVia(SiChannel):
    via_class = IdealEscapeVia


class NoViaModel(SiChannel):
    via_class = BareEscapeVia


class SiChannelDesign(SampleDesign):
    def __init__(self) -> None:
        self.circuit = SiChannel()


class CapNoModelDesign(SampleDesign):
    def __init__(self) -> None:
        self.circuit = CapNoModel()


class NoRoutesDesign(SampleDesign):
    def __init__(self) -> None:
        self.circuit = NoRoutes()


class NoTerminationDesign(SampleDesign):
    def __init__(self) -> None:
        self.circuit = NoTermination()


class IdealViaDesign(SampleDesign):
    def __init__(self) -> None:
        self.circuit = IdealVia()


class NoViaModelDesign(SampleDesign):
    def __init__(self) -> None:
        self.circuit = NoViaModel()
