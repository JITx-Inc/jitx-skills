#!/usr/bin/env python3
"""Grade the substrate-api-retrieval case: what the runner answered, and where
it read.

Usage:
  grade_retrieval.py answers ANSWERS_MD
  grade_retrieval.py reads TRANSCRIPT_JSONL

``answers`` reads the runner's ANSWERS.md, one section per question, each
under a heading carrying the question's number (``## 1``). Where the file has
no numbered headings, lines that start with the number (``1.``, ``**1.**``,
``Q1:``) mark the sections instead. A section starts at the first marker whose
number is above the last one taken, so a numbered list inside an answer does
not end it. Each question has a key: facts its answer must state, as regex
alternatives over the facts rather than the wording, and wrong claims it must
not make. A wrong claim counts only when it is asserted: a negation earlier in
the same sentence ("not", "never", "rather than"), or a following "is
deprecated" or "is wrong", turns it into a rejection. A missing answer, and a
file that cannot be read, fail.

``reads`` parses the runner's stream-json transcript the way the eval
launcher does (one JSON object per line; any other line is skipped) and, for each
question with a read target, looks for a tool call that names the target and
did not come back as an error:

- Read: ``file_path``;
- Grep: ``path``, ``glob``, and the two joined;
- Glob: ``path``, ``pattern``, and the two joined;
- Bash: ``command``, where the dotted module (``jitx.si``) also counts.

A Grep's search pattern, a Write or an Edit names no source the runner read,
and a search over a whole package directory that never names the module does
not count. A call whose tool_result has ``is_error`` set (a denied command, a
grep with no match) does not count.

Output: one ``PASS  Qn <topic>`` or ``FAIL  Qn <topic>: <reason>`` line per
question graded, then a summary line. Exit 0 when every line passes, 1 when
any fails, 2 on a usage error (a transcript that cannot be read is one: the
launcher always writes it). The grader prints only its own wording, never the
runner's text, so no runner sentence can make an eval harness read a red as an
environment problem.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FLAGS = re.IGNORECASE | re.DOTALL

NEGATION = (
    r"\b(?:not|never|no|nor|avoid|instead of|rather than|unlike|"
    r"don't|do not|doesn't|does not|isn't|is not|aren't|are not|"
    r"wrong|incorrect|deprecated|discontinued)\b|n't\b"
)
"""Wording before a wrong claim, in the same sentence, that rejects it."""

DISOWNED = (
    r"^\W{0,4}(?:\w+\W+){0,4}?(?:is|are|was|were)?\s*"
    r"(?:deprecated|discontinued|obsolete|wrong|incorrect|"
    r"does not apply|doesn't apply|not supported)\b"
)
"""Wording just after a wrong claim that rejects it ("NeckDown is
discontinued")."""


@dataclass(frozen=True)
class Fact:
    """A fact the answer must state: ``label`` names it in a FAIL line."""

    label: str
    pattern: str


@dataclass(frozen=True)
class Wrong:
    """A claim the answer must not assert. ``after`` is extra wording that,
    just after the claim, rejects it."""

    label: str
    pattern: str
    after: str = ""


@dataclass(frozen=True)
class Key:
    number: int
    topic: str
    facts: tuple[Fact, ...]
    wrong: tuple[Wrong, ...] = ()
    target: str | None = None
    """The read target's name, a key of TARGETS, or None for no read check."""


def module_target(package: str, module: str, *, file: bool) -> str:
    """A pattern naming ``package/module(.py)`` as a path or ``package.module``
    as a dotted import."""
    path = rf"{package}/{module}\.py" if file else rf"{package}/{module}"
    return rf"(?<![\w.-]){path}(?![\w-])|(?<![\w.]){package}\.{module}(?!\w)"


TARGETS: dict[str, str] = {
    "architectural-patterns.md": r"(?<![\w-])architectural-patterns\.md",
    "jitx/si.py": module_target("jitx", "si", file=True),
    "jitx/constraints.py": module_target("jitx", "constraints", file=True),
    "jitx/stackup.py": module_target("jitx", "stackup", file=True),
    "jitx/via.py": module_target("jitx", "via", file=True),
    "jitx/inspect.py": module_target("jitx", "inspect", file=True),
    "jitx/test.py": module_target("jitx", "test", file=True),
    "jitxexamples/patterns": module_target("jitxexamples", "patterns", file=False),
    "jitxlib/physics": module_target("jitxlib", "physics", file=False),
}
"""Read target -> a pattern that finds it in a tool call's path or command."""

RAISES = r"\b(?:\w*error|raises?|raising|exception|fails?)\b"

KEYS: tuple[Key, ...] = (
    Key(
        1,
        "environment setup skill",
        (
            Fact(
                "the base jitx skill",
                r"\bbase\b.{0,30}?(?<![\w-])jitx(?![\w-])"
                r"|(?<![\w/-])jitx`?\s+skill|(?<![\w-])jitx/skill\.md",
            ),
        ),
    ),
    Key(
        2,
        "substrate-shaped tables",
        (
            Fact(
                "the table lives on the substrate",
                r"\b(?:on|in|inside|into|onto|to|owned by)\s+(?:the|your|a|its)?\s*"
                r"(?:own\s+)?(?:\w+\s+)?substrate\b(?![-_])",
            ),
        ),
        (
            Wrong(
                "keeps the table in the design",
                r"\b(?:design|module)[- ]level (?:dict|table|constant|mapping)"
                r"|\b(?:dict|table|constant|mapping)s? in (?:the|your) design\b",
            ),
        ),
        "architectural-patterns.md",
    ),
    Key(
        3,
        "generic stackup in a substrate",
        (Fact("instantiate the generic stackup", r"instantiat|=\s*\w+\(\s*\)"),),
        (
            Wrong(
                "recommends the empty inline subclass",
                r"\b(?:use|write|keep|prefer|go with)\s+(?:an?\s+|the\s+)?(?:empty\s+)?"
                r"`?(?:@inline|inline[- ]subclass)",
            ),
        ),
        "architectural-patterns.md",
    ),
    Key(
        4,
        "sharing vias between substrates",
        (
            Fact(
                "ordinary Python reuse",
                r"inherit|mix-?in|base class|parent class|subclass"
                r"|module[- ]level|\bimport\b",
            ),
        ),
        (
            Wrong(
                "copy the vias or say they cannot be shared",
                r"(?:can't|cannot|can not) (?:be )?shar"
                r"|\bcop(?:y|ies|ying) (?:the |each |every |them )?"
                r"(?:via )?(?:class(?:es)?|definitions?|them)? ?(?:into|to|in) "
                r"(?:both|each)",
            ),
        ),
    ),
    Key(
        5,
        "routing layer units",
        (
            Fact(
                "velocity in mm/s",
                r"\bmm\s*/\s*s\b|millimet(?:er|re)s? per second|\bmm\s*s\^?-1",
            ),
            Fact(
                "insertion_loss in dB/mm",
                r"\bdb\s*/\s*mm\b|decibels? per millimet(?:er|re)",
            ),
        ),
        target="jitx/si.py",
    ),
    Key(
        6,
        "pair_spacing",
        (
            Fact(
                "the gap between the P and N conductors",
                r"\bgap\b|edge[- ]to[- ]edge|between (?:their |the )?"
                r"(?:inner |facing |adjacent |near )?edges",
            ),
        ),
        (
            Wrong(
                "a centre-to-centre distance",
                r"cent(?:er|re)[- ]to[- ]cent(?:er|re)|\bpitch\b",
            ),
        ),
        "jitx/si.py",
    ),
    Key(
        7,
        "ViaFencePattern offset and initial_offset",
        (
            Fact(
                "offset is the spacing between rows",
                r"\brow[- ]to[- ]row\b|\brows?\s+(?:spacing|pitch|separation)"
                r"|between (?:the |successive |adjacent |two )?(?:fence[- ]?via )?rows"
                r"|spacing (?:of|between) (?:the )?(?:fence[- ]?via )?rows",
            ),
            Fact(
                "initial_offset runs from the boundary to the first row",
                r"initial[_ ]offset.{0,200}?\b(?:boundary|edge|outline|perimeter|border)",
            ),
            Fact(
                "offset is the default initial_offset",
                r"\bdefault|\bunset\b|not (?:set|given|specified)"
                r"|\bomit|falls? back|\bif (?:you )?(?:leave|don't set)",
            ),
        ),
        (
            Wrong(
                "measured from the trace centre",
                r"(?:trace|route|line|signal)(?:'s)?\s+cent(?:er|re)(?:\s*line)?\s+to\b"
                r"|trace_width\s*/\s*2\s*\+",
            ),
        ),
        "jitx/constraints.py",
    ),
    Key(
        8,
        "input_shape_only",
        (
            Fact(
                "true fences the pre-isolation outline",
                r"pre-?isolation|before isolation|original (?:pour )?(?:outline|shape)"
                r"|as drawn|input (?:shape|outline)|un-?isolated",
            ),
            Fact(
                "defaults to true",
                r"defaults?\W{0,3}(?:is|to|value is|=|:)?\W{0,3}true"
                r"|true\W{0,3}(?:by default|is the default|\((?:the )?default)",
            ),
        ),
        target="jitx/constraints.py",
    ),
    Key(
        9,
        "Symmetric's last layer",
        (
            Fact("the last layer is a dielectric", r"\bdielectric\b"),
            Fact("anything else raises", RAISES),
        ),
        (
            Wrong(
                "the last layer is a conductor",
                r"(?:must|has to|should|needs to) be (?:a |the )?(?:conductor|copper)",
            ),
        ),
        "jitx/stackup.py",
    ),
    Key(
        10,
        "non-functional pad removal",
        (
            Fact("an nfp diameter", r"\bnfp\b"),
            Fact("on a ViaDiameter", r"viadiameter"),
        ),
        target="jitx/via.py",
    ),
    Key(
        11,
        "backdrill depth",
        (Fact("the via's stop_layer sets it", r"stop_layer"),),
        (Wrong("a depth field", r"\bdepth\s*=|backdrill\([^)]*\bdepth\b"),),
        "jitx/via.py",
    ),
    Key(
        12,
        "decompose results",
        (
            Fact("the elements are proxies", r"\bprox(?:y|ies)\b"),
            Fact(
                "subtype fields: decompose by the subtype, or read off the element",
                r"decompose\(\s*\w+\s*,\s*(?:dielectric|conductor)\s*\)"
                r"|\bby\s+`?(?:dielectric|conductor)\b|attributeerror",
            ),
        ),
        target="jitx/inspect.py",
    ),
    Key(
        13,
        "empty stackup in a test",
        (
            Fact("no instantiation context", r"instantiation|context"),
            Fact(
                "subclass jitx.test.TestCase",
                r"jitx\.test\b|jitx's (?:own )?testcase|jitx testcase",
            ),
        ),
        target="jitx/test.py",
    ),
    Key(
        14,
        "material thickness on class and constructor",
        (
            Fact(
                "one place, never both",
                r"never both|not both|n't (?:\w+ )?both|cannot (?:\w+ )?both"
                r"|one or the other|only one|\beither\b.{0,80}?\bor\b",
            ),
            Fact("both raises", RAISES),
        ),
        (Wrong("one overrides the other", r"overrid|takes precedence|\bwins\b"),),
        "jitx/stackup.py",
    ),
    Key(
        15,
        "Dk and Df fields",
        (
            Fact("Dk is dielectric_coefficient", r"dielectric_coefficient"),
            Fact("Df is loss_tangent", r"loss_tangent"),
        ),
        target="jitx/stackup.py",
    ),
    Key(
        16,
        "via layer indices",
        (
            Fact(
                "conductors only",
                r"conductors?\s+(?:layers?\s+)?only|only\s+(?:the\s+)?(?:conductor|copper)"
                r"|copper\s+(?:layers?\s+)?only"
                r"|(?:not|n't|never)\s+(?:\w+\s+){0,2}dielectric"
                r"|dielectrics?\b.{0,40}?(?:not (?:counted|indexed)|take no index"
                r"|have no index|are skipped|n't (?:counted|indexed))",
            ),
            Fact(
                "-1 is the bottom conductor",
                r"-1\b.{0,60}?\bbottom|\bbottom\b.{0,60}?-1\b",
            ),
        ),
    ),
    Key(
        17,
        "a structure for part of a route",
        (
            Fact("a routing_structure rule", r"routing_structure"),
            Fact("on a tag", r"\btag"),
        ),
        (Wrong("a NeckDown", r"neck[_ -]?down"),),
        "jitx/constraints.py",
    ),
    Key(
        18,
        "fenced pour outline example",
        (
            Fact("a Tag", r"\btag"),
            Fact("a fence_via rule", r"fence_via"),
            Fact("a tagged pour", r"\bpours?\b"),
        ),
        target="jitxexamples/patterns",
    ),
    Key(
        19,
        "stripline eps_eff",
        (
            Fact(
                "one dielectric: eps_eff = Dk = 4.0", r"(?<![\d.])4(?:\.0+)?(?!\d|\.\d)"
            ),
            Fact("two dielectrics: (3.9 + 4.3) / 2 = 4.1", r"(?<![\d.])4\.10*(?![\d])"),
        ),
        (
            Wrong(
                "the microstrip form",
                r"(?<![\d.])2\.50*(?!\d)|\(\s*(?:4(?:\.0+)?|er|dk|eps_r)\s*\+\s*1\s*\)\s*/\s*2",
                after=r"^.{0,60}?\bmicrostrip\b",
            ),
        ),
        "jitxlib/physics",
    ),
)

DASHES = re.compile("[\u2010-\u2015\u2212]")
QUOTES = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}

HEADING = re.compile(
    r"^ {0,3}#{1,6}[ \t]*(?:\*\*)?[ \t]*(?:Q(?:uestion)?[ \t]*)?(\d{1,2})(?!\d)",
    re.IGNORECASE | re.MULTILINE,
)
PLAIN = re.compile(
    r"^ {0,3}(?:\*\*)?(?:Q(?:uestion)?[ \t]*)?(\d{1,2})[ \t]*(?:\*\*)?[ \t]*[.):]",
    re.IGNORECASE | re.MULTILINE,
)


def normalize(text: str) -> str:
    """``text`` with dashes and quotes made ASCII and the whitespace in each
    line collapsed; line breaks stay, since they end a sentence."""
    text = DASHES.sub("-", text)
    for curly, plain in QUOTES.items():
        text = text.replace(curly, plain)
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def sections(text: str) -> dict[int, str]:
    """Question number -> its answer text, by numbered headings when the file
    has any, else by numbered lines."""
    count = len(KEYS)
    for marker in (HEADING, PLAIN):
        starts: list[tuple[int, int, int]] = []
        for match in marker.finditer(text):
            number = int(match.group(1))
            if starts and number <= starts[-1][0]:
                continue
            if 1 <= number <= count:
                starts.append((number, match.start(), match.end()))
        if starts:
            found: dict[int, str] = {}
            for index, (number, _, end) in enumerate(starts):
                stop = starts[index + 1][1] if index + 1 < len(starts) else len(text)
                found[number] = text[end:stop]
            return found
    return {}


def sentence_before(text: str, at: int) -> str:
    """The part of the sentence before position ``at``."""
    before = text[:at]
    cut = max(before.rfind("\n"), before.rfind(". "), before.rfind("; "))
    return before[cut + 1 :][-80:]


def asserted(wrong: Wrong, text: str) -> bool:
    """Whether ``text`` makes the wrong claim rather than rejecting it."""
    for match in re.finditer(wrong.pattern, text, FLAGS):
        if re.search(NEGATION, sentence_before(text, match.start()), re.IGNORECASE):
            continue
        after = text[match.end() : match.end() + 80].split("\n", 1)[0]
        if re.search(DISOWNED, after, re.IGNORECASE):
            continue
        if wrong.after and re.search(wrong.after, after, re.IGNORECASE):
            continue
        return True
    return False


def grade_answer(key: Key, answer: str | None) -> str | None:
    """Why ``answer`` fails ``key``, or None when it passes."""
    if answer is None or not normalize(answer):
        return "no answer"
    text = normalize(answer)
    missing = [f.label for f in key.facts if not re.search(f.pattern, text, FLAGS)]
    if missing:
        return "does not state " + "; ".join(missing)
    claims = [w.label for w in key.wrong if asserted(w, text)]
    if claims:
        return "claims " + "; ".join(claims)
    return None


def report(results: list[tuple[Key, str | None]], what: str) -> int:
    failed = [key for key, why in results if why is not None]
    for key, why in results:
        if why is None:
            print(f"PASS  Q{key.number} {key.topic}")
        else:
            print(f"FAIL  Q{key.number} {key.topic}: {why}")
    if failed:
        numbers = ", ".join(f"Q{key.number}" for key in failed)
        print(f"FAIL  {what}: {len(failed)} of {len(results)} failed ({numbers})")
        return 1
    print(f"PASS  {what}: all {len(results)} passed")
    return 0


def grade_answers(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        why = f"ANSWERS.md cannot be read ({type(error).__name__})"
        return report([(key, why) for key in KEYS], "answers")
    found = sections(text)
    return report(
        [(key, grade_answer(key, found.get(key.number))) for key in KEYS], "answers"
    )


def events(transcript: Path) -> list[dict[str, Any]]:
    """Each JSON object in the transcript, one per line, as the eval launcher
    reads it."""
    found: list[dict[str, Any]] = []
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            found.append(event)
    return found


def contents(event: dict[str, Any]) -> list[dict[str, Any]]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict)]


def joined(directory: object, name: object) -> list[str]:
    parts = [p for p in (directory, name) if isinstance(p, str) and p]
    if len(parts) == 2:
        parts.append(parts[0].rstrip("/") + "/" + parts[1])
    return parts


def named(tool: object, given: object) -> list[str]:
    """The strings a tool call names a source by."""
    if not isinstance(given, dict):
        return []
    if tool == "Read":
        return [v for v in (given.get("file_path"),) if isinstance(v, str)]
    if tool == "Grep":
        return joined(given.get("path"), given.get("glob"))
    if tool == "Glob":
        return joined(given.get("path"), given.get("pattern"))
    if tool == "Bash":
        return [v for v in (given.get("command"),) if isinstance(v, str)]
    return []


def reads(evs: list[dict[str, Any]]) -> list[str]:
    """What every tool call that did not error names."""
    errored = {
        item.get("tool_use_id")
        for event in evs
        if event.get("type") == "user"
        for item in contents(event)
        if item.get("type") == "tool_result" and item.get("is_error") is True
    }
    found: list[str] = []
    for event in evs:
        if event.get("type") != "assistant":
            continue
        for item in contents(event):
            if item.get("type") == "tool_use" and item.get("id") not in errored:
                found += named(item.get("name"), item.get("input"))
    return found


def grade_reads(transcript: Path) -> int:
    try:
        evs = events(transcript)
    except OSError as error:
        print(
            f"usage error: the transcript cannot be read ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    seen = reads(evs)
    results: list[tuple[Key, str | None]] = []
    for key in KEYS:
        if key.target is None:
            continue
        hit = any(re.search(TARGETS[key.target], s) for s in seen)
        why = (
            None
            if hit
            else f"no Read, Grep, Glob or Bash call that succeeded names {key.target}"
        )
        results.append((key, why))
    return report(results, "reads")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("answers").add_argument("answers_md", type=Path)
    commands.add_parser("reads").add_argument("transcript", type=Path)
    args = parser.parse_args(argv)
    if args.command == "answers":
        return grade_answers(args.answers_md)
    return grade_reads(args.transcript)


if __name__ == "__main__":
    sys.exit(main())
