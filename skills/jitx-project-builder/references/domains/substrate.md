# Substrate

- [ ] **User's fab house confirmed** (`decomposition-guide.md` Step 0): if it is JLCPCB, its predefined substrates are in `jitx-jlcpcb`; otherwise select or model one as `decomposition-guide.md` "Substrate" sets out
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
