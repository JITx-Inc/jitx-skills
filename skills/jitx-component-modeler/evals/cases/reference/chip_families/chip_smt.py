"""Shared building blocks for two-terminal SMT chip component families.

Vendor- and component-agnostic infrastructure used by the per-manufacturer
passive families (``yageo_rc``, ``panasonic_erj``, ``vishay_crcw``,
``samsung_cl``): a chip land-pattern builder driven by datasheet body
dimensions, a two-terminal ``.insert()`` placement helper, a carry-correct
significant-figure rounder for the value-code encoders, and an optional
E-series resistance check. Vendor-specific data — size / part-number tables
and value-code schemes — lives in each family module, since those genuinely
differ between manufacturers.

(This module began life as ``chip_resistor.py``; it was renamed once the MLCC
capacitor family started using it — everything here except ``check_eseries``
is component-agnostic.)
"""

from math import floor, log10
from typing import NamedTuple, Protocol, TypeVar

from jitx import current
from jitx.container import Container
from jitx.net import Net, Port, ShortTrace
from jitx.toleranced import Toleranced
from jitx.units import PlainQuantity
from jitxlib.landpatterns.leads import LeadProfile, SMDLead
from jitxlib.landpatterns.leads.protrusions import (
    BigRectangularLeads,
    SmallRectangularLeads,
)
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.landpatterns.twopin.smt import SMT


class ChipDims(NamedTuple):
    """Body + termination dimensions for a chip component (from a datasheet)."""

    length: Toleranced  # body length L (= lead-to-lead span)
    width: Toleranced  # body width W (= termination width)
    height: Toleranced  # body height / thickness
    lead: Toleranced  # bottom solderable termination band length


def datasheet_dim(typ: float, plus: float, minus: float | None = None) -> Toleranced:
    """Toleranced from a datasheet nominal and its +/- tolerances (mm).

    One argument for a symmetric tolerance, two for an asymmetric one -- chip
    datasheets print both (Vishay's 0603 length is 1.55 +0.10 / -0.05).
    """
    if minus is None:
        return Toleranced(typ, plus)
    return Toleranced.min_typ_max(typ - minus, typ, typ + plus)


def round_sig(value: float, sig_figs: int) -> float:
    """Round a positive value to ``sig_figs`` significant figures.

    Used by the family value-code encoders so rounding carries propagate
    correctly across decade boundaries (e.g. ``9999`` -> ``10000``), avoiding
    malformed or wrong part-number value fields.
    """
    if value <= 0:
        return value
    return round(value, sig_figs - 1 - floor(log10(value)))


def compact_value(quantity: PlainQuantity, sig_figs: int = 6) -> PlainQuantity:
    """Scale a quantity to its natural SI prefix, without binary-float noise.

    Use in place of :meth:`PlainQuantity.to_compact`, which divides by a power of
    ten and so reintroduces representation error on exactly the inputs a passive
    library uses most: ``100e-9 F`` becomes ``99.99999999999999 nanofarad``, and
    ``2.2e6 ohm`` becomes ``2.1999999999999997 megaohm``. Those strings reach the
    BOM, and no build, type check or land-pattern test looks at them. Rounding
    the scaled magnitude restores the value the caller actually asked for.
    """
    compact = quantity.to_compact()
    return PlainQuantity(round_sig(compact.magnitude, sig_figs), compact.units)


def chip_smt_landpattern(size_key: str, dims: ChipDims | None = None) -> SMT:
    """Build a 2-pad SMT chip land pattern for the given case size.

    ``size_key`` is the JITX ``SMT_CHIP_DEFS`` case name (the imperial size,
    e.g. ``"0603"``). When ``dims`` is given, its datasheet values override the
    generator defaults (``length`` -> span, ``width`` -> lead/body width,
    ``lead`` -> foot length, ``height`` -> body height). When ``dims`` is ``None``,
    the generator's standard EIA dimensions for the size are used — appropriate
    when a datasheet specifies the case only by its standard size code (with no
    custom mechanical drawing).
    """
    landpattern = SMT(size_key)
    if dims is None:
        return landpattern
    lead_type = BigRectangularLeads if dims.width.typ > 0.8 else SmallRectangularLeads
    return landpattern.lead_profile(
        LeadProfile(
            span=dims.length,
            pitch=0.0,  # unused for a two-terminal chip
            type=SMDLead(length=dims.lead, width=dims.width, lead_type=lead_type),
        )
    ).package_body(
        RectanglePackage(width=dims.width, length=dims.length, height=dims.height)
    )


class _TwoPin(Protocol):
    """A two-terminal component exposing ``p1`` and ``p2`` ports."""

    p1: Port
    p2: Port


C = TypeVar("C", bound=_TwoPin)


class _InsertContainer(Container):
    """Holds the nets/short-traces produced by :func:`insert_two_pin`."""

    nets: list[Net]
    a_short_trace: ShortTrace | None
    c_short_trace: ShortTrace | None


def insert_two_pin(
    component: C,
    pin_a: Port | Net,
    pin_b: Port | Net,
    *,
    short_trace: bool = False,
) -> C:
    """Place a two-terminal component (ports ``p1``/``p2``) into the active circuit.

    Mirrors :meth:`jitxlib.parts.Resistor.insert`. With ``short_trace=True`` both
    pins must be ports (not nets) and a short trace is added to each terminal.
    """
    container = _InsertContainer()
    container.nets = [pin_a + component.p1, pin_b + component.p2]
    if short_trace:
        if not isinstance(pin_a, Port) or not isinstance(pin_b, Port):
            raise ValueError("short_trace=True requires Port arguments, not Nets")
        container.a_short_trace = ShortTrace(pin_a, component.p1)
        container.c_short_trace = ShortTrace(pin_b, component.p2)
    circuit = current.circuit
    circuit += container
    return component


def check_eseries(ohms: float, tolerance: float) -> None:
    """Raise if ``ohms`` is not a standard E-series value for ``tolerance``.

    Two grades, because two is what these four datasheets between them name:
    E24 (>=5%) and E96 (tighter). Both ends are deliberate. Yageo's tightest
    grade is +/-0.1% (code B) and its own datasheet puts that on E24/E96, so
    falling through to E192 would accept values no vendor here makes; and no
    vendor in the set offers +/-2%, so an E48 branch would have no caller. Add a
    series when a family that needs it lands, not before.
    """
    from eseries import E24, E96, find_nearest

    if tolerance >= 0.05:
        series, name = E24, "E24"
    else:
        series, name = E96, "E96"
    nearest = find_nearest(series, ohms)
    if abs(ohms - nearest) > 1e-3 * nearest:
        raise ValueError(
            f"resistance {ohms} ohms is not a standard {name} value "
            f"(nearest is {nearest} ohms); pass check_eseries=False to bypass"
        )
