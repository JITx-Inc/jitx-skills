"""
Texas Instruments LM1117MP Low Dropout Linear Regulator

Component definition for the Texas Instruments LM1117 series
low dropout linear regulator in WSON-8 package.
"""

import jitx
from jitx.net import Port
from jitx.shapes.composites import rectangle
from jitxlib.landpatterns.generators.son import SON, SONLead
from jitxlib.landpatterns.leads import LeadProfile
from jitxlib.landpatterns.package import RectanglePackage
from jitxlib.landpatterns.pads import SMDPadConfig, WindowSubdivide
from jitxlib.symbols.box import BoxSymbol, Column, PinGroup, Row


class LM1117MP(jitx.Component):
    mpn = "LM1117MP"
    manufacturer = "Texas Instruments"
    reference_designator_prefix = "U"
    datasheet = "https://www.ti.com/lit/ds/symlink/lm1117.pdf"

    ADJ = Port()
    OUT = Port()
    IN = Port()

    landpattern = (
        SON(num_leads=8)
        .lead_profile(
            LeadProfile(
                span=jitx.Toleranced.min_max(3.45, 3.65),
                pitch=0.8,
                type=SONLead(
                    length=jitx.Toleranced.min_max(0.4, 0.6),
                    width=jitx.Toleranced.min_max(0.25, 0.35),
                ),
            )
        )
        .package_body(
            RectanglePackage(
                width=jitx.Toleranced.exact(4.0),
                length=jitx.Toleranced.exact(4.0),
                height=jitx.Toleranced.min_max(0.0, 0.8),
            )
        )
        .thermal_pad(
            shape=rectangle(2.2, 3),
            config=SMDPadConfig(paste=WindowSubdivide(padding=0.05)),
        )
    )

    symbol = BoxSymbol(
        rows=Row(
            left=PinGroup(IN),
            right=PinGroup(OUT),
        ),
        columns=Column(
            down=PinGroup(ADJ),
        ),
    )

    mappings = [
        jitx.PadMapping(
            {
                ADJ: landpattern.p[1],
                IN: [landpattern.p[2], landpattern.p[3], landpattern.p[4]],
                OUT: [
                    landpattern.p[5],
                    landpattern.p[6],
                    landpattern.p[7],
                    landpattern.thermal_pads[0],
                ],
            }
        )
    ]


Device: type[LM1117MP] = LM1117MP
