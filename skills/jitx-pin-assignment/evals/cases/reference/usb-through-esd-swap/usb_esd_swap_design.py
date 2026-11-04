"""Reference designs: a USB 2.0 pair through a channel-swappable ESD part, JITX 4.6.

Signal path: host ``usb`` pair -> ESD channel in -> ESD channel out -> connector
``usb`` pair, all plain ``+`` nets; no ``>>``. The ESD part is flow-through: each
channel is an ``in`` pin and an ``out`` pin on opposite sides, joined by a
``BridgingPinModel`` so the constrained path crosses the part.

What is flexible is which ESD channel carries D+ and which carries D-, not the
USB polarity: the provider offers the pair on channels (1, 2) or (3, 4), with
either channel of the pair on D+. Every offered mapping moves the host side and
the connector side of a channel together, so host D+ always reaches connector
D+. Crossing D+ and D- end to end is never offered.

The constraint is on ``Topology(host.usb, conn.usb)``: fixed physical ends on
either side of the assigned ESD pins. It measures only once the assignment
resolves, and the assignment resolves from code routes on the ESD part's
physical pins (a route cannot end on a ``require()`` port).

Every part here is a fictional fixture, not a real product. The pin-model values
are fixture values, the skew limit is ``jitxlib.protocols.usb.USB.v2.skew`` from
jitxlib-standard, and the 1 ns delay budget is a fixture value. The sample
substrate offers only a 100 ohm differential structure (``DRS_100``); USB 2.0
asks for 90 ohm (``USB.v2.impedance``), which a real board's substrate supplies.

Channel ``k`` of the ESD part is index ``k - 1`` of ``ch_in`` and ``ch_out``.

Two more groups of variants route the straight mapping differently:

- Placement: ``CircuitPlaced`` places the ESD provider circuit with ``.at()``
  and not the ESD part inside it. A circuit's ``.at()`` sets only its frame, so
  the part is left to the placer and its routes are not made.
- A via in the ESD part's pad: each host-side leg drops from the host pad
  through a via netted to the host pin, runs on the bottom layer, and comes up
  through a via in the ESD channel's pad. ``ViaInPadAttached`` joins that via
  to the channel pin with ``PortAttachment`` and resolves. ``ViaInPadBoth``
  also puts it in a ``Net`` with the pin, which the build rejects.
"""

from __future__ import annotations

from typing import Literal

from jitx.circuit import Circuit, Route
from jitx.component import Component
from jitx.feature import Courtyard, Soldermask
from jitx.landpattern import Landpattern, Pad
from jitx.net import DiffPair, Net, Port, PortAttachment, Topology, provide
from jitx.sample import SampleDesign, SampleSubstrate
from jitx.shapes.composites import rectangle
from jitx.si import BridgingPinModel, ConstrainDiffPair
from jitx.symbol import Direction, Pin, Symbol
from jitxlib.protocols.usb import USB

ESD_CHANNEL_DELAY = 3e-12  # fixture value: 3 ps per ESD channel, in to out.
ESD_CHANNEL_LOSS = 0.05  # fixture value: 0.05 dB per ESD channel, in to out.
TIMING_BUDGET = 1e-9  # fixture value: 1 ns host-to-connector delay budget.
# jitxlib-standard's USB 2.0 intra-pair skew limit, Toleranced(0, 3.75 ps).
USB2_SKEW = USB.v2.skew

HOST_X = -12.0
CONN_X = 12.0
ESD_IN_X = -1.5  # the ESD part's in pads, in its frame
VIA_LAYER = 1  # the bottom layer, between the in-pad vias

ChannelPair = tuple[int, int]
"""ESD channel indices (P, N): index of the channel carrying D+, then D-."""

OFFERED: tuple[ChannelPair, ...] = ((0, 1), (1, 0), (2, 3), (3, 2))
"""Channel pairs the provider offers: channels (1, 2) and (3, 4), each either way round."""


class SquarePad(Pad):
    shape = rectangle(0.6, 0.6)
    soldermask = Soldermask(shape)


class ColumnLandpattern(Landpattern):
    """One column of pads at 1 mm pitch, centered on the origin."""

    def __init__(self, count: int, x: float = 0.0) -> None:
        self.pads = [SquarePad().at(x, (count - 1) / 2 - i) for i in range(count)]
        self.courtyard = Courtyard(rectangle(1.5 + 2 * abs(x), count + 0.5))


class FlowThroughLandpattern(Landpattern):
    """Fictional flow-through DFN: in pads left, out pads right, ground pad center.

    Pad order is ``ch_in[0..3]``, ``ch_out[0..3]``, ``gnd``, matching the port
    declaration order of :class:`FlowThroughEsd4`.
    """

    def __init__(self) -> None:
        ins = [SquarePad().at(-1.5, 1.5 - i) for i in range(4)]
        outs = [SquarePad().at(1.5, 1.5 - i) for i in range(4)]
        self.pads = [*ins, *outs, SquarePad().at(0, 0)]
        self.courtyard = Courtyard(rectangle(4.0, 4.5))


class BoxSymbol(Symbol):
    def __init__(self, count: int) -> None:
        self.pins = [
            Pin(at=(-1, count // 2 - i), length=1, direction=Direction.Left)
            for i in range(count)
        ]
        self.body = rectangle(2, count + 1)


class UsbHost(Component):
    """Fictional USB 2.0 host fixture: one D+/D- pair and ground."""

    usb = DiffPair()
    gnd = Port()

    def __init__(self) -> None:
        self.landpattern = ColumnLandpattern(3)
        self.symbol = BoxSymbol(3)


class UsbConnector(Component):
    """Fictional USB 2.0 connector fixture: one D+/D- pair and ground."""

    usb = DiffPair()
    gnd = Port()

    def __init__(self) -> None:
        self.landpattern = ColumnLandpattern(3)
        self.symbol = BoxSymbol(3)


class FlowThroughEsd4(Component):
    """Fictional 4-channel flow-through ESD array in a DFN-style package.

    Each channel is a straight-through line from ``ch_in[i]`` to ``ch_out[i]``
    with a clamp to ``gnd``. The channels are identical, so any channel may carry
    either USB line. Not a real part; the pin-model values are fixture values.
    """

    ch_in = [Port() for _ in range(4)]
    ch_out = [Port() for _ in range(4)]
    gnd = Port()

    def __init__(self) -> None:
        self.landpattern = FlowThroughLandpattern()
        self.symbol = BoxSymbol(9)
        self.channel_models = [
            BridgingPinModel(
                self.ch_in[i],
                self.ch_out[i],
                delay=ESD_CHANNEL_DELAY,
                loss=ESD_CHANNEL_LOSS,
            )
            for i in range(4)
        ]


class ProtectedPair(Port):
    """A D+/D- pair through one ESD channel pair: the host side and the connector side."""

    host = DiffPair()
    conn = DiffPair()


class EsdProtection(Circuit):
    """Provider: offers one protected pair on either channel pair, either way round.

    ``place_part=False`` leaves the ESD part unplaced, for the variant that
    places this circuit instead.
    """

    gnd = Port()

    def __init__(self, place_part: bool = True) -> None:
        self.esd = FlowThroughEsd4()
        if place_part:
            self.esd.at(0, 0)
        self.gnd_net = self.gnd + self.esd.gnd

    @provide.one_of(ProtectedPair)
    def protected_pair(self, pair: ProtectedPair) -> list[dict[Port, Port]]:
        esd = self.esd
        return [
            {
                pair.host.p: esd.ch_in[p],
                pair.host.n: esd.ch_in[n],
                pair.conn.p: esd.ch_out[p],
                pair.conn.n: esd.ch_out[n],
            }
            for p, n in OFFERED
        ]


class UsbThroughEsd(Circuit):
    """Host to connector through the ESD provider, with code routes on chosen channels.

    ``host_channels`` names the ESD channels the host-side routes land on and
    ``conn_channels`` the channels the connector-side routes leave from, each as
    (D+ channel, D- channel). ``None`` leaves that side unrouted.
    ``place_circuit`` places the provider circuit rather than its ESD part.
    ``via_join`` routes the host side through a via in each ESD in pad, joined
    to the channel pin by ``PortAttachment``, or by that and a ``Net`` both.
    """

    def __init__(
        self,
        host_channels: ChannelPair | None,
        conn_channels: ChannelPair | None,
        place_circuit: bool = False,
        via_join: Literal["attached", "both"] | None = None,
    ) -> None:
        self.host = UsbHost().at(HOST_X, 0)
        self.conn = UsbConnector().at(CONN_X, 0)
        if place_circuit:
            self.prot = EsdProtection(place_part=False).at(0, 0)
        else:
            self.prot = EsdProtection()

        # The required pair stays local: a require() port cannot be a member field.
        pair = self.prot.require(ProtectedPair)
        self.DP_HOST = self.host.usb.p + pair.host.p
        self.DN_HOST = self.host.usb.n + pair.host.n
        self.DP_CONN = pair.conn.p + self.conn.usb.p
        self.DN_CONN = pair.conn.n + self.conn.usb.n
        self.gnd = Net([self.host.gnd, self.prot.gnd, self.conn.gnd], name="GND")

        # Routes end on the ESD part's physical pins, never on the required port.
        esd = self.prot.esd
        self.routes: list[Route] = []
        self.vias: list[SampleSubstrate.THVia] = []
        self.via_joins: list[PortAttachment] = []
        self.via_nets: list[Net] = []
        if host_channels is not None and via_join is not None:
            # Host pads sit at y = 1 (D+) and y = 0 (D-); ESD in pad k at 1.5 - k.
            for host_pin, host_y, k in zip(
                (self.host.usb.p, self.host.usb.n),
                (1.0, 0.0),
                host_channels,
                strict=True,
            ):
                pin = esd.ch_in[k]
                host_via = SampleSubstrate.THVia().at(HOST_X, host_y)
                esd_via = SampleSubstrate.THVia().at(ESD_IN_X, 1.5 - k)
                self.vias += [host_via, esd_via]
                self.via_nets.append(Net([host_pin, host_via]))
                self.via_joins.append(PortAttachment(pin, esd_via))
                if via_join == "both":
                    self.via_nets.append(Net([pin, esd_via]))
                self.routes.append(Route(host_via, esd_via, layer=VIA_LAYER))
        elif host_channels is not None:
            p, n = host_channels
            self.routes += [
                Route(self.host.usb.p, esd.ch_in[p], layer=0),
                Route(self.host.usb.n, esd.ch_in[n], layer=0),
            ]
        if conn_channels is not None:
            p, n = conn_channels
            self.routes += [
                Route(esd.ch_out[p], self.conn.usb.p, layer=0),
                Route(esd.ch_out[n], self.conn.usb.n, layer=0),
            ]

        self.usb_constraint = (
            ConstrainDiffPair(Topology(self.host.usb, self.conn.usb))
            .timing_difference(USB2_SKEW)
            .timing(TIMING_BUDGET)
            .structure(SampleSubstrate.DRS_100)
        )


class Straight(SampleDesign):
    """D+ on channel 1, D- on channel 2: an offered mapping, so it resolves and measures."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsd(host_channels=(0, 1), conn_channels=(0, 1))


class SwappedInverted(SampleDesign):
    """D+ on channel 4, D- on channel 3: the other pair, inverted; offered, so it measures."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsd(host_channels=(3, 2), conn_channels=(3, 2))


class Illegal(SampleDesign):
    """D+ on channel 1, D- on channel 3: splits the pairs, not offered, so a route drops."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsd(host_channels=(0, 2), conn_channels=(0, 2))


class SidesDisagree(SampleDesign):
    """Host side on channels (1, 2), connector side on (3, 4): no offered mapping has both."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsd(host_channels=(0, 1), conn_channels=(2, 3))


class Unrouted(SampleDesign):
    """No routes: the assignment cannot resolve, so nothing measures."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsd(host_channels=None, conn_channels=None)


class CircuitPlaced(SampleDesign):
    """Straight routes, with the ESD circuit placed instead of the ESD part."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsd(
            host_channels=(0, 1), conn_channels=(0, 1), place_circuit=True
        )


class ViaInPadAttached(SampleDesign):
    """Straight, the host side through a via in each ESD in pad, attached to its pin."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsd(
            host_channels=(0, 1), conn_channels=(0, 1), via_join="attached"
        )


class ViaInPadBoth(SampleDesign):
    """Straight, the ESD-pad vias both attached and netted: the build rejects it."""

    def __init__(self) -> None:
        self.circuit = UsbThroughEsd(
            host_channels=(0, 1), conn_channels=(0, 1), via_join="both"
        )
