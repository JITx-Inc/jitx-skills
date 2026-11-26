# Project Builder Flow (complete-board)

The orchestrator runs each phase and emits its gate block from `completion-blocks.md` before the next one starts.

## Task Status Flow

- `pending`: startable.
- `blocked: OQ-n`: an open question affects it. Blocking is transitive: a task whose dependency is blocked is blocked, not pending.
- `in-progress`: a sub-agent holds it.
- `review`: its acceptance block is back.
- `accepted`: downstream tasks may start.
- `rework`: sent back with the issues; after two cycles, `rejected`.
- `rejected`: replan it or ask the user.

When a task fails on another task's file, or its block's `Open issues` names a defect in one, confirm the defect at its file:line and send that file's task to `rework` with it as evidence; a spec-note defect goes by CD-1 instead. A `FAIL` or `ERROR` the defect causes is not the finding task's rework: set that task `review --note "waiting on <task-id>"` with no verdict; after the fix, set it `in-progress` and continue its sub-agent to rerun its checks and return an updated block.

## Dispatch

Spawn sub-agents with the Agent tool and `model: "opus"`. Each spawn carries the task definition from PLAN.md, the sub-skill to invoke, `task-execution.md` Part A to follow, and the spec notes or upstream outputs it needs. A PDF goes only to the component sub-agent writing that part's note, or to a sub-agent resolving a listed open question. Set the task `in-progress` before the spawn.

## Phase 0: Requirements and Architecture

The orchestrator alone.

1. Lock the requirements (`decomposition-guide.md` Step 0).
2. Choose the parts (`parts-sourcing.md`).
3. Present the data source plan as a table, Component | Package | Data source | Footprint method | Status, and wait for the user's approval. With a named sourcing channel, the plan carries its evidence for every IC and connector (`parts-sourcing.md`).
4. Ask for the user's approved-parts list (below).
5. Decompose into tasks (`decomposition-guide.md`).
6. Write PLAN.md (`plan-template.md`) and ARCHITECTURE.md (`architecture-template.md`).
7. Show the user both documents and wait for their approval of the plan.

### Approved passives

The parts chain's first member reads `parts/approved-parts.csv`. Ask for a CSV whose header names `category`, `mpn`, `manufacturer`, then one column per attribute a query filters on (`capacitance`, `case`, `rated_voltage_dc`, ...), or an internal parts database a `jitxlib.parts.Provider` can serve, which takes the `csv:` entry's place in the chain. Once the user chose JLCPCB, the chain follows `jitx-jlcpcb`.

With no list, copy the `jitxexamples` example as a stand-in, tell the user it is one, and record it in `Data Sources`:

```bash
mkdir -p parts
python -c "import importlib.resources as r, shutil; shutil.copy(r.files('jitxexamples') / 'parts' / 'example-passives.csv', 'parts/approved-parts.csv')"
```

`ModuleNotFoundError`: install `jitxexamples` (base `jitx` skill, Step 1) and copy again. `FileNotFoundError`: the installed `jitxexamples` predates the CSV; ask the user for a list.

To list the MPNs a build resolved, start `jitx design session <design>` in the background, then:

```bash
jitx design exec <design> -c '
from jitx.inspect import extract
from jitxlib.parts import DeferredPart
def main(design):
    return sorted({part.mpn for part in extract(design.root, DeferredPart)})'
jitx design session --stop <design>
```

It prints the chain-resolved MPNs as a JSON list, no modeled components.

## Phase 1: Substrate and Components

Parallel sub-agents, one per task. Dispatch every startable task in one message carrying all the spawn calls, and record N, B and C for the gate. Review each return (`task-execution.md` Part B).

## Phase 2: Constraints, Circuits and Pin Assignment

Spawn each task once its dependencies are accepted, independent ones in parallel.

### SI verification designs

A constrained interface is every constrained path between the same modules, with every constraint on them (an FPGA to its DDR5 device: data, strobe, address, command and clock, each byte lane's `ConstrainReferenceDifference`). Each gets one `ver-` task, which writes `<ns>/designs/verify_<iface>.py` and its check `<ns>/designs/check_si_<iface>.py`, run as `python -m <ns>.designs.check_si_<iface>`. It depends on every module task on the path and the `cst-` task.

Module tasks verify on their own `TestDesign` and take no SI dependency on each other. The constraints go in `verify_<iface>.py` and the assembly, never a product module: `jitxexamples.patterns.pin_series_array` applies its constraints inside its circuit, which the `SI/top-level applications` grep gate hard-fails under `<ns>/circuits/`, so follow its routing and placement only.

What a verification design holds, its pass bar, how the assembly's groups sort by routing state, where compliance is read, and the parity comparison: `jitx-interconnect-constraints` [Verification design and assembly](../../jitx-interconnect-constraints/references/verification.md#verification-design-and-assembly). On a pin-assigned end, `jitx-pin-assignment` "Constraints on Pin-Assigned Ports".

## Phase 3: Top-Level Assembly

One assembly sub-agent (`asm-01`), with `jitx-circuit-builder`, `jitx-interconnect-constraints`, `jitx-layout-constraints` and `jitx-code-layout`.

1. Instantiate the accepted circuits and wire them; signal interfaces through `require()`.
2. Place bus termination that spans circuits (CAN termination, SPI chip-select pull-ups) at the circuit that composes the bus.
3. Apply every SI constraint in the top-level design inside `ReferencePlanes(GND)`, and compare each with its verification design for the parity row.
4. Write `<ns>/designs/check_si_main.py`, the same check on the top-level design; with pours (step 5's plane pours included), stitching or code-placed copper, `<ns>/designs/check_layout_main.py` (`jitx-code-layout` "Verification").
5. Board shape, mounting holes and keepouts; mechanical data through `jitx-mechanical`. An outline `Board` gives as a limit is drawn at the limit, and one it leaves to place and route at a first size the assembly agent states. Plane pours drawn in code go on the layers `Board` `Layer plan` names. Position in code only what the mechanical constraints fix. Arranging other parts, or routing copper to meet a layout finding, is place and route (`jitx-interactive-layout`), a step of its own, unless the user asked for layout in code.
6. Set passive query defaults on the Design for the lock's assembly tier (`jitx-circuit-builder` "Passives"): machine assembly, SMD only, in every case the assembler accepts; hand-build, 0603 to 1206, through-hole allowed on large parts; specialty, per circuit.
7. Tag the power and ground nets `PowerTag` and `GroundTag`. Set the lock's default trace width and clearance on the Design, and a rule per class of nets, each value with its source (`jitx-layout-constraints` [Defaults and classes](../../jitx-layout-constraints/SKILL.md#defaults-and-classes)). Every net that carries supply current is in one of those classes, a regulator's switch node and output included; none is left at the default width. Where the user asked for the fab's minimum, set no board defaults.

When `asm-01` returns with the top-level build passing, the orchestrator runs `jitx ui open --board --design <module.path.DesignClass>` in the background (base `jitx` skill, "Visualizers") and tells the user the board view is open. It stays open for the rest of the run, place and route included: the orchestrator opens no second board view and never closes this one, and if it cannot open, says so once and goes on. The assembly sub-agent opens no view.

## Phase 3b: Design Audit and Loopback

Spawn a read-only audit agent. It edits nothing, spec notes included, and reads the datasheet PDFs, not the notes; a note that disagrees with its datasheet is a finding. It emits the audit block from `completion-blocks.md` after four passes:

1. Circuit vs datasheet application schematic: count each IC's external parts from the datasheet, not the note, against the code; values and types against the datasheet's; every assumption about input voltage, load, enable timing and sequencing.
2. Assumption compatibility: those assumptions against the system (actual input voltage, sequencing each IC needs, load sums within regulator ratings, voltage domains across boundaries).
3. Interface trace: each multi-IC interface from source to destination through every part (bus conflicts, pull-up value and rail, address conflicts, levels, clock source and format, ESD, termination, SI constraints on every high-speed interface).
4. Power and thermal: regulator ratings against load sums with margin, dissipation against package, hot-plug and power-up behaviour, bulk capacitance against the datasheet.

Then run the outside-voice passes (`outside-voice-review.md`).

### Loopback

The orchestrator decides each finding's disposition ([Precedence and combined verdict](outside-voice-review.md#precedence-and-combined-verdict)) and spawns fix tasks, one per group of findings that change the same files, each with its finding and datasheet reference. A finding only a layout can meet is deferred to place and route and gets no fix task and no placement in the assembly; a rule it needs (width, clearance, keepout, stitching, fencing) is a fix task under `jitx-layout-constraints`, and an SI constraint it needs one under `jitx-interconnect-constraints`.

After the fixes, re-audit the files they changed: each original finding resolved, nothing new introduced. A pass that reads none of the changed code is not repeated. A new finding goes through loopback.

A redirection (new ICs, a missing rail, an architecture change) updates ARCHITECTURE.md and PLAN.md, adds tasks, and returns to that phase.

## Phase 4: Build, Verify, Iterate

The orchestrator or one agent.

1. Run the parts gate, `python scripts/check.py <ns>/ --build <module.path.DesignClass>` and `prune_lock.py --check` (base `jitx` skill, Step 2), listing MPNs as in Phase 0. An `IDEAL-` MPN or `no part found` goes to the user, not a fix task: ask for the approved part, and change a value or rating only with the user's sign-off and the affected circuit recomputed. Every later check runs on the approved parts.
2. Run each `check_si_<iface>` and `check_si_main`.
3. With pours, stitching or code-placed copper, run `python -m <ns>.designs.check_layout_main`; rerun it after any change to placement, routing, pours or layout rules.
4. In the board view already open, and `jitx ui open --schematic --design <module.path.DesignClass>`, check connections, placement, the Issues List and DRC.
5. Dispatch each failure to the task that owns it (a `ver-` task, a module, the assembly; a missing connection back to its Phase 2 or 3 task), review its block, rerun the step.
6. Emit the Phase 4 block.

## Place and Route

When the user asked for a laid-out board, or asks for one at the verdict, and the layout is not in code (Phase 3 step 5), the orchestrator runs place and route itself with `jitx-interactive-layout`, in the board view already open, with no sub-agent. The Phase 4 block's Deferred items and ARCHITECTURE.md `Board` (size, layer plan) are its requirements. Unless the user said to route without a review, stop at the placement review (`general-pnr.md` "Routing", item 3): show the user the placement and route between blocks only after their answer. A change it needs in `<ns>/` (a rule, a constraint, a placement fixed in code) is a fix task. After routing, rerun Phase 4 from step 1 and emit the block again: step 5 takes a failure whose cause is in `<ns>/`, and the orchestrator fixes any other in the layout.
