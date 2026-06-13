# ARCHITECTURE.md Template

Copy this into the project root alongside PLAN.md. The orchestrator maintains this file to give sub-agents the big picture of the design.

---

```markdown
# Architecture: [Project Name]

## Module Hierarchy

```
[project_name]/
├── substrate.py          # Substrate definition (or predefined import)
├── components/
│   ├── [ic_name].py      # One file per component or family
│   └── ...
├── circuits/
│   ├── power/
│   │   └── [rail_name].py    # One per power rail or power group
│   ├── [interface_name].py   # One per interface circuit
│   └── ...
├── constraints/
│   └── [protocol].py     # SI constraint classes per protocol
└── main.py               # Top-level assembly
```

## Power Tree

Trace power from input through every regulator to every load. Include voltage, current, noise, and sequencing.

| Rail | Voltage | Source | Regulator | Type | Load | Current | Noise Req | Sequence |
|------|---------|--------|-----------|------|------|---------|-----------|----------|
| VIN | 5-20V | USB PD / barrel jack | — | Input | — | — | — | — |
| VCC_CORE | 1.2V | VIN | TPS62933 | Buck | MCU core | 500mA | <30mV ripple | 1st |
| VCC_IO | 3.3V | VIN | LM1117 | LDO | MCU IO, sensors | 300mA | <10mV ripple | 2nd (after core) |
| VCC_ANA | 3.3V | VCC_IO | Ferrite + LC filter | Filter | ADC VREF | 50mA | <1mV ripple | After VCC_IO |

### Sequencing Requirements
- [Document which rails must come up before others and why]
- [Document any enable-chain or PGOOD-chain dependencies]

### Thermal Notes
- [Document any regulators with tight thermal budgets]
- [P_dissipation = (Vin - Vout) * I for LDOs; check efficiency curves for switchers]

## Interface Map

Document every interface between components, the protocol, and SI constraints needed.

| Interface | From | To | Protocol | Speed | SI Constrained | Impedance | Clock Source |
|-----------|------|----|----------|-------|----------------|-----------|--------------|
| USB | MCU USB_DP/DM | Connector J1 | USB 2.0 HS | 480Mbps | Yes | 90 ohm diff | MCU PLL |
| I2C_SENSOR | MCU I2C1 | Sensor U3 | I2C | 400kHz | No | — | MCU |
| SPI_FLASH | MCU SPI2 | Flash U4 | SPI | 50MHz | No | — | MCU |
| DDR5 | FPGA bank A | Memory U2 | DDR5-4800 | 4800MT/s | Yes | 40/80 ohm | FPGA PLL |

### Clock Distribution
- [List any shared clock requirements — e.g., PCIe REFCLK to all endpoints]
- [Jitter budget for each clock domain if applicable]

## Board

- **Dimensions:** [width x height mm, or "defined by DXF: path/to/outline.dxf"]
- **Layers:** [count]
- **Material:** [FR-4 / Megtron 6 / Rogers / etc.]
- **Fab house:** [JLCPCB / custom / TBD]
- **Substrate:** [predefined class name or "custom — see substrate.py"]

### Mechanical Constraints
- [Mounting holes: locations, sizes]
- [Keepout zones: under antenna, near connectors]
- [Height restrictions: component side, bottom side]
- [Board outline source: DXF file path, or dimensions]

## Voltage Domains

List every distinct voltage domain and which components/pins operate in each. This helps catch level-shifting issues.

| Domain | Voltage | Components/Pins |
|--------|---------|-----------------|
| 3.3V | 3.3V | MCU IO, sensor VCC, I2C pull-ups, SPI |
| 1.2V | 1.2V | MCU core |
| VBUS | 5-20V (variable) | USB connector VBUS, PD controller VIN |

## Object-Hierarchy Decisions

For parametric / generator subsystems (BGA ballout, deskew geometry, antipad fence, N-lane fanout, per-layer table, repeating-block scene graph), commit to the object shape before sub-agents write code. 3–5 lines per major parametric subsystem. The point is to make the structural commitment explicit so that the anti-string-hacking rules in `jitx/SKILL.md` Don'ts have something concrete to enforce.

Example entries (delete this example, fill in for the actual design):

- **BGA escape (`circuits/bga_escape.py`):** 7 differential lanes modeled as `self.lanes: list[EscapeLane]` where `EscapeLane` is a frozen dataclass `{tx_pair: DiffPair, via: Via, antipad: KeepOut, fence: Pour}`. Ballout positions, via choices, and antipad geometry are derived from substrate constants and lane index — no string-keyed lookup tables. No sibling `TX_b0..TX_b6` attributes.
- **Substrate via map (`substrate.py`):** `Substrate.via[(layer_a, layer_b)]` owns the layer-pair → Via mapping. Design code queries this; no design-level `_SIGNAL_LAYER_TO_VIA` table.
- **Deskew geometry (`circuits/deskew.py`):** Parameterized by one knob `theta_exit_deg`; emits a typed `DeskewBuild` dataclass. No intermediate "spec" records.

Subsystems that are *not* parametric (one MCU, one buck regulator, one ground pour) do not need an entry — `list`-of-things only matters when N > 1 and the things are siblings.

## Design Notes

[Any non-obvious design decisions, tradeoffs, or constraints that sub-agents should know about. Examples:]
- [Mixed-signal ground strategy: unified ground plane with careful component placement, not split ground]
- [Thermal constraint: buck converter must be near board edge for heat dissipation]
- [EMI constraint: USB connector needs ESD protection within 10mm of connector]
```
