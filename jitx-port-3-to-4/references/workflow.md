# Porting Workflow (Stanza 3.x → Python 4.x)

A phased recipe. Verification phases (0 and 6) bracket the port and are mandatory; the build smoke test is what makes a port reviewable.

## Phase 0 — Pre-verify the 3.x design

**Goal:** prove the Stanza source builds *before* you change anything.

1. Confirm an active sign-in: `~/.jitx/<3.x>/jitx sign-in -email <email>`. Without sign-in the build fails at the OCDB part-database query.
2. Point `~/.jitx/current` at the 3.x install you're about to use (`ln -sfn <3.x version> ~/.jitx/current`). JITX reads runtime state via this symlink — a stale 4.x target silently breaks the export pipeline (see `verification.md`).
3. Read the 3.x entry point. For nightly-test style designs, find the row in `nightly_design_tests/config/designs.yaml` to identify `project_dir`, `stanza_file`, and `design_name`.
4. Run `slm fetch` to resolve dependencies declared in `slm.toml`, then run the 3.x build using the installed 3.x release at `~/.jitx/<3.x version>/`. See `verification.md` for the exact invocation.
5. Capture the baseline export (BOM, schematic, board) to `/tmp/jitx-port/<design>/baseline-3.x/`.
6. If the build fails, **do not silently proceed**. Surface the error verbatim, tell the user "the 3.x baseline did not build cleanly," and ask whether to continue. Continuing is allowed — the user may be porting a legacy design that no longer builds. The user must acknowledge:
   - Pre-existing errors in the 3.x source may carry over into the 4.x port without being detected by the post-port verification.
   - The export comparison step (Phase 7) will be unreliable because there's no clean 3.x baseline to compare against.

   Record the user's acknowledgement in the porting notes (e.g. add a `BASELINE-FAILED.md` to the project root listing the 3.x error) so reviewers know the comparison was waived.

## Phase 1 — Inventory the Stanza design

Read the source tree and list:

- Entry point (`main.stanza`) and any `set-board` / `set-current-design` / `view` / `run` calls.
- Top-level `pcb-module` (the design root).
- All child `pcb-module` definitions (the hierarchy).
- All `pcb-component` definitions (leaves).
- Any `pcb-stackup`, `pcb-via`, `pcb-material`, `pcb-bundle` declarations.
- `supports` / `require` clauses (provide/require — these become Python decorators).
- Topology declarations and signal constraints.
- The `stanza.proj` and `defpackage` graph (informs Python module layout).

This inventory drives the rest of the port. Save it to a scratch file so it can be checked off as work progresses.

## Phase 2 — Bootstrap the Python project

Use the `jitx` skill for the canonical layout. Minimum:

```
<project>/
├── pyproject.toml
├── main.py             # imports + Design subclass
└── <package>/          # mirrors the Stanza package layout where useful
    ├── __init__.py
    ├── components/
    └── circuits/
```

Stub the top-level `class <Design>(Design)` so `python -m jitx build` can find a target before the implementation lands. Use the `jitx-component-modeler` and `jitx-circuit-builder` skills for boilerplate templates.

## Phase 3 — Port components (leaves first)

One Python file per `pcb-component`. For each:

1. Look up the construct mapping in `references/construct-map.md`.
2. Translate pin tables, package, landpattern, symbol mapping.
3. Defer API depth to `jitx-component-modeler` — especially for symbol generation, multi-unit symbols, thermal pads, and complex pin mappings.
4. If the Stanza component used parametric helpers (e.g. a generator that produced a family of components), port the generator as a Python function or factory rather than transcribing every emitted instance.

## Phase 4 — Port circuits / modules

Bottom-up: leaf circuits before parents. For each:

1. Translate `pcb-module` to `class X(Circuit)`.
2. Map `inst` declarations to attribute assignments inside `__init__`.
3. Translate every `net (a, b)` / `connect ...` to a Python `+` chain on `Port`s.
4. Use `jitx-circuit-builder` for nets, passives, power, pours, copper geometry.
5. Use `jitx-pin-assignment` for any `supports` / `require` clauses — they map to `@provide` / `@require` decorators with subtle hierarchical-composition differences from Stanza.

## Phase 5 — Substrate, constraints, topology, pin assignment

These are the domain-heavy parts of the port. They typically arrive intact in the design but must be reformulated for the Python API:

- **Stackup:** translate `pcb-stackup` to `Stackup` / `Symmetric` (uses `jitx-substrate-modeler`).
- **Vias and routing structures:** `pcb-via` → `Via`; new in 4.x, formalize via `RoutingStructure`, `DifferentialRoutingStructure`, `NeckDown` where appropriate.
- **Signal constraints:** Stanza topology constraints → `Constrain`, `ConstrainDiffPair`, `TimingConstraint`, `InsertionLossConstraint`, `ReferencePlanes` (uses `jitx-interconnect-constraints`).
- **Topology graph:** `>>` operator builds the routed graph; bridging/terminating pin models attach to nodes.

## Phase 6 — Post-verify the 4.x design

**Goal:** prove the Python target builds, types-check, and produces an export.

1. Confirm an active sign-in (same as Phase 0). The 4.x build connects to the part database too — without sign-in it fails with `You are not authenticated`.
2. Repoint `~/.jitx/current` to the 4.x install (`ln -sfn <4.x version> ~/.jitx/current`). The same symlink rule applies — a stale 3.x target will break the 4.x pipeline.
3. Set up a project venv: `python -m venv .venv && source .venv/bin/activate && pip install --pre .` (or `uv sync --active --prerelease=allow`). The `jitx` Python package lives on the JITX internal index, not public PyPI.
4. `pyright` must be clean (the `jitx` skill covers the venv + pyright config). Treat any `pyright` error as blocking — type errors in JITX 4.x commonly mask wiring bugs.
5. Start `~/.jitx/<4.x>/jitx interactive "$PWD" &` in the background — it writes `.socket.jitx`, which `python -m jitx build` discovers automatically by walking up from cwd.
6. Run `python -m jitx build <package>.<module>.<DesignClass>` from the project root (with `PYTHONPATH=$PWD` if the project isn't installed). See `verification.md` for the exact invocation.
7. Capture the export to `/tmp/jitx-port/<design>/ported-4.x/`.

## Phase 7 — Compare exports (placeholder)

Manual today, automatable later. Diff the artifact pairs:

- BOM (CSV) — same parts, same counts, same values.
- Netlist — same (component, pin) ↔ net mapping.
- Board geometry — same component placement (strict) and similar trace routing (loose).
- Schematic — visual review.

The `verification.md` doc names a future `scripts/compare-exports.py` slot. Until that exists, attach the two export directories to the PR / report and call out any divergence found by manual review.

## Heuristic: what to port first when stuck

If the design is large, port a **vertical slice** end-to-end before going wide:

1. Top-level `Design` class with a Board + Substrate (placeholder) + a single trivial Circuit (one component).
2. Confirm pre/post build smoke works.
3. Add components and circuits incrementally, re-running `python -m jitx build` after each addition.

This catches build / packaging / pyright issues early, when the diff is small enough to debug.
