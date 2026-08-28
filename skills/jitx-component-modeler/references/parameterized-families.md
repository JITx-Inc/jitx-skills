# Parameterized Component Families

The class shape behind SKILL.md's "Parameterized Component Families". Read that section first —
it carries the rules that decide whether the result is right (fail-fast validation, round-before-
encode, extract-at-the-second-family, E-series, and what to do when the catalog withholds a lineup).
This file is the *how*.

One `jitx.Component` subclass stands in for every part a manufacturer lists under one series, with
the part number computed per instance from the datasheet's own ordering scheme. No parts-database
query — the class is the data.

## The class

```python
class AcmeSeries(jitx.Component):
    """<Manufacturer> <series> — <what it is>.

    Every table below is transcribed from <document number, revision>; the
    section each came from is named at its definition. <Catalog URL.>
    """

    manufacturer = "<Manufacturer>"
    reference_designator_prefix = "R"     # or "C", "L", "FB"
    datasheet = "<url or document citation>"

    # Bare annotations: these depend on constructor arguments, so they are
    # assigned on self in __init__, not at class level.
    #
    # Never NARROW an inherited attribute's type. A mutable attribute's type is
    # invariant, so re-declaring one with a tighter type is a pyright error
    # (reportIncompatibleVariableOverride). `mpn` is inherited as `str | None`
    # and `value` as `str | PlainQuantity | None`, so `mpn: str` and
    # `value: PlainQuantity` are two errors the gate forbids you to suppress.
    # Repeating the base type exactly type-checks, but it buys nothing -- the
    # simplest way to comply is not to annotate an inherited name at all and
    # just assign it in __init__. The inherited names are `mpn`, `value`,
    # `manufacturer`, `reference_designator`, `reference_designator_prefix`,
    # `in_bom`, `soldered` and `schematic_x_out`; annotate freely below that
    # line, as `p1`/`p2`/`landpattern`/`symbol` do.
    p1: Port
    p2: Port
    landpattern: SMT
    symbol: ResistorSymbol

    def __init__(
        self,
        resistance: float,
        *,
        size: str,
        tolerance: float,
        packaging: str = _DEFAULT_PACKAGING,
        check_eseries: bool = False,
    ) -> None:
        # One call that validates every axis and returns the part number, so the
        # same checks are reachable without an instantiation context.
        self.mpn = self.build_mpn(resistance, size=size, tolerance=tolerance,
                                  packaging=packaging, check_eseries=check_eseries)
        dims = DIMENSIONS[size]
        self.p1, self.p2 = Port(), Port()
        self.landpattern = chip_smt_landpattern(_SMT_KEY[size], dims)
        self.symbol = ResistorSymbol()
        self.value = compact_value(resistance * ohm)

    @classmethod
    def build_mpn(cls, resistance: float, *, size: str, ...) -> str:
        """Validate every axis and assemble the catalog part number."""
        ...

    def insert(self, pin_a: Port | Net, pin_b: Port | Net, *, short_trace: bool = False) -> Self:
        return insert_two_pin(self, pin_a, pin_b, short_trace=short_trace)
```

Notes on each piece:

- **`build_mpn` as a classmethod is the load-bearing choice.** It is where every axis and cross-axis
  rule is checked, and `__init__` calls it. That keeps the validation reachable from a plain unit
  test, which matters because `__init__` never runs outside a JITX instantiation context — see
  SKILL.md "Verifying a component with tests".
- **Class-level attributes do not work for the parameterized members.** A family's landpattern,
  symbol and metadata depend on constructor arguments, so they are assigned on `self` with bare
  class-level annotations declaring their types. Declare `p1` and `p2` in `__init__` too, in pad
  order. This is the exception SKILL.md's "Class-Level vs Instance-Level" names.
- **`.insert()` parity** with `jitxlib.parts.Resistor` / `Capacitor` makes a family part a drop-in
  for a queried one in circuit code.
- **`value`** is the quantity the BOM prints. Round the scaled magnitude before assigning it.

## One dict per datasheet table

Transcribe tables as tables, each named for the section it came from. A reviewer should be able to
put the file next to the datasheet and read down both.

```python
# §4 DIMENSIONS AND MASS. ChipDims(L, W, H, seating-plane band).
DIMENSIONS: dict[str, ChipDims] = {
    "0402": ChipDims(dim(1.00, 0.10), dim(0.50, 0.10), dim(0.35, 0.05), dim(0.25, 0.15)),
    ...
}

# §2 case labels -> standard chip-table key, matched by body L x W, not by label.
_SMT_KEY = {"0075": "009005",  # 0.30 x 0.15 mm
            "0402": "0402", ...}

# §6 tolerance codes.        §7 packaging codes, per size.
TOLERANCE_CODE = {0.01: "F"}  PACKAGING = {"T": frozenset({...})}
```

## The shared module

Extracted when the second family lands, never before. What belongs in it — none of this is
vendor-specific, and none of it is resistor-specific either, which is why it gets a
component-agnostic name as soon as a second component type uses it:

| Helper | Does |
| --- | --- |
| `ChipDims` | body + seating-plane-band dimensions, one per case size |
| `datasheet_dim(typ, plus, minus=None)` | a `Toleranced` from a datasheet's nominal and its ± tolerances; chip datasheets print asymmetric ones |
| `round_sig(value, n)` | carry-correct significant-figure rounding, for the value encoders |
| `compact_value(quantity)` | `to_compact()` without the binary-float noise it reintroduces |
| `chip_smt_landpattern(size_key, dims=None)` | the `SMT` chain, datasheet dims overriding the defaults |
| `insert_two_pin(component, a, b, *, short_trace=False)` | `.insert()` parity with the queried passives |

What stays per-family: the value encoder, the size / rating / range tables, and the part-number
f-string. Three vendors, three encoders — see SKILL.md "Value-code encoders".

## Generalizing across component types

What changes between component types is the axis set and the encoder, not the structure. A capacitor
family adds dielectric and rated voltage, uses `CapacitorSymbol` and `reference_designator_prefix =
"C"`, and encodes picofarads instead of ohms; the chip geometry, the two-pin `.insert()` and the
rounding are the same calls. That is the test of whether the extraction in the table above was drawn
in the right place: if adding the second component type forces a change to a shared helper's
signature, the split was wrong.

## The test file

One per family, mirroring SKILL.md's "Verifying a component with tests". The family-specific
additions to that list:

- Every case size instantiated at least once, so every land pattern is exercised.
- The encoder unit-tested directly, including the decade-carry cases the datasheet's own worked
  examples name.
- Validation raising on each invalid axis **and** on the cross-axis combinations the catalog
  excludes.
- The standard chip table asserted against the datasheet per size, with a known-bad entry pinned as
  still-wrong so its override is removed when the library is fixed.
