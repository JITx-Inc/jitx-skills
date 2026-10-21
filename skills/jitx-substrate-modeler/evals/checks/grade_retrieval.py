#!/usr/bin/env python3
"""Grade the substrate-api-retrieval case: what the runner answered, and what
it read.

Usage:
  grade_retrieval.py answers ANSWERS_MD
  grade_retrieval.py reads TRANSCRIPT_JSONL
  grade_retrieval.py compare BEFORE_DIR AFTER_DIR

``answers`` reads the runner's ANSWERS.md, one section per question, each
under a heading carrying the question's number (``## 1``). Where the file has
no numbered headings, lines that start with the number (``1.``, ``**1.**``,
``Q1:``) mark the sections instead, whichever kind finds more questions. Only
the answer body is graded: the rest of a heading line is not, nor is a
numbered line that restates the question (it ends in ``?``). Lines inside
fenced code blocks never start a section. The sections taken are the longest
run of markers whose numbers rise, among headings of one level or numbered
lines of the least indent, so a document title (``# 19 answers``) or a
numbered list inside an answer does not end it.

Each question has a key: facts its answer must state, as regex alternatives
over the facts rather than the wording, and wrong claims it must not make. A
wrong claim counts unless its own clause rejects it: a negation ("not",
"never", "rather than", "instead of") earlier in the clause, where a clause
ends at ``.``, ``;``, ``:``, ``,``, "so" or a line break, or wording that
follows the claim directly ("is not", "is deprecated", "only through the
UI", or a next clause such as "that disagrees with the docstring"). A
missing answer, and a file that cannot be read, fail.

``reads`` parses the runner's stream-json transcript the way the eval
launcher does (one JSON object per line; any other line is skipped). For each
question with a read check it looks for a tool call whose tool_result is
present, is not an error, and shows a phrase that only that question's
destination text carries, as built. Naming a file is not reading it: an
import, a file listing, a files_with_matches search, or a call with no result
shows no such phrase. The phrase must come from the result, not from the
call's own input, and calls that write files or name ANSWERS.md are skipped.

``compare`` grades two runs of the case, each a directory holding
``output/ANSWERS.md`` and ``transcript.jsonl``, and prints one line per
question with each verdict before and after (``Q7 answers FAIL->PASS``, then
``reads`` where the question has a read check). It exits 1 when any answer
goes from PASS to FAIL.

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
    r"\b(?:not|never|no|nor|neither|avoid|instead of|rather than|in place of|"
    r"unlike|replaces?|don't|do not|doesn't|does not|isn't|is not|aren't|are not|"
    r"wrong|incorrect|deprecated|discontinued)\b|n't\b"
)
"""Wording earlier in a wrong claim's clause that rejects the claim."""

DISOWNED = (
    r"^\W{0,4}(?:(?!but\b|and\b)\w+\W+){0,4}?"
    r"(?:(?:is|are|was|were|does|do)\s+(?:not|never)\b|n't\b"
    r"|\bnot\s+(?:used|needed|supported|the (?:code path|way|answer))\b"
    r"|(?:(?:is|are|was|were)\s+)?(?:deprecated|discontinued|obsolete|wrong|incorrect)"
    r"|only\b[^\n]{0,30}?\b(?:through|in|from) the ui\b)"
)
"""Wording that follows a wrong claim in its clause and rejects it
("NeckDown is not used", "parameters take effect only through the UI")."""

REJECTED_NEXT = (
    r"^\W{0,4}(?:that|which|this)\s+(?:\w+\s+){0,2}?"
    r"(?:disagrees|contradicts|conflicts|is wrong|is incorrect|is outdated)"
)
"""A next clause that rejects the claim before it ("...; that disagrees with
the docstring")."""

CLAUSE_END = re.compile(r"[.;:,!?](?=\s|$)|\n|\bso\b", re.IGNORECASE)


@dataclass(frozen=True)
class Fact:
    """A fact the answer must state: ``label`` names it in a FAIL line."""

    label: str
    pattern: str


@dataclass(frozen=True)
class Wrong:
    """A claim the answer must not assert. ``after`` is extra wording that,
    after the claim in its clause, rejects it."""

    label: str
    pattern: str
    after: str = ""


@dataclass(frozen=True)
class Source:
    """A question's destination as built: ``where`` names it in a FAIL line,
    and ``phrase`` matches text a tool result shows only when the runner read
    that destination."""

    where: str
    phrase: str


@dataclass(frozen=True)
class Key:
    number: int
    topic: str
    facts: tuple[Fact, ...]
    wrong: tuple[Wrong, ...] = ()
    source: Source | None = None
    """The read check, or None for a question with no read check."""


RAISES = r"\b(?:\w*error|raises?|raising|exception|fails?)\b"
NOT_NEGATED = r"(?:(?!not\b|never\b|no\b)\w+\s+)"
"""A word that is not a negation, for patterns that skip a few words."""
OTHER_SKILL = r"(?:/(?!jitx(?![\w-]))[\w-]+|\w+-[\w-]+)"
"""A skill name other than the base jitx skill: hyphenated, or a slash
command."""

KEYS: tuple[Key, ...] = (
    Key(
        1,
        "environment setup skill",
        (
            Fact(
                "the base jitx skill",
                r"(?<![\w/-])/?jitx(?![\w-])[*`]{0,2}\s+(?:base\s+)?skill"
                r"|\bbase\b.{0,30}?(?<![\w-])jitx(?![\w-])"
                r"|(?<![\w-])/jitx(?![\w-])|(?<![\w-])jitx/skill\.md",
            ),
        ),
        (
            Wrong(
                "names another skill for the environment",
                r"(?<![\w/-])" + OTHER_SKILL + r"[*`]{0,2}\s+skill\b"
                r"(?:(?!\bnot\b|n't\b|\bnever\b)[^.;\n]){0,40}?"
                r"\b(?:environment|set(?:s|ting)?\s+up|handles|owns)"
                r"|\b(?:use|invoke|load|run)\s+(?:the\s+)?[*`]{0,2}"
                + OTHER_SKILL
                + r"[*`]{0,2}\s+(?:skill\s+)?first\b",
            ),
        ),
    ),
    Key(
        2,
        "substrate-shaped tables",
        (
            Fact(
                "the table lives on the substrate",
                r"\b(?:on|in|inside|into|onto|to|of|owned by)\s+(?:the|your|a|its)?\s*"
                r"(?:own\s+)?[*`]{0,2}(?:\w+\s+)?\w*substrate\b(?![-_])"
                r"|\bsubstrate\s+(?:should\s+|must\s+)?owns?\b",
            ),
        ),
        (
            Wrong(
                "keeps the table in the design",
                r"\b(?:design|module)[- ]level (?:dict|table|constant|mapping)"
                r"|\b(?:dict|table|constant|mapping)s? in (?:the|your) design\b"
                r"|\b(?:keep|put|place|define|store)\s+(?:it|the (?:table|dict|mapping))"
                r"\s+(?:\w+\s+){0,5}?(?:in|inside)\s+(?:the\s+|your\s+)?design\b",
            ),
        ),
    ),
    Key(
        3,
        "generic stackup in a substrate",
        (Fact("instantiate the generic stackup", r"instantiat|=\s*\w+\(\s*\)"),),
        (
            Wrong(
                "recommends the empty inline subclass",
                r"(?<!if you )(?<!whether to )\b(?:use|write|keep|prefer|go with)\s+"
                r"(?:an?\s+|the\s+)?(?:empty\s+)?`?@inline\s+class\s+\w+\(\s*\w*generic"
                r"|\b(?:use|write|keep|prefer|go with)\s+(?:an?\s+|the\s+)?empty\s+"
                r"`?(?:@inline|inline)",
            ),
            Wrong(
                "says either form works",
                r"\beither (?:\w+ )?works\b|\bboth (?:\w+ )?work\b|\bpick whichever\b",
            ),
        ),
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
                r"\bmm\s*(?:/|per)\s*s(?:ec(?:ond)?)?\b"
                r"|millimet(?:er|re)s? per second|\bmm\s*s\^?-1",
            ),
            Fact(
                "insertion_loss in dB/mm",
                r"\bdb\s*(?:/|per)\s*mm\b|decibels? per millimet(?:er|re)",
            ),
        ),
        (
            Wrong(
                "velocity in m/s",
                r"(?<![\w/])m\s*/\s*s\b|\bmet(?:er|re)s? per second",
            ),
        ),
        Source("jitx.si RoutingStructure.Layer.velocity", r"in millimeters per second"),
    ),
    Key(
        6,
        "pair_spacing",
        (
            Fact(
                "the gap between the P and N conductors",
                r"\bgap\b|edge[- ]to[- ]edge|between (?:their |the )?"
                r"(?:inner |facing |adjacent |near )?edges"
                r"|\b(?:space|spacing|clearance)\s+between\s+(?:the\s+)?(?:two\s+)?"
                r"(?:p\s+and\s+n|conductors|traces|lines)",
            ),
        ),
        (
            Wrong(
                "a centre-to-centre distance",
                r"pair_spacing`?\W{0,3}(?:is|=|means|measures|:)\s*(?:the\s+)?"
                r"(?:\w+\s+){0,2}?(?:cent(?:er|re)[- ]to[- ]cent(?:er|re)|pitch)"
                r"|(?m:^)\W{0,4}(?:it(?:'s| is)\s+)?(?:the\s+)?"
                r"cent(?:er|re)[- ]to[- ]cent(?:er|re)",
            ),
        ),
    ),
    Key(
        7,
        "ViaFencePattern offset and initial_offset",
        (
            Fact(
                "offset is the spacing between rows",
                r"\brow[- ]to[- ]row\b|\brows?\s+(?:spacing|pitch|separation)"
                r"|between (?:the |successive |adjacent |consecutive |two )?"
                r"(?:fence[- ]?)?(?:via )?rows"
                r"|spacing (?:of|between) (?:the )?(?:fence[- ]?)?(?:via )?rows",
            ),
            Fact(
                "initial_offset runs from the boundary to the first row",
                r"initial[_ ]offset.{0,200}?\b(?:boundary|edge|outline|perimeter|border)",
            ),
        ),
        (
            Wrong(
                "measured from the trace centre",
                r"(?:trace|route|line|signal)(?:'s)?\s+cent(?:er|re)(?:\s*line)?\s+to\b"
                r"|cent(?:er|re)\s+of\s+the\s+(?:trace|route|line)"
                r"|trace_width\s*/\s*2\s*\+",
            ),
        ),
        Source(
            "jitx.constraints ViaFencePattern.offset",
            r"center-to-center distance between fence via rows",
        ),
    ),
    Key(
        8,
        "input_shape_only",
        (
            Fact(
                "true fences the pre-isolation outline",
                r"pre-?isolation|before isolation|original (?:pour )?(?:outline|shape)"
                r"|as drawn|input (?:pour )?(?:shape|outline)|un-?isolated",
            ),
            Fact(
                "defaults to true",
                r"default\w*[^.;\n]{0,50}?\btrue\b"
                r"|(?:unset|none|not (?:set|specified|given)|omitted)[^.;\n]{0,30}?\btrue\b"
                r"|true\W{0,3}(?:by default|is the default|\((?:the )?default)",
            ),
        ),
        (
            Wrong(
                "true and false swapped",
                r"\btrue\b\W{0,3}(?:\w+\W+){0,4}?(?:post-?isolation|after isolation)"
                r"|\bfalse\b\W{0,3}(?:\w+\W+){0,4}?(?:pre-?isolation|before isolation)"
                r"|default\w*\W{0,4}(?:is|to|value is|=|:)?\W{0,3}false\b",
            ),
        ),
        Source(
            "jitx.constraints ViaFencePattern.input_shape_only",
            r"pre-isolation outline shape of the pour",
        ),
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
        Source(
            "jitx.stackup Symmetric", r"last layer must be a :py:class:`Dielectric`"
        ),
    ),
    Key(
        10,
        "non-functional pad removal",
        (
            Fact("an nfp diameter", r"\bnfp\b"),
            Fact("on a ViaDiameter", r"viadiameter"),
        ),
        (
            Wrong(
                "says it cannot be done",
                r"\bno\s+(?:api|way|support)\b|\bnot\s+(?:supported|possible|available)\b",
            ),
        ),
        Source("jitx.via Via.diameters", r"where non-functional pads are removed"),
    ),
    Key(
        11,
        "backdrill depth",
        (Fact("the via's stop_layer sets it", r"stop_layer"),),
        (
            Wrong(
                "a depth field on Backdrill",
                r"\bdepth\s*=\s*\.?\d|backdrill`?\.depth\b"
                r"|\b(?:set|use|pass|give)\s+(?:the\s+|a\s+)?`?depth`?\s*"
                r"(?:attribute|field|parameter|argument)"
                r"|backdrill`?\s+has\s+a\s+`?depth",
            ),
        ),
        Source(
            "jitx.via Via.backdrill",
            r"sets the depth of a bottom backdrill"
            r"|each backdrill comes from the via's layer span",
        ),
    ),
    Key(
        12,
        "decompose results",
        (
            Fact("the elements are proxies", r"\bprox(?:y|ies)\b"),
            Fact(
                "subtype fields: decompose by the subtype, or read off the element",
                r"decompose\(\s*[\w.]+\s*,\s*`?(?:dielectric|conductor)\s*\)"
                r"|\bby\s+`?(?:dielectric|conductor)\b|attributeerror|isinstance"
                r"|\b(?:read|access|get)\w*\s+(?:\w+\s+){0,3}?(?:off|from|on)\s+"
                r"(?:the\s+)?element|(?:on|from|off)\s+the\s+element\s+itself",
            ),
        ),
        (
            Wrong(
                "reads fields through type(layer)",
                r"\b(?:read|use|access|go)\w*\s+(?:\w+\s+){0,3}?(?:through|via|with|from)"
                r"\s+`?type\("
                r"|\buse\s+`?type\(\w*\)",
                after=r"\b(?:raises|fails|errors|breaks)\b",
            ),
            Wrong(
                "type(layer) works",
                r"type\(\w*\)(?:\.\w+)?`?\s+(?:works|is fine|is ok|is safe)"
                r"|attributeerror\s+only\s+(?:happens\s+)?(?:for|on|when)\s+unset"
                r"|only\s+(?:for|on)\s+unset\s+fields",
            ),
        ),
        Source("jitx.inspect decompose", r"reading a class attribute through"),
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
        (
            Wrong(
                "the runtime is not started",
                r"\bstart(?:ing)?\s+(?:the\s+)?(?:jitx\s+)?runtime"
                r"|runtime\s+(?:is\s+)?not\s+(?:running|started)"
                r"|runtime\s+(?:starts|is started|is running)",
            ),
        ),
    ),
    Key(
        14,
        "material thickness on class and constructor",
        (
            Fact(
                "one place, never both",
                r"never both|not both|n't (?:\w+ )?both|cannot (?:\w+ )?both"
                r"|one or the other|only one|only in one|\beither\b.{0,80}?\bor\b"
                r"|\bboth\b(?:(?!\.\s)[^\n]){0,60}?(?:raises?|error)"
                r"|(?:raises?|error)\b(?:(?!\.\s)[^\n]){0,80}?\bboth\b",
            ),
            Fact("both raises", RAISES),
        ),
        (Wrong("one overrides the other", r"overrid|takes precedence|\bwins\b"),),
        Source(
            "jitx.stackup Material.thickness", r"raises ValueError if both are given"
        ),
    ),
    Key(
        15,
        "Dk and Df fields",
        (
            Fact("Dk is dielectric_coefficient", r"dielectric_coefficient"),
            Fact("Df is loss_tangent", r"loss_tangent"),
        ),
        source=Source(
            "jitx.stackup Dielectric fields",
            r"the Dk of a datasheet|the Df \(dissipation factor\)",
        ),
    ),
    Key(
        16,
        "via layer indices",
        (
            Fact(
                "conductors only",
                r"(?:conductor|copper)s?\s*(?:\(\w+\)\s*)?(?:layers?\s+)?only"
                r"|only\s+(?:the\s+)?(?:conductor|copper)"
                r"|(?:not|n't|never)\s+(?:\w+\s+){0,2}dielectric"
                r"|dielectrics?\b.{0,40}?(?:not (?:counted|indexed)|take no index"
                r"|have no index|are skipped|are ignored|n't (?:counted|indexed))"
                r"|\bskip\w*\s+(?:the\s+)?dielectric"
                r"|\bindex(?:es)?\s+(?:the\s+)?conductors|\bconductor\s+indices"
                r"|\bcount\w*\s+(?:the\s+)?conductors",
            ),
            Fact(
                "-1 is the bottom conductor",
                r"-1\b.{0,60}?\bbottom|\bbottom\b.{0,60}?-1\b",
            ),
        ),
        (
            Wrong(
                "dielectrics take an index",
                r"\bcount\w*\s+(?:the\s+)?(?:dielectric|every|all)\b"
                r"|dielectrics?\s+(?:layers?\s+)?(?:included|counted|too|as well)"
                r"|every\s+(?:stackup\s+)?layer\s+gets\s+an?\s+index",
            ),
            Wrong(
                "-1 is the solder mask",
                r"-1\b[^.;\n]{0,50}?solder\s*mask|solder\s*mask[^.;\n]{0,30}?(?<![\w-])-1\b",
            ),
        ),
    ),
    Key(
        17,
        "a structure for part of a route",
        (
            Fact(
                "a routing structure rule",
                r"routing_structure|routingstructure|routing structure",
            ),
            Fact("on a tag", r"\btag"),
        ),
        (Wrong("a NeckDown", r"neck[_ -]?down"),),
        Source(
            "jitx.constraints Tag",
            r"Tags are the fundamental building blocks|Tags can be assigned to",
        ),
    ),
    Key(
        18,
        "fenced pour outline example",
        (
            Fact(
                "the jitxexamples fenced_pour_outline pattern",
                r"jitxexamples[./]patterns"
                r"|jitxexamples.{0,200}?fenced_pour_outline"
                r"|fenced_pour_outline.{0,200}?jitxexamples",
            ),
        ),
        source=Source(
            "jitxexamples.patterns.fenced_pour_outline",
            r"Fence vias along an arbitrary closed outline",
        ),
    ),
    Key(
        19,
        "phase_velocity closed forms",
        (
            Fact(
                "the microstrip narrow-strip limit: (3.6 + 1) / 2 = 2.3",
                r"(?<![\d.])2\.30*(?!\d|\.\d)",
            ),
            Fact(
                "the boundary stripline: (3.2 + 3.8) / 2 = 3.5",
                r"(?<![\d.])3\.50*(?!\d|\.\d)",
            ),
            Fact(
                "the real eps_eff is higher, so the limit overstates velocity",
                r"overstat|over-?estimat\w*\s+(?:the\s+)?velocity|\blower bound\b"
                r"|(?:real|true|actual)\s+(?:eps_eff\s+)?" + NOT_NEGATED + r"{0,4}?"
                r"(?:higher|above|larger|greater)\b"
                r"|velocity\s+(?:\w+\s+){0,3}?too\s+(?:high|fast)"
                r"|(?m:^)\W{0,4}(?:\(a\)\W*)?above\b",
            ),
            Fact(
                "the documented error: about 11% for a 50 ohm line",
                r"(?<![\d.])11(?:\.\d+)?\s*(?:%|per ?cent)",
            ),
        ),
        (
            Wrong(
                "the microstrip form on the stripline",
                r"(?<![\d.])2\.250*(?!\d)|\(\s*3\.50*\s*\+\s*1\s*\)",
            ),
            Wrong("averages air in with the dielectrics", r"\+\s*1\s*\)\s*/\s*3"),
            Wrong(
                "fringing lowers the stripline eps_eff",
                r"fring\w*\s+(?:\w+\s+){0,3}?(?:lowers?|reduces?|pulls?\s+(?:it\s+)?down)"
                r"|(?:lower|below|less)\w*\s+(?:\w+\s+){0,4}?(?:because of|due to|from)"
                r"\s+(?:the\s+)?fring",
            ),
            Wrong(
                "the real eps_eff is below the limit",
                r"(?:real|true|actual)\s+(?:eps_eff\s+)?" + NOT_NEGATED + r"{0,4}?"
                r"(?:lower|below|smaller|less)\b"
                r"|understat\w*\s+(?:the\s+)?velocity",
            ),
        ),
        Source(
            "jitxlib.physics phase_velocity",
            r"half its field lies in each|Hammerstad and Jensen",
        ),
    ),
)

DASHES = re.compile("[\u2010-\u2015\u2212]")
QUOTES = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}

HEADING = re.compile(
    r"^ {0,3}(#{1,6})[ \t]*(?:\*\*)?[ \t]*(?:Q(?:uestion)?[ \t]*)?(\d{1,2})(?!\d)",
    re.IGNORECASE,
)
PLAIN = re.compile(
    r"^( {0,3})(?:\*\*)?(?:Q(?:uestion)?[ \t]*)?(\d{1,2})[ \t]*(?:\*\*)?[ \t]*[.):]",
    re.IGNORECASE,
)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def normalize(text: str) -> str:
    """``text`` with dashes and quotes made ASCII and the whitespace in each
    line collapsed; line breaks stay, since they end a clause."""
    text = DASHES.sub("-", text)
    for curly, plain in QUOTES.items():
        text = text.replace(curly, plain)
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


@dataclass(frozen=True)
class Marker:
    number: int
    group: int
    """Heading level, or the indent of a numbered line."""
    line_start: int
    body_start: int


def markers(text: str) -> tuple[list[Marker], list[Marker]]:
    """Every numbered heading and numbered line outside fenced code blocks."""
    headings: list[Marker] = []
    plain: list[Marker] = []
    fence = ""
    offset = 0
    for line in text.splitlines(keepends=True):
        start, offset = offset, offset + len(line)
        opening = FENCE.match(line)
        if fence:
            if opening and opening.group(1)[0] == fence[0]:
                if len(opening.group(1)) >= len(fence):
                    fence = ""
            continue
        if opening:
            fence = opening.group(1)
            continue
        heading = HEADING.match(line)
        if heading:
            number, level = int(heading.group(2)), len(heading.group(1))
            headings.append(Marker(number, level, start, offset))
            continue
        numbered = PLAIN.match(line)
        if numbered:
            rest = line[numbered.end() :].strip().rstrip("*").rstrip()
            body = offset if rest.endswith("?") else start + numbered.end()
            plain.append(
                Marker(int(numbered.group(2)), len(numbered.group(1)), start, body)
            )
    return headings, plain


def rising(found: list[Marker]) -> list[Marker]:
    """The longest run, in file order, of markers whose numbers rise and lie
    in the keyed range; the earliest such run on a tie."""
    found = [m for m in found if 1 <= m.number <= len(KEYS)]
    length = [1] * len(found)
    before = [-1] * len(found)
    for i, marker in enumerate(found):
        for j in range(i):
            if found[j].number < marker.number and length[j] + 1 > length[i]:
                length[i], before[i] = length[j] + 1, j
    if not found:
        return []
    i = max(range(len(found)), key=lambda k: (length[k], -k))
    run: list[Marker] = []
    while i >= 0:
        run.append(found[i])
        i = before[i]
    return run[::-1]


def sections(text: str) -> dict[int, str]:
    """Question number -> its answer body, by numbered headings of one level
    or numbered lines of the least indent, whichever finds more questions."""
    headings, plain = markers(text)
    candidates = [
        rising([m for m in headings if m.group == level])
        for level in sorted({m.group for m in headings})
    ]
    if plain:
        least = min(m.group for m in plain)
        candidates.append(rising([m for m in plain if m.group == least]))
    best = max(candidates, key=len, default=[])
    found: dict[int, str] = {}
    for index, marker in enumerate(best):
        stop = best[index + 1].line_start if index + 1 < len(best) else len(text)
        found[marker.number] = text[marker.body_start : stop]
    return found


def clause_before(text: str, at: int) -> str:
    """The part of the clause that ends at position ``at``."""
    ends = [end for end in CLAUSE_END.finditer(text) if end.end() <= at]
    return text[ends[-1].end() : at] if ends else text[:at]


def clause_after(text: str, at: int) -> str:
    """The rest of the clause from position ``at``."""
    end = CLAUSE_END.search(text, at)
    return text[at : end.start()] if end else text[at:]


def asserted(wrong: Wrong, text: str) -> bool:
    """Whether ``text`` makes the wrong claim rather than rejecting it in the
    claim's own clause."""
    for match in re.finditer(wrong.pattern, text, FLAGS):
        if re.search(NEGATION, clause_before(text, match.start()), re.IGNORECASE):
            continue
        after = clause_after(text, match.end())
        if re.search(DISOWNED, after, re.IGNORECASE):
            continue
        if wrong.after and re.search(wrong.after, after, re.IGNORECASE):
            continue
        end = CLAUSE_END.search(text, match.end())
        if end and re.search(REJECTED_NEXT, clause_after(text, end.end()), re.I):
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


Results = list[tuple[Key, str | None]]


def report(results: Results, what: str) -> int:
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


def answer_results(path: Path) -> Results:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        why = f"ANSWERS.md cannot be read ({type(error).__name__})"
        return [(key, why) for key in KEYS]
    found = sections(text)
    return [(key, grade_answer(key, found.get(key.number))) for key in KEYS]


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


WRITING_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def reads(evs: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(input, output) of each tool call that returned a result, did not
    error, does not write a file and does not name ANSWERS.md; whitespace in
    both is collapsed."""
    results: dict[str, str] = {}
    for event in evs:
        if event.get("type") != "user":
            continue
        for item in contents(event):
            if item.get("type") != "tool_result" or item.get("is_error") is True:
                continue
            results[str(item.get("tool_use_id"))] = result_text(item.get("content"))
    found: list[tuple[str, str]] = []
    for event in evs:
        if event.get("type") != "assistant":
            continue
        for item in contents(event):
            if item.get("type") != "tool_use" or item.get("name") in WRITING_TOOLS:
                continue
            output = results.get(str(item.get("id")))
            given = json.dumps(item.get("input"))
            if output is None or "ANSWERS.md" in given:
                continue
            found.append((" ".join(given.split()), " ".join(output.split())))
    return found


def read_results(evs: list[dict[str, Any]]) -> Results:
    calls = reads(evs)
    results: Results = []
    for key in KEYS:
        if key.source is None:
            continue
        phrase = key.source.phrase
        hit = any(
            re.search(phrase, output) and not re.search(phrase, given)
            for given, output in calls
        )
        why = None if hit else f"no tool result shows the {key.source.where} text"
        results.append((key, why))
    return results


def load_events(transcript: Path) -> list[dict[str, Any]] | None:
    """The transcript's events, or None after a usage error is printed."""
    try:
        return events(transcript)
    except OSError as error:
        print(
            f"usage error: the transcript cannot be read ({type(error).__name__})",
            file=sys.stderr,
        )
        return None


def verdict(why: str | None) -> str:
    return "PASS" if why is None else "FAIL"


def compare(before: Path, after: Path) -> int:
    runs = [
        (d / "output" / "ANSWERS.md", d / "transcript.jsonl") for d in (before, after)
    ]
    first, second = (load_events(transcript) for _, transcript in runs)
    if first is None or second is None:
        return 2
    loaded = [first, second]
    answers = [
        {key.number: verdict(why) for key, why in answer_results(path)}
        for path, _ in runs
    ]
    read = [
        {key.number: verdict(why) for key, why in read_results(evs)} for evs in loaded
    ]
    lost: list[str] = []
    for key in KEYS:
        n = key.number
        line = f"Q{n} answers {answers[0][n]}->{answers[1][n]}"
        if n in read[0]:
            line += f"  reads {read[0][n]}->{read[1][n]}"
        print(line)
        if answers[0][n] == "PASS" and answers[1][n] == "FAIL":
            lost.append(f"Q{n}")
    if lost:
        print(f"FAIL  compare: answers lost after ({', '.join(lost)})")
        return 1
    print("PASS  compare: no answer went from PASS to FAIL")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("answers").add_argument("answers_md", type=Path)
    commands.add_parser("reads").add_argument("transcript", type=Path)
    compared = commands.add_parser("compare")
    compared.add_argument("before", type=Path)
    compared.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    if args.command == "answers":
        return report(answer_results(args.answers_md), "answers")
    if args.command == "compare":
        return compare(args.before, args.after)
    evs = load_events(args.transcript)
    if evs is None:
        return 2
    return report(read_results(evs), "reads")


if __name__ == "__main__":
    sys.exit(main())
