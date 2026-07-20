# Completion Blocks — Mandatory Output Templates

Structured output that any JITX work must emit before claiming "done". The blocks are the artifact — prose summaries are not a substitute. An agent that finishes work without emitting the relevant block has not actually finished.

This file holds:

1. **Workflow tiers** — which artifacts apply to which size of job.
2. **Task acceptance block** — the per-task completion artifact (universal: every tier requires this).
3. **Grep gate patterns** — what `jitx/scripts/grep_gates.py` enforces.
4. **Phase exit gate blocks** — for complete-board tier transitions (Phase 0→1, 1→2, 2→3, 3→3b, 3b→4).
5. **Phase 3b design audit block** — read-only audit with CRITICAL / WARNING / NOTE classification.
6. **Phase 4 verification block** — final JITX UI / Issues / DRC / SI verification with explicit tool-availability handling.

---

## Workflow Tiers

The first decision in any JITX work is which tier applies. The tier names which blocks are required, not which work is done. Every tier requires the **task acceptance block** for each unit of work.

**Tier classification is upstream of Phase 0.** Only complete-board enters the formal Phase 0 → Phase 4 chain. Single-task is routed before that.

| Tier | When to use | Required output blocks | Phase chain |
|------|-------------|------------------------|-------------|
| **single-task** | One subskill invocation against one artifact: one component, one circuit, one substrate, one constraint set, one pin-assignment wrapper. No top-level assembly. | Task acceptance block (1) | None |
| **complete-board** | Anything beyond a single isolated artifact — any work that produces a buildable board, no matter how few components. | Task acceptance block per task + phase exit gate blocks + Phase 3b audit block + Phase 4 verification block | Full Phase 0 → 1 → 2 → 3 → 3b → 4 |

### Why no "small-board" middle tier

Earlier revisions of this skill defined a small-board tier as a lighter-weight middle ground for "trivially decomposable" projects. It turned out to be a footgun: agents used "this is just a small board" as an escape hatch from Phase 0 ceremony, and the numeric heuristics (2–8 components, ≤2 power rails) excluded boards that genuinely needed the full process. The cost of Phase 0–4 on a small project is a few extra block emissions; the cost of skipping it on a real project is shipping with required features missing.

If you're tempted to call something "small" or "trivial" to avoid the workflow, classify it as complete-board. Phase 0 will be brief; that's fine.

### Tier upgrade

If a job classified as `single-task` grows beyond a single artifact mid-work, re-class it as `complete-board`. Write `PLAN.md` and `ARCHITECTURE.md` retroactively, then continue with full Phase 0 → 4 enforcement. Don't drift past the single-artifact line without upgrading.

---

## Task Acceptance Block

**Required:** every task in every tier. Sub-agents emit this on completion. The orchestrator (or the user, in single-task mode) appends the acceptance verdict.

Copy this template verbatim. Fill every field. Every `N/A` requires a reason.

```markdown
## Task complete: <task-id-or-short-name>

**What was built:** <one sentence — file path + class name>

**Build:** `status: ok` (via `<exact build command run>`)

**Primary source:** <datasheet PDF path + sections referenced (cite page/figure for any mechanical dimension), OR the equivalent source-of-truth — manufacturer reference design, vendor mechanical drawing, protocol spec. **For any named IC / connector / non-passive part where the user named a sourcing channel:** the row must also include channel evidence (e.g. for LCSC: `parts2jitx-lcsc <C-number>` output path saved to project). See `parts-sourcing.md` "Required-Sourcing Rule". Bare "datasheet (from memory)" or "typical dimensions" is invalid for a real MPN.>

**Secondary references:** <list, or "none">
- <e.g. "User-supplied known-good design at <path> — used to cross-check pinout">
- <e.g. "Prior internal project <path> — used for X only after datasheet confirmed">

**Footprint source:** <KiCad file path + origin> | <JITX standard generator: QFN/SOIC/etc.> | <vendor mechanical drawing — for pad-only / mechanical footprints>

**Checks run:**
- <Domain checklist name linked from domain-checklists.md>: N/N items, M issues fixed, K items N/A (with reasons)
- General Gotcha Scrub: N/N items
- `ruff check`: clean | <N issues, fixed>
- `ruff format`: applied
- `pyright`: clean | <N issues, fixed> | not available (<reason>)
- Grep gates (`python <project>/scripts/grep_gates.py <ns>/`): hard-fail 0 hits, review-required <0 | N hits with disposition>

**Interface notes:** <compact — only fields downstream tasks need>
- Ports exposed: <bundle types, e.g. "I2S (out), Power (3V3 in), GPIO (status)">
- Power requirements: <voltage and current draw>
- Constraints needed at top level: <SI constraints to apply, or "none">

**JITX code review (self):** clean | <N> findings | not applicable: single-task tier | not applicable: no JITX Python changed (verify-only task) | not run: <reason — blocking unless user approves>
- CRITICAL: <one-line> — file:line — rule source (e.g., `jitx/SKILL.md` Don'ts, `architectural-patterns.md` § N) — disposition: fix | accept with rationale: <why>
- WARNING: ...
- NOTE: ...

See `jitx-code-review/SKILL.md` for what this pass covers and `jitx-code-review/references/checklist.md` for the pattern taxonomy. The field is **mandatory for complete-board tier task acceptance blocks** (the review runs at Think Twice Step 4 — see `task-execution.md`). For single-task tier, value is `not applicable: single-task tier` unless the user explicitly invoked `jitx-code-review`. For verify-type tasks (no Python written, just `jitx build` and inspection of the build output), use `not applicable: no JITX Python changed`. The field is **scoped to the task acceptance block only** — the Phase 3b audit block uses the four-pass audit instead (see `Phase 3b Design Audit Block` below). CRITICAL or WARNING findings change the combined verdict to `issues-pending` until fixed, downgraded with rationale, or user-approved — same precedence rule as `Outside-voice review (codex)` below.

**Outside-voice review (codex):** clean | <N> findings | not applicable: single-task tier | not applicable: complete-board, task class not in trigger list | not run: <reason — blocking unless user approves on trigger-list tasks>
- CRITICAL: <one-line> — file:line — datasheet p.M fig.N (or "inference") — disposition
- WARNING: ...
- NOTE: ...

See `references/outside-voice-review.md` for trigger list and prompt shape. The field is always present. `not applicable: single-task tier` is the correct value whenever the task is in single-task tier (regardless of task class) — the trigger list only applies to complete-board.

**Verdict (self):** ready-for-review

**Open issues / deferred:** <list, or "none">
```

The orchestrator (or user) then appends the acceptance decision:

```markdown
**Verdict (acceptance):** accept | rework | reject
**Notes:** <if rework or reject: specific issues with file:line references>
```

### Rules for the block

- **No block, not done.** A task without the block is `in-progress`, regardless of build state. "Build clean" alone does not move a task to `review`.
- **`N/A` requires a reason.** Bare `N/A` in any field is rejected on review.
- **Primary source must be ground truth.** A prior project as primary source is a flag — the orchestrator should reject and ask for the datasheet (or user-confirmed exception). Prior projects belong under "Secondary references".
- **Static checks are required where Python was touched.** `ruff check` and `ruff format` always run. `pyright` runs if installed; `not available` requires a reason and may be rejected for high-risk tasks (MCUs, RF, power converters, safety).
- **JITX code review (self) is required for complete-board tier.** A complete-board task acceptance block with `JITX code review (self): not run` defaults to `block`. Bulk dispositions on findings ("all accepted, framework code") without per-line rationale fail review. See `jitx-code-review/SKILL.md`.
- **Verdict (self): ready-for-review** is the only valid sub-agent verdict. Any other value (e.g. `done`, `complete`) means the protocol was not followed.

### Verdict workflow

| Acceptance verdict | Effect |
|--------------------|--------|
| `accept` | Task status `review` → `accepted`. Downstream tasks unblock. |
| `rework` | Task status `review` → `rework`. Sub-agent respawned with the issues list and instructed to fix only those issues. Status becomes `in-progress` on respawn. Maximum 2 rework cycles. |
| `reject` | Task status → `rejected`. Replan: rewrite the task definition, split it, or escalate to user. Update PLAN.md. |

---

## Grep Gate Patterns

The `Grep gates:` line in the task acceptance block reports the result of running `jitx/scripts/grep_gates.py` against the project's source tree. The script is the executable source of truth — copy it into the project's `scripts/` directory. This section summarizes which patterns are checked and why.

> **Note on table display.** The regex patterns below are rendered inside markdown tables, so `|` in alternations is escaped as `\|` for readability. The script in `jitx/scripts/grep_gates.py` carries the exact regexes — read it for the runnable form.

### Hard-fail patterns (must report 0 hits)

A hard-fail hit blocks task acceptance. Fix the underlying code; do not whitelist.

| # | Rule | Pattern (Python `re`-style) | Where checked |
|---|------|------|----|
| 1 | SI / top-level applications outside top-level designs (top-level only — `ReferencePlanes`, `Constrain`, `ConstrainDiffPair`, `ConstrainReferenceDifference` are *applied* in `designs/`, not subcircuits) | `\b(ReferencePlanes\|Constrain\|ConstrainDiffPair\|ConstrainReferenceDifference)\s*\(` | `<ns>/` excluding `<ns>/designs/` |
| 2 | Net symbols outside top-level designs (`GroundSymbol` / `PowerSymbol` are top-level only) | `\b(GroundSymbol\|PowerSymbol)\s*\(` | `<ns>/` excluding `<ns>/designs/` |
| 3 | `setattr(self, ...)` / `getattr(self, ...)` — JITX convention violation (see `jitx/SKILL.md` Don'ts) | `\b(setattr\|getattr)\s*\(\s*self\b` | anywhere in `<ns>/` |
| 4 | Anonymous structural `.insert(...)` (silent-drop pattern 1 — `Resistor(...).insert(...)` instead of `self.r = Resistor(...); self.r.insert(...)`) | `\b(Capacitor\|Resistor\|Inductor)\s*\([^)]*\)\s*\.insert\s*\(` | anywhere in `<ns>/` |
Pattern 1 catches the *call* form, not imports. `from jitx.si import ConstrainDiffPair` is fine; `ConstrainDiffPair(...)` is not (outside top-level designs).

Pattern 4 misses nested constructor args (e.g., `Resistor(resistance=Toleranced.percent(...)).insert(...)`). Not common; treat as a known gap, not a reason to broaden the regex (cost of false positives is too high).

### Review-required patterns (need disposition)

A review-required hit does not block, but each hit must appear in the task acceptance block with a disposition: `accepted with rationale: <why>` | `fixed` | `deferred to Pass 3 (or named follow-up)`. Bare hits without disposition fail acceptance review.

| # | Rule | Pattern | Where checked |
|---|------|---------|----|
| 5 | Module-scope `for` loop — anti-string-hacking theme 9. Module-import-time logic that *might* populate a global table; legitimate uses (dispatch registration, static data generation) exist. Disposition: `fix (move into function)` or `accept (legitimate import-time logic: <reason>)`. See `jitx/SKILL.md` Don'ts and `references/architectural-patterns.md` § "No code at module-import time". | `^for\s+\w+\s+in\s+` | anywhere in `<ns>/` |
| 6 | `Pour(..., isolate=...)` — legacy parameter (Pass 3 deprecates in favor of `design_constraint(...)` with Tags) | `\bPour\s*\([^)]*\bisolate\s*=` | anywhere in `<ns>/` |
| 7 | Bare net/topology expression (silent-drop pattern 2 — `self.a + self.b` or `self.a >> self.b` with no LHS assignment) | `^\s*self\.\w+(\.\w+\|\[[^]]+\])*\s*(\+\|>>)\s*self\.\w+(\.\w+\|\[[^]]+\])*(\s*#.*)?$` | anywhere in `<ns>/` |
| 8 | `type(...)` call — verify not used for runtime type construction (use `isinstance` for type checks) | `\btype\s*\(` | anywhere in `<ns>/` |
| 9 | Tag-like f-string — anti-string-hacking theme 1. f-strings (single- or double-quoted, lowercase or uppercase `f`/`F`) starting with an uppercase letter and building names via brace-substitution (`f"TX_b{i}"`, `f'L{n}_via'`, `F"GND_via_{n}"`) are the canonical string-keyed-name failure mode. See `jitx/SKILL.md` Don'ts and `references/architectural-patterns.md` § "String-keyed dicts → structural objects". Disposition: `fix (use structural object)` or `accept (legitimate use: <reason>)`. | `[fF]["'][A-Z][A-Za-z0-9_]*\{` | anywhere in `<ns>/` |
| 10 | Broader `getattr(` — narrower hard-fail Pattern 3 catches `getattr(self, ...)`. This wider net catches `getattr(other, "...")` where strings are still the indirection mechanism. Most are still smells; legitimate framework uses (e.g., `getattr` on a known-typed external object) are dispositioned per-hit. | `\bgetattr\s*\(` | anywhere in `<ns>/` |
| 11 | I2C pull-up (`r_sda` / `r_scl`) outside top-level designs — flag for review of bus-aggregation level. Pull-ups belong at the level that composes master + slaves on the bus (usually the top-level design; sometimes a subcircuit that encloses an entire private bus). Pull-up local to a single bus participant is the failure mode. Disposition: `accept (bus-aggregation level: <circuit>)` or `fix (move to <level>)`. | `\br_(sda\|scl)\b` | `<ns>/` excluding `<ns>/designs/` |
| 12 | `.insert(...)` calls missing `short_trace=` — every power-rail capacitor insert (decoupling, bypass, bulk, output filter) needs `short_trace=True`. Non-power-rail caps and non-cap inserts dispositioned as exception or N/A. See `jitx-circuit-builder/SKILL.md` "short_trace=True is the default for power-rail capacitors" | `\.insert\s*\(` minus lines containing `short_trace` | anywhere in `<ns>/` |

Pattern 8 is intentionally broad; it will match comments and legitimate `isinstance`-adjacent uses. The disposition workflow handles this — review-required is the right severity.

Pattern 9 catches f-strings that look like they're building tag-style identifiers (`ALL_CAPS` prefix + brace). Legitimate uses (log lines like `f"ERROR_{code}"`) need disposition with rationale. The disposition workflow keeps this from becoming compliance theater.

Pattern 10 (broader `getattr(`) is intentionally a wider net than Pattern 3 (`getattr(self, ...)` hard-fail). It catches string-indirection on other objects (`getattr(self.bga, "TX_b0")`). Bulk dispositions ("all accepted, framework code") fail review — each hit needs a per-line rationale.

### Reporting in the task acceptance block

When the grep gates pass with no hits:

```
- Grep gates (`python scripts/grep_gates.py <ns>/`): hard-fail 0 hits, review-required 0 hits
```

When there are review-required hits:

```
- Grep gates (`python scripts/grep_gates.py <ns>/`): hard-fail 0 hits, review-required 2 hits:
    - <ns>/circuits/usb.py:88 — `Pour(..., isolate=0.15)` — deferred to Pass 3 deprecation
    - <ns>/circuits/power.py:42 — `type(x) is Foo` — fixed: changed to `isinstance(x, Foo)`
```

When there are hard-fail hits, the task is not done. Fix and re-run.

### Project layout override

The script defaults to excluding `**/designs/**` from the top-level-only checks. If a project uses a different convention (e.g. `top/` or `boards/`), set `TOP_LEVEL_PATH` before invocation:

```bash
# bash (macOS / Linux / WSL / Git Bash)
TOP_LEVEL_PATH=top python scripts/grep_gates.py <ns>/
```
```powershell
# PowerShell (Windows) — Remove-Item keeps it one-shot (else it persists for the session)
$env:TOP_LEVEL_PATH="top"; python scripts/grep_gates.py <ns>/; Remove-Item Env:TOP_LEVEL_PATH
```

---

## Phase Exit Gate Blocks (complete-board only)

Each transition between phases emits one block before advancing. Single-task tier does not have phase gates — it uses the task acceptance block only. The block is the gate; an unemitted block means the transition has not happened.

The criteria mirror the exit-gate bullet lists in `references/project-builder-flow.md`. The Phase 3b → Phase 4 gate references the Phase 3b audit block (see "Phase 3b Design Audit Block" below).

### Phase 0 → Phase 1

```markdown
## Gate: Phase 0 → Phase 1

**Environment probe:** all of `jitx`, `jitxlib`, `jitxlib.parts`, `jitxlib.symbols.box`, `jitxlib.voltage_divider` import; target substrate package imports (e.g. `jitxlib.jlcpcb` for JLCPCB). See `jitx/SKILL.md` "Environment Setup".
**Requirements lock complete:** yes — see `decomposition-guide.md` "Requirements Lock" — programming path, UI count, rails, assembly-cost target, RF/module policy, connector UX, fab house all answered in PLAN.md
**PLAN.md exists:** yes — `<path>` (referenced)
**ARCHITECTURE.md exists:** yes — `<path>` (power tree, interface map, voltage domains, board)
**Data source audit completed:** yes — table presented to user, user approved on <date>
**Component-choice rationale documented:** yes — see `parts-sourcing.md` "Component-Choice Rationale Table" — every proposed part has assembly tier, stock, package, fabrication risk, rejected alternatives
**All datasheets and reference materials identified:** <yes | partial — list missing items>
**Dependencies acyclic:** yes (verified by reading PLAN.md task graph)
**No ambiguous requirements:** yes | <list of open questions for user>
**User approval recorded:** yes — <quote or note>

**Verdict:** advance | block (reason: ...)
```

### Phase 1 → Phase 2

```markdown
## Gate: Phase 1 → Phase 2

**Tasks accepted:** <count> / <total in phase>
- Component tasks: <list of task IDs with `accept` verdicts>
- Substrate task: <task ID with verdict, or "predefined — no task needed">

**Build status:** every task's test harness produced `status: ok`

**Spot-check items reviewed:** <list of high-risk items verified per task type — see task-execution.md Part B Step 3>

**Interface notes consistency:** <pass | fail with details — `Interface notes` fields in task acceptance blocks line up with ARCHITECTURE.md power tree and interface map>

**Open from this phase:** <list of issues deferred with rationale, or "none">

**Verdict:** advance | block (reason: ...)
```

### Phase 2 → Phase 3

```markdown
## Gate: Phase 2 → Phase 3

**Tasks accepted:** <count> / <total in phase>

**Build status:** every circuit / constraint / pin-assignment task built `status: ok` individually

**Constraint classes instantiate:** verified via test build of `<task ID>`
**Provide/require interfaces consistent:** confirmed across wrappers and consumers
**Bundle-typed ports:** every interface circuit exposes bundle-typed ports (I2S, I2C, SPI, USB2, etc.) — not individual signal ports — confirmed by code review
**Topology vs net wiring:** subcircuits exposing bundles for SI-constrained signals wire bundle sub-ports with `>>` not `+` — confirmed
**`short_trace=True` on power-rail caps:** every decoupling / bypass / bulk / output-filter capacitor `.insert(...)` uses `short_trace=True`. Non-power-rail caps (AC coupling, RC, RF, crystal load) and non-cap inserts dispositioned in task acceptance blocks. `python scripts/grep_gates.py <ns>/` review-required hits all resolved.
**Power circuit outputs match ARCHITECTURE.md:** voltage and current ratings line up with the documented power tree

**Open from this phase:** <list, or "none">

**Verdict:** advance | block (reason: ...)
```

### Phase 3 → Phase 3b

```markdown
## Gate: Phase 3 → Phase 3b

**Top-level build:** `status: ok` (via `<exact build command>`)

**Net completeness:** all nets connected — no floating ports on instantiated circuits

**Power tree complete:** every load rail connected to a regulator output

**Symbols and constraints:**
- `GroundSymbol` on GND net: yes
- `PowerSymbol` on every power rail: yes
- All SI constraints applied at top level inside `ReferencePlanes(...)`: yes
- All `require()` calls have matching provides: yes

**JITX UI errors:** no "Invalid Topology Definitions" or "No path for signal constraint" issues | <list> | not run because <reason>

**Build warnings:** no `Reference to structural object … lost during instantiation` warnings | <list>

**Grep gates (top-level-only enforcement):** `python scripts/grep_gates.py <ns>/` — hard-fail 0 hits, review-required <count + disposition>

**Passive defaults:** `capacitor_defaults` and `resistor_defaults` set on the Design class to match the manufacturing path and circuit role; per-circuit overrides for specialty parts documented

**Default design rules:** `self.rules` on the Design class contains the four canonical entries — default trace width (`IsTrace`), copper-to-copper clearance (`IsCopper`, `IsCopper`), thermal relief on pads (`IsPad`), and wider trace rule for tagged power/ground rails (`PowerTag | GroundTag`, `priority=1`). Values calibrated to substrate fab class. See `project-builder-flow.md` "Default design rules"

**Board geometry:** shape, mounting holes, pours defined

**Open from this phase:** <list, or "none">

**Verdict:** advance | block (reason: ...)
```

### Phase 3b → Phase 4

```markdown
## Gate: Phase 3b → Phase 4

**Phase 3b audit block emitted:** yes — see audit block below or `<link>`

**CRITICAL findings:** <count> — all fixed and re-audited
**WARNING findings:** <count> — fixed | accepted with rationale (each accept needs the rationale here, not just a count)
**NOTE findings:** <count> — for documentation only

**Loopback tasks completed:** <list of task IDs that came out of the audit, all with `accept` verdicts>

**Re-audit status:** done — no new CRITICAL/WARNING introduced | not needed (no fixes applied)

**Open from this phase:** <list, or "none">

**Verdict:** advance | block (reason: ...)
```

---

## Phase 3b Design Audit Block (complete-board only)

The audit happens in Phase 3b. A read-only audit agent (no code edits) reviews the assembled design across four passes and emits this block. The orchestrator decides which findings to fix; fix sub-agents handle the loopback. After fixes, the audit re-runs and the block is updated (or a new block is emitted alongside the first).

```markdown
## Phase 3b Audit: <project-name>

**Auditor:** <agent name or "manual self-audit">
**Audited from:** <commit hash, or files reviewed at this snapshot>

### Pass 1: Circuit vs Datasheet Application Schematic

| IC | Datasheet figure / page | External components in datasheet | External components in code | Status | Findings |
|----|--------------------------|----------------------------------|-----------------------------|--------|----------|
| <MPN> | Fig N, p.M | <count> | <count> | match | full | partial | <link to finding below> |

Findings (one bullet per CRITICAL / WARNING / NOTE):
- **CRITICAL** <IC>: <one-line description>. Datasheet says X, code does Y. Loopback: <task to create>.
- **WARNING** <IC>: ...
- **NOTE** <IC>: ...

### Pass 2: Assumption Compatibility

For each circuit, list every assumption (input voltage, load current, enable timing, sequencing) and verify against the system. Findings:

- **CRITICAL** ...
- **WARNING** ...
- **NOTE** ...

### Pass 3: Interface-by-Interface Trace

For every interface connecting two or more ICs, trace source → destination through every component. Power rails included.

| Interface | From | To | Hops verified | SI constraint? | Findings |
|-----------|------|----|---------------|----------------|----------|
| USB | mcu.usb | conn.J1 | mcu → ESD → conn | yes (top-level) | none |
| I2C bus 1 | mcu.i2c1 | sensor U3 | direct | n/a | <finding> |

Findings:
- **CRITICAL** ...
- **WARNING** ...
- **NOTE** ...

### Pass 4: Power and Thermal

For every regulator: load sum + margin, thermal dissipation, package rating, hot-plug behavior.

| Rail | Regulator | Sum of loads | Output rating | Margin | Thermal | Findings |
|------|-----------|--------------|---------------|--------|---------|----------|
| 3V3 | LDO U2 | 350 mA | 800 mA | OK | OK | none |
| ... | ... | ... | ... | ... | ... | ... |

Findings:
- **CRITICAL** ...
- **WARNING** ...
- **NOTE** ...

### Outside-Voice Review (codex)

**Required for complete-board.** Run after the four passes above; codex provides an independent perspective from outside the conversation context. See `references/outside-voice-review.md` for invocation, prompt shape, and combined-verdict rule.

```
Outside-voice review (codex): clean | <N> findings | not run: <reason — blocking unless user approves>
- CRITICAL: <one-line> — file:line — datasheet p.M fig.N (or "inference") — disposition: fix → new task `<task-id>` | accept with rationale: <why>
- WARNING: ...
- NOTE: ...
```

Any CRITICAL or WARNING outside-voice finding changes the combined audit verdict to `issues-pending`, even if the four passes above were `clean`.

### Loopback Decisions

| Finding | Severity | Source | Decision | Owner |
|---------|----------|--------|----------|-------|
| <one-line> | CRITICAL | same-model | fix → new task `<task-id>` | <sub-agent> |
| <one-line> | WARNING | outside-voice | fix inline | orchestrator |
| <one-line> | NOTE | same-model | document only | — |
| <one-line> | WARNING | outside-voice | accepted with rationale: <why> | — |

**Re-audit needed:** yes (after fixes land) | no (no fixes)

**Audit verdict (combined):** clean | issues-pending (returns to phase chain after fixes)
```

Severity definitions:

- **CRITICAL** — design is broken (electrical error, missing required component, wrong voltage domain, bus contention, missing SI constraint on a spec-required signal). Must fix before Phase 4.
- **WARNING** — design has a real risk (under-margined power, weak ESD, ambiguous routing intent, missing decoupling). Fix or document an accept-with-rationale.
- **NOTE** — observation worth recording (suboptimal but functional, alternative would be better, future-improvement candidate). Document only; do not block.

Rules:

- Audit agent does not edit files. Findings → orchestrator → fix agents.
- "Noted for future refactoring" is not a valid disposition for CRITICAL or WARNING.
- After any fix lands, re-audit. The re-audit does not need to repeat passes that didn't touch the changed code, but must re-verify the original findings are resolved.

---

## Phase 4 Verification Block (complete-board only)

Final verification before declaring the project done.

```markdown
## Phase 4 Verification: <project-name>

**Final build:** `status: ok` (via `<exact build command — usually `jitx build <ns>.designs.Design`>`)

**Build warnings:** none | <list — every warning needs a disposition>

### JITX UI Verification

For each item: pass | fail with details | not run (with reason)

| Check | Status | Notes |
|-------|--------|-------|
| Schematic readability | pass | all symbols readable, ports labeled |
| Schematic connections | pass | every net visible, no orphans |
| Board placement | pass | components placed (or floating with rationale), no overlaps |
| Issues List | <count> issues | <list, each with disposition> |
| DRC | pass | <or list of violations with disposition> |
| SI constraints | all satisfied | <or list of failures with disposition> |
| Placement overlap | none | <or list> |

If any row is `not run`, give the reason. Common reasons:

- **JITX UI not available** (CI / headless / no display). When this applies, use the build-output checks: parse `cache/netlist.json` for orphan nets, parse `design-info/stable.design` for placement, and the build log for SI/DRC complaints. Note in the row: `not run: headless — checked via netlist.json (no orphans) and build log (no SI errors)`.
- **Tool not installed.** Reason should name what's missing and a follow-up to install.

A row that is `not run` without a reason fails the gate.

### PLAN Reconciliation

- All PLAN.md tasks `accepted`: yes | no — <list of non-accepted tasks>
- All gate blocks emitted (Phase 0→1, 1→2, 2→3, 3→3b, 3b→4): yes | no — <list of missing>
- Phase 3b audit block emitted with `Audit verdict: clean`: yes | no — <details>

### Deferred items

User-approved deferrals only. Each item: description + reason + follow-up plan.

- <item 1>
- <item 2>

### Blocking items

**Must be empty to claim done.** Anything that prevents fabrication, programming, power-up, RF function, or required board geometry is blocking unless the user has explicitly removed it from scope.

- <list — must be empty for verdict: done>

**Verdict:** done | not-yet — open: <list>
```

Rules:

- A `not run` row with no reason fails the gate.
- A `not run` row also requires fallback artifacts: if the JITX UI isn't available, name the build-output files used to substitute for it. Conventional fallbacks:
    - **Schematic / Issues List → `build log`** (cite path; flag any errors/warnings)
    - **Board placement / overlap → `<design-folder>/design-info/stable.design`** (machine-readable; can be inspected for overlap)
    - **Connectivity / orphan nets → `<design-folder>/cache/netlist.json`** (parse for disconnected ports)
    - **DRC / SI → `build log`** (constraint failures and DRC complaints surface in the build output)
  A `not run: headless` row with no fallback artifact named is rejected.
- "Builds clean" alone is never sufficient. The block's other rows must show real verification (or stated absence with reason and fallback).
- Blocking items must be empty. Programming-debug headers, antenna implementations, board-edge geometry, and SI constraints on required interfaces are blocking unless the user explicitly de-scoped them in writing.
- After any rework that touches design code, re-emit the verification block — it doesn't carry over.

---

The block templates are append-only — fields defined here stay as-is.
