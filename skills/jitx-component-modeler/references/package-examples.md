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
| `BGA` | `jitxexamples.jumpstart_kits.js1_stackup_components.versal_fpga.landpattern` (source only, not on the components docs pages) | A full-grid `BGA` subclass with a public `get_pad(row, column)` adapter, `ball_diameter` set to the copper land diameter from the vendor's design-rule table |

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

6. **`ball_diameter` is the PCB land diameter, not the package's ball.** The generator draws the pad
   from it (`jitxlib/landpatterns/generators/bga.py`: `pad_shape(Circle(diameter=ball_diameter))`),
   so it takes the land diameter from the manual's PCB design-rule table, keyed by pitch, never the
   ball diameter printed beside the pitch on the mechanical drawing. Passing the ball builds a
   plausible, silently oversized land pattern. The Versal module's docstring (table above) works
   one example; record in a comment which document each number came from.

7. **Reach pads through a public adapter.** Verification code needs pad-by-position access and the
   framework's accessor is `_`-prefixed: wrap it once in a subclass, taking 0-indexed `(row, column)`
   to match the generated coordinates and adding the framework's 1-based column offset inside, as
   `VersalBGA.get_pad` in the Versal module does. State the convention in its docstring.

## Non-Uniform BGAs

Some BGAs put balls off a regular grid: a second pitch in one region, offset ball groups, split grids. Check the mechanical drawing. For these, subclass `BGADecorated` (not `BGA`, which already mixes in `A1` and `AlphaDictNumbering`), override `_generate_layout` to yield a `GridPosition` per ball, and compose `class MyBGA(A1, AlphaDictNumbering, MyBGADecorated)`. `HexBGA` in `jitxexamples.demos.si_bga_optimization.generic_bga` (source only) is the worked example, a hex-staggered grid.

Row index 0 is the top row (`A`), at the largest y: compute y as `(center_row - r) * pitch`.
