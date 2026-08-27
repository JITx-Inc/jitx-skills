# Interface Circuit

### Port Design
- [ ] Circuit exposes **bundle-typed ports** (I2S, I2C, SPI, USB2, GPIO, DiffPair, Power) — not individual signal ports
- [ ] If wrapping a component with individual pins, bundle wiring happens inside the circuit
- [ ] Bundle port types match what the MCU/FPGA wrapper provides via require()

### Signal Integrity
- [ ] Termination scheme matches the protocol standard:
      - Series termination at source for point-to-point
      - Parallel termination at receiver for transmission lines
      - AC coupling caps for DC-blocking (check value for frequency range)
- [ ] Impedance targets documented for constrained signals
- [ ] Routing structure assigned matches impedance target
- [ ] Topologies created with `>>` inside the circuit for constrained signal paths
- [ ] **SI constraints (Constrain, ConstrainDiffPair, ReferencePlanes) are NOT applied here** — they go at the top-level design where the full path is visible. The circuit only creates the topology segments.

### Level Translation
- [ ] Voltage domains of connected ICs compared — level shifter needed if they differ
- [ ] Level shifter direction correct (unidirectional vs bidirectional)
- [ ] Level shifter OE pin handled (not floating)
- [ ] Open-collector/open-drain outputs: pull-up voltage compatible with the receiving IC's input voltage range (e.g., a 5V-tolerant OC output pulled up to 5V must not drive a 3.3V-only input)

### Control Signal Handling
- [ ] I2C lines: open-drain with pull-ups to VDDIO (value per bus speed: 4.7k for 100kHz, 2.2k for 400kHz)
- [ ] SPI chip select: pull-up to deselect when inactive
- [ ] UART: TX-to-RX crossover verified (not TX-to-TX)
- [ ] Reset pins: RC filter for noise immunity, ESD protection if board edge
- [ ] Interrupt pins: pull-up or pull-down matching active polarity

### Unused Pin Handling
- [ ] Unused inputs on active devices terminated (not floating) — tie to VCC or GND per datasheet
- [ ] Unused outputs left unconnected or noted as NC
- [ ] Unused op-amp sections: non-inverting input to mid-rail, output left open

### Decoupling — CRITICAL (commonly missed)
- [ ] Decoupling per the datasheet and any PDN requirement where they specify values and placement; otherwise the fewest, largest MLCCs in the smallest package rated at least 2x the rail, one per group of power pins, connected with the lowest loop inductance (Bogatin; see `jitx-layout-constraints` Decoupling). No per-pin 10uF / 1uF / 100nF stack unless the datasheet asks for it
- [ ] **Every power-rail cap `.insert(...)` uses `short_trace=True`** — decoupling, bypass, bulk, output filter. Exceptions (AC coupling, RC time constants, RF, crystal load) are dispositioned in the task acceptance block. Gated at Phase 2 → 3.
- [ ] Ferrite bead or filter on analog supply pins if mixed-signal

### Protocol-Specific Checks
Apply the relevant protocol check:

**USB**: differential impedance 90 ohm, AC coupling caps if required by standard, VBUS decoupling, ESD on connector pins, ID pin handling (OTG)

**Ethernet (RGMII/SGMII)**: TX/RX clock routing, 50 ohm / 100 ohm impedance, magnetics/transformer, MDI termination

**DDR (DDR3/DDR4/DDR5)**: per-byte-lane DQ-to-DQS matching, CK differential, command/address timing, ODT values, VREF decoupling, ZQ calibration resistor

**LPDDR (LPDDR4/LPDDR5)**: differential read/write strobes per byte lane (different signaling than standard DDR), per-lane DQ-to-DQS matching, CK differential, CA bus timing, VREF decoupling, termination values differ from DDR — consult the specific LPDDR spec

**PCIe**: AC coupling on TX (required by spec for different ground references between endpoints — but verify for your specific link configuration), 100 ohm differential, REFCLK distribution to all endpoints on same clock domain, PERST# handling, WAKE# pull-up

**SPI**: clock polarity (CPOL) and phase (CPHA) mode verified, chip select unique per device

---
