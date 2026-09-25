# Protocol SI Standards Reference

Parameter tables sourced from [jitx_protocols_ext](https://github.com/JITx-Inc/jitx-protocols-ext) and industry specifications. All timing values in seconds, impedance in ohms.

**`jitx_protocols_ext` is a separate distribution and is not installed with jitx or jitxlib.** Every import below fails with `ModuleNotFoundError` until it is added to the project. Confirm it imports before building on it, and if it is absent, either add it deliberately or write the constraint from the parameter tables here rather than leaving a dead import in the design.

## Serial Protocols

### PCIe

| Gen | Intra-pair Skew | Max Loss (dB) | Diff Impedance | Notes |
|-----|----------------|---------------|----------------|-------|
| V1/V2 | 1ps | 12.0 | 100 +/-5% | 2.5/5.0 GT/s |
| V3 | 1ps | 10.3 | 85 +/-5% | 8.0 GT/s |
| V4 | 0.85ps | 13.5 | 85 +/-5% | 16.0 GT/s |
| V5-V7 | 0.85ps | 16.0 | 85 +/-5% | 32-128 GT/s |

```python
# requires the separate jitx-protocols-ext distribution; not installed with jitx
from jitx_protocols_ext.protocols.pcie import PCIe, PCIeConstraint, PCIeVersion, PCIeWidth

std = PCIeVersion.V5.standard()  # Returns PCIeStandard(skew, loss, impedance)
cst = PCIeConstraint(std, width=PCIeWidth.x4)
```

Lane widths: x1, x2, x4, x8, x16, x32. Supports `on_board=True` for chip-to-chip (omits control signals), `xover=True/False` for crossover vs straight-through.

### SATA

| Gen | Intra-pair Skew | Max Loss (dB) | Diff Impedance | Data Rate |
|-----|----------------|---------------|----------------|-----------|
| SATA 1.0 | 4ps | 15.0 | 90 +/-15% | 1.5 Gb/s |
| SATA 2.0 | 2ps | 15.0 | 90 +/-15% | 3.0 Gb/s |
| SATA 3.0 | 1ps | 15.0 | 90 +/-15% | 6.0 Gb/s |
| SATA 3.4 | 1ps | 15.0 | 90 +/-15% | 6.0 Gb/s |

```python
# requires the separate jitx-protocols-ext distribution; not installed with jitx
from jitx_protocols_ext.protocols.sata import SATA

std = SATA.Generation.SATA3p0.standard()
cst = SATA.Constraint(std)
# SATA always uses crossover topology (TX->RX)
```

### SFP / QSFP

| Link | Lanes | Intra-pair Skew | Inter-lane Skew | Loss (dB) | Impedance |
|------|-------|----------------|-----------------|-----------|-----------|
| SFP (1G) | 1 | 5ps | - | 12.0 | 100 +/-10% |
| SFP+ (10G) | 1 | 2ps | - | 15.0 | 100 +/-10% |
| SFP28 (25G) | 1 | 1.5ps | - | 16.0 | 100 +/-10% |
| SFP-DD (50G) | 2 | 1ps | 10ps | 16.0 | 100 +/-10% |
| QSFP (40G) | 4 | 2ps | 10ps | 15.0 | 100 +/-10% |
| QSFP28 (100G) | 4 | 1.5ps | 10ps | 16.0 | 100 +/-10% |
| QSFP56 (200G) | 4 | 1ps | 10ps | 18.0 | 100 +/-10% |
| QSFP-DD (400G) | 8 | 1ps | 10ps | 18.0 | 100 +/-10% |

```python
# requires the separate jitx-protocols-ext distribution; not installed with jitx
from jitx_protocols_ext.protocols.sfp import SFP_Lane, SFPConstraint, SFPLink

std = SFPLink.QSFP28_100G.standard()
cst = SFPConstraint(std)
# Uses ConstrainReferenceDifference for inter-lane skew (first lane as ref)
```

## Ethernet MDI

### 100BASE-TX

| Parameter | Value |
|-----------|-------|
| Intra-pair skew | 750ps |
| Max loss | 12 dB |
| Diff impedance | 100 +/-10% |

### 1000BASE-T (Gigabit)

| Parameter | Value |
|-----------|-------|
| Intra-pair skew | 0.8ps |
| Pair-to-pair skew | 165ps |
| Max loss | 12 dB |
| Diff impedance | 95 +/-15% |

### 10GBASE-KR

| Parameter | Value |
|-----------|-------|
| Intra-pair skew | 62.5fs |
| Pair-to-pair skew | 62.5fs |
| Max loss | 15 dB |
| Diff impedance | 100 +/-10% |

```python
from jitxlib.protocols.ethernet.mdi.mdi100base_tx import MDI100BaseTX
from jitxlib.protocols.ethernet.mdi.mdi1000base_t import MDI1000BaseT

std = MDI100BaseTX.Standard()
cst = MDI100BaseTX.Constraint(std, structure=drs100)
```

## Ethernet MII

### RGMII

| Version | Data-to-Clock Delay | Bus Skew | Max Loss | Impedance |
|---------|---------------------|----------|----------|-----------|
| STD (v1) | 1.75ns +/-250ps | 11ps | 7.5 dB | 50 +/-15% |
| ID (v2) | 0 +/-500ps | 11ps | 7.5 dB | 50 +/-15% |

```python
from jitxlib.protocols.ethernet.mii.rgmii import RGMII

# Uses Constrain for SE signals + ConstrainReferenceDifference for bus matching
```

RGMII is single-ended (not differential). Uses `RoutingStructure` (not `DifferentialRoutingStructure`).

## Memory Protocols

### DDR4

| Signal Group | Constraint Type | Tolerance | Notes |
|-------------|-----------------|-----------|-------|
| DQS intra-pair | ConstrainDiffPair | +/-1.0ps | Per byte lane |
| DQ to DQS | ConstrainReferenceDifference | +/-3.5ps | Data to strobe |
| CK intra-pair | ConstrainDiffPair | +/-1.0ps | Clock pair |
| CMD/ADDR to CK | ConstrainReferenceDifference | +/-20ps | Address/command |
| CMD/ADDR group | ConstrainReferenceDifference | +/-10ps | Intra-group |
| CK to DQS | ConstrainReferenceDifference | -85ps to +935ps | Cross-group |
| DQ insertion loss | Constrain | 5.0 dB | Single-ended |
| ACC insertion loss | Constrain | 5.0 dB | Single-ended |

**Impedances:** CK: 90 +/-5% (diff), DQS: 100 +/-5% (diff), DQ: 50 +/-5% (SE), ACC: 45 +/-5% (SE)

**Topology:** Fly-by (daisy-chain controller → mem0 → mem1)

```python
# requires the separate jitx-protocols-ext distribution; not installed with jitx
from jitx_protocols_ext.protocols.memory.ddr4 import DDR4, DDR4Constraint, DDR4Width, DDR4Rank
```

### LPDDR4

| Signal Group | Constraint Type | Tolerance |
|-------------|-----------------|-----------|
| CK intra-pair | ConstrainDiffPair | +/-2.0ps |
| CKE/CS/CA to CK | ConstrainReferenceDifference | +/-8.0ps |
| DQS intra-pair | ConstrainDiffPair | +/-2.0ps |
| DQ/DMI to DQS | ConstrainReferenceDifference | +/-5.0ps |
| CK to DQS | ConstrainReferenceDifference | -500ps to +2500ps |

**Impedances:** 85 +/-5% (diff), 40 +/-10% (SE)

```python
# requires the separate jitx-protocols-ext distribution; not installed with jitx
from jitx_protocols_ext.protocols.memory.lpddr4 import LPDDR4, LPDDR4Constraint, LPDDR4Width
```

### LPDDR5

| Signal Group | Constraint Type | Tolerance |
|-------------|-----------------|-----------|
| CK intra-pair | ConstrainDiffPair | +/-1.0ps |
| CS/CA to CK | ConstrainReferenceDifference | +/-4.0ps |
| WCK/RDQS intra-pair | ConstrainDiffPair | +/-1.0ps |
| DQ to WCK/RDQS | ConstrainReferenceDifference | +/-2.5ps |
| CK to WCK/RDQS | ConstrainReferenceDifference | -250ps to +1250ps |
| Max insertion loss | Constrain | 4.0 dB |

**Impedances:** 100 +/-5% (diff), 50 +/-5% (SE)

Separate write clock (WCK) and read data strobe (RDQS) per byte lane.

```python
# requires the separate jitx-protocols-ext distribution; not installed with jitx
from jitx_protocols_ext.protocols.memory.lpddr5 import LPDDR5, LPDDR5Constraint, LPDDR5Width
```

### GDDR7

| Signal Group | Constraint Type | Tolerance |
|-------------|-----------------|-----------|
| RCK/WCK intra-pair | ConstrainDiffPair | +/-10fs |
| RCK to WCK | ConstrainReferenceDifference | +/-20ps |
| WCK to CA | ConstrainReferenceDifference | +/-20ps |
| DQ to RCK/WCK | ConstrainReferenceDifference | +/-5ps |
| CA to CA | ConstrainReferenceDifference | +/-5ps |
| ERR to WCK | ConstrainReferenceDifference | +/-100ps |
| RESET to CA | ConstrainReferenceDifference | +/-100ps |

**Impedances:** 100 +/-10% (diff), 50 +/-10% (SE)

4 data channels, PAM3 signaling on DQ.

```python
# requires the separate jitx-protocols-ext distribution; not installed with jitx
from jitx_protocols_ext.protocols.memory.gddr7 import GDDR7, GDDR7Constraint
```

## Constraint Primitive Usage Summary

| Primitive | Typical Use | Example Protocol |
|-----------|-------------|------------------|
| `DiffPairConstraint` | Intra-pair skew + loss on diff pairs | All (CK, DQS, TX/RX lanes) |
| `ConstrainReferenceDifference` | Inter-signal timing to reference | DDR DQ-to-DQS, RGMII data-to-clk, SFP lane-to-lane |
| `Constrain.insertion_loss()` | Single-ended signal loss | DDR DQ, DDR ACC, RGMII data |
| `Constrain.structure()` | Routing structure assignment | All SE signals |
| `ConstrainDiffPair.structure()` | Diff routing structure | All diff pairs |
| `BridgingPinModel` | AC coupling caps, series R | PCIe, SATA, SFP (blocking caps) |
| `TerminatingPinModel` | IC pin characterization | All active components |
