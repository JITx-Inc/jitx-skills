# High-Speed Signal Integrity Reference

## When to read this

You are working on signals at ≥ 100 MHz fundamental: USB (any), Ethernet, PCIe, DDR / LPDDR, MIPI, DisplayPort, HDMI, SerDes, JESD204, clock distribution, crystals. Also read [`emc-esd.md`](emc-esd.md) for plane / return-path concerns and [`net-classes.md`](../net-classes.md) for the routing-structure mapping.

## Authoring-time targets

### Topology and constraints

- [ ] Differential pairs declared with `DiffPair` bundle, not parallel single-ended ports
- [ ] Topologies built with `>>` operator (not `+`), one node per IC-pin / in-line component
- [ ] AC-coupling caps and series resistors use `BridgingPinModel` so delay/loss propagates
- [ ] IC endpoints use `TerminatingPinModel`
- [ ] SI constraints applied at the **top-level design** with ground reference planes, never inside subcircuits; see `jitx-interconnect-constraints/SKILL.md` for exact API syntax
- [ ] Length-matching scope correct: per-DQS-group for DDR; per-pair for diff; per-bus for parallel

### Impedance and stackup

- [ ] Routing structure assigned for every impedance class in the design
- [ ] Substrate stackup verifies impedance achievable with chosen Dk and geometry
- [ ] Every signal layer has an adjacent ground reference plane (`HS_STACK_001`)
- [ ] RF or > 500 Mbps designs use ≥ 4 layers, 6 preferred (`HS_STACK_002`)
- [ ] Material specified for design class — controlled-Dk PCB for > 2 GHz; avoid standard FR-4 for multi-Gbps (`HS_MAT_001`, `HS_DIFF_004`)

### Termination

- [ ] Series termination at source for point-to-point clock signals (33 Ω typical) (`HS_CLK_001`)
- [ ] Parallel termination at receiver for transmission lines
- [ ] AC coupling at correct end for the protocol (USB3, PCIe TX side per spec)
- [ ] ODT enabled for DDR — verify in MCU/FPGA boot configuration

### Protocol-specifics

| Protocol | Diff impedance | Match constraint | Termination | Notes |
|---|---|---|---|---|
| USB 2.0 | 90 Ω | timing/skew constraint via SI skill | None (host pull-ups) | D+/D- ESD low-cap, ID pin for OTG |
| USB 3.x SS | 90 Ω | timing/skew + loss constraint via SI skill | AC coupling on TX | Low-cap TVS < 1 pF |
| PCIe Gen 2+ | 85 Ω | timing/skew + loss constraint via SI skill | AC coupling on TX | REFCLK shared across endpoints, PERST# |
| Ethernet RGMII | 50 Ω | bus timing/skew constraint via SI skill | Source termination | Magnetics + MDI termination |
| Ethernet 1000BASE-T | 100 Ω | pair timing/skew constraint via SI skill | Magnetics | Bob Smith terminations |
| DDR3/4 | 40/50 Ω SE, 80/100 Ω diff | per-byte-lane DQ↔DQS skew | ODT | VREF/VTT decoupling per `HS_DDR_002` |
| LPDDR4/5 | per spec | per-byte-lane DQ↔DQS skew | per spec | Diff strobes per byte lane |
| MIPI D-PHY | 100 Ω | intra-pair skew | At receiver | LP and HS modes |

Match constraints are applied as **timing skew** plus impedance/loss via the `jitx-interconnect-constraints` skill. JITX matches by timing, not by length; the routing-length figures sometimes quoted for these protocols are guidance only. Do not restate length tolerances here — define the timing constraint in the constraints layer.

## JITX implementation source

This file defines what must be constrained. The canonical "how" for `Topology`, `ConstrainDiffPair`, `ConstrainReferenceDifference`, `ReferencePlanes`, timing units, insertion loss, and `BridgingPinModel` / `TerminatingPinModel` patterns is `jitx-interconnect-constraints/SKILL.md`. Do not copy API snippets from here into designs; open that skill when writing constraints.

DDR DQ-to-DQS and bus-to-clock matching are timing constraints, not length-only specs; implement them through the SI skill's canonical patterns.

## Quantitative layout targets (waiting on introspection)

| Rule | Target | Introspection API needed |
|---|---|---|
| `HS_DIFF_001` | Diff pair over continuous reference plane (no splits) | `board.plane_continuity_under(net)` |
| `HS_DIFF_003` | Via stub < 5 mils for > 3 Gbps | `board.via_stub_length(via)` |
| `HS_DIFF_005` | ≥ 10–15 mils from board / plane edges | `board.distance_to_edge(net)` |
| `HS_DIFF_006` | Prefer inner-layer routing for diff pairs | `board.layer(net)` |
| `HS_SER_002` | ≤ 2 vias per high-speed serial trace | `board.via_count(net)` |
| `HS_XTAL_001` | Crystal within 10 mm of MCU | `board.distance(component, component)` |
| `HS_XTAL_002` | No vias on crystal traces (or symmetric on both) | `board.via_count(net)` |
| `HS_XTAL_003` | No pour or routing under crystal | `board.copper_under(component)` |
| `HS_XTAL_004` | Crystal load-cap GND returns directly to MCU GND | `board.return_path(net)` |
| `HS_XTAL_005` | Load caps within 5 mm of crystal; lengths matched ±1 mil | `board.distance()`, `board.trace_length_match()` |
| `HS_XTAL_006` | No 90° corners on crystal traces | `board.trace_corners(net)` |
| `HS_ROUTE_001` | Serpentine 4W spacing between segments | `board.serpentine_spacing(net)` |
| `HS_SHORT_001` | Driver-receiver trace runs < 50 mm | `board.trace_length(net)` |
| `HS_CROSS_001` | Minimize trace crossings | `board.trace_crossings()` |
| `HS_SENS_001` | Guard traces / dedicated GND plane for sensitive signals | `board.guard_trace(net)`, `board.adjacent_ground(net)` |
| `HS_CLK_002` | Clock traces short to minimize EMI / skew | `board.trace_length(net)` |

## Common gotchas

- **AC coupling cap polarity (don't put input on output side)** — caps in series for AC coupling are symmetric, but the BridgingPinModel chain must respect signal direction.
- **REFCLK distribution for PCIe** — every endpoint on the same clock domain needs the same REFCLK source. Trying to use separate oscillators causes link-up failures.
- **Crystal vs. MEMS oscillator** — MEMS oscillators relax `HS_XTAL_*` rules (output is driven, not resonant). Document the choice.

## Cross-references

- [`emc-esd.md`](emc-esd.md) — return path, plane stitching, aggressor separation
- [`net-classes.md`](../net-classes.md) — `HighSpeedDiffTag`, `DDRTag`, `RFTag`, `ClockTag`
- [`code-hygiene.md`](code-hygiene.md) — UART crossover, I2C addressing
