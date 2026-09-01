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

from check_si_spans import check_cache, main


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


def run_document(document: dict[str, object], allow_partial: tuple[str, ...] = ()):
    """Runs one fixture through the file-backed public checker."""

    with tempfile.TemporaryDirectory(prefix="si-span-test-") as temporary:
        path = Path(temporary) / "load-cache.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = check_cache(path, allow_partial=allow_partial)
    return result, output.getvalue()


def run_main_document(document: dict[str, object]):
    """Run malformed-input fixtures through the exit-code boundary."""

    with tempfile.TemporaryDirectory(prefix="si-span-test-") as temporary:
        path = Path(temporary) / "load-cache.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main([str(path)])
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

    def test_documented_partial_span_can_be_allowed_by_exact_label(self) -> None:
        result, output = run_document(
            cache_document(constraint_end=11),
            allow_partial=("structure 50[0]: src -> middle",),
        )
        self.assertEqual(result, 0)
        self.assertIn("ALLOWED PARTIAL", output)

    def test_allowing_one_partial_span_does_not_disable_another(self) -> None:
        document = cache_document(constraint_end=11)
        module = document["v1"]["modules"][0]  # type: ignore[index]
        module["constrainTimings"] = [  # type: ignore[index]
            {
                "path": {
                    "key": {"path": [10]},
                    "value": {"path": [11]},
                },
                "constraint": {"minDelay": 0.0, "maxDelay": 1e-9},
            }
        ]
        result, output = run_document(
            document,
            allow_partial=("structure 50[0]: src -> middle",),
        )
        self.assertEqual(result, 1)
        self.assertIn("ALLOWED PARTIAL", output)
        self.assertIn("FAIL  timing[0] 0.0..1e-09 s: src -> middle", output)

    def test_unknown_partial_label_is_usage_error(self) -> None:
        result, output = run_document(
            cache_document(constraint_end=12),
            allow_partial=("structure 50[0]: typo -> target",),
        )
        self.assertEqual(result, 2)
        self.assertIn("unknown or unnecessary", output)

    def test_bare_allow_partial_is_usage_error(self) -> None:
        stderr = io.StringIO()
        with (
            contextlib.redirect_stderr(stderr),
            self.assertRaisesRegex(SystemExit, "2"),
        ):
            main(["load-cache.json", "--allow-partial"])
        self.assertIn("expected one argument", stderr.getvalue())

    def test_t_topology_branch_is_not_uncovered(self) -> None:
        document = cache_document(constraint_end=12)
        module = document["v1"]["modules"][0]  # type: ignore[index]
        module["topologySegments"].append(  # type: ignore[index]
            {"key": {"path": [11]}, "value": {"path": [13]}}
        )
        result, output = run_document(document)
        self.assertEqual(result, 0)
        self.assertIn("BRANCH: middle >> other", output)

    def test_sparse_single_ended_cache_omits_empty_collections(self) -> None:
        document = cache_document(constraint_end=12)
        module = document["v1"]["modules"][0]  # type: ignore[index]
        module["topologySegments"].append(  # type: ignore[index]
            {"key": {"path": [11]}, "value": {"path": [12]}}
        )
        module["pinModels"] = []  # type: ignore[index]
        for field in (
            "pinModels",
            "differentialStructures",
            "constrainInsertionLosses",
        ):
            del module[field]  # type: ignore[index]
        document["v1"].pop("components")  # type: ignore[index]
        document["v1"].pop("bundles")  # type: ignore[index]
        result, output = run_document(document)
        self.assertEqual(result, 0)
        self.assertIn("PASS  structure 50", output)

    def test_sparse_differential_cache_omits_other_si_collections(self) -> None:
        def path(port: int) -> dict[str, list[int]]:
            return {"path": [port]}

        module = {
            "id": 1,
            "name": "Root",
            "ports": [
                {"id": port, "name": name, "type": {}}
                for port, name in (
                    (10, "src_p"),
                    (11, "src_n"),
                    (12, "dst_p"),
                    (13, "dst_n"),
                )
            ],
            "instances": [],
            "topologySegments": [
                {"key": path(10), "value": path(12)},
                {"key": path(11), "value": path(13)},
            ],
            "differentialStructures": [
                {
                    "path1": {"key": path(10), "value": path(12)},
                    "path2": {"key": path(11), "value": path(13)},
                    "differentialRoutingStructure": 100,
                }
            ],
        }
        document = {"v1": {"module": 1, "modules": [module]}}
        result, output = run_document(document)
        self.assertEqual(result, 0)
        self.assertEqual(output.count("PASS  diff structure 100"), 2)

    def test_timing_constraint_with_missing_topology_path_fails(self) -> None:
        document = cache_document(constraint_end=12)
        module = document["v1"]["modules"][0]  # type: ignore[index]
        module["constrainTimings"] = [  # type: ignore[index]
            {
                "path": {
                    "key": {"path": [10]},
                    "value": {"path": [13]},
                },
                "constraint": {"minDelay": 0.0, "maxDelay": 5e-10},
            }
        ]
        result, output = run_document(document)
        self.assertEqual(result, 1)
        self.assertIn("FAIL  timing", output)
        self.assertIn("NO PATH", output)

    def test_timing_constraint_with_short_span_fails(self) -> None:
        document = cache_document(constraint_end=12)
        module = document["v1"]["modules"][0]  # type: ignore[index]
        module["constrainTimings"] = [  # type: ignore[index]
            {
                "path": {
                    "key": {"path": [10]},
                    "value": {"path": [11]},
                },
                "constraint": {"minDelay": 0.0, "maxDelay": 5e-10},
            }
        ]
        result, output = run_document(document)
        self.assertEqual(result, 1)
        self.assertIn("FAIL  timing", output)
        self.assertIn("UNCOVERED", output)

    def test_timing_difference_checks_both_spans(self) -> None:
        document = cache_document(constraint_end=12)
        module = document["v1"]["modules"][0]  # type: ignore[index]
        module["constrainTimingDifferences"] = [  # type: ignore[index]
            {
                "path1": {
                    "key": {"path": [10]},
                    "value": {"path": [12]},
                },
                "path2": {
                    "key": {"path": [10]},
                    "value": {"path": [13]},
                },
                "constraint": {"minDelta": -1e-11, "maxDelta": 1e-11},
            }
        ]
        result, output = run_document(document)
        self.assertEqual(result, 1)
        self.assertIn("path1", output)
        self.assertIn("FAIL  timing difference", output)
        self.assertIn("path2", output)

    def test_no_emitted_constraint_fails(self) -> None:
        document = cache_document(constraint_end=12)
        document["v1"]["modules"][0]["structures"] = []  # type: ignore[index]
        result, output = run_document(document)
        self.assertEqual(result, 1)
        self.assertIn("no emitted SI constraint spans", output)

    def test_present_malformed_optional_collection_is_exit_two(self) -> None:
        document = cache_document(constraint_end=12)
        document["v1"]["modules"][0]["constrainTimings"] = {}  # type: ignore[index]
        result, output = run_main_document(document)
        self.assertEqual(result, 2)
        self.assertIn("constrainTimings is not a collection", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
