# PLAN.md Template

PLAN.md owns the work: the requirements lock, data sources, task graph and state, gate outcomes and modifications. ARCHITECTURE.md owns the design. Copy the fenced block into the project root; nothing above it goes in the file.

## How to fill it

- If a sentence would read identically for any board, delete it. Write the decision this board made, not the rule it obeyed.
- Five bullet lines per ordinary task, plus engineering questions on a circuit task and `Shape` on a parametric one. Checklists come with the task type (`task-execution.md`); a `Checklist:` line only overrides one.
- Never write a value a table already owns; name the row or section. MPN and package belong to `Data Sources`; rail voltage, load and current to ARCHITECTURE.md `Power Tree`; protocol, impedance and routing structure to `Interface Map`; dimensions, layer count, stackup and mechanical constraints to `Board`; shape commitments to `Object-Hierarchy Decisions`. `Data` names the rows a task reads.
- A concern has one home: settled, an ARCHITECTURE.md design note; unsettled, an Open Questions row.
- `Specifics` is one line, about 25 words, holding what no table owns and no task of its type shares. A fact needing a second line belongs in ARCHITECTURE.md; a caveat a sub-agent must not miss is an engineering or open question.
- The `Verify` module path places the task's file: `--build <ns>.circuits.usb.TestDesign` puts it in `<ns>/circuits/usb.py`. No task restates it.
- Support circuitry ownership shows in the graph: the owning task's `Data` names the part, or depends on the part's task.

Requirements Lock:

- Each row records **who settled the item**, not the value:
  - `user-stated` and the constraint, where nothing else owns it;
  - `user-stated — see ARCHITECTURE.md <Section>`, where a table owns the value;
  - `not specified — assuming: X`, for a requirement the user did not state, written out in full;
  - `no constraint`;
  - `open: OQ-n`, under the no-fab rule (`decomposition-guide.md` Step 0).
- A design fact a datasheet or specification settles is never an assumption: it is an Open Questions row, and the tasks it gates read `blocked: OQ-n`.

Data Sources:

- Approval lives only in each row's `Source status`; no heading or sentence restates it.
- Every row reads `source approved` before the Phase 0 gate except the stand-in passives row. `needs input` blocks and gets an Open Questions row. The column never says whether a task can start.
- `Chosen over`: one rejected part and why, in a few words. The full rationale table goes to the user in chat.
- Passives take one row for the approved-parts list. The stand-in row reads `stand-in: approval at the Phase 4 parts gate`, which does not block the Phase 0 gate, until the user approves every MPN the final build resolved or replaces the list.

Open Questions:

- One row per unresolved decision that blocks work, with a stable `OQ-n`: the decision and what closes it, not the argument or the affected tasks. Never renumber. An answer during Phase 0 becomes a lock row; delete the section when empty.
- A decision another task's `Verify` or `Data` depends on is a task, not a question.

Tasks:

- Engineering questions: at most three, each naming the datasheet section or specification that settles it ([Engineering Questions (circuit tasks only)](decomposition-guide.md#engineering-questions-circuit-tasks-only)).
- `Shape`: the collection or typed object committed to, never the prohibitions behind it.
- `Status` is the only stored task state; an approved datasheet does not make a task startable. Blocking is transitive: a task whose dependency is blocked is blocked, not pending. Each `blocked: OQ-n` names an unresolved question that affects the task; with several, name one and keep the task blocked until all resolve.
- Before starting or unblocking work, check each open question against every task's `Data`, `Verify` and dependencies, transitively, and set `Status` to match. Starting from the current statuses misses a task never marked blocked.
- `Gate status` takes one row per gate; `Modifications` one row per change batch, never narration.
- Replace every placeholder; delete unused headings and example rows. Write the package's name in place of `<ns>` on every line, so each command runs as written. When the project has no package yet, choose the name, state it under the title, and pass it to `jitx project layout init` as `--name`.

```markdown
# Project Plan: [Project Name]

## Requirements Lock

| Item | Source | Where it lives |
|------|--------|----------------|
| Programming / debug path | [user-stated: the constraint \| not specified — assuming: X \| no constraint] | this row |
| UI count and class | [user-stated: the constraint \| not specified — assuming: X \| no constraint] | this row |
| Power rails | [user-stated \| not specified — assuming: X] | ARCHITECTURE.md `Power Tree` |
| Assembly cost target / tier | [user-stated: the tier and parts channel \| not specified — assuming: X \| open: OQ-n] | this row |
| RF / wireless module policy | [user-stated: the policy \| no RF] | this row |
| Connector UX | [user-stated: the constraint \| not specified — assuming: X \| no constraint] | this row |
| Fab house / process | [user-stated \| open: OQ-n] | ARCHITECTURE.md `Board` |
| Default trace width and clearance | [user-stated: the figures \| not specified — assuming: X \| open: OQ-n] | this row |
| Mechanical / enclosure constraint | [user-stated \| not specified — assuming: X \| no constraint] | ARCHITECTURE.md `Board` |

## Design Reference

See ARCHITECTURE.md sections `Power Tree`, `Interface Map`, `Board`, and, when present, `Object-Hierarchy Decisions` and `Design Notes`.

## Data Sources

| Component | MPN | Package | Datasheet source | Footprint method | Chosen over | Source status |
|-----------|-----|---------|------------------|------------------|-------------|---------------|
| [component] | [MPN] | [package] | [approved source] | [generator or approved file/source] | [one rejected part, and why] | [source approved \| needs input: what is missing] |
| Passives | `parts/approved-parts.csv` | per row | [user's list \| jitxexamples example CSV, stand-in] | per row `case` | n/a | [source approved \| stand-in: approval at the Phase 4 parts gate \| needs input: what is missing] |

## Open Questions

| ID | Question | Owner | Resolution path |
|----|----------|-------|-----------------|
| OQ-1 | [the decision, in one line] | [user \| orchestrator] | [what closes it] |

## Phase 1: Substrate + Components

### [sub-01] [Substrate]
- **Type / skill / deps:** substrate | [jitx-substrate-modeler, or jitx-jlcpcb for a predefined JLCPCB class, or `—` for another predefined class] | —
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

### [ver-01] [Interface] SI Verification
- **Type / skill / deps:** si-verification | jitx-interconnect-constraints [+ jitx-pin-assignment for a pin-assigned end] | [every module task id on the interface's paths; `cst-` task id]
- **Data:** [ARCHITECTURE.md `Interface Map` row; the accepted module and constraint outputs]
- **Specifics:** [the constraint, each path's two ends, and the one legal mapping the proof routes fix]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.designs.verify_<iface>.<VerifyDesign>`, then `python -m <ns>.designs.check_si_<iface>`
- **Status:** pending

## Phase 3: Top-Level Assembly

### [asm-01] Top-Level Design
- **Type / skill / deps:** assembly | jitx-circuit-builder + jitx-interconnect-constraints + jitx-layout-constraints + jitx-code-layout (pours) | [every Phase 2 id, listed out]
- **Data:** [accepted Phase 2 outputs; ARCHITECTURE.md sections by name]
- **Specifics:** [assembly decisions no other document owns; writes `<ns>/designs/check_si_main.py` when the design has SI constraints, and `<ns>/designs/check_layout_main.py` when it has pours, stitching or code-placed copper]
- **Verify:** `python scripts/check.py <ns>/ --build <ns>.main.Design`, then `python -m <ns>.designs.check_si_main` when the design has SI constraints, and `python -m <ns>.designs.check_layout_main` when it has pours, stitching or code-placed copper
- **Status:** pending

## Phase 3b: Design Review and Loopback

### [aud-01] Design-level audit
- **Type / skill / deps:** audit | — (a spawned read-only audit agent plus the outside voice) | [assembly task id]
- **Data:** [top-level design; accepted task acceptance blocks; ARCHITECTURE.md]
- **Specifics:** [the design-level risks this board raises]
- **Verify:** `python scripts/check.py <ns>/` exits 0, and the audit block carries all four passes plus the outside-voice findings and their disposition
- **Status:** pending

## Phase 4: Build + Verify + Iterate

### [fin-01] Final Verification
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
