# Outside-Voice Review (codex integration)

The same-model audit in Phase 3b uses the JITX skill knowledge to review its own work. That's load-bearing but not sufficient — agents reliably miss things their own context primes them to overlook. An outside-voice review (codex, or any independent second-opinion tool) catches what the primary agent's prior reasoning made invisible.

This file specifies when to invoke outside-voice review, what to ask it, and how to integrate findings.

## Same-model passes precede codex (two distinct pre-passes, two distinct scopes)

Codex outside-voice never runs first. A same-model pass always precedes it. The pre-pass differs by scope:

- **Per-task (Think Twice — `task-execution.md` Part A Step 4):** the `jitx-code-review` skill runs as the same-model self-critique pre-pass. Catches architectural and code-craft smells: parallel string-keyed models, sibling-attribute reflection, substrate-shaped tables in design files, build-spec-then-iterate, name-construction patterns. Reads `jitx/SKILL.md` Don'ts and `jitx/references/architectural-patterns.md`. **Mandatory for every sub-agent task in complete-board tier**; user-invoked for single-task work. Codex then runs *per-task* only for trigger-list task classes (this file's "Per-task — mandatory for triggered tasks" section).
- **Phase 3b (whole-design audit):** the **four-pass design audit** runs as the same-model pre-pass: Circuit-vs-Datasheet, Assumption Compatibility, Interface-by-Interface Trace, Power+Thermal (see `references/completion-blocks.md` "Phase 3b Design Audit Block"). `jitx-code-review` does **not** re-run at Phase 3b because every Phase 1/2/3 task has already passed its per-task `jitx-code-review`. Codex then runs a bounded fan-out of outside-voice passes after the four-pass audit.

In both scopes the two reviewers are additive — neither replaces the other. Findings from both get severity tags (`CRITICAL` / `WARNING` / `NOTE`) and feed the same combined-verdict precedence rule below. A CRITICAL or WARNING finding from *either* reviewer changes the combined verdict to `issues-pending`.

## When outside-voice review runs

### Phase 3b — mandatory for complete-board

After the same-model audit produces its block (see `completion-blocks.md` "Phase 3b Design Audit Block"), the orchestrator attempts the bounded outside-voice fan-out defined below. The attempt is **mandatory for complete-board tier**. The four-pass audit remains the primary gate evidence; the outside voice is additive.

Tool unavailability, a nonzero reviewer exit, or an invocation that produces no
non-empty findings output is recorded as `skipped: <reason>`. A skipped reviewer
has made no claim about the design, so it is not a failed review and does not by
itself block Phase 3b → 4. Any output that does exist is integrated under the
combined-verdict rule. The audit block records attempted, completed, and skipped
pass counts so a missing reviewer is visible rather than silently treated as
`clean`.

### Per-task — mandatory for triggered tasks (complete-board tier)

During Part B (orchestrator acceptance review), see `task-execution.md` Part B Step 5, an outside-voice pass is attempted **before** issuing `accept` for any complete-board task in the trigger list below. **The trigger list applies only to complete-board tier.** In single-task tier, the task acceptance block's `Outside-voice review` field is always `not applicable: single-task tier`, regardless of whether the task class is in the list. A user invoking the component-modeler subskill directly for a single MCU does not trigger a codex pass; if they want an outside-voice review on that work, they invoke it themselves.

**Trigger list (mandatory outside-voice):**

| Task class | What outside-voice reviews |
|------------|----------------------------|
| **MCU / FPGA components** | Pin coverage, power-domain completeness, reset, boot straps, programming/debug interface, footprint dimensions vs mechanical drawing |
| **RF components and circuits** | Impedance budget, return-plane keepout, ESD class, antenna feed structure, matching network |
| **Power converters** | Voltage-divider math (target voltage vs Vref and R1/R2), bootstrap caps, enable handling, compensation if external, dissipation vs package rating, sequencing |
| **Safety-critical circuits** | Isolation barrier, creepage, fail-safe state, fault-on-component-failure behavior |
| **High-speed digital / controlled-impedance interfaces** | DDR, LPDDR, PCIe, USB, Ethernet, HDMI, DisplayPort, MIPI, SerDes — constraints, topology, termination, return-path continuity |
| **Battery charging / protection** | Charger IC, fuel gauge, pack protection, thermistor handling, power-path behavior, fault response |

For other task classes (passive circuit, low-speed interface like I2C/SPI/UART, simple connector, jellybean component) the orchestrator **may** invoke outside-voice if a red flag warrants it — but the block must record a reason. Default is no outside-voice for non-triggered tasks; it would be noise.

**Mixed-signal frontends** are not automatic triggers. Invoke outside-voice only when precision, protection, leakage, filtering, or ADC reference integrity is load-bearing for the task; bare ADC reads don't need it.

### When outside-voice does NOT run

- **single-task tier** — the trigger list does not apply; field value is `not applicable: single-task tier`. User can invoke codex manually if they want.
- complete-board tier, non-triggered task class (orchestrator may invoke if a red flag warrants it; record reason if invoked)
- re-review of a fix-only loopback where the fix didn't touch the originally flagged code

## What outside-voice reviews — prompt shape

Prompts are **narrow and evidence-anchored**, not "review everything". The prompt names: the target directory codex can read, the exact files and datasheets that constitute the evidence packet, the specific failure modes to look for, and the output format the orchestrator can fold back into the block. Codex reads the datasheet PDFs, not the spec notes. It is the reviewer of last resort, and a spec note is the building chain's own output, so a review anchored to it cannot catch an extraction error. Codex runs in its own context, so the pages cost the orchestrator nothing.

| Trigger | Target dir | Evidence packet | Prompt focus |
|---------|------------|-----------------|---------------|
| Phase 3b: accepted trigger-list task | project root | that task's acceptance block, files it owns or touches, and only its relevant datasheet or protocol PDF | Re-check that task's trigger-list failure modes against the shipping assembly integration. One accepted task produces one bounded pass and one output. |
| Phase 3b: cross-cutting | project root | ARCHITECTURE.md `Power Tree` and only the regulator, protection, and load files plus their relevant datasheets | Power-tree arithmetic, sequencing, hot-plug behavior, and absolute-maximum compatibility only. |
| Per-task: MCU/FPGA | component dir + datasheet PDF | `<ns>/components/<part>.py`, `datasheets/<part>.pdf` | Datasheet-vs-code: pin coverage, power-domain completeness, footprint dimensions vs mechanical drawing |
| Per-task: RF | circuit dir + datasheets + relevant ref design | `<ns>/circuits/<this>.py`, component files, `datasheets/<rf-part>.pdf` | Impedance, return path, ESD, antenna feed structure |
| Per-task: power converter | circuit dir + regulator datasheet | `<ns>/circuits/<this>.py`, `datasheets/<regulator>.pdf` | Voltage divider math, bootstrap, enable, compensation, dissipation |
| Per-task: safety-critical | circuit dir + spec doc | `<ns>/circuits/<this>.py`, relevant spec | Isolation, creepage, fail-safe state, fault behavior |
| Per-task: high-speed digital | circuit dir + protocol spec + substrate | `<ns>/circuits/<this>.py`, substrate file, protocol spec PDF | Constraint application, topology with `>>`, termination, return-path continuity |
| Per-task: battery/protection | circuit dir + charger datasheet + pack spec | `<ns>/circuits/<this>.py`, `datasheets/<charger>.pdf`, pack spec | Charger config, fuel gauge wiring, thermistor, power-path, fault response |

Append a catch-all line at the end of every prompt: **"Also flag any directly observable blocking electrical or geometry mismatch in the reviewed files."** This preserves narrow focus while allowing obvious unknown unknowns to surface.

Phase 3b never sends the project root as an undifferentiated evidence packet. It
creates one pass per accepted trigger-list task and one cross-cutting pass, may
run those independent passes concurrently, and writes each result separately.
The prompt names the exact files in that pass. It does not include all of
`<ns>/`, all datasheets, all acceptance blocks, or a generic "review everything"
request.

Every finding from codex must include a file:line citation and, when it references a datasheet, the page/figure or an "inference" label. Findings without that anchoring are downgraded to NOTE.

## How to invoke

The configured outside-voice reviewer is the **codex** skill when it is available in the current agent environment. Invoke it as the installed `codex` skill (Claude Code users may invoke `/codex`; Codex users may invoke `$codex` when installed). The skill resolves its own paths — do not hard-code installation locations in the project.

### Checking availability

Skills available in the current session appear in the agent skill list at startup. To check from the agent's side:

- **Preferred:** look for `codex` in the session's available-skills list; if it's not there, treat the reviewer as unavailable.
- **Shell-side cross-check:** `command -v codex` (PowerShell: `Get-Command codex`) returns non-empty if the codex CLI is on the `PATH`. Useful for scripted flows but does not guarantee the wrapping skill is loaded.

If neither check passes, the relevant block records
`Outside-voice review: skipped: codex skill not available`. The skipped attempt is
visible but is not a failed gate.

### Invocation pattern

The codex skill itself documents how to run a focused review. It receives the
target directory it may read, one output file for this bounded pass, and the
prompt via stdin or as an argument per the skill's interface. The output path is
project-local and unique per pass. Prompts stay narrow and evidence-anchored (see
"What outside-voice reviews: prompt shape" above).

An invocation counts as completed only when it leaves a non-empty findings
output. If it exits without that output, the orchestrator records the pass as
`skipped: no reviewer output` and continues combining the passes that completed.
It does not convert missing output into a `clean` result or a failed design gate.

Any read-only outside-voice reviewer that takes a prompt and produces
severity-tagged findings can substitute for codex. The audit block names the
configured reviewer when it is not codex.

## Integrating findings — combined verdict rule

Codex findings fill the `Outside-voice review (codex)`, `Outside-voice CRITICAL`, `Outside-voice WARNING`, and `Outside-voice NOTE` rows in the task acceptance block. Phase 3b records the overall result in its outside-voice field and puts each finding in `Findings and Loopback Decisions`. The canonical compact shapes live in `references/completion-blocks.md`.

The field is **always present** in the task acceptance block and the Phase 3b audit block. Valid values: `clean`, `<N> findings`, `not applicable: <reason>`, `skipped: <reason>`. A missing field fails review.

### Precedence and combined verdict

**Any CRITICAL or WARNING finding — from `jitx-code-review` (same-model) OR codex (outside-voice) — changes the combined review verdict to `issues-pending`**, even if the other reviewer said `clean`. The combined gate cannot advance until each CRITICAL/WARNING finding is one of:

- **Fixed** — new task created, fix landed, re-audit confirms resolution
- **Downgraded with rationale** — explicit argument why the finding is a false positive or non-applicable; user reviews
- **User-approved** — user explicitly accepts the finding as known and acceptable for this design; recorded in deferred items

NOTE findings document only; they don't block.

A skipped outside-voice pass contributes no findings and does not change the
combined verdict. It remains recorded with its reason. A later produced finding
still takes precedence under the rules above.

This precedence rule prevents either pass from being decorative — both reviewers' findings carry equal weight.

## Where this is referenced

The mandatory invocation sites:

- `references/project-builder-flow.md` — Phase 3b section: after the same-model audit block, run outside-voice pass per this file. Result is required in the Phase 3b audit block and the Phase 3b → 4 gate.
- `references/task-execution.md` Part A Step 4 — same-model `jitx-code-review` runs after grep gates and before emitting the task acceptance block, mandatory for every complete-board sub-agent task.
- `references/task-execution.md` Part B Step 5 (Issue Verdict): for trigger-list task classes, run outside-voice (codex) before issuing `accept`. Result is required in the task acceptance block.
- `references/completion-blocks.md` — task acceptance block carries both the `JITX code review (self)` and `Outside-voice review (codex)` fields (both always present). Phase 3b audit block carries only the `Outside-voice review (codex)` field (Phase 3b's same-model pre-pass is the four-pass audit recorded in the block body itself, not the per-task `jitx-code-review`).

## Compliance-theater watch list

The outside-voice pass can become ritual instead of real verification. Concrete signals the orchestrator should watch for:

- **`Outside-voice review: clean`** on a trigger-list task with no non-empty reviewer output file to back it up
- **Findings without file:line citations or datasheet refs** — codex was asked but didn't actually inspect the evidence
- **`skipped: codex unavailable`** recorded as `clean` or omitted from the attempt counts
- **Same-model audit `clean` + outside-voice `<N> findings, all downgraded`** without specific rationale per finding

A valid outside-voice section should let a reviewer reopen the codex output file and verify at least one finding against the cited source in under a minute.
