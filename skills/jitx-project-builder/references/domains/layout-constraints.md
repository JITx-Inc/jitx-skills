# Layout Constraints Checklist

Run after the rules are written and the design builds. `jitx-layout-constraints` owns rule arity, priority, reachability, sources and verification. Add:

- [ ] Priority ladder written in a comment where the rules are declared.
- [ ] Board-wide rules on the Design; one circuit's rules (escapes, puddles, fence pours) on that circuit.
- [ ] Board defaults and classes of nets on the Design as `project-builder-flow.md` Phase 3 step 7 requires, or `no board defaults` / `no classes of nets` recorded in the block.
- [ ] Power routed as a trace is under its tag's width; supply rails and high-current paths are pours or planes (`jitx-interactive-layout` `general-pnr.md` "Power paths"). A rail's pour drawn in code carries its reason on the line that creates it.
- [ ] Every net that carries supply current has a width rule with its source, switch nodes and regulator outputs included; none is left at the default width.
- [ ] Ground pour on its own return layer, not a top-side fill.
- [ ] Heavy-copper layers selected by index (`OnLayer(n)`), not `OnLayer.internal()`.
- [ ] Escapes as separate routes with escape tags, never `RoutingStructure.NeckDown`.
- [ ] Anything a missing runtime left unverified named as an open item.
