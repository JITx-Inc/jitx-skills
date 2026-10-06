# Physical layout example owners

- Soldermask-defined thermal pad: use
  [thermal_via_stitch.py](../scripts/thermal_via_stitch.py), following
  [construction sequencing](../SKILL.md#verification).
- Drawn `OverlappableCopper` antenna, `VirtualConnection`, one-point net tie,
  and exposed-pad mask dams/paste subdivision: `jitxexamples.patterns` (UNPUBLISHED:jitxexamples.patterns).
- Custom-pad soldermask/paste: `jitxlib.landpatterns.pads`, including
  `SMDPadConfig`, `THPadConfig`, `ThermalPadGeneratorMixin`, and `WindowSubdivide`.
