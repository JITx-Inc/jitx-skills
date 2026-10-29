# Protocol SI Standards Reference

Parameter tables for the protocol constraints JITX ships. All timing values in seconds, impedance in ohms.

- `jitxlib.protocols`, in the `jitxlib-standard` package (installed separately from jitx), carries USB, DisplayPort, Ethernet MDI, RGMII and others. The Ethernet tables below are the values those modules apply.
- `jitxexamples.protocols.memory`, in the `jitxexamples` distribution, carries point-to-point DDR4 and LPDDR4. Each module's docstring cites the source table for every number, and each has a worked example design (`ddr4_example`, `lpddr4_example`).

For a protocol not listed here, write the constraint from the controller's layout guide and cite it; do not use typical values.

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

Both modules are point-to-point (one controller, one memory device) on plain nets, and set no insertion-loss limit and no impedance target by default: pass `loss` in the parameter class and the routing structures from the board's substrate.

### DDR4

Source: Altera 683216 (version 23.2), Table 116, "Skew Matching Guidelines for DDR4 Discrete Topologies", which covers single-rank x8 and x16 discrete topologies.

| Signal Group | Constraint Type | Tolerance |
|-------------|-----------------|-----------|
| CK intra-pair | ConstrainDiffPair | +/-1ps |
| DQS intra-pair | ConstrainDiffPair | +/-1ps |
| DQ, DM_n to DQS | ConstrainReferenceDifference | +/-3.5ps |
| CMD/ADDR/CTRL to CK | ConstrainReferenceDifference | +/-20ps |
| CMD/ADDR/CTRL group | ConstrainReferenceDifference | +/-10ps of CKE[0] (stricter than the table's 20ps) |
| CK to DQS | ConstrainReferenceDifference | -85ps to +935ps, CK minus DQS |

```python
from jitxexamples.protocols.memory.ddr4 import DDR4, DDR4Constraint, DDR4Width, DDR4Rank
```

### LPDDR4

Source: AMD UG583, Table 2, "LPDDR4 without ECC Skew Constraints", written for the Zynq UltraScale+ MPSoC PS driving one device; check another controller's own guide.

| Signal Group | Constraint Type | Tolerance |
|-------------|-----------------|-----------|
| CK intra-pair | ConstrainDiffPair | +/-2ps |
| DQS intra-pair | ConstrainDiffPair | +/-2ps |
| CKE/CS/CA to CK | ConstrainReferenceDifference | +/-8ps |
| DQ/DMI to DQS | ConstrainReferenceDifference | +/-5ps |
| DQ and DMI spread | ConstrainReferenceDifference | +/-2.5ps of DMI |
| CK to DQS | ConstrainReferenceDifference | -500ps to +2500ps, CK minus DQS |

```python
from jitxexamples.protocols.memory.lpddr4 import LPDDR4, LPDDR4Constraint, LPDDR4Width
```

## Constraint Primitive Usage Summary

| Primitive | Typical Use | Example Protocol |
|-----------|-------------|------------------|
| `DiffPairConstraint` | Intra-pair skew + loss on diff pairs | All (CK, DQS, TX/RX lanes) |
| `ConstrainReferenceDifference` | Inter-signal timing to reference | DDR DQ-to-DQS, RGMII data-to-clk, 1000BASE-T pair-to-pair |
| `Constrain.insertion_loss()` | Single-ended signal loss | RGMII data; DDR when `loss` is passed |
| `Constrain.structure()` | Routing structure assignment | All SE signals |
| `ConstrainDiffPair.structure()` | Diff routing structure | All diff pairs |
| `BridgingPinModel` | AC coupling caps, series R, ESD arrays | Any AC-coupled lane; parts a constrained path passes through |
| `TerminatingPinModel` | IC pin characterization | All active components |
