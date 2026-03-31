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

### Conversion: Use the `kicad_to_jitx.py` Script

Do NOT manually write pad positions from KiCad data — use the conversion script. It deterministically parses the S-expression format and generates correct JITX code with proper Y-axis inversion, pad grouping, and BoxSymbol layout.

```bash
# From a .kicad_mod file
python scripts/kicad_to_jitx.py connector.kicad_mod --class-name USB_C_16P

# With metadata
python scripts/kicad_to_jitx.py connector.kicad_mod \
    --class-name USB_C_16P \
    --manufacturer "Amphenol" --mpn "12401610E4#2A" \
    -o src/myproject/components/connectors/usb_c_16p.py

# From MCP tool output (piped)
echo '<kicad_mod content>' | python scripts/kicad_to_jitx.py --stdin --class-name USB_C_16P

# Debug: inspect parsed pads as JSON
python scripts/kicad_to_jitx.py connector.kicad_mod --dump-pads
```

The script handles:
- SMD, through-hole, and non-plated pads (all shapes: rect, oval, circle, roundrect, custom)
- Pad rotation, duplicate pad names (USB-C A/B rows), shield/mounting pads
- KiCad Y-axis inversion (KiCad Y+ = down, JITX Y+ = up)
- Automatic BoxSymbol with power up, ground down, signals left, shield right
- PadMapping linking ports to landpattern pads

Copy `scripts/kicad_to_jitx.py` from this skill into the project if sub-agents need to run it.

After generation, review the output and build-test the component. The script produces mechanically correct geometry but you may want to rename ports for clarity (e.g., group USB data pins into DP/DM bundles).
