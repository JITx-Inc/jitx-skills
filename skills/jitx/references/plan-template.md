# PLAN.md Template

PLAN.md owns the work: the requirements lock, the approved data sources, the task graph and its state, gate outcomes, and the modification history. ARCHITECTURE.md owns the design. Copy the fenced block into the project root and fill it in.

Everything above that block is guidance for filling it, and none of it belongs in the file you write. The fenced block carries headings, table skeletons, field names and placeholders and nothing else, because a sentence that reads identically for any board is boilerplate every sub-agent already has.

## How to fill it

**Economy**

- Five bullet lines per ordinary task, plus the engineering questions on circuit tasks and a `Shape` line on parametric ones.
- **If a sentence would read identically for any board, delete it.** The skill and its references are already loaded for every sub-agent: a design rule, a banned form, a naming prohibition, or a procedure recital costs lines here and teaches nothing. Write the decision this board made, not the rule the decision obeyed.
- Checklists are not a per-task field. They are fixed per task type in `references/task-execution.md`, which every sub-agent reads. Give a task a `Checklist:` line only to override its type's default.

**Ownership**

- **Never write a value a table already owns.** Name the row or the section instead. The generic instruction to cross-reference proved not to be enough on its own, so the list is explicit: MPN and package belong to `Data Sources`; rail voltage, load and current to ARCHITECTURE.md `Power Tree`; protocol, impedance and routing structure to `Interface Map`; board dimensions, layer count, stackup order and mechanical constraints to `Board`; parametric shape commitments to `Object-Hierarchy Decisions`. A task body that repeats any of them has created a second owner, even when the two copies agree today.
- `Data` names the rows and sections a task reads. It does not reproduce their contents.
- `Specifics` carries only what no table owns and no task of the same type shares: the one gotcha, the topology choice, the exception.
- The `Verify` module path is where the task's file lives: `python scripts/check.py <ns>/ --build <ns>.circuits.usb.TestDesign` commits the task to `<ns>/circuits/usb.py`. That gives the path one owner, so no task restates it and no two sub-agents place the same module differently. `jitx/SKILL.md` "Project Structure" gives the directory shape.

**Requirements Lock**

- Each row records **who settled the item**, not the value. That is the payload: a design cannot fake the difference between something the user required and something the orchestrator assumed, which is what makes the lock hold. Write one of:
  - `user-stated` plus the constraint, when no other document owns it (programming path, UI count, assembly tier, RF policy).
  - `user-stated — see ARCHITECTURE.md <Section>`, when a table owns the realization (rails, fab house, mechanical). The provenance claim is the row's content; the value stays with its owner.
  - `not specified — assuming: X`, where the assumption is the content and has no other owner, so it is written out in full and is challengeable at the audit.
  - `no constraint`.
- An earlier revision filled these rows with a bare `locked — see ARCHITECTURE.md ...`, which asserted nothing about who decided and was therefore satisfied by any self-consistent design. A later one quoted the request verbatim, which reproduced the dimensions, layer count, impedances and fab house that ARCHITECTURE.md owns. Naming the source and pointing at the owner is what avoids both.
- **A design fact that a datasheet or a specification settles is never an assumption.** It is an Open Questions row with an owner and a resolution path, and the tasks it gates read `blocked: OQ-n`. The `assuming: X` form is only for a requirement the user did not state, never for a value nobody has looked up yet.

**Data Sources**

- Every row reads `ready` before the Phase 0 gate opens. A `needs input` row is a blocker and gets an Open Questions row.
- `Chosen over` is the surviving record of the component-choice rationale: one rejected part and why, in a few words. The full rationale table in `parts-sourcing.md` is presented to the user in chat at the data source audit, not filed here.

**Open Questions**

- One row per unresolved decision that blocks work. Record the decision and what closes it, never the argument that produced it. Delete the section when empty; a question answered during Phase 0 becomes a Requirements Lock row instead.
- If another task's `Verify` or `Data` depends on it, it is a task with an id, not an Open Questions row.

**Tasks**

- Engineering questions: one test decides whether a question belongs on a task. Could the sub-agent answer it by reading the datasheet's own application circuit, or does it already appear on a checklist for this task type? Then it is checklist work with a second owner, not a question. Write at most three, name the datasheet section or specification that settles each, and give a part whose application circuit answers everything none at all.
- The `Shape` line is for parametric or generator tasks only (BGA ballout, deskew geometry, antipad fence, N-lane fanout, per-layer table, repeating-block scene graph) and states the collection or typed object committed to. The three questions behind it are in `decomposition-guide.md` Step 3b: record the answer, never the prohibitions the questions enforce.
- `Status` is one of `pending`, `blocked: OQ-n`, `in-progress`, `review`, `accepted`, `rework`, `rejected`. Blocking is transitive: a task whose dependency is blocked is blocked, not pending. A resumed session reads Status first, so blocked state belongs there and not only in the Open Questions `Blocks` column. The orchestrator changes it with `python scripts/plan_status.py <task-id> <status> [--note "<short note>"]`; the optional note is stored after the status as `; note: <text>`. It does not rewrite PLAN.md wholesale for a status change.

**State**

- Mandatory blocks are emitted in chat (`completion-blocks.md`). `Gate status` takes one row per gate; `Modifications` takes one row per modification batch, never a re-narration of the work.
- Replace every placeholder and delete every unused heading or example row.

---

```markdown
# Project Plan: [Project Name]

## Requirements Lock

| Item | Source | Where it lives |
|------|--------|----------------|
| Programming / debug path | [user-stated: the constraint \| not specified — assuming: X \| no constraint] | this row |
| UI count and class | [user-stated: the constraint \| not specified — assuming: X \| no constraint] | this row |
| Power rails | [user-stated \| not specified — assuming: X] | ARCHITECTURE.md `Power Tree` |
| Assembly cost target / tier | [user-stated: the tier \| not specified — assuming: X] | this row |
| RF / wireless module policy | [user-stated: the policy \| no RF] | this row |
| Connector UX | [user-stated: the constraint \| not specified — assuming: X \| no constraint] | this row |
| Fab house / process | [user-stated \| not specified — recommending X, treated as an assumption] | ARCHITECTURE.md `Board` |
| Mechanical / enclosure constraint | [user-stated \| not specified — assuming: X \| no constraint] | ARCHITECTURE.md `Board` |

## Design Reference

See ARCHITECTURE.md sections `Power Tree`, `Interface Map`, `Board`, and, when present, `Object-Hierarchy Decisions` and `Design Notes`.

## Data Sources (approved by user)

| Component | MPN | Package | Datasheet source | Footprint method | Chosen over | Status |
|-----------|-----|---------|------------------|------------------|-------------|--------|
| [component] | [MPN] | [package] | [approved source] | [generator or approved file/source] | [one rejected part, and why] | [ready \| needs input: what is missing] |

## Open Questions

| Question | Blocks | Owner | Resolution path |
|----------|--------|-------|-----------------|
| [the decision, in one line] | [task ids or gate] | [user \| orchestrator] | [what closes it] |

## Phase 1: Substrate + Components

### [sub-01] [Substrate]
- **Type / skill / deps:** substrate | [jitx-substrate-modeler, or `—` for a predefined class] | —
- **Data:** [ARCHITECTURE.md `Board`; the predefined class or the stackup source]
- **Specifics:** [via choices and package-density constraints this board imposes]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.substrate.TestDesign`
- **Status:** pending

### [comp-01] [Component name]
- **Type / skill / deps:** component | jitx-component-modeler | —
- **Data:** [`Data Sources` row for this part; any task-only input]
- **Specifics:** [pin count, and the one gotcha that matters for this part]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.components.<category>.<name>.TestDesign`
- **Status:** pending

## Phase 2: Constraints + Circuits + Pin Assignment

### [pin-01] [IC name] Pin Assignment
- **Type / skill / deps:** pin-assignment | jitx-pin-assignment | [component task id]
- **Data:** [component model; ARCHITECTURE.md `Interface Map`]
- **Specifics:** [the provides and the flexibility unique to this IC]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.circuits.<wrapper>.TestDesign`
- **Status:** pending

### [cst-01] [Protocol] Constraints
- **Type / skill / deps:** constraint | jitx-interconnect-constraints | [substrate task id]
- **Data:** [protocol specification; ARCHITECTURE.md `Interface Map` row]
- **Specifics:** [limits this protocol imposes that the Interface Map does not carry]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.constraints.<name>.TestDesign`
- **Status:** pending

### [cir-01] [Circuit name]
- **Type / skill / deps:** circuit | jitx-circuit-builder + jitx-component-modeler | [task ids]
- **Data:** [`Data Sources` rows for every IC; upstream task outputs]
- **Specifics:** [topology, passives, and bundle ports unique to this circuit]
- **Engineering questions:**
  - [question, and the datasheet section or specification that settles it]
- **Shape:** [parametric tasks only — the collection or typed object committed to]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.circuits.<name>.TestDesign`
- **Status:** pending

## Phase 3: Top-Level Assembly

### [asm-01] Top-Level Design
- **Type / skill / deps:** assembly | jitx-circuit-builder + jitx-interconnect-constraints | [every Phase 2 id, listed out]
- **Data:** [accepted Phase 2 outputs; ARCHITECTURE.md sections by name]
- **Specifics:** [assembly decisions no other document owns]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.main.Design`
- **Status:** pending

## Phase 3b: Design Review and Loopback

### [aud-01] Design-level audit
- **Type / skill / deps:** audit | — (orchestrator plus the outside voice) | [assembly task id]
- **Data:** [top-level design; accepted task acceptance blocks; ARCHITECTURE.md]
- **Specifics:** [the design-level risks this board raises]
- **Verify:** `python scripts/check.py <ns>/` exits 0, and the audit block carries all four passes plus the outside-voice findings and their disposition
- **Status:** pending

## Phase 4: Build + Verify + Iterate

### [ver-01] Final Verification
- **Type / skill / deps:** verify | — | [audit task id]
- **Data:** [top-level design; required verification artifacts]
- **Specifics:** [board-specific checks or tool constraints]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.main.Design`
- **Status:** pending

## Gate status

| Gate | Verdict | Date | Deferred / blocking |
|------|---------|------|---------------------|
| 0 → 1 | advance | YYYY-MM-DD | — |

## Modifications

| ID | Change | Files | Verdict |
|----|--------|-------|---------|
```
