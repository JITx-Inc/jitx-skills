# Interface Circuit

### Ports
- [ ] Bundle ports (I2S, I2C, SPI, USB2, GPIO, DiffPair, Power), wired to individual pins inside the circuit, matching the bundles the MCU or FPGA wrapper provides.

### Signal integrity
- [ ] Termination per the protocol: series at the source for point to point, parallel at the receiver for transmission lines, AC coupling sized for the frequency range.
- [ ] Each constrained signal's impedance target recorded, with the routing structure that meets it.
- [ ] Constrained paths wired as `jitx-interconnect-constraints` "Plain nets by default" requires, a pin model on every part a path crosses; no SI constraint applied here.

### Levels
- [ ] Voltage domains of connected ICs compared; a level shifter where they differ, its direction right and its OE pin driven.
- [ ] An open-drain output's pull-up rail within the receiver's input range (a 5 V pull-up never reaches a 3.3 V-only input).

### Control signals
- [ ] I2C open-drain with pull-ups to VDDIO sized for the bus speed (4.7 kΩ at 100 kHz, 2.2 kΩ at 400 kHz).
- [ ] SPI chip selects pulled up to deselect, one per device; CPOL and CPHA match each device.
- [ ] UART TX to RX, never TX to TX.
- [ ] Reset with an RC filter, and ESD where it reaches the board edge; interrupt pull matches its active polarity.

### Unused pins
- [ ] Unused inputs tied per the datasheet; unused outputs NC; an unused op-amp section has its non-inverting input at mid-rail and output open.

### Decoupling
- [ ] Decoupling follows the datasheet and any PDN requirement. Without a recommendation: one 100 nF per supply pin and one bulk capacitor per rail at the IC, not a per-pin stack of three values.
- [ ] Ferrite bead or filter on analog supply pins of a mixed-signal part.

### Protocols
- [ ] USB: 90 Ω differential; AC coupling where the standard needs it; VBUS decoupling; ESD on the connector pins; ID pin for OTG.
- [ ] Ethernet (RGMII, SGMII): TX and RX clocking, 50 Ω and 100 Ω impedance, magnetics, MDI termination.
- [ ] DDR3/4/5: DQ to DQS matching per byte lane, differential CK, command and address timing, ODT, VREF decoupling, ZQ resistor.
- [ ] LPDDR4/5: differential read and write strobes per byte lane, DQ to DQS matching, differential CK, CA timing, VREF decoupling, termination from the LPDDR specification, not DDR's.
- [ ] PCIe: TX AC coupling (confirmed for the link), 100 Ω differential, REFCLK to every endpoint of the clock domain, PERST#, a WAKE# pull-up.
