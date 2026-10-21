"""The runner-output stand-ins under this directory hold test suites of their
own, which mutation_check.py runs with FAB_CSV set. The skill's self-tests
must not collect them."""

collect_ignore_glob = ["*/tests/*"]
