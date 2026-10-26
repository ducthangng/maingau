"""Feedback loop: measure each pattern against its control group, record what works, and open a
fix case for a human (with an AI brief) when something does not (python -m nba.learn --help).

The loop never changes a hard rule and never edits a rule on its own. A fix only takes effect when a
reviewer applies it; it is then an approved p override in config/nba.yaml with the case ID.
"""
