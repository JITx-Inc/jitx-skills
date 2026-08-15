"""Vishay CRCW e3 standard thick-film chip resistor family (parameterized).

Models Vishay's CRCW e3 standard thick-film chip resistor series (datasheet
20035) as a single parameterized :class:`jitx.Component`. Choose a case size,
resistance, tolerance, and temperature coefficient and the component builds the
matching land pattern, resistor symbol, and Vishay (Dale) part number with no
parts-database or online lookup. It is a drop-in alternative to
:class:`jitxlib.parts.Resistor` and provides a matching :meth:`VishayCRCW.insert`.

Case sizes: 0402, 0603, 0805, 1206, 1210, 1218, 2010, 2512. Tolerances +/-1% (F)
and +/-5% (J); temperature coefficient +/-100 ppm/K (K, 1% only) or +/-200 ppm/K (N).

Note on dimensions: datasheet 20035 specifies each case by its standard EIA/IEC
size code (e.g. RR1608M = 1.6 x 0.8 mm for 0603), so the land pattern takes
JITX's standard chip dimensions for the size rather than vendor-specific
overrides. That is a deliberate choice, not an absence of data -- the datasheet's
DIMENSIONS AND MASS table (doc page 11) is transcribed below as
:data:`CRCW_DIMENSIONS` and asserted against the standard table per size in
``tests/test_js1_vishay_crcw.py``, which is how the one size that disagrees
(2512) was found and overridden.

Datasheet (doc 20035): https://www.vishay.com/docs/20035/dcrcwe3.pdf

Land-pattern construction, two-pin ``.insert()``, and the E-series check are
shared with the other chip-resistor families via :mod:`.chip_smt`.
"""

from typing import Self

import jitx
from jitx.net import Net, Port
from jitx.units import PlainQuantity, ohm
from jitxlib.symbols.resistor import ResistorSymbol

from .chip_smt import (
    ChipDims,
    check_eseries as _check_eseries,
    chip_smt_landpattern,
    datasheet_dim as _t,
    compact_value,
    insert_two_pin,
    round_sig,
)

DATASHEET_URL = "https://www.vishay.com/docs/20035/dcrcwe3.pdf"

# Body dimensions (mm) from the datasheet's DIMENSIONS AND MASS table (doc page
# 11): L, W, H and T1 -- T1 being the band dimensioned on the seating plane in
# the outline drawing, i.e. the solderable termination. Every vendor in this kit
# prints a second band (here T2) and labels neither; T1 is the one that belongs
# in ChipDims.lead.
#
# The family builds its land patterns from JITX's standard chip table, not from
# this dict -- it is transcribed so the standard table can be *checked* against
# it. See _STANDARD_TABLE_OVERRIDES below and the test that enforces both
# directions.
CRCW_DIMENSIONS: dict[str, ChipDims] = {
    "0402": ChipDims(_t(1.00, 0.05), _t(0.50, 0.05), _t(0.35, 0.05), _t(0.25, 0.10)),
    "0603": ChipDims(
        _t(1.55, 0.10, 0.05), _t(0.85, 0.10), _t(0.45, 0.05), _t(0.30, 0.20)
    ),
    "0805": ChipDims(
        _t(2.00, 0.20, 0.10), _t(1.25, 0.15), _t(0.50, 0.10), _t(0.30, 0.20, 0.10)
    ),
    "1206": ChipDims(
        _t(3.20, 0.10, 0.20), _t(1.60, 0.15), _t(0.55, 0.05), _t(0.45, 0.20)
    ),
    "1210": ChipDims(_t(3.20, 0.20), _t(2.50, 0.20), _t(0.55, 0.05), _t(0.45, 0.20)),
    "1218": ChipDims(
        _t(3.20, 0.10, 0.20), _t(4.60, 0.15), _t(0.55, 0.05), _t(0.45, 0.20)
    ),
    "2010": ChipDims(_t(5.00, 0.15), _t(2.50, 0.15), _t(0.60, 0.10), _t(0.60, 0.20)),
    "2512": ChipDims(_t(6.30, 0.20), _t(3.15, 0.15), _t(0.60, 0.10), _t(0.60, 0.20)),
}

# Sizes where JITX's standard chip table disagrees with the datasheet badly
# enough to build the wrong land pattern, so we override it with the datasheet.
#
# 2512: SMT_CHIP_DEFS["2512"].lead_length is 2.0 +/- 0.5 mm. The datasheet's T1
# is 0.6 +/- 0.20, and Yageo's RC_L Table 1 gives 0.60 +/- 0.20 for the same case
# (see yageo_rc.RC_DIMENSIONS). A 2.0 mm band on a 6.35 mm body is a third of the
# part's length and sizes the pads from a termination roughly three times too
# long. Every other size in this family agrees within 0.2 mm. Filed upstream as a
# jitxlib data bug; drop this override once the table is corrected -- the test
# below fails when that happens, so it will not be forgotten.
_STANDARD_TABLE_OVERRIDES = ("2512",)

# Rated dissipation P70 (W) per size (datasheet Technical Specifications).
POWER_RATING: dict[str, float] = {
    "0402": 0.10,
    "0603": 0.125,
    "0805": 0.25,
    "1206": 0.25,
    "1210": 0.5,
    "1218": 1.0,
    "2010": 0.75,
    "2512": 1.0,
}

# Operating (max working) voltage (V) per size.
MAX_VOLTAGE: dict[str, int] = {
    "0402": 75,
    "0603": 75,
    "0805": 150,
    "1206": 200,
    "1210": 200,
    "1218": 200,
    "2010": 400,
    "2512": 500,
}

# Maximum resistance (ohms) per size; the range is 1 ohm up to this value.
RES_MAX: dict[str, float] = {
    "0402": 10e6,
    "0603": 10e6,
    "0805": 10e6,
    "1206": 10e6,
    "1210": 10e6,
    "1218": 2.2e6,
    "2010": 10e6,
    "2512": 10e6,
}

# Default packaging-field code per size (datasheet packaging table, 7" reel).
PACKAGING_DEFAULT: dict[str, str] = {
    "0402": "ED",
    "0603": "EA",
    "0805": "EA",
    "1206": "EA",
    "1210": "EA",
    "1218": "EK",
    "2010": "EF",
    "2512": "EH",
}
PACKAGING_CODES = ("EA", "EC", "ED", "EE", "EF", "EG", "EH", "EI", "EK")

# Tolerance (fraction) -> Vishay part-number code.
TOLERANCE_CODE: dict[float, str] = {0.01: "F", 0.05: "J"}

# Temperature coefficient (ppm/K) -> code, and which TCRs each tolerance offers
# (datasheet: +/-5% is +/-200 ppm/K only; +/-1% offers +/-100 or +/-200 ppm/K).
TCR_CODE: dict[int, str] = {100: "K", 200: "N"}
_ALLOWED_TCR: dict[float, tuple[int, ...]] = {0.01: (100, 200), 0.05: (200,)}


def format_value_code(ohms: float) -> str:
    """Encode a resistance as Vishay's fixed 4-character value code.

    Three significant figures with the multiplier letter (``R`` = x1, ``K`` = x1e3,
    ``M`` = x1e6) standing in for the decimal point.

    >>> format_value_code(562)
    '562R'
    >>> format_value_code(10_000)
    '10K0'
    >>> format_value_code(1_000_000)
    '1M00'
    """
    if ohms <= 0:
        raise ValueError(f"resistance must be > 0 ohms, got {ohms}")
    ohms = round_sig(ohms, 3)  # 3 significant figures; propagates decade carries
    if ohms < 1e3:
        letter, scale = "R", 1.0
    elif ohms < 1e6:
        letter, scale = "K", 1e3
    else:
        letter, scale = "M", 1e6
    mantissa = ohms / scale
    if mantissa < 10:
        digits = f"{mantissa:.2f}".replace(".", "")
        return f"{digits[0]}{letter}{digits[1:]}"
    if mantissa < 100:
        digits = f"{mantissa:.1f}".replace(".", "")
        return f"{digits[:2]}{letter}{digits[2:]}"
    return f"{round(mantissa)}{letter}"


def _build_mpn(
    size: str, ohms: float, tolerance: float, tcr_ppm: int, packaging: str
) -> str:
    """Assemble the Vishay CRCW part number (e.g. ``CRCW0603562RFKEA``)."""
    return (
        f"CRCW{size}{format_value_code(ohms)}"
        f"{TOLERANCE_CODE[tolerance]}{TCR_CODE[tcr_ppm]}{packaging}"
    )


class VishayCRCW(jitx.Component):
    """A Vishay CRCW e3 thick-film chip resistor, built from datasheet data.

    Args:
        resistance: Resistance in ohms (1 to the size's maximum).
        size: Imperial case code, e.g. ``"0603"``. One of 0402 .. 2512.
        tolerance: Tolerance as a fraction: ``0.01`` (+/-1%, F) or ``0.05``
            (+/-5%, J).
        tcr_ppm: Temperature coefficient in ppm/K (100 or 200). ``None`` picks the
            default for the tolerance (100 for 1%, 200 for 5%). +/-5% parts are
            +/-200 ppm/K only.
        packaging: Packaging-field code (e.g. ``"EA"``). ``None`` uses the size's
            datasheet default.
        check_eseries: If true, validate ``resistance`` against the E24/E96 grid.
    """

    datasheet: str
    p1: Port
    p2: Port
    landpattern: jitx.Landpattern
    symbol: jitx.Symbol
    case: str
    tolerance: float
    tcr_ppm: int
    power: float
    max_voltage: int

    def __init__(
        self,
        *,
        resistance: float,
        size: str = "0402",
        tolerance: float = 0.01,
        tcr_ppm: int | None = None,
        packaging: str | None = None,
        check_eseries: bool = False,
    ):
        if size not in POWER_RATING:
            raise ValueError(
                f"Unknown Vishay CRCW size {size!r}; supported sizes: "
                f"{sorted(POWER_RATING)}"
            )
        if tolerance not in TOLERANCE_CODE:
            raise ValueError(
                f"tolerance {tolerance} not available; choose one of "
                f"{sorted(TOLERANCE_CODE)} (F=1%, J=5%)"
            )
        allowed_tcr = _ALLOWED_TCR[tolerance]
        if tcr_ppm is None:
            tcr_ppm = allowed_tcr[0]
        elif tcr_ppm not in allowed_tcr:
            raise ValueError(
                f"TCR {tcr_ppm} ppm/K not available for {tolerance:.0%} tolerance; "
                f"choices: {allowed_tcr}"
            )
        res_max = RES_MAX[size]
        if not 1 <= resistance <= res_max:
            raise ValueError(
                f"resistance {resistance} ohms out of range for size {size} "
                f"(1 to {res_max:,.0f} ohms)"
            )
        if packaging is None:
            packaging = PACKAGING_DEFAULT[size]
        elif packaging not in PACKAGING_CODES:
            raise ValueError(
                f"packaging {packaging!r} invalid; choose one of {PACKAGING_CODES}"
            )
        if check_eseries:
            _check_eseries(resistance, tolerance)

        self.mpn = _build_mpn(size, resistance, tolerance, tcr_ppm, packaging)
        self.manufacturer = "Vishay"
        self.reference_designator_prefix = "R"
        self.datasheet = DATASHEET_URL
        self.value = compact_value(PlainQuantity(resistance, ohm))
        self.case = size
        self.tolerance = tolerance
        self.tcr_ppm = tcr_ppm
        self.power = POWER_RATING[size]
        self.max_voltage = MAX_VOLTAGE[size]

        self.symbol = ResistorSymbol()
        # Vishay specifies standard EIA/IEC cases, so take JITX's standard chip
        # dimensions -- except where the standard table disagrees with the
        # datasheet badly enough to matter (see _STANDARD_TABLE_OVERRIDES).
        self.landpattern = chip_smt_landpattern(
            size,
            CRCW_DIMENSIONS[size] if size in _STANDARD_TABLE_OVERRIDES else None,
        )

        # Two symmetric terminals; declaration order drives the default
        # port -> symbol-pin -> pad mapping (p1 -> p[1], p2 -> p[2]).
        self.p1 = Port()
        self.p2 = Port()

    def insert(
        self,
        pin_a: Port | Net,
        pin_b: Port | Net,
        *,
        short_trace: bool = False,
    ) -> Self:
        """Place this resistor between two pins/nets of the active circuit.

        Mirrors :meth:`jitxlib.parts.Resistor.insert`; see
        :func:`.chip_smt.insert_two_pin`.
        """
        return insert_two_pin(self, pin_a, pin_b, short_trace=short_trace)


Device: type[VishayCRCW] = VishayCRCW
