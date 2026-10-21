#!/usr/bin/env python3
"""Log what the runner read in the substrate-api-retrieval case.

Usage:
  grade_retrieval.py reads TRANSCRIPT_JSONL
  grade_retrieval.py compare BEFORE_DIR AFTER_DIR

The case's answers are graded by its judge assertions, one per question.
This script checks only where the answers could have come from.

``reads`` parses the runner's stream-json transcript the way the eval
launcher does (one JSON object per line; any other line is skipped). For each
question with a read check it looks for a tool call whose tool_result is
present, is not an error, and shows a phrase that only that question's
destination text carries, as built. Naming a file is not reading it: an
import, a file listing, a files_with_matches search, or a call with no result
shows no such phrase. The phrase must come from the result, not from the
call's own input. Of a call's input, only its path fields (``file_path``,
``notebook_path``, ``path``) and its ``command`` are read; a ``description``
or any other field is never read. A call that writes a file (Write, Edit,
MultiEdit, NotebookEdit) is never a read.

One rule keeps a run from crediting itself, the draft rule: a call does not
count when it reads back a file the run wrote earlier with the phrase in the
writing call's own input. That covers a draft or an ANSWERS.md written from
memory with Write or Edit (their written text is that input), a shell
redirect or tee, or a Python one-liner. The read-back names the file by its
path, by a relative path or bare name, or by a glob that matches it
(``cat output/*.md``). Where the file sits does not matter: a help() page
saved into the output directory and read back counts, since the phrase came
from help(), not from the writing call.

``compare`` takes two runs of the case, each a directory holding
``transcript.jsonl`` and ``output/``, and prints one line per read-checked
question with its read verdict before and after (``Q9 reads FAIL->PASS``).
It exits 1 when a read goes from PASS to FAIL. When either run has no
transcript or no output/ANSWERS.md, compare reports that run as having
produced no output, lists no reads, and exits 2.

Output of ``reads``: one ``PASS  Qn <topic>`` or ``FAIL  Qn <topic>: <reason>``
line per read-checked question, then a summary line. Exit 0 when every line
passes, 1 when any fails, 2 on a usage error (a transcript that cannot be read
is one: the launcher always writes it). The script prints only its own
wording, never the runner's text, so no runner sentence can make an eval
harness read a red as an environment problem.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Check:
    """A question's read check: ``where`` names its destination as built in a
    FAIL line, and ``phrase`` matches text a tool result shows only when the
    runner read that destination."""

    number: int
    topic: str
    where: str
    phrase: str


CHECKS: tuple[Check, ...] = (
    Check(
        3,
        "generic stackup in a substrate",
        "jitx skill references/architectural-patterns.md section 7",
        r"legitimate inline-subclass case|non-empty body = legitimate",
    ),
    Check(
        5,
        "routing layer units",
        "jitx.si RoutingStructure.Layer.velocity",
        r"in millimeters per second",
    ),
    Check(
        7,
        "ViaFencePattern offset and initial_offset",
        "jitx.constraints ViaFencePattern.offset",
        r"center-to-center distance between fence via rows",
    ),
    Check(
        8,
        "input_shape_only",
        "jitx.constraints ViaFencePattern.input_shape_only",
        r"pre-isolation outline shape of the pour",
    ),
    Check(
        9,
        "Symmetric's last layer",
        "jitx.stackup Symmetric",
        r"last layer must be a :py:class:`Dielectric`",
    ),
    Check(
        10,
        "non-functional pad removal",
        "jitx.via Via.diameters",
        r"where non-functional pads are removed",
    ),
    Check(
        11,
        "backdrill depth",
        "jitx.via Via.backdrill",
        r"sets the depth of a bottom backdrill"
        r"|each backdrill comes from the via's layer span",
    ),
    Check(
        12,
        "decompose results",
        "jitx.inspect decompose",
        r"reading a class attribute through",
    ),
    Check(
        14,
        "material thickness on class and constructor",
        "jitx.stackup Material.thickness",
        r"raises ValueError if both are given",
    ),
    Check(
        15,
        "Dk and Df fields",
        "jitx.stackup Dielectric fields",
        r"the Dk of a datasheet|the Df \(dissipation factor\)",
    ),
    Check(
        18,
        "fenced pour outline example",
        "jitxexamples.patterns.fenced_pour_outline",
        r"generated vias take the pour's net",
    ),
    Check(
        19,
        "phase_velocity closed forms",
        "jitxlib.physics phase_velocity",
        r"half its field lies in each|Hammerstad and Jensen",
    ),
)
"""The questions with a read check. The others have none: the cut SKILL.md
answers them itself, or (Q1, Q4) no destination is needed."""

WRITING_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATH_FIELDS = ("file_path", "notebook_path", "path")
WRITTEN_FIELDS = ("content", "new_string", "new_source")
REDIRECT = re.compile(r"(?:(?<![02-9])>>?|\btee(?:\s+-a)?)\s*([^\s;&|<>()'\"]+)")
WORD = re.compile(r"[^\s'\"`()<>;&|=,]+")
PYTHON_WRITE = re.compile(
    r"""open\(\s*['"]([^'"]+)['"]\s*,\s*['"][wax]"""
    r"""|Path\(\s*['"]([^'"]+)['"]\s*\)\.write_(?:text|bytes)"""
)

Results = list[tuple[Check, str | None]]
Event = dict[str, Any]


def events(transcript: Path) -> list[Event]:
    """Each JSON object in the transcript, one per line, as the eval launcher
    reads it."""
    found: list[Event] = []
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            found.append(event)
    return found


def contents(event: Event) -> list[dict[str, Any]]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict)]


def result_text(content: object) -> str:
    """A tool_result's text, whether it is a string or a list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""


def inspected(name: str, raw: dict[str, Any]) -> list[str]:
    """The parts of a call's input the read log looks at: its path fields and
    its command, and for a writing tool the text it writes."""
    fields = PATH_FIELDS + ("command",)
    if name in WRITING_TOOLS:
        fields += WRITTEN_FIELDS
    found = [raw[f] for f in fields if isinstance(raw.get(f), str)]
    edits = raw.get("edits") if name in WRITING_TOOLS else None
    if isinstance(edits, list):
        found += [
            e["new_string"]
            for e in edits
            if isinstance(e, dict) and isinstance(e.get("new_string"), str)
        ]
    return found


@dataclass(frozen=True)
class Call:
    name: str
    raw: dict[str, Any]
    given: list[str]
    """The parts of the call's input that the read log looks at."""
    output: str | None
    """The result's text, or None when it has no result or errored."""


def calls(evs: list[Event]) -> list[Call]:
    """Each tool call in transcript order, with its result."""
    results: dict[str, str | None] = {}
    for event in evs:
        if event.get("type") != "user":
            continue
        for item in contents(event):
            if item.get("type") != "tool_result":
                continue
            ok = item.get("is_error") is not True
            text = result_text(item.get("content")) if ok else None
            results[str(item.get("tool_use_id"))] = text
    found: list[Call] = []
    for event in evs:
        if event.get("type") != "assistant":
            continue
        for item in contents(event):
            if item.get("type") != "tool_use":
                continue
            raw = item.get("input")
            found.append(
                Call(
                    str(item.get("name")),
                    raw if isinstance(raw, dict) else {},
                    inspected(
                        str(item.get("name")), raw if isinstance(raw, dict) else {}
                    ),
                    results.get(str(item.get("id"))),
                )
            )
    return found


def written(call: Call) -> list[str]:
    """The files a call writes: a writing tool's path, a shell redirect's or
    tee's target, or a file a Python one-liner opens for writing."""
    raw = call.raw
    if call.name in WRITING_TOOLS:
        return [raw[f] for f in PATH_FIELDS if isinstance(raw.get(f), str)]
    command = raw.get("command")
    if call.name != "Bash" or not isinstance(command, str):
        return []
    opened = [a or b for a, b in PYTHON_WRITE.findall(command)]
    targets = REDIRECT.findall(command) + opened
    return [t for t in targets if not t.startswith("/dev/")]


def names(text: str, path: str) -> bool:
    """Whether ``text`` names the file ``path``: by its path, by a relative
    path or bare name that ends it, or by a glob that matches it. A path the
    run wrote relative to its working directory is matched by the tail of an
    absolute one. A directory that holds the file is not the file."""
    path = path.removeprefix("./")
    for word in WORD.findall(text):
        word = word.removeprefix("./")
        if not word or word.endswith("/"):
            continue
        tails = [word]
        if not path.startswith("/"):
            parts = word.split("/")
            depth = len(path.split("/"))
            tails += ["/".join(parts[-depth:])] if len(parts) > depth else []
        if any(fnmatchcase(path, t) or fnmatchcase(path, f"*/{t}") for t in tails if t):
            return True
    return False


def collapsed(text: str) -> str:
    return " ".join(text.split())


def read_results(evs: list[Event]) -> Results:
    found = calls(evs)
    writes = [written(call) for call in found]
    given = [collapsed(" ".join(call.given)) for call in found]
    shown = [collapsed(call.output or "") for call in found]
    candidates = [
        index
        for index, call in enumerate(found)
        if call.output is not None and call.name not in WRITING_TOOLS
    ]
    results: Results = []
    for check in CHECKS:
        drafts = [
            (index, path)
            for index, paths in enumerate(writes)
            if re.search(check.phrase, given[index])
            for path in paths
        ]
        hit = any(
            re.search(check.phrase, shown[index])
            and not re.search(check.phrase, given[index])
            and not any(at < index and names(given[index], path) for at, path in drafts)
            for index in candidates
        )
        why = None if hit else f"no tool result shows the {check.where} text"
        results.append((check, why))
    return results


def report(results: Results) -> int:
    failed = [check for check, why in results if why is not None]
    for check, why in results:
        if why is None:
            print(f"PASS  Q{check.number} {check.topic}")
        else:
            print(f"FAIL  Q{check.number} {check.topic}: {why}")
    if failed:
        numbers = ", ".join(f"Q{check.number}" for check in failed)
        print(f"FAIL  reads: {len(failed)} of {len(results)} failed ({numbers})")
        return 1
    print(f"PASS  reads: all {len(results)} passed")
    return 0


def load_events(transcript: Path) -> list[Event] | None:
    """The transcript's events, or None when it cannot be read."""
    try:
        return events(transcript)
    except OSError:
        return None


def verdict(why: str | None) -> str:
    return "PASS" if why is None else "FAIL"


def compare(before: Path, after: Path) -> int:
    loaded: list[list[Event]] = []
    for label, run in (("before", before), ("after", after)):
        evs = load_events(run / "transcript.jsonl")
        if evs is None:
            print(f"{label}: run produced no output (no transcript.jsonl)")
        elif not (run / "output" / "ANSWERS.md").is_file():
            print(f"{label}: run produced no output (no output/ANSWERS.md)")
        else:
            loaded.append(evs)
    if len(loaded) < 2:
        print("compare: nothing to compare")
        return 2
    verdicts = [
        {check.number: verdict(why) for check, why in read_results(evs)}
        for evs in loaded
    ]
    lost: list[str] = []
    for check in CHECKS:
        n = check.number
        print(f"Q{n} reads {verdicts[0][n]}->{verdicts[1][n]}")
        if verdicts[0][n] == "PASS" and verdicts[1][n] == "FAIL":
            lost.append(f"Q{n}")
    if lost:
        print(f"FAIL  compare: reads lost after ({', '.join(lost)})")
        return 1
    print("PASS  compare: no read went from PASS to FAIL")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    logged = commands.add_parser("reads")
    logged.add_argument("transcript", type=Path)
    compared = commands.add_parser("compare")
    compared.add_argument("before", type=Path)
    compared.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    if args.command == "compare":
        return compare(args.before, args.after)
    evs = load_events(args.transcript)
    if evs is None:
        print("usage error: the transcript cannot be read", file=sys.stderr)
        return 2
    return report(read_results(evs))


if __name__ == "__main__":
    sys.exit(main())
