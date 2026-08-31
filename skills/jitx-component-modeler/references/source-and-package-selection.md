# Source Handling and Package Selection

The agent opens this file when the task starts from a datasheet, drawing, URL, sourcing-channel record, KiCad footprint, or user specification. It carries source acquisition, citation, output-location, page-extraction, package-selection, and standard-versus-imported-footprint rules.

Generate JITX Python component code from datasheets, user-provided KiCad footprints, or specifications. Data can come from multiple sources — always prefer user-provided data over automated lookups.

## No fabrication — source authority for geometry and pinout

> **Do not write dimensions, pin labels, or pad assignments from memory.**
>
> If you find yourself writing **"typical dimensions"**, **"reasonable defaults"**, **"user can refine specific values later"**, **"approximate"**, **"will adjust later"**, or any synonym for guessed / default / placeholder geometry on a component that has a real MPN, **stop**. This skill is not a pattern catalog you can skim and walk away from — it is the rule that you don't ship a landpattern from memory.
>
> For every named component (anything with an MPN, distributor part number, or user-supplied datasheet), before writing landpattern dimensions or pin labels, work down this ladder until you have a source:
>
> 1. **Manufacturer's current datasheet** — open the mechanical drawing page (use `extract_pages.py` to pull only those pages — do not read the full PDF). Cite the page/figure where you got each dimension.
> 2. **Manufacturer's machine-readable pin file** — where the vendor publishes the pin map as data rather than as a drawing (FPGAs, large SoCs, most high-ball-count BGAs). It is the authority for **names, balls and banks only**; geometry still comes from the packaging document, and the two never substitute for each other. Parse it — do not transcribe it, and do not read a sample and extrapolate. See [pin-file-generation.md](pin-file-generation.md).
> 3. **Sourcing-channel lookup** — if the user has named LCSC/JLCPCB, `parts2jitx-lcsc <C-number>` (stock, lifecycle, datasheet URL) and `parts2jitx-lcsc <C-number> --pinout` (pin labels). Use it as channel evidence and as a pin-label cross-check. Datasheet remains higher authority where they disagree; document the conflict.
> 4. **Ask the user** — for an LCSC C-number, a user-supplied `.kicad_mod`, or the datasheet itself.
>
> If none of the four produce a source, the component is **blocked**. Do not proceed by estimating. The only way out is for the user to explicitly authorize a non-MPN generic component (e.g. "use a typical 0.4 mm pitch QFN-56, this is a placeholder"). Record that authorization in the task acceptance block under `Notes`.
>
> **Carve-out — parameterized catalog families.** A class that models a manufacturer's whole catalog series has no single MPN by construction: it *computes* one per instance from the datasheet's own part-numbering scheme. That is not the fabrication this rule forbids, and it needs no user authorization — the source authority is the same datasheet, and every dimension, code table and range still traces to a page of it. What the rule still forbids is a family with no datasheet behind it: a size table from memory, a "typical" termination band, an ordering scheme inferred from one example part. In place of the single MPN, a family owes one extra piece of evidence — a generated part number reproduced against the datasheet's own worked ordering example. See [parameterized-families.md](parameterized-families.md).
>
> The rule is also about values that could be wrong, not about labels the source never supplied. A two-terminal chip datasheet does not name its terminations, so `p1`/`p2` with declaration-order pad mapping is the framework's sanctioned idiom, not an invented pin label.
>
> This callout exists because a test session loaded the former monolithic skill body, said "I have the patterns, I'll proceed without invoking the modeler skill further — writing each component directly with reasonable typical dimensions" — and then fabricated nine components. That is the failure this rule forbids.

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
4. **Pin functions**: Pin names and functions from pinout table (see [component-code-patterns.md](component-code-patterns.md#pin-naming-best-practices))
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
│         See parameterized-families.md "Two-Terminal Chip Components" for the size key, the
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
