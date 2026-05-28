# Parts Sourcing and Footprint Data

How to get component data (datasheets, footprints, pinouts) into JITX projects. Multiple data sources are supported — the user chooses what's appropriate for their workflow.

## Evidence Hierarchy and Conflict Resolution

When sourcing a component or designing a circuit around an IC, use sources in this order. Higher entries beat lower entries when they conflict. If sources disagree, document the conflict and pick with rationale; do not silently choose the convenient one.

1. **Current datasheet** — the manufacturer's most recent revision. Always download fresh; do not reuse a year-old PDF without checking the manufacturer page for an update.
2. **Errata** — same vendor, same part, same revision. Errata can supersede the datasheet on specific points; check before committing to a circuit detail that errata might change.
3. **Application notes** — vendor-published guidance and worked examples. Useful for circuit topology and component values, but they interpret the datasheet — they don't override it.
4. **Vendor reference design / eval board schematic, layout, BOM** — manufacturer or distributor reference design. Treat as authoritative for "this works"; cross-check against the current datasheet when something is surprising.
5. **User-supplied known-good design** — a design the user explicitly identifies as field-validated and provides as a reference. Can be primary if the user explicitly says it is the source of truth for this design; otherwise treat as secondary and cross-check.
6. **Prior internal project** — your own prior project that used the same part. Useful but secondary; cross-check against the current datasheet before relying on it for any pin function, register usage, or external component value.
7. **Community examples** — Adafruit / SparkFun / hobbyist designs, forum posts, demo boards. Treat as hints, not authority.

The task acceptance block's `Primary source:` field must come from items 1–4, OR item 5 when the user has explicitly designated it as authority. If a prior internal project (item 6) appears as primary, that's a flag — the orchestrator should ask the sub-agent to confirm against the datasheet.

When sources conflict, the task acceptance block's `Secondary references:` field documents the conflict ("datasheet says X, user-supplied known-good says Y; chose Y because user confirmed Y is field-validated for this exact application").

## Data Sources (in priority order)

### 1. User-Provided Data (preferred)

Users may supply their own:

- **Datasheets** — PDF files placed in `datasheets/<mpn>.pdf`
- **KiCad footprints** — `.kicad_mod` files placed in `kicad_footprints/`
- **Specifications** — pin count, package type, dimensions provided directly
- **Existing component libraries** — pre-built JITX components from their codebase

Always ask if the user has data before reaching for external tools.

### 2. JITX Standard Generators (for standard packages)

For standard packages, use JITX landpattern generators — no external data needed:

| Package | Generator |
|---------|-----------|
| QFN | `QFN(...)` |
| SON/DFN | `SON(...)` |
| SOIC | `SOIC(...)` |
| SOT-23/SOT-223 | jitxlib standard library |
| QFP | `QFP(...)` |
| BGA | `BGA(...)` |

Dimensions come from the datasheet (user-provided or fetched). No footprint download needed.

### 3. LCSC / JLCPCB via parts2jitx (split consent: lookup vs footprint data)

There are **two distinct uses** of parts2jitx; each has its own consent rule. They are routinely confused.

| Use | What it does | Consent rule |
|-----|--------------|--------------|
| **Lookup / evidence** | `parts2jitx-lcsc <C-number>` (stock, lifecycle, datasheet URL) and `parts2jitx-lcsc <C-number> --pinout` (pin labels). Cross-checks the datasheet and confirms the part is buyable. | **Implied** when the user names LCSC / JLCPCB / a specific LCSC C-number as the sourcing channel. The orchestrator may `pip install parts2jitx` automatically — naming the channel implies consent for the lookup tool. |
| **Footprint data ingestion** | `parts2jitx-lcsc --footprint` downloads the EasyEDA-sourced `.kicad_mod`; `parts2jitx-kicad` converts it into JITX landpattern code. Uses the EasyEDA component database as the *primary geometric source*. | **Explicit per-project approval required.** EasyEDA component data has its own terms of use; commercial users in particular may not want EasyEDA-sourced footprint provenance in their project. Always ask before using the footprint download path. |

For standard packages (QFN, SON, DFN, SOIC, SOT, QFP, BGA), the default landpattern source is the **JITX generator** with dimensions from the datasheet mechanical drawing — not the LCSC KiCad footprint. Fall back to KiCad import only when the generator can't represent specialty paddle geometry (split paddles, non-standard thermal pads, asymmetric layouts). See `jitx-component-modeler/SKILL.md` "Standard-Package Decision Rule".

For non-standard packages (connectors, RF modules, unusual mechanical), the workflow is:

```bash
# Install (auto-OK once user has named LCSC/JLCPCB as the channel)
pip install parts2jitx

# Lookup / evidence (auto-OK once user has named LCSC/JLCPCB)
parts2jitx-lcsc C165948                                      # stock, lifecycle, datasheet URL
parts2jitx-lcsc C165948 --pinout                             # pin labels

# Footprint data ingestion (requires explicit per-project user approval)
parts2jitx-lcsc C165948 --footprint -o kicad_footprints/usb_c.kicad_mod
parts2jitx-kicad kicad_footprints/usb_c.kicad_mod --class-name USB_C_16P \
    --manufacturer "Korean Hroparts Elec" --mpn "TYPE-C-31-M-12"
```

**Skip parts2jitx entirely** when:
- The user has their own footprint data (use it directly)
- The package is standard and the JITX generator handles it
- The user explicitly declined LCSC/EasyEDA (use manufacturer KiCad library or ask the user for the footprint)

### Converting User-Provided KiCad Footprints

Users who already have `.kicad_mod` files (from KiCad libraries, vendor downloads, or their own designs) can convert them with `parts2jitx-kicad`:

```bash
parts2jitx-kicad my_footprint.kicad_mod --class-name MyConnector \
    --manufacturer "Amphenol" --mpn "12345" \
    -o <namespace>/components/connectors/amphenol_12345.py
```

This works with any `.kicad_mod` file regardless of source — not just LCSC/EasyEDA.

## Data Audit (Project Builder)

In the Project Builder workflow, Phase 0 includes a **data source audit** before any work begins. The orchestrator presents a table showing where each component's data will come from, and the user approves or provides alternatives. See `references/project-builder-flow.md` Phase 0 for details.

## Required-Sourcing Rule (named channel → channel-specific evidence)

When the user has named a sourcing channel — LCSC / JLCPCB / "buy from Mouser" / an LCSC C-number for any part / an internal PLM — channel-specific evidence is **required** for every named part before any component code is written. The evidence is saved to the project (so reviewers can verify) and cited in the Phase 0 data source audit row for the part.

| Channel named | Required evidence | How |
|---------------|------------------|-----|
| **LCSC / JLCPCB** | Stock + lifecycle + datasheet URL + pinout for each LCSC C-number | `parts2jitx-lcsc <C-number>` output saved (or piped to the data-source-audit doc). `parts2jitx-lcsc <C-number> --pinout` for pin-label cross-check. The orchestrator may `pip install parts2jitx` automatically — naming LCSC/JLCPCB as the channel implies consent for *lookup/evidence* via parts2jitx. *Footprint data ingestion* (using LCSC/EasyEDA's `.kicad_mod` as the landpattern source) is the separate, opt-in path — see "LCSC / JLCPCB via parts2jitx" above. |
| **Digi-Key / Mouser / Newark / other distributor** | Saved screenshot or text excerpt of stock + manufacturer/datasheet from the distributor page; user approves the evidence method | Manual save to `datasheets/sourcing/<mpn>-<distributor>.txt` or similar. No automated tool today. |
| **Internal PLM / user library** | Reference to the PLM record or library entry; user confirms the record is current | Cite the record ID or library file path in the data source audit row. |
| **No channel named** | Treat sourcing as an open question — ask the user before proposing parts | The component-choice rationale table is incomplete without a channel; flag in Phase 0. |

When `parts2jitx` is the required tool (LCSC/JLCPCB channel) and isn't installed, install it:

```bash
pip install parts2jitx
```

The datasheet remains the higher authority for dimensions, pin labels, and pad assignments. Sourcing-channel pinout (e.g., `parts2jitx-lcsc --pinout`) is a useful cross-check but does not replace the datasheet's mechanical drawing and pinout table. When the two disagree, the datasheet wins and the conflict is documented in the task acceptance block under `Secondary references`.

**Standard packages (QFN, SON, DFN, SOIC, SOT, QFP, BGA):** parts2jitx-lcsc gives you stock + pinout. Use the **JITX generator** for the landpattern, with dimensions from the datasheet mechanical drawing. Do not import the LCSC KiCad footprint as the landpattern for standard packages — see `jitx-component-modeler/SKILL.md` "Standard-Package Decision Rule".

**Mechanical / pad-only footprints (Tag-Connect TC2050, fiducials, castellations, pogo pads):** these have no purchasable component — no stock/lifecycle to check. Channel evidence does not apply; the vendor mechanical drawing is the source. See "Mechanical / Vendor-Defined Footprints" above.

**Standard passives queried via `jitxlib.parts`:** the LCSC channel for an `R 4.7kΩ 0402` is satisfied by the query — `jitxlib.parts` already returns LCSC-stocked options when `mounting="smd"` is set in the design's passive defaults. Don't run `parts2jitx-lcsc` for every passive; only for named ICs and connectors.

## Part Selection Workflow

1. **Read the requirements lock first.** Component proposals must respect the locked answers from `decomposition-guide.md` "Requirements Lock" — assembly-cost target, RF policy, programming path, fab house. Proposing an ESP32 to a user who locked "JLCPCB economy, no extended parts" wastes a cycle.

2. **Claude proposes ideal parts** based on engineering requirements: voltage/current ratings, package thermal limits, peripheral set, interface support, proven reliability. Weigh tradeoffs (dropout vs efficiency, pin count vs board area, feature set vs complexity).

3. **Identify data source** for each part: does the user have a datasheet? A footprint? Or should we search/download?

4. **Record chosen parts in PLAN.md** with MPN, package, key specs, data source, and the **component-choice rationale table** below.

### Component-Choice Rationale Table

For every part the orchestrator proposes, record the rationale. This is the table the user reviews at the Phase 0 data source audit. Filling it forces the agent to justify each choice against the locked requirements, not just availability.

| Field | What to capture |
|-------|-----------------|
| **MPN / package** | The proposed part and package |
| **Function** | One-line description of what role this part plays |
| **Locked-requirement match** | Which lock items it satisfies (assembly-cost tier, RF policy, voltage/current, programming path, etc.) — and which it might strain (e.g. "uses extended JLCPCB part — user locked economy") |
| **Stock / availability** | Stock level at the chosen distributor; lead time if not in stock |
| **Fabrication risk** | Package class fab requires (e.g. "0.5 mm pitch BGA — needs ≥6-layer w/ microvias"), any DRC concerns |
| **Thermal / power** | Worst-case dissipation, whether package can handle it, ambient assumption |
| **Why this part over alternatives** | Concrete: which 1–2 alternatives were considered and why rejected (cost, availability, package, feature gap, EOL, etc.) |

A row without a real "rejected alternatives" entry is a flag — it usually means the agent took the first hit from a query without weighing tradeoffs. The user can challenge any row at the data source audit.

Example (one row):

| Field | Value |
|-------|-------|
| MPN / package | TPS62933DRLR / SOT-583 6-pin |
| Function | 5V → 3.3V buck, 2 A load |
| Locked-requirement match | JLCPCB economy ✓ (basic part); 5V in / 3.3V out ✓; 2 A load + 30% margin ✓ |
| Stock / availability | 25k+ at LCSC, no lead time |
| Fabrication risk | SOT-583 needs 0.4 mm pitch reflow — within JLCPCB economy |
| Thermal / power | P_diss ≈ 0.35 W worst-case; package θJA OK to 60 °C ambient |
| Why this part over alternatives | Considered MP2315 (efficient but extended part on JLCPCB — fails cost lock); TLV62568 (cheaper but only 1 A — fails margin); chose TPS62933 for cost + headroom |

## Reference Search Order for Component Modeling

Before generating a new component model, search existing sources in this order. Each source is one input; the goal is not to copy but to anchor the new model in proven patterns. Document `searched: found <path>` or `searched: no analog available` in the task acceptance block — but only for reusable IC families or common package patterns. A single resistor or jellybean connector doesn't need this overhead.

1. **User's own libraries** — if the user maintains a JITX component library (in this project or a shared internal repo), check it first. The user's conventions take precedence.
2. **`jitxexamples.components`** — the JITX-shipped examples package. Check for the same IC family or a closely-related package. Found a model? Use it as a starting point for pin patterns, port shape, and common idioms.
3. **Vendor reference design** — manufacturer eval-board library or KiCad pack.
4. **Generated from datasheet** — when no reference exists, generate from the datasheet using the `jitx-component-modeler` subskill.

Don't skip steps, but don't pretend a search produced nothing without recording where you looked. If nothing applies (e.g. a one-off resistor), say so in one line.

## Footprint Workflow

### Standard packages — use JITX generators

Dimensions from the datasheet mechanical drawing. No external footprint needed.

### Non-standard packages — convert from KiCad

Source the `.kicad_mod` from one of:
- User's existing KiCad library
- Manufacturer's KiCad library download
- LCSC/EasyEDA (via `parts2jitx-lcsc --footprint`, only if user has approved this data source)

Then convert: `parts2jitx-kicad <file.kicad_mod> --class-name MyPart`

**NEVER hand-craft pad positions for non-standard packages.** Use the converter output as the base. If you must add pads the converter didn't generate, verify shapes against the datasheet mechanical drawing: round holes use `circle(radius)`, oval holes use `capsule(width, height)`.

Always use `BoxSymbol`. Never convert KiCad schematic symbol graphics.

## Mechanical / Vendor-Defined Footprints

The "NEVER hand-craft pad positions" rule above has a legitimate exception: footprints that are board geometry, not a purchasable component. Examples include programming/test pad patterns (Tag-Connect TC2050, pogo-pin fixtures), castellated module edges, fiducials, board-edge shield contacts, and mounting pads with electrical function. For these, no `.kicad_mod` source exists — the source of truth is a vendor mechanical drawing.

### When this applies

- The "footprint" represents a mechanical/copper feature, not a part with an MPN.
- Or: the part exists but no purchasable component model is available, and a vendor mechanical drawing is the source of truth.

This exception does **not** authorize hand-crafting pad positions for purchasable components (resistors, ICs, connectors with MPNs). Those still go through the standard JITX generators or `parts2jitx-kicad` conversion.

### Workflow

1. **Source the vendor mechanical drawing** — manufacturer datasheet pad pattern, vendor application note, or user-provided drawing. Save to `kicad_footprints/<name>.pdf` (or wherever a static reference fits in the project — keep it findable).
2. **Cite dimensions in the JITX code as comments** — pad center-to-center, pad size, hole sizes, keepouts, board-edge constraints. Future reviewers need to verify against the drawing without rediscovering the source.
3. **Verification checklist** (include in the task acceptance block under `Checks run:`):
    - Pad count matches drawing
    - Pad pitch matches drawing
    - Pad dimensions (width × length) match drawing
    - Orientation / pin 1 marker matches drawing
    - Keepouts and board-side restrictions captured
    - Connection points electrically correct (e.g. TC2050 pin assignments per the programmer / debugger spec)

Block completion until the verification checklist is full.

## Project Directory Convention

All sourced data must be saved to the project for reproducibility:

```
project/
├── datasheets/          # PDFs (from manufacturer sites or user-provided)
├── kicad_footprints/    # .kicad_mod files (from any source)
└── <namespace>/
    └── components/      # Generated JITX Python
```
