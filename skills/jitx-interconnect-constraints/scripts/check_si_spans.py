#!/usr/bin/env python3
"""Prove that emitted SI constraint spans bind to complete topology chains.

The checker reads ``cache/load-cache.json`` after a JITX build. It resolves
numeric local-id paths against the artifact's own module, component, and bundle
tables, joins ``topologySegments`` with ``pinModels``, and walks every emitted
routing-structure and insertion-loss span from begin to end.

Exit codes: 0 means every emitted span has a complete path and covers its
connected chain; 1 means a span is unbound, partial, or absent; 2 means usage or
the internal cache schema is unsupported. ``--allow-partial`` permits a
deliberately partial constraint after the caller records why the remainder of
the chain is outside the task's SI scope.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from itertools import pairwise
from pathlib import Path
from typing import Any


PathId = tuple[int, ...]
Graph = dict[PathId, set[PathId]]
REQUIRED_CACHE_FIELDS = {
    "topologySegments",
    "pinModels",
    "structures",
    "differentialStructures",
    "constrainInsertionLosses",
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

    required_root = {"module", "modules", "components", "bundles"}
    missing_root = sorted(required_root - cache.keys())
    if missing_root:
        raise CacheSchemaError(
            f"load-cache v1 is missing root fields: {', '.join(missing_root)}"
        )
    module_fields = {key for module in cache["modules"] for key in module.keys()}
    missing_fields = sorted(REQUIRED_CACHE_FIELDS - module_fields)
    if missing_fields:
        raise CacheSchemaError(
            "load-cache v1 has no supported SI fields: " + ", ".join(missing_fields)
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

    module_ids = {module["id"] for module in cache["modules"]}
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


def constraints(cache: dict[str, Any], defs: dict[int, dict[str, Any]]):
    """Yields every emitted span as ``(label, absolute begin, absolute end)``."""

    for prefix, module in walk_instances(cache, defs):
        for entry in module.get("structures", []) or []:
            path = entry["path"]
            yield (
                f"structure {entry['routingStructure']}",
                prefix + tuple(path["key"]["path"]),
                prefix + tuple(path["value"]["path"]),
            )
        for entry in module.get("differentialStructures", []) or []:
            for leg in ("path1", "path2"):
                path = entry[leg]
                yield (
                    f"diff structure {entry['differentialRoutingStructure']}",
                    prefix + tuple(path["key"]["path"]),
                    prefix + tuple(path["value"]["path"]),
                )
        for entry in module.get("constrainInsertionLosses", []) or []:
            path = entry["path"]
            limit = entry["constraint"]
            yield (
                f"insertion loss <= {limit['maxLoss']} dB",
                prefix + tuple(path["key"]["path"]),
                prefix + tuple(path["value"]["path"]),
            )


def check_cache(path: Path, allow_partial: bool = False) -> int:
    """Checks one cache and prints each emitted span with its resolved path."""

    document = json.loads(path.read_text(encoding="utf-8"))
    if "v1" not in document:
        raise CacheSchemaError("load-cache has no supported v1 document")
    cache = document["v1"]
    validate_schema(cache)
    defs = definitions(cache)
    root = defs[cache["module"]]
    edges = topology_graph(cache, defs)

    failures = 0
    checked = 0
    for label, begin, end in constraints(cache, defs):
        checked += 1
        names = f"{name_of(begin, defs, root)} -> {name_of(end, defs, root)}"
        missing_endpoints = [
            endpoint for endpoint in (begin, end) if endpoint not in edges
        ]
        route = None if missing_endpoints else span(begin, end, edges)
        if route is None:
            failures += 1
            print(f"FAIL  {label:<26} {names}")
            print("      NO PATH: the endpoints are not joined by the emitted topology")
            continue

        covered = {frozenset(edge) for edge in pairwise(route)}
        outside = chain_edges(begin, edges) - covered
        partial_failure = bool(outside) and not allow_partial
        failures += int(partial_failure)
        status = "FAIL" if partial_failure else "PASS"
        print(f"{status}  {label:<26} {names}   {len(route) - 1} hops")
        for node in route:
            print(f"      {name_of(node, defs, root)}")
        for edge in sorted(outside, key=lambda item: sorted(item)):
            first, second = sorted(edge)
            prefix = "ALLOWED PARTIAL" if allow_partial else "UNCOVERED"
            print(
                f"      {prefix}: {name_of(first, defs, root)} >> "
                f"{name_of(second, defs, root)}"
            )

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
        action="store_true",
        help="allow connected chain segments outside the declared span",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Runs the checker with stable exit codes."""

    args = parse_args(argv)
    try:
        return check_cache(args.cache, allow_partial=args.allow_partial)
    except (CacheSchemaError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"ERROR unsupported load-cache schema: {error}")
        return 2
    except OSError as error:
        print(f"ERROR cannot read {args.cache}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
