# Protocol Pin Flexibility Reference

> **Important:** The tables below describe what a protocol *specification* permits in principle. Whether a specific IC actually supports a given swap depends entirely on the controller or PHY datasheet. **Always confirm with the user** what their particular parts support before coding any Provide options. Ask: "Does your controller datasheet confirm support for [byte swap / lane reversal / P/N inversion]?"

## DiffPair P/N Polarity Swapping

P/N inversion is only safe when both endpoints handle the inverted signal correctly. Many controllers have internal inversion logic, but this is **not universal** — check the datasheet.

| Protocol | P/N Swap Possible | Controller-Dependent? | Notes | Constraint Class |
|----------|-------------------|----------------------|-------|------------------|
| PCIe | Yes (spec allows) | Yes — controller must have RX polarity inversion | Per-lane; most modern PCIe PHYs support this | `DiffPairConstraint` |
| USB 2.0 | No | — | D+/D- polarity is protocol-critical | N/A |
| USB 3.x | Not covered | n/a | This reference has no cited source for USB 3.x lane or polarity freedom. Offer none unless the controller datasheet documents it, and cite that datasheet in the provider. | `DiffPairConstraint` |
| DisplayPort | Yes (spec allows) | Yes — source must support lane polarity inversion | Per lane (ML0-ML3) | `DiffPairConstraint` |
| Ethernet 100BASE-TX | No | — | TD+/TD- polarity fixed | `DiffPairConstraint` |
| Ethernet 1000BASE-T | Partially | PHY-dependent (MDI/MDI-X auto-negotiation) | Software-managed, not pin assignment | `DiffPairConstraint` |
| DDR4 DQS | No | — | DQS_t/DQS_c polarity is always fixed | `ConstrainDiffPair` |
| DDR4 CK | No | — | CK_t/CK_c polarity is always fixed | `ConstrainDiffPair` |
| LPDDR5 WCK | No | — | Strict polarity | `ConstrainDiffPair` |
| LPDDR5 RDQS | No | — | Strict polarity | `ConstrainDiffPair` |

**Implementation pattern (only after confirming controller support):**
```python
@provide.one_of(TXLink)
def provide_tx(self, link: TXLink):
    return [
        {link.tx.p: self.ic.TXP, link.tx.n: self.ic.TXN},  # Normal
        {link.tx.p: self.ic.TXN, link.tx.n: self.ic.TXP},  # Swapped
    ]
```

## PCIe Lane Flexibility

The PCIe specification permits lane reversal and polarity inversion, but **the controller must explicitly support these features**. Many PCIe switches and root complexes do; some endpoint devices do not. Check the controller datasheet for a "lane reversal" or "polarity inversion" feature description.

| Feature | Spec Allows | Controller-Dependent? | Provider Pattern | Constraint Pattern |
|---------|-------------|----------------------|-----------------|-------------------|
| Lane reversal | Yes | Yes — both endpoints must support | `Provide().one_of()` with reversed lane indices | `DiffPairConstraint` per lane |
| P/N polarity swap | Yes | Yes — RX side must have polarity inversion | Nested `provide.one_of` per diff pair | `DiffPairConstraint` |
| Width variants (x1/x2/x4/x8/x16) | Yes | Yes — controller must support the narrower width | Separate `Provide` per width | `DiffPairConstraint` per lane |
| Lane-to-port remapping | Yes | Yes — requires lane reversal support | `one_of` with different `lane_offset` | `ConstrainReferenceDifference` for inter-lane skew |

### PCIe Constraint Parameters

This reference carries no PCIe skew or loss numbers. Take them from the controller's or retimer's layout guide and cite it in the constraint.

### PCIe Constraint Pattern
```
require(PCIeLink) -> lane[i].TX + dst.lane[i].RX                 (plain nets)
                  -> DiffPairConstraint(skew, loss).constrain(TX, RX)
                  -> ConstrainReferenceDifference(guide=Topology(lane[0].TX.p, ...),
                                                  topologies=[lane[1:] legs])
                  -> Route on the switch's physical lane pins   (resolves the mapping)
                  -> rt.submit(Design).issues(satisfied=True) (measurements; group.satisfied)
```
The reference guide must be a single pin, so inter-lane skew uses one leg (`TX.p`) as the guide. See the SKILL.md section [Constraints on Pin-Assigned Ports](../SKILL.md#constraints-on-pin-assigned-ports).

## DDR4 Pin Flexibility

DDR4 byte and bit swapping is **entirely controller-dependent**. The DDR4 JEDEC spec defines signal functions, but many controllers include internal crossbar logic that allows reordering data bits and byte lanes. The memory IC itself does not care about ordering — it responds to whatever arrives on its DQ/DQS pins.

**Before coding any DDR4 swaps, ask the user:** "Does your DDR4 controller support byte lane swapping? Bit swapping within a byte lane? Check the controller reference manual for a 'DQ mapping' or 'byte lane remapping' section."

| Feature | Possible | Controller-Dependent? | Scope | Provider Pattern | Constraint |
|---------|----------|----------------------|-------|-----------------|------------|
| Byte lane reorder | Yes | **Yes** — controller must have byte-swap logic | Channel | `Provide().one_of()` with byte permutations | `ConstrainReferenceDifference` per byte |
| Bit swap in byte | Yes | **Yes** — controller must have bit-swap logic | Per byte lane | `Provide().one_of()` with bit permutations | `Constrain` per DQ |
| DQS-to-byte assoc | Fixed | No — always DQS0 with byte 0 | Per byte | N/A | `ConstrainReferenceDifference` DQ-to-DQS |
| Address/CMD bits | No | — | Global | Fixed wiring | `Constrain` timing |
| CK P/N swap | No | — | Per rank | Fixed wiring | `ConstrainDiffPair` |
| Bank address | No | — | Global | Fixed wiring | `Constrain` timing |

### DDR4 Constraint Parameters

`jitxexamples.protocols.memory.ddr4` applies cited point-to-point values; the table is in `jitx-interconnect-constraints` [protocol-standards.md](../../jitx-interconnect-constraints/references/protocol-standards.md#ddr4). For another controller, take the values from its layout guide.

### DDR4 Byte Swap Constraint Pattern
```
require(DDR4Data) -> byte_lane[bl].DQ[i] + mem.DQ[offset+i]      (plain nets)
                  -> byte_lane[bl].DQS.p + mem.DQS_P[bl], DQS.n + mem.DQS_N[bl]
                  -> ConstrainReferenceDifference(guide=Topology(DQS.p, mem.DQS_P[bl]),
                                                  topologies=DQ_topos)
                  -> Route on the controller's physical DQ/DQS pins (resolves the mapping)
                  -> rt.submit(Design).issues(satisfied=True) (measurements; group.satisfied)
```

## LPDDR5 Pin Flexibility

Like DDR4, LPDDR5 data bus flexibility is **controller-dependent**. The JEDEC spec defines the interface, but the controller's internal crossbar determines which swaps are possible. The memory device is agnostic to data ordering.

**Before coding LPDDR5 swaps, confirm with the user** which reorderings their controller supports.

| Feature | Possible | Controller-Dependent? | Scope | Notes |
|---------|----------|----------------------|-------|-------|
| Channel reorder | Yes | **Yes** — controller must map channels flexibly | Device | Channels A/B may be interchangeable |
| Byte lanes in channel | Yes | **Yes** — controller must support byte swap | Per channel | WCK/RDQS must stay with their byte lane |
| Bits within byte | Yes | **Yes** — controller must support bit swap | Per byte lane | Any permutation of 8 DQ bits |
| CA bits | No | — | Per channel | Fixed mapping |
| CK/WCK/RDQS P/N | No | — | Strict | Polarity is always fixed |
| CS per rank | No | — | Per channel | Fixed mapping |

### LPDDR5 Constraint Parameters

This reference carries no LPDDR5 numbers. Take them from the controller's layout guide and cite it in the constraint.

## MCU Peripheral Muxing (I2C, SPI, UART)

MCU peripheral pin muxing is the most straightforward case — the MCU datasheet's "alternate function" or "pin mux" table is the definitive source. These are always safe to model because the MCU's internal mux is fully documented.

### I2C

| Feature | Provider Pattern | Notes |
|---------|-----------------|-------|
| SDA/SCL mux | Hierarchical: `@provide.one_of(I2C_SDA)` + `@provide.one_of(I2C_SCL)` composed via `@provide(I2C)` | SDA and SCL can be independently muxed per the MCU's AF table |
| Multiple I2C instances | Separate `@provide.one_of` per instance | I2C1 and I2C2 with different pin options |

### SPI

| Feature | Provider Pattern | Notes |
|---------|-----------------|-------|
| MOSI/MISO/SCK mux | `@provide.one_of(SPI)` | Read the MCU AF table for valid pin groups |
| CS pin selection | `@provide(GPIO)` | Often any GPIO can serve as CS |
| Clock polarity (CPOL/CPHA) | Not pin assignment | Set in firmware, not PCB |

### UART

| Feature | Provider Pattern | Notes |
|---------|-----------------|-------|
| TX/RX mux | `@provide.one_of(UART)` | Read the MCU AF table for valid pin pairs |
| Flow control (RTS/CTS) | `@provide.one_of(UART_FC)` or `@provide(GPIO)` | Optional, often any GPIO |
