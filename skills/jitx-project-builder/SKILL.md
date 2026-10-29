---
name: jitx-project-builder
description: "Complete-board workflow for JITX: turn board requirements into a buildable, verified design through phased sub-agent work. Use when the user asks to build or design a whole board or PCB from requirements, create a full JITX project, write or trim PLAN.md and ARCHITECTURE.md, classify a request as single-task or complete-board, check a phase exit gate, run the Phase 3b design audit, or resume a board project's task graph. Covers tier classification, Phase 0 to 4, context discipline, task acceptance and gate blocks, grep gates, parts data sourcing, and the shared state documents. Environment setup, the CLI and code conventions are the base jitx skill; one component, circuit, substrate or constraint set on its own goes straight to its sub-skill."
---

# JITX Project Builder

The complete-board workflow: requirements in, a buildable and verified board out, built by parallel sub-agents under phase gates. Run the base `jitx` skill's environment setup first; this skill assumes a working CLI, runtime and `scripts/check.py`.

## First: Pick the Workflow Tier

> **STOP. Classify first. Before any architecture proposal, parts research, design prose, code, or `Skill(...)` invocation other than environment probes, your first observable action must be a chat line of the form:**
>
> > **Workflow tier: `single-task` | `complete-board` — because `<one-sentence reason>`**
>
> **For `complete-board`, the *next* observable action must be writing `PLAN.md` (and `ARCHITECTURE.md`).** Verbal architecture proposals, parts-list bullets, "here's what I'll build" prose, or `Write(...)` of code before `PLAN.md` exists are explicitly invalid work for a complete-board project — they must be backed out before the workflow can continue.
>
> If you find yourself already typing "Big design — here's my proposed architecture..." or "I'll set up the skeleton and start filling in components", you have skipped Phase 0. Stop, classify, and create `PLAN.md` first.
>
> This callout exists because the prior failure mode was exactly this: the agent jumped from request to architecture prose to component files without classifying, never entered Phase 0, and bypassed every Pass 1–5 enforcement.

After environment setup, classify the work into one of two tiers. The tier names which output blocks are required and whether the formal Phase 0 → Phase 4 chain applies. Every tier requires a **task acceptance block** for each unit of work — no exceptions.

| Tier | When | Required output | Path |
|------|------|-----------------|------|
| **single-task** | One subskill against one artifact: a component, a circuit, a substrate, a constraint set, a pin-assignment wrapper. No top-level assembly. | Task acceptance block in chat | Invoke the subskill directly |
| **complete-board** | Anything beyond a single isolated artifact — anything that produces a buildable board, no matter how few components. | Task acceptance block per task + phase exit gate blocks + Phase 3b audit + Phase 4 verification | Full Project Builder Workflow below |

If you're tempted to call something "small" or "trivial" to avoid the workflow, classify it as complete-board. The Phase 0–4 ceremony is cheap on a small board (a few extra block emissions); the cost of skipping it on a real board is shipping with required features missing. The original failure mode of this skill was exactly the "looks small, skip the workflow" escape hatch.

For tier definitions, the task acceptance block, phase exit gate blocks, the Phase 3b design audit block, and the Phase 4 verification block: read `references/completion-blocks.md`.

Do NOT skip the planning phase for complete-board designs. Do not start exploring libraries or writing code until PLAN.md exists.

## Project Builder Workflow

For building complete JITX designs from requirements — multiple components, substrate, circuits, and constraints assembled into a working board. Use this when the design involves 3+ components with a substrate and interconnected circuits.

### Phases

| Phase | What | Parallelism |
|-------|------|-------------|
| 0 | Requirements analysis, decompose into tasks, create PLAN.md | Orchestrator only |
| 1 | Model substrate + all components | Fully parallel sub-agents |
| 2 | SI constraints, pin assignment, circuit wiring | Clustered parallel |
| 3 | Top-level assembly (instantiate, connect, constrain) | Single agent |
| 3b | **Design-level analysis + loopback** (voltage domains, bus contention, missing components, SI) | Orchestrator — loops back to fix upstream |
| 4 | Build, verify DRC + SI, iterate on failures | Single agent |

For full phase details and gate criteria: read `references/project-builder-flow.md`
For how to decompose requirements into tasks: read `references/decomposition-guide.md`
For PLAN.md format: read `references/plan-template.md`
For ARCHITECTURE.md format: read `references/architecture-template.md`

### Context Discipline

This section applies only to the `complete-board` tier. `single-task` work is exempt.

**CD-1: Datasheets are read where the reading is cheap and verified where the reader is independent.**

| Reader | Reads | Writes |
|---|---|---|
| Extraction sub-agent (usually the component-modeling sub-agent) | the datasheet PDF | `datasheets/<MPN>.spec.md`, at most 400 words, per `references/datasheet-spec-template.md`, citing the pages it used |
| Building sub-agents (circuit, assembly, pin-assignment, constraints) | the spec note; the PDF only to resolve an item under `Open questions`, then it updates the note | design code |
| Orchestrator, acceptance review | the PDF pages the note cites for the items being checked; never the note as the evidence, never the whole PDF | nothing under `<ns>/` |
| Phase 3b audit agent, outside-voice reviewer | the PDF | findings only; the audit agent edits nothing |

Where a note and the datasheet disagree, the note is the defect: a fix sub-agent corrects the note, a re-audit confirms it, and only then is a fix dispatched against the code. The orchestrator sends an unresolved item back to a sub-agent rather than opening the PDF itself. "Re-examine the datasheet" in `references/task-execution.md` means re-examine the cited spec note for complete-board building work.

**CD-2: The orchestrator does not author design code.** It creates and edits only `PLAN.md`, `ARCHITECTURE.md`, and files under `scripts/`. A sub-agent writes every file under the project namespace `<ns>/`, including one-line fixes. The orchestrator reads code during acceptance review but does not write it. If spawning feels heavy for a fix, batch the fix into the next sub-agent rework cycle.

**CD-3: A sub-agent returns its acceptance block and nothing else.** No transcript, narration, or restated file contents. It names each written file by path in the block; the orchestrator reads it from disk if needed.

### Build Safety

The rule is the base skill's [Build safety](../jitx/SKILL.md#build-safety-dont-parallelize-same-design-work). Phase 1 sub-agents can run in parallel, each working on its own component file and its own test design. They are not running concurrent builds of the *same* design. Phase 2/3/4 builds are inherently sequential.

### Grep Gate Enforcement

Copy `scripts/grep_gates.py` and `scripts/check.py` from the base `jitx` skill into the
project's `scripts/` directory. Copy
`jitx-physical-layout/scripts/check_realization.py` to
`<project>/scripts/check_realization.py`; it is owned and tested by its skill.
SI constraints need no copied script. Each design whose SI constraints are
checked gets a report script under `<ns>/`, at `<ns>/designs/check_si_<name>.py`:
the Python check in `jitx-interconnect-constraints` "Verification" (its body
in `main()` behind the `__name__` guard) with that design imported, run from
the project root as
`python -m <ns>.designs.check_si_<name>` while the project's runtime is running.
This skill's `scripts/plan_status.py` is copied when PLAN.md is created as
described below. Sub-agents and the
orchestrator at every phase exit gate run the single static-check entry point
against the project's Python package (e.g. `<ns>/`) to enforce lint, formatting,
type, and JITX grep-gate checks:

```bash
python scripts/check.py <ns>/
```

Use `--build <module.path.DesignClass>` when the verification also requires a build. The command prints one summary line per check. Those exact lines populate the matching acceptance-block fields. The `grep gates` line reports hard-fail hits, which block task acceptance and gate transitions, and review-required hits, which need a disposition in the task acceptance block. Pattern set and disposition rules: `references/completion-blocks.md` "Grep Gate Patterns".

### Two-Tier Quality System

Sub-agent work goes through TWO quality checks before being accepted:

**1. Sub-Agent Self-Validation ("Think Twice")**

After initial implementation, sub-agents MUST stop and run the domain-specific checklist against the cited datasheet spec note for complete-board work or the datasheet for single-task work. This forced second pass typically catches 3-5 missed details (floating enable pins, missing thermal pads, wrong output types, forgotten decoupling). Sub-agents return a **task acceptance block** documenting what they checked and fixed. The block is mandatory; "build clean" is not a substitute. See `references/completion-blocks.md` for the template.

**2. Orchestrator Acceptance Review**

The orchestrator does NOT blindly trust the self-validation block. For each returned task:
- Read the generated code for obvious issues
- Verify the build claim (re-run `python scripts/check.py <ns>/ --build <module.path.DesignClass>` for critical tasks)
- Spot-check high-risk checklist items independently against the cited datasheet spec note for complete-board work or the datasheet for single-task work
- Verify interface compatibility with downstream tasks
- Append the acceptance verdict to the same block: **accept** / **rework** (send back with specific issues) / **reject** (replan)

A task without an acceptance block is `in-progress`, not done. Phase gates only open when ALL tasks in the phase have `Verdict (acceptance): accept` blocks.

For the full protocol: read `references/task-execution.md`
For block templates: read `references/completion-blocks.md`
For domain checklists: read `references/domain-checklists.md`, then open every linked checklist that applies. Net-class guidance lives in `references/net-classes.md`.

### Exit Gates

| Gate | Key Criteria |
|------|-------------|
| 0 → 1 | PLAN.md created with all tasks, data source audit approved, user approved plan |
| 1 → 2 | All components + substrate build individually, acceptance reviews passed; **Dispatch:** `N`, `B`, `C` recorded; for `N >= 3`, both `B == N` and `C < 3` fail unless each serialized task names the dependency that forced it |
| 2 → 3 | All circuits build, constraint classes valid, provide/require interfaces consistent |
| 3 → 3b | Top-level assembles, all nets connected, power tree complete |
| 3b → 4 | **Design-level analysis passed**: voltage domains correct, no bus contention, no missing components, SI constraints functional. All blocking issues fixed via loopback. |

Do NOT proceed past a gate if any task has unresolved failures. Fix upstream before moving downstream.

### Parts Data and Footprint Conversion

The agent selects parts based on engineering requirements first. Data for each component comes from the **user-approved data source plan** (see Phase 0 data audit).

**Data sources (in priority order):**
1. **User-provided** — datasheets, KiCad footprints, or specs the user supplies directly
2. **JITX generators** — standard packages (QFN, SOIC, BGA, SOT, SON, QFP) with dimensions from datasheets
3. **KiCad footprints**: for packages no generator expresses, a user-provided or manufacturer `.kicad_mod`. A distributor or third-party library footprint needs the user's per-project approval (`references/parts-sourcing.md`).

For non-standard packages (connectors, RF modules): `jitx-component-modeler` reads the `.kicad_mod` and writes each entry into the component. **NEVER hand-craft pad positions** for a purchasable part. Standard packages use built-in JITX generators. All symbols use `BoxSymbol`. Exception: mechanical / vendor-defined footprints (Tag-Connect, pogo-pin fixtures, castellations, fiducials) where no purchasable component exists — see `references/parts-sourcing.md` "Mechanical / Vendor-Defined Footprints".

For details: read `references/parts-sourcing.md`

### Project Structure

Standard JITX project layout — what `jitx project layout init` seeds, plus the conventional subdirs for larger projects:
```
project/
├── pyproject.toml          # Project config with JITX deps
├── <namespace>/            # Flat package (NOT src/<namespace>/)
│   ├── __init__.py
│   ├── main.py             # Seeded Design class; the top-level design for a single-design project
│   ├── substrate.py        # Substrate definition, or the predefined-class import (add as needed)
│   ├── components/         # Custom component definitions (the scaffold seeds resistor.py)
│   │   ├── <category>/     # mcus, connectors, power, etc.
│   │   │   └── <mfr>_<mpn>.py
│   │   └── __init__.py
│   ├── circuits/           # Reusable circuit blocks (add as needed)
│   │   └── power/          # One module per rail or power group
│   ├── constraints/        # SI constraint classes, one module per protocol (add as needed)
│   └── designs/            # Additional top-level designs, when a project carries more than one
├── designs/                # Build output directory (created on first build)
├── .socket.jitx            # Written by `jitx runtime start --background`
├── .jitx/logs/             # Runtime logs (written by the daemon)
└── .venv/                  # Virtual environment
```

### Shared State Documents

The orchestrator creates and maintains these in the project root. Give every fact one owner and refer to the owning document by section name instead of copying it:

- **PLAN.md** — Owns the requirements lock, approved data sources, task graph and statuses, gate outcomes with deferred/blocking items, and one-line modification history. It is the resumable source of truth for the work. Copy this skill's `scripts/plan_status.py` into the project `scripts/` directory. Change a task status only with `python scripts/plan_status.py <task-id> <status> [--note "<short note>"]`; inspect statuses with `python scripts/plan_status.py --show [<task-id>]`. (`plan-template.md` owns the status rule.) Prose edits that add tasks, gate outcomes, or modification history are unaffected.
- **ARCHITECTURE.md** — Owns the power tree, interface map, board and mechanical constraints, parametric object-hierarchy commitments, and non-derivable design notes. It is the source of design context for sub-agents.
