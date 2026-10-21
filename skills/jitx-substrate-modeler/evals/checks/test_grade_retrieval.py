"""grade_retrieval.py credits a read only where a tool result shows the
destination's text and the run did not write that text itself, and compares
the read logs of two runs.

Every test drives the script's CLI as the case runs it, so the stream-json
parsing and the exit code are in the path. The case's answers are graded by
its judge assertions; the last tests check that the case keeps one per
question, in the prompt's order.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

CHECKS = Path(__file__).resolve().parent
SKILL = CHECKS.parents[1]
GRADER = CHECKS / "grade_retrieval.py"
CASE = SKILL / "evals" / "cases" / "substrate-api-retrieval.json"
CASE_E = CHECKS / "testdata" / "case_e"
READS_ALL = CASE_E / "transcript_reads_all.jsonl"
READS_NONE = CASE_E / "transcript_reads_none.jsonl"
OUTPUT = "/work/output"
"""The output directory the fixture runner was given. The read log is not
told it: where a file sits does not decide whether reading it counts."""

QUESTIONS = range(1, 20)
READ_CHECKED = [5, 7, 8, 9, 10, 11, 12, 14, 15, 19]

LINE = re.compile(r"^(PASS|FAIL)  Q(\d+) [^:\n]*(?:: (.*))?$", re.MULTILINE)

PASS = "PASS"


def grade(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GRADER), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def statuses(stdout: str) -> dict[int, str]:
    """Question number -> PASS or FAIL, from the per-question lines."""
    return {int(m.group(2)): m.group(1) for m in LINE.finditer(stdout)}


SITE = "/work/venv/lib/python3.12/site-packages"
PY = "/work/venv/bin/python"

Call = tuple[str, dict[str, object], str | list[dict[str, str]] | None, bool | None]
"""(tool, input, result content or None for no result, is_error or None for
no is_error key)."""


def transcript(path: Path, calls: list[Call]) -> Path:
    events: list[dict[str, object]] = [{"type": "system", "subtype": "init"}]
    for index, (tool, given, content, error) in enumerate(calls):
        use_id = f"toolu_{index:02d}"
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "id": use_id, "name": tool, "input": given}
                    ]
                },
            }
        )
        if content is None:
            continue
        result: dict[str, object] = {
            "type": "tool_result",
            "tool_use_id": use_id,
            "content": content,
        }
        if error is not None:
            result["is_error"] = error
        events.append({"type": "user", "message": {"content": [result]}})
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


# Runner idioms that read a destination, each with the lines its output shows
# from the built text.
IDIOMS: list[Call] = [
    (
        "Bash",
        {
            "command": f"J={SITE}/jitx && grep -n -i 'velocity\\|insertion_loss' $J/si.py"
        },
        '569:        """Velocity of signal for purposes of timing constraints, in'
        ' millimeters per second."""',
        False,
    ),
    (
        "Bash",
        {"command": f"cd {SITE}/jitx && sed -n 200,240p constraints.py"},
        '    """The center-to-center distance between fence via rows, and the default'
        " initial offset in millimeters\n    If true, the pre-isolation outline shape"
        " of the pour is used to generate the",
        False,
    ),
    (
        "Grep",
        {
            "pattern": "class Symmetric",
            "path": f"{SITE}/jitx",
            "output_mode": "content",
        },
        f"{SITE}/jitx/stackup.py:67:class Symmetric(Stackup):\n{SITE}/jitx/stackup.py-80-"
        "    The last layer must be a :py:class:`Dielectric`; instantiating the",
        None,
    ),
    (
        "Bash",
        {"command": f"sed -n 60,75p {SITE}/jitx/via.py"},
        "    pad diameter where non-functional pads are removed (see",
        False,
    ),
    (
        "Bash",
        {"command": f"{PY} -c 'from jitx import via; help(via.BackdrillSet)'"},
        "class BackdrillSet(builtins.object)\n |  Set of backdrill specifications for"
        " top and bottom sides. The depth of\n |  each backdrill comes from the via's"
        " layer span: see",
        False,
    ),
    (
        "Bash",
        {"command": f"grep -rn 'def decompose' -A 40 {SITE}/jitx/"},
        f"{SITE}/jitx/inspect.py-240-    class, so reading a class attribute through"
        " ``type(element)`` raises",
        False,
    ),
    (
        "Grep",
        {"pattern": "thickness|Dk|Df", "path": f"{SITE}/jitx/stackup.py", "-n": True},
        [
            {
                "type": "text",
                "text": "129:    both: the constructor raises ValueError if both are given,"
                ' and also if\n188:    """Dielectric constant, the Dk of a datasheet'
                " (also called relative",
            }
        ],
        None,
    ),
    (
        "Grep",
        {
            "pattern": "class Tag",
            "path": f"{SITE}/jitx",
            "-A": 3,
            "output_mode": "content",
        },
        f"{SITE}/jitx/constraints.py:345:class Tag:\n{SITE}/jitx/constraints.py-346-"
        '    """Tags are the fundamental building blocks for design constraints.',
        None,
    ),
    (
        "Bash",
        {"command": f"sed -n 1,90p {SITE}/jitxlib/physics/__init__.py"},
        "      and half its field lies in each. Real widths approach that limit slowly,",
        False,
    ),
    (
        "Bash",
        {
            "command": "python -c 'import jitxexamples.patterns.fenced_pour_outline as m;"
            " print(m.__doc__)'"
        },
        "Fence vias along an arbitrary closed outline.\n\nUse this pattern when",
        False,
    ),
]

LISTING: list[Call] = [
    (
        "Glob",
        {"pattern": "**/*.py", "path": f"{SITE}/jitx"},
        f"{SITE}/jitx/si.py",
        None,
    ),
    ("Bash", {"command": f"ls {SITE}/jitxlib/physics"}, "__init__.py", False),
    (
        "Grep",
        {"pattern": "nfp|depth", "path": f"{SITE}/jitx"},
        f"Found 2 files\n{SITE}/jitx/via.py\n{SITE}/jitx/stackup.py",
        None,
    ),
]
HEREDOC: list[Call] = [
    (
        "Bash",
        {
            "command": "cat > /work/output/notes.md <<'EOF'\nTags are the fundamental"
            " building blocks; see jitx.constraints, jitxlib.physics\nEOF"
        },
        "",
        False,
    ),
    (
        "Bash",
        {"command": "echo 'Hammerstad and Jensen' && echo jitxlib.physics"},
        "Hammerstad and Jensen\njitxlib.physics",
        False,
    ),
]
IMPORT_ONLY: list[Call] = [
    (
        "Bash",
        {
            "command": f"{PY} -c 'import jitx.si, jitx.via, jitx.stackup, jitx.constraints,"
            ' jitx.inspect, jitxlib.physics, jitxexamples.patterns; print("ok")\''
        },
        "ok",
        False,
    ),
]
# The runner's own answers, written with Write and read back.
ANSWERS_ONLY: list[Call] = [
    (
        "Write",
        {
            "file_path": f"{OUTPUT}/ANSWERS.md",
            "content": "## 19\nThe Hammerstad and Jensen closed form.",
        },
        f"File created successfully at: {OUTPUT}/ANSWERS.md",
        None,
    ),
    (
        "Read",
        {"file_path": f"{OUTPUT}/ANSWERS.md"},
        "     1\t## 19\n     2\tThe Hammerstad and Jensen closed form.",
        None,
    ),
]
PHASE: Call = (
    "Bash",
    {"command": f"{PY} -c 'from jitxlib import physics; help(physics.phase_velocity)'"},
    "    and half its field lies in each. Real widths approach that limit slowly,",
    False,
)
PHASE_FAILED: list[Call] = [
    (PHASE[0], PHASE[1], "<tool_use_error>Permission denied</tool_use_error>", None),
    (PHASE[0], PHASE[1], PHASE[2], True),
    (PHASE[0], PHASE[1], None, None),
]
NONE_READ = {n: "FAIL" for n in READ_CHECKED}


def truncated(path: Path) -> Path:
    """The good transcript cut off partway through the result of its last
    read, the phase_velocity help."""
    rows = READS_ALL.read_text(encoding="utf-8").splitlines()
    last = max(i for i, row in enumerate(rows) if "phase_velocity" in row)
    kept = rows[:last] + [rows[last + 1][: len(rows[last + 1]) // 2]]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return path


# The runner's own answers read back through a glob that does not name
# ANSWERS.md, absolutely or relative to the run directory. The draft rule
# alone excludes them: the phrases were in the writing call's own input.
OWN_ANSWERS = (
    "## 19\nThe Hammerstad and Jensen closed form; half its field lies in each.\n"
    "## 11\nstop_layer sets the depth of a bottom backdrill."
)
WROTE_ANSWERS: Call = (
    "Write",
    {"file_path": f"{OUTPUT}/ANSWERS.md", "content": OWN_ANSWERS},
    f"File created successfully at: {OUTPUT}/ANSWERS.md",
    None,
)
OWN_OUTPUT_GLOB: list[Call] = [
    WROTE_ANSWERS,
    ("Bash", {"command": f"cat {OUTPUT}/*.md"}, OWN_ANSWERS, False),
]
OWN_OUTPUT_RELATIVE: list[Call] = [
    WROTE_ANSWERS,
    ("Bash", {"command": "cd /work && cat output/*.md"}, OWN_ANSWERS, False),
]
OWN_OUTPUT_HEREDOC: list[Call] = [
    (
        "Bash",
        {"command": f"cd /work && cat > output/ANSWERS.md <<'EOF'\n{OWN_ANSWERS}\nEOF"},
        "",
        False,
    ),
    ("Bash", {"command": "cat /work/output/*.md"}, OWN_ANSWERS, False),
]
# Answers begun as a skeleton and filled in by Edit: the Edit's new text is
# the writing call's input.
OWN_OUTPUT_EDITED: list[Call] = [
    (
        "Write",
        {"file_path": "/run/out/ANSWERS.md", "content": "# Answers\n"},
        "File created successfully at: /run/out/ANSWERS.md",
        None,
    ),
    (
        "Edit",
        {
            "file_path": "/run/out/ANSWERS.md",
            "old_string": "# Answers\n",
            "new_string": f"# Answers\n{OWN_ANSWERS}",
        },
        "The file /run/out/ANSWERS.md has been updated.",
        None,
    ),
    ("Bash", {"command": "cd /run/out && cat ANSWERS.md"}, OWN_ANSWERS, False),
]
OWN_OUTPUT_DRAFT: list[Call] = [
    (
        "Write",
        {
            "file_path": f"{OUTPUT}/draft.md",
            "content": "velocity is in millimeters per second",
        },
        f"File created successfully at: {OUTPUT}/draft.md",
        None,
    ),
    (
        "Read",
        {"file_path": f"{OUTPUT}/draft.md"},
        "     1\tvelocity is in millimeters per second",
        None,
    ),
]
# A draft written from memory outside the output directory, then read back.
DRAFT_WRITTEN: list[Call] = [
    (
        "Write",
        {
            "file_path": "/work/notes/draft.md",
            "content": "Hammerstad and Jensen (1980): real eps_eff above (er+1)/2",
        },
        "File created successfully at: /work/notes/draft.md",
        None,
    ),
    (
        "Bash",
        {"command": "cat /work/notes/draft.md"},
        "Hammerstad and Jensen (1980): real eps_eff above (er+1)/2",
        False,
    ),
]
DRAFT_ECHOED: list[Call] = [
    (
        "Bash",
        {"command": "echo 'velocity in millimeters per second' > /tmp/units.txt"},
        "",
        False,
    ),
    (
        "Read",
        {"file_path": "/tmp/units.txt"},
        "     1\tvelocity in millimeters per second",
        None,
    ),
]
DRAFT_PYTHON: list[Call] = [
    (
        "Bash",
        {
            "command": "python -c \"open('/tmp/q19.md', 'w').write('Hammerstad and"
            " Jensen: above the limit')\""
        },
        "",
        False,
    ),
    (
        "Read",
        {"file_path": "/tmp/q19.md"},
        "     1\tHammerstad and Jensen: above the limit",
        None,
    ),
]
# Real help output saved to a file and read back is a read: the file's text
# came from the destination, not from the runner.
HELP_SAVED: list[Call] = [
    (
        "Bash",
        {
            "command": f"{PY} -c 'from jitxlib.physics import phase_velocity;"
            " help(phase_velocity)' > /tmp/help.txt"
        },
        "",
        False,
    ),
    ("Bash", {"command": "cat /tmp/help.txt"}, PHASE[2], False),
]
# An Edit's result shows a snippet of the edited file; editing is not reading.
EDIT_SNIPPET: list[Call] = [
    (
        "Edit",
        {
            "file_path": "/work/notes.md",
            "old_string": "units: unknown",
            "new_string": "units: see the jitx.si docstring",
        },
        "The file /work/notes.md has been updated. Here's the result of running"
        " `cat -n` on a snippet of the edited file:\n     3\tVelocity of signal for"
        " purposes of timing constraints, in millimeters per second.",
        None,
    ),
]


# Genuine reads of the Q5 docstring that touch the output directory or the
# word "output". Each counts.
HELP5 = f"{PY} -c 'import jitx.si; help(jitx.si.RoutingStructure.Layer)'"
DOC5 = (
    "    Velocity of signal for purposes of timing constraints, in millimeters per"
    " second."
)
ANSWERS5: Call = (
    "Write",
    {"file_path": f"{OUTPUT}/ANSWERS.md", "content": "Q5: in millimeters per second"},
    f"File created successfully at: {OUTPUT}/ANSWERS.md",
    None,
)
HELP_DESCRIBED: list[Call] = [
    (
        "Bash",
        {
            "command": HELP5,
            "description": "Print help output for RoutingStructure.Layer",
        },
        DOC5,
        False,
    ),
]
PRINT_OUTPUT: list[Call] = [
    (
        "Bash",
        {
            "command": f"{PY} -c 'import jitx.si as m;"
            " output = m.RoutingStructure.Layer.__doc__; print(output)'"
        },
        DOC5,
        False,
    ),
]
# Answers that quote the phrase are already written: a directory that holds
# them is not them.
CD_OUTPUT: list[Call] = [
    ANSWERS5,
    ("Bash", {"command": f"cd {OUTPUT} && {HELP5}"}, DOC5, False),
]
PROBE_IN_OUTPUT: list[Call] = [
    ANSWERS5,
    (
        "Write",
        {
            "file_path": f"{OUTPUT}/probe.py",
            "content": "import jitx.si\nprint(jitx.si.RoutingStructure.Layer.velocity.__doc__)",
        },
        f"File created successfully at: {OUTPUT}/probe.py",
        None,
    ),
    ("Bash", {"command": f"{PY} {OUTPUT}/probe.py"}, DOC5, False),
]
# help() saved into the output directory is not a draft: the phrase is in
# the help output, not in the writing call's input.
HELP_SAVED_IN_OUTPUT: list[Call] = [
    ("Bash", {"command": f"{HELP5} > {OUTPUT}/help_si.txt"}, "", False),
    ("Read", {"file_path": f"{OUTPUT}/help_si.txt"}, "     1\t" + DOC5, None),
]
# Silencing stderr writes no file.
GREP_THEN_SED: list[Call] = [
    (
        "Bash",
        {"command": f"grep -rn 'in millimeters per second' {SITE}/x 2>/dev/null"},
        "",
        False,
    ),
    (
        "Bash",
        {"command": f"sed -n 560,575p {SITE}/jitx/si.py 2>/dev/null"},
        DOC5,
        False,
    ),
]
READ5 = {**NONE_READ, 5: PASS}


def calls_of(calls: list[Call]) -> object:
    return lambda p: transcript(p, calls)


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        pytest.param(
            lambda p: READS_ALL, {n: PASS for n in READ_CHECKED}, id="fixture-all"
        ),
        pytest.param(lambda p: READS_NONE, NONE_READ, id="fixture-none"),
        pytest.param(
            truncated, {**{n: PASS for n in READ_CHECKED}, 19: "FAIL"}, id="truncated"
        ),
        pytest.param(
            calls_of(IDIOMS),
            {n: PASS for n in READ_CHECKED},
            id="runner-idioms-showing-the-text",
        ),
        pytest.param(calls_of(LISTING), NONE_READ, id="listing-only"),
        pytest.param(calls_of(HEREDOC), NONE_READ, id="heredoc-and-echo"),
        pytest.param(calls_of(IMPORT_ONLY), NONE_READ, id="import-only"),
        pytest.param(calls_of(ANSWERS_ONLY), NONE_READ, id="answers-written-then-read"),
        pytest.param(calls_of([PHASE]), {**NONE_READ, 19: PASS}, id="help-output"),
        pytest.param(
            calls_of(PHASE_FAILED), NONE_READ, id="errored-or-missing-results"
        ),
        pytest.param(calls_of(OWN_OUTPUT_GLOB), NONE_READ, id="own-answers-by-glob"),
        pytest.param(
            calls_of(OWN_OUTPUT_RELATIVE), NONE_READ, id="own-answers-by-relative-glob"
        ),
        pytest.param(
            calls_of(OWN_OUTPUT_HEREDOC), NONE_READ, id="own-answers-from-heredoc"
        ),
        pytest.param(calls_of(OWN_OUTPUT_EDITED), NONE_READ, id="own-answers-by-edit"),
        pytest.param(calls_of(OWN_OUTPUT_DRAFT), NONE_READ, id="draft-in-own-output"),
        pytest.param(calls_of(DRAFT_WRITTEN), NONE_READ, id="draft-written-then-read"),
        pytest.param(calls_of(DRAFT_ECHOED), NONE_READ, id="draft-echoed-then-read"),
        pytest.param(
            calls_of(DRAFT_PYTHON), NONE_READ, id="draft-from-python-then-read"
        ),
        pytest.param(
            calls_of(HELP_SAVED), {**NONE_READ, 19: PASS}, id="help-saved-then-read"
        ),
        pytest.param(calls_of(EDIT_SNIPPET), NONE_READ, id="edit-result-snippet"),
        pytest.param(calls_of(HELP_DESCRIBED), READ5, id="description-says-output"),
        pytest.param(calls_of(PRINT_OUTPUT), READ5, id="print-output-variable"),
        pytest.param(calls_of(CD_OUTPUT), READ5, id="cd-into-output-then-help"),
        pytest.param(calls_of(PROBE_IN_OUTPUT), READ5, id="probe-script-in-output"),
        pytest.param(calls_of(HELP_SAVED_IN_OUTPUT), READ5, id="help-saved-in-output"),
        pytest.param(calls_of(GREP_THEN_SED), READ5, id="stderr-to-dev-null"),
    ],
)
def test_read_log(tmp_path: Path, build: object, expected: dict[int, str]) -> None:
    assert callable(build)
    path = build(tmp_path / "transcript.jsonl")
    assert isinstance(path, Path)
    run = grade("reads", str(path))
    assert statuses(run.stdout) == expected, run.stdout
    assert run.returncode == (0 if set(expected.values()) == {PASS} else 1)


Run = tuple[Path | list[Call] | None, bool]
"""(the transcript, or the calls to build one from, or None for none;
whether output/ANSWERS.md exists)."""


def run_dir(root: Path, source: Path | list[Call] | None, answers: bool) -> Path:
    (root / "output").mkdir(parents=True)
    if answers:
        (root / "output" / "ANSWERS.md").write_text("# Answers\n", encoding="utf-8")
    if isinstance(source, list):
        transcript(root / "transcript.jsonl", source)
    elif source is not None:
        (root / "transcript.jsonl").write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
    return root


@pytest.mark.parametrize(
    ("before", "after", "code", "shown", "questions"),
    [
        pytest.param(
            (READS_NONE, True),
            (READS_ALL, True),
            0,
            ["Q9 reads FAIL->PASS", "PASS  compare: no read went from PASS to FAIL"],
            len(READ_CHECKED),
            id="gains-only",
        ),
        pytest.param(
            (READS_ALL, True),
            (READS_NONE, True),
            1,
            ["Q5 reads PASS->FAIL", "Q19 reads PASS->FAIL"],
            len(READ_CHECKED),
            id="a-read-lost",
        ),
        pytest.param(
            (None, False),
            (READS_ALL, True),
            2,
            ["before: run produced no output (no transcript.jsonl)"],
            0,
            id="before-produced-nothing",
        ),
        pytest.param(
            (READS_ALL, True),
            (READS_ALL, False),
            2,
            ["after: run produced no output (no output/ANSWERS.md)"],
            0,
            id="after-read-everything-wrote-no-answers",
        ),
        pytest.param(
            (READS_ALL, True),
            ([], False),
            2,
            ["after: run produced no output (no output/ANSWERS.md)"],
            0,
            id="after-init-only-wrote-no-answers",
        ),
    ],
)
def test_compare(
    tmp_path: Path,
    before: Run,
    after: Run,
    code: int,
    shown: list[str],
    questions: int,
) -> None:
    run = grade(
        "compare",
        str(run_dir(tmp_path / "before", *before)),
        str(run_dir(tmp_path / "after", *after)),
    )
    assert run.returncode == code, run.stdout + run.stderr
    printed = run.stdout.splitlines()
    assert all(line in printed for line in shown), run.stdout
    assert len([line for line in printed if re.match(r"^Q\d+ reads ", line)]) == (
        questions
    )


@pytest.mark.parametrize(
    "args",
    [
        pytest.param([], id="no-subcommand"),
        pytest.param(["answers", "ANSWERS.md"], id="no-answers-subcommand"),
        pytest.param(["reads"], id="no-transcript"),
        pytest.param(["reads", "no-such-transcript.jsonl"], id="missing-transcript"),
        pytest.param(["compare", "before"], id="compare-one-directory"),
    ],
)
def test_usage_errors_exit_2(tmp_path: Path, args: list[str]) -> None:
    run = grade(*args, cwd=tmp_path)
    assert run.returncode == 2, run.stdout + run.stderr


def test_each_question_has_one_judge_assertion_in_prompt_order() -> None:
    case = json.loads(CASE.read_text(encoding="utf-8"))
    numbered = [int(n) for n in re.findall(r"^(\d+)\. ", case["prompt"], flags=re.M)]
    assert numbered == list(QUESTIONS)
    judged = [a["text"] for a in case["assertions"] if a["check"] == "judge"]
    assert [int(m.group(1)) for t in judged if (m := re.match(r"Q(\d+) \(", t))] == (
        list(QUESTIONS)
    )
    for text in judged:
        assert " fails if " in text, text
        assert "may name a wrong form in order to reject it" in text, text


def test_the_reads_assertion_names_the_logged_questions() -> None:
    case = json.loads(CASE.read_text(encoding="utf-8"))
    [reads] = [a for a in case["assertions"] if a["check"] == "deterministic"]
    assert reads["cmd"].endswith("reads <transcript>")
    named = [int(n) for n in re.findall(r"\bQ(\d+)\b", reads["text"])]
    assert named == READ_CHECKED


needs_jitx = pytest.mark.skipif(
    importlib.util.find_spec("jitx") is None,
    reason="jitx is not importable; check_runner.py needs it for its wording list",
)


@needs_jitx
def test_no_output_reads_as_an_environment_problem(tmp_path: Path) -> None:
    import check_runner

    harmful = "ModuleNotFoundError: No module named jitx; command not found"
    reads = transcript(
        tmp_path / "t.jsonl",
        [
            ("Bash", {"command": "python -c 'import jitx'"}, harmful, False),
            ("Read", {"file_path": f"{SITE}/jitx/si.py"}, harmful, None),
        ],
    )
    runs = [
        grade("reads", str(reads)),
        grade("reads", str(tmp_path / "missing.jsonl")),
        grade(
            "compare",
            str(run_dir(tmp_path / "before", None, answers=False)),
            str(run_dir(tmp_path / "after", reads, answers=True)),
        ),
    ]
    for run in runs:
        for line in (run.stdout + run.stderr).splitlines():
            hits = [
                p for p in check_runner.ENVIRONMENT_WORDING if re.search(p, line, re.I)
            ]
            assert not hits, line
