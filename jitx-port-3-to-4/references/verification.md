# Verification: Pre/Post Build Using Parallel JITX Installs

The porting workflow brackets every conversion with two builds:

- **Pre-port:** build the original 3.x Stanza design to confirm a working baseline.
- **Post-port:** build the new 4.x Python design to confirm the port builds and exports.

Both runs capture artifacts to known directories so a future automated comparator can diff them.

## Parallel Installs

JITX releases install per-version under `~/.jitx/<version>/`. Both lines can be installed at the same time. Typical layout:

```
~/.jitx/
├── 3.36.1/                 # a 3.x release (Stanza line)
├── 4.1.0/                  # a 4.x release (Python line)
├── current -> 3.36.1       # symlink — MUST point at the version you're invoking
└── jitx.config
```

Substitute the actual version directories the user has installed. Each install is self-contained — its own binaries, libraries, runtime.

| Line | Path (example) | Provides |
|---|---|---|
| 3.x (Stanza) | `~/.jitx/3.36.1/` | `jitx` launcher (wraps `jstanza`); `slm/slm` package manager; bundled JITX/JITX3/ocdb stdlib |
| 4.x (Python) | `~/.jitx/4.1.0/` | `jitx` launcher with `interactive` (build server) + `sign-in`. The Python build toolchain itself is installed per-project via `pip install jitx`. |

## ⚠️ CRITICAL: `~/.jitx/current` MUST match the version being invoked

**Only one JITX version can run at a time, and `~/.jitx/current` selects which.** JITX reads its runtime, config, and plugin state via `~/.jitx/current/...` regardless of which versioned binary you launched. Mismatch between the symlink and the binary feeds wrong-version state into the build and **the design will fail** — most often as the obscure `FATAL PLUGIN ERROR: No appropriate branch for arguments of type (False)` in `StableBoardSerializer/write-stable-id`, but other silent corruptions are possible.

**Update `~/.jitx/current` before every test run:**

```bash
ln -sfn 3.36.1 ~/.jitx/current             # before any 3.x build (substitute your installed 3.x version)
ln -sfn 4.1.0  ~/.jitx/current             # before any 4.x build (substitute your installed 4.x version)
```

The pre-port build (3.x) and post-port build (4.x) snippets below both include this `ln -sfn` step. **Do not skip it** even if you "just" rebuilt the same version — any prior interleaved run with a different version may have left the symlink elsewhere. If a build crashes with `write-stable-id (False)`, the first thing to verify is that `readlink ~/.jitx/current` matches the install you're actually invoking.

## Sanity-check both installs

```bash
JITX_3X=~/.jitx/3.36.1        # adjust to your installed 3.x version
JITX_4X=~/.jitx/4.1.0         # adjust to your installed 4.x version

# 3.x — Stanza compiler is alive (bundled in $JITX_3X/stanza/)
"$JITX_3X/stanza/stanza" version

# 4.x — launcher is alive
"$JITX_4X/jitx" check-install
```

If either fails, reinstall that version from the official JITX release before continuing.

## Sign-in (mandatory, both versions)

Both 3.x and 4.x builds query a part database and **fail without an active sign-in**. Errors look like:

- 3.x: `Unhandled Exception while searching parts database`
- 4.x: `You are not authenticated. Please sign in through the JITX Sidebar in VSCode.`

Sign in once before running either build (auth state is shared across versioned installs):

```bash
"$JITX_4X/jitx" sign-in -email <your-email>     # password prompted on stdin
```

For non-interactive runs (CI), the project's build driver (`jitx-test/scripts/jitx-build-design.bash`) sets `JITX_USER_EMAIL`, `JITX_USER_PASS`, `JITX_ENV` (`app` / `app-testing` / `app-dev`) and pipes the password into `jitx sign-in -email <email> <<<"$JITX_USER_PASS"`.

## Pre-port build (3.x baseline)

Identify the design's entry from its `nightly_design_tests`-style row (or equivalent):

```yaml
- project_dir: "ethernet_io"
  stanza_file: "main.stanza"
  design_name: "ethernet-board"
```

Build with the 3.x install:

```bash
DESIGN=ethernet_io
PROJECT_DIR=/path/to/${DESIGN}
DESIGN_NAME=ethernet-board
JITX_3X=~/.jitx/3.36.1            # adjust
OUT=/tmp/jitx-port/${DESIGN}/baseline-3.x
mkdir -p "$OUT"

# CRITICAL: point ~/.jitx/current at the 3.x install before invoking it,
# otherwise runtime state from a different version leaks in and breaks the
# export pipeline.
ln -sfn "$(basename "$JITX_3X")" ~/.jitx/current

(
  cd "$PROJECT_DIR"

  # Resolve SLM dependencies declared in slm.toml (clones jsl etc.). Stanza
  # must be on PATH for SLM to invoke it, and SLM_ROOT must point at the
  # 3.x slm install or `slm fetch` exits with
  #   ValueError: No Environment Variable 'SLM_ROOT' found
  SLM_ROOT="$JITX_3X/slm" \
      PATH="$JITX_3X/stanza:$PATH" "$JITX_3X/slm/slm" fetch

  # Run via the `jitx` wrapper, which finds the install's .stanza config.
  # Calling jstanza directly fails with "Could not locate .stanza
  # configuration file".
  PATH="$JITX_3X/stanza:$PATH" "$JITX_3X/jitx" run main.stanza \
      > "$OUT/build.stdout" 2> "$OUT/build.stderr"
  echo $? > "$OUT/exit-code"
)
```

The exact invocation may differ per design (some designs ship a wrapper script, some use `slm build`, some run `jitx run` against a specific entrypoint). The design's own runner / Makefile / README is the source of truth — read it and reuse its invocation, only substituting binary paths with `"$JITX_3X/..."`.

**On nonzero `exit-code`, do not silently proceed.** Surface `build.stderr` verbatim, tell the user the 3.x baseline did not build cleanly, and ask whether to continue. The user is allowed to override (some legacy 3.x designs no longer build but still need to be ported), but they must explicitly acknowledge that:

- Pre-existing errors in the 3.x source may carry over into the 4.x port without being caught by post-port verification.
- The export comparison step is unreliable because there is no clean baseline to diff against.

When proceeding under override, record the failure mode in a `BASELINE-FAILED.md` next to the port (or in PR notes) so reviewers can see what was waived. The default is still to fix the baseline first.

Expected artifacts under `$OUT/` (varies by design): KiCad project + 3D STEP under `kicad/`, schematic, BOM, internal `stable.design` / `netlist.json`.

## Post-port build (4.x)

The 4.x build runs from a **project venv** that has the JITX Python toolchain pip-installed; the `~/.jitx/<4.x>/` install supplies the `jitx interactive` server (which the build connects to) and `jitx sign-in`, but does **not** provide a `jitx build` subcommand.

### 4.x bootstrap ordering checklist

The steps below are **order-sensitive**. Skipping or reordering them produces
opaque failures (silent hangs, "Unable to determine socket URI", auth errors with
no hint that `sign-in` is the missing step).

1. **Symlink first**: `ln -sfn <version> ~/.jitx/current` — must point at the
   4.x install before launching `jitx interactive`. The interactive server
   reads runtime state via `~/.jitx/current/`; a stale symlink poisons the
   build (see the §"⚠️ CRITICAL" warning above).
2. **Sign in once** (if not already): `"$JITX_4X/jitx" sign-in -email <email>`
   — `python -m jitx build` fails authentication if the user is not signed
   in, with no hint that sign-in is the missing step. See §"Sign-in" above.
3. **Start the interactive server**: `"$JITX_4X/jitx" interactive "$PWD" &`.
   ⚠️ `interactive` is **not** listed in `jitx --help` — this is a known
   quirk, not a missing binary. Without it, the build fails with
   `Unable to determine socket URI`.
4. **Wait for the socket** before issuing any build: the server takes a few
   seconds to write `.socket.jitx`. Use a real wait, not a fixed `sleep`:
   `until [ -e .socket.jitx ]; do sleep 1; done`.
5. **Install the project**: `pip install --pre .` inside the venv. The
   server must already be up — some `pip install` paths exercise jitx
   imports that need the server.
6. **Verify version match**: `python -c 'import jitx; print(jitx.__version__)'`
   should match `readlink ~/.jitx/current`. Mismatches may work but cause
   subtle API drift; flag them.
7. **Build headless**: prefix with `JITX_SKIP_STABILIZE_CONFIRMATION=1`.
   Without this env var, `python -m jitx build` pauses interactively asking
   "save stable design?" and hangs any CI / unattended run.

### Worked snippet

```bash
DESIGN=ethernet_io
PORT_DIR=/path/to/ported/${DESIGN}
DESIGN_NAME=runnable_example.main.RunnableExample   # <package>.<module>.<DesignClass>
JITX_4X=~/.jitx/4.1.0                               # adjust
OUT=/tmp/jitx-port/${DESIGN}/ported-4.x
mkdir -p "$OUT"

# (1) Repoint ~/.jitx/current at the 4.x install before doing anything else.
ln -sfn "$(basename "$JITX_4X")" ~/.jitx/current

# (2) Sign in (once per session; auth state shared across versioned installs).
"$JITX_4X/jitx" sign-in -email "$JITX_USER_EMAIL" <<<"$JITX_USER_PASS"

(
  cd "$PORT_DIR"

  # (3) Start the interactive server. It writes .socket.jitx in $PWD; the
  # build auto-discovers it by walking up from cwd.
  # NOTE: `interactive` is not listed in `jitx --help` — known quirk.
  "$JITX_4X/jitx" interactive "$PWD" > "$OUT/interactive.log" 2>&1 &
  INT_PID=$!

  # (4) Wait for the socket file rather than a fixed sleep.
  until [ -e .socket.jitx ]; do sleep 1; done

  # (5) Project venv with the jitx Python toolchain (pre-release wheels are
  # common). Internal package index access required for `pip install jitx*`.
  python -m venv .venv
  source .venv/bin/activate
  pip install --pre . > "$OUT/pip.log" 2>&1

  # (6) Sanity-check that the pip-installed jitx matches ~/.jitx/current.
  python -c 'import jitx; print(jitx.__version__)' > "$OUT/jitx-version.txt"
  echo "current -> $(readlink ~/.jitx/current)" >> "$OUT/jitx-version.txt"

  # Pre-flight: pyright must be clean.
  pyright . > "$OUT/pyright.txt" 2>&1 || { echo "pyright failed"; exit 1; }

  # (7) Build headless. JITX_SKIP_STABILIZE_CONFIRMATION=1 suppresses the
  # interactive "save stable design?" prompt that would otherwise hang.
  # PYTHONPATH=. ensures the project package is importable.
  JITX_SKIP_STABILIZE_CONFIRMATION=1 \
      PYTHONPATH="$PWD" python -m jitx build "$DESIGN_NAME" \
      > "$OUT/build.stdout" 2> "$OUT/build.stderr"
  echo $? > "$OUT/exit-code"

  kill $INT_PID 2>/dev/null
)
```

Notes:

- The design name is the fully-qualified Python class path: `<package>.<module>.<class>`. Find it with `python -m jitx find .` from the project root.
- The `.socket.jitx` file the interactive server writes is the discovery hook used by `python -m jitx build` — there's no need to pass `--port` if you build from the project root.
- Some projects use `uv sync --active --prerelease=allow` instead of `pip install --pre .` (see `jitx-test/scripts/jitx-build-design.bash`).
- `pyright` issues block the build review even if `python -m jitx build` succeeds. Treat type errors as wiring bugs (see `pitfalls.md`).

## Compare exports — structured checklist

`status: ok` is not sufficient evidence that the port is correct. The
TEC-example pilot built cleanly with four distinct categories of silent
netlist errors (swapped connector pins, wrong PVDD source, an entire output
filter section missing, mis-wired control signals). Walk the six sections
below for every port — they catch errors that the build will not.

### A. Net inventory

1. Grep the Stanza source for every `net <Name> (...)` declaration.
2. For each, verify a correspondingly-named net exists in the Python
   netlist at `designs/<design_name>/cache/netlist.json`.
3. Any Stanza net with no Python counterpart is a potential missing
   connection — investigate before signing off.

### B. Connector pin assignment

1. Read every `inst <conn> : pin-header(N)` and `net (<conn>.p[i] <name>)`
   in the Stanza source.
2. Verify the Python connector uses matching assignments. **Stanza pin
   indices are 1-based; Python is 0-based** — `conn.p[1]` in Stanza is
   `conn.p[0]` in Python.
3. Confirm every connector pin's net name matches (`VCC`, `GND`, `EN`,
   `SCL`, `SDA`, etc.).

### C. Power topology

1. Identify the **external input net** (connected to the connector and
   to the regulator's VIN).
2. Identify the **regulated output net** (connected to the regulator's
   VOUT).
3. For each sub-circuit, verify its power ports connect to the correct
   rail — amp PVDD on the raw external supply, MCU/digital DVDD on the
   regulated rail. See `pitfalls.md` §"Power topology / net naming" —
   this is the most-inverted check in practice.

### D. Component output pins

1. For every IC in the design, grep the Stanza source for every component pin.
2. For output-stage ICs (amplifiers, regulators, motor drivers): verify
   every output pin (`OUT_x`, `BST_x`, `SW`, etc.) is connected to a net.
   **A floating output pin is always wrong.**
3. In the Python port, confirm no `OUT_*` / `BST_*` / `SW` pin appears
   only inside its component's GND/DVDD/PVDD net — that pattern indicates
   the output filter / bootstrap / switching network was never added (the
   classic GAP-18 module-wrapper miss).

### E. Passive count sanity

Compare approximate passive counts between Stanza and Python:

- Stanza: count `bypass-cap-strap`, `cap-strap`, `res-strap`, and direct
  `inst c : capacitor`/`resistor` calls per module.
- Python: count `Capacitor`, `Resistor`, `Inductor` instances per `Circuit`.
- A discrepancy of more than ~2× per circuit is a strong signal that a
  `pcb-module` wrapper was missed (see workflow.md Phase 3/4 boundary).

### F. Control-signal completeness

1. List every GPIO / control connection in Stanza (`net (ctrl amp.GPIO0)`,
   `net (mute mcu.gpio[3] amp.MUTE)`, etc.).
2. Verify each appears in the Python netlist with the correct number of
   pins on the net.
3. Stanza often wires "tie-off" control signals to the digital supply
   (e.g. `net (VDD amp.PDN_NOT)`). If the design intent is MCU-controlled
   instead, the Python port must wire that pin to an MCU GPIO, not to the
   rail.

### Future automation

A future automated comparator at `scripts/compare-exports.py` (not yet
implemented) is expected to mechanize sections A, B, E, F:

```bash
# FUTURE — not implemented yet
python scripts/compare-exports.py \
    --baseline /tmp/jitx-port/<design>/baseline-3.x \
    --ported   /tmp/jitx-port/<design>/ported-4.x \
    --report   /tmp/jitx-port/<design>/diff-report.html
```

Until then, every porting session should still produce both directories
under `/tmp/jitx-port/<design>/{baseline-3.x,ported-4.x}/` so the future
tool can be retrofit without re-running builds.

## Smoke test

For an end-to-end runnable example of this flow (a small two-resistor design in both versions, with a real `slm.toml` for the 3.x side and a real `pyproject.toml` for the 4.x side), see `runnable-example/` next to this doc.

## Cross-shell hygiene

Don't put both versions on `PATH` in the same shell — both 3.x and 4.x ship a binary named `jitx`. Either:

- **Always invoke by absolute path** (`"$JITX_3X/jitx"`, `"$JITX_4X/jitx"`), as the snippets above do, **or**
- Run each build in its own subshell with only that version's bin on `PATH`:

```bash
( PATH="$JITX_3X:$PATH"; jitx run ... )              # 3.x only
( PATH="$JITX_4X:$PATH"; jitx interactive ... )      # 4.x only
```

Subshells (`( ... )`) discard the env on exit, so the next build starts clean. Don't forget the `~/.jitx/current` symlink update — that's separate from `PATH` and applies process-globally.
