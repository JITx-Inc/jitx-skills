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

2. **Identify all components**: propose ideal parts based on electrical requirements and engineering tradeoffs (voltage/current, thermal, peripheral set, package, reliability). Note the part number, package, and datasheet for each.

3. **Map interfaces**: document which components connect to which, via what protocol, and whether SI constraints are needed.

4. **Plan the power tree**: trace power from input through regulators to every load. Note voltage, current, and sequencing requirements.

5. **Assess substrate needs**: based on interface speeds and routing density, determine layer count, material class, and via technology. **Check predefined substrates first**: if fab house is JLCPCB and design needs standard 4-layer or 6-layer FR-4 with 50/90/100 ohm impedance, use a predefined substrate from `jitxlib.jlcpcb` (JLC04161H_1080, JLC04161H_7628, JLC06161H_7628) — no substrate modeling task needed. Only create a custom substrate for non-JLCPCB, non-FR-4, or non-standard impedance requirements.

6. **Data source audit**: for every component, identify where its data will come from. Present a table to the user for approval **before proceeding**. See the Data Source Audit section below.

7. **Decompose into tasks**: follow `references/decomposition-guide.md` to create the task graph.

8. **Write PLAN.md**: use `references/plan-template.md` as the starting point. Fill in every task with specific details. Include the approved data sources.

9. **Write ARCHITECTURE.md**: summarize module hierarchy, power tree, and interface map. This gives sub-agents the big picture.

### Data Source Audit

Before decomposing into tasks, present the user with a data source plan for each component. This ensures the user controls where data comes from and can provide their own files.

**Present this table and wait for approval:**

```
## Data Source Plan

| Component | Package | Data Source | Footprint Method | Status |
|-----------|---------|-------------|------------------|--------|
| MCU (STM32H753) | QFP-100 | User datasheet (provided) | JITX QFP generator | Ready |
| USB-C connector | Non-std | Need footprint | User to provide .kicad_mod, or LCSC lookup | Needs input |
| LDO (LM1117) | SOT-223 | Datasheet from manufacturer | JITX SOT generator | Will fetch |
| Buck (TPS62933) | SOT-23-6 | User datasheet (provided) | JITX SOT23_6 generator | Ready |
| WiFi module | Non-std | Need footprint + datasheet | User to provide, or LCSC lookup | Needs input |

**Data sources:**
- "User datasheet (provided)" — user has already supplied the PDF
- "Datasheet from manufacturer" — will download from manufacturer site (ti.com, st.com, etc.)
- "JITX [generator] generator" — standard package, dimensions from datasheet
- "User to provide .kicad_mod" — non-standard package, user has KiCad footprint
- "LCSC lookup" — non-standard package, will use parts2jitx if installed (fallback)

Please confirm data sources or provide alternatives (datasheets, footprints, specs).
```

**Rules:**
- Always prefer user-provided data over automated lookups
- Standard packages (QFN, SOIC, SON, SOT, QFP, BGA) use JITX generators — no footprint download needed
- For non-standard packages, ask the user if they have a `.kicad_mod` before suggesting LCSC
- LCSC/EasyEDA is a fallback, not the default — only suggest it when the user has no data and `parts2jitx` is available
- Do NOT proceed past the data audit until the user approves the data source plan

### Exit Gate

- [ ] PLAN.md exists with all tasks defined
- [ ] ARCHITECTURE.md exists with power tree and interface map
- [ ] Data source audit completed and user approved
- [ ] All datasheets and reference materials identified and accessible (or user committed to providing them)
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

## Phase 3b: Design Review and Loopback

**Who**: orchestrator spawns a **read-only audit agent** (critic only — no code edits), then separately spawns fix agents for issues found.

Each subcircuit was designed in isolation. Now review the assembled design as a system. **Do not proceed to Phase 4 with known electrical errors.**

### Audit Structure

Before spawning the audit agent, run the static lint check:

```bash
python scripts/jitx_lint.py src/<namespace>/
```

This catches mechanical mistakes (square cutouts, VBUS pull-ups, missing self. storage, bare net expressions, I2C pull-ups in subcircuits, missing SI constraints, hard-tied dual-function pins). Fix any errors before proceeding.

Then spawn a sub-agent to perform the design-level audit. The audit agent reads code and datasheets but **does not edit any files**. It produces a report with issues classified as CRITICAL / WARNING / NOTE.

The audit runs four passes:

#### Pass 1: Circuit vs Datasheet Application Schematic

For each major IC circuit, open the datasheet's typical application schematic and compare component-by-component:
- Count external components in the datasheet. Count components in the code. Flag any missing.
- Check passive values match datasheet recommendations (cap values, resistor values, inductor values).
- Check component types match (e.g., datasheet says 0.22uF bootstrap but code has 0.1uF).
- Note every assumption the circuit makes about its operating environment (input voltage, load current, enable timing, power sequencing).

#### Pass 2: Assumption Compatibility

Collect all assumptions from Pass 1 and check them at the system level:
- Does the actual input voltage match what each circuit assumes?
- Does the power sequencing match what each IC requires? (e.g., does the amp expect PDN held low during power-up, but the circuit pulls it high immediately?)
- Do the current draws add up within regulator ratings?
- Are voltage domains compatible across circuit boundaries?

#### Pass 3: Interface-by-Interface Trace

For every interface connecting two or more ICs, trace the complete signal path from source to destination through every component:
- **USB**: trace D+/D- from connector through every device on the bus. Are there bus conflicts? ESD protection? Series termination? **Are SI constraints applied?**
- **I2C**: trace SDA/SCL. Pull-up voltage and value correct? Address conflicts? Level compatible?
- **I2S**: trace BCLK/LRCLK/DIN/DOUT. Clock source correct? Format (I2S vs TDM vs LJ) compatible?
- **SPI**: trace MOSI/MISO/SCK/CS. Polarity? Speed? Pull-ups on CS?
- **Power**: trace each rail from source through regulation to every load. Decoupling at every IC?
- For every high-speed interface (USB, Ethernet, DDR, PCIe, HDMI): **verify SI constraints exist and are applied at the top level**. If constraints are missing, this is CRITICAL.

#### Pass 4: Power and Thermal

- Verify every regulator's output current rating exceeds the sum of its loads (with margin).
- Check thermal dissipation: P = (Vin - Vout) * I for linear regulators, efficiency loss for switchers. Flag any package that will exceed its thermal rating.
- Check hot-plug and transient scenarios: what happens when power appears suddenly? Does anything see voltage before its regulator stabilizes?
- Verify bulk capacitance meets datasheet recommendations (especially for power amplifiers).

### Loopback

After the audit report, the orchestrator (not the audit agent) decides what to fix:

- **CRITICAL issues**: must fix before Phase 4. Spawn a separate sub-agent for each fix with the specific issue and datasheet reference.
- **WARNING issues**: should fix. Spawn fix agents or fix directly.
- **NOTE issues**: document for the user, fix if straightforward.

After fixes, **re-run the audit** to verify the fixes didn't introduce new issues and the original issues are resolved. Do not skip the re-audit.

For major redirections (bus contention needing new ICs, missing power rails, architecture changes), update ARCHITECTURE.md and PLAN.md, add new tasks, and go back to the appropriate phase.

Do not accept "noted for future refactoring" — if it's broken, fix it now.

### Exit Gate: Phase 3b → Phase 4

- [ ] Audit found no CRITICAL or WARNING issues (or all were fixed and re-audited)
- [ ] Every high-speed interface has SI constraints applied and functional
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
