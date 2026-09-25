#!/usr/bin/env python3
"""Tests for thermal_via_stitch.py. Run directly with the project Python."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from shapely.geometry import MultiPolygon

sys.path.insert(0, str(Path(__file__).resolve().parent))

from thermal_via_stitch import (  # noqa: E402
    StitchParams,
    grid_thermal_via_positions,
    soldermask_defined_thermal_pad_config,
    soldermask_thermal_pad_opening,
)


class StandInVia:
    diameter = 0.52


class StitchParamsTests(unittest.TestCase):
    def test_from_substrate_reads_constraints_and_via_class(self) -> None:
        constraints = SimpleNamespace(
            min_soldermask_bridge=0.12,
            solder_mask_registration=0.06,
            min_copper_edge_space=0.31,
        )

        params = StitchParams.from_substrate(constraints, StandInVia)  # type: ignore[arg-type]

        self.assertEqual(params.min_mask_bridge, 0.12)
        self.assertEqual(params.mask_expansion, 0.06)
        self.assertAlmostEqual(params.edge_margin, 0.18)  # skill default: bridge + registration
        self.assertEqual(params.via_pad_diameter, 0.52)
        self.assertEqual(params.fillet_radius, 0.0)

    def test_caller_supplied_edge_margin_wins(self) -> None:
        constraints = SimpleNamespace(
            min_soldermask_bridge=0.12,
            solder_mask_registration=0.06,
        )
        params = StitchParams.from_substrate(constraints, StandInVia, edge_margin=0.3)  # type: ignore[arg-type]
        self.assertEqual(params.edge_margin, 0.3)


class GridTests(unittest.TestCase):
    def test_count_symmetry_and_inset(self) -> None:
        edge_margin = 0.3
        via_pad_diameter = 0.5
        positions = grid_thermal_via_positions(
            ep_size=(5.0, 4.0),
            via_grid=(4, 3),
            edge_margin=edge_margin,
            via_pad_diameter=via_pad_diameter,
        )

        self.assertEqual(len(positions), 12)
        xs = sorted({x for x, _ in positions})
        ys = sorted({y for _, y in positions})
        for left, right in zip(xs, reversed(xs)):
            self.assertAlmostEqual(left, -right)
        for bottom, top in zip(ys, reversed(ys)):
            self.assertAlmostEqual(bottom, -top)
        self.assertAlmostEqual(
            5.0 / 2.0 - max(xs) - via_pad_diameter / 2.0, edge_margin
        )
        self.assertAlmostEqual(
            4.0 / 2.0 - max(ys) - via_pad_diameter / 2.0, edge_margin
        )

    def test_one_via_is_centered(self) -> None:
        self.assertEqual(
            grid_thermal_via_positions(
                ep_size=(2.0, 2.0),
                via_grid=(1, 1),
                edge_margin=0.2,
                via_pad_diameter=0.4,
            ),
            [(0.0, 0.0)],
        )

    def test_too_small_exposed_pad_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "too small"):
            grid_thermal_via_positions(
                ep_size=(0.9, 2.0),
                via_grid=(2, 2),
                edge_margin=0.3,
                via_pad_diameter=0.4,
            )


class OpeningTests(unittest.TestCase):
    ep_size = (5.0, 5.0)
    positions = grid_thermal_via_positions(
        ep_size=ep_size,
        via_grid=(2, 2),
        edge_margin=0.7,
        via_pad_diameter=0.4,
    )

    def opening(self, *, fillet_radius: float):
        return (
            soldermask_thermal_pad_opening(
                ep_size=self.ep_size,
                via_positions=self.positions,
                via_pad_diameter=0.4,
                min_mask_bridge=0.2,
                mask_expansion=0.15,
                fillet_radius=fillet_radius,
            )
            .to_shapely()
            .g
        )

    def test_opening_is_smaller_polygonal_geometry(self) -> None:
        opening = self.opening(fillet_radius=0.0)

        self.assertIn(opening.geom_type, ("Polygon", "MultiPolygon"))
        self.assertLess(opening.area, self.ep_size[0] * self.ep_size[1])
        self.assertTrue(opening.is_valid)

    def test_webs_and_frame_enclose_all_cells(self) -> None:
        opening = self.opening(fillet_radius=0.0)
        cells = (
            list(opening.geoms) if isinstance(opening, MultiPolygon) else [opening]
        )

        self.assertEqual(len(cells), 9)
        half_width = self.ep_size[0] / 2.0
        half_height = self.ep_size[1] / 2.0
        for cell in cells:
            min_x, min_y, max_x, max_y = cell.bounds
            self.assertGreater(min_x, -half_width)
            self.assertGreater(min_y, -half_height)
            self.assertLess(max_x, half_width)
            self.assertLess(max_y, half_height)

    def test_via_centers_are_under_mask_dams(self) -> None:
        import shapely

        opening = self.opening(fillet_radius=0.0)
        for position in self.positions:
            self.assertFalse(opening.covers(shapely.Point(position)))

    def test_fillet_off_preserves_raw_cells(self) -> None:
        raw = self.opening(fillet_radius=0.0)

        self.assertIsInstance(raw, MultiPolygon)
        assert isinstance(raw, MultiPolygon)
        self.assertEqual(len(raw.geoms), 9)

    def test_fillet_on_rounds_cells_without_invalidating_them(self) -> None:
        raw = self.opening(fillet_radius=0.0)
        filleted = self.opening(fillet_radius=0.08)

        self.assertTrue(filleted.is_valid)
        self.assertFalse(filleted.is_empty)
        self.assertLess(filleted.area, raw.area)

    def test_config_reuses_opening_for_mask_and_paste(self) -> None:
        config = soldermask_defined_thermal_pad_config(
            ep_size=self.ep_size,
            via_positions=self.positions,
            via_pad_diameter=0.4,
            min_mask_bridge=0.2,
            mask_expansion=0.15,
            fillet_radius=0.0,
        )

        self.assertIs(config.soldermask, config.paste)


if __name__ == "__main__":
    unittest.main(verbosity=2)
