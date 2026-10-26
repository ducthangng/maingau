"""One rulebook for every decision rule (python -m nba.rules --help).

`rules.yaml` is a working copy of kg/policy.yaml, config/kg.yaml, config/nba.yaml and config/learn.yaml
in one file. Edit it, run `diff` to see what changes for all 750 customers and whether every hard rule
still holds, then `apply` to write the edits back into the source files. The source files stay the
truth in git; rules.yaml is git-ignored.
"""
