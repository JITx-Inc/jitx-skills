# Layout Constraints Checklist

Run after the design-rule set is written and the design builds. Use with the
`jitx-layout-constraints` skill.

### Rule mechanics
- [ ] Every clearance is a two-condition rule; no other effect is on a two-condition rule
- [ ] Every override carries a priority above the rule it overrides, and the ladder is written in a comment where the rules are declared
- [ ] Every rule is a structural attribute reachable from the Design (no module-level rules, no dropped locals)
- [ ] Board-wide rules are on the Design; rules about one circuit's objects (escape routes, puddles, fence pours) are attributes of that circuit
- [ ] Tag classes are declared at module scope; builtin tags are used only as conditions
- [ ] No rule other than a routing structure is looser than a `FabricationConstraints` floor (the floor would override it silently); a routing structure whose width or pair gap is below a floor (a structure overrides the floors) is listed as an open item for the user

### Defaults and classes
- [ ] The board defaults and the classes of nets the design needs are on the Design, or the acceptance block records "no board defaults" or "no classes of nets" with a reason
- [ ] Every width, clearance and gap has its source on the same line: a fab-sheet row, a value in the prompt, a cited datasheet or standard, or a derivation from one of those with its arithmetic; a value with none is an open item

### Power, pours, fanout
- [ ] Power is routed as traces under its tag's width; a pour on a rail has its reason on the line that creates it
- [ ] Ground pour on its own return layer; no reliance on a top-side ground fill
- [ ] Heavy-copper layers selected per index (`OnLayer(n)`), not `OnLayer.internal()`
- [ ] Every class width that cannot fit a package pad has an escape tag, escape rules above the class rule, and a control point at the transition; no `RoutingStructure.NeckDown` used for this

### After build
- [ ] Widths checked on the captured design per tagged net and layer
- [ ] Minimum clearance between the nets each two-condition rule names measured at or above the rule
- [ ] `route.traces` non-empty for every authored escape route
- [ ] Anything a missing runtime left unverified is named as an open item
