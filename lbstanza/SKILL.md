---
name: lbstanza
description: This skill should be used when the user asks to write, read, debug, or explain LB Stanza (lbstanza) code — including Stanza syntax, idioms, the standard library (Core, Math, Collections, Reader, Macro Utilities), packages and `.proj` files, the test framework (`deftest`), LoStanza/FFI, multimethods, sequences, parametric types, generators, coroutines, exception handling, and macros. Triggers on `.stanza` files, the keywords `defn`/`defmulti`/`defmethod`/`deftype`/`defstruct`/`defpackage`, and phrases like "write Stanza", "Stanza function", "Stanza package", "Stanza test", "lbstanza", or "LoStanza".
---

# LB Stanza Skill

Write, read, debug, and explain LB Stanza (lbstanza) programs.

## Mental Model

Stanza is an **optionally-typed, natively-compiled** functional language. Source is parsed from an indentation-sensitive surface syntax into s-expressions that core macros expand into a small set of primitive forms.

Key features:
- Multimethods (`defmulti` / `defmethod`) for open polymorphism.
- Parametric types with captured-type arguments (`?T`).
- Lazy sequences (`Seq`, `Seqable`) and a rich sequence library.
- Indentation-sensitive blocks with `:` introducing a body.
- Labeled scopes for non-local exit; `attempt`/`fail` for control-flow backtracking; `try`/`catch` for genuine exceptions.
- A LoStanza sublanguage for FFI and low-level work, sharing surface syntax.

**CRITICAL:** Stanza compiles to native code (AOT). **There is no JVM target.** Never describe Stanza as JVM-targeted, JVM-compiled, or running on a JVM. If you find a stale doc claiming otherwise (including any CLAUDE.md), it is wrong. (The bundled docs describe native compilation but don't pin the exact backend — historically Stanza has emitted assembly and linked via GCC, but treat anything beyond "native, AOT, no JVM" as compiler-internals territory outside this skill's scope.)

## When to Use This Skill

Activate on any of:
- The user is editing or asking about a `.stanza` file.
- The user mentions Stanza/lbstanza/LoStanza by name.
- The user uses Stanza keywords: `defpackage`, `defn`, `defmulti`, `defmethod`, `deftype`, `defstruct`, `val`, `var`, `lostanza`.
- The user asks to write a Stanza function, package, test, multimethod, generator, coroutine, macro, or FFI binding.
- The user asks how to structure a Stanza project, write a `.proj` file, or run Stanza tests.

Do NOT activate for:
- Pure JITPCB design questions (use the `jitx` skills instead — though Stanza syntax help inside JITPCB code is fine).
- Questions about the Stanza compiler internals, IR, register allocator, or VM design (the bundled docs cover only the surface language).

## Reference Index

All bundled docs live in `references/` next to this file. Use grep/Read on these — do NOT load whole files into context unless necessary.

**Most porters need only `porter-cheatsheet.md` (~400 lines).** It's the minimum Stanza surface for reading a 3.x JITX design and translating to 4.x Python, with cross-links to the Python equivalents. Reach for the big files only when the cheatsheet doesn't cover what you hit.

| Question type | First file | Backup |
|---|---|---|
| **Porting context — "what does this Stanza syntax mean and where is the 4.x equivalent?"** | **`references/porter-cheatsheet.md`** | `references/cheatsheet.md` / `reference-manual.md` |
| Surface syntax (general, not port-specific) | `references/cheatsheet.md` | `references/reference-manual.md` (Ch. 1 Core Macros) |
| Idiomatic patterns / "how should I write this" | `references/idioms.md` | `references/by-example.md` |
| Stdlib API lookup (Core/Math/Collections/Reader/Macro Utils) | `references/reference-manual.md` (Ch. 2–6) | — |
| Worked tutorial examples | `references/by-example.md` | — |
| Package layout, `.proj` files, build targets | `references/build-system.md` | — |
| Tests (`deftest`, tags, runners) | `references/test-framework.md` | — |
| LoStanza / FFI to C | `references/by-example.md` (final chapter) | `references/reference-manual.md` |

Upstream provenance for each reference file (which are verbatim copies of
Patrick Li's LB Stanza docs and which are skill-team-derived indices) is
recorded in `references/NOTICE.md`.

## How to Use the References

The reference docs are large (`reference-manual.md` ~5,300 lines, `by-example.md` ~12,400 lines). Pick the smallest tool for the question:

1. **Specific symbol or API lookup** — grep first.
   ```
   rg -n "^### defmulti\b" references/reference-manual.md
   rg -n "\bgenerate\b"   references/reference-manual.md
   ```
   Then `Read` the matched lines with a small offset/limit window.

2. **Routine syntax questions in a porting context** — read `porter-cheatsheet.md` (short, port-focused, cross-links to Python equivalents). For Stanza language questions outside a port, `cheatsheet.md` is the broader reference; only descend into `reference-manual.md` if neither cheatsheet covers it.

3. **"How should I write X idiomatically"** — read the relevant section of `idioms.md` first; consult `by-example.md` only if you need a longer worked example.

4. **Multi-section research** (e.g. "survey all coroutine and generator APIs", "summarize the type system chapter"): spawn an Explore subagent and point it at the relevant chapters. Don't pull the whole big files into the main thread.

5. **Always verify symbols exist** before recommending them. If you're not sure a function or type is real, grep the reference manual first. Hallucinating stdlib APIs is the most common failure mode here.

## Conventions When Writing Stanza

- **Multimethods over type-dispatch chains.** Reach for `defmulti`/`defmethod` before `match` on concrete types.
- **Sequences over imperative loops.** Pipeline `map`/`filter`/`seq-cat`/`reduce` on a `Seq` before falling back to `while` with mutation.
- **`for x in xs do`** for eager side-effects; **`for x in xs seq`** to lazily build a sequence.
- **`val` by default.** Use `var` only when rebinding is required.
- **Immutable structures by default.** Reach for `List`/`Tuple` before `Vector`/`HashTable`.
- **Labeled scopes** (`label<T>: ...`) for non-local exit instead of break flags.
- **`attempt`/`fail`/`else`** for parser-style backtracking; `try`/`catch` is for exceptional I/O / external errors, not for routine control flow.
- **Every reusable file** opens with `defpackage`. Keep the public surface explicit (`public` markers); internal helpers stay private.
- **Indentation-sensitive blocks**: a body introduced by `:` must be indented consistently. Misalignment is a syntax error, not a warning.
- **LoStanza only at the FFI boundary.** Convert to/from HiStanza values immediately at the edge; keep core logic in HiStanza.

## Anti-patterns

- ❌ Describing Stanza as "JVM-compiled" or "JVM-targeted" — it is natively compiled (via C).
- ❌ Recommending stdlib symbols without verifying them in `references/reference-manual.md`.
- ❌ Inventing syntax (`switch{}`, `with: only(...)`, declaration-attached `where`, etc.) that the bundled docs don't show. If a construct isn't in the cheatsheet or the reference manual, assume it doesn't exist until you've confirmed.
- ❌ Reading entire reference files into context when grep + a small `Read` window would do.
- ❌ Using `match` to dispatch on type when a `defmulti` group already exists for that type — extend the multi instead.
- ❌ Using `try`/`catch` for ordinary control flow — use `attempt`/`fail`/`else` or `label`/`return` instead.

## Writing a Stanza Test

Tests are `.test.stanza` files using `deftest`. See `references/test-framework.md`. The standard runner pattern in this repo is:

```
python jitpcb/tests/run-all-tests.py --path tests/<file-or-dir>
```

The test binaries must already be built (`./scripts/make.bash all-with-tests`).

## Writing a `.proj` File

See `references/build-system.md` for the syntax (`package`, `import-when`, `requires`, conditional imports, foreign-C deps, build targets).
