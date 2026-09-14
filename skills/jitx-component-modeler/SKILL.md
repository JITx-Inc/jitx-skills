---
name: jitx-component-modeler
description: "Create JITX Python component code from datasheets, KiCad footprints, or user specifications. ALWAYS use this skill when user asks to \"create a component\", \"model a part\", \"generate a component\", \"add a component\", or \"make a JITX component\" - even without a datasheet. Also triggers on part numbers (NE555, LM1117, RP2040, etc.), package types (SOIC, QFN, BGA, SON, SOT), and two-terminal chip sizes (0402, 0603, 2512). Supports user-provided data, JITX generators for standard packages, and optional LCSC/EasyEDA fallback for non-standard footprints. Supports multi-unit symbols, thermal pads, and complex pin mappings. Also covers parameterized catalog families — one class standing in for a manufacturer's whole series (chip resistors, MLCCs) with the part number computed per instance and no parts-database query — and verifying a component against its datasheet with jitx.test.TestCase. Also covers generating a component from a vendor's machine-readable package pinout file rather than a drawing (\"generate the FPGA from the pin file\", \"parse the package pinout file\", \"model this 1000-ball BGA\"): parse-don't-transcribe, reconcile the ball inventory before emitting, and a committed generator with a regenerate-and-diff check. For choosing and placing an ordinary queried passive, use jitx-circuit-builder instead."
---

# JITX Component Generation Skill

A JITX component binds five claims into one class: BOM identity, one `Port` per physical pin, a source-derived land pattern, a readable symbol, and any explicit port-to-pad mapping. The modeling job is to turn manufacturer evidence into those claims without adding a plausible number or name that the evidence never states.

A component task is **not complete** until the **Component completeness check** block (near the end of this skill) is filled out, row by row, **as a written artifact alongside the code** — a `COMPLETION.md` next to the components, or the equivalent your project already uses. Prose that paraphrases some of its rows is not the block, and neither is a filled block that exists only in the chat you are having: the next person to open the directory, human or agent, sees the files. A block nobody can find later did not happen. It is the component-specific expansion of the base `jitx` skill's task-acceptance block, not a rival to it — embed it under that block's `Checks run` field rather than producing two competing completion artifacts. No filled block, no "done".

## Route before reading detail

The agent evaluates the conditions before writing code. It opens every matching row and does not read references whose conditions do not match.

| Condition the agent can evaluate now | Open |
|---|---|
| The evidence source (datasheet, package drawing, URL, sourcing-channel record, KiCad footprint, user artifact) or the package generator is not yet settled. | [references/source-and-package-selection.md](references/source-and-package-selection.md) |
| The source and package are known, and the agent is about to write the component class, symbol, generator call, multi-unit partition, or explicit `PadMapping`. | [references/component-code-patterns.md](references/component-code-patterns.md) |
| The body is a rectangular two-terminal chip, or one class must represent a manufacturer's catalog family and compute the MPN per instance. | [references/parameterized-families.md](references/parameterized-families.md) |
| The vendor supplied a machine-readable pinout or ball-map file rather than a drawing to transcribe. | [references/pin-file-generation.md](references/pin-file-generation.md) |
| The selected package is a SOIC, SOT23, SON, QFN, QFP or BGA, or another standard-generator package whose pad numbering, mapping or thermal pad the agent has not built before. The file works those six; any BGA also needs its BGA-specific notes. | [references/package-examples.md](references/package-examples.md) |
| Code exists and the component still has to be tested, built and reported, or a typical application circuit must be captured. This row matches every task that reaches verification. | [references/verification-and-application.md](references/verification-and-application.md) |

The agent reads every matched reference before writing code and records the rows matched and the files read in the `References opened` row of the Component check. A reference file absent from disk is reported as a blocker, never replaced by remembered API details.

## Universal source gate

The base `jitx` skill handles environment setup and runs first.

**The agent does not write dimensions, pin labels, pad assignments, or an MPN from memory.** For a named part, it obtains the manufacturer's current datasheet or package document, uses a manufacturer machine-readable pin file for names, balls, and banks only, uses named sourcing-channel data as secondary evidence, or asks the user. Datasheet evidence outranks channel evidence where they conflict. Geometry still comes from the package document when a pin file exists.

**A user's typed description is a claim, not a source.** A datasheet PDF, a package
drawing, a vendor pin file or a `.kicad_mod` the user hands over is evidence. A pin list,
a package name or a pin count typed into the request is a transcription to verify against
the manufacturer document, not to implement. Where they disagree, the document wins and
the disagreement goes back to the user before anything is built: they may have named the
wrong part, package variant or revision, and which it is changes what they want.

**"The source is unavailable" is a conclusion that needs evidence.** Before recording a
source as unreachable, try the manufacturer URL, the named sourcing channel and the local
project directories; a statement in the request that no datasheet exists is a belief about
the environment, not a fact about it. If a probe succeeds, the source gate applies as
normal. If every probe fails, the completion artifact records what was tried and what each
attempt returned, so a reader can tell an unreachable source from an unattempted one.

A real component with no source is blocked before land-pattern or pin code is written. The only exception is an explicitly authorized non-MPN generic placeholder; the completion artifact records that authorization under `Notes`. A parameterized family may compute its MPN from the source's ordering grammar, but every table and range still traces to that source and a generated MPN reproduces its worked example.

When no document states an orderable MPN, the identity gate asks the user while device and package are being confirmed. A device string or package name does not become an MPN. The agreed value records what it does and does not identify. No test or build catches a fabricated MPN, so component generation does not proceed past the identity gate without that answer.

The agent never reads a full datasheet PDF. It saves the PDF locally or in the project's gitignored source scratch area, verifies that its bytes begin `%PDF-`, locates relevant pages with `scripts/extract_pages.py`, and reads only the extract. A manufacturer URL that times out is not silently replaced with an aggregator copy. Citations use the figure or table caption as the primary key, then figure number, edition, and page.

A `Component check` whose `Source reached by` or `References opened` row is unset, or whose `Probes` row is `n/a` while no source was reached, is not a completed check: the component returns for rework rather than being accepted. A recorded disagreement between a user-typed fact and the document blocks acceptance until the user rules on it, because implementing either reading silently is how the wrong part ships looking finished.

If `extract_pages.py` exits non-zero or no relevant pages are found, the source gate remains closed and component code does not start. The agent reports the failed extraction or asks for the required pages.

## Universal construction gate

All component output lives under `components/`, with a category subdirectory when the project uses them and filenames of the form `<manufacturer>_<mpn>.py` in lowercase with underscores.

The construction step refuses to proceed with any of these patterns:

- guessed, approximate, typical, or deferred geometry for a real MPN;
- one representative `Port` standing in for several physical pins, or separate ports for alternate functions of one physical pin;
- numbered sibling attributes plus `getattr`, instead of an indexed list such as `GPIO = [Port() for _ in range(N)]`;
- a second stored attribute containing ports the component already owns; structural groupings are methods returning fresh records;
- hand-crafted pad positions for a non-standard package when a sourced KiCad footprint can be converted;
- transcribing or sampling a supplied machine-readable pin file, or making ball-reference strings the runtime data model;
- invented constructor arguments, class-scope `self`, or a JITX class declared inside a function, method, or active instantiation context;
- a silent package-variant choice when the source covers more than one variant.

Before tests begin, the component has manufacturer, MPN or user-approved identity, datasheet URL, reference-designator prefix, one port for every physical pin or ball including NC-with-pad and a thermal pad, a symbol containing every port, and a land pattern from cited toleranced dimensions. Automatic declaration-order mapping is allowed only when declaration order is pad order. Thermal pads, shared pads, out-of-order declarations, or any other mismatch require explicit `PadMapping`.

Library and generator defaults are inputs to verify, not authority. The construction gate records each relied-on default, including density level, checks it against the source wherever the source speaks, and overrides from the source when they disagree.

For a machine-readable pin file, no component code is emitted until the parsed row count, unique balls, decoded grid, source total, and a non-overlapping inventory reconcile and the user approves the report. The circuit wrapper does not start until the later ball-to-coordinate-to-port-to-pad sample is approved.

## Verification and halt

After code exists, the agent performs these steps in order:

1. Tests that construct components subclass `jitx.test.TestCase`; pure helper tests may use `unittest.TestCase`. Every package variant, and every family case size, gets a pad-count check. For a land pattern `lp`, count pads with the framework's structural traversal, which does not depend on the numbering scheme:

   ```python
   from jitx.inspect import visit
   from jitx.landpattern import Pad

   pad_count = sum(1 for _ in visit(lp, Pad))  # every pad the landpattern owns, thermal pads included
   ```

   Verified on jitx 4.4.0 inside a `SubstrateContext`: 8 for a generated SOIC-8, equal to `len(lp.p)`, and 441 for a generated 21 by 21 BGA, where `lp.p` does not exist. Do not count by enumerating attributes: `lp.p` exists only on the linearly numbered generators, a BGA's `AlphaDictNumbering` keeps its row dictionaries outside the instance namespace, and an attribute walk over one-letter row names returned 0 for that BGA. `lp.pads` is not an accessor either. Compare `pad_count` with the datasheet's pin count plus its thermal pads. If the count cannot be established for the package at hand, the pad-count row remains open and verification stops rather than recording an unchecked number.

2. Run the generated test suite and `pyright`. Tests also assert metadata, pin and pad counts, any ordering example or value encoder, the rendered `.value` or its deliberate absence, validation failures, and every relied-on library default.
3. Run `jitx find`, take its printed build target verbatim, then build in the available virtual environment. If no environment is present, stop and ask. JITX builds run sequentially, never in parallel against one project.
4. Write the task acceptance block from the base skill, with the complete `Component check` below embedded under `Checks run`, into `COMPLETION.md` or the project's existing equivalent.

**Halt:** no filled block, no "done". Any non-clean type check, failing test, failed build, unrun available check, missing source, or unresolved row forces `Verdict: open items`. `Verdict: complete` is invalid until every row closes.

## Component completeness check — run before calling it done

A component is judged by whether every value in it traces back to a source — the manufacturer's datasheet, a vendor mechanical drawing, or the user's explicit specification. The predictable failure mode is not a missing feature; it is a **plausible number sitting where it looks authoritative**: a termination band read off the wrong dimension line, a library-table default nobody checked, a value label the BOM will print that no test ever read. Before presenting a component as complete, fill this block in the completion summary, each row with its evidence (datasheet page / table / figure → class or attribute). A row you cannot check is an open item to name to the user — not a silent pass.

```
## Component check
Source: <manufacturer + document number + revision/date>; page/figure cited per claim below
        (+ channel evidence where the user named a sourcing channel)
        Source reached by: <fetched from <url> | supplied by the user as <path> | local <path>>
        Probes, when any source was recorded unreachable: <what was tried, and what each
        attempt returned> | n/a (a source was reached)
        User-typed facts checked against it: <each typed pin name, number, package or count,
        and whether the document confirms it> | none (the user typed no part facts)
        Disagreements found: NONE | <each, with the document's value, and confirmation that
        it went back to the user>
References opened: <routing rows matched -> reference files read | none matched>
Identity: <class name> — mpn <literal | computed from <scheme>, cross-checked against
        <the datasheet's ordering example or a real catalog part>>; manufacturer,
        refdes prefix and datasheet URL set on the class
Pins: <N> ports / <N> physical pins or pads on the drawing — every power, ground,
        NC-with-pad and thermal pad present; names from the datasheet's own pin table
Landpattern: <generator + args> from <page/figure>; <N> pads; dimensions transcribed —
        body <L/D> <W/E> <H/A>, <pitch | n/a>, lead/termination <length> <width>,
        each cited; Toleranced from the drawing's min/max, not nominal-only
Library defaults: generator/table defaults relied on: <list | none> — each checked
        against the source where the source speaks to it; agreements <list>,
        overrides <item + reason | none>; defaults relied on because the source
        publishes nothing to check against: <list per dimension | none>, and sizes
        excluded for having neither: <list | none>
        Density level: <A | B | C> — <what the source asks for, or "no preference stated">;
        installed default is <level> — <set explicitly | default already matches>
Value / BOM: .value renders as "<string>" — asserted in a test
        | n/a (<reason>) — AND pinned by a test asserting it is unset
No-field walk: datasheet-stated facts with no JITX field, recorded in the docstring: <list>
Provenance: values traceable to no datasheet page: NONE | <list + the labeled rule backing each>
Checks: pyright <clean | N errors>; pytest <N passed | not run: <reason>>;
        build <status: ok via <command> | not run: <reason>>
Verdict: complete | open items: <list>
        Derive this line from every row above. List each unresolved or unsupported
        claim, mismatch, and failed, skipped, or unavailable check as an open item.
        Any open item requires "open items"; "complete" is valid only when every
        row is supported and resolved and every check ran clean.
        An unavailable environment is an open item, not an exemption.
```

Row-by-row intent — the *why*, so the block stays evidence rather than ceremony:

- **Source** — a page or figure per claim, not one URL for the whole component. "Datasheet (from memory)" and "typical dimensions" are invalid for a real MPN; see [source-and-package-selection.md](references/source-and-package-selection.md#no-fabrication--source-authority-for-geometry-and-pinout).
- **Identity** — a part number is a claim about the manufacturer's numbering scheme. Where it is a literal from the ordering table, cite that table. Where the class *computes* it, the only thing that tests the claim is reproducing a part number the manufacturer itself printed — one cross-check per scheme. Where **no source document states one** — which happens for parts whose ground truth is a pin file and a packaging manual — this row records what was agreed with the user and what the value does and does not identify. It is never a value you chose yourself; see [source-and-package-selection.md](references/source-and-package-selection.md#when-no-document-states-an-mpn).
- **Pins** — count first, then compare row by row. A ports-vs-pads mismatch is the one component error the build reliably catches; everything below this row is the class of error the build does not catch.
- **Landpattern** — dimensions come from the mechanical drawing, not the overview page or the ordering table, and carry the drawing's tolerances. Where the generator could not express the package, the fallback and its reason belong here.
- **Library defaults** — a generator default is a convenience, not an authority. Wherever the datasheet publishes the same dimension, transcribe it anyway and check the two against each other; where they disagree, override from the datasheet and say so. The whole risk of taking a default is that nobody transcribed the number that would have caught a bad one. A default you took without checking is indistinguishable, in the output, from one you verified.

  **Defaults are not only dimensions.** The one that gets missed is **density level**, because it never appears as a number in your code; on 4.4.0 the installed default is `B` (`jitxlib/landpatterns/ipc.py`), earlier lines defaulted to `C`, and the choice moves real copper. Read what the source asks for, check what your installed `DensityLevelContext` defaults to, and either set the level explicitly (`DensityLevel` from `jitxlib.landpatterns.ipc`) or record in this row that the default already matches. The IPC-7351 levels and their fillets are in `references/parameterized-families.md`.
- **Value / BOM** — no build, type check or land-pattern test looks at the rendered value string. If this row says anything other than an asserted literal, nothing is checking what the BOM will print.

  **`n/a` is a claim, and it needs a test like any other.** For an IC there is often no value in the passive sense, and leaving `.value` unset is right — but "right" and "checked" are different, and an unpinned `n/a` is indistinguishable from having forgotten the field. Treat it exactly as you would any other deliberate absence: a component that deliberately ships without a land pattern gets a test asserting no land pattern is present, so a component that deliberately ships without a value gets a test asserting `value is None`. Then the decision cannot silently rot when someone later sets it.

  This row is the one most often filled by declaring rather than checking, which is why it says so twice.
- **Provenance** — if the datasheet doesn't state a value, ask the user or document the omission. Never invent a number to satisfy a type checker or complete a table; suppress the type error with a comment saying why instead.

## Output Format

A component task delivers files, not chat output:

1. The component module under `components/`, per the Output Location rule
2. Its test module, and the `jitx build` result
3. The `Component check` block, written alongside the code as the completion artifact
4. Assumptions, decisions, and items needing manual review, in that block's rows
5. An offer to capture the application circuit when the datasheet includes one
