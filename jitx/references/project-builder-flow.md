# Project Builder Orchestration Flow

Five-phase workflow for building complete JITX hardware designs from requirements. The orchestrator drives the flow, spawns parallel sub-agents, and enforces exit gates with acceptance reviews.

## Overview

```
Phase 0: Requirements + Architecture
    │  Create PLAN.md + ARCHITECTURE.md
    ▼
Phase 1: Substrate + Components ──── parallel sub-agents
    │  Acceptance review each task
    ▼
Phase 2: Constraints + Circuits + Pins ──── clustered parallel
    │  Acceptance review each task
    ▼
Phase 3: Top-Level Assembly ──── single agent
    │  Acceptance review
    ▼
Phase 4: Build + Verify + Iterate
```

## Task Status Flow

```
pending → in-progress → review → accepted
                          │
                          ├→ rework → review → accepted (max 2 cycles)
                          │
                          └→ rejected (replan or escalate to user)
```

- `pending`: not started
- `in-progress`: sub-agent working
- `review`: sub-agent returned self-evaluation, awaiting orchestrator review
- `accepted`: orchestrator verified, ready for downstream tasks
- `rework`: orchestrator found issues, sent back with specific feedback
- `rejected`: fundamental problem, task needs replanning

---

## Phase 0: Requirements + Architecture

**Who**: orchestrator (no sub-agents)

### Process

1. **Analyze requirements**: parse the user's request, spec documents, or reference designs into structured form.

2. **Identify all components**: propose ideal parts based on electrical requirements and engineering tradeoffs (voltage/current, thermal, peripheral set, package, reliability). Note the part number, package, and datasheet for each. Optionally verify sourcing with `scripts/lcsc_lookup.py` (see `references/parts-sourcing.md`) — but sourcing does not drive the selection.

3. **Map interfaces**: document which components connect to which, via what protocol, and whether SI constraints are needed.

4. **Plan the power tree**: trace power from input through regulators to every load. Note voltage, current, and sequencing requirements.

5. **Assess substrate needs**: based on interface speeds and routing density, determine layer count, material class, and via technology.

6. **Decompose into tasks**: follow `references/decomposition-guide.md` to create the task graph.

7. **Write PLAN.md**: use `references/plan-template.md` as the starting point. Fill in every task with specific details.

8. **Write ARCHITECTURE.md**: summarize module hierarchy, power tree, and interface map. This gives sub-agents the big picture.

### Exit Gate

- [ ] PLAN.md exists with all tasks defined
- [ ] ARCHITECTURE.md exists with power tree and interface map
- [ ] All datasheets and reference materials identified and accessible
- [ ] Dependencies are acyclic
- [ ] No ambiguous requirements remain (ask user if unclear)
- [ ] User has reviewed and approved the plan

---

## Phase 1: Substrate + Components

**Who**: parallel sub-agents (one per task)

### Orchestrator Actions

1. Copy `build_lock.py` from skill scripts into the project's `runner/` directory.
2. For each Phase 1 task in PLAN.md:
   a. Update status to `in-progress`
   b. Spawn a sub-agent with the task definition, relevant datasheets, and instruction to follow `references/task-execution.md`
3. As sub-agents return, perform acceptance review (Part B of task-execution.md).
4. Issue verdicts: accept, rework, or reject.

### Parallel Safety

All Phase 1 tasks are independent — zero mutual dependencies. Spawn all sub-agents simultaneously. Each uses `build_lock.py` for test builds to avoid WebSocket collisions.

### Exit Gate: Phase 1 → Phase 2

ALL of the following must be true:
- [ ] Every Phase 1 task has status `accepted`
- [ ] Every component builds with `status: ok` in its test harness
- [ ] Substrate builds with all routing structures and via definitions
- [ ] Orchestrator has spot-checked high-risk items per task type (see task-execution.md Part B)
- [ ] Interface notes in self-evaluation reports are consistent (port names, power requirements match ARCHITECTURE.md)

---

## Phase 2: Constraints + Circuits + Pin Assignment

**Who**: clustered parallel sub-agents

### Task Ordering

Phase 2 tasks have partial dependencies. Group into clusters:

- **Cluster A: Pin assignment wrappers** — depend on components from Phase 1. These define the provide/require flexibility for the central IC(s). Other Phase 2 tasks may depend on these.
- **Cluster B: Power circuits** — depend on power components. Often independent of other clusters.
- **Cluster C: Interface circuits + constraints** — depend on components, substrate routing structures, and possibly pin assignment wrappers.

Run independent clusters in parallel. Within a cluster, respect dependencies.

### Orchestrator Actions

1. Identify which Phase 2 tasks can run immediately (dependencies all `accepted`).
2. Spawn those sub-agents.
3. As tasks complete and are accepted, check if new tasks are unblocked.
4. Continue until all Phase 2 tasks are accepted.

### Exit Gate: Phase 2 → Phase 3

- [ ] Every Phase 2 task has status `accepted`
- [ ] All circuits build individually with `status: ok`
- [ ] Constraint classes instantiate without error
- [ ] Provide/require interfaces are consistent across wrapper and consuming circuits
- [ ] **Interface circuits expose bundle-typed ports** (I2S, I2C, SPI, USB2, GPIO, Power) — not individual signal ports. If a circuit wraps individual-pin components, the bundle wiring happens inside the circuit.
- [ ] Port names and bundle types match between providers and consumers
- [ ] Power circuit outputs match the voltage/current needs documented in ARCHITECTURE.md

---

## Phase 3: Top-Level Assembly

**Who**: single agent (not parallelizable)

### Process

The orchestrator (or a single sub-agent) assembles the top-level design.

**CRITICAL**: Net symbols (`GroundSymbol`, `PowerSymbol`) and SI constraints (`Constrain`, `ConstrainDiffPair`, `ReferencePlanes`) MUST be applied at the top-level design — not inside subcircuits. Subcircuits create topologies with `>>` but constraints are applied here where the full signal path is visible.

1. Create the top-level Circuit class.
2. Instantiate all subcircuits from Phase 2.
3. Create global ground net with `GroundSymbol`, connect all ground ports, add pours on ground layers.
4. Create power nets with `PowerSymbol`, connect regulator outputs to load inputs.
5. Wire signal interfaces using `require()` from provides. Example:
   ```python
   i2s = self.mcu_wrapper.require(I2S)   # solver picks pins
   self += i2s.sck + self.amp.i2s.sck    # wire bundle sub-ports
   self += i2s.ws + self.amp.i2s.ws
   self += i2s.sd + self.amp.i2s.sd
   ```
   NEVER hardcode GPIO numbers. If a downstream circuit has individual ports instead of a bundle, wire the required bundle's sub-ports to them. Use `>>` topology for SI-constrained signals.
6. Add shared-bus components at this level (NOT inside subcircuits):
   - **I2C pull-ups** — one set per bus, to the correct voltage rail (usually 3.3V)
   - **SPI pull-ups** on CS lines
   - **CAN termination** resistors
   - Any termination that spans multiple subcircuits
7. Apply ALL SI constraints at this level within `ReferencePlanes(GND)` context. Example:
   ```python
   with ReferencePlanes(self.GND):
       usb_topo = Topology(self.mcu.usb.data.p, self.usb_conn.DP)
       self.cst_usb = ConstrainDiffPair(usb_topo) \
           .structure(substrate.DRS_90) \
           .timing_difference(0.1e-12)
   ```
   Every protocol with impedance or timing requirements needs constraints here.
8. Define board shape, mounting holes, and any keepout zones.
9. Build and verify `status: ok`.

### Exit Gate: Phase 3 → Phase 3b

- [ ] Top-level design builds with `status: ok`
- [ ] All nets connected (no floating ports on instantiated circuits)
- [ ] Power tree complete (every load rail connected to a regulator output)
- [ ] All require() calls have matching provides
- [ ] `GroundSymbol` on GND net, `PowerSymbol` on every power rail
- [ ] SI constraints applied **at this level** (not inside subcircuits) for every protocol with impedance/timing requirements
- [ ] `ReferencePlanes(GND)` context wraps all constraint applications
- [ ] Board geometry defined (shape, mounting holes, pours)

---

## Phase 3b: Design-Level Analysis and Loopback

**Who**: orchestrator (CRITICAL — this is where electrical errors are caught)

The top-level assembly compiling does NOT mean the design is correct. The orchestrator must now review the full assembled design as a system and loop back to fix problems. This is not optional — **do not proceed to Phase 4 with known electrical errors**.

### Analysis Steps

Walk through the assembled design and check each of these:

#### 1. Voltage Domain Audit

For every net in the design, verify:
- What voltage is on this net?
- Is anything connected to this net that can't handle that voltage?
- Are all pull-ups to the correct voltage rail? (e.g., I2C pull-ups to 3.3V, not VBUS)
- Are level shifters needed between different voltage domains?

**Common failures:** Pull-ups to VBUS on PD boards (20V kills 3.3V MCU inputs), mixed 1.8V/3.3V IO without level shifting.

#### 2. Bus Contention Audit

For every shared bus (USB D+/D-, I2C, SPI, CAN):
- How many drivers are on this bus?
- Are any ICs driving the bus that shouldn't be? (e.g., PD controller driving D+/D- for BC1.2 while MCU uses them for data)
- Are there analog switches or muxes needed?
- Is bus termination correct and not duplicated?

**Common failures:** USB D+/D- shared between PD controller and MCU, multiple I2C devices with conflicting address.

#### 3. Missing Component Audit

For every IC in the design, compare the circuit against the datasheet application circuit:
- Count the external components in the datasheet. Count the components in the JITX circuit. Are any missing?
- Specifically look for: external transistors (PMOS switches, level shifters), bootstrap capacitors, snubber circuits, compensation networks, discharge resistors
- Check dual-function pins: are they configured with resistors (not hard ties)?

**Common failures:** Missing PMOS on PD controller GATE output, missing bootstrap cap on buck converter, dual-function pin hard-tied to GND preventing fault detection.

#### 4. SI Constraint Audit

For every protocol that requires signal integrity:
- Are constraints actually applied? (not just commented as "TODO")
- Do the ports used in constraints actually exist and connect correctly?
- If constraints failed to apply (e.g., ports aren't DiffPair bundles), this is a **blocking issue** — fix the upstream circuit, don't ship without constraints.

**Common failures:** "Noted for future refactoring" — this means it's broken NOW. Fix it.

#### 5. Power Sequencing Audit

- What happens during power-on? Does anything get powered before its controller is ready?
- Are enable pins handled for startup sequence?
- Does the PD negotiation happen before or after the load powers up?

### Loopback Protocol

When the analysis finds issues:

1. **Classify severity:**
   - **Blocking** (electrical damage, bus contention, missing safety components) → MUST fix before Phase 4
   - **Significant** (missing constraints, wrong configuration) → fix before Phase 4
   - **Minor** (cosmetic, non-functional) → note for Phase 4 iteration

2. **Identify the source:** Which Phase 2 circuit or component caused the issue?

3. **Loop back:** Re-open the task in PLAN.md, spawn a sub-agent to fix it:
   ```
   REWORK for [task-id]: [specific issue found during design-level analysis]

   The assembled design reveals: [describe the system-level problem]
   Root cause in this circuit: [what needs to change]
   Datasheet reference: [page/section showing correct circuit]
   ```

4. **After fixes:** Re-run top-level assembly (Phase 3) and re-do this analysis.

5. **Major redirections:** If the analysis reveals a fundamental architecture problem (e.g., bus contention requiring analog switches, voltage domain incompatibility requiring additional ICs), update ARCHITECTURE.md and PLAN.md. Add new component and circuit tasks as needed. This may require going back to Phase 1 for new component models.

### Exit Gate: Phase 3b → Phase 4

- [ ] **All blocking and significant issues resolved** (no known electrical errors)
- [ ] Voltage domain audit passed (no high-voltage pull-ups on low-voltage ICs)
- [ ] Bus contention audit passed (no shared buses with conflicting drivers)
- [ ] Missing component audit passed (every IC's circuit matches its datasheet)
- [ ] SI constraints applied and functional (not "noted for future")
- [ ] PLAN.md updated with all rework tasks completed

---

## Phase 4: Build + Verify + Iterate

**Who**: orchestrator or single agent

### Process

1. Run full build: `python runner/build_lock.py <ns>.main.Design`
2. Check output for:
   - `status: ok` — proceed to verification
   - `status: error` — read traceback, fix, rebuild
3. Open in JITX UI and verify:
   - Schematic: all connections present, symbols readable
   - Board: components placed (or floating), no overlaps
   - Issues List: SI constraints satisfied or flagged
4. Iterate:
   - Build errors → fix code, rebuild
   - DRC violations → adjust clearances or routing structures
   - SI constraint failures → review parameters, check routing structure impedance
   - Missing connections → trace back to Phase 2/3 and fix

### Completion Criteria

- [ ] `status: ok` on final build
- [ ] No critical DRC violations
- [ ] All SI constraints satisfied (or user-acknowledged exceptions)
- [ ] User has reviewed schematic and board in JITX UI

---

## Session Resumption

If the orchestrator session is interrupted, a new session can resume:

1. Read PLAN.md to see the current state of all tasks.
2. Read ARCHITECTURE.md for the design context.
3. Identify the current phase based on task statuses.
4. Continue from where the previous session left off.

This is why PLAN.md must be kept up-to-date with every status change.

---

## Recovery Procedures

### Rework Loop

When a task is sent back for rework:
1. Orchestrator sends specific issues to the sub-agent (see task-execution.md rework protocol).
2. Sub-agent fixes only the identified issues, re-runs checklist, rebuilds.
3. Orchestrator reviews again.
4. Maximum 2 rework cycles. After that, escalate to reject.

### Replanning

When a task is rejected:
1. Orchestrator analyzes why the approach failed.
2. Options:
   a. Rewrite the task description with better guidance and reassign.
   b. Split the task into smaller, more focused tasks.
   c. Ask the user for clarification or additional data (e.g., missing datasheet pages).
3. Update PLAN.md with the new task definitions.
4. Resume from the affected phase.

### Upstream Cascade

If a Phase 2 task fails because of a Phase 1 output:
1. Identify the upstream task that produced the bad output.
2. Send the upstream task back to rework (with the downstream failure as evidence).
3. After upstream is fixed, re-run the downstream task.
4. Update PLAN.md statuses for both tasks.
