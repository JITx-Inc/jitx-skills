# External Connector / Hot-Plug Interface

For every connector to the outside: USB, Ethernet, audio, power input (barrel, terminal, USB-PD, PoE), user-reachable debug headers, expansion connectors, antenna connectors (U.FL, SMA, edge contacts). PCB antenna geometry is not covered here.

### Per connector
- [ ] Pin map matches the orientation (USB-C mirrors CC1/CC2; USB-A/B does not).
- [ ] Shield to chassis by a chosen method (short trace, ferrite, capacitor, hard tie), stated.
- [ ] Ampacity above the worst-case load with margin.
- [ ] Reverse voltage, surge and inrush handled for the source class (USB-PD, barrel jack and PoE differ).
- [ ] Mechanical retention matched to use (through-hole tabs, screws, latch, none).

### ESD or justification
Every user-reachable conductor (connector pins, switch contacts, jumpers, buttons, test points, edge fingers, castellations) states one of:
- [ ] a TVS or ESD diode with capacitance the signal rate allows;
- [ ] internal only (board-to-board, sealed enclosure, controlled fixture);
- [ ] omitted by design, with the reason (RF budget, prototype cost), confirmed by the user.

### By connector type, where present
- [ ] USB-C / USB-PD: CC pull-downs or PD resistors for the role (sink, source, DRP); CC capacitance limit; VBUS protection rated for the negotiated voltages (5, 9, 15, 20 V); low-capacitance ESD on D+/D-; the controller's configuration pins.
- [ ] Ethernet (RJ45): magnetics or LAN module, MDI/MDIX and Bob Smith terminations, shield bond and the chassis-to-ground bond per the EMC plan.
- [ ] Audio (TRS, TRRS): insertion-detect contacts, AC coupling (or DC with the reason), ESD on tip and ring, a ground-loop plan for line out.
- [ ] Antenna feed: 50 Ω structure to the connector, return-plane keepout under the feed ([Defaults and classes](../../../jitx-layout-constraints/SKILL.md#defaults-and-classes)), connector suited to the frequency.
- [ ] Debug header: ESD, short protection, keying or marking against reverse insertion; a sealed internal header may omit ESD, noted.
