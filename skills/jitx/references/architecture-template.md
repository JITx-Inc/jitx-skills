# ARCHITECTURE.md Template

Copy this into the project root alongside PLAN.md. Maintain it as the single owner of design facts needed across tasks.

- Keep it around 60 lines for a board of roughly 8–15 components. Denser boards need more; when over budget, cut something before adding something.
- Use tables, not prose. Never write a section that restates a table already in the file.
- Delete every heading with no content for this board. A heading over `N/A` or the template's own placeholder rows is a defect.
- Never restate a fact owned by PLAN.md.
- **If a sentence would read identically for any board, delete it.** Banned forms, naming prohibitions and design rules are owned by `jitx/SKILL.md` and `references/architectural-patterns.md`, and every sub-agent already has them. Record the commitment this design made, never the rule behind it.
- Name the routing structure rather than the ohms wherever the substrate owns one: a predefined class already defines what `DRS_90` and `RS_50` mean, so a repeated number is a second copy. Leave the cell `—` on rows with no structure; a routing structure on a plain GPIO row is noise.
- Put a level-shift boundary, enable/PGOOD dependency, real regulator thermal budget, or shared-clock/jitter constraint in Design Notes only when its table row cannot express it.
- **A Design Note is a settled constraint, never an open question.** If the fact is still unresolved it belongs in PLAN.md `Open Questions`, with an owner, a resolution path and the tasks it gates, and it appears nowhere else. Writing the same unresolved concern as both an open question and a design note is the most common way these two documents end up disagreeing: the open question gets resolved and closed, and the design note keeps asserting the worry forever. One sentence restating a PLAN.md question is one owner too many.
- `Object-Hierarchy Decisions` is for parametric or generator subsystems only (BGA ballout, deskew geometry, antipad fence, N-lane fanout, per-layer table, repeating-block scene graph): commit to the object shape before sub-agents write code, 3 to 5 lines each. A subsystem that is not parametric (one MCU, one buck regulator, one ground pour) gets no entry at all, because a collection matters only when N > 1 and the things are siblings. Record the commitment, never the prohibition behind it: `jitx/SKILL.md` Don'ts and `references/architectural-patterns.md` own the banned forms.
- Omit `Object-Hierarchy Decisions` and `Design Notes` entirely when the design has nothing for them. One bullet per Design Notes constraint.
- Everything above the fenced block is guidance for filling it and belongs in none of it. The block carries headings, table skeletons and placeholders only.

---

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

- **Dimensions:** [width × height mm, or source drawing]
- **Layer count:** [count]
- **Material:** [material]
- **Fab house:** [fab house]
- **Substrate class:** [predefined class or custom class]
- **[Mechanical constraint]:** [one actual mounting, keepout, height, or outline constraint; repeat only for constraints that exist]

## Object-Hierarchy Decisions

- **[Subsystem (`path.py`)]:**
  - **Shape:** [collection or typed object shape]
  - **Owner:** [structural object that owns the data]
  - **Derivation:** [how instances and values are derived]

## Design Notes

- [Settled non-derivable constraint that no table above represents. Not an open question: those live in PLAN.md]
```
