"""Tests for the frames layout_report.py reports footprints in.

They need a Python that imports jitx and shapely. Set JITX_PYTHON to one: the
tests then fail if it cannot import them. Without JITX_PYTHON they use the
running interpreter when it can, and are skipped otherwise. No runtime or
session is contacted: the design is instantiated in the driver below and
queried offline.

Every expected value is worked by hand from the design in DRIVER: a two-pad
part with pads at (-0.5, 0.2) and (0.5, 0.2), each 0.6 by 0.4, and a 2.0 by
1.0 courtyard centred on (0.0, 0.2), so the courtyard spans -1.0 to 1.0 in x
and -0.3 to 0.7 in y in the part's own frame. A second part has the same
land pattern at (0.3, -0.1) turned 90 degrees inside the part.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent


def imports_jitx(python: str) -> bool:
    probe = subprocess.run(
        [python, "-c", "import jitx.run, shapely"],
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


JITX_PYTHON = os.environ.get("JITX_PYTHON") or (
    sys.executable if imports_jitx(sys.executable) else None
)

DRIVER = textwrap.dedent(
    """
    import json
    import sys
    from typing import Any

    import jitx.run

    jitx.run.autodetect_design = False

    from jitx._instantiation import instantiation
    from jitx.circuit import Circuit
    from jitx.component import Component
    from jitx.feature import Courtyard
    from jitx.landpattern import Landpattern, Pad
    from jitx.layerindex import Side
    from jitx.net import Port
    from jitx.query import query
    from jitx.sample import SampleDesign
    from jitx.shapes.composites import rectangle
    from jitx.transform import IDENTITY

    sys.path.insert(0, sys.argv[1])
    import layout_report


    class P(Pad):
        shape = rectangle(0.6, 0.4)


    class LP(Landpattern):
        p1 = P().at(-0.5, 0.2)
        p2 = P().at(0.5, 0.2)
        courtyard = Courtyard(rectangle(2.0, 1.0).at(0.0, 0.2))


    class C(Component):
        a = Port()
        b = Port()
        landpattern = LP()


    class Turned(Component):
        a = Port()
        b = Port()
        landpattern = LP().at(0.3, -0.1, rotate=90)


    class Blk(Circuit):
        def __init__(self) -> None:
            self.free = C()
            self.fixed = C().at(1.0, 2.0, rotate=90)
            self.turned = Turned()
            self.turned_fixed = Turned().at(1.0, 2.0, rotate=90)


    class Top(Circuit):
        def __init__(self) -> None:
            self.blk = Blk().at(10.0, 5.0, rotate=90)
            self.under = Blk().at(20.0, 5.0, on=Side.Bottom)


    class D(SampleDesign):
        circuit = Top()


    class Offline:
        def __init__(self, design: D) -> None:
            self.design = design

        def query(self, kind: type[Any]) -> Any:
            return query(self.design, kind, transform=IDENTITY)


    with instantiation.activate():
        design = D()
    components, pads, _, _ = layout_report.footprints(
        Offline(design),
        lambda trace: ".".join(str(step) for step in trace.path),
        lambda obj: None,
    )
    json.dump({"components": components, "pads": pads}, sys.stdout)
    """
)


@unittest.skipUnless(JITX_PYTHON, "set JITX_PYTHON to a Python with jitx and shapely")
class FootprintFrames(unittest.TestCase):
    state: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        assert JITX_PYTHON is not None
        if not imports_jitx(JITX_PYTHON):
            raise AssertionError(
                f"JITX_PYTHON={JITX_PYTHON} cannot import jitx.run and shapely"
            )
        done = subprocess.run(
            [JITX_PYTHON, "-B", "-c", DRIVER, str(SCRIPTS)],
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode != 0:
            raise AssertionError(f"driver failed:\n{done.stderr}")
        cls.state = json.loads(done.stdout)

    def component(self, name: str) -> dict[str, Any]:
        found = [c for c in self.state["components"] if c["key"].endswith(name)]
        self.assertEqual(len(found), 1, f"{name}: {found}")
        return found[0]

    def pad(self, part: str, name: str) -> dict[str, Any]:
        owner = self.component(part)["key"]
        found = [
            p
            for p in self.state["pads"]
            if p["key"].startswith(owner + ".") and p["key"].endswith("." + name)
        ]
        self.assertEqual(len(found), 1, f"{part} {name}: {found}")
        return found[0]

    def near(self, got: list[float] | tuple[float, ...], want: list[float]) -> None:
        self.assertEqual(len(got), len(want), got)
        for g, w in zip(got, want, strict=True):
            self.assertAlmostEqual(g, w, places=3, msg=f"{got} != {want}")

    def bounds(self, outline: list[list[float]]) -> list[float]:
        xs = [x for x, _ in outline]
        ys = [y for _, y in outline]
        return [min(xs), min(ys), max(xs), max(ys)]

    def own_frame(self, part: str) -> None:
        comp = self.component(part)
        self.assertIsNone(comp["placement"])
        self.assertIsNone(comp["courtyard"])
        self.near(comp["courtyard_local"], [-1.0, -0.3, 1.0, 0.7])
        p1, p2 = self.pad(part, "p1"), self.pad(part, "p2")
        self.assertFalse(p1["placed"])
        self.near(p1["pos"], [-0.5, 0.2])
        self.near(p2["pos"], [0.5, 0.2])
        self.near(self.bounds(p1["outline"]), [-0.8, 0.0, -0.2, 0.4])

    def test_unplaced_part_is_in_its_own_frame_inside_a_placed_circuit(self) -> None:
        # The circuit sits at (10, 5) turned 90 degrees. None of that may show
        # in an unplaced part: its pads and courtyard_local share one frame.
        self.own_frame("blk.free")

    def test_unplaced_part_is_in_its_own_frame_inside_a_bottom_circuit(self) -> None:
        self.own_frame("under.free")

    def test_placed_part_is_in_board_coordinates(self) -> None:
        # (1, 2) turned 90 degrees is (-2, 1); the circuit adds (10, 5): the
        # part is at (8, 6), turned 90 + 90 = 180. A pad at (-0.5, 0.2) turned
        # 180 is (0.5, -0.2), so (8.5, 5.8) on the board. The courtyard's
        # -0.3..0.7 in y becomes -0.7..0.3, so 5.3..6.3.
        comp = self.component("blk.fixed")
        self.near(comp["placement"][:3], [8.0, 6.0, 180.0])
        self.assertEqual(comp["placement"][3], "top")
        self.near(comp["courtyard"], [7.0, 5.3, 9.0, 6.3])
        self.near(comp["courtyard_local"], [-1.0, -0.3, 1.0, 0.7])
        p1, p2 = self.pad("blk.fixed", "p1"), self.pad("blk.fixed", "p2")
        self.assertTrue(p1["placed"])
        self.near(p1["pos"], [8.5, 5.8])
        self.near(p2["pos"], [7.5, 5.8])

    def test_land_pattern_turned_inside_an_unplaced_part(self) -> None:
        # The land pattern sits at (0.3, -0.1) turned 90 degrees, which takes
        # (x, y) to (-y, x): the pad at (-0.5, 0.2) goes to (-0.2, -0.5), then
        # (0.1, -0.6); the pad at (0.5, 0.2) to (-0.2, 0.5), then (0.1, 0.4).
        # The 0.6 by 0.4 pad stands 0.4 wide and 0.6 tall. The courtyard's
        # x of -1.0..1.0 becomes y, and its y of -0.3..0.7 becomes x of
        # -0.7..0.3: -0.4..0.6 in x and -1.1..0.9 in y after the offset.
        comp = self.component("blk.turned")
        self.assertIsNone(comp["placement"])
        self.near(comp["courtyard_local"], [-0.4, -1.1, 0.6, 0.9])
        self.near(comp["courtyard_size"], [1.0, 2.0])
        p1, p2 = self.pad("blk.turned", "p1"), self.pad("blk.turned", "p2")
        self.near(p1["pos"], [0.1, -0.6])
        self.near(p2["pos"], [0.1, 0.4])
        self.near(self.bounds(p1["outline"]), [-0.1, -0.9, 0.3, -0.3])

    def test_land_pattern_turned_inside_a_placed_part(self) -> None:
        # The part is at (8, 6) turned 180 on the board, as blk.fixed is, and
        # 180 takes (x, y) to (-x, -y). Its own courtyard is the unplaced
        # one's; on the board -0.4..0.6 in x becomes -0.6..0.4, so 7.4..8.4,
        # and -1.1..0.9 in y becomes -0.9..1.1, so 5.1..7.1. The pad at
        # (0.1, -0.6) lands at (7.9, 6.6).
        comp = self.component("blk.turned_fixed")
        self.near(comp["placement"][:3], [8.0, 6.0, 180.0])
        self.near(comp["courtyard_local"], [-0.4, -1.1, 0.6, 0.9])
        self.near(comp["courtyard"], [7.4, 5.1, 8.4, 7.1])
        self.near(self.pad("blk.turned_fixed", "p1")["pos"], [7.9, 6.6])

    def test_placed_part_in_a_bottom_circuit_keeps_its_own_courtyard(self) -> None:
        comp = self.component("under.fixed")
        self.assertEqual(comp["placement"][3], "bottom")
        self.near(comp["courtyard_local"], [-1.0, -0.3, 1.0, 0.7])


SUMMARY_DRIVER = textwrap.dedent(
    """
    import json
    import sys
    from typing import Any

    import jitx.run

    jitx.run.autodetect_design = False

    from jitx._instantiation import instantiation
    from jitx.circuit import Circuit
    from jitx.component import Component
    from jitx.feature import Courtyard, Cutout
    from jitx.landpattern import Landpattern, Pad
    from jitx.layerindex import Side
    from jitx.net import Port
    from jitx.query import query
    from jitx.sample import SampleDesign
    from jitx.shapes.composites import rectangle
    from jitx.shapes.primitive import Circle
    from jitx.transform import IDENTITY

    sys.path.insert(0, sys.argv[1])
    import layout_report


    class P(Pad):
        shape = rectangle(0.6, 0.4)


    class LP(Landpattern):
        p1 = P().at(-0.5, 0.2)
        p2 = P().at(0.5, 0.2)
        courtyard = Courtyard(rectangle(2.0, 1.0).at(0.0, 0.2))


    class LongLP(Landpattern):
        p1 = P().at(-0.5, 0.0)
        p2 = P().at(0.5, 0.0)
        courtyard = Courtyard(rectangle(1.0, 1.0))


    class Hole(Pad):
        shape = rectangle(1.0, 1.0)

        def __init__(self) -> None:
            self.cutout = Cutout(Circle(diameter=0.4))


    class Flat(Pad):
        shape = rectangle(1.0, 1.0)


    class HoleLP(Landpattern):
        p1 = Hole()
        courtyard = Courtyard(rectangle(1.2, 1.2))


    class FlatLP(Landpattern):
        p1 = Flat()
        courtyard = Courtyard(rectangle(1.2, 1.2))


    class C(Component):
        a = Port()
        b = Port()
        landpattern = LP()


    class Long(Component):
        a = Port()
        b = Port()
        landpattern = LongLP()


    class Through(Component):
        a = Port()
        landpattern = HoleLP()


    class Surface(Component):
        a = Port()
        landpattern = FlatLP()


    class Top(Circuit):
        def __init__(self) -> None:
            self.a = Long().at(0.0, 0.0)
            self.b = C().at(1.5, -0.2)
            self.t = Through().at(10.0, 0.0)
            self.u = C().at(10.5, -0.2, on=Side.Bottom)
            self.s = Surface().at(20.0, 0.0)
            self.v = C().at(20.5, -0.2, on=Side.Bottom)
            self.w = C().at(0.0, 10.0)
            self.x = C().at(1.0, 10.0)


    class D(SampleDesign):
        circuit = Top()


    class Nets:
        def find(self, obj: object) -> None:
            return None


    class Offline:
        name = "test"
        nets = Nets()

        def __init__(self, design: D) -> None:
            self.root = design
            self.design = design

        def query(self, kind: type[Any]) -> Any:
            return query(self.design, kind, transform=IDENTITY)


    with instantiation.activate():
        design = D()
    json.dump(layout_report.main(Offline(design)), sys.stdout)
    """
)


@unittest.skipUnless(JITX_PYTHON, "set JITX_PYTHON to a Python with jitx and shapely")
class SummaryOverlaps(unittest.TestCase):
    """``main``'s summary for the design in SUMMARY_DRIVER, worked by hand.

    a: courtyard 1.0 by 1.0 at the origin, x -0.5 to 0.5, and 0.6 by 0.4
    pads at x = -0.5 and 0.5, so its second pad spans x 0.2 to 0.8, 0.3 past
    the courtyard. b, at (1.5, -0.2), has the 2.0 by 1.0 courtyard centred
    0.2 above its origin: x 0.5 to 2.5, y -0.5 to 0.5, meeting a's at x =
    0.5 with no area; its pads (x 0.7 to 1.3 and 1.7 to 2.3) are inside it
    and clear of a's courtyard. a's pad over b's courtyard is x 0.5 to 0.8
    by y -0.2 to 0.2: 0.12 mm2.

    t, at (10, 0) on top, has one 1.0 by 1.0 pad with a hole, x 9.5 to 10.5
    and y -0.5 to 0.5. u, on the bottom at (10.5, -0.2), mirrored in x, has
    its courtyard over x 9.5 to 11.5 and y -0.5 to 0.5, which takes in the
    whole of t's pad: 1.0 mm2. s and v are the same pair with a pad that has
    no hole: s's copper is on top only, so the two do not meet.

    w at (0, 10) and x at (1, 10) have courtyards over x -1 to 1 and 0 to 2,
    y 9.7 to 10.7: 1.0 mm2 of courtyard overlap, listed there only."""

    summary: dict[str, Any]
    state: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        assert JITX_PYTHON is not None
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.run(
                [JITX_PYTHON, "-B", "-c", SUMMARY_DRIVER, str(SCRIPTS)],
                capture_output=True,
                text=True,
                check=False,
                cwd=folder,
            )
            if done.returncode != 0:
                raise AssertionError(f"driver failed:\n{done.stderr}")
            cls.summary = json.loads(done.stdout)
            cls.state = json.loads(Path(cls.summary["written"]).read_text())

    def test_courtyard_overlaps_keep_their_meaning(self) -> None:
        self.assertEqual(self.summary["courtyard_overlaps"], [["w", "x", 1.0]])

    def test_pads_past_a_courtyard_and_through_hole_pads_overlap(self) -> None:
        self.assertEqual(
            self.summary["pad_overlaps"], [["a", "b", 0.12], ["t", "u", 1.0]]
        )

    def test_state_marks_through_hole_pads(self) -> None:
        holes = {
            p["key"].split(".")[0]: p["through_hole"]
            for p in self.state["pads"]
            if p["key"].split(".")[0] in ("t", "s")
        }
        self.assertEqual(holes, {"t": True, "s": False})


if __name__ == "__main__":
    unittest.main()
