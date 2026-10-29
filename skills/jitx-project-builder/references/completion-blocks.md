# Completion Blocks — Mandatory Output Templates

Structured output that any JITX work must emit before claiming "done". The blocks are the artifact — prose summaries are not a substitute. An agent that finishes work without emitting the relevant block has not actually finished.

This file holds:

1. [Workflow Tiers](#workflow-tiers) — which artifacts apply to which size of job.
2. [Task Acceptance Block](#task-acceptance-block) — the per-task completion artifact (universal: every tier requires this).
3. [Grep Gate Patterns](#grep-gate-patterns) — what `jitx/scripts/grep_gates.py` enforces.
4. [Phase Exit Gate Blocks (complete-board only)](#phase-exit-gate-blocks-complete-board-only) — the complete-board tier transitions (Phase 0→1, 1→2, 2→3, 3→3b, 3b→4).
5. [Phase 3b Design Audit Block (complete-board only)](#phase-3b-design-audit-block-complete-board-only) — read-only audit with CRITICAL / WARNING / NOTE classification.
6. [Phase 4 Verification Block (complete-board only)](#phase-4-verification-block-complete-board-only) — final JITX UI / Issues / DRC / SI verification with explicit tool-availability handling.

---

## Where Blocks Live

Emit every mandatory block in chat. Chat is the block's home. Never paste a task acceptance block, phase gate block, Phase 3b audit block, or Phase 4 verification block into PLAN.md.

Record only the resumable outcome in PLAN.md: update the task status after acceptance; add one row to `Gate status` after a gate or final verification; and carry forward any deferred or blocking item that a later phase or resumed session must know. A fresh session reading PLAN.md must be able to identify accepted tasks, passed gates, deferrals, and blockers. Record that state, not the checklist that produced it.

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

`Primary source` names the ground-truth source and exact pages or sections. In complete-board work, cite `datasheets/<MPN>.spec.md` and the PDF pages recorded there. In single-task work, cite the PDF directly. When the user named a sourcing channel for an IC, connector, or other non-passive part, include the saved channel-evidence path required by `parts-sourcing.md`. Prior projects belong under `Secondary references`, never `Primary source`. Bare "datasheet (from memory)" or "typical dimensions" is invalid for a real MPN.

The two review fields are always present. `JITX code review (self)` is mandatory for complete-board tasks, except verify-only tasks with no JITX Python change; see `jitx-code-review/SKILL.md`. For single-task work it is `not applicable: single-task tier` unless the user invoked the review. `Outside-voice review` follows `references/outside-voice-review.md`; its complete-board trigger list does not apply to single-task work. A required outside-voice attempt that produces no output is recorded as `skipped: <reason>`; it carries no findings, and the Phase 3b → 4 gate blocks until the user explicitly approves proceeding without it. CRITICAL or WARNING findings from completed reviews produce `issues-pending` until fixed, downgraded with rationale, or user-approved.

Run `python scripts/check.py <ns>/ --build <module.path.DesignClass>` once from the project root. The `Build` field and the four verification rows report the corresponding summary lines from that invocation. Review-required grep hits retain their per-hit dispositions in the `Grep gates` row.

```markdown
## Task complete: <task-id-or-short-name>

| Field | Value |
|-------|-------|
| What was built | <paths; classes> |
| Build | <command; exact `build` summary line> |
| Primary source | <path; cites; channel evidence> |
| Secondary references | <list/none> |
| Footprint source | <source> |

### Checks run

| Check | Result |
|-------|--------|
| Domain checklist | <name; N/N; M fixed; K N/A + reasons> |
| General Gotcha Scrub | N/N |
| Layout rules | <command; exit; witnessed/unwitnessed> |
| SI measurements | <`ver-` task: `python -m <ns>.designs.check_si_<iface>` command; one quoted group per constraint with a timing, loss or skew target, carrying its Time / Loss / Skew measurement, intended ends, `met` or `NOT MET`, no unresolved text; each structure-only constraint named from its code / any other task: not applicable + reason> |
| Physical realization | <`python scripts/check_realization.py <module.Design> [witness args]`; exit code; authored pours, stitch targets, board-wide pours / not applicable + reason> |
| `ruff check` | <`ruff check` summary line; PASS, or FAIL fixed and re-run> |
| `ruff format` | <`ruff format` summary line; PASS, or reformatted and re-run> |
| `pyright` | <`pyright` summary line; PASS, or FAIL fixed and re-run; ERROR needs a reason> |
| Grep gates | <exact `grep gates` summary line; review-required dispositions> |

### Interface notes

| Field | Value |
|-------|-------|
| Ports exposed | <bundles; directions> |
| Power requirements | <voltage; current> |
| Constraints needed at top level | <list/none> |
| Verification design / assembly constraint parity | <constraint class, parameters, routing structure, Topology ends and pin models compared; verification design: measurements (structure-only: code); assembly: constraint code, plus its `Unconnected Topology on Path:` segment list where the report gives one; match evidence / not applicable + reason> |

### Reviews

| Field | Result |
|-------|--------|
| JITX code review (self) | <result/reason> |
| JITX CRITICAL | <file:line; rule; disposition / none> |
| JITX WARNING | <file:line; rule; disposition / none> |
| JITX NOTE | <file:line; rule / none> |
| Outside-voice review | <reviewer; result/reason> |
| Outside-voice CRITICAL | <file:line; cite/inference; disposition / none> |
| Outside-voice WARNING | <file:line; cite/inference; disposition / none> |
| Outside-voice NOTE | <file:line; cite/inference / none> |

**Verdict (self):** ready-for-review

**Open issues / deferred:** <list/none>
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
- **Static checks are required where Python was touched.** `python scripts/check.py <ns>/` always runs `ruff check`, `ruff format --check`, `pyright`, and the grep gates. Every check reports `PASS`, `FAIL` or `ERROR`, and only `PASS` reaches acceptance. A `FAIL` is fixed and the command re-run, so the block carries the passing line rather than a recorded violation; a `FAIL` line in a submitted block returns the task to `rework`. An `ERROR` means the check did not run, which is not a pass: it blocks acceptance until the tool is available, or the orchestrator records why the environment cannot run it.
- **SI-measurement and physical-realization rows are executable evidence.** SI
  binding is proven on a code-routed verification design, one per constrained
  interface (the paths one constraint spans between the same modules), written
  by that interface's `ver-` task: it places the parts, code-routes each path
  between physical pads (on a pin-assigned port, the
  provider's physical pins), and runs its SI check,
  `python -m <ns>.designs.check_si_<iface>`. It passes when every constraint
  with a timing, loss or skew target shows a quoted Time, Loss or Skew
  measurement from its intended begin pad to its intended end pad, and no group
  for it holds unresolved text.

  A constraint that carries only `.structure(...)`, with no timing, loss or
  skew target, never appears in the report, satisfied or not. It is exempt from
  the measured-line rule and from the absent-from-report rule; its evidence is
  the constraint in code (class, Topology ends, structure), recorded in the
  parity row.

  The shipping assembly carries no proof routes. Sort each of its SI groups by
  whether its constraint's path has copper yet:
  - No route on the path: `Unconnected Topology`, `not routed yet`, `No path
    for signal constraint` with no part named, and `Unassigned Pin` on a
    pin-assigned end are expected and recorded.
  - Any route on the path: the constraint is held to the verification-design
    bar, a measurement between its intended ends with no unresolved text,
    `Missing routing structure` and a placeholder via model included. Those two
    appear only beside a measurement, so they are checked on the verification
    design and on routed paths.
  - Blocking wherever it appears: `No path for signal constraint ... which has
    no pin model`, `Virtual connection without a pin model`, and a constraint
    with a timing, loss or skew target that is absent from the report.

  Compliance is read from the routed assembly's own groups
  (`group.satisfied`); the printed text reads the same met or unmet. A
  verification design's values are proof-route numbers, not the board's.

  The physical row carries the command, exit 0, and the witness names. A
  missing row, a verification design that does not pass, a blocking text, exit
  1, exit 2, or a claimed pass without named witnesses blocks acceptance.
  `not applicable` names the concrete reason no SI constraint or authored
  physical witness exists; it is not a substitute for an unavailable command.
- **JITX code review (self) is required for complete-board tier.** A complete-board task acceptance block with `JITX code review (self): not run` defaults to `block`. Bulk dispositions on findings ("all accepted, framework code") without per-line rationale fail review. See `jitx-code-review/SKILL.md`.
- **Verification design / assembly constraint parity is required at assembly
  acceptance.** Parity compares constraint class, parameters, routing
  structure, Topology ends and pin models between the verification design and
  the assembly. The verification side's evidence is its measurements (for a
  structure-only constraint, its code). The assembly side's is its constraint
  code, plus the `Unconnected Topology on Path:` segment list where the report
  gives one; a pin-assigned end reports `Unassigned Pin`, and an unrouted plain
  chain may report `not routed yet` or a bare `No path`, and then the code
  comparison stands alone. A missing comparison or a mismatch returns the
  assembly task to `rework`. Earlier tasks use `not applicable` with a reason
  because the assembly does not exist yet.
- **Verdict (self): ready-for-review** is the only valid sub-agent verdict. Any other value (e.g. `done`, `complete`) means the protocol was not followed.

### Verdict workflow

| Acceptance verdict | Effect |
|--------------------|--------|
| `accept` | Run `python scripts/plan_status.py <task-id> accepted`. Downstream tasks unblock. |
| `rework` | Run `python scripts/plan_status.py <task-id> rework --note "<issue summary>"`; respawn with the issues; then set `in-progress`. Maximum 2 cycles. |
| `reject` | Run `python scripts/plan_status.py <task-id> rejected --note "<reason>"`; replan, split, or escalate. |

---

## Grep Gate Patterns

The `Grep gates` row in the task acceptance block reports the `grep gates` summary line from `python scripts/check.py <ns>/`. The check entry point runs `jitx/scripts/grep_gates.py --quiet` against the project's source tree. The grep-gate script remains the executable source of truth. This section summarizes which patterns are checked and why.

> **Note on table display.** The regex patterns below are rendered inside markdown tables, so `|` in alternations is escaped as `\|` for readability. The script in `jitx/scripts/grep_gates.py` carries the exact regexes — read it for the runnable form.

### Hard-fail patterns (must report 0 hits)

A hard-fail hit blocks task acceptance. Fix the underlying code; do not whitelist.

| # | Rule | Pattern (Python `re`-style) | Where checked |
|---|------|------|----|
| 1 | SI application outside the conventional top-level directory. The search skips the paths where such a call is a definition or a harness rather than a misplaced application: any `constraints/` directory, `main.py`, and test modules. What remains is an SI constraint applied inside an ordinary subcircuit, which is the failure the rule names. A comment or docstring that spells out the call form in a non-skipped path still trips the regex; reword the prose, since a hard-fail takes no disposition. | `\b(ReferencePlanes\|Constrain\|ConstrainDiffPair\|ConstrainReferenceDifference)\s*\(` | `<ns>/` excluding `<ns>/designs/`, `constraints/`, `main.py`, tests |
| 2 | Net symbols outside top-level designs (`GroundSymbol` / `PowerSymbol` are top-level only) | `\b(GroundSymbol\|PowerSymbol)\s*\(` | `<ns>/` excluding `<ns>/designs/` |
| 3 | `setattr(self, ...)` / `getattr(self, ...)` — JITX convention violation (see `jitx/SKILL.md` Don'ts) | `\b(setattr\|getattr)\s*\(\s*self\b` | anywhere in `<ns>/` |
| 4 | Anonymous structural `.insert(...)` (silent-drop pattern 1 — `Resistor(...).insert(...)` instead of `self.r = Resistor(...); self.r.insert(...)`) | `\b(Capacitor\|Resistor\|Inductor)\s*\([^)]*\)\s*\.insert\s*\(` | anywhere in `<ns>/` |

Pattern 4 misses nested constructor args (e.g., `Resistor(resistance=Toleranced.percent(...)).insert(...)`). Not common; treat as a known gap, not a reason to broaden the regex (cost of false positives is too high).

### Review-required patterns (need disposition)

A review-required hit does not block, but each hit must appear in the task acceptance block with a disposition: `accepted with rationale: <why>` | `fixed` | `deferred to Pass 3 (or named follow-up)`. Bare hits without disposition fail acceptance review.

| # | Rule | Pattern | Where checked |
|---|------|---------|----|
| 5 | Module-scope `for` loop — anti-string-hacking theme 9. Module-import-time logic that *might* populate a global table; legitimate uses (dispatch registration, static data generation) exist. Disposition: `fix (move into function)` or `accept (legitimate import-time logic: <reason>)`. See `jitx/SKILL.md` Don'ts and `jitx/references/architectural-patterns.md` § "No code at module-import time". | `^for\s+\w+\s+in\s+` | anywhere in `<ns>/` |
| 6 | `Pour(..., isolate=...)` — legacy parameter (Pass 3 deprecates in favor of `design_constraint(...)` with Tags) | `\bPour\s*\([^)]*\bisolate\s*=` | anywhere in `<ns>/` |
| 7 | Bare net/topology expression (silent-drop pattern 2: `self.a + self.b`, or the same with the daisy-chain operator, with no LHS assignment) | `^\s*self\.\w+(\.\w+\|\[[^]]+\])*\s*(\+\|>>)\s*self\.\w+(\.\w+\|\[[^]]+\])*(\s*#.*)?$` | anywhere in `<ns>/` |
| 8 | `type(...)` call — verify not used for runtime type construction (use `isinstance` for type checks) | `\btype\s*\(` | anywhere in `<ns>/` |
| 9 | Tag-like f-string — anti-string-hacking theme 1. f-strings (single- or double-quoted, lowercase or uppercase `f`/`F`) starting with an uppercase letter and building names via brace-substitution (`f"TX_b{i}"`, `f'L{n}_via'`, `F"GND_via_{n}"`) are the canonical string-keyed-name failure mode. See `jitx/SKILL.md` Don'ts and `jitx/references/architectural-patterns.md` § "String-keyed dicts → structural objects". Disposition: `fix (use structural object)` or `accept (legitimate use: <reason>)`. | `[fF]["'][A-Z][A-Za-z0-9_]*\{` | anywhere in `<ns>/` |
| 10 | Broader `getattr(` — narrower hard-fail Pattern 3 catches `getattr(self, ...)`. This wider net catches `getattr(other, "...")` where strings are still the indirection mechanism. Most are still smells; legitimate framework uses (e.g., `getattr` on a known-typed external object) are dispositioned per-hit. | `\bgetattr\s*\(` | anywhere in `<ns>/` |
| 11 | I2C pull-up (`r_sda` / `r_scl`) outside top-level designs — flag for review of bus-aggregation level. Pull-ups belong at the level that composes master + slaves on the bus (usually the top-level design; sometimes a subcircuit that encloses an entire private bus). Pull-up local to a single bus participant is the failure mode. Disposition: `accept (bus-aggregation level: <circuit>)` or `fix (move to <level>)`. | `\br_(sda\|scl)\b` | `<ns>/` excluding `<ns>/designs/` |
| 12 | `.insert(...)` calls missing `short_trace=` — every power-rail capacitor insert (decoupling, bypass, bulk, output filter) needs `short_trace=True`. Non-power-rail caps and non-cap inserts dispositioned as exception or N/A. See `jitx-circuit-builder/SKILL.md` "short_trace=True is the default for power-rail capacitors" | `\.insert\s*\(` minus lines containing `short_trace` | anywhere in `<ns>/` |

Pattern 8 is intentionally broad; it will match comments and legitimate `isinstance`-adjacent uses. The disposition workflow handles this — review-required is the right severity.

Pattern 1 skips `constraints/` directories, `main.py`, and test modules
(`test_*.py`, `*_test.py`, `tests/`) because the prescribed layout puts SI
constraint definitions, the seeded top-level design, and test harnesses there.
It also skips `<ns>/designs/`, where SI verification designs
(`verify_<iface>.py`) apply their constraints. A hit anywhere else is an SI
constraint applied inside an ordinary subcircuit and blocks acceptance.

Pattern 9 catches f-strings that look like they're building tag-style identifiers (`ALL_CAPS` prefix + brace). Legitimate uses (log lines like `f"ERROR_{code}"`) need disposition with rationale. The disposition workflow keeps this from becoming compliance theater.

Pattern 10 (broader `getattr(`) is intentionally a wider net than Pattern 3 (`getattr(self, ...)` hard-fail). It catches string-indirection on other objects (`getattr(self.bga, "TX_b0")`). Bulk dispositions ("all accepted, framework code") fail review — each hit needs a per-line rationale.

### Reporting in the task acceptance block

When the grep gates pass with no hits:

```
| Grep gates | `grep gates     PASS   0 hard-fail, 0 review-required` |
```

When there are review-required hits:

```
| Grep gates | `grep gates     PASS   0 hard-fail, 2 review-required`; `<ns>/circuits/usb.py:88`, deferred to Pass 3; `<ns>/circuits/power.py:42`, fixed with `isinstance` |
```

When there are hard-fail hits, the task is not done. Fix and re-run.

### Project layout override

The script defaults to excluding `**/designs/**` from the top-level-only checks. If a project uses a different convention (e.g. `top/` or `boards/`), set `TOP_LEVEL_PATH` before invocation:

```bash
# bash (macOS / Linux / WSL / Git Bash)
TOP_LEVEL_PATH=top python scripts/check.py <ns>/
```
```powershell
# PowerShell (Windows) — Remove-Item keeps it one-shot (else it persists for the session)
$env:TOP_LEVEL_PATH="top"; python scripts/check.py <ns>/; Remove-Item Env:TOP_LEVEL_PATH
```

---

## Phase Exit Gate Blocks (complete-board only)

Each transition between phases emits one block before advancing. Single-task tier does not have phase gates — it uses the task acceptance block only. The block is the gate; an unemitted block means the transition has not happened.

The criteria mirror the exit-gate bullet lists in `references/project-builder-flow.md`. The Phase 3b → Phase 4 gate references the Phase 3b audit block (see [Phase 3b Design Audit Block (complete-board only)](#phase-3b-design-audit-block-complete-board-only)).

### Phase 0 → Phase 1

```markdown
## Gate: Phase 0 → Phase 1

| Field | Result |
|-------|--------|
| Environment probe | <all of `jitx`, `jitxlib`, `jitxlib.parts`, `jitxlib.symbols.box` import; target substrate package (e.g. `jitxlib.jlcpcb`) imports; `jitx --version` and `jitx runtime introspect` report the same major.minor; result> |
| Requirements lock complete | <result; assumptions> |
| PLAN.md exists | <path> |
| ARCHITECTURE.md exists | <path; sections> |
| No fact copied between documents | <N checked; name the specific pairs compared; duplication counts at the sentence level, not the section level; clean, or each copy and its owner> |
| Support circuitry owned | <part -> task, per powered part, from each application circuit; or "none needed, per <datasheet section>"> |
| Task status reconciles with open questions | <N questions checked against task Data, Verify, and dependencies, including transitive blockers; all statuses reconcile, or each missing, stale, or incorrect blocked status> |
| Planning docs within budget | <line counts; result> |
| Data source audit completed | <approval; date> |
| Component-choice rationale documented | <result; PLAN.md location> |
| All datasheets and reference materials identified | <result> |
| Dependencies acyclic | <result> |
| No ambiguous requirements | <result/questions> |
| User approval recorded | <evidence> |
| Verdict | <advance/block + reason> |
```

Any remaining duplicated fact or missing, stale, or incorrect blocked status requires
`Verdict: block`. Listing discrepancies is not resolution; fix them and recheck before
advancing. Derive affected tasks from the unresolved questions and task inputs and
dependencies, not solely from existing statuses (`plan-template.md` owns the status rule).

The `jitxlib` namespace is split across distributions and installing `jitx` brings none of them; a failing environment probe is almost always a missing `jitxlib-standard` / `jitxlib-parts`, which is an install to do, not a module to work around. See `jitx/SKILL.md` "Install".

### Phase 1 → Phase 2

```markdown
## Gate: Phase 1 → Phase 2

**Dispatch:** <N> Phase 1 tasks in <B> spawn batches, max <C> concurrent (C is the
number of sub-agents running at the same time in the widest batch). For `N >= 3`,
`B == N` fails and so does `C < 3`, unless each serialized task names the dependency
that forced it; recording two batches that each run one task at a time is serial
work with a batch count on it.

| Field | Result |
|-------|--------|
| Tasks accepted | <count/total> |
| Component tasks | <IDs; verdicts> |
| Substrate task | <ID; verdict> |
| Build status | <result> |
| Spot-check items reviewed | <list> |
| Interface notes consistency | <result/details> |
| Grep gates | <exact `grep gates` summary line; dispositions> |
| Open from this phase | <list/none> |
| Verdict | <advance/block + reason> |
```

### Phase 2 → Phase 3

```markdown
## Gate: Phase 2 → Phase 3

| Field | Result |
|-------|--------|
| Tasks accepted | <count/total> |
| Build status | <result> |
| Constraint classes instantiate | <evidence> |
| Provide/require interfaces consistent | <result> |
| Bundle-typed ports | <result> |
| Constrained-path wiring and pin models | <plain `+` nets on constrained paths; a `BridgingPinModel` on every pass-through part; result> |
| SI verification designs | <per constrained interface: `ver-` task id, `<ns>/designs/verify_<iface>.py`, verdict; every interface with an SI constraint has an accepted one / not applicable + reason> |
| `short_trace=True` on power-rail caps | <result; dispositions> |
| Power circuit outputs match ARCHITECTURE.md | <result> |
| Open from this phase | <list/none> |
| Verdict | <advance/block + reason> |
```

### Phase 3 → Phase 3b

```markdown
## Gate: Phase 3 → Phase 3b

| Field | Result |
|-------|--------|
| Top-level build | <status; command> |
| Net completeness | <result> |
| Power tree complete | <result> |
| Symbols and constraints | <result> |
| `GroundSymbol` on GND | <result> |
| `PowerSymbol` on each rail | <result> |
| SI constraints at top level in `ReferencePlanes(...)` | <result> |
| Verification design / assembly constraint parity | <per constraint: class, parameters, routing structure, Topology ends and pin models, verification design vs assembly code; segment list where the report gives one; result> |
| SI design issues dispositioned | <assembly `python -m <ns>.designs.check_si_main` command; each SI group dispositioned expected (path has no route), measured (routed path), or blocking; blocking list empty> |
| `require()` calls have matching provides | <result> |
| JITX UI errors | <result/reason> |
| Build warnings | <result> |
| Grep gates, top-level enforcement | <exact `grep gates` summary line; dispositions> |
| Passive defaults | <result; overrides> |
| Default design rules | <four-rule result> |
| Board geometry | <result> |
| Open from this phase | <list/none> |
| Verdict | <advance/block + reason> |
```

### Phase 3b → Phase 4

```markdown
## Gate: Phase 3b → Phase 4

| Field | Result |
|-------|--------|
| Phase 3b audit block emitted | <block/link> |
| Outside-voice review | <reviewer; N attempted; M completed; K skipped + reasons; if K > 0, the user's approval to proceed quoted, else Verdict is block> |
| CRITICAL findings | <count; result> |
| WARNING findings | <count; dispositions> |
| NOTE findings | <count> |
| Loopback tasks completed | <IDs; verdicts> |
| Re-audit status | <result/reason> |
| Open from this phase | <list/none> |
| Verdict | <advance/block + reason> |
```

---

## Phase 3b Design Audit Block (complete-board only)

The audit happens in Phase 3b. A read-only audit agent (no design-code edits) reviews the assembled design across four passes and emits this block. It reads the datasheet PDFs, not the spec notes (CD-1). The orchestrator decides which findings to fix; fix sub-agents handle the loopback. After fixes, the audit re-runs and the block is updated (or a new block is emitted alongside the first).

The four pass scopes remain those in `references/project-builder-flow.md`: application-circuit external parts and values; every circuit assumption against the system; every interface path including power; and every regulator's load margin, thermal/package limit, and hot-plug behavior.

The bounded outside-voice fan-out is a required attempt for complete-board work and follows `references/outside-voice-review.md`. Any CRITICAL or WARNING finding from a completed outside-voice pass makes the combined verdict `issues-pending`, even when the four passes are clean. A pass with no output is recorded as `skipped: <reason>`; it carries no findings, and the Phase 3b → 4 gate blocks until the user explicitly approves proceeding without it.

```markdown
## Phase 3b Audit: <project-name>

**Auditor:** <name>
**Audited from:** <commit/files>

### Pass 1: Circuit vs Datasheet Application Schematic

| IC | Datasheet page/figure | Datasheet externals | Code externals | Status | Findings |
|----|-----------|---------------------|----------------|--------|----------|
| <MPN> | <page> | <N> | <N> | <status> | <IDs/none> |

### Pass 2: Assumption Compatibility

| Circuit | Assumption | System evidence | Status | Finding ID |
|---------|------------|-----------------|--------|------------|
| <name> | <assumption> | <source> | <status> | <ID/none> |

### Pass 3: Interface-by-Interface Trace

| Interface | From | To | Hops verified | SI constraint? | Findings |
|-----------|------|----|---------------|----------------|----------|
| <name> | <source> | <destination> | <hops> | <result> | <ID/none> |

### Pass 4: Power and Thermal

| Rail | Regulator | Load sum | Rating | Margin | Thermal/package | Hot-plug | Finding ID |
|------|-----------|----------|--------|--------|-----------------|----------|------------|
| <rail> | <part> | <load> | <rating> | <margin> | <result> | <result> | <ID/none> |

### Outside-Voice Review

**Outside-voice review:** <reviewer; N attempted; M completed; K skipped + reasons; completed-pass result>

### Findings and Loopback Decisions

| ID | Pass/source | Severity | Finding + evidence | Decision | Owner |
|----|-------------|----------|--------------------|----------|-------|
| <ID> | <pass/source> | <severity> | <finding; evidence> | <decision> | <owner> |

**Re-audit needed:** <yes/no + reason>

**Audit verdict (combined):** <clean/issues-pending>
```

Severity definitions:

- **CRITICAL** — design is broken (electrical error, missing required component, wrong voltage domain, bus contention, missing SI constraint on a spec-required signal). Must fix before Phase 4.
- **WARNING** — design has a real risk (under-margined power, weak ESD, ambiguous routing intent, missing decoupling). Fix or document an accept-with-rationale.
- **NOTE** — observation worth recording (suboptimal but functional, alternative would be better, future-improvement candidate). Document only; do not block.

Rules:

- Audit agent edits nothing, including the datasheet spec notes. A note that disagrees with the datasheet is a finding like any other. Findings → orchestrator → fix agents → re-audit.
- "Noted for future refactoring" is not a valid disposition for CRITICAL or WARNING.
- After any fix lands, re-audit. The re-audit does not need to repeat passes that didn't touch the changed code, but must re-verify the original findings are resolved.

---

## Phase 4 Verification Block (complete-board only)

Final verification before declaring the project done.

```markdown
## Phase 4 Verification: <project-name>

**Parts gate (run first):** <`ideal` removed from `[tool.jitx.parts] chain`; exact `jitx build <design>` status line; exact `jitx design export parts-check <design> --fail all` summary line, exit 0. A design left on `IDEAL-` parts is a user-approved deferral, listed below>

**Verification command:** `python scripts/check.py <ns>/ --build <ns>.main.Design`

**Check summary:** <the four check summary lines from `python scripts/check.py` (ruff check, ruff format, pyright, grep gates)>

**Final build:** <exact `build` summary line>

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
| SI constraints | all satisfied | <compliance from the routed assembly's own groups (`group.satisfied`; the measurement is binding evidence, not the verdict), or list of failures with disposition; verification-design values are proof-route numbers and do not stand in; a constraint whose path has no route reads `not measured: unrouted; see SI constraint binding` and gets the `SI compliance pending routing` Deferred item> |
| SI constraint binding | measured / not applicable | <each verification design: exact `python -m <ns>.designs.check_si_<iface>` command and one quoted group per constraint with a timing, loss or skew target, with its measurement (structure-only: named from code); assembly: command and each SI group dispositioned / concrete reason no SI constraint is expected> |
| Placement overlap | none | <or list> |
| Physical realization | exit 0 | <exact `check_realization.py` command; authored pour names; stitch targets; board-wide pours> |

If any row is `not run`, give the reason. Common reasons:

- **JITX UI not available** (CI / headless / no display). When this applies, use the build-output checks: parse `cache/netlist.json` for orphan nets, parse `design-info/stable.design` for placement, the build log for DRC complaints, and `python -m <ns>.designs.check_si_main` for SI. Note in the row: `not run: headless; checked via netlist.json (no orphans), build log, and the SI check script (SI groups dispositioned)`.
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
- When SI constraints are expected, the SI constraint-binding row is blocking.
  Phase 4 runs the SI check on each verification design and on the assembly
  and applies the SI rule in [Rules for the block](#rules-for-the-block):
  structure-only constraints exempt from the measured-line and
  absent-from-report rules, unrouted texts expected only on a constraint whose
  path has no route, a routed constraint held to the verification-design bar.
  Absence, `not run`, a verification design that does not pass, or an assembly
  constraint below the bar for its routing state makes the verdict `not-yet`.
  Rerun the commands after final rework that changes routing, a pin model, or
  an SI constraint.
- An assembly constraint whose path has no route has binding evidence from
  its verification design but no compliance measurement. The `SI constraints`
  row reads `not measured: unrouted` for it, and the row passes only with the
  Deferred item `SI compliance pending routing: rerun python -m
  <ns>.designs.check_si_main after routing`, shown to the user with the
  verdict. Without that item the verdict is `not-yet`.
- The Physical realization row is blocking. Absence, `not run`, exit 1, or exit
  2 makes the verdict `not-yet`; a clean build does not substitute for it.
- A `not run` row also requires fallback artifacts: if the JITX UI isn't available, name the build-output files used to substitute for it. Conventional fallbacks:
    - **Schematic / Issues List → `build log`** (cite path; flag any errors/warnings)
    - **Board placement / overlap → `<design-folder>/design-info/stable.design`** (machine-readable; can be inspected for overlap)
    - **Connectivity / orphan nets → `<design-folder>/cache/netlist.json`** (parse for disconnected ports)
    - **DRC → `build log`** (DRC complaints surface in the build output)
    - **SI → `python -m <ns>.designs.check_si_main`** (measured and unresolved SI groups)
  A `not run: headless` row with no fallback artifact named is rejected.
- "Builds clean" alone is never sufficient. The block's other rows must show real verification (or stated absence with reason and fallback).
- Blocking items must be empty. Programming-debug headers, antenna implementations, board-edge geometry, and SI constraints on required interfaces are blocking unless the user explicitly de-scoped them in writing.
- After any rework that touches design code, re-emit the verification block — it doesn't carry over.

---

The block templates are append-only — fields defined here stay as-is.
