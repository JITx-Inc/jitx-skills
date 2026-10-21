"""grade_retrieval.py passes a correct answer however it is phrased, fails the
wrong answer each question exists to catch, credits a read only where a tool
result shows the destination's text, and compares two runs.

Every test drives the grader's CLI as the case runs it, so the file read, the
section parsing, the stream-json parsing and the exit code are all in the
path. Answer keys are tested by one table of rows: correct phrasings that
must pass, and for every fact and every wrong claim of every key, an answer
that must fail on exactly that fact or claim.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import grade_retrieval

CHECKS = Path(__file__).resolve().parent
SKILL = CHECKS.parents[1]
GRADER = CHECKS / "grade_retrieval.py"
CASE = SKILL / "evals" / "cases" / "substrate-api-retrieval.json"
CASE_E = CHECKS / "testdata" / "case_e"
ANSWERS = CASE_E / "ANSWERS.md"
READS_ALL = CASE_E / "transcript_reads_all.jsonl"
READS_NONE = CASE_E / "transcript_reads_none.jsonl"

QUESTIONS = range(1, 20)
READ_CHECKED = [5, 7, 8, 9, 10, 11, 12, 14, 15, 17, 18, 19]

LINE = re.compile(r"^(PASS|FAIL)  Q(\d+) [^:\n]*(?:: (.*))?$", re.MULTILINE)

PASS = "PASS"


def lacks(label: str) -> str:
    return "does not state " + label


def claims(label: str) -> str:
    return "claims " + label


# (question, expected, answer). Expected is PASS, or the FAIL reason the line
# must carry: lacks(<fact label>) or claims(<wrong-claim label>).
ROWS: list[tuple[int, str, str]] = [
    (1, PASS, "Use the **jitx** skill first; it sets up the environment."),
    (1, PASS, "The `jitx` base skill handles the environment."),
    (1, PASS, "Invoke /jitx first: the base skill owns environment setup."),
    (
        1,
        PASS,
        "Use the jitx skill first; the jitx-substrate-modeler skill does not handle"
        " the environment.",
    ),
    (1, lacks("the base jitx skill"), "A setup skill handles it; run that first."),
    (
        1,
        claims("names another skill for the environment"),
        "The jitx-substrate-modeler skill handles the environment itself; the base"
        " jitx skill is only for designs.",
    ),
    (2, PASS, "Put it on your `Substrate` subclass, as a property the design queries."),
    (2, PASS, "Make it a property of the Substrate class; the design queries it."),
    (
        2,
        PASS,
        "As an attribute of the Substrate class; the design reads"
        " self.substrate.signal_via[layer].",
    ),
    (
        2,
        PASS,
        "The substrate should own it (e.g. a `signal_via` property); the design reads"
        " `self.substrate.signal_via`.",
    ),
    (
        2,
        PASS,
        "As a property on `MySubstrate`, which the design queries through"
        " `self.substrate`.",
    ),
    (2, lacks("the table lives on the substrate"), "Keep it next to the routing code."),
    (
        2,
        claims("keeps the table in the design"),
        "Keep it next to the routing code in your design module; the via classes"
        " themselves are defined in the substrate, so import them from there.",
    ),
    (
        2,
        claims("keeps the table in the design"),
        "Put it in the design file as a module-level constant; vias live in the"
        " substrate but the table is design data.",
    ),
    (
        3,
        PASS,
        "Use `@inline` only when the body declares layers; here instantiate it:"
        " `stackup = GenericStackup()`.",
    ),
    (
        3,
        PASS,
        "Instantiate it: `stackup = GenericStackup()`. If you write `@inline class"
        " stackup(GenericStackup): pass`, the empty body adds nothing; inline-subclass"
        " only when the body declares layers.",
    ),
    (
        3,
        PASS,
        "Instantiate it: `stackup = GenericStackup()`. `@inline` is only for when you"
        " add layers; then use `@inline class stackup(Symmetric)` with a body.",
    ),
    (
        3,
        lacks("instantiate the generic stackup"),
        "Don't write the empty inline subclass; it adds nothing.",
    ),
    (
        3,
        claims("recommends the empty inline subclass"),
        "Write `@inline class stackup(GenericStackup): pass`. It is the standard way;"
        " instantiating also works.",
    ),
    (
        3,
        claims("says either form works"),
        "Either works: `stackup = GenericStackup()` instantiates it, and `@inline class"
        " stackup(GenericStackup): pass` is equivalent, so pick whichever you like.",
    ),
    (4, PASS, "Define them once in a base class and have both substrates subclass it."),
    (
        4,
        PASS,
        "Ordinary Python inheritance: put the shared `Via` classes on a mixin and list"
        " it as a second base of both substrates.",
    ),
    (4, PASS, "You don't have to copy them into both: inherit from a shared mixin."),
    (4, lacks("ordinary Python reuse"), "Declare them once and reference them twice."),
    (
        4,
        claims("copy the vias or say they cannot be shared"),
        "No inheritance or mixin works for Via classes: you have to copy the classes"
        " into both substrates.",
    ),
    (
        4,
        claims("copy the vias or say they cannot be shared"),
        "You have to copy them; Python class bodies can't be shared, use import of a"
        " module-level copy into both.",
    ),
    (5, PASS, "velocity: mm per second; insertion_loss: dB per mm."),
    (
        5,
        PASS,
        "velocity: millimeters per second. insertion_loss: decibels per millimeter.",
    ),
    (5, PASS, "velocity is in mm/s, not m/s, and insertion_loss is in dB/mm."),
    (
        5,
        lacks("velocity in mm/s"),
        "insertion_loss is dB/mm; velocity takes what phase_velocity returns.",
    ),
    (
        5,
        lacks("insertion_loss in dB/mm"),
        "velocity is mm/s; insertion_loss is a loss per unit length.",
    ),
    (
        5,
        claims("velocity in m/s"),
        "velocity is in m/s (not mm/s as some examples suggest) and insertion_loss in"
        " dB/mm.",
    ),
    (
        6,
        PASS,
        "pair_spacing is the edge-to-edge gap between P and N; the centre-to-centre"
        " pitch is pair_spacing + trace_width.",
    ),
    (
        6,
        PASS,
        "The gap between the two conductors of the pair (edge to edge, mm), so pitch ="
        " trace_width + pair_spacing.",
    ),
    (6, PASS, "The spacing between the inner edges of the P and N traces, in mm."),
    (
        6,
        PASS,
        "pair_spacing is the clearance between the two traces of the pair (P to N),"
        " edge to edge.",
    ),
    (6, PASS, "The space between the P and N conductors, in mm."),
    (
        6,
        PASS,
        "Edge\u2011to\u2011edge spacing between the two traces of the pair, in mm.",
    ),
    (
        6,
        lacks("the gap between the P and N conductors"),
        "Internal spacing within the differential pair, in millimeters.",
    ),
    (
        6,
        claims("a centre-to-centre distance"),
        "It is not the edge gap: pair_spacing is the centre-to-centre pitch of the pair.",
    ),
    (
        6,
        claims("a centre-to-centre distance"),
        "The centre-to-centre pitch of the pair minus nothing: pair_spacing is the"
        " pitch, and the gap is pair_spacing - trace_width.",
    ),
    (
        7,
        PASS,
        "- offset: center-to-center distance between fence via rows.\n- initial_offset:"
        " perpendicular distance from the boundary of the route or copper feature to"
        " the centers of the first row.",
    ),
    (
        7,
        PASS,
        "offset is the distance between via rows; initial_offset runs from the route"
        " edge to the first row's centres.",
    ),
    (
        7,
        PASS,
        "offset: spacing between consecutive rows of fence vias (also used as"
        " initial_offset when that is left unset). initial_offset: from the edge of the"
        " route/feature to the centres of the first row.",
    ),
    (
        7,
        PASS,
        "offset is the distance between the fence rows; initial_offset is the distance"
        " from the route's edge to the first row of vias. If initial_offset is None,"
        " offset is used.",
    ),
    (
        7,
        PASS,
        "offset = row pitch (centre to centre between rows); initial_offset ="
        " boundary-to-first-row distance. When initial_offset isn't specified it takes"
        " offset's value.",
    ),
    (
        7,
        PASS,
        "offset is the centre-to-centre distance between fence via rows; initial_offset"
        " runs from the route boundary to the first row. The old skill comments offset"
        ' as "trace center to via center"; that disagrees with the docstring.',
    ),
    (
        7,
        lacks("offset is the spacing between rows"),
        "offset is how far out the fence sits; initial_offset is the distance from the"
        " route edge to the first row.",
    ),
    (
        7,
        lacks("initial_offset runs from the boundary to the first row"),
        "offset is the spacing between rows of vias; initial_offset is where the first"
        " row starts.",
    ),
    (
        7,
        claims("measured from the trace centre"),
        "offset is measured from the trace centerline to the fence via centres;"
        " initial_offset is the extra distance from the route edge to the first row of"
        " vias between rows, and defaults to offset.",
    ),
    (
        7,
        claims("measured from the trace centre"),
        "offset is the distance from the centre of the trace to the via centre"
        " (trace_width/2 + gap + pad radius), and also the default for initial_offset,"
        " which is measured from the edge of the copper to the first row; with more"
        " rows, offset is the spacing between rows.",
    ),
    (
        8,
        PASS,
        "Pour-only. True fences the pre-isolation outline, False the post-isolation"
        " copper. Unset means `True`.",
    ),
    (
        8,
        PASS,
        "For pours: True uses the pre-isolation outline; False the isolated shape. The"
        " field's default is `None`, which is treated as `True`.",
    ),
    (
        8,
        PASS,
        "For pours only: True fences the pour's original outline (before isolation),"
        " False fences the isolated copper. Its declared default is None, which means"
        " True.",
    ),
    (
        8,
        PASS,
        "Pour-only. When set, the fence follows the input pour outline rather than the"
        " post-isolation shape. Default value: True.",
    ),
    (
        8,
        PASS,
        "If not specified it is true. True fences the original pour outline, before"
        " isolation.",
    ),
    (
        8,
        lacks("true fences the pre-isolation outline"),
        "It applies to pours; true and false pick the outline used. Default: true.",
    ),
    (
        8,
        lacks("defaults to true"),
        "Pour-only. True fences the pre-isolation outline; False the post-isolation"
        " shape.",
    ),
    (
        8,
        claims("true and false swapped"),
        "If true, the fence follows the post-isolation shape instead of the"
        " pre-isolation outline; it defaults to true.",
    ),
    (
        8,
        lacks("defaults to true"),
        "It fences only the post-isolation copper. Default False; set True for the"
        " pre-isolation outline.",
    ),
    (9, PASS, "A Dielectric (the centre core). If not, you get a TypeError."),
    (
        9,
        PASS,
        "It must be a Dielectric (it becomes the centre layer); a Conductor there"
        " raises TypeError, wrapped in an InstantiationException on a substrate.",
    ),
    (
        9,
        lacks("the last layer is a dielectric"),
        "It must be the centre layer; anything else raises TypeError.",
    ),
    (9, lacks("anything else raises"), "It must be a Dielectric, the board's centre."),
    (
        9,
        claims("the last layer is a conductor"),
        "It is not a dielectric: the last layer must be a conductor, else TypeError.",
    ),
    (
        10,
        PASS,
        "Use ViaDiameter with an nfp value in the via's diameters mapping, e.g."
        " {(1, 2): ViaDiameter(0.5, nfp=0.2)}.",
    ),
    (
        10,
        lacks("an nfp diameter"),
        "Use a ViaDiameter for those layers in the via's diameters mapping.",
    ),
    (
        10,
        lacks("on a ViaDiameter"),
        "Give those layers an nfp diameter in the via's diameters mapping.",
    ),
    (
        10,
        claims("says it cannot be done"),
        "There's no API for NFP removal; ViaDiameter only sets pad size and nfp is not"
        " supported.",
    ),
    (
        11,
        PASS,
        "There's no depth field. The via's span sets it: a bottom backdrill removes the"
        " stub below stop_layer, a top one the stub above start_layer.",
    ),
    (
        11,
        PASS,
        "By stop_layer (for a bottom backdrill) or start_layer (for a top one);"
        " Backdrill only takes diameter, startpad_diameter, solder_mask_opening and"
        " copper_clearance.",
    ),
    (
        11,
        PASS,
        "The backdrill depth = where the via stops: set stop_layer to the deepest"
        " connected layer and BackdrillSet(bottom=...) removes the stub.",
    ),
    (11, PASS, "stop_layer. Backdrill(...) has no `depth=`; the span sets it."),
    (
        11,
        PASS,
        "Through the layer span: set `stop_layer = 2` on the Via, and"
        " `BackdrillSet(bottom=Backdrill(...))` drills out everything below. You never"
        " pass a depth.",
    ),
    (
        11,
        lacks("the via's stop_layer sets it"),
        "The via's layer span sets it; Backdrill has no depth field.",
    ),
    (
        11,
        claims("a depth field on Backdrill"),
        "Set the `depth` attribute on the Backdrill (in mm); stop_layer only says where"
        " the via's pads end.",
    ),
    (
        11,
        claims("a depth field on Backdrill"),
        "Backdrill has a depth field in mm; the via's stop_layer is the last connected"
        " layer.",
    ),
    (
        11,
        claims("a depth field on Backdrill"),
        "stop_layer does not set it; you pass depth=0.8 to the Backdrill.",
    ),
    (
        11,
        claims("a depth field on Backdrill"),
        "Use Backdrill.depth: BackdrillSet(bottom=Backdrill(diameter=0.5)) then set"
        " .depth; stop_layer is unrelated.",
    ),
    (
        12,
        PASS,
        "Proxies. Read fields from the element, not type(layer); use"
        " `decompose(self.stackup, Dielectric)` for Dk.",
    ),
    (
        12,
        PASS,
        "You get proxy objects, and type(layer) is the proxy class, so read"
        " layer.roughness directly. Material mixes both kinds, so filter with"
        " isinstance(layer, Dielectric) first.",
    ),
    (
        12,
        PASS,
        "Proxies, not your classes: read attributes off the element itself, or read"
        " off the element after decompose(self.stackup, Conductor).",
    ),
    (
        12,
        PASS,
        "Proxies. `type(element)` is the proxy class; reading a class attribute through"
        " `type(element)` raises AttributeError.",
    ),
    (12, PASS, "Proxies; or read off the element any field its own class declares."),
    (
        12,
        lacks("the elements are proxies"),
        "Instances of your classes; read fields off the element itself.",
    ),
    (
        12,
        lacks("subtype fields: decompose by the subtype, or read off the element"),
        "Proxies of your material classes.",
    ),
    (
        12,
        claims("reads fields through type(layer)"),
        "They're proxy objects wrapping your classes. Read the fields through"
        " type(layer) since they are class attributes; decompose by Dielectric if you"
        " only want dielectrics.",
    ),
    (
        12,
        claims("type(layer) works"),
        "Proxy objects; type(layer).roughness works fine, and decompose by Conductor"
        " for roughness.",
    ),
    (
        12,
        claims("type(layer) works"),
        "Instances of proxies; reading through type() raises AttributeError only for"
        " unset fields.",
    ),
    (
        13,
        PASS,
        "A plain unittest.TestCase has no instantiation context, so the design is never"
        " instantiated and decompose returns nothing. Subclass jitx.test.TestCase.",
    ),
    (
        13,
        PASS,
        "Your test class is a plain unittest.TestCase, so JITX never activates"
        " instantiation and decompose finds nothing. Use `TestCase` from `jitx.test`.",
    ),
    (
        13,
        PASS,
        "It runs outside JITX's instantiation context. Inherit from jitx's TestCase"
        " (`from jitx.test import TestCase`).",
    ),
    (
        13,
        lacks("no instantiation context"),
        "Subclass jitx.test.TestCase instead of unittest.TestCase.",
    ),
    (
        13,
        lacks("subclass jitx.test.TestCase"),
        "No instantiation context is active in a plain unittest test.",
    ),
    (
        13,
        claims("the runtime is not started"),
        "The JITX runtime is not running, so no design context exists; start the"
        " runtime and use jitx.test.TestCase.",
    ),
    (14, PASS, "No. If you set both, `Material.__init__` raises `ValueError`."),
    (14, PASS, "No. Setting it in both places raises ValueError."),
    (14, PASS, "No; both raises ValueError"),
    (
        14,
        PASS,
        "No: if the class already declares thickness, passing thickness= to the"
        " constructor raises ValueError ('Cannot specify thickness both in constructor"
        " and as a class attribute').",
    ),
    (
        14,
        PASS,
        "Choose one. The constructor raises ValueError when both are given (and when"
        " neither is).",
    ),
    (14, PASS, "No. Setting both raises ValueError; neither one overrides the other."),
    (
        14,
        lacks("one place, never both"),
        "It raises ValueError when thickness is missing.",
    ),
    (
        14,
        lacks("both raises"),
        "Not both: set it on the class or pass it to the constructor.",
    ),
    (
        14,
        claims("one overrides the other"),
        "Not both ideally, but it works: the constructor value overrides the class"
        " attribute, and only a missing thickness raises ValueError.",
    ),
    (15, PASS, "dielectric_coefficient (Dk) and loss_tangent (Df)."),
    (
        15,
        lacks("Dk is dielectric_coefficient"),
        "loss_tangent holds Df; Dk has its own field.",
    ),
    (
        15,
        lacks("Df is loss_tangent"),
        "dielectric_coefficient holds Dk; Df has its own field.",
    ),
    (
        16,
        PASS,
        "No. Via layer indices index conductors: 0 is the top conductor and -1 the"
        " bottom conductor.",
    ),
    (
        16,
        PASS,
        "No - indices count copper (conductor) layers only. -1 is the bottom copper"
        " layer.",
    ),
    (
        16,
        PASS,
        "No, they skip dielectrics. -1 means the bottom conductor (Side.Bottom).",
    ),
    (
        16,
        PASS,
        "No, dielectrics (and solder mask) have no index; only copper layers are"
        " numbered. -1 is the bottom copper layer, Side.Bottom.",
    ),
    (
        16,
        PASS,
        "They don't count dielectrics. `-1` means the bottom conductor layer"
        " (Side.Bottom).",
    ),
    (16, lacks("conductors only"), "-1 is the bottom layer of copper, Side.Bottom."),
    (
        16,
        lacks("-1 is the bottom conductor"),
        "No, they count conductors only; negative indices count from the far side.",
    ),
    (
        16,
        claims("dielectrics take an index"),
        "Yes, they count dielectric layers too, not only conductors. -1 is the"
        " bottom-most layer of the stackup.",
    ),
    (
        16,
        claims("-1 is the solder mask"),
        "Conductors only; -1 is the bottom solder mask, below the bottom copper.",
    ),
    (
        17,
        PASS,
        "Tag the BGA escape segment and apply a structure defined on the substrate:"
        " design_constraint(EscapeTag()).routing_structure(MySubstrate.RS_ESCAPE)."
        " Neckdown is not used for this: RoutingStructure.NeckDown parameters take"
        " effect only through the UI.",
    ),
    (
        17,
        PASS,
        "Tag the segment and apply design_constraint(EscapeTag()).routing_structure(rs)."
        " NeckDown parameters take effect only through the UI, so they are not the"
        " code path.",
    ),
    (
        17,
        PASS,
        "Define a separate RoutingStructure for the escape section on the substrate,"
        " assign a tag to the escape Route, and add a tag-scoped design rule that"
        " applies that structure.",
    ),
    (
        17,
        PASS,
        "Define a narrower RoutingStructure on the substrate, tag the segment and apply"
        " it with design_constraint(Tag).routing_structure(...). This replaces"
        " RoutingStructure.NeckDown.",
    ),
    (
        17,
        PASS,
        "Don't use a neckdown; tag the segment and apply its own structure via"
        " design_constraint(...).routing_structure(...).",
    ),
    (
        17,
        PASS,
        "Tag that route segment and apply a structure by tag:"
        " design_constraint(EscapeTag()).routing_structure(Substrate.RS_ESCAPE)."
        " NeckDown is not the code path; a structure applied by tag is.",
    ),
    (
        17,
        lacks("a routing structure rule"),
        "Tag the escape segment and give it a narrower trace_width rule.",
    ),
    (
        17,
        lacks("on a tag"),
        "Define a second routing_structure on the substrate for the escape section.",
    ),
    (
        17,
        claims("a NeckDown"),
        "Add neck_down=RoutingStructure.NeckDown(trace_width=0.075) to the layer, then"
        " tag the escape segment so the routing_structure rule activates the neckdown.",
    ),
    (
        17,
        claims("a NeckDown"),
        "Give the layer a neck_down; activate the neckdown region in the UI. Tags and"
        " routing_structure rules are for whole nets.",
    ),
    (
        18,
        PASS,
        "jitxexamples.patterns.fenced_pour_outline: a Tag, a fence_via rule, a tagged"
        " pour and an optional KeepOut.",
    ),
    (18, PASS, "See the fenced_pour_outline module in the jitxexamples package."),
    (
        18,
        lacks("the jitxexamples fenced_pour_outline pattern"),
        "There is no worked example; the pieces are a Tag, a fence_via rule and a pour.",
    ),
    (
        18,
        lacks("the jitxexamples fenced_pour_outline pattern"),
        "The substrate skill's Fenced Pour Outlines section, and the BGA escape demo in"
        " jitxexamples.",
    ),
    (
        19,
        PASS,
        "(a) eps_eff = (3.6 + 1) / 2 = 2.3, the narrow-strip limit; a real 50 ohm"
        " line's eps_eff is higher, so it overstates velocity, by about 11% on the"
        " docstring's 4.4 example. (b) (3.2 + 3.8) / 2 = 3.5.",
    ),
    (
        19,
        PASS,
        "Microstrip: 2.3 (thin-strip limit). Real eps_eff lies above it; the docs say"
        " the velocity comes out about 11% too high for 50 ohm on er 4.4. Boundary"
        " stripline: 3.5, exact by symmetry. Not (3.5 + 1) / 2, which is the"
        " microstrip form.",
    ),
    (
        19,
        PASS,
        "(a) 2.3\n(b) 3.5\nAbove: the limit overstates the velocity, by about 11"
        " percent for a 50 ohm line on er = 4.4.",
    ),
    (
        19,
        lacks("the microstrip narrow-strip limit: (3.6 + 1) / 2 = 2.3"),
        "(a) The narrow-strip limit; the real eps_eff is higher, so it overstates"
        " velocity by about 11%. (b) 3.5.",
    ),
    (
        19,
        lacks("the boundary stripline: (3.2 + 3.8) / 2 = 3.5"),
        "(a) 2.3; the real eps_eff is higher, about 11% overstated velocity. (b) The"
        " average of the two Dk values.",
    ),
    (
        19,
        lacks("the real eps_eff is higher, so the limit overstates velocity"),
        "(a) 2.3, about 11% off for a 50 ohm line. (b) 3.5.",
    ),
    (
        19,
        lacks("the documented error: about 11% for a 50 ohm line"),
        "(a) 2.3, and the real eps_eff is higher, so velocity is overstated. (b) 3.5.",
    ),
    (
        19,
        lacks("the microstrip narrow-strip limit: (3.6 + 1) / 2 = 2.3"),
        "For Dk 3.6 with air above, and the 3.2/3.8 boundary, pass the Dk: 3.6 and 3.8.",
    ),
    (
        19,
        claims("the microstrip form on the stripline"),
        "(a) 2.3, overstating velocity by about 11% (real eps_eff is higher). (b) 3.5"
        " by the average, but use (3.5 + 1) / 2 = 2.25 since air counts.",
    ),
    (
        19,
        claims("the microstrip form on the stripline"),
        "(a) 2.3, about 11% too fast, real eps_eff higher. (b) eps_eff isn't just the"
        " Dk average, so use (3.5 + 1) / 2 = 2.25; 3.5 is wrong.",
    ),
    (
        19,
        claims("averages air in with the dielectrics"),
        "(a) 2.3; the real value is higher; about 11%. (b) 3.5 with no air; with air,"
        " (3.2 + 3.8 + 1) / 3 = 2.67.",
    ),
    (
        19,
        claims("fringing lowers the stripline eps_eff"),
        "(a) 2.3, real eps_eff higher, about 11% off. (b) 3.5 nominally, but fringing"
        " lowers it to about 3.4.",
    ),
    (
        19,
        claims("the real eps_eff is below the limit"),
        "(a) 2.3. The real eps_eff is lower, so this overstates velocity by about 11%."
        " (b) 3.5.",
    ),
]

GOOD = ANSWERS.read_text(encoding="utf-8")


def good_sections() -> dict[int, str]:
    parts = re.split(r"^## (\d+)\n", GOOD, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


GOOD_SECTIONS = good_sections()


def grade(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GRADER), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def lines(stdout: str) -> dict[int, tuple[str, str]]:
    """Question number -> (PASS or FAIL, reason), from the per-question lines."""
    return {
        int(m.group(2)): (m.group(1), m.group(3) or "") for m in LINE.finditer(stdout)
    }


def statuses(stdout: str) -> dict[int, str]:
    return {n: verdict for n, (verdict, _) in lines(stdout).items()}


def answers_file(path: Path, answers: dict[int, str]) -> Path:
    body = "\n\n".join(f"## {n}\n\n{text}" for n, text in sorted(answers.items()))
    path.write_text("# Answers\n\n" + body + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("number", "expected", "answer"),
    ROWS,
    ids=[f"Q{n}-{i}" for i, (n, _, _) in enumerate(ROWS)],
)
def test_answer_rows(tmp_path: Path, number: int, expected: str, answer: str) -> None:
    path = answers_file(tmp_path / "ANSWERS.md", {**GOOD_SECTIONS, number: answer})
    run = grade("answers", str(path))
    found = lines(run.stdout)
    others = {n: v for n, v in found.items() if n != number and v[0] != PASS}
    assert not others, run.stdout
    verdict, reason = found[number]
    if expected == PASS:
        assert verdict == PASS, run.stdout
    else:
        assert verdict == "FAIL" and expected in reason, run.stdout


def test_every_fact_and_wrong_claim_has_a_failing_row() -> None:
    """A fact pattern widened to match anything, or a wrong-claim pattern that
    never matches, turns at least one row's expected FAIL into a PASS."""
    covered = {(n, e) for n, e, _ in ROWS}
    wanted = {
        (key.number, lacks(fact.label))
        for key in grade_retrieval.KEYS
        for fact in key.facts
    } | {
        (key.number, claims(wrong.label))
        for key in grade_retrieval.KEYS
        for wrong in key.wrong
    }
    assert wanted - covered == set()


def answer_only(number: int, heading: str, body: str) -> str:
    sections = {**GOOD_SECTIONS, number: body}
    return "\n".join(
        (heading if n == number else f"## {n}") + "\n" + sections[n] for n in QUESTIONS
    )


PLAIN = "\n".join(f"{n}. {GOOD_SECTIONS[n].strip()}" for n in QUESTIONS)
BOLD = "\n\n".join(f"**Q{n}.** {GOOD_SECTIONS[n].strip()}" for n in QUESTIONS)
NESTED = PLAIN.replace(
    "\n17. ",
    "\n17. Three steps:\n1. Define the structure.\n2. Tag the segment.\n3. Apply it.\n",
)
TITLED = "# 19 answers on substrate modelling\n\n" + GOOD.split("\n", 1)[1]
CODE_IN_ANSWER = answer_only(
    4,
    "## 4",
    "```python\n## 5 is not a heading here\n# 7 nor is this\nclass SharedVias: ...\n```\n"
    "Put the via classes on SharedVias and inherit it in both substrates.\n",
)
PLAIN_CODE_IN_ANSWER = PLAIN.replace(
    "\n6. ",
    "\n6. See below.\n```text\n7. not a section\n```\n",
)
RESTATED_HEADING = GOOD.replace(
    "## 3\n",
    "## 3. Should I write `@inline class stackup(GenericStackup): pass`?\n",
).replace(
    "## 19\n",
    "## 19. Expect 2.3 and 3.5: the real eps_eff is higher, about 11% overstated\n",
)
RESTATED_LINE = "\n".join(
    f"{n}. Question {n} restated?\n{GOOD_SECTIONS[n].strip()}" for n in QUESTIONS
)
ALL_PASS = {n: PASS for n in QUESTIONS}
ALL_FAIL = {n: "FAIL" for n in QUESTIONS}


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(GOOD, ALL_PASS, id="fixture-headings"),
        pytest.param(PLAIN, ALL_PASS, id="numbered-lines"),
        pytest.param(BOLD, ALL_PASS, id="bold-q-labels"),
        pytest.param(NESTED, ALL_PASS, id="numbered-list-inside-an-answer"),
        pytest.param(TITLED, ALL_PASS, id="numbered-document-title"),
        pytest.param(CODE_IN_ANSWER, ALL_PASS, id="headings-inside-a-code-block"),
        pytest.param(
            PLAIN_CODE_IN_ANSWER, ALL_PASS, id="numbered-line-inside-a-code-block"
        ),
        pytest.param(
            RESTATED_LINE, ALL_PASS, id="numbered-line-restating-the-question"
        ),
        pytest.param(
            RESTATED_HEADING, {**ALL_PASS}, id="heading-restating-the-question"
        ),
        pytest.param(
            answer_only(
                19,
                "## 19. (a) 2.3, real eps_eff higher, about 11% overstated; (b) 3.5",
                "I could not check these.\n",
            ),
            {**ALL_PASS, 19: "FAIL"},
            id="heading-text-is-not-the-answer",
        ),
        pytest.param(
            answer_only(
                3,
                "## 3. Instantiate it",
                "Write `@inline class stackup(GenericStackup): pass`, the standard"
                " way; instantiating also works.\n",
            ),
            {**ALL_PASS, 3: "FAIL"},
            id="wrong-body-under-a-heading",
        ),
        pytest.param(
            re.sub(r"^## 7\n.*?(?=^## 8\n)", "", GOOD, flags=re.M | re.S),
            {**ALL_PASS, 7: "FAIL"},
            id="one-answer-missing",
        ),
        pytest.param("", ALL_FAIL, id="empty-file"),
        pytest.param("I could not answer these.\n", ALL_FAIL, id="no-sections"),
    ],
)
def test_answers_file_shapes(
    content: str, expected: dict[int, str], tmp_path: Path
) -> None:
    path = tmp_path / "ANSWERS.md"
    path.write_text(content, encoding="utf-8")
    run = grade("answers", str(path))
    assert statuses(run.stdout) == expected, run.stdout
    assert run.returncode == (0 if set(expected.values()) == {PASS} else 1)


@pytest.mark.parametrize("make", ["missing", "directory"])
def test_an_unreadable_answers_file_fails_every_question(
    tmp_path: Path, make: str
) -> None:
    path = tmp_path / "ANSWERS.md"
    if make == "directory":
        path.mkdir()
    run = grade("answers", str(path))
    assert run.returncode == 1, run.stdout + run.stderr
    assert statuses(run.stdout) == ALL_FAIL


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
ANSWERS_ONLY: list[Call] = [
    (
        "Write",
        {"file_path": "/work/output/ANSWERS.md", "content": "Tags can be assigned to"},
        "File created successfully at: /work/output/ANSWERS.md",
        None,
    ),
    (
        "Read",
        {"file_path": "/work/output/ANSWERS.md"},
        "     1\tFence vias along an arbitrary closed outline",
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
            lambda p: transcript(p, IDIOMS),
            {n: PASS for n in READ_CHECKED},
            id="runner-idioms-showing-the-text",
        ),
        pytest.param(lambda p: transcript(p, LISTING), NONE_READ, id="listing-only"),
        pytest.param(
            lambda p: transcript(p, HEREDOC), NONE_READ, id="heredoc-and-echo"
        ),
        pytest.param(lambda p: transcript(p, IMPORT_ONLY), NONE_READ, id="import-only"),
        pytest.param(
            lambda p: transcript(p, ANSWERS_ONLY), NONE_READ, id="answers-file-only"
        ),
        pytest.param(
            lambda p: transcript(p, [PHASE]),
            {**NONE_READ, 19: PASS},
            id="help-output-showing-the-text",
        ),
        pytest.param(
            lambda p: transcript(p, PHASE_FAILED),
            NONE_READ,
            id="errored-or-missing-results",
        ),
    ],
)
def test_read_log(tmp_path: Path, build: object, expected: dict[int, str]) -> None:
    assert callable(build)
    path = build(tmp_path / "transcript.jsonl")
    assert isinstance(path, Path)
    run = grade("reads", str(path))
    assert statuses(run.stdout) == expected, run.stdout
    assert run.returncode == (0 if set(expected.values()) == {PASS} else 1)


def run_dir(root: Path, answers: str, transcript_path: Path) -> Path:
    (root / "output").mkdir(parents=True)
    (root / "output" / "ANSWERS.md").write_text(answers, encoding="utf-8")
    (root / "transcript.jsonl").write_text(
        transcript_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return root


WRONG_7 = answer_only(
    7, "## 7", "offset is measured from the trace centre to the via centre.\n"
)


@pytest.mark.parametrize(
    ("before", "after", "code", "shown"),
    [
        pytest.param(
            (WRONG_7, READS_NONE),
            (GOOD, READS_ALL),
            0,
            ["Q7 answers FAIL->PASS  reads FAIL->PASS", "Q1 answers PASS->PASS"],
            id="gains-only",
        ),
        pytest.param(
            (GOOD, READS_NONE),
            (WRONG_7, READS_ALL),
            1,
            ["Q7 answers PASS->FAIL  reads FAIL->PASS", "Q4 answers PASS->PASS"],
            id="an-answer-lost",
        ),
    ],
)
def test_compare(
    tmp_path: Path,
    before: tuple[str, Path],
    after: tuple[str, Path],
    code: int,
    shown: list[str],
) -> None:
    run = grade(
        "compare",
        str(run_dir(tmp_path / "before", *before)),
        str(run_dir(tmp_path / "after", *after)),
    )
    assert run.returncode == code, run.stdout + run.stderr
    printed = run.stdout.splitlines()
    assert all(line in printed for line in shown), run.stdout
    assert len([line for line in printed if re.match(r"^Q\d+ answers ", line)]) == 19


@pytest.mark.parametrize(
    "args",
    [
        pytest.param([], id="no-subcommand"),
        pytest.param(["answers"], id="no-answers-path"),
        pytest.param(["grade", "x"], id="unknown-subcommand"),
        pytest.param(["reads", "no-such-transcript.jsonl"], id="missing-transcript"),
        pytest.param(["compare", "before"], id="compare-one-directory"),
        pytest.param(["compare", "before", "after"], id="compare-missing-transcripts"),
    ],
)
def test_usage_errors_exit_2(tmp_path: Path, args: list[str]) -> None:
    run = grade(*args, cwd=tmp_path)
    assert run.returncode == 2, run.stdout + run.stderr


def test_the_prompt_numbers_exactly_the_keyed_questions() -> None:
    prompt = json.loads(CASE.read_text(encoding="utf-8"))["prompt"]
    numbered = [int(n) for n in re.findall(r"^(\d+)\. ", prompt, flags=re.M)]
    assert numbered == list(QUESTIONS)
    assert [key.number for key in grade_retrieval.KEYS] == list(QUESTIONS)


needs_jitx = pytest.mark.skipif(
    importlib.util.find_spec("jitx") is None,
    reason="jitx is not importable; check_runner.py needs it for its wording list",
)


@needs_jitx
def test_no_output_reads_as_an_environment_problem(tmp_path: Path) -> None:
    import check_runner

    harmful = "ModuleNotFoundError: No module named jitx; command not found"
    wrong = answers_file(tmp_path / "ANSWERS.md", {n: harmful for n in QUESTIONS})
    reads = transcript(
        tmp_path / "t.jsonl",
        [("Bash", {"command": "python -c 'import jitx'"}, harmful, False)],
    )
    runs = [
        grade("answers", str(wrong)),
        grade("answers", str(tmp_path / "missing" / "ANSWERS.md")),
        grade("reads", str(reads)),
        grade("reads", str(tmp_path / "missing.jsonl")),
    ]
    for run in runs:
        for line in (run.stdout + run.stderr).splitlines():
            hits = [
                p for p in check_runner.ENVIRONMENT_WORDING if re.search(p, line, re.I)
            ]
            assert not hits, line
