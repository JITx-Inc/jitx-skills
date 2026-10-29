# Net Class Taxonomy (Per-Design Table)

Some nets need non-default physical rules: width, clearance, impedance,
keepout, return path, shield. Each design enumerates the classes that apply,
one row per class, and expresses each as a tag plus `design_constraint`
rules at `priority >= 2` in the Design's rule list. If no net needs a
non-default rule, record "no non-default net classes" with a one-line
rationale.

The table (class, why it matters, width source, clearance source, rule
shape) and the derivation guidance are owned by the `jitx-layout-constraints`
skill, "Net classes: tag, derive, express". Invoke that skill to generate the
table during Phase 3.

The Phase 3 to 3b transition confirms the table exists if the design has any
non-default net classes; otherwise it confirms the explicit "no non-default
net classes" statement.
