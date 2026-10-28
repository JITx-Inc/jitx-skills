# Package Examples

Each standard generator below has a worked component in the `jitxexamples` package. Read the module before writing a package whose pad numbering, mapping or thermal pad you have not built before: it shows the generator call, the port declarations, the symbol and how pads map to ports on a real part. Its dimensions belong to that part; yours come from your own source. The modules show API shape: some take library defaults or device-name MPNs that this skill's gates reject.

Read the rendered module in the docs (see `jitx/references/docs-index.md` "Example Components"). `jitxexamples` is not installed with `jitx`; where it is installed, `python -c "import jitxexamples; print(list(jitxexamples.__path__))"` finds the source.

| Generator | Module | What it shows |
|---|---|---|
| `SOIC` | `jitxexamples.components.flash.winbond_W25Q128JVSIQ` | `SOIC` with an explicit `LeadProfile` and `PadMapping` |
| `SOIC` | `jitxexamples.components.timers.texas_instruments_NE555` | `SOIC(num_leads=8)`, ports declared in pin order, no `PadMapping` |
| `SOT23_5` | `jitxexamples.components.opamps.texas_instruments_TLV314IDBVR` | `SOT23_5` with `SOTLeadProfile`, `RectanglePackage` and `PadMapping` |
| `QFN` | `jitxexamples.components.mcus.raspberry_pi_RP2040` | `QFN(num_leads=56)` with port arrays and a thermal pad mapped through `PadMapping` |
| `SON` | `jitxexamples.components.power_linear_regulators.texas_instruments_LM1117LD` | `SON(num_leads=8)` with a thermal pad mapped through `PadMapping` |
| `BGA` | `jitxexamples.jumpstart_kits.js1_stackup_components.versal_fpga.landpattern` | A full-grid `BGA` subclass with a public `get_pad(row, column)` adapter, `ball_diameter` set to the copper land diameter from the vendor's design-rule table |

QFP has no module in `jitxexamples`. Its constructor signature is in [component-code-patterns.md](component-code-patterns.md#landpattern-constructor-signatures); every BGA also needs the notes below.

## BGA-Specific Notes

1. **Row naming convention**: Row letters come from `ABCDEFGHJKLMNPRTUVWY` — I, O, Q, S, X, and Z are skipped — rolling over to two letters (`AA`, `AB`, …) past row 19. Row index 0 is `A`, so a 12-row BGA is A, B, C, D, E, F, G, H, J, K, L, M.

2. **Grid planner**: Subclass `GridPlanner` from `jitxlib.landpatterns.grid_planner` and override `is_active(self, pos, num_rows, num_cols)`, returning `False` for depopulated positions and `None` to defer to the default, then pass an instance to the generator's `.grid_planner(...)`.

3. **Pad naming**: BGA pads accessed via `lp.A[1]` or `lp.B[12]` (dict-style).

4. **NC vs Depopulated**:
   - **NC**: Physical ball exists but not connected. Use `Port().no_connect()`, include in symbol.
   - **Depopulated**: No physical ball. Mark inactive in grid planner, no port needed.

   `no_connect()` works from the component's `__init__`, which is where it belongs for a ball the
   vendor defines as NC — that is a property of the part, not of a board that uses it. (The docstring
   shows it called from the enclosing circuit; that is the *other* case, a pin this design leaves
   open.) On a large BGA the NC group runs to dozens of balls, and leaving them as ordinary ports
   makes "intentionally open per the vendor" and "the board designer forgot to wire it"
   indistinguishable to every downstream unconnected-port check.

5. **Package dimensions**: Body size is overall package. Ball array centered within.

6. **`ball_diameter` is the PCB land diameter, not the package's ball.** This is the one BGA
   parameter whose name points at the wrong document. The mechanical drawing gives you a ball
   diameter — often as a min/nom/max triple, sitting right next to the pitch, which is exactly where
   you are already reading — and it is *not* what this argument wants. The land diameter comes from
   the manual's **PCB design-rule table**, keyed by pitch, and it is a different number.

   **Don't take that on trust: open `jitxlib/landpatterns/generators/bga.py` and read what the
   parameter drives** (`self.pad_shape(Circle(diameter=ball_diameter))`) before you pass anything to
   it. Reading the source for yourself is what makes this stick — an assertion here reads like
   trivia and gets skipped.

   Passing the physical ball builds a valid, plausible, silently oversized land pattern. Record in a
   comment which document each number came from.

7. **Reaching pads: add a public adapter, don't touch `_`-prefixed members.** Verification code needs
   pad-by-position access, and the framework's accessor is internal. Wrap it once in a subclass:

   ```python
   class MyBGA(BGA):
       def get_pad(self, row: int, column: int) -> Pad:
           """Both 0-indexed, matching emitted coordinates: ball A1 is get_pad(0, 0)."""
           return self._get_pad(row, column + 1)
   ```

   Design code never reaches into `_`-prefixed framework members directly — the adapter is the
   sanctioned boundary.

   **Make the adapter's convention the same one your coordinates use.** The framework numbers
   columns from 1 (matching the ball reference "A1"), while a generated module carries fully
   zero-indexed `(row, col)` coordinates. Those differ by one, and the whole value of the adapter is
   that it absorbs that difference *once* — so take 0-indexed arguments and do the `+ 1` inside.
   Write it the other way, taking a 1-indexed column, and every call site converts instead
   (`get_pad(row, col + 1)`), which is the same off-by-one risk you added the adapter to remove, now
   scattered. State the convention in the docstring either way, because a reader cannot tell from
   the signature.

## Non-Uniform BGAs (CRITICAL)

**IMPORTANT:** Some BGAs have balls NOT on a regular grid. Check mechanical drawing for:
- Different pitch in some regions
- Offset ball groups
- Split grids

**Pattern for non-uniform BGAs:**

```python
from collections.abc import Iterable

from jitx.transform import Transform
from jitxlib.landpatterns.generators.bga import BGADecorated
from jitxlib.landpatterns.grid_layout import A1, AlphaDictNumbering, GridPosition


class CustomBGA_Base(BGADecorated):
    """Custom BGA base with offset for specific pad positions.

    IMPORTANT: Extend BGADecorated, NOT BGA!
    BGA already includes A1 and AlphaDictNumbering mixins.
    """

    def __init__(self, num_rows: int, num_cols: int, ball_diameter: float, pitch: float):
        super().__init__(num_rows, num_cols, ball_diameter, pitch)
        self._pitch = pitch
        self._offset_rows = {0, 1, 2, 3}
        self._offset_cols = {8, 9, 10, 11}
        self._x_offset = 0.2975
        self._y_offset = 0.2075

    def _generate_layout(self) -> Iterable[GridPosition]:
        num_rows = self._num_rows
        num_cols = self._num_cols
        pitch = self._pitch
        center_row = (num_rows - 1) / 2.0
        center_col = (num_cols - 1) / 2.0

        for r in range(num_rows):
            row_y = (center_row - r) * pitch
            for c in range(num_cols):
                x = (c - center_col) * pitch
                if r in self._offset_rows and c in self._offset_cols:
                    x += self._x_offset
                    y = row_y + self._y_offset
                else:
                    y = row_y
                yield GridPosition(r, c, Transform.translate(x, y))


class CustomBGA(A1, AlphaDictNumbering, CustomBGA_Base):
    pass
```

**Key:** Row index 0 = TOP row (`A`), row 11 = BOTTOM (`M` in a 12-row BGA). The `(center_row - r)` term is what puts row 0 at the largest y.
