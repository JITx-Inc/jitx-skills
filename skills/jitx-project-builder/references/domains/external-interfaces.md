# External Connector / Hot-Plug Interface

Apply for any connector or interface that exposes the board to the outside world: USB (any flavor), Ethernet, audio jacks, power input (barrel, terminal, USB-PD, PoE), debug headers if user-accessible, expansion connectors, antenna connectors (U.FL, SMA, board-edge contacts). PCB antenna geometry itself belongs to the substrate / RF net-class rules — not this checklist.

### Per-Connector Decision

- [ ] **Connector orientation / pin mirroring**: USB-C is symmetric (CC1/CC2 mirror); standard USB-A/B is not. Verify pin map matches the chosen orientation.
- [ ] **Shield / chassis strategy**: connected to chassis ground via short trace, ferrite bead, capacitor, or hard-tied — picked deliberately, not by default.
- [ ] **Current rating**: connector ampacity exceeds the worst-case load with margin.
- [ ] **Polarity / hot-plug protection**: reverse-voltage, surge, inrush handled per the source class (USB-PD differs from barrel jack differs from PoE).
- [ ] **Mechanical retention**: through-hole tabs, screw mount, locking mechanism, or none — matched to expected use.

### ESD-or-Justification

For every external or user-accessible signal pin — not only connector pins, but also exposed switch contacts, jumpers, push-button terminals, exposed test points, edge-card fingers, exposed castellations, and any other user-touchable conductor — the row must say one of:

- **TVS / ESD diode** specified, with capacitance compatible with the signaling speed (low-cap TVS for high-speed; standard for low-speed).
- **Internal-only**: not user-accessible (board-to-board internal link, sealed enclosure, controlled environment).
- **Omitted by design**: explicit reason (e.g., RF impedance budget, cost-constrained prototype, EMC-controlled fixture). User confirms.

### Protocol-Specific Sub-Checklists (load only when applicable)

These are examples, not required coverage. Pick the ones that apply to the design.

**USB-C / USB-PD**: CC1/CC2 pull-down or PD configuration resistors per the role (sink/source/DRP); CC capacitance limits; VBUS protection rated for negotiated voltages (5V/9V/15V/20V); D+/D- ESD low-cap; configuration-trap pins per the controller datasheet.

**Ethernet (RJ45)**: magnetics/transformer or LAN module; MDI/MDIX termination; Bob Smith terminations; shield bond strategy; chassis-to-circuit-ground bond per EMC plan.

**Audio (3.5mm TRS / TRRS)**: switching contacts on TRS detect insertion; AC coupling on signal lines (or DC-coupled with explicit reason); ESD on tip/ring; ground-loop strategy for line-out.

**Antenna connector / feed (U.FL, SMA, board-edge contact)**: 50Ω routing structure to the connector; return-plane keepout under the feed (see [Net Class Taxonomy](../net-classes.md)); connector type matched to frequency and connector-mate strategy.

**Debug headers (if user-accessible)**: ESD on signals; protection if user can short pins; pin keying or marking to prevent reverse insertion. (Internal-only debug headers in sealed enclosures may justify omitting ESD — note explicitly.)

---
