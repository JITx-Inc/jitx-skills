---
name: jitx-code-review
description: Same-model self-critique pass for JITX Python code just written in this workspace. Use when the user asks to "review my JITX code", "self-critique", "check JITX conventions", "find string-hacking", "audit before merge", or any equivalent. Mandatory for complete-board tier at task acceptance (folds into Think Twice); user-invoked for single-task work. Catches the architectural failure modes that grep gates and static linters miss — parallel string-keyed models, sibling-attribute reflection, substrate-shaped tables duplicated in designs, build-spec-then-iterate, name-construction at module-import time. Produces severity-tagged findings (CRITICAL / WARNING / NOTE) that fold into the task acceptance block.
---

# JITX Code Review

Task-level architectural self-review for JITX Python code just written in the current workspace. The reviewer agent reads the code with a checklist-bound, evidence-anchored framing — different from the framing under which the code was written — which is what catches what the in-session author rationalized as fine.

This skill is the *per-task same-model pre-pass* in the Think Twice flow (see `jitx/references/task-execution.md` Part A Step 4 and `jitx/references/outside-voice-review.md` "Same-model passes precede codex"). It catches architectural and code-craft smells (string-hacking, parallel models, naming hygiene). Codex outside-voice — which runs only for trigger-list task classes (MCU/FPGA, RF, power, safety, high-speed digital, battery) — catches the JITX-engineering-domain issues (datasheet-vs-code, impedance/return-path, voltage-divider math).

Phase 3b's same-model pre-pass is the **four-pass design audit** (not this skill) — see `jitx/references/completion-blocks.md` "Phase 3b Design Audit Block". By the time Phase 3b runs, every Phase 1/2/3 task has already passed its per-task `jitx-code-review` and the findings live in the task acceptance blocks.

## When this skill runs

- **Mandatory** for every accepted task in complete-board tier. The `jitx` base skill invokes this at the Think Twice step in `task-execution.md` Part A Step 4 (before the orchestrator's acceptance review). The task acceptance block's `JITX code review (self):` field carries the finding count + disposition; missing or `not run` defaults to `block`.
- **User-invoked** for single-task tier. A user who wants self-critique on their single-skill work invokes this directly ("review my JITX code"). Each subskill's SKILL.md mentions the option but does not auto-trigger.
- **Not a replacement** for codex outside-voice. Codex still runs at Phase 3b (mandatory complete-board) and per-task for the trigger list (MCU/FPGA, RF, power converter, safety, high-speed digital, battery — see `jitx/references/outside-voice-review.md`).

## Inputs the review takes

1. **The code under review.** Default: the workspace's `src/<ns>/` directory (everything just written for the current task). The orchestrator may scope tighter (single file) when invoking from Think Twice.
2. **The task acceptance block draft** (if running mid-Think-Twice). Tells the reviewer what was supposed to be built and what evidence the author cites.
3. **The relevant rule sources.** Read at review time:
   - `jitx/SKILL.md` Don'ts (always)
   - `jitx/references/architectural-patterns.md` (always — this is the worked-counter-example source for the dominant failure modes)
   - Subskill SKILL.mds for the work in scope (component-modeler if a component file changed, etc.)
   - `jitx-code-review/references/checklist.md` (the pattern taxonomy)
   - `jitx-code-review/references/patterns.md` (PR-derived worked examples)

The review is **evidence-anchored**: every finding cites `file:line` and quotes a rule sentence (from SKILL.md, a reference file, or a wiki page if applicable). Findings without a citation are downgraded to `NOTE`.

## Workflow

1. **Identify the scope.** Files / directories under review. Default `src/<ns>/`, but a scoped run can target a single file.
2. **Read the rule sources** above. The point of reading them in-skill is so the reviewer cites verbatim — not paraphrases.
3. **Walk the pattern checklist** (`references/checklist.md`). For each pattern, look for instances; for each instance, capture severity and citation.
4. **Apply the architectural pass** (`references/patterns.md`). The dominant failure modes from PR #4 are encoded as worked patterns; check each one against the code under review.
5. **Emit the findings block** in the format below.
6. **Hand back to the caller** (orchestrator in Think Twice, or user for single-task). The orchestrator folds findings into the task acceptance block; the user decides whether to fix or accept-with-rationale.

The skill does **not** modify code. Findings → caller → fix decision → next iteration.

## Severity scheme

Same vocabulary as `outside-voice-review.md` for consistency:

- **CRITICAL** — code clearly violates a rule, or contains a pattern that's named as illegal in `jitx/SKILL.md` Don'ts or `architectural-patterns.md`. Must be fixed before the task can be `accepted`. Examples: `getattr(self, f"...")`, module-level loop populating a global dict, design file with `_SIGNAL_LAYER_TO_VIA` that duplicates the substrate.
- **WARNING** — looks like the failure pattern but has ambiguity (e.g., a `list[dict]` that might be a legitimate parameter-staging pattern, an `f"X_{i}"` that might be a log message). Each WARNING needs a disposition: `fix` or `accept with rationale: <why>`.
- **NOTE** — observation worth recording but not blocking. Code-craft hygiene that's better-done-otherwise (vestigial `from __future__ import annotations`, named constant used exactly once, suboptimal naming).

Combined with the codex outside-voice precedence rule: **any CRITICAL or WARNING finding here changes the combined verdict to `issues-pending`** even if codex says `clean`. Same rule, two same-tier reviewers.

## Output format

```markdown
## JITX code review — <scope, e.g., src/<ns>/circuits/bga_escape.py>

**Reviewer:** jitx-code-review (same-model self-critique)
**Scope:** <list of files reviewed, with revision/commit if relevant>
**Rule sources read:** jitx/SKILL.md, jitx/references/architectural-patterns.md, <subskill SKILL.mds if relevant>

### CRITICAL

- **<pattern tag>** at `<file>:<line>` — <one-line description>. Rule: "<verbatim quote>" (from <source>). Disposition required.
- ...

### WARNING

- **<pattern tag>** at `<file>:<line>` — <one-line description>. <Why this might be the failure mode vs. legitimate use.> Disposition: fix | accept with rationale: <why>.
- ...

### NOTE

- **<pattern tag>** at `<file>:<line>` — <one-line description>.
- ...

### Summary

CRITICAL: <count> | WARNING: <count> | NOTE: <count>
```

The `<pattern tag>` is from the checklist (e.g., `string-keyed-model`, `getattr-on-self`, `substrate-pollution`, `parallel-data-model`). Pattern tags are orthogonal to severity — a single pattern can produce CRITICAL or WARNING findings depending on the specific instance.

## What this skill is NOT

- **Not a port of the internal `code-review` skill.** That one (in `jitx-knowledge`) reviews JITX codebases against the wiki, pulls cached remote clones, runs Claude + codex two-pass. Different use case (cross-repo audit), different evidence flow. This skill is in-workspace, same-model only.
- **Not a replacement for static analysis.** `pyright` and `ruff check` still run as part of the task acceptance block. They catch type / lint issues; this skill catches architectural smells they can't see.
- **Not a build verifier.** `python -m jitx build` still runs. This skill is purely a code-quality pass.

## Compliance-theater watch

The skill can become ritual if the reviewer agent passes everything as `clean` without doing the work. Concrete signals the orchestrator should treat as suspicious:

- `CRITICAL: 0 | WARNING: 0 | NOTE: 0` on a parametric / generator task where the architectural patterns are likely to surface.
- Findings without `file:line` citations or rule quotes.
- All findings tagged `NOTE` when the pattern checklist named CRITICAL-eligible patterns.
- Bulk dispositions (`all accepted, all framework code`) on review-required grep-gate hits — each hit needs a per-line rationale.

A valid review output should let a reader open the cited file at the cited line and verify the finding in under a minute.
