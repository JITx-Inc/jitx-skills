# Parts Sourcing and Footprint Data

## Evidence Hierarchy

Higher beats lower; record a conflict and the choice under `Secondary references`, never pick silently.

1. The current datasheet, checked against the manufacturer's page for a newer revision.
2. Errata for that part and revision.
3. Vendor application notes.
4. Vendor reference design or eval board (schematic, layout, BOM).
5. A design the user names as field-proven.
6. A prior project using the part.
7. Community designs and forum posts, as hints.

`Primary source` comes from 1 to 4, or 5 when the user names it the source of truth. A sourcing channel's pinout is a cross-check: the datasheet wins on dimensions, pin labels and pads.

## Data Sources

Ask the user for their datasheets, footprints and component libraries before fetching anything. Footprint method: `jitx-component-modeler` "Package and generator choice" and "KiCad import".

## Required-Sourcing Rule (named channel → channel-specific evidence)

Once the user names a sourcing channel (LCSC or JLCPCB, a distributor, an LCSC C-number, an internal PLM), every named IC and connector needs that channel's evidence saved in the project and cited in its data source plan row before component code exists:

- LCSC / JLCPCB: stock, lifecycle (or `none stated`), datasheet URL and pinout per C-number, saved as `jitx-jlcpcb` sets out.
- Digi-Key, Mouser, Newark or another distributor: stock and manufacturer datasheet from its page, saved as text or a screenshot (`datasheets/sourcing/<mpn>-<distributor>.txt`), by a method the user approves.
- Internal PLM or user library: the record ID or library path, which the user confirms is current.

No channel evidence for passives the approved-parts list serves, or for pad-only footprints with no purchasable part. A channel's KiCad footprint never replaces the generator for a standard package.

## Part Selection

Propose parts against the requirements lock: a part the locked assembly tier, RF policy or programming path rules out wastes a cycle. Then name each part's data source, and record it in `Data Sources`.

### Selection and Chosen over

For each proposed part, show the user this table in chat at the data source plan; PLAN.md keeps only the `Chosen over` cell.

| Field | Content |
|-------|---------|
| MPN / package | the part |
| Locked-requirement match | the lock items it meets, and any it strains |
| Stock / availability | stock at the chosen channel; lead time |
| Fabrication risk | the package's demands on the fab (pitch, layers, microvias) |
| Thermal / power | worst-case dissipation against the package, with the ambient |
| Why this part over alternatives | one rejected part and why; a second only if it changed the decision |

A row with no real rejected alternative is a flag: the first query hit, unweighed.

## Reference Search Order for Component Modeling

Before modeling a reusable IC family or common package, search in order: the user's libraries, `jitxexamples.components`, the vendor's reference design or KiCad pack. Record `searched: found <path>` or `searched: no analog` in `Secondary references`.

## Mechanical / Vendor-Defined Footprints

Never place pads by hand where a generator or a vendor or KiCad footprint exists. Pads come from the vendor drawing only for board geometry with no purchasable part (Tag-Connect TC2050, pogo pads, castellated edges, fiducials, edge shield contacts, mounting pads with an electrical role), and for a part with no footprint from any source, or whose third-party footprint the user declined; record "no vendor KiCad footprint found" under `Notes`.

1. Save the drawing in the project (`kicad_footprints/<name>.pdf`).
2. Cite each dimension in a code comment: pad pitch, pad size, holes, keepouts, board-edge limits.
   A round hole is `Circle(radius=r)` (`jitx.shapes.primitive`), an oval one `capsule(width, height)` (`jitx.shapes.composites`).
3. Check, in `Checks run`: pad count, pitch, pad size, orientation and pin 1, keepouts and board-side limits, and each connection against the programmer or mating spec (TC2050 pins per the debugger). The task is not complete until every item is checked.
