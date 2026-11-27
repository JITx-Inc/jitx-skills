# Completion Blocks

## Where blocks live

Emit every block in chat. Never paste a task acceptance block, phase gate block, Phase 3b audit block or Phase 4 verification block into PLAN.md: it takes the task status, one `Gate status` row per gate and for Phase 4, and each deferred or blocking item a later session needs.

An empty field reads `none` or `not applicable: <reason>`; a bare `N/A` fails review.

## Task Acceptance Block

The sub-agent fills it; the orchestrator, or the user in single-task work, appends the verdict.

```markdown
## Task complete: <task-id>

| Field | Value |
|-------|-------|
| What was built | <paths; classes> |
| Primary source | <datasheet, vendor reference design or drawing, or protocol spec, with pages; complete-board: `datasheets/<MPN>.spec.md` and its PDF pages; saved channel evidence when the user named a channel> |
| Secondary references | <prior projects, other sources; `searched: ...` / none> |
| Footprint source | <generator, or KiCad import and why / not applicable: <reason>> |

### Checks run

| Check | Result |
|-------|--------|
| check.py | <summary lines of `python scripts/check.py <ns>/ --build <module.path.DesignClass>` as printed; each review-required grep hit, file:line, disposition> |
| Checks | <each checklist: N/N, items fixed, not-applicable items with reasons; a sub-skill's check block (the component check) in full> |

### Interface notes

| Field | Value |
|-------|-------|
| Ports exposed | <bundles; directions> |
| Power requirements | <voltage; current> |
| Constraints needed at top level | <list / none> |

### Reviews

| Field | Result |
|-------|--------|
| JITX code review (self) | <severity counts; each finding: file:line, rule, disposition / not run: <reason> / not applicable: single-task tier> |
| Outside-voice review | <reviewer; output file; each finding: file:line, page or `inference`, severity, disposition / skipped: <reason> / not applicable: <reason>> |

**Open issues / deferred:** <list / none>
```

The orchestrator appends:

```markdown
**Verdict (acceptance):** accept | rework | reject
**Notes:** <for rework or reject: each issue with file:line>
```

Added under `Checks run` by task type:

- `si-verification`, row `SI measurements`: the `python -m <ns>.designs.check_si_<iface>` command; per constraint with a timing, loss or skew target, one quoted group with its Time, Loss or Skew, intended ends, `met` or `NOT MET`; each structure-only constraint named from its code.
- `assembly`, row `Design rules`: each rule on the Design with its value, source and the need it holds, or `no board defaults` with the lock row quoted, or `no classes of nets: <reason>`; the layout check's command and exit code; each rule witnessed in captured copper, or named unwitnessed with the reason.
- `assembly`, row `Physical realization`: `python -m <ns>.designs.check_layout_main`, exit code, witnesses named (authored pours, stitch targets, board-wide pours); not applicable without pours, stitching or code-placed copper.
- `assembly`, row `Parity`: per SI constraint, class, parameters, routing structure, Topology ends and pin models, verification design against assembly, with the evidence [SI verification designs](project-builder-flow.md#si-verification-designs) names.

Acceptance blocks on: a `FAIL` line; an `ERROR` line, unless the block records why the check could not run; a prior project, memory or "typical dimensions" as a real MPN's `Primary source`; a missing type row, nonzero exit or unnamed witness; a bulk disposition. In complete-board work, also on `JITX code review (self): not run` without the user's approval quoted, and on a CRITICAL or WARNING in either Reviews row not settled as [Precedence and combined verdict](outside-voice-review.md#precedence-and-combined-verdict) sets out.

## Grep Gate Patterns

`check.py` runs `grep_gates.py --quiet`, which prints each hit under its label.

A hard-fail hit blocks acceptance and takes no disposition:

- `SI/top-level applications outside designs/`: checked in `<ns>/` except `designs/`, `constraints/`, `main.py` and tests. A comment spelling out the call trips it: reword it.
- `Net symbols (GroundSymbol/PowerSymbol) outside designs/`: checked in `<ns>/` except `designs/` and `main.py`.
- `setattr/getattr on self (JITX convention)`: checked everywhere.

Each review-required hit gets `fix`, `accept: <reason>` or `deferred: <named follow-up>`. Accept only:

- `Module-scope for-loop — review for module-import-time logic`: dispatch registration or static data generation.
- `Pour(..., isolate=...) — legacy parameter`: never; use `design_constraint(...)` with tags.
- `Bare net/topology expression — silent-drop pattern`: never; assign it to `self.<name>`.
- `type(...) call — verify not used for runtime type construction`: no type built at runtime.
- `Tag-like f-string (anti-string-hacking — string-keyed names)`: no name a structural object should hold, such as a log string.
- `getattr( — review for string-keyed indirection on non-self objects`: a framework call on a known-typed object.
- `I2C pull-up (r_sda/r_scl) outside designs/ — review bus-aggregation level`: the circuit composes the whole bus (`jitx-circuit-builder`); name it.
- `Capacitor(...) call sites outnumber ShortTrace(...) call sites in a file (power-rail cap rule)`: a cap off the power rails (AC coupling, timing, compensation, RF matching).

## Phase Exit Gate Blocks (complete-board only)

Each gate emits, before the phase advances:

```markdown
## Gate: Phase <a> → Phase <b>

| Criterion | Result |
|-----------|--------|
| <each criterion below> | <evidence> |
| Open from this phase | <list / none> |
| Verdict | advance / block: <reason> |
```

A failing criterion makes the verdict `block`. Listing a discrepancy is not resolving it: fix and recheck.

### Phase 0 → Phase 1

- Environment probe: `jitx`, `jitxlib`, `jitxlib.parts`, `jitxlib.symbols.box` and, once a fab is chosen, its substrate package import; `jitx --version` and `jitx runtime introspect` share major.minor.
- Requirements lock: every row settled or an open question. With no fab named, fab house, assembly tier and parts channel are open in one question, their tasks blocked, never assumed.
- No fact copied between documents: the pairs compared named; a sentence repeated in a second document is a copy, removed.
- Support circuitry owned: each powered part maps to the task building its application circuit, or "none needed, per <datasheet section>".
- Task status reconciles with open questions, checked as `plan-template.md` "Tasks" sets out.
- Data sources: each component has a datasheet and footprint source; the user's approval of the data source plan quoted and dated.
- Plan approval: the user's approval of PLAN.md and ARCHITECTURE.md quoted and dated.
- Approved-parts list: the user's CSV or database, or the `jitxexamples` stand-in, told to the user and recorded in `Data Sources`.
- Component choice: the rationale table shown in chat; one `Chosen over` line per part in `Data Sources`.
- Dependencies acyclic.
- No ambiguous requirements: each ambiguity is an open question.

### Phase 1 → Phase 2

- Dispatch: N tasks in B spawn batches, at most C concurrent. For N ≥ 3, B = N or C < 3 fails unless each serialized task names the dependency that forced it.
- Tasks accepted: every Phase 1 task, by ID.
- check.py: `python scripts/check.py <ns>/` all `PASS`, grep hits dispositioned.
- Interface notes: port names and power requirements match ARCHITECTURE.md.

### Phase 2 → Phase 3

- Tasks accepted: every Phase 2 task, by ID.
- Interfaces: bundle-typed ports on every circuit; provide and require names and bundle types match.
- No silent drops: every passive on `self`; no bare `+` in a subcircuit.
- Constrained paths: plain `+` nets; a `BridgingPinModel` on every part a path crosses, none on a flow-through package whose opposite pin is n.c.
- SI verification designs: an accepted `ver-` task per constrained interface.
- Power-rail caps: each has its `ShortTrace`; other caps dispositioned.
- Power outputs: each power circuit's voltage and current match `Power Tree`.

### Phase 3 → Phase 3b

- check.py: `python scripts/check.py <ns>/ --build <module.path.DesignClass>` on the top-level design all `PASS`, grep hits dispositioned.
- Build warnings: no `Reference to structural object … lost during instantiation`.
- Net completeness: no floating port on an instantiated circuit; each rail reaches every load.
- Net symbols: `GroundSymbol` on GND, `PowerSymbol` on each rail.
- SI constraints: applied in the top-level design inside `ReferencePlanes(...)`.
- Parity: the assembly block's row matches for every constraint.
- SI design issues: `python -m <ns>.designs.check_si_main` run; each group sorted expected, measured or blocking; nothing blocking.
- `require()`: each call has a matching provide.
- JITX UI errors: none, or each dispositioned.
- Passives: each passive the build resolved has a case and mounting the lock's assembly tier accepts (`project-builder-flow.md` Phase 3 step 6).
- Default design rules: every value on the Design sourced and at or above the substrate's fab floors; default width and clearance are the lock row's, or the lower clearance the coplanar cap sets, cited to its structure.
- Board geometry: shape, mounting holes and pours match the requirements.

### Phase 3b → Phase 4

- Audit: the latest audit block reads `Audit verdict (combined): clean`.
- Outside-voice review: attempted, completed and skipped counts, covered tasks cited; each skip carries the user's approval, quoted.
- Loopback: every fix task accepted and in PLAN.md.
- Re-audit: run on the files the fixes changed, or no fixes.
- SI constraints: each high-speed interface constrained in the assembly, each constraint at the bar for its routing state, its verification design passing.

## Phase 3b Design Audit Block (complete-board only)

```markdown
## Phase 3b Audit: <project-name>

**Audited from:** <commit or files>

### Pass 1: Circuit vs Datasheet Application Schematic

| IC | Datasheet page/figure | Datasheet externals | Code externals | Status | Findings |
|----|-----------|---------------------|----------------|--------|----------|

### Pass 2: Assumption Compatibility

| Circuit | Assumption | System evidence | Status | Finding ID |
|---------|------------|-----------------|--------|------------|

### Pass 3: Interface-by-Interface Trace

| Interface | From | To | Hops verified | SI constraint? | Findings |
|-----------|------|----|---------------|----------------|----------|

### Pass 4: Power and Thermal

| Rail | Regulator | Load sum | Rating | Margin | Thermal/package | Hot-plug | Finding ID |
|------|-----------|----------|--------|--------|-----------------|----------|------------|

**Outside-voice review:** <reviewer; N attempted; M completed; K skipped with reasons; covered tasks cited>

### Findings and Loopback Decisions

| ID | Pass/source | Severity | Finding + evidence | Decision | Owner |
|----|-------------|----------|--------------------|----------|-------|

**Re-audit needed:** <yes/no + reason>

**Audit verdict (combined):** <clean/issues-pending>
```

Severity: CRITICAL, the design is broken (electrical error, missing required part, wrong voltage domain, bus contention, no SI constraint on a spec-required signal); WARNING, a real risk (thin power margin, weak ESD, ambiguous routing intent, missing decoupling); NOTE, works but could be better. What each requires: [Precedence and combined verdict](outside-voice-review.md#precedence-and-combined-verdict).

## Phase 4 Verification Block (complete-board only)

```markdown
## Phase 4 Verification: <project-name>

**Parts gate:** <`jitx build <design>` status line; `jitx design export parts-check <design> --fail all` summary line, exit 0; last line of `python <jitx skill>/scripts/prune_lock.py <design> [--exclude <test design> ...] --check`, exit 0; every MPN the final build resolved, none `IDEAL-` unless the user approved leaving it (then a Deferred item), each with the user's approval quoted when `Data Sources` records the stand-in>

**check.py:** <summary lines of `python scripts/check.py <ns>/ --build <module.path.DesignClass>`>

**Build warnings:** none | <each with its disposition>

| Check | Status | Notes |
|-------|--------|-------|
| Schematic | <pass/fail/not run> | <nets connected, symbols readable> |
| Board placement | <pass/fail/not run> | <placed, or floating with reason; no overlaps> |
| Issues List | <count> | <each with its disposition> |
| DRC | <pass/fail/not run> | <each violation with its disposition> |
| SI constraints | <all satisfied / failures> | <the routed assembly's `group.satisfied`, never a verification design's numbers; unrouted: `not measured: unrouted`> |
| SI constraint binding | <measured / not applicable> | <each `check_si_<iface>` command, one quoted group per targeted constraint; the assembly's command, each group dispositioned / why no SI constraint is expected> |
| Physical realization | <exit code> | <`python -m <ns>.designs.check_layout_main`; witnesses> |

### PLAN Reconciliation

- All tasks `accepted`: yes | no: <tasks>
- All five gate blocks emitted: yes | no: <missing>
- Latest audit verdict `clean`: yes | no: <details>

### Deferred items

- <item; source; reason; follow-up>

### Blocking items

- <list>

**Verdict:** done | not-yet: <open items>
```

Rules:

- `done` needs an empty blocking list. Whatever prevents fabrication, programming, power-up, RF function or required board geometry blocks, programming headers, antennas, board edge and required SI constraints included, unless the user de-scoped it in writing. Every other deferral needs the user's approval.
- With SI constraints expected, a missing binding row, `not run`, a failing verification design or an assembly constraint below the bar for its routing state makes the verdict `not-yet`. Rerun the SI checks after rework that changes routing, a pin model or an SI constraint.
- A `not measured: unrouted` constraint passes only with the Deferred item `SI compliance pending routing: rerun python -m <ns>.designs.check_si_main after routing`, shown to the user with the verdict.
- A finding deferred to place and route, from a task review or the audit, is a Deferred item with its source, shown to the user with the verdict as a requirement on place and route (`jitx-interactive-layout`). It needs no approval and does not make the verdict `not-yet`.
- A missing physical-realization row, `not run` or a nonzero exit makes the verdict `not-yet`.
- A `not run` row names its reason and the artifact read instead, or it fails. Headless: schematic, Issues List and DRC from the build log; placement and overlap from `<design-folder>/design-info/stable.design`; connectivity from quoted test output (`jitx-circuit-builder`, "Asserting connectivity in tests"), since `cache/design-explorer.json` is no netlist; SI from `check_si_main`.
