#!/usr/bin/env python3
"""Show or update one task status in PLAN.md."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PLAN_PATH = Path("PLAN.md")
FIXED_STATUSES = {
    "pending",
    "in-progress",
    "review",
    "accepted",
    "rework",
    "rejected",
}
BLOCKED_STATUS = re.compile(r"blocked: OQ-\d+")
TASK_HEADING = re.compile(r"^### \[([A-Za-z0-9][A-Za-z0-9._-]*)\] .+")
STATUS_ROW = re.compile(r"^- \*\*Status:\*\* (.+?)(\r?\n)?$")
NOTE_SEPARATOR = "; note: "
MAX_NOTE_LENGTH = 120


class PlanStatusError(Exception):
    """A PLAN.md status operation cannot be completed safely."""


def valid_status(value: str) -> bool:
    return value in FIXED_STATUSES or BLOCKED_STATUS.fullmatch(value) is not None


def split_status(value: str) -> tuple[str, str | None]:
    status, separator, note = value.partition(NOTE_SEPARATOR)
    if not valid_status(status):
        raise PlanStatusError(f"invalid status in PLAN.md: {status!r}")
    if separator and not note.strip():
        raise PlanStatusError("empty status note in PLAN.md")
    if separator and len(note) > MAX_NOTE_LENGTH:
        raise PlanStatusError(
            f"status note in PLAN.md exceeds {MAX_NOTE_LENGTH} characters"
        )
    return status, note if separator else None


def parse_tasks(lines: list[str]) -> dict[str, tuple[int, str, str | None]]:
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        match = TASK_HEADING.fullmatch(stripped)
        if match:
            headings.append((index, match.group(1)))
        elif stripped.startswith("### ["):
            raise PlanStatusError(
                f"malformed task heading on line {index + 1}; expected '### [task-id] name'"
            )

    if not headings:
        raise PlanStatusError(
            "PLAN.md has no task headings shaped as '### [task-id] name'"
        )

    tasks: dict[str, tuple[int, str, str | None]] = {}
    for position, (start, task_id) in enumerate(headings):
        if task_id in tasks:
            raise PlanStatusError(f"duplicate task id in PLAN.md: {task_id}")
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        status_rows: list[tuple[int, re.Match[str]]] = []
        for index in range(start + 1, end):
            if index > start + 1 and re.match(r"^#{1,3} ", lines[index]):
                break
            match = STATUS_ROW.match(lines[index])
            if match:
                status_rows.append((index, match))
        if len(status_rows) != 1:
            raise PlanStatusError(
                f"task {task_id} has {len(status_rows)} status rows; expected exactly one"
            )
        row_index, match = status_rows[0]
        status, note = split_status(match.group(1))
        tasks[task_id] = (row_index, status, note)

    task_status_rows = {row_index for row_index, _, _ in tasks.values()}
    orphan_rows = [
        index + 1
        for index, line in enumerate(lines)
        if STATUS_ROW.match(line) and index not in task_status_rows
    ]
    if orphan_rows:
        joined = ", ".join(str(line) for line in orphan_rows)
        raise PlanStatusError(f"status rows outside task records on lines: {joined}")
    return tasks


def load_plan() -> tuple[list[str], dict[str, tuple[int, str, str | None]]]:
    if not PLAN_PATH.is_file():
        raise PlanStatusError(f"{PLAN_PATH} not found in {Path.cwd()}")
    try:
        text = PLAN_PATH.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlanStatusError("PLAN.md is not valid UTF-8") from exc
    lines = text.splitlines(keepends=True)
    return lines, parse_tasks(lines)


def show(task_id: str | None) -> None:
    _, tasks = load_plan()
    if task_id is not None:
        if task_id not in tasks:
            raise PlanStatusError(f"task id not found: {task_id}")
        selected = [(task_id, tasks[task_id])]
    else:
        selected = tasks.items()
    for current_id, (_, status, note) in selected:
        suffix = f"; note: {note}" if note is not None else ""
        print(f"{current_id}: {status}{suffix}")


def update(task_id: str, status: str, note: str | None) -> None:
    if not valid_status(status):
        allowed = ", ".join(sorted(FIXED_STATUSES))
        raise PlanStatusError(
            f"invalid status {status!r}; expected one of {allowed}, or blocked: OQ-<number>"
        )
    if note is not None:
        note = note.strip()
        if not note:
            raise PlanStatusError("--note must not be empty")
        if "\n" in note or "\r" in note:
            raise PlanStatusError("--note must be one line")
        if len(note) > MAX_NOTE_LENGTH:
            raise PlanStatusError(
                f"--note must be at most {MAX_NOTE_LENGTH} characters"
            )

    lines, tasks = load_plan()
    if task_id not in tasks:
        raise PlanStatusError(f"task id not found: {task_id}")

    row_index, old_status, old_note = tasks[task_id]
    ending = "\r\n" if lines[row_index].endswith("\r\n") else "\n"
    if not lines[row_index].endswith(("\n", "\r")):
        ending = ""
    value = status if note is None else f"{status}{NOTE_SEPARATOR}{note}"
    updated_lines = list(lines)
    updated_lines[row_index] = f"- **Status:** {value}{ending}"

    changed = [
        index
        for index, (before, after) in enumerate(zip(lines, updated_lines, strict=True))
        if before != after
    ]
    if changed not in ([], [row_index]):
        raise PlanStatusError(
            "internal error: update would change more than the target row"
        )
    if changed:
        PLAN_PATH.write_bytes("".join(updated_lines).encode("utf-8"))

    old_value = (
        old_status if old_note is None else f"{old_status}{NOTE_SEPARATOR}{old_note}"
    )
    print(f"Updated {task_id}: {old_value} -> {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id", nargs="?")
    parser.add_argument("status", nargs="?")
    parser.add_argument("--note", help="append a one-line note to the status row")
    parser.add_argument(
        "--show",
        nargs="?",
        const="",
        metavar="TASK_ID",
        help="show all task statuses, or one task status",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.show is not None:
            if (
                args.task_id is not None
                or args.status is not None
                or args.note is not None
            ):
                raise PlanStatusError("--show cannot be combined with an update")
            show(args.show or None)
        else:
            if args.task_id is None or args.status is None:
                raise PlanStatusError("update requires <task-id> <status>")
            update(args.task_id, args.status, args.note)
    except PlanStatusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
