"""Check the count law against recorded measurements without starting a runtime."""

import unittest

from check_stitch_via import (
    POUR_SIZE,
    VARIANTS,
    expected_grid_count,
)
from jitx.test import TestCase
from jitxlib.jlcpcb import JLC04161H_7628


class StitchGridCountTests(TestCase):
    def test_reference_variants(self):
        for variant, (design_class, measured) in VARIANTS.items():
            with self.subTest(variant=variant):
                design = design_class()
                if measured == 0:
                    self.assertEqual(design.rules, [])
                    continue
                self.assertEqual(len(design.rules), 1)
                stitch = design.rules[0].stitch_via_constraint
                assert stitch is not None
                pad_diameter = stitch.definition.diameter
                assert isinstance(pad_diameter, float)
                self.assertEqual(
                    expected_grid_count(
                        POUR_SIZE,
                        stitch.pattern.pitch,
                        stitch.pattern.inset,
                        pad_diameter,
                    ),
                    measured,
                )

    def test_original_measurements(self):
        # Source: jitxexamples.patterns.stitch_via module docstring.
        pad_diameter = JLC04161H_7628.StdViaPreferred.diameter
        assert isinstance(pad_diameter, float)
        for span, pitch, inset, measured in (
            (8.0, 2.0, 0.5, 9),
            (8.0, 1.5, 0.5, 25),
            (10.0, 2.0, 0.5, 25),
            (8.0, 2.0, 1.5, 9),
        ):
            with self.subTest(span=span, pitch=pitch, inset=inset):
                self.assertEqual(
                    expected_grid_count(span, pitch, inset, pad_diameter), measured
                )

    def test_discriminating_measurements(self):
        # Same source, follow-up measurements using StdViaTentedFilled.
        # The first seven rows distinguish the pad-edge law from the center law.
        pad_diameter = JLC04161H_7628.StdViaTentedFilled.diameter
        assert isinstance(pad_diameter, float)
        for span, pitch, inset, measured in (
            (1.90, 0.540, 0.315, 1),
            (1.90, 0.540, 0.225, 1),
            (1.90, 0.600, 0.300, 1),
            (1.90, 0.500, 0.300, 1),
            (1.90, 0.450, 0.300, 1),
            (1.90, 0.635, 0.315, 1),
            (3.00, 0.540, 0.315, 9),
            (8.00, 2.000, 0.500, 9),
        ):
            with self.subTest(span=span, pitch=pitch, inset=inset):
                self.assertEqual(
                    expected_grid_count(span, pitch, inset, pad_diameter), measured
                )


if __name__ == "__main__":
    unittest.main()
