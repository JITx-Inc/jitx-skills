"""Yageo RC_L general-purpose chip resistor family (parameterized).

This models Yageo's RC_L thick-film chip resistor series as a single
parameterized :class:`jitx.Component`. One class covers every catalog part in
the family: choose a case size, resistance, and tolerance and the component
builds the matching land pattern, resistor symbol, and Yageo global part number
with no parts-database or online lookup. It is a drop-in alternative to
:class:`jitxlib.parts.Resistor` and provides a matching :meth:`YageoRC.insert`
helper.

Supported case sizes: the full RC_L family — 0075, 0100, 0201, 0402, 0603, 0805,
1206, 1210, 1218, 2010, 2512. The two ultra-tiny sizes (0075, 0100) are
ESD-reel-only parts (packaging code S); JITX's chip land-pattern generator keys
them by metric body size (0075 -> 009005, 0100 -> 01005) rather than the Yageo
label.

Datasheet (RC_L series, doc rev. 14); all dimensions below are transcribed from
its Table 1: https://yageogroup.com/content/datasheet/asset/file/PYU-RC_GROUP_51_ROHS_L

Land-pattern construction, two-pin ``.insert()``, value-code rounding, and the
E-series check are shared with the other chip-resistor families via
:mod:`.chip_smt`.
"""

from typing import Self

import jitx
from jitx.net import Net, Port
from jitx.toleranced import Toleranced
from jitx.units import PlainQuantity, ohm
from jitxlib.symbols.resistor import ResistorSymbol

from .chip_smt import (
    ChipDims,
    check_eseries as _check_eseries,
    chip_smt_landpattern,
    compact_value,
    insert_two_pin,
    round_sig,
)

DATASHEET_URL = (
    "https://yageogroup.com/content/datasheet/asset/file/PYU-RC_GROUP_51_ROHS_L"
)


def _dims(
    length: float,
    length_tol: float,
    width: float,
    width_tol: float,
    height: float,
    height_tol: float,
    lead: float,
    lead_tol: float,
) -> ChipDims:
    """Build a ChipDims from datasheet typ +/- tolerances (mm)."""
    return ChipDims(
        Toleranced(length, length_tol),
        Toleranced(width, width_tol),
        Toleranced(height, height_tol),
        Toleranced(lead, lead_tol),
    )


# Yageo size label -> JITX SMT_CHIP_DEFS case key, where the two differ. Most
# sizes use their imperial label directly; the ultra-tiny 0075/0100 are keyed in
# the generator by their metric body size (0.30x0.15 mm, 0.40x0.20 mm).
_SMT_KEY: dict[str, str] = {"0075": "009005", "0100": "01005"}

# Dimensions (mm) from datasheet Table 1: _dims(L, +/-, W, +/-, H, +/-, l2, +/-)
# where L=body length, W=width, H=height, l2=bottom solderable termination band.
RC_DIMENSIONS: dict[str, ChipDims] = {
    "0075": _dims(0.30, 0.01, 0.15, 0.01, 0.13, 0.01, 0.08, 0.03),
    "0100": _dims(0.40, 0.02, 0.20, 0.02, 0.13, 0.02, 0.10, 0.03),
    "0201": _dims(0.60, 0.03, 0.30, 0.03, 0.23, 0.03, 0.15, 0.05),
    "0402": _dims(1.00, 0.05, 0.50, 0.05, 0.35, 0.05, 0.25, 0.10),
    "0603": _dims(1.60, 0.10, 0.80, 0.10, 0.45, 0.10, 0.25, 0.15),
    "0805": _dims(2.00, 0.10, 1.25, 0.10, 0.50, 0.10, 0.35, 0.20),
    "1206": _dims(3.10, 0.10, 1.60, 0.10, 0.55, 0.10, 0.45, 0.20),
    "1210": _dims(3.10, 0.10, 2.60, 0.15, 0.55, 0.10, 0.50, 0.20),
    "1218": _dims(3.10, 0.10, 4.60, 0.10, 0.55, 0.10, 0.40, 0.20),
    "2010": _dims(5.00, 0.10, 2.50, 0.15, 0.55, 0.10, 0.55, 0.20),
    "2512": _dims(6.35, 0.10, 3.10, 0.15, 0.55, 0.10, 0.60, 0.20),
}

# Rated power (W at 70 C) per size; the first entry is the standard rating, a
# second entry (if present) is the datasheet's double-power variant.
POWER_RATING: dict[str, tuple[float, ...]] = {
    "0075": (1 / 50,),
    "0100": (1 / 32,),
    "0201": (1 / 20,),
    "0402": (1 / 16, 1 / 8),
    "0603": (1 / 10, 1 / 5),
    "0805": (1 / 8, 1 / 4),
    "1206": (1 / 4, 1 / 2),
    "1210": (1 / 2,),
    "1218": (1.0,),
    "2010": (3 / 4,),
    "2512": (1.0, 2.0),
}

# Maximum working voltage (V) per size (datasheet Table 2).
MAX_VOLTAGE: dict[str, int] = {
    "0075": 10,
    "0100": 15,
    "0201": 25,
    "0402": 50,
    "0603": 75,
    "0805": 150,
    "1206": 200,
    "1210": 200,
    "1218": 200,
    "2010": 200,
    "2512": 200,
}

# Tolerance (fraction) -> Yageo part-number code (datasheet ordering field 2).
TOLERANCE_CODE: dict[float, str] = {0.001: "B", 0.005: "D", 0.01: "F", 0.05: "J"}

# Packaging-type codes (datasheet field 3) allowed per size. S (ESD safe reel)
# is a 0075/0100-only option; RC0075 ships only on the ESD reel. Sizes not listed
# default to paper/embossed (R/K).
PACKAGING_BY_SIZE: dict[str, tuple[str, ...]] = {
    "0075": ("S",),
    "0100": ("R", "S"),
}
_DEFAULT_PACKAGING = ("R", "K")

# Reel/power ordering codes (datasheet field 5). The "W" codes select the
# double-power variant; 7D is double-quantity (0201/0402); 7N is the ESD reel
# (0075/0100), which pairs with packaging code S.
REEL_POWER_CODES = ("07", "10", "13", "7W", "7D", "7N", "3W")
_DOUBLE_POWER_CODES = ("7W", "3W")


def format_resistance_code(ohms: float, *, sig_figs: int = 3) -> str:
    """Encode a resistance as a Yageo / IEC-60062 RKM part-number field.

    The multiplier letter doubles as the decimal point: ``R`` = x1, ``K`` = x1e3,
    ``M`` = x1e6. The mantissa carries up to ``sig_figs`` significant digits;
    the value is first rounded to that resolution so decade carries propagate.

    >>> format_resistance_code(4.7)
    '4R7'
    >>> format_resistance_code(9760)
    '9K76'
    >>> format_resistance_code(100_000)
    '100K'
    >>> format_resistance_code(9999)
    '10K'
    """
    if ohms <= 0:
        raise ValueError(f"resistance must be > 0 ohms, got {ohms}")
    ohms = round_sig(ohms, sig_figs)
    if ohms < 1e3:
        letter, scale = "R", 1.0
    elif ohms < 1e6:
        letter, scale = "K", 1e3
    else:
        letter, scale = "M", 1e6
    mantissa = ohms / scale
    whole = int(mantissa)
    whole_str = str(whole) if whole else ""
    frac_digits = max(sig_figs - len(whole_str) if whole_str else sig_figs, 0)
    frac_str = (
        f"{mantissa - whole:.{frac_digits}f}"[2:].rstrip("0") if frac_digits else ""
    )
    return f"{whole_str}{letter}{frac_str}"


def _build_mpn(
    size: str, tolerance: float, packaging: str, reel_power_code: str, ohms: float
) -> str:
    """Assemble the Yageo RC_L global part number (e.g. ``RC0402JR-07100KL``)."""
    return (
        f"RC{size}{TOLERANCE_CODE[tolerance]}{packaging}"
        f"-{reel_power_code}{format_resistance_code(ohms)}L"
    )


class YageoRC(jitx.Component):
    """A Yageo RC_L general-purpose chip resistor, built from datasheet data.

    Args:
        resistance: Resistance in ohms (must be > 0).
        size: Imperial case code, e.g. ``"0603"``. Any of the 11 RC_L sizes
            (0075-2512).
        tolerance: Tolerance as a fraction: ``0.001``/``0.005``/``0.01``/``0.05``
            (codes B/D/F/J).
        packaging: Packaging-type code. ``None`` uses the size's default —
            ``"R"`` (paper reel) for standard sizes, ``"S"`` (ESD reel) for 0075.
            Valid options are per-size: R/K for 0201-2512, S for 0075, R/S for 0100.
        reel_power_code: Reel/power ordering field (datasheet field 5). ``None``
            uses ``"7N"`` for ESD (S) packaging else ``"07"``. The rated power is
            derived from this and the size; ``"7W"``/``"3W"`` select double power.
        check_eseries: If true, validate ``resistance`` against the E24/E96 grid.
    """

    datasheet: str
    p1: Port
    p2: Port
    landpattern: jitx.Landpattern
    symbol: jitx.Symbol
    case: str
    tolerance: float
    power: float
    max_voltage: int

    def __init__(
        self,
        *,
        resistance: float,
        size: str = "0402",
        tolerance: float = 0.01,
        packaging: str | None = None,
        reel_power_code: str | None = None,
        check_eseries: bool = False,
    ):
        if size not in RC_DIMENSIONS:
            raise ValueError(
                f"Unknown Yageo RC size {size!r}; supported sizes: "
                f"{sorted(RC_DIMENSIONS)}"
            )
        if resistance <= 0:
            raise ValueError(f"resistance must be > 0 ohms, got {resistance}")
        if tolerance not in TOLERANCE_CODE:
            raise ValueError(
                f"tolerance {tolerance} is not a Yageo RC option; choose one of "
                f"{sorted(TOLERANCE_CODE)} (B/D/F/J)"
            )
        allowed_pkg = PACKAGING_BY_SIZE.get(size, _DEFAULT_PACKAGING)
        if packaging is None:
            packaging = allowed_pkg[0]
        elif packaging not in allowed_pkg:
            raise ValueError(
                f"packaging {packaging!r} not available for size {size}; choose "
                f"one of {allowed_pkg}"
            )
        if reel_power_code is None:
            reel_power_code = "7N" if packaging == "S" else "07"
        elif reel_power_code not in REEL_POWER_CODES:
            raise ValueError(
                f"reel_power_code {reel_power_code!r} invalid; choose one of "
                f"{REEL_POWER_CODES}"
            )
        if (reel_power_code == "7N") != (packaging == "S"):
            raise ValueError(
                f"reel_power_code {reel_power_code!r} and packaging {packaging!r} "
                f"are inconsistent: the ESD reel (7N) pairs with packaging S "
                f"(sizes 0075/0100)"
            )
        ratings = POWER_RATING[size]
        if reel_power_code in _DOUBLE_POWER_CODES:
            if len(ratings) < 2:
                raise ValueError(
                    f"size {size} has no double-power variant for reel_power_code "
                    f"{reel_power_code!r}"
                )
            power = ratings[1]
        else:
            power = ratings[0]
        if check_eseries:
            _check_eseries(resistance, tolerance)

        self.mpn = _build_mpn(size, tolerance, packaging, reel_power_code, resistance)
        self.manufacturer = "Yageo"
        self.reference_designator_prefix = "R"
        self.datasheet = DATASHEET_URL
        self.value = compact_value(PlainQuantity(resistance, ohm))
        self.case = size
        self.tolerance = tolerance
        self.power = power
        self.max_voltage = MAX_VOLTAGE[size]

        self.symbol = ResistorSymbol()
        self.landpattern = chip_smt_landpattern(
            _SMT_KEY.get(size, size), RC_DIMENSIONS[size]
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


Device: type[YageoRC] = YageoRC
