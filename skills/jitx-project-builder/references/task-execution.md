# Task Execution

## Task types

| Type | Sub-skill | Checklists (`domains/`) |
|------|-----------|-------------------------|
| `component` | `jitx-component-modeler` | [component-modeling.md](domains/component-modeling.md), its MCU / FPGA section where the part is one |
| `circuit` | `jitx-circuit-builder`, `jitx-component-modeler` | [power-circuits.md](domains/power-circuits.md) or [interface-circuits.md](domains/interface-circuits.md); [external-interfaces.md](domains/external-interfaces.md) for a connector to the outside; [general-gotchas.md](domains/general-gotchas.md) |
| `assembly` | `jitx-circuit-builder`, `jitx-interconnect-constraints`, `jitx-layout-constraints`, `jitx-code-layout` | [general-gotchas.md](domains/general-gotchas.md), [layout-constraints.md](domains/layout-constraints.md) |
| `substrate` | `jitx-substrate-modeler` for a custom stackup, `jitx-jlcpcb` for a JLCPCB class, none for another predefined class | [substrate.md](domains/substrate.md) |
| `constraint` | `jitx-interconnect-constraints` | [substrate.md](domains/substrate.md), [general-gotchas.md](domains/general-gotchas.md) |
| `pin-assignment` | `jitx-pin-assignment` | [general-gotchas.md](domains/general-gotchas.md) |
| `si-verification` | `jitx-interconnect-constraints`, plus `jitx-pin-assignment` for a pin-assigned end | [general-gotchas.md](domains/general-gotchas.md) |
| `audit`, `verify` | none | `project-builder-flow.md` Phase 3b, Phase 4 |

Per type:

- `component`: write `datasheets/<MPN>.spec.md` from the PDF with the modeler's `extract_pages.py` (`datasheet-spec-template.md`) and model from it. Follow `jitx-component-modeler` "Verification and halt" through the application-circuit offer, whose capture complete-board work requires.
- `circuit`: save each IC's English datasheet from the manufacturer's site, not a sourcing channel's copy, which may be another language or revision. Answer each engineering question with cited datasheet evidence. Build every external part of the application circuit, and follow the modeler's application-circuit handoff before wiring where it applies.
- `constraint`: define the constraint classes; the assembly applies them.
- `pin-assignment`: leave every pin choice the provider can solve to the solver.

## Part A: Sub-agent

In every step, change in `<ns>/` only the files this task builds or was sent to fix: a defect in another task's file goes in `Open issues / deferred` with file:line, unpatched.

### Step 1: Read the task

Take the file path and class from the `Verify` module path.

### Step 2: Build from the evidence

Invoke the sub-skill and work from the spec note (CD-1); single-task work reads the datasheet. Text extraction is not evidence for a scanned page or a table whose values sit apart from their rows: render the page and read it, or report a tooling blocker. Save every download in the project, never `/tmp`: `datasheets/<mpn>.pdf`, `kicad_footprints/<mpn>.kicad_mod`.

### Step 3: Build

```bash
python scripts/check.py <ns>/ --build <module.path.TestDesign>
```

`jitx build` reads no piped answer; without a terminal a prompt prints `input is disabled without a terminal`. Output carrying that line ends the task: return `blocked: build prompt` with the printed lines. Fix every `FAIL` and `ERROR` and rerun.

### Step 4: Checklist and grep-gate review (Think Twice)

Check every item of the task type's checklists against the spec note (single-task: the datasheet): fix each discrepancy, give each item that does not apply its reason. Fix hard-fail grep hits; give each review-required hit its disposition (`completion-blocks.md` "Grep Gate Patterns").

Then run `jitx-code-review` on the files the task touched. Complete-board work runs it on every task except a verify-only task that changed no JITX Python. If it cannot run, the block records `JITX code review (self): not run: <reason>`.

### Step 5: Fix and rerun

Rerun Step 3's command after any change. Rerun `jitx-code-review` when a fix touches code it flagged.

### Step 6: Return

Return the task acceptance block (`completion-blocks.md`), or `blocked: build prompt` with the printed lines.

## Part B: Orchestrator acceptance

A return without a block stays `in-progress`: ask for the block. That is not rework.

On `blocked: build prompt`, relay the lines to the user with `jitx build <design>` to run in their terminal, or start the build and have them confirm in the JITX UI. Set `in-progress --note "build prompt: waiting on the user"`, keep dispatching tasks that do not depend on it, and once the user has answered, re-spawn the task at Step 3.

On a block, set `review`, then:

1. Read every file the block names: missing `self.` on nets and parts, empty classes.
2. For a critical task, rerun its check.py command; for a `ver-` task, its build and `python -m <ns>.designs.check_si_<iface>`.
3. Spot-check against the PDF pages the note cites, never the note:

   | Type | Check |
   |------|-------|
   | Component | power and ground pin count, thermal pad, pin names; pad positions, row spacing and pad sizes against the mechanical drawing |
   | MCU / FPGA | every power domain, the programming interface, reset |
   | Power circuit | enable handling, PGOOD output type and pull-up, feedback divider on a named E-series with VOUT recomputed, bootstrap cap |
   | Interface circuit | bundle-typed ports, decoupling on every IC supply pin, bus pull-ups only where the circuit composes the bus |
   | Any circuit | the application circuit's external parts counted; no pull-up to a high-voltage rail such as VBUS |
   | Substrate | every via type, ground plane continuity, impedance reachable |
   | SI verification | each measurement names its intended pads; constraints match the assembly's; no module file changed |

4. Check fit downstream: bundle-typed ports (individual signal ports break `require()`: rework), provide and require bundles against the pin plan, power ports against the power tree, routing structures and topology ports, and for the assembly the parity row.
5. For a trigger-list task, run the outside-voice pass before `accept` (`outside-voice-review.md`).
6. Check the block, its Reviews rows included, against the acceptance rules in `completion-blocks.md` "Task Acceptance Block".
7. An `Open issues` entry naming a defect in another task's file: follow `project-builder-flow.md` "Task Status Flow".

Append the verdict, unless step 7 leaves the task waiting:

- Accept: set `accepted`.
- Rework: set `rework --note "<issues>"`, then `in-progress` and continue the same sub-agent with the issues by file:line, to fix only those, recheck their checklist categories and return an updated block.
- Reject: set `rejected --note "<reason>"`; rewrite or split the task, or ask the user.
