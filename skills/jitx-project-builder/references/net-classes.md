# Net Class Taxonomy (Per-Design Table)

Some nets need their own physical rules: width, clearance, impedance,
keepout, return path, shield. Each design enumerates the classes of nets that
apply, one row per class, and expresses each as a tag on the nets plus
`design_constraint` rules on that tag in the Design's rule list. If no net
needs its own rule, record "no classes of nets" with a one-line reason.

The rule shapes, the rung each class takes on the priority ladder, and where
each value comes from are owned by the `jitx-layout-constraints` skill
([Defaults and classes](../../jitx-layout-constraints/SKILL.md#defaults-and-classes)).
Invoke that skill to write the table during Phase 3.

The Phase 3 to 3b transition confirms the table exists if the design has any
classes of nets; otherwise it confirms the explicit "no classes of nets"
statement.
