# Outside-Voice Review (codex integration)

The same-model audit in Phase 3b uses the JITX skill knowledge to review its own work. That's load-bearing but not sufficient — agents reliably miss things their own context primes them to overlook. An outside-voice review (codex, or any independent second-opinion tool) catches what the primary agent's prior reasoning made invisible.

This file specifies when to invoke outside-voice review, what to ask it, and how to integrate findings.

## When outside-voice review runs

### Phase 3b — mandatory for complete-board

After the same-model audit produces its block (see `completion-blocks.md` "Phase 3b Design Audit Block"), the orchestrator runs an outside-voice pass. This is **mandatory for complete-board tier**, **not** optional. The two reviews are additive — neither replaces the other.

If the outside-voice tool is unavailable, the verdict for the Phase 3b → 4 gate defaults to **`block`** unless the user explicitly approves proceeding without it. Record `Outside-voice review: not run: <reason>` with `blocking unless user approves` in the audit block.

### Per-task — mandatory for triggered tasks

During Part B (orchestrator acceptance review) — see `task-execution.md` Part B Step 5 — an outside-voice pass runs **before** issuing `accept` for any task in the trigger list below.

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

- single-task tier (cost > value)
- non-triggered task classes (use orchestrator judgement; record reason if invoked)
- re-review of a fix-only loopback where the fix didn't touch the originally flagged code

## What outside-voice reviews — prompt shape

Prompts are **narrow and evidence-anchored**, not "review everything". The prompt names: the target directory codex can read, the exact files/datasheets that constitute the evidence packet, the specific failure modes to look for, and the output format the orchestrator can fold back into the block.

| Trigger | Target dir | Evidence packet | Prompt focus |
|---------|------------|-----------------|---------------|
| Phase 3b complete-board | project root | `PLAN.md`, `ARCHITECTURE.md`, `src/<ns>/`, `datasheets/`, all accepted task acceptance blocks | Cross-reference PLAN.md task statuses vs `src/<ns>/` reality. For each high-stakes IC, compare code against datasheet sections. Surface CRITICAL/WARNING/NOTE findings the same-model audit missed. |
| Per-task: MCU/FPGA | component dir + datasheet PDF | `src/<ns>/components/<part>.py`, `datasheets/<part>.pdf` | Datasheet-vs-code: pin coverage, power-domain completeness, footprint dimensions vs mechanical drawing |
| Per-task: RF | circuit dir + datasheets + relevant ref design | `src/<ns>/circuits/<this>.py`, component files, `datasheets/<rf-part>.pdf` | Impedance, return path, ESD, antenna feed structure |
| Per-task: power converter | circuit dir + regulator datasheet | `src/<ns>/circuits/<this>.py`, `datasheets/<regulator>.pdf` | Voltage divider math, bootstrap, enable, compensation, dissipation |
| Per-task: safety-critical | circuit dir + spec doc | `src/<ns>/circuits/<this>.py`, relevant spec | Isolation, creepage, fail-safe state, fault behavior |
| Per-task: high-speed digital | circuit dir + protocol spec + substrate | `src/<ns>/circuits/<this>.py`, substrate file, protocol spec PDF | Constraint application, topology with `>>`, termination, return-path continuity |
| Per-task: battery/protection | circuit dir + charger datasheet + pack spec | `src/<ns>/circuits/<this>.py`, `datasheets/<charger>.pdf`, pack spec | Charger config, fuel gauge wiring, thermistor, power-path, fault response |

Append a catch-all line at the end of every prompt: **"Also flag any directly observable blocking electrical or geometry mismatch in the reviewed files."** This preserves narrow focus while allowing obvious unknown unknowns to surface.

Every finding from codex must include a file:line citation and (if it references a datasheet) the page/figure or "inference" label. Findings without that anchoring are downgraded to NOTE.

## How to invoke

The configured outside-voice reviewer in Claude Code is the **codex** skill. Invoke it via the `Skill` tool with `skill: "codex"` (or `/codex` as a slash command from the user). The skill resolves its own paths — do not hard-code installation locations in the project.

### Checking availability

Skills available in the current session appear in the system reminder Claude receives at startup. To check from the agent's side:

- **Preferred:** look for `codex` in the session's available-skills list (the system reminder lists what's installed); if it's not there, treat the reviewer as unavailable.
- **Shell-side cross-check:** `command -v codex` returns non-empty if the codex CLI is on `$PATH`. Useful for scripted flows but does not guarantee the wrapping skill is loaded.

If neither check passes, record `Outside-voice review: not run: codex skill not available` in the relevant block. Per the rule above, this **blocks complete-board Phase 3b advancement unless the user explicitly approves proceeding**.

### Invocation pattern

The codex skill itself documents how to run a focused review. Pass it: the target directory codex may read, an output file under `.context/`, and the prompt via stdin or as an argument per the skill's interface. Keep prompts narrow and evidence-anchored (see "What outside-voice reviews — prompt shape" above).

Any read-only outside-voice reviewer that takes a prompt and produces severity-tagged findings can substitute for codex. Document the configured reviewer in the project's `.context/` notes if it isn't codex.

## Integrating findings — combined verdict rule

Codex findings get appended to the relevant block as a new field:

```markdown
**Outside-voice review (codex):** clean | <N> findings | not applicable: <reason> | not run: <reason — blocking unless user approves>
- CRITICAL: <one-line description> — file:line — datasheet p.M fig.N (or "inference") — disposition: fix → new task `<task-id>` | accept with rationale: <why>
- WARNING: <one-line> — file:line — disposition
- NOTE: <one-line> — file:line — for documentation only
```

The field is **always present** in the task acceptance block and the Phase 3b audit block. Valid values: `clean`, `<N> findings`, `not applicable: <reason>`, `not run: <reason/blocking status>`. A missing field fails review.

### Precedence and combined verdict

**Any CRITICAL or WARNING outside-voice finding changes the combined review verdict to `issues-pending`** — even if the same-model audit said `clean`. The combined gate cannot advance until each CRITICAL/WARNING finding is one of:

- **Fixed** — new task created, fix landed, re-audit confirms resolution
- **Downgraded with rationale** — explicit argument why the finding is a false positive or non-applicable; user reviews
- **User-approved** — user explicitly accepts the finding as known and acceptable for this design; recorded in deferred items

NOTE findings document only; they don't block.

This precedence rule prevents the outside-voice pass from being decorative — its findings carry equal weight to the same-model audit's.

## Where this is referenced

The mandatory invocation sites:

- `references/project-builder-flow.md` — Phase 3b section: after the same-model audit block, run outside-voice pass per this file. Result is required in the Phase 3b audit block and the Phase 3b → 4 gate.
- `references/task-execution.md` — Part B Step 5 (Issue Verdict): for trigger-list task classes, run outside-voice before issuing `accept`. Result is required in the task acceptance block.
- `references/completion-blocks.md` — task acceptance block and Phase 3b audit block templates carry the `Outside-voice review` field; it's always present.

## Compliance-theater watch list

The outside-voice pass can become ritual instead of real verification. Concrete signals the orchestrator should watch for:

- **`Outside-voice review: clean`** on a trigger-list task with no codex output file under `.context/` to back it up
- **Findings without file:line citations or datasheet refs** — codex was asked but didn't actually inspect the evidence
- **`not run: codex unavailable`** without a follow-up plan, on a complete-board project
- **Same-model audit `clean` + outside-voice `<N> findings, all downgraded`** without specific rationale per finding

A valid outside-voice section should let a reviewer reopen the codex output file and verify at least one finding against the cited source in under a minute.
