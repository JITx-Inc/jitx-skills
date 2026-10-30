# Protocol Pin Flexibility Reference

The tables say what a protocol specification permits. Whether a part supports a swap is in its controller or PHY datasheet; confirm with the user before coding any Provide option: "Does your controller datasheet confirm support for [byte swap / lane reversal / P/N inversion]?"

## DiffPair P/N Polarity Swapping

P/N inversion is safe only when both ends handle the inverted signal.

| Protocol | P/N swap | Condition |
|----------|----------|-----------|
| PCIe | Spec allows | Controller must have RX polarity inversion; per lane |
| USB 2.0 | No | D+/D- polarity is protocol-critical |
| USB 3.x | Not covered | No cited source here for USB 3.x lane or polarity freedom: offer none unless the controller datasheet documents it, and cite it in the provider. |
| DisplayPort | Spec allows | Source must support lane polarity inversion; per lane (ML0-ML3) |
| Ethernet 100BASE-TX | No | TD+/TD- polarity fixed |
| Ethernet 1000BASE-T | Partially | MDI/MDI-X auto-negotiation in the PHY: software, not pin assignment |
| DDR4 DQS, DDR4 CK | No | DQS_t/DQS_c and CK_t/CK_c polarity always fixed |
| LPDDR5 WCK, RDQS | No | Strict polarity |

Worked pattern: `jitxexamples.patterns.pin_lane_polarity` (lane choice and P/N inversion, with an SI constraint that begins on the required pair).

## PCIe Lane Flexibility

The specification permits lane reversal and polarity inversion, but the controller must support each (look for "lane reversal" or "polarity inversion" in its datasheet); some endpoints do not.

| Feature | Controller condition | Provider pattern |
|---------|----------------------|------------------|
| Lane reversal | Both endpoints support it | `one_of` with reversed lane indices |
| P/N polarity swap | RX side has polarity inversion | Nested `provide.one_of` per diff pair |
| Width variants (x1/x2/x4/x8/x16) | Controller supports the narrower width | Separate `Provide` per width |
| Lane-to-port remapping | Requires lane reversal support | `one_of` with a different lane offset |

No PCIe skew or loss numbers here: take them from the controller's or retimer's layout guide and cite it. Inter-lane skew uses one leg (`TX.p`) as the single-pin guide. Constraint shape: [Constraints on Pin-Assigned Ports](../SKILL.md#constraints-on-pin-assigned-ports).

## DDR4 Pin Flexibility

DDR4 byte and bit swapping is controller-dependent: the controller's crossbar decides what may move. Ask the user: "Does your controller support byte lane swapping? Bit swapping within a byte lane?" (its manual's 'DQ mapping' or 'byte lane remapping' section).

| Feature | Possible | Scope | Provider pattern |
|---------|----------|-------|------------------|
| Byte lane reorder | Controller-dependent | Channel | `one_of` over the allowed byte orders |
| Bit swap in byte | Controller-dependent | Per byte lane | Per-slot bit bundle offered `all_of`, required `count=8` inside the byte `one_of` (SKILL.md, DDR Byte/Bit Swapping) |
| DQS-to-byte association | Fixed: DQS0 always with byte 0 | Per byte | None |
| Address/CMD, bank address | No | Global | Fixed wiring |
| CK P/N | No | Per rank | Fixed wiring |

`jitxexamples.protocols.memory.ddr4` applies cited point-to-point values, its docstring citing the source table for each; for another controller, use its layout guide.

## LPDDR4/4X on an AMD Versal DDRMC

AMD's PG313 pin rules for LPDDR4/4X allow two swaps: DQ bits within a byte, and a byte with the other byte of the same x16 channel, its DQS and DM going with it. Channel A never swaps with channel B, and every command, address, control, reset and clock pin is fixed. `jitxexamples.jumpstart_kits.js4_fpga_lpddr4x.pinout` holds the rules with their PG313 sections, and `js4_fpga_lpddr4x.fpga` offers them on a VP1002.

## LPDDR5 Pin Flexibility

Controller-dependent, as for DDR4; confirm which reorderings the controller supports. A controller may allow channel reorder (A and B interchangeable), byte lanes within a channel (WCK and RDQS stay with their byte lane) and any permutation of a byte's 8 DQ bits. CA bits and CS per rank are fixed mappings, and CK, WCK and RDQS polarity is always fixed.

No LPDDR5 numbers here: take them from the controller's layout guide and cite it.

## MCU Peripheral Muxing (I2C, SPI, UART)

The MCU datasheet's alternate-function (pin-mux) table documents the mux fully; model from it.

- I2C: SDA and SCL mux independently per the table, so compose `@provide(I2C)` from a `@provide.one_of` per signal; each instance (I2C1, I2C2) gets its own offer. Worked patterns: `jitxexamples.components.mcus.raspberry_pi_RP2040` (per-signal `one_of` pin lists from the datasheet's Table 279) and `jitxexamples.jumpstart_kits.js3_pin_assignment.mcu_muxing` (requires them; legal and illegal proofs).
- SPI: `@provide.one_of(SPI)` over the table's valid pin groups. CS is often any GPIO (`@provide(GPIO)`). CPOL/CPHA are set in firmware, not pin assignment.
- UART: `@provide.one_of(UART)` over the table's valid TX/RX pairs. RTS/CTS are optional, often any GPIO (`@provide.one_of(UART_FC)` or `@provide(GPIO)`).
