# Parts Sourcing and Footprint Conversion

Optional integration for choosing in-stock parts and obtaining footprint/pinout data. This is NOT required — designs can use any parts with manual datasheet-driven modeling. When available, these tools accelerate Phase 0 part selection and reduce manual footprint work for non-standard packages.

## Available Tools (via pcbparts MCP)

Available when the `pcbparts` MCP server is configured. If not present, skip and use datasheets directly.

### Part Search: `jlc_search`

Primary tool. Fast parametric search of JLCPCB in-stock inventory.

```
jlc_search(query="STM32F103 LQFP-48", limit=5)
jlc_search(query="3.3V LDO SOT-23 500mA", sort_by="stock")
jlc_search(query="USB-C 16pin connector SMD")
```

Returns: MPN, manufacturer, package, stock, price, specs, LCSC code.

Use `jlc_search_help` to browse categories and discover filterable attributes.

### Pinout Data: `jlc_get_pinout`

Pin names and numbers from EasyEDA symbol data.

```
jlc_get_pinout(lcsc="C8734")  # STM32F103C8T6 pins
```

### KiCad Footprint Download: `cse_get_kicad`

Download KiCad footprint for a part. Slow (~45s) — only use for non-standard packages where JITX landpattern generators don't apply.

```
cse_get_kicad(query="USB-C connector MPN")
```

Returns: raw `.kicad_sym` and `.kicad_mod` file contents.

## Phase 0: Part Selection

During Phase 0, optionally use `jlc_search` to choose parts:

1. **Search for candidates** with parametric filters matching functional requirements
2. **Prefer**: high stock, basic/preferred library type, known manufacturers
3. **Record chosen parts** in PLAN.md task descriptions with MPN, LCSC code, package, and key specs

Optional and swappable — the project builder flow works identically without it.

## KiCad-to-JITX Footprint Conversion

### When to Convert

Only for **non-standard packages** where JITX built-in generators don't work:

- Connectors (USB-C, QSFP, board-to-board, card edge)
- RF modules (antenna footprints, shielding cans)
- Unusual mechanical packages (custom thermal pads, non-rectangular outlines)
- Parts with asymmetric or irregular pad layouts

### When NOT to Convert

Use JITX standard landpattern generators for all standard packages:

| Package | Generator |
|---------|-----------|
| QFN | `QFN(...)` |
| SON/DFN | `SON(...)` |
| SOIC | `SOIC(...)` |
| SOT-23/SOT-223 | jitxlib standard library |
| QFP | `QFP(...)` |
| BGA | `BGA(...)` |

Always use `BoxSymbol` for schematic symbols. Never convert KiCad symbol graphics.

### Conversion Process

From a KiCad `.kicad_mod` footprint:

1. **Parse pad definitions**: name, position (x, y), size (width, height), shape, drill (if through-hole)
2. **Map to JITX pads**:
   - SMD rectangular: `smd_pad(width, height)` at `pose(x, y, rotation)`
   - SMD circular: `bga_pad(diameter)` at position
   - Through-hole: `th_pad(drill, pad_diameter)` at position
3. **Build Component**: ports matching pin names, `Landpattern` with pads, `BoxSymbol`, `PadMapping`
4. **Test harness**: build to confirm pad positions and mapping

### Example

KiCad pads:
```
(pad "1" smd rect (at -2.5 0) (size 1.0 2.0) (layers "F.Cu" "F.Paste" "F.Mask"))
(pad "2" smd rect (at  0.0 0) (size 1.0 2.0) (layers "F.Cu" "F.Paste" "F.Mask"))
(pad "3" smd rect (at  2.5 0) (size 1.0 2.0) (layers "F.Cu" "F.Paste" "F.Mask"))
```

JITX equivalent:
```python
class MyConnector(Component):
    pin1 = Port()
    pin2 = Port()
    pin3 = Port()

    def __init__(self):
        self.landpattern = Landpattern(
            pads=[
                Pad("1", smd_pad(1.0, 2.0), pose(-2.5, 0.0)),
                Pad("2", smd_pad(1.0, 2.0), pose(0.0, 0.0)),
                Pad("3", smd_pad(1.0, 2.0), pose(2.5, 0.0)),
            ]
        )
        self.symbol = BoxSymbol(self)
        self.pad_mapping = PadMapping(
            mapping={
                "1": self.pin1,
                "2": self.pin2,
                "3": self.pin3,
            }
        )
```

For complex connectors (USB-C with 16+ pads, shield tabs, mounting posts), group related ports logically (DP/DM for data, CC1/CC2 for configuration, VBUS/GND for power, shield for shielding tabs).
