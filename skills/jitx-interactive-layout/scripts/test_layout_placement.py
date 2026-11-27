"""Tests for layout_placement: the frame it works in, pad sides, and the
spots, gaps and exit codes it reports.

Expected values come from a runtime report of one part at two rotations,
from jitx's bottom-side transform, or are worked out here from each test's
own geometry."""

import itertools
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

try:
    import shapely  # noqa: F401
except ImportError:
    raise unittest.SkipTest("needs shapely: run with a Python that has jitx") from None

import layout_placement as lp

SCRIPT = Path(__file__).with_name("layout_placement.py")
Ring = list[list[float]]


def ring(cx: float, cy: float, w: float, h: float) -> Ring:
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def pad(
    key: str, cx: float, cy: float, w: float, h: float, net: str | None
) -> dict[str, Any]:
    return {
        "key": key,
        "placed": True,
        "pos": [cx, cy],
        "net": net,
        "outline": ring(cx, cy, w, h),
    }


def comp(
    key: str, x: float, y: float, rot: float, court: list[float]
) -> dict[str, Any]:
    return {
        "key": key,
        "mpn": None,
        "placement": [x, y, rot, "top"],
        "courtyard": court,
    }


def write_state(
    folder: str, components: list[dict[str, Any]], pads: list[dict[str, Any]]
) -> Path:
    path = Path(folder) / "state.json"
    path.write_text(
        json.dumps(
            {
                "design": "test",
                "board": ring(0.0, 0.0, 20.0, 20.0),
                "components": components,
                "pads": pads,
            }
        )
    )
    return path


def board(components: list[dict[str, Any]], pads: list[dict[str, Any]]) -> lp.Board:
    with tempfile.TemporaryDirectory() as folder:
        return lp.load(write_state(folder, components, pads))


def ic(east: list[tuple[float, str]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """An IC at the origin, courtyard 4 x 4, with pads 0.5 x 0.3 whose outer
    edge is at x = 2 on the east side, and four ground pads on the west."""
    pads = [
        pad(f"u1.landpattern.p.{i + 1}", 1.75, y, 0.5, 0.3, net)
        for i, (y, net) in enumerate(east)
    ]
    pads += [
        pad(f"u1.landpattern.g.{i}", -1.75, -0.9 + 0.6 * i, 0.5, 0.3, "GND")
        for i in range(4)
    ]
    return comp("u1", 0.0, 0.0, 0.0, [-2.0, -2.0, 2.0, 2.0]), pads


def cap(
    key: str, x: float, y: float, first: str, second: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """A two-pad part at rotation 0: pads 0.5 x 0.5 at 0.5 either side of its
    origin along x, the first on the -x side, courtyard 2 x 1."""
    return comp(key, x, y, 0.0, [x - 1.0, y - 0.5, x + 1.0, y + 0.5]), [
        pad(f"{key}.p.1", x - 0.5, y, 0.5, 0.5, first),
        pad(f"{key}.p.2", x + 0.5, y, 0.5, 0.5, second),
    ]


def assemble(*items: tuple[dict[str, Any], list[dict[str, Any]]]) -> lp.Board:
    return board([c for c, _ in items], [p for _, pads in items for p in pads])


def court_of(spot: dict[str, Any]) -> tuple[float, float, float, float]:
    """The 2 x 1 courtyard of ``cap`` at a spot, long side along x at 0 and 180."""
    hx, hy = (1.0, 0.5) if spot["rotation"] in (0.0, 180.0) else (0.5, 1.0)
    return spot["x"] - hx, spot["y"] - hy, spot["x"] + hx, spot["y"] + hy


def overlap_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(w, 0.0) * max(h, 0.0)


class Frame(unittest.TestCase):
    def test_rotation_is_counter_clockwise_as_the_runtime_reports(self) -> None:
        # One two-pad part as layout_report.py wrote it at 0 and at 90 degrees.
        at_0 = comp("d0", 1.0, -23.2, 0.0, [0.25, -24.55, 1.75, -21.85])
        at_90 = comp("d90", -18.75, 23.2, 90.0, [-20.1, 22.45, -17.4, 23.95])
        b = board(
            [at_0, at_90],
            [
                pad("d0.landpattern.a", 1.0, -22.5, 0.9, 0.7, "A"),
                pad("d0.landpattern.c", 1.0, -23.9, 0.9, 0.7, "C"),
            ],
        )
        part, pose = b.parts["d0"], lp.Pose(-18.75, 23.2, 90.0, "top")
        anode, cathode = (lp.to_board(p.own, pose).centroid for p in part.pads)
        self.assertAlmostEqual(anode.x, -19.45, places=6)
        self.assertAlmostEqual(anode.y, 23.2, places=6)
        self.assertAlmostEqual(cathode.x, -18.05, places=6)
        self.assertAlmostEqual(cathode.y, 23.2, places=6)
        for got, want in zip(
            lp._court_at(part, pose), [-20.1, 22.45, -17.4, 23.95], strict=True
        ):
            self.assertAlmostEqual(got, want, places=6)

    def test_bottom_side_mirrors_x_before_turning(self) -> None:
        # jitx.placement.Placement scales x by -1 on the bottom side, and
        # Transform scales, turns, then moves: (1, 0) -> (-1, 0) -> (0, -1).
        pose = lp.Pose(10.0, 5.0, 90.0, "bottom")
        on_board = lp.to_board(lp.Point(1.0, 0.0), pose)
        self.assertAlmostEqual(on_board.centroid.x, 10.0, places=9)
        self.assertAlmostEqual(on_board.centroid.y, 4.0, places=9)
        back = lp.to_own(on_board, pose).centroid
        self.assertAlmostEqual(back.x, 1.0, places=9)
        self.assertAlmostEqual(back.y, 0.0, places=9)


class PinSides(unittest.TestCase):
    def two_rows(self, x: float, y: float, rot: float) -> lp.Board:
        """A two-row package, rows 5.8 apart and 8.45 long, square pads."""
        pads = []
        for i in range(14):
            for name, px in (("l", -2.9), ("r", 2.9)):
                py = -4.225 + 0.65 * i
                bx, by = (px, py) if rot == 0.0 else (-py, px)
                pads.append(
                    pad(
                        f"u.landpattern.{name}{i}",
                        x + bx,
                        y + by,
                        0.4,
                        0.4,
                        f"N{name}{i}",
                    )
                )
        pads.append(pad("u.landpattern.ep", x, y, 2.0, 2.0, "GND"))
        court = [x - 5.0, y - 5.0, x + 5.0, y + 5.0]
        return board([comp("u", x, y, rot, court)], pads)

    def test_two_row_package_has_no_pads_on_its_ends(self) -> None:
        part = self.two_rows(0.0, 0.0, 0.0).parts["u"]
        found = lp.pin_sides(part)
        names = {p.key: p.label for p in part.pads}
        west = sorted(names[k] for k, s in found.items() if s == 0)
        east = sorted(names[k] for k, s in found.items() if s == 1)
        self.assertEqual(west, sorted(f"l{i}" for i in range(14)))
        self.assertEqual(east, sorted(f"r{i}" for i in range(14)))
        self.assertIsNone(found["u.landpattern.ep"])

    def test_four_sided_package(self) -> None:
        pads = []
        for i, t in enumerate((-0.75, -0.25, 0.25, 0.75)):
            pads.append(pad(f"q.landpattern.w{i}", -2.0, t, 0.6, 0.25, "W"))
            pads.append(pad(f"q.landpattern.e{i}", 2.0, t, 0.6, 0.25, "E"))
            pads.append(pad(f"q.landpattern.s{i}", t, -2.0, 0.25, 0.6, "S"))
            pads.append(pad(f"q.landpattern.n{i}", t, 2.0, 0.25, 0.6, "N"))
        part = board([comp("q", 0.0, 0.0, 0.0, [-2.5, -2.5, 2.5, 2.5])], pads).parts[
            "q"
        ]
        found = lp.pin_sides(part)
        for pad_ in part.pads:
            self.assertEqual(found[pad_.key], "wesn".index(pad_.label[0]), pad_.label)

    def test_sides_turn_with_the_part(self) -> None:
        # Turned 90 degrees counter-clockwise, the package's -x row is on
        # the board's -y side, in order along x.
        result = lp.sides(self.two_rows(3.0, 1.0, 90.0), "u")
        south = [row["pad"] for row in result["sides"]["south (-y)"]]
        self.assertEqual(south, [f"l{i}" for i in reversed(range(14))])
        self.assertEqual(result["sides"]["west (-x)"], [])


class Search(unittest.TestCase):
    def test_nearest_legal_spot(self) -> None:
        # The pin's outer edge is at x = 2, on the courtyard's edge. The
        # part's courtyard reaches 0.25 past its pad, so no spot outside the
        # IC's courtyard brings the pad nearer than 0.25.
        b = assemble(ic([(0.0, "VDD")]), cap("c1", 8.0, 8.0, "VDD", "GND"))
        found = lp.search(
            b, "c1", "u1:p.1", step=0.25, radius=3.0, top=10**6, spread=0.0
        )
        self.assertEqual(found["spots"][0]["gap_mm"], 0.25)
        self.assertTrue(found["spots"][0]["faces"])
        self.assertEqual(
            found["current_gap_mm"],
            round(((7.25 - 2.0) ** 2 + (7.75 - 0.15) ** 2) ** 0.5, 3),
        )
        self.assertEqual(len(found["spots"]), found["legal"])
        for spot in found["spots"]:
            court = court_of(spot)
            self.assertLess(overlap_area(court, (-2.0, -2.0, 2.0, 2.0)), 1e-9, spot)
            self.assertTrue(-10.0 <= court[0] and court[2] <= 10.0, spot)
            self.assertTrue(-10.0 <= court[1] and court[3] <= 10.0, spot)

    def test_conflicts_name_the_part_in_the_way(self) -> None:
        blocker = comp("c2", 3.25, 0.0, 0.0, [2.0, -1.0, 4.5, 1.0])
        b = assemble(
            ic([(0.0, "VDD")]), cap("c1", 8.0, 8.0, "VDD", "GND"), (blocker, [])
        )
        plain = lp.search(b, "c1", "u1:p.1", step=0.25, radius=3.0)
        self.assertGreater(plain["spots"][0]["gap_mm"], 0.25)
        self.assertTrue(all(not s["overlaps"] for s in plain["spots"]))
        named = lp.search(
            b,
            "c1",
            "u1:p.1",
            step=0.25,
            radius=3.0,
            conflicts=True,
            top=10**6,
            spread=0.0,
        )
        # Overlapping spots rank by gap with the rest: the spot against the
        # pin, under c2, comes before every legal one.
        nearest = named["spots"][0]
        self.assertEqual(nearest["gap_mm"], 0.25)
        self.assertEqual(nearest["overlaps"], ["c2"])
        self.assertTrue(all("u1" not in s["overlaps"] for s in named["spots"]))
        fixed = lp.search(
            b, "c1", "u1:p.1", step=0.25, radius=3.0, conflicts=True, movable=[]
        )
        self.assertTrue(all(not s["overlaps"] for s in fixed["spots"]))

    def test_group_gives_the_tight_connection_the_near_spot(self) -> None:
        # One spot touches the pin's side of the IC at 0.25; the next is
        # further than 0.25 and nearer than 1. With c2 tolerating four times
        # the distance, c1 first leaves a worst weighted gap of 0.25.
        b = assemble(
            ic([(0.0, "VDD")]),
            cap("c1", 8.0, 8.0, "VDD", "GND"),
            cap("c2", 8.0, 6.0, "VDD", "GND"),
        )
        found = lp.group(b, ["c2=u1:p.1@4", "c1=u1:p.1"], step=0.25, radius=3.0)
        self.assertEqual(found["orders_tried"], 2)
        self.assertEqual(
            {tuple(o["order"]) for o in found["orders"]}, {("c1", "c2"), ("c2", "c1")}
        )
        self.assertEqual(found["orders"][0]["order"], ["c1", "c2"])
        self.assertEqual(found["orders"][0]["worst_mm"], 0.25)
        a, c = (court_of(p) for p in found["orders"][0]["placements"])
        self.assertLess(overlap_area(a, c), 1e-9)


class GroupOrders(unittest.TestCase):
    def test_every_order_names_each_part_once(self) -> None:
        for count in (1, 2, 3, 4):
            orders = list(lp._orders(count))
            self.assertEqual(len(orders), math.factorial(count))
            self.assertEqual(len(set(orders)), len(orders))
            for order in orders:
                self.assertEqual(sorted(order), list(range(count)), order)

    def test_the_first_orders_are_each_led_by_a_different_part(self) -> None:
        for count in (2, 3, 4):
            first = itertools.islice(lp._orders(count), count)
            self.assertEqual(sorted(o[0] for o in first), list(range(count)))

    def test_group_places_every_part_in_every_order_it_lists(self) -> None:
        # Three parts have six orders, the number tried by default, and the
        # board has room east of the pin for all three in any order.
        names = ["c1", "c2", "c3"]
        b = assemble(
            ic([(0.0, "VDD")]),
            *(cap(n, 8.0, 8.0 - 2.0 * i, "VDD", "GND") for i, n in enumerate(names)),
        )
        found = lp.group(
            b, [f"{n}=u1:p.1" for n in names], step=0.25, radius=3.0, top=6
        )
        self.assertEqual(found["orders_tried"], 6)
        self.assertEqual(found["no_spot"], {})
        self.assertEqual(len({tuple(o["order"]) for o in found["orders"]}), 6)
        for listed in found["orders"]:
            self.assertEqual(sorted(listed["order"]), names, listed["order"])
            self.assertEqual(sorted(p["part"] for p in listed["placements"]), names)


class GroupChannels(unittest.TestCase):
    def test_a_member_closes_channels_for_the_members_after_it(self) -> None:
        # SIG leaves the IC's east side at (2, 0) between pins A (y = 1) and
        # B (y = -1). Channels are 0.2 wide (track 0.1, clearance 0.05): one
        # straight out along y = 0, one up along y = x - 2, one down along
        # y = 2 - x. The pad of n1 at (3.3, 1.3) closes the upper one.
        # Walls leave the caps one pocket, x 2 to 4 and y -1.25 to 0.75.
        # c1 at (3, 0.25) has its pads across y = 0 to 0.5: it closes the
        # straight channel and not the lower one. c2 at (3, -0.75) has a pad
        # over (2.5, -0.5), on the lower channel, and none above y = -0.5.
        # Each takes that spot when it goes first: it is its nearest that
        # leaves SIG a channel. The other then has only the rest of the
        # pocket, where it closes SIG's last one.
        walls = [
            ("n1", [2.0, 0.75, 6.0, 4.0]),
            ("n2", [-3.0, 2.0, 2.0, 4.0]),
            ("s1", [2.0, -4.0, 6.0, -1.25]),
            ("s2", [-3.0, -4.0, 2.0, -2.0]),
            ("e1", [4.0, -1.25, 6.0, 0.75]),
        ]
        b = assemble(
            ic([(1.0, "A"), (0.0, "SIG"), (-1.0, "B")]),
            cap("c1", 8.0, 8.0, "A", "GND"),
            cap("c2", 8.0, 6.0, "B", "GND"),
            *(
                (
                    comp(key, court[0], court[1], 0.0, court),
                    [pad("n1.p.1", 3.3, 1.3, 0.2, 0.2, "X")] if key == "n1" else [],
                )
                for key, court in walls
            ),
        )
        found = lp.group(
            b,
            ["c1=u1:p.1", "c2=u1:p.3"],
            step=0.25,
            radius=2.0,
            track=0.1,
            clear=0.05,
        )
        self.assertEqual(
            {tuple(o["order"]) for o in found["orders"]}, {("c1", "c2"), ("c2", "c1")}
        )
        spot = {"c1": (3.0, 0.25, 0.0), "c2": (3.0, -0.75, 0.0)}
        for listed in found["orders"]:
            first, second = listed["placements"]
            for placed in (first, second):
                self.assertEqual(
                    (placed["x"], placed["y"], placed["rotation"]),
                    spot[placed["part"]],
                    listed["order"],
                )
            self.assertEqual(first["blocked"], [], listed["order"])
            self.assertEqual(second["blocked"], ["p.2"], listed["order"])
            self.assertEqual(listed["blocked"], 1)


class UnplacedPart(unittest.TestCase):
    def test_courtyard_offset_from_the_pads_is_kept(self) -> None:
        # An unplaced part as layout_report.py writes it, in its own frame:
        # pads 0.5 x 0.5 at x = -0.5 (VDD) and 0.5, courtyard -1.0 to 1.5 in
        # x. The courtyard is 0.25 past the VDD pad and 0.75 past the other.
        # VDD pad towards the pin (rotation 0): the courtyard meets the IC's
        # at x = 2 with the part at x = 3.0, its pad edge at 2.25, 0.25 from
        # the pin's edge at 2.0. Turned 180, the long end faces the IC: the
        # part is no nearer than x = 3.5 and its VDD pad edge is at 3.75.
        loose = {
            "key": "c1",
            "mpn": None,
            "placement": None,
            "courtyard": None,
            "courtyard_local": [-1.0, -0.5, 1.5, 0.5],
        }
        pads = [
            {**pad("c1.p.1", -0.5, 0.0, 0.5, 0.5, "VDD"), "placed": False},
            {**pad("c1.p.2", 0.5, 0.0, 0.5, 0.5, "GND"), "placed": False},
        ]
        b = assemble(ic([(0.0, "VDD")]), (loose, pads))
        found = lp.search(
            b, "c1", "u1:p.1", step=0.25, radius=3.0, top=10**6, spread=0.0
        )
        facing = [
            s
            for s in found["spots"]
            if (s["rotation"], s["x"], s["y"]) == (0.0, 3.0, 0.0)
        ]
        self.assertEqual([s["gap_mm"] for s in facing], [0.25])
        turned = [s["gap_mm"] for s in found["spots"] if s["rotation"] == 180.0]
        self.assertEqual(min(turned), 1.75)

    def test_unplaced_part_without_its_courtyard_is_refused(self) -> None:
        loose = {"key": "c1", "mpn": None, "placement": None, "courtyard": None}
        pads = [
            {**pad("c1.p.1", -0.5, 0.0, 0.5, 0.5, "VDD"), "placed": False},
            {**pad("c1.p.2", 0.5, 0.0, 0.5, 0.5, "GND"), "placed": False},
        ]
        b = assemble(ic([(0.0, "VDD")]), (loose, pads))
        with self.assertRaisesRegex(lp.UsageError, "courtyard_local"):
            lp.search(b, "c1", "u1:p.1", step=0.25, radius=3.0)

    def test_room_needed_counts_an_unplaced_part_by_its_size(self) -> None:
        # A state from a report that gave only the courtyard's size, 2.4 by
        # 1.0: the part still needs 2.4 mm2 beside the side its net is on.
        loose = {
            "key": "c1",
            "mpn": None,
            "placement": None,
            "courtyard": None,
            "courtyard_size": [2.4, 1.0],
        }
        pads = [
            {**pad("c1.p.1", -0.5, 0.0, 0.5, 0.5, "VDD"), "placed": False},
            {**pad("c1.p.2", 0.5, 0.0, 0.5, 0.5, "GND"), "placed": False},
        ]
        b = assemble(ic([(0.0, "VDD")]), (loose, pads))
        unturned = [r for r in lp.sides(b, "u1")["rotations"] if r["rotation"] == 0.0]
        self.assertEqual(len(unturned), 1)
        self.assertEqual(unturned[0]["room"]["east (+x)"]["parts"], 1)
        self.assertEqual(unturned[0]["room"]["east (+x)"]["need_mm2"], 2.4)
        self.assertEqual(unturned[0]["room"]["west (-x)"]["need_mm2"], 0.0)


class EscapeChannels(unittest.TestCase):
    """The signal pin's outer edge is at (2, 0) on the IC's east side. With
    front 2.0 and width 0.3 its channels are: straight out, y within 0.15 of
    0 from x = 2 to 4; and two at 45 degrees, along y = x - 2 and y = 2 - x."""

    def lanes(
        self,
        *others: tuple[dict[str, Any], list[dict[str, Any]]],
        chip: tuple[dict[str, Any], list[dict[str, Any]]] | None = None,
    ) -> tuple[int, list[str]]:
        b = assemble(chip or ic([(0.0, "SIG")]), *others)
        ((_, free, closing),) = lp.escape_lanes(
            b, b.parts["u1"], set(), {"GND"}, 2.0, 0.3
        )
        return len(free), closing

    def other(
        self, key: str, x: float, y: float, net: str, side: str = "top"
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """A one-pad part, pad 0.4 x 0.4 at (x, y)."""
        part = comp(key, x, y, 0.0, [x - 0.5, y - 0.5, x + 0.5, y + 0.5])
        part["placement"][3] = side
        return part, [pad(f"{key}.p.1", x, y, 0.4, 0.4, net)]

    def test_nothing_near_leaves_three_channels(self) -> None:
        self.assertEqual(self.lanes(), (3, []))

    def test_another_nets_pad_closes_the_channel_it_sits_in(self) -> None:
        for name, x, y in (("ahead", 3.0, 0.0), ("up", 3.0, 1.0), ("down", 3.0, -1.0)):
            with self.subTest(name):
                self.assertEqual(
                    self.lanes(self.other("j1", x, y, "X")), (2, ["j1.p.1"])
                )

    def test_three_pads_close_the_pin_in(self) -> None:
        free, closing = self.lanes(
            self.other("j1", 3.0, 0.0, "X"),
            self.other("j2", 3.0, 1.0, "Y"),
            self.other("j3", 3.0, -1.0, "Z"),
        )
        self.assertEqual((free, closing), (0, ["j1.p.1", "j2.p.1", "j3.p.1"]))

    def test_pads_that_close_nothing(self) -> None:
        # The pin's own net ahead of it, a pad on the other side of the
        # board, and a pad behind the pin's outer edge.
        for name, part in (
            ("same net", self.other("j1", 3.0, 0.0, "SIG")),
            ("other side", self.other("j1", 3.0, 0.0, "X", side="bottom")),
            ("behind the pin", self.other("j1", 0.5, 0.0, "X")),
        ):
            with self.subTest(name):
                self.assertEqual(self.lanes(part), (3, []))

    def test_channels_turn_with_the_ic(self) -> None:
        # The same IC turned 90 degrees, which takes (x, y) to (-y, x): its
        # east side faces north. The signal pin is at (0, 1.75), standing 0.3
        # wide, outer edge at y = 2, and the ground pads lie along the south.
        # Its channels run north, so a pad at (0, 3) closes one and a pad at
        # (3, 0), where they ran before the turn, closes none.
        chip = (
            comp("u1", 0.0, 0.0, 90.0, [-2.0, -2.0, 2.0, 2.0]),
            [pad("u1.landpattern.p.1", 0.0, 1.75, 0.3, 0.5, "SIG")]
            + [
                pad(f"u1.landpattern.g.{i}", 0.9 - 0.6 * i, -1.75, 0.3, 0.5, "GND")
                for i in range(4)
            ],
        )
        north = self.lanes(self.other("j1", 0.0, 3.0, "X"), chip=chip)
        self.assertEqual(north, (2, ["j1.p.1"]))
        self.assertEqual(
            self.lanes(self.other("j1", 3.0, 0.0, "X"), chip=chip), (3, [])
        )

    def test_channels_mirror_with_a_bottom_side_ic(self) -> None:
        # On the bottom the IC is mirrored in x: its east side faces west.
        # The signal pin is at (-1.75, 0), outer edge at x = -2, the ground
        # pads at x = 1.75. A bottom-side pad at (-3, 0) closes one channel;
        # one at (3, 0) closes none.
        part = comp("u1", 0.0, 0.0, 0.0, [-2.0, -2.0, 2.0, 2.0])
        part["placement"][3] = "bottom"
        chip = (
            part,
            [pad("u1.landpattern.p.1", -1.75, 0.0, 0.5, 0.3, "SIG")]
            + [
                pad(f"u1.landpattern.g.{i}", 1.75, -0.9 + 0.6 * i, 0.5, 0.3, "GND")
                for i in range(4)
            ],
        )
        west = self.lanes(self.other("j1", -3.0, 0.0, "X", side="bottom"), chip=chip)
        self.assertEqual(west, (2, ["j1.p.1"]))
        east = self.lanes(self.other("j1", 3.0, 0.0, "X", side="bottom"), chip=chip)
        self.assertEqual(east, (3, []))

    def test_a_part_on_the_other_side_closes_no_channel(self) -> None:
        # SIG's two diagonal channels are closed by j1 and j2, so the one
        # straight out along y = 0 is its last. On top, a spot for c1 with a
        # pad across y = 0 between x = 2 and 4 would close it; on the bottom
        # no spot closes anything.
        b = assemble(
            ic([(0.6, "VDD"), (0.0, "SIG")]),
            cap("c1", 8.0, 8.0, "VDD", "GND"),
            self.other("j1", 3.0, 1.0, "X"),
            self.other("j2", 3.0, -1.0, "Y"),
        )
        found = {
            side: lp.search(
                b,
                "c1",
                "u1:p.1",
                side=side,
                step=0.25,
                radius=3.0,
                track=0.1,
                clear=0.1,
                top=10**6,
                spread=0.0,
            )
            for side in ("top", "bottom")
        }
        self.assertTrue(any(s["blocked"] for s in found["top"]["spots"]))
        self.assertTrue(found["bottom"]["spots"])
        self.assertTrue(all(not s["blocked"] for s in found["bottom"]["spots"]))


class Audit(unittest.TestCase):
    def turned_cap(self, rot: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """``cap`` against the IC's east edge, its VDD pad towards the pin at
        rotation 0 and away from it at 180."""
        near, far = (2.5, 3.5) if rot == 0.0 else (3.5, 2.5)
        return comp("u1c", 3.0, 0.0, rot, [2.0, -0.5, 4.0, 0.5]), [
            pad("u1c.p.1", near, 0.0, 0.5, 0.5, "VDD"),
            pad("u1c.p.2", far, 0.0, 0.5, 0.5, "GND"),
        ]

    def test_part_turned_away_from_its_pin(self) -> None:
        for rot, gap, turned in ((0.0, 0.25, False), (180.0, 1.25, True)):
            b = assemble(ic([(0.0, "VDD")]), self.turned_cap(rot))
            (row,) = lp.audit(b, ics=["u1"])["ics"]["u1"]["pins"]
            self.assertEqual(
                (row["part"], row["gap_mm"], row["turned"]), ("u1c", gap, turned)
            )

    def test_part_between_two_pins_is_not_turned(self) -> None:
        # A part across two IC pins sits with each pad at its own pin. A
        # second pin on one of its nets, beyond the other pad, does not make
        # it the wrong way round.
        between = comp("u1b", 2.5, 0.0, 90.0, [2.0, -1.0, 3.0, 1.0])
        pads = [
            pad("u1b.p.1", 2.5, -0.5, 0.5, 0.5, "BST"),
            pad("u1b.p.2", 2.5, 0.5, 0.5, 0.5, "SW"),
        ]
        b = assemble(ic([(0.65, "SW"), (-0.65, "BST"), (-1.3, "SW")]), (between, pads))
        rows = lp.audit(b, ics=["u1"])["ics"]["u1"]["pins"]
        self.assertEqual({r["pin"] for r in rows}, {"p.1", "p.2", "p.3"})
        self.assertFalse(any(r["turned"] for r in rows))

    def test_block_packing(self) -> None:
        # Two 1 x 1 courtyards 2 apart: a 4 x 1 box over 2 of courtyard, on
        # a 20 x 20 board.
        b = board(
            [
                comp("a.r1", 0.5, 0.5, 0.0, [0.0, 0.0, 1.0, 1.0]),
                comp("a.r2", 3.5, 0.5, 0.0, [3.0, 0.0, 4.0, 1.0]),
            ],
            [],
        )
        found = lp.audit(b)["board"]
        (row,) = found["blocks"]
        self.assertEqual(
            (row["block"], row["courtyards_mm2"], row["box_mm2"], row["ratio"]),
            ("a", 2.0, 4.0, 2.0),
        )
        self.assertEqual(found["sides"]["top"]["percent_of_board"], 0.5)


def cap_pads(spot: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    """The two 0.5 x 0.5 pads of ``cap`` at a spot, 0.5 either side of it."""
    dx, dy = (0.5, 0.0) if spot["rotation"] in (0.0, 180.0) else (0.0, 0.5)
    return [
        (spot["x"] + s * dx - 0.25, spot["y"] + s * dy - 0.25)
        + (spot["x"] + s * dx + 0.25, spot["y"] + s * dy + 0.25)
        for s in (-1.0, 1.0)
    ]


class Keepouts(unittest.TestCase):
    """A part's keep-out is its courtyard and every one of its pads; a
    through-hole pad counts on both sides; nets do not matter."""

    def overhang(
        self, missing: tuple[str, ...] = ()
    ) -> tuple[tuple[dict[str, Any], list[dict[str, Any]]], ...]:
        """l1: courtyard x -1 to 1, pads 0.6 x 0.4 at x = -1 and 1, so its
        east pad spans x 0.7 to 1.3, 0.3 past the courtyard. c9: courtyard x
        1 to 2 and y -0.5 to 0.5, meeting l1's at x = 1 with no area, and a
        0.4 x 0.4 pad at x 1.3 to 1.7 on the same net as l1's. l1's pad over
        c9's courtyard is x 1 to 1.3 by y -0.2 to 0.2: 0.12 mm2. ``missing``
        names l1's pads the state gives with no outline."""
        l1 = [
            pad("l1.p.1", -1.0, 0.0, 0.6, 0.4, "SW"),
            pad("l1.p.2", 1.0, 0.0, 0.6, 0.4, "SW"),
        ]
        l1 = [{**p, "outline": None} if p["key"] in missing else p for p in l1]
        return (
            (comp("l1", 0.0, 0.0, 0.0, [-1.0, -1.0, 1.0, 1.0]), l1),
            (
                comp("c9", 1.5, 0.0, 0.0, [1.0, -0.5, 2.0, 0.5]),
                [pad("c9.p.1", 1.5, 0.0, 0.4, 0.4, "SW")],
            ),
        )

    def test_audit_lists_a_pad_past_its_courtyard_on_a_neighbour(self) -> None:
        found = lp.audit(assemble(*self.overhang()))
        self.assertEqual(found["board"]["courtyard_overlaps"], [])
        self.assertEqual(
            found["board"]["pad_overlaps"],
            [{"components": ["c9", "l1"], "area_mm2": 0.12, "approximate": False}],
        )

    def test_a_pad_with_no_outline_leaves_out_that_pad_only(self) -> None:
        # l1's west pad has no outline; its east pad still lies over c9.
        found = lp.audit(assemble(*self.overhang(missing=("l1.p.1",))))
        self.assertEqual(
            [(r["components"], r["area_mm2"]) for r in found["board"]["pad_overlaps"]],
            [(["c9", "l1"], 0.12)],
        )
        self.assertTrue(any("l1" in n for n in found["notes"]), found["notes"])

    def test_pads_the_state_cannot_place_leave_the_courtyard_and_say_so(
        self,
    ) -> None:
        # The same parts from a state with no outline for l1's pads, and no
        # through-hole marks: l1 keeps its courtyard only, which clears c9's.
        found = lp.audit(assemble(*self.overhang(missing=("l1.p.1", "l1.p.2"))))
        self.assertEqual(found["board"]["pad_overlaps"], [])
        self.assertTrue(any("l1" in n for n in found["notes"]), found["notes"])
        self.assertTrue(
            any("through-hole" in n for n in found["notes"]), found["notes"]
        )

    def test_a_through_hole_pad_meets_a_part_on_the_other_side(self) -> None:
        # j1 on top has a 1 x 1 pad at the origin; b1 on the bottom has its
        # courtyard over x 0 to 1 and y -0.25 to 0.25 and a pad clear of
        # j1's. With a hole, j1's pad covers 0.5 x 0.5 of b1's courtyard.
        under = comp("b1", 0.5, 0.0, 0.0, [0.0, -0.25, 1.0, 0.25])
        under["placement"][3] = "bottom"
        for hole, want in ((True, [["b1", "j1"]]), (False, [])):
            with self.subTest(through_hole=hole):
                found = lp.audit(
                    assemble(
                        (
                            comp("j1", 0.0, 0.0, 0.0, [-1.0, -1.0, 1.0, 1.0]),
                            [
                                {
                                    **pad("j1.p.1", 0.0, 0.0, 1.0, 1.0, "A"),
                                    "through_hole": hole,
                                }
                            ],
                        ),
                        (
                            under,
                            [
                                {
                                    **pad("b1.p.1", 0.75, 0.0, 0.2, 0.2, "B"),
                                    "through_hole": False,
                                }
                            ],
                        ),
                    )
                )
                rows = found["board"]["pad_overlaps"]
                self.assertEqual([r["components"] for r in rows], want)
                if want:
                    self.assertEqual(rows[0]["area_mm2"], 0.25)
                self.assertFalse(
                    any("does not mark through-hole" in n for n in found["notes"])
                )

    def test_audit_marks_overlaps_of_turned_boxes_approximate(self) -> None:
        # Two 2 x 2 courtyards turned 45 degrees, centred at (0, 0) and (2,
        # 2): along the diagonal their centres are 2 * sqrt(2) apart and each
        # reaches 1 towards the other, so they clear. Their boxes reach
        # sqrt(2) each way and overlap by (2 * sqrt(2) - 2) squared, 0.686.
        r = math.sqrt(2.0)
        parts = [
            (
                {
                    **comp(k, c, c, 45.0, [c - r, c - r, c + r, c + r]),
                    "courtyard_local": [-1.0, -1.0, 1.0, 1.0],
                },
                [pad(f"{k}.p.1", c, c, 0.2, 0.2, None)],
            )
            for k, c in (("a", 0.0), ("b", 2.0))
        ]
        found = lp.audit(assemble(*parts))
        self.assertEqual(
            found["board"]["courtyard_overlaps"],
            [{"components": ["a", "b"], "area_mm2": 0.686, "approximate": True}],
        )
        self.assertTrue(any("real shapes" in n for n in found["notes"]))

    def test_search_refuses_a_spot_on_a_pad_past_its_courtyard(self) -> None:
        # l1's courtyard is y 1 to 3, clear of every spot in front of the
        # pin, and its VDD pad reaches 0.6 below it: x 2.5 to 3.5, y 0.4 to
        # 1.0. c1 at (3, 0) has its courtyard up to y 0.5, over 0.1 of it.
        blocker = (
            comp("l1", 3.0, 2.0, 0.0, [2.0, 1.0, 4.0, 3.0]),
            [pad("l1.p.1", 3.0, 0.7, 1.0, 0.6, "VDD")],
        )
        b = assemble(ic([(0.0, "VDD")]), cap("c1", 8.0, 8.0, "VDD", "GND"), blocker)
        kw: dict[str, Any] = {"step": 0.25, "radius": 3.0, "top": 10**6, "spread": 0.0}
        legal = lp.search(b, "c1", "u1:p.1", **kw)["spots"]
        self.assertTrue(legal)
        for spot in legal:
            self.assertLess(
                overlap_area(court_of(spot), (2.5, 0.4, 3.5, 1.0)), 1e-9, spot
            )
        named = lp.search(b, "c1", "u1:p.1", conflicts=True, **kw)["spots"]
        at = [s for s in named if (s["x"], s["y"], s["rotation"]) == (3.0, 0.0, 0.0)]
        self.assertEqual([s["overlaps"] for s in at], [["l1"]])

    def test_search_keeps_a_through_hole_pad_off_a_part_below(self) -> None:
        # b1 on the bottom covers x 2.25 to 2.75, y -0.25 to 0.25, where
        # c1's VDD pad sits in the spots nearest the pin.
        under = comp("b1", 2.5, 0.0, 0.0, [2.25, -0.25, 2.75, 0.25])
        under["placement"][3] = "bottom"
        kw: dict[str, Any] = {"step": 0.25, "radius": 3.0, "top": 10**6, "spread": 0.0}
        for hole in (True, False):
            part, pads = cap("c1", 8.0, 8.0, "VDD", "GND")
            pads = [{**p, "through_hole": hole} for p in pads]
            b = assemble(ic([(0.0, "VDD")]), (part, pads), (under, []))
            spots = lp.search(b, "c1", "u1:p.1", **kw)["spots"]
            hits = [
                s
                for s in spots
                if any(
                    overlap_area(p, (2.25, -0.25, 2.75, 0.25)) > 1e-9
                    for p in cap_pads(s)
                )
            ]
            with self.subTest(through_hole=hole):
                self.assertTrue(spots)
                self.assertEqual(bool(hits), not hole)

    def overhanging_cap(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """c1: courtyard 1 x 1, its 0.5 x 0.5 pads wholly past it, centred
        0.75 either side of its origin."""
        return comp("c1", 8.0, 8.0, 0.0, [7.5, 7.5, 8.5, 8.5]), [
            pad("c1.p.1", 7.25, 8.0, 0.5, 0.5, "VDD"),
            pad("c1.p.2", 8.75, 8.0, 0.5, 0.5, "GND"),
        ]

    def test_group_keeps_pad_copper_clear_of_the_pin(self) -> None:
        # The pin spans x 1.5 to 2 by y -0.15 to 0.15. c1's courtyard may
        # abut the IC's, so at rotation 0 x >= 3 (its VDD pad over x 2 to
        # 2.5 may abut the IC courtyard too); at x = 3 the gap is |y| - 0.4.
        # Without --clear the pads may not touch: |y| = 0.5 on the 0.25
        # grid, 0.1, nearer than rotation 90's best of 0.25. With 0.3 the
        # gap is at least 0.3: |y| = 0.75 at x = 3 gives 0.35; x = 3.25
        # gives 0.43 and rotation 90 at x 2.5 the same, x = 3.5 gives 0.5.
        b = assemble(ic([(0.0, "VDD")]), self.overhanging_cap())
        for clear, want in ((None, 0.1), (0.3, 0.35)):
            with self.subTest(clear=clear):
                found = lp.group(b, ["c1=u1:p.1"], step=0.25, radius=3.0, clear=clear)
                self.assertEqual(found["orders"][0]["worst_mm"], want)

    def test_search_keeps_pad_copper_off_every_other_pad(self) -> None:
        # A second pin on SIG at y = 0.6, beside the VDD pin: no legal spot
        # puts c1's pads nearer either pin than the clearance, or touching
        # without one, whatever the nets.
        b = assemble(ic([(0.0, "VDD"), (0.6, "SIG")]), self.overhanging_cap())
        pins = [lp.box(1.5, -0.15, 2.0, 0.15), lp.box(1.5, 0.45, 2.0, 0.75)]
        kw: dict[str, Any] = {"step": 0.05, "radius": 2.0, "top": 10**6, "spread": 0.0}
        for clear in (None, 0.2):
            spots = lp.search(b, "c1", "u1:p.1", clear=clear, **kw)["spots"]
            with self.subTest(clear=clear):
                self.assertTrue(spots)
                for spot in spots:
                    dx, dy = (
                        (0.75, 0.0)
                        if spot["rotation"] in (0.0, 180.0)
                        else (
                            0.0,
                            0.75,
                        )
                    )
                    for sign in (-1.0, 1.0):
                        x, y = spot["x"] + sign * dx, spot["y"] + sign * dy
                        mine = lp.box(x - 0.25, y - 0.25, x + 0.25, y + 0.25)
                        apart = min(mine.distance(p) for p in pins)
                        self.assertGreater(apart, (clear or 0.0) - 1e-9, spot)
                        self.assertGreater(apart, 1e-9, spot)

    def test_search_keeps_the_keep_out_inside_the_board(self) -> None:
        # u2's pin is at the top of a 20 x 20 board, y 8.5 to 9.0, board edge
        # at y = 10. Turned 90, c1's pads reach 1.0 above and below its
        # origin, past its courtyard's 0.5: a spot with the courtyard inside
        # and a pad over the edge is not legal.
        u2 = (
            comp("u2", 0.0, 8.0, 0.0, [-1.0, 7.0, 1.0, 9.0]),
            [pad("u2.p.1", 0.0, 8.75, 0.3, 0.5, "VDD")],
        )
        c1, pads = self.overhanging_cap()
        found = lp.search(
            assemble(u2, (c1, pads)),
            "c1",
            "u2:p.1",
            step=0.25,
            radius=3.0,
            top=10**6,
            spread=0.0,
        )
        self.assertTrue(found["spots"])
        for spot in found["spots"]:
            hx, hy = (1.0, 0.5) if spot["rotation"] in (0.0, 180.0) else (0.5, 1.0)
            self.assertLessEqual(spot["y"] + hy, 10.0 + 1e-9, spot)
            self.assertLessEqual(abs(spot["x"]) + hx, 10.0 + 1e-9, spot)


class ExitCodes(unittest.TestCase):
    def run_script(
        self,
        *args: str,
        extra: tuple[dict[str, Any], ...] = (),
        text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the script on an IC and a far-off c1, plus ``extra``
        components, or on a state file holding ``text``."""
        with tempfile.TemporaryDirectory() as folder:
            first, second = ic([(0.0, "VDD")]), cap("c1", 8.0, 8.0, "VDD", "GND")
            state = write_state(
                folder, [first[0], second[0], *extra], first[1] + second[1]
            )
            if text is not None:
                state.write_text(text)
            return subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--state", str(state), *args],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_spots_found_exit_0(self) -> None:
        done = self.run_script(
            "search", "--part", "c1", "--pin", "u1:p.1", "--step", "0.25"
        )
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_no_legal_spot_exits_1(self) -> None:
        # Every spot within 0.2 of the pin's centre overlaps the IC.
        done = self.run_script(
            "search", "--part", "c1", "--pin", "u1:p.1", "--radius", "0.2"
        )
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_only_overlapping_spots_exit_1_with_conflicts(self) -> None:
        # c2's courtyard covers x 2 to 4.5 and y -1 to 1, east of the pin.
        # Within 1.0 of the pin, a spot clear of the IC has c1's courtyard
        # over c2's: there are spots to list, and none is legal.
        blocker = comp("c2", 3.25, 0.0, 0.0, [2.0, -1.0, 4.5, 1.0])
        done = self.run_script(
            "search",
            "--part",
            "c1",
            "--pin",
            "u1:p.1",
            "--radius",
            "1.0",
            "--step",
            "0.25",
            "--conflicts",
            "--json",
            extra=(blocker,),
        )
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        found = json.loads(done.stdout)
        self.assertEqual(found["legal"], 0)
        self.assertTrue(found["spots"])
        self.assertTrue(all(s["overlaps"] == ["c2"] for s in found["spots"]))

    def test_search_without_clear_says_pad_clearance_was_not_checked(self) -> None:
        args = ("search", "--part", "c1", "--pin", "u1:p.1", "--step", "0.25")
        bare = self.run_script(*args)
        self.assertIn("pad clearance not checked", bare.stdout)
        given = self.run_script(*args, "--clear", "0.1")
        self.assertEqual(given.returncode, 0, given.stderr)
        self.assertNotIn("pad clearance not checked", given.stdout)

    def test_a_negative_clearance_exits_2_and_names_the_flag(self) -> None:
        # A clearance below zero once let spots through that overlap a
        # neighbour's courtyard by less than its size.
        done = self.run_script(
            "search",
            "--part",
            "c1",
            "--pin",
            "u1:p.1",
            "--step",
            "0.25",
            "--clear",
            "-0.3",
        )
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        # The script's own refusal, not the argument parser's.
        self.assertIn("--clear is 0 or more", done.stderr)

    def test_unknown_component_exits_2_and_names_it(self) -> None:
        done = self.run_script("sides", "u9")
        self.assertEqual(done.returncode, 2)
        self.assertIn("u9", done.stderr)

    def test_ground_name_no_pad_carries_exits_2_and_names_the_nets(self) -> None:
        # Five pads are on GND and two on VDD; none is on VSS.
        done = self.run_script("audit", "--ground", "VSS")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("VSS", done.stderr)
        self.assertIn("GND", done.stderr)

    def test_one_ground_name_no_pad_carries_exits_2_and_names_it(self) -> None:
        done = self.run_script("audit", "--ground", "GND", "VSS")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("no pad is on VSS", done.stderr)

    def test_a_ground_name_from_an_earlier_flag_is_still_checked(self) -> None:
        done = self.run_script("audit", "--ground", "VSS", "--ground", "GND")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("no pad is on VSS", done.stderr)

    def test_ground_with_no_names_is_a_board_with_no_ground(self) -> None:
        done = self.run_script("audit", "--ground")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_state_that_is_not_json_exits_2(self) -> None:
        done = self.run_script("sides", "u1", text='{"components": [')
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("not JSON", done.stderr)


if __name__ == "__main__":
    unittest.main()
