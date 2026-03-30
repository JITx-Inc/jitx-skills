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

2. **Identify all components**: propose ideal parts based on electrical requirements and engineering tradeoffs (voltage/current, thermal, peripheral set, package, reliability). Note the part number, package, and datasheet for each. Optionally verify sourcing availability via `jlc_search` (see `references/parts-sourcing.md`) — but the search does not drive the selection.

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
- [ ] Port names and bundle types match between providers and consumers
- [ ] Power circuit outputs match the voltage/current needs documented in ARCHITECTURE.md

---

## Phase 3: Top-Level Assembly

**Who**: single agent (not parallelizable)

### Process

The orchestrator (or a single sub-agent) assembles the top-level design:

1. Create the top-level Circuit class.
2. Instantiate all subcircuits from Phase 2.
3. Create global ground net with `GroundSymbol`, connect all ground ports, add pours on ground layers.
4. Create power nets with `PowerSymbol`, connect regulator outputs to load inputs.
5. Wire signal interfaces using `require()` from provides → topology `>>` to circuit ports.
6. Apply board-level SI constraints within `ReferencePlanes(GND)` context.
7. Define board shape, mounting holes, and any keepout zones.
8. Build and verify `status: ok`.

### Exit Gate: Phase 3 → Phase 4

- [ ] Top-level design builds with `status: ok`
- [ ] All nets connected (no floating ports on instantiated circuits)
- [ ] Power tree complete (every load rail connected to a regulator output)
- [ ] All require() calls have matching provides
- [ ] SI constraints applied and visible in the design
- [ ] Board geometry defined

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
