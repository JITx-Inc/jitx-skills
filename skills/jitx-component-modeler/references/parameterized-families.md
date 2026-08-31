# Parameterized Component Families

This file owns the two-terminal chip and parameterized-family paths. Read "Two-Terminal Chip
Components" and "Parameterized Component Families" below before using the class shape. Those
sections carry the rules that decide whether the result is right: fail-fast validation,
round-before-encode, extract-at-the-second-family, E-series, and what to do when the catalog
withholds a lineup. The opening sections carry the implementation shape.

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
    p1: Port
    p2: Port
    landpattern: SMT
    symbol: ResistorSymbol
    mpn: str
    value: PlainQuantity

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
  [verification-and-application.md](verification-and-application.md#verifying-a-component-with-tests).
- **Class-level attributes do not work for the parameterized members.** A family's landpattern,
  symbol and metadata depend on constructor arguments, so they are assigned on `self` with bare
  class-level annotations declaring their types. Declare `p1` and `p2` in `__init__` too, in pad
  order. This is the exception [component-code-patterns.md](component-code-patterns.md#class-level-vs-instance-level) names.
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
f-string. Three vendors, three encoders — see "Value-code encoders" below.

## Generalizing across component types

What changes between component types is the axis set and the encoder, not the structure. A capacitor
family adds dielectric and rated voltage, uses `CapacitorSymbol` and `reference_designator_prefix =
"C"`, and encodes picofarads instead of ohms; the chip geometry, the two-pin `.insert()` and the
rounding are the same calls. That is the test of whether the extraction in the table above was drawn
in the right place: if adding the second component type forces a change to a shared helper's
signature, the split was wrong.

## The test file

One per family, following [verification-and-application.md](verification-and-application.md#verifying-a-component-with-tests). The family-specific
additions to that list:

- Every case size instantiated at least once, so every land pattern is exercised.
- The encoder unit-tested directly, including the decade-carry cases the datasheet's own worked
  examples name.
- Validation raising on each invalid axis **and** on the cross-axis combinations the catalog
  excludes.
- The standard chip table asserted against the datasheet per size, with a known-bad entry pinned as
  still-wrong so its override is removed when the library is fixed.

## Two-Terminal Chip Components

Chip resistors, MLCCs, chip inductors and ferrite beads share one land-pattern generator and one set of failure modes. All three of the failures below produce a land pattern that is **valid, builds, and is wrong**; none of them is caught by a type check, a test that only counts pads, or `jitx build`.

```python
from jitxlib.landpatterns.leads import LeadProfile, SMDLead
from jitxlib.landpatterns.leads.protrusions import BigRectangularLeads, SmallRectangularLeads
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.landpatterns.twopin.smt import SMT
from jitxlib.landpatterns.twopin.SMT_table import SMT_CHIP_DEFS   # the standard size table

# Standard dimensions for the size:
landpattern = SMT("0603")

# Datasheet dimensions overriding them:
landpattern = SMT("0603").lead_profile(
    LeadProfile(
        span=body_length,                  # L, termination end face to end face
        pitch=0.0,                         # ignored for a two-terminal chip
        type=SMDLead(
            length=band,                   # the seating-plane termination band — see below
            width=body_width,
            lead_type=protrusion,          # see below — pick it, don't guess a threshold
        ),
    )
).package_body(RectanglePackage(width=body_width, length=body_length, height=body_height))
```

`SMT_CHIP_DEFS` is keyed by case size and each entry carries `.length`, `.width`, `.lead_length` and `.lead_width` as `Toleranced`. Declare two ports, `p1` and `p2`, in that order; declaration-order mapping handles the rest and no `PadMapping` is needed. Use `ResistorSymbol` / `CapacitorSymbol` / `InductorSymbol` from `jitxlib.symbols`, not a `BoxSymbol`.

**Choosing the protrusion.** `SmallRectangularLeads` and `BigRectangularLeads` (from `jitxlib.landpatterns.leads.protrusions`) are protrusion *instances*, not classes — pass them, don't call them. They carry different fillet goals, so the choice moves copper, and it belongs in the `Library defaults` row like any other. `jitxlib` publishes no size threshold for picking between them: read the two protrusions' own fillet values and choose against what the package actually is, or take the choice from a land-pattern recommendation the datasheet gives. **Do not copy a body-width cutoff from another model** — a bare `width > 0.8` in a geometry path is exactly the uncited constant the no-fabrication rule forbids everywhere else, and it is easy to inherit without noticing.

### Matching a vendor size label to the generator's size key

**Match by body L × W, not by the label.** Vendors print imperial labels, metric labels and house codes interchangeably, and the small end of the range is where they diverge: a vendor's `0075` is a 0.30 × 0.15 mm body, which the standard table keys as `009005`. Read the body dimensions out of the datasheet's dimension table, then find the `SMT_CHIP_DEFS` entry that matches them. A small dict mapping vendor label → size key, with the body dimensions in a comment, is the readable form; a bare `size` string passed straight through is the form that silently builds the wrong pattern.

**A size the table appears not to offer is a claim to check, not a size to drop.** Walk the whole of `SMT_CHIP_DEFS` — imperial keys and metric aliases both — before concluding the geometry is absent, because a label mismatch looks exactly like a missing size. If it really is absent, say so: name the size, name the body dimensions you looked for, and tell the user, rather than quietly shipping a model that covers less than its datasheet does.

### The two termination bands — which one is the solderable land

**Every chip datasheet prints two termination bands and labels neither "solderable".** The one that belongs in the land pattern's lead length is the band dimensioned **on the seating plane** — the bottom face that meets the pad. The other is the wrap-up on the end face, and the pad is not sized from it. The dimension symbols differ by vendor and none of them says which is which, so read the outline drawing and follow the dimension line to the seating plane; do not pick by which symbol looks familiar.

Cross-check the answer across manufacturers before committing to it. For a given case size the seating-plane band agrees between vendors to within a few hundredths of a millimetre, while the wrap-up band does not. Picking the wrong one is a pad shift of a few hundredths on a small chip and substantially more on a large one — still valid, still building, still wrong.

### Taking the standard table's dimensions is a verification obligation, not a shortcut

Passing the generator a bare size key and no datasheet override is the right call when a datasheet specifies its cases only by standard EIA/IEC size code. **It is not a licence to skip reading the dimension table.** The standard table is a convenience, not an authority: wherever the datasheet publishes dimensions, transcribe them anyway and add a test asserting the table against them per size. Where a size disagrees, override that one size from the datasheet and say why in a comment. The whole risk of taking the defaults is that nobody transcribed the numbers that would have caught a bad one.

**The table's entries have changed between versions, so read the one you have.** `SMT_CHIP_DEFS["2512"]` carried a `lead_length` of `2.0 ± 0.5 mm` on 4.2.2 and 4.4.0rc3, against roughly `0.60 ± 0.20 mm` in manufacturers' tables — a band nearly a third of the body length, sizing the pads from a termination three times too long. Later `jitxlib` corrects it, along with several neighbouring case sizes and a metric alias. Hard-code neither value: compare the installed table against the datasheet per size, override from the datasheet where they disagree, and pin the disagreement in a test that *fails once the table is corrected*, so the workaround is removed on upgrade rather than left to rot.

**Density level is a default too, and it is the one that gets missed** — because it never appears as a number in your code. See the `Library defaults` row of the completeness check: read what the source asks for, check what your installed `DensityLevelContext` actually defaults to, and either set the level explicitly or record that the default already matches.

## Parameterized Component Families

Sometimes the right model is not one part but one **catalog family**: a single `jitx.Component` subclass standing in for every part a manufacturer lists under one series, with the part number computed per instance. It replaces a parts-database query with the datasheet — the class *is* the data. It works offline, it is reviewable against the datasheet line by line, and it can produce a value the database never stocked.

**A queried passive is still the default.** `jitxlib.parts.Resistor(resistance=10e3)` and its siblings are the normal way to place a passive, and `jitx-circuit-builder` owns that path. Build a family class when the user asks for a family, a series, or "any value in this package"; when the design must build with no parts database reachable; or when a specific series is required and the query cannot express it. Do **not** build one to model a single named part — that part gets the ordinary single-MPN treatment in [component-code-patterns.md](component-code-patterns.md#step-3-generate-component-code).

The opening sections of this file carry the class shape, shared/per-family split, and worked family. The rules that decide whether the result is right follow.

### Fail-fast validation

**Validate every axis and raise `ValueError` with the valid options in the message.** A family accepts arguments a single-part class never sees, so an unsupported size or a tolerance grade the series does not offer must fail where the caller can read what to pass instead:

```python
if size not in DIMENSIONS:
    raise ValueError(f"unknown {SERIES} size {size!r}; supported: {sorted(DIMENSIONS)}")
```

Validate the **cross-axis** rules too, not only the individual ones. The combinations a catalog does not offer — a tolerance grade available at only one temperature coefficient, a packaging code available on only two sizes, a dielectric absent from the smallest case — are where a generated part number turns into a part nobody sells, and each axis on its own looks fine.

MPN construction refuses to return until every individual and cross-axis check passes. Verification stays open until tests exercise every invalid axis and excluded combination.

**Key a coded axis on the datasheet's own code, not on a float.** A tolerance table maps `F` to ±1 %, so a `dict[float, str]` keyed on `0.01` makes the public constructor depend on float equality — `1/100` and `0.010000000000000002` are different keys, and the failure is a spurious "unsupported tolerance". Take the code as the argument, or key the dict on it, and convert to a number for display only.

**Put the checks where they will actually run.** Validation reached only through `__init__` does nothing outside a JITX instantiation context, because `__init__` does not run there — see [verification-and-application.md](verification-and-application.md#verifying-a-component-with-tests). A pure classmethod that builds and validates the part number, which `__init__` then calls, runs in both places and is the more testable shape.

### Value-code encoders — round before you encode

**Round to significant figures first, then encode.** Manufacturer value codes are fixed-width significand-plus-multiplier fields, and encoding an unrounded value truncates instead of carrying: a value that rounds up across a decade must carry into the multiplier, never emit the un-carried significand or a malformed field. Split the *rounded* number, and unit-test the decade-carry cases explicitly — the happy-path values pass either way, which is why this ships.

Verification stays open until the value-encoder unit tests include decade-carry cases and pass.

**Do not force one encoder across vendors.** Value-code schemes genuinely differ, and one shared encoder with a mode flag per vendor is harder to check against a datasheet than three short functions. The encoder is the per-family part; the rounding helper is the shared part.

### Shared helpers — extract at the second family

**Write the first family self-contained, and extract the shared helpers when the second one lands** — not before. One family gives you no evidence about which pieces are vendor-agnostic; two do. Refactoring the first family onto the extracted helpers with *its tests unchanged* is what proves the extraction safe. The durable split: land-pattern construction, the two-pin `.insert()`, datasheet-tolerance-to-`Toleranced` conversion and significant-figure rounding are shared; the value encoder, the size / rating / range tables and the part-number f-string are per-family. When a shared module first serves a second component type, rename it for what it actually is — a module called `chip_resistor.py` that a capacitor family imports is a name that lies — and re-run the full suite after the rename.

### E-series checks

`jitx-circuit-builder` owns the rule for *choosing* a passive value — use the `eseries` package, default E96. A family class sits on the other side of that transaction: it is handed a value and must say whether the series actually makes it. **Pick the series from the part's tolerance grade, not from a global default.** A ±5 % part is built on E24, and accepting an E96 value for it produces an orderable-looking part number for a part that does not exist. Do not reach past what the datasheet says the family is built on in either direction — a tight grade a manufacturer builds on E96 does not become E192 just because the tolerance is tight. Make the check opt-in so a deliberate non-standard value stays possible, and add a series when a family that needs it lands, not in anticipation.

When the opt-in check is enabled, MPN construction raises `ValueError` for a value outside the source-stated series. Verification stays open until tests pin each tolerance-to-series mapping and the deliberate bypass.

### When the catalog does not publish what you need, say so

Overview and selector-guide editions routinely omit the per-size value lineup the full series datasheet carries. Validate what the document *does* state — the ordering code, the published significand grid, the size / voltage / dielectric offering — record the gap in the docstring, and tell the user which envelope is checked and which is not. Do not invent ranges to make the validation look complete: a range nothing backs is the same failure as a dimension nothing backs.
