# ARCHITECTURE.md Template

ARCHITECTURE.md owns the design facts tasks share. Copy the fenced block into the project root; nothing above it goes in the file.

- Keep it near 60 lines for 8 to 15 components; over budget, cut before adding.
- Tables, not prose. Never restate a table, or a fact PLAN.md owns.
- Delete every heading this board has nothing for; a heading over `N/A` or placeholder rows is a defect.
- If a sentence would read identically for any board, delete it: record the commitment, never the rule behind it.
- Name the routing structure rather than the ohms wherever the substrate defines one (`DRS_90`, `RS_50`); `—` on rows with no structure.
- Design Notes hold settled constraints a table row cannot express (a level-shift boundary, an enable or PGOOD dependency, a real thermal budget, a shared-clock jitter limit), one bullet each. An unresolved fact is a PLAN.md Open Questions row instead.
- `Object-Hierarchy Decisions` covers parametric or generator subsystems only, 3 to 5 lines each, written before code. A collection matters only when N > 1 and the things are siblings, so one MCU, one buck or one pour gets no entry.

```markdown
# Architecture: [Project Name]

## Power Tree

| Rail | Voltage | Source | Regulator | Type | Loads | Current | Noise / ripple requirement | Sequence position |
|------|---------|--------|-----------|------|-------|---------|----------------------------|-------------------|
| [rail] | [voltage] | [source rail/input] | [MPN or —] | [input/buck/LDO/filter] | [loads] | [worst-case total as a number, or `blocked: OQ-n`] | [requirement or —] | [order] |

## Interface Map

| Interface | From | To | Protocol | Speed | SI constrained | Impedance | Clock source |
|-----------|------|----|----------|-------|----------------|-----------|--------------|
| [name] | [source port] | [destination port] | [protocol] | [rate] | [yes/no] | [routing structure, or a target only when no structure owns one, or —] | [source] |

## Board

- **Dimensions:** [width × height mm or source drawing when the size is fixed; "at most width × height mm" when the figure is a limit; "set at place and route" when the user gave none. Place and route sets the size in those two cases]
- **Layer count:** [count]
- **Layer plan:** [what each layer carries: planes with their nets, routing layers. With nothing fixing it, a four-layer board has a ground plane on each inner layer and signals and power on the outer layers (`jitx-interactive-layout` `general-pnr.md` "Via plan")]
- **Material:** [material \| open: OQ-n]
- **Fab house:** [fab house \| open: OQ-n]
- **Substrate class:** [predefined class or custom class \| open: OQ-n]
- **[Mechanical constraint]:** [one actual mounting, keepout, height, or outline constraint; repeat only for constraints that exist]

## Object-Hierarchy Decisions

- **[Subsystem (`path.py`)]:**
  - **Shape:** [collection or typed object shape]
  - **Owner:** [structural object that owns the data]
  - **Derivation:** [how instances and values are derived]

## Design Notes

- [Settled non-derivable constraint that no table above represents. Not an open question: those live in PLAN.md]
```
