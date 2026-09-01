"""Reference: tying a wide repeated-name rail, and asserting it held.

The part under test stands in for any BGA with a large ground rail — the point is
the shape of the tie, not the part. Everything here instantiates offline: no
runtime, no parts database, no auth.
"""

import jitx
from jitx import Circuit, Net
from jitx.net import Port

GND_BALLS = 24
RSVD_GND_BALLS = 6
CORE_BALLS = 8


class WideRailPart(jitx.Component):
    """A part whose ground arrives as two repeated-name rails, as BGAs do."""

    GND: list[Port]
    RSVDGND: list[Port]
    VCCINT: list[Port]
    VCCAUX: Port

    def __init__(self) -> None:
        super().__init__()
        self.GND = [Port() for _ in range(GND_BALLS)]
        self.RSVDGND = [Port() for _ in range(RSVD_GND_BALLS)]
        self.VCCINT = [Port() for _ in range(CORE_BALLS)]
        self.VCCAUX = Port()


class RailTie(Circuit):
    """Both rails onto one ground net in a single call, and a core net beside it.

    `Net(...)` takes an iterable, so the whole rail is one line. `+=` takes a port
    or a Net and never a bare list — see SKILL.md "`+=` takes a port or a `Net`".
    """

    def __init__(self) -> None:
        super().__init__()
        self.u1 = WideRailPart()
        self.GND = Net([*self.u1.GND, *self.u1.RSVDGND], name="GND")
        self.V1V0 = Net([*self.u1.VCCINT], name="V1V0")
        self.V1V0 += self.u1.VCCAUX          # a port, not a list


class _Inner(Circuit):
    """Support for the `in`-is-unreliable guard in check.py.

    JITX classes cannot be declared inside a function or a test method — the
    framework raises "Creating new JITX classes dynamically during instantiation
    is not supported" — so these live at module scope like every other one.
    """

    p = Port()
    q = Port()

    def __init__(self) -> None:
        super().__init__()
        self.n = self.p + self.q


class NestedNetFirst(Circuit):
    """A net whose first member is another net, which is what breaks `in`."""

    t = Port()

    def __init__(self) -> None:
        super().__init__()
        self.inner = _Inner()
        self.top = Net([self.inner.n], name="top")
        self.top += self.t
