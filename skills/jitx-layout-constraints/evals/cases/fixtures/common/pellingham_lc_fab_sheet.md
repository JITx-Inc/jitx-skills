# Pellingham Circuits: capability sheet PC-CAP-4L, revision C (synthetic example)

Pellingham Circuits is a fictional fabricator. This sheet is the fab's published
capability for its 4-layer FR-4 line, quoted for the boards in this folder. All
dimensions are millimetres. Copper-to-copper rows apply between copper of
different nets; same-net copper may touch. Rows are cited by number (for example
"row 7").

## Stackups

| Row | Item | Value |
|---|---|---|
| 1 | Standard 4-layer build (`LcStandard4`) | L1 1 oz (0.035), L2 1 oz, L3 1 oz, L4 1 oz; 1.6 total |
| 2 | Heavy-inner 4-layer build (`LcHeavyInner4`) | L1 1 oz (0.035), L2 2 oz (0.070), L3 0.5 oz (0.018), L4 1 oz (0.035); 1.6 total |

Layer numbering in JITX: L1 is layer 0, L2 is layer 1, L3 is layer 2, L4 is layer 3.

## Copper floors

| Row | Rule | Value |
|---|---|---|
| 3 | Minimum trace width, 0.5 oz and 1 oz copper | 0.100 |
| 4 | Minimum copper-to-copper space, 0.5 oz and 1 oz copper | 0.100 |
| 5 | Minimum trace width, 2 oz copper | 0.200 |
| 6 | Minimum copper-to-copper space, 2 oz copper | 0.250 |
| 7 | Minimum copper to drilled hole edge (any hole, plated or not, including via drills) | 0.200 |
| 8 | Minimum copper to board outline (routed outer edge) | 0.300 |
| 9 | Minimum copper to an internal routed slot or cutout edge | 0.300 |
| 10 | Minimum pour feature (narrowest strip of poured copper kept) | 0.200 |

## Drilling and vias

| Row | Rule | Value |
|---|---|---|
| 11 | Standard through via (`LcStandard4.ThVia`, `LcHeavyInner4.ThVia`): pad diameter | 0.500 |
| 12 | Standard through via: finished drill | 0.250 |
| 13 | Minimum annular ring | 0.125 |
| 14 | Minimum drill | 0.200 |
| 15 | Minimum hole-to-hole, drill edge to drill edge | 0.250 |

## Notes

- Row 15 is checked between every pair of drills, including two vias of the same net.
- Rows 6 and 5 apply only on a 2 oz layer. A 1 oz or 0.5 oz layer in the same build keeps rows 3 and 4.
- Rows 8 and 9 are separate checks: a slot milled inside the board is not part of the outer outline.
