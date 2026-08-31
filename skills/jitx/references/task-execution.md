# Sub-Agent Task Execution Protocol

Two-tier quality system: sub-agents validate their own work, then the orchestrator independently reviews before accepting.

---

## Part A: Sub-Agent Self-Validation ("Think Twice")

### Why This Exists

When an agent builds something complex in hardware, it can miss key details on the first pass — floating enable pins, missing thermal pads, wrong output types, forgotten decoupling. But when prompted to look harder at the same data, they catch what was missed. This protocol formalizes that second look.

The output of Part A is a **task acceptance block** (template in `references/completion-blocks.md`) — a structured artifact, not a prose summary. The orchestrator in Part B reviews the block, not free-form text.

### The Protocol

#### Step 1: Receive Task

Read your task definition from PLAN.md. Note:
- **Task heading / phase**: task ID, name, and phase
- **Type / skill / deps**: task type, sub-skill, and accepted prerequisites
- **Data**: approved sources, specifications, and upstream outputs
- **Specifics**: task-specific design facts. The file path and class name come from the `Verify` module path, not from prose here
- **Checklist**: which domain checklist(s) apply
- **Verify**: build command for testing
- **Status**: current resumable state. `blocked: OQ-n` means do not start; return it unstarted and say which question is open
- **Questions**: engineering questions for every circuit and architectural questions only for parametric tasks

#### Step 2: Invoke Sub-Skill, Read the Datasheet Evidence, and Implement

**The sub-agent MUST invoke the sub-skill and use the datasheet evidence.** It does not design circuits from memory. For complete-board work, the component-modeling sub-agent first extracts the real PDF pages into `datasheets/<MPN>.spec.md` using `references/datasheet-spec-template.md`, then it and every later task read that note. A later sub-agent opens the PDF only for an item listed under `Open questions` and updates the note before continuing. For single-task work, the sub-agent reads the actual datasheet directly. The datasheet's authority and source ranking do not change; see `references/parts-sourcing.md` "Evidence Hierarchy and Conflict Resolution" (datasheet > errata > app notes > vendor reference design > user-supplied known-good > prior internal project > community).

| Task type | Skill / source | Standing instructions |
|-----------|----------------|-----------------------|
| `component` | `jitx-component-modeler`; approved datasheet evidence | Checklists: Component Modeling, plus MCU/FPGA where the part is one. Invoke the skill. For complete-board work, use its `extract_pages.py` to read the real pinout, mechanical, and application pages, write `datasheets/<MPN>.spec.md`, then model from the note. For single-task work, model from the datasheet. Capture the IC's application circuit in Step 5. |
| `circuit` | `jitx-circuit-builder` + `jitx-component-modeler`; every IC's datasheet evidence | Checklists: Power Circuit or Interface Circuit as applicable, Datasheet Compliance, General Gotcha Scrub. Answer every engineering question with cited evidence from the spec note for complete-board work or the datasheet for single-task work. The English datasheet for every IC remains at `datasheets/<mpn>.pdf`; the sub-agent counts and implements every required external component without simplification and captures each application circuit in component-modeler Step 5 before wiring. Expose bundle-typed ports, use `>>` through paths constrained at top level, and place shared-bus pull-ups or termination only at the bus-aggregation level. |
| `assembly` | `jitx-circuit-builder` + `jitx-interconnect-constraints` + `jitx-layout-constraints`; accepted subcircuits and ARCHITECTURE.md | Checklists: General Gotcha Scrub. Instantiate every subcircuit; connect power and ground with `PowerSymbol` / `GroundSymbol`; tag those nets with `PowerTag` / `GroundTag`; wire bundles with `require()`; add shared-bus parts at the aggregation level; apply every SI constraint inside `ReferencePlanes(...)`; define board geometry; set manufacturing-appropriate `capacitor_defaults` / `resistor_defaults` and document specialty refinements; set the rule set by invoking `jitx-layout-constraints` (the four defaults, the net-class rules, any escape rules; its Layout Constraints checklist applies, and its check script's command and exit code go in the acceptance block). See `project-builder-flow.md` Phase 3. |
| `substrate` | `jitx-substrate-modeler` when custom; board specification | Checklists: Substrate. If JLCPCB is approved, check `JLC04161H_1080` (4L/1080, RS_50/DRS_90/DRS_100), `JLC04161H_7628` (4L/7628, RS_50/DRS_90/DRS_100), and `JLC06161H_7628` (6L/7628, RS_50/DRS_100); each includes its stackup, fab rules, and vias. Import the suitable class directly. Otherwise invoke the skill. Ensure the layer count, routing structures, and vias fit the interface speeds and component packages. |
| `constraint` | `jitx-interconnect-constraints`; protocol spec and substrate | Checklists: Substrate, General Gotcha Scrub. Define the protocol constraint classes from the timing/impedance limits; use `ConstrainDiffPair` for differential pairs and the substrate's routing structure. Define here, but apply constraints only in top-level assembly. |
| `pin-assignment` | `jitx-pin-assignment`; IC datasheet evidence and ARCHITECTURE.md `Interface Map` | Checklists: General Gotcha Scrub. Use the spec note for complete-board work or the datasheet for single-task work. Define the required provides and allowed mux flexibility; do not hardcode a pin choice that the provider should solve. |
| `audit` | No skill; the orchestrator plus the outside voice in `outside-voice-review.md` | Checklists: the four Phase 3b passes in `project-builder-flow.md`. Read every IC's datasheet PDF, not its spec note, run the four passes, then the outside-voice review; a same-model `clean` verdict is not a verification. |
| `verify` | No skill; top-level design and build artifacts | Checklists: the Phase 4 verification block in `completion-blocks.md`. Run the full build, inspect DRC and SI constraints in the Issues List, iterate on failures, and emit the Phase 4 verification block. |

**Parts not in jitxlib:** If a passive or simple component (LED, TVS diode, ferrite bead) is not available from jitxlib queries, check if the user provided a KiCad footprint or ask them for one. If the user has named LCSC/JLCPCB as the sourcing channel, `parts2jitx-lcsc` *lookup/evidence* (stock, lifecycle, datasheet URL, pinout) is implied — install `parts2jitx` and run it. **Footprint data ingestion** via `parts2jitx-lcsc --footprint` + `parts2jitx-kicad` still requires explicit per-project approval (EasyEDA terms-of-use). See `references/parts-sourcing.md` "LCSC / JLCPCB via parts2jitx" for the split-consent table. Do not give up on a component because it's not in the standard library.

**Common mistakes from not reading the datasheet:**
- Missing external transistors (e.g., PMOS for power switching on PD controllers)
- Missing output filter inductors (e.g., LC filter on Class D amplifier outputs)
- Missing reset/boot circuitry on MCUs (RC filter on reset, pull-up on boot pins)
- Wrong pull-up voltage domain (e.g., pulling I2C to VBUS instead of 3.3V)
- Connecting data lines that the IC drives internally (e.g., D+/D- on a PD controller that uses them for BC1.2)
- Omitting bootstrap capacitors on buck converters
- Hard-tying dual-function pins instead of using resistors

#### Step 2b: Save All Source Data Locally

All downloaded data must be saved to the project — never use /tmp or transient locations:
- **Datasheets** → `datasheets/<mpn>.pdf`
- **Datasheet spec notes (complete-board)** → `datasheets/<MPN>.spec.md`
- **KiCad footprints** → `kicad_footprints/<mpn>.kicad_mod` (user-provided, manufacturer download, or from `parts2jitx-lcsc --footprint`)
- **Generated components** → `<namespace>/components/<category>/<file>.py`

This ensures reproducibility across sessions and avoids repeated downloads.

#### Step 3: Initial Build Test

Run the required checks and test build once from the project root:

```bash
python scripts/check.py <ns>/ --build <module.path.TestDesign>
```

Don't run a concurrent build of the same design in parallel — see `jitx/SKILL.md` "Build Safety".

If any line is `FAIL` or `ERROR`, fix the cause and re-run the command until every line is `PASS`. Do not proceed to Step 4 with a broken build.

#### Step 4: Domain Checklist Review + Grep Gates (CRITICAL)

**STOP. Do not return yet.**

Open `references/domain-checklists.md`, then open the linked checklist(s) for your task type. Go through EVERY item:

1. For each item, re-examine the cited datasheet spec note or specification. For complete-board work, this is the faithful extract from the real pages, not a memory. For single-task work, re-examine the datasheet directly.
2. If there is a discrepancy, fix it now.
3. If an item does not apply, note why.

This step typically catches 3-5 issues. Common misses by domain:

**Components**: thermal pad forgotten, NC pins with physical pads omitted, pin naming inconsistent with datasheet

**MCU/FPGA**: not all power domains modeled (only VCC but missed VCCA, VCCIO per bank), boot/config pins missing, debug interface incomplete

**Power**: enable pin floating (needs pull-up or tie to VIN), PGOOD is open-drain but no pull-up, feedback divider uses manual resistor values instead of solver, thermal pad not connected to ground

**Interface**: missing decoupling on one of several power pins, I2C missing pull-ups, UART TX/RX crossed wrong, unused inputs floating

**Substrate**: missing via definition for a needed layer transition, routing structure velocity in wrong units

The Step 3 `check.py` invocation runs the grep gates. Its `grep gates` summary line reports the hard-fail and review-required counts. Hard-fail hits must be fixed before proceeding. Review-required hits get a disposition (`fixed`, `accepted with rationale: <why>`, or `deferred to <named follow-up>`) when reported in the task acceptance block in Step 6. If the domain checklist changes Python code, re-run the single Step 3 command in Step 5.

For the full pattern set and copy-paste templates: read `references/completion-blocks.md` "Grep Gate Patterns" section.

After the `grep gates` line reports `PASS`, run the same-model code review:

```
Skill: jitx-code-review
Scope: <ns>/<files-this-task-touched>
```

This is **mandatory for every sub-agent task in complete-board tier**, before emitting the task acceptance block. The review catches the architectural failure modes that grep regex can't see — parallel string-keyed models, sibling-attribute reflection, substrate-shaped tables duplicated in designs, build-spec-then-iterate, untyped intermediate records. CRITICAL findings must be fixed before Step 6; WARNING findings get a disposition (fix or accept-with-rationale) in the task acceptance block's `JITX code review (self):` field; NOTE findings are recorded but don't block.

The review reads `jitx/SKILL.md` Don'ts, `jitx/references/architectural-patterns.md`, the subskill SKILL.mds relevant to this task, and its own `references/checklist.md`. It produces a structured findings block with severity tags and `file:line` citations that fold directly into the task acceptance block.

If `jitx-code-review` is unavailable (skill not loaded, errored), record `JITX code review (self): not run: <reason>` in the task acceptance block. Per the precedence rule in `references/completion-blocks.md`, this defaults to `block` unless the user explicitly approves proceeding.

#### Step 5: Fix and Rebuild

If Step 4 found issues (it usually does; checklist or grep), fix them all and re-run the required checks and build:

```bash
python scripts/check.py <ns>/ --build <module.path.TestDesign>
```

Every summary line must report `PASS`; the `grep gates` line must show 0 hard-fail hits. Re-run `jitx-code-review` if the fix touched code the previous review flagged.

#### Step 6: Emit the Task Acceptance Block

Emit the **task acceptance block** verbatim using the template in `references/completion-blocks.md`. The block is the report; prose summaries are not a substitute. Required fields include `Primary source`, `Secondary references`, `Footprint source`, `Checks run` (domain checklist + General Gotcha Scrub + the four exact `check.py` verification summary lines), `Interface notes`, and `Verdict (self): ready-for-review`.

Rules (full set in `completion-blocks.md`):

- **No block, not done.** A task without the block is `in-progress` regardless of build state.
- **`N/A` requires a reason.** Bare `N/A` in any field is rejected on review.
- **Primary source must be ground truth.** Datasheet, manufacturer reference design, vendor mechanical drawing, or protocol spec — not a prior project. Prior projects belong only under `Secondary references`.
- **Static checks** run through `python scripts/check.py <ns>/` where Python was touched. A `FAIL` or `ERROR` line blocks acceptance.

#### Step 7: Return

For complete-board work, the sub-agent returns the task acceptance block and nothing else, at most 350 words. It names written files by path in the block and does not return a transcript, narration, or restated file contents. Every tier still completes Steps 4-6 before returning.

---

## Part B: Orchestrator Acceptance Review

After a sub-agent returns, the orchestrator performs an independent review of the **task acceptance block** the sub-agent emitted. The orchestrator does NOT trust the block claims at face value — it verifies them against the code, the build, and the checklist.

A returned task without an acceptance block is automatically `rework`; run `python scripts/plan_status.py <task-id> rework --note "missing acceptance block"`. The block is the contract.

When a valid block arrives, run `python scripts/plan_status.py <task-id> review` before starting the acceptance review.

### Review Steps

#### 1. Read the Generated Code

Open each file the sub-agent created or modified. Scan for:
- Obvious structural issues (missing `self.` on nets/components, empty classes)
- Completeness (does the code match what the task asked for?)
- Code patterns that violate JITX conventions (see the Gotcha Scrub checklist)

#### 2. Verify the Build Claim

If the sub-agent's block reports a passing build, confirm by checking for the test harness file and that the code structure is plausible. For critical tasks, re-run the required checks and build:

```bash
python scripts/check.py <ns>/ --build <module.path.TestDesign>
```

#### 3. Spot-Check High-Risk Checklist Items

Do not re-run the entire checklist. Focus on the items most commonly missed for this task type:

| Task Type | High-Risk Items to Verify |
|-----------|--------------------------|
| Component | Power/ground pin count matches the spec note (complete-board) or datasheet (single-task), thermal pad present, pin naming |
| Component (footprint) | Pad positions plausible for package size, row spacing correct, pad dimensions match the cited spec-note drawing (complete-board) or datasheet drawing (single-task), not fabricated from memory |
| MCU/FPGA | All power domains present, programming interface complete, reset pin present |
| Power circuit | Enable pin handling, PGOOD output type + pull-up, **feedback divider uses solver not manual values**, bootstrap cap present |
| Interface circuit | **Exposes bundle-typed ports**, decoupling on every IC power pin, **I2C pull-ups only if this circuit is the bus-aggregation level** (encloses both ends of a private bus); otherwise pull-ups go at the level that composes the bus |
| **Any circuit** | **Did the sub-agent read the spec note (complete-board) or datasheet (single-task)?** Compare against the cited application circuit. Count external components; are any missing (transistors, caps, resistors)? Check pull-up voltage domains; nothing should pull to a high-voltage rail like VBUS. |
| Substrate | All via types defined, ground plane continuity, impedance achievable |

#### 4. Check Interface Compatibility

Verify that the task output is compatible with downstream tasks:
- **Do interface circuits expose bundle-typed ports?** If they expose individual signal ports (SCLK, LRCLK, SDIN), send back for rework — this breaks require() at top level.
- Are provide/require bundles consistent with the pin-assignment plan?
- Do power ports match the voltage/current the power tree will supply?
- Are constraint interfaces (routing structures, topology ports) compatible?

#### 5. Issue Verdict

For **complete-board** tasks in the outside-voice trigger list (MCU/FPGA, RF, power converter, safety-critical, high-speed digital / controlled-impedance, battery charging / protection), **run an outside-voice (codex) pass before issuing `accept`**. The trigger list does not apply to single-task tier; for single-task, the block's `Outside-voice review` field is `not applicable: single-task tier`. See `references/outside-voice-review.md` for trigger rules, prompt shape, invocation, and the combined-verdict rule. Append the outside-voice result as a field in the task acceptance block; CRITICAL/WARNING findings block `accept` until fixed, downgraded with rationale, or user-approved.

Append the acceptance verdict to the same task acceptance block the sub-agent emitted:

```markdown
**Verdict (acceptance):** accept | rework | reject
**Notes:** <if rework or reject: specific issues with file:line references>
```

**Accept**: Task passes. Run `python scripts/plan_status.py <task-id> accepted`.

**Rework**: Specific issues found. Run `python scripts/plan_status.py <task-id> rework --note "<specific issue summary>"`. Respawn the same sub-agent with:
- The original task definition
- The specific issues found (code references, line numbers)
- Instruction to fix only the identified issues and re-run checklist
- The sub-agent retains its prior context; this is a continuation, not a restart

On respawn, run `python scripts/plan_status.py <task-id> in-progress`.

**Reject**: Fundamental approach is wrong. Run `python scripts/plan_status.py <task-id> rejected --note "<reason>"`. Options:
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
- Return an updated task acceptance block
```

The sub-agent fixes only the identified issues, re-checks, rebuilds, and returns an updated task acceptance block. The orchestrator reviews again. Maximum 2 rework cycles before escalating to reject. Status changes use `scripts/plan_status.py`; rewriting PLAN.md wholesale to change a status is not allowed.

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
4. Relevant datasheet spec notes or upstream task outputs. Send a PDF only to the component-modeling sub-agent responsible for its initial extraction or to a later sub-agent resolving a listed open question
