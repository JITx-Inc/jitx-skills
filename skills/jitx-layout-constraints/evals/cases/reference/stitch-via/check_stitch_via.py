"""Submit, capture, and count computed stitch vias for one reference variant."""

from __future__ import annotations

import argparse

import jitx
from jitx.design import Design
from jitx.via import Via

try:
    from .stitch_via_design import (
        DirectAttributeViaDesign,
        MixinViaDesign,
        ModuleScopeViaDesign,
    )
except ImportError:
    from stitch_via_design import (
        DirectAttributeViaDesign,
        MixinViaDesign,
        ModuleScopeViaDesign,
    )

VARIANTS: dict[str, type[Design]] = {
    "mixin": MixinViaDesign,
    "direct": DirectAttributeViaDesign,
    "module": ModuleScopeViaDesign,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=VARIANTS)
    args = parser.parse_args()
    design_class = VARIANTS[args.variant]

    with jitx.runtime as runtime:
        runtime_design = runtime.submit(design_class)
        runtime_design.capture()
        vias = list(runtime_design.query(Via))

    print(f"variant={args.variant} status=ok via_count={len(vias)}")


if __name__ == "__main__":
    main()
