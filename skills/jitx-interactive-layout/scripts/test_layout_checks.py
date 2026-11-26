"""Tests for layout_checks: which capacitors `decap_vias` lists and fails,
and which thin traces on a power net `power_branches` excuses.

They need a Python that imports jitx and shapely, and contact no session:
each test hands the check its pads, vias, traces and pour fills directly.

Every expected value is worked out here from the test's own geometry and
the rule the check states. The capacitor has two 0.5 by 0.5 pads on TOP
(layer 0), VDD at (0, 0) and GND at (1, 0), so the pad pitch is 1.0. Where
a test has a ground plane it is a 10 by 10 fill on layer 1, under both
pads.

The branch tests add pads on VDD, whose rule width is 1.0, and join them
with 0.2 wide traces, each 3.0 long: `u1.p1` is the supply pin the traces
leave from, `r_led.p1` the part a test names as a branch, `u2.p1` a load
no test names.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any, cast

try:
    import jitx  # noqa: F401
    import shapely  # noqa: F401
except ImportError:
    raise unittest.SkipTest(
        "needs jitx and shapely: run with the project's Python"
    ) from None

from shapely.geometry import Point, box

import layout_checks as lc

VDD, GND = 1, 0
TOP, INNER = 0, 1
BOTH = frozenset({TOP, INNER})


class Board:
    """The parts of the model the checks read, built by hand."""

    # The model's own lookups: they read only `nodes` and `labels`.
    find = lc._Model.find
    net_named = lc._Model.net_named

    def __init__(self) -> None:
        self.labels = {VDD: "VDD", GND: "GND"}
        self.nodes: list[lc._Node] = []
        self.edges: list[lc._Edge] = []
        self.pieces: list[lc._Piece] = []
        self.contacts: dict[int, list[int]] = {}
        self.rd = SimpleNamespace(
            query=lambda kind: [("c1", SimpleNamespace(capacitance=1e-7))]
        )
        self.vdd = self.pad("c1.p1", 0.0, VDD)
        self.gnd = self.pad("c1.p2", 1.0, GND)

    def key(self, trace: str) -> str:
        return trace

    def label(self, net: int) -> str:
        return self.labels[net]

    def pad(self, key: str, x: float, net: int) -> int:
        """A pad of the component its key names: all but the last part."""
        shape = box(x - 0.25, -0.25, x + 0.25, 0.25)
        owner = key.rsplit(".", 1)[0]
        self.nodes.append(
            lc._Node(key, "pad", (x, 0.0), {net}, frozenset({TOP}), shape, owner=owner)
        )
        return len(self.nodes) - 1

    def via(self, x: float, y: float, net: int) -> int:
        shape = Point(x, y).buffer(0.15)
        self.nodes.append(lc._Node(f"via@{x},{y}", "via", (x, y), {net}, BOTH, shape))
        return len(self.nodes) - 1

    def in_pad(self, pad: int, via: int) -> None:
        self.contacts.setdefault(pad, []).append(via)
        self.contacts.setdefault(via, []).append(pad)

    def trace(self, a: int, b: int, width: float = 0.2) -> None:
        """A VDD trace on TOP from node `a` to node `b`, 3.0 long."""
        route = f"route{len(self.edges)}"
        self.edges.append(lc._Edge(a, b, VDD, TOP, route, 3.0, width, []))

    def fill(
        self,
        net: int,
        layer: int,
        touching: list[int],
        hole: tuple[float, float] | None = None,
    ) -> None:
        """A 10 by 10 fill, with a 0.4 radius hole at `hole` when given."""
        geom = box(-5, -5, 5, 5)
        if hole is not None:
            geom = geom.difference(Point(hole).buffer(0.4))
        self.pieces.append(
            lc._Piece(net, layer, f"pour{len(self.pieces)}", geom, touching)
        )


def decaps(board: Board, planes: list[int]) -> list[dict[str, Any]]:
    return lc._decap_vias(cast(lc._Model, board), {"plane_layers": planes}, [])


def pad_entry(entry: dict[str, Any], key: str) -> dict[str, Any]:
    return next(p for p in entry["pads"] if p["pad"] == key)


class DecapVias(unittest.TestCase):
    def test_a_ground_pad_over_a_plane_with_no_via_is_listed_and_fails(self) -> None:
        # The rule: a pad whose net has a plane under it needs a plane via.
        # Before, a capacitor with no via was left out of the list.
        board = Board()
        board.fill(GND, INNER, [])
        (entry,) = decaps(board, [INNER])
        self.assertEqual(entry["cap"], "c1")
        self.assertIs(entry["met"], False)
        self.assertIs(pad_entry(entry, "c1.p2").get("missing"), True)
        # VDD has no plane, so its pad needs no via and is not marked.
        self.assertNotIn("missing", pad_entry(entry, "c1.p1"))

    def test_a_via_in_the_ground_pad_that_reaches_the_plane_passes(self) -> None:
        board = Board()
        via = board.via(1.0, 0.0, GND)
        board.in_pad(board.gnd, via)
        board.fill(GND, INNER, [via])
        (entry,) = decaps(board, [INNER])
        self.assertIs(entry["met"], True)
        ground = pad_entry(entry, "c1.p2")
        self.assertNotIn("missing", ground)
        self.assertEqual([v["placement"] for v in ground["vias"]], ["in_pad"])
        # One pad has no via, so there is no pair to measure a gap between.
        self.assertNotIn("via_gap", entry)

    def test_a_via_the_plane_fill_does_not_touch_is_still_missing(self) -> None:
        # The via sits in the pad but in a hole in the plane: it reaches nothing.
        board = Board()
        via = board.via(1.0, 0.0, GND)
        board.in_pad(board.gnd, via)
        board.fill(GND, INNER, [], hole=(1.0, 0.0))
        (entry,) = decaps(board, [INNER])
        self.assertIs(entry["met"], False)
        self.assertIs(pad_entry(entry, "c1.p2").get("missing"), True)

    def test_a_fill_on_the_pads_own_layer_is_not_the_plane(self) -> None:
        # TOP counts as a plane too here (an outer-layer ground flood). The
        # in-pad via touches the TOP fill and sits in a hole of the INNER
        # one: the pad still has no via into a plane on another layer.
        board = Board()
        via = board.via(1.0, 0.0, GND)
        board.in_pad(board.gnd, via)
        board.fill(GND, TOP, [board.gnd, via])
        board.fill(GND, INNER, [], hole=(1.0, 0.0))
        (entry,) = decaps(board, [TOP, INNER])
        self.assertIs(entry["met"], False)
        self.assertIs(pad_entry(entry, "c1.p2").get("missing"), True)

    def test_through_a_pour_a_via_into_the_plane_beats_a_nearer_one(self) -> None:
        # Two vias in the TOP pour, both beside the pad: one 0.6 away in a
        # hole of the plane, one 1.5 away that the plane touches. The pad's
        # plane via is the one that reaches the plane.
        board = Board()
        near = board.via(1.0, 0.6, GND)
        far = board.via(1.0, -1.5, GND)
        board.fill(GND, TOP, [board.gnd, near, far])
        board.fill(GND, INNER, [far], hole=(1.0, 0.6))
        (entry,) = decaps(board, [INNER])
        ground = pad_entry(entry, "c1.p2")
        self.assertEqual([v["via"] for v in ground["vias"]], ["via@1.0,-1.5"])
        self.assertNotIn("missing", ground)
        self.assertIs(entry["met"], True)

    def test_a_pour_on_the_pads_layer_lends_its_nearest_via(self) -> None:
        # A TOP ground pour touches the pad and two vias: one 0.8 to the side
        # of the pad, one 1.5 past its outer end. The nearer one is the pad's.
        board = Board()
        side = board.via(1.0, 0.8, GND)
        past = board.via(2.5, 0.0, GND)
        board.fill(GND, TOP, [board.gnd, side, past])
        board.fill(GND, INNER, [side, past])
        (entry,) = decaps(board, [INNER])
        ground = pad_entry(entry, "c1.p2")
        self.assertEqual([v["via"] for v in ground["vias"]], ["via@1.0,0.8"])
        self.assertEqual(ground["vias"][0]["placement"], "side")
        self.assertIs(entry["met"], True)

    def test_with_no_plane_a_capacitor_without_vias_is_not_listed(self) -> None:
        # No plane to reach, so no pad needs a via: nothing to judge.
        self.assertEqual(decaps(Board(), []), [])

    def test_with_no_plane_a_via_in_each_pad_is_judged_as_before(self) -> None:
        board = Board()
        board.in_pad(board.vdd, board.via(0.0, 0.0, VDD))
        board.in_pad(board.gnd, board.via(1.0, 0.0, GND))
        (entry,) = decaps(board, [])
        self.assertIs(entry["met"], True)
        # The two vias sit at the pad centres, one pad pitch apart.
        self.assertEqual(entry["via_gap"], 1.0)


def power(board: Board, branches: dict[str, str] | None = None) -> dict[str, Any]:
    """The power check with VDD's rule at 1.0 and `branches` named on it.
    Step-down legs are at most 1.0 long, so no 3.0 trace is one."""
    config: dict[str, Any] = {"power": {"VDD": 1.0}}
    if branches is not None:
        config["power_branches"] = {"VDD": branches}
    return lc._power(cast(lc._Model, board), config, 1.0, None)


def branch_of(out: dict[str, Any]) -> dict[str, list[str]]:
    """Each narrow VDD trace by its far end, with the parts it feeds as a
    branch."""
    rows = out["nets"]["VDD"]["narrower_than_rule"]
    return {row["ends"][1]: row["branch"] for row in rows}


class PowerBranches(unittest.TestCase):
    def setUp(self) -> None:
        self.board = Board()
        self.pin = self.board.pad("u1.p1", 3.0, VDD)
        self.led = self.board.pad("r_led.p1", 6.0, VDD)
        self.load = self.board.pad("u2.p1", 9.0, VDD)

    def test_a_thin_trace_fails_the_net_until_its_part_is_named(self) -> None:
        self.board.trace(self.pin, self.led)
        self.assertIs(power(self.board)["nets"]["VDD"]["met"], False)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], True)
        self.assertEqual(branch_of(out), {"r_led.p1": ["r_led"]})
        # One 0.2 wide, 3.0 long trace serves the named part.
        self.assertEqual(
            out["branches"],
            [
                {
                    "net": "VDD",
                    "part": "r_led",
                    "why": "indicator, 2 mA",
                    "traces": 1,
                    "length": 3.0,
                    "narrowest": 0.2,
                }
            ],
        )

    def test_a_thin_trace_to_a_part_not_named_still_fails(self) -> None:
        # Naming the indicator excuses its own trace, not the load's.
        self.board.trace(self.pin, self.led)
        self.board.trace(self.pin, self.load)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(branch_of(out), {"r_led.p1": ["r_led"], "u2.p1": []})

    def test_a_trace_that_carries_on_from_the_named_part_is_not_one(self) -> None:
        # The load is fed through the indicator's pad, so both traces carry
        # the load's current: the one into the pad and the one out of it.
        self.board.trace(self.pin, self.led)
        self.board.trace(self.led, self.load)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(branch_of(out), {"r_led.p1": [], "u2.p1": []})
        # Naming the load as well makes both of them branches.
        both = power(self.board, {"r_led": "indicator, 2 mA", "u2": "bias, 1 mA"})
        self.assertIs(both["nets"]["VDD"]["met"], True)
        self.assertEqual(
            branch_of(both), {"r_led.p1": ["r_led", "u2"], "u2.p1": ["u2"]}
        )

    def test_a_branch_runs_through_a_via_that_feeds_nothing_else(self) -> None:
        via = self.board.via(4.5, 2.0, VDD)
        self.board.trace(self.pin, via)
        self.board.trace(via, self.led)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], True)
        self.assertEqual(out["branches"][0]["traces"], 2)
        self.assertEqual(out["branches"][0]["length"], 6.0)

    def test_a_via_that_also_feeds_a_load_ends_the_branch(self) -> None:
        # The leg from the pin to the via carries the load's current too.
        via = self.board.via(4.5, 2.0, VDD)
        self.board.trace(self.pin, via)
        self.board.trace(via, self.led)
        self.board.trace(via, self.load)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(
            branch_of(out),
            {"via@4.5,2.0": [], "r_led.p1": ["r_led"], "u2.p1": []},
        )

    def test_a_via_in_a_pour_ends_the_branch(self) -> None:
        # The thin leg from the pin joins it to the pour: that is supply
        # copper, whatever hangs off the via after it.
        via = self.board.via(4.5, 2.0, VDD)
        self.board.fill(VDD, INNER, [via])
        self.board.trace(self.pin, via)
        self.board.trace(via, self.led)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(branch_of(out), {"via@4.5,2.0": [], "r_led.p1": ["r_led"]})

    def test_a_named_part_tied_twice_to_one_pour_is_a_branch(self) -> None:
        # Both traces end on the same pour, so neither feeds anything but
        # the indicator between them.
        self.board.fill(VDD, TOP, [self.pin, self.load])
        self.board.trace(self.pin, self.led)
        self.board.trace(self.load, self.led)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], True)
        self.assertEqual(out["branches"][0]["traces"], 2)

    def test_a_named_part_between_two_pours_is_not_a_branch(self) -> None:
        # The traces are the only copper from one pour to the other, so
        # they carry what the second pour feeds.
        self.board.fill(VDD, TOP, [self.pin])
        self.board.fill(VDD, TOP, [self.load])
        self.board.trace(self.pin, self.led)
        self.board.trace(self.led, self.load)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(branch_of(out), {"r_led.p1": [], "u2.p1": []})

    def test_a_thin_trace_between_two_pads_on_one_pour_feeds_nothing(self) -> None:
        # The pour already joins the two pads, the named one included.
        self.board.fill(VDD, TOP, [self.pin, self.led])
        self.board.trace(self.pin, self.led)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(branch_of(out), {"r_led.p1": []})
        self.assertEqual(out["branches"][0]["traces"], 0)

    def test_a_trace_into_a_via_in_the_named_pad_is_a_branch(self) -> None:
        via = self.board.via(6.0, 0.0, VDD)
        self.board.in_pad(self.led, via)
        self.board.trace(self.pin, via)
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], True)

    def test_a_name_with_no_reason_excuses_nothing(self) -> None:
        self.board.trace(self.pin, self.led)
        out = power(self.board, {"r_led": " "})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(out["branches"], [])
        self.assertEqual(len(out["errors"]), 1)
        self.assertIn("r_led has no reason", out["errors"][0])

    def test_a_name_with_no_pad_on_the_net_is_an_error(self) -> None:
        self.board.trace(self.pin, self.led)
        out = power(self.board, {"c1.p2": "on GND, not VDD"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(len(out["errors"]), 1)
        self.assertIn("c1.p2 has no pad on VDD", out["errors"][0])

    def test_a_module_key_names_no_branch(self) -> None:
        # A name is one component or one pad. A module's key covers every
        # part under it, the load beside the indicator included.
        led = self.board.pad("blk.r_led.p1", 12.0, VDD)
        load = self.board.pad("blk.u3.p1", 15.0, VDD)
        self.board.trace(self.pin, led)
        self.board.trace(self.pin, load)
        out = power(self.board, {"blk": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(out["branches"], [])
        self.assertEqual(len(out["errors"]), 1)
        self.assertIn("blk covers more than one component", out["errors"][0])
        # The component's own key is a name.
        one = power(self.board, {"blk.r_led": "indicator, 2 mA"})
        self.assertEqual(
            branch_of(one), {"blk.r_led.p1": ["blk.r_led"], "blk.u3.p1": []}
        )

    def test_polygon_route_copper_at_the_named_pad_is_not_a_pour(self) -> None:
        # Route copper that came back as a polygon is route copper: on the
        # named pad alone it joins nothing, so the trace is still a branch.
        self.board.fill(VDD, TOP, [self.pin])
        self.board.trace(self.pin, self.led)
        blob = box(5.5, -0.5, 6.5, 0.5)
        self.board.pieces.append(
            lc._Piece(VDD, TOP, "route9", blob, [self.led], route="route9")
        )
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], True)
        self.assertEqual(branch_of(out), {"r_led.p1": ["r_led"]})

    def test_polygon_route_copper_on_to_a_load_ends_the_branch(self) -> None:
        # The polygon joins the indicator's pad to the load's, so the thin
        # trace into the indicator carries the load's current.
        self.board.trace(self.pin, self.led)
        blob = box(5.5, -0.5, 9.5, 0.5)
        self.board.pieces.append(
            lc._Piece(VDD, TOP, "route9", blob, [self.led, self.load], route="route9")
        )
        out = power(self.board, {"r_led": "indicator, 2 mA"})
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(branch_of(out), {"r_led.p1": []})

    def test_a_list_where_the_parts_go_is_an_error_not_a_crash(self) -> None:
        # The config is {net: {part: reason}}. A list of parts has no
        # reasons, so it names nothing and the trace still fails.
        self.board.trace(self.pin, self.led)
        config = {"power": {"VDD": 1.0}, "power_branches": {"VDD": ["r_led"]}}
        out = lc._power(cast(lc._Model, self.board), config, 1.0, None)
        self.assertIs(out["nets"]["VDD"]["met"], False)
        self.assertEqual(out["branches"], [])
        self.assertEqual(len(out["errors"]), 1)
        self.assertIn("power_branches: write", out["errors"][0])


if __name__ == "__main__":
    unittest.main()
