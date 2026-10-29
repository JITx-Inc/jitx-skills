---
name: jitx-component-modeler
description: "Create JITX Python component code from datasheets, KiCad footprints, vendor pin files, or user specifications. ALWAYS use this skill when user asks to \"create a component\", \"model a part\", \"generate a component\", \"add a component\", or \"make a JITX component\" - even without a datasheet. Also triggers on part numbers (NE555, LM1117, RP2040) and package types (SOIC, QFN, BGA, SON, SOT). Covers JITX generators for standard packages, a vendor's KiCad footprint read directly for non-standard ones, multi-unit symbols, thermal pads, pin mappings, and datasheet checks with jitx.test.TestCase. Also covers generating from a vendor's machine-readable pinout file rather than a drawing (\"generate the FPGA from the pin file\", \"parse the package pinout file\", \"model this 1000-ball BGA\"): parse-don't-transcribe, reconcile the ball inventory before emitting, and a committed generator with a regenerate-and-diff check. For choosing and placing an ordinary queried passive, use jitx-circuit-builder instead."
---

# JITX Component Generation Skill

A component task is not complete until the [Component completeness check — run before calling it done](#component-completeness-check--run-before-calling-it-done) block is filled row by row in `COMPLETION.md` next to the components, under the `Checks run` field of the task acceptance block in `jitx-project-builder/references/completion-blocks.md`. A block only in chat is not the block.

## Route before reading detail

| Condition | Open |
|---|---|
| Any component task: sources, package and generator choice, KiCad import, the class and symbol, BGAs, tests, build and report. | [references/component-guide.md](references/component-guide.md) |
| The vendor supplied a machine-readable pinout or ball-map file. | [references/pin-file-generation.md](references/pin-file-generation.md) |

Before writing code, read every matching row's file, and record the rows matched and files read in the `References opened` row. A reference file missing from disk is a blocker, never replaced by remembered API details.

## Universal source gate

Never write dimensions, pin labels, pad assignments or an MPN from memory. The source is the manufacturer's current datasheet or package document; a manufacturer pin file is authority for names, balls and banks, never geometry; named sourcing-channel data is secondary evidence the datasheet outranks; failing those, ask the user. With no source, a real component is blocked unless the user explicitly authorizes a non-MPN generic placeholder, recorded under `Notes`. The full ladder is in [component-guide.md](references/component-guide.md#sources).

A part fact typed into the request (pin list, package, pin count) is a claim, not a source: check it against the document and send any disagreement back to the user before building.

Before recording a source as unreachable, try the manufacturer URL, the named sourcing channel and the local project directories.

When no document states an orderable MPN, ask the user while device and package are being confirmed. A device string or package name is not an MPN, and no test or build catches a fabricated one; see [component-guide.md](references/component-guide.md#mpn-identity).

Never read a full datasheet PDF. Save it, check that its bytes begin `%PDF-`, locate pages with `scripts/extract_pages.py`, and read only the extract; if extraction fails or finds nothing relevant, stop and report it. Cite by figure or table caption first, then figure number, edition and page.

## Universal construction gate

Output goes under `components/`, in a category subdirectory where the project uses them, as `<manufacturer>_<mpn>.py`: lowercase manufacturer, MPN as the manufacturer prints it, underscores for separators.

Refuse to proceed with:

- guessed, approximate, typical or deferred geometry for a real MPN;
- one `Port` for several physical pins, or several ports for alternate functions of one pin;
- numbered sibling attributes plus `getattr` instead of an indexed list (`GPIO = [Port() for _ in range(N)]`);
- a second stored attribute holding ports the component owns; groupings are methods returning fresh records;
- pads placed from a drawing for a package no generator expresses, when the vendor publishes a KiCad footprint;
- transcribing or sampling a machine-readable pin file, or ball-reference strings as the runtime data model;
- invented constructor arguments, class-scope `self`, or a JITX class declared inside a function, method or active instantiation context;
- a silent package-variant choice when the source covers more than one.

Every physical pin or ball, NC-with-pad and thermal pad included, gets its own port; contacts sharing one land share one port. The symbol carries every port. A port on several pads (ground plus the thermal pad), a port on no pad, or a declaration order that is not pad order requires an explicit `PadMapping`; an unmapped thermal pad builds unconnected with no error.

Library and generator defaults are inputs to verify: check each one relied on against the source wherever the source speaks, and override from the source where they disagree. Density level is one (installed default `B`): set `DensityLevel` (`jitxlib.landpatterns.ipc`) explicitly or record that the default matches the source.

For a pin file, emit no component code until the parse reconciles and the user approves the inventory, and start no circuit wrapper until the user approves the mapping sample; see [pin-file-generation.md](references/pin-file-generation.md#the-human-gates).

## Verification and halt

After code exists, in order:

1. Tests that construct components subclass `jitx.test.TestCase`; pure helper tests may use `unittest.TestCase`. Every package variant gets a pad-count check by `jitx.inspect.visit(lp, Pad)`; until it runs, verification stops. The snippet and other assertions: [component-guide.md](references/component-guide.md#testing-and-build).
2. Run the test suite, and `pyright` on every Python file left in the output. Tests assert metadata, pin and pad counts, `.value` unset, and each relied-on default or imported footprint entry against the source.
3. Run `jitx find`, take its printed build target verbatim, then build in the available virtual environment.
4. Write the task acceptance block from `jitx-project-builder`, with the complete `Component check` below embedded under `Checks run`, into `COMPLETION.md` or the project's existing equivalent.

**Halt:** no filled block, no "done". Any non-clean type check, failing test, failed build, unrun available check, missing source, or unresolved row forces `Verdict: open items`. `Verdict: complete` is invalid until every row closes.

Then offer the datasheet application circuit and, on yes, invoke `jitx-circuit-builder` with the component class's import path and the figure caption.

## Component completeness check — run before calling it done

Fill each row with its evidence (page, table or figure, then class or attribute).

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
Identity: <class name> — mpn <literal>; manufacturer,
        refdes prefix and datasheet URL set on the class
Pins: <N> ports / <N> physical pins or pads on the drawing — every power, ground,
        NC-with-pad and thermal pad present; names from the datasheet's own pin table
Landpattern: <generator + args> from <page/figure>; <N> pads; dimensions transcribed —
        body <L/D> <W/E> <H/A>, <pitch | n/a>, lead/termination <length> <width>,
        each cited; Toleranced from the drawing's min/max, not nominal-only
Library defaults: generator/table defaults relied on: <list | none> — each checked
        against the source where the source speaks to it; agreements <list>,
        overrides <item + reason | none>; defaults relied on because the source
        publishes nothing to check against: <list per dimension | none>
        Density level: <A | B | C> — <what the source asks for, or "no preference stated">;
        installed default is <level> — <set explicitly | default already matches>
Value / BOM: .value unset — pinned by a test asserting it is unset
No-field walk: datasheet-stated facts with no JITX field, recorded in the docstring: <list>
Provenance: values traceable to no datasheet page: NONE | <list + the labeled rule backing each>
Checks: pyright <clean | N errors>; pytest <N passed | not run: <reason>>;
        build <status: ok via <command> | not run: <reason>>
Verdict: complete | open items: <list>
        Derived from every row above; an unavailable environment is an open item.
```

Rows whose label leaves the content open:

- Source: a page or figure per claim, not one URL for the component.
- Identity: where no document states an MPN, what was agreed with the user and what the value does and does not identify.
- Landpattern: dimensions from the mechanical drawing, not the overview page; a generator fallback or KiCad import goes here with its reason.
- Value / BOM: `n/a` needs a test asserting `value is None`; nothing else checks what the BOM prints.
