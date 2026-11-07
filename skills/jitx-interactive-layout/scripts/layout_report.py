"""Report the interactive layout of a design held by `jitx design session`.

Run against a running session, from the project root:

    jitx design exec <module.path.DesignClass> <this file>                 # layout state
    jitx design exec <module.path.DesignClass> <this file> -f issues      # open issues
    jitx design exec <module.path.DesignClass> <this file> -f issues_all  # with passing checks

Each writes a JSON file under ``.jitx/interactive-layout/`` in the directory
the session was started in, and returns a short summary that ``exec`` prints.

``main`` writes ``state.json``, in board-absolute millimetres:

* ``board``: outline points; ``conductors``: copper layer count.
* ``via_definitions``: name, layers, diameter, hole, via-in-pad.
* ``components``: key, part number, placement ``[x, y, rotation, side]`` or
  null, courtyard bounds on the board (null when unplaced), and
  ``courtyard_size`` (width and height in the part's own frame, also for
  unplaced parts, for planning around a footprint).
* ``pads``: key, ``placed`` (false when the pad's component is unplaced: its
  position and outline are then in the component's own frame, not on the
  board), position, net name (null if unconnected), outline points.
* ``routes``: key, layer, net, status, endpoint kinds and endpoint keys
  (``source_key``, ``destination_key``: the pad, via or control point the
  route ends at; null when the endpoint is none of these).
* ``vias``: key, ``placed`` (false when a component in the via's circuit is
  unplaced: its position may then be in its owning component's own frame, or
  the circuit's for a via the circuit owns), position, definition, net.
* ``control_points``, with ``placed`` as for vias, and ``pours`` with rank
  and ``fill_pieces``, the number of pieces the fill came out in: 0 when the
  pour has no copper (listed under ``empty_pours``), null when the fill has
  not come back yet (listed under ``fill_unknown``; sync and run again). Which pads and vias a piece joins is not
  reported: read the pour's ``shape`` polygons with ``rd.query(Pour)``.

Its summary lists components whose part number starts with ``IDEAL-`` (a
placeholder the parts chain synthesized because no real part matched; its
footprint is a guess), unplaced components, overlapping courtyards on the same
side, courtyards not inside the board (a connector meant to overhang the
edge appears here too), blocked routes, and pours whose fill is in more than
one piece, has no copper, or has not come back yet.

Changes since the last report
-----------------------------
Before writing ``state.json``, ``main`` moves the previous one to
``state-prev.json`` and compares the two in the summary's ``changed``: what
moved in the board editor, or by any request, between two reports. ``changed``
is null when there is no previous report (or it is of another design), and
``{}`` when nothing changed. Otherwise it holds only the kinds that changed,
each with nonzero ``counts`` and lists cut at ``LIST_LIMIT``:

* ``components``: counts of ``moved``, ``rotated``, ``flipped``, ``placed``
  and ``unplaced``; ``list`` gives each changed component's key, ``change``
  (one or more of those words) and its ``old`` and ``new`` placement.
* ``routes``: ``added`` and ``removed``, each with key, net and layer (the
  new key for an added route, the old key for a removed one).
* ``vias`` and ``control_points``: ``added``, ``removed`` and ``moved``
  (``old`` and ``new`` position; for a control point, position and
  rotation). ``placed_with_component`` counts vias or control points that had
  no board position because a component in their circuit was unplaced, and
  have one now; ``unplaced_with_component`` the reverse. Neither is listed.
* ``pours``: ``added`` and ``removed``, with key, net and layer.

Component keys and the keys of objects placed in code are tree paths from
the source and stay the same between reports. Keys under the link containers
(below) are list positions: two reports with no edit between them give the
same keys, but deleting one object renumbers the ones after it, and placing
a component re-reports the vias of its circuit under new keys. So those
objects are matched by what they are, not by key:

* a route by net, layer and its two ends, where an end is the pad's key, or
  the end's type for a via or control point. A route whose via moved stays
  the same route.
* a via by position, net, definition and ``placed``, then, among those left,
  by key with the same net and definition (a move);
* a control point by position, rotation, type, layer and ``placed``, then by
  key with the same type and layer;
* a pour by layer, rank and net. A change to a pour's outline is not
  reported.

A via or control point moved in the same edit that renumbered it (a delete
earlier in its list) can be paired with another of the same net and
definition, or read as removed and added. Across a session restart, a route
attached to a component on the bottom side has read a different layer number
(counted from the top before, from the bottom side's own layer after) and so
shows as removed and added.

``issues`` and ``issues_all`` write ``issues.json``: each issue's type,
severity, category, text, the objects it references (by key where the
object is in the tree), the runtime's ``cause`` where the issue has one, and
for timing issues the constrained ``paths`` when the runtime names them (the
issue text always names the path ends). Signal-integrity issues add the measured and
acceptable ranges and ``margin``, the distance from the measured range to
the nearest acceptable bound, negative when out of bounds; timing in
picoseconds, loss in dB. ``issues_all`` includes checks that pass, so a skew
constraint that holds shows the room it has left. The summary groups the
first few errors of each type, and says whether
every category was complete when the report was taken; a pending category
means background work was still running, so run it again.

Keys are dotted tree paths with the prefix every component shares removed
(``circuit.reg.u1`` becomes ``reg.u1``). They are for reading: pass objects
from ``rd.root`` to requests. Objects whose key passes through a link
container (``_Capture__link`` or ``_Links__session``) were made by the
runtime, by a request or in the board editor, and are marked
``"interactive": true``; requests can modify or delete only those. These
container names are internals of the jitx package, used here only to tell
the two kinds apart.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Hashable
from pathlib import Path
from typing import Any

from jitx.circuit import Route
from jitx.component import Component
from jitx.controlpoint import ControlPoint
from jitx.copper import Pour
from jitx.feature import Courtyard
from jitx.inspect import Trace
from jitx.issue import (
    CategoryStatus,
    DesignIssue,
    IssueCategory,
    Severity,
    SignalIntegrityIssue,
    TimingIssue,
    UnmetTime,
    UnmetTimeDiff,
)
from jitx.landpattern import Pad, PadShape
from jitx.layerindex import Side
from jitx.net import Port
from jitx.proxy import typeof
from jitx.shapes import Shape
from jitx.shapes.primitive import Empty, PolygonSet
from jitx.via import Via
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

OUT_DIR = Path(".jitx") / "interactive-layout"
STATE = "state.json"
PREVIOUS_STATE = "state-prev.json"
LIST_LIMIT = 20
# Placements closer than these are the same placement.
SAME_MM = 1e-3
SAME_DEG = 1e-2
ERRORS_PER_TYPE = 5
IDEAL_PREFIX = "IDEAL-"
ISSUE_WAIT_SECONDS = 15.0
PS_PER_S = 1e12
_LINK_MARKERS = ("__link", "__session")
# Attributes through which a route attaches to a control point: RoutePoint.pad,
# PairInsertion.coupled and .uncoupled, PairPoint.front and .back. Coupled
# endpoints carry .p and .n as well.
_CONTROL_ENDS = ("pad", "coupled", "uncoupled", "front", "back")


class _Keys:
    """Dotted keys for tree objects, with the common component prefix cut
    from paths that start with it."""

    def __init__(self, rd: Any) -> None:
        paths = [[str(p) for p in t.path] for t, _ in rd.query(Component)]
        self.prefix: list[str] = []
        if paths:
            shortest = min(len(p) for p in paths)
            while (
                len(self.prefix) < shortest - 1
                and len({p[len(self.prefix)] for p in paths}) == 1
            ):
                self.prefix.append(paths[0][len(self.prefix)])

    def __call__(self, trace: Trace) -> str:
        path = [str(p) for p in trace.path]
        cut = len(self.prefix)
        return ".".join(path[cut:] if path[:cut] == self.prefix else path)

    def known(self, rd: Any) -> dict[int, str]:
        """Keys of the tree objects issues and routes refer to, by identity."""
        found: dict[int, str] = {}
        for kind in (Port, Pad, Route, Via, ControlPoint, Component, Pour):
            for trace, obj in rd.query(kind):
                found.setdefault(id(obj), self(trace))
        # A route ending at a control point ends at one of its endpoint
        # objects; report it under the control point's key.
        for trace, cp in rd.query(ControlPoint):
            for name in _CONTROL_ENDS:
                end = getattr(cp, name, None)
                if end is None:
                    continue
                found.setdefault(id(end), self(trace))
                for half in ("p", "n"):
                    sub = getattr(end, half, None)
                    if sub is not None:
                        found.setdefault(id(sub), self(trace))
        return found


def _pieces(shape: object) -> int | None:
    """How many separate pieces a pour's fill came out in: 0 when the pour has
    no copper, None when the fill has not come back yet. The fill comes back as
    a ``PolygonSet``, bare or wrapped in a transformed ``Shape``, or ``Empty``;
    before it comes back the pour holds the requested outline, a plain
    polygon, which is not a fill."""
    geom = shape.geometry if isinstance(shape, Shape) else shape
    if isinstance(geom, PolygonSet):
        return len(geom.polygons)
    if isinstance(geom, Empty):
        return 0
    return None


def _owner(key: str, components: list[str]) -> str:
    """The longest prefix of ``key`` that holds a component: the circuit the
    object belongs to, or "" at the top."""
    parts = key.split(".")
    for n in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:n]) + "."
        if any(c.startswith(prefix) for c in components):
            return prefix
    return ""


def _interactive(key: str) -> bool:
    return any(m in step for step in key.split(".") for m in _LINK_MARKERS)


def _xy(point: Any) -> list[float]:
    return [round(float(v), 4) for v in point]


def _outline(geom: BaseGeometry) -> list[list[float]] | None:
    if geom.is_empty:
        return None
    poly = geom if isinstance(geom, ShapelyPolygon) else geom.convex_hull
    return (
        [_xy(p) for p in poly.exterior.coords]
        if isinstance(poly, ShapelyPolygon)
        else None
    )


def _write(name: str, payload: dict[str, Any]) -> str:
    out = Path.cwd() / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text(json.dumps(payload, indent=1))
    return str(path)


def _placement(trace: Trace, comp: Any) -> list[Any] | None:
    """A component's board placement ``[x, y, rotation, side]``: the
    board-absolute transform ``trace.transform * comp.transform``, rotation in
    degrees counter-clockwise in [0, 360), side "top" or "bottom". None when
    the component is unplaced. These are the values ``rd.layout.place``
    takes."""
    if comp.transform is None or trace.transform is None:
        return None
    xf = trace.transform * comp.transform
    side = "bottom" if getattr(xf, "side", Side.Top) == Side.Bottom else "top"
    return [*_xy(xf.translation), round(xf.rotation % 360, 3), side]


def _same_angle(a: float, b: float) -> bool:
    turn = abs(a - b) % 360
    return min(turn, 360 - turn) <= SAME_DEG


def _same_xy(a: list[float], b: list[float]) -> bool:
    return all(abs(p - q) <= SAME_MM for p, q in zip(a, b, strict=True))


def _same_placement(a: list[Any] | None, b: list[Any] | None) -> bool:
    """Whether two placements from ``_placement`` agree; None is unplaced."""
    if a is None or b is None:
        return a is b
    return _same_xy(a[:2], b[:2]) and _same_angle(a[2], b[2]) and a[3] == b[3]


def _trim(section: dict[str, Any]) -> dict[str, Any]:
    """Drop zero counts and empty lists, and cut lists at LIST_LIMIT."""
    out: dict[str, Any] = {}
    for name, value in section.items():
        if name == "counts":
            value = {k: n for k, n in value.items() if n}
        elif isinstance(value, list):
            value = value[:LIST_LIMIT]
        if value:
            out[name] = value
    return out


def _component_changes(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    before = {c["key"]: c["placement"] for c in old.get("components", [])}
    counts: Counter[str] = Counter()
    changed: list[dict[str, Any]] = []
    for comp in new["components"]:
        if comp["key"] not in before:
            continue
        was, now = before[comp["key"]], comp["placement"]
        if was is None and now is None:
            continue
        if was is None:
            kinds = ["placed"]
        elif now is None:
            kinds = ["unplaced"]
        else:
            kinds = [
                kind
                for kind, same in (
                    ("moved", _same_xy(was[:2], now[:2])),
                    ("rotated", _same_angle(was[2], now[2])),
                    ("flipped", was[3] == now[3]),
                )
                if not same
            ]
        if kinds:
            counts.update(kinds)
            changed.append(
                {"key": comp["key"], "change": kinds, "old": was, "new": now}
            )
    return _trim({"counts": counts, "list": changed})


def _unmatched(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    old_identity: Callable[[dict[str, Any]], Hashable],
    new_identity: Callable[[dict[str, Any]], Hashable] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The entries of ``old`` and of ``new`` left after pairing, one for one,
    those whose identities are equal."""
    new_identity = new_identity or old_identity
    pool: dict[Hashable, list[dict[str, Any]]] = {}
    for entry in old:
        pool.setdefault(old_identity(entry), []).append(entry)
    left_new: list[dict[str, Any]] = []
    for entry in new:
        same = pool.get(new_identity(entry))
        if same:
            same.pop()
        else:
            left_new.append(entry)
    return [e for entries in pool.values() for e in entries], left_new


def _route_changes(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    def identity_in(state: dict[str, Any]) -> Callable[[dict[str, Any]], Hashable]:
        pads = {p["key"] for p in state.get("pads", [])}

        def identity(route: dict[str, Any]) -> Hashable:
            ends = sorted(
                route[f"{end}_key"] if route[f"{end}_key"] in pads else route[end]
                for end in ("source", "destination")
            )
            return (route["net"], route["layer"], *ends)

        return identity

    def brief(route: dict[str, Any]) -> dict[str, Any]:
        return {k: route[k] for k in ("key", "net", "layer")}

    gone, fresh = _unmatched(
        old.get("routes", []), new["routes"], identity_in(old), identity_in(new)
    )
    return _trim(
        {
            "counts": {"added": len(fresh), "removed": len(gone)},
            "added": [brief(r) for r in fresh],
            "removed": [brief(r) for r in gone],
        }
    )


def _point_changes(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    kind: Callable[[dict[str, Any]], Hashable],
    where: Callable[[dict[str, Any]], list[float]],
) -> dict[str, Any]:
    """Changes to vias or control points. ``kind`` is what a move keeps (net
    and definition, or type and layer); ``where`` is what a move changes
    (position, and rotation for a control point)."""

    def identity(entry: dict[str, Any]) -> Hashable:
        return (kind(entry), entry["placed"], *(round(v, 3) for v in where(entry)))

    def brief(entry: dict[str, Any]) -> dict[str, Any]:
        named = ("key", "net", "definition", "type")
        return {k: entry[k] for k in named if k in entry}

    gone, fresh = _unmatched(old, new, identity)

    # Among those left, the same key with the same kind, placed both times,
    # is a move.
    moved: list[dict[str, Any]] = []
    by_key = {e["key"]: e for e in gone if e["placed"]}
    still_fresh: list[dict[str, Any]] = []
    for entry in fresh:
        was = by_key.get(entry["key"]) if entry["placed"] else None
        if was is None or kind(was) != kind(entry):
            still_fresh.append(entry)
            continue
        del by_key[entry["key"]]
        moved.append({**brief(entry), "old": where(was), "new": where(entry)})
    unpaired = {id(e) for e in by_key.values()}
    gone = [e for e in gone if not e["placed"] or id(e) in unpaired]
    fresh = still_fresh

    # Placing a component re-reports the vias and control points of its
    # circuit at board positions under new keys (unplacing it, the reverse):
    # pair those by kind rather than list them as added and removed.
    def placed(entries: list[dict[str, Any]], flag: bool) -> list[dict[str, Any]]:
        return [e for e in entries if e["placed"] == flag]

    gone_off, now_on = _unmatched(placed(gone, False), placed(fresh, True), kind)
    gone_on, now_off = _unmatched(placed(gone, True), placed(fresh, False), kind)
    counts = {
        "added": len(now_on) + len(now_off),
        "removed": len(gone_off) + len(gone_on),
        "moved": len(moved),
        "placed_with_component": len(placed(fresh, True)) - len(now_on),
        "unplaced_with_component": len(placed(fresh, False)) - len(now_off),
    }

    def listed(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**brief(e), "at": where(e)} for e in entries]

    return _trim(
        {
            "counts": counts,
            "added": listed(now_on + now_off),
            "removed": listed(gone_off + gone_on),
            "moved": moved,
        }
    )


def _pour_changes(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    def identity(pour: dict[str, Any]) -> Hashable:
        return (pour["layer"], pour["rank"], pour["net"])

    def brief(pour: dict[str, Any]) -> dict[str, Any]:
        return {k: pour[k] for k in ("key", "net", "layer")}

    gone, fresh = _unmatched(old.get("pours", []), new["pours"], identity)
    return _trim(
        {
            "counts": {"added": len(fresh), "removed": len(gone)},
            "added": [brief(p) for p in fresh],
            "removed": [brief(p) for p in gone],
        }
    )


def _changes(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any] | None:
    """What changed from the previous state to this one; None without a
    previous state of the same design."""
    if old is None or old.get("design") != new["design"]:
        return None
    sections = {
        "components": _component_changes(old, new),
        "routes": _route_changes(old, new),
        "vias": _point_changes(
            old.get("vias", []),
            new["vias"],
            lambda v: (v["definition"], v["net"]),
            lambda v: v["pos"],
        ),
        "control_points": _point_changes(
            old.get("control_points", []),
            new["control_points"],
            lambda c: (c["type"], c["layer"]),
            lambda c: [*c["pos"], c["rotation"]],
        ),
        "pours": _pour_changes(old, new),
    }
    return {name: section for name, section in sections.items() if section}


def _keep_previous() -> dict[str, Any] | None:
    """Move the last state.json to state-prev.json and return its contents,
    or None if there is none or it cannot be read."""
    out = Path.cwd() / OUT_DIR
    current = out / STATE
    if not current.exists():
        return None
    current.replace(out / PREVIOUS_STATE)
    try:
        previous = json.loads((out / PREVIOUS_STATE).read_text())
    except (OSError, ValueError):
        return None
    return previous if isinstance(previous, dict) else None


def main(rd: Any) -> dict[str, Any]:
    """Write state.json and return the layout summary."""
    root = rd.root
    key = _Keys(rd)

    def net_name(obj: object) -> str | None:
        net = rd.nets.find(obj)
        return None if net is None else net.name

    board = root.board.shape.to_shapely().g
    state: dict[str, Any] = {
        "design": rd.name,
        "board": _outline(board),
        "conductors": len(root.substrate.stackup.conductors),
        "via_definitions": [],
        "components": [],
        "pads": [],
        "routes": [],
        "vias": [],
        "control_points": [],
        "pours": [],
    }

    seen: set[str] = set()
    for klass in typeof(root.substrate).__mro__:
        for value in vars(klass).values():
            if not (isinstance(value, type) and issubclass(value, Via)):
                continue
            name = value.name or value.__name__
            if name in seen:
                continue
            seen.add(name)
            diameter = getattr(value, "diameter", None)
            state["via_definitions"].append(
                {
                    "name": name,
                    "layers": [value.start_layer, value.stop_layer],
                    "diameter": diameter if isinstance(diameter, float | int) else None,
                    "hole": getattr(value, "hole_diameter", None),
                    "via_in_pad": bool(getattr(value, "via_in_pad", False)),
                }
            )

    side_of: dict[str, str] = {}
    for trace, comp in rd.query(Component):
        mpn = getattr(comp, "mpn", None)
        entry: dict[str, Any] = {
            "key": key(trace),
            "mpn": None if mpn is None else str(mpn),
            "placement": None,
            "courtyard": None,
        }
        entry["placement"] = _placement(trace, comp)
        if entry["placement"] is not None:
            side_of[entry["key"]] = entry["placement"][3]
        state["components"].append(entry)

    courtyards: dict[str, BaseGeometry] = {}
    local: dict[str, BaseGeometry] = {}
    owners = sorted((c["key"] for c in state["components"]), key=len, reverse=True)
    for trace, court in rd.query(Courtyard):
        k = key(trace)
        owner = next((c for c in owners if k.startswith(c + ".")), None)
        if owner is None:
            continue
        own = court.shape.to_shapely().g
        local[owner] = own if owner not in local else local[owner].union(own)
        if owner in side_of and trace.transform is not None:
            geom = (trace.transform * court.shape).to_shapely().g
            courtyards[owner] = (
                geom if owner not in courtyards else courtyards[owner].union(geom)
            )
    for entry in state["components"]:
        if entry["key"] in courtyards:
            entry["courtyard"] = _xy(courtyards[entry["key"]].bounds)
        if entry["key"] in local:
            x0, y0, x1, y1 = local[entry["key"]].bounds
            entry["courtyard_size"] = [round(x1 - x0, 4), round(y1 - y0, 4)]

    for trace, pad in rd.query(Pad):
        k = key(trace)
        xf = (
            trace.transform * pad.transform
            if pad.transform is not None
            else trace.transform
        )
        base = pad.shape.shape if isinstance(pad.shape, PadShape) else pad.shape
        state["pads"].append(
            {
                "key": k,
                "placed": any(k.startswith(c + ".") for c in side_of),
                "pos": _xy(xf.translation),
                "net": net_name(pad),
                "outline": _outline((xf * base).to_shapely().g)
                if isinstance(base, Shape)
                else None,
            }
        )

    known = key.known(rd)
    for trace, route in rd.query(Route):
        k = key(trace)
        status = route.status
        state["routes"].append(
            {
                "key": k,
                "interactive": _interactive(k),
                "layer": route.layer,
                "net": net_name(route.source) or net_name(route.destination),
                "status": None
                if status is None
                else ("routed" if status.routed else "blocked"),
                "source": typeof(route.source).__name__,
                "source_key": known.get(id(route.source)),
                "destination": typeof(route.destination).__name__,
                "destination_key": known.get(id(route.destination)),
                "traces": len(route.traces or []),
            }
        )

    unplaced = [c["key"] for c in state["components"] if c["placement"] is None]
    component_keys = [c["key"] for c in state["components"]]
    for trace, via in rd.query(Via):
        if trace.transform is None or via.transform is None:
            continue
        k = key(trace)
        owner = _owner(k, component_keys)
        state["vias"].append(
            {
                "key": k,
                "interactive": _interactive(k),
                "placed": not owner or not any(c.startswith(owner) for c in unplaced),
                "pos": _xy((trace.transform * via.transform).translation),
                "definition": typeof(via).name or typeof(via).__name__,
                "net": net_name(via),
            }
        )

    for trace, cp in rd.query(ControlPoint):
        if trace.transform is None or cp.transform is None:
            continue
        k = key(trace)
        xf = trace.transform * cp.transform
        owner = _owner(k, component_keys)
        state["control_points"].append(
            {
                "key": k,
                "interactive": _interactive(k),
                "placed": not owner or not any(c.startswith(owner) for c in unplaced),
                "type": typeof(cp).__name__,
                "layer": cp.layer,
                "pos": _xy(xf.translation),
                "rotation": round(xf.rotation % 360, 3),
            }
        )

    for trace, pour in rd.query(Pour):
        k = key(trace)
        shape = pour.shape
        state["pours"].append(
            {
                "key": k,
                "interactive": _interactive(k),
                "layer": pour.layer,
                "rank": pour.rank,
                "net": net_name(pour),
                "fill_pieces": _pieces(shape),
            }
        )

    overlaps: list[list[Any]] = []
    placed = sorted(courtyards)
    for i, a in enumerate(placed):
        for b in placed[i + 1 :]:
            if side_of[a] == side_of[b]:
                area = courtyards[a].intersection(courtyards[b]).area
                if area > 1e-6:
                    overlaps.append([a, b, round(area, 4)])
    inside = board.buffer(1e-6)

    changed = _changes(_keep_previous(), state)
    return {
        "written": _write(STATE, state),
        "changed": changed,
        "counts": {
            "components": len(state["components"]),
            "placed": len(side_of),
            **{
                n: len(state[n])
                for n in ("pads", "routes", "vias", "control_points", "pours")
            },
        },
        "ideal_parts": [
            c["key"]
            for c in state["components"]
            if (c["mpn"] or "").startswith(IDEAL_PREFIX)
        ][:LIST_LIMIT],
        "unplaced": unplaced[:LIST_LIMIT],
        "courtyard_overlaps": overlaps[:LIST_LIMIT],
        "off_board": [k for k in placed if not inside.contains(courtyards[k])][
            :LIST_LIMIT
        ],
        "blocked_routes": [r for r in state["routes"] if r["status"] == "blocked"][
            :LIST_LIMIT
        ],
        "split_pours": [p for p in state["pours"] if (p["fill_pieces"] or 0) > 1][
            :LIST_LIMIT
        ],
        "fill_unknown": [p["key"] for p in state["pours"] if p["fill_pieces"] is None][
            :LIST_LIMIT
        ],
        "empty_pours": [p["key"] for p in state["pours"] if p["fill_pieces"] == 0][
            :LIST_LIMIT
        ],
        "lists_truncated_at": LIST_LIMIT,
    }


def _measurement(issue: SignalIntegrityIssue) -> dict[str, Any]:
    scale, unit = (PS_PER_S, "ps") if isinstance(issue, TimingIssue) else (1.0, "dB")
    entry: dict[str, Any] = {"unit": unit, "satisfied": issue.satisfied}
    measured, acceptable = issue.measured_range, issue.acceptable_range
    if measured is not None:
        entry["measured"] = [
            round(measured[0] * scale, 3),
            round(measured[1] * scale, 3),
        ]
    if acceptable is not None:
        entry["acceptable"] = [
            round(acceptable[0] * scale, 3),
            round(acceptable[1] * scale, 3),
        ]
    if measured is not None and acceptable is not None:
        low = (measured[0] - acceptable[0]) * scale
        high = (acceptable[1] - measured[1]) * scale
        entry["margin"] = round(min(low, high), 3)
    return entry


def _label(value: object) -> str:
    return value.name if isinstance(value, Severity | IssueCategory) else str(value)


def _issues(rd: Any, satisfied: bool) -> dict[str, Any]:
    known = _Keys(rd).known(rd)

    def entry_of(issue: DesignIssue) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "type": type(issue).__name__,
            "severity": _label(issue.severity),
            "category": _label(issue.category),
            "text": issue.text,
            "objects": [
                {"role": o.role, "ref": o.ref, "key": known.get(id(o.instance))}
                for o in issue.objects
            ],
        }
        cause = getattr(issue, "cause", None)
        if cause:
            entry["cause"] = str(cause)
        refs: list[str] = []
        if isinstance(issue, UnmetTimeDiff):
            refs = [
                p.ref for p in (issue.longer_path, issue.shorter_path) if p is not None
            ]
        elif isinstance(issue, UnmetTime) and issue.path is not None:
            refs = [issue.path.ref]
        if any(refs):
            entry["paths"] = refs
        if isinstance(issue, SignalIntegrityIssue):
            entry.update(_measurement(issue))
        return entry

    report = rd.issues(satisfied=satisfied, wait=ISSUE_WAIT_SECONDS)
    issues = [entry_of(i) for i in report]
    pending = [
        _label(category)
        for category, cat in report.categories.items()
        if cat.status != CategoryStatus.COMPLETE
    ]
    written = _write("issues.json", {"satisfied_included": satisfied, "issues": issues})
    errors: dict[str, list[dict[str, Any]]] = {}
    for i in issues:
        if i["severity"] == Severity.ERROR.name:
            errors.setdefault(i["type"], []).append(
                {"text": i["text"], "keys": [o["key"] for o in i["objects"]]}
            )
    tightest = sorted((i for i in issues if "margin" in i), key=lambda i: i["margin"])
    return {
        "written": written,
        "complete": not pending,
        "pending": pending,
        "counts": dict(
            sorted(Counter(f"{i['type']}/{i['severity']}" for i in issues).items())
        ),
        "errors": {t: e[:ERRORS_PER_TYPE] for t, e in errors.items()},
        "tightest_margins": [
            {k: i[k] for k in ("type", "unit", "margin", "satisfied", "text")}
            for i in tightest[:LIST_LIMIT]
        ],
        "lists_truncated_at": LIST_LIMIT,
    }


def issues(rd: Any) -> dict[str, Any]:
    """Write issues.json with the open issues and return their summary."""
    return _issues(rd, satisfied=False)


def issues_all(rd: Any) -> dict[str, Any]:
    """As ``issues``, including checks that pass."""
    return _issues(rd, satisfied=True)
