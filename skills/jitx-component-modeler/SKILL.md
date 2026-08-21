---
name: jitx-component-modeler
description: "Create JITX Python component code from datasheets, KiCad footprints, or user specifications. ALWAYS use this skill when user asks to \"create a component\", \"model a part\", \"generate a component\", \"add a component\", or \"make a JITX component\" - even without a datasheet. Also triggers on part numbers (NE555, LM1117, RP2040, etc.), package types (SOIC, QFN, BGA, SON, SOT), and two-terminal chip sizes (0402, 0603, 2512). Supports user-provided data, JITX generators for standard packages, and optional LCSC/EasyEDA fallback for non-standard footprints. Supports multi-unit symbols, thermal pads, and complex pin mappings. Also covers parameterized catalog families — one class standing in for a manufacturer's whole series (chip resistors, MLCCs) with the part number computed per instance and no parts-database query — and verifying a component against its datasheet with jitx.test.TestCase. Also covers generating a component from a vendor's machine-readable package pinout file rather than a drawing (\"generate the FPGA from the pin file\", \"parse the package pinout file\", \"model this 1000-ball BGA\"): parse-don't-transcribe, reconcile the ball inventory before emitting, and a committed generator with a regenerate-and-diff check. For choosing and placing an ordinary queried passive, use jitx-circuit-builder instead."
---

# JITX Component Generation Skill

Generate JITX Python component code from datasheets, user-provided KiCad footprints, or specifications. Data can come from multiple sources — always prefer user-provided data over automated lookups.

A component task is **not complete** until the **Component completeness check** block (near the end of this skill) is filled out, row by row, **as a written artifact alongside the code** — a `COMPLETION.md` next to the components, or the equivalent your project already uses. Prose that paraphrases some of its rows is not the block, and neither is a filled block that exists only in the chat you are having: the next person to open the directory, human or agent, sees the files. A block nobody can find later did not happen. It is the component-specific expansion of the base `jitx` skill's task-acceptance block, not a rival to it — embed it under that block's `Checks run` field rather than producing two competing completion artifacts. No filled block, no "done".

## No fabrication — source authority for geometry and pinout

> **Do not write dimensions, pin labels, or pad assignments from memory.**
>
> If you find yourself writing **"typical dimensions"**, **"reasonable defaults"**, **"user can refine specific values later"**, **"approximate"**, **"will adjust later"**, or any synonym for guessed / default / placeholder geometry on a component that has a real MPN, **stop**. This skill is not a pattern catalog you can skim and walk away from — it is the rule that you don't ship a landpattern from memory.
>
> For every named component (anything with an MPN, distributor part number, or user-supplied datasheet), before writing landpattern dimensions or pin labels, work down this ladder until you have a source:
>
> 1. **Manufacturer's current datasheet** — open the mechanical drawing page (use `extract_pages.py` to pull only those pages — do not read the full PDF). Cite the page/figure where you got each dimension.
> 2. **Manufacturer's machine-readable pin file** — where the vendor publishes the pin map as data rather than as a drawing (FPGAs, large SoCs, most high-ball-count BGAs). It is the authority for **names, balls and banks only**; geometry still comes from the packaging document, and the two never substitute for each other. Parse it — do not transcribe it, and do not read a sample and extrapolate. See "Generating a component from a machine-readable vendor pin file".
> 3. **Sourcing-channel lookup** — if the user has named LCSC/JLCPCB, `parts2jitx-lcsc <C-number>` (stock, lifecycle, datasheet URL) and `parts2jitx-lcsc <C-number> --pinout` (pin labels). Use it as channel evidence and as a pin-label cross-check. Datasheet remains higher authority where they disagree; document the conflict.
> 4. **Ask the user** — for an LCSC C-number, a user-supplied `.kicad_mod`, or the datasheet itself.
>
> If none of the four produce a source, the component is **blocked**. Do not proceed by estimating. The only way out is for the user to explicitly authorize a non-MPN generic component (e.g. "use a typical 0.4 mm pitch QFN-56, this is a placeholder"). Record that authorization in the task acceptance block under `Notes`.
>
> **Carve-out — parameterized catalog families.** A class that models a manufacturer's whole catalog series has no single MPN by construction: it *computes* one per instance from the datasheet's own part-numbering scheme. That is not the fabrication this rule forbids, and it needs no user authorization — the source authority is the same datasheet, and every dimension, code table and range still traces to a page of it. What the rule still forbids is a family with no datasheet behind it: a size table from memory, a "typical" termination band, an ordering scheme inferred from one example part. In place of the single MPN, a family owes one extra piece of evidence — a generated part number reproduced against the datasheet's own worked ordering example. See "Parameterized Component Families".
>
> The rule is also about values that could be wrong, not about labels the source never supplied. A two-terminal chip datasheet does not name its terminations, so `p1`/`p2` with declaration-order pad mapping is the framework's sanctioned idiom, not an invented pin label.
>
> This callout exists because a test session of this skill loaded this very file, said "I have the patterns, I'll proceed without invoking the modeler skill further — writing each component directly with reasonable typical dimensions" — and then fabricated nine components. That is the failure this rule forbids.

### When no document states an MPN

`mpn` is identity: it drives sourcing, and the source-authority ladder above keys on "anything with an MPN". So it is not a field to fill in on the way past — and there are real parts whose ground-truth documents do not contain one.

A pin file's header typically gives a **device string** (`xcvp1002nfvi1369`), and a packaging manual gives a package. Neither is an orderable part number: a real one usually also encodes **speed grade and temperature range**, which are procurement decisions, not properties of the silicon or the package. The governing rule applies unchanged — if the data doesn't say it, ask.

**Raise it at a gate, not at the end.** Where the user is already confirming device and package, ask what to use as the MPN in the same breath, and say what the documents do and do not identify. Then set it to what was agreed, with a comment recording what it identifies.

The reason this needs saying: an orderable part number is highly *guessable in shape*, which is exactly what makes a fabricated one dangerous — it looks right. And nothing downstream catches it. `pyright`, `pytest`, the build and `jitx-code-review` all pass on a wrong MPN, while every other unknown in a component (a pin, a bank, a dimension) is gated by a reconciliation or a human check. This is the one place where "estimate nothing" has no corresponding checkpoint unless you add one.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

## Datasheet Handling

**ALWAYS save datasheets locally before reading.**

When user provides a URL or asks to download a datasheet:
1. Download the PDF using curl or wget via Bash
2. Save to `datasheets/<mpn>.pdf` in the project (create folder if needed)
3. Then use the extraction process in Step 0

This ensures:
- Datasheet is available for future reference
- Consistent file paths for extraction scripts
- No repeated downloads

If the project keeps a gitignored scratch directory for source documents, save there instead and do not commit the PDF. Either way the component's `datasheet` attribute and its module docstring carry the URL — that is the durable record, not the file.

### Verify the download is a datasheet

**Check the file's magic bytes before extracting anything from it.** A PDF begins `%PDF-`. Distributor mirrors and CDN edges serve bot-block or consent-wall HTML under a `.pdf` URL with a 200 status, and PyMuPDF will not tell you: it either raises a generic "cannot open broken document" or opens the markup as a one-page render and hands back an empty page list. A 12 kB "datasheet" is the other tell.

`scripts/extract_pages.py` enforces this itself — it checks the magic bytes and exits non-zero with the reason before touching PyMuPDF, so a mirror page fails loudly instead of extracting nothing. Fetching by hand, check it by hand:

```bash
file datasheets/<mpn>.pdf        # expect: PDF document, version 1.x
head -c 5 datasheets/<mpn>.pdf   # expect: %PDF-
```

**Unreachable is not the same as dead.** A manufacturer URL the user gave you, or one printed in a catalog, is canonical: a timeout or TLS failure on it is more likely your egress path — proxy, sandbox, geo-block — than a moved file. Say which one you hit. Never silently substitute an aggregator's copy for a manufacturer URL that merely didn't answer; if the document really has moved, find the current equivalent on the manufacturer's own site and tell the user which URL you used and why.

**Catalog filenames are dated per revision.** Where the only link you have embeds a date or revision in the filename, record the manufacturer's catalog index page in the component docstring alongside the direct link — the direct link rots at the next revision, the index does not.

### Cite by caption first, figure number second

**Figure and table numbers move between editions of a living document.** Large packaging and pinout
manuals are revised continuously at a stable URL, and a revision that inserts one figure renumbers
every figure after it.

This is worse than a dead reference, and the difference matters. A dead link fails loudly. A drifted
figure number still **resolves** — to a *different* figure, often of the same kind, for a different
part in a different package. Jump to the number without reading the caption and you get plausible
geometry with no signal that anything is wrong: every dimension downstream is then silently wrong,
and a geometry cross-check still passes, because it compares the land pattern against whatever the
package spec was populated with.

So write the citation with the **caption as the primary key**:

> the figure captioned *Package Dimensions for NFVI1369* — Figure 273 in AM013 v1.10; the number
> moves between editions

and when you locate it, **grep for the caption, not the number**. Record caption, edition and page
in the code next to the values it sourced, so the next reader can re-locate it after the next
revision rather than re-deriving which figure was meant.

Any citation of a living document by bare number has a shelf life. Treat one you were *handed* the
same way: verify the caption matches before you use the number, and say so if it doesn't.

**AVOID REDUNDANT WEB SEARCHES**

Once the datasheet PDF is available, extract pinout, package dimensions, and pin descriptions from it using Step 0. Do NOT search for info that's already in the datasheet. **Also: do NOT write dimensions or pin labels from memory or "typical values" when the datasheet is available.** See "No fabrication — source authority for geometry and pinout" at the top of this file.

**When additional searches ARE appropriate:**
- Datasheet lacks package mechanical drawings (common for simple parts)
- Complex packages (200+ pins) where cross-referencing helps catch errors
- Need separate package drawing document (e.g., TI's MPDS files)

**When searching:**
- Use manufacturer sites: ti.com, analog.com, st.com, nxp.com, microchip.com, infineon.com, onsemi.com
- Search pattern: `"<MPN> datasheet" site:<manufacturer>.com`
- Avoid distributor sites, random aggregators, or unverified PDFs

## Output Location

**ALWAYS place components in a `components/` folder**, even for single components.

### Standard Structure
```
project/
└── <namespace>/
    └── components/
        ├── __init__.py
        ├── <category>/
        │   ├── __init__.py
        │   └── <manufacturer>_<mpn>.py
        └── <category>/
            └── ...
```

For a project without a namespace package, place components at the root:
```
project/
└── components/
    ├── __init__.py
    └── <manufacturer>_<mpn>.py
```

**Category examples:** mcus, connectors, power_linear_regulators, opamp, flash, crystals, leds, logic, timers, buttons, transceivers, diodes_tvs, isolators, power_switchmode

**File naming:** `<manufacturer>_<mpn>.py` - lowercase, underscores for spaces/special chars
- `texas_instruments_NE555.py`
- `raspberry_pi_RP2040.py`
- `renesas_DA14705.py`

## Anti-string-hacking — read before building arrays of pins / lanes / bundles

For any component with N parallel siblings (BGAs, multi-channel ICs, banked diff-pairs), reach for `self.pins: list[Port]` or `self.lanes: list[DiffPair]` — **never** `self.TX_b0, self.TX_b1, ...` plus `getattr(self, f"TX_b{i}")` to iterate. See `jitx/references/architectural-patterns.md` § "Sibling attributes → array attributes" before writing the constructor. Also: do not assign `refdes=`, net names, or other JITX-assigned values yourself (§ "Don't assign what JITX assigns").

For a same-model self-critique pass on the component after writing (catches what these rules don't), invoke `jitx-code-review`. Optional for single-task use.

## A `Port` has exactly one home

**Never store a collection of the component's own ports as a second attribute.** A `Port` belongs to
exactly one place in the object tree, and stashing the same ports under a second name — `self.bank_groups = [...]`, `self.rails = {...}` — fails translation with:

```
Child object encountered multiple times
```

The grouping itself is usually a legitimate thing to want: a bank roster, a lane grouping, a list of
supply rails to tie. Expose it as a **method returning fresh records**, not as stored state:

```python
def bank_pins(self) -> dict[int, list[Port]]:      # computed per call
    return {700: [self.IO_0_700, self.IO_1_700, ...], ...}
```

The distinction is ownership, not syntax. `self.symbols = [BoxSymbol(...), ...]` is fine — the
component owns those symbols and nothing else does. `self.bank_groups = [[self.IO_0_700, ...]]` is
not — those ports already have a home.

Design the groupings as methods from the start. Retrofitting this after the fact means unpicking
every consumer, and the error message names the symptom rather than the attribute that caused it.

## Generating a component from a machine-readable vendor pin file

When the vendor publishes the pin map as data — FPGAs, large SoCs, most high-ball-count BGAs — do not
transcribe it. Write a small standard-library generator that parses the vendor file, **reconciles the
inventory before any component code exists**, and emits the component module as Python. Commit the
generator and the emitted module; the vendor file stays in the gitignored scratch directory, recorded
by sha256 and URL in the emitted header.

See [references/pin-file-generation.md](references/pin-file-generation.md) for the full pattern:
reconcile-before-emit and the partition property, the `--report` / `--check` generator shape,
deterministic *and* formatter-stable emission, provenance, coordinates-not-ball-strings, where the
human gates go, and what to test.

## Instructions

When generating a JITX component from a datasheet or specification, follow this structured approach:

### Step 0: Handle Datasheets (CRITICAL)

**NEVER read a full datasheet PDF directly.** Even 50-page PDFs consume excessive context.

**Always extract relevant pages first** using `scripts/extract_pages.py`:

```bash
# Find pages containing keywords
python scripts/extract_pages.py datasheet.pdf --find "pinout" "pin description" "dimension" "package" "ball map" "mechanical"

# Extract matched pages to a smaller PDF
python scripts/extract_pages.py datasheet.pdf --pages 10 11 12 -o datasheet_extract.pdf
```

Then read only the extracted PDF.

**Key pages to find:**
- Pin assignment / ball map (usually pages 10-20)
- Pin description table
- Package mechanical drawing (usually near end)
- Ordering information

**If pymupdf not available**, ask user to provide:
- Pin count and package type
- Screenshot of pinout/ball map
- Package dimensions (body size, pitch, ball/lead size)

**Do NOT** just read the PDF and hope for the best - this will exhaust context.

### Step 1: Extract Key Information

**Before generating from scratch:** for a reusable IC family or common package pattern, search existing references first — see `jitx/references/parts-sourcing.md` "Reference Search Order for Component Modeling". User libraries → `jitxexamples.components` → vendor reference design → generate. Document `searched: found <path>` or `searched: no analog` in the task acceptance block.

**IMPORTANT: Multiple Packages/Variants**

If the datasheet covers multiple package options or component variants, ask the user which one to model:

```
Example: "The datasheet shows 3 package options for this part:
- SOIC-8 (NE555DR)
- PDIP-8 (NE555P)
- VSSOP-8 (NE555DGKR)

Which package would you like me to model?"
```

Do NOT assume or pick one arbitrarily. Ask first.

From the datasheet (or extracted pages), extract:
1. **Component identification**: Manufacturer, MPN, description
2. **Package type**: SOIC, SOT, QFN, BGA, SON, etc.
3. **Pin count**: Total number of pins
4. **Pin functions**: Pin names and functions from pinout table (see Pin Naming below)
5. **Package dimensions**:
   - Body width/length (D, E dimensions)
   - Body height (A dimension)
   - Lead span (E1/D1 or terminal span)
   - Lead pitch (e dimension)
   - Lead width (b dimension)
   - Lead length (L dimension)

### Step 2: Select Package Generator

Use this decision tree to select the appropriate generator:

```
Is it a two-terminal chip? (rectangular ceramic body, one metallised
termination band wrapped around each end — chip resistor, MLCC, chip
inductor, ferrite bead)
├── Yes → SMT("<size_key>") from jitxlib.landpatterns.twopin.smt
│         See "Two-Terminal Chip Components" below for the size key, the
│         termination band, and the obligation that comes with the defaults.
│         Other two-terminal bodies are NOT chips — confirm against the
│         outline drawing before taking this branch: axial → twopin.axial;
│         molded tantalum or an SOD-/SMA-/SMB-style diode → twopin.molded;
│         a 2- or 3-lead plastic body with formed leads → the SOT generators.
└── No → Is it a 2-sided package?
    ├── Yes, ≤6 pins → SOT23_3, SOT23_5, or SOT23_6
    ├── Yes, >6 pins with gull-wing leads → SOIC
    ├── Yes, >6 pins with flat leads (no-lead) → SON
    └── No (4-sided or array)
        ├── 4-sided gull-wing leads → QFP
        ├── 4-sided flat/no-lead → QFN
        ├── Bottom ball array → BGA
        └── Custom/unusual (connectors, RF modules, irregular pads)
            → Convert from a KiCad footprint (.kicad_mod):
              parts2jitx-kicad fp.kicad_mod --class-name MyPart
              NEVER hand-craft pad positions for non-standard packages.

Exception: mechanical / vendor-defined footprints (Tag-Connect TC2050,
pogo-pin fixtures, castellated edges, fiducials, board-edge contacts).
No purchasable component model exists; vendor mechanical drawing is
the source of truth. See parts-sourcing.md "Mechanical / Vendor-Defined
Footprints" for the workflow and verification checklist.
```

### Standard-Package Decision Rule (parts2jitx + LCSC workflows)

When using `parts2jitx-lcsc` for a part whose package is in the standard set (`QFN`, `SON`, `DFN`, `SOIC`, `SOT-23`, `SOT-223`, `QFP`, `BGA`), use `parts2jitx-lcsc` for stock / pricing / pinout evidence and **default to the JITX generator** for the landpattern, with dimensions from the datasheet's mechanical drawing.

| LCSC package | Use parts2jitx for | Default landpattern |
|--------------|--------------------|---------------------|
| QFN-* | Stock, pinout, datasheet URL | `QFN(...)` |
| SON-* / DFN-* | Stock, pinout, datasheet URL | `SON(...)` |
| SOIC-* | Stock, pinout, datasheet URL | `SOIC(...)` |
| SOT-23 / SOT-223 | Stock, pinout, datasheet URL | jitxlib standard library |
| QFP-* | Stock, pinout, datasheet URL | `QFP(...)` |
| BGA-* | Stock, pinout, datasheet URL | `BGA(...)` |
| Non-standard (connectors, RF modules, irregular pads) | Stock, pinout, footprint download | KiCad import via `parts2jitx-kicad` |

Why default to the generator: JITX standard generators use datasheet mechanical dimensions and produce reviewable, parameterized code. KiCad-imported footprints carry the importer's quirks, may use non-standard pad shapes, and are harder to audit against the datasheet.

**Fall back to KiCad import when the generator can't represent the package.** Some "QFN-like" parts (especially regulators from TI, Micrel, Microchip) have specialty paddle geometry — split paddles, non-standard thermal pad dimensions, asymmetric layouts — that the generic `QFN(...)` / `SON(...)` generator can't express cleanly. When this happens:

1. Try the generator first against the datasheet mechanical drawing.
2. If the generator can't represent the paddle (or the lead layout), import the KiCad footprint via `parts2jitx-kicad` and verify pad-by-pad against the datasheet.
3. Document the reason for falling back in the task acceptance block under `Notes` (e.g. "TPS62903 split thermal paddle not expressible in QFN generator — imported from KiCad and verified against figure 9-1 page 18").

**Getting a .kicad_mod for non-standard packages** (in priority order):
1. **User-provided** — ask if they have a `.kicad_mod` from their KiCad library or manufacturer download
2. **Manufacturer KiCad library** — many vendors (Molex, TE, Amphenol) publish official KiCad footprints
3. **LCSC / EasyEDA footprint ingestion (requires explicit per-project approval)** — using EasyEDA-sourced `.kicad_mod` as the footprint data source needs user opt-in (terms of use). `parts2jitx-lcsc` *lookup/evidence* is implied when LCSC/JLCPCB is the named sourcing channel, but downloading and converting the footprint is the separate, opt-in path. Install `parts2jitx` if not already available, then use:
   ```bash
   pip install parts2jitx
   parts2jitx-lcsc C165948 --footprint -o kicad_footprints/fp.kicad_mod
   parts2jitx-kicad kicad_footprints/fp.kicad_mod --class-name MyPart
   ```
   Ask the user before using LCSC data — commercial users may not want EasyEDA-sourced data in their project.

### Step 3: Generate Component Code

Use this template structure:

```python
"""
{Manufacturer} {MPN} - {Description}

Component definition for the {full description}.
"""

import jitx
from jitx import PadMapping
from jitx.net import Port
from jitx.toleranced import Toleranced
from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column
# Import appropriate landpattern generator:
# from jitxlib.landpatterns.generators.soic import SOIC, SOIC_DEFAULT_LEAD_PROFILE
# from jitxlib.landpatterns.generators.sot import SOT23_3, SOT23_5, SOT23_6, SOTLead, SOTLeadProfile
# from jitxlib.landpatterns.generators.qfn import QFN, QFNLead
# from jitxlib.landpatterns.generators.son import SON, SONLead
# from jitxlib.landpatterns.generators.bga import BGA
from jitxlib.landpatterns.leads import LeadProfile
from jitxlib.landpatterns.package import RectanglePackage


class {ComponentClassName}(jitx.Component):
    """Brief description of the component."""

    mpn = "{MPN}"
    manufacturer = "{Manufacturer}"
    reference_designator_prefix = "U"  # or "Q" for transistors, etc.
    datasheet = "{datasheet_url}"

    # Define ports for each pin
    # Single pins:
    VCC = Port()
    GND = Port()

    # Pin arrays (for many similar pins):
    GPIO = [Port() for _ in range(N)]

    # Landpattern definition
    landpattern = (
        {Generator}(num_leads=N)
        .lead_profile(...)
        .package_body(...)
        # Optional: .thermal_pad(...)
    )

    # Symbol definition — use BARE attribute names (GND, VCC), NEVER self.GND
    # (self does not exist at class scope)
    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(...),
            right=PinGroup(...),
        ),
        columns=Column(
            up=PinGroup(...),    # Power pins typically go up
            down=PinGroup(...),  # Ground pins typically go down
        ),
    )

    # For non-standard pin ordering, add explicit mapping in __init__:
    def __init__(self):
        lp = self.landpattern
        self.mappings = [PadMapping({
            self.PIN1: [lp.p[1]],
            self.PIN2: [lp.p[2]],
            # ...
        })]


Device: type[{ComponentClassName}] = {ComponentClassName}
```

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

**A queried passive is still the default.** `jitxlib.parts.Resistor(resistance=10e3)` and its siblings are the normal way to place a passive, and `jitx-circuit-builder` owns that path. Build a family class when the user asks for a family, a series, or "any value in this package"; when the design must build with no parts database reachable; or when a specific series is required and the query cannot express it. Do **not** build one to model a single named part — that part gets the ordinary single-MPN treatment in Step 3.

For the class shape, the shared/per-family split, and a worked family, see [references/parameterized-families.md](references/parameterized-families.md). The rules that decide whether the result is right:

### Fail-fast validation

**Validate every axis and raise `ValueError` with the valid options in the message.** A family accepts arguments a single-part class never sees, so an unsupported size or a tolerance grade the series does not offer must fail where the caller can read what to pass instead:

```python
if size not in DIMENSIONS:
    raise ValueError(f"unknown {SERIES} size {size!r}; supported: {sorted(DIMENSIONS)}")
```

Validate the **cross-axis** rules too, not only the individual ones. The combinations a catalog does not offer — a tolerance grade available at only one temperature coefficient, a packaging code available on only two sizes, a dielectric absent from the smallest case — are where a generated part number turns into a part nobody sells, and each axis on its own looks fine.

**Key a coded axis on the datasheet's own code, not on a float.** A tolerance table maps `F` to ±1 %, so a `dict[float, str]` keyed on `0.01` makes the public constructor depend on float equality — `1/100` and `0.010000000000000002` are different keys, and the failure is a spurious "unsupported tolerance". Take the code as the argument, or key the dict on it, and convert to a number for display only.

**Put the checks where they will actually run.** Validation reached only through `__init__` does nothing outside a JITX instantiation context, because `__init__` does not run there — see "Verifying a component with tests". A pure classmethod that builds and validates the part number, which `__init__` then calls, runs in both places and is the more testable shape.

### Value-code encoders — round before you encode

**Round to significant figures first, then encode.** Manufacturer value codes are fixed-width significand-plus-multiplier fields, and encoding an unrounded value truncates instead of carrying: a value that rounds up across a decade must carry into the multiplier, never emit the un-carried significand or a malformed field. Split the *rounded* number, and unit-test the decade-carry cases explicitly — the happy-path values pass either way, which is why this ships.

**Do not force one encoder across vendors.** Value-code schemes genuinely differ, and one shared encoder with a mode flag per vendor is harder to check against a datasheet than three short functions. The encoder is the per-family part; the rounding helper is the shared part.

### Shared helpers — extract at the second family

**Write the first family self-contained, and extract the shared helpers when the second one lands** — not before. One family gives you no evidence about which pieces are vendor-agnostic; two do. Refactoring the first family onto the extracted helpers with *its tests unchanged* is what proves the extraction safe. The durable split: land-pattern construction, the two-pin `.insert()`, datasheet-tolerance-to-`Toleranced` conversion and significant-figure rounding are shared; the value encoder, the size / rating / range tables and the part-number f-string are per-family. When a shared module first serves a second component type, rename it for what it actually is — a module called `chip_resistor.py` that a capacitor family imports is a name that lies — and re-run the full suite after the rename.

### E-series checks

`jitx-circuit-builder` owns the rule for *choosing* a passive value — use the `eseries` package, default E96. A family class sits on the other side of that transaction: it is handed a value and must say whether the series actually makes it. **Pick the series from the part's tolerance grade, not from a global default.** A ±5 % part is built on E24, and accepting an E96 value for it produces an orderable-looking part number for a part that does not exist. Do not reach past what the datasheet says the family is built on in either direction — a tight grade a manufacturer builds on E96 does not become E192 just because the tolerance is tight. Make the check opt-in so a deliberate non-standard value stays possible, and add a series when a family that needs it lands, not in anticipation.

### When the catalog does not publish what you need, say so

Overview and selector-guide editions routinely omit the per-size value lineup the full series datasheet carries. Validate what the document *does* state — the ordering code, the published significand grid, the size / voltage / dielectric offering — record the gap in the docstring, and tell the user which envelope is checked and which is not. Do not invent ranges to make the validation look complete: a range nothing backs is the same failure as a dimension nothing backs.

## Package-Specific Examples

For complete examples of each package type (SOIC, SOT, SON, QFN, QFP, BGA), including thermal pads,
port arrays, inactive positions, and non-uniform BGA grids, see
[references/package-examples.md](references/package-examples.md).

Read its **BGA-Specific Notes** before any BGA, not just an unusual one — in particular what
`ball_diameter` actually sets, and the public `get_pad` adapter for reaching pads from test and
verification code. Both are places where the obvious reading is the wrong one.

## Dimension Mapping Reference

| Datasheet Symbol | Description | JITX Parameter |
|-----------------|-------------|----------------|
| D | Package length | `RectanglePackage.length` |
| E | Package width | `RectanglePackage.width` |
| A | Package height | `RectanglePackage.height` |
| E1 / D1 | Lead span | `LeadProfile.span` |
| e | Lead pitch | `LeadProfile.pitch` |
| b | Lead width | `SMDLead.width` / `QFNLead.width` |
| L | Lead length | `SMDLead.length` / `QFNLead.length` |
| D2 / E2 | Thermal pad size | `.thermal_pad(rectangle(E2, D2))` — **E2 is width (X), D2 is height (Y)**. D=along pins, E=across. Do NOT write rectangle(D2, E2). |

**Two-terminal chips use L / W / T instead, and the two symbol sets do not correspond row for row** — do not translate one into the other by position.

| Chip datasheet symbol | Description | JITX Parameter |
|-----------------|-------------|----------------|
| L | Body length, termination end face to end face | `LeadProfile.span`, `RectanglePackage.length` |
| W | Body width (= termination width) | `SMDLead.width`, `RectanglePackage.width` |
| H / T | Body height / thickness | `RectanglePackage.height` |
| *(seating-plane band; symbol varies by vendor)* | Solderable termination length | `SMDLead.length` — **not** the end-face wrap-up band. See "The two termination bands — which one is the solderable land". |

## Common Patterns

### Class-Level vs Instance-Level

Ports, landpattern, and symbol defined at **class level** (no `self`). The exception to this is if a parameter is needed at the class initialization time then the definition can be done in the initialization function:

```python
class MyIC(jitx.Component):
    GND = Port()          # class-level: no self
    VCC = Port()

    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(GND),    # bare name, NEVER self.GND
            right=PinGroup(VCC),   # bare name, NEVER self.VCC
        ),
    )
```

Only use `self` inside `__init__` (for PadMapping, multi-unit symbols).

### Toleranced Values

```python
Toleranced.min_max(3.8, 4.0)           # Min-max range (most common)
Toleranced(5.0, 0.1)                    # Nominal ± tolerance
Toleranced.min_typ_max(0.13, 0.18, 0.23)  # Asymmetric
Toleranced.exact(7.0)                   # BSC = Basic
```

### Thermal Pad with Paste Subdivision

```python
from jitx.shapes.composites import rectangle
from jitxlib.landpatterns.pads import SMDPadConfig, WindowSubdivide

.thermal_pad(
    shape=rectangle(3.0, 3.0),
    config=SMDPadConfig(paste=WindowSubdivide(padding=0.25)),
)
```

### Reference Designator Prefixes

- `U` - Integrated circuits
- `Q` - Transistors (typically BJTs)
- `D` - Diodes (LEDs)
- `R` - Resistors
- `C` - Capacitors
- `L` - Inductors
- `J` - Connectors
- `Y` or `X`- Crystals/oscillators
- `FB` - Ferrite beads
- `T` - Transformers

## Multi-Unit Symbols

`BoxSymbol` accepts `BoxConfig` field overrides as keyword arguments — e.g.
`BoxSymbol(rows=..., orientation=90)` rotates the box symbol (an int multiple
of 90 degrees; other values raise `ValueError`; jitxlib 4.2+).

**Prefer partitioning large symbols into several smaller boxes.** A single box
with dozens of pins is unreadable; as a rule of thumb, **once a part exceeds
~40 pins, split it into multiple symbols.** A component may carry more than one
`BoxSymbol` — each becomes a separate visual box, and the boxes can be placed on
different schematic pages (see "Splitting across schematic pages" below).

**At four figures' worth of pins the partition becomes the schematic.** Past a
few hundred pins there is no "the symbol" left to split — the partition *is* the
part's readable form, and it needs stating as a property rather than a habit:

- **Every port in exactly one partition**, and the partition count reconciles
  against the total pin count. Same property the pin inventory owes (see
  `pin-file-generation.md`), asserted the same way. A port in two boxes and a
  port in none both draw without complaint.
- **One box per structural group the source itself defines.** Take the grouping
  from the datasheet's own organizing axis and do not invent one — on an FPGA
  that is typically the IO bank, transceiver quad or power domain; on other
  parts it is whatever the pin table is organized by. If you cannot name the
  document that defines your grouping, it is invented.
- **A per-box ceiling for the groups that have no natural size** — the large
  rails, where one box per net would mean a single box of several hundred pins.
  Chunk them at a stated ceiling and say what it is. The right number is
  whatever keeps a box readable at your schematic's page size; state it, enforce
  it in a test, and revisit it by looking at the rendered sheet rather than
  trusting the number.
- Pins belonging to no group get their own box rather than being distributed by
  convenience.

Build the boxes from a **method returning fresh partitions**, never a stored
attribute holding the ports a second time; see "A `Port` has exactly one home".

**By functional group** (the usual case — split where the datasheet does: each
op-amp unit, the power unit, each peripheral block):

```python
def __init__(self):
    self.symbol_a = BoxSymbol(rows=Row(
        left=PinGroup(self.INp[0], self.INn[0]),
        right=PinGroup(self.OUT[0]),
    ))
    self.symbol_b = BoxSymbol(rows=Row(
        left=PinGroup(self.INp[1], self.INn[1]),
        right=PinGroup(self.OUT[1]),
    ))
    # Power unit: use horizontal layout (left=supplies, right=grounds)
    self.symbol_power = BoxSymbol(
        rows=Row(
            left=PinGroup(self.VCC, self.VBAT),
            right=PinGroup(self.VSS, self.GND),
        ),
    )
```

**By regular slices** — only when the part has **no** natural functional
grouping (generic connectors, board-to-board headers, pin arrays). For FPGAs,
MCUs, and memory, partition by the structure the datasheet already gives you —
IO bank, power domain, byte lane, peripheral block — *before* falling back to
arbitrary slices. When slicing is the right call, store the boxes as a **list**
and slice a `p = [Port() for _ in range(N)]` pin array into fixed-size groups:

```python
# 100-pin part → ten 10-pin boxes (5 left / 5 right each):
self.symbols = [
    BoxSymbol(
        rows=Row(
            left=PinGroup(*self.p[i * 10:i * 10 + 5]),
            right=PinGroup(*self.p[i * 10 + 5:i * 10 + 10]),
        ),
    )
    for i in range(10)
]
```

`self.symbols` (a list of `BoxSymbol`) is a recognized structural collection —
no string-keyed dict, no `getattr` (see `jitx/references/architectural-patterns.md`).

### Splitting across schematic pages

Each symbol can be assigned to its own schematic page by wrapping it in a
`SchematicGroup`. In the **enclosing circuit/design**, pull the component's
symbols out with `extract(..., Symbol)` and give each its own group:

```python
from jitx import extract, Symbol
from jitx.circuit import SchematicGroup

# In the circuit that instantiates the part:
self.banks = [SchematicGroup(symbol) for symbol in extract(self.u1, Symbol)]
```

`extract(self.u1, Symbol)` yields every `Symbol` in `self.u1` (the partitioned
boxes); each `SchematicGroup` becomes a separately placeable schematic group, so
a 100-pin part's ten banks can land on ten pages. Rails connect across those
pages through `PowerSymbol` / `GroundSymbol` net symbols, not drawn wires — see
`jitx-circuit-builder` "Net Definitions". (`SchematicGroup` is in `jitx.circuit`;
`extract` and `Symbol` are top-level `jitx` exports.)

## Pin Naming Best Practices

**Every physical pin/ball MUST have a Port().** Never use "representative samples" — a 142-ball
BGA needs exactly 142 Port() declarations. Enumerate every pin from the datasheet pin table or
ball map row by row. NC (no-connect) pins with physical pads also need ports. 

**One Port per physical pin** — if a ball has a primary name and alternate functions
(SPI_CLK, UART_TX, etc.), create ONE port using the datasheet's primary pin name. Do not create
separate ports for each alternate function of the same physical ball.
Also for Ports that have incrementing numbers in the name, use an indexed Port name instead (GND1, GND2, GND3 -> GND[1 through 3])

**Use real functional names from the datasheet**, not generic placeholders:

```python
# GOOD - from datasheet
OQSPIF_D0 = Port()   # Octal QSPI Flash data bit 0
eMMC_CMD = Port()    # eMMC command line
V18F = Port()        # 1.8V flash supply

# BAD - generic
P0 = Port()          # What does P0 do?
VDD1 = Port()        # Which power domain?
```

## Landpattern Constructor Signatures

Do NOT invent constructor parameters — use only these documented signatures:

```python
# SOT — SOTLeadProfile takes ONLY span, nothing else
SOTLeadProfile(span=Toleranced.min_max(2.3, 2.5))

# LeadProfile — used for SOIC, SON, QFN
LeadProfile(
    span=Toleranced.min_max(5.8, 6.2),   # terminal-to-terminal
    pitch=1.27,                            # center-to-center lead spacing
    type=SONLead(length=..., width=...),   # or SMDLead, QFNLead
)

# SON — use .lead_profile() method chain, NOT .lead()
SON(num_leads=8).lead_profile(LeadProfile(span=..., pitch=..., type=SONLead(...)))

# QFP — uses LeadProfile with QFPLead (BigGullWingLeads)
QFP(num_leads=48).lead_profile(LeadProfile(span=..., pitch=0.5, type=QFPLead(...)))
# For asymmetric pin counts: QFP(num_rows=(left, bottom, right, top))
# For asymmetric lead spans: .lead_profile(x_profile, y_profile)

# BGA — constructor takes these 4 args
BGA(num_rows=12, num_cols=12, pitch=0.45, ball_diameter=0.25)
# then chain: .grid_planner(...).pad_config(SMDPadConfig()).package_body(...)
```

### `.narrow()` vs `.package_body()` for SOIC

SOIC provides a convenience method `.narrow(length)` that sets the package body to the standard SOIC narrow width (3.9mm) with a given length:

```python
# .narrow() — shorthand for narrow-body SOIC (3.9mm width)
SOIC(num_leads=8).lead_profile(SOIC_DEFAULT_LEAD_PROFILE).narrow(Toleranced.min_max(4.81, 5.0))

# Equivalent explicit form using .package_body()
SOIC(num_leads=8).lead_profile(SOIC_DEFAULT_LEAD_PROFILE).package_body(
    RectanglePackage(width=Toleranced.exact(3.9), length=Toleranced.min_max(4.81, 5.0))
)
```

Use `.narrow()` for standard narrow-body SOICs. Use `.package_body()` for wide-body SOICs or when specifying all three dimensions (width, length, height).

## PadMapping Requirements

- **Automatic mapping (no PadMapping needed):** Ports mapped to pads in declaration order.
- **Explicit PadMapping required when:**
  - Thermal pad exists (map to `lp.thermal_pads[0]`)
  - Ports declared out of pin order
  - Multiple ports map to same pad
  - Pin 1 is not the first declared port

A `PadMapping` resolves port → pad, and nothing more. It carries **no coordinate** — and a component
declaring more than one landpattern is combined into a single *composite* landpattern, so each
`Pad.transform` is local to its own sub-landpattern rather than to the component. Pad coordinates
must be composed from a `visit` (`trace.transform * pad.transform`), never read off `Pad.transform`
alone.

**Both of these need narrowing before a type checker will accept them**, which matters because a
"pyright clean" gate and an un-narrowed lookup contradict each other:

- `PadMapping.__getitem__` returns `Pad | Sequence[Pad]` — a port may map to several pads — so
  `mapping[port][0]` is a `reportIndexIssue`, and `len(mapping[port])` fails on the `Pad` arm.
- `Pad.transform` is `Placement | None`, so `pad.transform.translation` is a
  `reportOptionalMemberAccess`.

Each is a small helper once you know — write both; they narrow different unions:

```python
from jitx.landpattern import Pad, PadMapping
from jitx.transform import Placement


def one_pad(mapping: PadMapping, port: Port) -> Pad:
    """The single pad for a port. Raises if the port maps to several."""
    pads = mapping[port]
    if isinstance(pads, Pad):
        return pads
    if len(pads) != 1:
        raise AssertionError(f"expected one pad for {port}, got {len(pads)}")
    return pads[0]


def placement_of(pad: Pad) -> Placement:
    """A pad's own placement. Raises rather than returning a silent default."""
    if pad.transform is None:
        raise AssertionError(f"pad {pad} has no placement")
    return pad.transform
```

Write the helpers rather than suppressing the errors. A `pyright: ignore` on the first hides the
composite-landpattern case the union exists to flag; one on the second turns a missing placement into
an `AttributeError` at some later line instead of a named failure here. And note `placement_of` gives
you the pad's *local* transform — for a coordinate in the component's frame, compose it from a
`visit`, per the paragraph above.

## Verification Process

### Step 4: Test Harness

```python
import jitx
from jitx.container import inline
from jitx.sample import SampleDesign

from .component import Device


class TestDesign(SampleDesign):
    @inline
    class circuit(jitx.Circuit):
        dut = Device()
```

**Put the harness where `jitx find` can see it.** The CLI's project scanner imports candidate modules by their top-level name, so a design that only exists inside a `tests/` package — or in any directory the project doesn't make importable — is not discovered, and `jitx find` reports `designs: []` with a `ModuleNotFoundError` per file rather than saying the design is missing. Confirm with `jitx find` before `jitx build`, and **take the build target verbatim from what `jitx find` prints** rather than composing it from the module path yourself. A `jitx.test.TestCase` suite is the offline check; it does not substitute for the build, and a design the CLI cannot find has not been built.

### Verifying a component with tests

A build proves the component translates. It does not prove the pin count matches the datasheet, that the part number the class computes is one the manufacturer sells, or that the value the BOM prints is the value the user asked for. Those need tests.

**Tests that construct a component must subclass `jitx.test.TestCase`, never plain `unittest.TestCase`** (verified on jitx 4.2.2–4.4.0rc3). It activates the JITX instantiation context, and needs no runtime — instantiating a component works offline. Outside that context a constructor does not run: `MyPart(size="0505")` returns a deferred `Instantiable` proxy and **`__init__` is never called**, so every fail-fast check in the class silently passes. A negative test written on a plain `unittest.TestCase` then fails for the wrong reason — not because the validation is missing but because nothing ran — and a demo script that constructs a deliberately invalid part raises nothing at all.

This is about *construction*, not about the base class on its own: a plain `unittest.TestCase` exercising a pure function — a value-code encoder, a table cross-check, a classmethod that validates arguments without instantiating — is fine, and is a good reason to put validation in such a classmethod in the first place.

**To build a component directly — outside a `SampleDesign` class body — open a substrate context as well:**

```python
from jitx.sample import SampleSubstrate
from jitx.substrate import SubstrateContext

with SubstrateContext(SampleSubstrate()):
    part = MyPart(size="0402", ...)
```

**Declare every JITX class at module scope, never inside a test method.** Defining one while an
instantiation context is active raises (verified on 4.4.0rc3):

```
TypeError: Creating new JITX classes dynamically during instantiation is not supported,
please create new classes separately.
```

So a `SampleDesign`, a `Circuit` harness, or a throwaway component built to exercise one case all
belong at module scope, even when only one test uses them. This is the same instantiation-tracking
rule as the base skill's "no subclassing JITX classes inside functions or methods"; it bites here
because a test method is the natural place to reach for a one-off fixture.

Direct construction is what `@pytest.mark.parametrize` forces, since a parametrized case cannot drive a class-body `SampleDesign`. The chip land-pattern generator reads fabrication values off the active substrate — silkscreen-to-soldermask spacing, via `jitx.current.substrate.constraints` — so with no substrate active it raises instead of building. **Never rely on a context an earlier test left set**: that passes in suite order and fails when the test runs alone, which is the order a bisect or a `-k` filter uses.

**What a component test asserts,** beyond `status: ok` from the build:

- **It builds in a `SampleDesign`** and its metadata reads back — manufacturer, reference-designator prefix, ratings.
- **Pad count equals pin count**, once per package variant, and for a family once per case size, so every land pattern is exercised at least once.
- **The generated part number against the datasheet's own ordering example** — the worked example in the ordering-information section, or a real catalog part. This is the one assertion that proves the numbering scheme was read rather than inferred; one per scheme is enough.
- **The human-readable value label**, not just the part number — see below.
- **The value encoder as a unit test, with decade-carry cases** alongside the ordinary ones.
- **That validation raises** on each invalid axis *and* on the invalid cross-axis combinations.
- **Library defaults against the datasheet, per size**, wherever the land pattern took them — dimensions *and* density level. Pin a known-bad entry as still-wrong, so the override is removed when the table is fixed.

**For a generated component**, add the assertions in `pin-file-generation.md` § "Testing a generated component". Note that a spot-check expression indexing a `PadMapping` needs the narrowing in "PadMapping Requirements"; written literally it does not type-check, and a suite gated on "pyright clean" will contradict itself.

Where a test is skipped unless a source file is present — the idempotency check usually is, since the vendor file cannot be committed — **confirm it actually ran** when you are relying on it. A skipped test is green.

**"The environment can't run this" is a claim to test, not to assert.** Before recording a check as unavailable, try it. The completion block's hard-fail is on an *undeclared* unavailable environment, which makes declaring feel like the safe move — but a declaration that turns out to be wrong is worse than a failing check, because it reads as diligence while hiding the result.

The specific trap: a missing `pyproject.toml` looks like "no project, so no build," and it is four lines away from being a project. In one run an agent declared `jitx build` unrunnable for exactly that reason; adding a minimal `pyproject.toml` made `jitx build --dry` run, and it reported `translation failed: <Component> does not have a landpattern` — a fact about the delivered artifact that the completion block never stated. Cheap to check, and `--dry` needs no runtime. If the check then fails for a reason you already know and accepted (geometry deliberately absent, say), record the actual message; "cannot be placed on a board" and "cannot be translated into any design" are different claims, and the second is the one the reader needs.

**Assert the value label — scaling to an SI prefix reintroduces float noise on exactly the values a passive library uses most.** `PlainQuantity.to_compact()` divides by a power of ten, so an exactly specified `100e-9 F` comes back as `99.99999999999999 nanofarad`, and `2.2e6 Ω` as `2.1999999999999997 megaohm` (verified on jitx 4.2.2). Nothing else catches it: `pyright` sees a well-typed quantity, `pytest` never touches `.value` unless you tell it to, `jitx build` reports `status: ok` — and the string goes to the BOM. Round the scaled magnitude back to significant figures before assigning `.value`, and assert the rendered string. Assert it the way the translator renders it (`f"{value:g~P}"`), not through a bespoke format spec — a spec of your own can hide the noise it is supposed to catch.

### Build Command

Always use the available virtual environment. If one is not present, stop and ask.
```bash
jitx build <module>.TestDesign
```

Don't run parallel JITX builds against the same project — sequence them. See `jitx/SKILL.md` "Build Safety".

**Success:** `status: ok`
**Failure:** Python traceback or `status: error`

**Output files** (in `designs/<design_name>/`):
- `cache/netlist.json` - Verify net connections
- `design-info/stable.design` - Design snapshot

### Common Build Errors

| Error | Fix |
|-------|-----|
| `port X not mapped to symbol pin` | Add port to BoxSymbol |
| `port X not mapped to pad` | Check port count = pad count |
| `No pad configuration specified` | BGA needs `.pad_config(SMDPadConfig())` |

### Verification Report

Emit the **task acceptance block** from `jitx/references/completion-blocks.md` "Task Acceptance Block", with the **Component completeness check** (below) filled in under its `Checks run` field. For a component task, the block's `Primary source` field cites the datasheet pages with the pinout and mechanical drawing; the `Footprint source` field names the JITX generator used (or KiCad import with reason); the `Checks run` field includes the Component checklist from `jitx/references/domains/component-modeling.md` with N/N items and any issues fixed (pin count vs datasheet, pad count vs landpattern, dimensions vs datasheet mechanical drawing). The acceptance block is the report; do not invent a parallel format.

The checklist and the completeness check are complementary, not interchangeable. The **domain checklist is the per-pin / per-pad enumeration you walk while writing** the component; the **completeness check is the evidence you present when claiming it is done**, one row per way a component fails quietly. Report each build, type check and test run **once** — the completeness check's `Checks` row is where they live, and it satisfies the checklist's Build Test items.

## Step 5: Capture Application Circuit

**In the project-builder (complete-board) workflow, this step is MANDATORY — not optional.** The application circuit from the datasheet is the foundation for the downstream circuit task; capture it now while the datasheet is open.

In single-task tier (user invoked component-modeler standalone), this step is optional — ask the user.

After generating component code, check the datasheet for "Typical Application", "Reference Design", or "Application Circuit" sections. These provide valuable circuit templates.

**Process (complete-board):**

1. Capture the application circuit without asking. Extract the relevant datasheet figure (use `extract_pages.py`) and invoke `jitx-circuit-builder` to generate the circuit code.

**Process (single-task):**

1. **Ask user** whether to capture the application circuit:
   ```
   "The datasheet includes a Typical Application circuit (Figure X).
   Would you like me to also generate the application circuit code?"
   ```

2. **If yes**, invoke the `jitx-circuit-builder` skill to generate circuit code

3. **Pass context** to circuit-builder:
   - Component class name and import path
   - Datasheet figure reference
   - Component values from schematic (cap values, resistor values, inductor specs)
   - Pin connections shown in the schematic

**Example application circuit output:**

```python
"""
Texas Instruments TPS62933DRLR Application Circuit
From datasheet Figure 23 - Typical Application

3.8-V to 30-V input, 3.3V 3A output buck converter.
"""

from jitx import Circuit, Net
from jitx.toleranced import Toleranced
from jitx.common import Power
from jitxlib.parts import Capacitor, CapacitorQuery, Resistor, Inductor, ResistorQuery
from jitxlib.voltage_divider import VoltageDividerConstraints, voltage_divider_from_constraints

from .texas_instruments_TPS62933DRLR import TPS62933DRLR


class TPS62933DRLRCircuit(Circuit):
    """Buck converter application circuit per datasheet Figure 23."""

    vin = Power()   # Input power (3.8V-30V)
    vout = Power()  # Output power (3.3V)

    def __init__(self, output_voltage=3.3):
        self.GND = Net(name="GND")
        self.VOUT = Net(name="VOUT")
        self.VIN = Net(name="VIN")

        # Main IC
        self.buck = TPS62933DRLR()

        # Power connections
        self.VIN += self.vin.Vp + self.buck.VIN
        self.GND += self.buck.GND + self.vin.Vn + self.vout.Vn

        # Input capacitors (C1, C2 - 10µF each per schematic)
        with CapacitorQuery.refine(type="ceramic", case="0805"):
            self.c_in1 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
            self.c_in1.insert(self.buck.VIN, self.GND, short_trace=True)

            self.c_in2 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
            self.c_in2.insert(self.buck.VIN, self.GND, short_trace=True)

        # Feedback voltage divider
        vdiv_cons = VoltageDividerConstraints(
            v_in=Toleranced.exact(output_voltage),
            v_out=Toleranced.percent(0.8, 3.0),  # MUST have tolerance window
            current=0.8 / 10e3,
            prec_series=[1.00, 0.10],             # REQUIRED
            base_query=ResistorQuery(case=["0402"]),
        )
        self.fb_div = voltage_divider_from_constraints(vdiv_cons, name="feedback")
        self.VOUT += self.fb_div.hi + self.vout.Vp
        self.GND += self.fb_div.lo
        self.nets = [self.fb_div.out + self.buck.FB]

        # Output inductor and capacitors
        self.L = Inductor(inductance=4.7e-6, current_rating=3.9)
        # ... complete circuit per datasheet
```

**File location:** Save application circuits alongside the component:
```
components/
├── power_switchmode/
│   ├── texas_instruments_TPS62933DRLR.py      # Component
│   └── texas_instruments_TPS62933DRLR_circuit.py  # Application circuit
```

## Component completeness check — run before calling it done

A component is judged by whether every value in it traces back to a source — the manufacturer's datasheet, a vendor mechanical drawing, or the user's explicit specification. The predictable failure mode is not a missing feature; it is a **plausible number sitting where it looks authoritative**: a termination band read off the wrong dimension line, a library-table default nobody checked, a value label the BOM will print that no test ever read. Before presenting a component as complete, fill this block in the completion summary, each row with its evidence (datasheet page / table / figure → class or attribute). A row you cannot check is an open item to name to the user — not a silent pass.

```
## Component check
Source: <manufacturer + document number + revision/date>; page/figure cited per claim below
        (+ channel evidence where the user named a sourcing channel)
Identity: <class name> — mpn <literal | computed from <scheme>, cross-checked against
        <the datasheet's ordering example or a real catalog part>>; manufacturer,
        refdes prefix and datasheet URL set on the class
Pins: <N> ports / <N> physical pins or pads on the drawing — every power, ground,
        NC-with-pad and thermal pad present; names from the datasheet's own pin table
Landpattern: <generator + args> from <page/figure>; <N> pads; dimensions transcribed —
        body <L/D> <W/E> <H/A>, <pitch | n/a>, lead/termination <length> <width>,
        each cited; Toleranced from the drawing's min/max, not nominal-only
Library defaults: generator/table defaults relied on: <list | none> — each checked
        against the source where the source speaks to it; agreements <list>,
        overrides <item + reason | none>
        Density level: <A | B | C> — <what the source asks for, or "no preference stated">;
        installed default is <level> — <set explicitly | default already matches>
Value / BOM: .value renders as "<string>" — asserted in a test
        | n/a (<reason>) — AND pinned by a test asserting it is unset
No-field walk: datasheet-stated facts with no JITX field, recorded in the docstring: <list>
Provenance: values traceable to no datasheet page: NONE | <list + the labeled rule backing each>
Checks: pyright <clean | N errors>; pytest <N passed | not run: <reason>>;
        build <status: ok via <command> | not run: <reason>>
Verdict: complete | open items: <list>   (any non-clean check, or build not run, is an
        open item — "complete" with a failing or unrun check is not a valid combination)
```

Row-by-row intent — the *why*, so the block stays evidence rather than ceremony:

- **Source** — a page or figure per claim, not one URL for the whole component. "Datasheet (from memory)" and "typical dimensions" are invalid for a real MPN; see "No fabrication — source authority for geometry and pinout".
- **Identity** — a part number is a claim about the manufacturer's numbering scheme. Where it is a literal from the ordering table, cite that table. Where the class *computes* it, the only thing that tests the claim is reproducing a part number the manufacturer itself printed — one cross-check per scheme. Where **no source document states one** — which happens for parts whose ground truth is a pin file and a packaging manual — this row records what was agreed with the user and what the value does and does not identify. It is never a value you chose yourself; see "When no document states an MPN".
- **Pins** — count first, then compare row by row. A ports-vs-pads mismatch is the one component error the build reliably catches; everything below this row is the class of error the build does not catch.
- **Landpattern** — dimensions come from the mechanical drawing, not the overview page or the ordering table, and carry the drawing's tolerances. Where the generator could not express the package, the fallback and its reason belong here.
- **Library defaults** — a generator default is a convenience, not an authority. Wherever the datasheet publishes the same dimension, transcribe it anyway and check the two against each other; where they disagree, override from the datasheet and say so. The whole risk of taking a default is that nobody transcribed the number that would have caught a bad one. A default you took without checking is indistinguishable, in the output, from one you verified.

  **Defaults are not only dimensions.** The one that gets missed is **density level**, because it never appears as a number in your code. The levels are IPC-7351's land-protrusion goals — `A` most, `B` median/nominal, `C` least — and the choice moves real copper: on `BigRectangularLeads`, a 0.55 mm toe fillet at `A`, 0.35 at `B`, 0.15 with a **negative** 0.05 mm side fillet at `C`. The default has changed between versions (`C` on 4.2.2 and 4.4.0rc3, `B` later), so assume neither: read what the source asks for, check what your installed `DensityLevelContext` defaults to, and either set the level explicitly (`DensityLevel` from `jitxlib.landpatterns.ipc`, on the generator or via the surrounding context) or record in this row that the default already matches.
- **Value / BOM** — no build, type check or land-pattern test looks at the rendered value string. If this row says anything other than an asserted literal, nothing is checking what the BOM will print.

  **`n/a` is a claim, and it needs a test like any other.** For an IC there is often no value in the passive sense, and leaving `.value` unset is right — but "right" and "checked" are different, and an unpinned `n/a` is indistinguishable from having forgotten the field. Treat it exactly as you would any other deliberate absence: a component that deliberately ships without a land pattern gets a test asserting no land pattern is present, so a component that deliberately ships without a value gets a test asserting `value is None`. Then the decision cannot silently rot when someone later sets it.

  This row is the one most often filled by declaring rather than checking, which is why it says so twice.
- **Provenance** — if the datasheet doesn't state a value, ask the user or document the omission. Never invent a number to satisfy a type checker or complete a table; suppress the type error with a comment saying why instead.

## Output Format

When generating a component, provide:

1. Complete Python source code in a code block
2. Verification report (using format above)
3. Any assumptions or decisions made
4. Known limitations or items requiring manual review
5. **Offer to capture application circuit** if datasheet includes one
