# Layout Constraints Checklist

Run after the design-rule set is written and the design builds. Use with the
`jitx-layout-constraints` skill.

### Rule mechanics
- [ ] Every clearance is a two-condition rule; no other effect is on a two-condition rule
- [ ] Every override carries a priority above the rule it overrides, and the ladder is written in a comment where the rules are declared
- [ ] Every rule is a structural attribute reachable from the Design (no module-level rules, no dropped locals)
- [ ] Board-wide rules are on the Design; rules about one circuit's objects (escape routes, puddles, fence pours) are attributes of that circuit
- [ ] Tag classes are declared at module scope; builtin tags are used only as conditions
- [ ] No rule is looser than a `FabricationConstraints` floor (the floor would override it silently)

### Defaults and classes
- [ ] The four board-wide defaults are present on the Design: trace width, copper clearance, pad thermal relief, wider power and ground
- [ ] Net-class table present, or the explicit "no non-default net classes" line with a reason
- [ ] Every width and clearance has its source on the same line: a fab field, a cited source, or a labeled skill default

### Power, pours, fanout, decoupling
- [ ] Power is routed as traces at a stated tier; no power distribution by copper fill
- [ ] Ground pour on its own return layer; no reliance on a top-side ground fill
- [ ] Heavy-copper layers selected per index (`OnLayer(n)`), not `OnLayer.internal()`
- [ ] Every class width that cannot fit a package pad has an escape tag, escape rules above the class rule, and a control point at the transition; no `RoutingStructure.NeckDown` used for this
- [ ] Decoupling follows the datasheet where it specifies; otherwise fewest, largest MLCCs with the lowest loop inductance, no per-pin value stack

### After build
- [ ] Widths checked on the captured design per tagged net and layer
- [ ] Minimum clearance between the nets each two-condition rule names measured at or above the rule
- [ ] `route.traces` non-empty for every authored escape route
- [ ] Anything a missing runtime left unverified is named as an open item
