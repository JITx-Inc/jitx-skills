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
  # must be on PATH for SLM to invoke it.
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

```bash
DESIGN=ethernet_io
PORT_DIR=/path/to/ported/${DESIGN}
DESIGN_NAME=runnable_example.main.RunnableExample   # <package>.<module>.<DesignClass>
JITX_4X=~/.jitx/4.1.0                               # adjust
OUT=/tmp/jitx-port/${DESIGN}/ported-4.x
mkdir -p "$OUT"

# Repoint ~/.jitx/current at the 4.x install for this build.
ln -sfn "$(basename "$JITX_4X")" ~/.jitx/current

(
  cd "$PORT_DIR"

  # Project venv with the jitx Python toolchain (pre-release wheels are
  # common). Internal package index access required for `pip install jitx*`.
  python -m venv .venv
  source .venv/bin/activate
  pip install --pre . > "$OUT/pip.log" 2>&1

  # Pre-flight: pyright must be clean.
  pyright . > "$OUT/pyright.txt" 2>&1 || { echo "pyright failed"; exit 1; }

  # Start the interactive server. It writes .socket.jitx in $PWD; the build
  # auto-discovers it by walking up from cwd.
  "$JITX_4X/jitx" interactive "$PWD" > "$OUT/interactive.log" 2>&1 &
  INT_PID=$!
  sleep 2

  # Build. PYTHONPATH=. ensures the project package is importable.
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

## Compare exports — placeholder

Today this step is a manual visual comparison. The skill reserves a future automated comparator at `scripts/compare-exports.py` (not yet implemented), with this expected interface:

```bash
# FUTURE — not implemented yet
python scripts/compare-exports.py \
    --baseline /tmp/jitx-port/<design>/baseline-3.x \
    --ported   /tmp/jitx-port/<design>/ported-4.x \
    --report   /tmp/jitx-port/<design>/diff-report.html
```

The comparator should diff the artifact pairs:

| Artifact | Comparison |
|---|---|
| BOM (CSV) | Sort + diff by part number / value / count. |
| Netlist | Graph isomorphism on (component, pin) ↔ net mapping. |
| Board geometry | Layer-by-layer polygon equivalence. Strict tolerance for component placement; loose for trace routing (the routers differ). |
| Schematic | Out of scope for automation — recommend visual review. |

Until the comparator exists, every porting session should still produce both directories under `/tmp/jitx-port/<design>/{baseline-3.x,ported-4.x}/` so the future tool can be retrofit without re-running builds.

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
