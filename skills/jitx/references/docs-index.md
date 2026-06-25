# JITX Documentation Index

Base URL: `https://docs.jitx.com/en/latest/`

## Quick Lookup by Task

| Task | Doc Page |
|------|----------|
| Set up new project | `getting-started/creating-new-project.html` |
| Understand design hierarchy | `essentials/design/design-hierarchy.html` |
| Learn port/pin/pad relationships | `essentials/design/object-relationships.html` |
| Configure pin assignment | `essentials/design/pin_assignment.html` |
| Set up board substrate/stackup | `essentials/design/substrate.html` |
| Query design programmatically | `essentials/design/introspection.html` |
| Build recursive circuits | `essentials/design/recursive_designs.html` |
| Avoid common mistakes | `essentials/design/footguns.html` |
| Place components (kinematic tree) | `essentials/physical_design/kinematic-tree.html` |
| Route traces (autorouter) | `essentials/physical_design/autorouter.html` |
| Add copper pours | `essentials/physical_design/pours.html` |
| Define transmission lines | `essentials/SI/topology.html` |
| Set SI constraints | `essentials/SI/constraints.html` |
| View keyboard shortcuts | `user-interface/ui-commands/hotkeys.html` |

## API Reference

Core modules at `api/jitx.<module>.html`:

| Module | Purpose |
|--------|---------|
| `circuit` | Circuit class, connections, net operators |
| `component` | Component class, MPN, reference designator |
| `board` | Board definition and properties |
| `design` | Top-level design entry point |
| `landpattern` | Landpattern definition |
| `symbol` | Schematic symbol definition |
| `net` | Net and net-class definitions |
| `constraints` | Design rules and constraints |
| `si` | Signal integrity definitions |
| `stackup` | Layer stackup configuration |
| `substrate` | Substrate and material properties |
| `placement` | Component placement control |
| `copper` | Copper shapes and pours |
| `via` | Via definitions |
| `anchor` | Anchor points for placement |
| `transform` | Geometric transformations |
| `shapes` | Shape primitives (`shapes/primitive.html`, `shapes/composites.html`) |
| `units` | Unit handling (mm, mil, etc.) |
| `toleranced` | Toleranced values |
| `inspect` | Design introspection utilities |
| `property` | Property system |
| `decorators` | Python decorators (@provide, etc.) |

## Standard Library (jitxlib)

Base: `jitxlib-standard/jitxlib.<module>.html`

### Landpattern Generators

| Generator | URL |
|-----------|-----|
| BGA | `jitxlib.landpatterns.generators.bga.html` |
| QFN | `jitxlib.landpatterns.generators.qfn.html` |
| QFP | `jitxlib.landpatterns.generators.qfp.html` |
| SOIC | `jitxlib.landpatterns.generators.soic.html` |
| SON | `jitxlib.landpatterns.generators.son.html` |
| SOP | `jitxlib.landpatterns.generators.sop.html` |
| SOT | `jitxlib.landpatterns.generators.sot.html` |
| Header | `jitxlib.landpatterns.generators.header.html` |
| Two-pin SMT | `jitxlib.landpatterns.twopin.smt.html` |
| Two-pin Axial | `jitxlib.landpatterns.twopin.axial.html` |
| Two-pin Molded | `jitxlib.landpatterns.twopin.molded.html` |

### Landpattern Support

| Topic | URL |
|-------|-----|
| Lead fillets (IPC) | `jitxlib.landpatterns.leads.fillets.html` |
| Protrusion types | `jitxlib.landpatterns.leads.protrusions.html` |
| Silkscreen outlines | `jitxlib.landpatterns.silkscreen.outlines.html` |
| Silkscreen labels | `jitxlib.landpatterns.silkscreen.labels.html` |
| Pin 1 marker | `jitxlib.landpatterns.silkscreen.marker.html` |
| Courtyard | `jitxlib.landpatterns.courtyard.html` |
| Pads | `jitxlib.landpatterns.pads.html` |
| IPC standards | `jitxlib.landpatterns.ipc.html` |

### Protocols

| Protocol | URL |
|----------|-----|
| USB | `jitxlib.protocols.usb.html` |
| Ethernet MDI | `jitxlib.protocols.ethernet.mdi.html` |
| Ethernet MII/RMII/RGMII | `jitxlib.protocols.ethernet.mii.html` |
| DisplayPort | `jitxlib.protocols.displayport.html` |
| Serial (UART, SPI, I2C) | `jitxlib.protocols.serial.html` |

### Symbols

| Symbol Type | URL |
|-------------|-----|
| Resistor | `jitxlib.symbols.resistor.resistor.html` |
| Capacitor | `jitxlib.symbols.capacitor.capacitor.html` |
| Inductor | `jitxlib.symbols.inductor.inductor.html` |
| Op-amp | `jitxlib.symbols.opamp.html` |
| Logic gates | `jitxlib.symbols.logic.html` |
| Box symbol | `jitxlib.symbols.box.html` |
| Power/Ground | `jitxlib.symbols.net_symbols.html` |

## Libraries (jitxlib)

Base: `jitxlib/jitxlib.<module>.html`

| Library | URL | Purpose |
|---------|-----|---------|
| JLCPCB stackups | `jitxlib.jlcpcb.html` | Pre-defined JLCPCB stackups |
| JLCPCB rules | `jitxlib.jlcpcb.rules.html` | Manufacturing rules |
| JLCPCB vias | `jitxlib.jlcpcb.vias.html` | Via definitions |
| Parts query | `jitxlib.parts.query_api.html` | Parts database API |
| Voltage divider | `jitxlib.voltage_divider.html` | Voltage divider solver |

## Example Components

Base: `jitxexamples/jitxexamples.components.<category>.html`

| Category | Key Examples |
|----------|--------------|
| MCUs | `nordic_NRF52840_QIAA_R`, `raspberry_pi_RP2040` |
| Power regulators | `texas_instruments_LM1117MP`, `AP2125K_2_8TRG1` |
| Switchmode power | `texas_instruments_TPS62933DRLR` |
| Op-amps | `texas_instruments_OPA189`, `stmicroelectronics_TS971ILT` |
| N-ch FETs | `BSS138`, `BSN20` |
| P-ch FETs | `AO3401A`, `AO6409` |
| Connectors | `molex_2012670005`, `hirose_electric_co_ltd_U_FL_R_SMT_10` |
| LEDs | `WS2816C_2121`, `KT_0603R` |
| Crystals | `yangxing_tech_X322512MSB4SI` |
| Flash | `winbond_W25Q128JVSIQ` |
| Sensors | `stmicroelectronics_LIS3DHTR`, `VL53L0CXV0DH_1` |

## User Interface Commands

### Board Commands (`user-interface/ui-commands/board/`)
`route`, `unroute`, `via`, `auto-via`, `delete`, `rotate`, `flip`, `align`, `distribute`, `layer`, `mode`, `select-nets`, `select-expand`

### Schematic Commands (`user-interface/ui-commands/schematic/`)
`add-page`, `page`, `rotate`, `flip`, `merge`, `split`, `net-merge`, `net-split`, `group-merge`, `group-split`, `replicate`

### General Commands (`user-interface/ui-commands/general/`)
`find`, `select`, `pan`, `zoom`, `undo`, `bind`, `open`, `toggle`

## Search Patterns

When looking for specific topics:

- **"How do I [action]?"** → Check Essentials section first
- **"What parameters does [class] have?"** → API Reference
- **"How do I create a [package] landpattern?"** → Landpattern Generators
- **"How do I connect [protocol]?"** → Protocols section
- **"Show me an example of [component type]"** → Example Components
- **"What's the keyboard shortcut for [action]?"** → `hotkeys.html`
- **"How do I [UI action] in the board/schematic?"** → UI Commands
