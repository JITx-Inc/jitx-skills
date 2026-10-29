# Datasheet Specification Note Template

The datasheet extraction sub-agent writes one note per MPN at
`datasheets/<MPN>.spec.md`. Keep the completed note at or below 400 words and
cite the datasheet page for every extracted requirement.

```markdown
# <MPN> - <manufacturer>, <one-line function>

Source: `datasheets/<mpn>.pdf`; pages read: <list>
Package: <name>, <body dimensions>, thermal pad: <no | dimensions>
Absolute maxima that bind this design: <list with page cites>

## Pinout
| pin | name | type | note |
|-----|------|------|------|

## Required external components
| part | value | why | page |
|------|-------|-----|------|

## Layout, thermal and decoupling requirements
<from the datasheet, with page cites>

## Open questions
<anything the datasheet did not answer; empty is a valid answer>
```
