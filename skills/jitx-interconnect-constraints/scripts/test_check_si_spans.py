#!/usr/bin/env python3
"""Unit tests for the emitted SI span checker."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_si_spans import check_cache


def cache_document(
    constraint_end: int = 13,
    constraint_begin: int = 10,
) -> dict[str, object]:
    """Returns a minimal supported cache with one three-node topology chain."""

    def path(port: int) -> dict[str, list[int]]:
        return {"path": [port]}

    module = {
        "id": 1,
        "name": "Root",
        "ports": [
            {"id": port, "name": name, "type": {}}
            for port, name in ((10, "src"), (11, "middle"), (12, "dst"), (13, "other"))
        ],
        "instances": [],
        "topologySegments": [
            {"key": path(10), "value": path(11)},
        ],
        "pinModels": [
            {"a": path(11), "b": path(12)},
        ],
        "structures": [
            {
                "path": {"key": path(constraint_begin), "value": path(constraint_end)},
                "routingStructure": 50,
            }
        ],
        "differentialStructures": [],
        "constrainInsertionLosses": [],
    }
    return {
        "v1": {
            "module": 1,
            "modules": [module],
            "components": [],
            "bundles": [],
        }
    }


def run_document(document: dict[str, object], allow_partial: bool = False):
    """Runs one fixture through the file-backed public checker."""

    with tempfile.TemporaryDirectory(prefix="si-span-test-") as temporary:
        path = Path(temporary) / "load-cache.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = check_cache(path, allow_partial=allow_partial)
    return result, output.getvalue()


class CheckSiSpansTests(unittest.TestCase):
    def test_complete_span_passes(self) -> None:
        result, output = run_document(cache_document(constraint_end=12))
        self.assertEqual(result, 0)
        self.assertIn("PASS", output)
        self.assertIn("2 hops", output)

    def test_dangling_endpoint_fails_despite_valid_cache(self) -> None:
        result, output = run_document(cache_document(constraint_end=13))
        self.assertEqual(result, 1)
        self.assertIn("NO PATH", output)

    def test_missing_bridging_pin_model_fails(self) -> None:
        document = cache_document(constraint_end=12)
        document["v1"]["modules"][0]["pinModels"] = []  # type: ignore[index]
        result, output = run_document(document)
        self.assertEqual(result, 1)
        self.assertIn("NO PATH", output)

    def test_partial_span_fails_on_uncovered_chain_segment(self) -> None:
        result, output = run_document(cache_document(constraint_end=11))
        self.assertEqual(result, 1)
        self.assertIn("UNCOVERED", output)

    def test_documented_partial_span_can_be_allowed(self) -> None:
        result, output = run_document(
            cache_document(constraint_end=11), allow_partial=True
        )
        self.assertEqual(result, 0)
        self.assertIn("ALLOWED PARTIAL", output)

    def test_no_emitted_constraint_fails(self) -> None:
        document = cache_document(constraint_end=12)
        document["v1"]["modules"][0]["structures"] = []  # type: ignore[index]
        result, output = run_document(document)
        self.assertEqual(result, 1)
        self.assertIn("no emitted SI constraint spans", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
