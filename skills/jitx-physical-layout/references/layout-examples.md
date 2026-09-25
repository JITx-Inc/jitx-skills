# Physical layout example owners

- Soldermask-defined thermal pad: migration to `jitxlib.landpatterns` is pending;
  use [thermal_via_stitch.py](../scripts/thermal_via_stitch.py) until it lands,
  following [construction sequencing](../SKILL.md#verification).
- Drawn `OverlappableCopper` antenna, `VirtualConnection`, one-point net tie,
  and exposed-pad mask dams/paste subdivision: `jitxexamples.patterns` (UNPUBLISHED:jitxexamples.patterns), antenna example promotion pending.
- Custom-pad soldermask/paste: `jitxlib.landpatterns.pads`, including
  `SMDPadConfig`, `THPadConfig`, `ThermalPadGeneratorMixin`, and `WindowSubdivide`.
