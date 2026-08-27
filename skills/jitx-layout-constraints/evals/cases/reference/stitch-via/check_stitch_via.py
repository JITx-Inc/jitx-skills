"""Submit, capture, and count computed stitch vias for one reference variant."""

from __future__ import annotations

import argparse

import jitx
from jitx.design import Design
from jitx.via import Via

try:
    from .stitch_via_design import (
        POUR_SIZE,
        STITCH_INSET,
        STITCH_PITCH,
        ControlNoRuleDesign,
        DirectAttributeViaDesign,
        MixinViaDesign,
        ModuleScopeViaDesign,
    )
except ImportError:
    from stitch_via_design import (  # type: ignore[no-redef]
        POUR_SIZE,
        STITCH_INSET,
        STITCH_PITCH,
        ControlNoRuleDesign,
        DirectAttributeViaDesign,
        MixinViaDesign,
        ModuleScopeViaDesign,
    )


def expected_grid_count(pour_size: float, pitch: float, inset: float) -> int:
    """Vias per axis on a square grid inset from the pour boundary, squared."""
    per_axis = int((pour_size - 2.0 * inset) // pitch) + 1
    return per_axis * per_axis


EXPECTED = expected_grid_count(POUR_SIZE, STITCH_PITCH, STITCH_INSET)  # 9 for an 8 mm pour, 2 mm pitch, 0.5 mm inset

VARIANTS: dict[str, tuple[type[Design], int]] = {
    "mixin": (MixinViaDesign, EXPECTED),
    "direct": (DirectAttributeViaDesign, EXPECTED),
    "module": (ModuleScopeViaDesign, EXPECTED),
    "control": (ControlNoRuleDesign, 0),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=VARIANTS)
    args = parser.parse_args()
    design_class, expected = VARIANTS[args.variant]

    with jitx.runtime as runtime:
        runtime_design = runtime.submit(design_class)
        runtime_design.capture()
        vias = list(runtime_design.query(Via))

    status = "PASS" if len(vias) == expected else "FAIL"
    print(f"{status} variant={args.variant} via_count={len(vias)} expected={expected}")
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
