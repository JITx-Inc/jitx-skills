# Sub-Agent Task Execution Protocol

Two-tier quality system: sub-agents validate their own work, then the orchestrator independently reviews before accepting.

---

## Part A: Sub-Agent Self-Validation ("Think Twice")

### Why This Exists

When Claude builds something complex in hardware, they tend to miss key details on the first pass — floating enable pins, missing thermal pads, wrong output types, forgotten decoupling. But when prompted to look harder at the same data, they catch what was missed. This protocol formalizes that second look.

### The Protocol

#### Step 1: Receive Task

Read your task definition from PLAN.md. Note:
- **Description**: what to build, including file path and class name
- **Inputs / Datasheet**: datasheets, specs, or outputs from prior tasks
- **Skill**: which sub-skill to invoke
- **Checklist**: which domain checklist(s) apply
- **Verification**: build command for testing

#### Step 2: Invoke Sub-Skill and Implement

Load the appropriate JITX sub-skill and follow its instructions:

| Task Type | Skill |
|-----------|-------|
| Component | `jitx-skills:jitx-component-modeler` |
| Circuit | `jitx-skills:jitx-circuit-builder` |
| Assembly | `jitx-skills:jitx-circuit-builder` (top-level is also a Circuit) |
| Substrate | `jitx-skills:jitx-substrate-modeler` |
| SI constraints | `jitx-skills:jitx-interconnect-constraints` |
| Pin assignment | `jitx-skills:jitx-pin-assignment` |
| Verify | No skill — orchestrator runs `jitx build` and reviews output |

#### Step 2b: Save All Source Data Locally

All downloaded data must be saved to the project — never use /tmp or transient locations:
- **Datasheets** → `datasheets/<mpn>.pdf`
- **KiCad footprints** → `kicad_footprints/<mpn>.kicad_mod` (from `lcsc_lookup.py --footprint -o`)
- **Generated components** → `src/<namespace>/components/<category>/<file>.py`

This ensures reproducibility across sessions and avoids repeated downloads.

#### Step 3: Initial Build Test

Build using the lock wrapper to avoid collisions with parallel agents:

```bash
python <project>/runner/build_lock.py <module.path.TestDesign>
```

If it fails, fix errors and rebuild until `status: ok`. Do not proceed to Step 4 with a broken build.

#### Step 4: Domain Checklist Review (CRITICAL)

**STOP. Do not return yet.**

Open `references/domain-checklists.md` and find the checklist(s) for your task type. Go through EVERY item:

1. For each item, re-examine the datasheet or specification — do not check from memory.
2. If there is a discrepancy, fix it now.
3. If an item does not apply, note why.

This step typically catches 3-5 issues. Common misses by domain:

**Components**: thermal pad forgotten, NC pins with physical pads omitted, pin naming inconsistent with datasheet

**MCU/FPGA**: not all power domains modeled (only VCC but missed VCCA, VCCIO per bank), boot/config pins missing, debug interface incomplete

**Power**: enable pin floating (needs pull-up or tie to VIN), PGOOD is open-drain but no pull-up, feedback divider uses manual resistor values instead of solver, thermal pad not connected to ground

**Interface**: missing decoupling on one of several power pins, I2C missing pull-ups, UART TX/RX crossed wrong, unused inputs floating

**Substrate**: missing via definition for a needed layer transition, routing structure velocity in wrong units

#### Step 5: Fix and Rebuild

If Step 4 found issues (it usually does), fix them all and rebuild:

```bash
python <project>/runner/build_lock.py <module.path.TestDesign>
```

Verify `status: ok`.

#### Step 6: Self-Evaluation Report

Write a report in this format:

```
## Task: [task-id] [Task Name]
## Status: PASS | FAIL

### Implementation
[1-2 sentences: what was built, key decisions made]

### Build Result
status: ok
[or: status: error — with the error details]

### Checklist Review
Checklist(s) used: [Component + MCU/FPGA, Power Circuit, etc.]
Items checked: N/N
Issues found and fixed:
  - [issue 1]: [what was wrong] → [what was fixed]
  - [issue 2]: [what was wrong] → [what was fixed]
Items not applicable:
  - [item]: [why it doesn't apply]

### Interface Notes
Ports exposed: [list of ports that downstream tasks will connect to]
Power requirements: [voltage and current needs for upstream power tree]
Constraints needed: [any SI constraints that should be applied at top level]

### Known Limitations
[Anything that could not be resolved, or assumptions made]
```

#### Step 7: Return

Return the self-evaluation report. Do NOT return without completing Steps 4-6.

---

## Part B: Orchestrator Acceptance Review

After a sub-agent returns, the orchestrator performs an independent review. The orchestrator does NOT trust the self-evaluation at face value.

### Review Steps

#### 1. Read the Generated Code

Open each file the sub-agent created or modified. Scan for:
- Obvious structural issues (missing `self.` on nets/components, empty classes)
- Completeness (does the code match what the task asked for?)
- Code patterns that violate JITX conventions (see the Gotcha Scrub checklist)

#### 2. Verify the Build Claim

If the sub-agent claims `status: ok`, confirm by checking for the test harness file and that the code structure is plausible. For critical tasks, re-run the build:

```bash
python <project>/runner/build_lock.py <module.path.TestDesign>
```

#### 3. Spot-Check High-Risk Checklist Items

Do not re-run the entire checklist. Focus on the items most commonly missed for this task type:

| Task Type | High-Risk Items to Verify |
|-----------|--------------------------|
| Component | Power/ground pin count matches datasheet, thermal pad present, pin naming |
| Component (footprint) | Pad positions plausible for package size, row spacing correct, pad dimensions match datasheet mechanical drawing — not fabricated from memory |
| MCU/FPGA | All power domains present, programming interface complete, reset pin present |
| Power circuit | Enable pin handling, PGOOD output type + pull-up, **feedback divider uses solver not manual values** |
| Interface circuit | **Exposes bundle-typed ports** (I2S, I2C, SPI, USB2, GPIO), decoupling on every IC power pin, pull-ups on open-drain signals |
| Substrate | All via types defined, ground plane continuity, impedance achievable |

#### 4. Check Interface Compatibility

Verify that the task output is compatible with downstream tasks:
- **Do interface circuits expose bundle-typed ports?** If they expose individual signal ports (SCLK, LRCLK, SDIN), send back for rework — this breaks require() at top level.
- Are provide/require bundles consistent with the pin-assignment plan?
- Do power ports match the voltage/current the power tree will supply?
- Are constraint interfaces (routing structures, topology ports) compatible?

#### 5. Issue Verdict

**Accept** — Task passes. Update PLAN.md status to `accepted`.

**Rework** — Specific issues found. Respawn the same sub-agent with:
- The original task definition
- The specific issues found (code references, line numbers)
- Instruction to fix only the identified issues and re-run checklist
- The sub-agent retains its prior context; this is a continuation, not a restart

**Reject** — Fundamental approach is wrong. Options:
- Rewrite the task definition in PLAN.md with better guidance
- Escalate to the user for clarification
- Reassign to a different task decomposition

### Rework Protocol

When sending a rework request to a sub-agent:

```
REWORK for task [task-id]: [Task Name]

Issues found during acceptance review:
1. [specific issue with file:line reference]
2. [specific issue with file:line reference]

Action required:
- Fix the issues listed above
- Re-run the domain checklist (focus on the categories where issues were found)
- Rebuild and verify status: ok
- Return an updated self-evaluation report
```

The sub-agent fixes only the identified issues, re-checks, rebuilds, and returns an updated report. The orchestrator reviews again. Maximum 2 rework cycles before escalating to reject.

---

## Task Sizing Guidelines

Scope tasks so a single sub-agent can complete them in one session:

| Task Type | Typical Scope | Notes |
|-----------|--------------|-------|
| Component (simple) | 1 part, <20 pins | SOT, SOIC, small QFN |
| Component (complex) | 1 part, 20-100 pins | Large QFN, QFP |
| Component (very complex) | 1 part, 100+ pins | BGA, FPGA, large MCU |
| Component family | 2-4 related parts | Same manufacturer, similar packages |
| Substrate | Full stackup + vias + routing structures | Always one task |
| Circuit (simple) | 1 regulator or 1 interface | Power rail, I2C bus |
| Circuit (complex) | 1 multi-component interface | DDR, PCIe, Ethernet |
| Constraint set | 1 protocol | All constraints for that protocol |
| Pin assignment | 1 component wrapper | All provides for one IC |

### Parallel vs Sequential

- All Phase 1 tasks (substrate + components) are independent — run in parallel.
- Phase 2 tasks may have partial dependencies (circuits depend on components from Phase 1, constraints depend on substrate routing structures). Run independent groups in parallel.
- Phase 3 (top-level assembly) and Phase 4 (build/verify) are sequential — single agent.

### Spawning Sub-Agents

Use the Agent tool with `model: "opus"` for sub-agents. Each sub-agent receives:
1. The task definition from PLAN.md
2. Instruction to invoke the appropriate sub-skill
3. Instruction to follow this execution protocol (reference this file)
4. Any relevant datasheets or upstream task outputs
