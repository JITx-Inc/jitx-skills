# Runnable Example: Two-Resistor Design in 3.x and 4.x

The canonical end-to-end smoke test for the verification flow in `../verification.md`. Same logical content (two 1 kΩ chip resistors connected by one net) expressed in both versions.

The `side-by-side/` directory next to this one teaches **construct mappings** with fragments that don't compile. This directory is the opposite — it doesn't try to demonstrate every construct, but the two versions here **do compile and export real artifacts** with the released JITX toolchains, end to end, given a signed-in install. Use it to (a) sanity-check your install, (b) anchor `verification.md`'s pre/post commands on something concrete, (c) cross-check the future export comparator.

## Layout

```
runnable-example/
├── 3.x/
│   ├── main.stanza           # the design source
│   ├── stanza.proj           # project file referencing bundled SLM libs
│   └── slm.toml              # SLM dependencies (jsl, JITX, JITX3, ocdb)
└── 4.x/
    ├── pyproject.toml        # python project + jitx deps
    └── runnable_example/
        ├── __init__.py
        └── main.py           # the design source
```

## Prerequisites

- 3.x release installed at `~/.jitx/<3.x version>/` (e.g. `3.36.1`).
- 4.x release installed at `~/.jitx/<4.x version>/` for the `interactive` server. (The `python -m jitx build` toolchain itself comes from the project venv, not this install.)
- Signed in: `~/.jitx/<ver>/jitx sign-in -email <email>`. **Mandatory** for both versions — 3.x needs auth for the OCDB part-database query that resolves `chip-resistor`; 4.x needs auth for the equivalent part lookup in `jitxlib.parts`. Without sign-in, both builds fail with a clear "You are not authenticated" / "Unhandled Exception while searching parts database" error.
- For 4.x: a Python ≥3.12 environment that can `pip install jitx jitxlib-parts jitxlib-standard` (these come from the JITX internal index — same one the project's CI uses; see `jitx-test/scripts/jitx-build-design.bash`).
- **⚠️ CRITICAL: `~/.jitx/current` MUST match the version you're invoking.** Only one JITX version can run at a time. JITX reads runtime/config/plugin state via `~/.jitx/current/...` regardless of which versioned binary you launched, so a mismatch silently corrupts the build and the design **will fail** (typical symptom: `write-stable-id (False)` crash in `StableBoardSerializer`). Repoint with `ln -sfn <version> ~/.jitx/current` **between every alternation** between the 3.x baseline build and the 4.x port build below — even if you "just" rebuilt the same version. If a build crashes obscurely, `readlink ~/.jitx/current` is the first thing to check.

## Build the 3.x baseline

```bash
JITX_3X=~/.jitx/3.36.1

# Critical: align the current symlink with the version we're about to invoke.
ln -sfn "$(basename "$JITX_3X")" ~/.jitx/current

# Stage a working copy
cp -r 3.x /tmp/jitx-port/runnable-example/baseline-src
cd /tmp/jitx-port/runnable-example/baseline-src

# Fetch SLM deps (clones jsl + transitive). Stanza must be on PATH for SLM.
PATH="$JITX_3X/stanza:$PATH" "$JITX_3X/slm/slm" fetch

# Build (the `jitx` launcher is a thin wrapper around jstanza that finds the
# install's .stanza config; calling jstanza directly fails with "Could not
# locate .stanza configuration file").
PATH="$JITX_3X/stanza:$PATH" "$JITX_3X/jitx" run main.stanza
```

Expected outcome (on a signed-in install with the matching symlink): real CAD artifacts under `./designs/runnable-example/kicad/` (`.kicad_pcb`, `.kicad_sch`, `.kicad_pro`, footprint lib, sym lib, plus a STEP 3D model). Capture them to `/tmp/jitx-port/runnable-example/baseline-3.x/`.

If you see `Unhandled Exception while searching parts database` / `You are not authenticated`, run `~/.jitx/<ver>/jitx sign-in -email <your-email>` first.

If you see `FATAL PLUGIN ERROR: No appropriate branch for arguments of type (False)` in `StableBoardSerializer/write-stable-id`, confirm the `~/.jitx/current` symlink matches `JITX_3X` — that's the failure mode of a symlink mismatch.

## Build the 4.x port

```bash
JITX_4X=~/.jitx/4.1.0          # adjust to your installed version

# Repoint current at the 4.x install for this build.
ln -sfn "$(basename "$JITX_4X")" ~/.jitx/current

# Stage a working copy
cp -r 4.x /tmp/jitx-port/runnable-example/ported-src
cd /tmp/jitx-port/runnable-example/ported-src

# Project venv with the JITX Python toolchain
python -m venv .venv
source .venv/bin/activate
pip install --pre .             # `--pre` allows pre-release jitx wheels

# The build needs a local websocket server. `jitx interactive` writes
# .socket.jitx in the project dir; the build auto-discovers it.
"$JITX_4X/jitx" interactive "$PWD" > .jitx-interactive.log 2>&1 &
INT_PID=$!
sleep 2

# Build. The fully-qualified design name = <package>.<module>.<class>.
PYTHONPATH="$PWD" python -m jitx build runnable_example.main.runnable_example

kill $INT_PID 2>/dev/null
```

Expected outcome (on a signed-in install): exports under `./designs/runnable_example.main.runnable_example/`. Capture to `/tmp/jitx-port/runnable-example/ported-4.x/`.

If `pip install --pre .` fails with a 401/403, your venv doesn't have access to the JITX internal package index. Use the same `JITX_USER_EMAIL`/`JITX_USER_PASS`/`JITX_ENV` env-var setup that `jitx-test/scripts/jitx-build-design.bash` uses.

## What to compare

For now, manually inspect both directories:

```
ls /tmp/jitx-port/runnable-example/baseline-3.x/
ls /tmp/jitx-port/runnable-example/ported-4.x/
```

Both should contain `cache/` + `design-info/` directories with `netlist.json`, `physical-layout.design`, `stable.design`. The 3.x side additionally has a `kicad/` subdirectory with the real CAD project (`.kicad_pcb`, `.kicad_sch`, `.kicad_pro`, footprint/symbol libs, STEP 3D model). The 4.x side currently writes its CAD output under `cache/` rather than a separate `kicad/` dir — the future `scripts/compare-exports.py` comparator (placeholder, see `../verification.md`) will normalize these layouts.

Trace routing won't match exactly between versions (the routers differ); component placement and BOM should.

## Known limitations

- **Sign-in required.** Both builds query a part database and will fail without auth. There is no fully-offline mode for stdlib parts in either version.
- **Internal package index for 4.x.** `pip install jitx jitxlib-parts jitxlib-standard` requires the JITX internal index. Public PyPI does not host these.
- **`~/.jitx/current` is load-bearing — see the CRITICAL note in Prerequisites.** Forgetting to re-point it produces a confusing `write-stable-id (False)` crash that is *not* a JITX bug.
- **Stdlib-parts only.** This example uses `chip-resistor` / `Resistor` from OCDB / `jitxlib.parts`. It does not exercise custom-landpattern porting — for that, `../side-by-side/01-component.md` documents the conceptual mapping.
- **Routers differ.** Even with identical components, routed traces will not be byte-identical between versions; comparison should be tolerant of trace geometry.
- **`SampleDesign` is for tests, not real designs.** The 4.x side wraps `SampleDesign` (from `jitx.sample`) which uses an arbitrary stdlib stackup and fab constraints. Real ports should declare a real `Substrate` / `Stackup` / `Board` — see `jitx-substrate-modeler` for that work.

## Verification status (this machine)

Last verified end-to-end on this machine (3.x install: `~/.jitx/3.36.1/`; 4.x install: `~/.jitx/4.1.0-develop.9/`; signed in; `~/.jitx/current` updated to match the binary being invoked):

- **3.x baseline:** SLM deps fetched, design compiled, OCDB resolved real chip-resistor part, `export-cad()` produced a complete KiCad project under `designs/runnable-example/kicad/` plus internal `stable.design` / `netlist.json`.
- **4.x port:** venv with `jitx` toolchain pip-installed, `jitx interactive` started, `python -m jitx build runnable_example.main.runnable_example` returned `status: ok`, OCDB resolved real part `CRCW01001K00FREL`, artifacts under `designs/runnable_example.main.runnable_example/{cache,design-info}/`.

Both directories sit side-by-side at `/tmp/jitx-port/runnable-example/{baseline-3.x,ported-4.x}/`, ready for the future `compare-exports.py` comparator.

### Headless / IDE-detached notes

When run outside VS Code, both versions print warnings about `runtime/visualizer-socket`:

```
ERROR: Could not open connection ... visualizer-socket: No such file or directory.
Please open Visual Studio Code.
```

These are cosmetic — they're the `view-board()` / `view-schematic()` calls trying to push into the JITX Sidebar UI, which isn't running headless. The build (and the CAD export, when the symlink is correct) completes regardless.
