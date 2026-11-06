# Pellingham Circuits: capability sheet PC-CAP-4L, revision D (synthetic example)

Pellingham Circuits is a fictional fabricator. This sheet is the fab's published
capability for its 4-layer FR-4 line, quoted for the boards in this folder. All
dimensions are millimetres. Copper-to-copper rows apply between copper of
different nets; same-net copper may touch. Rows are cited by number (for example
"row 7").

## Stackup

| Row | Item | Value |
|---|---|---|
| 1 | Standard 4-layer build (`ClStandard4`) | L1 1 oz (0.035), L2 1 oz, L3 1 oz, L4 1 oz; 1.6 total; L1 to L2 dielectric 0.2 |

Layer numbering in JITX: L1 is layer 0, L2 is layer 1, L3 is layer 2, L4 is layer 3.

## Copper floors

| Row | Rule | Value |
|---|---|---|
| 3 | Minimum trace width | 0.100 |
| 4 | Minimum copper-to-copper space | 0.100 |
| 7 | Minimum copper to drilled hole edge (any hole, plated or not, including via drills) | 0.200 |
| 8 | Minimum copper to board outline (routed outer edge) | 0.300 |
| 10 | Minimum pour feature (narrowest strip of poured copper kept) | 0.200 |

## Drilling and vias

| Row | Rule | Value |
|---|---|---|
| 11 | Standard through via (`ClStandard4.ThVia`): pad diameter | 0.500 |
| 12 | Standard through via: finished drill. Open drill, not filled: not accepted inside an SMD pad | 0.250 |
| 13 | Minimum annular ring | 0.125 |
| 14 | Minimum drill | 0.200 |
| 15 | Minimum hole-to-hole, drill edge to drill edge | 0.250 |
| 16 | Filled and capped via-in-pad (`ClStandard4.VipVia`): pad diameter 0.450, finished drill 0.200, filled with epoxy and plated over; accepted inside SMD pads | 0.450 / 0.200 |

## Notes

- Row 15 is checked between every pair of drills, including two vias of the same net.
- Row 12: solder wicks down an open via inside a pad. Use row 16 inside a pad.
- Rows 2, 5, 6 and 9 (heavy copper and internal slots) are withdrawn on this line.
