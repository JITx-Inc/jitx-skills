---
name: jitx-project-builder
description: "Complete-board workflow for JITX: turn board requirements into a buildable, verified design through phased sub-agent work. Use when the user asks to build or design a whole board or PCB from requirements, create a full JITX project, write or trim PLAN.md and ARCHITECTURE.md, classify a request as single-task or complete-board, check a phase exit gate, run the Phase 3b design audit, or resume a board project's task graph. Covers tier classification, Phase 0 to 4, context discipline, task acceptance and gate blocks, grep gates, parts data sourcing, and the shared state documents. Environment setup, the CLI and code conventions are the base jitx skill; one component, circuit, substrate or constraint set on its own goes straight to its sub-skill."
---

# JITX Project Builder

Requirements in, a verified board out, built by sub-agents under phase gates. Run the base `jitx` skill's environment setup first.

## First: Pick the Workflow Tier

Before any architecture, parts research, design prose, code or sub-skill call, write in chat:

> Workflow tier: `single-task` | `complete-board` — because `<one-sentence reason>`

- `single-task`: one sub-skill, one artifact (component, circuit, substrate, constraint set, pin-assignment wrapper), no assembly. Invoke the sub-skill; return a task acceptance block in chat.
- `complete-board`: anything producing a buildable board, however small. An acceptance block per task, five gate blocks, the Phase 3b audit and Phase 4 verification (`references/completion-blocks.md`).

For `complete-board`, write PLAN.md and ARCHITECTURE.md next: no code, architecture proposal or parts list before PLAN.md exists; back out anything done before it. A `single-task` job that grows past one artifact becomes `complete-board` from Phase 0.

## Phases

| Phase | Who acts | Reads (`references/`) |
|-------|----------|-------|
| 0: lock, parts, tasks, PLAN.md | orchestrator | `project-builder-flow.md`, `decomposition-guide.md`, `parts-sourcing.md`, both templates |
| 1: substrate, components | parallel sub-agents | `task-execution.md` Part A |
| 2: constraints, circuits, pins, SI verification | sub-agents | `task-execution.md` Part A |
| 3: assembly | one sub-agent | the same, and the flow's Phase 3 |
| 3b: audit, loopback | audit agent, outside voice | the flow's Phase 3b, `outside-voice-review.md` |
| 4: build, verify | orchestrator or one agent | the flow's Phase 4 |
| Place and route, when the user wants a laid-out board | orchestrator, no sub-agent | the flow's Place and Route |

The orchestrator reviews each return (`task-execution.md` Part B) and emits each gate block.

## Context Discipline

Complete-board only.

- CD-1: the component sub-agent reads the PDF and writes `datasheets/<MPN>.spec.md` (`references/datasheet-spec-template.md`). Building sub-agents read the note, and the PDF only to resolve its `Open questions`, updating the note. At acceptance the orchestrator reads the PDF pages the note cites, never the note as evidence or the whole PDF; an unresolved item goes back to a sub-agent. The audit agent and outside voice read the PDF. A note that disagrees with its datasheet is the defect: corrected by a fix sub-agent and re-audited before any code fix.
- CD-2: the orchestrator writes only PLAN.md, ARCHITECTURE.md, `scripts/` and, in place and route, what `jitx-interactive-layout` writes outside `<ns>/`; sub-agents write all of `<ns>/`, one-line fixes included.
- CD-3: a sub-agent returns its acceptance block, or `blocked: build prompt` with the printed lines, and nothing else.

Build safety: [the base skill's](../jitx/SKILL.md#build-safety-dont-parallelize-same-design-work).

## Checks

Copy `grep_gates.py` and `check.py` from the base `jitx` skill's `scripts/` into the project's. Every task and gate runs:

```bash
python scripts/check.py <ns>/ [--build <module.path.DesignClass>]
```

Its PASS, FAIL and ERROR lines go into the blocks as printed; grep gate dispositions: `references/completion-blocks.md` "Grep Gate Patterns". Checklists: `references/task-execution.md` "Task types".

## Project Structure

```
project/
├── pyproject.toml          # Project config with JITX deps
├── <ns>/                   # The project's Python package, flat (NOT src/<ns>/)
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

## Shared State Documents

One owner per fact; refer to it by section, never copy it.

- PLAN.md: lock, data sources, tasks and statuses, gates, modifications; what a resumed session reads. Copy `scripts/plan_status.py` into the project with it, and change a status only with `python scripts/plan_status.py <task-id> <status> [--note "<text>"]`, a status with a space quoted (`"blocked: OQ-3"`); `--show [<task-id>]` lists them.
- ARCHITECTURE.md: power tree, interface map, board, object hierarchy, design notes.
