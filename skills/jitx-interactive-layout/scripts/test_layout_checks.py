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

The pin selection tests run `pin_ends` with a stand-in for
`rd.layout.route_ends` (each start's possible ends listed in the test), in
a scratch directory, and read what it saves and what the check makes of it.
Starts sit at x = 0 and their possible ends at x = 10 unless a test says
otherwise; each route is a trace from a start to an end on the start's net.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

try:
    import jitx  # noqa: F401
    import shapely  # noqa: F401
except ImportError:
    raise unittest.SkipTest(
        "needs jitx and shapely: run with the project's Python"
    ) from None

from shapely.geometry import Point, box
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

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


class LiveModel:
    """The model the checks read, with the session's own keys, for a run of
    every check: no traces, pours or capacitors."""

    find = lc._Model.find
    net_named = lc._Model.net_named

    def __init__(self, rd: Any) -> None:
        self.rd = rd
        self.key = lc._Keys(rd)
        self.labels: dict[int, str] = {}
        self.nodes: list[lc._Node] = []
        self.edges: list[lc._Edge] = []
        self.pieces: list[lc._Piece] = []
        self.contacts: dict[int, list[int]] = {}
        self.unmeasured: list[dict[str, Any]] = []
        self.fill_unknown: list[str] = []

    def label(self, net: int) -> str:
        return self.labels.get(net, f"net {net}")


class Live:
    """A stand-in session: `rd.query`, `rd.nets.find` and
    `rd.layout.route_ends` built from the pads, vias and routes a test
    adds, and the model the checks would build from it (placed pads only)."""

    def __init__(self, route_ends: bool = True) -> None:
        self.found: dict[type, list[tuple[Any, Any]]] = {}
        self.obj: dict[str, Any] = {}
        self.labels: dict[int, Any] = {}
        self.answers: dict[str, list[Any] | Exception] = {}
        layout = SimpleNamespace(route_ends=self.route_ends) if route_ends else None
        outline = SimpleNamespace(g=box(-50, -50, 50, 50))
        self.rd = SimpleNamespace(
            query=lambda kind: list(self.found.get(kind, [])),
            nets=SimpleNamespace(find=lambda o: self.labels.get(id(o))),
            layout=layout or SimpleNamespace(),
            root=SimpleNamespace(
                board=SimpleNamespace(shape=SimpleNamespace(to_shapely=lambda: outline))
            ),
        )
        self.board = LiveModel(self.rd)

    def _add(self, kind: type, key: str) -> Any:
        obj = SimpleNamespace(name=key)
        self.found.setdefault(kind, []).append(
            (SimpleNamespace(path=key.split(".")), obj)
        )
        self.obj[key] = obj
        return obj

    def pad(
        self,
        key: str,
        x: float,
        y: float,
        net: str | None = None,
        placed: bool = True,
        layers: frozenset[int] = frozenset({TOP}),
        shape: BaseGeometry | None = None,
    ) -> None:
        """A pad at (x, y): a 0.5 mm square unless ``shape`` is given."""
        obj = self._add(lc.Pad, key)
        if net is not None:
            self.labels[id(obj)] = self.net(net)
        if placed:
            if shape is None:
                shape = box(x - 0.25, y - 0.25, x + 0.25, y + 0.25)
            self.board.nodes.append(lc._Node(key, "pad", (x, y), set(), layers, shape))

    def via(
        self,
        key: str,
        x: float,
        y: float,
        layers: frozenset[int] = BOTH,
        shape: BaseGeometry | None = None,
    ) -> None:
        """A via at (x, y): 0.3 mm across unless ``shape`` is given."""
        self._add(lc.Via, key)
        if shape is None:
            shape = Point(x, y).buffer(0.15)
        self.board.nodes.append(lc._Node(key, "via", (x, y), set(), layers, shape))

    def net(self, name: str) -> Any:
        nets = cast(dict[str, Any], self.__dict__.setdefault("_nets", {}))
        return nets.setdefault(name, SimpleNamespace(name=name))

    def control(self, key: str, **ends: Any) -> Any:
        """A control point with the given end objects (`pad`, `coupled`,
        `uncoupled`, `front`, `back`)."""
        cp = SimpleNamespace(name=key, **ends)
        self.found.setdefault(lc.ControlPoint, []).append(
            (SimpleNamespace(path=key.split(".")), cp)
        )
        return cp

    def route(self, a: str | Any, b: str | Any) -> None:
        """A routed route between two keys, or two end objects."""
        route = SimpleNamespace(
            source=self.obj[a] if isinstance(a, str) else a,
            destination=self.obj[b] if isinstance(b, str) else b,
            status=SimpleNamespace(routed=True),
        )
        n = len(self.found.get(lc.Route, []))
        self.found.setdefault(lc.Route, []).append(
            (SimpleNamespace(path=["routes", str(n)]), route)
        )

    def unplace(self, key: str) -> None:
        self.board.nodes = [n for n in self.board.nodes if n.key != key]

    def route_ends(self, start: Any) -> list[Any]:
        answer = self.answers[start.name]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def answer(self, **ends: list[str]) -> None:
        """Each start's possible ends, as the objects queried for them."""
        self.answers = {s: [self.obj[e] for e in keys] for s, keys in ends.items()}

    def _config(self, groups: dict[str, Any]) -> dict[str, Any]:
        config = {"pin_selection": groups}
        path = Path.cwd() / lc.OUT_DIR / lc.CONFIG
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config))
        return config

    def read(self, groups: dict[str, Any]) -> dict[str, Any]:
        self._config(groups)
        with patch.object(lc, "_Model", lambda rd: self.board):
            return lc.pin_ends(self.rd)["groups"]

    def check(self, groups: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """The run's summary and its full checks.json."""
        config = self._config(groups)
        with patch.object(lc, "_Model", lambda rd: self.board):
            summary = lc.run(self.rd, config)
        full = json.loads((Path.cwd() / lc.OUT_DIR / "checks.json").read_text())
        return summary, full

    def group(self, groups: dict[str, Any], name: str = "bus") -> dict[str, Any]:
        return self.check(groups)[1]["pin_selection"]["groups"][name]


def saved() -> dict[str, Any]:
    return json.loads((Path.cwd() / lc.OUT_DIR / lc.PIN_ENDS).read_text())["groups"]


# The two possible ends most pin selection tests name as the pool.
E12 = ["e1", "e2"]
BUS: dict[str, Any] = {"bus": {"starts": ["s1", "s2"], "ends": E12}}


def two_by_two(route_ends: bool = True) -> Live:
    """Two signals and two pins: the straight selection is s1 to e1 and s2
    to e2, 10 each; crossed over, each is sqrt(10^2 + 1^2) and the two
    segments cross at (5, 0.5)."""
    live = Live(route_ends)
    live.pad("s1", 0.0, 0.0, "A")
    live.pad("s2", 0.0, 1.0, "B")
    live.pad("e1", 10.0, 0.0)
    live.pad("e2", 10.0, 1.0)
    live.answer(s1=E12, s2=E12)
    return live


class InScratch(unittest.TestCase):
    def setUp(self) -> None:
        self.home = os.getcwd()
        self.scratch = tempfile.TemporaryDirectory()
        os.chdir(self.scratch.name)

    def tearDown(self) -> None:
        os.chdir(self.home)
        self.scratch.cleanup()


class PinEnds(InScratch):
    def test_the_selection_is_the_least_total_over_every_permutation(self) -> None:
        # Five starts, six ends, each start limited to its own ends. Taking
        # each start's nearest free end in order totals more than the least.
        live = Live()
        starts = {f"s{i}": (0.0, float(i)) for i in range(5)}
        ends = {
            "e0": (10.0, 0.0),
            "e1": (10.0, 1.5),
            "e2": (10.0, 3.0),
            "e3": (10.0, 4.5),
            "e4": (4.0, -3.0),
            "e5": (12.0, 8.0),
        }
        allowed = {
            "s0": ["e0", "e1", "e4"],
            "s1": ["e0", "e1"],
            "s2": ["e1", "e2", "e5"],
            "s3": ["e2", "e3"],
            "s4": ["e3", "e5", "e0"],
        }
        for key, (x, y) in {**starts, **ends}.items():
            live.pad(key, x, y)
        live.answer(**allowed)
        group = live.read({"bus": {"starts": list(starts), "ends": list(ends)}})["bus"]

        least = min(
            sum(math.dist(starts[s], ends[e]) for s, e in zip(starts, pick))
            for pick in itertools.permutations(ends, len(starts))
            if all(e in allowed[s] for s, e in zip(starts, pick))
        )
        self.assertIs(group["complete"], True)
        self.assertAlmostEqual(group["total_mm"], least, places=3)
        chosen = {row["start"]: row["end"] for row in group["selection"]}
        self.assertEqual(len(set(chosen.values())), len(starts))
        self.assertTrue(all(chosen[s] in allowed[s] for s in starts))
        # The answered objects come back as their keys, and no positions.
        self.assertEqual(saved(), {"bus": {"complete": True, "ends": allowed}})

    def test_an_answer_that_matches_no_queried_object_is_no_candidate(self) -> None:
        live = two_by_two()
        stranger = SimpleNamespace(name="stranger")
        live.answers["s1"] = [live.obj["e1"], stranger, live.obj["e2"]]
        group = live.read(BUS)["bus"]
        kept = saved()["bus"]["ends"]["s1"]
        self.assertEqual(len(kept), 3)
        self.assertEqual([kept[0], kept[2]], ["e1", "e2"])
        self.assertNotIn(kept[1], live.obj)
        self.assertEqual(group["candidates"], {"s1": 2, "s2": 2})

    def test_a_refused_start_is_a_group_error(self) -> None:
        live = two_by_two()
        live.answers["s2"] = lc.RequestRejected("unknown", "no such endpoint")
        group = live.read(BUS)["bus"]
        self.assertIs(group["complete"], False)
        self.assertTrue(
            any("s2" in e and "no such endpoint" in e for e in group["errors"])
        )
        self.assertEqual(saved()["bus"]["ends"]["s1"], E12)

    def test_a_start_unplaced_at_reading_time_is_an_error_not_a_crash(
        self,
    ) -> None:
        live = two_by_two()
        live.unplace("s2")
        live.pad("s3", 0.0, 5.0)
        live.pad("e3", 10.0, 5.0)
        live.answers["s3"] = [live.obj["e3"]]
        groups = {**BUS, "other": {"starts": ["s3"], "ends": ["e3"]}}
        read = live.read(groups)
        self.assertTrue(
            any("s2 names no placed pad" in e for e in read["bus"]["errors"])
        )
        self.assertNotIn("total_mm", read["bus"])
        self.assertAlmostEqual(read["other"]["total_mm"], 10.0, places=3)

    def test_a_later_reading_that_is_not_complete_keeps_the_complete_one(
        self,
    ) -> None:
        live = two_by_two()
        live.read(BUS)
        first = saved()
        # s1 is routed now, so it answers nothing.
        live.answer(s1=[], s2=["e2"])
        group = live.read(BUS)["bus"]
        self.assertIs(group["complete"], False)
        self.assertEqual(group["answered_nothing"], ["s1"])
        self.assertEqual(saved(), first)
        # A group gone from the config is dropped from the file.
        live.read({"other": {"starts": ["s2"], "ends": E12}})
        self.assertEqual(list(saved()), ["other"])

    def test_a_reading_that_is_not_complete_is_saved_when_none_was(self) -> None:
        live = two_by_two()
        live.answer(s1=["e1"], s2=[])
        live.read(BUS)
        self.assertEqual(
            saved(), {"bus": {"complete": False, "ends": {"s1": ["e1"], "s2": []}}}
        )

    def test_a_bad_accept_still_reads_the_pool(self) -> None:
        live = two_by_two()
        group = live.read({"bus": {**BUS["bus"], "accept": 3}})["bus"]
        self.assertTrue(any("accept is not a string" in e for e in group["errors"]))
        self.assertIs(saved()["bus"]["complete"], True)

    def test_it_fails_with_no_pools_no_ends_or_no_route_ends(self) -> None:
        config = Path.cwd() / lc.OUT_DIR / lc.CONFIG
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"scope": ["u1"]}))
        with self.assertRaisesRegex(ValueError, "pin_selection"):
            lc.pin_ends(two_by_two().rd)
        with self.assertRaisesRegex(ValueError, "ends is not a list"):
            two_by_two().read({"bus": {"starts": ["s1"]}})
        with self.assertRaises(RuntimeError) as caught:
            two_by_two(route_ends=False).read(BUS)
        self.assertIn("route_ends", str(caught.exception))
        self.assertNotIn("\n", str(caught.exception))


class PoolEnds(InScratch):
    def test_a_plain_pad_on_the_net_is_not_a_pin_choice(self) -> None:
        # s1's net also holds a pull-up pad 1 away, nearer than either pin
        # of u1 (10 away). With ends naming u1 the least total is the two
        # straight 10 routes, and the routed pull-up is not a realized end.
        live = Live()
        live.pad("s1", 0.0, 0.0)
        live.pad("s2", 0.0, 1.0)
        live.pad("r_pull.p.1", 1.0, 0.0)
        live.pad("u1.p.1", 10.0, 0.0)
        live.pad("u1.p.2", 10.0, 1.0)
        live.answer(s1=["r_pull.p.1", "u1.p.1", "u1.p.2"], s2=["u1.p.1", "u1.p.2"])
        groups = {"bus": {"starts": ["s1", "s2"], "ends": ["u1"]}}
        self.assertAlmostEqual(live.read(groups)["bus"]["total_mm"], 20.0, places=3)
        # The file keeps every answer as the runtime gave it.
        self.assertEqual(
            saved()["bus"]["ends"]["s1"], ["r_pull.p.1", "u1.p.1", "u1.p.2"]
        )
        live.route("s1", "r_pull.p.1")
        live.route("s1", "u1.p.1")
        live.route("s2", "u1.p.2")
        group = live.group(groups)
        self.assertEqual([r["end"] for r in group["starts"]], ["u1.p.1", "u1.p.2"])
        self.assertIs(group["met"], True)

    def test_an_entry_does_not_admit_a_key_that_only_shares_its_prefix(
        self,
    ) -> None:
        # u1.p.12 is nearer s1 (5 away) than u1.p.1 (10 away), and only
        # u1.p.1 is named.
        live = Live()
        live.pad("s1", 0.0, 0.0)
        live.pad("s2", 0.0, 1.0)
        live.pad("u1.p.12", 5.0, 0.0)
        live.pad("u1.p.1", 10.0, 0.0)
        live.answer(s1=["u1.p.12", "u1.p.1"], s2=["u1.p.12"])
        groups = {
            "one": {"starts": ["s1"], "ends": ["u1.p.1"]},
            "two": {"starts": ["s1", "s2"], "ends": ["u1.p.1"]},
        }
        read = live.read(groups)
        self.assertAlmostEqual(read["one"]["total_mm"], 10.0, places=3)
        # In "two", s2's only answer is outside ends: it has no candidate.
        self.assertTrue(any("s2: no possible end" in e for e in read["two"]["errors"]))
        group = live.group(groups, "two")
        self.assertTrue(any("s2: no possible end" in e for e in group["errors"]))
        self.assertIs(group["met"], False)


class PinSelection(InScratch):
    def test_the_least_total_selection_is_met(self) -> None:
        live = two_by_two()
        live.read(BUS)
        live.route("s1", "e1")
        live.route("s2", "e2")
        summary, full = live.check(BUS)
        group = full["pin_selection"]["groups"]["bus"]
        self.assertEqual(group["read"], "complete")
        self.assertAlmostEqual(group["realized_mm"], 20.0, places=3)
        self.assertAlmostEqual(group["least_mm"], 20.0, places=3)
        self.assertEqual(group["crossings"], {"realized": 0, "least": 0})
        self.assertIs(group["met"], True)
        # The summary echoes the pool and how many candidates each start has.
        brief = summary["pin_selection"]["groups"]["bus"]
        self.assertEqual(brief["ends"], E12)
        self.assertEqual(brief["candidates"], {"s1": 2, "s2": 2})
        self.assertIs(summary["pin_selection"]["met"], True)

    def test_a_longer_selection_fails_until_accept_gives_a_reason(self) -> None:
        live = two_by_two()
        live.read(BUS)
        live.route("s1", "e2")
        live.route("s2", "e1")
        group = live.group(BUS)
        crossed = 2 * math.hypot(10.0, 1.0)
        self.assertEqual([r["end"] for r in group["starts"]], ["e2", "e1"])
        self.assertAlmostEqual(group["realized_mm"], crossed, places=3)
        self.assertAlmostEqual(group["excess_mm"], crossed - 20.0, places=3)
        self.assertEqual(group["crossings"], {"realized": 1, "least": 0})
        self.assertIs(group["met"], False)
        blank = {"bus": {**BUS["bus"], "accept": "  "}}
        self.assertIs(live.group(blank)["met"], False)
        why = {"bus": {**BUS["bus"], "accept": "keeps SDA off the clock"}}
        group = live.group(why)
        self.assertIs(group["met"], True)
        self.assertAlmostEqual(group["excess_mm"], crossed - 20.0, places=3)

    def test_a_pool_routed_with_no_reading_fails_and_still_reads_routed(
        self,
    ) -> None:
        # Routed one signal at a time, straight to the nearest pin, and the
        # ends read only afterwards: routed starts answer nothing.
        live = two_by_two()
        live.route("s1", "e1")
        live.route("s2", "e2")
        summary, full = live.check(BUS)
        group = full["pin_selection"]["groups"]["bus"]
        self.assertEqual(group["read"], "none")
        self.assertIs(group["met"], False)
        self.assertAlmostEqual(group["realized_mm"], 20.0, places=3)
        self.assertIsNone(group["least_mm"])
        self.assertEqual(summary["pin_selection"]["groups"]["bus"]["open"], [])
        live.answer(s1=[], s2=[])
        self.assertEqual(live.read(BUS)["bus"]["answered_nothing"], ["s1", "s2"])
        group = live.group(BUS)
        self.assertEqual(group["read"], "partial")
        self.assertIs(group["met"], False)

    def test_each_error_fails_its_group(self) -> None:
        live = two_by_two()
        live.answer(s1=["e1"], s2=["e1"])
        live.read({"one_pin": {"starts": ["s1", "s2"], "ends": E12}})
        live.route("s1", "e1")
        groups = {
            "no_pad": {"starts": ["s1", "nope"], "ends": E12},
            "not_a_list": {"starts": "s1", "ends": E12},
            "accept_number": {"starts": ["s1"], "ends": E12, "accept": 3},
            "one_pin": {"starts": ["s1", "s2"], "ends": E12},
            "no_ends": {"starts": ["s1"]},
            "ends_empty": {"starts": ["s1"], "ends": []},
        }
        out = live.check(groups)[1]["pin_selection"]
        expected = {
            "no_pad": "nope names no placed pad",
            "not_a_list": "starts is not a list",
            "accept_number": "accept is not a string",
            "one_pin": "no one-to-one selection",
            "no_ends": "ends is not a list",
            "ends_empty": "ends is not a list",
        }
        for name, error in expected.items():
            group = out["groups"][name]
            self.assertIs(group["met"], False, name)
            self.assertTrue(any(error in e for e in group["errors"]), name)
        self.assertIs(out["met"], False)

    def test_an_open_start_or_two_pins_or_a_shared_pin_fails(self) -> None:
        live = two_by_two()
        live.read(BUS)
        live.route("s1", "e1")
        group = live.group(BUS)
        self.assertEqual([r["end"] for r in group["starts"]], ["e1", "open"])
        self.assertIs(group["met"], False)
        live.route("s1", "e2")
        group = live.group(BUS)
        self.assertTrue(any("more than one" in e for e in group["errors"]))
        live.found[lc.Route].pop()
        live.route("s2", "e1")
        group = live.group(BUS)
        self.assertTrue(any("all end at e1" in e for e in group["errors"]))
        self.assertIs(group["met"], False)

    def test_the_walk_passes_vias_and_plain_pads_and_stops_at_a_pool_pad(
        self,
    ) -> None:
        live = Live()
        live.pad("s1", 0.0, 0.0)
        live.pad("s2", 0.0, 1.0)
        live.via("v1", 5.0, 0.0)
        live.pad("c1.p.1", 5.0, 1.0)
        for n, y in ((1, 0.0), (2, 1.0), (3, 2.0)):
            live.pad(f"u1.p.{n}", 10.0, y)
        live.answer(s1=["u1.p.1", "u1.p.2"], s2=["u1.p.1", "u1.p.2"])
        groups = {"bus": {"starts": ["s1", "s2"], "ends": ["u1"]}}
        live.read(groups)
        live.route("s1", "v1")
        live.route("v1", "u1.p.1")
        # The walk stops at u1.p.1: what is routed on from it is not s1's.
        live.route("u1.p.1", "u1.p.3")
        live.route("s2", "c1.p.1")
        live.route("c1.p.1", "u1.p.2")
        group = live.group(groups)
        self.assertEqual([r["end"] for r in group["starts"]], ["u1.p.1", "u1.p.2"])
        self.assertEqual(group["errors"], [])

    def test_a_pair_walks_each_leg_to_its_own_pad(self) -> None:
        # P1 and N1 into insertion A, A's coupled end to a pair point's
        # back, its front to insertion B's coupled end, B out to P2 and N2.
        live = Live()
        live.pad("p1", 0.0, 0.0)
        live.pad("n1", 0.0, 1.0)
        live.pad("p2", 20.0, 0.0)
        live.pad("n2", 20.0, 1.0)

        def pair() -> Any:
            return SimpleNamespace(p=SimpleNamespace(), n=SimpleNamespace())

        a = live.control("ins_a", coupled=pair(), uncoupled=pair())
        mid = live.control("pp", front=pair(), back=pair())
        b = live.control("ins_b", coupled=pair(), uncoupled=pair())
        live.answer(p1=["p2"], n1=["n2"])
        groups = {"usb": {"starts": ["p1", "n1"], "ends": ["p2", "n2"]}}
        live.read(groups)
        live.route("p1", a.uncoupled.p)
        live.route("n1", a.uncoupled.n)
        live.route(a.coupled, mid.back)
        live.route(mid.front, b.coupled)
        live.route("p2", b.uncoupled.p)
        live.route("n2", b.uncoupled.n)
        group = live.group(groups, "usb")
        self.assertEqual([r["end"] for r in group["starts"]], ["p2", "n2"])
        self.assertEqual(group["errors"], [])
        self.assertIs(group["met"], True)

    def test_single_routes_walk_through_a_route_point(self) -> None:
        live = two_by_two()
        rp = live.control("rp", pad=SimpleNamespace())
        live.read(BUS)
        live.route("s1", rp.pad)
        live.route(rp.pad, "e1")
        live.route("s2", "e2")
        group = live.group(BUS)
        self.assertEqual([r["end"] for r in group["starts"]], ["e1", "e2"])
        self.assertIs(group["met"], True)

    def test_an_end_the_reading_does_not_list_fails_even_with_accept(
        self,
    ) -> None:
        live = two_by_two()
        live.answer(s1=["e1"], s2=["e2"])
        live.read(BUS)
        live.route("s1", "e2")
        live.route("s2", "e1")
        why = {"bus": {**BUS["bus"], "accept": "keeps SDA off the clock"}}
        group = live.group(why)
        self.assertTrue(
            any("s1" in e and "e2" in e and "pin_ends" in e for e in group["errors"])
        )
        self.assertIs(group["met"], False)

    def vias_in_pads(self, far_via_x: float, label: bool) -> Live:
        """s1's pad holds via v1 with no route at the pad; v1 is routed to
        v2 at (far_via_x, 0), and e1 is a 0.5 mm pad at (10, 0). s2 routes
        straight to e2."""
        live = two_by_two()
        if label:
            live.labels[id(live.obj["e1"])] = live.net("A")
        live.labels[id(live.obj["e2"])] = live.net("B")
        live.via("v1", 0.0, 0.0)
        live.via("v2", far_via_x, 0.0)
        live.read(BUS)
        live.route("v1", "v2")
        live.route("s2", "e2")
        return live

    def test_a_via_in_a_pad_joins_the_walk_to_it(self) -> None:
        full = self.vias_in_pads(10.0, label=True).check(BUS)[1]
        group = full["pin_selection"]["groups"]["bus"]
        self.assertEqual([r["end"] for r in group["starts"]], ["e1", "e2"])
        self.assertIs(group["met"], True)
        self.assertEqual(full["stale_labels"], [])

    def test_the_summary_says_the_walk_does_not_cross_pours(self) -> None:
        cannot = two_by_two().check(BUS)[0]["cannot_measure"]
        self.assertTrue(
            any(c.startswith("pin selection") and "pour" in c for c in cannot)
        )

    def test_a_via_does_not_join_a_pad_on_a_layer_it_is_not_on(self) -> None:
        # e1 is a bottom-side pad (on INNER only here); v2 is on TOP only,
        # inside e1's outline.
        live = Live()
        live.pad("s1", 0.0, 0.0, "A")
        live.pad("s2", 0.0, 1.0, "B")
        live.pad("e1", 10.0, 0.0, "A", layers=frozenset({INNER}))
        live.pad("e2", 10.0, 1.0, "B")
        live.via("v1", 0.0, 0.0)
        live.via("v2", 10.0, 0.0, layers=frozenset({TOP}))
        live.answer(s1=E12, s2=E12)
        live.read(BUS)
        live.route("v1", "v2")
        live.route("s2", "e2")
        group = live.group(BUS)
        self.assertEqual([r["end"] for r in group["starts"]], ["open", "e2"])

    def test_two_stacked_vias_with_no_route_between_join(self) -> None:
        # va's copper ends at x = 9.65, 0.1 short of e1 (from 9.75); vb at
        # 9.75 overlaps va (centres 0.25 apart, radii 0.15) and e1.
        live = two_by_two()
        live.labels[id(live.obj["e1"])] = live.net("A")
        live.labels[id(live.obj["e2"])] = live.net("B")
        live.via("va", 9.5, 0.0)
        live.via("vb", 9.75, 0.0)
        live.read(BUS)
        live.route("s1", "va")
        live.route("s2", "e2")
        group = live.group(BUS)
        self.assertEqual([r["end"] for r in group["starts"]], ["e1", "e2"])

    def test_a_via_joins_a_pad_within_the_end_tolerance_only(self) -> None:
        # e1's copper ends at x = 10.25 and v2's radius is 0.15: a gap of
        # 0.01 mm is within the 0.02 mm end tolerance, 0.03 mm is past it.
        within = self.vias_in_pads(10.25 + 0.15 + 0.01, label=True).group(BUS)
        self.assertEqual([r["end"] for r in within["starts"]], ["e1", "e2"])
        past = self.vias_in_pads(10.25 + 0.15 + 0.03, label=True).group(BUS)
        self.assertEqual([r["end"] for r in past["starts"]], ["open", "e2"])

    def test_a_pad_or_via_with_no_shape_joins_nothing(self) -> None:
        live = two_by_two()
        live.pad("c9.p.1", 5.0, 0.0, shape=ShapelyPolygon())
        live.via("v9", 5.0, 1.0, shape=ShapelyPolygon())
        live.read(BUS)
        live.route("s1", "e1")
        live.route("s2", "e2")
        group = live.group(BUS)
        self.assertEqual([r["end"] for r in group["starts"]], ["e1", "e2"])

    def test_a_via_in_an_unlabelled_pad_joins_it_and_lists_the_label(
        self,
    ) -> None:
        full = self.vias_in_pads(10.0, label=False).check(BUS)[1]
        group = full["pin_selection"]["groups"]["bus"]
        self.assertEqual([r["end"] for r in group["starts"]], ["e1", "e2"])
        self.assertEqual(full["stale_labels"], ["e1"])

    def test_a_via_beside_a_pad_joins_nothing(self) -> None:
        # e1's copper ends at x = 10.25; a 0.3 mm via at x = 10.6 ends at
        # 10.45, 0.2 mm away, far past the end tolerance.
        full = self.vias_in_pads(10.6, label=True).check(BUS)[1]
        group = full["pin_selection"]["groups"]["bus"]
        self.assertEqual([r["end"] for r in group["starts"]], ["open", "e2"])

    def test_a_start_that_loses_its_position_fails_its_group_only(self) -> None:
        live = two_by_two()
        live.pad("s3", 0.0, 5.0)
        live.pad("e3", 10.0, 5.0)
        live.answers["s3"] = [live.obj["e3"]]
        groups = {**BUS, "other": {"starts": ["s3"], "ends": ["e3"]}}
        live.read(groups)
        live.route("s3", "e3")
        live.unplace("s1")
        summary, full = live.check(groups)
        bus = full["pin_selection"]["groups"]["bus"]
        self.assertTrue(any("s1 names no placed pad" in e for e in bus["errors"]))
        self.assertIs(bus["met"], False)
        self.assertIs(full["pin_selection"]["groups"]["other"]["met"], True)
        self.assertIn("connectivity", summary)

    def test_a_realized_pad_whose_label_is_not_the_signal_net_is_listed(
        self,
    ) -> None:
        # e1 carries no net label (the capture's), s1 carries A; e2 is
        # labelled B, as s2 is.
        live = two_by_two()
        live.labels[id(live.obj["e2"])] = live.net("B")
        live.read(BUS)
        live.route("s1", "e1")
        live.route("s2", "e2")
        summary, full = live.check(BUS)
        self.assertEqual(full["stale_labels"], ["e1"])
        self.assertEqual(summary["stale_labels"], ["e1"])

    def test_without_route_ends_the_pool_is_not_measurable(self) -> None:
        live = two_by_two(route_ends=False)
        live.route("s1", "e1")
        live.route("s2", "e2")
        summary, full = live.check(BUS)
        group = full["pin_selection"]["groups"]["bus"]
        self.assertEqual(group["read"], "unavailable")
        self.assertIsNone(group["met"])
        self.assertIsNone(summary["pin_selection"]["met"])
        self.assertTrue(
            any("pin selection" in c and "bus" in c for c in summary["cannot_measure"])
        )


if __name__ == "__main__":
    unittest.main()
