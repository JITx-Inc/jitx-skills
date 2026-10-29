# Parts provider chain (jitxlib-parts 2.x)

`Resistor`, `Capacitor`, `PolarizedCapacitor` and `Inductor` from `jitxlib.parts` describe a passive by what it has to do; a chain of providers decides which part satisfies it. The base skill's Step 2 sets up the default chain, a CSV of approved parts followed by `ideal`. This page covers the CSV format, what falls through to `ideal` without a warning, the lockfile, the gate before a design counts as done, and how an internal parts database joins the chain. Verified on jitxlib-parts 2.0.0rc2.dev3 with jitx 4.6.0rc8.

## Where the chain comes from

In precedence order; a level applies only when every earlier one is absent:

1. a `with PartSource([...])` block
2. a `parts` attribute on the `Design`
3. `[tool.jitx.parts] chain` in the project's `pyproject.toml`
4. a chain an installed package publishes through the `jitxlib-parts-policy` entry-point group
5. auto-discovery from the `jitxlib-parts-provider` group, only with `discover = true`

With none of them, a query raises `NoChainConfigured`.

With `[tool.jitx.parts]` in `pyproject.toml`, `jitx find` prints `Warning, unexpected tool option: parts`: jitx's own pyproject reader does not know the table. The warning is harmless; do not move or delete the table.

## The approved-parts CSV

The header is the vocabulary. `category`, `mpn` and `manufacturer` are identity, `datasheet` is reported but not queryable, and every other column is a queryable attribute under its own name. One file holds every category; leave a cell blank where a column does not apply:

```csv
category,mpn,manufacturer,resistance,capacitance,case,tolerance,rated_voltage_dc,temperature_coefficient_code
resistor,RC0402FR-0710KL,Yageo,10 kohm,,0402,0.01,,
capacitor,GRM155R71A104KA01D,Murata,,100 nF,0402,0.1,10 V,X7R
```

- `category` is matched exactly: `resistor`, `capacitor` or `inductor`, lowercase.
- A dimensioned cell takes a bare number (`10000`) or one carrying its unit (`10 kohm`).
- Every key a design's query filters or ranks on needs a column. Adding a column is all it takes to filter or rank on it.
- Rows come from the user or the user's parts database, never from the agent. A row's `case` picks the footprint, so a guessed MPN or case puts a wrong part on the board. Ask for each value that has no row.

## What falls through to `ideal` without a warning

`ideal` answers a query that pins one value by snapping it to an E-series the tolerance allows (E24 or E96 at 1%, E24 at 5%) and synthesizing an `IDEAL-...` part with no manufacturer. When the snapped value falls outside the query, it declines, and the build fails with `no part found` even with `ideal` in the chain: at 5%, a 31.6 kΩ request snaps to 33 kΩ and fails. Of the other keys it honors only `case` (default `0402`), `tolerance` (default 1%) and `polarized`, and ignores the rest. It answers, silently, when:

- the CSV file is missing or the path in `chain` is mistyped;
- a row's `category` is not lowercase;
- the query filters or ranks on a key the CSV has no column for, such as `tcr_pos` or `mounting`;
- no row matches.

To see which provider answered a query and why the others declined, use `explain`. Give dimensioned values their units: a bare number in a query compared against a unit-carrying column raises `DimensionMismatch`.

```python
from jitx.units import ohm
from jitxlib.parts import ResistorQuery, explain

print(explain(ResistorQuery(resistance=10e3 * ohm, tolerance=0.01, mounting="smd")))
# 1 csv:approved-parts.csv   unsupported: .../approved-parts.csv has no such column
# 2 ideal                    1 candidate(s)
```

`grep IDEAL- parts.lock.json` lists synthesized parts pinned under every chain the lockfile has seen, including chains no longer active.

## The lockfile

`parts.lock.json` records which part answered each query, so a later run builds the same board. An entry is keyed on the query, the active chain and an optional `lock_scope`. A chain the lockfile has not seen re-resolves every query; returning to a chain it has seen brings back that chain's pins, since entries are never pruned. An edited query keeps its pinned part if that part still satisfies it. Rows added to or removed from the CSV re-resolve nothing. A `jitx.test.TestCase` run uses the same mode and also writes the lockfile. A part pinned from `ideal` stays `IDEAL-` after the real part is approved, and a part stays pinned after its row is removed. Set the mode under `[tool.jitx.parts]` with `lock-mode`: `read-write` (default), `read`, `check`, `replay` or `off`.

## Before a design counts as done

1. Remove `"ideal"` from `chain`. The changed chain re-resolves every query, so `jitx build <design>` fails with `no part found for ...` on each value without an approved row. Ask the user for each approved part. Changing a value instead needs the user's sign-off, and anything the value sets is recomputed (a divider's VOUT against the rail's requirement). Repeat until it prints `status: ok`. A part whose `case` differs from `ideal`'s default changes the footprint, so run this gate before layout verification.
2. Run `jitx design export parts-check <design> --fail all`. It re-resolves every query against the chain and compares it with the build, so it fails (`N differs`) on a pinned part whose row has since changed or gone. Exit 0 is the pass.

Do not restore `ideal` afterwards: the old chain's `IDEAL-` pins come back with it. A design going back into work keeps the csv-only chain, or deletes `parts.lock.json` before restoring `ideal`.

## Connecting an internal parts database

The chain is pluggable. To serve parts from an internal database or a procurement system:

- Implement `jitxlib.parts.Provider`. The installed `jitxlib/parts/providers/csv_parts.py` is the reference implementation: its vocabulary comes from the data, so what is left in the file is the provider protocol.
- Its `config()` is part of the lock key. It must cover everything that changes which part is chosen (a file path, a base URL) and nothing machine-specific, or the lock never matches on another machine or in CI.
- Register it in the `jitxlib-parts-provider` entry-point group so a chain can name it. A chain string `name:argument` selects the entry point by `name` and passes `argument` as the provider's single constructor argument:

  ```toml
  [project.entry-points."jitxlib-parts-provider"]
  acme = "acme_parts:AcmeParts"
  ```

  Without the registration, naming it in `chain` raises `ProviderUnavailable: chain names provider ..., which is not installed`.
- An organization that wants every project on the same chain publishes it through `jitxlib-parts-policy` (level 4 above) instead of each project listing it.
- In code, a `PartSource([...])` of provider instances can be assigned as a `Design`'s `parts` attribute or entered with `with`, which suits a test or a one-off variant.
- `Remapped` wraps a provider whose attribute names differ from the ones the design's queries use.
