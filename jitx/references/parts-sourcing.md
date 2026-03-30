# Parts Sourcing and Footprint Conversion

Optional integration for verifying sourcing of chosen parts and obtaining footprint data. The MCP tools are dumb data lookups — they do NOT make engineering decisions. Claude selects parts based on electrical requirements and tradeoffs first, then optionally checks sourcing availability.

## Caution

The pcbparts MCP server also exposes reference board search, design rules, and sensor recommendation tools. **Do NOT use these.** The reference board data is contaminated with hobby-grade Adafruit/SparkFun designs that are not appropriate for professional hardware. Design rules and circuit topology come from Claude's own engineering knowledge and the domain checklists — not from an external database. Only use the two tools listed below.

## Available Tools (via pcbparts MCP)

Available when the `pcbparts` MCP server is configured. If not present, skip and use datasheets directly.

### Sourcing Check: `jlc_search`

Verify that a specific part is in stock. Search by **exact MPN only** — do not use semantic/natural language queries like "3.3V LDO" or "USB-C connector". Claude already knows what part it wants; this tool just checks if JLCPCB has it.

```
jlc_search(query="STM32F103C8T6")
jlc_search(query="ME6211C33M5G-N")
jlc_search(query="AO3400A")
```

Returns: MPN, manufacturer, package, stock, price, LCSC code.

Do NOT use: `jlc_search(query="3.3V LDO SOT-23 500mA")` — this is a semantic search that returns whatever the database ranks highest, not what the design needs.

### KiCad Footprint Download: `cse_get_kicad`

Download KiCad footprint for a part. Slow (~45s) — only use for non-standard packages where JITX landpattern generators don't apply.

```
cse_get_kicad(query="USB-C connector MPN")
```

Returns: raw `.kicad_sym` and `.kicad_mod` file contents.

## Phase 0: Part Selection

Claude drives part selection based on engineering judgment. The MCP is a lookup tool, not a decision maker.

1. **Claude proposes ideal parts** based on the design requirements: voltage/current ratings, package thermal limits, peripheral set, interface support, proven reliability, datasheet quality. Weigh tradeoffs (dropout vs efficiency, pin count vs board area, feature set vs complexity).
2. **Optionally verify sourcing**: use `jlc_search` to check if the proposed parts are in stock and at reasonable cost. If a preferred part is unavailable or prohibitively expensive, Claude proposes an alternative with equivalent specs — do not let the search results dictate the architecture.
3. **Record chosen parts** in PLAN.md task descriptions with MPN, package, key specs, and rationale for the selection.

The search tool is a filter, not an oracle. Never pick a part just because it has high stock or low price — pick the right part for the design, then check if it's sourceable.

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
