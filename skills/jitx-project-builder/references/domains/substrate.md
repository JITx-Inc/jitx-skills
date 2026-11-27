# Substrate

`jitx-substrate-modeler` owns the vias, structures and reference planes a report defines. Check the stackup against the design:

- [ ] Fab house confirmed (`decomposition-guide.md` Step 0).
- [ ] Layer count covers routing density and keeps reference planes continuous.
- [ ] Every signal layer has an adjacent ground reference plane, continuous under every high-speed layer.
- [ ] Every impedance class the design uses has a routing structure; differential targets match the protocol (100 Ω, 90 Ω, 85 Ω).
- [ ] Impedance targets reachable with the chosen dielectric and geometry.
- [ ] Via types cover every layer transition the design needs, not only top to bottom.
- [ ] Width, spacing, drill, annular ring, dielectric thickness and copper weight within the fab's capability.
- [ ] Microvia span within the fab's limit (usually one or two layers); stacked microvias filled and capped; backdrill on through vias in high-speed paths where needed.
- [ ] Routing structure velocity from `phase_velocity()`, which returns mm/s, not m/s.
