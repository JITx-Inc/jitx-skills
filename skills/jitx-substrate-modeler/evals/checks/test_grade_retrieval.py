"""grade_retrieval.py passes a correct answer however it is phrased, fails a
plausible wrong one, and finds a read exactly where the transcript shows one.

Every test drives the grader's CLI as the case runs it, so the file read, the
section parsing, the stream-json parsing and the exit code are all in the
path. Answer keys are tested by table: per question, two correct paraphrases
that must pass and one plausible wrong answer that must fail.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

CHECKS = Path(__file__).resolve().parent
SKILL = CHECKS.parents[1]
REPO = SKILL.parents[1]
GRADER = CHECKS / "grade_retrieval.py"
CASE = SKILL / "evals" / "cases" / "substrate-api-retrieval.json"
CASE_E = CHECKS / "testdata" / "case_e"
ANSWERS = CASE_E / "ANSWERS.md"
READS_ALL = CASE_E / "transcript_reads_all.jsonl"
READS_NONE = CASE_E / "transcript_reads_none.jsonl"

QUESTIONS = range(1, 20)
READ_CHECKED = [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19]

LINE = re.compile(r"^(PASS|FAIL)  Q(\d+) ")

# Per question: (correct paraphrase A, correct paraphrase B, plausible wrong).
ROWS: dict[int, tuple[str, str, str]] = {
    1: (
        "Use the jitx skill first (skills/jitx/SKILL.md); it handles environment setup.",
        "The base jitx skill sets up the environment; invoke it before the substrate work.",
        "The jitx-substrate-modeler skill sets up the environment itself; no other skill"
        " is needed.",
    ),
    2: (
        "They belong to the substrate class, as attributes or properties the design"
        " queries, e.g. `self.substrate.via[(a, b)]`.",
        "Put substrate-shaped data in the substrate, not as module-level dicts in the"
        " design file; the design reads them from `self.substrate`.",
        "Keep a module-level dict in the design file mapping each signal layer to its"
        " via class.",
    ),
    3: (
        "Instantiate it: `stackup = Generic_Stackup()` inside the Substrate. Don't use"
        " an empty inline subclass.",
        "Write `stackup = Generic_Stackup()`. `@inline class stackup(Generic_Stackup):"
        " pass` with an empty body is a pass-through subclass; inline-subclassing is only"
        " for a body that declares layers.",
        "Use `@inline class stackup(Generic_Stackup): pass` inside the Substrate; that"
        " is the canonical pattern.",
    ),
    4: (
        "Define them once in a base class and have both substrates subclass it"
        " (multiple inheritance).",
        "Nothing JITX-specific: declare the vias in a mixin and list it as a second"
        " parent of each Substrate class.",
        "Via classes can't be shared between substrates; copy each via class into both"
        " substrate classes.",
    ),
    5: (
        "velocity: millimeters per second. insertion_loss: decibels per millimeter.",
        "velocity is mm/s (not m/s) and insertion_loss is dB/mm.",
        "velocity is in m/s and insertion_loss in dB/m.",
    ),
    6: (
        "Edge\u2011to\u2011edge spacing between the two traces of the pair, in mm.",
        "pair_spacing is the gap between P and N, measured edge to edge rather than"
        " centre to centre.",
        "The centre-to-centre distance between the P and N traces.",
    ),
    7: (
        "offset is the row-to-row spacing of the fence; initial_offset is the distance"
        " from the edge of the route or pour to the first row's via centres. If"
        " initial_offset is not given, offset is used.",
        "`offset`: centre-to-centre distance between rows of fence vias, and the default"
        " initial offset. `initial_offset`: from the route or feature boundary out to"
        " the centres of the first row (positive outwards).",
        "offset is measured from the trace centre to the via centre: trace_width/2 +"
        " gap + via pad radius. initial_offset is the distance from the edge to the"
        " first row, defaulting to offset.",
    ),
    8: (
        "Pour-only flag. True (the default) fences the input shape, the outline as"
        " drawn before isolation; False fences the isolated copper.",
        "If true, the fence uses the pre-isolation outline of the pour; if false, the"
        " post-isolation shape. Default: true.",
        "It makes the fence follow only the post-isolation copper; it defaults to False.",
    ),
    9: (
        "It has to be a dielectric, the symmetry plane; a conductor there raises a"
        " TypeError.",
        "`Symmetric` needs the last listed layer to be a Dielectric, which becomes the"
        " centre of the board; otherwise instantiating it raises TypeError.",
        "The last listed layer must be a conductor so the copper mirrors; a dielectric"
        " there raises TypeError.",
    ),
    10: (
        "Use per-layer `diameters` with `ViaDiameter(pad, nfp=reduced)` for the layers"
        " whose pads you want reduced.",
        "In `Via.diameters`, map the layers to `ViaDiameter(0.5, nfp=0.2)`; the nfp"
        " diameter applies where the pad is non-functional.",
        "Set the pad diameter to 0 in `diameters` for the layers without connections.",
    ),
    11: (
        "Set stop_layer to the layer the signal connects at; a bottom BackdrillSet then"
        " drills out the stub below it.",
        "The via's span sets it: for a bottom backdrill, stop_layer is the deepest layer"
        " kept; for BackdrillSet(top=...), start_layer.",
        "Pass the depth to the Backdrill: Backdrill(diameter=0.5, depth=0.8, ...).",
    ),
    12: (
        "It yields Proxy objects. A mixed Material list gives AttributeError for fields"
        " the layer's class lacks, so decompose by Dielectric or Conductor.",
        "Proxies. type(element) is the proxy class, so read fields from the element, and"
        " decompose(stackup, Dielectric) when you want dielectric fields.",
        "It returns instances of your material classes, so read"
        " type(layer).dielectric_coefficient directly.",
    ),
    13: (
        "Plain unittest.TestCase has no JITX instantiation context, so reads come back"
        " empty. Base the test on jitx.test.TestCase.",
        "Outside an instantiation context the stackup is never instantiated and"
        " decompose returns nothing. Use `from jitx.test import TestCase`.",
        "The JITX runtime is not running; start it before running the unittest suite.",
    ),
    14: (
        "Pick one. Setting both raises ValueError. Only one of the two is allowed.",
        "Either on the class or in the constructor, never both; the constructor raises"
        " ValueError if both are given.",
        "Yes; the constructor value overrides the class attribute.",
    ),
    15: (
        "dielectric_coefficient (Dk) and loss_tangent (Df).",
        "Dk goes in `dielectric_coefficient`, Df in `loss_tangent`.",
        "Set `dk` and `df` class attributes on the Dielectric.",
    ),
    16: (
        "Only copper layers are indexed, dielectrics are not counted. -1 is the bottom"
        " copper layer.",
        "They count conductor layers only. Index -1 is the bottom conductor"
        " (Side.Bottom).",
        "Yes, every layer including the dielectrics gets an index; -1 is the bottom"
        " soldermask.",
    ),
    17: (
        "Make a separate RoutingStructure on the substrate, assign a Tag to that part of"
        " the route, and add design_constraint(MyTag()).routing_structure(...).",
        "Tag that route segment and apply a structure by tag:"
        " design_constraint(EscapeTag()).routing_structure(Substrate.RS_ESCAPE)."
        " NeckDown is discontinued.",
        "Add a neck_down=RoutingStructure.NeckDown(trace_width=0.075) to the layer and"
        " activate the neckdown region in the UI.",
    ),
    18: (
        "See jitxexamples.patterns.fenced_pour_outline: a Tag, a"
        " design_constraint(...).fence_via(...) rule, a Pour carrying the tag, and a"
        " KeepOut.",
        "There is a buildable pattern module for it in jitxexamples. Pieces: a Tag"
        " subclass, a fence_via design constraint on that tag, and a tagged pour on GND.",
        "Use RoutingStructure.Layer.fence() with a ViaFencePattern on a route drawn"
        " around the outline.",
    ),
    19: (
        "4.0 for the single dielectric (stripline eps_eff equals Dk), and 4.1 for the"
        " prepreg/core boundary.",
        "Single dielectric: eps_eff = 4.0 (stripline is TEM in a homogeneous medium)."
        " Prepreg/core with equal heights: (3.9 + 4.3)/2 = 4.1. The microstrip"
        " (er + 1)/2 form does not apply.",
        "Use the microstrip form: (4.0 + 1) / 2 = 2.5 for the single dielectric, and"
        " (3.9 + 4.3) / 2 = 4.1 for the boundary.",
    ),
}


# Per question: an answer that states every fact of its key but also makes the
# key's wrong claim. Q9 and Q19 are covered by their wrong answers in ROWS.
WRONG_CLAIMS: dict[int, str] = {
    2: "It lives on the substrate too, but keep a module-level dict in the design file"
    " for speed.",
    3: "You could instantiate it, but use the empty inline subclass"
    " `@inline class stackup(Generic_Stackup): pass`.",
    4: "Inheritance won't work for vias; copy each via class into both substrates.",
    6: "The centre-to-centre gap between the P and N traces.",
    7: "offset is the spacing between rows and the default initial_offset;"
    " initial_offset is measured from the edge, at trace_width/2 + gap + pad radius"
    " from the trace centre.",
    11: "stop_layer sets where the via connects, and Backdrill(depth=0.8) sets the"
    " backdrill depth.",
    14: "Not both, in theory. In practice the constructor value overrides the class"
    " one without an error.",
    17: "Tag the route segment and give its layer a"
    " neck_down=RoutingStructure.NeckDown(...); routing_structure stays as it is.",
}


def grade(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GRADER), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def statuses(stdout: str) -> dict[int, str]:
    """Question number -> PASS or FAIL, from the grader's per-question lines."""
    found: dict[int, str] = {}
    for line in stdout.splitlines():
        match = LINE.match(line)
        if match:
            found[int(match.group(2))] = match.group(1)
    return found


def answers_file(tmp_path: Path, answers: dict[int, str]) -> Path:
    path = tmp_path / "ANSWERS.md"
    body = "\n\n".join(f"## {n}\n\n{text}" for n, text in sorted(answers.items()))
    path.write_text(body + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("column", "expected"),
    [(0, "PASS"), (1, "PASS"), (2, "FAIL")],
    ids=["paraphrase-a", "paraphrase-b", "plausible-wrong"],
)
def test_each_key_passes_correct_paraphrases_and_fails_a_wrong_answer(
    tmp_path: Path, column: int, expected: str
) -> None:
    path = answers_file(tmp_path, {n: row[column] for n, row in ROWS.items()})
    run = grade("answers", str(path))
    assert statuses(run.stdout) == {n: expected for n in QUESTIONS}, run.stdout
    assert run.returncode == (0 if expected == "PASS" else 1), run.stdout + run.stderr


def test_a_wrong_claim_fails_beside_the_right_facts(tmp_path: Path) -> None:
    run = grade("answers", str(answers_file(tmp_path, WRONG_CLAIMS)))
    reasons = {
        int(m.group(1)): m.group(2)
        for m in re.finditer(r"^FAIL  Q(\d+) [^:]*: (.*)$", run.stdout, flags=re.M)
    }
    assert {n: reasons.get(n, "PASS").split(" ", 1)[0] for n in WRONG_CLAIMS} == {
        n: "claims" for n in WRONG_CLAIMS
    }, run.stdout


def without_section(text: str, number: int) -> str:
    return re.sub(
        rf"^## {number}\n.*?(?=^## {number + 1}\n)", "", text, flags=re.M | re.S
    )


GOOD = ANSWERS.read_text(encoding="utf-8")
PLAIN = "\n".join(f"{n}. {row[0]}" for n, row in sorted(ROWS.items()))
BOLD = "\n\n".join(f"**Q{n}.** {row[1]}" for n, row in sorted(ROWS.items()))
NESTED = PLAIN.replace(
    "\n17. ",
    "\n17. Three steps:\n1. Define the structure.\n2. Tag the segment.\n3. Apply it.\n",
)
ALL_PASS = {n: "PASS" for n in QUESTIONS}


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(GOOD, ALL_PASS, id="fixture-headings"),
        pytest.param(PLAIN, ALL_PASS, id="numbered-lines"),
        pytest.param(BOLD, ALL_PASS, id="bold-q-labels"),
        pytest.param(NESTED, ALL_PASS, id="numbered-list-inside-an-answer"),
        pytest.param(
            without_section(GOOD, 7), {**ALL_PASS, 7: "FAIL"}, id="one-answer-missing"
        ),
        pytest.param("", {n: "FAIL" for n in QUESTIONS}, id="empty-file"),
        pytest.param(
            "I could not answer these.\n",
            {n: "FAIL" for n in QUESTIONS},
            id="no-sections",
        ),
    ],
)
def test_answers_file_shapes(
    tmp_path: Path, content: str, expected: dict[int, str]
) -> None:
    path = tmp_path / "ANSWERS.md"
    path.write_text(content, encoding="utf-8")
    run = grade("answers", str(path))
    assert statuses(run.stdout) == expected, run.stdout
    assert run.returncode == (0 if set(expected.values()) == {"PASS"} else 1)


@pytest.mark.parametrize("make", ["missing", "directory"])
def test_an_unreadable_answers_file_fails_every_question(
    tmp_path: Path, make: str
) -> None:
    path = tmp_path / "ANSWERS.md"
    if make == "directory":
        path.mkdir()
    run = grade("answers", str(path))
    assert run.returncode == 1, run.stdout + run.stderr
    assert statuses(run.stdout) == {n: "FAIL" for n in QUESTIONS}


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        pytest.param(
            READS_ALL, {n: "PASS" for n in READ_CHECKED}, id="every-target-read"
        ),
        pytest.param(
            READS_NONE, {n: "FAIL" for n in READ_CHECKED}, id="no-target-read"
        ),
    ],
)
def test_read_log(transcript: Path, expected: dict[int, str]) -> None:
    run = grade("reads", str(transcript))
    assert statuses(run.stdout) == expected, run.stdout
    assert run.returncode == (0 if set(expected.values()) == {"PASS"} else 1)


@pytest.mark.parametrize(
    "args",
    [
        pytest.param([], id="no-subcommand"),
        pytest.param(["answers"], id="no-answers-path"),
        pytest.param(["grade", "x"], id="unknown-subcommand"),
        pytest.param(["reads", "no-such-transcript.jsonl"], id="missing-transcript"),
    ],
)
def test_usage_errors_exit_2(tmp_path: Path, args: list[str]) -> None:
    run = subprocess.run(
        [sys.executable, str(GRADER), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert run.returncode == 2, run.stdout + run.stderr


def test_the_prompt_numbers_exactly_the_keyed_questions() -> None:
    prompt = json.loads(CASE.read_text(encoding="utf-8"))["prompt"]
    numbered = [int(n) for n in re.findall(r"^(\d+)\. ", prompt, flags=re.M)]
    assert numbered == list(QUESTIONS)
    assert sorted(ROWS) == list(QUESTIONS)


def case_commands() -> list[str]:
    data = json.loads(CASE.read_text(encoding="utf-8"))
    return [a["cmd"] for a in data["assertions"] if a["check"] == "deterministic"]


@pytest.mark.parametrize(
    ("transcript", "returncodes"),
    [
        pytest.param(READS_ALL, [0, 0], id="good-transcript"),
        pytest.param(READS_NONE, [0, 1], id="no-reads-transcript"),
    ],
)
def test_case_commands_run_as_written(
    tmp_path: Path, transcript: Path, returncodes: list[int]
) -> None:
    (tmp_path / "ANSWERS.md").write_text(GOOD, encoding="utf-8")
    env = {
        **os.environ,
        "PATH": os.pathsep.join([str(Path(sys.executable).parent), os.environ["PATH"]]),
    }
    codes = []
    for cmd in case_commands():
        command = cmd.replace("<output>", shlex.quote(str(tmp_path))).replace(
            "<transcript>", shlex.quote(str(transcript))
        )
        run = subprocess.run(
            command,
            shell=True,
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        codes.append(run.returncode)
    assert codes == returncodes


needs_jitx = pytest.mark.skipif(
    importlib.util.find_spec("jitx") is None,
    reason="jitx is not importable; check_runner.py needs it for its wording list",
)


@needs_jitx
def test_no_output_reads_as_an_environment_problem(tmp_path: Path) -> None:
    import check_runner

    wrong = answers_file(tmp_path, {n: row[2] for n, row in ROWS.items()})
    runs = [
        grade("answers", str(wrong)),
        grade("answers", str(tmp_path / "missing" / "ANSWERS.md")),
        grade("reads", str(READS_NONE)),
        grade("reads", str(tmp_path / "missing.jsonl")),
    ]
    for run in runs:
        out = run.stdout + run.stderr
        hits = [p for p in check_runner.ENVIRONMENT_WORDING if re.search(p, out, re.I)]
        assert not hits, out
