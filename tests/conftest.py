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
