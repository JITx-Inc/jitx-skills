# 4.x Bootstrap & Run

**Canonical source** for the order-sensitive startup sequence required to
run any JITX 4.x design. Other skills (`jitx-port-3-to-4`, per-design
`CLAUDE.md` files) link to this file rather than duplicating it.

A `python -m jitx build` invocation cannot succeed in isolation. It needs:

- the right install selected via the `~/.jitx/current` symlink,
- an active `jitx sign-in`,
- a running `jitx interactive` backend server,
- a `.socket.jitx` file written by that server (do not race it),
- the project pip-installed into a venv,
- `JITX_SKIP_STABILIZE_CONFIRMATION=1` so the build doesn't hang on a
  confirmation prompt.

Skip or reorder any of these and the build either silently hangs or fails
with an opaque error. The most common symptoms are catalogued at the
bottom of this file.

## Ordering checklist

The steps below are **order-sensitive**. Do not change the order.

1. **Symlink first**: `ln -sfn <version> ~/.jitx/current` — must point at
   the install you're about to use **before** launching `jitx interactive`.
   The interactive server reads runtime state via `~/.jitx/current/`; a
   stale symlink poisons the build (typically with the obscure
   `FATAL PLUGIN ERROR: No appropriate branch for arguments of type
   (False)` in `StableBoardSerializer/write-stable-id`).
2. **Sign in once** (if not already):
   `~/.jitx/<version>/jitx sign-in -email <email>`. `python -m jitx build`
   fails authentication if the user is not signed in, with no hint that
   sign-in is the missing step. Auth state is shared across versioned
   installs, so this only needs to happen once per machine + user.
   Headless: pipe the password in via stdin
   (`<<<"$JITX_USER_PASS"`).
3. **Start the interactive server**:
   `~/.jitx/<version>/jitx interactive $(pwd) &`. ⚠️ `interactive` is
   **not** listed in `jitx --help` — this is a known quirk, not a missing
   binary. Without it, the build fails with `Unable to determine socket URI`.
4. **Wait for the socket** before issuing any build: the server takes a
   few seconds to write `.socket.jitx` into the project directory. Use a
   real wait, not a fixed `sleep`:
   `until [ -e .socket.jitx ]; do sleep 1; done`.
5. **Install the project**: `pip install --pre .` inside a venv. The
   server must already be up — some `pip install` paths exercise jitx
   imports that need the server. (Some projects use
   `uv sync --active --prerelease=allow` instead.)
6. **Verify version match**:
   `python -c 'import jitx; print(jitx.__version__)'` should match
   `readlink ~/.jitx/current`. Mismatches may work but cause subtle API
   drift; flag them.
7. **Build headless**: prefix with `JITX_SKIP_STABILIZE_CONFIRMATION=1`.
   Without this env var, `python -m jitx build` pauses interactively
   asking "save stable design?" and hangs any CI / unattended run.

## Worked snippet (generic)

```bash
JITX_VER=4.1.0                                  # adjust to your install
DESIGN_NAME=<package>.<module>.<DesignClass>    # see `python -m jitx find .`

# (1) Repoint ~/.jitx/current at the install before doing anything else.
ln -sfn "$JITX_VER" ~/.jitx/current

# (2) Sign in (once per session; auth state shared across installs).
~/.jitx/$JITX_VER/jitx sign-in -email "$JITX_USER_EMAIL" <<<"$JITX_USER_PASS"

(
  # All subsequent steps run with cwd = the project root.
  cd "$PROJECT_DIR"

  # (3) Start the interactive server. It writes .socket.jitx in $PWD;
  # the build auto-discovers it by walking up from cwd.
  ~/.jitx/$JITX_VER/jitx interactive "$PWD" &
  INT_PID=$!

  # (4) Wait for the socket file rather than a fixed sleep.
  until [ -e .socket.jitx ]; do sleep 1; done

  # (5) Project venv with the jitx Python toolchain.
  python -m venv .venv
  source .venv/bin/activate
  pip install --pre .

  # (6) Sanity-check that the pip-installed jitx matches ~/.jitx/current.
  python -c 'import jitx; print(jitx.__version__)'
  readlink ~/.jitx/current

  # (7) Build headless. JITX_SKIP_STABILIZE_CONFIRMATION=1 suppresses the
  # interactive "save stable design?" prompt. PYTHONPATH=$PWD ensures the
  # project package is importable if not installed.
  JITX_SKIP_STABILIZE_CONFIRMATION=1 \
      PYTHONPATH="$PWD" python -m jitx build "$DESIGN_NAME"

  kill "$INT_PID" 2>/dev/null
)
```

## Common startup failures

| Symptom | Cause |
|---|---|
| `Unable to determine socket URI` | `jitx interactive` not running, or socket not yet written — see step (3)/(4) |
| `You are not authenticated. Please sign in through the JITX Sidebar in VSCode.` | Missing sign-in (step 2) |
| Build hangs at "save stable design?" | Missing `JITX_SKIP_STABILIZE_CONFIRMATION=1` (step 7) |
| `FATAL PLUGIN ERROR: No appropriate branch for arguments of type (False)` in `write-stable-id` | `~/.jitx/current` symlink mismatch — see step (1) |
| `pip install` errors importing jitx mid-install | `jitx interactive` not yet up, or version mismatch between symlink and installed wheel |
| `ModuleNotFoundError: No module named 'jitx'` after `pip install --pre .` succeeded | Wrong venv active; re-run `source .venv/bin/activate` |

## Parallel installs

JITX releases install per-version under `~/.jitx/<version>/` and multiple
versions can coexist. The 3.x line (Stanza) and 4.x line (Python) share
the binary name `jitx`, so invoke each by absolute path or use isolated
subshells with only one version's `bin/` on `PATH`.

`~/.jitx/current` is the active-version selector — JITX reads runtime,
config, and plugin state via `~/.jitx/current/...` regardless of which
versioned binary you launched. Repoint it (step 1) whenever you alternate
between installs.

The `jitx-port-3-to-4` skill's `references/verification.md` covers the
parallel-install patterns in more depth (pre-port 3.x baseline vs
post-port 4.x build, etc.).

## Output files

After a successful build, expect:

- `designs/<design_name>/cache/netlist.json` — JSON netlist for verification
- `designs/<design_name>/cache/design-explorer.json` — design hierarchy
- `designs/<design_name>/design-info/stable.design` — design snapshot
