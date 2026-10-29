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

### 3. KiCad footprints (for packages no generator expresses)

For standard packages (QFN, SON, DFN, SOIC, SOT, QFP, BGA), the default landpattern source is the **JITX generator** with dimensions from the datasheet mechanical drawing, even when a KiCad footprint exists. Fall back to a KiCad footprint only when the generator can't represent the package: connectors, RF modules, unusual mechanical, or specialty paddle geometry (split paddles, non-standard thermal pads, asymmetric layouts). The agent reads the `.kicad_mod` itself and writes each entry into the component, as `jitx-component-modeler` describes in [Packages no generator expresses](../../jitx-component-modeler/references/source-and-package-selection.md#packages-no-generator-expresses).

## Data Audit (Project Builder)

In the Project Builder workflow, Phase 0 includes a **data source audit** before any work begins. The orchestrator presents a table showing where each component's data will come from, and the user approves or provides alternatives. See `references/project-builder-flow.md` Phase 0 for details.

## Required-Sourcing Rule (named channel → channel-specific evidence)

When the user has named a sourcing channel — LCSC / JLCPCB / "buy from Mouser" / an LCSC C-number for any part / an internal PLM — channel-specific evidence is **required** for every named part before any component code is written. The evidence is saved to the project (so reviewers can verify) and cited in the Phase 0 data source audit row for the part.

| Channel named | Required evidence | How |
|---------------|------------------|-----|
| **LCSC / JLCPCB** | Stock + lifecycle + datasheet URL + pinout for each LCSC C-number | Saved text excerpt of the part's channel record (stock, lifecycle, datasheet URL, pin labels) to `datasheets/sourcing/<mpn>-lcsc.txt` or similar, cited in the data source audit row. |
| **Digi-Key / Mouser / Newark / other distributor** | Saved screenshot or text excerpt of stock + manufacturer/datasheet from the distributor page; user approves the evidence method | Manual save to `datasheets/sourcing/<mpn>-<distributor>.txt` or similar. |
| **Internal PLM / user library** | Reference to the PLM record or library entry; user confirms the record is current | Cite the record ID or library file path in the data source audit row. |
| **No channel named** | Treat sourcing as an open question — ask the user before proposing parts | The component-choice rationale table is incomplete without a channel; flag in Phase 0. |

The datasheet remains the higher authority for dimensions, pin labels, and pad assignments. A sourcing channel's pinout record is a useful cross-check but does not replace the datasheet's mechanical drawing and pinout table. When the two disagree, the datasheet wins and the conflict is documented in the task acceptance block under `Secondary references`.

**Standard packages (QFN, SON, DFN, SOIC, SOT, QFP, BGA):** the channel gives you stock and pinout. Use the **JITX generator** for the landpattern, with dimensions from the datasheet mechanical drawing. Do not import a channel's KiCad footprint as the landpattern for a standard package; see [Packages no generator expresses](../../jitx-component-modeler/references/source-and-package-selection.md#packages-no-generator-expresses).

**Mechanical / pad-only footprints (Tag-Connect TC2050, fiducials, castellations, pogo pads):** these have no purchasable component — no stock/lifecycle to check. Channel evidence does not apply; the vendor mechanical drawing is the source. See "Mechanical / Vendor-Defined Footprints" below.

**Standard passives queried via `jitxlib.parts`:** the LCSC channel for an `R 4.7kΩ 0402` is satisfied by the query — `jitxlib.parts` already returns LCSC-stocked options when `mounting="smd"` is set in the design's passive defaults. Don't collect channel evidence for every passive; only for named ICs and connectors.

## Part Selection Workflow

1. **Read the requirements lock first.** Component proposals must respect the locked answers from `decomposition-guide.md` "Requirements Lock" — assembly-cost target, RF policy, programming path, fab house. Proposing an ESP32 to a user who locked "JLCPCB economy, no extended parts" wastes a cycle.

2. **Claude proposes ideal parts** based on engineering requirements: voltage/current ratings, package thermal limits, peripheral set, interface support, proven reliability. Weigh tradeoffs (dropout vs efficiency, pin count vs board area, feature set vs complexity).

3. **Identify data source** for each part: does the user have a datasheet? A footprint? Or should we search/download?

4. **Record chosen parts in PLAN.md** `Data Sources`: MPN, package, data source, and the one-line `Chosen over` outcome. The full **component-choice rationale table** below is presented at the audit in chat, not filed in PLAN.md.

### Component-Choice Rationale Table

For every part the orchestrator proposes, record the rationale. **Present this table to the user in chat at the Phase 0 data source audit; it does not go into PLAN.md.** What PLAN.md keeps afterwards is the `Data Sources` row: the chosen part, its approved sources, and the `Chosen over` cell. Filling this table forces the agent to justify each choice against the locked requirements, not just availability.

| Field | What to capture |
|-------|-----------------|
| **MPN / package** | The proposed part and package |
| **Function** | One-line description of what role this part plays |
| **Locked-requirement match** | Which lock items it satisfies (assembly-cost tier, RF policy, voltage/current, programming path, etc.) — and which it might strain (e.g. "uses extended JLCPCB part — user locked economy") |
| **Stock / availability** | Stock level at the chosen distributor; lead time if not in stock |
| **Fabrication risk** | Package class fab requires (e.g. "0.5 mm pitch BGA — needs ≥6-layer w/ microvias"), any DRC concerns |
| **Thermal / power** | Worst-case dissipation, whether package can handle it, ambient assumption |
| **Why this part over alternatives** | Concrete: one rejected alternative and why (cost, availability, package, feature gap, EOL). A second only when it changed the decision; a list of three is padding, not rigour. |

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

### Non-standard packages — import from KiCad

Source the `.kicad_mod` from one of:
- User's existing KiCad library
- Manufacturer's KiCad library download
- A distributor-hosted or third-party library footprint (LCSC/EasyEDA, SnapEDA and similar), which is third-party data under its own terms: use it as the land-pattern source only with the user's explicit approval for this project, record the approval under `Notes`, and check it pad by pad against the manufacturer's drawing

Then import it entry by entry, as `jitx-component-modeler` describes in [Packages no generator expresses](../../jitx-component-modeler/references/source-and-package-selection.md#packages-no-generator-expresses).

**NEVER place pads from a drawing when a vendor KiCad footprint exists.** If you must add pads the footprint file does not list, verify shapes against the datasheet mechanical drawing: round holes use `Circle(radius=r)` from `jitx.shapes.primitive`, oval holes use `capsule(width, height)` from `jitx.shapes.composites`.

Always use `BoxSymbol`. Never convert KiCad schematic symbol graphics.

## Mechanical / Vendor-Defined Footprints

The "NEVER place pads from a drawing" rule above has a legitimate exception: footprints that are board geometry, not a purchasable component. Examples include programming/test pad patterns (Tag-Connect TC2050, pogo-pin fixtures), castellated module edges, fiducials, board-edge shield contacts, and mounting pads with electrical function. For these, no `.kicad_mod` source exists — the source of truth is a vendor mechanical drawing.

### When this applies

- The "footprint" represents a mechanical/copper feature, not a part with an MPN.
- Or: the part exists but no purchasable component model is available, and a vendor mechanical drawing is the source of truth.

This exception does **not** authorize hand-crafting pad positions for purchasable components (resistors, ICs, connectors with MPNs). Those still go through the standard JITX generators or a KiCad footprint import. When no source above yields a KiCad footprint, or the user declines a third-party one, place each pad from the drawing's recommended land pattern, citing the figure per dimension, and record "no vendor KiCad footprint found" under `Notes`.

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
