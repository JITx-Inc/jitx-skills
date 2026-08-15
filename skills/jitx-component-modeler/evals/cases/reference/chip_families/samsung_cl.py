"""Samsung Electro-Mechanics CL general-purpose MLCC family (parameterized).

Models Samsung's CL series multilayer ceramic chip capacitors (the
commercial/industrial "Normal" line from the Samsung MLCC catalog) as a single
parameterized :class:`jitx.Component`. Choose a case size, capacitance,
dielectric, tolerance, and rated voltage and the component builds the matching
land pattern, capacitor symbol, and Samsung part number with no parts-database
or online lookup. It provides a matching :meth:`SamsungCL.insert` helper.

This model scopes the family to its most common general-purpose corner: case
sizes 0402/0603/0805, class-I C0G and class-II X7R dielectrics, and rated
voltages 16/25/50 V. The capacitance envelopes below are deliberately coarse —
they catch order-of-magnitude mistakes; whether a specific
size/dielectric/voltage/capacitance combination is actually offered is
confirmed against Samsung's product search, which the catalog itself defers to
for the live lineup.

Note on dimensions: the catalog specifies the normal-series cases by their
standard EIA/metric size codes (05 = 0402/1005, 10 = 0603/1608,
21 = 0805/2012), so the land pattern takes JITX's standard chip dimensions for
the size — the same path as the Vishay CRCW resistor family. As there, that is a
choice rather than an absence of data: the catalog's own "Structure and
Dimensions" tables are transcribed below as :data:`CL_DIMENSIONS` and asserted
against the standard table per size in ``tests/test_js1_samsung_cl.py``, so a
wrong default cannot pass unnoticed.

Datasheet (Samsung MLCC catalog, Dec 2025 revision; the filename is dated per
revision — the newest is linked from
https://product.samsungsem.com/product-catalog.do):
https://product.samsungsem.com/resources/file/product-catalog/MLCC_2512.pdf

Land-pattern construction, two-pin ``.insert()``, and value-code rounding are
shared with the chip-resistor families via :mod:`.chip_smt`.
"""

import math
from typing import Self

import jitx
from jitx.net import Net, Port
from jitx.units import F, PlainQuantity
from jitxlib.symbols.capacitor import CapacitorSymbol

from .chip_smt import (
    ChipDims,
    chip_smt_landpattern,
    compact_value,
    datasheet_dim as _t,
    insert_two_pin,
    round_sig,
)

DATASHEET_URL = (
    "https://product.samsungsem.com/resources/file/product-catalog/MLCC_2512.pdf"
)

# Imperial case size -> Samsung part-number size code (catalog "Size Code":
# 05 = 0402/1005, 10 = 0603/1608, 21 = 0805/2012).
SIZE_CODE: dict[str, str] = {
    "0402": "05",
    "0603": "10",
    "0805": "21",
}

# Dimensions (mm) from the catalog's "Structure and Dimensions" tables, for the
# thickness variant named in THICKNESS_DEFAULT below: L, W, T and BW, where BW is
# the termination band width -- the MLCC equivalent of the resistor datasheets'
# seating-plane band, and what belongs in ChipDims.lead.
#
# As in vishay_crcw, the family builds from JITX's standard chip table; this is
# transcribed so that table can be checked against the catalog per size.
CL_DIMENSIONS: dict[str, ChipDims] = {
    "0402": ChipDims(_t(1.00, 0.05), _t(0.50, 0.05), _t(0.50, 0.05), _t(0.25, 0.10)),
    "0603": ChipDims(_t(1.60, 0.10), _t(0.80, 0.10), _t(0.80, 0.10), _t(0.30, 0.20)),
    "0805": ChipDims(
        _t(2.00, 0.10), _t(1.25, 0.10), _t(0.85, 0.10), _t(0.50, 0.20, 0.30)
    ),
}

# Dielectric (EIA code) -> Samsung part-number symbol (catalog "Dielectric
# Code"): class I C0G (0 +/- 30 ppm/C) and class II X7R (+/-15% dC).
DIELECTRIC_CODE: dict[str, str] = {"C0G": "C", "X7R": "B"}

# Tolerance (fraction) -> Samsung part-number code (catalog "Capacitance
# Tolerance Code"), and which tolerances each dielectric class offers: class I
# C0G is the precision line (+/-1/2/5%); class II X7R is +/-5/10/20%.
TOLERANCE_CODE: dict[float, str] = {
    0.01: "F",
    0.02: "G",
    0.05: "J",
    0.10: "K",
    0.20: "M",
}
_ALLOWED_TOLERANCE: dict[str, tuple[float, ...]] = {
    "C0G": (0.01, 0.02, 0.05),
    "X7R": (0.05, 0.10, 0.20),
}

# Rated voltage (V DC) -> Samsung part-number code (catalog "Rated Voltage
# Code"; the full table spans 2.5 V to 3 kV — this family scopes to 16/25/50 V).
VOLTAGE_CODE: dict[int, str] = {16: "O", 25: "A", 50: "B"}

# Default thickness code per size (catalog "Thickness Code" table): the
# standard maximum-thickness variant for each case (0402 -> 0.50 mm,
# 0603 -> 0.80 mm, 0805 -> 0.85 mm). Thinner low-profile variants exist in the
# catalog; pass ``thickness_code`` explicitly to select one.
THICKNESS_DEFAULT: dict[str, str] = {"0402": "5", "0603": "8", "0805": "C"}

# Coarse capacitance envelopes (F) per (size, dielectric). These catch
# order-of-magnitude errors; exact offered values also depend on rated voltage
# and thickness — confirm the specific part via Samsung's product search.
CAP_RANGE: dict[tuple[str, str], tuple[float, float]] = {
    ("0402", "C0G"): (0.5e-12, 1e-9),
    ("0603", "C0G"): (0.5e-12, 10e-9),
    ("0805", "C0G"): (1e-12, 47e-9),
    ("0402", "X7R"): (100e-12, 100e-9),
    ("0603", "X7R"): (100e-12, 1e-6),
    ("0805", "X7R"): (100e-12, 4.7e-6),
}

# Fixed trailing part-number fields for the scoped normal line (catalog
# positions 8-11): design code N (Ni electrode / Cu termination / Ni-Sn
# plating), product code N (normal), control code N (standard), and the
# packaging code (paper tape, 7" reel = C by default).
_DESIGN_CODE = "N"
_PRODUCT_CODE = "N"
_CONTROL_CODE = "N"
PACKAGING_CODES = ("C", "8", "H", "E", "G", "F", "S", "O")
_DEFAULT_PACKAGING = "C"


def format_capacitance_code(farads: float) -> str:
    """Encode a capacitance as Samsung's 3-character picofarad code.

    Two significant figures plus a zero-count exponent, expressed in pF
    (catalog "Capacitance Code"); values below 10 pF use ``R`` as the decimal
    point. The value is first rounded to two significant figures so decade
    carries propagate.

    >>> format_capacitance_code(100e-9)
    '104'
    >>> format_capacitance_code(1.5e-12)
    '1R5'
    >>> format_capacitance_code(10e-6)
    '106'
    """
    if farads <= 0:
        raise ValueError(f"capacitance must be > 0 F, got {farads}")
    pf = round_sig(farads * 1e12, 2)
    if pf < 10:
        whole = int(pf)
        return f"{whole}R{round((pf - whole) * 10)}"
    exponent = int(math.floor(math.log10(pf))) - 1
    significant = round(pf / (10**exponent))
    if significant >= 100:  # rounding carried into a new decade (e.g. 9.96 nF)
        significant //= 10
        exponent += 1
    return f"{significant}{exponent}"


def _build_mpn(
    size: str,
    dielectric: str,
    farads: float,
    tolerance: float,
    voltage: int,
    thickness_code: str,
    packaging: str,
) -> str:
    """Assemble the Samsung CL part number (e.g. ``CL10B104KB8NNNC``)."""
    return (
        f"CL{SIZE_CODE[size]}{DIELECTRIC_CODE[dielectric]}"
        f"{format_capacitance_code(farads)}{TOLERANCE_CODE[tolerance]}"
        f"{VOLTAGE_CODE[voltage]}{thickness_code}"
        f"{_DESIGN_CODE}{_PRODUCT_CODE}{_CONTROL_CODE}{packaging}"
    )


class SamsungCL(jitx.Component):
    """A Samsung CL general-purpose MLCC, built from catalog data.

    Args:
        capacitance: Capacitance in farads (within the size/dielectric
            envelope).
        size: Imperial case code: ``"0402"``, ``"0603"``, or ``"0805"``.
        dielectric: ``"C0G"`` (class I) or ``"X7R"`` (class II).
        tolerance: Tolerance as a fraction. C0G offers 0.01/0.02/0.05
            (F/G/J); X7R offers 0.05/0.10/0.20 (J/K/M).
        voltage: Rated voltage in V DC: 16, 25, or 50 (codes O/A/B).
        thickness_code: Part-number thickness field. ``None`` uses the size's
            standard maximum-thickness variant (5/8/C for 0402/0603/0805).
        packaging: Packaging-field code. ``None`` uses ``"C"`` (paper tape,
            7" reel).
    """

    datasheet: str
    p1: Port
    p2: Port
    landpattern: jitx.Landpattern
    symbol: jitx.Symbol
    case: str
    dielectric: str
    tolerance: float
    voltage: int

    def __init__(
        self,
        *,
        capacitance: float,
        size: str = "0402",
        dielectric: str = "X7R",
        tolerance: float = 0.10,
        voltage: int = 50,
        thickness_code: str | None = None,
        packaging: str | None = None,
    ):
        if size not in SIZE_CODE:
            raise ValueError(
                f"Unknown Samsung CL size {size!r}; supported sizes: "
                f"{sorted(SIZE_CODE)}"
            )
        if dielectric not in DIELECTRIC_CODE:
            raise ValueError(
                f"dielectric {dielectric!r} not supported; choose one of "
                f"{sorted(DIELECTRIC_CODE)}"
            )
        allowed_tol = _ALLOWED_TOLERANCE[dielectric]
        if tolerance not in allowed_tol:
            raise ValueError(
                f"tolerance {tolerance} not available for {dielectric}; choose "
                f"one of {allowed_tol} "
                f"({'/'.join(TOLERANCE_CODE[t] for t in allowed_tol)})"
            )
        if voltage not in VOLTAGE_CODE:
            raise ValueError(
                f"rated voltage {voltage} V not in this family's scope; choose "
                f"one of {sorted(VOLTAGE_CODE)} (codes "
                f"{'/'.join(VOLTAGE_CODE[v] for v in sorted(VOLTAGE_CODE))})"
            )
        cap_min, cap_max = CAP_RANGE[(size, dielectric)]
        if not cap_min <= capacitance <= cap_max:
            raise ValueError(
                f"capacitance {capacitance} F out of the {size} {dielectric} "
                f"envelope ({cap_min} to {cap_max} F); confirm availability via "
                f"Samsung's product search"
            )
        if thickness_code is None:
            thickness_code = THICKNESS_DEFAULT[size]
        if packaging is None:
            packaging = _DEFAULT_PACKAGING
        elif packaging not in PACKAGING_CODES:
            raise ValueError(
                f"packaging {packaging!r} invalid; choose one of {PACKAGING_CODES}"
            )

        self.mpn = _build_mpn(
            size,
            dielectric,
            capacitance,
            tolerance,
            voltage,
            thickness_code,
            packaging,
        )
        self.manufacturer = "Samsung Electro-Mechanics"
        self.reference_designator_prefix = "C"
        self.datasheet = DATASHEET_URL
        self.value = compact_value(PlainQuantity(capacitance, F))
        self.case = size
        self.dielectric = dielectric
        self.tolerance = tolerance
        self.voltage = voltage

        self.symbol = CapacitorSymbol()
        # The catalog specifies the standard line by EIA size code only (no
        # mechanical drawing); use JITX standard chip dims for the size.
        self.landpattern = chip_smt_landpattern(size)

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
        """Place this capacitor between two pins/nets of the active circuit.

        Mirrors :meth:`jitxlib.parts.Capacitor.insert`; see
        :func:`.chip_smt.insert_two_pin`.
        """
        return insert_two_pin(self, pin_a, pin_b, short_trace=short_trace)


Device: type[SamsungCL] = SamsungCL
