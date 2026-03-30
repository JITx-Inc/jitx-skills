# Parts Sourcing and Footprint Conversion

Optional integration for choosing in-stock parts and converting non-standard footprints to JITX. This is NOT required — designs can use any parts with manual datasheet-driven modeling. When available, these tools accelerate Phase 0 architecture decisions and reduce manual footprint work for non-standard packages.

## When to Use

- **Architecture phase**: search for in-stock parts to guide component selection
- **Reference circuits**: find how real boards use a specific IC (decoupling, pin connections)
- **Design rules**: look up best practices for LDOs, USB, ESD, etc.
- **Non-standard footprints**: pull KiCad footprints for connectors or unusual packages and convert to JITX

## Available Tools (via pcbparts MCP)

These tools are available when the `pcbparts` MCP server is configured. If not present, skip this workflow and use datasheets directly.

### Part Search: `jlc_search`

Primary search tool. Fast, parametric, searches JLCPCB in-stock inventory.

```
jlc_search(query="STM32F103 LQFP-48", limit=5)
jlc_search(query="3.3V LDO SOT-23 500mA", sort_by="stock")
jlc_search(query="100nF 25V 0402 capacitor")
jlc_search(query="USB-C 16pin connector SMD")
```

Returns: MPN, manufacturer, package, stock, price, specs, LCSC code.

Use `jlc_search_help` to browse categories and discover filterable attributes.

### Reference Boards: `board_search` + `board_get`

Find real-world open-source designs using a specific IC. Two-step workflow:

```
board_search(component="STM32F103")           # find boards using this IC
board_get(slug="crazyflie", focus="STM32F103") # see pin-by-pin neighborhood
```

Returns: decoupling strategy, pull-up/pull-down networks, power topology, cross-board consensus when multiple boards use the same IC.

Use during Phase 2 circuit design to see how experienced designers wire an IC.

### Design Rules: `get_design_rules`

Curated best practices for PCB design topics.

```
get_design_rules("ldo")     # LDO stability, thermal, PSRR
get_design_rules("usb")     # USB routing, CC resistors, power delivery
get_design_rules("esd")     # ESD protection strategies
get_design_rules("esp32")   # ESP32 strapping pins, RF layout
get_design_rules("")         # full index of all topics
```

Use during acceptance review to verify circuit design against known best practices.

### Pinout Data: `jlc_get_pinout`

Get pin names and numbers from EasyEDA symbol data. Useful for verifying pin mapping without reading the full datasheet.

```
jlc_get_pinout(lcsc="C8734")  # STM32F103C8T6 pins
```

### KiCad Footprint Download: `cse_get_kicad`

Download KiCad symbol and footprint files for a part. Slow (~45s) — only use for non-standard packages where the standard JITX landpattern generators don't apply.

```
cse_get_kicad(query="USB-C connector MPN")
```

Returns: raw `.kicad_sym` and `.kicad_mod` file contents.

### Sensor Recommendation: `sensor_recommend`

Find sensor ICs by what they measure, protocol, or platform.

```
sensor_recommend(measure="temperature", protocol="i2c")
```

## Phase 0: Architecture-Driven Part Selection

During Phase 0 (requirements + architecture), optionally use part search to make informed choices:

1. **Identify functional requirements** (MCU with USB and SPI, 3.3V LDO at 500mA, etc.)
2. **Search for candidates**: `jlc_search` with parametric filters
3. **Prefer**: high stock, basic/preferred library type (lower assembly fee), known manufacturers
4. **Record chosen parts** in PLAN.md task descriptions with MPN, LCSC code, package, and key specs
5. **Find reference circuits**: `board_search` for the chosen IC, then `board_get` with focus to see real wiring

This step is optional. The orchestrator can skip it if the user has already specified parts, or if no parts database is available. The project builder flow works the same either way — parts sourcing just informs the architecture, it doesn't change the phases.

## KiCad-to-JITX Footprint Conversion

### When to Convert

Only convert KiCad footprints for **non-standard packages** where JITX's built-in landpattern generators don't work:

- Connectors (USB-C, QSFP, board-to-board, card edge)
- RF modules (antenna footprints, shielding cans)
- Unusual mechanical packages (custom thermal pads, non-rectangular outlines)
- Parts with asymmetric or irregular pad layouts

### When NOT to Convert

Use JITX standard landpattern generators for all standard packages:

| Package | Generator | Notes |
|---------|-----------|-------|
| QFN | `QFN(...)` | 4-sided no-lead |
| SON/DFN | `SON(...)` | 2-sided no-lead |
| SOIC | `SOIC(...)` | Gull-wing |
| SOT-23/SOT-223 | Standard library | From jitxlib |
| QFP | `QFP(...)` | 4-sided gull-wing |
| BGA | `BGA(...)` | Ball grid array |

Always use `BoxSymbol` for schematic symbols. Do not attempt to convert KiCad schematic symbol graphics — BoxSymbol with proper port grouping is cleaner and more maintainable.

### Conversion Process

When you have a KiCad `.kicad_mod` footprint:

1. **Parse the pad definitions**: extract pad name, position (x, y), size (width, height), shape (rect, circle, oval, roundrect), layers, and drill (if through-hole).

2. **Map to JITX landpattern pads**: create a `Landpattern` with pads at the extracted positions. Use JITX pad constructors:
   - SMD rectangular: `smd_pad(width, height)` at `pose(x, y, rotation)`
   - SMD circular: `bga_pad(diameter)` at position
   - Through-hole: `th_pad(drill, pad_diameter)` at position
   - Oval/elongated: `smd_pad(width, height)` with appropriate dimensions

3. **Create the Component class**: define ports matching the KiCad symbol pin names, create the landpattern, and build a `BoxSymbol`. Use `PadMapping` to map pad names to ports.

4. **Verify with test harness**: build the component to confirm pad positions and mapping.

### Example: Converting a Simple Connector

Given KiCad pads:
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

For complex connectors (USB-C with 16+ pads, shield tabs, mounting posts), the same process applies — just more pads. Group related ports logically (DP/DM for USB data, CC1/CC2 for configuration, VBUS/GND for power, shield for shielding tabs).
