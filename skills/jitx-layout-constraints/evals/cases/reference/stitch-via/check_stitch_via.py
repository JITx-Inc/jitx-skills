"""Submit, capture, and count computed stitch vias for one reference variant."""

from __future__ import annotations

import argparse
from math import floor

from jitx.via import Via

import jitx

try:
    from .stitch_via_design import (
        POUR_SIZE,
        ControlNoRuleDesign,
        DirectAttributeViaDesign,
        MixinViaDesign,
        ModuleScopeViaDesign,
    )
except ImportError:
    from stitch_via_design import (  # type: ignore[no-redef]
        POUR_SIZE,
        ControlNoRuleDesign,
        DirectAttributeViaDesign,
        MixinViaDesign,
        ModuleScopeViaDesign,
    )


def expected_grid_count(
    pour_size: float, pitch: float, inset: float, pad_diameter: float
) -> int:
    """Vias per axis on a center-anchored square grid, squared.

    Measured on the 4.4.0 runtime, ``inset`` is the distance from the stitched
    region's boundary to the via pad edge, so the general
    count per axis is ``2 * floor((pour_size / 2 - inset - pad_diameter / 2) / pitch) + 1``.
    The runtime anchors one via on the region center and steps outward by whole
    pitches, so the count per axis is odd. Read ``pad_diameter`` from the
    selected via class, not its drill. No pad fits when the available radius
    is negative. Discriminating measurements are recorded in the
    ``jitxexamples.patterns.stitch_via`` module docstring.
    """
    available_radius = pour_size / 2.0 - inset - pad_diameter / 2.0
    if available_radius < 0:
        return 0
    rings = floor(available_radius / pitch)
    per_axis = 2 * rings + 1
    return per_axis * per_axis


# Measured counts in NOTES.md, independent of the helper under test.
StitchDesign = (
    MixinViaDesign
    | DirectAttributeViaDesign
    | ModuleScopeViaDesign
    | ControlNoRuleDesign
)
VARIANTS: dict[str, tuple[type[StitchDesign], int]] = {
    "mixin": (MixinViaDesign, 9),
    "direct": (DirectAttributeViaDesign, 9),
    "module": (ModuleScopeViaDesign, 9),
    "control": (ControlNoRuleDesign, 0),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=VARIANTS)
    args = parser.parse_args()
    design_class, expected = VARIANTS[args.variant]

    with jitx.runtime as runtime:
        runtime_design = runtime.submit(design_class)
        if runtime_design.root.rules:
            stitch = runtime_design.root.rules[0].stitch_via_constraint
            assert stitch is not None
            pad_diameter = stitch.definition.diameter
            if not isinstance(pad_diameter, float):
                raise TypeError("this reference requires a circular via pad diameter")
            predicted = expected_grid_count(
                POUR_SIZE, stitch.pattern.pitch, stitch.pattern.inset, pad_diameter
            )
            if predicted != expected:
                print(f"FAIL grid_count={predicted} measured_reference={expected}")
                raise SystemExit(1)
        runtime_design.capture()
        vias = list(runtime_design.query(Via))

    status = "PASS" if len(vias) == expected else "FAIL"
    print(f"{status} variant={args.variant} via_count={len(vias)} expected={expected}")
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
