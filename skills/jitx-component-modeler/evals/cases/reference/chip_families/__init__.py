"""Reference solution for the parameterized chip-component-family eval case.

Verbatim copies of a shipped four-family passive library's shared chip helpers
and three of its families (two chip-resistor vendors and one MLCC). Kept as a
package rather than flattened into one file: each family module defines its own
module-level ``_build_mpn`` and code tables, so concatenating them into a single
namespace would silently bind every class to the last family's helpers.

This is built from REAL manufacturer datasheets. The eval fixtures are the
synthetic ACME analogues, so a candidate is verified against the FIXTURES, never
against this package's part numbers, size labels or packaging codes. What this
package demonstrates is shape, not content:

- the shared / never-shared split -- chip geometry, the two-pin ``.insert()`` and
  significant-figure rounding are shared in ``chip_smt``; the value encoder, the
  per-size tables and the part-number grammar stay per-family;
- ``compact_value`` wrapping ``PlainQuantity.to_compact`` to keep binary-float
  noise out of the BOM value label;
- a standard-chip-table override scoped to the single case size that disagrees
  with the datasheet, pinned by a test that fails once the library is corrected
  (``vishay_crcw._STANDARD_TABLE_OVERRIDES``);
- ``insert_two_pin`` giving family classes ``.insert()`` parity with the queried
  passives in ``jitxlib.parts``;
- the shared module's own name recording that it was renamed once a non-resistor
  family started using it.
"""
