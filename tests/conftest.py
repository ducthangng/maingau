"""Shared pytest fixtures (Agent KG). Loading is cached, so every test module reuses one parse."""

from __future__ import annotations

import pytest

from nba.data import load_workbook
from nba.state import build_states


@pytest.fixture(scope="session")
def tables():
    return load_workbook()


@pytest.fixture(scope="session")
def states(tables):
    return build_states(tables)


@pytest.fixture(scope="session")
def policy(tables):
    from nba.kg.policy import load_policy

    return load_policy(catalog=tables["product_catalog"])


@pytest.fixture(scope="session")
def pop(tables):
    from nba.state import population

    return population(tables)


@pytest.fixture(scope="session")
def kg_all(states, policy, pop):
    """customer_id -> (signals, candidates, blocked, triage), computed once per test session."""
    from nba.kg.rules import generate_candidates
    from nba.kg.segments import triage
    from nba.kg.signals import extract_signals

    out = {}
    for cid, s in states.items():
        sig = extract_signals(s, policy)
        cands, blocked = generate_candidates(s, sig, policy, "sie")
        out[cid] = (sig, cands, blocked, triage(s, sig, policy, pop))
    return out
