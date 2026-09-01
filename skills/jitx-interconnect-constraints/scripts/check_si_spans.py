#!/usr/bin/env python3
"""Prove that emitted SI constraint spans bind to complete topology chains.

The checker reads ``cache/load-cache.json`` after a JITX build. It resolves
numeric local-id paths against the artifact's own module, component, and bundle
tables, joins ``topologySegments`` with ``pinModels``, and walks every emitted
routing-structure and insertion-loss span from begin to end.

Exit codes: 0 means every emitted span has a complete path and covers its
connected chain; 1 means a span is unbound, partial, or absent; 2 means usage,
an unreadable cache, or a malformed internal cache schema. ``--allow-partial``
accepts one exact printed span label per use, so an intentional partial span
cannot disable coverage checking for any other constraint.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Collection
from collections import deque
from itertools import pairwise
from pathlib import Path
from typing import Any


PathId = tuple[int, ...]
Graph = dict[PathId, set[PathId]]
OPTIONAL_MODULE_COLLECTIONS = {
    "topologySegments",
    "pinModels",
    "structures",
    "differentialStructures",
    "constrainInsertionLosses",
    "constrainTimings",
    "constrainTimingDifferences",
}


class CacheSchemaError(ValueError):
    """The build artifact does not match the supported internal schema."""


def definitions(cache: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Returns definitions keyed by local id across all definition groups."""

    return {
        definition["id"]: definition
        for group in ("modules", "components", "bundles")
        for definition in cache.get(group, [])
    }


def validate_schema(cache: dict[str, Any]) -> None:
    """Fails loudly when the internal cache surface changes."""

    if not isinstance(cache, dict):
        raise CacheSchemaError("load-cache v1 document is not an object")
    required_root = {"module", "modules"}
    missing_root = sorted(required_root - cache.keys())
    if missing_root:
        raise CacheSchemaError(
            f"load-cache v1 is missing root fields: {', '.join(missing_root)}"
        )
    for field in ("modules", "components", "bundles"):
        value = cache.get(field, [])
        if not isinstance(value, list):
            raise CacheSchemaError(f"load-cache v1 field {field} is not a collection")
    for index, module in enumerate(cache["modules"]):
        if not isinstance(module, dict):
            raise CacheSchemaError(f"load-cache v1 module {index} is not an object")
        for field in OPTIONAL_MODULE_COLLECTIONS:
            if field in module and not isinstance(module[field], list):
                raise CacheSchemaError(
                    f"load-cache v1 module {index} field {field} is not a collection"
                )
    if cache["module"] not in definitions(cache):
        raise CacheSchemaError("load-cache v1 root module id is unresolved")


def name_of(
    path: PathId,
    defs: dict[int, dict[str, Any]],
    root: dict[str, Any],
) -> str:
    """Resolves an absolute local-id path to a dotted structural name."""

    here: dict[str, Any] | None = root
    parts: list[str] = []
    for element in path:
        ports = {port["id"]: port for port in here.get("ports", [])} if here else {}
        instances = (
            {instance["id"]: instance for instance in here.get("instances", [])}
            if here
            else {}
        )
        if element in ports:
            port = ports[element]
            parts.append(port["name"])
            bundle = port["type"].get("bundle")
            here = defs.get(bundle["bundle"]) if bundle else None
        elif element in instances:
            instance = instances[element]
            parts.append(instance["name"])
            here = defs.get(instance["instantiable"])
        else:
            parts.append(f"<{element}>")
            here = None
    return ".".join(parts)


def walk_instances(cache: dict[str, Any], defs: dict[int, dict[str, Any]]):
    """Yields each module definition with its absolute instance-path prefix."""

    module_ids = {module["id"] for module in cache.get("modules", [])}
    queue: deque[tuple[PathId, dict[str, Any]]] = deque([((), defs[cache["module"]])])
    while queue:
        prefix, module = queue.popleft()
        yield prefix, module
        for instance in module.get("instances", []):
            if instance["instantiable"] in module_ids:
                queue.append(
                    (
                        prefix + (instance["id"],),
                        defs[instance["instantiable"]],
                    )
                )


def topology_graph(cache: dict[str, Any], defs: dict[int, dict[str, Any]]) -> Graph:
    """Returns one graph over emitted ``>>`` segments and bridging pin models."""

    edges: Graph = {}

    def join(first: PathId, second: PathId) -> None:
        edges.setdefault(first, set()).add(second)
        edges.setdefault(second, set()).add(first)

    for prefix, module in walk_instances(cache, defs):
        for segment in module.get("topologySegments", []) or []:
            join(
                prefix + tuple(segment["key"]["path"]),
                prefix + tuple(segment["value"]["path"]),
            )
        for model in module.get("pinModels", []) or []:
            join(
                prefix + tuple(model["a"]["path"]),
                prefix + tuple(model["b"]["path"]),
            )
    return edges


def span(begin: PathId, end: PathId, edges: Graph) -> list[PathId] | None:
    """Returns a breadth-first path between endpoints, or ``None``."""

    if begin == end:
        return [begin]
    previous: dict[PathId, PathId] = {begin: begin}
    queue = deque([begin])
    while queue:
        node = queue.popleft()
        for neighbor in edges.get(node, ()):
            if neighbor in previous:
                continue
            previous[neighbor] = node
            if neighbor == end:
                route = [end]
                while route[-1] != begin:
                    route.append(previous[route[-1]])
                return list(reversed(route))
            queue.append(neighbor)
    return None


def chain_edges(node: PathId, edges: Graph) -> set[frozenset[PathId]]:
    """Returns every edge in the connected chain containing ``node``."""

    seen = {node}
    queue = deque([node])
    found: set[frozenset[PathId]] = set()
    while queue:
        current = queue.popleft()
        for neighbor in edges.get(current, ()):
            found.add(frozenset((current, neighbor)))
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return found


def legitimate_branch_edges(
    route: list[PathId], edges: Graph
) -> set[frozenset[PathId]]:
    """Return off-route limbs rooted at a degree-greater-than-two route node."""

    route_nodes = set(route)
    found: set[frozenset[PathId]] = set()
    for branch in route:
        if len(edges.get(branch, ())) <= 2:
            continue
        for neighbor in edges.get(branch, ()):
            if neighbor in route_nodes:
                continue
            pending = [(branch, neighbor)]
            seen = {branch}
            while pending:
                previous, node = pending.pop()
                edge = frozenset((previous, node))
                if edge in found:
                    continue
                found.add(edge)
                seen.add(node)
                for next_node in edges.get(node, ()):
                    if next_node in route_nodes or next_node in seen:
                        continue
                    pending.append((node, next_node))
    return found


def constraints(cache: dict[str, Any], defs: dict[int, dict[str, Any]]):
    """Yields every emitted span as ``(label, absolute begin, absolute end)``."""

    for prefix, module in walk_instances(cache, defs):
        for index, entry in enumerate(module.get("structures", []) or []):
            path = entry["path"]
            yield (
                f"structure {entry['routingStructure']}[{index}]",
                prefix + tuple(path["key"]["path"]),
                prefix + tuple(path["value"]["path"]),
            )
        for index, entry in enumerate(module.get("differentialStructures", []) or []):
            for leg in ("path1", "path2"):
                path = entry[leg]
                yield (
                    f"diff structure {entry['differentialRoutingStructure']}"
                    f"[{index}] {leg}",
                    prefix + tuple(path["key"]["path"]),
                    prefix + tuple(path["value"]["path"]),
                )
        for index, entry in enumerate(module.get("constrainInsertionLosses", []) or []):
            path = entry["path"]
            limit = entry["constraint"]
            yield (
                f"insertion loss[{index}] <= {limit['maxLoss']} dB",
                prefix + tuple(path["key"]["path"]),
                prefix + tuple(path["value"]["path"]),
            )
        for index, entry in enumerate(module.get("constrainTimings", []) or []):
            path = entry["path"]
            limit = entry["constraint"]
            yield (
                f"timing[{index}] {limit['minDelay']}..{limit['maxDelay']} s",
                prefix + tuple(path["key"]["path"]),
                prefix + tuple(path["value"]["path"]),
            )
        for index, entry in enumerate(
            module.get("constrainTimingDifferences", []) or []
        ):
            limit = entry["constraint"]
            for leg in ("path1", "path2"):
                path = entry[leg]
                yield (
                    "timing difference "
                    f"[{index}] {limit['minDelta']}..{limit['maxDelta']} s {leg}",
                    prefix + tuple(path["key"]["path"]),
                    prefix + tuple(path["value"]["path"]),
                )


def check_cache(path: Path, allow_partial: Collection[str] | None = None) -> int:
    """Checks one cache and prints each emitted span with its resolved path."""

    document = json.loads(path.read_text(encoding="utf-8"))
    if "v1" not in document:
        raise CacheSchemaError("load-cache has no supported v1 document")
    cache = document["v1"]
    validate_schema(cache)
    defs = definitions(cache)
    root = defs[cache["module"]]
    edges = topology_graph(cache, defs)
    allowed_labels = set(allow_partial or ())
    used_allowances: set[str] = set()

    failures = 0
    checked = 0
    for label, begin, end in constraints(cache, defs):
        checked += 1
        names = f"{name_of(begin, defs, root)} -> {name_of(end, defs, root)}"
        span_label = f"{label}: {names}"
        missing_endpoints = [
            endpoint for endpoint in (begin, end) if endpoint not in edges
        ]
        route = None if missing_endpoints else span(begin, end, edges)
        if route is None:
            failures += 1
            print(f"FAIL  {span_label}")
            print("      NO PATH: the endpoints are not joined by the emitted topology")
            continue

        covered = {frozenset(edge) for edge in pairwise(route)}
        branches = legitimate_branch_edges(route, edges)
        outside = chain_edges(begin, edges) - covered - branches
        partial_allowed = bool(outside) and span_label in allowed_labels
        if partial_allowed:
            used_allowances.add(span_label)
        partial_failure = bool(outside) and not partial_allowed
        failures += int(partial_failure)
        status = "FAIL" if partial_failure else "PASS"
        print(f"{status}  {span_label}   {len(route) - 1} hops")
        for node in route:
            print(f"      {name_of(node, defs, root)}")
        for edge in sorted(branches, key=lambda item: sorted(item)):
            first, second = sorted(edge)
            print(
                f"      BRANCH: {name_of(first, defs, root)} >> "
                f"{name_of(second, defs, root)}"
            )
        for edge in sorted(outside, key=lambda item: sorted(item)):
            first, second = sorted(edge)
            prefix = "ALLOWED PARTIAL" if partial_allowed else "UNCOVERED"
            print(
                f"      {prefix}: {name_of(first, defs, root)} >> "
                f"{name_of(second, defs, root)}"
            )

    unused_allowances = sorted(allowed_labels - used_allowances)
    if unused_allowances:
        print(
            "ERROR unknown or unnecessary --allow-partial span label(s): "
            + ", ".join(unused_allowances)
        )
        return 2
    if not checked:
        print("FAIL  no emitted SI constraint spans were found")
        return 1
    print(f"summary: checked={checked} passed={checked - failures} failed={failures}")
    return 1 if failures else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path, help="path to cache/load-cache.json")
    parser.add_argument(
        "--allow-partial",
        action="append",
        default=[],
        metavar="SPAN_LABEL",
        help="allow uncovered linear segments for this exact printed span label; repeatable",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Runs the checker with stable exit codes."""

    args = parse_args(argv)
    try:
        return check_cache(args.cache, allow_partial=args.allow_partial)
    except (
        CacheSchemaError,
        AttributeError,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR unsupported load-cache schema: {error}")
        return 2
    except (OSError, UnicodeError) as error:
        print(f"ERROR cannot read {args.cache}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
