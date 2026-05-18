---
name: jitx-port-3-to-4
description: This skill should be used when the user asks to port, migrate, or convert a JITX 3.x (LB Stanza) PCB design to JITX 4.x (Python) — including translating `pcb-module`/`pcb-component`/`defpackage` to Python `Circuit`/`Component`/modules, rewriting nets and topology, mapping `stanza.proj`/`main.stanza` build entry points to `pyproject.toml`/`python -m jitx build`, and updating `nightly_design_tests` style configs to `jitx-test` style integration. Triggers on phrases like "port to 4.x", "migrate from Stanza", "convert .stanza design to Python", "Stanza→Python", "rewrite this pcb-module in Python", or when the user has both `.stanza` source and a Python target. Also activates when the user asks to **plan** a port rather than execute one — phrases like "plan a port", "plan to migrate", "make a plan to convert", "design a Stanza→Python migration", or any plan-mode request that names a `.stanza` design as the source.
---

# JITX Port 3.x → 4.x Skill

Help port JITX 3.x (LB Stanza) PCB designs to JITX 4.x (Python).

This skill is a **router**, not a full tutorial. It does not re-teach Stanza or the Python 4.x API — it points to the existing skills that do, and supplies the construct mappings, workflow, pitfalls, and verification recipe that are unique to the porting task.

## Port plan checklist — every plan must include all five

A port plan that omits any of these is incomplete, regardless of how thorough the porting steps look:

1. **Phase 0 pre-verify** — build the 3.x source at the target commit with `~/.jitx/<3.x>/jitx run main.stanza` BEFORE creating the port branch. No pre-verify → a 4.x failure cannot be distinguished from a broken baseline.
2. **`~/.jitx/current` alternation** — symlink repointed between every 3.x ↔ 4.x build (see ⚠️ CRITICAL section below).
3. **Baseline capture** — 3.x exports (BOM, schematic, board) preserved outside the working tree so they survive `git clean -fdx` on the branch switch.
4. **4.x build smoke** — `python -m jitx build <pkg>.<mod>.<DesignClass>` exits 0 AND `pyright` is clean modulo the documented `Part(mpn=…).<port>` exception in `jitx-skills:jitx-component-modeler` §"pyright caveat" (those attribute-access errors come from runtime parts-DB ports that pyright cannot know — filter them, treat all others as blocking).
5. **Export compare** — general six-section export-verification checklist at [`jitx-skills:jitx/references/export-verification.md`](../jitx/references/export-verification.md) (A net inventory through F control signals) plus port-only B′ / E′ in `references/verification.md` (not just `status: ok`).

If you're writing a plan and any of these is missing, the plan is not done.

## Mental Model

Three facts drive the whole port:

1. **JITX 3.x is the Stanza line; JITX 4.x is the Python line.** 4.x introduced the Python workflow and is Python-only going forward — some Stanza designs may still happen to compile under 4.x, but Stanza is not a supported target for 4.x. The supported migration path is 3.x Stanza → 4.x Python.
2. **The languages differ but the JITX object model is similar.** A Stanza `pcb-module` is a Python `Circuit` subclass; a Stanza `pcb-component` is a Python `Component` subclass; `pcb-stackup` is `Stackup`; nets connect via `+`; topology connects via `>>`. Most ports are mechanical at the structural level once the mapping is internalized.
3. **The build/CI shell differs.** Stanza designs are launched from `main.stanza` + `design_name` (per `nightly_design_tests/config/designs.yaml`). Python designs use `python -m jitx build <package>.<module>.<DesignClass>` against a `jitx interactive` server (per `jitx-test/.github/workflows/integration-testing.yml`). The CI matrix shape changes accordingly.

**Note on Stanza:** Stanza compiles natively (via a C backend). It has no JVM target. Never describe Stanza as JVM-compiled in any porting guidance.

## Cross-references for general JITX 4.x discipline

The general JITX 4.x rules a porter needs (API verification, symlink
discipline, the common invented-API gallery, missing-Stanza-helper table)
live in the top-level `jitx` skill rather than being duplicated here:

- **Rule 0 — verify every API before writing it**: see
  `jitx-skills:jitx/SKILL.md` §"Rule 0".
- **`~/.jitx/current` symlink and parallel installs**: see
  `jitx-skills:jitx/references/bootstrap.md` step (1) and §"Parallel
  installs", plus `jitx-skills:jitx/SKILL.md` §"Parallel JITX installs".
- **Common invented-API gallery** (`RoundedRectangle`, `BGADepop`,
  `min_rated_voltage`, `from jitx import NonPopulatedComponent`, etc.):
  see `jitx-skills:jitx/SKILL.md` §"Common API mistakes".
- **Stanza helpers without a 4.x equivalent**
  (`add-mounting-holes`, `add-open-drain-pullups`, `set-paper`, `view-*`):
  see `jitx-skills:jitx/SKILL.md` §"Stanza helpers without a 4.x
  equivalent".

The **porting-specific** twist on the symlink is that this skill's whole
point is running 3.x and 4.x **alternately** — pre-port baseline build
vs post-port build — so the symlink is updated between every test run.
The pre/post snippets in `references/verification.md` and
`references/runnable-example/README.md` include the `ln -sfn` step
explicitly.

## When to Use This Skill

Activate on any of:

- The user has a `.stanza` design tree and asks to convert it to Python.
- The user mentions "JITX 3", "JITX 4", "Stanza→Python", "port from Stanza", "migrate to py-jitx", "rewrite in Python".
- The user has both a `.stanza` source file and an empty Python target (or vice versa) open and asks for the equivalent.
- The user is updating an entry in `nightly_design_tests/config/designs.yaml` style config to a `jitx-test/.github/workflows/integration-testing.yml` style row.

Do NOT activate for:

- Pure 3.x maintenance work (use `lbstanza` plus the user's running 3.x codebase).
- Pure 4.x greenfield design (use `jitx` and the `jitx-*` family).
- Stanza language questions unrelated to JITX (use `lbstanza` directly).

## Delegation Table

The unique scope of this skill is the *mapping* and the *cross-version verification flow*. For everything else, defer:

| Question | Skill |
|---|---|
| Stanza syntax / stdlib / package mechanics | `lbstanza` |
| Python 4.x environment, venv, pyright, build commands | `jitx` |
| Python 4.x component creation from datasheets / packages | `jitx-component-modeler` |
| Python 4.x circuits, wiring, passives, pours | `jitx-circuit-builder` |
| Python 4.x stackups, vias, routing structures | `jitx-substrate-modeler` |
| Python 4.x SI constraints, topology, protocols | `jitx-interconnect-constraints` |
| Python 4.x provide/require, pin muxing | `jitx-pin-assignment` |

Quote enough Stanza in your responses to anchor the mapping, then immediately switch to the Python target and delegate API depth.

## Reference Index

All bundled docs live in `references/`. Use grep + a small `Read` window — do not load whole files into context unnecessarily.

| Question type | File |
|---|---|
| "What does Stanza X become in Python?" | `references/construct-map.md` |
| "Where do I start? What order?" | `references/workflow.md` |
| "What gotchas should I expect?" | `references/pitfalls.md` |
| "How do I run the 3.x baseline + 4.x port?" | `references/verification.md` |
| "Show me a real example port." | `references/side-by-side/01-component.md`, `02-circuit.md`, `03-design-entry.md` (construct mappings, fragments) |
| "Show me `supports` → `@provide` translation." | `references/side-by-side/04-pin-assignment.md` (four common shapes: single, multi-option, per-pin GPIO, per-instance) |
| "Show me a parametric module with formulas." | `references/side-by-side/05-parametric-module.md` (TPS62933 with closed-form L / Cout / Css / divider math) |
| "Show me a runnable end-to-end port pair." | `references/runnable-example/` (small two-resistor design that builds in both versions) |

## Porting Workflow (Phase 0 → Phase 7)

Full recipe in `references/workflow.md` (Phase 0 — pre-verify ... Phase 7 — compare exports). Summary:

- **Phase 0 — Pre-verify the 3.x design.** Build the Stanza design with an installed 3.x release (`~/.jitx/<3.x version>/`). Capture baseline export to `/tmp/jitx-port/<design>/baseline-3.x/`. If this fails, **surface the error to the user, explain that the 3.x baseline did not execute cleanly, and ask whether to continue.** Continuing is allowed (some legacy designs no longer build but still need to be ported); the user must acknowledge that any artifacts the 4.x port produces cannot be cleanly compared to a known-good baseline and that pre-existing errors in the 3.x source may carry over silently into the 4.x port.
- **Phase 1 — Inventory.** Identify the top-level `pcb-module`, all `pcb-component`s, packages, `pcb-stackup`, constraints, provide/require usages, and the `main.stanza` entry point.
- **Phase 2 — Bootstrap the Python project.** `pyproject.toml`, `main.py`, placeholder `Design` subclass. Use the `jitx` skill for the boilerplate.
- **Phase 3 — Port components (leaves).** One Python file per `pcb-component`; translate pin tables, package, landpattern, symbol mapping. Defer API depth to `jitx-component-modeler`.
- **Phase 4 — Port circuits / modules.** Bottom-up. **Before closing Phase 4**, every Stanza `require` / `supports` / `provide` construct must reach one of three states — fixed `Net` wiring, `@provide` / `require()` via inline `jitx-pin-assignment` invocation, or an *explicitly* deferred follow-up (named in `PORT-DEFERRED.md`, not a `# TODO` comment). Apply the hardware-analysis gate in `references/workflow.md` Phase 4 before delegating to `jitx-pin-assignment` — most `require` clauses are fixed wiring, not pin-mux. **`status: ok` with "module port(s) have no internal connections" warnings is not an acceptable Phase 4 exit.**
- **Phase 5 — Port substrate / constraints / topology / pin assignment.** These are usually the trickiest — defer to `jitx-substrate-modeler`, `jitx-interconnect-constraints`, `jitx-pin-assignment`.
- **Phase 6 — Post-verify the 4.x design.** Project venv with `pip install --pre -e .`, `pyright` clean (modulo the `Part(mpn=…).<port>` exception documented in `jitx-component-modeler` §"pyright caveat" — those errors are unavoidable), `~/.jitx/<4.x>/jitx interactive .` running in background, `JITX_SKIP_STABILIZE_CONFIRMATION=1 python -m jitx build <package>.<module>.<DesignClass>` succeeds. Capture to `/tmp/jitx-port/<design>/ported-4.x/`. The order-sensitive bootstrap recipe is canonical in [`jitx-skills:jitx/references/bootstrap.md`](../jitx/references/bootstrap.md); `references/verification.md` adds the port-specific concerns (artifact capture, baseline alternation, CI env-var pattern) on top.
- **Phase 7 — Compare exports.** Walk the general six-section export-verification checklist in [`jitx-skills:jitx/references/export-verification.md`](../jitx/references/export-verification.md) (A. net inventory, B. connector pin assignment, C. power topology, D. component output pins, E. passive counts, F. control signals), plus the port-only B′ (connector pin-index translation) and E′ (passive-count delta) checks in `references/verification.md`. `status: ok` is not evidence of correctness.

## Port-mode anti-patterns

(General JITX 4.x "don't"s — inventing APIs, skipping pyright, etc. — live
in `jitx-skills:jitx/SKILL.md` §"Common API mistakes". The list below is
porting-specific.)

- ❌ Paraphrasing Stanza idioms 1:1 in Python. Python has its own
  idioms — `+` for nets, `>>` for topology, decorators
  (`@provide`/`@require`) for pin assignment, attribute assignment in
  `Circuit.__init__` instead of returned values.
- ❌ Re-explaining Stanza syntax inside this skill — defer to `lbstanza`.
- ❌ Carrying over Stanza package paths verbatim. Python uses standard
  module paths from `pyproject.toml`.
- ❌ Skipping the 3.x pre-verify build silently. The pre-verify is
  mandatory; if it fails, surface the error and get explicit user
  acknowledgement before proceeding (porting a broken source can mask
  the original bug as a porting bug — but the user gets to decide
  whether to continue).
- ❌ Writing a port plan that does not name Phase 0 (3.x pre-verify) as
  an explicit step. Plan-time omission is the silent-failure surface —
  if Phase 0 isn't in the plan, it won't happen during execution. A plan
  that says "build the v3 source at the target commit first" satisfies
  this; a plan that begins with "create the port branch" does not.
- ❌ Treating 4.x as a Stanza target. 4.x is Python-only; running a 3.x
  Stanza design under 4.x is unsupported and may break in non-obvious
  ways.
- ❌ Describing Stanza as JVM-compiled. It is natively compiled via C.
