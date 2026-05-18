# Provenance of `lbstanza/references/`

These reference docs are vendored into this skill bundle so an AI agent
working in this skill (typically while porting a JITX 3.x Stanza design to
4.x Python, or maintaining 3.x source) can grep / read them without a
network round-trip. Skill text in `lbstanza/SKILL.md` instructs the agent
to grep + read narrow windows rather than load whole files.

The originals are the LB Stanza language docs authored or maintained by
**Patrick S. Li** (the language's primary author). LB Stanza upstream
lives at <https://github.com/StanzaOrg/lbstanza>. Consult the upstream
repository for the canonical, latest version and for the license terms
that apply to the docs.

## Per-file origin

| File | Origin | Notes |
|---|---|---|
| `reference-manual.md` | Upstream LB Stanza Reference Manual — "Patrick Li, January 2019" header preserved at top of file. | Verbatim copy. ~5,273 lines. |
| `by-example.md` | Upstream "Stanza by Example" tutorial — "By Patrick S. Li" header preserved at top of file. | Verbatim copy. ~12,427 lines. |
| `build-system.md` | Upstream LB Stanza build-system documentation. | Verbatim copy. |
| `test-framework.md` | Upstream LB Stanza test-framework documentation. | Verbatim copy. |
| `cheatsheet.md` | **Skill-team derived.** Surface-syntax cheatsheet distilled from the reference manual and by-example. | Internal index. Verify edge cases against the upstream reference manual. |
| `idioms.md` | **Skill-team derived.** Idiomatic patterns extracted from "Stanza By Example." | Internal index. Verify edge cases against the upstream source. |

## Snapshot date

The verbatim files in this directory were captured before the lbstanza
skill was introduced (see commit history for `lbstanza/references/`).
Re-sync when the upstream changes by replacing each verbatim file with
the corresponding upstream version; the skill-team-derived files
(`cheatsheet.md`, `idioms.md`) should be re-checked against the new
upstream and updated for any drift.

## License

LB Stanza is open-source. The upstream license file at
<https://github.com/StanzaOrg/lbstanza> is the authoritative source —
consult it before redistributing these vendored docs outside this skill
bundle.
