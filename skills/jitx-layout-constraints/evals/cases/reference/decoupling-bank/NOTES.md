# Decoupling Bank Reference Notes

The reference uses a placeholder QFN with four pads (skill default: four pads).
It has two power pins and two ground pins (skill default: two of each). It is
not a production component model.

## Solver result

The reference reads the selected capacitor's courtyard, pad bounds, pad pitch,
and orientation before solving. Design instantiation did not run, so no
reference `Solution` or loop-area values were observed. The check script prints
those values only after a successful submit and capture.

## Commands and observed output

```text
$ python3 skills/jitx-layout-constraints/scripts/test_decoupling_solver.py
Ran 8 tests in 0.423s
OK

$ python3 -m pyright skills/jitx-layout-constraints/scripts/decoupling_solver.py skills/jitx-layout-constraints/evals/cases/reference/decoupling-bank/*.py
0 errors, 0 warnings, 0 informations

$ grep -n "[em dash]" skills/jitx-layout-constraints/references/decoupling.md skills/jitx-layout-constraints/scripts/decoupling_solver.py
<no output>
```

The deliberate-break check negated the loop-area return value. The suite
reported `FAILED (failures=1)` and
`-0.3625 not less than -0.6625` in
`test_loop_area_decreases_when_ic_pads_move_closer`. After restoring the
positive objective, the restored suite's final output is recorded above.

The required scratch-directory creation was attempted before build. The
managed filesystem returned `Operation not permitted`. The private task path
is omitted from this shipped file. Building inside the skill repository is
prohibited, so these commands were not run:

The runtime is unavailable for capture.

```text
$ jitx build decoupling_ref.design.DecouplingReference
NOT RUN: required scratch project directory could not be created

$ python3 -m decoupling_ref.check
NOT RUN: build and capture project was unavailable
```

No build, capture, queried placement, or route-realization result is claimed.
The build and check remain open verification items.
