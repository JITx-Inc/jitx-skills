# House rule HS-2: conductor spacing by voltage, revision B (synthetic example)

Applies to every board we release. Spacing is copper edge to copper edge, in
millimetres, between a conductor and copper of any other net. Voltage is the
largest steady-state voltage the conductor carries with respect to any other
net on the board. Where a part's datasheet or a safety standard asks for more,
the larger value applies.

| Row | Conductor voltage | External layers | Internal layers |
|---|---|---|---|
| S1 | 30 V or less | fab minimum | fab minimum |
| S2 | above 30 V, up to 60 V | 0.6 | 0.4 |
| S3 | above 60 V | per safety review | per safety review |
