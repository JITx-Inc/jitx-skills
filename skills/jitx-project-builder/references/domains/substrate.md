# Substrate

- [ ] **User's fab house confirmed**: if user confirmed JLCPCB, predefined substrates from `jitxlib.jlcpcb` (JLC04161H_1080, JLC04161H_7628, JLC06161H_7628) are available for standard FR-4 + 50/90/100 ohm. Otherwise, create a custom substrate (default)
- [ ] Layer count sufficient for routing density and reference plane continuity
- [ ] Impedance targets achievable with chosen dielectric Dk and geometry
- [ ] Via definitions cover ALL needed layer transitions (not just top-to-bottom)
- [ ] Ground reference planes continuous under all high-speed signal layers
- [ ] No signal layers without an adjacent ground reference plane
- [ ] Routing structures defined for every impedance class in the design
- [ ] Differential routing structures match protocol requirements (100 ohm, 85 ohm, etc.)
- [ ] Fabrication constraints are within manufacturer capabilities:
      - Minimum trace width and spacing
      - Minimum via drill and annular ring
      - Minimum dielectric thickness
      - Copper weight compatibility
- [ ] Microvia span within fab capability (typically 1-2 layers max)
- [ ] Stacked microvias specified correctly if needed (filled and capped)
- [ ] Backdrill specified for through-hole vias in high-speed paths (if needed)
- [ ] Routing structure velocity uses `phase_velocity()` (returns mm/s, NOT m/s)

---
