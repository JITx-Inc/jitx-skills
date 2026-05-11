#!/usr/bin/env python3
"""
JITX build wrapper with file-locked invocation.

Acquires an exclusive file lock before running `jitx build`. This serializes
the build calls themselves when parallel agents share a project, which
*reduces* — but does not eliminate — the risk of conflicts: cache state,
build artifacts, and WebSocket session state extend past the build call,
so concurrent work on the same design remains risky.

Working on the same JITX design in parallel is not recommended. For
genuinely independent work, sequence tasks against the same design or
run parallel agents on different projects.

Note: Uses fcntl for file locking (Unix/macOS only). Not supported on Windows.

Usage (CLI):
    python build_lock.py <module.path.DesignClass>
    python build_lock.py <module.path.DesignClass> --timeout 600
    python build_lock.py <module.path.DesignClass> --lock-dir /tmp

Usage (Python):
    from build_lock import jitx_build
    ok, output = jitx_build("myproject.main.Design")

Setup:
    Copy this script into your project (e.g., runner/build_lock.py) so
    sub-agents can invoke it directly. The lock file is created in the
    lock directory (default: current working directory).
"""

import argparse
import fcntl
import subprocess
import sys
from pathlib import Path


def jitx_build(
    module_path: str,
    timeout: int = 300,
    lock_dir: Path | None = None,
) -> tuple[bool, str]:
    """Run `jitx build <module_path>` under an exclusive file lock.

    Returns (success, combined_stdout_stderr).
    """
    lock_dir = lock_dir or Path.cwd()
    lock_file = lock_dir / ".jitx-build.lock"
    python = _find_python()

    with open(lock_file, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            result = subprocess.run(
                [python, "-m", "jitx", "build", module_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (result.stdout + "\n" + result.stderr).strip()
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"Build timed out after {timeout}s"
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _find_python() -> str:
    """Use the project venv python if available, else the current interpreter."""
    venv = Path.cwd() / ".venv" / "bin" / "python"
    if venv.exists():
        return str(venv)
    return sys.executable


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serialized JITX build wrapper for parallel agent safety.",
    )
    parser.add_argument(
        "module_path",
        help="Module path for jitx build (e.g., myproject.main.Design)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Build timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--lock-dir",
        type=str,
        default=".",
        help="Directory for the .jitx-build.lock file (default: cwd)",
    )
    args = parser.parse_args()

    ok, output = jitx_build(args.module_path, args.timeout, Path(args.lock_dir))
    print(output)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
