"""Choose a placement from the layout state ``layout_report.py`` wrote.

Run from the project root with the project's Python, after a report:

    python <this file> sides <component>
    python <this file> audit [--ic <component> ...]
    python <this file> search --part <component> --pin <pad>
    python <this file> group --assign <component>=<pad>[@weight][,<pad>...] ...

It reads ``.jitx/interactive-layout/state.json`` (``--state`` names another
file), needs no session, sends no request and writes nothing: it prints
what it found, or the same as JSON with ``--json``. The state is as old as
the last report, so run ``layout_report.py`` again after a batch of
placements. Millimetres, board-absolute. A component is named by its key in
the state (``reg.buck``); a pad by its key (``reg.buck.landpattern.p.3``) or
as ``component:pad`` with the pad label ``sides`` prints (``reg.buck:p.3``).

``--ground`` names the ground nets (``GND`` when not given). Ground is left
out wherever a net ties a pin to a part: gaps, facing counts, pairs and
escape channels. A name no pad carries is refused, with the busiest nets
listed, because every figure would then be measured to the ground net;
``--ground`` with no names is for a board that has none. Exit codes: 0, 1
when ``search`` or ``group`` finds nothing legal, 2 for a state or an
argument it cannot use.

``sides`` lists a component's pads by the side of the package they are on,
in order along it, with nets, for its current rotation: west (-x), east
(+x), south (-y), north (+y), and the pads in the middle. Then it compares
the four rotations about the component's origin (``--at X Y`` for another
origin, which an unplaced component needs): how many pins face the larger
parts they connect to (``--toward`` names those parts instead), the summed
distance to them, and for each side of the package the room it has against
the small parts its nets need there. Room is the free depth to the nearest
larger part or the board edge, times the side's length. Need is the summed
courtyards of the small parts on that side's nets; they also need room to
route, so compare the two with the floorplan's allowance.

``audit`` measures a placement around each IC (every placed component with
more than ``--small`` pads, 4 when not given, or the ones ``--ic`` names),
the rows under each IC worst first. A
small part counts for an IC when it is in the IC's block (components
sharing the first part of their key) or either is at the top level of the
design; ``sides`` counts need the same way.

* ``pins``: each IC pin whose net reaches a small part: the gap to the
  nearest such pad, the part, and ``turned`` when a pad of that part that
  goes elsewhere (ground, or a net not on this IC) is nearer the pin than
  the pad that connects to it.
* ``parts``: each small-part pad on an IC net: the gap to the nearest IC pin
  on that net. A part close only to another passive shows here.
* ``pairs``: small parts with two signal pads that both go to IC pins (a
  crystal, a flying capacitor): the two gaps and their difference.
* ``blocked`` (with ``--track`` and ``--clear``): IC signal pins with no
  free channel straight out or at 45 degrees for ``--front`` mm (2 when
  not given). A channel is a track and its clearance each side wide, and
  another net's pad on the IC's side of the board closes it. Pins whose
  net a small part of the block serves are left out: that part belongs in
  front of its pin.

and for the board: courtyard area against board area on each side, for
each block (components sharing the first part of their key) the box around
its courtyards against their sum, and the placed parts that collide:
``courtyard_overlaps``, pairs on one side whose courtyards overlap, and
``pad_overlaps``, pairs whose keep-outs overlap and whose courtyards do not,
each with the two keys, the area, and ``approximate``, true when either
part is turned off a quarter turn so its courtyard box is larger than the
part. These two lists compare courtyards as the boxes the state gives, so
when either has an entry the notes say so: ``layout_report.py``'s summary
and ``layout_checks.py``'s ``sanity`` compare the real shapes.

``search`` tries one part at every position on a ``--step`` grid (0.05)
within ``--radius`` of a pin (2 mm plus half the part's longer side), at
the four rotations, on the part's own side, or the IC's when it is
unplaced, or ``--side``. It lists the ``--top`` (10) legal spots nearest
the pin, as the x, y and rotation ``rd.layout.place`` takes: keep-out
inside the board and clear of every other part's keep-out, and pad copper
at least ``--clear`` from every other part's pad copper on that side,
whatever the nets (without ``--clear``, not touching; the output then says
clearance was not checked beyond that). ``search`` and ``group`` take
``--clear`` for this with or without ``--track``.
``gap`` is from the part's pad on the pin's net to the pin, ``faces`` is
false when another pad of the part is nearer the pin, ``partner`` is the
gap to ``--partner``'s pad on the net the two share. With ``--track`` and
``--clear`` it counts the IC pins whose last free channel the spot would
close and ranks those spots last. ``--conflicts`` also lists spots that
overlap other parts, ranked by gap with the rest and naming what they
overlap, so the part to move is known; ``--movable`` limits those to the
named parts. Overlapping spots are counted apart from the legal ones.
Spots closer together than ``--spread`` (0.5) at one rotation are listed
once. It exits 1 when no spot is legal, whatever ``--conflicts`` lists.

``group`` places several parts that compete for the same pins. Each
``--assign`` gives a part and the pin or two pins it serves, each with a
weight for how much distance that connection tolerates (1 by default,
larger for a filtered path). The parts are lifted, with any ``--lift``
names; in each order tried, every part takes its best legal spot given the
ones before it, on a ``--step`` grid (0.15) within ``--radius``, and the
channels its pads close are closed for the parts after it. It tries
``--max-orders`` orders (6, or one for each part when there are more),
the first ones each led by a different part, and lists the ``--top`` (3)
ranked by blocked channels, then the worst weighted gap, then the sum. It
exits 1 when no order fits.

A part's keep-out is its courtyard and every one of its pads, since a land
pattern can put pads past its courtyard; two keep-outs collide when they
overlap by more than a rounding error, whatever the pads' nets. Courtyards
are the boxes the report gives. A part on the other side of the board
collides only through its through-hole pads, which count on both sides, and
closes no escape channel. A state written before the report marked
through-hole pads checks every pad on its own part's side only, and a pad
the state does not give on the board, or gives with no outline, is left out
of its part's keep-out while its other pads stay in; the output says so in
both cases. A part at a rotation that is not a multiple
of 90 degrees has a box larger than the part, which the output says. An
unplaced part's pads and courtyard come from the report in the part's own
frame; a state with no ``courtyard_local`` for it is too old to search it.
A bottom-side part is mirrored in x before it is rotated, as
``jitx.placement.Placement`` does.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import prep

STATE = Path(".jitx/interactive-layout/state.json")
ROTATIONS = (0.0, 90.0, 180.0, 270.0)
SIDE_NAMES = ("west (-x)", "east (+x)", "south (-y)", "north (+y)")
NORMALS = ((-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0))
EPS = 1e-6
EDGE_TOL = 0.01
SIDES = ("top", "bottom")
CENTRE_FRACTION = 0.25

Box = tuple[float, float, float, float]


class UsageError(Exception):
    """A request this state cannot answer: main prints it and exits 2."""


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    rot: float
    side: str

    @property
    def mirror(self) -> float:
        return -1.0 if self.side == "bottom" else 1.0

    def listed(self) -> list[Any]:
        return [self.x, self.y, self.rot, self.side]


@dataclass(frozen=True)
class Pad:
    key: str
    label: str
    net: str | None
    own: BaseGeometry
    board: BaseGeometry | None
    through_hole: bool = False
    known: bool = True
    """Whether the pad has an outline, on the board when its part is
    placed: a pad that is not known is left out of its part's keep-out."""


@dataclass(frozen=True)
class Part:
    key: str
    mpn: str | None
    pose: Pose | None
    pads: tuple[Pad, ...]
    court_own: Box | None
    court_board: Box | None
    court_size: tuple[float, float] | None
    court_note: str | None

    @property
    def court_area(self) -> float:
        """From the report's ``courtyard_size`` when it has one: that is the
        part's own box at any rotation, and needs no frame."""
        if self.court_size is not None:
            return self.court_size[0] * self.court_size[1]
        if self.court_own is None:
            return 0.0
        x0, y0, x1, y1 = self.court_own
        return (x1 - x0) * (y1 - y0)


@dataclass(frozen=True)
class Board:
    design: str
    outline: Polygon
    parts: dict[str, Part]
    pad_owner: dict[str, str]
    holes_known: bool = True
    """Whether the state marks through-hole pads: one written before the
    report did does not."""


@dataclass(frozen=True)
class Keepout:
    """What a part keeps clear on one side of the board: its courtyard and
    pads on its own side, its through-hole pads on the other."""

    key: str
    shape: BaseGeometry
    bounds: Box
    court: Box | None
    """The courtyard box, on the part's own side only."""
    copper: BaseGeometry | None
    """The part's pads on this side, for clearance."""


@dataclass(frozen=True)
class Lane:
    """An IC pin's escape channels that nothing closes today, and the side
    of the board they are on."""

    pad: Pad
    free: tuple[BaseGeometry, ...]
    side: str


@dataclass(frozen=True)
class Spot:
    x: float
    y: float
    rot: float
    gap: float
    faces: bool | None
    partner: float | None
    blocked: tuple[str, ...]
    overlaps: tuple[str, ...]

    def listed(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "rotation": self.rot,
            "gap_mm": round(self.gap, 3),
            "faces": self.faces,
            "partner_mm": None if self.partner is None else round(self.partner, 3),
            "blocked": list(self.blocked),
            "overlaps": list(self.overlaps),
        }


def _cs(rot: float) -> tuple[float, float]:
    """Cosine and sine of a rotation, exact on the quarter turns."""
    quarter = round(rot / 90.0)
    if abs(rot - 90.0 * quarter) < 1e-9:
        return ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[quarter % 4]
    angle = math.radians(rot)
    return math.cos(angle), math.sin(angle)


def _quarter(rot: float) -> bool:
    return abs(rot - 90.0 * round(rot / 90.0)) < 1e-9


def to_board(geom: BaseGeometry, pose: Pose) -> BaseGeometry:
    """A shape in a part's own frame, on the board at ``pose``: mirrored in x
    on the bottom side, turned counter-clockwise, then moved."""
    c, s = _cs(pose.rot)
    m = pose.mirror
    return affinity.affine_transform(geom, [m * c, -s, m * s, c, pose.x, pose.y])


def to_own(geom: BaseGeometry, pose: Pose) -> BaseGeometry:
    """The inverse of ``to_board``."""
    c, s = _cs(pose.rot)
    m = pose.mirror
    return affinity.affine_transform(
        geom,
        [m * c, m * s, -s, c, -m * (c * pose.x + s * pose.y), s * pose.x - c * pose.y],
    )


def turn(vec: tuple[float, float], pose: Pose) -> tuple[float, float]:
    """A direction in a part's own frame, as a direction on the board."""
    c, s = _cs(pose.rot)
    x, y = pose.mirror * vec[0], vec[1]
    return c * x - s * y, s * x + c * y


def _shape(outline: Any, pos: Sequence[float]) -> BaseGeometry:
    if outline and len(outline) >= 4:
        return Polygon(outline)
    return Point(pos[0], pos[1])


def _label(pad_key: str, owner: str) -> str:
    label = pad_key[len(owner) + 1 :]
    while label.startswith("landpattern."):
        label = label[len("landpattern.") :]
    return label


def _owner(pad_key: str, keys: set[str]) -> str | None:
    head = pad_key
    while "." in head:
        head = head.rsplit(".", 1)[0]
        if head in keys:
            return head
    return None


def _courtyard(
    comp: dict[str, Any], pose: Pose | None
) -> tuple[Box | None, str | None]:
    """A part's courtyard box in its own frame, and what is approximate in it.

    A part placed on a quarter turn gives it exactly from its box on the
    board. Otherwise it is the report's ``courtyard_local``. An unplaced
    part with no ``courtyard_local`` has none: a state that old does not
    say where the courtyard sits against the pads."""
    court = comp.get("courtyard")
    local = comp.get("courtyard_local")
    exact = court and pose is not None and _quarter(pose.rot)
    if local and not exact:
        return (local[0], local[1], local[2], local[3]), None
    if court and pose is not None:
        x0, y0, x1, y1 = to_own(box(*court), pose).bounds
        note = (
            None
            if exact
            else "its courtyard is the box around the turned part, larger than the part"
        )
        return (x0, y0, x1, y1), note
    return None, None


def load(path: Path) -> Board:
    try:
        state = json.loads(path.read_text())
    except FileNotFoundError:
        raise UsageError(
            f"{path} not found: run layout_report.py against the session first"
        ) from None
    except json.JSONDecodeError as error:
        raise UsageError(
            f"{path} is not JSON ({error.msg}, line {error.lineno}): "
            "run layout_report.py again"
        ) from None
    if not isinstance(state, dict) or not all(
        isinstance(state.get(name), list) for name in ("components", "pads")
    ):
        raise UsageError(
            f"{path} has no components or pads: it is not a state.json "
            "from layout_report.py"
        )
    outline = state.get("board")
    if not outline or len(outline) < 4:
        raise UsageError(f"{path} has no board outline")
    keys = {c["key"] for c in state["components"]}
    raw: dict[str, list[dict[str, Any]]] = {k: [] for k in keys}
    pad_owner: dict[str, str] = {}
    for pad in state["pads"]:
        owner = _owner(pad["key"], keys)
        if owner is not None:
            raw[owner].append(pad)
            pad_owner[pad["key"]] = owner
    parts: dict[str, Part] = {}
    for comp in state["components"]:
        key = comp["key"]
        placement = comp.get("placement")
        pose = (
            Pose(
                float(placement[0]),
                float(placement[1]),
                float(placement[2]),
                str(placement[3]),
            )
            if placement
            else None
        )
        pads: list[Pad] = []
        for pad in raw[key]:
            geom = _shape(pad.get("outline"), pad["pos"])
            on_board = pose is not None and bool(pad.get("placed"))
            pads.append(
                Pad(
                    key=pad["key"],
                    label=_label(pad["key"], key),
                    net=pad.get("net"),
                    own=to_own(geom, pose) if on_board and pose is not None else geom,
                    board=geom if on_board else None,
                    through_hole=bool(pad.get("through_hole")),
                    known=isinstance(geom, Polygon) and (pose is None or on_board),
                )
            )
        court_own, note = _courtyard(comp, pose)
        court = comp.get("courtyard")
        size = comp.get("courtyard_size")
        parts[key] = Part(
            key=key,
            mpn=comp.get("mpn"),
            pose=pose,
            pads=tuple(pads),
            court_own=court_own,
            court_board=(court[0], court[1], court[2], court[3]) if court else None,
            court_size=(float(size[0]), float(size[1])) if size else None,
            court_note=note,
        )
    return Board(
        design=str(state.get("design")),
        outline=Polygon(outline),
        parts=parts,
        pad_owner=pad_owner,
        holes_known=all("through_hole" in pad for pad in state["pads"]),
    )


def find_part(board: Board, key: str) -> Part:
    if key in board.parts:
        return board.parts[key]
    near = sorted(k for k in board.parts if key in k or k in key)[:8]
    hint = f"; close: {', '.join(near)}" if near else ""
    raise UsageError(f"no component {key!r} in the state{hint}")


def find_pad(board: Board, text: str) -> tuple[Part, Pad]:
    if text in board.pad_owner:
        part = board.parts[board.pad_owner[text]]
        return part, next(p for p in part.pads if p.key == text)
    comp, sep, label = text.partition(":")
    if sep and comp in board.parts:
        part = board.parts[comp]
        for pad in part.pads:
            if pad.label == label:
                return part, pad
        labels = ", ".join(p.label for p in part.pads[:40])
        raise UsageError(f"{comp} has no pad {label!r}; its pads: {labels}")
    raise UsageError(
        f"no pad {text!r} in the state: give a pad key, or component:pad "
        "with a label that sides prints"
    )


def is_small(part: Part, small: int) -> bool:
    return len(part.pads) <= small


def pin_sides(part: Part) -> dict[str, int | None]:
    """Which side of the package each pad is on, in the part's own frame: an
    index into ``SIDE_NAMES``, or None for a pad in the middle.

    A pad belongs to the nearest edge of the box around the pad centres. A
    corner pad, equally near two edges, goes to the edge more pads sit on
    (the rows of a two-row package), then to the edge its long side points
    at."""
    centres = {p.key: (p.own.centroid.x, p.own.centroid.y) for p in part.pads}
    if not centres:
        return {}
    xs = [c[0] for c in centres.values()]
    ys = [c[1] for c in centres.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    usable = [hw > EDGE_TOL, hw > EDGE_TOL, hh > EDGE_TOL, hh > EDGE_TOL]

    def edge_distances(point: tuple[float, float]) -> tuple[float, ...]:
        return (point[0] - x0, x1 - point[0], point[1] - y0, y1 - point[1])

    def in_middle(point: tuple[float, float]) -> bool:
        return (
            abs(point[0] - cx) <= CENTRE_FRACTION * hw + EDGE_TOL
            and abs(point[1] - cy) <= CENTRE_FRACTION * hh + EDGE_TOL
        )

    on_edge = [0, 0, 0, 0]
    for point in centres.values():
        if in_middle(point):
            continue
        for i, d in enumerate(edge_distances(point)):
            if usable[i] and d <= EDGE_TOL:
                on_edge[i] += 1
    sides: dict[str, int | None] = {}
    for pad in part.pads:
        point = centres[pad.key]
        if in_middle(point) or not any(usable):
            sides[pad.key] = None
            continue
        dist = edge_distances(point)
        nearest = min(d for i, d in enumerate(dist) if usable[i])
        tied = [i for i, d in enumerate(dist) if usable[i] and d <= nearest + EDGE_TOL]
        if len(tied) > 1:
            most = max(on_edge[i] for i in tied)
            tied = [i for i in tied if on_edge[i] == most]
        if len(tied) > 1:
            bx0, by0, bx1, by1 = pad.own.bounds
            wide = (bx1 - bx0) - (by1 - by0)
            if abs(wide) > EDGE_TOL:
                tied = [i for i in tied if (i < 2) == (wide > 0)] or tied
        sides[pad.key] = tied[0]
    return sides


def _board_side(normal: tuple[float, float]) -> int:
    if abs(normal[0]) >= abs(normal[1]):
        return 1 if normal[0] > 0 else 0
    return 3 if normal[1] > 0 else 2


def _overlap(a: Box, b: Box) -> bool:
    return (
        min(a[2], b[2]) - max(a[0], b[0]) > EPS
        and min(a[3], b[3]) - max(a[1], b[1]) > EPS
    )


def _shift(b: Box, x: float, y: float) -> Box:
    return (b[0] + x, b[1] + y, b[2] + x, b[3] + y)


def _court_at(part: Part, pose: Pose) -> Box:
    if part.court_own is None:
        raise UsageError(f"{part.key} has no courtyard in the state")
    x0, y0, x1, y1 = to_board(box(*part.court_own), pose).bounds
    return (x0, y0, x1, y1)


def _occupied(board: Board, side: str, lifted: set[str]) -> list[tuple[str, Box]]:
    return [
        (p.key, p.court_board)
        for p in board.parts.values()
        if p.key not in lifted
        and p.pose is not None
        and p.pose.side == side
        and p.court_board is not None
    ]


def _keepout(part: Part, side: str, pose: Pose | None = None) -> Keepout | None:
    """What ``part`` keeps clear on ``side``, placed as it is or at ``pose``:
    None when it is unplaced, or keeps nothing there."""
    at = pose or part.pose
    if at is None:
        return None
    own_side = at.side == side
    court: Box | None = None
    if own_side and pose is not None and part.court_own is not None:
        court = _court_at(part, pose)
    elif own_side and pose is None:
        court = part.court_board
    pads: list[BaseGeometry] = []
    for pad in part.pads:
        if not pad.known or (not own_side and not pad.through_hole):
            continue
        geom = to_board(pad.own, pose) if pose is not None else pad.board
        if geom is not None:
            pads.append(geom)
    shapes = pads + ([box(*court)] if court is not None else [])
    if not shapes:
        return None
    shape = unary_union(shapes)
    x0, y0, x1, y1 = shape.bounds
    copper = unary_union(pads) if pads else None
    return Keepout(part.key, shape, (x0, y0, x1, y1), court, copper)


def _keepouts(board: Board, side: str, lifted: set[str]) -> list[Keepout]:
    """What the placed parts, but ``lifted``, keep clear on ``side``."""
    out: list[Keepout] = []
    for part in board.parts.values():
        if part.key in lifted:
            continue
        keep = _keepout(part, side)
        if keep is not None:
            out.append(keep)
    return out


def _clashes(a: Keepout, b: Keepout) -> bool:
    """Whether two keep-outs on one side collide: their courtyard boxes
    overlap by more than ``EPS`` each way, as two courtyards always have, or
    the two shapes share more than ``EPS`` mm2."""
    if not _overlap(a.bounds, b.bounds):
        return False
    if a.court is not None and b.court is not None and _overlap(a.court, b.court):
        return True
    return a.shape.intersection(b.shape).area > EPS


def _other(side: str) -> str:
    return "bottom" if side == "top" else "top"


def _pad_notes(board: Board, keys: Sequence[str] = ()) -> list[str]:
    """What the keep-outs leave out: pads that are not known, of placed
    parts and of the parts ``keys`` names, and through-hole pads the state
    does not mark."""
    notes: list[str] = []
    unknown = sorted(
        p.key
        for p in board.parts.values()
        if any(not pad.known for pad in p.pads)
        and (p.pose is not None or p.key in keys)
    )
    if unknown:
        shown = ", ".join(unknown[:8]) + (", ..." if len(unknown) > 8 else "")
        notes.append(
            f"{len(unknown)} parts have pads left out of their keep-out: the "
            f"state gives those pads no outline, or not on the board ({shown})"
        )
    if not board.holes_known:
        notes.append(
            "the state does not mark through-hole pads (run layout_report.py "
            "again): every pad is checked on its own part's side only"
        )
    return notes


def _net_pads(
    board: Board, skip: set[str]
) -> dict[str, list[tuple[Part, Pad, BaseGeometry]]]:
    """Placed pads by net, leaving out the parts in ``skip``."""
    by_net: dict[str, list[tuple[Part, Pad, BaseGeometry]]] = {}
    for part in board.parts.values():
        if part.key in skip:
            continue
        for pad in part.pads:
            if pad.net is not None and pad.board is not None:
                by_net.setdefault(pad.net, []).append((part, pad, pad.board))
    return by_net


def _channels(
    pad_geom: BaseGeometry, normal: tuple[float, float], front: float, width: float
) -> list[BaseGeometry]:
    """Channels ``width`` wide and ``front`` long leaving a pad's outer edge,
    straight out and at 45 degrees either way."""
    centre = pad_geom.centroid
    coords = (
        list(pad_geom.exterior.coords)
        if isinstance(pad_geom, Polygon)
        else [(centre.x, centre.y)]
    )
    reach = max(
        (x - centre.x) * normal[0] + (y - centre.y) * normal[1] for x, y in coords
    )
    sx, sy = centre.x + reach * normal[0], centre.y + reach * normal[1]
    out: list[BaseGeometry] = []
    for angle in (0.0, 45.0, -45.0):
        a = math.radians(angle)
        vx = normal[0] * math.cos(a) - normal[1] * math.sin(a)
        vy = normal[0] * math.sin(a) + normal[1] * math.cos(a)
        line = LineString([(sx, sy), (sx + front * vx, sy + front * vy)])
        out.append(line.buffer(width / 2, cap_style="flat"))
    return out


def escape_lanes(
    board: Board,
    ic: Part,
    skip_parts: set[str],
    skip_nets: set[str],
    front: float,
    width: float,
) -> list[tuple[Pad, list[BaseGeometry], list[str]]]:
    """For each signal pin on a side of ``ic``: the channels no other net's
    pad closes today, and the pads closing the rest. Only pads of parts on
    the IC's side of the board count; pads of ``skip_parts`` and of the IC
    itself do not."""
    if ic.pose is None:
        return []
    others = [
        (pad, geom)
        for pads in _net_pads(board, skip_parts | {ic.key}).values()
        for part, pad, geom in pads
        if part.pose is not None and part.pose.side == ic.pose.side
    ]
    sides = pin_sides(ic)
    lanes: list[tuple[Pad, list[BaseGeometry], list[str]]] = []
    for pad in ic.pads:
        side = sides.get(pad.key)
        if pad.net is None or pad.net in skip_nets or pad.board is None or side is None:
            continue
        free: list[BaseGeometry] = []
        closing: set[str] = set()
        for channel in _channels(pad.board, turn(NORMALS[side], ic.pose), front, width):
            hits = [
                o.key for o, g in others if o.net != pad.net and g.intersects(channel)
            ]
            if hits:
                closing.update(hits)
            else:
                free.append(channel)
        lanes.append((pad, free, sorted(closing)))
    return lanes


def _free_lanes(
    board: Board,
    ics: Sequence[Part],
    lifted: set[str],
    skip_nets: set[str],
    front: float,
    track: float | None,
    clear: float | None,
) -> list[Lane] | None:
    if track is None or clear is None:
        return None
    lanes: list[Lane] = []
    for ic in ics:
        if ic.pose is None:
            continue
        for pad, free, _ in escape_lanes(
            board, ic, lifted, skip_nets, front, track + 2 * clear
        ):
            if free:
                lanes.append(Lane(pad, tuple(free), ic.pose.side))
    return lanes


def _pads_at(part: Part, pose: Pose) -> list[tuple[Pad, BaseGeometry]]:
    return [(p, to_board(p.own, pose)) for p in part.pads]


def _closed_by(lane: Lane, pads: Sequence[tuple[Pad, BaseGeometry]]) -> list[bool]:
    """For each free channel of ``lane``, whether another net's pad in
    ``pads`` closes it."""
    return [
        any(g.intersects(channel) for p, g in pads if p.net != lane.pad.net)
        for channel in lane.free
    ]


def _lanes_after(
    lanes: Sequence[Lane], side: str, pads: Sequence[tuple[Pad, BaseGeometry]]
) -> list[Lane]:
    """The lanes left once a part with ``pads`` is placed on ``side``: its
    pads close some channels, and a pin with none left drops out."""
    left: list[Lane] = []
    for lane in lanes:
        if lane.side != side:
            left.append(lane)
            continue
        closed = _closed_by(lane, pads)
        free = tuple(c for c, shut in zip(lane.free, closed, strict=True) if not shut)
        if free:
            left.append(Lane(lane.pad, free, lane.side))
    return left


def iter_spots(
    board: Board,
    part: Part,
    side: str,
    pins: Sequence[tuple[Pad, float]],
    radius: float,
    step: float,
    occupied: Sequence[Keepout],
    reject: set[str] | None,
    lanes: Sequence[Lane],
    partner: Sequence[tuple[BaseGeometry, BaseGeometry]] | None = None,
    beneath: Sequence[Keepout] = (),
    clear: float | None = None,
) -> Iterator[Spot]:
    """Every legal spot for ``part`` within ``radius`` of the centre of
    ``pins``: its keep-out inside the board. ``occupied`` is what the other
    parts keep clear on ``side``, and ``beneath`` on the other side, where
    only the part's through-hole pads reach. A part collides when the
    keep-outs overlap, or when the pads come within ``clear`` (None: touch).
    ``reject`` None refuses any collision; a set refuses one with those
    parts and records the others."""
    if part.court_own is None:
        raise UsageError(
            f"{part.key} has no courtyard in the state (an unplaced part needs "
            "courtyard_local: run this skill's layout_report.py again)"
        )
    if step <= 0 or radius <= 0:
        raise UsageError("--step and --radius are above 0")
    lanes = [lane for lane in lanes if lane.side == side]
    pin_geoms: list[tuple[Pad, BaseGeometry, float]] = []
    for pin, weight in pins:
        if pin.board is None:
            raise UsageError(f"{pin.key} is on an unplaced component")
        if not any(p.net == pin.net for p in part.pads):
            raise UsageError(
                f"{part.key} has no pad on {pin.net}, the net of {pin.key}"
            )
        pin_geoms.append((pin, pin.board, weight))
    cx = sum(g.centroid.x for _, g, _ in pin_geoms) / len(pin_geoms)
    cy = sum(g.centroid.y for _, g, _ in pin_geoms) / len(pin_geoms)
    gap = clear or 0.0
    shapes: dict[
        float, tuple[list[tuple[Pad, BaseGeometry]], Keepout, Keepout | None]
    ] = {}
    for rot in ROTATIONS:
        origin = Pose(0.0, 0.0, rot, side)
        keep = _keepout(part, side, origin)
        assert keep is not None  # it has a courtyard
        shapes[rot] = (
            [(p, to_board(p.own, origin)) for p in part.pads],
            keep,
            _keepout(part, _other(side), origin),
        )
    reach = (
        radius
        + gap
        + max(abs(v) for _, keep, _ in shapes.values() for v in keep.bounds)
    )
    window = (cx - reach, cy - reach, cx + reach, cy + reach)
    near = [k for k in occupied if _overlap(window, k.bounds)]
    under = [k for k in beneath if _overlap(window, k.bounds)]
    inside = prep(board.outline.buffer(EPS))
    steps = int(radius / step + 1e-9) + 1
    gx, gy = round(cx / step), round(cy / step)
    for i in range(gx - steps, gx + steps + 1):
        for j in range(gy - steps, gy + steps + 1):
            x, y = round(i * step, 4), round(j * step, 4)
            if math.hypot(x - cx, y - cy) > radius + 1e-9:
                continue
            for rot in ROTATIONS:
                pads0, keep0, through0 = shapes[rot]
                over = _collisions(keep0, near, x, y, gap) + _collisions(
                    through0, under, x, y, gap
                )
                over = list(dict.fromkeys(over))
                if over and (reject is None or any(k in reject for k in over)):
                    continue
                if not inside.covers(
                    box(*_shift(keep0.bounds, x, y))
                ) and not inside.covers(affinity.translate(keep0.shape, x, y)):
                    continue
                moved = [(p, affinity.translate(g, x, y)) for p, g in pads0]
                gaps: list[float] = []
                for pin, pin_geom, weight in pin_geoms:
                    on = min(g.distance(pin_geom) for p, g in moved if p.net == pin.net)
                    gaps.append(on / weight)
                faces: bool | None = None
                if len(pin_geoms) == 1:
                    nearest = min(g.distance(pin_geoms[0][1]) for _, g in moved)
                    faces = gaps[0] * pin_geoms[0][2] <= nearest + EPS
                blocked = tuple(
                    lane.pad.label for lane in lanes if all(_closed_by(lane, moved))
                )
                partner_gap = (
                    min(
                        affinity.translate(
                            to_board(mine, Pose(0.0, 0.0, rot, side)), x, y
                        ).distance(theirs)
                        for mine, theirs in partner
                    )
                    if partner
                    else None
                )
                yield Spot(
                    x,
                    y,
                    rot,
                    max(gaps),
                    faces,
                    partner_gap,
                    blocked,
                    tuple(over),
                )


def _collisions(
    keep: Keepout | None, others: Sequence[Keepout], x: float, y: float, gap: float
) -> list[str]:
    """The parts among ``others`` that ``keep``, moved by (x, y), collides
    with: the keep-outs overlap, or the pads are closer than ``gap``, or
    touch when it is 0."""
    if keep is None:
        return []
    bounds = _shift(keep.bounds, x, y)
    reach = gap + EPS
    hits = [
        o
        for o in others
        if min(bounds[2], o.bounds[2]) - max(bounds[0], o.bounds[0]) > -reach
        and min(bounds[3], o.bounds[3]) - max(bounds[1], o.bounds[1]) > -reach
    ]
    if not hits:
        return []
    moved = Keepout(
        keep.key,
        affinity.translate(keep.shape, x, y),
        bounds,
        None if keep.court is None else _shift(keep.court, x, y),
        None if keep.copper is None else affinity.translate(keep.copper, x, y),
    )
    out: list[str] = []
    for o in hits:
        if _clashes(moved, o):
            out.append(o.key)
        elif moved.copper is not None and o.copper is not None:
            apart = moved.copper.distance(o.copper)
            if apart <= EPS or apart < gap - EPS:
                out.append(o.key)
    return out


def _spot_order(spot: Spot) -> tuple[Any, ...]:
    """Closed channels, then the gap, then the partner gap. A spot that
    overlaps a part ranks by its gap like any other, so the nearer spot
    behind a movable part shows."""
    return (
        len(spot.blocked),
        round(spot.gap, 3),
        9.0 if spot.partner is None else round(spot.partner, 3),
        len(spot.overlaps),
        spot.rot,
        spot.x,
        spot.y,
    )


def _default_radius(part: Part) -> float:
    if part.court_own is None:
        return 2.0
    x0, y0, x1, y1 = part.court_own
    return round(2.0 + max(x1 - x0, y1 - y0) / 2, 2)


def _part_side(part: Part, fallback: Part) -> str:
    if part.pose is not None:
        return part.pose.side
    if fallback.pose is not None:
        return fallback.pose.side
    return "top"


def search(
    board: Board,
    part_key: str,
    pin_text: str,
    *,
    partner_key: str | None = None,
    ground: Sequence[str] = ("GND",),
    radius: float | None = None,
    step: float = 0.05,
    side: str | None = None,
    track: float | None = None,
    clear: float | None = None,
    front: float = 2.0,
    conflicts: bool = False,
    movable: Sequence[str] | None = None,
    top: int = 10,
    spread: float = 0.5,
) -> dict[str, Any]:
    part = find_part(board, part_key)
    ic, pin = find_pad(board, pin_text)
    if ic.key == part.key:
        raise UsageError(f"{pin.key} is a pad of {part.key} itself")
    if movable is not None and not conflicts:
        raise UsageError("--movable only narrows --conflicts: give both")
    if top < 1:
        raise UsageError("--top is 1 or more")
    place_side = side or _part_side(part, ic)
    used_radius = radius if radius is not None else _default_radius(part)
    occupied = _keepouts(board, place_side, {part.key})
    beneath = _keepouts(board, _other(place_side), {part.key})
    reject: set[str] | None = None
    if conflicts:
        reject = {ic.key}
        if movable is not None:
            reject |= {k.key for k in [*occupied, *beneath] if k.key not in movable}
    own_nets = {p.net for p in part.pads if p.net is not None}
    lanes = _free_lanes(
        board, [ic], {part.key}, own_nets | set(ground), front, track, clear
    )
    pairs: list[tuple[BaseGeometry, BaseGeometry]] | None = None
    shared: str | None = None
    if partner_key is not None:
        other = find_part(board, partner_key)
        nets = sorted(
            {p.net for p in other.pads if p.net is not None} & own_nets - set(ground)
        )
        if not nets:
            raise UsageError(f"{part.key} and {other.key} share no signal net")
        shared = nets[0]
        pairs = [
            (mine.own, theirs.board)
            for mine in part.pads
            if mine.net == shared
            for theirs in other.pads
            if theirs.net == shared and theirs.board is not None
        ]
        if not pairs:
            raise UsageError(f"{other.key} is unplaced: place it first")
    spots = sorted(
        iter_spots(
            board,
            part,
            place_side,
            [(pin, 1.0)],
            used_radius,
            step,
            occupied,
            reject,
            lanes or [],
            pairs,
            beneath,
            clear,
        ),
        key=_spot_order,
    )
    kept: list[Spot] = []
    for spot in spots:
        if len(kept) >= top:
            break
        if spread > 0 and any(
            k.rot == spot.rot
            and k.overlaps == spot.overlaps
            and math.hypot(k.x - spot.x, k.y - spot.y) < spread
            for k in kept
        ):
            continue
        kept.append(spot)
    legal = [s for s in spots if not s.overlaps]
    current = None
    if part.pose is not None:
        on = [p.board for p in part.pads if p.net == pin.net and p.board is not None]
        if on and pin.board is not None:
            current = round(min(g.distance(pin.board) for g in on), 3)
    return {
        "part": part.key,
        "pin": pin.key,
        "net": pin.net,
        "side": place_side,
        "radius_mm": used_radius,
        "step_mm": step,
        "current_gap_mm": current,
        "legal": len(legal),
        "best_legal_gap_mm": round(legal[0].gap, 3) if legal else None,
        "overlapping": len(spots) - len(legal),
        "conflicts": conflicts,
        "channels_checked": lanes is not None,
        "pad_clearance_mm": clear,
        "partner_net": shared,
        "notes": [
            n
            for n in (
                part.court_note,
                "the part is on the other side from the IC, so it closes none "
                "of the IC's escape channels"
                if lanes is not None
                and ic.pose is not None
                and ic.pose.side != place_side
                else None,
                *_pad_notes(board, [part.key]),
            )
            if n
        ],
        "spots": [s.listed() for s in kept],
    }


def _led_by(lead: int, count: int) -> Iterator[tuple[int, ...]]:
    for rest in itertools.permutations(i for i in range(count) if i != lead):
        yield (lead, *rest)


def _orders(count: int) -> Iterator[tuple[int, ...]]:
    """Every order of ``count`` parts, taking the leading part in turn: the
    first ``count`` orders each start with a different part."""
    streams = [_led_by(lead, count) for lead in range(count)]
    while streams:
        alive: list[Iterator[tuple[int, ...]]] = []
        for stream in streams:
            order = next(stream, None)
            if order is not None:
                yield order
                alive.append(stream)
        streams = alive


def parse_assign(board: Board, text: str) -> tuple[Part, list[tuple[Pad, float]], Part]:
    key, sep, spec = text.partition("=")
    if not sep or not spec:
        raise UsageError(f"--assign {text!r}: write component=pad[@weight][,pad...]")
    part = find_part(board, key)
    pins: list[tuple[Pad, float]] = []
    owner: Part | None = None
    for item in spec.split(","):
        name, _, weight = item.partition("@")
        ic, pad = find_pad(board, name)
        try:
            value = float(weight) if weight else 1.0
        except ValueError:
            raise UsageError(
                f"--assign {text!r}: weight {weight!r} is not a number"
            ) from None
        if value <= 0:
            raise UsageError(f"--assign {text!r}: a weight is above 0")
        pins.append((pad, value))
        owner = owner or ic
    if owner is None or len(pins) > 2:
        raise UsageError(f"--assign {text!r}: one or two pads")
    return part, pins, owner


def group(
    board: Board,
    assigns: Sequence[str],
    *,
    lift: Sequence[str] = (),
    ground: Sequence[str] = ("GND",),
    radius: float | None = None,
    step: float = 0.15,
    max_orders: int | None = None,
    track: float | None = None,
    clear: float | None = None,
    front: float = 2.0,
    top: int = 3,
) -> dict[str, Any]:
    members = [parse_assign(board, a) for a in assigns]
    keys = [m[0].key for m in members]
    if len(set(keys)) != len(keys):
        raise UsageError("--assign names a component twice")
    if top < 1 or (max_orders is not None and max_orders < 1):
        raise UsageError("--top and --max-orders are 1 or more")
    limit = max_orders if max_orders is not None else max(6, len(members))
    lifted = set(keys) | {find_part(board, k).key for k in lift}
    ics = list({m[2].key: m[2] for m in members}.values())
    own_nets = {p.net for m in members for p in m[0].pads if p.net is not None}
    lanes = _free_lanes(board, ics, lifted, own_nets | set(ground), front, track, clear)
    current: dict[str, float | None] = {}
    for part, pins, _ in members:
        gaps: list[float] = []
        for pin, weight in pins:
            on = [
                p.board for p in part.pads if p.net == pin.net and p.board is not None
            ]
            if on and pin.board is not None:
                gaps.append(min(g.distance(pin.board) for g in on) / weight)
        current[part.key] = round(max(gaps), 3) if len(gaps) == len(pins) else None
    results: list[dict[str, Any]] = []
    stuck: dict[str, int] = {}
    tried = 0
    for order in itertools.islice(_orders(len(members)), limit):
        tried += 1
        added: dict[str, list[Keepout]] = {s: [] for s in SIDES}
        placed: list[dict[str, Any]] = []
        open_lanes = list(lanes or [])
        for index in order:
            part, pins, ic = members[index]
            side = _part_side(part, ic)
            occupied = _keepouts(board, side, lifted) + added[side]
            beneath = _keepouts(board, _other(side), lifted) + added[_other(side)]
            best = min(
                iter_spots(
                    board,
                    part,
                    side,
                    pins,
                    radius if radius is not None else _default_radius(part),
                    step,
                    occupied,
                    None,
                    open_lanes,
                    beneath=beneath,
                    clear=clear,
                ),
                key=_spot_order,
                default=None,
            )
            if best is None:
                stuck[part.key] = stuck.get(part.key, 0) + 1
                placed = []
                break
            pose = Pose(best.x, best.y, best.rot, side)
            for seen in SIDES:
                keep = _keepout(part, seen, pose)
                if keep is not None:
                    added[seen].append(keep)
            open_lanes = _lanes_after(open_lanes, side, _pads_at(part, pose))
            placed.append(
                {
                    "part": part.key,
                    "x": best.x,
                    "y": best.y,
                    "rotation": best.rot,
                    "side": side,
                    "weighted_gap_mm": round(best.gap, 3),
                    "blocked": list(best.blocked),
                }
            )
        if not placed:
            continue
        results.append(
            {
                "order": [members[i][0].key for i in order],
                "blocked": sum(len(p["blocked"]) for p in placed),
                "worst_mm": max(p["weighted_gap_mm"] for p in placed),
                "sum_mm": round(sum(p["weighted_gap_mm"] for p in placed), 3),
                "placements": placed,
            }
        )
    results.sort(key=lambda r: (r["blocked"], r["worst_mm"], r["sum_mm"]))
    return {
        "current_weighted_gap_mm": current,
        "orders_tried": tried,
        "no_spot": stuck,
        "channels_checked": lanes is not None,
        "pad_clearance_mm": clear,
        "notes": sorted({m[0].court_note for m in members if m[0].court_note})
        + _pad_notes(board, keys),
        "orders": results[:top],
    }


def _room(
    board: Board,
    court: Box,
    normal: tuple[float, float],
    obstacles: Sequence[Box],
) -> tuple[float, float]:
    """Free depth from one edge of a courtyard to the nearest obstacle or the
    board edge, and that edge's length."""
    x0, y0, x1, y1 = court
    bx0, by0, bx1, by1 = board.outline.bounds
    far = (bx1 - bx0) + (by1 - by0)
    side = _board_side(normal)
    if side == 0:
        strip, edge, length = (x0 - far, y0, x0, y1), ((x0, y0), (x0, y1)), y1 - y0
    elif side == 1:
        strip, edge, length = (x1, y0, x1 + far, y1), ((x1, y0), (x1, y1)), y1 - y0
    elif side == 2:
        strip, edge, length = (x0, y0 - far, x1, y0), ((x0, y0), (x1, y0)), x1 - x0
    else:
        strip, edge, length = (x0, y1, x1, y1 + far), ((x0, y1), (x1, y1)), x1 - x0
    line = LineString(edge)
    depth = far
    outside = box(*strip).difference(board.outline)
    if not outside.is_empty:
        depth = min(depth, line.distance(outside))
    for other in obstacles:
        if _overlap(strip, other):
            depth = min(depth, line.distance(box(*other)))
    return depth, length


def sides(
    board: Board,
    key: str,
    *,
    at: Sequence[float] | None = None,
    toward: Sequence[str] | None = None,
    ground: Sequence[str] = ("GND",),
    small: int = 4,
) -> dict[str, Any]:
    part = find_part(board, key)
    own_sides = pin_sides(part)
    result: dict[str, Any] = {
        "component": part.key,
        "mpn": part.mpn,
        "placement": part.pose.listed() if part.pose else None,
        "pads": len(part.pads),
        "notes": [n for n in (part.court_note,) if n],
    }
    shown = part.pose or Pose(0.0, 0.0, 0.0, "top")
    by_side: dict[str, list[dict[str, Any]]] = {name: [] for name in SIDE_NAMES}
    middle: list[Pad] = []
    for pad in part.pads:
        side = own_sides.get(pad.key)
        if side is None:
            middle.append(pad)
            continue
        centre = to_board(pad.own, shown).centroid
        name = SIDE_NAMES[_board_side(turn(NORMALS[side], shown))]
        by_side[name].append(
            {
                "pad": pad.label,
                "net": pad.net,
                "pos": [round(centre.x, 3), round(centre.y, 3)],
            }
        )
    for name, rows in by_side.items():
        along = 1 if "x)" in name else 0
        rows.sort(key=lambda r, a=along: r["pos"][a])
    result["sides"] = by_side
    result["middle"] = {
        "pads": len(middle),
        "nets": sorted({str(p.net) for p in middle}),
    }
    if not part.pose:
        result["frame"] = "the component's own frame: it is unplaced"
    if at is None and part.pose is None:
        result["rotations"] = None
        result["notes"].append("unplaced: give --at X Y to compare rotations there")
        return result
    assert at is not None or part.pose is not None
    origin = (at[0], at[1]) if at is not None else (shown.x, shown.y)
    board_side = shown.side
    if toward is not None:
        anchors = {find_part(board, k).key for k in toward}
    else:
        anchors = {
            p.key
            for p in board.parts.values()
            if p.pose is not None and not is_small(p, small) and p.key != part.key
        }
    targets: dict[str, list[BaseGeometry]] = {}
    for anchor in sorted(anchors):
        if anchor == part.key:
            continue
        for pad in board.parts[anchor].pads:
            if pad.net is not None and pad.net not in ground and pad.board is not None:
                targets.setdefault(pad.net, []).append(pad.board)
    obstacles = [b for k, b in _occupied(board, board_side, {part.key}) if k in anchors]
    need: dict[int, dict[str, Any]] = {}
    for side in range(4):
        nets = {
            p.net
            for p in part.pads
            if own_sides.get(p.key) == side
            and p.net is not None
            and p.net not in ground
        }
        users = [
            o
            for o in board.parts.values()
            if o.key != part.key
            and is_small(o, small)
            and _serves(part, o)
            and any(p.net in nets for p in o.pads)
        ]
        need[side] = {
            "parts": len(users),
            "need_mm2": round(sum(o.court_area for o in users), 2),
        }
    rows: list[dict[str, Any]] = []
    for rot in ROTATIONS:
        pose = Pose(origin[0], origin[1], rot, board_side)
        facing = connected = 0
        length = 0.0
        away: list[str] = []
        for pad in part.pads:
            side = own_sides.get(pad.key)
            if side is None or pad.net is None or pad.net not in targets:
                continue
            geom = to_board(pad.own, pose)
            target = min(targets[pad.net], key=geom.distance)
            normal = turn(NORMALS[side], pose)
            dx = target.centroid.x - geom.centroid.x
            dy = target.centroid.y - geom.centroid.y
            connected += 1
            length += geom.distance(target)
            if dx * normal[0] + dy * normal[1] > EPS:
                facing += 1
            else:
                away.append(pad.label)
        room: dict[str, Any] = {}
        if part.court_own is not None:
            court = _court_at(part, pose)
            for side in range(4):
                normal = turn(NORMALS[side], pose)
                depth, edge = _room(board, court, normal, obstacles)
                room[SIDE_NAMES[_board_side(normal)]] = {
                    "package_side": SIDE_NAMES[side],
                    **need[side],
                    "depth_mm": round(depth, 2),
                    "room_mm2": round(depth * edge, 2),
                }
        rows.append(
            {
                "rotation": rot,
                "current": part.pose is not None
                and at is None
                and abs(part.pose.rot - rot) < 1e-6,
                "facing": facing,
                "connected": connected,
                "length_mm": round(length, 2),
                "away": away,
                "room": room,
            }
        )
    result["rotations"] = rows
    result["toward"] = sorted(anchors)
    return result


def _block(key: str) -> str:
    return key.split(".", 1)[0]


def _serves(ic: Part, part: Part) -> bool:
    """Whether a small part counts as one of an IC's own: in the IC's block,
    or either of them at the top level of the design."""
    return (
        "." not in ic.key or "." not in part.key or _block(ic.key) == _block(part.key)
    )


def overlaps(board: Board) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The placed parts that collide: pairs on one side whose courtyard boxes
    overlap, then the other pairs whose keep-outs overlap on either side of
    the board, each with the two keys, the overlap in mm2 (the larger of
    the two sides for a pad overlap), and ``approximate``: whether either
    part is turned off a quarter turn, so its box is larger than it."""
    seen = {side: {k.key: k for k in _keepouts(board, side, set())} for side in SIDES}
    courts: list[dict[str, Any]] = []
    padded: dict[tuple[str, str], float] = {}
    for keeps in seen.values():
        ordered = sorted(keeps.values(), key=lambda k: k.key)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                if not _clashes(a, b):
                    continue
                if (
                    a.court is not None
                    and b.court is not None
                    and _overlap(a.court, b.court)
                ):
                    x0, y0 = max(a.court[0], b.court[0]), max(a.court[1], b.court[1])
                    x1, y1 = min(a.court[2], b.court[2]), min(a.court[3], b.court[3])
                    courts.append(
                        {
                            "components": [a.key, b.key],
                            "area_mm2": round((x1 - x0) * (y1 - y0), 3),
                            "approximate": _turned(board, a.key, b.key),
                        }
                    )
                    continue
                area = a.shape.intersection(b.shape).area
                pair = (a.key, b.key)
                padded[pair] = max(padded.get(pair, 0.0), area)
    in_courts = {tuple(c["components"]) for c in courts}
    pads = [
        {
            "components": list(pair),
            "area_mm2": round(area, 3),
            "approximate": _turned(board, *pair),
        }
        for pair, area in sorted(padded.items())
        if pair not in in_courts
    ]
    return sorted(courts, key=lambda c: c["components"]), pads


def _turned(board: Board, *keys: str) -> bool:
    """Whether any of the parts is placed off a quarter turn: its courtyard
    on the board is then the box around the turned part."""
    return any(
        (pose := board.parts[k].pose) is not None and not _quarter(pose.rot)
        for k in keys
    )


def _overlap_notes(board: Board, rows: Sequence[dict[str, Any]]) -> list[str]:
    """For ``audit``'s overlap lists: each listed part whose box is larger
    than it, and where the real shapes are compared."""
    if not rows:
        return []
    notes: list[str] = []
    for k in sorted({k for r in rows for k in r["components"]}):
        pose = board.parts[k].pose
        if pose is not None and not _quarter(pose.rot):
            notes.append(
                f"{k} is turned {pose.rot:g} degrees: its courtyard is the box "
                "around the turned part, larger than the part"
            )
    notes.append(
        "courtyard_overlaps and pad_overlaps compare courtyards as the boxes "
        "the state gives; layout_report.py's summary and layout_checks.py's "
        "sanity compare the real shapes"
    )
    return notes


def audit(
    board: Board,
    *,
    ics: Sequence[str] | None = None,
    ground: Sequence[str] = ("GND",),
    small: int = 4,
    track: float | None = None,
    clear: float | None = None,
    front: float = 2.0,
) -> dict[str, Any]:
    if ics:
        chosen = [find_part(board, k) for k in ics]
    else:
        chosen = [
            p
            for p in board.parts.values()
            if p.pose is not None and not is_small(p, small)
        ]
    every_small = [p for p in board.parts.values() if is_small(p, small)]
    report: dict[str, Any] = {"ics": {}}
    for ic in sorted(chosen, key=lambda p: p.key):
        if ic.pose is None:
            raise UsageError(f"{ic.key} is unplaced")
        smalls = [p for p in every_small if _serves(ic, p)]
        ic_pins = [
            p
            for p in ic.pads
            if p.net is not None and p.net not in ground and p.board is not None
        ]
        nets = {p.net for p in ic_pins}
        pins: list[dict[str, Any]] = []
        for pin in ic_pins:
            assert pin.board is not None
            reach = [
                (part, pad)
                for part in smalls
                if part.key != ic.key
                for pad in part.pads
                if pad.net == pin.net
            ]
            if not reach:
                continue
            placed = [(part, pad) for part, pad in reach if pad.board is not None]
            if not placed:
                pins.append(
                    {
                        "pin": pin.label,
                        "net": pin.net,
                        "gap_mm": None,
                        "part": None,
                        "turned": False,
                        "unplaced": sorted({part.key for part, _ in reach}),
                    }
                )
                continue
            pin_geom = pin.board
            part, pad = min(
                placed,
                key=lambda pp: pp[1].board.distance(pin_geom) if pp[1].board else 0.0,
            )
            assert pad.board is not None
            gap = pad.board.distance(pin_geom)
            turned = any(
                o.board is not None
                and o.net not in nets
                and o.board.distance(pin_geom) < gap - EPS
                for o in part.pads
            )
            pins.append(
                {
                    "pin": pin.label,
                    "net": pin.net,
                    "gap_mm": round(gap, 3),
                    "part": part.key,
                    "turned": turned,
                }
            )
        pins.sort(key=lambda r: (r["gap_mm"] is not None, -(r["gap_mm"] or 0.0)))
        parts: list[dict[str, Any]] = []
        pairs: list[dict[str, Any]] = []
        for part in smalls:
            if part.key == ic.key or part.pose is None:
                continue
            gaps: list[tuple[str, float]] = []
            for pad in part.pads:
                if pad.net not in nets or pad.board is None:
                    continue
                gap = min(
                    pad.board.distance(p.board)
                    for p in ic_pins
                    if p.net == pad.net and p.board is not None
                )
                gaps.append((pad.label, gap))
                parts.append(
                    {
                        "part": part.key,
                        "pad": pad.label,
                        "net": pad.net,
                        "gap_mm": round(gap, 3),
                    }
                )
            signal = [p for p in part.pads if p.net is not None and p.net not in ground]
            if len(signal) == 2 and len(gaps) == 2 and signal[0].net != signal[1].net:
                pairs.append(
                    {
                        "part": part.key,
                        "gaps_mm": [round(g, 3) for _, g in gaps],
                        "difference_mm": round(abs(gaps[0][1] - gaps[1][1]), 3),
                    }
                )
        parts.sort(key=lambda r: -r["gap_mm"])
        entry: dict[str, Any] = {"pins": pins, "parts": parts, "pairs": pairs}
        if track is not None and clear is not None:
            served = {p.net for part in smalls for p in part.pads if p.net is not None}
            entry["blocked"] = [
                {"pin": pad.label, "net": pad.net, "by": closing}
                for pad, free, closing in escape_lanes(
                    board, ic, set(), served | set(ground), front, track + 2 * clear
                )
                if not free
            ]
        report["ics"][ic.key] = entry
    board_area = board.outline.area
    use: dict[str, Any] = {}
    blocks: dict[tuple[str, str], list[Part]] = {}
    for part in board.parts.values():
        if part.pose is None or part.court_board is None:
            continue
        x0, y0, x1, y1 = part.court_board
        tally = use.setdefault(part.pose.side, {"parts": 0, "courtyards_mm2": 0.0})
        tally["parts"] += 1
        tally["courtyards_mm2"] += (x1 - x0) * (y1 - y0)
        blocks.setdefault((_block(part.key), part.pose.side), []).append(part)
    for tally in use.values():
        tally["courtyards_mm2"] = round(tally["courtyards_mm2"], 1)
        tally["percent_of_board"] = round(100 * tally["courtyards_mm2"] / board_area, 1)
    packing: list[dict[str, Any]] = []
    for (name, side), members in sorted(blocks.items()):
        if len(members) < 2:
            continue
        courts = [m.court_board for m in members if m.court_board is not None]
        total = sum((c[2] - c[0]) * (c[3] - c[1]) for c in courts)
        span = (max(c[2] for c in courts) - min(c[0] for c in courts)) * (
            max(c[3] for c in courts) - min(c[1] for c in courts)
        )
        packing.append(
            {
                "block": name,
                "side": side,
                "parts": len(members),
                "courtyards_mm2": round(total, 1),
                "box_mm2": round(span, 1),
                "ratio": round(span / total, 2) if total else None,
            }
        )
    packing.sort(key=lambda r: -(r["ratio"] or 0.0))
    court_overlaps, pad_overlaps = overlaps(board)
    report["board"] = {
        "area_mm2": round(board_area, 1),
        "unplaced": sorted(p.key for p in board.parts.values() if p.pose is None),
        "sides": use,
        "blocks": packing,
        "courtyard_overlaps": court_overlaps,
        "pad_overlaps": pad_overlaps,
    }
    report["channels_checked"] = track is not None and clear is not None
    report["notes"] = _overlap_notes(board, court_overlaps + pad_overlaps) + _pad_notes(
        board
    )
    return report


def _fmt(value: float | None, width: int = 7) -> str:
    return f"{'-':>{width}}" if value is None else f"{value:{width}.3f}"


def show_sides(r: dict[str, Any]) -> None:
    where = r["placement"] if r["placement"] else "unplaced"
    print(f"{r['component']} ({r['mpn']}) {where}, {r['pads']} pads")
    if "frame" in r:
        print(f"  positions are in {r['frame']}")
    for name, rows in r["sides"].items():
        print(f"{name}: {len(rows)} pads")
        for row in rows:
            print(
                f"   {row['pad']:10} {row['net']!s:18} "
                f"({row['pos'][0]:.3f}, {row['pos'][1]:.3f})"
            )
    print(f"middle: {r['middle']['pads']} pads, nets {r['middle']['nets']}")
    if r["rotations"]:
        print(f"rotations, facing {', '.join(r['toward']) or 'nothing'} (* is current)")
        print("   rot   facing  length_mm  pins facing away")
        for row in r["rotations"]:
            mark = "*" if row["current"] else " "
            print(
                f"  {row['rotation']:4.0f}{mark}  {row['facing']:3d}/{row['connected']:<3d}"
                f"  {row['length_mm']:9.2f}  {' '.join(row['away'])}"
            )
        print(
            "room on each side: small parts its nets need, against free depth x length"
        )
        for row in r["rotations"]:
            mark = "*" if row["current"] else " "
            for name, room in row["room"].items():
                print(
                    f"  {row['rotation']:4.0f}{mark} {name:11} {room['parts']:3d} parts "
                    f"need {room['need_mm2']:7.2f} mm2, room {room['depth_mm']:6.2f} mm "
                    f"deep = {room['room_mm2']:8.2f} mm2"
                )
    for note in r["notes"]:
        print(f"note: {note}")


def show_audit(r: dict[str, Any]) -> None:
    for key, ic in r["ics"].items():
        print(f"== {key}")
        print("pins (gap to the nearest small part on the net, worst first)")
        for row in ic["pins"]:
            if row["gap_mm"] is None:
                print(
                    f"  {row['pin']:10} {row['net']!s:16} unplaced: "
                    f"{', '.join(row['unplaced'])}"
                )
                continue
            turned = (
                "  TURNED: another pad of the part is nearer" if row["turned"] else ""
            )
            print(
                f"  {row['pin']:10} {row['net']!s:16} {row['gap_mm']:7.3f} mm  "
                f"{row['part']}{turned}"
            )
        print("parts (each small-part pad to the nearest pin on its net, worst first)")
        for row in ic["parts"]:
            print(
                f"  {row['part']:28} {row['pad']:8} {row['net']!s:16} "
                f"{row['gap_mm']:7.3f} mm"
            )
        if ic["pairs"]:
            print("pairs (both signal pads on IC pins)")
            for row in ic["pairs"]:
                a, b = row["gaps_mm"]
                print(
                    f"  {row['part']:28} {a:.3f} mm, {b:.3f} mm, "
                    f"difference {row['difference_mm']:.3f} mm"
                )
        if "blocked" in ic:
            print("blocked (signal pins no small part serves, with no free channel)")
            for row in ic["blocked"]:
                print(f"  {row['pin']:10} {row['net']!s:16} by {', '.join(row['by'])}")
    b = r["board"]
    print(f"== board, {b['area_mm2']} mm2")
    for side, tally in b["sides"].items():
        print(
            f"  {side}: {tally['parts']} parts, courtyards {tally['courtyards_mm2']} mm2, "
            f"{tally['percent_of_board']}% of the board"
        )
    if b["unplaced"]:
        print(f"  unplaced: {', '.join(b['unplaced'])}")
    for name, rows in (
        ("courtyard overlaps", b["courtyard_overlaps"]),
        (
            "pad overlaps (keep-outs with pads collide, courtyards clear)",
            b["pad_overlaps"],
        ),
    ):
        print(f"{name}: {len(rows)}")
        for row in rows:
            a, c = row["components"]
            rough = "  approximate: a turned part's box" if row["approximate"] else ""
            print(f"  {a} / {c}  {row['area_mm2']:.3f} mm2{rough}")
    print("blocks (box around the block's courtyards over their sum, loosest first)")
    for row in b["blocks"]:
        print(
            f"  {row['block']:18} {row['side']:6} {row['parts']:3d} parts  "
            f"courtyards {row['courtyards_mm2']:8.1f}  box {row['box_mm2']:8.1f}  "
            f"ratio {row['ratio']}"
        )
    if not r["channels_checked"]:
        print("note: escape channels not checked (give --track and --clear)")
    for note in r["notes"]:
        print(f"note: {note}")


def _clearance_note(r: dict[str, Any]) -> None:
    if r["pad_clearance_mm"] is None:
        print(
            "note: pad clearance not checked beyond touching "
            "(give --clear for the copper-to-copper clearance)"
        )


def show_search(r: dict[str, Any]) -> None:
    print(
        f"{r['legal']} legal spots for {r['part']} at {r['pin']} ({r['net']}), "
        f"{r['side']} side, within {r['radius_mm']} mm, step {r['step_mm']} mm; "
        f"current gap {_fmt(r['current_gap_mm']).strip()} mm, "
        f"best legal gap {_fmt(r['best_legal_gap_mm']).strip()} mm"
    )
    if r["overlapping"]:
        print(
            f"{r['overlapping']} more spots overlap other parts; "
            "each row names what it overlaps"
        )
    print("  blocks  gap_mm  partner_mm        x        y   rot  faces  overlaps")
    for s in r["spots"]:
        print(
            f"  {len(s['blocked']):6d} {_fmt(s['gap_mm'])}  {_fmt(s['partner_mm'], 10)} "
            f"{s['x']:8.3f} {s['y']:8.3f}  {s['rotation']:4.0f}  {s['faces']!s:5}  "
            f"{' '.join(s['overlaps'])}{'  closes ' + ' '.join(s['blocked']) if s['blocked'] else ''}"
        )
    if not r["legal"]:
        if r["overlapping"]:
            print("no legal spot: widen --radius, or move a part a row names")
        elif r["conflicts"]:
            print("no legal spot: widen --radius")
        else:
            print(
                "no legal spot: widen --radius, or list what is in the way "
                "with --conflicts"
            )
    if not r["channels_checked"]:
        print("note: escape channels not checked (give --track and --clear)")
    _clearance_note(r)
    for note in r["notes"]:
        print(f"note: {note}")


def show_group(r: dict[str, Any]) -> None:
    now = ", ".join(
        f"{k} {_fmt(v).strip()}" for k, v in r["current_weighted_gap_mm"].items()
    )
    print(f"current weighted gaps (mm): {now}")
    for order in r["orders"]:
        print(
            f"order {' > '.join(order['order'])}: worst weighted gap "
            f"{order['worst_mm']:.3f} mm, sum {order['sum_mm']:.3f} mm, "
            f"blocked channels {order['blocked']}"
        )
        for p in order["placements"]:
            print(
                f"   {p['part']:28} ({p['x']:.3f}, {p['y']:.3f}) rot {p['rotation']:.0f} "
                f"{p['side']}  weighted gap {p['weighted_gap_mm']:.3f} mm"
            )
    if not r["orders"]:
        print(
            f"no order of {r['orders_tried']} tried fits (no spot for "
            f"{', '.join(r['no_spot'])}): widen --radius or --lift more"
        )
    if not r["channels_checked"]:
        print("note: escape channels not checked (give --track and --clear)")
    _clearance_note(r)
    for note in r["notes"]:
        print(f"note: {note}")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Choose a placement from the layout state layout_report.py wrote."
    )
    ap.add_argument("--state", type=Path, default=STATE)
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    sub = ap.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, channels: bool) -> None:
        # The same two options after the command; SUPPRESS keeps a value
        # given before the command.
        p.add_argument("--state", type=Path, default=argparse.SUPPRESS)
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        p.add_argument(
            "--ground",
            nargs="*",
            action="extend",
            default=None,
            help="ground nets (default GND), given once or more; no names for "
            "a board with none",
        )
        if channels:
            p.add_argument("--track", type=float, help="trace width, mm")
            p.add_argument(
                "--clear",
                type=float,
                help="clearance, mm: for escape channels with --track, and "
                "in search and group between pad copper of different parts",
            )
            p.add_argument("--front", type=float, default=2.0, help="channel length")

    p = sub.add_parser("sides", help="pads by package side, and the four rotations")
    p.add_argument("component")
    p.add_argument("--at", nargs=2, type=float, metavar=("X", "Y"))
    p.add_argument("--toward", nargs="+", help="parts to face (default: larger parts)")
    p.add_argument("--small", type=int, default=4, help="most pads a small part has")
    common(p, False)

    p = sub.add_parser("audit", help="gaps from IC pins to the parts that serve them")
    p.add_argument("--ic", nargs="+")
    p.add_argument("--small", type=int, default=4, help="most pads a small part has")
    common(p, True)

    p = sub.add_parser("search", help="legal spots for one part near a pin")
    p.add_argument("--part", required=True)
    p.add_argument("--pin", required=True)
    p.add_argument("--partner")
    p.add_argument("--radius", type=float)
    p.add_argument("--step", type=float, default=0.05)
    p.add_argument("--side", choices=["top", "bottom"])
    p.add_argument("--conflicts", action="store_true")
    p.add_argument("--movable", nargs="*")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--spread", type=float, default=0.5)
    common(p, True)

    p = sub.add_parser("group", help="place several parts that compete for pins")
    p.add_argument("--assign", nargs="+", required=True)
    p.add_argument("--lift", nargs="*", default=[])
    p.add_argument("--radius", type=float)
    p.add_argument("--step", type=float, default=0.15)
    p.add_argument("--max-orders", type=int)
    p.add_argument("--top", type=int, default=3)
    common(p, True)
    return ap


def check_ground(board: Board, ground: Sequence[str]) -> None:
    """Refuse a ground name no pad carries: with a ground net counted as a
    signal, every gap and facing count below would be measured to it."""
    if not ground:
        return
    count: dict[str, int] = {}
    for part in board.parts.values():
        for pad in part.pads:
            if pad.net is not None:
                count[pad.net] = count.get(pad.net, 0) + 1
    missing = [name for name in ground if name not in count]
    if not missing:
        return
    most = sorted(count, key=lambda net: (-count[net], net))[:5]
    raise UsageError(
        f"no pad is on {' or '.join(missing)}: name the ground nets with --ground "
        f"(the nets with the most pads: {', '.join(f'{n} {count[n]}' for n in most)}), "
        "or give --ground with no names for a board with none"
    )


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    board = load(args.state)
    ground: list[str] = ["GND"] if args.ground is None else args.ground
    check_ground(board, ground)
    clear: float | None = getattr(args, "clear", None)
    if clear is not None and clear < 0:
        raise UsageError("--clear is 0 or more")
    if args.command == "sides":
        return (
            sides(
                board,
                args.component,
                at=args.at,
                toward=args.toward,
                ground=ground,
                small=args.small,
            ),
            0,
        )
    if args.command == "audit":
        return (
            audit(
                board,
                ics=args.ic,
                ground=ground,
                small=args.small,
                track=args.track,
                clear=args.clear,
                front=args.front,
            ),
            0,
        )
    if args.command == "search":
        found = search(
            board,
            args.part,
            args.pin,
            partner_key=args.partner,
            ground=ground,
            radius=args.radius,
            step=args.step,
            side=args.side,
            track=args.track,
            clear=args.clear,
            front=args.front,
            conflicts=args.conflicts,
            movable=args.movable,
            top=args.top,
            spread=args.spread,
        )
        return found, 0 if found["legal"] else 1
    placed = group(
        board,
        args.assign,
        lift=args.lift,
        ground=ground,
        radius=args.radius,
        step=args.step,
        max_orders=args.max_orders,
        track=args.track,
        clear=args.clear,
        front=args.front,
        top=args.top,
    )
    return placed, 0 if placed["orders"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result, code = run(args)
    except UsageError as error:
        print(f"layout_placement: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=1))
        return code
    age = time.time() - args.state.stat().st_mtime
    print(f"state: {args.state}, written {age / 60:.0f} min ago")
    {
        "sides": show_sides,
        "audit": show_audit,
        "search": show_search,
        "group": show_group,
    }[args.command](result)
    return code


if __name__ == "__main__":
    sys.exit(main())
