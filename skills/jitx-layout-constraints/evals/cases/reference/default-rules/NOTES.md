# Default-rule scope reference notes

## Result

A width rule declared as an attribute of one child `Circuit` applies board wide,
not only inside that child. The sibling's route on the tagged `SPAN` net realizes
at 0.3000 mm, the child-declared value, not the 0.12 mm board default.

The scope is the whole design, not just the nets that reach the owning child. A
control probe adds two more children: a route on an untagged net realizes at
0.12 mm, confirming the board default is live, and a route on a second
`SpanningTag` net that never connects to the rule owner also realizes at
0.30 mm.

Measured with py-jitx 4.4.0rc5.dev2, runtime 4.4.0-rc.9, substrate
`JLC04161H_7628`.

## What the probe measures

The four board defaults sit on the `Design`. The tagged width rule sits only on
`RuleOwner`, a child `Circuit`, built with
`design_constraint(SpanningTag(), priority=2).trace_width(0.30)`. The named net
`SPAN` joins `RuleOwner.bus` to `Sibling.bus`, so the tagged net spans both
children. `Sibling` declares no rule of its own. The realized width of the
sibling's route is the answer.

## Commands and real output

Run from the project root. The project holds the two reference directories as
packages plus `scripts/layout_checks.py`; the interpreter is the project venv.

```text
$ jitx build <project>.default_rules.design.DefaultRulesDesign
Running design <project>.default_rules.design.DefaultRulesDesign...
Saving stable design and reference designator table
<project>.default_rules.design.DefaultRulesDesign:
  design: <project>.default_rules.design.DefaultRulesDesign
  status: ok

$ python3 -m <project>.default_rules.check
child-rule scope probe, result classified from captured copper
PASS routes: measured=0 expected=0 checked=2 unrealized=0
PASS width-rule-owner: measured=0.3000 expected=0.3000 tol=0.0010 mm
PASS child-rule-scope: measured=0.3000 expected=none observed=board-wide
summary: checks=3 failures=0
exit=0
```

`observed=board-wide` is the check script's own classification: the sibling's
realized width matched `CHILD_RULE_WIDTH` (0.30 mm) within the 0.001 mm
tolerance, not `DEFAULT_TRACE_WIDTH` (0.12 mm).

## Control probe

`board-wide` from a single sibling reading 0.30 mm is consistent with two
different scopes: the design, or the set of nets that touch the owning child. A
side probe in the same project separates them. It reuses `RoutedChild`,
`RuleOwner`, and `Sibling` unchanged and adds two more children under the same
top circuit: `untagged`, whose net carries no tag, and `disjoint`, whose net
carries `SpanningTag` but connects to nothing in `RuleOwner`.

```text
  rule_owner (tagged SPAN, owns rule): widths=[0.3]
  sibling (tagged SPAN, no rule): widths=[0.3]
  untagged (net PLAIN, no tag): widths=[0.12]
  disjoint (tagged SPAN, never touches rule_owner): widths=[0.3]
```

The 0.12 mm on `untagged` rules out the reading that 0.30 mm arrives from
somewhere other than the child's rule. The 0.30 mm on `disjoint` rules out the
narrower scope: where a rule object is stored does not restrict which copper it
governs. A `Circuit` is a container for the rule, not a scope for it.

## Changes recorded during the run

None. The design builds, the routes realize, and the check script settles the
question as written.

One observation worth carrying forward, which needed no change here: the route
sketch `[(left_x, 0.0), (right_x, 0.0)]` in `RoutedChild` is inert on this
runtime. Its start point is not the pad center, because the `SMT("0402")`
landpattern stacks its two pads along Y and `route_pad` sits about 0.51 mm above
the child origin. The realized route still runs from the pad to the route point,
so the widths measured above are unaffected. See the `net-net-clearance` notes
for the measured behavior of sketch turns, which are dropped by this runtime.

`scripts/layout_checks.py` was not changed. Its own unit tests pass:

```text
$ python3 -m pytest scripts/test_layout_checks.py -q
8 passed in 0.04s
```

## Later run: Rerun after check rewrite

Rerun alongside the `net-net-clearance` check rewrite, which did not touch this
case. Same environment: py-jitx 4.4.0rc5.dev2, runtime 4.4.0-rc.9,
substrate `JLC04161H_7628`, run from the project root with the project venv
interpreter.

```text
$ python3 -m <project>.default_rules.check
child-rule scope probe, result classified from captured copper
PASS routes: measured=0 expected=0 checked=2 unrealized=0
PASS width-rule-owner: measured=0.3000 expected=0.3000 tol=0.0010 mm
PASS child-rule-scope: measured=0.3000 expected=none observed=board-wide
summary: checks=3 failures=0
```

Exit code: 0. Nothing was trimmed; that is the whole output.
