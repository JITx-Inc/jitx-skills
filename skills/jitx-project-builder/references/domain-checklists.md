# Domain-Specific Validation Checklists

Sub-agents MUST run the relevant checklist after initial implementation and BEFORE returning results. The orchestrator will independently verify high-risk items during acceptance review.

## How to Use

1. Complete your implementation and get an initial `status: ok` build.
2. Read the checklist(s) below that match your task type.
3. For EVERY item, verify against the datasheet or specification. Do not check items from memory.
4. If you find an issue, FIX IT before continuing.
5. If an item does not apply, note why (do not silently skip).
6. Rebuild after fixes and verify `status: ok`.
7. Include checklist results in your task acceptance block (see `references/completion-blocks.md`).

Your initial implementation likely missed something. This is expected and normal. The purpose of this checklist is to catch those misses. Approach it as a critical reviewer, not a rubber stamp.

---

## Checklist Index

- [Component Modeling and MCU / FPGA](domains/component-modeling.md)
- [Power Circuits](domains/power-circuits.md)
- [Interface Circuits](domains/interface-circuits.md)
- [External Connector / Hot-Plug Interfaces](domains/external-interfaces.md)
- [Substrate](domains/substrate.md)
- [General Gotcha Scrub](domains/general-gotchas.md)
- [Layout Constraints](domains/layout-constraints.md)
- [Net Class Taxonomy](net-classes.md)
