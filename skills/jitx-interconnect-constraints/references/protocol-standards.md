# Protocol SI Standards Reference

The numbers for the protocol constraints JITX ships live in the modules that apply them. Read the module's `Standard` (or parameter class) and its docstring rather than a copy here. All timing values are in seconds, impedance in ohms.

For a protocol not listed here, write the constraint from the controller's layout guide and cite it; do not use typical values.

## Ethernet

`jitxlib.protocols`, in the `jitxlib-standard` package (installed separately from jitx), carries the values. Each class's nested `Standard` holds its skew, loss and impedance:

- 100BASE-TX: `jitxlib.protocols.ethernet.mdi.mdi100base_tx.MDI100BaseTX.Standard`
- 1000BASE-T: `jitxlib.protocols.ethernet.mdi.mdi1000base_t.MDI1000BaseT.Standard` (intra-pair and pair-to-pair skew)
- 10GBASE-KR: `jitxlib.protocols.ethernet.mdi.e10gbase_kr.E10GBaseKR.Standard`
- RGMII: `jitxlib.protocols.ethernet.mii.rgmii.RGMII.Standard`, with the data-to-clock delay per version in `RGMII.Version` (`STD`, `ID`). RGMII is single-ended: it uses `RoutingStructure`, not `DifferentialRoutingStructure`.

```python
from jitx import current
from jitxlib.protocols.ethernet.mdi.mdi100base_tx import MDI100BaseTX

drs100 = current.substrate.differential_routing_structure(100.0)
std = MDI100BaseTX.Standard()
cst = MDI100BaseTX.Constraint(std, structure=drs100)
```

## Memory

`jitxexamples.protocols.memory`, in the `jitxexamples` distribution, carries point-to-point DDR4 (`ddr4`, from Altera 683216 Table 116) and LPDDR4 (`lpddr4`, from AMD UG583 Table 2). Each module's docstring cites the source table for every number, states each limit's sign convention, and has a worked example design (`ddr4_example`, `lpddr4_example`). Both set no insertion-loss limit and no impedance target by default: pass `loss` in the parameter class and the routing structures from the board's substrate.

## Constraint Primitive Usage Summary

| Primitive | Typical Use | Example Protocol |
|-----------|-------------|------------------|
| `DiffPairConstraint` | Intra-pair skew + loss on diff pairs | All (CK, DQS, TX/RX lanes) |
| `ConstrainReferenceDifference` | Inter-signal timing to reference | DDR DQ-to-DQS, RGMII data-to-clk, 1000BASE-T pair-to-pair |
| `Constrain.insertion_loss()` | Single-ended signal loss | RGMII data; DDR when `loss` is passed |
| `Constrain.structure()` | Routing structure assignment | All SE signals |
| `ConstrainDiffPair.structure()` | Diff routing structure | All diff pairs |
| `BridgingPinModel` | AC coupling caps, series R, ESD channels with an in-to-out path; not a flow-through package whose opposite pin is n.c., whose two lands are one net | Any AC-coupled lane; parts a constrained path passes through |
| `TerminatingPinModel` | IC pin characterization | All active components |
