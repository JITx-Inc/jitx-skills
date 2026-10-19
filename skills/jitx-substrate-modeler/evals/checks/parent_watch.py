"""End a grading child once grade_substrate.py, its parent, is gone.

Usage: call ``watch_parent()`` first thing in a child grade_substrate.py
starts (import_candidate.py and substrate_grader.py do). A board that hangs,
and anything it started, then does not outlive the grader. The watch is on
only when GRADE_SUBSTRATE_PID names the parent, so a child run by hand is left
alone.

Exit code: a child whose parent is gone and that leads its own process group,
as each child grade_substrate.py starts does, dies with the group by SIGKILL;
one that leads no group exits 1. POSIX only: it uses process groups and
SIGKILL.
"""

from __future__ import annotations

import os
import signal
import threading
import time

PARENT = "GRADE_SUBSTRATE_PID"
"""The environment variable through which grade_substrate.py names itself."""


def end_group() -> None:
    """Kill this process's group when it leads one, else just this process."""
    if os.getpgrp() == os.getpid():
        os.killpg(os.getpid(), signal.SIGKILL)
    os._exit(1)


def watch_parent(interval: float = 0.2) -> None:
    """Start a daemon thread that ends this process when its parent dies."""
    # grade_substrate.py starts each child in its own process group, so a
    # signal sent to grade_substrate.py or to its group does not reach the
    # child. Its handlers kill the child's group for the signals they can
    # catch; for the one they cannot (SIGKILL), the child watches for its
    # parent's death here and kills its own group.
    named = os.environ.get(PARENT, "").strip()
    if not named:
        return
    parent = int(named)
    if os.getppid() != parent:
        end_group()

    def watch() -> None:
        while os.getppid() == parent:
            time.sleep(interval)
        end_group()

    threading.Thread(target=watch, name="parent-watch", daemon=True).start()
