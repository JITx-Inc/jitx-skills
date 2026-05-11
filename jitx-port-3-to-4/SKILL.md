---
name: jitx-port-3-to-4
description: This skill should be used when the user asks to port, migrate, or convert a JITX 3.x (LB Stanza) PCB design to JITX 4.x (Python) — including translating `pcb-module`/`pcb-component`/`defpackage` to Python `Circuit`/`Component`/modules, rewriting nets and topology, mapping `stanza.proj`/`main.stanza` build entry points to `pyproject.toml`/`python -m jitx build`, and updating `nightly_design_tests` style configs to `jitx-test` style integration. Triggers on phrases like "port to 4.x", "migrate from Stanza", "convert .stanza design to Python", "Stanza→Python", "rewrite this pcb-module in Python", or when the user has both `.stanza` source and a Python target.
---

# JITX Port 3.x → 4.x Skill

Help port JITX 3.x (LB Stanza) PCB designs to JITX 4.x (Python).

This skill is a **router**, not a full tutorial. It does not re-teach Stanza or the Python 4.x API — it points to the existing skills that do, and supplies the construct mappings, workflow, pitfalls, and verification recipe that are unique to the porting task.

## Mental Model

Three facts drive the whole port:

1. **JITX 3.x is the Stanza line; JITX 4.x is the Python line.** 4.x introduced the Python workflow and is Python-only going forward — some Stanza designs may still happen to compile under 4.x, but Stanza is not a supported target for 4.x. The supported migration path is 3.x Stanza → 4.x Python.
2. **The languages differ but the JITX object model is similar.** A Stanza `pcb-module` is a Python `Circuit` subclass; a Stanza `pcb-component` is a Python `Component` subclass; `pcb-stackup` is `Stackup`; nets connect via `+`; topology connects via `>>`. Most ports are mechanical at the structural level once the mapping is internalized.
3. **The build/CI shell differs.** Stanza designs are launched from `main.stanza` + `design_name` (per `nightly_design_tests/config/designs.yaml`). Python designs use `python -m jitx build <package>.<module>.<DesignClass>` against a `jitx interactive` server (per `jitx-test/.github/workflows/integration-testing.yml`). The CI matrix shape changes accordingly.

**Note on Stanza:** Stanza compiles natively (via a C backend). It has no JVM target. Never describe Stanza as JVM-compiled in any porting guidance.

## ⚠️ CRITICAL: `~/.jitx/current` must match the version you're running

**Only one JITX version can be active at a time, and `~/.jitx/current` selects which one.** JITX reads runtime, config, and plugin state via `~/.jitx/current/...` regardless of which versioned binary you launched. If the symlink points at a different version than the binary you invoke, wrong-version state silently leaks into the build pipeline and the design **will fail** — typically with the obscure `FATAL PLUGIN ERROR: No appropriate branch for arguments of type (False)` in `StableBoardSerializer/write-stable-id`, but other failure modes are possible.

This skill's whole point is running 3.x and 4.x **alternately** (pre-port build vs post-port build). **Update the symlink between every test run:**

```bash
ln -sfn 3.36.1 ~/.jitx/current             # before any 3.x build
ln -sfn 4.1.0 ~/.jitx/current              # before any 4.x build
```

(Substitute your installed version directories.) The pre/post commands in `references/verification.md` and `references/runnable-example/README.md` include this step explicitly. If a build crashes with `write-stable-id (False)`, **check the symlink before suspecting anything else** — every documented occurrence of that error has been a `~/.jitx/current` mismatch, not a JITX bug.

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
| "Show me a runnable end-to-end port pair." | `references/runnable-example/` (small two-resistor design that builds in both versions) |

## Porting Workflow (7 Steps)

Full recipe in `references/workflow.md`. Summary:

1. **Pre-verify the 3.x design.** Build the Stanza design with an installed 3.x release (`~/.jitx/<3.x version>/`). Capture baseline export to `/tmp/jitx-port/<design>/baseline-3.x/`. If this fails, **surface the error to the user, explain that the 3.x baseline did not execute cleanly, and ask whether to continue.** Continuing is allowed (some legacy designs no longer build but still need to be ported); the user must acknowledge that any artifacts the 4.x port produces cannot be cleanly compared to a known-good baseline and that pre-existing errors in the 3.x source may carry over silently into the 4.x port.
2. **Inventory.** Identify the top-level `pcb-module`, all `pcb-component`s, packages, `pcb-stackup`, constraints, provide/require usages, and the `main.stanza` entry point.
3. **Bootstrap the Python project.** `pyproject.toml`, `main.py`, placeholder `Design` subclass. Use the `jitx` skill for the boilerplate.
4. **Port leaves first.** Components → circuits → top-level `Design`. **Before closing Step 4**, every Stanza `require` / `supports` / `provide` construct must reach one of three states — fixed `Net` wiring, `@provide` / `require()` via inline `jitx-pin-assignment` invocation, or an *explicitly* deferred follow-up (named in `PORT-DEFERRED.md`, not a `# TODO` comment). Apply the hardware-analysis gate in `references/workflow.md` Phase 4 before delegating to `jitx-pin-assignment` — most `require` clauses are fixed wiring, not pin-mux. **`status: ok` with "module port(s) have no internal connections" warnings is not an acceptable Step 4 exit.**
5. **Port substrate / constraints / topology / pin assignment.** These are usually the trickiest — defer to `jitx-substrate-modeler`, `jitx-interconnect-constraints`, `jitx-pin-assignment`.
6. **Post-verify the 4.x design.** Project venv with `pip install jitx ...`, `pyright` clean, `~/.jitx/<4.x>/jitx interactive .` running in background, `JITX_SKIP_STABILIZE_CONFIRMATION=1 python -m jitx build <package>.<module>.<DesignClass>` succeeds. Capture to `/tmp/jitx-port/<design>/ported-4.x/`. See `references/verification.md` §"4.x bootstrap ordering checklist" for the full ordered recipe — the steps are order-sensitive and skipping any of them produces opaque failures.
7. **Compare exports.** Walk the six-section structured checklist in `references/verification.md` §"Compare exports — structured checklist" (net inventory, connector pin assignment, power topology, component output pins, passive counts, control signals). `status: ok` is not evidence of correctness. The TEC-example pilot built cleanly with four distinct categories of silent netlist errors that this checklist catches.

## Anti-patterns

- ❌ Paraphrasing Stanza idioms 1:1 in Python. Python has its own idioms — `+` for nets, `>>` for topology, decorators (`@provide`/`@require`) for pin assignment, attribute assignment in `Circuit.__init__` instead of returned values.
- ❌ Inventing Python APIs. Always verify symbols against `jitx-4-1-python-llms.txt` (the `jitx` skill bundles it) or `py-jitx/src/jitx/*.py`.
- ❌ Re-explaining Stanza syntax inside this skill — defer to `lbstanza`.
- ❌ Carrying over Stanza package paths verbatim. Python uses standard module paths from `pyproject.toml`.
- ❌ Skipping the 3.x pre-verify build silently. The pre-verify is mandatory; if it fails, surface the error and get explicit user acknowledgement before proceeding (porting a broken source can mask the original bug as a porting bug — but the user gets to decide whether to continue).
- ❌ Treating 4.x as a Stanza target. 4.x is Python-only; running a 3.x Stanza design under 4.x is unsupported and may break in non-obvious ways.
- ❌ Describing Stanza as JVM-compiled. It is natively compiled via C.

## Two Parallel JITX Installs

JITX releases install per-version under `~/.jitx/<version>/` and both can coexist:

- **3.x** under e.g. `~/.jitx/3.36.1/` — provides the `jitx` launcher (a thin wrapper around `jstanza`), the bundled Stanza compiler at `stanza/stanza`, the SLM package manager at `slm/slm`, and the bundled JITX/JITX3/ocdb stdlib under `slm/`.
- **4.x** under e.g. `~/.jitx/4.1.0/` — provides the launcher's `interactive` server (the WebSocket the build connects to) and `sign-in`. The Python build toolchain itself (`python -m jitx build`) is installed per-project via `pip install jitx jitxlib-parts ...` from the JITX internal package index.

The user substitutes their own installed version directories. Both lines share the binary name `jitx`, so invoke each by absolute path or use isolated subshells.

Re-update `~/.jitx/current` between every alternation between the two installs — see the **⚠️ CRITICAL** section near the top of this file. `references/verification.md` includes the `ln -sfn` step in the pre/post build snippets.
